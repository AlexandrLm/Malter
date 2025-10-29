import os
import logging
from dotenv import load_dotenv

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger(__name__)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN")
PAYMENT_CURRENCY = "RUB"
PAYMENT_PHOTO_URL = os.getenv("PAYMENT_PHOTO_URL", "https://via.placeholder.com/400x200/6C5CE7/FFFFFF?text=Premium+EvolveAI")
API_BASE_URL = "http://api:8000"
POSTGRES_USER = os.getenv('POSTGRES_USER', 'myuser')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')  # Не задаем значение по умолчанию для безопасности
DB_HOST = os.getenv('DB_HOST', 'db')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'malterdb')

if not POSTGRES_PASSWORD:
    raise ValueError("Необходимо установить POSTGRES_PASSWORD в .env файле")

DATABASE_URL = (
    f"postgresql+asyncpg://"
    f"{POSTGRES_USER}:"
    f"{POSTGRES_PASSWORD}@"
    f"{DB_HOST}:5432/"
    f"{POSTGRES_DB}"
)

MODEL_NAME = "gemini-flash-latest"
SUMMARIZER_MODEL_NAME = os.getenv("SUMMARIZER_MODEL_NAME", "gemma-3-27b-it")
TTS_VOICE_NAME = os.getenv("TTS_VOICE_NAME", "leda")

SUMMARY_THRESHOLD = 26
MESSAGES_TO_SUMMARIZE_COUNT = 20

CHAT_HISTORY_LIMIT_FREE = 5
CHAT_HISTORY_LIMIT_PREMIUM = 12

MAX_EMOTIONAL_MEMORIES_PER_USER = int(os.getenv('MAX_EMOTIONAL_MEMORIES_PER_USER', 100))
DAILY_MESSAGE_LIMIT = 50

MAX_AI_ITERATIONS = int(os.getenv('MAX_AI_ITERATIONS', 3))
AI_THINKING_BUDGET = int(os.getenv('AI_THINKING_BUDGET', 0))
MAX_IMAGE_SIZE_MB = int(os.getenv('MAX_IMAGE_SIZE_MB', 10))

CACHE_TTL_SECONDS = int(os.getenv('CACHE_TTL_SECONDS', 600))
REDIS_RETRY_ATTEMPTS = int(os.getenv('REDIS_RETRY_ATTEMPTS', 2))
REDIS_RETRY_MIN_WAIT = float(os.getenv('REDIS_RETRY_MIN_WAIT', 0.5))
REDIS_RETRY_MAX_WAIT = float(os.getenv('REDIS_RETRY_MAX_WAIT', 2.0))

SUBSCRIPTION_DEFAULT_DURATION = 30
SUBSCRIPTION_EXPIRY_CHECK_HOURS = 24

TYPING_SPEED_CPS = int(os.getenv('TYPING_SPEED_CPS', 15))
MIN_TYPING_DELAY = float(os.getenv('MIN_TYPING_DELAY', 0.5))
MAX_TYPING_DELAY = float(os.getenv('MAX_TYPING_DELAY', 4.0))

HTTPX_TIMEOUT = int(os.getenv('HTTPX_TIMEOUT', 180))
HTTPX_CONNECT_TIMEOUT = int(os.getenv('HTTPX_CONNECT_TIMEOUT', 10))

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

if not TELEGRAM_TOKEN:
    raise ValueError("Необходимо установить TELEGRAM_BOT_TOKEN в .env файле")

if not os.getenv('GOOGLE_API_KEY'):
    logger.warning("GOOGLE_API_KEY не установлен. AI функции могут не работать.")

if not REDIS_HOST:
    logger.warning("REDIS_HOST не установлен. Кэширование может не работать.")

GEMINI_CLIENT = None
TTS_CLIENT = None
try:
    from google import genai
    GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")

    if GEMINI_API_KEY:
        GEMINI_CLIENT = genai.Client(api_key=GEMINI_API_KEY)
        TTS_CLIENT = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("Клиенты Gemini успешно инициализированы.")
    else:
        logger.warning("Переменная GOOGLE_API_KEY не установлена. Клиенты Gemini не будут инициализированы.")
        GEMINI_CLIENT = None
        TTS_CLIENT = None

except ImportError:
    logger.info("Модуль 'google.genai' не найден. Клиенты Gemini не будут инициализированы.")
    GEMINI_CLIENT = None
    TTS_CLIENT = None
except Exception as e:
    logger.error(f"Не удалось инициализировать клиенты Gemini. {e}")
    GEMINI_CLIENT = None
    TTS_CLIENT = None

REDIS_CLIENT = None
REDIS_POOL = None
try:
    import redis.asyncio as redis

    REDIS_POOL = redis.ConnectionPool(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
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

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise ValueError("JWT_SECRET обязателен для безопасности! Установите его в .env файле.")

if len(JWT_SECRET) < 32:
    raise ValueError(
        f"JWT_SECRET слишком короткий ({len(JWT_SECRET)} символов)! Минимум 32 символа.\n"
        "Сгенерируйте безопасный ключ: openssl rand -hex 32"
    )

unique_chars = len(set(JWT_SECRET))
if unique_chars < 16:
    logger.warning(f"JWT_SECRET имеет низкую энтропию ({unique_chars} уникальных символов).")

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60

ADMIN_USER_IDS_STR = os.getenv('ADMIN_USER_IDS', '')
ADMIN_USER_IDS = set()
if ADMIN_USER_IDS_STR:
    try:
        ADMIN_USER_IDS = set(map(int, ADMIN_USER_IDS_STR.split(',')))
        logger.info(f"Загружено {len(ADMIN_USER_IDS)} admin user ID(s)")
    except ValueError as e:
        logger.error(f"Ошибка парсинга ADMIN_USER_IDS: {e}")
else:
    logger.warning("ADMIN_USER_IDS не установлен. Admin endpoints будут недоступны.")

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    logger.warning("ENCRYPTION_KEY не установлен! Чувствительные данные будут храниться БЕЗ шифрования.")
elif ENCRYPTION_KEY == "generate_new_key_for_production":
    logger.error("❌ ИСПОЛЬЗУЕТСЯ ДЕФОЛТНЫЙ ENCRYPTION_KEY! Это КРИТИЧЕСКАЯ уязвимость безопасности!")
    if os.getenv('ENVIRONMENT') == 'production':
        raise ValueError("Нельзя использовать дефолтный ENCRYPTION_KEY в production!")
else:
    try:
        from cryptography.fernet import Fernet
        Fernet(ENCRYPTION_KEY.encode())
        logger.info("ENCRYPTION_KEY валиден и успешно загружен")
    except Exception as e:
        logger.error(f"❌ ENCRYPTION_KEY имеет неверный формат: {e}")
        raise ValueError(f"ENCRYPTION_KEY имеет неверный формат Fernet key: {e}")
