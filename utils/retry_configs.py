"""
Централизованные конфигурации retry декораторов для проекта.

Этот модуль содержит переиспользуемые retry стратегии для разных типов операций:
- Запросы к БД (PostgreSQL)
- Запросы к кэшу (Redis)
- Запросы к внешним API (Gemini, httpx)
- TTS операции

Использование:
    from utils.retry_configs import db_retry, redis_retry, api_retry
    
    @db_retry
    async def my_database_function():
        ...
"""

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    wait_fixed,
    retry_if_exception_type,
    before_sleep_log
)
from sqlalchemy.exc import SQLAlchemyError
from redis.exceptions import ConnectionError as RedisConnectionError, RedisError
import httpx
import logging

logger = logging.getLogger(__name__)

# --- Database Retry Configuration ---
db_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(SQLAlchemyError),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)

# --- Redis Retry Configuration ---
redis_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type((RedisConnectionError, RedisError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=False  # Не критично - просто пропускаем кэш
)

# --- External API Retry Configuration (Gemini, httpx) ---
api_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError, ConnectionError, TimeoutError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)

# --- API Client Retry (короткие интервалы для внутренних API) ---
api_client_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(2),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)

# --- TTS Retry Configuration ---
tts_retry = retry(
    stop=stop_after_attempt(2),  # TTS не критично - максимум 2 попытки
    wait=wait_fixed(1),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError, Exception)),
    before_sleep=before_sleep_log(logger, logging.DEBUG),
    reraise=False  # При неудаче просто не возвращаем голос
)
