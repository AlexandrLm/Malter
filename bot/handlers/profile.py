import logging
from typing import Optional, Tuple

import httpx
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove

from ..services.api_client import make_api_request
from ..services.geolocation_service import GeolocationService
from ..utils.validators import is_valid_city, is_valid_name
from .keyboards import gender_keyboard

router = Router()
logger = logging.getLogger(__name__)


class ProfileStates(StatesGroup):
    """FSM состояния для создания профиля."""
    name = State()
    gender = State()
    city = State()


geolocation_service = GeolocationService()

@router.message(ProfileStates.name, F.text)
async def process_name(message: types.Message, state: FSMContext) -> None:
    """Обработчик ввода имени."""
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
async def process_name_invalid(message: types.Message) -> None:
    """Обработчик неверного формата имени."""
    await message.answer("Пожалуйста, отправь свое имя в виде текста.")


@router.message(ProfileStates.gender, F.text.in_(["Мужчина", "Женщина"]))
async def process_gender(message: types.Message, state: FSMContext) -> None:
    """Обработчик выбора пола."""
    await state.update_data(gender=message.text.lower())
    await message.answer(
        "И последний вопрос, чтобы я не путалась во времени... В каком городе ты живешь?",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(ProfileStates.city)


@router.message(ProfileStates.gender)
async def process_gender_invalid(message: types.Message) -> None:
    """Обработчик неверного выбора пола."""
    await message.answer("Пожалуйста, выбери один из вариантов на клавиатуре.")


@router.message(ProfileStates.city, F.text)
async def process_city(message: types.Message, state: FSMContext, client: httpx.AsyncClient) -> None:
    """
    Обработчик ввода города с улучшенной обработкой ошибок.
    
    Args:
        message: Сообщение с названием города
        state: FSM состояние
        client: HTTP клиент
    """
    if not message.text:
        await message.answer("Пожалуйста, отправь название города в виде текста.")
        return
        
    city_name = message.text.strip()
    
    if not is_valid_city(city_name):
        await message.answer("Название города кажется слишком коротким. Попробуй еще раз.")
        return

    try:
        location, timezone = await geolocation_service.get_location_and_timezone(city_name)
        
        if not location:
            await message.answer(
                "Не могу найти такой город... Попробуй, пожалуйста, ввести его еще раз, "
                "возможно, с уточнением (например, 'Москва, Россия')."
            )
            return

        await state.update_data(city=city_name, timezone=timezone)
        user_data = await state.get_data()

        profile_data = {
            "name": user_data.get("name"),
            "gender": user_data.get("gender"),
            "city": user_data.get("city"),
            "timezone": user_data.get("timezone")
        }

        await make_api_request(
            client,
            "post",
            "/profile",
            user_id=message.from_user.id,
            json={"user_id": message.from_user.id, "data": profile_data}
        )
        
        await state.clear()
        await message.answer("Привет!")
        logger.info(f"Profile created for user {message.from_user.id}, city: {city_name}")
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error processing city for user {message.from_user.id}: {e.response.status_code}", exc_info=True)
        await message.answer(
            "Произошла ошибка при сохранении профиля. Попробуй еще раз через несколько секунд."
        )
    except httpx.RequestError as e:
        logger.error(f"Network error processing city for user {message.from_user.id}: {e}", exc_info=True)
        await message.answer(
            "Проблема с подключением к серверу. Проверь интернет и попробуй еще раз."
        )
    except Exception as e:
        logger.error(f"Unexpected error processing city for user {message.from_user.id}: {e}", exc_info=True)
        await message.answer(
            "Произошла неожиданная ошибка. Попробуй еще раз или введи другой город."
        )


@router.message(ProfileStates.city)
async def process_city_invalid(message: types.Message) -> None:
    """Обработчик неверного формата города."""
    await message.answer("Пожалуйста, отправь название города в виде текста.")