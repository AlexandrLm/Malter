import logging
import httpx
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove
from ..utils.validators import is_valid_name, is_valid_city
from ..services.geolocation_service import GeolocationService
from ..services.api_client import make_api_request
from .keyboards import gender_keyboard

router = Router()
logger = logging.getLogger(__name__)

class ProfileStates(StatesGroup):
    name = State()
    gender = State()
    city = State()

geolocation_service = GeolocationService()

@router.message(ProfileStates.name, F.text)
async def process_name(message: types.Message, state: FSMContext):
    if is_valid_name(message.text):
        await state.update_data(name=message.text)
        await message.answer(
            f"Хорошо, {message.text}. А ты мужчина или женщина? Мне это нужно, чтобы правильно к тебе обращаться.",
            reply_markup=gender_keyboard
        )
        await state.set_state(ProfileStates.gender)
    else:
        await message.answer("Хм, что-то не похоже на имя. Попробуй еще раз. Используй только буквы, пожалуйста.")

@router.message(ProfileStates.name)
async def process_name_invalid(message: types.Message):
    await message.answer("Пожалуйста, отправь свое имя в виде текста.")

@router.message(ProfileStates.gender, F.text.in_(["Мужчина", "Женщина"]))
async def process_gender(message: types.Message, state: FSMContext):
    await state.update_data(gender=message.text.lower())
    await message.answer(
        "И последний вопрос, чтобы я не путалась во времени... В каком городе ты живешь?",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(ProfileStates.city)

@router.message(ProfileStates.gender)
async def process_gender_invalid(message: types.Message):
    await message.answer("Пожалуйста, выбери один из вариантов на клавиатуре.")

@router.message(ProfileStates.city, F.text)
async def process_city(message: types.Message, state: FSMContext, client: httpx.AsyncClient):
    if not is_valid_city(message.text):
        await message.answer("Название города кажется слишком коротким. Попробуй еще раз.")
        return

    try:
        location, timezone = await geolocation_service.get_location_and_timezone(message.text)
        if not location:
            await message.answer("Не могу найти такой город... Попробуй, пожалуйста, ввести его еще раз, возможно, с уточнением (например, 'Москва, Россия').")
            return
    except Exception as e:
        logger.error(f"Could not determine timezone for {message.text}: {e}")
        timezone = "UTC"  # Фоллбэк

    await state.update_data(city=message.text, timezone=timezone)
    user_data = await state.get_data()

    profile_data = {
        "name": user_data.get("name"),
        "gender": user_data.get("gender"),
        "city": user_data.get("city"),
        "timezone": user_data.get("timezone")
    }

    try:
        await make_api_request(
            client,
            "post",
            "/profile",
            user_id=message.from_user.id,
            json={"user_id": message.from_user.id, "data": profile_data}
        )
        await state.clear()
        await message.answer("Привет!")
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logger.error(f"API connection error saving profile for user {message.from_user.id} after retries: {e}")
        await message.answer("Ой, не могу сохранить... что-то с телефоном. Давай попробуем позже, нажми /reset.")
    except Exception as e:
        logger.error(f"Unexpected error saving profile for user {message.from_user.id}: {e}", exc_info=True)
        await message.answer("Произошла непредвиденная ошибка при сохранении профиля. Попробуйте еще раз позже.")

@router.message(ProfileStates.city)
async def process_city_invalid(message: types.Message):
    await message.answer("Пожалуйста, отправь название города в виде текста.")