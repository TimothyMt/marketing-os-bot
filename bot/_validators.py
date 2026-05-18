"""
Input validation at the Telegram boundary.
Reject malformed input early — never let it flow into agents/storage.
"""
from typing import Optional
from config import MAX_INPUT_LENGTH
from storage.models import TaskType


# Pre-compute valid task values once at import time.
_VALID_TASK_VALUES = {t.value for t in TaskType}


def validate_user_input(text: Optional[str]) -> tuple[str, Optional[str]]:
    """
    Sanitize a Telegram text message.
    Returns (cleaned_text, error_message). If error_message is non-None,
    the caller should reply with it instead of processing.
    """
    if not text or not isinstance(text, str):
        return "", "❌ Tin nhắn trống. Bạn gõ lại nhé."

    cleaned = text.strip()

    if len(cleaned) == 0:
        return "", "❌ Tin nhắn trống. Bạn gõ lại nhé."

    if len(cleaned) > MAX_INPUT_LENGTH:
        return "", (
            f"❌ Tin nhắn dài quá ({len(cleaned)} ký tự, tối đa {MAX_INPUT_LENGTH}).\n"
            "Bạn rút gọn lại nhé."
        )

    # Spam heuristic: tin nhắn chỉ có 1-2 ký tự khác nhau lặp lại.
    # Vd: "aaaaaa" hoặc "abababab". Bỏ qua nếu tin ngắn (< 5 chars).
    if len(cleaned) >= 5 and len(set(cleaned)) <= 2:
        return "", "❌ Tin nhắn không hợp lệ. Bạn gõ rõ ràng hơn nhé."

    # Collapse 3+ consecutive newlines to 2 (markdown-safe).
    while "\n\n\n" in cleaned:
        cleaned = cleaned.replace("\n\n\n", "\n\n")

    return cleaned, None


def validate_task_type(task: Optional[str]) -> bool:
    """True if task is a recognised TaskType enum value."""
    return task in _VALID_TASK_VALUES
