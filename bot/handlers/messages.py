import logging
import httpx
from aiogram import Router, F, types
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext
from ..services.image_processor import process_image
from ..services.api_client import make_api_request
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

    try:
        await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
        # Обработка изображения, если оно есть
        image_data_b64 = await process_image(message)

        # Текст сообщения (или подпись к фото)
        text = message.text or message.caption or ""

        payload = {
            "user_id": user_id,
            "message": text,
            "timestamp": message.date.isoformat(),
            "image_data": image_data_b64  # Добавляем base64 картинки
        }

        response = await make_api_request(
            client,
            "post",
            "/chat",
            user_id=user_id,
            json=payload,
            timeout=180.0  # Увеличиваем таймаут для обработки изображений
        )

        data = response.json()
        await send_response(message, data)

    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logger.error(f"API connection error in handle_message for user {user_id} after retries: {e}")
        await message.answer("Милый, у меня связь пропала... Не вижу твое сообщение. Напиши, как только интернет появится.")
    except ValueError as e:
        logger.error(f"ValueError in handle_message for user {user_id}: {e}")
        await message.answer("Произошла ошибка обработки данных. Попробуйте еще раз.")
    except Exception as e:
        logger.error(f"An unexpected error occurred in handle_message for user {user_id}: {e}", exc_info=True)
        await message.answer("Ой, что-то пошло не так... Попробуй еще раз.")