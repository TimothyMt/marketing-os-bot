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
    # Social Listening tạm tắt — chờ web search engine có VN coverage tốt hơn
    # [InlineKeyboardButton("📡 Social Listening",       callback_data="task_social")],
    [InlineKeyboardButton("🎯 Marketing Strategy",       callback_data="task_strategy")],
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


def stage_done_keyboard(is_last: bool = False) -> InlineKeyboardMarkup:
    if is_last:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Phân tích business mới", callback_data="restart")],
            [InlineKeyboardButton("❓ Hỏi thêm về strategy",   callback_data="ask_followup")],
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Chạy bước tiếp theo", callback_data="continue_pipeline")],
    ])
