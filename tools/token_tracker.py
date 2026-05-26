"""
Token tracking helper — đếm tokens sau mỗi Anthropic API call,
cộng dồn vào session.preferences["token_used"].

Mỗi user mặc định có quota 1,000,000 tokens (free tier).
Khi gần hết, hiển thị cảnh báo qua /settings hoặc khi chạy skill.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_QUOTA = 1_000_000  # 1M tokens/user/month
_TOKEN_LOG_KEY = "_token_log"
_TOKEN_LOG_MAX = 50  # số entries tối đa giữ lại


def _append_log(prefs: dict, entry: dict):
    """Thêm entry vào _token_log, cắt bớt nếu vượt giới hạn."""
    log: list = prefs.get(_TOKEN_LOG_KEY, [])
    if not isinstance(log, list):
        log = []
    log.append(entry)
    if len(log) > _TOKEN_LOG_MAX:
        log = log[-_TOKEN_LOG_MAX:]
    prefs[_TOKEN_LOG_KEY] = log


def track_skill(
    session,
    skill_name: str,
    provider: str,
    input_tok: int,
    output_tok: int,
    cache_read: int = 0,
    cache_create: int = 0,
    latency_sec: float = 0.0,
) -> int:
    """Track per-skill token usage với đầy đủ metadata (provider, latency).

    Cập nhật đồng thời:
    - session.preferences["token_used"]  — cumulative counter
    - session.preferences["_token_log"]  — per-call log (capped _TOKEN_LOG_MAX)

    Returns: tổng tokens call này.
    """
    if session is None:
        return 0

    total = max(0, input_tok) + max(0, output_tok) + max(0, cache_read) + max(0, cache_create)
    if total <= 0:
        return 0

    prefs = session.preferences or {}
    try:
        current = int(str(prefs.get("token_used", "0")).replace(",", "").replace(".", ""))
    except (ValueError, TypeError):
        current = 0
    new_total = current + total
    prefs["token_used"] = str(new_total)

    _append_log(prefs, {
        "skill":        skill_name,
        "provider":     provider,
        "input_tok":    max(0, input_tok),
        "output_tok":   max(0, output_tok),
        "cache_read":   max(0, cache_read),
        "cache_create": max(0, cache_create),
        "total":        total,
        "latency_sec":  round(latency_sec, 1),
        "ts":           datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
    })

    session.preferences = prefs

    logger.info(
        "[token] user=%s skill=%s provider=%s in=%d out=%d cache_r=%d cache_c=%d total=%d latency=%.1fs cumulative=%d",
        session.user_id, skill_name, provider,
        input_tok, output_tok, cache_read, cache_create,
        total, latency_sec, new_total,
    )
    return total


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

    _append_log(prefs, {
        "skill":        label,
        "provider":     "claude-sonnet-4-6",
        "input_tok":    input_tok,
        "output_tok":   output_tok,
        "cache_read":   cache_read,
        "cache_create": cache_create,
        "total":        total,
        "latency_sec":  0.0,
        "ts":           datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
    })

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

    _append_log(prefs, {
        "skill":        label,
        "provider":     "unknown",
        "input_tok":    max(0, int(input_tokens)),
        "output_tok":   max(0, int(output_tokens)),
        "cache_read":   0,
        "cache_create": 0,
        "total":        total,
        "latency_sec":  0.0,
        "ts":           datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
    })

    session.preferences = prefs

    logger.info(
        "[token-raw] user=%s call=%s in=%d out=%d total=%d cumulative=%d",
        session.user_id, label, input_tokens, output_tokens, total, new_total,
    )
    return total


def get_token_log(session) -> list[dict]:
    """Trả về danh sách per-call log entries (mới nhất cuối list)."""
    prefs = session.preferences or {}
    log = prefs.get(_TOKEN_LOG_KEY, [])
    return log if isinstance(log, list) else []


def get_latest_skill_entry(session, skill_name: str) -> Optional[dict]:
    """Lấy entry gần nhất của skill_name từ log, hoặc None nếu chưa có."""
    for entry in reversed(get_token_log(session)):
        if entry.get("skill") == skill_name:
            return entry
    return None


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
