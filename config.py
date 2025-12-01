import os
import logging
from typing import Optional, Set
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# ============================================================================
# SETTINGS CLASS
# ============================================================================

from dotenv import load_dotenv
load_dotenv('.env', encoding='utf-8')

class Settings(BaseSettings):
    """
    Application configuration using Pydantic Settings.
    Reads from environment variables and .env file.
    """
    model_config = SettingsConfigDict(env_file=None, extra='ignore')

    # --- General ---
    log_level: str = Field("DEBUG", validation_alias="LOG_LEVEL")
    environment: str = Field("development", validation_alias="ENVIRONMENT")

    # --- Telegram ---
    telegram_token: str = Field(..., validation_alias="TELEGRAM_BOT_TOKEN")
    admin_user_ids_str: str = Field("", validation_alias="ADMIN_USER_IDS")

    # --- Payment ---
    payment_provider_token: Optional[str] = Field(None, validation_alias="PAYMENT_PROVIDER_TOKEN")
    payment_currency: str = "RUB"
    payment_photo_url: str = Field("https://via.placeholder.com/400x200/6C5CE7/FFFFFF?text=Premium+EvolveAI", validation_alias="PAYMENT_PHOTO_URL")

    # --- Database ---
    postgres_user: str = Field("myuser", validation_alias="POSTGRES_USER")
    postgres_password: str = Field(..., validation_alias="POSTGRES_PASSWORD")
    db_host: str = Field("db", validation_alias="DB_HOST")
    postgres_db: str = Field("malterdb", validation_alias="POSTGRES_DB")

    # --- Redis ---
    redis_host: str = Field("localhost", validation_alias="REDIS_HOST")
    redis_port: int = Field(6379, validation_alias="REDIS_PORT")
    redis_db: int = Field(0, validation_alias="REDIS_DB")
    cache_ttl_seconds: int = Field(600, validation_alias="CACHE_TTL_SECONDS")
    redis_retry_attempts: int = Field(2, validation_alias="REDIS_RETRY_ATTEMPTS")
    redis_retry_min_wait: float = Field(0.5, validation_alias="REDIS_RETRY_MIN_WAIT")
    redis_retry_max_wait: float = Field(2.0, validation_alias="REDIS_RETRY_MAX_WAIT")

    # --- AI / Gemini ---
    google_api_key: Optional[str] = Field(None, validation_alias="GOOGLE_API_KEY")
    gemini_model_name: str = "gemini-flash-latest"
    summarizer_model_name: str = Field("gemma-3-27b-it", validation_alias="SUMMARIZER_MODEL_NAME")
    tts_voice_name: str = Field("leda", validation_alias="TTS_VOICE_NAME")
    max_ai_iterations: int = Field(3, validation_alias="MAX_AI_ITERATIONS")
    ai_thinking_budget: int = Field(0, validation_alias="AI_THINKING_BUDGET")
    max_image_size_mb: int = Field(10, validation_alias="MAX_IMAGE_SIZE_MB")

    # --- Security ---
    jwt_secret: str = Field(..., min_length=32, validation_alias="JWT_SECRET")
    encryption_key: str = Field(..., validation_alias="ENCRYPTION_KEY")

    # --- Application Logic ---
    api_base_url: str = "http://api:8000"
    summary_threshold: int = 26
    messages_to_summarize_count: int = 20
    chat_history_limit_free: int = 5
    chat_history_limit_premium: int = 12
    max_emotional_memories_per_user: int = Field(100, validation_alias="MAX_EMOTIONAL_MEMORIES_PER_USER")
    daily_message_limit: int = 50
    subscription_default_duration: int = 30
    subscription_expiry_check_hours: int = 24
    typing_speed_cps: int = Field(15, validation_alias="TYPING_SPEED_CPS")
    min_typing_delay: float = Field(0.5, validation_alias="MIN_TYPING_DELAY")
    max_typing_delay: float = Field(4.0, validation_alias="MAX_TYPING_DELAY")
    httpx_timeout: int = Field(180, validation_alias="HTTPX_TIMEOUT")
    httpx_connect_timeout: int = Field(10, validation_alias="HTTPX_CONNECT_TIMEOUT")

    @computed_field
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://"
            f"{self.postgres_user}:"
            f"{self.postgres_password}@"
            f"{self.db_host}:5432/"
            f"{self.postgres_db}"
        )

    @computed_field
    def admin_user_ids(self) -> Set[int]:
        if not self.admin_user_ids_str:
            return set()
        try:
            return set(map(int, self.admin_user_ids_str.split(',')))
        except ValueError:
            return set()

# Initialize Settings
# This will raise ValidationError if required fields are missing
try:
    settings = Settings()
except Exception as e:
    print(f"❌ Configuration Error: {e}")
    raise

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)

# ============================================================================
# EXPORTED VARIABLES (Backward Compatibility)
# ============================================================================

