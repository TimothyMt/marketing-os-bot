"""
Local development runner — polling mode.
Không cần webhook, không cần public URL.
Bot tự hỏi Telegram mỗi giây, log hiện trong terminal.

Chạy: python run_local.py
Dừng: Ctrl+C
"""
import logging
import asyncio
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from config import TELEGRAM_BOT_TOKEN
from storage import init_pool, init_db
from bot.handlers import (
    cmd_start,
    cmd_reset,
    cmd_help,
    handle_message,
    handle_callback,
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(application: Application):
    await init_pool()
    await init_db()
    logger.info("✅ Supabase connected.")
    logger.info("✅ Bot running in POLLING mode — local dev.")
    logger.info("💬 Mở Telegram và chat với bot. Ctrl+C để dừng.\n")


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN chưa được set trong .env")

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
