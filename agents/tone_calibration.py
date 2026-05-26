"""
Tone Calibration Loop — Sprint 6.

Flow:
  1. Content Calendar gen xong → extract Post 1 → show user để check tone
  2. User approve → lock tone signals → gen N-1 bài còn lại với signals
  3. User reject + feedback → AI regen Post 1 theo feedback (max 3 lần)
  4. Sau 3 lần reject → auto-lock (dùng sample_content nếu có)

Graceful: mọi lỗi AI đều degrade về "show calendar gốc".
"""
import logging
import json
import re
from typing import Optional

import anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_HAIKU_MODEL, CLAUDE_SONNET_MODEL, AGENT_TIMEOUT

logger = logging.getLogger(__name__)

_client: Optional[anthropic.AsyncAnthropic] = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    return _client


# ─── Parse first post from calendar text ──────────────────────────────────────

def parse_first_post(calendar_text: str) -> Optional[dict]:
    """
    Extract bài đăng đầu tiên từ content calendar text.
    Trả về dict {hook, body, channel, day} hoặc None nếu không parse được.
    """
    # Tìm block đầu tiên có dấu hiệu là 1 post
    patterns = [
        # Pattern: "Tuần 1 | Thứ X | ..."
        r"(?:Tuần\s*1|Week\s*1).*?(?:Hook|Caption|Nội dung|Content)[:\s]+(.{50,500}?)(?=\n\n|\nTuần|\nWeek|\Z)",
        # Pattern: "POST-001" hoặc "Bài 1"
        r"(?:POST-001|Bài\s*1|Day\s*1|Ngày\s*1).*?(?:Hook|Caption|Nội dung)[:\s]+(.{50,500}?)(?=\n\n|\nBài|\nPost|\Z)",
    ]

    for pat in patterns:
        m = re.search(pat, calendar_text, re.DOTALL | re.IGNORECASE)
        if m:
            content = m.group(1).strip()[:800]
            return {"preview": content, "full_block": m.group(0)[:1000]}

    # Fallback: lấy đoạn văn đầu tiên đủ dài
    paragraphs = [p.strip() for p in calendar_text.split("\n\n") if len(p.strip()) > 100]
    if paragraphs:
        first = paragraphs[0][:800]
        return {"preview": first, "full_block": first}

    return None


# ─── Extract tone signals from user feedback ──────────────────────────────────

_EXTRACT_TONE_SYSTEM = """Bạn là chuyên gia phân tích Brand Voice.
User vừa đọc bài content và cho feedback về tone.

NHIỆM VỤ: Extract "tone signals" từ feedback để dùng làm style guide cho toàn bộ calendar.

Trả về JSON:
{
  "tone_words": ["list 3-5 từ mô tả tone mong muốn, vd: thân thiện, chuyên nghiệp, hài hước"],
  "do_adjust": ["điều chỉnh CẦN làm, vd: viết câu ngắn hơn, dùng emoji vừa phải"],
  "dont_repeat": ["lỗi cần tránh lặp lại từ bài cũ"],
  "sample_phrase": "1 câu mẫu thể hiện đúng tone mong muốn (nếu user có gợi ý)"
}

Chỉ trả về JSON, không giải thích thêm."""


