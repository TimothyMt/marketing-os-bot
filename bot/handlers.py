"""
Telegram bot message and callback handlers.
All storage calls are async (Supabase REST).
Top-level handlers are wrapped with @safe_handler — exceptions become
user-friendly Vietnamese messages, full context logged for debugging.
"""
import asyncio
import logging
import re
from telegram import Update, Message
from telegram.ext import ContextTypes
from telegram.constants import ParseMode, ChatAction

from storage import get_session, save_session, reset_session
from storage.models import PipelineStage
from agents.pipeline import run_intake, run_targeted_pipeline
from agents.prompts import INTAKE_CONFIRM_TEMPLATE, PROGRESS_MESSAGES, TASK_OPENING_QUESTIONS
from frameworks.kpi_library import KPI_LIBRARY
from bot._error_handler import safe_handler
from bot._validators import validate_user_input, validate_task_type
from bot.keyboards import (
    TASK_SELECT_KEYBOARD,
    CONFIRM_KEYBOARD,
    RESTART_KEYBOARD,
    stage_done_keyboard,
    brand_select_keyboard,
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
    "full":       "Phân tích toàn diện (6 bước)",
    "market":     "Nghiên cứu thị trường",
    "competitor": "Phân tích đối thủ",
    "customer":   "Customer Insight & ICP",
    "pricing":    "Pricing Strategy",
    "social":     "Social Listening",
    "strategy":   "Marketing Strategy",
}

TASK_PIPELINE_STEPS = {
    "full":       "1️⃣ Thị trường · 2️⃣ Đối thủ · 3️⃣ Customer · 4️⃣ Psychology & Pricing · 5️⃣ Social · 6️⃣ Strategy",
    "market":     "📊 Phân tích TAM/SAM/SOM + market dynamics",
    "competitor": "🕵️ Landscape đối thủ + market gap analysis",
    "customer":   "👥 ICP profile + Jobs-to-be-Done + Customer Journey",
    "pricing":    "💰 Pricing model + psychology tactics + revenue optimization",
    "social":     "📡 Keyword clusters + monitoring routine + crisis thresholds",
    "strategy":   "🎯 SAVE Framework + SMART Goals + 90-day Roadmap",
}

TASK_STAGE_COUNT = {
    "full": 6,
    "market": 1,
    "competitor": 1,
    "customer": 1,
    "pricing": 1,
    "social": 1,
    "strategy": 1,
}

WELCOME_MESSAGE = """👋 Xin chào! Tôi là *Max — AI CMO* của bạn.

Tôi có thể giúp bạn:
📊 Nghiên cứu thị trường · 🕵️ Phân tích đối thủ · 👥 Customer Insight
💰 Pricing Strategy · 📡 Social Listening · 🎯 Marketing Strategy

─────────────────────────
*Bạn muốn Max làm gì hôm nay?*"""

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

@safe_handler
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await reset_session(user_id)
    session = await get_session(user_id)
    session.stage = PipelineStage.TASK_SELECT
    await save_session(session)
    await update.message.reply_text(
        WELCOME_MESSAGE,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=TASK_SELECT_KEYBOARD,
    )


@safe_handler
async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await reset_session(user_id)
    await update.message.reply_text(
        "✅ Đã xóa phiên cũ. Bắt đầu lại nhé!",
        reply_markup=RESTART_KEYBOARD,
    )


@safe_handler
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_MESSAGE, parse_mode=ParseMode.MARKDOWN)


# ─── Main message handler ─────────────────────────────────────────

@safe_handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    text, err = validate_user_input(update.message.text)
    if err is not None:
        await update.message.reply_text(err)
        return

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
        await _handle_intake(update, context, session, text)

    elif session.stage == PipelineStage.BRAND_SELECT:
        # User typed instead of picking from keyboard — treat as manual description
        session.stage = PipelineStage.INTAKE
        session.brand_candidates = []
        await save_session(session)
        await _handle_intake(update, context, session, text)

    elif session.stage == PipelineStage.GUIDED_INTAKE:
        await _handle_guided_text(update, session, text)

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


# ─── Brand identification helpers ────────────────────────────────

