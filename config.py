import os
import logging
from dotenv import load_dotenv

# Настройка логирования
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger(__name__)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN")
PAYMENT_CURRENCY = "RUB"
PAYMENT_PHOTO_URL = os.getenv("PAYMENT_PHOTO_URL", "https://via.placeholder.com/400x200/6C5CE7/FFFFFF?text=Premium+EvolveAI")
API_BASE_URL = "http://api:8000"
# Чтобы переключиться на PostgreSQL, просто закомментируйте строку для SQLite
# и раскомментируйте строку для PostgreSQL, указав свои данные.

# Вариант 1: SQLite (файл будет создан в той же папке)
# DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///profiles.db")
# Вариант 2: PostgreSQL (нужно предварительно создать базу данных)

# Используем переменные окружения напрямую
POSTGRES_USER = os.getenv('POSTGRES_USER', 'myuser')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')  # Не задаем значение по умолчанию для безопасности
DB_HOST = os.getenv('DB_HOST', 'db')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'malterdb')

# Проверяем, что пароль задан
if not POSTGRES_PASSWORD:
    raise ValueError("Необходимо установить POSTGRES_PASSWORD в .env файле")

DATABASE_URL = (
    f"postgresql+asyncpg://"
    f"{POSTGRES_USER}:"
    f"{POSTGRES_PASSWORD}@"
    f"{DB_HOST}:5432/"
    f"{POSTGRES_DB}"
)

# MODEL_NAME = "gemini-2.5-flash-lite"
# MODEL_NAME = "gemini-2.5-flash"
MODEL_NAME = "gemini-flash-latest"
# MODEL_NAME = "gemini-2.5-pro"

SUMMARY_THRESHOLD = 26 # Количество сообщений для запуска суммирования
MESSAGES_TO_SUMMARIZE_COUNT = 20 # Количество сообщений, которые будут взяты для создания сводки (и последующего удаления)
CHAT_HISTORY_LIMIT = 10 # Количество последних сообщений, которые будут загружены из истории
DAILY_MESSAGE_LIMIT = 50 # Максимальное количество сообщений в день для бесплатных пользователей

# AI Response settings
MAX_AI_ITERATIONS = int(os.getenv('MAX_AI_ITERATIONS', 3))  # Максимальное количество итераций при генерации ответа
AI_THINKING_BUDGET = int(os.getenv('AI_THINKING_BUDGET', 0))  # Бюджет для "мышления" модели
MAX_IMAGE_SIZE_MB = int(os.getenv('MAX_IMAGE_SIZE_MB', 10))  # Максимальный размер изображения в MB

# Cache settings
CACHE_TTL_SECONDS = int(os.getenv('CACHE_TTL_SECONDS', 600))  # 10 минут - время жизни кэша
REDIS_RETRY_ATTEMPTS = int(os.getenv('REDIS_RETRY_ATTEMPTS', 2))  # Количество попыток для Redis операций
REDIS_RETRY_MIN_WAIT = float(os.getenv('REDIS_RETRY_MIN_WAIT', 0.5))  # Минимальная задержка между попытками (сек)
REDIS_RETRY_MAX_WAIT = float(os.getenv('REDIS_RETRY_MAX_WAIT', 2.0))  # Максимальная задержка между попытками (сек)

# Subscription settings
SUBSCRIPTION_DEFAULT_DURATION = 30  # дней
SUBSCRIPTION_EXPIRY_CHECK_HOURS = 24  # проверка истечения подписки каждые 24 часа

TYPING_SPEED_CPS = int(os.getenv('TYPING_SPEED_CPS', 15))
MIN_TYPING_DELAY = float(os.getenv('MIN_TYPING_DELAY', 0.5))
MAX_TYPING_DELAY = float(os.getenv('MAX_TYPING_DELAY', 4.0))

# HTTPX timeout settings
HTTPX_TIMEOUT = int(os.getenv('HTTPX_TIMEOUT', 180))  # Общий таймаут в секундах
HTTPX_CONNECT_TIMEOUT = int(os.getenv('HTTPX_CONNECT_TIMEOUT', 10))  # Таймаут подключения

# --- Redis Configuration ---
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

if not TELEGRAM_TOKEN:
    raise ValueError("Необходимо установить TELEGRAM_BOT_TOKEN в .env файле")

