"""
Dream Engine worker — bot "mơ" ý tưởng marketing ban đêm.

Mỗi ngày (quanh DREAM_HOUR), với từng user có campaign history:
  1. Gom ký ức (campaign history + brand voice + đối thủ đang track).
  2. Sinh 3 ý tưởng marketing mới qua llm_router.
  3. Lưu vào table user_dreams.
  4. Gửi "morning digest" qua Telegram + nút Phát triển / Bỏ qua.

Deploy:
- In-process: start_background_dreamer() gọi trong bot/main.py post_init (asyncio task).
- Railway cron: `python -m workers.dream_engine` (one-shot run_once).

Lệnh /dream (user tự gọi) tái dùng generate_and_store() — xem bot/handlers.py.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from config import (
    TELEGRAM_BOT_TOKEN,
    DREAM_ENABLED,
    DREAM_HOUR,
    DREAM_MAX_USERS,
    DREAM_IDEAS_PER_USER,
)
from storage import init_pool
from storage.campaign_history import get_history_user_ids
from storage.dreams import save_dreams, mark_surfaced
from agents.dreamer import gather_memory, generate_dreams

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

_IMPACT_EMOJI = {"high": "🔥", "medium": "💡"}


async def generate_and_store(user_id: int) -> tuple[Optional[str], list[dict]]:
    """
    Mơ cho 1 user: gom ký ức → sinh ý tưởng → lưu DB.
    Returns (memory_block, saved_rows). (None, []) nếu user không có ký ức để mơ.
    Dùng chung cho worker nền lẫn lệnh /dream.
    """
    memory_block = await gather_memory(user_id)
    if not memory_block:
        return None, []

    dreams = await generate_dreams(user_id, memory_block)
    if not dreams:
        return memory_block, []

    dreams = dreams[:DREAM_IDEAS_PER_USER]
    batch_id = str(uuid.uuid4())
    saved = await save_dreams(user_id, dreams, batch_id=batch_id)
    return memory_block, saved


def build_digest_text(rows: list[dict]) -> str:
    """Format morning digest từ saved dream rows."""
    n = len(rows)
    lines = [
        f"🌙 *Đêm qua em mơ ra {n} ý tưởng marketing cho sếp đây ạ:*",
        "",
    ]
    for i, d in enumerate(rows, 1):
        emoji = _IMPACT_EMOJI.get((d.get("impact") or "").lower(), "💡")
        lines.append(f"{emoji} *{i}. {d.get('title','')}*")
        if d.get("angle"):
            lines.append(f"   {d['angle']}")
        if d.get("why_now"):
            lines.append(f"   _⏰ Vì sao lúc này: {d['why_now']}_")
        if d.get("first_step"):
            lines.append(f"   👉 Bước đầu: {d['first_step']}")
        lines.append("")
    lines.append("_Sếp muốn em phát triển ý tưởng nào thành kế hoạch thực thi không ạ?_")
    return "\n".join(lines)


def build_digest_keyboard(rows: list[dict]) -> InlineKeyboardMarkup:
    """1 hàng nút / dream: Phát triển + Bỏ qua. callback_data dùng dream id (UUID)."""
    buttons = []
    for i, d in enumerate(rows, 1):
        did = d.get("id")
        if not did:
            continue
        buttons.append([
            InlineKeyboardButton(f"🚀 Phát triển #{i}", callback_data=f"dreamdev_{did}"),
            InlineKeyboardButton("🗑", callback_data=f"dreamx_{did}"),
        ])
    return InlineKeyboardMarkup(buttons)


async def notify_user(bot: Bot, user_id: int, rows: list[dict]) -> bool:
    """Gửi digest + đánh dấu surfaced. Returns True nếu gửi thành công."""
    if not rows:
        return False
    text = build_digest_text(rows)
    keyboard = build_digest_keyboard(rows)
    try:
        await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
        await mark_surfaced([r["id"] for r in rows if r.get("id")])
        return True
    except Exception as e:
        # Markdown lỗi → thử plain text
        try:
            await bot.send_message(chat_id=user_id, text=text, reply_markup=keyboard)
            await mark_surfaced([r["id"] for r in rows if r.get("id")])
            return True
        except Exception as e2:
            logger.warning("notify_user failed (user=%d): %s / %s", user_id, e, e2)
            return False


async def run_dream_for_user(bot: Bot, user_id: int) -> bool:
    """Mơ + gửi digest cho 1 user. Returns True nếu có gửi gì đó."""
    try:
        _memory, rows = await generate_and_store(user_id)
        if not rows:
            return False
        return await notify_user(bot, user_id, rows)
    except Exception as e:
        logger.exception("run_dream_for_user failed (user=%d): %s", user_id, e)
        return False


async def run_once_with_bot(bot: Bot) -> int:
    """1 pass: mơ cho tất cả eligible user (cap DREAM_MAX_USERS). Returns số user đã gửi."""
    user_ids = await get_history_user_ids(limit=DREAM_MAX_USERS)
    if not user_ids:
        logger.info("Dream Engine: không có user nào đủ điều kiện (chưa có campaign history)")
        return 0

    logger.info("Dream Engine: bắt đầu mơ cho %d user", len(user_ids))
    sent = 0
    for uid in user_ids:
        try:
            if await run_dream_for_user(bot, uid):
                sent += 1
            await asyncio.sleep(2)  # nhẹ tay với API + Telegram rate limit
        except Exception as e:
            logger.exception("Dream pass failed for user %s: %s", uid, e)
    logger.info("Dream Engine: hoàn tất — gửi digest cho %d/%d user", sent, len(user_ids))
    return sent


def _seconds_until_hour(target_hour: int) -> float:
    """Số giây tới lần kế tiếp đạt target_hour (theo UTC)."""
    now = datetime.utcnow()
    target = now.replace(hour=target_hour % 24, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def start_background_dreamer(bot: Bot) -> None:
    """
    Vòng lặp nền: mỗi ngày quanh DREAM_HOUR chạy 1 pass mơ.
    Gọi trong Application.post_init. No-op nếu DREAM_ENABLED=false.
    """
    if not DREAM_ENABLED:
        logger.info("Dream Engine TẮT (set DREAM_ENABLED=true để bật). Lệnh /dream vẫn dùng được.")
        return

    logger.info("Dream Engine BẬT — digest hàng ngày quanh %02d:00 UTC", DREAM_HOUR)
    while True:
        delay = _seconds_until_hour(DREAM_HOUR)
        logger.info("Dream Engine: ngủ %.0f phút tới lần mơ kế tiếp", delay / 60)
        await asyncio.sleep(delay)
        try:
            await run_once_with_bot(bot)
        except Exception as e:
            logger.exception("Dream Engine background pass error: %s", e)
        # Tránh trigger lặp ngay trong cùng giờ
        await asyncio.sleep(3600)


async def run_once():
    """CLI one-shot — dùng cho Railway cron `python -m workers.dream_engine`."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN missing")
        return
    await init_pool()
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    await run_once_with_bot(bot)


if __name__ == "__main__":
    asyncio.run(run_once())
