"""
Entry point — Marketing OS Telegram Bot (Webhook mode).
Designed for Railway + Supabase deployment.
"""
import logging
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from config import TELEGRAM_BOT_TOKEN, WEBHOOK_URL, PORT
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
    """Called once after Application is built — init DB pool here."""
    from config import SUPABASE_URL, SUPABASE_KEY
    logger.info(f"SUPABASE_URL = '{SUPABASE_URL[:30] if SUPABASE_URL else 'EMPTY'}'")
    logger.info(f"SUPABASE_KEY = '{'SET (' + str(len(SUPABASE_KEY)) + ' chars)' if SUPABASE_KEY else 'EMPTY'}'")
    await init_pool()
    await init_db()
    logger.info("DB pool ready.")


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set.")
    if not WEBHOOK_URL:
        raise ValueError("WEBHOOK_URL is not set.")

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("help", cmd_help))

    # Inline keyboard callbacks
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Webhook endpoint path = /TOKEN (keeps Telegram updates private)
    webhook_path = TELEGRAM_BOT_TOKEN

    logger.info(f"Starting webhook on port {PORT} → {WEBHOOK_URL}/{webhook_path}")

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=webhook_path,
        webhook_url=f"{WEBHOOK_URL}/{webhook_path}",
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
