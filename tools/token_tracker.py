"""
Token tracking helper — đếm tokens sau mỗi Anthropic API call,
cộng dồn vào session.preferences["token_used"].

Mỗi user mặc định có quota 1,000,000 tokens (free tier).
Khi gần hết, hiển thị cảnh báo qua /settings hoặc khi chạy skill.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_QUOTA = 1_000_000  # 1M tokens/user/month


def track_usage(session, response, label: str = "") -> int:
    """Đếm tokens từ Anthropic response.usage, cộng vào session.preferences.

    Args:
        session: Session object (sẽ update preferences in-place)
        response: Anthropic API response object (có .usage)
        label: Tên call để log (vd "intake" / "competitor_spy" / "advisor")

    Returns:
        Tổng tokens đã track của call này.
    """
    if session is None or response is None:
        return 0

    usage = getattr(response, "usage", None)
    if usage is None:
        return 0

    # Anthropic usage fields
    input_tok  = getattr(usage, "input_tokens", 0) or 0
    output_tok = getattr(usage, "output_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_create = getattr(usage, "cache_creation_input_tokens", 0) or 0

    total = input_tok + output_tok + cache_read + cache_create

    if total <= 0:
        return 0

    # Update session.preferences
    prefs = session.preferences or {}
    try:
        current = int(str(prefs.get("token_used", "0")).replace(",", "").replace(".", ""))
    except (ValueError, TypeError):
        current = 0
    new_total = current + total
    prefs["token_used"] = str(new_total)
    session.preferences = prefs

    logger.info(
        "[token] user=%s call=%s in=%d out=%d cache_r=%d cache_c=%d total=%d cumulative=%d",
        session.user_id, label, input_tok, output_tok, cache_read, cache_create, total, new_total,
    )
    return total


def track_usage_raw(session, input_tokens: int, output_tokens: int, label: str = "") -> int:
    """Track tokens manually — cho providers KHÔNG phải Anthropic (Gemini, OpenAI...).

    Khác track_usage: không parse response object, accept raw int.
    Cùng cumulative counter trong session.preferences['token_used'].
    """
    if session is None:
        return 0

    total = max(0, int(input_tokens)) + max(0, int(output_tokens))
    if total <= 0:
        return 0

    prefs = session.preferences or {}
    try:
        current = int(str(prefs.get("token_used", "0")).replace(",", "").replace(".", ""))
    except (ValueError, TypeError):
        current = 0
    new_total = current + total
    prefs["token_used"] = str(new_total)
    session.preferences = prefs

    logger.info(
        "[token-raw] user=%s call=%s in=%d out=%d total=%d cumulative=%d",
        session.user_id, label, input_tokens, output_tokens, total, new_total,
    )
    return total


def get_quota(session) -> int:
    """Lấy quota của user (mặc định 1M)."""
    prefs = session.preferences or {}
    try:
        return int(str(prefs.get("token_quota", DEFAULT_QUOTA)).replace(",", ""))
    except (ValueError, TypeError):
        return DEFAULT_QUOTA


def get_used(session) -> int:
    """Lấy số token đã dùng."""
    prefs = session.preferences or {}
    try:
        return int(str(prefs.get("token_used", "0")).replace(",", ""))
    except (ValueError, TypeError):
        return 0


def get_remaining(session) -> int:
    """Còn lại bao nhiêu token."""
    return max(0, get_quota(session) - get_used(session))


def is_low(session, threshold_pct: float = 0.1) -> bool:
    """True nếu còn < threshold_pct của quota (mặc định 10%)."""
    quota = get_quota(session)
    if quota <= 0:
        return False
    return get_remaining(session) / quota < threshold_pct


def is_exhausted(session) -> bool:
    """True nếu đã hết quota."""
    return get_remaining(session) <= 0


def fmt(n: int) -> str:
    """Format số token cho user: 1500 → '1.5K', 1_234_567 → '1.23M'."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1000:
        return f"{n / 1000:.1f}K"
    return str(n)


def usage_summary(session) -> str:
    """Trả về string format cho /settings: '12.5K / 1M (1.2%)'."""
    used = get_used(session)
    quota = get_quota(session)
    pct = (used / quota * 100) if quota else 0
    return f"{fmt(used)} / {fmt(quota)} ({pct:.1f}%)"
