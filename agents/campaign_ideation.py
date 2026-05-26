"""
Campaign Ideation — Bridge skill giữa Strategy (A→Z) và Campaign Brief.

2 modes:
- PROPOSE: User chưa biết chạy gì → bot đề xuất 3 campaign options dựa vào
  synthesis + customer_insight + market_research.
- REFINE: User đã có idea → bot validate + refine với customer_insight + market_research.

Cả 2 đều output JSON structured để feed thẳng vào campaign_brief skill.
"""
import json
import logging
import re
from typing import Optional

import anthropic

from config import CLAUDE_SONNET_MODEL, ANTHROPIC_API_KEY
from storage.models import Session

logger = logging.getLogger(__name__)

client = anthropic.AsyncAnthropic(
    api_key=ANTHROPIC_API_KEY,
    timeout=120.0,
    max_retries=1,
)


PROPOSE_SYSTEM = """Bạn là Max — CMO AI giúp founder VN xác định campaign tiếp theo dựa trên Marketing Strategy đã có.

Dựa vào Strategy synthesis + Customer Insight + Market Research, đề xuất 3 campaign options KHẢ THI nhất.

Mỗi option phải:
- Bám sát SAVE Framework + SMART Goals trong synthesis
- Match với pain point từ Customer Insight (cite cụ thể)
- Tận dụng cơ hội từ Market Research (timing, seasonality, market gap)
- Khác biệt rõ ràng giữa 3 options — mỗi option giải quyết 1 mục tiêu chính khác nhau:
  Option 1: Acquisition / thu khách mới
  Option 2: Retention / upsell / tăng AOV
  Option 3: Brand / awareness / positioning

🔴 QUY TẮC TUYỆT ĐỐI — 4 trường SAU DO USER QUYẾT, KHÔNG ĐỀ XUẤT:
- ❌ KHÔNG đề xuất **Budget** (số tiền VND cụ thể)
- ❌ KHÔNG đề xuất **Team size** (số người)
- ❌ KHÔNG đề xuất **Start date** (ngày bắt đầu)
- ❌ KHÔNG đề xuất **% giảm giá** cụ thể trong offer

→ Trong `goal`, `duration`, `key_offer` chỉ đưa BENCHMARK định tính + range gợi ý:
- Goal: "Thu lead mới + chốt booking" (KHÔNG nói "500 booking, doanh thu 350tr" vì chưa biết budget)
- Duration: gợi ý số tuần (vd "4-6 tuần") — KHÔNG ngày cụ thể vì user chọn start date
- Key offer: mô tả CƠ CHẾ offer (combo / bundle / sample / quà tặng) — KHÔNG % giảm cụ thể

OUTPUT BẮT BUỘC dạng JSON (KHÔNG có text khác bên ngoài JSON):

```json
{
  "options": [
    {
      "name": "Tên campaign tiếng Việt, hook-y, ngắn (vd: 'Tặng Mình Trước', 'Cuối Năm Đẹp Hơn')",
      "goal": "Mục tiêu QUALITATIVE (vd: 'Acquisition khách mới ở segment phụ nữ 28-40 chưa từng dùng spa, build initial trust')",
      "key_offer": "MÔ TẢ cơ chế offer KHÔNG có % giảm cụ thể (vd: 'Combo trial 2-buổi + tặng kèm 1 sản phẩm sample. % giảm do sếp quyết')",
      "duration_suggestion": "Gợi ý độ dài (vd: '4-6 tuần để build awareness + chuyển đổi đợt đầu')",
      "target_segment": "Tệp target cụ thể (vd: 'Phụ nữ 28-40 sống Q1/Q3 HCM, đã follow page chưa book')",
      "why_fit": "2-3 câu: tại sao campaign này hợp với business sếp ở thời điểm này — CITE cụ thể từ synthesis/customer/market"
    },
    { ... option 2 ... },
    { ... option 3 ... }
  ]
}
```

QUY TẮC:
- KHÔNG bịa số liệu — chỉ dùng data đã có trong context
- 3 options đa dạng về mục tiêu (acquisition / retention / brand)
- Tên campaign tiếng Việt, không dùng tiếng Anh
- Output CHỈ JSON trong ```json``` block, KHÔNG có text giải thích bên ngoài
"""