LOG_LEVEL = settings.log_level
TELEGRAM_TOKEN = settings.telegram_token
PAYMENT_PROVIDER_TOKEN = settings.payment_provider_token
PAYMENT_CURRENCY = settings.payment_currency
PAYMENT_PHOTO_URL = settings.payment_photo_url
API_BASE_URL = settings.api_base_url
POSTGRES_USER = settings.postgres_user
POSTGRES_PASSWORD = settings.postgres_password
DB_HOST = settings.db_host
POSTGRES_DB = settings.postgres_db
DATABASE_URL = settings.database_url

MODEL_NAME = settings.gemini_model_name
SUMMARIZER_MODEL_NAME = settings.summarizer_model_name
TTS_VOICE_NAME = settings.tts_voice_name
SUMMARY_THRESHOLD = settings.summary_threshold
MESSAGES_TO_SUMMARIZE_COUNT = settings.messages_to_summarize_count
CHAT_HISTORY_LIMIT_FREE = settings.chat_history_limit_free
CHAT_HISTORY_LIMIT_PREMIUM = settings.chat_history_limit_premium
MAX_EMOTIONAL_MEMORIES_PER_USER = settings.max_emotional_memories_per_user
DAILY_MESSAGE_LIMIT = settings.daily_message_limit
MAX_AI_ITERATIONS = settings.max_ai_iterations
AI_THINKING_BUDGET = settings.ai_thinking_budget
MAX_IMAGE_SIZE_MB = settings.max_image_size_mb

CACHE_TTL_SECONDS = settings.cache_ttl_seconds
REDIS_RETRY_ATTEMPTS = settings.redis_retry_attempts
REDIS_RETRY_MIN_WAIT = settings.redis_retry_min_wait
REDIS_RETRY_MAX_WAIT = settings.redis_retry_max_wait
REDIS_HOST = settings.redis_host
REDIS_PORT = settings.redis_port
REDIS_DB = settings.redis_db

SUBSCRIPTION_DEFAULT_DURATION = settings.subscription_default_duration
SUBSCRIPTION_EXPIRY_CHECK_HOURS = settings.subscription_expiry_check_hours
TYPING_SPEED_CPS = settings.typing_speed_cps
MIN_TYPING_DELAY = settings.min_typing_delay
MAX_TYPING_DELAY = settings.max_typing_delay
HTTPX_TIMEOUT = settings.httpx_timeout
HTTPX_CONNECT_TIMEOUT = settings.httpx_connect_timeout

JWT_SECRET = settings.jwt_secret
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60
ADMIN_USER_IDS = settings.admin_user_ids
ENCRYPTION_KEY = settings.encryption_key

# ============================================================================
# CLIENT INITIALIZATION
# ============================================================================

# Security Checks
unique_chars = len(set(JWT_SECRET))
if unique_chars < 16:
    logger.warning(f"JWT_SECRET имеет низкую энтропию ({unique_chars} уникальных символов).")

if ENCRYPTION_KEY == "generate_new_key_for_production":
    logger.error("❌ ИСПОЛЬЗУЕТСЯ ДЕФОЛТНЫЙ ENCRYPTION_KEY! Это КРИТИЧЕСКАЯ уязвимость безопасности!")
    if settings.environment == 'production':
        raise ValueError("Нельзя использовать дефолтный ENCRYPTION_KEY в production!")
else:
    try:
        from cryptography.fernet import Fernet
        Fernet(ENCRYPTION_KEY.encode())
        logger.info("ENCRYPTION_KEY валиден и успешно загружен")
    except Exception as e:
        logger.error(f"❌ ENCRYPTION_KEY имеет неверный формат: {e}")
        raise ValueError(f"ENCRYPTION_KEY имеет неверный формат Fernet key: {e}")

# Gemini Client
GEMINI_CLIENT = None
TTS_CLIENT = None
if settings.google_api_key:
    try:
        from google import genai
        GEMINI_CLIENT = genai.Client(api_key=settings.google_api_key)
        TTS_CLIENT = genai.Client(api_key=settings.google_api_key)
        logger.info("Клиенты Gemini успешно инициализированы.")
    except ImportError:
        logger.info("Модуль 'google.genai' не найден. Клиенты Gemini не будут инициализированы.")
    except Exception as e:
        logger.error(f"Не удалось инициализировать клиенты Gemini. {e}")
else:
    logger.warning("GOOGLE_API_KEY не установлен. AI функции могут не работать.")

# Redis Client
REDIS_CLIENT = None
REDIS_POOL = None
if settings.redis_host:
    try:
        import redis.asyncio as redis
        REDIS_POOL = redis.ConnectionPool(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
            max_connections=50,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30
        )
        REDIS_CLIENT = redis.Redis(connection_pool=REDIS_POOL)
        logger.info("Redis Client успешно инициализирован (pool_size=50).")
    except ImportError:
        logger.info("Модуль 'redis' не найден. Redis Client не будет инициализирован.")
    except Exception as e:
        logger.error(f"Не удалось инициализировать Redis Client. {e}")
else:
    logger.warning("REDIS_HOST не установлен. Кэширование может не работать.")
