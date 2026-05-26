"""
Telegram bot message and callback handlers.
All storage calls are async (asyncpg-backed).
"""
import asyncio
import functools
import logging
import re
from telegram import Update, Message, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode, ChatAction

from storage import get_session, save_session, reset_session
from storage.models import PipelineStage
from agents.pipeline import run_intake, run_targeted_pipeline, run_operational_skill, run_multi_agent_targeted
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
    CALENDAR_TO_CONTENT_GEN_KEYBOARD,
    ADS_FORMAT_KEYBOARD,
    IMAGE_REFERENCE_KEYBOARD,
    IMAGE_GEN_PROMPT_KEYBOARD,
    IMAGE_SIZE_KEYBOARD,
    IMAGE_REVIEW_KEYBOARD,
    NEEDS_STRATEGY_KEYBOARD,
    MONITOR_PROMPT_KEYBOARD,
    MONITOR_INTERVAL_KEYBOARD,
    CONTENT_SUITE_KEYBOARD,
    POST_AZ_CAMPAIGN_KEYBOARD,
    CAMPAIGN_OPTION_KEYBOARD,
    CAMPAIGN_IDEA_CONFIRM_KEYBOARD,
    OFFER_LEVER_KEYBOARD,
    BRAND_VOICE_PROMPT_KEYBOARD,
)


# Sprint 5: Creative ops skills cần Brand Voice — lazy trigger gate
BRAND_VOICE_GATED_SKILLS = {
    "post_write", "post_adapt", "post_batch", "post_hooks", "post_visual",
    "ads_generator", "ads_copy", "video_scripts",
    "sales_inbox_script", "email_zalo_sequence", "content_repurpose",
    "content_generator",
}

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
    # Sprint 2+3: full pipeline mở rộng 5 → 8 stages
    # market + competitor + customer + psychology+pricing + usp_definition (conditional)
    # + retention_strategy + winback_campaign + synthesis
    "full": 8,
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


# Per-user lock map — chống race khi user spam click với concurrent_updates=True.
# Lock được tạo lazy, giữ trong dict module-level. Memory ~1KB/user, không cần evict
# trong scope hiện tại (small user base). Nếu scale lớn → wrap bằng LRU cache.
_user_locks: dict[int, asyncio.Lock] = {}


def _get_user_lock(user_id: int) -> asyncio.Lock:
    lock = _user_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _user_locks[user_id] = lock
    return lock


def with_user_lock(handler):
    """Decorator: serialize đồng thời 2 update của cùng 1 user. Updates của user khác
    vẫn chạy song song (vì PTB concurrent_updates=True)."""
    @functools.wraps(handler)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user is None and update.callback_query:
            user = update.callback_query.from_user
        if user is None:
            return await handler(update, context)
        async with _get_user_lock(user.id):
            return await handler(update, context)
    return wrapped


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