REFINE_SYSTEM = """Bạn là Max — CMO AI validate idea campaign của founder VN.

User đã có ý tưởng campaign. Dựa vào Customer Insight + Market Research, hãy:
1. **Validate idea**: idea có hợp với customer pain point + market timing không?
2. **Refine**: đưa ra tên/goal/offer cụ thể hơn nếu user nói chung chung
3. **Cảnh báo risks** (nếu có): timing sai, segment không match, offer yếu, v.v.

🔴 QUY TẮC TUYỆT ĐỐI — 4 trường SAU DO USER QUYẾT, KHÔNG ĐỀ XUẤT:
- ❌ KHÔNG đề xuất **Budget** (số tiền VND cụ thể)
- ❌ KHÔNG đề xuất **Team size** (số người)
- ❌ KHÔNG đề xuất **Start date** (ngày bắt đầu)
- ❌ KHÔNG đề xuất **% giảm giá** cụ thể trong offer

→ Goal/duration/key_offer chỉ benchmark định tính + range gợi ý.

OUTPUT BẮT BUỘC dạng JSON (KHÔNG có text khác bên ngoài JSON):

```json
{
  "refined": {
    "name": "Tên campaign hoàn chỉnh (giữ ý user, refine wording)",
    "goal": "Mục tiêu QUALITATIVE (vd: 'Acquisition khách mới + build initial trust')",
    "key_offer": "MÔ TẢ cơ chế offer KHÔNG có % giảm cụ thể",
    "duration_suggestion": "Gợi ý độ dài (vd: '4-6 tuần')",
    "target_segment": "Tệp target cụ thể"
  },
  "validation": {
    "alignment_score": "high | medium | low",
    "fit_analysis": "2-3 câu phân tích: idea sếp có align với customer pain + market timing không (CITE cụ thể)",
    "risks": ["risk 1 ngắn gọn", "risk 2 (nếu có)"],
    "suggestions": ["gợi ý 1 để tăng impact", "gợi ý 2 (nếu có)"]
  }
}
```

QUY TẮC:
- KHÔNG bịa số — chỉ dùng từ context
- Nếu idea quá vague (vd "chạy combo Tết") → expand chi tiết dựa trên synthesis
- TÔN TRỌNG user intent — không đổi hoàn toàn idea, chỉ refine
- Output CHỈ JSON trong ```json``` block
"""


def _build_ideation_context(session: Session) -> str:
    """Build subset context: profile + customer + market + synthesis (nếu có)."""
    parts = [session.profile.to_context_string()]

    for key, label in [
        ("market_research",  "## Kết quả Nghiên cứu Thị trường"),
        ("customer_insight", "## Kết quả Customer Insight"),
        ("synthesis",        "## Marketing Strategy (Synthesis)"),
        ("psychology_pricing","## Pricing & Psychology"),
        ("usp_definition",   "## USP"),
    ]:
        content = session.get_latest_result(key)
        if content:
            parts.append(f"{label}\n{content}")

    return "\n\n---\n\n".join(parts)


def _extract_json(text: str) -> Optional[dict]:
    """Extract first ```json``` block from LLM output."""
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if not match:
        # Fallback: try parsing whole text as JSON
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JSON from campaign ideation: %s", e)
        return None


async def propose_campaigns(session: Session) -> Optional[list[dict]]:
    """Mode PROPOSE: Đề xuất 3 campaign options.

    Returns list[dict] với 3 options, hoặc None nếu fail.
    """
    context = _build_ideation_context(session)
    user_msg = (
        f"{context}\n\n---\n\n"
        "Đề xuất 3 campaign options khả thi nhất cho business của sếp trong 1-3 tháng tới. "
        "Mỗi option phải khác biệt rõ ràng về mục tiêu."
    )

    try:
        response = await client.messages.create(
            model=CLAUDE_SONNET_MODEL,
            max_tokens=3000,
            system=[{"type": "text", "text": PROPOSE_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_msg}],
        )
    except Exception as e:
        logger.exception("Campaign propose API call failed: %s", e)
        return None

    # Token tracking
    try:
        from tools.token_tracker import track_usage
        track_usage(session, response, label="campaign_propose")
    except Exception:
        pass

    raw = response.content[0].text
    data = _extract_json(raw)
    if not data or "options" not in data:
        logger.error("Campaign propose returned invalid JSON: %s", raw[:200])
        return None

    options = data.get("options", [])
    if not isinstance(options, list) or len(options) < 1:
        return None

    return options[:3]  # cap 3