# Descriptive Vietnamese tokens that suggest a sentence, not a brand name.
# Tuned conservatively — false negatives (miss a brand) are cheaper than false
# positives (Tavily call wasted + worse UX).
_DESCRIPTIVE_TOKENS = frozenset({
    # Pronouns
    "tôi", "mình", "chúng", "anh", "chị", "em", "bạn",
    # Verbs / state
    "đang", "là", "sẽ", "đã", "có", "muốn", "cần", "làm", "giúp", "hỏi",
    # Business/service nouns
    "bán", "dịch", "vụ", "sản", "phẩm", "khách", "hàng", "shop", "cửa", "hiệu",
    # Numbers / units (revenue mentions)
    "triệu", "nghìn", "tỷ", "năm", "tháng",
    # Prepositions / conjunctions
    "về", "cho", "với", "trong", "và", "hoặc", "như",
    # Question / qualifier words
    "gì", "thế", "nào", "không", "ai",
    # Platform words (often part of descriptions)
    "app", "web", "site", "ứng", "dụng",
})


def _is_likely_brand_name(text: str, session) -> bool:
    """
    True when user's first intake message looks like just a brand name.
    Triggers an optional Tavily-backed brand lookup. False on uncertainty —
    matching too aggressively wastes Tavily quota and frustrates users who
    typed a real description.
    """
    if len(session.intake_history) > 0:
        return False

    cleaned = text.strip()
    if not cleaned:
        return False

    # Stricter length: real Vietnamese brand names rarely exceed 30 chars / 3 words.
    words = cleaned.split()
    if not (1 <= len(words) <= 3) or len(cleaned) > 30:
        return False

    # Must contain only letters/digits/dashes/apostrophes/spaces.
    # Rejects: emojis, punctuation that hints at sentences (".?!:,").
    for ch in cleaned:
        if ch.isalnum() or ch.isspace() or ch in "-'.":
            continue
        return False

    # Sentence-ending punctuation → definitely not a brand name.
    if cleaned.endswith(("?", "!", ".", ",")):
        return False

    # Any descriptive token disqualifies it.
    lower_words = {w.lower() for w in words}
    if lower_words & _DESCRIPTIVE_TOKENS:
        return False

    return True


async def _handle_brand_search(update, context, session, brand_name: str):
    """
    Search brand, show 1-4 candidates with confirm/select keyboard.
    On any failure (timeout, no results, error), fall back gracefully to normal
    intake — Tavily is an optimization, never required.
    """
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    from tools.search import search_brand_candidates

    status_msg = await update.message.reply_text(
        f"🔍 Đang tìm kiếm *{brand_name}*...",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        candidates = await search_brand_candidates(brand_name)
    except Exception as e:
        # search_brand_candidates already catches its own errors, but be defensive.
        logger.warning(
            "brand_search_unexpected_error",
            extra={"brand": brand_name, "error_type": type(e).__name__, "error": str(e)[:200]},
        )
        candidates = []

    if not candidates:
        # Could not auto-research → enter guided wizard. Keyboard taps are
        # lower-friction than typing 5 free-form answers, and "Khác" preserves
        # the open-ended escape hatch.
        from bot._guided_intake import start_guided_intake

        await status_msg.edit_text(
            f"😅 Xin lỗi bạn, tôi không tìm được thông tin về *{brand_name}* trên web.\n\n"
            f"Để phân tích cho bạn được chất lượng nhất, tôi hỏi vài câu nhanh — "
            f"bạn chọn nút bên dưới hoặc gõ tự do nhé.",
            parse_mode=ParseMode.MARKDOWN,
        )
        # Remember the brand name as the business_name for later.
        session.profile.business_name = brand_name
        await start_guided_intake(update.message, session)
        await save_session(session)
        return

    session.brand_candidates = candidates

    if len(candidates) == 1:
        c = candidates[0]
        desc = c.get("description", "")[:150]
        url_line = f"\n🌐 _{c['url']}_" if c.get("url") else ""
        await status_msg.edit_text(
            f"Tôi tìm thấy:\n\n"
            f"🏢 *{c['name']}*\n"
            f"{desc}{url_line}\n\n"
            f"Đây có phải brand của bạn không?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=brand_select_keyboard(candidates, single=True),
        )
    else:
        lines = [f"Tìm thấy *{len(candidates)} kết quả* cho _{brand_name}_. Brand của bạn là cái nào?\n"]
        for i, c in enumerate(candidates):
            desc = c.get("description", "")[:80]
            lines.append(f"{i+1}. *{c['name']}*\n_{desc}_\n")
        await status_msg.edit_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=brand_select_keyboard(candidates, single=False),
        )

    session.stage = PipelineStage.BRAND_SELECT
    await save_session(session)


