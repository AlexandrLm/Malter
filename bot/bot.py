# bot.py

import asyncio
import logging
import sys
import httpx # <--- Импортируем

from aiogram import Bot, Dispatcher

from config import TELEGRAM_TOKEN
from bot.handlers import router

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    
    # Создаем httpx клиент, который будет жить все время работы бота
    async with httpx.AsyncClient() as client:
        # Создаем диспетчер и передаем ему клиент
        # Теперь все хендлеры в 'router' смогут его получить
        dp = Dispatcher(client=client)

        dp.include_router(router)

        await bot.delete_webhook(drop_pending_updates=True)

        try:
            logging.info("Запуск polling...")
            await dp.start_polling(bot)
        finally:
            await bot.session.close()
            logging.info("Бот остановлен.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    logging.info("Бот 'Маша' инициализируется...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Выход по команде (Ctrl+C)")