from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

gender_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Мужчина"), KeyboardButton(text="Женщина")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_profile_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔙 Назад в чат", callback_data="back_to_chat")
        ],
        [
            InlineKeyboardButton(text="📊 Прогресс отношений", callback_data="show_progress")
        ],
    ])
    return keyboard