async def refine_user_idea(session: Session, user_idea: str) -> Optional[dict]:
    """Mode REFINE: Validate + refine user's campaign idea.

    Returns dict {refined: {...}, validation: {...}} hoặc None nếu fail.
    """
    context = _build_ideation_context(session)
    user_msg = (
        f"{context}\n\n---\n\n"
        f"**Ý tưởng campaign của sếp:**\n{user_idea}\n\n"
        "Validate + refine idea này dựa trên Customer Insight + Market Research."
    )

    try:
        response = await client.messages.create(
            model=CLAUDE_SONNET_MODEL,
            max_tokens=2000,
            system=[{"type": "text", "text": REFINE_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_msg}],
        )
    except Exception as e:
        logger.exception("Campaign refine API call failed: %s", e)
        return None

    try:
        from tools.token_tracker import track_usage
        track_usage(session, response, label="campaign_refine")
    except Exception:
        pass

    raw = response.content[0].text
    data = _extract_json(raw)
    if not data or "refined" not in data:
        logger.error("Campaign refine returned invalid JSON: %s", raw[:200])
        return None

    return data


def format_options_card(options: list[dict]) -> str:
    """Format 3 options thành text card cho user đọc."""
    lines = ["💡 *Em đề xuất 3 campaign options dựa trên Strategy của sếp:*\n"]

    for i, opt in enumerate(options, 1):
        lines.append(f"━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"*OPTION {i}: {opt.get('name', '?')}*\n")
        lines.append(f"🎯 *Mục tiêu:* {opt.get('goal', '?')}")
        lines.append(f"🎁 *Cơ chế offer:* {opt.get('key_offer', '?')}")
        lines.append(f"📅 *Gợi ý độ dài:* {opt.get('duration_suggestion', '?')}")
        lines.append(f"👥 *Target:* {opt.get('target_segment', '?')}")
        lines.append(f"💭 *Vì sao phù hợp:* {opt.get('why_fit', '?')}\n")

    lines.append(f"━━━━━━━━━━━━━━━━━━━━")
    lines.append("\n_💰 Budget / 👥 Team / 📆 Ngày bắt đầu / 🎟 % giảm — sếp sẽ quyết ở bước sau._\n")
    lines.append("👇 *Sếp chọn option nào để em làm Brief Campaign?*")
    return "\n".join(lines)


def format_refined_card(refined_data: dict) -> str:
    """Format refined idea thành text card cho user confirm."""
    refined = refined_data.get("refined", {})
    validation = refined_data.get("validation", {})

    score_emoji = {
        "high":   "🟢 Cao",
        "medium": "🟡 Trung bình",
        "low":    "🔴 Thấp",
    }.get(validation.get("alignment_score", "").lower(), "⚪️ ?")

    lines = [
        "✨ *Em đã phân tích idea của sếp với Customer + Market:*\n",
        "━━━━━━━━━━━━━━━━━━━━",
        "*📋 CAMPAIGN REFINED*\n",
        f"🏷️ *Tên:* {refined.get('name', '?')}",
        f"🎯 *Mục tiêu:* {refined.get('goal', '?')}",
        f"🎁 *Cơ chế offer:* {refined.get('key_offer', '?')}",
        f"📅 *Gợi ý độ dài:* {refined.get('duration_suggestion', '?')}",
        f"👥 *Target:* {refined.get('target_segment', '?')}\n",
        "━━━━━━━━━━━━━━━━━━━━",
        f"*📊 VALIDATION* — Mức phù hợp: {score_emoji}\n",
        f"_{validation.get('fit_analysis', '')}_\n",
    ]

    risks = validation.get("risks", [])
    if risks:
        lines.append("⚠️ *Risks cần lưu ý:*")
        for r in risks:
            lines.append(f"  • {r}")
        lines.append("")

    suggestions = validation.get("suggestions", [])
    if suggestions:
        lines.append("💡 *Gợi ý tăng impact:*")
        for s in suggestions:
            lines.append(f"  • {s}")
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("\n_💰 Budget / 👥 Team / 📆 Ngày bắt đầu / 🎟 % giảm — sếp sẽ quyết ở bước sau._\n")
    lines.append("👇 *Sếp OK với campaign này không?*")
    return "\n".join(lines)


# ─── Finalize Form — 4 trường USER QUYẾT ────────────────────────

FINALIZE_FIELDS = [
    {"key": "budget",        "label": "Budget tổng",                  "example": "150 triệu / 80tr / 500M VND"},
    {"key": "team_size",     "label": "Capacity team chạy campaign",  "example": "3 người: 1 content, 1 ads, 1 sales"},
    {"key": "start_date",    "label": "Ngày bắt đầu",                 "example": "15/01/2026 / Thứ 2 tuần sau"},
    {"key": "discount_pct",  "label": "% giảm giá tối đa chấp nhận",  "example": "20% / 0% (không giảm) / Tặng quà thay vì giảm"},
]


def format_finalize_form(campaign: dict) -> str:
    """Form cho user fill 4 trường QUYẾT ĐỊNH trước khi launch Brief.

    AI proposal đã có trong card trước; form này CHỈ hỏi 4 trường còn thiếu.
    """
    lines = [
        f"✅ *Đã chốt campaign: \"{campaign.get('name', '?')}\"*",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "*🔧 4 thông tin cuối — do sếp quyết:*",
        "",
    ]
    for f in FINALIZE_FIELDS:
        lines.append(f"*{f['label']}:*")
        lines.append(f"_Vd: {f['example']}_")
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(
        "💬 *Copy form trên, điền vào, gửi lại 1 lần.*\n"
        "Em parse xong sẽ chạy Brief Campaign luôn ạ."
    )
    return "\n".join(lines)


def parse_finalize_form(text: str) -> tuple[dict, list[str]]:
    """Parse user reply theo FINALIZE_FIELDS.
    Returns (parsed_dict, missing_keys).
    """
    parsed = {}
    label_to_key = {f["label"].lower().strip(): f["key"] for f in FINALIZE_FIELDS}

    text_lines = text.split("\n")
    current_key = None
    current_parts: list[str] = []

    def _flush():
        nonlocal current_key, current_parts
        if current_key and current_parts:
            val = " ".join(current_parts).strip()
            # Loại bỏ italic "Vd: ..." nếu user paste cả example
            if val.lower().startswith("vd:") or val.lower().startswith("_vd:"):
                val = ""
            if val:
                parsed[current_key] = val
        current_key = None
        current_parts = []

    for line in text_lines:
        line_stripped = line.strip().lstrip("*_").rstrip("*_")
        if not line_stripped:
            continue

        # Match "Label: value"
        m = re.match(r"^([^:]+?)\s*:\s*(.*)$", line_stripped)
        if m:
            label = m.group(1).strip().lower()
            value = m.group(2).strip()
            # Tìm key khớp với label (substring match cho linh hoạt)
            matched_key = None
            for lbl, key in label_to_key.items():
                if lbl in label or label in lbl:
                    matched_key = key
                    break
            if matched_key:
                _flush()
                current_key = matched_key
                if value:
                    current_parts = [value]
                else:
                    current_parts = []
                continue

        # Continuation line
        if current_key:
            current_parts.append(line_stripped)

    _flush()

    # Validate required
    missing = [f["key"] for f in FINALIZE_FIELDS if not parsed.get(f["key"])]
    return parsed, missing


def merge_to_brief_fields(campaign: dict, user_inputs: dict) -> dict:
    """Merge AI proposal + user constraints → fields cho campaign_brief skill.

    campaign_brief consume 4 keys: campaign_name, campaign_goal, duration, key_offer
    """
    budget = user_inputs.get("budget", "")
    team_size = user_inputs.get("team_size", "")
    start_date = user_inputs.get("start_date", "")
    discount_pct = user_inputs.get("discount_pct", "")

    ai_duration = campaign.get("duration_suggestion") or campaign.get("duration", "")

    return {
        "campaign_name": campaign.get("name", ""),
        "campaign_goal": (
            f"{campaign.get('goal', '')}\n\n"
            f"**Constraints sếp quyết:**\n"
            f"- Budget: {budget}\n"
            f"- Team chạy campaign: {team_size}\n"
            f"- Target segment: {campaign.get('target_segment', 'chưa rõ')}"
        ),
        "duration": f"Bắt đầu {start_date}. Gợi ý độ dài: {ai_duration}",
        "key_offer": (
            f"{campaign.get('key_offer', '')}\n\n"
            f"**Mức giảm giá tối đa sếp chấp nhận:** {discount_pct}"
        ),
    }


# Backward-compat alias (cũ chỉ dùng AI, không inject user constraint)
def campaign_to_brief_fields(campaign: dict) -> dict:
    return merge_to_brief_fields(campaign, {
        "budget": "chưa xác định",
        "team_size": "chưa xác định",
        "start_date": "chưa xác định",
        "discount_pct": "chưa xác định",
    })
