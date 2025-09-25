import asyncio
from aiogram.types import Message
from aiogram.enums import ChatAction
from aiogram.utils.chat_action import ChatActionSender
from config import TYPING_SPEED_CPS, MIN_TYPING_DELAY, MAX_TYPING_DELAY


async def simulate_typing_and_send(message: Message, text: str):
    """
    Имитирует набор текста с реалистичной скоростью и отправляет сообщение.
    """
    # 1. Рассчитываем задержку на основе длины текста
    delay = len(text) / TYPING_SPEED_CPS
    
    # 2. Ограничиваем задержку минимальным и максимальным значениями
    clamped_delay = max(MIN_TYPING_DELAY, min(delay, MAX_TYPING_DELAY))

    # 3. Отправляем экшен "печатает", ждем и отправляем сообщение
    async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
        await asyncio.sleep(clamped_delay)
        await message.answer(text)


async def send_typing_response(message: Message, text: str):
    """
    Отправляет ответ, разделяя его по '||' и имитируя набор для каждой части.
    """
    parts = text.split('||')
    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue

        # Отправляем первую часть с имитацией набора
        await simulate_typing_and_send(message, part)

        # Если есть следующая часть, делаем небольшую паузу "на подумать"
        if i < len(parts) - 1:
            await asyncio.sleep(1.2)