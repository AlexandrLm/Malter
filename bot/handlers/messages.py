import logging
from typing import Optional

import httpx
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from ..services.api_client import get_token, make_api_request
from ..services.image_processor import process_image
from ..services.response_handler import send_response

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.text | F.photo)
async def handle_message(message: types.Message, state: FSMContext, client: httpx.AsyncClient) -> None:
    """
    Обработчик текстовых сообщений и изображений.
    
    Args:
        message: Входящее сообщение
        state: FSM состояние
        client: HTTP клиент для API запросов
    """
    # Проверяем, не находится ли пользователь в процессе заполнения профиля
    current_state = await state.get_state()
    if current_state is not None:
        await message.answer("Подожди, давай сначала я все вспомню...")
        return

    user_id = message.from_user.id
    image_data_b64: Optional[str] = None

    # Обработка изображения, если оно есть
    image_data_b64 = await process_image(message)

    # Текст сообщения (или подпись к фото)
    text = message.text or message.caption or ""

    # Получаем JWT токен для пользователя
    token = await get_token(client, user_id)
    
    payload = {
        "message": text,
        "timestamp": message.date.isoformat(),
        "image_data": image_data_b64
    }

    response = await make_api_request(
        client,
        "post",
        "/chat",
        user_id=user_id,
        token=token,
        json=payload,
        timeout=180.0
    )

    data = response.json()
    
    await send_response(message, data)