async def _extract_profile_from_brand(session, chosen: dict):
    """Quick Claude call to infer industry + product_service from brand search result."""
    import anthropic, json, re
    from config import CLAUDE_MODEL, ANTHROPIC_API_KEY

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    try:
        resp = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content":
                f'Brand: {chosen.get("name", "")}\n'
                f'URL: {chosen.get("url", "")}\n'
                f'Description: {chosen.get("description", "")}\n\n'
                f'Trả về JSON: {{"industry": "(fnb/tech_saas/ecommerce/education/health_beauty/retail/b2b_service/real_estate)", '
                f'"product_service": "mô tả ngắn sản phẩm/dịch vụ", "target_customer": "khách hàng tiêu biểu"}}'
            }],
        )
        match = re.search(r'\{.*\}', resp.content[0].text, re.DOTALL)
        if match:
            data = json.loads(match.group())
            session.profile.industry        = data.get("industry") or "retail"
            session.profile.product_service = data.get("product_service") or chosen.get("description", "")[:200]
            session.profile.target_customer = data.get("target_customer") or "chưa xác định"
            return
    except Exception:
        pass
    # Fallback
    session.profile.industry        = "retail"
    session.profile.product_service = chosen.get("description", "")[:200] or chosen.get("name", "")
    session.profile.target_customer = "chưa xác định"


# ─── Intake ───────────────────────────────────────────────────────

async def _handle_intake(update, context, session, text):
    # Detect brand-name-only message → trigger brand search flow
    if _is_likely_brand_name(text, session):
        await _handle_brand_search(update, context, session, text)
        return

    from bot._heartbeat import with_heartbeat

    response, is_complete = await with_heartbeat(
        lambda: run_intake(session, text),
        update.message,
        context.bot,
    )
    await save_session(session)

    if is_complete:
        session.stage = PipelineStage.CONFIRMED
        await save_session(session)
        await _send_confirm_card(update.message, session)
    else:
        await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)


async def _send_confirm_card(message: Message, session) -> None:
    """Render the profile-summary + CONFIRM_KEYBOARD card. Reused by intake
    and guided-intake paths."""
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
        f"🌏 *Địa bàn*: {session.profile.location or 'Chưa xác định'}\n\n"
        f"─────────────────────────\n"
        f"*Task*: {task_label}\n"
        f"{steps_desc}\n\n"
        f"Bắt đầu nhé? 🚀"
    )
    await message.reply_text(
        confirm_msg,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=CONFIRM_KEYBOARD,
    )


# ─── Follow-up Q&A after analysis complete ───────────────────────

async def _handle_followup(update, context, session, text):
    from agents.pipeline import run_followup
    from bot._heartbeat import with_heartbeat

    answer = await with_heartbeat(
        lambda: run_followup(session, text),
        update.message,
        context.bot,
    )
    await send_long_message(
        update.message,
        answer,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=stage_done_keyboard(is_last=True),
    )


# ─── Callback (inline keyboard) ──────────────────────────────────

