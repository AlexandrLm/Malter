import logging
import httpx
from functools import wraps
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from config import API_BASE_URL

logger = logging.getLogger(__name__)

def handle_api_errors(func):
    """
    Декоратор для обработки ошибок API в обработчиках.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        message = None
        if args and isinstance(args[0], httpx.AsyncClient):
            # Если первый аргумент - client, то message - второй
            if len(args) > 1 and hasattr(args[1], 'answer'):
                message = args[1]
            client = args[0]
        else:
            # Ищем message в kwargs или args
            for arg in args:
                if hasattr(arg, 'answer'):
                    message = arg
                    break
            client = kwargs.get('client')

        try:
            return await func(*args, **kwargs)
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.error(f"API connection error in {func.__name__} for user {getattr(message, 'from_user', {}).id if message else 'unknown'} after retries: {e}")
            if message:
                await message.answer("Ой, у меня что-то с интернетом... Попробуй чуть позже.")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__} for user {getattr(message, 'from_user', {}).id if message else 'unknown'}: {e}", exc_info=True)
            if message:
                await message.answer("Произошла непредвиденная ошибка. Попробуйте еще раз позже.")
            raise
    return wrapper

@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(2),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    reraise=True
)
async def make_api_request(client: httpx.AsyncClient, method: str, endpoint: str, **kwargs):
    """Централизованная функция для выполнения запросов к API."""
    url = f"{API_BASE_URL}{endpoint}"
    logger.info(f"Вызов API: {method.upper()} {url}")
    response = await client.request(method, url, **kwargs)
    response.raise_for_status()
    return response