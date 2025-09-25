import logging
import httpx
from aiogram import Router, F, types
from aiogram.enums import ChatAction
from aiogram.utils.chat_action import ChatActionSender
from aiogram.fsm.context import FSMContext
from ..services.image_processor import process_image
from ..services.api_client import make_api_request, get_token
from ..services.response_handler import send_response

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text | F.photo)
async def handle_message(message: types.Message, state: FSMContext, client: httpx.AsyncClient):
    if await state.get_state() is not None:
        await message.answer("Подожди, давай сначала я все вспомню...")
        return

    user_id = message.from_user.id
    image_data_b64 = None

    async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
        # Обработка изображения, если оно есть
        image_data_b64 = await process_image(message)

        # Текст сообщения (или подпись к фото)
        text = message.text or message.caption or ""

        # Get JWT token for the user
        token = await get_token(client, user_id)
        
        payload = {
            "message": text,
            "timestamp": message.date.isoformat(),
            "image_data": image_data_b64  # Добавляем base64 картинки
        }

        response = await make_api_request(
            client,
            "post",
            "/chat",
            user_id=user_id,
            token=token,
            json=payload,
            timeout=180.0  # Увеличиваем таймаут для обработки изображений
        )

        data = response.json()
    await send_response(message, data)