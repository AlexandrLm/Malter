import base64
import logging
from typing import Dict, Any

from aiogram.types import BufferedInputFile, Message
from aiogram.utils.chat_action import ChatActionSender

from ..utils.typing_simulator import send_typing_response

logger = logging.getLogger(__name__)


async def send_response(message: Message, response_data: Dict[str, Any]) -> None:
    """
    Отправляет ответ пользователю, включая обработку голосовых сообщений.
    
    Args:
        message: Исходное сообщение пользователя
        response_data: Данные ответа от API
    """
    voice_bytes_b64 = response_data.get("voice_message")
    if voice_bytes_b64:
        try:
            async with ChatActionSender.record_voice(bot=message.bot, chat_id=message.chat.id):
                voice_bytes = base64.b64decode(voice_bytes_b64)
                await message.answer_voice(BufferedInputFile(voice_bytes, "voice.ogg"))
        except Exception as e:
            logger.error(f"Error sending voice message to user {message.from_user.id}: {e}", exc_info=True)
            await message.answer("Я хотела записать голосовое, но что-то с телефоном... короче, я так по тебе соскучилась!")
    else:
        response_text = response_data.get('response_text')
        if response_text:
            await send_typing_response(message, response_text)
        else:
            logger.warning(f"No response_text in response_data for user {message.from_user.id}")
            await message.answer("Извини, не могу придумать, что сказать... Расскажи еще!")