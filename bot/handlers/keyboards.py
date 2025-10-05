from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

gender_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Мужчина"), KeyboardButton(text="Женщина")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)


def get_profile_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру для профиля пользователя."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔙 Назад в чат", callback_data="back_to_chat")
        ],
        [
            InlineKeyboardButton(text="📊 Прогресс отношений", callback_data="show_progress")
        ],
    ])
    return keyboard