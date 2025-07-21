import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
API_BASE_URL = "http://127.0.0.1:8000"
# Чтобы переключиться на PostgreSQL, просто закомментируйте строку для SQLite
# и раскомментируйте строку для PostgreSQL, указав свои данные.

# Вариант 1: SQLite (файл будет создан в той же папке)
DATABASE_URL = "sqlite+aiosqlite:///profiles.db"

MODEL_NAME = "gemini-2.5-flash-lite-preview-06-17"
# Вариант 2: PostgreSQL (нужно предварительно создать базу данных)
# DATABASE_URL = "postgresql+asyncpg://user:password@localhost/db_name"

if not TELEGRAM_TOKEN or not GEMINI_KEY:
    raise ValueError("Необходимо установить TELEGRAM_BOT_TOKEN и GEMINI_API_KEY в .env файле")