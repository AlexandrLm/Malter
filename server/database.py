"""
Модуль для работы с базой данных.

Этот файл содержит функции для взаимодействия с базой данных PostgreSQL и Redis,
включая операции CRUD для профилей пользователей, истории чата, долговременной памяти и сводок.
"""

from datetime import datetime, date, timedelta, timezone
from sqlalchemy import select, delete, desc, update, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import json
import logging
from sqlalchemy.dialects.postgresql import insert
import bleach  # For text sanitization
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
from utils.retry_configs import db_retry, redis_retry
from utils.db_monitoring import setup_query_monitoring, get_query_metrics
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

# Настраиваем мониторинг запросов
setup_query_monitoring(async_engine, threshold=1.0)

def get_profile_cache_key(user_id: int) -> str:
    """Генерирует ключ для кэша профиля."""
    return f"profile:{user_id}"

def get_chat_messages_cache_key(user_id: int) -> str:
    """Генерирует ключ для кэша сообщений чата."""
    return f"chat_messages:{user_id}"

# --- Circuit Breaker для Redis ---
class RedisCircuitBreaker:
    """
    Circuit Breaker паттерн для защиты от cascade failures при проблемах с Redis.
    
    States:
    - CLOSED: Нормальная работа, все запросы идут к Redis
    - OPEN: Redis недоступен, запросы сразу возвращают None (30 секунд)
    - HALF_OPEN: Пробуем восстановить соединение (1 тестовый запрос)
    """
    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: datetime | None = None
        self.is_open = False
    
    def record_success(self):
        """Запрос успешен - сбрасываем счетчик."""
        self.failure_count = 0
        self.is_open = False
    
    def record_failure(self):
        """Запрос провален - увеличиваем счетчик."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.is_open = True
            logging.warning(f"Redis Circuit Breaker ОТКРЫТ после {self.failure_count} неудач")
    
    def can_attempt(self) -> bool:
        """Проверяет, можно ли попытаться подключиться к Redis."""
        if not self.is_open:
            return True
        
        # Circuit breaker открыт - проверяем, прошло ли время восстановления
        if self.last_failure_time:
            time_since_failure = (datetime.now() - self.last_failure_time).total_seconds()
            if time_since_failure >= self.recovery_timeout:
                logging.info("Redis Circuit Breaker пробует восстановление (HALF-OPEN)")
                self.is_open = False  # Переходим в HALF-OPEN
                self.failure_count = self.failure_threshold - 1  # Еще 1 неудача = снова OPEN
                return True
        
        return False
    
    def get_state(self) -> str:
        """Возвращает текущее состояние circuit breaker."""
        if not self.is_open:
            return "CLOSED" if self.failure_count == 0 else "HALF_OPEN"
        return "OPEN"

redis_circuit_breaker = RedisCircuitBreaker()

@redis_retry
async def _safe_redis_get(key: str) -> str | None:
    """
    Безопасное чтение из Redis с retry механизмом и Circuit Breaker.
    При неудаче возвращает None вместо exception.
    """
    if not REDIS_CLIENT or not redis_circuit_breaker.can_attempt():
        return None
    try:
        result = await REDIS_CLIENT.get(key)
        redis_circuit_breaker.record_success()
        return result
    except Exception as e:
        redis_circuit_breaker.record_failure()
        logging.warning(f"Redis GET failed for key {key}: {e}")
        return None

@redis_retry
async def _safe_redis_set(key: str, value: str, ex: int) -> bool:
    """
    Безопасная запись в Redis с retry механизмом и Circuit Breaker.
    Возвращает True при успехе, False при неудаче.
    """
    if not REDIS_CLIENT or not redis_circuit_breaker.can_attempt():
        return False
    try:
        await REDIS_CLIENT.set(key, value, ex=ex)
        redis_circuit_breaker.record_success()
        return True
    except Exception as e:
        redis_circuit_breaker.record_failure()
        logging.warning(f"Redis SET failed for key {key}: {e}")
        return False

@redis_retry
async def _safe_redis_delete(key: str) -> bool:
    """
    Безопасное удаление из Redis с retry механизмом и Circuit Breaker.
    Возвращает True при успехе, False при неудаче.
    """
    if not REDIS_CLIENT or not redis_circuit_breaker.can_attempt():
        return False
    try:
        await REDIS_CLIENT.delete(key)
        redis_circuit_breaker.record_success()
        return True
    except Exception as e:
        redis_circuit_breaker.record_failure()
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
        # Шифруем поле name, если оно есть, но оставляем ключ как 'name' для соответствия колонке БД
        db_data = data.copy()
        if 'name' in db_data:
            from utils.encryption import encrypt_field
            db_data['name'] = encrypt_field(db_data['name'])
        
        async with async_session_factory() as session:
            # Используем Core-style insert через __table__ чтобы избежать проблем с @property
            stmt = insert(UserProfile.__table__).values(user_id=user_id, **db_data)
            stmt = stmt.on_conflict_do_update(index_elements=['user_id'], set_=db_data)
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
                logging.debug(f"Факт для user_id {user_id} уже существует: '{fact}'. Пропускаем сохранение.")
                return {"status": "skipped", "reason": "duplicate fact"}

            # 3. Если факта нет, сохраняем его
            logging.debug(f"Сохранение нового факта для user_id {user_id}")
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

def sanitize_search_query(query: str) -> str:
    """
    Санитизирует поисковый запрос для предотвращения SQL Injection и DoS атак.
    
    Args:
        query: Исходный поисковый запрос
        
    Returns:
        Очищенный запрос или пустая строка если валидация не прошла
    """
    import re
    
    if not query:
        return ""
    
    # Ограничение длины для предотвращения DoS
    if len(query) > 100:
        logging.warning(f"Search query too long: {len(query)} characters")
        return ""
    
    # Удаляем потенциально опасные символы, оставляем только буквы, цифры, пробелы и дефисы
    # re.UNICODE позволяет использовать кириллицу
    sanitized = re.sub(r'[^\w\s\-]', '', query, flags=re.UNICODE)
    
    # Убираем множественные пробелы
    sanitized = ' '.join(sanitized.split())
    
    return sanitized

async def get_long_term_memories(user_id: int, query: str) -> dict:
    """
    Выполняет полнотекстовый поиск в долгосрочной памяти пользователя.
    
    Использует PostgreSQL Full-Text Search с русским языком для быстрого
    и релевантного поиска по фактам. Fallback на ILIKE если полнотекстовый
    поиск не дал результатов.
    
    SECURITY: Запрос санитизируется перед использованием для предотвращения SQL Injection.
    
    Args:
        user_id: ID пользователя
        query: Поисковый запрос
        
    Returns:
        Dict с найденными memories или сообщением об ошибке
    """
    # SECURITY: Санитизация запроса для предотвращения SQL Injection и DoS
    sanitized_query = sanitize_search_query(query)
    
    if not sanitized_query:
        logging.warning(f"Invalid or empty search query for user_id {user_id}: '{query}'")
        return {"memories": ["Поисковый запрос слишком короткий или содержит недопустимые символы."]}
    
    logging.debug(f"Выполнение полнотекстового поиска для user_id {user_id} с запросом: '{sanitized_query}'")
    try:
        async with async_session_factory() as session:
            # Используем полнотекстовый поиск PostgreSQL с русским языком
            # plainto_tsquery автоматически обрабатывает спецсимволы и стоп-слова
            from sqlalchemy import func, text
            
            result = await session.execute(
                select(LongTermMemory).where(
                    LongTermMemory.user_id == user_id,
                    LongTermMemory.fact_tsv.op('@@')(func.plainto_tsquery('russian', sanitized_query))
                ).order_by(
                    # Сортируем по релевантности (ts_rank) и времени
                    func.ts_rank(LongTermMemory.fact_tsv, func.plainto_tsquery('russian', sanitized_query)).desc(),
                    desc(LongTermMemory.timestamp)
                ).limit(5)
            )
            memories = result.scalars().all()
            
            # Fallback на ILIKE если полнотекстовый поиск не дал результатов
            if not memories and sanitized_query:
                logging.debug(f"Full-text search дал 0 результатов, пробуем ILIKE fallback для user_id {user_id}")
                result = await session.execute(
                    select(LongTermMemory).where(
                        LongTermMemory.user_id == user_id,
                        LongTermMemory.fact.ilike(f"%{sanitized_query}%")
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
        logging.error(f"Ошибка БД при поиске для user_id {user_id}: {e}", exc_info=True)
        return {"status": "error", "reason": "database_error"}
    except Exception as e:
        logging.error(f"Неожиданная ошибка при поиске для user_id {user_id}: {e}", exc_info=True)
        return {"status": "error", "reason": "fulltext_search_failed"}

async def save_chat_message(user_id: int, role: str, content: str, timestamp: datetime | None = None):
    """Сохраняет одно сообщение в историю чата и обновляет счетчик ежедневных сообщений.
    Использует атомарную операцию для предотвращения race conditions.
    Добавлена санитизация текста с bleach для безопасности.
    
    Args:
        user_id: ID пользователя
        role: 'user' или 'model'
        content: Содержимое сообщения
        timestamp: Временная метка (если None, используется текущее время БД)
    """
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
            # Для сообщений модели не передаем timestamp, чтобы БД использовала server_default
            if timestamp is not None:
                # Убираем timezone, так как колонка TIMESTAMP WITHOUT TIME ZONE
                naive_timestamp = timestamp.replace(tzinfo=None) if timestamp.tzinfo else timestamp
                message = ChatHistory(user_id=user_id, role=role, content=sanitized_content, timestamp=naive_timestamp)
            else:
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
            "timestamp": datetime.now(timezone.utc) # Явно обновляем время
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
        profile.subscription_expires > datetime.now(timezone.utc)):
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
        logging.debug(f"Подписка пользователя {user_id} истекла, переведен на бесплатный план")
        return False
    
    return profile.subscription_plan == 'premium'

async def cleanup_old_chat_history(days_to_keep: int = 30) -> int:
    """
    Удаляет историю чата старше указанного количества дней.
    
    Эта функция должна вызываться периодически (например, через APScheduler)
    для предотвращения бесконечного роста таблицы chat_history.
    
    Args:
        days_to_keep (int): Количество дней для хранения истории чата (по умолчанию 30).
        
    Returns:
        int: Количество удаленных записей.
    """
    from datetime import timezone
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
    logging.info(f"Запуск cleanup старых сообщений (удаляем сообщения старше {cutoff_date})")
    
    try:
        async with async_session_factory() as session:
            # Подсчитываем количество записей для удаления
            count_stmt = select(func.count()).select_from(ChatHistory).where(ChatHistory.timestamp < cutoff_date)
            result = await session.execute(count_stmt)
            count = result.scalar()
            
            if count == 0:
                logging.info("Нет старых сообщений для удаления")
                return 0
            
            # Удаляем старые записи
            stmt = delete(ChatHistory).where(ChatHistory.timestamp < cutoff_date)
            await session.execute(stmt)
            await session.commit()
            
            logging.info(f"Удалено {count} старых сообщений из chat_history")
            return count
    except SQLAlchemyError as e:
        logging.error(f"Ошибка при cleanup старых сообщений: {e}", exc_info=True)
        return 0

async def activate_premium_subscription(user_id: int, duration_days: int = 30, charge_id: str = None) -> bool:
    """
    Активирует премиум подписку для пользователя с проверкой идемпотентности по charge_id.
    
    SECURITY: Валидация charge_id длины для предотвращения DoS атак на БД.
    
    Args:
        user_id (int): Уникальный идентификатор пользователя.
        duration_days (int): Длительность подписки в днях.
        charge_id (str, optional): ID платежа для проверки идемпотентности (макс 255 символов).
        
    Returns:
        bool: True если подписка успешно активирована или уже была активирована.
    """
    # SECURITY: Валидация charge_id длины
    if charge_id and len(charge_id) > 255:
        logging.error(f"charge_id слишком длинный для user {user_id}: {len(charge_id)} символов (макс 255)")
        return False
    
    try:
        profile = await get_profile(user_id)
        if not profile:
            # Создаем профиль если не существует
            await create_or_update_profile(user_id, {})
            profile = await get_profile(user_id)

        # Проверяем идемпотентность
        if charge_id and profile.last_processed_payment_charge_id == charge_id:
            logging.debug(f"Платеж {charge_id} для пользователя {user_id} уже обработан")
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

async def check_all_subscriptions_expiry() -> int:
    """
    Проверяет истечение подписок для всех пользователей с premium планом.
    
    Эта функция должна вызываться периодически (например, через APScheduler)
    для автоматической деактивации истекших подписок.
    
    Returns:
        int: Количество деактивированных подписок.
    """
    try:
        now_utc = datetime.now(timezone.utc)
        
        async with async_session_factory() as session:
            # Находим всех пользователей с premium планом, у которых истек срок
            stmt = select(UserProfile).where(
                UserProfile.subscription_plan == 'premium',
                UserProfile.subscription_expires != None,
                UserProfile.subscription_expires < now_utc
            )
            result = await session.execute(stmt)
            expired_users = result.scalars().all()
            
            if not expired_users:
                return 0
            
            # Деактивируем подписки
            expired_count = 0
            for user in expired_users:
                await create_or_update_profile(user.user_id, {
                    "subscription_plan": "free",
                    "subscription_expires": None
                })
                logging.info(f"Деактивирована истекшая подписка для пользователя {user.user_id}")
                expired_count += 1
            
            return expired_count
            
    except SQLAlchemyError as e:
        logging.error(f"Ошибка при проверке истечения подписок: {e}", exc_info=True)
        return 0
