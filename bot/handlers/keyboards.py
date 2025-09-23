from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

gender_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Мужчина"), KeyboardButton(text="Женщина")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)