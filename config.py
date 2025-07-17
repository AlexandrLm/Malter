import os
from dotenv import load_dotenv

load_dotenv()

# TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_TOKEN = "7624247836:AAFV8L_w_59yhk4q9O3bNJGF-a7xHddtwXg"
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# Чтобы переключиться на PostgreSQL, просто закомментируйте строку для SQLite
# и раскомментируйте строку для PostgreSQL, указав свои данные.

# Вариант 1: SQLite (файл будет создан в той же папке)
DATABASE_URL = "sqlite+aiosqlite:///profiles.db"

# Вариант 2: PostgreSQL (нужно предварительно создать базу данных)
# DATABASE_URL = "postgresql+asyncpg://user:password@localhost/db_name"

if not TELEGRAM_TOKEN or not GEMINI_KEY:
    raise ValueError("Необходимо установить TELEGRAM_BOT_TOKEN и GEMINI_API_KEY в .env файле")