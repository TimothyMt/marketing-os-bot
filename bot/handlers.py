"""
Telegram bot message and callback handlers.
All storage calls are async (asyncpg-backed).
"""
import asyncio
import logging
import re
from telegram import Update, Message
from telegram.ext import ContextTypes
from telegram.constants import ParseMode, ChatAction

from storage import get_session, save_session, reset_session
from storage.models import PipelineStage
from agents.pipeline import run_intake, run_full_pipeline
from agents.prompts import INTAKE_CONFIRM_TEMPLATE, PROGRESS_MESSAGES
from frameworks.kpi_library import KPI_LIBRARY
from bot.keyboards import (
    CONFIRM_KEYBOARD,
    RESTART_KEYBOARD,
    stage_done_keyboard,
)

logger = logging.getLogger(__name__)

STAGE_HEADERS = {
    "market_research": "📊 NGHIÊN CỨU THỊ TRƯỜNG (TAM/SAM/SOM)",
    "competitor":      "🕵️ PHÂN TÍCH ĐỐI THỦ CẠNH TRANH",
    "customer_insight":"👥 CUSTOMER INSIGHT & ICP",
    "psychology_pricing": "💡 MARKETING PSYCHOLOGY & PRICING STRATEGY",
    "social_listening":"📡 SOCIAL LISTENING SYSTEM",
    "synthesis":       "🚀 MARKETING STRATEGY TỔNG HỢP",
}

WELCOME_MESSAGE = """👋 Xin chào! Tôi là *Max — AI CMO* của bạn.

Tôi sẽ phân tích và xây dựng Marketing Strategy hoàn chỉnh trong vài phút:
📊 Thị trường · 🕵️ Đối thủ · 👥 Khách hàng · 💡 Psychology & Pricing · 🎯 Strategy 90 ngày

─────────────────────────
*Trả lời 5 câu dưới đây — copy và điền vào chỗ trống hoặc tự viết theo cách của bạn:*

*1. Bạn đang bán gì?*
_Vd: Quán cà phê / App quản lý bán hàng / Khóa học digital marketing / Spa làm đẹp_

*2. Bán cho ai, ở đâu?*
_Vd: Dân văn phòng 25-35 tuổi tại HCM / SME chủ shop online toàn quốc / Phụ nữ 28-40 tuổi tại Hà Nội_

*3. Doanh thu hiện tại?*
_Vd: 80 triệu/tháng / Chưa có (đang chuẩn bị launch) / 500 triệu/tháng_

*4. Mục tiêu 90 ngày tới?*
_Vd: Tăng lên 150 triệu/tháng / Có 100 khách hàng đầu tiên / Giảm CAC xuống dưới 200k_

*5. Khó khăn lớn nhất hiện tại?*
_Vd: Chạy ads tốn tiền nhưng không ra khách / Khách mua 1 lần rồi thôi / Không biết bắt đầu từ đâu_

─────────────────────────
💬 *Điền xong gửi một lần — tôi phân tích ngay!*"""

HELP_MESSAGE = """*Marketing OS — Hướng dẫn sử dụng*

/start — Bắt đầu phân tích business mới
/reset — Xóa phiên hiện tại, bắt đầu lại
/help  — Hiển thị hướng dẫn này

*Cách sử dụng*:
1. Nhắn mô tả business của bạn (tiếng Việt tự nhiên)
2. Tôi sẽ hỏi thêm nếu cần thông tin
3. Xác nhận thông tin → Tôi chạy 6 bước phân tích
4. Nhận Marketing Strategy hoàn chỉnh

*Thời gian*: Khoảng 3-5 phút cho đầy đủ 6 bước phân tích."""


async def send_long_message(message: Message, text: str, **kwargs):
    """Split messages exceeding Telegram's 4096-char limit."""
    MAX_LEN = 4000
    if len(text) <= MAX_LEN:
        await message.reply_text(text, **kwargs)
        return

    chunks, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > MAX_LEN:
            if current:
                chunks.append(current)
            current = line
        else:
            current = (current + "\n" + line) if current else line
    if current:
        chunks.append(current)

    for i, chunk in enumerate(chunks):
        kw = kwargs if i == len(chunks) - 1 else {k: v for k, v in kwargs.items() if k != "reply_markup"}
        await message.reply_text(chunk, **kw)
        await asyncio.sleep(0.3)


# ─── Commands ────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await reset_session(user_id)
    session = await get_session(user_id)
    session.stage = PipelineStage.INTAKE
    await save_session(session)
    await update.message.reply_text(WELCOME_MESSAGE, parse_mode=ParseMode.MARKDOWN)


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await reset_session(user_id)
    await update.message.reply_text(
        "✅ Đã xóa phiên cũ. Hãy kể về business mới của bạn nhé!",
        reply_markup=RESTART_KEYBOARD,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_MESSAGE, parse_mode=ParseMode.MARKDOWN)


