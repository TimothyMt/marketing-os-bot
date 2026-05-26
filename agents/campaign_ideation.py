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

Dựa vào Strategy synthesis + Customer Insight + Market Research, đề xuất 3 campaign options KHẢ THI nhất cho 1-3 tháng tới.

Mỗi option phải:
- Bám sát SAVE Framework + SMART Goals trong synthesis
- Match với pain point từ Customer Insight (cite cụ thể)
- Tận dụng cơ hội từ Market Research (timing, seasonality, market gap)
- Khác biệt rõ ràng giữa 3 options — mỗi option giải quyết 1 mục tiêu chính khác nhau:
  Option 1: Acquisition / thu khách mới
  Option 2: Retention / upsell / tăng AOV
  Option 3: Brand / awareness / positioning

OUTPUT BẮT BUỘC dạng JSON (KHÔNG có text khác bên ngoài JSON):

```json
{
  "options": [
    {
      "name": "Tên campaign tiếng Việt, hook-y, ngắn (vd: 'Tặng Mình Trước', 'Cuối Năm Đẹp Hơn')",
      "goal": "Mục tiêu cụ thể CÓ SỐ (vd: 'Thu 3000 mess + chốt 500 booking, doanh thu 350tr')",
      "key_offer": "Offer chính cụ thể (vd: 'Combo 680K giảm 20% từ 850K, tặng 1 buổi mask')",
      "duration": "Thời lượng + ngày (vd: '6 tuần — 15/01/2026 → 28/02/2026')",
      "target_segment": "Tệp target cụ thể (vd: 'Phụ nữ 28-40 đã từng inbox chưa book')",
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
2. **Refine**: đưa ra tên/goal/offer/duration cụ thể hơn nếu user nói chung chung
3. **Cảnh báo risks** (nếu có): timing sai, segment không match, offer yếu, v.v.

OUTPUT BẮT BUỘC dạng JSON (KHÔNG có text khác bên ngoài JSON):

```json
{
  "refined": {
    "name": "Tên campaign hoàn chỉnh (giữ ý user, refine wording)",
    "goal": "Mục tiêu CÓ SỐ (suy ra từ goal user nói)",
    "key_offer": "Offer chính cụ thể",
    "duration": "Thời lượng + ngày cụ thể",
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
        lines.append(f"🎁 *Offer chính:* {opt.get('key_offer', '?')}")
        lines.append(f"📅 *Thời lượng:* {opt.get('duration', '?')}")
        lines.append(f"👥 *Target:* {opt.get('target_segment', '?')}")
        lines.append(f"💭 *Vì sao phù hợp:* {opt.get('why_fit', '?')}\n")

    lines.append(f"━━━━━━━━━━━━━━━━━━━━")
    lines.append("\n👇 *Sếp chọn option nào để em làm Brief Campaign?*")
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
        f"🎁 *Offer:* {refined.get('key_offer', '?')}",
        f"📅 *Thời lượng:* {refined.get('duration', '?')}",
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
    lines.append("\n👇 *Sếp OK với campaign này không?*")
    return "\n".join(lines)


def campaign_to_brief_fields(campaign: dict) -> dict:
    """Convert proposed/refined campaign → fields cho campaign_brief skill.

    campaign_brief expects: campaign_name, campaign_goal, duration, key_offer
    """
    return {
        "campaign_name": campaign.get("name", ""),
        "campaign_goal": campaign.get("goal", ""),
        "duration":      campaign.get("duration", ""),
        "key_offer":     campaign.get("key_offer", ""),
    }
