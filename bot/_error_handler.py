"""
Centralized error handling for Telegram handlers.
Maps exception types to user-friendly Vietnamese messages, logs full context.
"""
import asyncio
import logging
from functools import wraps
from typing import Callable

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import TelegramError

from agents._decorators import AgentTimeoutError, AgentExecutionError

logger = logging.getLogger(__name__)


# User-facing messages keyed by exception class — keep Vietnamese, apologetic,
# and ALWAYS re-invite the user to send their last message again so they
# don't feel like progress was lost.
ERROR_MESSAGES = {
    AgentTimeoutError: (
        "😅 Xin lỗi bạn! Tôi vừa gặp sự cố kết nối với AI tạm thời.\n\n"
        "Bạn vui lòng *gõ lại tin nhắn vừa rồi* giúp tôi nhé — tôi sẽ xử lý ngay.\n\n"
        "_Nếu vẫn lỗi, gõ /reset để bắt đầu lại từ đầu._"
    ),
    AgentExecutionError: (
        "😅 Xin lỗi bạn! Tôi vừa gặp lỗi khi xử lý tin nhắn.\n\n"
        "Bạn có thể:\n"
        "• *Gõ lại tin nhắn vừa rồi* để tôi thử lại\n"
        "• Hoặc /reset nếu muốn bắt đầu phân tích mới\n\n"
        "_Phần thông tin bạn đã cung cấp trước đó vẫn được lưu — không phải nhập lại từ đầu._"
    ),
    asyncio.TimeoutError: (
        "😅 Xin lỗi, yêu cầu xử lý hơi lâu.\n\n"
        "Bạn *gõ lại tin nhắn vừa rồi* giúp tôi nhé."
    ),
}

GENERIC_ERROR_MESSAGE = (
    "😅 Xin lỗi bạn, tôi gặp lỗi kỹ thuật không mong muốn.\n\n"
    "Bạn *gõ lại tin nhắn vừa rồi* giúp tôi nhé — phần đã trả lời trước đó vẫn còn.\n\n"
    "_Nếu vẫn lỗi, gõ /reset để bắt đầu lại từ đầu._"
)


async def _reply(update: Update, text: str) -> None:
    """
    Reply to whichever message/callback triggered this update — best effort.
    Uses Markdown so *bold* highlights survive; falls back to plain text if
    Telegram rejects the markup (avoids a second error swallowing the first).
    """
    try:
        if update.callback_query is not None:
            target = update.callback_query.message
        elif update.message is not None:
            target = update.message
        else:
            return
        try:
            await target.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        except TelegramError:
            # Markdown parse failed — strip markup and try plain text.
            await target.reply_text(text)
    except TelegramError as e:
        # Telegram itself is failing — just log, nothing else we can do.
        logger.error("telegram_reply_failed", extra={"error": str(e)})


def safe_handler(func: Callable) -> Callable:
    """
    Wraps a Telegram handler with structured error handling.
    On exception: logs full traceback, replies to user with mapped message,
    swallows so python-telegram-bot doesn't propagate.
    """
    @wraps(func)
    async def wrapper(update: Update, context, *args, **kwargs):
        user_id = update.effective_user.id if update.effective_user else None
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            # Find best-matching message — exact class first, then isinstance fallback.
            msg = ERROR_MESSAGES.get(type(e))
            if msg is None:
                for exc_cls, candidate in ERROR_MESSAGES.items():
                    if isinstance(e, exc_cls):
                        msg = candidate
                        break
            msg = msg or GENERIC_ERROR_MESSAGE

            logger.error(
                "handler_error",
                extra={
                    "handler": func.__name__,
                    "user_id": user_id,
                    "error_type": type(e).__name__,
                    "error_msg": str(e)[:200],
                },
                exc_info=True,
            )
            await _reply(update, msg)
    return wrapper