# Проверяем другие критические переменные
if not os.getenv('GOOGLE_API_KEY'):
    logger.warning("GOOGLE_API_KEY не установлен. AI функции могут не работать.")

if not REDIS_HOST:
    logger.warning("REDIS_HOST не установлен. Кэширование может не работать.")

# --- Gemini Client ---
# Создаем единый клиент, который будет использоваться во всем приложении
GEMINI_CLIENT = None
TTS_CLIENT = None
try:
    # Эта проверка нужна, чтобы миграции работали без установленного google-genai
    from google import genai
    
    # Используем GOOGLE_API_KEY, как было изначально
    GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
    
    if GEMINI_API_KEY:
        GEMINI_CLIENT = genai.Client(api_key=GEMINI_API_KEY)
        TTS_CLIENT = genai.Client(api_key=GEMINI_API_KEY) # Отдельный клиент для TTS
        logger.info("Клиенты Gemini успешно инициализированы.")
    else:
        # Не бросаем ошибку, а просто логируем, чтобы приложение не падало
        logger.warning("Переменная GOOGLE_API_KEY не установлена. Клиенты Gemini не будут инициализированы.")
        GEMINI_CLIENT = None
        TTS_CLIENT = None

except ImportError:
    logger.info("Модуль 'google.genai' не найден. Клиенты Gemini не будут инициализированы. Это ожидаемо для окружения миграций.")
    GEMINI_CLIENT = None
    TTS_CLIENT = None
except Exception as e:
    logger.error(f"Критическая ошибка: Не удалось инициализировать клиенты Gemini. {e}")
    GEMINI_CLIENT = None
    TTS_CLIENT = None

# --- Redis Client with Connection Pool ---
REDIS_CLIENT = None
REDIS_POOL = None
try:
    import redis.asyncio as redis
    
    # Создаем connection pool для эффективного переиспользования соединений
    REDIS_POOL = redis.ConnectionPool(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True,
        max_connections=50,  # Максимум соединений в пуле
        socket_timeout=5,     # Таймаут операций
        socket_connect_timeout=5,  # Таймаут подключения
        retry_on_timeout=True,
        health_check_interval=30  # Проверка здоровья соединений каждые 30 сек
    )
    
    REDIS_CLIENT = redis.Redis(connection_pool=REDIS_POOL)
    logger.info("Redis Client с connection pool успешно инициализирован (pool_size=50).")
except ImportError:
    logger.info("Модуль 'redis' не найден. Redis Client не будет инициализирован.")
except Exception as e:
    logger.error(f"Критическая ошибка: Не удалось инициализировать Redis Client. {e}")

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise ValueError("JWT_SECRET обязателен для безопасности! Установите его в .env файле.")

# Валидация JWT_SECRET силы
if len(JWT_SECRET) < 32:
    raise ValueError(
        f"JWT_SECRET слишком короткий ({len(JWT_SECRET)} символов)! Минимум 32 символа.\n"
        "Сгенерируйте безопасный ключ: openssl rand -hex 32"
    )

# Проверка энтропии (простая эвристика)
unique_chars = len(set(JWT_SECRET))
if unique_chars < 16:
    logger.warning(
        f"JWT_SECRET имеет низкую энтропию ({unique_chars} уникальных символов). "
        "Рекомендуется использовать криптографически стойкий ключ."
    )

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60  # Token expires in 1 hour

# Encryption Configuration
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    logger.warning(
        "ENCRYPTION_KEY не установлен! Чувствительные данные будут храниться БЕЗ шифрования.\n"
        "Для production ОБЯЗАТЕЛЬНО установите ENCRYPTION_KEY.\n"
        "Генерация: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    )
elif ENCRYPTION_KEY == "generate_new_key_for_production":
    logger.error(
        "❌ ИСПОЛЬЗУЕТСЯ ДЕФОЛТНЫЙ ENCRYPTION_KEY! Это КРИТИЧЕСКАЯ уязвимость безопасности!\n"
        "Немедленно сгенерируйте новый ключ: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    )
    if os.getenv('ENVIRONMENT') == 'production':
        raise ValueError("Нельзя использовать дефолтный ENCRYPTION_KEY в production!")
