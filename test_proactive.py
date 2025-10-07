"""
Тестовый скрипт для проверки проактивных сообщений.
Запускается внутри Docker контейнера.
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
import pytz

# Добавляем текущую директорию в путь
sys.path.insert(0, '/app')

from server.database import get_active_users_for_proactive, get_last_message_time
from server.scheduler import _should_send_proactive, PROACTIVE_MESSAGES


async def test_proactive_messages():
    """Тестирует функции проактивных сообщений."""
    
    print("=" * 60)
    print("ТЕСТ: Проактивные сообщения")
    print("=" * 60)
    
    # Тест 1: Получение активных пользователей
    print("\n1. Получение активных пользователей...")
    try:
        active_users = await get_active_users_for_proactive()
        print(f"   ✅ Найдено активных пользователей: {len(active_users)}")
        
        if active_users:
            for user in active_users[:3]:  # Показываем первых 3
                print(f"      - User {user.user_id}: timezone={user.timezone}, plan={user.subscription_plan}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return
    
    # Тест 2: Получение времени последнего сообщения
    print("\n2. Получение времени последних сообщений...")
    for user in active_users[:3]:
        try:
            last_time = await get_last_message_time(user.user_id)
            if last_time:
                # Конвертируем в локальное время пользователя
                user_tz = pytz.timezone(user.timezone)
                if last_time.tzinfo is None:
                    last_time = last_time.replace(tzinfo=timezone.utc)
                local_time = last_time.astimezone(user_tz)
                hours_ago = (datetime.now(timezone.utc) - last_time).total_seconds() / 3600
                print(f"   ✅ User {user.user_id}: {local_time.strftime('%Y-%m-%d %H:%M %Z')} ({hours_ago:.1f}ч назад)")
            else:
                print(f"   ⚠️  User {user.user_id}: нет истории сообщений")
        except Exception as e:
            print(f"   ❌ User {user.user_id}: ошибка - {e}")
    
    # Тест 3: Проверка логики should_send_proactive
    print("\n3. Проверка логики отправки...")
    for user in active_users[:5]:
        try:
            last_time = await get_last_message_time(user.user_id)
            should_send, message_type = _should_send_proactive(user, last_time)
            
            if should_send:
                print(f"   📤 User {user.user_id}: ОТПРАВИТЬ - тип '{message_type}'")
            else:
                # Определяем причину
                if not user.timezone:
                    reason = "нет timezone"
                elif not last_time:
                    reason = "нет истории"
                else:
                    user_tz = pytz.timezone(user.timezone)
                    user_now = datetime.now(user_tz)
                    hour = user_now.hour
                    if hour >= 23 or hour < 8:
                        reason = f"ночное время ({hour}:00)"
                    else:
                        hours_ago = (user_now - last_time.replace(tzinfo=timezone.utc)).total_seconds() / 3600
                        reason = f"недавно писали ({hours_ago:.1f}ч назад)"
                
                print(f"   ⏸️  User {user.user_id}: НЕ отправлять - {reason}")
        except Exception as e:
            print(f"   ❌ User {user.user_id}: ошибка - {e}")
    
    # Тест 4: Проверка шаблонов сообщений
    print("\n4. Проверка шаблонов сообщений...")
    for msg_type, messages in PROACTIVE_MESSAGES.items():
        print(f"   ✅ {msg_type}: {len(messages)} вариантов")
        print(f"      Пример: '{messages[0]}'")
    
    print("\n" + "=" * 60)
    print("ТЕСТ ЗАВЕРШЕН")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_proactive_messages())
