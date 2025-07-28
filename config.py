import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_KEY = os.getenv("GOOGLE_API_KEY")
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

if not TELEGRAM_TOKEN or not GEMINI_KEY:
    raise ValueError("Необходимо установить TELEGRAM_BOT_TOKEN и GEMINI_API_KEY в .env файле")