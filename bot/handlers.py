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
    ADS_COPY_TIER_KEYBOARD,
    VIDEO_CREATOR_KEYBOARD,
    LANG_LEVEL_KEYBOARD,
    RATING_KEYBOARD,
    REGEN_PROMPT_KEYBOARD,
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

/start — Bắt đầu phân tích business mới
/reset — Xóa phiên hiện tại, bắt đầu lại
/help  — Hiển thị hướng dẫn này

*Cách sử dụng*:
1. Chọn task bạn muốn Max thực hiện
2. Trả lời câu hỏi để Max nắm bức tranh business
3. Xác nhận thông tin → Max chạy phân tích
4. Nhận kết quả chuyên sâu

*Thời gian*: 30-60 giây cho task đơn lẻ, 3-5 phút cho phân tích toàn diện."""


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
    user_id = update.effective_user.id

    # PRESERVE preferences từ session cũ (vd: en_level đã set trước)
    old_session = await get_session(user_id)
    preserved_prefs = dict(old_session.preferences) if old_session.preferences else {}

    await reset_session(user_id)
    session = await get_session(user_id)
    session.preferences = preserved_prefs
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

    # Returning user → vào menu chính ngay
    await update.message.reply_text(
        WELCOME_MESSAGE,
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
    user_id = update.effective_user.id
    await reset_session(user_id)
    await update.message.reply_text(
        "✅ Đã xóa phiên cũ. Bắt đầu lại nhé!",
        reply_markup=RESTART_KEYBOARD,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_MESSAGE, parse_mode=ParseMode.MARKDOWN)


# ─── Main message handler ─────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    session = await get_session(user_id)

    if session.stage in (PipelineStage.IDLE, PipelineStage.TASK_SELECT):
        # User typed instead of using the keyboard — show task menu
        session.stage = PipelineStage.TASK_SELECT
        await save_session(session)
        await update.message.reply_text(
            "Chọn task bạn muốn Max thực hiện nhé 👇",
            reply_markup=TASK_SELECT_KEYBOARD,
        )

    elif session.stage == PipelineStage.INTAKE:
        # Route to ops single-shot intake if marker present, else strategic multi-turn
        if session.pending_intake.get(OPS_INTAKE_AWAITING):
            await _handle_ops_intake_reply(update, context, session, text)
        else:
            await _handle_intake(update, context, session, text)

    elif session.stage == PipelineStage.CONFIRMED:
        await update.message.reply_text(
            "Nhấn *Đúng rồi, bắt đầu!* để tôi chạy phân tích nhé! Hoặc /reset để bắt đầu lại.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=CONFIRM_KEYBOARD,
        )

    elif session.stage == PipelineStage.COMPLETE:
        await _handle_followup(update, context, session, text)

    else:
        await update.message.reply_text(
            "⏳ Đang phân tích... Vui lòng chờ tôi hoàn thành nhé."
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
        await query.edit_message_text(
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
        await _send_single_shot_form(query.message, session, "ads_copy")
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

        # Operational skills → single-shot form (or variant chooser first)
        if task_type in OPERATIONAL_TASKS:
            await query.edit_message_reply_markup(reply_markup=None)

            # Special skills with variant chooser
            if task_type == "ads_copy":
                await query.message.reply_text(
                    "✍️ *Ads Copy* — Bạn muốn gen tier nào trước?",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=ADS_COPY_TIER_KEYBOARD,
                )
                return
            if task_type == "video_scripts":
                await query.message.reply_text(
                    "🎬 *Video Scripts* — Brief cho loại creator nào?",
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

    elif data == "ask_followup":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "💬 Bạn muốn hỏi thêm gì về kết quả phân tích? Cứ nhắn thẳng vào đây nhé!"
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

    # Final action keyboard
    await message.reply_text(
        f"✅ *Hoàn thành {task.label}!*\n\nChạy task khác hoặc hỏi thêm?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=stage_done_keyboard(is_last=True),
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
            reply_markup=stage_done_keyboard(is_last=is_last) if is_last else None,
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
                "⚠️ Không generate được file HTML — phần tóm tắt ở trên đã đủ. Bạn có thể hỏi thêm tự do."
            )

    if stage_count > 0 and stage_count == total_stages:
        if total_stages > 1:
            await message.reply_text(
                "✅ *Hoàn thành phân tích!*\n\nMở file HTML để xem báo cáo đầy đủ.\nCó câu hỏi gì thêm? Nhắn thẳng vào đây nhé! 💬",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=stage_done_keyboard(is_last=True),
            )
        else:
            await message.reply_text(
                f"✅ *Hoàn thành {task_label}!*\n\nMở file HTML để xem báo cáo đẹp hơn.\nCó câu hỏi gì thêm? 💬",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=stage_done_keyboard(is_last=True),
            )


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
