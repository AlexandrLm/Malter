 # bot.py

import asyncio
import logging

import httpx
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio.client import Redis

from config import TELEGRAM_TOKEN
from bot.handlers import router

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    
    # Инициализируем хранилище Redis
    redis = Redis(host='redis')
    storage = RedisStorage(redis=redis)

    # Создаем httpx клиент, который будет жить все время работы бота
    async with httpx.AsyncClient() as client:
        # Создаем диспетчер и передаем ему клиент и хранилище
        dp = Dispatcher(client=client, storage=storage)

        dp.include_router(router)

        await bot.delete_webhook(drop_pending_updates=True)

        try:
            logging.info("Запуск polling...")
            await dp.start_polling(bot)
        finally:
            await bot.session.close()
            logging.info("Бот остановлен.")