async def extract_tone_signals(
    session,
    user_feedback: str,
    post_content: str,
) -> dict:
    """
    Dùng AI extract tone signals từ user feedback + post content.
    Returns dict signals, hoặc minimal fallback nếu fail.
    """
    client = _get_client()

    user_msg = f"""**Bài content vừa gen:**
{post_content[:600]}

**Feedback của user:**
{user_feedback}

**Business context:**
Ngành: {getattr(session.profile, 'industry', 'chưa rõ')}
Tone hiện tại: {getattr(session.profile, 'usp', '')}
"""

    try:
        resp = await client.messages.create(
            model=CLAUDE_HAIKU_MODEL,
            max_tokens=500,
            system=_EXTRACT_TONE_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = resp.content[0].text.strip()
        # Parse JSON
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            return json.loads(m.group(0))
    except Exception as e:
        logger.warning("extract_tone_signals failed: %s", e)

    # Fallback: minimal signals from feedback text
    return {
        "tone_words": [],
        "do_adjust": [user_feedback[:200]],
        "dont_repeat": [],
        "sample_phrase": "",
    }


# ─── Regen post 1 with tone signals ───────────────────────────────────────────

_REGEN_POST_SYSTEM = """Bạn là Content Writer chuyên nghiệp.
Viết lại bài content theo đúng tone signals được cung cấp.
Giữ nguyên chủ đề, thông điệp core. Chỉ thay đổi phong cách.
Trả về bài content đã viết lại, không cần giải thích."""


async def regen_post_with_signals(
    session,
    original_post: str,
    signals: dict,
) -> str:
    """Viết lại Post 1 theo tone signals. Returns new post text."""
    client = _get_client()

    tone_guide = []
    if signals.get("tone_words"):
        tone_guide.append(f"Tone: {', '.join(signals['tone_words'])}")
    if signals.get("do_adjust"):
        tone_guide.append("Cần làm: " + "; ".join(signals["do_adjust"]))
    if signals.get("dont_repeat"):
        tone_guide.append("Tránh: " + "; ".join(signals["dont_repeat"]))
    if signals.get("sample_phrase"):
        tone_guide.append(f"Câu mẫu: {signals['sample_phrase']}")

    user_msg = f"""**Bài gốc cần viết lại:**
{original_post}

**Tone signals (TUÂN THỦ TUYỆT ĐỐI):**
{chr(10).join(tone_guide)}

**Business:**
{session.profile.to_context_string()[:400]}

Viết lại bài theo đúng tone signals trên."""

    try:
        resp = await client.messages.create(
            model=CLAUDE_HAIKU_MODEL,
            max_tokens=1000,
            system=_REGEN_POST_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        return resp.content[0].text.strip()
    except Exception as e:
        logger.warning("regen_post_with_signals failed: %s", e)
        return original_post  # Fallback: return original


# ─── Apply tone signals to full calendar ──────────────────────────────────────

_APPLY_TONE_SYSTEM = """Bạn là Content Director review toàn bộ content calendar.

Đã lock tone signals từ Post 1. Áp dụng đồng nhất cho TẤT CẢ bài còn lại.

KHÔNG thay đổi:
- Chủ đề từng bài
- Ngày đăng / kênh
- CTA core
- Số lượng bài

CHỈ điều chỉnh:
- Phong cách viết (tone, từ ngữ, cấu trúc câu)
- Mức độ emoji
- Voice consistency

Giữ nguyên format structure của calendar gốc."""


async def apply_tone_to_calendar(
    session,
    calendar_text: str,
    signals: dict,
    approved_post1: str,
) -> str:
    """
    Áp dụng locked tone signals lên full calendar.
    Returns updated calendar text.
    """
    client = _get_client()

    tone_guide = []
    if signals.get("tone_words"):
        tone_guide.append(f"Tone đã lock: {', '.join(signals['tone_words'])}")
    if signals.get("do_adjust"):
        tone_guide.append("Style rules: " + "; ".join(signals["do_adjust"]))
    if signals.get("dont_repeat"):
        tone_guide.append("Tránh: " + "; ".join(signals["dont_repeat"]))

    user_msg = f"""**Post 1 (đã approved — dùng làm mẫu tone):**
{approved_post1[:600]}

**Tone signals đã lock:**
{chr(10).join(tone_guide)}

**Full Content Calendar cần update:**
{calendar_text}

Áp dụng tone đồng nhất cho toàn bộ calendar theo mẫu Post 1."""

    try:
        resp = await client.messages.create(
            model=CLAUDE_SONNET_MODEL,
            max_tokens=8000,
            system=_APPLY_TONE_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        return resp.content[0].text.strip()
    except Exception as e:
        logger.warning("apply_tone_to_calendar failed: %s", e)
        return calendar_text  # Fallback: return original calendar


# ─── Format signals for display ───────────────────────────────────────────────

def format_signals_card(signals: dict) -> str:
    """Format tone signals thành text card để show user."""
    lines = ["🎯 *Tone đã extract:*"]
    if signals.get("tone_words"):
        lines.append(f"• Phong cách: {', '.join(signals['tone_words'])}")
    if signals.get("do_adjust"):
        for d in signals["do_adjust"][:3]:
            lines.append(f"• ✅ {d}")
    if signals.get("dont_repeat"):
        for d in signals["dont_repeat"][:2]:
            lines.append(f"• ❌ Tránh: {d}")
    return "\n".join(lines)
