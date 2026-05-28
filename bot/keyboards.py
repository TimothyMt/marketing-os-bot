"""
Telegram inline keyboards for the bot.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ─────────────────────────────────────────────────────────────────
# MAIN MENU — Persona-based entry (6 active managers)
# ─────────────────────────────────────────────────────────────────

MAIN_MENU_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("✍️ Viết Content — full workflow", callback_data="task_write_content")],
    [InlineKeyboardButton("📊 Minh — Ads & Performance",   callback_data="persona_menu_digital_marketing")],
    [InlineKeyboardButton("🎨 Linh — Brand Voice",          callback_data="persona_menu_brand")],
    [InlineKeyboardButton("✍️ Nam — Content",               callback_data="persona_menu_content")],
    [InlineKeyboardButton("🎬 Trang — TikTok",              callback_data="persona_menu_tiktok")],
    [InlineKeyboardButton("🚀 Khoa — Growth & Retention",  callback_data="persona_menu_growth")],
    [InlineKeyboardButton("💬 Mai — CRM & Zalo",            callback_data="persona_menu_crm")],
])

TASK_SELECT_KEYBOARD = MAIN_MENU_KEYBOARD  # alias

# Sprint 1: Language preference setup (first-time)
LANG_LEVEL_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔴 Không rành — Toàn Việt",         callback_data="lang_none")],
    [InlineKeyboardButton("🟡 Hiểu cơ bản — Có giải thích",     callback_data="lang_moderate")],
    [InlineKeyboardButton("🟢 Thông thạo — EN tự nhiên",        callback_data="lang_fluent")],
])

# Sprint 2: Rating after skill execution (5 stars + skip)
RATING_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("⭐",         callback_data="rate_1"),
        InlineKeyboardButton("⭐⭐",        callback_data="rate_2"),
        InlineKeyboardButton("⭐⭐⭐",       callback_data="rate_3"),
        InlineKeyboardButton("⭐⭐⭐⭐",      callback_data="rate_4"),
        InlineKeyboardButton("⭐⭐⭐⭐⭐",     callback_data="rate_5"),
    ],
    [InlineKeyboardButton("⏭️ Bỏ qua đánh giá", callback_data="rate_skip")],
])

# Sprint 2: After rating ≤ 3 + user provided feedback — 2 buttons only
REGEN_PROMPT_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("✅ Chạy lại theo feedback", callback_data="regen_yes")],
    [InlineKeyboardButton("⏭️ Bỏ qua",                  callback_data="regen_no")],
])

# Sprint 2 v2: After rating ≤ 3 — trước khi user gõ feedback, cho skip luôn
FEEDBACK_PROMPT_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("⏭️ Bỏ qua, không feedback", callback_data="feedback_skip")],
])

# Sprint 4: Sau competitor analysis — hỏi user có muốn so sánh business sếp không
COMPARE_PROMPT_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🆚 So sánh business của sếp với đối thủ", callback_data="run_compare")],
    [InlineKeyboardButton("⏭️ Để sau",                                callback_data="skip_compare")],
])

# Sau khi Lịch Nội Dung xong — hỏi user có muốn sản xuất content luôn không
CALENDAR_TO_CONTENT_GEN_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("✍️ Sản xuất content luôn",      callback_data="run_content_gen_after_cal")],
    [InlineKeyboardButton("⏭️ Để sau — đánh giá lịch trước", callback_data="skip_content_gen_after_cal")],
])

# Sprint 5: Ads Generator — sau tier chooser, hỏi format (Video hay Ảnh)
ADS_FORMAT_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🎥 Video",     callback_data="ads_format_video")],
    [InlineKeyboardButton("🖼️ Ảnh tĩnh",  callback_data="ads_format_image")],
])



# ─────────────────────────────────────────────────────────────────
# Confirmation + flow control
# ─────────────────────────────────────────────────────────────────

CONFIRM_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("✅ Đúng rồi, bắt đầu!", callback_data="confirm_yes"),
        InlineKeyboardButton("✏️ Sửa thông tin",       callback_data="confirm_no"),
    ]
])

RESTART_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔄 Bắt đầu phân tích mới", callback_data="restart")],
])


# ─────────────────────────────────────────────────────────────────
# ACTION KEYBOARD — sau khi bất kỳ skill nào xong
# ─────────────────────────────────────────────────────────────────

ACTION_AFTER_SKILL = InlineKeyboardMarkup([
    [InlineKeyboardButton("🏠 Về menu chính",            callback_data="menu_main")],
    [InlineKeyboardButton("❓ Hỏi thêm về output này",  callback_data="ask_followup")],
])

# Aliases for backward compat (old callback_data "menu_strategic" / "menu_operational" still route to menu_main)
ACTION_AFTER_STRATEGIC = ACTION_AFTER_SKILL
ACTION_AFTER_OPS       = ACTION_AFTER_SKILL
ACTION_AFTER_ANALYSIS  = ACTION_AFTER_SKILL

# Q&A follow-up — sau khi user hỏi thêm 1 lần, có thể hỏi tiếp hoặc thoát
ASK_FOLLOWUP_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("💬 Hỏi tiếp",              callback_data="ask_followup")],
    [InlineKeyboardButton("✅ Đủ rồi, về menu",        callback_data="menu_main")],
])


def get_action_keyboard(task_name: str) -> InlineKeyboardMarkup:
    """Return post-skill action keyboard."""
    return ACTION_AFTER_SKILL


def stage_done_keyboard(is_last: bool = False, task_name: str | None = None) -> InlineKeyboardMarkup:
    """Keyboard sau mỗi stage. is_last=True → action keyboard, else continue button."""
    if is_last:
        return ACTION_AFTER_SKILL
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Chạy bước tiếp theo", callback_data="continue_pipeline")],
    ])


# ─────────────────────────────────────────────────────────────────
# Variant choosers — for special ops skills
# ─────────────────────────────────────────────────────────────────

# Ads Copy: user picks which tier(s) to generate
ADS_COPY_TIER_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🌐 TOFU (Tệp lạnh)",    callback_data="ads_tier_tofu"),
        InlineKeyboardButton("🌡️ MOFU (Tệp ấm)",      callback_data="ads_tier_mofu"),
    ],
    [
        InlineKeyboardButton("🔥 BOFU (Tệp nóng)",   callback_data="ads_tier_bofu"),
        InlineKeyboardButton("⚡ Full 3 tầng",        callback_data="ads_tier_all"),
    ],
])

# Video Scripts: user picks creator type
VIDEO_CREATOR_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("👥 UGC (Khách thật)",    callback_data="video_creator_ugc"),
        InlineKeyboardButton("👤 EGC (Nhân viên)",     callback_data="video_creator_egc"),
    ],
    [
        InlineKeyboardButton("🎤 FGC (Founder)",       callback_data="video_creator_fgc"),
        InlineKeyboardButton("⭐ KOL/KOC (Paid)",      callback_data="video_creator_kol"),
    ],
])


# ─────────────────────────────────────────────────────────────────
# Strategy gating — skill cần Strategy base nhưng chưa có
# ─────────────────────────────────────────────────────────────────

NEEDS_STRATEGY_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("✅ Chạy A→Z, rồi quay lại task này", callback_data="run_az_then_back")],
    [InlineKeyboardButton("⏭️ Quay lại menu",                  callback_data="menu_main")],
])

# Sprint 5: Lazy Brand Voice setup prompt (creative ops skills)
BRAND_VOICE_PROMPT_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("✅ Setup Brand Voice ngay",          callback_data="bv_setup_now")],
    [InlineKeyboardButton("⏭️ Bỏ qua, chạy luôn skill này",     callback_data="bv_skip_for_now")],
    [InlineKeyboardButton("🔙 Quay lại menu",                   callback_data="menu_main")],
])

# Sau khi A→Z xong — hỏi có muốn triển khai campaign ngay không
POST_AZ_CAMPAIGN_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("💡 Tôi đã có ý tưởng campaign",      callback_data="az_have_idea")],
    [InlineKeyboardButton("🔍 Max đề xuất campaign phù hợp",   callback_data="az_propose_campaign")],
    [InlineKeyboardButton("⏭️ Đánh giá output trước, làm sau", callback_data="az_skip_campaign")],
])

# Sau khi Max đề xuất 3 options — user chọn 1 trong 3
CAMPAIGN_OPTION_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("1️⃣", callback_data="campaign_pick_1"),
        InlineKeyboardButton("2️⃣", callback_data="campaign_pick_2"),
        InlineKeyboardButton("3️⃣", callback_data="campaign_pick_3"),
    ],
    [InlineKeyboardButton("🔄 Đề xuất 3 options khác", callback_data="campaign_propose_again")],
    [InlineKeyboardButton("⏭️ Quay lại, đánh giá A→Z", callback_data="az_skip_campaign")],
])

# Sau khi refine idea của user — confirm proceed hay sửa lại
CAMPAIGN_IDEA_CONFIRM_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("✅ OK, chọn Offer Lever",        callback_data="campaign_idea_confirm")],
    [InlineKeyboardButton("✏️ Sửa lại idea",                callback_data="campaign_idea_redo")],
    [InlineKeyboardButton("⏭️ Hủy, quay lại đánh giá",     callback_data="az_skip_campaign")],
])

# Sau khi chốt campaign → AI gen 4 offer levers → user pick 1
OFFER_LEVER_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("1️⃣", callback_data="lever_pick_0"),
        InlineKeyboardButton("2️⃣", callback_data="lever_pick_1"),
        InlineKeyboardButton("3️⃣", callback_data="lever_pick_2"),
        InlineKeyboardButton("4️⃣", callback_data="lever_pick_3"),
    ],
    [InlineKeyboardButton("🔄 Đề xuất 4 levers khác", callback_data="lever_propose_again")],
    [InlineKeyboardButton("⏭️ Hủy, quay lại đánh giá", callback_data="az_skip_campaign")],
])


