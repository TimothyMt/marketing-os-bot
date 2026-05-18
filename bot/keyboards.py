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


def stage_done_keyboard(is_last: bool = False) -> InlineKeyboardMarkup:
    if is_last:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Phân tích business mới", callback_data="restart")],
            [InlineKeyboardButton("❓ Hỏi thêm về strategy",   callback_data="ask_followup")],
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Chạy bước tiếp theo", callback_data="continue_pipeline")],
    ])
