import base64
import logging
from aiogram.types import Message, BufferedInputFile
from aiogram.enums import ChatAction
from aiogram.utils.chat_action import ChatActionSender
from ..utils.typing_simulator import send_typing_response

logger = logging.getLogger(__name__)

async def send_response(message: Message, response_data: dict):
    """
    Отправляет ответ пользователю, включая обработку голосовых сообщений.
    
    Args:
        message (Message): Исходное сообщение пользователя.
        response_data (dict): Данные ответа от API.
    """
    voice_bytes_b64 = response_data.get("voice_message")
    if voice_bytes_b64:
        try:
            async with ChatActionSender.record_voice(bot=message.bot, chat_id=message.chat.id):
                voice_bytes = base64.b64decode(voice_bytes_b64)
                await message.answer_voice(BufferedInputFile(voice_bytes, "voice.ogg"))
        except Exception as e:
            logger.error(f"Error sending voice message to user {message.from_user.id}: {e}")
            await message.answer("Я хотела записать голосовое, но что-то с телефоном... короче, я так по тебе соскучилась!")
    else:
        if 'response_text' in response_data:
            await send_typing_response(message, response_data["response_text"])
        else:
            logger.warning(f"No response_text in response_data for user {message.from_user.id}")
            await message.answer("Извини, не могу придумать, что сказать... Расскажи еще!")