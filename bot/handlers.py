"""
Telegram bot message and callback handlers.
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

# Stage display names for progress headers
STAGE_HEADERS = {
    "market_research": "📊 NGHIÊN CỨU THỊ TRƯỜNG (TAM/SAM/SOM)",
    "competitor": "🕵️ PHÂN TÍCH ĐỐI THỦ CẠNH TRANH",
    "customer_insight": "👥 CUSTOMER INSIGHT & ICP",
    "psychology_pricing": "💡 MARKETING PSYCHOLOGY & PRICING STRATEGY",
    "social_listening": "📡 SOCIAL LISTENING SYSTEM",
    "synthesis": "🚀 MARKETING STRATEGY TỔNG HỢP",
}

WELCOME_MESSAGE = """👋 Xin chào! Tôi là *Marketing OS* — AI hỗ trợ Founders & Business Owners xây dựng Marketing Strategy chuyên nghiệp.

Tôi sẽ giúp bạn:
• 📊 Nghiên cứu thị trường (TAM/SAM/SOM)
• 🕵️ Phân tích đối thủ cạnh tranh
• 👥 Hiểu sâu khách hàng (ICP + JTBD)
• 💡 Áp dụng Marketing Psychology & Pricing
• 📡 Thiết lập Social Listening
• 🎯 Xây dựng Marketing Strategy (SAVE + SMART)

*Hãy kể cho tôi nghe về business của bạn* — tự nhiên như đang nói chuyện nhé! Ngành gì, đang ở giai đoạn nào, đang gặp vấn đề gì... càng chi tiết tôi phân tích càng sâu. 🙂"""

HELP_MESSAGE = """*Marketing OS — Hướng dẫn sử dụng*

/start — Bắt đầu phân tích business mới
/reset — Xóa phiên hiện tại, bắt đầu lại
/help — Hiển thị hướng dẫn này

*Cách sử dụng*:
1. Nhắn mô tả business của bạn (tiếng Việt tự nhiên)
2. Tôi sẽ hỏi thêm nếu cần thông tin
3. Xác nhận thông tin → Tôi chạy 6 bước phân tích
4. Nhận Marketing Strategy hoàn chỉnh

*Thời gian*: Khoảng 3-5 phút cho đầy đủ 6 bước phân tích."""


async def send_long_message(message: Message, text: str, **kwargs):
    """Split and send messages longer than Telegram's 4096 char limit."""
    MAX_LEN = 4000
    if len(text) <= MAX_LEN:
        await message.reply_text(text, **kwargs)
        return

    # Split at newlines, keeping sections intact
    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > MAX_LEN:
            if current:
                chunks.append(current)
            current = line
        else:
            current = current + "\n" + line if current else line
    if current:
        chunks.append(current)

    for i, chunk in enumerate(chunks):
        if i == len(chunks) - 1:
            await message.reply_text(chunk, **kwargs)
        else:
            await message.reply_text(chunk, parse_mode=kwargs.get("parse_mode"))
        await asyncio.sleep(0.3)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user_id = update.effective_user.id
    reset_session(user_id)
    session = get_session(user_id)
    session.stage = PipelineStage.INTAKE
    save_session(session)

    await update.message.reply_text(
        WELCOME_MESSAGE,
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reset command."""
    user_id = update.effective_user.id
    reset_session(user_id)
    await update.message.reply_text(
        "✅ Đã xóa phiên cũ. Hãy kể về business mới của bạn nhé!",
        reply_markup=RESTART_KEYBOARD,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_MESSAGE, parse_mode=ParseMode.MARKDOWN)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main message handler — routes based on session stage."""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    session = get_session(user_id)

    # Auto-start if user messages without /start
    if session.stage == PipelineStage.IDLE:
        session.stage = PipelineStage.INTAKE
        save_session(session)

    if session.stage == PipelineStage.INTAKE:
        await _handle_intake(update, context, session, text)

    elif session.stage == PipelineStage.CONFIRMED:
        # User is confirmed but pipeline not started yet
        await update.message.reply_text(
            "Nhấn *Bắt đầu phân tích* để tôi chạy 6 bước nhé! Hoặc /reset để bắt đầu lại.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=CONFIRM_KEYBOARD,
        )

    elif session.stage == PipelineStage.COMPLETE:
        # Allow follow-up questions after analysis
        await _handle_followup(update, context, session, text)

    else:
        # Pipeline is running
        await update.message.reply_text(
            "⏳ Đang phân tích... Vui lòng chờ tôi hoàn thành các bước nhé."
        )


async def _handle_intake(update, context, session, text):
    """Handle intake phase conversation."""
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )

    response, is_complete = await run_intake(session, text)
    save_session(session)

    if is_complete:
        # Show confirmation without the JSON block
        clean_response = re.sub(r"```json.*?```", "", response, flags=re.DOTALL).strip()

        # Build confirmation message
        industry_display = KPI_LIBRARY.get(
            session.profile.industry or "", None
        )
        industry_name = industry_display.display_name if industry_display else (session.profile.industry or "Chưa xác định")

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
        save_session(session)

        await update.message.reply_text(
            confirm_msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=CONFIRM_KEYBOARD,
        )
    else:
        # Still gathering info
        await update.message.reply_text(
            response,
            parse_mode=ParseMode.MARKDOWN,
        )