@safe_handler
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    session = await get_session(user_id)
    data = query.data

    # ── Brand pick ───────────────────────────────────────────────
    if data.startswith("brand_pick_"):
        # Guard: ignore double-click / stale callback after stage moved on.
        if session.stage != PipelineStage.BRAND_SELECT:
            await query.answer("Đã xử lý rồi nhé!", show_alert=False)
            return

        try:
            idx = int(data.split("_")[-1])
        except ValueError:
            await query.edit_message_text("Có lỗi xảy ra. Vui lòng /start lại nhé.")
            return

        candidates = session.brand_candidates or []
        if not (0 <= idx < len(candidates)):
            await query.edit_message_text("Có lỗi xảy ra. Vui lòng /start lại nhé.")
            return

        # Claim the transition immediately — second concurrent click hits the guard above.
        chosen = candidates[idx]
        session.profile.business_name = chosen.get("name", "")
        session.brand_candidates = []
        session.stage = PipelineStage.CONFIRMED
        await save_session(session)

        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"✅ *{chosen['name']}* — đã xác nhận!\n\n🔍 Đang thu thập thông tin để phân tích...",
            parse_mode=ParseMode.MARKDOWN,
        )
        await _extract_profile_from_brand(session, chosen)
        await save_session(session)
        await _run_pipeline_sequentially(query.message, session)
        return

    elif data == "brand_none":
        if session.stage != PipelineStage.BRAND_SELECT:
            await query.answer("Đã xử lý rồi nhé!", show_alert=False)
            return
        session.brand_candidates = []
        await save_session(session)

        from bot._guided_intake import start_guided_intake
        await query.edit_message_text(
            "Không sao! Tôi sẽ hỏi vài câu nhanh để hiểu business của bạn.\n\n"
            "Bạn chọn nút bên dưới hoặc gõ tự do nhé."
        )
        await start_guided_intake(query.message, session)
        await save_session(session)
        return

    # ── Guided intake wizard ─────────────────────────────────────
    if data.startswith("guided_"):
        await _handle_guided_callback(query, session, data)
        return

    # ── Task selection ────────────────────────────────────────────
    if data.startswith("task_"):
        task_type = data[5:]  # strip "task_" prefix

        if not validate_task_type(task_type):
            logger.warning(
                "invalid_task_type",
                extra={"user_id": user_id, "task_type": task_type},
            )
            await query.answer("❌ Task không hợp lệ", show_alert=True)
            return

        session.selected_task = task_type
        session.stage = PipelineStage.INTAKE
        await save_session(session)

        task_label = TASK_LABELS.get(task_type, "Phân tích")
        opening = TASK_OPENING_QUESTIONS.get(task_type, TASK_OPENING_QUESTIONS["full"])

        await query.edit_message_text(
            f"✅ *{task_label}*\n\n{opening}",
            parse_mode=ParseMode.MARKDOWN,
        )

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
        await query.edit_message_text(
            "✅ Đã reset! Bạn muốn Max làm gì hôm nay?",
            reply_markup=TASK_SELECT_KEYBOARD,
        )

    elif data == "ask_followup":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "💬 Bạn muốn hỏi thêm gì về kết quả phân tích? Cứ nhắn thẳng vào đây nhé!"
        )


# ─── Guided intake wizard handlers ───────────────────────────────

async def _handle_guided_callback(query, session, data: str) -> None:
    """
    Handle keyboard taps inside the guided wizard.
    Callback format: guided_<step>_<value>  (e.g. guided_industry_fnb)
    Special value "other" → wait for free-text input on the next message.
    """
    from bot._guided_intake import (
        advance_guided_step, mark_awaiting_other,
        INDUSTRY_LABELS, STAGE_LABELS, LOCATION_LABELS, GUIDED_STEP_KEY,
    )

    if session.stage != PipelineStage.GUIDED_INTAKE:
        await query.answer("Đã xử lý rồi nhé!", show_alert=False)
        return

    # Strip "guided_" prefix; "<step>_<value>" remains.
    rest = data[len("guided_"):]
    if "_" not in rest:
        await query.answer("Callback không hợp lệ", show_alert=True)
        return
    step, value = rest.split("_", 1)

    if step not in ("industry", "stage", "location"):
        await query.answer("Bước không hợp lệ", show_alert=True)
        return

    if value == "other":
        # Ask for free-text — stay on this step.
        mark_awaiting_other(session, step)
        await save_session(session)
        await query.edit_message_reply_markup(reply_markup=None)
        prompts = {
            "industry": "Ngành nghề của bạn là gì? (gõ vào nhé)",
            "stage": "Stage của business là gì? (gõ vào nhé)",
            "location": "Bạn hoạt động ở đâu? (gõ vào nhé)",
        }
        await query.message.reply_text(prompts[step])
        return

    # Persist the chosen value into the right profile field.
    label_map = {"industry": INDUSTRY_LABELS, "stage": STAGE_LABELS, "location": LOCATION_LABELS}
    label = label_map[step].get(value, value)
    if step == "industry":
        session.profile.industry = value
    elif step == "stage":
        session.profile.stage = value
    elif step == "location":
        session.profile.location = label

    await query.edit_message_text(f"✅ {label}")

    # Advance to next step, or finish the wizard.
    has_more = await advance_guided_step(query.message, session)
    if not has_more:
        session.stage = PipelineStage.CONFIRMED
        await save_session(session)
        await _send_confirm_card(query.message, session)
    else:
        await save_session(session)


async def _handle_guided_text(update: Update, session, text: str) -> None:
    """
    Handle free-text input during the guided wizard.
    - Steps `product` and `customer` always come here.
    - `industry`/`stage`/`location` come here only after user tapped "Khác".
    """
    from bot._guided_intake import (
        advance_guided_step, is_awaiting_text_for_step,
        GUIDED_STEP_KEY,
    )

    step = session.results.get(GUIDED_STEP_KEY)
    if not step:
        # Lost state — bail out cleanly back to normal intake.
        session.stage = PipelineStage.INTAKE
        await save_session(session)
        await update.message.reply_text(
            "Có vẻ phiên bị mất trạng thái. Bạn gõ /reset để bắt đầu lại nhé."
        )
        return

    # Persist into the right profile field.
    if step == "industry" and is_awaiting_text_for_step(session, "industry"):
        session.profile.industry = text[:60]
    elif step == "stage" and is_awaiting_text_for_step(session, "stage"):
        session.profile.stage = text[:60]
    elif step == "location" and is_awaiting_text_for_step(session, "location"):
        session.profile.location = text[:120]
    elif step == "product":
        session.profile.product_service = text[:500]
    elif step == "customer":
        session.profile.target_customer = text[:500]
    else:
        # User typed text on a keyboard step without tapping "Khác" first —
        # treat their text as the answer (forgiving UX).
        if step == "industry":
            session.profile.industry = text[:60]
        elif step == "stage":
            session.profile.stage = text[:60]
        elif step == "location":
            session.profile.location = text[:120]

    has_more = await advance_guided_step(update.message, session)
    if not has_more:
        session.stage = PipelineStage.CONFIRMED
        await save_session(session)
        await _send_confirm_card(update.message, session)
    else:
        await save_session(session)


# ─── Pipeline runner ─────────────────────────────────────────────

async def _run_pipeline_sequentially(message: Message, session):
    from bot._heartbeat import with_heartbeat

    task = session.selected_task or "full"
    task_label = TASK_LABELS.get(task, "Phân tích")
    total_stages = TASK_STAGE_COUNT.get(task, 1)

    if total_stages > 1:
        await message.reply_text(
            f"🚀 *Bắt đầu {task_label}!*\n\nTôi sẽ chạy {total_stages} bước và gửi kết quả từng bước.",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await message.reply_text(
            f"🚀 *Bắt đầu {task_label}...*",
            parse_mode=ParseMode.MARKDOWN,
        )

    stage_count = 0

    async def progress_cb(msg: str):
        await message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    bot = message.get_bot()
    iterator = run_targeted_pipeline(session, progress_callback=progress_cb).__aiter__()

    # Manual iteration so we can wrap each stage's wait in with_heartbeat —
    # users see typing + progress pings during the 30-120s gap per stage.
    while True:
        try:
            stage_key, result = await with_heartbeat(
                lambda: iterator.__anext__(),
                message,
                bot,
            )
        except StopAsyncIteration:
            break

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

    if stage_count > 0 and stage_count == total_stages:
        if total_stages > 1:
            await message.reply_text(
                "✅ *Hoàn thành phân tích!*\n\nBạn đã có đầy đủ:\n• Market Intelligence\n• Competitor Landscape\n• Customer Insights\n• Psychology & Pricing\n• Social Listening System\n• Marketing Strategy 90 ngày\n\nCó câu hỏi gì thêm không? Cứ nhắn thẳng vào đây nhé! 💬",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=stage_done_keyboard(is_last=True),
            )
        else:
            await message.reply_text(
                f"✅ *Hoàn thành {task_label}!*\n\nCó câu hỏi gì thêm không? Cứ nhắn thẳng vào đây nhé! 💬",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=stage_done_keyboard(is_last=True),
            )
