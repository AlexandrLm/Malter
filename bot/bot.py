# bot.py

import asyncio
import logging
import platform
import signal
import sys
from typing import Any, Awaitable, Callable, Dict

import httpx
from aiogram import BaseMiddleware, Bot, Dispatcher, types
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio.client import Redis

from config import HTTPX_CONNECT_TIMEOUT, HTTPX_TIMEOUT, REDIS_DB, REDIS_HOST, REDIS_PORT, TELEGRAM_TOKEN
from bot.handlers import router

logger = logging.getLogger(__name__)

# Глобальный флаг для graceful shutdown
shutdown_event = asyncio.Event()

def signal_handler(signum: int, frame: Any) -> None:
    """
    Обработчик сигналов SIGTERM и SIGINT для graceful shutdown.
    
    Args:
        signum: Номер сигнала
        frame: Текущий stack frame
    """
    try:
        signal_name = signal.Signals(signum).name
    except (ValueError, AttributeError):
        signal_name = str(signum)
    logger.info(f"Получен сигнал {signal_name} ({signum}). Начинаем graceful shutdown...")
    shutdown_event.set()

class HttpClientMiddleware(BaseMiddleware):
    """Middleware для внедрения HTTP клиента в обработчики."""
    
    def __init__(self, client: httpx.AsyncClient) -> None:
        super().__init__()
        self.client = client

    async def __call__(
        self,
        handler: Callable[[types.TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: types.TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        data["client"] = self.client
        return await handler(event, data)


class ErrorMiddleware(BaseMiddleware):
    """
    Middleware для глобальной обработки ошибок в хендлерах.
    Логирует ошибки и отправляет пользовательские сообщения.
    """
    
    async def __call__(
        self,
        handler: Callable[[types.TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: types.TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as e:
            user_id = event.from_user.id if hasattr(event, 'from_user') else 'unknown'
            logger.error(f"Error in handler for user {user_id}: {e}", exc_info=True)
            
            if hasattr(event, 'answer'):
                if isinstance(e, (httpx.RequestError, httpx.HTTPStatusError)):
                    await event.answer("Произошла ошибка связи с сервером. Попробуйте позже.")
                else:
                    await event.answer("Произошла неожиданная ошибка. Попробуйте еще раз.")
            
            raise


async def main() -> None:
    """Основная функция запуска бота."""
    bot = Bot(token=TELEGRAM_TOKEN)
    redis: Redis | None = None
    storage: RedisStorage | None = None
    
    try:
        # Инициализируем хранилище Redis
        redis = Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
        storage = RedisStorage(redis=redis)

        # Создаем диспетчер и передаем ему хранилище
        dp = Dispatcher(storage=storage)
        
        dp.update.middleware(ErrorMiddleware())
        dp.include_router(router)

        await bot.delete_webhook(drop_pending_updates=True)

        # Регистрируем обработчики сигналов для graceful shutdown
        # На Windows SIGTERM может не работать корректно, поэтому только SIGINT
        signal.signal(signal.SIGINT, signal_handler)
        
        # SIGTERM только для Unix-подобных систем
        if platform.system() != 'Windows':
            signal.signal(signal.SIGTERM, signal_handler)
            logger.debug("Обработчики сигналов SIGTERM и SIGINT зарегистрированы")
        else:
            logger.debug("Обработчик сигнала SIGINT зарегистрирован (Windows)")

        # Используем async context manager для httpx клиента с настраиваемыми таймаутами
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(HTTPX_TIMEOUT, connect=HTTPX_CONNECT_TIMEOUT)
        ) as client:
            # Добавляем middleware с клиентом
            dp.update.middleware(HttpClientMiddleware(client))
            
            try:
                logger.debug("Запуск polling...")
                
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
                    logger.info("Получен сигнал остановки. Завершаем обработку текущих сообщений...")
                    
                    # Останавливаем polling gracefully
                    await dp.stop_polling()
                    
                    # Даём время на завершение обработки текущих сообщений (макс 10 сек)
                    try:
                        await asyncio.wait_for(polling_task, timeout=10.0)
                        logger.debug("Все текущие сообщения обработаны")
                    except asyncio.TimeoutError:
                        logger.warning("Таймаут ожидания завершения обработки сообщений (10s)")
                        polling_task.cancel()
                        try:
                            await polling_task
                        except asyncio.CancelledError:
                            pass
                
            except Exception as e:
                logger.error(f"Критическая ошибка в main loop: {e}", exc_info=True)
                raise
            
    finally:
        # Cleanup resources
        logger.debug("Начинаем cleanup ресурсов...")
        
        # Закрываем сессию бота
        try:
            await bot.session.close()
            logger.debug("Bot session закрыта")
        except Exception as e:
            logger.error(f"Ошибка при закрытии bot session: {e}")
        
        # Закрываем storage
        if storage:
            try:
                await storage.close()
                logger.debug("Redis storage закрыт")
            except Exception as e:
                logger.error(f"Ошибка при закрытии storage: {e}")
        
        # Закрываем Redis соединение
        if redis:
            try:
                await redis.close()
                logger.debug("Redis connection закрыто")
            except Exception as e:
                logger.error(f"Ошибка при закрытии Redis connection: {e}")
        
        logger.info("Бот полностью остановлен. Goodbye! 👋")
