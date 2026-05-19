"""
Telegram inline keyboards for the bot.
Multi-tier menu: Main → Chiến lược / Sản xuất / Đánh giá.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ─────────────────────────────────────────────────────────────────
# MAIN MENU — Tier 1 (categories)
# ─────────────────────────────────────────────────────────────────

MAIN_MENU_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🎯 Chiến lược (Strategic)",        callback_data="menu_strategic")],
    [InlineKeyboardButton("⚙️ Sản xuất (Operational)",        callback_data="menu_operational")],
    [InlineKeyboardButton("📊 Đánh giá (Analysis)",            callback_data="menu_analysis")],
    [InlineKeyboardButton("🔍 Phân tích toàn diện (Full)",     callback_data="task_full")],
])


# ─────────────────────────────────────────────────────────────────
# STRATEGIC MENU — Tier 2
# ─────────────────────────────────────────────────────────────────

STRATEGIC_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("📊 Nghiên cứu thị trường", callback_data="task_market"),
        InlineKeyboardButton("🕵️ Phân tích đối thủ",     callback_data="task_competitor"),
    ],
    [
        InlineKeyboardButton("👥 Customer Insight",       callback_data="task_customer"),
        InlineKeyboardButton("💰 Pricing Strategy",       callback_data="task_pricing"),
    ],
    [InlineKeyboardButton("🎯 Marketing Strategy",        callback_data="task_strategy")],
    [InlineKeyboardButton("← Quay lại menu chính",        callback_data="menu_main")],
])


# ─────────────────────────────────────────────────────────────────
# OPERATIONAL MENU — Tier 2 (8 skills, grouped by purpose)
# ─────────────────────────────────────────────────────────────────

OPERATIONAL_KEYBOARD = InlineKeyboardMarkup([
    # Planning cluster
    [
        InlineKeyboardButton("📋 Campaign Brief",         callback_data="task_campaign_brief"),
        InlineKeyboardButton("📅 Content Calendar",       callback_data="task_content_calendar"),
    ],
    # Production cluster
    [
        InlineKeyboardButton("✍️ Ads Copy",               callback_data="task_ads_copy"),
        InlineKeyboardButton("🎬 Video Scripts",          callback_data="task_video_scripts"),
    ],
    [
        InlineKeyboardButton("🌐 Landing Page",           callback_data="task_landing_page"),
        InlineKeyboardButton("💬 Sales/Inbox Script",     callback_data="task_sales_inbox_script"),
    ],
    [InlineKeyboardButton("📧 Email/Zalo Nurture",         callback_data="task_email_zalo_sequence")],
    [InlineKeyboardButton("← Quay lại menu chính",         callback_data="menu_main")],
])


# ─────────────────────────────────────────────────────────────────
# ANALYSIS MENU — Tier 2
# ─────────────────────────────────────────────────────────────────

ANALYSIS_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("📈 Performance Audit",          callback_data="task_performance_audit")],
    [InlineKeyboardButton("← Quay lại menu chính",         callback_data="menu_main")],
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


def stage_done_keyboard(is_last: bool = False) -> InlineKeyboardMarkup:
    if is_last:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Phân tích business mới", callback_data="restart")],
            [InlineKeyboardButton("❓ Hỏi thêm về strategy",   callback_data="ask_followup")],
        ])
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
# Legacy — keep for backward compat (callbacks still work)
# ─────────────────────────────────────────────────────────────────

TASK_SELECT_KEYBOARD = MAIN_MENU_KEYBOARD  # alias for old code