@with_user_lock
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show main menu. GIỮ NGUYÊN session (profile, results, feedback, preferences).
    First-time user (no name) → hỏi tên TRƯỚC, sau đó ngôn ngữ.
    Dùng /reset nếu muốn xoá business data.
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

    # FIRST-TIME — hỏi tên trước
    if not session.preferences.get("user_name"):
        session.pending_intake["_awaiting_user_name"] = "1"
        await save_session(session)
        await update.message.reply_text(
            "👋 *Em là Max — AI CMO của sếp.*\n\n"
            "Trước khi vào việc, sếp gõ tên để em biết gọi sếp thế nào ạ?\n\n"
            "_Vd: \"Nhiên\" / \"Anh Minh\" / \"Founder Lily\"_",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # FIRST-TIME (đã có tên) — hỏi ngôn ngữ
    if not session.preferences.get("en_level"):
        name = session.preferences.get("user_name", "")
        msg = LANG_SETUP_MESSAGE.replace("Em chào sếp!", f"Em chào sếp {name}!" if name else "Em chào sếp!")
        await update.message.reply_text(
            msg,
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

    welcome = _personalize(welcome, session)
    await _safe_reply(
        update.message,
        welcome,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=MAIN_MENU_KEYBOARD,
    )


@with_user_lock
async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/settings — config cho Max: Tên / Token / Ngôn ngữ."""
    user_id = update.effective_user.id
    session = await get_session(user_id)
    current = session.preferences.get("en_level", "moderate")
    name = session.preferences.get("user_name", "")
    label_map = {"none": "🔴 Không rành", "moderate": "🟡 Hiểu cơ bản", "fluent": "🟢 Thông thạo"}

    # Token info (real tracking)
    from tools.token_tracker import usage_summary, is_low, get_remaining, fmt
    token_line = usage_summary(session)
    low_warning = "\n⚠️ _Token gần hết, sếp liên hệ admin để nạp thêm._" if is_low(session) else ""

    name_line = f"👤 *Tên em đang gọi:* {name}" if name else "👤 *Tên:* chưa đặt"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Đổi tên",            callback_data="settings_change_name")],
        [InlineKeyboardButton("🔤 Đổi mức tiếng Anh",   callback_data="settings_change_lang")],
        [InlineKeyboardButton("💎 Xem chi tiết token",  callback_data="settings_tokens")],
    ])
    await update.message.reply_text(
        f"⚙️ *Cài đặt Max của sếp*\n\n"
        f"{name_line}\n"
        f"🔤 *Ngôn ngữ:* {label_map.get(current, '🟡')}\n"
        f"💎 *Token usage:* {token_line}{low_warning}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb,
    )


@with_user_lock
async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset business data. GIỮ tên + ngôn ngữ (preferences) gắn với User ID."""
    user_id = update.effective_user.id

    # Preserve preferences (name, en_level, future token balance)
    old_session = await get_session(user_id)
    preserved_prefs = dict(old_session.preferences) if old_session.preferences else {}

    await reset_session(user_id)
    session = await get_session(user_id)
    session.preferences = preserved_prefs
    session.stage = PipelineStage.TASK_SELECT
    await save_session(session)

    name = preserved_prefs.get("user_name", "")
    name_part = f" sếp {name}" if name else ""
    await update.message.reply_text(
        f"✅ *Đã xoá business data{name_part}!*\n\n"
        f"_Profile, kết quả, feedback đã clean. Tên + ngôn ngữ của sếp được giữ nguyên._",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=MAIN_MENU_KEYBOARD,
    )


@with_user_lock
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_MESSAGE, parse_mode=ParseMode.MARKDOWN)


# ─── Main message handler ─────────────────────────────────────────

@with_user_lock
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    session = await get_session(user_id)

    # NEW: First-time name capture
    if session.pending_intake.get("_awaiting_user_name"):
        raw = text.strip()
        # Strip common prefixes trước khi validate
        cleaned = raw
        for prefix in ("em là ", "tớ là ", "tôi là ", "mình là ", "anh ", "chị ", "tên ", "gọi "):
            if cleaned.lower().startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
                break

        valid, error_msg = _validate_user_name(cleaned)
        if valid:
            session.preferences["user_name"] = cleaned
            session.pending_intake.pop("_awaiting_user_name", None)
            await save_session(session)

            # Nếu chưa có en_level → hỏi tiếp ngôn ngữ
            if not session.preferences.get("en_level"):
                await update.message.reply_text(
                    f"✨ *Em chào sếp {cleaned}!*\n\n"
                    f"Em hỏi nhanh thêm 1 ý nữa ạ:\n\n"
                    f"*Khả năng tiếng Anh của sếp thế nào* để em biết cách trình bày output cho phù hợp?\n\n"
                    f"🔴 *Không rành* — Em dùng thuần Việt toàn bộ\n"
                    f"🟡 *Hiểu cơ bản* — Em dùng thuật ngữ EN kèm giải thích\n"
                    f"🟢 *Thông thạo* — Em dùng EN tự nhiên",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=LANG_LEVEL_KEYBOARD,
                )
            else:
                # Đã có lang rồi → vào menu thẳng
                await update.message.reply_text(
                    f"✨ *Em chào sếp {cleaned}!*\n\n"
                    f"Em đã ghi nhớ tên — đổi bất kỳ lúc nào qua /settings.\n\n"
                    f"Giờ vào việc thôi sếp {cleaned}! 👇",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=MAIN_MENU_KEYBOARD,
                )
        else:
            await update.message.reply_text(
                f"⚠️ {error_msg}\n\n"
                f"_Sếp gõ lại 1 tên hợp lệ nhé. Vd: 'Nhiên' / 'Anh Minh' / 'Founder Lily'._",
                parse_mode=ParseMode.MARKDOWN,
            )
        return

    # Sprint 6: Tone calibration feedback
    if session.tone_calibration.get("stage") == "waiting_feedback":
        await _handle_tone_feedback(update, context, session, text)
        return

    # Sprint 7: Post edit instruction
    if session.pending_intake.get("_post_editing"):
        post_id = session.pending_intake.pop("_post_editing")
        post = session.content_outputs.get(post_id)
        if post:
            await update.message.reply_text("✏️ _Đang chỉnh sửa..._", parse_mode=ParseMode.MARKDOWN)
            from agents.post_actions import edit_post
            edited = await edit_post(post.get("content", ""), text, session)
            session.content_outputs[post_id]["content"] = edited
            session.content_outputs[post_id]["status"] = "draft"
            await save_session(session)
            from agents.post_actions import format_post_preview
            from bot.keyboards import post_action_keyboard
            await update.message.reply_text(
                f"✅ *`{post_id}` đã chỉnh:*\n\n" + format_post_preview(post_id, session.content_outputs[post_id]),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=post_action_keyboard(post_id),
            )
        return

    # Sprint 5 v2: Image edit text reply
    if session.pending_intake.get("_awaiting_image_edit"):
        await _handle_image_edit_text(update, context, session, text)
        return

    # Post A→Z: User mô tả idea campaign → refine với customer + market
    if session.pending_intake.get("_awaiting_campaign_idea"):
        await _handle_campaign_idea_text(update, context, session, text)
        return

    # Post A→Z: User fill 4 trường quyết định (budget, team, start_date, discount)
    if session.pending_intake.get("_awaiting_campaign_finalize"):
        await _handle_campaign_finalize_text(update, context, session, text)
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
        # Greeting detection — nếu user chỉ chào/nhắn ngắn → show menu trực tiếp
        # Không gọi LLM để tránh bot hỏi lại business info khi đã có trong DB
        _GREETING_KEYWORDS = (
            "max ơi", "ơi", "hello", "hi ", "chào", "hey", "xin chào",
            "helo", "hii", "alo", "yo ", "sup", "hola",
        )
        _is_greeting = (
            len(text.strip()) <= 25
            or any(text.lower().strip().startswith(kw) or text.lower().strip() == kw.strip()
                   for kw in _GREETING_KEYWORDS)
        )
        if _is_greeting:
            addr = _addr(session)
            biz = session.profile.business_name
            if session.profile.is_intake_complete():
                msg = f"Em chào {addr}! Hôm nay tiếp tục phần nào ạ? 👇"
            elif biz:
                msg = f"Em chào {addr}! Mình tiếp tục từ đây nhé 👇"
            else:
                msg = f"Em chào {addr}! Sếp muốn bắt đầu từ đâu ạ? 👇"
            await update.message.reply_text(
                msg,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=MAIN_MENU_KEYBOARD,
            )
            return
        # Câu hỏi / yêu cầu thực → Sonnet advisor với full context
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


@with_user_lock
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
        # Smart Intake v2: LLM có thể vô tình output JSON sớm dù chưa đủ 8
        # fields. Strip JSON block để user không thấy block thô trong chat.
        clean_response = re.sub(r"```json.*?```", "", response, flags=re.DOTALL).strip()
        if not clean_response:
            clean_response = "Em note rồi sếp. Cho em hỏi thêm 1 câu nữa nhé..."
        await _safe_reply(update.message, clean_response, parse_mode=ParseMode.MARKDOWN)


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

    user_name = _get_user_name(session)
    name_hint = (
        f"User tên là '{user_name}' — khi xưng hô gọi 'sếp {user_name}', không chỉ 'sếp'."
    ) if user_name else ""

    system_text = (
        "Bạn là Max, AI CMO của founder Việt Nam. "
        "Sếp vừa hỏi follow-up về output em đưa ra. "
        "Trả lời BÁM SÁT output đã có. Nếu sếp hỏi ngoài scope, "
        "gợi ý chạy skill khác phù hợp.\n\n"
        f"Tone: em/sếp, professional nhưng thân thiện. {name_hint}\n"
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

    # Token tracking
    try:
        from tools.token_tracker import track_usage
        track_usage(session, response, label="followup_qa")
        await save_session(session)
    except Exception as e:
        logger.warning("Token tracking failed (followup): %s", e)

    await send_long_message(
        update.message,
        response.content[0].text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ASK_FOLLOWUP_KEYBOARD,
    )


# ─── Callback (inline keyboard) ──────────────────────────────────

@with_user_lock
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

    # ── Sprint 6: Tone Calibration ────────────────────────────────
    if data.startswith("tone_"):
        await _handle_tone_callback(query, session)
        return

    # ── Sprint 7: Per-post Actions ────────────────────────────────
    if data.startswith("post_"):
        await _handle_post_action_callback(query, session)
        return

    if data.startswith("adapt_"):
        await _handle_adapt_channel_callback(query, session)
        return

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

    # ── Calendar → Content Gen chain ─────────────────────────────
    if data == "run_content_gen_after_cal":
        await query.edit_message_reply_markup(reply_markup=None)
        session.selected_task = "content_generator"
        session.pending_intake = {}  # reset cho fresh intake
        await save_session(session)
        await query.message.reply_text(
            "✍️ *Tiếp tục Sản Xuất Nội Dung từ Calendar...*",
            parse_mode=ParseMode.MARKDOWN,
        )
        await _send_single_shot_form(query.message, session, "content_generator")
        return

    if data == "skip_content_gen_after_cal":
        await query.edit_message_reply_markup(reply_markup=None)
        # Tiếp tục flow rating cho calendar
        session.pending_intake["_awaiting_rating_for"] = "content_calendar"
        await save_session(session)
        await query.message.reply_text(
            "OK ạ! Sếp đánh giá Lịch Nội Dung em vừa làm thế nào ạ?",
            reply_markup=RATING_KEYBOARD,
        )
        return

    # ── Post A→Z: Campaign Ideation flow ─────────────────────────
    # Branch A: User đã có idea → ask user gõ idea → refine
    if data == "az_have_idea":
        await query.edit_message_reply_markup(reply_markup=None)
        session.pending_intake["_awaiting_campaign_idea"] = "1"
        session.pending_intake.pop("_awaiting_rating_for", None)
        await save_session(session)
        addr = _addr(session)
        await query.message.reply_text(
            f"💡 *OK {addr}!* Sếp mô tả ngắn campaign muốn chạy ạ.\n\n"
            f"_Vd: \"Combo Tết giảm giá cho khách cũ\", \"Launch sản phẩm mới cho gen Z\", "
            f"\"Tăng repeat rate sau khi khách mua lần đầu\"..._\n\n"
            f"Em sẽ đối chiếu với Customer Insight + Market Research để validate và refine cho sếp.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Branch B: User chưa biết → Max propose 3 options
    if data == "az_propose_campaign" or data == "campaign_propose_again":
        await query.edit_message_reply_markup(reply_markup=None)
        session.pending_intake.pop("_awaiting_rating_for", None)
        await save_session(session)

        await query.message.reply_text(
            "🔍 *Em đang phân tích Strategy + Customer + Market để đề xuất campaign...*\n"
            "_Khoảng 20-40 giây ạ._",
            parse_mode=ParseMode.MARKDOWN,
        )
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.TYPING,
        )

        try:
            from agents.campaign_ideation import propose_campaigns, format_options_card
            options = await propose_campaigns(session)
            if not options:
                await query.message.reply_text(
                    "⚠️ Em đề xuất bị lỗi. Sếp thử lại hoặc gõ idea trực tiếp nhé.",
                    reply_markup=POST_AZ_CAMPAIGN_KEYBOARD,
                )
                return

            # Store options vào pending_intake để pick_X dùng lại
            import json as _json
            session.pending_intake["_proposed_campaigns"] = _json.dumps(options, ensure_ascii=False)
            await save_session(session)

            card = format_options_card(options)
            await send_long_message(
                query.message, card,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=CAMPAIGN_OPTION_KEYBOARD,
            )
        except Exception as e:
            logger.exception("Campaign propose failed: %s", e)
            await query.message.reply_text(
                f"⚠️ Lỗi khi đề xuất: {str(e)[:200]}",
                reply_markup=POST_AZ_CAMPAIGN_KEYBOARD,
            )
        return

    # User picks 1/2/3 từ proposed options → show finalize form
    if data.startswith("campaign_pick_"):
        await query.edit_message_reply_markup(reply_markup=None)
        try:
            pick_idx = int(data.split("_")[-1]) - 1  # 1 → 0, 2 → 1, 3 → 2
        except ValueError:
            await query.message.reply_text("⚠️ Pick không hợp lệ.")
            return

        import json as _json
        raw = session.pending_intake.get("_proposed_campaigns", "[]")
        try:
            options = _json.loads(raw)
        except _json.JSONDecodeError:
            options = []

        if pick_idx < 0 or pick_idx >= len(options):
            await query.message.reply_text("⚠️ Option đã hết hạn. Sếp đề xuất lại nhé.")
            return

        chosen = options[pick_idx]
        await _show_offer_lever_selection(query.message, session, chosen)
        return

    # User confirm refined idea → show finalize form
    if data == "campaign_idea_confirm":
        await query.edit_message_reply_markup(reply_markup=None)
        import json as _json
        raw = session.pending_intake.get("_refined_campaign", "{}")
        try:
            refined_data = _json.loads(raw)
            chosen = refined_data.get("refined", {})
        except _json.JSONDecodeError:
            chosen = {}

        if not chosen:
            await query.message.reply_text("⚠️ Idea đã hết hạn. Sếp gõ lại idea nhé.")
            return

        await _show_offer_lever_selection(query.message, session, chosen)
        return

    # User muốn sửa lại idea
    if data == "campaign_idea_redo":
        await query.edit_message_reply_markup(reply_markup=None)
        session.pending_intake["_awaiting_campaign_idea"] = "1"
        session.pending_intake.pop("_refined_campaign", None)
        await save_session(session)
        await query.message.reply_text(
            "✏️ OK, sếp mô tả lại idea campaign mới ạ.",
        )
        return

    # User pick offer lever 1/2/3/4 → show dynamic finalize form
    if data.startswith("lever_pick_"):
        await query.edit_message_reply_markup(reply_markup=None)
        try:
            lever_idx = int(data.split("_")[-1])
        except ValueError:
            await query.message.reply_text("⚠️ Lever pick không hợp lệ.")
            return

        import json as _json
        raw_levers = session.pending_intake.get("_offer_levers", "[]")
        raw_campaign = session.pending_intake.get("_chosen_campaign", "{}")
        try:
            levers = _json.loads(raw_levers)
            campaign = _json.loads(raw_campaign)
        except _json.JSONDecodeError:
            levers, campaign = [], {}

        if lever_idx < 0 or lever_idx >= len(levers) or not campaign:
            await query.message.reply_text("⚠️ Lever đã hết hạn. Sếp đề xuất lại nhé.")
            return

        chosen_lever = levers[lever_idx]
        await _show_dynamic_finalize_form(query.message, session, campaign, chosen_lever)
        return

    # User muốn AI đề xuất 4 levers khác
    if data == "lever_propose_again":
        await query.edit_message_reply_markup(reply_markup=None)
        import json as _json
        raw_campaign = session.pending_intake.get("_chosen_campaign", "{}")
        try:
            campaign = _json.loads(raw_campaign)
        except _json.JSONDecodeError:
            campaign = {}

        if not campaign:
            await query.message.reply_text("⚠️ Campaign đã hết hạn. Sếp /start lại nhé.")
            return

        await _show_offer_lever_selection(query.message, session, campaign)
        return

    # ── Sprint 5: Brand Voice lazy trigger callbacks ─────────────
    if data == "bv_setup_now":
        await query.edit_message_reply_markup(reply_markup=None)
        # Pivot session sang brand_voice skill — _bv_pending_skill đã lưu task gốc
        session.selected_task = "brand_voice"
        # KHÔNG xóa _bv_pending_skill — sẽ chain sau khi BV xong
        await save_session(session)
        await query.message.reply_text(
            "🎙 *Setup Brand Voice* — em hỏi vài câu để build bộ quy tắc.\n",
            parse_mode=ParseMode.MARKDOWN,
        )
        await _send_single_shot_form(query.message, session, "brand_voice")
        return

    if data == "bv_skip_for_now":
        await query.edit_message_reply_markup(reply_markup=None)
        # Mark skip cho session này — không hỏi lại
        session.pending_intake["_bv_skipped_session"] = "1"
        pending_skill = session.pending_intake.pop("_bv_pending_skill", None)
        await save_session(session)

        if pending_skill:
            # Resume skill gốc user định chạy
            from bot.keyboards import ADS_COPY_TIER_KEYBOARD as _ADS_KB, VIDEO_CREATOR_KEYBOARD as _VID_KB
            session.selected_task = (
                "ads_generator" if pending_skill in ("ads_copy", "ads_generator") else pending_skill
            )
            await save_session(session)

            if pending_skill in ("ads_copy", "ads_generator"):
                await query.message.reply_text(
                    "OK ạ. *Sản Xuất Nội Dung Ads* — Sếp muốn gen tier nào trước?",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=_ADS_KB,
                )
                return
            if pending_skill == "video_scripts":
                await query.message.reply_text(
                    "OK ạ. *Viết Kịch Bản Video* — Brief cho loại creator nào?",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=_VID_KB,
                )
                return
            await _send_single_shot_form(query.message, session, pending_skill)
        else:
            await query.message.reply_text("OK, sếp /start để chọn skill khác nhé.")
        return

    if data == "az_skip_campaign":
        await query.edit_message_reply_markup(reply_markup=None)
        # Cleanup full ideation + lever + finalize state
        for k in (
            "_awaiting_campaign_idea", "_proposed_campaigns", "_refined_campaign",
            "_chosen_campaign", "_offer_levers", "_chosen_lever",
            "_awaiting_campaign_finalize", "_finalize_campaign",
        ):
            session.pending_intake.pop(k, None)
        await save_session(session)
        await query.message.reply_text(
            "Sếp đánh giá output A→Z em vừa làm thế nào ạ?",
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
            from config import AGENT_TIMEOUT

            if skill_name in SINGLE_SHOT_STRATEGIC:
                from agents.pipeline import run_strategic_single_skill
                result = await asyncio.wait_for(
                    run_strategic_single_skill(skill_name, session),
                    timeout=AGENT_TIMEOUT,
                )
            elif skill_name in OPERATIONAL_TASKS:
                result = await asyncio.wait_for(
                    run_operational_skill(skill_name, session),
                    timeout=AGENT_TIMEOUT,
                )
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
    if data == "settings_change_name":
        await query.edit_message_reply_markup(reply_markup=None)
        session.pending_intake["_awaiting_user_name"] = "1"
        await save_session(session)
        await query.message.reply_text(
            "✏️ *Sếp gõ tên mới em sẽ gọi nhé:*",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if data == "settings_change_lang":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "🔤 Chọn mức tiếng Anh em dùng trong output:",
            reply_markup=LANG_LEVEL_KEYBOARD,
        )
        return

    if data == "settings_tokens":
        await query.edit_message_reply_markup(reply_markup=None)
        from tools.token_tracker import (
            get_used, get_remaining, get_quota, fmt, is_low, is_exhausted,
        )
        used = get_used(session)
        remaining = get_remaining(session)
        quota = get_quota(session)
        pct_used = (used / quota * 100) if quota else 0

        name = _get_user_name(session)
        addr = f"sếp {name}" if name else "sếp"

        status_emoji = "🟢"
        if is_exhausted(session): status_emoji = "🔴"
        elif is_low(session):     status_emoji = "🟡"

        msg = (
            f"💎 *Chi tiết token của {addr}*\n\n"
            f"{status_emoji} *Quota:* {fmt(quota)}\n"
            f"📉 *Đã dùng:* {fmt(used)} ({pct_used:.1f}%)\n"
            f"📊 *Còn lại:* {fmt(remaining)}\n"
        )
        if is_exhausted(session):
            msg += "\n🔴 *Hết quota!* Sếp liên hệ admin để nạp thêm hoặc chờ reset hàng tháng."
        elif is_low(session):
            msg += "\n⚠️ Sếp còn dưới 10% quota — cân nhắc dùng tiết kiệm."

        await query.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        return

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
                f"✅ Em ghi nhận ạ: *{level_label}*",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass

        # Đã có name (first-time flow đã hỏi trước) → welcome menu
        name = session.preferences.get("user_name", "")
        greeting = f"Em chào sếp {name}! Vào việc thôi 👇" if name else "Vào việc thôi sếp 👇"
        await query.message.reply_text(
            f"{greeting}\n\n" + _personalize(WELCOME_MESSAGE, session),
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

    if data == "menu_content_suite":
        await query.edit_message_text(
            "✨ *Content Suite v2 — 6 skills chuyên content production*\n\n"
            "_Output narrative chất lượng cao, modular, channel-aware._\n\n"
            "Chọn skill:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=CONTENT_SUITE_KEYBOARD,
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
        task_name = session.selected_task or "competitor_spy"
        session.pending_intake["_awaiting_rating_for"] = task_name
        await save_session(session)
        await query.edit_message_reply_markup(reply_markup=None)
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
        # Set rating marker TRƯỚC khi reply
        session.pending_intake["_awaiting_rating_for"] = session.selected_task or ""
        await save_session(session)
        await query.message.reply_text(
            "OK ạ, em chỉ gửi copy thôi. Sếp đánh giá output em vừa làm thế nào ạ?",
            reply_markup=RATING_KEYBOARD,
        )
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
        # Clean image buffers + set rating marker BEFORE reply
        session.pending_intake.pop("_last_image_b64", None)
        session.pending_intake.pop("_last_image_size", None)
        session.pending_intake.pop("_img_n", None)
        session.pending_intake.pop("_img_prompt", None)
        session.pending_intake["_awaiting_rating_for"] = session.selected_task or ""
        await save_session(session)
        await query.message.reply_text(
            "✅ Chốt! Sếp đánh giá output em vừa làm thế nào ạ?",
            reply_markup=RATING_KEYBOARD,
        )
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

    # ── Coming Soon placeholder ───────────────────────────────────
    if data.startswith("coming_soon_"):
        skill_key = data.replace("coming_soon_", "")
        labels = {
            "campaign_brief":      "📋 Viết Brief Campaign",
            "ads_generator":       "📢 Sản Xuất Nội Dung Ads",
            "video_scripts":       "🎬 Viết Kịch Bản Video",
            "landing_page":        "🌐 Thiết Kế Website",
            "sales_inbox_script":  "💬 Kịch Bản Sales",
        }
        label = labels.get(skill_key, skill_key)
        await query.answer(f"Skill này sắp ra mắt", show_alert=False)
        await query.message.reply_text(
            f"🚧 *{label}* — sắp ra mắt!\n\n"
            f"_Skill này đang được hoàn thiện. Em sẽ thông báo sếp ngay khi ready._\n\n"
            f"Trong lúc chờ, sếp có thể chạy các skill khác từ menu nhé:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=MAIN_MENU_KEYBOARD,
        )
        return

    # ── Task selection ────────────────────────────────────────────
    if data.startswith("task_"):
        task_type = data[5:]

        # Pre-check token quota
        try:
            from tools.token_tracker import is_exhausted, get_used, get_quota, fmt
            if is_exhausted(session):
                await query.answer("Đã hết quota token", show_alert=True)
                await query.message.reply_text(
                    f"🔴 *Đã hết quota token!*\n\n"
                    f"Đã dùng: {fmt(get_used(session))} / {fmt(get_quota(session))}\n\n"
                    f"_Sếp liên hệ admin để nạp thêm hoặc chờ reset hàng tháng._",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return
        except Exception as e:
            logger.warning("Token quota pre-check failed: %s", e)

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

        # ── Sprint 5: Brand Voice lazy gate cho creative ops skills ─
        if task_type in BRAND_VOICE_GATED_SKILLS:
            # Skip nếu user đã skip trong session này
            skipped_flag = session.pending_intake.get("_bv_skipped_session")
            if not skipped_flag:
                try:
                    from storage import has_brand_voice
                    has_bv = await has_brand_voice(user_id)
                except Exception as e:
                    logger.warning("[BV] has_brand_voice check failed: %s", e)
                    has_bv = True  # fail-safe: skip prompt nếu DB lỗi
                if not has_bv:
                    await query.edit_message_reply_markup(reply_markup=None)
                    # Lưu task gốc để resume sau khi BV setup xong
                    session.pending_intake["_bv_pending_skill"] = task_type
                    await save_session(session)
                    task_label = get_task(task_type).label if get_task(task_type) else task_type
                    await query.message.reply_text(
                        f"🎙 *Sếp chưa setup Brand Voice cho brand.*\n\n"
                        f"Em recommend setup 1 lần để các skill creative "
                        f"(*{task_label}*, post, ads, video, email...) tuân thủ đúng tone & "
                        f"từ ngữ brand — output nhất quán hơn 10x.\n\n"
                        f"_Sếp có thể bỏ qua giờ và setup sau, em vẫn chạy được skill này._",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=BRAND_VOICE_PROMPT_KEYBOARD,
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

    elif data == "continue_pipeline":
        # Defensive: ngày trước button này show giữa intermediate stages,
        # giờ pipeline auto-run hết → button không nên reach. Fallback về menu.
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "Pipeline đã chạy hết các bước rồi sếp. Sếp muốn làm gì tiếp?",
            reply_markup=MAIN_MENU_KEYBOARD,
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


async def _haiku_extract_intake(text: str, task_name: str, session) -> dict:
    """Dùng Haiku để extract free-form text → structured intake fields.
    Trả về dict {field_key: value}. Field nào không extract được thì bỏ qua.
    """
    import anthropic, json as _json
    from config import CLAUDE_HAIKU_MODEL, ANTHROPIC_API_KEY

    task = get_task(task_name)
    if not task:
        return {}

    fields_desc = "\n".join(
        f"- {f['key']} ({f['label']}): example = '{f.get('example', '')}'"
        for f in task.intake_fields
    )

    system = f"""Extract values từ user message thành JSON.

Task: {task.label}
Fields cần extract:
{fields_desc}

Output: JSON object với key = field name, value = string extracted từ user.
Nếu field không có trong message → bỏ qua, KHÔNG put null hay empty.
KHÔNG thêm field nào ngoài list trên.
Output CHỈ JSON object, không markdown, không giải thích."""

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    try:
        response = await client.messages.create(
            model=CLAUDE_HAIKU_MODEL,
            max_tokens=400,
            system=system,
            messages=[{"role": "user", "content": text}],
        )
        # Token tracking
        try:
            from tools.token_tracker import track_usage
            track_usage(session, response, label="intake_extract")
        except Exception:
            pass

        raw = response.content[0].text.strip()
        # Strip markdown code fence if present
        raw = re.sub(r"^```json\s*|^```\s*|```$", "", raw, flags=re.MULTILINE).strip()
        data = _json.loads(raw)
        # Validate: only keep declared field keys
        valid_keys = {f["key"] for f in task.intake_fields}
        return {k: str(v) for k, v in data.items() if k in valid_keys and v}
    except Exception as e:
        logger.warning("Haiku extract intake failed for %s: %s — text was: %s", task_name, e, text[:100])
        return {}


async def _send_strategy_aware_form(message: Message, session, task_name: str):
    """Khi user đã có Strategy (synthesis) — show form rút gọn.
    Form khác nhau theo skill:
    - campaign_brief / landing_page: cần chọn campaign cụ thể (3 câu)
    - content_calendar: KHÔNG cần chọn campaign — chỉ hỏi duration/channel (2 câu)
    """
    task = get_task(task_name)
    if not task:
        await _send_single_shot_form(message, session, task_name)
        return

    # ── Content Calendar — form siêu gọn, KHÔNG hỏi campaign ──
    if task_name == "content_calendar":
        profile = session.profile
        default_channels = profile.current_channels or "Facebook + TikTok + Zalo OA"
        lines = [
            f"✅ *{task.button_emoji} {task.label}*",
            "",
            "_Em đã có Marketing Strategy + ICP của sếp. Em sẽ build lịch tháng theo Story Arc 4 tuần + 4 nhóm khách._",
            "",
            "─────────────────────────",
            "*Sếp trả lời 2 ý nhanh (hoặc gõ 'mặc định' để em chạy luôn):*",
            "",
            "**1️⃣ Lên lịch cho tháng/tuần nào?**",
            "  _Vd: 'Tháng 1/2026' / 'Tuần này' / 'Tháng tới'_",
            "  _Mặc định: tháng tới_",
            "",
            "**2️⃣ Kênh nào sếp đang chạy?**",
            f"  _Em đoán: {default_channels}_",
            "  _Sếp confirm hoặc đổi (vd: 'chỉ TikTok + Zalo')_",
            "",
            "─────────────────────────",
            "💬 *Gõ 'mặc định' để chạy ngay với data có sẵn, hoặc trả lời theo format trên.*",
        ]

        session.pending_intake[OPS_INTAKE_AWAITING] = task_name
        session.pending_intake["_strategy_aware"] = "1"
        # Pre-fill defaults
        session.pending_intake.setdefault("duration", "Tháng tới (30 ngày)")
        session.pending_intake.setdefault("channels", default_channels)
        session.selected_task = task_name
        session.stage = PipelineStage.INTAKE
        await save_session(session)

        await message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
        return

    # ── Brief Campaign / Landing Page — cần chọn campaign cụ thể ──
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

    # Shortcut: nếu user gõ "mặc định" / "default" / "chạy luôn" / "ok"
    # → bỏ qua parse, dùng defaults đã pre-fill trong _strategy_aware form
    text_lower = text.strip().lower()
    SKIP_KEYWORDS = ("mặc định", "mac dinh", "default", "chạy luôn", "chay luon",
                     "ok chạy", "ok chay", "ok luôn", "ok luon", "chạy đi", "chay di")
    if any(kw == text_lower or text_lower.startswith(kw) for kw in SKIP_KEYWORDS):
        # Defaults đã được pre-fill ở _send_strategy_aware_form, dùng nguyên
        parsed = {}
    else:
        # Strategy-aware form: dùng Haiku để extract free-form text nếu structured parse fail
        is_strategy_aware = session.pending_intake.get("_strategy_aware") == "1"
        parsed = _parse_single_shot_intake(text, task_name)
        # Nếu strategy-aware và parsed có < 2 field → text là free-form, dùng Haiku extract
        if is_strategy_aware and len([v for v in parsed.values() if v]) < 2:
            try:
                parsed_haiku = await _haiku_extract_intake(text, task_name, session)
                # Merge: parsed_haiku ưu tiên nếu structured parse rỗng
                for k, v in parsed_haiku.items():
                    if v and not parsed.get(k):
                        parsed[k] = v
            except Exception as e:
                logger.warning("Haiku intake extract failed: %s", e)

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
        from config import AGENT_TIMEOUT
        # Pre-fetch live FB data cho các skills cần (competitor_spy, performance_audit)
        if task_name == "competitor_spy":
            await _prefetch_competitor_ads(update.message, session)
        elif task_name == "performance_audit":
            await _prefetch_performance_data(update.message, session)

        # Dispatch theo task type
        if task_name in SINGLE_SHOT_STRATEGIC:
            from agents.pipeline import run_strategic_single_skill
            result = await asyncio.wait_for(
                run_strategic_single_skill(task_name, session),
                timeout=AGENT_TIMEOUT,
            )
            await save_session(session)
            # Strategic single-skill render via existing pipeline-sequentially logic
            # but for 1 stage only — reuse _send_ops_result for uniform UX
            await _send_ops_result(update.message, session, task_name, result)
        else:
            result = await asyncio.wait_for(
                run_operational_skill(task_name, session),
                timeout=AGENT_TIMEOUT,
            )
            await save_session(session)
            await _send_ops_result(update.message, session, task_name, result)

            # Sprint 6: Tone Calibration Loop cho content_calendar
            if task_name == "content_calendar":
                await _start_tone_calibration(update.message, session, result)
                return

            # Sprint 5: Persist Brand Voice to DB sau khi gen xong
            if task_name == "brand_voice":
                await _persist_brand_voice_from_session(session, result)
                # Chain sang skill gốc nếu user vào BV qua lazy trigger
                pending_skill = session.pending_intake.pop("_bv_pending_skill", None)
                session.pending_intake.pop("_bv_skipped_session", None)
                if pending_skill and pending_skill != "brand_voice":
                    await save_session(session)
                    pending_label = (
                        get_task(pending_skill).label if get_task(pending_skill) else pending_skill
                    )
                    await update.message.reply_text(
                        f"✅ *Brand Voice đã lưu!* Em tiếp tục *{pending_label}* "
                        f"với BV vừa setup luôn nhé...",
                        parse_mode=ParseMode.MARKDOWN,
                    )
                    session.selected_task = pending_skill
                    session.pending_intake = {}  # reset for fresh intake
                    await save_session(session)
                    if pending_skill in ("ads_copy", "ads_generator"):
                        from bot.keyboards import ADS_COPY_TIER_KEYBOARD as _ADS_KB
                        await update.message.reply_text(
                            "📢 *Sản Xuất Nội Dung Ads* — chọn tier:",
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=_ADS_KB,
                        )
                    elif pending_skill == "video_scripts":
                        from bot.keyboards import VIDEO_CREATOR_KEYBOARD as _VID_KB
                        await update.message.reply_text(
                            "🎬 *Viết Kịch Bản Video* — chọn loại creator:",
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=_VID_KB,
                        )
                    else:
                        await _send_single_shot_form(update.message, session, pending_skill)
    except asyncio.TimeoutError:
        logger.error("Skill %s timeout sau %ds", task_name, 500)
        await update.message.reply_text(
            f"⚠️ Skill {task_name} timeout (API chậm hoặc treo). Sếp thử lại nhé.\n"
            f"Nếu lặp lại, có thể giảm scope intake để output ngắn hơn."
        )
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

    await _safe_reply(message, card_text, parse_mode=ParseMode.MARKDOWN)

    business_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", session.profile.business_name or task_name)[:30]
    business_name = session.profile.business_name or "Business"

    # Skip HTML cho content_generator — chỉ cần Excel master (split by week)
    SKIP_HTML_SKILLS = {"content_generator"}

    if task_name not in SKIP_HTML_SKILLS:
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

    # Content Suite v2: skills luôn output MD primary + Excel secondary (Haiku convert)
    CONTENT_SUITE_V2 = {"post_write", "post_adapt", "post_voice_check", "post_hooks", "post_visual", "post_batch"}

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

        # Content Suite v2: TRY gen Excel secondary qua Haiku auto-convert
        if task_name in CONTENT_SUITE_V2:
            try:
                xlsx_bytes = render_excel_file(task_name, task.label, parsed, skill.output_format, business_name)
                if xlsx_bytes:
                    buf2 = io.BytesIO(xlsx_bytes)
                    buf2.name = f"{task_name}_{business_slug}.xlsx"
                    await message.reply_document(
                        document=buf2,
                        filename=buf2.name,
                        caption=f"📊 *{task.label}* — bản Excel (overview/track status)",
                        parse_mode=ParseMode.MARKDOWN,
                    )
                else:
                    logger.info("Excel secondary skipped for %s (Haiku convert returned no table)", task_name)
            except Exception as e:
                logger.warning("Excel secondary gen failed for %s (non-blocking): %s", task_name, e)
    elif skill.primary_deliverable == PrimaryDeliverable.EXCEL:
        # Wrap toàn bộ Excel pipeline trong try/except để user luôn thấy lỗi
        try:
            logger.info("Rendering Excel for skill=%s (parsed keys: %s, raw len: %d)",
                        task_name, list(parsed.keys()),
                        len(parsed.get("raw", "")) if isinstance(parsed.get("raw"), str) else 0)
            xlsx_bytes = render_excel_file(task_name, task.label, parsed, skill.output_format, business_name)
        except Exception as e:
            logger.exception("render_excel_file CRASHED for %s: %s", task_name, e)
            xlsx_bytes = None
            await message.reply_text(
                f"⚠️ Lỗi khi gen Excel: `{str(e)[:200]}`\n_Admin đã được notify qua logs._",
                parse_mode=ParseMode.MARKDOWN,
            )

        if xlsx_bytes:
            try:
                buf = io.BytesIO(xlsx_bytes)
                buf.name = f"{task_name}_{business_slug}.xlsx"
                await message.reply_document(
                    document=buf,
                    filename=buf.name,
                    caption=f"📊 *{task.label}* — bản Excel (paste vào Google Sheet)",
                    parse_mode=ParseMode.MARKDOWN,
                )
                logger.info("Excel sent successfully for %s (%d bytes)", task_name, len(xlsx_bytes))
            except Exception as e:
                logger.exception("reply_document FAILED for %s: %s", task_name, e)
                await message.reply_text(
                    f"⚠️ Lỗi khi gửi file Excel: `{str(e)[:200]}`",
                    parse_mode=ParseMode.MARKDOWN,
                )
        elif xlsx_bytes is None and "Lỗi khi gen" not in (parsed.get("raw", "")[:50] or ""):
            # Chỉ show "không gen được" nếu chưa show error ở trên
            logger.warning("Excel render returned None for %s", task_name)
            await message.reply_text(
                "⚠️ Em không gen được Excel — output AI không có pipe table chuẩn. Sếp chạy lại nhé.",
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

    # NEW: Sau Lịch Nội Dung → hỏi sản xuất content luôn không
    if task_name == "content_calendar":
        await message.reply_text(
            "✅ *Lịch Nội Dung xong rồi sếp!*\n\n"
            "Sếp muốn em *sản xuất nội dung chi tiết* từ lịch này luôn không ạ?\n"
            "_(Mỗi bài: Hook + Body 200-300 chữ + CTA + Hashtags + Visual hint)_",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=CALENDAR_TO_CONTENT_GEN_KEYBOARD,
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
        # Resilient: fallback to plain text if Markdown parse fails
        # (vd tier name có underscore không nằm trong */_ entity)
        try:
            await message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.warning("Progress message Markdown failed (%s) — falling back to plain", e)
            try:
                await message.reply_text(msg, parse_mode=None)
            except Exception as e2:
                logger.warning("Progress message plain fallback also failed: %s", e2)

    # Sprint 8.5 — dispatch: task=full + flag on → Multi-Agent Orchestrator,
    # các task khác → existing single-skill path (backward compat)
    from config import USE_MULTI_AGENT_PIPELINE
    if task == "full" and USE_MULTI_AGENT_PIPELINE:
        pipeline_runner = run_multi_agent_targeted
        logger.info("Using Multi-Agent Orchestrator (Sprint 8) for task=full")
    else:
        pipeline_runner = run_targeted_pipeline
        if task == "full":
            logger.info("Multi-Agent disabled (USE_MULTI_AGENT=false) — using legacy path")

    async for stage_key, result in pipeline_runner(session, progress_callback=progress_cb):
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
    # Hotfix: filter out stages bị timeout/error (result chứa "⚠️")
    # để HTML builder không cố parse skip message làm crash toàn report.
    valid_stages = [
        (k, p) for (k, p) in parsed_stages
        if p and not (p.get("summary", "") + p.get("deliverable", "")).startswith("⚠️")
        and not (p.get("raw", "") or "").startswith("⚠️")
    ]
    skipped_count = len(parsed_stages) - len(valid_stages)
    if skipped_count > 0:
        logger.warning(
            "HTML report: filtered %d skipped/error stages out of %d total",
            skipped_count, len(parsed_stages),
        )

    if valid_stages:
        try:
            html_str = build_report(
                business_name=session.profile.business_name or "Business",
                industry=session.profile.industry or "",
                stage=session.profile.stage or "",
                parsed_stages=valid_stages,
            )
            await _send_html_report(message, html_str, session)
            if skipped_count > 0:
                await message.reply_text(
                    f"ℹ️ Report HTML đã gửi, nhưng có {skipped_count} bước bị timeout/lỗi — "
                    "không xuất hiện trong report. Sếp có thể chạy lại các bước đó riêng lẻ."
                )
        except Exception as e:
            logger.exception("Failed to generate HTML report: %s", e)
            await message.reply_text(
                "⚠️ Không generate được file HTML — phần tóm tắt ở trên đã đủ. Sếp có thể hỏi thêm tự do."
            )
    elif stage_count > 0:
        # All stages failed/skipped → no valid content for HTML
        await message.reply_text(
            "⚠️ Tất cả bước phân tích đều timeout/lỗi — không có gì để render HTML. "
            "Sếp thử chạy lại từng bước riêng lẻ (từ menu Chiến Lược) để xem bước nào fail."
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
            # A→Z xong — hỏi xác định campaign để triển khai
            addr = _addr(session)
            await message.reply_text(
                f"✅ *Hoàn thành A→Z!* Mở file HTML để xem báo cáo đầy đủ.\n\n"
                f"─────────────────────\n"
                f"🚀 *Bước tiếp theo: triển khai campaign cụ thể*\n\n"
                f"Strategy đã sẵn sàng. Giờ {addr} muốn chạy campaign gì?\n\n"
                f"💡 *Đã có ý tưởng* → em validate + refine với Customer + Market\n"
                f"🔍 *Chưa biết chạy gì* → em đề xuất 3 options phù hợp\n\n"
                f"_Sau khi xác định campaign → Brief Campaign → Lịch Nội Dung._",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=POST_AZ_CAMPAIGN_KEYBOARD,
            )
        else:
            await message.reply_text(
                f"✅ *Hoàn thành {task_label}!*\n\nSếp đánh giá output em vừa làm thế nào ạ?",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=RATING_KEYBOARD,
            )


# ─── Name personalization helpers ───────────────────────────────

def _validate_user_name(name: str) -> tuple[bool, str]:
    """Validate user_name: dưới 20 ký tự, có chữ cái. Returns (is_valid, error_msg)."""
    import re as _re

    if not name or not name.strip():
        return False, "Em chưa nhận được tên."

    name = name.strip()

    if len(name) > 20:
        return False, "Tên dài quá (>20 ký tự). Sếp đặt nickname ngắn gọn nhé."

    # Phải có ít nhất 1 chữ cái
    if not _re.search(r"[a-zA-ZÀ-ỹ]", name):
        return False, "Tên cần có ít nhất 1 chữ cái."

    return True, ""


def _get_user_name(session) -> str:
    """Lấy user_name từ preferences, fallback empty string."""
    return (session.preferences.get("user_name", "") or "").strip()


def _addr(session) -> str:
    """Cách xưng hô: 'sếp Nhiên' hoặc 'sếp' nếu chưa có tên."""
    name = _get_user_name(session)
    return f"sếp {name}" if name else "sếp"


def _personalize(text: str, session) -> str:
    """Replace 'sếp' với 'sếp {name}' trong text nếu có user_name."""
    name = _get_user_name(session)
    if not name:
        return text
    import re as _re
    # Match standalone 'sếp' (case-insensitive) NOT already followed by a name
    def repl(m):
        head = m.group(1)  # 'S' or 's'
        rest = m.group(2)  # 'ếp'
        return f"{head}{rest} {name}"
    # 'sếp' at word boundary, not followed by ' <Name>' already
    return _re.sub(r"\b(s|S)(ếp)\b(?!\s+[A-ZÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ])", repl, text)


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

    user_name = _get_user_name(session)
    name_directive = (
        f"User name: '{user_name}'. Khi xưng hô gọi 'sếp {user_name}' (vd: 'Em chào sếp {user_name}', "
        f"'Sếp {user_name} ơi'), KHÔNG gọi chỉ 'sếp' nếu có tên này."
    ) if user_name else "User chưa cho biết tên, gọi 'sếp' thôi."

    system_text = f"""Bạn là Max — AI CMO cho founder Việt Nam.

Tone: xưng "em" gọi user "sếp", professional + thân thiện.
{name_directive}
Language: {en_note}

🎛️ **INTENT ROUTING — khi user yêu cầu mở menu / xem task / xem skill / hỏi em làm được gì:**
- Reply ngắn 1-2 câu giới thiệu rồi kết thúc bằng marker `[OPEN_MENU]` ở dòng cuối cùng
- Vd: "OK ạ, đây là menu task em hỗ trợ:\n[OPEN_MENU]"
- KHÔNG dùng marker này nếu user chỉ hỏi advisor bình thường

🎯 **INTENT ROUTING — khi user chỉ định rõ 1 skill cụ thể:**
- Nếu user nói rõ tên 1 task (vd: "chạy phân tích đối thủ", "lên lịch nội dung") → kết thúc bằng marker `[RUN_TASK:<task_name>]`
- Vd: "OK em chạy ngay ạ.\n[RUN_TASK:competitor]"
- task_name AVAILABLE: market / competitor / customer / pricing / strategy / full /
  content_calendar / content_generator / email_zalo_sequence / competitor_spy / performance_audit
- task_name COMING SOON (KHÔNG được dùng RUN_TASK, chỉ thông báo "sắp ra mắt"):
  campaign_brief / ads_generator / video_scripts / landing_page / sales_inbox_script

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
⚙️ Sản xuất: Lịch Nội Dung, Sản Xuất Nội Dung, Chăm Sóc Khách Hàng
📊 Theo dõi: Theo Dõi Đối Thủ, Báo Cáo Ads

🚧 Sắp ra mắt (chưa dùng được, nếu user hỏi → thông báo coming soon):
   Viết Brief Campaign, Sản Xuất Nội Dung Ads, Viết Kịch Bản Video,
   Thiết Kế Website, Kịch Bản Sales"""

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
        # Token tracking
        try:
            from tools.token_tracker import track_usage
            track_usage(session, response, label="advisor")
        except Exception as e:
            logger.warning("Token tracking failed (advisor): %s", e)
        reply = response.content[0].text
    except Exception as e:
        logger.exception("Claude advisor fallback failed: %s", e)
        await update.message.reply_text(
            "⚠️ Em đang gặp lỗi kết nối. Sếp thử chọn task từ menu nhé:",
            reply_markup=MAIN_MENU_KEYBOARD,
        )
        return

    # Detect intent markers từ Sonnet response
    open_menu = "[OPEN_MENU]" in reply
    run_task_match = re.search(r"\[RUN_TASK:(\w+)\]", reply)

    # Strip markers khỏi text hiển thị
    clean_reply = re.sub(r"\[OPEN_MENU\]|\[RUN_TASK:\w+\]", "", reply).strip()

    # CASE 1: User yêu cầu mở menu
    if open_menu:
        session.pending_intake.pop("_advisor_mode", None)
        await save_session(session)
        await send_long_message(
            update.message,
            clean_reply or "OK ạ, đây là menu task em hỗ trợ:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=MAIN_MENU_KEYBOARD,
        )
        return

    # CASE 2: User yêu cầu chạy task cụ thể
    if run_task_match:
        task_name = run_task_match.group(1)
        from agents.task_registry import TASK_REGISTRY
        if task_name in TASK_REGISTRY:
            session.pending_intake.pop("_advisor_mode", None)
            session.selected_task = task_name
            await save_session(session)
            if clean_reply:
                await update.message.reply_text(clean_reply, parse_mode=ParseMode.MARKDOWN)
            # Launch skill flow — same path as task_X callback
            await _launch_task_from_advisor(update, context, session, task_name)
            return
        # Invalid task name → fall through to default advisor reply

    # CASE 3: Default — advisor reply với "Hỏi tiếp" / "Mở menu"
    session.pending_intake["_advisor_mode"] = "1"
    await save_session(session)

    await send_long_message(
        update.message,
        clean_reply or reply,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Hỏi tiếp",      callback_data="continue_advisor")],
            [InlineKeyboardButton("⚙️ Mở menu task", callback_data="menu_main")],
        ]),
    )


async def _launch_task_from_advisor(update, context, session, task_name: str):
    """Khi advisor detect [RUN_TASK:X] → launch skill flow tương đương click button."""
    from agents.task_registry import OPERATIONAL_TASKS, get_task
    SINGLE_SHOT_STRATEGIC = {"market", "competitor", "customer", "pricing"}
    STRATEGY_GATED = {"campaign_brief", "content_calendar", "landing_page"}

    msg = update.message

    # Strategy gating
    if task_name in STRATEGY_GATED:
        has_strategy = bool(
            session.get_latest_result("synthesis") or session.get_latest_result("strategy")
        )
        if has_strategy:
            await _send_strategy_aware_form(msg, session, task_name)
        else:
            session.pending_followup_skill = task_name
            await save_session(session)
            task_label = (get_task(task_name).label if get_task(task_name) else task_name)
            await msg.reply_text(
                f"📋 *{task_label} cần Strategy nền.* Em chạy *A→Z* trước nhé sếp?",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=NEEDS_STRATEGY_KEYBOARD,
            )
        return

    # Content Generator cần Calendar
    if task_name == "content_generator":
        if not session.get_latest_result("content_calendar"):
            session.pending_followup_skill = "content_generator"
            await save_session(session)
            await msg.reply_text(
                "✍️ Sản Xuất Nội Dung cần *Lịch Nội Dung* trước. Em chạy Calendar trước nhé?",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📅 Chạy Lịch Nội Dung trước", callback_data="task_content_calendar")],
                    [InlineKeyboardButton("⏭️ Quay lại menu",              callback_data="menu_main")],
                ]),
            )
            return

    # Special skills with variant chooser
    if task_name in ("ads_copy", "ads_generator"):
        session.selected_task = "ads_generator"
        await save_session(session)
        await msg.reply_text(
            "📢 *Sản Xuất Nội Dung Ads* — Sếp muốn gen tier nào trước ạ?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ADS_COPY_TIER_KEYBOARD,
        )
        return
    if task_name == "video_scripts":
        await msg.reply_text(
            "🎬 *Viết Kịch Bản Video* — Brief cho loại creator nào ạ?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=VIDEO_CREATOR_KEYBOARD,
        )
        return

    # Operational + strategic single-shot → form
    if task_name in OPERATIONAL_TASKS or task_name in SINGLE_SHOT_STRATEGIC:
        await _send_single_shot_form(msg, session, task_name)
        return

    # Strategy multi-turn / full → intake
    session.stage = PipelineStage.INTAKE
    await save_session(session)
    opening = TASK_OPENING_QUESTIONS.get(task_name, TASK_OPENING_QUESTIONS["full"])
    task_label = (get_task(task_name).label if get_task(task_name) else task_name)
    await msg.reply_text(
        f"✅ *{task_label}*\n\n{opening}",
        parse_mode=ParseMode.MARKDOWN,
    )


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


# ─── Campaign Ideation Helpers ────────────────────────────────────

async def _handle_campaign_idea_text(update, context, session, text: str):
    """Refine user's campaign idea với customer_insight + market_research, rồi show confirm card."""
    text = (text or "").strip()
    if len(text) < 5:
        await update.message.reply_text(
            "⚠️ Idea hơi ngắn. Sếp mô tả thêm 1-2 câu để em refine chính xác ạ.",
        )
        return

    # Clear flag
    session.pending_intake.pop("_awaiting_campaign_idea", None)
    await save_session(session)

    await update.message.reply_text(
        "✨ *Em đang đối chiếu idea với Customer Insight + Market Research...*\n"
        "_Khoảng 20-40 giây ạ._",
        parse_mode=ParseMode.MARKDOWN,
    )
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING,
    )

    try:
        from agents.campaign_ideation import refine_user_idea, format_refined_card
        refined_data = await refine_user_idea(session, text)
        if not refined_data:
            await update.message.reply_text(
                "⚠️ Em refine bị lỗi. Sếp thử lại nhé.",
                reply_markup=POST_AZ_CAMPAIGN_KEYBOARD,
            )
            return

        # Save refined data để confirm_callback dùng lại
        import json as _json
        session.pending_intake["_refined_campaign"] = _json.dumps(refined_data, ensure_ascii=False)
        await save_session(session)

        card = format_refined_card(refined_data)
        await send_long_message(
            update.message, card,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=CAMPAIGN_IDEA_CONFIRM_KEYBOARD,
        )
    except Exception as e:
        logger.exception("Campaign refine failed: %s", e)
        await update.message.reply_text(
            f"⚠️ Lỗi khi refine: {str(e)[:200]}",
            reply_markup=POST_AZ_CAMPAIGN_KEYBOARD,
        )


async def _show_offer_lever_selection(message: Message, session, campaign: dict):
    """Sau khi chốt campaign, AI propose 4 offer levers SPECIFIC cho campaign này.
    Save campaign + levers vào pending_intake để lever_pick_X dùng lại.
    """
    from agents.campaign_ideation import propose_offer_levers, format_levers_card
    import json as _json

    # Cleanup ideation state, prepare for lever selection
    for k in ("_awaiting_campaign_idea", "_proposed_campaigns", "_refined_campaign",
              "_awaiting_campaign_finalize", "_finalize_campaign", "_chosen_lever"):
        session.pending_intake.pop(k, None)
    session.pending_intake.pop(OPS_INTAKE_AWAITING, None)

    session.pending_intake["_chosen_campaign"] = _json.dumps(campaign, ensure_ascii=False)
    await save_session(session)

    await message.reply_text(
        "🎯 *Em đang đề xuất 4 offer levers phù hợp với campaign vừa chốt...*\n"
        "_Khoảng 15-25 giây ạ._",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        levers = await propose_offer_levers(session, campaign)
        if not levers:
            await message.reply_text(
                "⚠️ Em đề xuất lever bị lỗi. Sếp thử lại hoặc /start lại nhé.",
                reply_markup=POST_AZ_CAMPAIGN_KEYBOARD,
            )
            return

        # Save levers vào pending_intake
        session.pending_intake["_offer_levers"] = _json.dumps(levers, ensure_ascii=False)
        await save_session(session)

        # Build keyboard động — chỉ show số nút tương ứng số levers
        if len(levers) == 4:
            kb = OFFER_LEVER_KEYBOARD
        else:
            # Fallback: build keyboard với đúng số levers thực tế
            from telegram import InlineKeyboardButton as _Btn, InlineKeyboardMarkup as _Mkup
            emoji_num = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
            row = [
                _Btn(emoji_num[i], callback_data=f"lever_pick_{i}")
                for i in range(len(levers))
            ]
            kb = _Mkup([
                row,
                [_Btn("🔄 Đề xuất 4 levers khác", callback_data="lever_propose_again")],
                [_Btn("⏭️ Hủy, quay lại đánh giá", callback_data="az_skip_campaign")],
            ])

        card = format_levers_card(campaign, levers)
        await send_long_message(
            message, card,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb,
        )
    except Exception as e:
        logger.exception("Show offer levers failed: %s", e)
        await message.reply_text(
            f"⚠️ Lỗi khi đề xuất lever: {str(e)[:200]}",
            reply_markup=POST_AZ_CAMPAIGN_KEYBOARD,
        )


async def _show_dynamic_finalize_form(message: Message, session, campaign: dict, lever: dict):
    """Show form động: lever params + Ngày bắt đầu + Ngày kết thúc."""
    from agents.campaign_ideation import format_dynamic_finalize_form
    import json as _json

    session.pending_intake["_chosen_lever"] = _json.dumps(lever, ensure_ascii=False)
    session.pending_intake["_awaiting_campaign_finalize"] = "1"
    session.stage = PipelineStage.INTAKE
    await save_session(session)

    form_text = format_dynamic_finalize_form(campaign, lever)
    await send_long_message(message, form_text, parse_mode=ParseMode.MARKDOWN)


async def _handle_campaign_finalize_text(update, context, session, text: str):
    """Parse user reply (dynamic theo lever) → merge với campaign + lever → run campaign_brief."""
    from agents.campaign_ideation import (
        parse_dynamic_finalize_form, merge_to_brief_fields, get_finalize_fields,
    )
    import json as _json

    raw_campaign = session.pending_intake.get("_chosen_campaign", "{}")
    raw_lever = session.pending_intake.get("_chosen_lever", "{}")
    try:
        campaign = _json.loads(raw_campaign)
        lever = _json.loads(raw_lever)
    except _json.JSONDecodeError:
        campaign, lever = {}, {}

    if not campaign or not lever:
        await update.message.reply_text(
            "⚠️ Campaign hoặc lever đã hết hạn. Sếp /start lại nhé.",
        )
        return

    fields = get_finalize_fields(lever)
    parsed, missing = parse_dynamic_finalize_form(text, fields)

    if missing:
        await update.message.reply_text(
            "⚠️ *Còn thiếu thông tin:*\n"
            + "\n".join(f"• {lbl}" for lbl in missing)
            + "\n\nSếp gửi lại form đầy đủ giúp em ạ.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Cleanup ideation states
    for k in ("_awaiting_campaign_finalize", "_chosen_campaign", "_chosen_lever",
              "_offer_levers"):
        session.pending_intake.pop(k, None)

    # Merge campaign + lever + user inputs → 4 fields cho campaign_brief
    brief_fields = merge_to_brief_fields(campaign, lever, parsed)
    for key, val in brief_fields.items():
        session.pending_intake[key] = val or "(chưa rõ)"

    session.selected_task = "campaign_brief"
    await save_session(session)

    await update.message.reply_text(
        f"✅ *Đã nhận đủ thông tin!*\n\n"
        f"📋 Em làm Brief Campaign cho \"{campaign.get('name', '?')}\" "
        f"(lever: {lever.get('name', '?')})...\n"
        f"_Khoảng 60-90 giây ạ._",
        parse_mode=ParseMode.MARKDOWN,
    )
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING,
    )

    try:
        from config import AGENT_TIMEOUT
        result = await asyncio.wait_for(
            run_operational_skill("campaign_brief", session),
            timeout=AGENT_TIMEOUT,
        )
        await save_session(session)
        await _send_ops_result(update.message, session, "campaign_brief", result)
    except asyncio.TimeoutError:
        await update.message.reply_text("⚠️ Brief Campaign timeout. Sếp thử lại nhé.")
    except Exception as e:
        logger.exception("Campaign brief auto-run failed: %s", e)
        await update.message.reply_text(f"⚠️ Lỗi khi chạy Brief: {str(e)[:200]}")


# ─── Brand Voice Persistence (Sprint 5) ──────────────────────────

def _split_rule_lines(text: str) -> list[str]:
    """Parse multiline rules from user input (numbered list, bullets, plain lines)."""
    if not text:
        return []
    items = []
    for line in text.split("\n"):
        line = line.strip()
        cleaned = re.sub(r"^[\d\.\-\*\+\)\s]+", "", line).strip()
        if cleaned:
            items.append(cleaned)
    return items[:10]  # cap


def _extract_banned_words_from_md(markdown: str) -> list[str]:
    """Best-effort parse banned-words table từ BrandVoiceSkill markdown output."""
    words = []
    # Section "NÊN TRÁNH" followed by markdown table
    m = re.search(r"(?i)NÊN TRÁNH.*?\n((?:\|.*\n){2,})", markdown, re.DOTALL)
    if not m:
        return words
    for line in m.group(1).split("\n"):
        if "|" not in line or "---" in line or "Lý do" in line:
            continue
        cells = [c.strip().strip("`*\"'") for c in line.split("|") if c.strip()]
        if len(cells) >= 2:
            w = cells[1] if cells[0].isdigit() else cells[0]
            if w and w not in ("...", "Từ/cụm tránh"):
                words.append(w)
    return words[:10]


def _extract_tone_from_md(markdown: str) -> list[str]:
    """Heuristic — extract tone descriptors from markdown."""
    m = re.search(r"(?i)tone[^:\n]*:\s*([^\n]+)", markdown)
    if not m:
        return []
    tones = re.split(r"[,;]|\s+và\s+", m.group(1))
    return [t.strip().strip("*_.`") for t in tones if t.strip()][:5]


async def _persist_brand_voice_from_session(session, raw_markdown: str):
    """Sau khi brand_voice skill xong, save BV vào user_brand_voice DB.
    Parse what we can từ pending_intake + markdown output. Graceful on error.
    """
    try:
        from storage import save_brand_voice, BrandVoice

        intake = session.pending_intake or {}
        do_rules = _split_rule_lines(intake.get("do_list", ""))
        dont_rules = _split_rule_lines(intake.get("dont_list", ""))
        sample_content = intake.get("sample_content") or None

        bv = BrandVoice(
            user_id=session.user_id,
            do_rules=do_rules,
            dont_rules=dont_rules,
            tone_descriptors=_extract_tone_from_md(raw_markdown),
            banned_words=_extract_banned_words_from_md(raw_markdown),
            sample_content=sample_content,
            rules_markdown=raw_markdown[:10000],  # cap 10K
            industry_context=session.profile.industry,
        )

        saved = await save_brand_voice(bv)
        if saved:
            logger.info(
                "[BV] Persisted user=%d version=%d do=%d dont=%d banned=%d",
                session.user_id, saved.version,
                len(saved.do_rules), len(saved.dont_rules), len(saved.banned_words),
            )
        else:
            logger.warning("[BV] save_brand_voice returned None for user=%d", session.user_id)
    except Exception as e:
        # Non-fatal — flow vẫn tiếp tục
        logger.exception("[BV] persist failed for user=%d: %s", session.user_id, e)


# ─── Admin Commands ───────────────────────────────────────────────

def _admin_only(handler):
    """Decorator: block non-admin users khỏi admin commands."""
    @functools.wraps(handler)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE):
        from config import ADMIN_IDS
        user_id = update.effective_user.id if update.effective_user else None
        if not user_id or user_id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Lệnh này chỉ dành cho admin.")
            return
        return await handler(update, context)
    return wrapped


@_admin_only
async def cmd_admin_addquota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/addquota <user_id> <amount> — Cộng thêm N token vào quota của user."""
    args = context.args
    if len(args) != 2 or not args[0].lstrip("-").isdigit() or not args[1].lstrip("-").isdigit():
        await update.message.reply_text(
            "⚠️ *Cú pháp:* `/addquota <user_id> <amount>`\n"
            "Ví dụ: `/addquota 123456789 500000`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    target_id = int(args[0])
    amount = int(args[1])
    if amount <= 0:
        await update.message.reply_text("⚠️ Amount phải là số dương.")
        return

    session = await get_session(target_id)
    from tools.token_tracker import get_quota, get_used, fmt

    old_quota = get_quota(session)
    new_quota = old_quota + amount
    session.preferences["token_quota"] = str(new_quota)
    await save_session(session)

    used = get_used(session)
    await update.message.reply_text(
        f"✅ *Nạp token thành công*\n\n"
        f"👤 User ID: `{target_id}`\n"
        f"➕ Nạp thêm: *{fmt(amount)}*\n"
        f"📊 Quota mới: *{fmt(new_quota)}* (trước: {fmt(old_quota)})\n"
        f"📉 Đã dùng: *{fmt(used)}*\n"
        f"💚 Còn lại: *{fmt(max(0, new_quota - used))}*",
        parse_mode=ParseMode.MARKDOWN,
    )
    logger.info("[admin] addquota user=%d amount=%d new_quota=%d by admin=%d",
                target_id, amount, new_quota, update.effective_user.id)


@_admin_only
async def cmd_admin_setquota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/setquota <user_id> <amount> — Set quota tuyệt đối cho user (ghi đè)."""
    args = context.args
    if len(args) != 2 or not args[0].lstrip("-").isdigit() or not args[1].lstrip("-").isdigit():
        await update.message.reply_text(
            "⚠️ *Cú pháp:* `/setquota <user_id> <amount>`\n"
            "Ví dụ: `/setquota 123456789 2000000`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    target_id = int(args[0])
    new_quota = int(args[1])
    if new_quota < 0:
        await update.message.reply_text("⚠️ Quota phải >= 0.")
        return

    session = await get_session(target_id)
    from tools.token_tracker import get_quota, get_used, fmt

    old_quota = get_quota(session)
    session.preferences["token_quota"] = str(new_quota)
    await save_session(session)

    used = get_used(session)
    await update.message.reply_text(
        f"✅ *Set quota thành công*\n\n"
        f"👤 User ID: `{target_id}`\n"
        f"📊 Quota mới: *{fmt(new_quota)}* (trước: {fmt(old_quota)})\n"
        f"📉 Đã dùng: *{fmt(used)}*\n"
        f"💚 Còn lại: *{fmt(max(0, new_quota - used))}*",
        parse_mode=ParseMode.MARKDOWN,
    )
    logger.info("[admin] setquota user=%d new_quota=%d old_quota=%d by admin=%d",
                target_id, new_quota, old_quota, update.effective_user.id)


@_admin_only
async def cmd_admin_resetusage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/resetusage <user_id> — Reset token_used về 0, giữ nguyên quota."""
    args = context.args
    if len(args) != 1 or not args[0].lstrip("-").isdigit():
        await update.message.reply_text(
            "⚠️ *Cú pháp:* `/resetusage <user_id>`\n"
            "Ví dụ: `/resetusage 123456789`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    target_id = int(args[0])
    session = await get_session(target_id)
    from tools.token_tracker import get_quota, get_used, fmt

    old_used = get_used(session)
    quota = get_quota(session)
    session.preferences["token_used"] = "0"
    await save_session(session)

    await update.message.reply_text(
        f"✅ *Reset usage thành công*\n\n"
        f"👤 User ID: `{target_id}`\n"
        f"🗑️ Đã xóa: *{fmt(old_used)}* tokens đã dùng\n"
        f"📊 Quota hiện tại: *{fmt(quota)}*\n"
        f"💚 Còn lại sau reset: *{fmt(quota)}*",
        parse_mode=ParseMode.MARKDOWN,
    )
    logger.info("[admin] resetusage user=%d old_used=%d by admin=%d",
                target_id, old_used, update.effective_user.id)


@_admin_only
async def cmd_admin_userinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/userinfo <user_id> — Xem thông tin token + profile của user."""
    args = context.args
    if len(args) != 1 or not args[0].lstrip("-").isdigit():
        await update.message.reply_text(
            "⚠️ *Cú pháp:* `/userinfo <user_id>`\n"
            "Ví dụ: `/userinfo 123456789`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    target_id = int(args[0])
    session = await get_session(target_id)
    from tools.token_tracker import get_quota, get_used, get_remaining, fmt, is_low, is_exhausted

    used = get_used(session)
    quota = get_quota(session)
    remaining = get_remaining(session)
    pct = (used / quota * 100) if quota else 0

    if is_exhausted(session):
        status = "🔴 Hết quota"
    elif is_low(session):
        status = "⚠️ Sắp hết (< 10%)"
    else:
        status = "✅ Bình thường"

    name = session.preferences.get("user_name", "_(chưa đặt)_")
    business = session.profile.business_name or "_(chưa có)_"
    stage = session.stage.value

    await update.message.reply_text(
        f"👤 *Thông tin user `{target_id}`*\n\n"
        f"🏷️ Tên: {name}\n"
        f"🏢 Business: {business}\n"
        f"📍 Stage hiện tại: `{stage}`\n\n"
        f"─────────────────────\n"
        f"💎 *Token*\n"
        f"📊 Quota: *{fmt(quota)}*\n"
        f"📉 Đã dùng: *{fmt(used)}* ({pct:.1f}%)\n"
        f"💚 Còn lại: *{fmt(remaining)}*\n"
        f"📌 Trạng thái: {status}",
        parse_mode=ParseMode.MARKDOWN,
    )


# ─────────────────────────────────────────────────────────────────
# /history — Campaign History + Semantic Search  (Sprint 8)
# ─────────────────────────────────────────────────────────────────

async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /history [query] — Xem hoặc tìm kiếm lịch sử campaigns.

    - /history          → Liệt kê 10 campaigns gần nhất
    - /history <query>  → Semantic search (tìm campaign tương tự)

    Mỗi entry hiển thị: business, ngành, mục tiêu, ngày chạy.
    """
    user_id = update.effective_user.id
    query = " ".join(context.args).strip() if context.args else ""

    from storage.campaign_history import list_campaigns, search_similar_campaigns

    await update.message.reply_text("🔍 Đang tìm...", parse_mode=ParseMode.MARKDOWN)

    if query:
        campaigns = await search_similar_campaigns(user_id, query, top_k=5)
        header = f"🔍 *Kết quả tìm kiếm:* _{query}_\n\n"
    else:
        campaigns = await list_campaigns(user_id, limit=10)
        header = "📚 *Lịch sử Campaigns của bạn*\n\n"

    if not campaigns:
        msg = (
            header +
            "_(Chưa có campaign nào được lưu)_\n\n"
            "💡 Chạy phân tích A→Z để bắt đầu tích lũy lịch sử."
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        return

    lines = [header]
    for i, c in enumerate(campaigns, start=1):
        biz  = c.get("business_name") or "_(chưa đặt tên)_"
        ind  = c.get("industry") or "—"
        goal = c.get("primary_goal") or "—"
        date = (c.get("created_at") or "")[:10]  # YYYY-MM-DD
        sim  = c.get("similarity")

        sim_tag = f" · {sim*100:.0f}% match" if sim is not None else ""
        lines.append(
            f"*{i}.* {biz}\n"
            f"   📌 {ind} · {goal}\n"
            f"   🗓 {date}{sim_tag}\n"
        )

    lines.append("\n💡 _Dùng `/history <từ khoá>` để tìm campaign tương tự_")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ═════════════════════════════════════════════════════════════════
# Sprint 6 — Tone Calibration Loop
# ═════════════════════════════════════════════════════════════════

async def _start_tone_calibration(message, session, calendar_result: str) -> None:
    """
    Khởi động Tone Calibration Loop sau khi content_calendar gen xong.
    Extract Post 1 → show với tone check keyboard.
    """
    from agents.tone_calibration import parse_first_post
    from bot.keyboards import TONE_CHECK_KEYBOARD

    first = parse_first_post(calendar_result)
    if not first:
        # Không parse được → skip calibration
        return

    # Lưu state calibration
    session.tone_calibration = {
        "stage":            "checking_tone",
        "rejection_count":  0,
        "post1_content":    first["full_block"],
        "calendar_full":    calendar_result,
        "locked_signals":   {},
    }
    await save_session(session)

    preview = first["preview"][:500]
    await message.reply_text(
        "🎨 *Kiểm tra Tone — Bài đăng đầu tiên*\n\n"
        "_Em extract bài đầu tiên để sếp check tone trước khi em apply cho toàn bộ calendar:_\n\n"
        f"```\n{preview}\n```\n\n"
        "Tone ổn chưa sếp? Nếu muốn chỉnh, gõ feedback sau khi bấm *Chỉnh tone*.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=TONE_CHECK_KEYBOARD,
    )


async def _handle_tone_feedback(update, context, session, text: str) -> None:
    """
    Xử lý feedback text sau khi user bấm 'Chỉnh tone'.
    Extract signals → regen Post 1 → show với TONE_REGEN_KEYBOARD.
    """
    from agents.tone_calibration import (
        extract_tone_signals, regen_post_with_signals, format_signals_card
    )
    from bot.keyboards import TONE_REGEN_KEYBOARD

    cal = session.tone_calibration
    rejection_count = cal.get("rejection_count", 0) + 1

    await update.message.reply_text("🔄 _Đang chỉnh tone..._", parse_mode=ParseMode.MARKDOWN)

    post1 = cal.get("post1_content", "")
    signals = await extract_tone_signals(session, text, post1)
    new_post = await regen_post_with_signals(session, post1, signals)

    # Update state
    session.tone_calibration.update({
        "stage":           "checking_tone",
        "rejection_count": rejection_count,
        "post1_content":   new_post,
        "locked_signals":  signals,
    })
    await save_session(session)

    signals_card = format_signals_card(signals)
    max_attempts = 3
    remaining = max_attempts - rejection_count

    kb = TONE_REGEN_KEYBOARD
    suffix = ""
    if rejection_count >= max_attempts:
        suffix = "\n\n⚠️ _Đã chỉnh tối đa 3 lần — lần này sẽ tự lock tone._"
        # Auto-approve after 3 rejections
        await _tone_lock_and_apply(update.message, session)
        return

    await update.message.reply_text(
        f"{signals_card}\n\n"
        f"*Bài viết lại:*\n```\n{new_post[:500]}\n```\n"
        f"_(Còn {remaining} lần chỉnh){suffix}_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb,
    )


async def _tone_lock_and_apply(message, session) -> None:
    """
    Lock tone signals → apply lên full calendar → update session.
    """
    from agents.tone_calibration import apply_tone_to_calendar
    from agents.post_actions import parse_calendar_to_posts

    cal = session.tone_calibration
    signals = cal.get("locked_signals", {})
    post1 = cal.get("post1_content", "")
    calendar_full = cal.get("calendar_full", "")

    await message.reply_text(
        "🔒 *Tone đã lock!* Em đang apply cho toàn bộ calendar...",
        parse_mode=ParseMode.MARKDOWN,
    )

    # Apply tone lên full calendar
    if signals:
        updated_calendar = await apply_tone_to_calendar(session, calendar_full, signals, post1)
    else:
        updated_calendar = calendar_full

    # Sprint 7: Parse posts → assign POST-XXX IDs
    campaign_id = session.pending_intake.get("campaign_name", "")
    posts = parse_calendar_to_posts(updated_calendar, campaign_id=campaign_id)
    if posts:
        session.content_outputs.update(posts)

    # Update results + clear tone state
    session.add_result("content_calendar", updated_calendar)
    session.tone_calibration = {"stage": "done", "locked_signals": signals}
    await save_session(session)

    # Show updated calendar
    preview = updated_calendar[:2000] + ("..." if len(updated_calendar) > 2000 else "")
    await message.reply_text(
        f"✅ *Content Calendar (Tone Applied)*\n\n{preview}",
        parse_mode=ParseMode.MARKDOWN,
    )

    # Sprint 7: Show post IDs summary
    if posts:
        post_count = len(posts)
        await message.reply_text(
            f"📋 *{post_count} bài đã được gán ID*\n\n"
            + "\n".join([f"`{pid}` — {p.get('channel','').capitalize()} · Tuần {p.get('week',1)}"
                        for pid, p in list(posts.items())[:10]])
            + ("\n..." if post_count > 10 else "")
            + "\n\n💡 _Dùng /post \\<ID\\> để xem + quản lý từng bài_",
            parse_mode=ParseMode.MARKDOWN,
        )


# ─── Tone calibration callbacks ───────────────────────────────────────────────

async def _handle_tone_callback(query, session) -> None:
    """Dispatch tone_* callback queries."""
    data = query.data

    if data == "tone_approve":
        await query.edit_message_reply_markup(reply_markup=None)
        # Lock với signals hiện tại (có thể rỗng nếu approve ngay lần đầu)
        await _tone_lock_and_apply(query.message, session)

    elif data == "tone_reject":
        await query.edit_message_reply_markup(reply_markup=None)
        session.tone_calibration["stage"] = "waiting_feedback"
        await save_session(session)
        await query.message.reply_text(
            "✏️ *Gõ feedback về tone để em chỉnh:*\n\n"
            "_Ví dụ: 'Viết thân mật hơn, bớt formal' / 'Thêm emoji' / 'Ngắn hơn, mạnh hơn'_",
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "tone_skip":
        await query.edit_message_reply_markup(reply_markup=None)
        # Skip: parse calendar gốc sang POST-XXX luôn không apply tone
        cal = session.tone_calibration
        from agents.post_actions import parse_calendar_to_posts
        posts = parse_calendar_to_posts(cal.get("calendar_full", ""))
        if posts:
            session.content_outputs.update(posts)
        session.tone_calibration = {"stage": "done"}
        await save_session(session)
        await query.message.reply_text(
            f"⏭ _Bỏ qua tone calibration. Calendar đã lưu với {len(posts)} bài._",
            parse_mode=ParseMode.MARKDOWN,
        )


# ═════════════════════════════════════════════════════════════════
# Sprint 7 — Per-post Actions (/post command + callbacks)
# ═════════════════════════════════════════════════════════════════

async def cmd_post(update, context) -> None:
    """
    /post <POST-ID> — Xem chi tiết + action menu cho 1 bài.
    Ví dụ: /post POST-001  hoặc  /post 001
    """
    user_id = update.effective_user.id
    from storage import get_session
    session = await get_session(user_id)

    arg = " ".join(context.args).strip().upper()
    if not arg.startswith("POST-"):
        arg = f"POST-{arg.zfill(3)}"

    post = session.content_outputs.get(arg)
    if not post:
        await update.message.reply_text(
            f"❌ Không tìm thấy `{arg}`.\n"
            "Dùng `/history` để xem danh sách posts.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    from agents.post_actions import format_post_preview
    from bot.keyboards import post_action_keyboard

    preview = format_post_preview(arg, post)
    await update.message.reply_text(
        preview,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=post_action_keyboard(arg),
    )


async def _handle_post_action_callback(query, session) -> None:
    """Dispatch post_edit/adapt/variant/delete callbacks."""
    data = query.data  # e.g. "post_edit_001"
    parts = data.split("_", 2)  # ["post", "edit", "001"]
    if len(parts) < 3:
        return

    action = parts[1]  # edit | adapt | variant | delete
    pid_short = parts[2]  # "001"
    post_id = f"POST-{pid_short}"
    post = session.content_outputs.get(post_id)

    if not post:
        await query.answer("Không tìm thấy bài này.", show_alert=True)
        return

    await query.edit_message_reply_markup(reply_markup=None)

    if action == "delete":
        session.content_outputs[post_id]["status"] = "deleted"
        await save_session(session)
        await query.message.reply_text(
            f"🗑 `{post_id}` đã xoá khỏi calendar.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if action == "adapt":
        # Show channel selection
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 TikTok",    callback_data=f"adapt_{pid_short}_tiktok")],
            [InlineKeyboardButton("💬 Zalo OA",   callback_data=f"adapt_{pid_short}_zalo")],
            [InlineKeyboardButton("📸 Instagram", callback_data=f"adapt_{pid_short}_instagram")],
            [InlineKeyboardButton("📧 Email",     callback_data=f"adapt_{pid_short}_email")],
        ])
        await query.message.reply_text(
            f"🔄 Adapt `{post_id}` sang kênh nào?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb,
        )
        return

    if action == "variant":
        await query.message.reply_text("✨ _Đang tạo A/B variant..._", parse_mode=ParseMode.MARKDOWN)
        from agents.post_actions import gen_variant
        variant_content = await gen_variant(post.get("content", ""), session)
        # Assign new ID
        existing = [k for k in session.content_outputs if k.startswith(f"{post_id}-V")]
        variant_id = f"{post_id}-V{len(existing)+1}"
        session.content_outputs[variant_id] = {
            **post,
            "content":   variant_content,
            "parent_id": post_id,
            "status":    "draft",
        }
        await save_session(session)
        from agents.post_actions import format_post_preview
        from bot.keyboards import post_action_keyboard
        await query.message.reply_text(
            f"✨ *Variant tạo thành công:* `{variant_id}`\n\n"
            + format_post_preview(variant_id, session.content_outputs[variant_id]),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=post_action_keyboard(variant_id),
        )
        return

    if action == "edit":
        # Set state chờ edit instruction
        session.pending_intake["_post_editing"] = post_id
        await save_session(session)
        await query.message.reply_text(
            f"✏️ *Edit `{post_id}`* — gõ yêu cầu chỉnh sửa:\n\n"
            "_Ví dụ: 'Viết hook mạnh hơn' / 'Thêm social proof' / 'Ngắn hơn 30%'_",
            parse_mode=ParseMode.MARKDOWN,
        )


async def _handle_adapt_channel_callback(query, session) -> None:
    """Xử lý adapt_<pid>_<channel> callback."""
    parts = query.data.split("_", 2)  # ["adapt", "001", "tiktok"]
    if len(parts) < 3:
        return
    pid_short = parts[1]
    channel   = parts[2]
    post_id   = f"POST-{pid_short}"
    post = session.content_outputs.get(post_id)
    if not post:
        await query.answer("Không tìm thấy bài.", show_alert=True)
        return

    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text(
        f"🔄 _Đang adapt `{post_id}` sang {channel.capitalize()}..._",
        parse_mode=ParseMode.MARKDOWN,
    )

    from agents.post_actions import adapt_post
    adapted = await adapt_post(post.get("content", ""), channel, session)

    adapted_id = f"{post_id}-{channel[:2].upper()}"
    session.content_outputs[adapted_id] = {
        **post,
        "content":   adapted,
        "channel":   channel,
        "parent_id": post_id,
        "status":    "draft",
    }
    # Track adapted versions on parent
    session.content_outputs[post_id].setdefault("adapted_versions", []).append(adapted_id)
    await save_session(session)

    from agents.post_actions import format_post_preview
    from bot.keyboards import post_action_keyboard
    await query.message.reply_text(
        f"✅ *Adapted: `{adapted_id}`* ({channel.capitalize()})\n\n"
        + format_post_preview(adapted_id, session.content_outputs[adapted_id]),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=post_action_keyboard(adapted_id),
    )
