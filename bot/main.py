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
    cmd_settings,
    handle_message,
    handle_callback,
    handle_photo,
    cmd_admin_addquota,
    cmd_admin_setquota,
    cmd_admin_resetusage,
    cmd_admin_userinfo,
    cmd_history,
    cmd_post,
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(application: Application):
    """Called once after Application is built — init DB pool here."""
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
        .concurrent_updates(True)
        .build()
    )

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CommandHandler("setting",  cmd_settings))  # alias
    app.add_handler(CommandHandler("config",   cmd_settings))  # alias

    # Admin commands (chỉ ADMIN_IDS mới dùng được)
    app.add_handler(CommandHandler("addquota",   cmd_admin_addquota))
    app.add_handler(CommandHandler("setquota",   cmd_admin_setquota))
    app.add_handler(CommandHandler("resetusage", cmd_admin_resetusage))
    app.add_handler(CommandHandler("userinfo",   cmd_admin_userinfo))

    # Sprint 8 — Campaign History + Semantic Search
    app.add_handler(CommandHandler("history", cmd_history))

    # Sprint 7 — Per-post Actions
    app.add_handler(CommandHandler("post", cmd_post))

    # Inline keyboard callbacks
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Photo messages (image reference upload for Ads Gen)
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

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
