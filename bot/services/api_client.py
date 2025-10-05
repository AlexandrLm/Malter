import logging
import time
from functools import wraps
from typing import Any, Dict, Optional

import httpx

from config import API_BASE_URL
from utils.retry_configs import api_client_retry

logger = logging.getLogger(__name__)

def handle_api_errors(func):
    """
    Декоратор для обработки ошибок API в обработчиках.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        message = None
        # Ищем message в args или kwargs
        for arg in list(args) + list(kwargs.values()):
            if hasattr(arg, 'answer'):
                message = arg
                break

        try:
            return await func(*args, **kwargs)
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            user_id = getattr(getattr(message, 'from_user', None), 'id', 'unknown') if message else 'unknown'
            logger.error(f"API connection error in {func.__name__} for user {user_id} after retries: {e}")
            if message:
                await message.answer("Ой, у меня что-то с интернетом... Попробуй чуть позже.")
            raise
        except Exception as e:
            user_id = getattr(getattr(message, 'from_user', None), 'id', 'unknown') if message else 'unknown'
            logger.error(f"Unexpected error in {func.__name__} for user {user_id}: {e}", exc_info=True)
            if message:
                await message.answer("Произошла непредвиденная ошибка. Попробуйте еще раз позже.")
            raise
    return wrapper

@api_client_retry
async def get_token(client: httpx.AsyncClient, user_id: int) -> str:
    """
    Получает JWT токен для пользователя.
    
    Args:
        client: HTTP клиент для запросов
        user_id: ID пользователя
        
    Returns:
        JWT токен
        
    Raises:
        httpx.HTTPStatusError: При ошибке HTTP
        httpx.RequestError: При ошибке соединения
    """
    try:
        response = await client.post(f"{API_BASE_URL}/auth", json={"user_id": user_id})
        response.raise_for_status()
        data = response.json()
        return data["access_token"]
    except Exception as e:
        logger.error(f"Error getting token for user {user_id}: {e}")
        raise

async def make_api_request(
    client: httpx.AsyncClient,
    method: str,
    endpoint: str,
    user_id: Optional[int] = None,
    token: Optional[str] = None,
    **kwargs: Any
) -> httpx.Response:
    """
    Централизованная функция для выполнения запросов к API с поддержкой JWT.
    
    Args:
        client: HTTP клиент для запросов
        method: HTTP метод (get, post, put, delete)
        endpoint: Эндпоинт API
        user_id: ID пользователя (для логирования)
        token: JWT токен для авторизации
        **kwargs: Дополнительные параметры для httpx.request
        
    Returns:
        HTTP ответ
        
    Raises:
        httpx.HTTPStatusError: При ошибке HTTP
        httpx.RequestError: При ошибке соединения
    """
    url = f"{API_BASE_URL}{endpoint}"
    headers: Dict[str, str] = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
        kwargs["headers"] = headers
    
    start_time = time.perf_counter()
    logger.info(f"API request start - user_id: {user_id}, method: {method.upper()}, endpoint: {endpoint}")
    response = await client.request(method, url, **kwargs)
    response.raise_for_status()
    latency = time.perf_counter() - start_time
    logger.info(f"API request end - user_id: {user_id}, method: {method.upper()}, endpoint: {endpoint}, latency: {latency:.2f}s")
    return response