async def _handle_followup(update, context, session, text):
    """Handle follow-up questions after analysis is complete."""
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
        system=[
            {
                "type": "text",
                "text": STRATEGY_SYNTHESIZER_SYSTEM + "\n\nBạn đã hoàn thành phân tích đầy đủ. Hãy trả lời câu hỏi follow-up của founder dựa trên kết quả phân tích đã có.",
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": f"{context_str}\n\n---\n\nCâu hỏi follow-up: {text}",
            }
        ],
    )

    await send_long_message(
        update.message,
        response.content[0].text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=stage_done_keyboard(is_last=True),
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    session = get_session(user_id)
    data = query.data

    if data == "confirm_yes":
        session.stage = PipelineStage.MARKET_RESEARCH
        save_session(session)
        await query.edit_message_reply_markup(reply_markup=None)
        await _run_pipeline_sequentially(query.message, session)

    elif data == "confirm_no":
        session.stage = PipelineStage.INTAKE
        # Clear profile to restart intake
        from storage.models import BusinessProfile
        session.profile = BusinessProfile()
        session.intake_history = []
        save_session(session)
        await query.edit_message_text(
            "Không sao! Hãy mô tả lại business của bạn — tôi sẽ lắng nghe lại từ đầu nhé 🙂"
        )

    elif data == "restart":
        reset_session(user_id)
        session = get_session(user_id)
        session.stage = PipelineStage.INTAKE
        save_session(session)
        await query.edit_message_text(
            "✅ Đã reset! Hãy kể cho tôi về business mới của bạn nhé:"
        )

    elif data == "ask_followup":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "💬 Bạn muốn hỏi thêm gì về strategy? Cứ nhắn thẳng vào đây nhé!"
        )


async def _run_pipeline_sequentially(message: Message, session):
    """Run all pipeline stages and send results one by one."""
    await message.reply_text(
        "🚀 *Bắt đầu phân tích toàn diện!*\n\nTôi sẽ chạy 6 bước và gửi kết quả từng bước để bạn xem trong khi chờ.",
        parse_mode=ParseMode.MARKDOWN,
    )

    from storage import save_session

    stage_count = 0
    total_stages = 6

    async def progress_cb(msg: str):
        await message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async for stage_key, result in run_full_pipeline(session, progress_callback=progress_cb):
        stage_count += 1
        is_last = stage_count == total_stages

        header = STAGE_HEADERS.get(stage_key, stage_key.upper())
        divider = "─" * 30
        full_text = f"*{header}*\n{divider}\n\n{result}"

        await send_long_message(
            message,
            full_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=stage_done_keyboard(is_last=is_last) if is_last else None,
        )

        save_session(session)
        await asyncio.sleep(0.5)

    if stage_count == total_stages:
        await message.reply_text(
            "✅ *Hoàn thành phân tích!*\n\nBạn đã có đầy đủ:\n• Market Intelligence\n• Competitor Landscape\n• Customer Insights\n• Psychology & Pricing\n• Social Listening System\n• Marketing Strategy 90 ngày\n\nCó câu hỏi gì thêm không? Cứ nhắn thẳng vào đây nhé! 💬",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=stage_done_keyboard(is_last=True),
        )
