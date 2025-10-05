"""
Модуль для работы с базой данных.

Этот файл содержит функции для взаимодействия с базой данных PostgreSQL и Redis,
включая операции CRUD для профилей пользователей, истории чата, долговременной памяти и сводок.
"""

from datetime import datetime, date, timedelta, timezone
from sqlalchemy import select, delete, desc, update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import json
import logging
from sqlalchemy.dialects.postgresql import insert
import bleach  # For text sanitization
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
from config import (
    DATABASE_URL, 
    CHAT_HISTORY_LIMIT, 
    REDIS_CLIENT,
    CACHE_TTL_SECONDS,
    REDIS_RETRY_ATTEMPTS,
    REDIS_RETRY_MIN_WAIT,
    REDIS_RETRY_MAX_WAIT
)
from server.models import Base, UserProfile, LongTermMemory, ChatHistory, ChatSummary

# Создаем асинхронный "движок" и фабрику сессий
async_engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,  # Количество соединений, которые будут оставаться открытыми в пуле
    max_overflow=10, # Максимальное количество "дополнительных" соединений сверх pool_size
    pool_timeout=30, # Время в секундах, которое можно ждать соединения перед тем, как выбросить ошибку
    pool_recycle=1800 # Время в секундах, через которое соединение будет пересоздано (для предотвращения проблем с "устаревшими" соединениями)
)
async_session_factory = async_sessionmaker(async_engine)

def get_profile_cache_key(user_id: int) -> str:
    """Генерирует ключ для кэша профиля."""
    return f"profile:{user_id}"

def get_chat_messages_cache_key(user_id: int) -> str:
    """Генерирует ключ для кэша сообщений чата."""
    return f"chat_messages:{user_id}"

@retry(
    stop=stop_after_attempt(REDIS_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=REDIS_RETRY_MIN_WAIT, max=REDIS_RETRY_MAX_WAIT),
    retry=retry_if_exception_type((RedisConnectionError, RedisError)),
    reraise=False  # Не выбрасываем ошибку - просто пропускаем кэш
)
async def _safe_redis_get(key: str) -> str | None:
    """
    Безопасное чтение из Redis с retry механизмом.
    При неудаче возвращает None вместо exception.
    """
    if not REDIS_CLIENT:
        return None
    try:
        return await REDIS_CLIENT.get(key)
    except Exception as e:
        logging.warning(f"Redis GET failed for key {key}: {e}")
        return None

@retry(
    stop=stop_after_attempt(REDIS_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=REDIS_RETRY_MIN_WAIT, max=REDIS_RETRY_MAX_WAIT),
    retry=retry_if_exception_type((RedisConnectionError, RedisError)),
    reraise=False
)
async def _safe_redis_set(key: str, value: str, ex: int) -> bool:
    """
    Безопасная запись в Redis с retry механизмом.
    Возвращает True при успехе, False при неудаче.
    """
    if not REDIS_CLIENT:
        return False
    try:
        await REDIS_CLIENT.set(key, value, ex=ex)
        return True
    except Exception as e:
        logging.warning(f"Redis SET failed for key {key}: {e}")
        return False

@retry(
    stop=stop_after_attempt(REDIS_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=REDIS_RETRY_MIN_WAIT, max=REDIS_RETRY_MAX_WAIT),
    retry=retry_if_exception_type((RedisConnectionError, RedisError)),
    reraise=False
)
async def _safe_redis_delete(key: str) -> bool:
    """
    Безопасное удаление из Redis с retry механизмом.
    Возвращает True при успехе, False при неудаче.
    """
    if not REDIS_CLIENT:
        return False
    try:
        await REDIS_CLIENT.delete(key)
        return True
    except Exception as e:
        logging.warning(f"Redis DELETE failed for key {key}: {e}")
        return False

