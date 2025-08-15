import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN")
API_BASE_URL = "http://api:8000"
# Чтобы переключиться на PostgreSQL, просто закомментируйте строку для SQLite
# и раскомментируйте строку для PostgreSQL, указав свои данные.

# Вариант 1: SQLite (файл будет создан в той же папке)
# DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///profiles.db")
# Вариант 2: PostgreSQL (нужно предварительно создать базу данных)

# Используем переменные окружения напрямую
DATABASE_URL = (
    f"postgresql+asyncpg://"
    f"{os.getenv('POSTGRES_USER', 'myuser')}:"
    f"{os.getenv('POSTGRES_PASSWORD', 'Al02082003')}@"
    f"{os.getenv('DB_HOST', 'db')}:5432/"
    f"{os.getenv('POSTGRES_DB', 'malterdb')}"
)

MODEL_NAME = "gemini-2.5-flash-lite"
# MODEL_NAME = "gemini-2.5-flash"
# MODEL_NAME = "gemini-2.5-pro"

SUMMARY_THRESHOLD = 26 # Количество сообщений для запуска суммирования
MESSAGES_TO_SUMMARIZE_COUNT = 20 # Количество сообщений, которые будут взяты для создания сводки (и последующего удаления)
CHAT_HISTORY_LIMIT = 10 # Количество последних сообщений, которые будут загружены из истории
DAILY_MESSAGE_LIMIT = 50 # Максимальное количество сообщений в день для бесплатных пользователей

if not TELEGRAM_TOKEN:
    raise ValueError("Необходимо установить TELEGRAM_BOT_TOKEN в .env файле")

# --- Gemini Client ---
# Создаем единый клиент, который будет использоваться во всем приложении
GEMINI_CLIENT = None
try:
    # Эта проверка нужна, чтобы миграции работали без установленного google-genai
    from google import genai
    
    # Используем GOOGLE_API_KEY, как было изначально
    GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
    
    if GEMINI_API_KEY:
        GEMINI_CLIENT = genai.Client(api_key=GEMINI_API_KEY)
        TTS_CLIENT = genai.Client(api_key=GEMINI_API_KEY) # Отдельный клиент для TTS
    else:
        # Не бросаем ошибку, а просто логируем, чтобы приложение не падало
        print("Переменная GOOGLE_API_KEY не установлена. Клиенты Gemini не будут инициализированы.")
        GEMINI_CLIENT = None
        TTS_CLIENT = None

except ImportError:
    print("Модуль 'google.genai' не найден. Клиенты Gemini не будут инициализированы. Это ожидаемо для окружения миграций.")
    GEMINI_CLIENT = None
    TTS_CLIENT = None
except Exception as e:
    print(f"Критическая ошибка: Не удалось инициализировать клиенты Gemini. {e}")
    GEMINI_CLIENT = None
    TTS_CLIENT = None

# --- Redis Client ---
REDIS_CLIENT = None
try:
    import redis.asyncio as redis
    REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_CLIENT = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
    print("Клиент Redis успешно инициализирован.")
except ImportError:
    print("Модуль 'redis' не найден. Redis Client не будет инициализирован.")
except Exception as e:
    print(f"Критическая ошибка: Не удалось инициализировать Redis Client. {e}")