# ─── Main message handler ─────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    session = await get_session(user_id)

    if session.stage == PipelineStage.IDLE:
        session.stage = PipelineStage.INTAKE
        await save_session(session)

    if session.stage == PipelineStage.INTAKE:
        await _handle_intake(update, context, session, text)

    elif session.stage == PipelineStage.CONFIRMED:
        await update.message.reply_text(
            "Nhấn *Bắt đầu phân tích* để tôi chạy 6 bước nhé! Hoặc /reset để bắt đầu lại.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=CONFIRM_KEYBOARD,
        )

    elif session.stage == PipelineStage.COMPLETE:
        await _handle_followup(update, context, session, text)

    else:
        await update.message.reply_text(
            "⏳ Đang phân tích... Vui lòng chờ tôi hoàn thành các bước nhé."
        )


# ─── Intake ───────────────────────────────────────────────────────

async def _handle_intake(update, context, session, text):
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )

    response, is_complete = await run_intake(session, text)
    await save_session(session)

    if is_complete:
        clean_response = re.sub(r"```json.*?```", "", response, flags=re.DOTALL).strip()

        fw = KPI_LIBRARY.get(session.profile.industry or "")
        industry_name = fw.display_name if fw else (session.profile.industry or "Chưa xác định")

        confirm_msg = INTAKE_CONFIRM_TEMPLATE.format(
            business_name=session.profile.business_name or "Business của bạn",
            product_service=session.profile.product_service or "Chưa xác định",
            target_customer=session.profile.target_customer or "Chưa xác định",
            industry_display=industry_name,
            stage=session.profile.stage or "Chưa xác định",
            monthly_revenue=session.profile.monthly_revenue or "Chưa rõ",
            primary_goal=session.profile.primary_goal or "Chưa xác định",
            main_challenge=session.profile.main_challenge or "Chưa xác định",
        )

        session.stage = PipelineStage.CONFIRMED
        await save_session(session)

        await update.message.reply_text(
            confirm_msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=CONFIRM_KEYBOARD,
        )
    else:
        await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)


# ─── Follow-up Q&A after analysis complete ───────────────────────

async def _handle_followup(update, context, session, text):
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )

    import anthropic
    from config import CLAUDE_MODEL, ANTHROPIC_API_KEY
    from agents.prompts import STRATEGY_SYNTHESIZER_SYSTEM

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    context_str = session.build_pipeline_context()

    response = await client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        system=[{
            "type": "text",
            "text": STRATEGY_SYNTHESIZER_SYSTEM + "\n\nBạn đã hoàn thành phân tích. Trả lời câu hỏi follow-up dựa trên kết quả đã có.",
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": f"{context_str}\n\n---\n\nCâu hỏi follow-up: {text}",
        }],
    )

    await send_long_message(
        update.message,
        response.content[0].text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=stage_done_keyboard(is_last=True),
    )


# ─── Callback (inline keyboard) ──────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    session = await get_session(user_id)
    data = query.data

    if data == "confirm_yes":
        session.stage = PipelineStage.MARKET_RESEARCH
        await save_session(session)
        await query.edit_message_reply_markup(reply_markup=None)
        await _run_pipeline_sequentially(query.message, session)

    elif data == "confirm_no":
        session.stage = PipelineStage.INTAKE
        from storage.models import BusinessProfile
        session.profile = BusinessProfile()
        session.intake_history = []
        await save_session(session)
        await query.edit_message_text(
            "Không sao! Hãy mô tả lại business của bạn — tôi sẽ lắng nghe lại từ đầu nhé 🙂"
        )

    elif data == "restart":
        await reset_session(user_id)
        session = await get_session(user_id)
        session.stage = PipelineStage.INTAKE
        await save_session(session)
        await query.edit_message_text(
            "✅ Đã reset! Hãy kể cho tôi về business mới của bạn nhé:"
        )

    elif data == "ask_followup":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "💬 Bạn muốn hỏi thêm gì về strategy? Cứ nhắn thẳng vào đây nhé!"
        )


# ─── Pipeline runner ─────────────────────────────────────────────

async def _run_pipeline_sequentially(message: Message, session):
    await message.reply_text(
        "🚀 *Bắt đầu phân tích toàn diện!*\n\nTôi sẽ chạy 6 bước và gửi kết quả từng bước để bạn xem trong khi chờ.",
        parse_mode=ParseMode.MARKDOWN,
    )

    stage_count = 0
    total_stages = 6

    async def progress_cb(msg: str):
        await message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async for stage_key, result in run_full_pipeline(session, progress_callback=progress_cb):
        stage_count += 1
        is_last = stage_count == total_stages
        header = STAGE_HEADERS.get(stage_key, stage_key.upper())
        full_text = f"*{header}*\n{'─' * 30}\n\n{result}"

        await send_long_message(
            message,
            full_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=stage_done_keyboard(is_last=is_last) if is_last else None,
        )
        await save_session(session)
        await asyncio.sleep(0.5)

    if stage_count == total_stages:
        await message.reply_text(
            "✅ *Hoàn thành phân tích!*\n\nBạn đã có đầy đủ:\n• Market Intelligence\n• Competitor Landscape\n• Customer Insights\n• Psychology & Pricing\n• Social Listening System\n• Marketing Strategy 90 ngày\n\nCó câu hỏi gì thêm không? Cứ nhắn thẳng vào đây nhé! 💬",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=stage_done_keyboard(is_last=True),
        )
