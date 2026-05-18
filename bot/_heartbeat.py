"""
Progress heartbeat for long-running agent calls.

Telegram's typing indicator expires after ~5s. For agent calls that take
30-240s, the user has no signal the bot is alive — they may /reset, double-send,
or think the bot crashed. This module wraps an async coroutine with periodic
progress updates so the user keeps seeing activity.
"""
import asyncio
import logging
from typing import Any, Awaitable, Callable

from telegram import Message
from telegram.constants import ChatAction
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


# Tiered progress messages — each fires at the elapsed time threshold (seconds).
# Tuned so a typical 30-60s intake never sees more than 1 heartbeat (the 30s one),
# while a slow 200s pipeline stage sees three.
PROGRESS_TIERS = [
    (30,  "⏳ Vẫn đang xử lý, mất hơi lâu chút..."),
    (75,  "⏳ Tin nhắn này khá phức tạp, tôi cần thêm chút thời gian..."),
    (150, "⏳ Đang tổng hợp kết quả cuối cùng..."),
]

TYPING_REFRESH_INTERVAL = 4  # seconds — Telegram typing lasts ~5s


async def _refresh_typing(chat_id: int, bot, stop_event: asyncio.Event) -> None:
    """Keep the 'typing...' indicator alive until stop_event is set."""
    try:
        while not stop_event.is_set():
            try:
                await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            except TelegramError:
                pass  # Don't kill the loop over a transient Telegram blip.
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=TYPING_REFRESH_INTERVAL)
            except asyncio.TimeoutError:
                continue
    except asyncio.CancelledError:
        pass


async def _send_heartbeats(message: Message, stop_event: asyncio.Event) -> None:
    """Send one progress message at each PROGRESS_TIERS threshold."""
    start = asyncio.get_event_loop().time()
    try:
        for delay_s, text in PROGRESS_TIERS:
            remaining = delay_s - (asyncio.get_event_loop().time() - start)
            if remaining > 0:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=remaining)
                    return  # Stopped before this tier fires — work finished.
                except asyncio.TimeoutError:
                    pass  # Tier reached; send the message.
            if stop_event.is_set():
                return
            try:
                await message.reply_text(text)
            except TelegramError as e:
                logger.warning("heartbeat_send_failed", extra={"error": str(e)})
    except asyncio.CancelledError:
        pass


async def with_heartbeat(
    coro_factory: Callable[[], Awaitable[Any]],
    message: Message,
    bot,
) -> Any:
    """
    Run `coro_factory()` while keeping the user informed with typing + heartbeats.

    The factory pattern (not just a coroutine) is used so we can construct the
    coroutine right before scheduling, avoiding "coroutine was never awaited"
    warnings if the caller passes a pre-built coroutine that we'd need to cancel.

    Returns whatever the wrapped coroutine returns. Exceptions propagate.
    """
    stop_event = asyncio.Event()
    chat_id = message.chat_id

    typing_task = asyncio.create_task(_refresh_typing(chat_id, bot, stop_event))
    heartbeat_task = asyncio.create_task(_send_heartbeats(message, stop_event))
    main_task = asyncio.create_task(coro_factory())

    try:
        return await main_task
    finally:
        stop_event.set()
        # Cancel background tasks; await them to swallow any pending CancelledError.
        for t in (typing_task, heartbeat_task):
            if not t.done():
                t.cancel()
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass
