"""
Guided intake wizard — used when brand auto-research (Tavily) fails.

5 sequential steps fill BusinessProfile via keyboard taps + text fallback:
  1. industry  (keyboard, 8 options + Khác)
  2. stage     (keyboard, 4 options + Khác)
  3. product_service  (free text — too open to enumerate)
  4. target_customer  (free text)
  5. location  (keyboard, 5 common + Khác)

State is tracked in session.results["_guided_step"] to avoid adding columns.
Each step persists the chosen value into session.profile immediately so a
restart doesn't lose progress.
"""
from telegram import Message
from telegram.constants import ParseMode

from storage.models import Session, PipelineStage
from bot.keyboards import INDUSTRY_KEYBOARD, STAGE_KEYBOARD, LOCATION_KEYBOARD


GUIDED_STEP_KEY = "_guided_step"
GUIDED_AWAIT_OTHER_KEY = "_guided_await_other"  # which step is waiting for text input
STEPS = ("industry", "stage", "product", "customer", "location")


# Human-readable labels for "I picked option X" confirmations.
INDUSTRY_LABELS = {
    "fnb": "F&B (ăn uống, nhà hàng, café)",
    "tech_saas": "Tech / SaaS",
    "ecommerce": "E-commerce",
    "education": "Education",
    "health_beauty": "Health & Beauty",
    "retail": "Retail (bán lẻ)",
    "b2b_service": "B2B Service",
    "real_estate": "Real Estate",
}

STAGE_LABELS = {
    "idea": "Idea (chưa launch)",
    "mvp": "MVP (đã có sản phẩm, đang test)",
    "growth": "Growth (đang scale)",
    "scale": "Scale (đã ổn định, mở rộng)",
}

LOCATION_LABELS = {
    "hcm": "TP. Hồ Chí Minh",
    "hanoi": "Hà Nội",
    "danang": "Đà Nẵng",
    "tourist": "Phú Quốc / Khu du lịch",
    "nationwide": "Toàn quốc / Online",
}


# Prompt sent at the start of each step.
STEP_PROMPTS = {
    "industry": (
        "*Bước 1/5: Ngành nghề*\n\n"
        "Business của bạn thuộc ngành nào? Chọn nhanh ở dưới hoặc gõ vào nếu khác:"
    ),
    "stage": (
        "*Bước 2/5: Giai đoạn*\n\n"
        "Business đang ở giai đoạn nào?"
    ),
    "product": (
        "*Bước 3/5: Sản phẩm / dịch vụ*\n\n"
        "Mô tả ngắn sản phẩm/dịch vụ chính nhé.\n\n"
        "_Ví dụ: \"Khóa học tiếng Anh online cho người đi làm\" hoặc "
        "\"Quán phở take-away, có giao tận nơi\"._"
    ),
    "customer": (
        "*Bước 4/5: Khách hàng mục tiêu*\n\n"
        "Ai là người mua chính?\n\n"
        "_Ví dụ: \"Nhân viên văn phòng 25-35 tuổi, thu nhập 15-30tr\" hoặc "
        "\"Mẹ bỉm sữa ở thành phố, con dưới 3 tuổi\"._"
    ),
    "location": (
        "*Bước 5/5: Địa bàn hoạt động*\n\n"
        "Bán ở đâu? Chọn nhanh hoặc gõ vào nếu khác:"
    ),
}


def _keyboard_for(step: str):
    """Return the inline keyboard for a step, or None for free-text steps."""
    if step == "industry":
        return INDUSTRY_KEYBOARD
    if step == "stage":
        return STAGE_KEYBOARD
    if step == "location":
        return LOCATION_KEYBOARD
    return None


async def start_guided_intake(message: Message, session: Session) -> None:
    """Enter the wizard at step 1. Caller has already set session.stage."""
    session.results[GUIDED_STEP_KEY] = "industry"
    session.results.pop(GUIDED_AWAIT_OTHER_KEY, None)
    session.stage = PipelineStage.GUIDED_INTAKE
    await message.reply_text(
        STEP_PROMPTS["industry"],
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=INDUSTRY_KEYBOARD,
    )


async def advance_guided_step(message: Message, session: Session) -> bool:
    """
    Move to the next step. Returns True if there's still a next step;
    False once all 5 are done (caller should produce the confirm card).
    """
    current = session.results.get(GUIDED_STEP_KEY, "industry")
    try:
        next_idx = STEPS.index(current) + 1
    except ValueError:
        next_idx = 0  # Defensive: corrupt state — restart wizard.

    if next_idx >= len(STEPS):
        # Wizard complete.
        session.results.pop(GUIDED_STEP_KEY, None)
        session.results.pop(GUIDED_AWAIT_OTHER_KEY, None)
        return False

    next_step = STEPS[next_idx]
    session.results[GUIDED_STEP_KEY] = next_step
    session.results.pop(GUIDED_AWAIT_OTHER_KEY, None)
    await message.reply_text(
        STEP_PROMPTS[next_step],
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_keyboard_for(next_step),
    )
    return True


def is_awaiting_text_for_step(session: Session, step: str) -> bool:
    """True if user tapped 'Khác' on `step` and we're waiting for their text."""
    return session.results.get(GUIDED_AWAIT_OTHER_KEY) == step


def mark_awaiting_other(session: Session, step: str) -> None:
    session.results[GUIDED_AWAIT_OTHER_KEY] = step
