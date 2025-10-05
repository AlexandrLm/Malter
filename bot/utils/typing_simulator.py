import asyncio

from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender

from config import MAX_TYPING_DELAY, MIN_TYPING_DELAY, TYPING_SPEED_CPS


async def simulate_typing_and_send(message: Message, text: str) -> None:
    """
    Имитирует набор текста с реалистичной скоростью и отправляет сообщение.
    
    Args:
        message: Сообщение для ответа
        text: Текст для отправки
    """
    delay = len(text) / TYPING_SPEED_CPS
    clamped_delay = max(MIN_TYPING_DELAY, min(delay, MAX_TYPING_DELAY))

    async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
        await asyncio.sleep(clamped_delay)
        await message.answer(text)


async def send_typing_response(message: Message, text: str) -> None:
    """
    Отправляет ответ, разделяя его по '||' и имитируя набор для каждой части.
    
    Args:
        message: Сообщение для ответа
        text: Текст с разделителями '||'
    """
    parts = text.split('||')
    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue

        await simulate_typing_and_send(message, part)

        if i < len(parts) - 1:
            await asyncio.sleep(1.2)