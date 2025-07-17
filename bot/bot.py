import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import TELEGRAM_TOKEN
from bot.handlers import router

async def main():
    # Настраиваем логирование
    logging.basicConfig(level=logging.INFO)

    # Создаем объекты Бота и Диспетчера
    bot = Bot(token=TELEGRAM_TOKEN)
    dp = Dispatcher()

    # Включаем роутер из handlers.py в основной диспетчер
    dp.include_router(router)

    # Удаляем вебхук и запускаем polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    print("Бот 'Маша' запускается...")
    asyncio.run(main())