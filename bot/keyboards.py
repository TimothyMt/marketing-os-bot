"""
Telegram inline keyboards for the bot.
Multi-tier menu: Main → Chiến lược / Sản xuất / Đánh giá.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ─────────────────────────────────────────────────────────────────
# MAIN MENU — Tier 1 (categories)
# ─────────────────────────────────────────────────────────────────

MAIN_MENU_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🎯 Chiến Lược",         callback_data="menu_strategic")],
    [InlineKeyboardButton("⚙️ Sản Xuất",           callback_data="menu_operational")],
    [InlineKeyboardButton("📊 Theo Dõi & Báo Cáo", callback_data="menu_analysis")],
])

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

# Sprint 5: Ads Generator — sau tier chooser, hỏi format (Video hay Ảnh)
ADS_FORMAT_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🎥 Video",     callback_data="ads_format_video")],
    [InlineKeyboardButton("🖼️ Ảnh tĩnh",  callback_data="ads_format_image")],
])

# Sprint 5 v2: Sau copy xong (format=image) — hỏi có upload ảnh mẫu không
IMAGE_REFERENCE_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("📤 Upload ảnh mẫu",          callback_data="img_ref_upload")],
    [InlineKeyboardButton("🎨 Tự gen theo brief",       callback_data="img_ref_skip")],
    [InlineKeyboardButton("⏭️ Chỉ lấy copy, không gen", callback_data="img_ref_no_gen")],
])

# Sprint 5 v2: Hỏi số lượng ảnh (bỏ cost display)
IMAGE_GEN_PROMPT_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🎨 Tạo 1 ảnh",        callback_data="img_gen_1")],
    [InlineKeyboardButton("🎨 Tạo 3 variants",   callback_data="img_gen_3")],
    [InlineKeyboardButton("⏭️ Bỏ qua",           callback_data="img_gen_skip")],
])

# Sprint 5: Chọn size ảnh
IMAGE_SIZE_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("📱 Vertical (Story/Reels)",  callback_data="img_size_vertical")],
    [InlineKeyboardButton("🖼️ Square (Feed)",            callback_data="img_size_square")],
    [InlineKeyboardButton("🖥️ Horizontal (Landscape)",  callback_data="img_size_horizontal")],
])

# Sprint 5 v2: Sau khi gen ảnh xong — Sửa hoặc Chốt
IMAGE_REVIEW_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("✏️ Sửa ảnh này",          callback_data="img_edit")],
    [InlineKeyboardButton("✅ Chốt ảnh này",          callback_data="img_confirm")],
    [InlineKeyboardButton("🔁 Gen ảnh khác",          callback_data="img_regen")],
])


# ─────────────────────────────────────────────────────────────────
# STRATEGIC MENU — Tier 2 (5 single + 1 A→Z full)
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
    [InlineKeyboardButton("🎯 Lập Kế Hoạch Tổng", callback_data="task_strategy")],
    [InlineKeyboardButton("🔍 Phân Tích Tổng Hợp A→Z (5 bước)", callback_data="task_full")],
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
    [InlineKeyboardButton("🎥 Phân Tích Video Viral", callback_data="task_viral_video_analyzer")],
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


# ─────────────────────────────────────────────────────────────────
# ACTION KEYBOARDS — sau khi 1 skill xong, split theo category
# ─────────────────────────────────────────────────────────────────

# Strategic skill done → suggest chuyển sang Ops
ACTION_AFTER_STRATEGIC = InlineKeyboardMarkup([
    [InlineKeyboardButton("⚡ Chuyển sang Sản Xuất",     callback_data="menu_operational")],
    [InlineKeyboardButton("⚙️ Chọn Strategic khác",     callback_data="menu_strategic")],
    [InlineKeyboardButton("❓ Hỏi thêm về output này",  callback_data="ask_followup")],
])

# Operational skill done → suggest quay về Strategic
ACTION_AFTER_OPS = InlineKeyboardMarkup([
    [InlineKeyboardButton("🎯 Quay lại Chiến Lược",     callback_data="menu_strategic")],
    [InlineKeyboardButton("⚙️ Chọn Ops khác",           callback_data="menu_operational")],
    [InlineKeyboardButton("❓ Hỏi thêm về output này",  callback_data="ask_followup")],
])

# Analysis skill done → about menu chính
ACTION_AFTER_ANALYSIS = InlineKeyboardMarkup([
    [InlineKeyboardButton("⚙️ Chọn task khác",          callback_data="menu_main")],
    [InlineKeyboardButton("❓ Hỏi thêm về output này",  callback_data="ask_followup")],
])

# Q&A follow-up — sau khi user hỏi thêm 1 lần, có thể hỏi tiếp hoặc thoát
ASK_FOLLOWUP_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("💬 Hỏi tiếp",              callback_data="ask_followup")],
    [InlineKeyboardButton("✅ Đủ rồi, về menu",        callback_data="menu_main")],
])


def get_action_keyboard(task_name: str) -> InlineKeyboardMarkup:
    """Pick action keyboard dựa trên category của skill vừa xong."""
    from agents.task_registry import OPERATIONAL_TASKS, STRATEGIC_TASKS
    SINGLE_SHOT_STRATEGIC = {"market", "competitor", "customer", "pricing", "strategy", "full"}
    ANALYSIS_TASKS = {"competitor_spy", "performance_audit", "viral_video_analyzer"}

    if task_name in ANALYSIS_TASKS:
        return ACTION_AFTER_ANALYSIS
    if task_name in OPERATIONAL_TASKS and task_name not in ANALYSIS_TASKS:
        return ACTION_AFTER_OPS
    if task_name in SINGLE_SHOT_STRATEGIC or task_name in STRATEGIC_TASKS:
        return ACTION_AFTER_STRATEGIC
    # Fallback
    return ACTION_AFTER_OPS


def stage_done_keyboard(is_last: bool = False, task_name: str | None = None) -> InlineKeyboardMarkup:
    """Keyboard sau mỗi stage. is_last=True → action keyboard, else continue button.

    Note: When is_last=True, prefer get_action_keyboard(task_name) directly.
    This function kept for backward compat.
    """
    if is_last:
        if task_name:
            return get_action_keyboard(task_name)
        # Fallback
        return ACTION_AFTER_OPS
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


# ─────────────────────────────────────────────────────────────────
# Auto monitor — interval picker
# ─────────────────────────────────────────────────────────────────

MONITOR_PROMPT_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔔 Có, theo dõi tự động",  callback_data="monitor_yes")],
    [InlineKeyboardButton("⏭️ Không cần",              callback_data="monitor_no")],
])

MONITOR_INTERVAL_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("⚡ 3 giờ",   callback_data="monitor_iv_3"),
        InlineKeyboardButton("🕐 6 giờ",   callback_data="monitor_iv_6"),
    ],
    [
        InlineKeyboardButton("🕔 12 giờ",  callback_data="monitor_iv_12"),
        InlineKeyboardButton("📅 1 ngày",  callback_data="monitor_iv_24"),
    ],
    [InlineKeyboardButton("📆 1 tuần",     callback_data="monitor_iv_168")],
])

# Note: New-ads notification keyboard được build động trong worker
# (workers/monitor_competitors.py:55-60) với callback_data="monitor_diff_{page_id}"
# vì cần inject page_id. Không define keyboard tĩnh ở đây.


# ─────────────────────────────────────────────────────────────────
# Legacy — keep for backward compat (callbacks still work)
# ─────────────────────────────────────────────────────────────────

TASK_SELECT_KEYBOARD = MAIN_MENU_KEYBOARD  # alias for old code
