"""
Telegram inline keyboards for the bot.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ── Task selection — hiện ngay sau welcome ────────────────────────
TASK_SELECT_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔍 Phân tích toàn diện",      callback_data="task_full")],
    [
        InlineKeyboardButton("📊 Nghiên cứu thị trường", callback_data="task_market"),
        InlineKeyboardButton("🕵️ Phân tích đối thủ",     callback_data="task_competitor"),
    ],
    [
        InlineKeyboardButton("👥 Customer Insight",       callback_data="task_customer"),
        InlineKeyboardButton("💰 Pricing Strategy",       callback_data="task_pricing"),
    ],
    [
        InlineKeyboardButton("📡 Social Listening",       callback_data="task_social"),
        InlineKeyboardButton("🎯 Marketing Strategy",     callback_data="task_strategy"),
    ],
])

CONFIRM_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("✅ Đúng rồi, bắt đầu!", callback_data="confirm_yes"),
        InlineKeyboardButton("✏️ Sửa thông tin",       callback_data="confirm_no"),
    ]
])

RESTART_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔄 Bắt đầu phân tích mới", callback_data="restart")],
])


def brand_select_keyboard(candidates: list, single: bool = False) -> InlineKeyboardMarkup:
    """Dynamic keyboard for brand confirmation / multi-select."""
    buttons = []
    if single:
        buttons.append([
            InlineKeyboardButton("✅ Đúng, đó là brand tôi", callback_data="brand_pick_0"),
            InlineKeyboardButton("❌ Không phải",            callback_data="brand_none"),
        ])
    else:
        for i, c in enumerate(candidates[:4]):
            label = c.get("name", f"Option {i+1}")
            desc  = c.get("description", "")[:45]
            if desc:
                label = f"{label} — {desc}"
            buttons.append([InlineKeyboardButton(label[:64], callback_data=f"brand_pick_{i}")])
        buttons.append([InlineKeyboardButton("❌ Không phải những cái trên", callback_data="brand_none")])
    return InlineKeyboardMarkup(buttons)


# ── Guided intake wizard — used when brand search can't auto-fill profile ──
# Each step shows known options + "Khác" so the user can either tap-to-pick
# or escape to free-text input. Reduces friction vs. typing everything.

INDUSTRY_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🍔 F&B",            callback_data="guided_industry_fnb"),
        InlineKeyboardButton("💻 Tech/SaaS",      callback_data="guided_industry_tech_saas"),
    ],
    [
        InlineKeyboardButton("🛒 E-commerce",     callback_data="guided_industry_ecommerce"),
        InlineKeyboardButton("📚 Education",      callback_data="guided_industry_education"),
    ],
    [
        InlineKeyboardButton("💄 Health & Beauty", callback_data="guided_industry_health_beauty"),
        InlineKeyboardButton("🛍️ Retail",          callback_data="guided_industry_retail"),
    ],
    [
        InlineKeyboardButton("🏢 B2B Service",    callback_data="guided_industry_b2b_service"),
        InlineKeyboardButton("🏘️ Real Estate",    callback_data="guided_industry_real_estate"),
    ],
    [InlineKeyboardButton("✏️ Khác (gõ vào)", callback_data="guided_industry_other")],
])

STAGE_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("💡 Idea",   callback_data="guided_stage_idea"),
        InlineKeyboardButton("🚀 MVP",    callback_data="guided_stage_mvp"),
    ],
    [
        InlineKeyboardButton("📈 Growth", callback_data="guided_stage_growth"),
        InlineKeyboardButton("🏆 Scale",  callback_data="guided_stage_scale"),
    ],
    [InlineKeyboardButton("✏️ Khác (gõ vào)", callback_data="guided_stage_other")],
])

LOCATION_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🏙️ TP.HCM",  callback_data="guided_location_hcm"),
        InlineKeyboardButton("🏛️ Hà Nội",  callback_data="guided_location_hanoi"),
    ],
    [
        InlineKeyboardButton("🌊 Đà Nẵng", callback_data="guided_location_danang"),
        InlineKeyboardButton("🏝️ Phú Quốc / Du lịch", callback_data="guided_location_tourist"),
    ],
    [InlineKeyboardButton("🇻🇳 Toàn quốc / Online", callback_data="guided_location_nationwide")],
    [InlineKeyboardButton("✏️ Khác (gõ vào)", callback_data="guided_location_other")],
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
