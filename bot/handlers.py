"""
Telegram bot message and callback handlers.
All storage calls are async (asyncpg-backed).
"""
import asyncio
import logging
import re
from telegram import Update, Message, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode, ChatAction

from storage import get_session, save_session, reset_session
from storage.models import PipelineStage
from agents.pipeline import run_intake, run_targeted_pipeline, run_operational_skill
from agents.prompts import INTAKE_CONFIRM_TEMPLATE, PROGRESS_MESSAGES, TASK_OPENING_QUESTIONS
from agents.task_registry import TASK_REGISTRY, OPERATIONAL_TASKS, STRATEGIC_TASKS, get_task, needs_intake
from frameworks.kpi_library import KPI_LIBRARY
from bot.keyboards import (
    MAIN_MENU_KEYBOARD,
    STRATEGIC_KEYBOARD,
    OPERATIONAL_KEYBOARD,
    ANALYSIS_KEYBOARD,
    TASK_SELECT_KEYBOARD,
    CONFIRM_KEYBOARD,
    RESTART_KEYBOARD,
    stage_done_keyboard,
    get_action_keyboard,
    ASK_FOLLOWUP_KEYBOARD,
    ADS_COPY_TIER_KEYBOARD,
    VIDEO_CREATOR_KEYBOARD,
    LANG_LEVEL_KEYBOARD,
    RATING_KEYBOARD,
    REGEN_PROMPT_KEYBOARD,
    FEEDBACK_PROMPT_KEYBOARD,
    COMPARE_PROMPT_KEYBOARD,
    ADS_FORMAT_KEYBOARD,
    IMAGE_REFERENCE_KEYBOARD,
    IMAGE_GEN_PROMPT_KEYBOARD,
    IMAGE_SIZE_KEYBOARD,
    IMAGE_REVIEW_KEYBOARD,
    NEEDS_STRATEGY_KEYBOARD,
    MONITOR_PROMPT_KEYBOARD,
    MONITOR_INTERVAL_KEYBOARD,
    MONITOR_NEW_ADS_KEYBOARD,
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

TASK_LABELS = {
    "full":       "Phân tích toàn diện (5 bước)",
    "market":     "Nghiên cứu thị trường",
    "competitor": "Phân tích đối thủ",
    "customer":   "Customer Insight & ICP",
    "pricing":    "Pricing Strategy",
    "social":     "Social Listening",
    "strategy":   "Marketing Strategy",
}

TASK_PIPELINE_STEPS = {
    "full":       "1️⃣ Thị trường · 2️⃣ Đối thủ · 3️⃣ Customer · 4️⃣ Psychology & Pricing · 5️⃣ Strategy",
    "market":     "📊 Phân tích TAM/SAM/SOM + market dynamics",
    "competitor": "🕵️ Landscape đối thủ + market gap analysis",
    "customer":   "👥 ICP profile + Jobs-to-be-Done + Customer Journey",
    "pricing":    "💰 Pricing model + psychology tactics + revenue optimization",
    # "social":  "📡 Keyword clusters + monitoring routine + crisis thresholds",  # tạm tắt
    "strategy":   "🎯 SAVE Framework + SMART Goals + 90-day Roadmap",
}

TASK_STAGE_COUNT = {
    "full": 5,
    "market": 1,
    "competitor": 1,
    "customer": 1,
    "pricing": 1,
    # "social": 1,  # tạm tắt
    "strategy": 1,
}

WELCOME_MESSAGE = """Em là *Max*, trợ lý marketing của sếp.

Em hỗ trợ sếp 3 mảng chính:

🎯 *Chiến Lược* — Phân tích thị trường, đối thủ, khách hàng, định giá, lập kế hoạch
⚙️ *Sản Xuất* — Brief campaign, lịch nội dung, viết quảng cáo, kịch bản video, website, kịch bản sales, chăm sóc khách
📊 *Theo Dõi & Báo Cáo* — Theo dõi đối thủ, báo cáo ads

─────────────────────────
*Hôm nay sếp muốn em xử lý phần nào ạ?*"""

# First-time language preference setup (Sprint 1)
LANG_SETUP_MESSAGE = """Em chào sếp! Trước khi vào việc, em hỏi nhanh 1 ý ạ:

*Khả năng tiếng Anh của sếp thế nào* để em biết cách trình bày output cho phù hợp?

🔴 *Không rành* — Em dùng thuần Việt toàn bộ, kể cả thuật ngữ
🟡 *Hiểu cơ bản* — Em dùng thuật ngữ EN nhưng kèm giải thích trong ngoặc
🟢 *Thông thạo* — Em dùng thuật ngữ EN tự nhiên, không cần giải thích

_(Sếp đổi lại bất kỳ lúc nào bằng /settings)_"""

HELP_MESSAGE = """*Marketing OS — Hướng dẫn sử dụng*

/start    — Mở menu chính (GIỮ data, không reset)
/reset    — Xoá toàn bộ data, bắt đầu phân tích mới
/settings — Đổi mức độ tiếng Anh trong output
/help     — Hiển thị hướng dẫn này

*Cách sử dụng*:
1. Chọn task sếp muốn em thực hiện
2. Trả lời các câu hỏi / paste form
3. Nhận card tóm tắt + file đầy đủ
4. Đánh giá output → em note lại để cải thiện

*Mẹo*: Chạy *Trọn Bộ A→Z* trước → các task sau (Brief Campaign, Content Calendar, Landing Page) sẽ tự động dùng Strategy đó làm base.

*Thời gian*: 30-60s task đơn, 3-5p A→Z toàn diện."""


def _strip_code_fences(text: str) -> str:
    """Remove ``` fences — Telegram renders them as ugly gray code blocks with copy button."""
    # Remove opening fence (optionally with language): ```python\n or ```\n
    text = re.sub(r"```[a-zA-Z]*\s*\n?", "", text)
    # Remove any remaining closing fences
    return text.replace("```", "")


async def _safe_reply(message: Message, text: str, **kwargs):
    """Reply with markdown; fallback to plain text if Telegram parser fails.
    Also strips ``` code fences which render ugly in Telegram."""
    text = _strip_code_fences(text)
    try:
        await message.reply_text(text, **kwargs)
    except Exception as e:
        # Markdown parse error (unbalanced *, _, etc.) — strip parse_mode and retry
        if "parse" in str(e).lower() or "entities" in str(e).lower():
            logger.warning("Markdown parse failed (%s) — sending as plain text", e)
            kwargs_plain = {k: v for k, v in kwargs.items() if k != "parse_mode"}
            await message.reply_text(text, **kwargs_plain)
        else:
            raise


async def send_long_message(message: Message, text: str, **kwargs):
    """Split messages exceeding Telegram's 4096-char limit. Safe markdown fallback."""
    MAX_LEN = 4000
    if len(text) <= MAX_LEN:
        await _safe_reply(message, text, **kwargs)
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
        await _safe_reply(message, chunk, **kw)
        await asyncio.sleep(0.3)


# ─── Commands ────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show main menu. GIỮ NGUYÊN session (profile, results, feedback).
    Dùng /reset nếu muốn xoá hết bắt đầu lại.
    """
    user_id = update.effective_user.id
    session = await get_session(user_id)

    # Clear any in-flight markers (awaiting feedback/rating/edit) — user vừa /start là muốn về menu
    transient_keys = [
        "_awaiting_feedback_for", "_awaiting_rating_for", "_awaiting_followup_for",
        "_awaiting_image_edit", "_awaiting_image_reference",
        "_pending_regen_skill", "_pending_feedback",
        "_monitor_pending_page_id", "_monitor_pending_page_name",
        "_last_image_b64", "_last_image_size", "_img_prompt", "_img_n",
        "_advisor_mode",
    ]
    for k in transient_keys:
        session.pending_intake.pop(k, None)

    session.stage = PipelineStage.TASK_SELECT
    await save_session(session)

    # Sprint 1.III: First-time user → hỏi en_level trước
    if not session.preferences.get("en_level"):
        await update.message.reply_text(
            LANG_SETUP_MESSAGE,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=LANG_LEVEL_KEYBOARD,
        )
        return

    # Returning user → vào menu chính, hiển thị status nếu có data
    welcome = WELCOME_MESSAGE
    status_lines = []
    if session.profile.business_name:
        status_lines.append(f"🏢 Business: *{session.profile.business_name}*")
    if session.has_result("synthesis") or session.has_result("strategy"):
        status_lines.append("✅ Đã có Marketing Strategy")
    elif session.has_result("market_research") or session.has_result("competitor"):
        status_lines.append("⚙️ Đã chạy 1 vài bước phân tích")
    if status_lines:
        welcome = "\n".join(status_lines) + "\n\n─────────────────────────\n\n" + welcome

    await _safe_reply(
        update.message,
        welcome,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=MAIN_MENU_KEYBOARD,
    )


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sprint 1.III: /settings — đổi en_level."""
    user_id = update.effective_user.id
    session = await get_session(user_id)
    current = session.preferences.get("en_level", "moderate")
    label_map = {"none": "🔴 Không rành", "moderate": "🟡 Hiểu cơ bản", "fluent": "🟢 Thông thạo"}
    await update.message.reply_text(
        f"Khả năng tiếng Anh hiện tại của sếp: *{label_map.get(current, '🟡')}*\n\nĐổi lại nhé:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=LANG_LEVEL_KEYBOARD,
    )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hard reset — xoá profile, results, feedback. GIỮ preferences (en_level)."""
    user_id = update.effective_user.id

    # Preserve preferences
    old_session = await get_session(user_id)
    preserved_prefs = dict(old_session.preferences) if old_session.preferences else {}

    await reset_session(user_id)
    session = await get_session(user_id)
    session.preferences = preserved_prefs
    session.stage = PipelineStage.TASK_SELECT
    await save_session(session)

    await update.message.reply_text(
        "✅ *Đã xoá toàn bộ data* (profile, kết quả, feedback).\n\n"
        "_Bắt đầu phân tích mới ạ._",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=MAIN_MENU_KEYBOARD,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_MESSAGE, parse_mode=ParseMode.MARKDOWN)


# ─── Main message handler ─────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    session = await get_session(user_id)

    # Sprint 5 v2: Image edit text reply
    if session.pending_intake.get("_awaiting_image_edit"):
        await _handle_image_edit_text(update, context, session, text)
        return

    # Sprint 2: Q&A follow-up (stage COMPLETE + awaiting_followup_for OR stage COMPLETE)
    if session.pending_intake.get("_awaiting_followup_for") or session.stage == PipelineStage.COMPLETE:
        await _handle_followup(update, context, session, text)
        return

    # Advisor mode chain — sau khi user click "Hỏi tiếp"
    if session.pending_intake.get("_advisor_mode"):
        await _claude_advisor_fallback(update, context, session, text)
        return

    if session.stage in (PipelineStage.IDLE, PipelineStage.TASK_SELECT):
        # User typed free-form text instead of using keyboard
        # → Fallback: Sonnet advisor with full context
        await _claude_advisor_fallback(update, context, session, text)
        return

    elif session.stage == PipelineStage.INTAKE:
        # Sprint 2: Check feedback flow first (user typing feedback after rating ≤3)
        if session.pending_intake.get("_awaiting_feedback_for"):
            await _handle_feedback_text(update, context, session, text)
            return
        # Route to ops single-shot intake if marker present, else strategic multi-turn
        if session.pending_intake.get(OPS_INTAKE_AWAITING):
            await _handle_ops_intake_reply(update, context, session, text)
        else:
            await _handle_intake(update, context, session, text)

    elif session.pending_intake.get("_awaiting_feedback_for"):
        # User trong stage khác nhưng đang đợi feedback text → vẫn handle
        await _handle_feedback_text(update, context, session, text)

    elif session.stage == PipelineStage.CONFIRMED:
        await update.message.reply_text(
            "Nhấn *Đúng rồi, bắt đầu!* để tôi chạy phân tích nhé! Hoặc /reset để bắt đầu lại.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=CONFIRM_KEYBOARD,
        )

    else:
        await update.message.reply_text(
            "⏳ Đang phân tích... Vui lòng chờ tôi hoàn thành nhé."
        )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sprint 5 v2: User upload ảnh mẫu để bot làm theo style."""
    user_id = update.effective_user.id
    session = await get_session(user_id)

    if not session.pending_intake.get("_awaiting_image_reference"):
        await update.message.reply_text(
            "📸 Em nhận ảnh nhưng chưa biết dùng làm gì ạ. "
            "Sếp vào *Sản Xuất Nội Dung Ads* để gửi ảnh mẫu nhé!",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    await update.message.reply_text(
        "🔍 Em đang phân tích style ảnh mẫu... (~10s)",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        # Download highest-res photo
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        import io as _io
        buf = _io.BytesIO()
        await file.download_to_memory(out=buf)
        image_bytes = buf.getvalue()

        # Analyze style
        from tools.image_gen import analyze_image_style
        style_desc = await analyze_image_style(image_bytes)

        # Build final prompt = original brief + style description
        original_prompt = session.pending_intake.get("_img_prompt", "")
        combined_prompt = f"{original_prompt}\n\nStyle reference (giữ style này): {style_desc}"
        session.pending_intake["_img_prompt"] = combined_prompt[:1500]
        session.pending_intake.pop("_awaiting_image_reference", None)
        await save_session(session)

        await update.message.reply_text(
            f"✅ *Em đã phân tích style:*\n\n_{style_desc[:300]}_\n\n"
            f"Sếp muốn em tạo mấy ảnh ạ?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=IMAGE_GEN_PROMPT_KEYBOARD,
        )
    except Exception as e:
        logger.exception("Image reference analysis failed: %s", e)
        await update.message.reply_text(
            f"⚠️ Em không phân tích được ảnh: {str(e)[:200]}\n\nSếp thử ảnh khác hoặc skip ạ.",
            reply_markup=IMAGE_GEN_PROMPT_KEYBOARD,
        )


async def _handle_image_edit_text(update, context, session, text):
    """User gõ description sửa ảnh → call image edit API."""
    if not session.pending_intake.get("_last_image_b64"):
        await update.message.reply_text(
            "⚠️ Em không tìm thấy ảnh cũ. Sếp gen ảnh mới nhé.",
            reply_markup=IMAGE_GEN_PROMPT_KEYBOARD,
        )
        session.pending_intake.pop("_awaiting_image_edit", None)
        await save_session(session)
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    await update.message.reply_text(
        "🎨 Em đang sửa ảnh theo yêu cầu... (~30s)",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        import base64 as _b64
        from tools.image_gen import edit_image
        base_b64 = session.pending_intake["_last_image_b64"]
        base_bytes = _b64.b64decode(base_b64)
        img_size = session.pending_intake.get("_last_image_size", "1024x1024")

        new_images = await edit_image(
            base_image_bytes=base_bytes,
            edit_prompt=text,
            size=img_size,
            quality="medium",
            n=1,
        )

        import io as _io
        new_bytes = new_images[0] if new_images else None
        if not new_bytes:
            raise RuntimeError("Không nhận được ảnh sau edit")

        buf = _io.BytesIO(new_bytes)
        buf.name = "ads_image_edited.png"
        await update.message.reply_photo(photo=buf, caption="✨ Ảnh đã sửa")

        # Update last image for chained edits
        session.pending_intake["_last_image_b64"] = _b64.b64encode(new_bytes).decode("ascii")
        session.pending_intake.pop("_awaiting_image_edit", None)
        await save_session(session)

        await update.message.reply_text(
            "Sếp muốn sửa tiếp hay chốt ạ?",
            reply_markup=IMAGE_REVIEW_KEYBOARD,
        )
    except Exception as e:
        logger.exception("Image edit failed: %s", e)
        session.pending_intake.pop("_awaiting_image_edit", None)
        await save_session(session)
        await update.message.reply_text(
            f"⚠️ Sửa ảnh thất bại: {str(e)[:200]}\n\nSếp thử lại hoặc gen ảnh mới?",
            reply_markup=IMAGE_REVIEW_KEYBOARD,
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

        task = session.selected_task or "full"
        task_label = TASK_LABELS.get(task, "Phân tích")
        steps_desc = TASK_PIPELINE_STEPS.get(task, "")

        confirm_msg = (
            f"Tôi đã nắm được thông tin cần thiết!\n\n"
            f"🏢 *Business*: {session.profile.business_name or 'Business của bạn'}\n"
            f"📦 *Sản phẩm/DV*: {session.profile.product_service or 'Chưa xác định'}\n"
            f"👥 *Khách hàng*: {session.profile.target_customer or 'Chưa xác định'}\n"
            f"📊 *Ngành*: {industry_name}\n"
            f"🚀 *Stage*: {session.profile.stage or 'Chưa xác định'}\n"
            f"💰 *Doanh thu*: {session.profile.monthly_revenue or 'Chưa rõ'}\n"
            f"🎯 *Mục tiêu*: {session.profile.primary_goal or 'Chưa xác định'}\n"
            f"⚡ *Thách thức*: {session.profile.main_challenge or 'Chưa xác định'}\n\n"
            f"─────────────────────────\n"
            f"*Task*: {task_label}\n"
            f"{steps_desc}\n\n"
            f"Bắt đầu nhé? 🚀"
        )

        session.stage = PipelineStage.CONFIRMED
        # Profile đã extract xong → intake_history không còn giá trị, xóa để tiết kiệm storage
        session.intake_history = []
        await save_session(session)

        await _safe_reply(
            update.message,
            confirm_msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=CONFIRM_KEYBOARD,
        )
    else:
        await _safe_reply(update.message, response, parse_mode=ParseMode.MARKDOWN)


# ─── Follow-up Q&A after analysis complete ───────────────────────

async def _handle_followup(update, context, session, text):
    """Multi-turn Q&A về output skill vừa xong.
    Ưu tiên context = latest result của skill được follow-up.
    Fallback = full pipeline context.
    """
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )

    import anthropic
    from config import CLAUDE_MODEL, ANTHROPIC_API_KEY

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    # Chọn context: ưu tiên latest output của skill đang follow-up
    skill_name = session.pending_intake.get("_awaiting_followup_for") or session.selected_task or ""
    latest_output = session.get_latest_result(skill_name) if skill_name else None

    if latest_output:
        context_str = (
            f"## Output em vừa đưa ra cho sếp ({skill_name}):\n\n"
            f"{latest_output}\n\n"
            f"## Profile business:\n{session.profile.to_context_string()}"
        )
    else:
        context_str = session.build_pipeline_context()

    system_text = (
        "Bạn là Max, AI CMO của founder Việt Nam. "
        "Sếp vừa hỏi follow-up về output em đưa ra. "
        "Trả lời BÁM SÁT output đã có. Nếu sếp hỏi ngoài scope, "
        "gợi ý chạy skill khác phù hợp.\n\n"
        "Tone: em/sếp, professional nhưng thân thiện. "
        "Trả lời ngắn gọn (1-3 đoạn), tập trung. Không lặp lại nguyên output."
    )

    response = await client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        system=[{
            "type": "text",
            "text": system_text,
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
        reply_markup=ASK_FOLLOWUP_KEYBOARD,
    )


# ─── Callback (inline keyboard) ──────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    session = await get_session(user_id)
    data = query.data

    try:
        return await _handle_callback_inner(update, context, query, session, data, user_id)
    except Exception as e:
        # Fallback for unhandled callback errors — at least tell user something
        logger.exception("Callback handler error (data=%s): %s", data, e)
        try:
            await query.message.reply_text(
                "⚠️ Có lỗi xảy ra. Gõ /start để bắt đầu lại nhé."
            )
        except Exception:
            pass


async def _handle_callback_inner(update, context, query, session, data, user_id):

    # ── Competitor → Compare follow-up (Sprint 4) ─────────────────
    if data == "run_compare":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "Em đang so sánh business của sếp với landscape đối thủ...",
            parse_mode=ParseMode.MARKDOWN,
        )
        try:
            result = await run_operational_skill("competitor_comparison", session)
            await save_session(session)
            await _send_ops_result(query.message, session, "competitor_comparison", result)
        except Exception as e:
            logger.exception("Comparison failed: %s", e)
            await query.message.reply_text(f"⚠️ Lỗi so sánh: {str(e)[:200]}")
        return

    if data == "skip_compare":
        await query.edit_message_reply_markup(reply_markup=None)
        # Show rating cho competitor như bình thường
        session.pending_intake["_awaiting_rating_for"] = "competitor"
        await save_session(session)
        await query.message.reply_text(
            "OK ạ. Sếp đánh giá output Phân Tích Đối Thủ vừa rồi thế nào?",
            reply_markup=RATING_KEYBOARD,
        )
        return

    # ── Rating callback (Sprint 2) ───────────────────────────────
    if data.startswith("rate_"):
        skill_name = session.pending_intake.get("_awaiting_rating_for")

        # Skip rating → đi thẳng action keyboard
        if data == "rate_skip":
            session.pending_intake.pop("_awaiting_rating_for", None)
            await save_session(session)
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(
                "OK ạ! Sếp muốn làm gì tiếp?",
                reply_markup=get_action_keyboard(skill_name or ""),
            )
            return

        try:
            rating = int(data.replace("rate_", ""))
        except ValueError:
            return
        if rating < 1 or rating > 5:
            return

        if not skill_name:
            await query.message.reply_text("Cảm ơn sếp! 🙏")
            return

        # Lưu rating vào session.feedback
        from datetime import datetime
        versions = session.results.get(skill_name, [])
        latest_version = versions[-1].version if versions else 0
        session.feedback.setdefault(skill_name, []).append({
            "version": latest_version,
            "rating": rating,
            "feedback": "",
            "created_at": datetime.utcnow().isoformat(),
        })

        # Log to feedback_log table (Task #12)
        try:
            await _log_feedback_to_db(session, skill_name, rating, "")
        except Exception as e:
            logger.warning("Feedback DB log failed (non-blocking): %s", e)

        await query.edit_message_reply_markup(reply_markup=None)

        if rating >= 4:
            # Rating cao → cảm ơn, hiện action keyboard theo category
            session.pending_intake.pop("_awaiting_rating_for", None)
            await save_session(session)
            await query.message.reply_text(
                "Cảm ơn sếp đã feedback! 🙏\n\nSếp muốn làm gì tiếp?",
                reply_markup=get_action_keyboard(skill_name),
            )
        else:
            # Rating ≤ 3 → hỏi feedback chi tiết
            session.pending_intake["_awaiting_feedback_for"] = skill_name
            session.pending_intake.pop("_awaiting_rating_for", None)
            await save_session(session)
            await query.message.reply_text(
                "Cảm ơn sếp! Sếp note giúp em chỗ nào chưa OK để em note lại nhé ạ?\n\n"
                "_Sếp gõ thoải mái — càng cụ thể em càng sửa được chính xác._",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=FEEDBACK_PROMPT_KEYBOARD,
            )
        return

    # Sprint 2 v2: User skip feedback text → action keyboard
    if data == "feedback_skip":
        skill_name = session.pending_intake.get("_awaiting_feedback_for", "")
        session.pending_intake.pop("_awaiting_feedback_for", None)
        await save_session(session)
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "OK ạ, cảm ơn sếp! 🙏",
            reply_markup=get_action_keyboard(skill_name),
        )
        return

    # ── Regen decision (Sprint 2) ────────────────────────────────
    if data == "regen_yes":
        skill_name = session.pending_intake.get("_pending_regen_skill")
        feedback = session.pending_intake.get("_pending_feedback", "")
        if not skill_name:
            await query.edit_message_text("Có lỗi, sếp gõ /start lại nhé.")
            return

        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "Em đang chạy lại theo feedback của sếp...",
            parse_mode=ParseMode.MARKDOWN,
        )

        # Inject user correction vào pending_intake để build_user_msg đọc
        session.pending_intake["_user_correction"] = feedback
        session.pending_intake.pop("_pending_regen_skill", None)
        session.pending_intake.pop("_pending_feedback", None)
        await save_session(session)

        try:
            # Dispatch lại theo loại skill
            SINGLE_SHOT_STRATEGIC = {"market", "competitor", "customer", "pricing"}

            if skill_name in SINGLE_SHOT_STRATEGIC:
                from agents.pipeline import run_strategic_single_skill
                result = await run_strategic_single_skill(skill_name, session)
            elif skill_name in OPERATIONAL_TASKS:
                result = await run_operational_skill(skill_name, session)
            else:
                await query.message.reply_text("⚠️ Em không re-run được skill này.")
                return

            # Clear correction marker sau khi dùng
            session.pending_intake.pop("_user_correction", None)
            await save_session(session)
            await _send_ops_result(query.message, session, skill_name, result)
        except Exception as e:
            logger.exception("Regen failed: %s", e)
            await query.message.reply_text(f"⚠️ Re-run gặp lỗi: {str(e)[:200]}")
        return

    if data == "regen_no":
        # User skip regen — feedback đã lưu DB rồi qua _handle_feedback_text
        skill_name = session.pending_intake.get("_pending_regen_skill")
        feedback = session.pending_intake.get("_pending_feedback", "")
        session.pending_intake.pop("_pending_regen_skill", None)
        session.pending_intake.pop("_pending_feedback", None)
        await save_session(session)

        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "OK ạ, cảm ơn sếp! 🙏",
            reply_markup=get_action_keyboard(skill_name or ""),
        )
        logger.info("FEEDBACK [%s] rating_low (regen_skip): %s", skill_name, feedback[:200])
        return

    # ── Language preference setup (Sprint 1.III) ─────────────────
    if data.startswith("lang_"):
        level = data.replace("lang_", "")  # "none" / "moderate" / "fluent"
        if level not in ("none", "moderate", "fluent"):
            return
        session.preferences["en_level"] = level
        await save_session(session)

        level_label = {
            "none": "🔴 Không rành — Em sẽ dùng thuần Việt",
            "moderate": "🟡 Hiểu cơ bản — Em dùng EN có giải thích",
            "fluent": "🟢 Thông thạo — Em dùng EN tự nhiên",
        }[level]

        try:
            await query.edit_message_text(
                f"✅ Em ghi nhận ạ: *{level_label}*\n\nGiờ vào việc thôi sếp! 👇",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass
        await query.message.reply_text(
            WELCOME_MESSAGE,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=MAIN_MENU_KEYBOARD,
        )
        return

    # ── Menu navigation (tier 1 → tier 2) ─────────────────────────
    if data == "menu_main":
        # Clear advisor mode marker khi về menu
        session.pending_intake.pop("_advisor_mode", None)
        await save_session(session)
        try:
            await query.edit_message_text(
                WELCOME_MESSAGE,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=MAIN_MENU_KEYBOARD,
            )
        except Exception:
            # Nếu edit fail (message quá cũ), send new message
            await query.message.reply_text(
                WELCOME_MESSAGE,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=MAIN_MENU_KEYBOARD,
            )
        return

    if data == "menu_strategic":
        await query.edit_message_text(
            "🎯 *Chiến lược* — phân tích sâu để ra quyết định lớn\n\nChọn task:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=STRATEGIC_KEYBOARD,
        )
        return

    if data == "menu_operational":
        await query.edit_message_text(
            "⚙️ *Sản xuất* — deliverable dùng hàng tuần\n\nChọn task:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=OPERATIONAL_KEYBOARD,
        )
        return

    if data == "menu_analysis":
        await query.edit_message_text(
            "📊 *Đánh giá* — audit campaign đang chạy\n\nChọn task:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ANALYSIS_KEYBOARD,
        )
        return

    # ── Variant choosers for special ops skills ───────────────────
    if data.startswith("ads_tier_"):
        tier = data.replace("ads_tier_", "")  # tofu / mofu / bofu / all
        session.pending_intake["selected_tiers"] = tier
        await save_session(session)
        await query.edit_message_reply_markup(reply_markup=None)
        # Sprint 5: Sau tier chọn → ask format (Video / Ảnh)
        tier_label = {"tofu": "TOFU (Tệp lạnh)", "mofu": "MOFU (Tệp ấm)",
                      "bofu": "BOFU (Tệp nóng)", "all": "All 3 tầng"}.get(tier, tier)
        await query.message.reply_text(
            f"✅ Tier: *{tier_label}*\n\nSếp muốn format Video hay Ảnh ạ?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ADS_FORMAT_KEYBOARD,
        )
        return

    if data.startswith("ads_format_"):
        ads_format = data.replace("ads_format_", "")  # "video" or "image"
        session.pending_intake["ads_format"] = ads_format
        await save_session(session)
        await query.edit_message_reply_markup(reply_markup=None)
        skill_name = session.selected_task or "ads_generator"
        await _send_single_shot_form(query.message, session, skill_name)
        return

    # Sprint 5: Image generation flow ──────────────────────────────
    if data.startswith("img_gen_"):
        choice = data.replace("img_gen_", "")  # "1", "3", or "skip"
        if choice == "skip":
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(
                "OK ạ, em chỉ gửi brief thôi. Team design của sếp tự làm tiếp nhé.",
                reply_markup=stage_done_keyboard(is_last=True),
            )
            return

        n_images = int(choice) if choice.isdigit() else 1
        session.pending_intake["_img_n"] = str(n_images)
        await save_session(session)
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"OK ạ, em sẽ tạo *{n_images} ảnh*. Sếp pick kích thước:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=IMAGE_SIZE_KEYBOARD,
        )
        return

    if data.startswith("img_size_"):
        size_choice = data.replace("img_size_", "")
        size_map = {"vertical": "1024x1536", "square": "1024x1024", "horizontal": "1536x1024"}
        img_size = size_map.get(size_choice, "1024x1024")
        n_images = int(session.pending_intake.get("_img_n", "1"))
        img_prompt = session.pending_intake.get("_img_prompt", "")

        if not img_prompt:
            await query.edit_message_text("⚠️ Chưa có brief ảnh để gen. Sếp /start lại.")
            return

        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"🎨 Em đang tạo {n_images} ảnh ({img_size})... (~30-60s)",
            parse_mode=ParseMode.MARKDOWN,
        )

        try:
            from tools.image_gen import generate_image
            images = await generate_image(img_prompt, size=img_size, quality="medium", n=n_images)
            import io as _io
            last_image_bytes = None
            for i, img_bytes in enumerate(images, start=1):
                buf = _io.BytesIO(img_bytes)
                buf.name = f"ads_image_{i}.png"
                await query.message.reply_photo(
                    photo=buf,
                    caption=f"🖼️ Ảnh {i}/{n_images}",
                )
                last_image_bytes = img_bytes
            # Lưu ảnh cuối cùng (để edit nếu user muốn sửa)
            if last_image_bytes:
                import base64 as _b64
                session.pending_intake["_last_image_b64"] = _b64.b64encode(last_image_bytes).decode("ascii")
                session.pending_intake["_last_image_size"] = img_size
            await save_session(session)
            await query.message.reply_text(
                f"✅ *Em tạo xong {n_images} ảnh!*\n\nSếp muốn sửa hay chốt ảnh này ạ?",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=IMAGE_REVIEW_KEYBOARD,
            )
        except Exception as e:
            logger.exception("Image gen failed: %s", e)
            await query.message.reply_text(
                f"⚠️ Gen ảnh thất bại: {str(e)[:200]}\n\nSếp check OPENAI_API_KEY trong Railway env vars."
            )
        return

    # ── Auto monitor flow ────────────────────────────────────────
    if data == "monitor_yes":
        # User chấp nhận → hỏi interval
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "⏰ *Em check mỗi bao lâu 1 lần ạ?*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=MONITOR_INTERVAL_KEYBOARD,
        )
        return

    if data == "monitor_no":
        # Skip monitor → tiếp tục flow rating bình thường
        session.pending_intake.pop("_monitor_pending_page_id", None)
        session.pending_intake.pop("_monitor_pending_page_name", None)
        await save_session(session)
        await query.edit_message_reply_markup(reply_markup=None)
        # Show rating cho competitor_spy
        task_name = session.selected_task or "competitor_spy"
        session.pending_intake["_awaiting_rating_for"] = task_name
        await save_session(session)
        await query.message.reply_text(
            "OK ạ! Sếp đánh giá output em vừa làm thế nào ạ?",
            reply_markup=RATING_KEYBOARD,
        )
        return

    if data.startswith("monitor_iv_"):
        # User chọn interval → lưu DB
        try:
            interval_hours = int(data.replace("monitor_iv_", ""))
        except ValueError:
            return

        page_id = session.pending_intake.get("_monitor_pending_page_id")
        page_name = session.pending_intake.get("_monitor_pending_page_name") or ""
        ad_ids_str = session.pending_intake.get("_fb_ad_ids", "")
        ad_ids = [aid for aid in ad_ids_str.split(",") if aid]

        if not page_id:
            await query.edit_message_text("⚠️ Có lỗi, sếp /start lại nhé.")
            return

        await query.edit_message_reply_markup(reply_markup=None)
        try:
            from storage.tracked_competitors import add_tracked
            ok = await add_tracked(
                user_id=user_id,
                page_id=page_id,
                page_name=page_name,
                interval_hours=interval_hours,
                ad_ids=ad_ids,
            )
            interval_label = {3: "3 giờ", 6: "6 giờ", 12: "12 giờ", 24: "1 ngày", 168: "1 tuần"}.get(interval_hours, f"{interval_hours}h")
            if ok:
                await query.message.reply_text(
                    f"✅ *Em sẽ theo dõi {page_name}!*\n\n"
                    f"_Mỗi {interval_label}, em check 1 lần và báo sếp ngay khi có ads mới._",
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                await query.message.reply_text(
                    "⚠️ Có lỗi khi lưu tracking. Em báo admin để fix ạ.",
                )
        except Exception as e:
            logger.exception("Add tracked failed: %s", e)
            await query.message.reply_text(
                f"⚠️ Lưu tracking thất bại: {str(e)[:200]}",
            )

        # Cleanup markers
        session.pending_intake.pop("_monitor_pending_page_id", None)
        session.pending_intake.pop("_monitor_pending_page_name", None)
        await save_session(session)

        # Tiếp tục rating
        task_name = session.selected_task or "competitor_spy"
        session.pending_intake["_awaiting_rating_for"] = task_name
        await save_session(session)
        await query.message.reply_text(
            "Tiện thể — sếp đánh giá output em vừa làm thế nào ạ?",
            reply_markup=RATING_KEYBOARD,
        )
        return

    if data.startswith("monitor_diff_"):
        # User click "Phân tích ads mới" từ notification
        page_id = data.replace("monitor_diff_", "")
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"🔍 Em đang phân tích ads mới của đối thủ này...",
            parse_mode=ParseMode.MARKDOWN,
        )
        try:
            from tools.fb_ads_library import search_by_page_id, format_ads_for_analysis
            ads = await search_by_page_id(page_id, country="VN", limit=10)
            # Chỉ phân tích N ads mới nhất (sort by start_time desc)
            ads_sorted = sorted(ads, key=lambda a: a.get("ad_delivery_start_time", ""), reverse=True)[:5]
            fb_data = format_ads_for_analysis(ads_sorted, "đối thủ")

            # Inject diff-mode data + run competitor_spy
            session.pending_intake["_fb_data"] = (
                "**[DIFF MODE — phân tích ads MỚI nhất]**\n\n" + fb_data +
                "\n\nFocus: đối thủ vừa thay đổi gì? Hint angle/strategy mới? Mình react thế nào (3 action cụ thể)?"
            )
            session.selected_task = "competitor_spy"
            await save_session(session)

            result = await run_operational_skill("competitor_spy", session)
            await save_session(session)
            await _send_ops_result(query.message, session, "competitor_spy", result)
        except Exception as e:
            logger.exception("Monitor diff analysis failed: %s", e)
            await query.message.reply_text(f"⚠️ Phân tích thất bại: {str(e)[:200]}")
        return

    if data == "monitor_skip_diff":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("OK ạ! Em tiếp tục theo dõi và báo sếp lần sau nhé.")
        return

    # Sprint 5 v2: Image reference upload flow
    if data == "img_ref_upload":
        await query.edit_message_reply_markup(reply_markup=None)
        session.pending_intake["_awaiting_image_reference"] = "1"
        await save_session(session)
        await query.message.reply_text(
            "📤 *Sếp gửi ảnh mẫu vào đây nhé!*\n\n"
            "_Em sẽ phân tích style ảnh đó và làm theo._",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if data == "img_ref_skip":
        # Tự gen theo brief, không có ảnh mẫu
        await query.edit_message_reply_markup(reply_markup=None)
        session.pending_intake.pop("_awaiting_image_reference", None)
        await save_session(session)
        await query.message.reply_text(
            "🎨 OK, em tự gen theo brief. Sếp muốn em tạo mấy ảnh ạ?",
            reply_markup=IMAGE_GEN_PROMPT_KEYBOARD,
        )
        return

    if data == "img_ref_no_gen":
        await query.edit_message_reply_markup(reply_markup=None)
        session.pending_intake.pop("_awaiting_image_reference", None)
        await save_session(session)
        await query.message.reply_text(
            "OK ạ, em chỉ gửi copy thôi. Sếp đánh giá output em vừa làm thế nào ạ?",
            reply_markup=RATING_KEYBOARD,
        )
        session.pending_intake["_awaiting_rating_for"] = session.selected_task or ""
        await save_session(session)
        return

    # Sprint 5 v2: Image review (Sửa / Chốt / Regen)
    if data == "img_edit":
        await query.edit_message_reply_markup(reply_markup=None)
        session.pending_intake["_awaiting_image_edit"] = "1"
        await save_session(session)
        await query.message.reply_text(
            "✏️ *Sếp muốn sửa gì ạ?*\n\n"
            "_Vd:_\n"
            "_• 'đổi nền sang biển'_\n"
            "_• 'thêm text \"Giảm 50%\" góc phải'_\n"
            "_• 'sáng hơn, ấm hơn'_\n"
            "_• 'bỏ logo bên góc trái'_",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if data == "img_confirm":
        await query.edit_message_reply_markup(reply_markup=None)
        # Clean image buffers
        session.pending_intake.pop("_last_image_b64", None)
        session.pending_intake.pop("_last_image_size", None)
        session.pending_intake.pop("_img_n", None)
        session.pending_intake.pop("_img_prompt", None)
        await save_session(session)
        await query.message.reply_text(
            "✅ Chốt! Sếp đánh giá output em vừa làm thế nào ạ?",
            reply_markup=RATING_KEYBOARD,
        )
        session.pending_intake["_awaiting_rating_for"] = session.selected_task or ""
        await save_session(session)
        return

    if data == "img_regen":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "🔁 OK, em gen ảnh khác. Mấy ảnh ạ?",
            reply_markup=IMAGE_GEN_PROMPT_KEYBOARD,
        )
        return

    if data.startswith("video_creator_"):
        creator = data.replace("video_creator_", "")  # ugc / egc / fgc / kol
        session.pending_intake["creator_type"] = creator
        await save_session(session)
        await query.edit_message_reply_markup(reply_markup=None)
        await _send_single_shot_form(query.message, session, "video_scripts")
        return

    # ── Task selection ────────────────────────────────────────────
    if data.startswith("task_"):
        task_type = data[5:]
        session.selected_task = task_type
        session.pending_intake = {}  # reset for fresh single-shot intake
        await save_session(session)

        # ── Smart gating: skill cần Strategy base ─────────────────
        STRATEGY_GATED_SKILLS = {"campaign_brief", "content_calendar", "landing_page"}
        if task_type in STRATEGY_GATED_SKILLS:
            await query.edit_message_reply_markup(reply_markup=None)
            # Check session có synthesis result chưa
            has_strategy = bool(
                session.get_latest_result("synthesis")
                or session.get_latest_result("strategy")
            )
            if has_strategy:
                # YES branch — leverage roadmap
                await _send_strategy_aware_form(query.message, session, task_type)
                return
            # NO branch — suggest A→Z
            task_label = (get_task(task_type).label if get_task(task_type) else task_type)
            session.pending_followup_skill = task_type  # store for chain
            await save_session(session)
            await query.message.reply_text(
                f"📋 *{task_label} chuyên sâu cần có Marketing Strategy nền.*\n\n"
                f"Em chưa có data Strategy của sếp.\n\n"
                f"Để output chính xác (đúng audience, đúng goals, đúng channels), "
                f"em chạy *Phân Tích Tổng Hợp A→Z* trước nhé. (~5-7 phút, 5 bước)\n\n"
                f"_Sau khi A→Z xong, em tự động tiếp tục {task_label} cho sếp._",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=NEEDS_STRATEGY_KEYBOARD,
            )
            return

        # ── Content Generator: cần Calendar trước ─────────────────
        if task_type == "content_generator":
            has_calendar = bool(session.get_latest_result("content_calendar"))
            if not has_calendar:
                await query.edit_message_reply_markup(reply_markup=None)
                session.pending_followup_skill = "content_generator"
                await save_session(session)
                await query.message.reply_text(
                    "✍️ *Sản Xuất Nội Dung cần có Lịch Nội Dung trước ạ.*\n\n"
                    "Em chưa có Calendar của sếp.\n\n"
                    "Em chạy *Lịch Nội Dung* trước nhé — sau đó em tự động "
                    "tiếp tục sản xuất content theo lịch đó cho sếp.",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📅 Chạy Lịch Nội Dung trước", callback_data="task_content_calendar")],
                        [InlineKeyboardButton("⏭️ Quay lại menu",              callback_data="menu_main")],
                    ]),
                )
                return

        # Operational skills → single-shot form (or variant chooser first)
        if task_type in OPERATIONAL_TASKS:
            await query.edit_message_reply_markup(reply_markup=None)

            # Special skills with variant chooser
            if task_type in ("ads_copy", "ads_generator"):
                # Lưu real skill name (cùng AdsCopySkill class)
                session.selected_task = "ads_generator"
                await save_session(session)
                await query.message.reply_text(
                    "📢 *Sản Xuất Nội Dung Ads* — Sếp muốn gen tier nào trước ạ?",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=ADS_COPY_TIER_KEYBOARD,
                )
                return
            if task_type == "video_scripts":
                await query.message.reply_text(
                    "🎬 *Viết Kịch Bản Video* — Brief cho loại creator nào ạ?",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=VIDEO_CREATOR_KEYBOARD,
                )
                return

            # Standard ops: jump straight to single-shot form
            await _send_single_shot_form(query.message, session, task_type)
            return

        # ── Strategic skills ─────────────────────────────────────
        # Phase 1.3: Profile reuse — nếu profile đã có required fields, skip intake
        if not needs_intake(session, task_type):
            await query.edit_message_reply_markup(reply_markup=None)
            await _show_profile_reuse_confirm(query.message, session, task_type)
            return

        # Phase 3: Strategic single-skill (market/competitor/customer/pricing) → single-shot form
        # KHÔNG dùng multi-turn để tránh hỏi đi hỏi lại
        # ONLY full + strategy giữ multi-turn (vì cần full profile + explore)
        SINGLE_SHOT_STRATEGIC = {"market", "competitor", "customer", "pricing"}
        if task_type in SINGLE_SHOT_STRATEGIC:
            task = get_task(task_type)
            if task and task.intake_fields:  # Phase 3: nếu task có template form
                await query.edit_message_reply_markup(reply_markup=None)
                await _send_single_shot_form(query.message, session, task_type)
                return

        # Profile chưa đủ + không phải single-shot → multi-turn intake (full / strategy)
        session.stage = PipelineStage.INTAKE
        await save_session(session)

        task_label = TASK_LABELS.get(task_type, "Phân tích")
        opening = TASK_OPENING_QUESTIONS.get(task_type, TASK_OPENING_QUESTIONS["full"])

        try:
            await query.edit_message_text(
                f"✅ *{task_label}*\n\n{opening}",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            logger.warning("edit_message_text markdown failed: %s — retrying as plain text", e)
            await query.edit_message_text(f"✅ {task_label}\n\n{opening}")

    # ── Pipeline confirmation ─────────────────────────────────────
    elif data == "confirm_yes":
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

        task = session.selected_task or "full"
        opening = TASK_OPENING_QUESTIONS.get(task, TASK_OPENING_QUESTIONS["full"])
        await query.edit_message_text(
            f"Không sao! Hãy mô tả lại — tôi nghe lại từ đầu nhé 🙂\n\n{opening}",
            parse_mode=ParseMode.MARKDOWN,
        )

    # ── Restart ───────────────────────────────────────────────────
    elif data == "restart":
        await reset_session(user_id)
        session = await get_session(user_id)
        session.stage = PipelineStage.TASK_SELECT
        await save_session(session)
        # Pattern an toàn: bỏ keyboard cũ, gửi tin mới (tránh edit failures với message cũ)
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception as e:
            logger.warning("restart: edit_reply_markup failed: %s", e)
        await query.message.reply_text(
            "✅ Đã reset! Bạn muốn Max làm gì hôm nay?",
            reply_markup=TASK_SELECT_KEYBOARD,
        )

    elif data == "run_az_then_back":
        # User chấp nhận chạy A→Z, sau đó tự quay lại skill ban đầu
        # pending_followup_skill đã được set ở bước trước
        await query.edit_message_reply_markup(reply_markup=None)
        session.selected_task = "full"
        await save_session(session)

        # Nếu profile đã đủ → CONFIRMED, chạy luôn
        if session.profile.is_ready_for_analysis():
            session.stage = PipelineStage.CONFIRMED
            await save_session(session)
            await query.message.reply_text(
                "🚀 *Bắt đầu Phân Tích Tổng Hợp A→Z...*",
                parse_mode=ParseMode.MARKDOWN,
            )
            session.stage = PipelineStage.MARKET_RESEARCH
            await save_session(session)
            await _run_pipeline_sequentially(query.message, session)
        else:
            # Cần multi-turn intake trước
            session.stage = PipelineStage.INTAKE
            await save_session(session)
            opening = TASK_OPENING_QUESTIONS.get("full", TASK_OPENING_QUESTIONS["full"])
            await query.message.reply_text(
                f"✅ *Chuẩn bị Phân Tích Tổng Hợp A→Z*\n\n{opening}",
                parse_mode=ParseMode.MARKDOWN,
            )
        return

    elif data == "continue_advisor":
        await query.edit_message_reply_markup(reply_markup=None)
        session.pending_intake["_advisor_mode"] = "1"
        await save_session(session)
        await query.message.reply_text(
            "💬 Sếp gõ tiếp câu hỏi nhé!",
        )
        return

    elif data == "ask_followup":
        # Multi-turn Q&A về output skill vừa xong
        skill_name = session.selected_task
        session.pending_intake["_awaiting_followup_for"] = skill_name or ""
        session.stage = PipelineStage.COMPLETE
        await save_session(session)
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "💬 *Sếp hỏi gì về output vừa rồi?*\n\n"
            "_Em trả lời bám sát kết quả em vừa đưa ra. "
            "Gõ thoải mái nhé._",
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "rerun_current_task":
        # Chạy lại cùng task với input mới (fresh form, giữ profile)
        task_name = session.selected_task
        if not task_name:
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(
                "⚠️ Em không nhớ task vừa chạy. Sếp chọn lại từ menu nhé.",
                reply_markup=MAIN_MENU_KEYBOARD,
            )
            return

        # Clear intake cũ (giữ preferences, profile, results)
        session.pending_intake = {}
        await save_session(session)
        await query.edit_message_reply_markup(reply_markup=None)

        # Dispatch lại theo loại task
        SINGLE_SHOT_STRATEGIC = {"market", "competitor", "customer", "pricing"}

        if task_name in OPERATIONAL_TASKS:
            # Special skills cần variant chooser trước
            if task_name in ("ads_copy", "ads_generator"):
                await query.message.reply_text(
                    "📢 *Sản Xuất Nội Dung Ads* — Sếp muốn gen tier nào ạ?",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=ADS_COPY_TIER_KEYBOARD,
                )
                return
            if task_name == "video_scripts":
                await query.message.reply_text(
                    "🎬 *Viết Kịch Bản Video* — Brief cho loại creator nào ạ?",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=VIDEO_CREATOR_KEYBOARD,
                )
                return
            await _send_single_shot_form(query.message, session, task_name)
            return

        if task_name in SINGLE_SHOT_STRATEGIC:
            task = get_task(task_name)
            if task and task.intake_fields:
                await _send_single_shot_form(query.message, session, task_name)
                return

        # Full pipeline / strategy → confirm với profile cũ rồi chạy
        if not needs_intake(session, task_name):
            await _show_profile_reuse_confirm(query.message, session, task_name)
            return

        # Fallback: về menu
        await query.message.reply_text(
            "Sếp chọn task từ menu nhé:",
            reply_markup=MAIN_MENU_KEYBOARD,
        )


# ─── Pipeline runner ─────────────────────────────────────────────

def _format_card(stage_key: str, parsed: dict) -> str:
    """Build Format-B Telegram card from parsed agent output."""
    header = STAGE_HEADERS.get(stage_key, stage_key.upper())
    parts = [f"*{header}*", "━" * 25, ""]

    if parsed.get("insight"):
        insight = parsed["insight"].strip().strip('"').strip("'")
        parts.append("💡 *Insight quan trọng nhất:*")
        parts.append(f"_{insight}_")
        parts.append("")

    if parsed.get("summary"):
        parts.append("📌 *Tóm tắt:*")
        parts.append(parsed["summary"].strip())
        parts.append("")

    if parsed.get("benchmarks"):
        parts.append("📊 *Benchmarks:*")
        parts.append(parsed["benchmarks"].strip())
        parts.append("")

    # If nothing parsed, fallback to raw detail (truncated)
    if not any(parsed.get(k) for k in ("insight", "summary", "benchmarks")):
        detail = parsed.get("detail", "")[:1500]
        parts.append(detail)

    parts.append("📎 _Xem full analysis trong file HTML cuối pipeline_")
    return "\n".join(parts)


# ─── Operational skill flow ──────────────────────────────────────

OPS_INTAKE_AWAITING = "ops_intake_awaiting"  # marker stored in pending_intake

async def _show_profile_reuse_confirm(message: Message, session, task_name: str):
    """Phase 1.3: Strategic task có profile đầy đủ → show confirm card với data cũ,
    user pick confirm → chạy luôn pipeline, không multi-turn intake."""
    task = get_task(task_name)
    profile = session.profile
    label = task.label if task else task_name
    emoji = task.button_emoji if task else "🎯"

    fw = KPI_LIBRARY.get(profile.industry or "")
    industry_name = fw.display_name if fw else (profile.industry or "Chưa xác định")

    # Build profile recap — chỉ hiện fields liên quan
    profile_lines = []
    profile_lines.append(f"🏢 *Business*: {profile.business_name or 'Business của bạn'}")
    profile_lines.append(f"📦 *Sản phẩm/DV*: {profile.product_service or '—'}")
    profile_lines.append(f"👥 *Khách hàng*: {profile.target_customer or '—'}")
    profile_lines.append(f"📊 *Ngành*: {industry_name}")
    if profile.location:
        profile_lines.append(f"📍 *Địa bàn*: {profile.location}")
    if profile.monthly_revenue:
        profile_lines.append(f"💰 *Doanh thu*: {profile.monthly_revenue}")
    if profile.primary_goal:
        profile_lines.append(f"🎯 *Mục tiêu*: {profile.primary_goal}")
    if profile.main_challenge:
        profile_lines.append(f"⚡ *Thách thức*: {profile.main_challenge}")
    if profile.competitors and task_name == "competitor":
        profile_lines.append(f"🕵️ *Đối thủ*: {profile.competitors}")

    confirm_msg = (
        f"{emoji} *{label}*\n\n"
        f"Tôi đã có thông tin business của bạn từ trước — không cần hỏi lại:\n\n"
        + "\n".join(profile_lines) + "\n\n"
        f"─────────────────────────\n"
        f"Bắt đầu *{label}* luôn nhé? 🚀\n"
        f"_(Nếu muốn cập nhật profile, bấm 'Sửa thông tin')_"
    )

    session.stage = PipelineStage.CONFIRMED
    await save_session(session)

    await message.reply_text(
        confirm_msg,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=CONFIRM_KEYBOARD,
    )


async def _send_strategy_aware_form(message: Message, session, task_name: str):
    """Khi user đã có Strategy (synthesis) — show form rút gọn tham chiếu roadmap.
    Áp dụng cho: campaign_brief, content_calendar, landing_page.
    """
    task = get_task(task_name)
    if not task:
        await _send_single_shot_form(message, session, task_name)
        return

    # Extract roadmap campaigns từ synthesis nếu parse được
    synthesis = session.get_latest_result("synthesis") or session.get_latest_result("strategy") or ""
    campaigns_hint = _extract_campaigns_from_strategy(synthesis)

    lines = [
        f"✅ *{task.button_emoji} {task.label}*",
        "",
        f"_Em thấy sếp đã có Marketing Strategy rồi. Em dùng strategy đó làm base._",
        "",
        "─────────────────────────",
    ]

    if campaigns_hint:
        lines.append("📅 *Roadmap của sếp có các campaigns:*")
        lines.append("")
        for i, c in enumerate(campaigns_hint, 1):
            lines.append(f"{i}️⃣ {c}")
        lines.append("")
        lines.append("─────────────────────────")

    lines.extend([
        "*Sếp trả lời 1 lần các ý sau:*",
        "",
        "**1️⃣ Chọn campaign nào?**",
        "  - Gõ số (1/2/3...) để chọn từ roadmap",
        "  - Hoặc tả campaign mới (ngoài roadmap)",
        "",
        "**2️⃣ Có muốn đổi thời gian / ngân sách không?**",
        "  _Vd: 'kéo 12 tuần thay vì 8, budget 80tr'_",
        "  _Hoặc 'giữ nguyên theo roadmap'_",
        "",
        "**3️⃣ Audience có khác ICP đã định không?**",
        "  _Nếu không nói gì, em dùng ICP cũ._",
        "",
        "─────────────────────────",
        "💬 *Gửi tin trả lời theo format trên — Max sẽ tự parse và chạy.*",
    ])

    # Mark session: form này có Strategy context
    session.pending_intake[OPS_INTAKE_AWAITING] = task_name
    session.pending_intake["_strategy_aware"] = "1"
    session.selected_task = task_name
    session.stage = PipelineStage.INTAKE
    await save_session(session)

    await message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


def _extract_campaigns_from_strategy(synthesis_text: str) -> list[str]:
    """Best-effort extract campaign names from strategy text.
    Looks for bullet points / numbered lists in roadmap sections."""
    if not synthesis_text:
        return []
    import re as _re
    candidates = []

    # Pattern 1: "Q1: xxx" or "Tháng 1: xxx"
    matches = _re.findall(r"(?:Q[1-4]|Tháng \d+|Week \d+)[:\s-]+([^\n]{10,120})", synthesis_text)
    candidates.extend(m.strip(' .*-') for m in matches)

    # Pattern 2: Bullet "- Campaign X: ..."
    matches2 = _re.findall(r"[-*•]\s*Campaign[:\s]+([^\n]{5,120})", synthesis_text, flags=_re.IGNORECASE)
    candidates.extend(m.strip(' .*-') for m in matches2)

    # Dedupe + cap 5
    seen = set()
    result = []
    for c in candidates:
        c_low = c.lower()[:50]
        if c_low not in seen:
            seen.add(c_low)
            result.append(c[:120])
        if len(result) >= 5:
            break
    return result


async def _send_single_shot_form(message: Message, session, task_name: str):
    """Send a paste-template form for ops skill intake.
    User fills in template, replies once with all fields."""
    task = get_task(task_name)
    if not task:
        await message.reply_text(f"⚠️ Skill {task_name} không tồn tại.")
        return

    lines = [
        f"✅ *{task.button_emoji} {task.label}*",
        "",
        f"_{task.description}_",
        "",
        "─────────────────────────",
        "*Copy template dưới, điền vào (hoặc thay example), gửi lại 1 lần:*",
        "",
    ]
    for f in task.intake_fields:
        required_mark = "" if f.get("required", True) else " _(không bắt buộc)_"
        lines.append(f"*{f['label']}*{required_mark}:")
        lines.append(f"_Vd: {f.get('example', '...')}_")
        lines.append("")

    lines.append("─────────────────────────")
    lines.append("💬 *Gửi tin trả lời theo format trên — Max sẽ tự parse và chạy.*")

    # Mark session as waiting for ops intake
    session.pending_intake[OPS_INTAKE_AWAITING] = task_name
    session.selected_task = task_name
    session.stage = PipelineStage.INTAKE
    await save_session(session)

    await message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


def _parse_single_shot_intake(text: str, task_name: str) -> dict:
    """Parse user's pasted template response.
    Strategy: extract value after each field label (case-insensitive match).
    Falls back to splitting by newlines if pattern unclear."""
    task = get_task(task_name)
    if not task:
        return {}

    parsed = {}
    text_lines = text.split("\n")

    # Build label → key map (case-insensitive)
    label_to_key = {f["label"].lower().strip(): f["key"] for f in task.intake_fields}

    current_field_key = None
    current_value_parts: list[str] = []

    for line in text_lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # Match "Label: value" or "*Label*: value" — extract label
        label_match = re.match(r"^[*_]*([^:*_]+?)[*_]*\s*:\s*(.*)$", line_stripped)
        if label_match:
            label_candidate = label_match.group(1).strip().lower()
            value_inline = label_match.group(2).strip()

            # Check if this label is one of our fields
            matched_key = None
            for label, key in label_to_key.items():
                if label_candidate == label or label_candidate.startswith(label[:15]):
                    matched_key = key
                    break

            if matched_key:
                # Save previous field
                if current_field_key and current_value_parts:
                    parsed[current_field_key] = " ".join(current_value_parts).strip()
                # Start new field
                current_field_key = matched_key
                current_value_parts = [value_inline] if value_inline else []
                continue

        # No label match — append to current field value
        if current_field_key:
            current_value_parts.append(line_stripped)

    # Save last field
    if current_field_key and current_value_parts:
        parsed[current_field_key] = " ".join(current_value_parts).strip()

    return parsed


async def _handle_feedback_text(update: Update, context: ContextTypes.DEFAULT_TYPE, session, text: str):
    """Sprint 2: User gửi feedback text sau khi rate ≤3.
    Save feedback, hỏi user có muốn regen không."""
    skill_name = session.pending_intake.get("_awaiting_feedback_for")
    if not skill_name:
        return

    # Update last feedback entry với text
    if session.feedback.get(skill_name):
        session.feedback[skill_name][-1]["feedback"] = text
        # Persist updated feedback to DB feedback_log
        last_rating = session.feedback[skill_name][-1].get("rating", 0)
        try:
            await _log_feedback_to_db(session, skill_name, last_rating, text)
        except Exception as e:
            logger.warning("Feedback DB log failed (non-blocking): %s", e)

    # Store pending feedback for regen decision
    session.pending_intake["_pending_feedback"] = text
    session.pending_intake["_pending_regen_skill"] = skill_name
    session.pending_intake.pop("_awaiting_feedback_for", None)
    await save_session(session)

    # Try detect source mention từ Max's previous output (Layer 3 simplified)
    versions = session.results.get(skill_name, [])
    last_output = versions[-1].content if versions else ""
    KNOWN_SOURCES = ["Statista", "GSO", "Tổng cục Thống kê", "WorldBank", "World Bank",
                     "Nielsen", "Q&Me", "Decision Lab", "Vietcetera", "CafeF",
                     "VnEconomy", "Brands Vietnam", "Adsota", "Kantar"]
    cited = [s for s in KNOWN_SOURCES if s in last_output]

    if cited:
        # Max output có cite source → bot hỏi user có nguồn không
        msg = (
            f"Em note rồi ạ.\n\n"
            f"Em hiểu sếp nói output em có chỗ chưa đúng. Em note rằng output trước em có dẫn nguồn từ "
            f"*{', '.join(cited[:2])}*.\n\n"
            f"Sếp có nguồn nào khác đáng tin hơn không ạ? Hoặc em chạy lại với feedback của sếp luôn?"
        )
    else:
        msg = (
            f"Em note rồi ạ. Sếp có muốn em chạy lại ngay với feedback này không?\n\n"
            f"_Em sẽ giữ nguyên context của sếp, chỉ điều chỉnh theo correction sếp đưa._"
        )

    await update.message.reply_text(
        msg,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=REGEN_PROMPT_KEYBOARD,
    )

    # Log feedback
    logger.info("Feedback collected for %s: %s", skill_name, text[:200])


async def _handle_ops_intake_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, session, text: str):
    """Handle user's paste reply for single-shot form (ops + strategic single-skill).
    Phase 3: also handles strategic single-skill tasks (market/competitor/customer/pricing).
    """
    task_name = session.pending_intake.get(OPS_INTAKE_AWAITING)
    if not task_name:
        return

    parsed = _parse_single_shot_intake(text, task_name)

    # Strategic single-shot: also merge parsed values into session.profile
    # (so future skills can reuse via profile reuse logic)
    SINGLE_SHOT_STRATEGIC = {"market", "competitor", "customer", "pricing"}
    if task_name in SINGLE_SHOT_STRATEGIC:
        # Map intake keys → BusinessProfile attributes
        profile = session.profile
        for k, v in parsed.items():
            if v and hasattr(profile, k):
                setattr(profile, k, v)
        # Try to infer industry from product_service if not set
        if not profile.industry and parsed.get("product_service"):
            inferred = _infer_industry(parsed["product_service"], parsed.get("target_customer", ""))
            if inferred:
                profile.industry = inferred

    # Merge into pending_intake (preserves variant chooser values like selected_tiers)
    for k, v in parsed.items():
        session.pending_intake[k] = v

    session.pending_intake.pop(OPS_INTAKE_AWAITING, None)
    await save_session(session)

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )

    task_label = get_task(task_name).label if get_task(task_name) else task_name
    await update.message.reply_text(
        f"⚡ *Đang chạy {task_label}...*\nThời gian dự kiến: 30-90 giây.",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        # Pre-fetch live FB data cho các skills cần (competitor_spy, performance_audit)
        if task_name == "competitor_spy":
            await _prefetch_competitor_ads(update.message, session)
        elif task_name == "performance_audit":
            await _prefetch_performance_data(update.message, session)

        # Dispatch theo task type
        if task_name in SINGLE_SHOT_STRATEGIC:
            from agents.pipeline import run_strategic_single_skill
            result = await run_strategic_single_skill(task_name, session)
            await save_session(session)
            # Strategic single-skill render via existing pipeline-sequentially logic
            # but for 1 stage only — reuse _send_ops_result for uniform UX
            await _send_ops_result(update.message, session, task_name, result)
        else:
            result = await run_operational_skill(task_name, session)
            await save_session(session)
            await _send_ops_result(update.message, session, task_name, result)
    except Exception as e:
        logger.exception("Skill %s failed: %s", task_name, e)
        await update.message.reply_text(
            f"⚠️ Skill {task_name} gặp lỗi: {str(e)[:200]}\n\nThử /start lại nhé."
        )


def _infer_industry(product: str, customer: str = "") -> str | None:
    """Phase 3 helper: infer industry from product description.
    Returns industry key or None if cannot infer."""
    text = f"{product} {customer}".lower()
    # Simple keyword matching for VN context
    if any(k in text for k in ["spa", "beauty", "skincare", "salon", "nails", "facial", "thẩm mỹ"]):
        return "health_beauty"
    if any(k in text for k in ["cafe", "quán", "nhà hàng", "f&b", "đồ ăn", "thức uống", "restaurant", "coffee"]):
        return "fnb"
    if any(k in text for k in ["saas", "phần mềm", "app", "platform", "tech"]):
        return "tech_saas"
    if any(k in text for k in ["khóa học", "course", "edu", "đào tạo", "training"]):
        return "education"
    if any(k in text for k in ["shop", "thời trang", "fashion", "ecommerce", "online store"]):
        return "ecommerce"
    if any(k in text for k in ["bđs", "bất động sản", "real estate", "căn hộ", "nhà"]):
        return "real_estate"
    return None


def _extract_image_prompt_from_brief(parsed: dict, session) -> str:
    """Sprint 5 v2: Build image gen prompt từ Ads output dùng prompt library.
    Match category dựa industry + product → template phù hợp → fill placeholders."""
    intake = session.pending_intake or {}
    product = intake.get("product", "") or session.profile.product_service or "sản phẩm"
    offer = intake.get("offer", "") or ""
    brand = session.profile.business_name or "Brand"
    industry = session.profile.industry or ""
    ads_format = intake.get("ads_format", "image")

    # Map size → aspect ratio
    aspect_map = {"vertical": "vertical", "square": "square", "horizontal": "horizontal"}
    aspect = aspect_map.get(intake.get("_last_image_size_hint", "square"), "square")

    # Build context_text từ industry + product để categorize
    context_text = f"{industry} {product} {ads_format}"

    try:
        from tools.image_prompt_library import build_prompt
        final_prompt, template_slug = build_prompt(
            product=product[:200],
            brand=brand[:100],
            offer=offer[:150],
            style_note="",
            category=None,  # auto-detect from context_text
            aspect_ratio=aspect,
        )
        intake["_template_slug"] = template_slug
        logger.info("Image prompt: template=%s for industry=%s", template_slug, industry)
        return final_prompt[:1500]
    except Exception as e:
        logger.warning("Prompt library failed, falling back: %s", e)

    # Fallback: legacy logic
    insight = intake.get("insight", "")
    offer = intake.get("offer", "")
    deliverable = parsed.get("deliverable", "") or parsed.get("raw", "")[:500]

    # Try extract "Visual" or "Style" lines from deliverable
    import re as _re
    visual_hints = _re.findall(
        r"(?:Visual|Concept|Mood|Style|Color)[:\s]+([^\n]+)",
        deliverable, flags=_re.IGNORECASE
    )
    visual_str = " ".join(visual_hints[:3]) if visual_hints else ""

    # Compose image prompt (English works best for gpt-image-1)
    prompt = (
        f"Marketing ad image for: {product}. "
        f"Key insight: {insight}. "
        f"Offer: {offer}. "
    )
    if visual_str:
        prompt += f"Visual style: {visual_str}. "
    prompt += (
        "Vietnamese market, modern professional style, "
        "high quality commercial photography, clean composition with space for text overlay."
    )
    return prompt[:1000]  # gpt-image-1 prompt limit


async def _send_ops_result(message: Message, session, task_name: str, result: str):
    """Render single-skill result (ops + strategic single-shot): Telegram card + files."""
    from bot.renderers import (
        parse_by_format,
        format_telegram_card,
        render_markdown_file,
        render_excel_file,
    )
    from bot.html_report import build_single_skill_report
    from agents.skills import PrimaryDeliverable
    import io

    # Resolve skill instance: strategic single-shot uses STRATEGIC_SKILL_CLASSES,
    # operational uses get_operational_skill factory
    SINGLE_SHOT_STRATEGIC = {"market", "competitor", "customer", "pricing"}
    if task_name in SINGLE_SHOT_STRATEGIC:
        from agents.pipeline import STRATEGIC_SKILL_CLASSES
        skill = STRATEGIC_SKILL_CLASSES[task_name]()
    else:
        from agents.operational_skills_config import get_operational_skill
        skill = get_operational_skill(task_name)

    task = get_task(task_name)
    parsed = parse_by_format(result, skill.output_format)

    # Telegram bullet card
    primary_label = {
        PrimaryDeliverable.HTML:     "Xem chi tiết trong file HTML đính kèm",
        PrimaryDeliverable.EXCEL:    "Xem chi tiết trong file Excel đính kèm",
        PrimaryDeliverable.MARKDOWN: "Xem chi tiết trong file Markdown đính kèm",
    }.get(skill.primary_deliverable, "Xem file đính kèm")

    card_text = format_telegram_card(
        task_name, task.label, task.button_emoji,
        parsed, skill.output_format,
        file_attached_hint=primary_label,
    )

    await message.reply_text(card_text, parse_mode=ParseMode.MARKDOWN)

    business_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", session.profile.business_name or task_name)[:30]
    business_name = session.profile.business_name or "Business"

    # Send HTML always (universal viewable)
    try:
        html_str = build_single_skill_report(
            task_name, parsed, skill.output_format,
            business_name=business_name,
            industry=session.profile.industry or "",
            stage=session.profile.stage or "",
        )
        buf = io.BytesIO(html_str.encode("utf-8"))
        buf.name = f"{task_name}_{business_slug}.html"
        await message.reply_document(
            document=buf,
            filename=buf.name,
            caption=f"📄 *{task.label}* — bản HTML đầy đủ",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.warning("HTML render failed for %s: %s", task_name, e)

    # Send primary deliverable per skill config
    if skill.primary_deliverable == PrimaryDeliverable.MARKDOWN:
        md_bytes = render_markdown_file(task_name, task.label, parsed, skill.output_format, business_name)
        buf = io.BytesIO(md_bytes)
        buf.name = f"{task_name}_{business_slug}.md"
        await message.reply_document(
            document=buf,
            filename=buf.name,
            caption=f"📝 *{task.label}* — bản Markdown (gửi designer/dev/creator)",
            parse_mode=ParseMode.MARKDOWN,
        )
    elif skill.primary_deliverable == PrimaryDeliverable.EXCEL:
        xlsx_bytes = render_excel_file(task_name, task.label, parsed, skill.output_format, business_name)
        if xlsx_bytes:
            buf = io.BytesIO(xlsx_bytes)
            buf.name = f"{task_name}_{business_slug}.xlsx"
            await message.reply_document(
                document=buf,
                filename=buf.name,
                caption=f"📊 *{task.label}* — bản Excel (paste vào Google Sheet)",
                parse_mode=ParseMode.MARKDOWN,
            )

    # Sprint 4: Special follow-up sau competitor → hỏi user có muốn so sánh không
    if task_name == "competitor":
        await message.reply_text(
            f"✅ *Hoàn thành {task.label}!*\n\nSếp có muốn em so sánh business của sếp với đối thủ luôn không ạ?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=COMPARE_PROMPT_KEYBOARD,
        )
        return

    # Sprint 5 v2: Sau ads_generator (format=image) → hỏi upload ảnh mẫu hoặc gen luôn
    if task_name in ("ads_generator", "ads_copy") and session.pending_intake.get("ads_format") == "image":
        from tools.image_gen import is_available
        if is_available():
            # Lưu copy output để build prompt sau
            img_prompt = _extract_image_prompt_from_brief(parsed, session)
            session.pending_intake["_img_prompt"] = img_prompt
            await save_session(session)
            await message.reply_text(
                "📸 *Sếp có ảnh mẫu muốn em làm theo style không ạ?*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=IMAGE_REFERENCE_KEYBOARD,
            )
            return
        else:
            await message.reply_text(
                "⚠️ _Image gen chưa setup (cần OPENAI_API_KEY). Em chỉ gửi copy thôi._",
                parse_mode=ParseMode.MARKDOWN,
            )

    # Sprint 4: Special follow-up sau monitor setup
    if task_name == "competitor_spy" and session.pending_intake.get("_fb_page_id"):
        page_id = session.pending_intake["_fb_page_id"]
        page_name = session.pending_intake.get("competitor_name", "đối thủ")
        session.pending_intake["_monitor_pending_page_id"] = page_id
        session.pending_intake["_monitor_pending_page_name"] = page_name
        await save_session(session)
        await message.reply_text(
            f"🔔 *Sếp muốn em theo dõi tự động ads mới của {page_name} không ạ?*\n\n"
            f"_Em sẽ check định kỳ và báo sếp ngay khi đối thủ tung ads mới._",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=MONITOR_PROMPT_KEYBOARD,
        )
        return

    # Sprint 2: Default — send RATING_KEYBOARD
    session.pending_intake["_awaiting_rating_for"] = task_name
    await save_session(session)

    await message.reply_text(
        f"✅ *Hoàn thành {task.label}!*\n\nSếp đánh giá output em vừa làm thế nào ạ?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=RATING_KEYBOARD,
    )


async def _run_pipeline_sequentially(message: Message, session):
    from bot.html_report import parse_agent_output, build_report

    task = session.selected_task or "full"
    task_label = TASK_LABELS.get(task, "Phân tích")
    total_stages = TASK_STAGE_COUNT.get(task, 1)

    if total_stages > 1:
        await message.reply_text(
            f"🚀 *Bắt đầu {task_label}!*\n\nTôi sẽ chạy {total_stages} bước và gửi card tóm tắt từng bước.\nFile HTML đầy đủ sẽ được gửi ở cuối.",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await message.reply_text(
            f"🚀 *Bắt đầu {task_label}...*",
            parse_mode=ParseMode.MARKDOWN,
        )

    stage_count = 0
    parsed_stages: list[tuple[str, dict]] = []  # for HTML report

    async def progress_cb(msg: str):
        await message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async for stage_key, result in run_targeted_pipeline(session, progress_callback=progress_cb):
        stage_count += 1
        is_last = stage_count == total_stages

        parsed = parse_agent_output(result)
        parsed_stages.append((stage_key, parsed))

        card_text = _format_card(stage_key, parsed)
        await send_long_message(
            message,
            card_text,
            parse_mode=ParseMode.MARKDOWN,
            # Intermediate stages: no keyboard (auto continue)
            # Last stage: handled below (Rating + chained followup)
            reply_markup=None,
        )
        await save_session(session)
        await asyncio.sleep(0.5)

    # After all stages complete: build + send HTML report
    if stage_count > 0:
        try:
            html_str = build_report(
                business_name=session.profile.business_name or "Business",
                industry=session.profile.industry or "",
                stage=session.profile.stage or "",
                parsed_stages=parsed_stages,
            )
            await _send_html_report(message, html_str, session)
        except Exception as e:
            logger.exception("Failed to generate HTML report: %s", e)
            await message.reply_text(
                "⚠️ Không generate được file HTML — phần tóm tắt ở trên đã đủ. Sếp có thể hỏi thêm tự do."
            )

    if stage_count > 0 and stage_count == total_stages:
        # Chained followup — Brief Campaign hoặc skill khác đang chờ Strategy
        followup_skill = session.pending_followup_skill
        if followup_skill:
            session.pending_followup_skill = None
            await save_session(session)
            from agents.task_registry import get_task as _get_task
            followup_label = (_get_task(followup_skill).label if _get_task(followup_skill) else followup_skill)
            await message.reply_text(
                f"✅ *A→Z xong rồi ạ!* Em tiếp tục *{followup_label}* cho sếp luôn nhé...",
                parse_mode=ParseMode.MARKDOWN,
            )
            session.selected_task = followup_skill
            await save_session(session)
            await _send_single_shot_form(message, session, followup_skill)
            return

        # Sprint 2: Rating loop sau khi xong pipeline
        session.pending_intake["_awaiting_rating_for"] = task
        await save_session(session)

        if total_stages > 1:
            await message.reply_text(
                "✅ *Hoàn thành phân tích!*\n\nMở file HTML để xem báo cáo đầy đủ.\n\nSếp đánh giá output em vừa làm thế nào ạ?",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=RATING_KEYBOARD,
            )
        else:
            await message.reply_text(
                f"✅ *Hoàn thành {task_label}!*\n\nSếp đánh giá output em vừa làm thế nào ạ?",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=RATING_KEYBOARD,
            )


# ─── Claude advisor fallback ────────────────────────────────────

async def _claude_advisor_fallback(update, context, session, text: str):
    """User nhắn free-form ngoài skill flow → Sonnet trả lời với full context.

    Context bao gồm: profile + tất cả results đã chạy + Strategy synthesis.
    Sau khi reply, kèm gợi ý các task có sẵn.
    """
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )

    import anthropic
    from config import CLAUDE_SONNET_MODEL, ANTHROPIC_API_KEY

    # Build context: profile + key results
    parts = []
    if session.profile and session.profile.business_name:
        parts.append(session.profile.to_context_string())

    synthesis = session.get_latest_result("synthesis") or session.get_latest_result("strategy")
    if synthesis:
        parts.append(f"## Marketing Strategy đã có:\n{synthesis[:3500]}")

    # Inject summaries của các skill đã chạy
    for skill_key in ("market_research", "competitor", "customer_insight", "psychology_pricing",
                       "campaign_brief", "content_calendar"):
        r = session.get_latest_result(skill_key)
        if r:
            parts.append(f"## Kết quả {skill_key}:\n{r[:1500]}")

    context_str = "\n\n---\n\n".join(parts) if parts else "_(User chưa chạy task nào, chưa có profile)_"

    en_level = session.preferences.get("en_level", "moderate")
    en_note = {
        "none":     "Dùng THUẦN VIỆT 100% — kể cả thuật ngữ marketing dịch sang VN.",
        "moderate": "Có thể dùng thuật ngữ EN nhưng kèm giải thích VN trong ngoặc.",
        "fluent":   "Dùng thuật ngữ EN tự nhiên, không cần giải thích.",
    }.get(en_level, "Moderate EN level.")

    system_text = f"""Bạn là Max — AI CMO cho founder Việt Nam.

Tone: xưng "em" gọi user "sếp", professional + thân thiện.
Language: {en_note}

NHIỆM VỤ: User nhắn câu hỏi/yêu cầu free-form ngoài flow skill chuẩn.
Trả lời như 1 marketing advisor có context business của sếp.

QUY TẮC:
- BÁM SÁT business profile + results đã có (đừng generic)
- Trả lời NGẮN GỌN (2-4 đoạn, max ~400 từ)
- Nếu câu hỏi liên quan task có sẵn → GỢI Ý chạy task đó cuối câu trả lời
  (vd: "Để có data đầy đủ về đối thủ, sếp chạy task *Phân Tích Đối Thủ* nhé")
- Nếu user hỏi vu vơ / chào / cảm ơn → reply ngắn, gợi ý mở menu
- KHÔNG bịa số liệu cụ thể, chỉ đưa khuyến nghị dựa trên framework

Skills có sẵn (gợi ý nếu phù hợp):
🎯 Chiến lược: Tìm Hiểu Thị Trường, Phân Tích Đối Thủ, Insight Khách Hàng,
   Chiến Lược Giá, Lập Kế Hoạch Tổng, Phân Tích Tổng Hợp A→Z
⚙️ Sản xuất: Viết Brief Campaign, Lịch Nội Dung, Sản Xuất Nội Dung,
   Sản Xuất Ads, Kịch Bản Video, Thiết Kế Website, Kịch Bản Sales,
   Chăm Sóc Khách Hàng
📊 Theo dõi: Theo Dõi Đối Thủ, Báo Cáo Ads"""

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    try:
        response = await client.messages.create(
            model=CLAUDE_SONNET_MODEL,
            max_tokens=1200,
            system=[{
                "type": "text",
                "text": system_text,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{
                "role": "user",
                "content": f"{context_str}\n\n---\n\nUser nhắn: {text}",
            }],
        )
        reply = response.content[0].text
    except Exception as e:
        logger.exception("Claude advisor fallback failed: %s", e)
        await update.message.reply_text(
            "⚠️ Em đang gặp lỗi kết nối. Sếp thử chọn task từ menu nhé:",
            reply_markup=MAIN_MENU_KEYBOARD,
        )
        return

    await send_long_message(
        update.message,
        reply,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Hỏi tiếp",      callback_data="continue_advisor")],
            [InlineKeyboardButton("⚙️ Mở menu task", callback_data="menu_main")],
        ]),
    )

    # Set marker để turn tiếp theo cũng route qua advisor
    session.pending_intake["_advisor_mode"] = "1"
    await save_session(session)


# ─── Feedback log DB helper ──────────────────────────────────────

async def _log_feedback_to_db(session, skill_name: str, rating: int, feedback_text: str = ""):
    """Persist feedback vào table feedback_log (Task #12). Non-blocking."""
    try:
        from storage.feedback_log import log_feedback
        output = session.get_latest_result(skill_name) or ""
        user_correction = session.pending_intake.get("_pending_feedback", "")
        await log_feedback(
            user_id=session.user_id,
            skill_name=skill_name,
            rating=rating,
            feedback_text=feedback_text,
            industry=session.profile.industry or "",
            stage=session.profile.stage or "",
            business_name=session.profile.business_name or "",
            output_excerpt=output[:500],
            user_correction=user_correction,
        )
    except Exception as e:
        logger.warning("Feedback DB log failed (non-blocking): %s", e)


# ─── Facebook API pre-fetch helpers ─────────────────────────────

async def _prefetch_competitor_ads(message: Message, session):
    """Pre-fetch FB Ads Library data cho competitor_spy skill.
    Ưu tiên link fanpage (search_by_page_id) → chính xác hơn search_terms.
    Inject _fb_data + _fb_page_id (để dùng cho auto-monitor sau).
    """
    try:
        from tools.fb_ads_library import (
            search_competitor_ads, search_by_page_id,
            format_ads_for_analysis, resolve_page_id_from_url, is_available,
        )
        if not is_available():
            logger.info("FB Ads Library not configured — skipping pre-fetch")
            return

        competitor_name = (
            session.pending_intake.get("competitor_name")
            or session.pending_intake.get("competitor")
            or session.profile.competitors
            or ""
        )
        fanpage_url = session.pending_intake.get("fanpage_url", "").strip()

        if not competitor_name and not fanpage_url:
            logger.info("No competitor name or URL — skipping Ads Library fetch")
            return

        # Try resolve page_id từ URL trước
        page_id = None
        if fanpage_url:
            await message.reply_text(
                f"🔗 Em đang resolve Page ID từ link {fanpage_url}...",
                parse_mode=ParseMode.MARKDOWN,
            )
            page_id = await resolve_page_id_from_url(fanpage_url)
            if page_id:
                logger.info("Resolved page_id %s from URL %s", page_id, fanpage_url)

        # Notify user
        await message.reply_text(
            f"🔍 Em đang tìm ads của *{competitor_name or fanpage_url}* trên Facebook Ads Library...",
            parse_mode=ParseMode.MARKDOWN,
        )

        # Ưu tiên search by page_id (chính xác hơn) → fallback to text search
        if page_id:
            ads = await search_by_page_id(page_id, country="VN", limit=20)
            session.pending_intake["_fb_page_id"] = page_id
        else:
            ads = await search_competitor_ads(
                search_terms=competitor_name or fanpage_url,
                country="VN",
                limit=20,
            )

        fb_data = format_ads_for_analysis(ads, competitor_name or "đối thủ")
        session.pending_intake["_fb_data"] = fb_data
        # Lưu ad IDs cho monitor diff sau
        session.pending_intake["_fb_ad_ids"] = ",".join(a.get("id", "") for a in ads if a.get("id"))
        logger.info("FB Ads Library: fetched %d ads (page_id=%s)", len(ads), page_id)

    except Exception as e:
        logger.warning("FB Ads Library pre-fetch failed (non-blocking): %s", e)
        # Non-blocking — skill vẫn chạy mà không có live data


async def _prefetch_performance_data(message: Message, session):
    """Pre-fetch FB Marketing API data cho performance_audit skill.
    Lấy date range từ pending_intake, pull insights, inject vào _fb_data."""
    try:
        from tools.fb_marketing import get_account_insights, format_insights_for_analysis, is_available
        if not is_available():
            logger.info("FB Marketing API not configured (need FB_AD_ACCOUNT_ID) — skipping pre-fetch")
            return

        # Map date label → FB date_preset
        period_raw = (
            session.pending_intake.get("date_range")
            or session.pending_intake.get("period")
            or "30 ngày"
        ).lower()

        date_preset_map = {
            "7":  "last_7d",  "7 ngày":  "last_7d",
            "14": "last_14d", "14 ngày": "last_14d",
            "30": "last_30d", "30 ngày": "last_30d",
            "90": "last_90d", "90 ngày": "last_90d",
            "tháng này": "this_month",
            "tháng trước": "last_month",
        }
        date_preset = "last_30d"
        for keyword, preset in date_preset_map.items():
            if keyword in period_raw:
                date_preset = preset
                break

        await message.reply_text(
            "📊 Em đang pull data Facebook Ads của sếp...",
            parse_mode=ParseMode.MARKDOWN,
        )

        insights = await get_account_insights(
            date_preset=date_preset,
            level="campaign",
        )
        fb_data = format_insights_for_analysis(insights, period_raw)
        session.pending_intake["_fb_data"] = fb_data
        logger.info("FB Marketing API: fetched %d rows | preset=%s", len(insights), date_preset)

    except Exception as e:
        logger.warning("FB Marketing pre-fetch failed (non-blocking): %s", e)
        # Non-blocking — skill vẫn chạy, user tự paste data


async def _send_html_report(message: Message, html_str: str, session):
    """Send HTML report as document attachment."""
    import io
    business_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", (session.profile.business_name or "report"))[:30]
    filename = f"marketing_report_{business_slug}.html"

    buf = io.BytesIO(html_str.encode("utf-8"))
    buf.name = filename

    await message.reply_document(
        document=buf,
        filename=filename,
        caption="📄 *Báo cáo đầy đủ* — mở để xem full analysis với layout đẹp.",
        parse_mode=ParseMode.MARKDOWN,
    )
