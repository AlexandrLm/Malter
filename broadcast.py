#!/usr/bin/env python3
"""
Скрипт для разовой рассылки сообщений всем пользователям бота.

Использование:
1. Убедитесь, что бот запущен и API доступен.
2. Запустите скрипт с текстом сообщения:
   python broadcast.py "Ваше сообщение здесь"

Важно:
- Скрипт должен запускаться на той же машине где работает API (например, в Docker-контейнере).
- Для работы скрипта необходим доступ к TELEGRAM_TOKEN из config.py.
"""

import sys
import asyncio
import logging
from typing import List

from aiogram import Bot

# Добавляем путь к проекту, чтобы можно было импортировать модули
sys.path.append(".")

from config import TELEGRAM_TOKEN
from server.database import get_all_user_ids

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def send_broadcast_message(message_text: str):
    """
    Отправляет сообщение всем пользователям.
    
    Args:
        message_text (str): Текст сообщения для рассылки.
    """
    if not message_text.strip():
        logger.error("Текст сообщения не может быть пустым")
        return

    # Получаем список всех пользователей
    user_ids = await get_all_user_ids()
    
    if not user_ids:
        logger.warning("Список пользователей пуст. Нечего отправлять.")
        return

    # Инициализируем бота
    bot = Bot(token=TELEGRAM_TOKEN)
    
    # Счетчики для статистики
    success_count = 0
    error_count = 0
    
    logger.info(f"Начинаем рассылку сообщения {len(user_ids)} пользователям...")
    
    # Отправляем сообщение каждому пользователю
    for user_id in user_ids:
        try:
            # Проверяем, что текст может быть закодирован в UTF-8
            clean_text = message_text.encode('utf-8', errors='ignore').decode('utf-8')
            await bot.send_message(chat_id=user_id, text=clean_text)
            logger.info(f"Сообщение успешно отправлено пользователю {user_id}")
            success_count += 1
            
            # Небольшая задержка между сообщениями, чтобы избежать ограничений Telegram
            await asyncio.sleep(0.1)
            
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
            error_count += 1
    
    # Закрываем сессию бота
    await bot.session.close()
    
    # Выводим итоговую статистику
    logger.info("=" * 50)
    logger.info("РАССЫЛКА ЗАВЕРШЕНА")
    logger.info(f"Успешно отправлено: {success_count}")
    logger.info(f"Ошибок: {error_count}")
    logger.info(f"Всего обработано: {len(user_ids)}")
    logger.info("=" * 50)

async def main():
    """Главная функция скрипта."""
    if len(sys.argv) != 2:
        print("Использование: python broadcast.py \"Текст сообщения\"")
        sys.exit(1)
    
    message_text = sys.argv[1]
    
    logger.info("Запуск скрипта рассылки...")
    await send_broadcast_message(message_text)
    logger.info("Скрипт рассылки завершен.")

if __name__ == "__main__":
    asyncio.run(main())