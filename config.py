import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
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

SUMMARY_THRESHOLD = 20 # Количество сообщений для запуска суммирования

if not TELEGRAM_TOKEN:
    raise ValueError("Необходимо установить TELEGRAM_BOT_TOKEN в .env файле")

# --- Gemini Client ---
# Создаем единый клиент, который будет использоваться во всем приложении
GEMINI_CLIENT = None
try:
    # Эта проверка нужна, чтобы миграции работали без установленного google-genai
    import google.genai as genai
    
    # Используем GOOGLE_API_KEY, как было изначально
    GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
    
    if GEMINI_API_KEY:
        GEMINI_CLIENT = genai.Client(api_key=GEMINI_API_KEY)
    else:
        # Не бросаем ошибку, а просто логируем, чтобы приложение не падало
        print("Переменная GOOGLE_API_KEY не установлена. Gemini Client не будет инициализирован.")

except ImportError:
    print("Модуль 'google.genai' не найден. Gemini Client не будет инициализирован. Это ожидаемо для окружения миграций.")
except Exception as e:
    print(f"Критическая ошибка: Не удалось инициализировать Gemini Client. {e}")