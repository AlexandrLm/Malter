# bot.py

import asyncio
import logging
import signal
import sys

import httpx
from aiogram import BaseMiddleware, Bot, Dispatcher, types
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio.client import Redis

from config import TELEGRAM_TOKEN, REDIS_HOST, REDIS_PORT, REDIS_DB, HTTPX_TIMEOUT, HTTPX_CONNECT_TIMEOUT
from bot.handlers import router

# Глобальный флаг для graceful shutdown
shutdown_event = asyncio.Event()

def signal_handler(signum, frame):
    """
    Обработчик сигналов SIGTERM и SIGINT для graceful shutdown.
    
    Args:
        signum: Номер сигнала
        frame: Текущий stack frame
    """
    signal_name = signal.Signals(signum).name
    logging.info(f"Получен сигнал {signal_name} ({signum}). Начинаем graceful shutdown...")
    shutdown_event.set()

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    
    # Инициализируем хранилище Redis
    redis = Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
    storage = RedisStorage(redis=redis)

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

    dp.update.middleware(ErrorMiddleware())

    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)

    # Регистрируем обработчики сигналов для graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    logging.debug("Обработчики сигналов SIGTERM и SIGINT зарегистрированы")

    # Используем async context manager для httpx клиента с настраиваемыми таймаутами
    async with httpx.AsyncClient(timeout=httpx.Timeout(HTTPX_TIMEOUT, connect=HTTPX_CONNECT_TIMEOUT)) as client:
        # Добавляем middleware с клиентом
        dp.update.middleware(HttpClientMiddleware(client))
        
        try:
            logging.debug("Запуск polling...")
            
            # Создаём задачу polling
            polling_task = asyncio.create_task(dp.start_polling(bot))
            
            # Создаём задачу ожидания shutdown сигнала
            shutdown_task = asyncio.create_task(shutdown_event.wait())
            
            # Ждём завершения одной из задач
            done, pending = await asyncio.wait(
                [polling_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Если получен shutdown сигнал
            if shutdown_task in done:
                logging.info("Получен сигнал остановки. Завершаем обработку текущих сообщений...")
                
                # Останавливаем polling gracefully
                await dp.stop_polling()
                
                # Даём время на завершение обработки текущих сообщений (макс 10 сек)
                try:
                    await asyncio.wait_for(polling_task, timeout=10.0)
                    logging.debug("Все текущие сообщения обработаны")
                except asyncio.TimeoutError:
                    logging.warning("Таймаут ожидания завершения обработки сообщений (10s)")
                    polling_task.cancel()
                    try:
                        await polling_task
                    except asyncio.CancelledError:
                        pass
            
        except Exception as e:
            logging.error(f"Критическая ошибка в main loop: {e}", exc_info=True)
        finally:
            # Cleanup resources
            logging.debug("Начинаем cleanup ресурсов...")
            
            # Закрываем сессию бота
            try:
                await bot.session.close()
                logging.debug("Bot session закрыта")
            except Exception as e:
                logging.error(f"Ошибка при закрытии bot session: {e}")
            
            # Закрываем storage
            if storage:
                try:
                    await storage.close()
                    logging.debug("Redis storage закрыт")
                except Exception as e:
                    logging.error(f"Ошибка при закрытии storage: {e}")
            
            logging.info("Бот полностью остановлен. Goodbye! 👋")
