"""
Telegram inline keyboards for the bot.
Multi-tier menu: Main → Chiến lược / Sản xuất / Đánh giá.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ─────────────────────────────────────────────────────────────────
# MAIN MENU — Tier 1 (categories)
# ─────────────────────────────────────────────────────────────────

MAIN_MENU_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🎯 Chiến Lược",       callback_data="menu_strategic")],
    [InlineKeyboardButton("⚙️ Sản Xuất",         callback_data="menu_operational")],
    [InlineKeyboardButton("📊 Theo Dõi & Báo Cáo", callback_data="menu_analysis")],
    [InlineKeyboardButton("🔍 Trọn Bộ (A → Z)",  callback_data="task_full")],
])

# Sprint 1: Language preference setup (first-time)
LANG_LEVEL_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔴 Không rành — Toàn Việt",         callback_data="lang_none")],
    [InlineKeyboardButton("🟡 Hiểu cơ bản — Có giải thích",     callback_data="lang_moderate")],
    [InlineKeyboardButton("🟢 Thông thạo — EN tự nhiên",        callback_data="lang_fluent")],
])

# Sprint 2: Rating after skill execution
RATING_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("⭐", callback_data="rate_1"),
        InlineKeyboardButton("⭐⭐", callback_data="rate_2"),
        InlineKeyboardButton("⭐⭐⭐", callback_data="rate_3"),
        InlineKeyboardButton("⭐⭐⭐⭐", callback_data="rate_4"),
        InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data="rate_5"),
    ]
])

# Sprint 2: After rating ≤ 3 + user provided feedback, ask if regen
REGEN_PROMPT_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("✅ Có, chạy lại ngay theo feedback", callback_data="regen_yes")],
    [InlineKeyboardButton("⏭️ Không cần, để admin review",      callback_data="regen_no")],
])

# Sprint 4: Sau competitor analysis — hỏi user có muốn so sánh business sếp không
COMPARE_PROMPT_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🆚 So sánh business của sếp với đối thủ", callback_data="run_compare")],
    [InlineKeyboardButton("⏭️ Để sau",                                callback_data="skip_compare")],
])

# Sprint 5: Ads Generator — sau tier chooser, hỏi format (Video hay Ảnh)
ADS_FORMAT_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🎥 Video",     callback_data="ads_format_video")],
    [InlineKeyboardButton("🖼️ Ảnh tĩnh",  callback_data="ads_format_image")],
])

# Sprint 5: Sau khi Ads Generator output brief ảnh — hỏi có gen ảnh thật luôn không
IMAGE_GEN_PROMPT_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🎨 Tạo 1 ảnh test (~$0.04)",    callback_data="img_gen_1")],
    [InlineKeyboardButton("🎨 Tạo 3 variants (~$0.12)",     callback_data="img_gen_3")],
    [InlineKeyboardButton("⏭️ Chỉ brief, không gen ảnh",   callback_data="img_gen_skip")],
])

# Sprint 5: Chọn size ảnh
IMAGE_SIZE_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("📱 Vertical (Story/Reels) 1024×1536", callback_data="img_size_vertical")],
    [InlineKeyboardButton("🖼️ Square (Feed) 1024×1024",          callback_data="img_size_square")],
    [InlineKeyboardButton("🖥️ Horizontal (Landscape) 1536×1024", callback_data="img_size_horizontal")],
])


# ─────────────────────────────────────────────────────────────────
# STRATEGIC MENU — Tier 2
# ─────────────────────────────────────────────────────────────────

STRATEGIC_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("📊 Tìm Hiểu Thị Trường", callback_data="task_market"),
        InlineKeyboardButton("🕵️ Phân Tích Đối Thủ",   callback_data="task_competitor"),
    ],
    [
        InlineKeyboardButton("👥 Insight Khách Hàng", callback_data="task_customer"),
        InlineKeyboardButton("💰 Chiến Lược Giá",     callback_data="task_pricing"),
    ],
    [InlineKeyboardButton("🎯 Lập Kế Hoạch Tổng",     callback_data="task_strategy")],
    [InlineKeyboardButton("← Quay lại",                callback_data="menu_main")],
])


# ─────────────────────────────────────────────────────────────────
# OPERATIONAL MENU — Tier 2 (8 skills, grouped by purpose)
# ─────────────────────────────────────────────────────────────────

OPERATIONAL_KEYBOARD = InlineKeyboardMarkup([
    # Planning cluster
    [
        InlineKeyboardButton("📋 Viết Brief Campaign",  callback_data="task_campaign_brief"),
        InlineKeyboardButton("📅 Lịch Nội Dung",        callback_data="task_content_calendar"),
    ],
    # Production cluster
    [
        InlineKeyboardButton("✍️ Sản Xuất Nội Dung",    callback_data="task_content_generator"),
        InlineKeyboardButton("📢 Sản Xuất Nội Dung Ads", callback_data="task_ads_generator"),
    ],
    [
        InlineKeyboardButton("🎬 Viết Kịch Bản Video", callback_data="task_video_scripts"),
        InlineKeyboardButton("🌐 Thiết Kế Website",    callback_data="task_landing_page"),
    ],
    [
        InlineKeyboardButton("💬 Kịch Bản Sales",      callback_data="task_sales_inbox_script"),
        InlineKeyboardButton("📧 Chăm Sóc Khách Hàng", callback_data="task_email_zalo_sequence"),
    ],
    [InlineKeyboardButton("← Quay lại",                callback_data="menu_main")],
])


# ─────────────────────────────────────────────────────────────────
# ANALYSIS MENU — Tier 2
# ─────────────────────────────────────────────────────────────────

ANALYSIS_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔍 Theo Dõi Đối Thủ",      callback_data="task_competitor_spy")],
    [InlineKeyboardButton("📊 Báo Cáo Ads",            callback_data="task_performance_audit")],
    [InlineKeyboardButton("← Quay lại",                callback_data="menu_main")],
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
