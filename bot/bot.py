# bot.py

import asyncio
import logging

import httpx
from aiogram import BaseMiddleware, Bot, Dispatcher, types
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio.client import Redis

from config import TELEGRAM_TOKEN, REDIS_HOST, REDIS_PORT, REDIS_DB
from bot.handlers import router

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    
    # Инициализируем хранилище Redis
    redis = Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
    storage = RedisStorage(redis=redis)

    # Создаем httpx клиент, который будет жить все время работы бота
    client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0))

    # Создаем диспетчер и передаем ему хранилище
    dp = Dispatcher(storage=storage)

    class HttpClientMiddleware(BaseMiddleware):
        def __init__(self, client: httpx.AsyncClient):
            self.client = client

        async def __call__(
            self,
            handler,
            event: types.TelegramObject,
            data: dict,
        ) -> types.TelegramObject:
            data["client"] = self.client
            return await handler(event, data)

    class ErrorMiddleware(BaseMiddleware):
        """
        Middleware to handle exceptions in handlers globally.
        Logs errors and sends user-friendly responses.
        """
        async def __call__(
            self,
            handler,
            event: types.TelegramObject,
            data: dict,
        ) -> types.TelegramObject:
            try:
                return await handler(event, data)
            except Exception as e:
                logging.error(f"Error in handler for {event.from_user.id if hasattr(event, 'from_user') else 'unknown'}: {e}", exc_info=True)
                
                if hasattr(event, 'answer'):
                    if isinstance(e, (httpx.RequestError, httpx.HTTPStatusError)):
                        await event.answer("Произошла ошибка связи с сервером. Попробуйте позже.")
                    else:
                        await event.answer("Произошла неожиданная ошибка. Попробуйте еще раз.")
                
                raise  # Re-raise to prevent silent failures

    dp.update.middleware(HttpClientMiddleware(client))
    dp.update.middleware(ErrorMiddleware())

    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)

    try:
        logging.info("Запуск polling...")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await client.aclose()
        if storage:
            await storage.close()
        logging.info("Бот остановлен.")
