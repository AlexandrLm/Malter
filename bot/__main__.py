import asyncio
import logging
import sys

from .bot import main

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    logging.info("Бот инициализируется...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Выход по команде (Ctrl+C)")