# Функция для инициализации БД (создания таблицы)
async def init_db():
    """Инициализирует базу данных, создавая все таблицы."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# CRUD-операции
async def get_profile(user_id: int) -> UserProfile | None:
    """
    Получает профиль пользователя, используя кэширование в Redis.
    
    Args:
        user_id (int): Уникальный идентификатор пользователя.
        
    Returns:
        UserProfile | None: Объект профиля пользователя или None, если профиль не найден.
    """
    # Пробуем получить из кэша с retry
    cache_key = get_profile_cache_key(user_id)
    cached_profile_json = await _safe_redis_get(cache_key)
    if cached_profile_json:
        try:
            profile_data = json.loads(cached_profile_json)
            # Преобразуем строки с датами обратно в объекты date/datetime
            for key, value in profile_data.items():
                if isinstance(value, str):
                    try:
                        profile_data[key] = datetime.fromisoformat(value)
                    except (ValueError, TypeError):
                        try:
                            profile_data[key] = date.fromisoformat(value)
                        except (ValueError, TypeError):
                            pass
            return UserProfile(**profile_data)
        except (json.JSONDecodeError, TypeError) as e:
            # Кэш поврежден - удаляем его
            logging.warning(f"Поврежденные данные в кэше для user {user_id}: {e}")
            await _safe_redis_delete(cache_key)

    # Если в кэше нет или произошла ошибка, идем в БД
    try:
        async with async_session_factory() as session:
            result = await session.execute(select(UserProfile).where(UserProfile.user_id == user_id))
            profile = result.scalars().first()

        # Сохраняем в кэш, если профиль найден
        if profile:
            profile_dict = profile.to_dict()
            # Конвертируем date/datetime в ISO строки для JSON
            for key, value in profile_dict.items():
                if isinstance(value, (datetime, date)):
                    profile_dict[key] = value.isoformat()
            
            cache_key = get_profile_cache_key(user_id)
            await _safe_redis_set(cache_key, json.dumps(profile_dict), ex=CACHE_TTL_SECONDS)

        return profile
    except SQLAlchemyError as e:
        logging.error(f"Ошибка БД при получении профиля для пользователя {user_id}: {e}", exc_info=True)
        return None
    except Exception as e:
        logging.error(f"Неожиданная ошибка при получении профиля для пользователя {user_id}: {e}", exc_info=True)
        return None

async def create_or_update_profile(user_id: int, data: dict):
    """
    Атомарно создает или обновляет профиль и инвалидирует кэш.
    
    Args:
        user_id (int): Уникальный идентификатор пользователя.
        data (dict): Данные профиля для создания или обновления.
    """
    try:
        async with async_session_factory() as session:
            stmt = insert(UserProfile).values(user_id=user_id, **data)
            stmt = stmt.on_conflict_do_update(index_elements=['user_id'], set_=data)
            await session.execute(stmt)
            await session.commit()
    except Exception as e:
        logging.error(f"Ошибка при создании/обновлении профиля в БД для пользователя {user_id}: {e}")
        raise

    # Инвалидируем кэш (критично для консистентности данных)
    cache_key = get_profile_cache_key(user_id)
    deleted = await _safe_redis_delete(cache_key)
    if not deleted:
        logging.warning(f"Не удалось инвалидировать кэш профиля для user {user_id}. Данные могут быть устаревшими.")

async def delete_profile(user_id: int):
    """Удаляет профиль и инвалидирует кэш.
    
    Args:
        user_id (int): Уникальный идентификатор пользователя.
    """
    try:
        async with async_session_factory() as session:
            await session.execute(delete(UserProfile).where(UserProfile.user_id == user_id))
            await session.commit()
    except SQLAlchemyError as e:
        logging.error(f"Ошибка БД при удалении профиля для пользователя {user_id}: {e}", exc_info=True)
        raise
    except Exception as e:
        logging.error(f"Неожиданная ошибка при удалении профиля для пользователя {user_id}: {e}", exc_info=True)
        raise

    # Инвалидируем кэш
    cache_key = get_profile_cache_key(user_id)
    await _safe_redis_delete(cache_key)

async def delete_chat_history(user_id: int):
    """Удаляет всю историю чата для пользователя.
    
    Args:
        user_id (int): Уникальный идентификатор пользователя.
    """
    try:
        async with async_session_factory() as session:
            await session.execute(delete(ChatHistory).where(ChatHistory.user_id == user_id))
            await session.commit()
    except SQLAlchemyError as e:
        logging.error(f"Ошибка БД при удалении истории чата для пользователя {user_id}: {e}", exc_info=True)
        raise

async def delete_long_term_memory(user_id: int):
    """Удаляет всю долговременную память для пользователя.
    
    Args:
        user_id (int): Уникальный идентификатор пользователя.
    """
    try:
        async with async_session_factory() as session:
            await session.execute(delete(LongTermMemory).where(LongTermMemory.user_id == user_id))
            await session.commit()
    except SQLAlchemyError as e:
        logging.error(f"Ошибка БД при удалении долговременной памяти для пользователя {user_id}: {e}", exc_info=True)
        raise

async def delete_summary(user_id: int):
    """Удаляет сводку чата для пользователя.
    
    Args:
        user_id (int): Уникальный идентификатор пользователя.
    """
    try:
        async with async_session_factory() as session:
            await session.execute(delete(ChatSummary).where(ChatSummary.user_id == user_id))
            await session.commit()
    except SQLAlchemyError as e:
        logging.error(f"Ошибка БД при удалении сводки для пользователя {user_id}: {e}", exc_info=True)
        raise

async def save_long_term_memory(user_id: int, fact: str, category: str):
    """
    Сохраняет новый факт, только если точно такого же факта еще нет в базе.
    """
    try:
        async with async_session_factory() as session:
            # 1. Проверяем, существует ли уже такой факт
            stmt = select(LongTermMemory).where(
                LongTermMemory.user_id == user_id,
                LongTermMemory.fact == fact
            )
            result = await session.execute(stmt)
            existing_fact = result.scalars().first()
            
            # 2. Если факт уже существует, ничего не делаем и сообщаем об этом
            if existing_fact:
                logging.info(f"Факт для user_id {user_id} уже существует: '{fact}'. Пропускаем сохранение.")
                return {"status": "skipped", "reason": "duplicate fact"}

            # 3. Если факта нет, сохраняем его
            logging.info(f"Сохранение нового факта для user_id {user_id}")
            memory = LongTermMemory(
                user_id=user_id,
                fact=fact,
                category=category
            )
            session.add(memory)
            await session.commit()
            return {"status": "success", "fact_saved": fact}
    except SQLAlchemyError as e:
        logging.error(f"Ошибка БД при сохранении факта для пользователя {user_id}: {e}", exc_info=True)
        return {"status": "error", "reason": "database_error"}

async def get_long_term_memories(user_id: int, query: str) -> dict:
    """Выполняет поиск по ключевым словам в долгосрочной памяти."""
    logging.info(f"Выполнение поиска по ключевым словам для user_id {user_id} с запросом: '{query}'")
    try:
        async with async_session_factory() as session:
            # Используем ilike для регистронезависимого поиска
            result = await session.execute(
                select(LongTermMemory).where(
                    LongTermMemory.user_id == user_id,
                    LongTermMemory.fact.ilike(f"%{query}%")
                ).order_by(desc(LongTermMemory.timestamp)).limit(5)
            )
            memories = result.scalars().all()

        if not memories:
            return {"memories": ["Поиск по ключевым словам не дал результатов."]}

        # Форматируем результат
        formatted_memories = [
            {
                "fact": mem.fact,
                "category": mem.category,
                "timestamp": str(mem.timestamp)
            }
            for mem in memories
        ]

        return {"memories": formatted_memories}
    except SQLAlchemyError as e:
        logging.error(f"Ошибка БД при поиске по ключевым словам для user_id {user_id}: {e}", exc_info=True)
        return {"status": "error", "reason": "database_error"}
    except Exception as e:
        logging.error(f"Неожиданная ошибка при поиске для user_id {user_id}: {e}", exc_info=True)
        return {"status": "error", "reason": "keyword_search_failed"}

async def save_chat_message(user_id: int, role: str, content: str):
    """Сохраняет одно сообщение в историю чата и обновляет счетчик ежедневных сообщений.
    Использует атомарную операцию для предотвращения race conditions.
    Добавлена санитизация текста с bleach для безопасности."""
    # Sanitize content to prevent XSS/prompt injection
    sanitized_content = bleach.clean(content, tags=[], strip=True)
    
    today = date.today()
    
    try:
        async with async_session_factory() as session:
            # Используем атомарную операцию UPDATE для счетчика
            # CASE WHEN гарантирует корректное обновление без race condition
            stmt = (
                update(UserProfile)
                .where(UserProfile.user_id == user_id)
                .values(
                    daily_message_count=(
                        # Если дата изменилась - ставим 1, иначе инкрементируем
                        1 if UserProfile.last_message_date != today 
                        else UserProfile.daily_message_count + 1
                    ),
                    last_message_date=today
                )
            )
            await session.execute(stmt)
            
            # Сохраняем сообщение в истории чата
            message = ChatHistory(user_id=user_id, role=role, content=sanitized_content)
            session.add(message)
            
            await session.commit()
    except SQLAlchemyError as e:
        logging.error(f"Ошибка БД при сохранении сообщения для user {user_id}: {e}")
        raise
        
    # Инвалидируем кэш сообщений чата
    if REDIS_CLIENT:
        try:
            cache_key = get_chat_messages_cache_key(user_id)
            await REDIS_CLIENT.delete(cache_key)
        except Exception as e:
            logging.error(f"Ошибка при удалении сообщений из Redis для пользователя {user_id}: {e}")

async def get_latest_summary(user_id: int) -> ChatSummary | None:
    """Извлекает самую последнюю сводку для пользователя."""
    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(ChatSummary)
                .where(ChatSummary.user_id == user_id)
                .order_by(ChatSummary.timestamp.desc())
                .limit(1)
            )
            return result.scalars().first()
    except SQLAlchemyError as e:
        logging.error(f"Ошибка БД при получении сводки для пользователя {user_id}: {e}", exc_info=True)
        return None

async def get_unsummarized_messages(user_id: int) -> list[ChatHistory]:
    """
    Извлекает все сообщения пользователя, которые еще не были включены в сводку.
    """
    try:
        latest_summary = await get_latest_summary(user_id)
        last_message_id = latest_summary.last_message_id if latest_summary else 0

        async with async_session_factory() as session:
            result = await session.execute(
                select(ChatHistory)
                .where(
                    ChatHistory.user_id == user_id,
                    ChatHistory.id > last_message_id
                )
                .order_by(ChatHistory.timestamp.asc())
            )
            messages = result.scalars().all()
            return messages
    except SQLAlchemyError as e:
        logging.error(f"Ошибка БД при получении несуммаризированных сообщений для пользователя {user_id}: {e}", exc_info=True)
        return []

async def get_user_context_data(user_id: int) -> tuple[UserProfile | None, ChatSummary | None, list[ChatHistory]]:
    """
    Оптимизированная функция для получения всех данных пользователя одним запросом к БД.
    Решает N+1 Query Problem.
    
    Args:
        user_id (int): Уникальный идентификатор пользователя.
        
    Returns:
        tuple: (profile, latest_summary, unsummarized_messages)
    """
    try:
        async with async_session_factory() as session:
            # Получаем профиль
            profile_result = await session.execute(
                select(UserProfile).where(UserProfile.user_id == user_id)
            )
            profile = profile_result.scalars().first()
            
            if not profile:
                return None, None, []
            
            # Получаем последнюю сводку
            summary_result = await session.execute(
                select(ChatSummary)
                .where(ChatSummary.user_id == user_id)
                .order_by(ChatSummary.timestamp.desc())
                .limit(1)
            )
            latest_summary = summary_result.scalars().first()
            last_message_id = latest_summary.last_message_id if latest_summary else 0
            
            # Получаем несуммаризированные сообщения
            messages_result = await session.execute(
                select(ChatHistory)
                .where(
                    ChatHistory.user_id == user_id,
                    ChatHistory.id > last_message_id
                )
                .order_by(ChatHistory.timestamp.asc())
            )
            messages = messages_result.scalars().all()
            
            # Кэшируем профиль в Redis если доступен
            if profile:
                profile_dict = profile.to_dict()
                for key, value in profile_dict.items():
                    if isinstance(value, (datetime, date)):
                        profile_dict[key] = value.isoformat()
                
                cache_key = get_profile_cache_key(user_id)
                await _safe_redis_set(cache_key, json.dumps(profile_dict), ex=CACHE_TTL_SECONDS)
            
            return profile, latest_summary, messages
            
    except SQLAlchemyError as e:
        logging.error(f"Ошибка БД при получении контекста пользователя {user_id}: {e}", exc_info=True)
        return None, None, []
    except Exception as e:
        logging.error(f"Неожиданная ошибка при получении контекста пользователя {user_id}: {e}", exc_info=True)
        return None, None, []
    
async def save_summary(user_id: int, summary_text: str, last_message_id: int):
    """
    Атомарно создает или обновляет сводку для пользователя (UPSERT).
    Гарантирует, что у каждого пользователя будет только одна запись в таблице.
    """
    async with async_session_factory() as session:
        # Данные для вставки или обновления
        data = {
            "summary": summary_text,
            "last_message_id": last_message_id,
            "timestamp": datetime.now() # Явно обновляем время
        }
        
        # Создаем оператор insert
        stmt = insert(ChatSummary).values(user_id=user_id, **data)
        
        # Указываем, что делать при конфликте по уникальному полю user_id
        # Мы обновляем все поля из словаря `data`
        stmt = stmt.on_conflict_do_update(
            index_elements=['user_id'],  # Поле, которое вызывает конфликт
            set_=data  # Обновляемые поля
        )
        
        await session.execute(stmt)
        await session.commit()

async def delete_summarized_messages(user_id: int, last_message_id: int):
    """Удаляет сообщения, которые уже вошли в сводку."""
    async with async_session_factory() as session:
        await session.execute(
            delete(ChatHistory)
            .where(
                ChatHistory.user_id == user_id,
                ChatHistory.id <= last_message_id
            )
        )
        await session.commit()

async def get_all_user_ids() -> list[int]:
    """
    Получает список всех уникальных user_id, которые взаимодействовали с ботом.
    Пользователи определяются по наличию записей в таблице профилей.
    
    Returns:
        list[int]: Список уникальных идентификаторов пользователей.
    """
    try:
        async with async_session_factory() as session:
            result = await session.execute(select(UserProfile.user_id))
            user_ids = [row[0] for row in result.fetchall()]
            return user_ids
    except Exception as e:
        logging.error(f"Ошибка при получении списка всех пользователей: {e}")
        return []

async def check_message_limit(user_id: int) -> dict:
    """
    Проверяет лимит сообщений для пользователя.
    
    Args:
        user_id (int): Уникальный идентификатор пользователя.
        
    Returns:
        dict: {
            "allowed": bool, 
            "message": str, 
            "count": int, 
            "limit": int,
            "plan": str
        }
    """
    from config import DAILY_MESSAGE_LIMIT
    
    profile = await get_profile(user_id)
    if not profile:
        return {
            "allowed": False, 
            "message": "Профиль не найден. Используйте /start для создания профиля.", 
            "count": 0, 
            "limit": 0,
            "plan": "none"
        }
    
    # Проверяем, не истекла ли премиум подписка
    await check_subscription_expiry(user_id)
    
    # Обновляем профиль после проверки истечения
    profile = await get_profile(user_id)
    
    # Премиум пользователи не имеют ограничений
    if (profile.subscription_plan == 'premium' and 
        profile.subscription_expires and 
        profile.subscription_expires > datetime.now()):
        return {
            "allowed": True, 
            "message": "premium", 
            "count": 0, 
            "limit": 0,
            "plan": "premium"
        }
    
    # Проверяем лимит для бесплатных пользователей
    if profile.daily_message_count >= DAILY_MESSAGE_LIMIT:
        return {
            "allowed": False, 
            "message": f"Достигнут дневной лимит сообщений ({DAILY_MESSAGE_LIMIT}). Купите премиум для безлимитного общения!",
            "count": profile.daily_message_count,
            "limit": DAILY_MESSAGE_LIMIT,
            "plan": "free"
        }
    
    return {
        "allowed": True, 
        "message": "ok", 
        "count": profile.daily_message_count, 
        "limit": DAILY_MESSAGE_LIMIT,
        "plan": "free"
    }

async def check_subscription_expiry(user_id: int) -> bool:
    """
    Проверяет и обновляет статус подписки при истечении.
    
    Args:
        user_id (int): Уникальный идентификатор пользователя.
        
    Returns:
        bool: True если подписка активна, False если истекла или отсутствует.
    """
    profile = await get_profile(user_id)
    if not profile:
        return False
    
    if (profile.subscription_plan == 'premium' and 
        profile.subscription_expires and 
        profile.subscription_expires.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc)):
        
        # Подписка истекла, переводим на бесплатный план
        await create_or_update_profile(user_id, {
            "subscription_plan": "free",
            "subscription_expires": None
        })
        logging.info(f"Подписка пользователя {user_id} истекла, переведен на бесплатный план")
        return False
    
    return profile.subscription_plan == 'premium'

async def activate_premium_subscription(user_id: int, duration_days: int = 30, charge_id: str = None) -> bool:
    """
    Активирует премиум подписку для пользователя с проверкой идемпотентности по charge_id.
    
    Args:
        user_id (int): Уникальный идентификатор пользователя.
        duration_days (int): Длительность подписки в днях.
        charge_id (str, optional): ID платежа для проверки идемпотентности.
        
    Returns:
        bool: True если подписка успешно активирована или уже была активирована.
    """
    try:
        profile = await get_profile(user_id)
        if not profile:
            # Создаем профиль если не существует
            await create_or_update_profile(user_id, {})
            profile = await get_profile(user_id)

        # Проверяем идемпотентность
        if charge_id and profile.last_processed_payment_charge_id == charge_id:
            logging.info(f"Платеж {charge_id} для пользователя {user_id} уже обработан")
            return True

        expires_at = datetime.now(timezone.utc) + timedelta(days=duration_days)
        
        update_data = {
            "subscription_plan": "premium",
            "subscription_expires": expires_at
        }
        if charge_id:
            update_data["last_processed_payment_charge_id"] = charge_id

        await create_or_update_profile(user_id, update_data)
        
        logging.info(f"Активирована премиум подписка для пользователя {user_id} до {expires_at} (charge_id: {charge_id})")
        return True
    except Exception as e:
        logging.error(f"Ошибка активации премиум подписки для пользователя {user_id}: {e}")
        return False
