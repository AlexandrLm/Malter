"""
Модуль для работы с Redis кэшем.

Предоставляет декораторы и функции для кэширования данных с автоматическим
управлением TTL и инвалидацией кэша.
"""

import json
import logging
import functools
from typing import Any, Callable, Optional
from datetime import timedelta

from config import REDIS_CLIENT, CACHE_TTL_SECONDS

logger = logging.getLogger(__name__)


def get_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Генерирует уникальный ключ кэша на основе префикса и аргументов.
    
    Args:
        prefix: Префикс ключа (например, 'profile', 'chat_history')
        *args: Позиционные аргументы функции
        **kwargs: Именованные аргументы функции
        
    Returns:
        str: Уникальный ключ для кэша
    """
    # Используем только первые несколько аргументов для ключа (обычно user_id)
    key_parts = [prefix]
    
    # Добавляем позиционные аргументы
    for arg in args:
        if isinstance(arg, (int, str)):
            key_parts.append(str(arg))
    
    # Добавляем важные kwargs (если есть)
    for k, v in sorted(kwargs.items()):
        if k in ['user_id', 'limit', 'offset']:
            key_parts.append(f"{k}:{v}")
    
    return ":".join(key_parts)


def cached(
    prefix: str,
    ttl: Optional[int] = None,
    key_builder: Optional[Callable] = None
):
    """
    Декоратор для кэширования результатов функций в Redis.
    
    Args:
        prefix: Префикс для ключа кэша
        ttl: Время жизни кэша в секундах (по умолчанию CACHE_TTL_SECONDS)
        key_builder: Кастомная функция для генерации ключа
        
    Example:
        @cached(prefix="profile", ttl=300)
        async def get_profile(user_id: int):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if not REDIS_CLIENT:
                # Redis недоступен - выполняем функцию напрямую
                return await func(*args, **kwargs)
            
            # Генерируем ключ кэша
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                cache_key = get_cache_key(prefix, *args, **kwargs)
            
            try:
                # Пытаемся получить из кэша
                cached_value = await REDIS_CLIENT.get(cache_key)
                if cached_value:
                    logger.debug(f"Cache HIT: {cache_key}")
                    # Десериализуем JSON
                    return json.loads(cached_value)
                
                logger.debug(f"Cache MISS: {cache_key}")
                
            except Exception as e:
                logger.warning(f"Redis GET error for {cache_key}: {e}")
            
            # Выполняем функцию
            result = await func(*args, **kwargs)
            
            # Кэшируем результат
            if result is not None:
                try:
                    cache_ttl = ttl if ttl is not None else CACHE_TTL_SECONDS
                    serialized = json.dumps(result, default=str)  # default=str для datetime
                    await REDIS_CLIENT.set(cache_key, serialized, ex=cache_ttl)
                    logger.debug(f"Cached: {cache_key} (TTL: {cache_ttl}s)")
                except Exception as e:
                    logger.warning(f"Redis SET error for {cache_key}: {e}")
            
            return result
        
        return wrapper
    return decorator


async def invalidate_cache(prefix: str, *args, **kwargs) -> bool:
    """
    Инвалидирует кэш по ключу.
    
    Args:
        prefix: Префикс ключа кэша
        *args, **kwargs: Аргументы для построения ключа
        
    Returns:
        bool: True если удаление успешно
        
    Example:
        await invalidate_cache("profile", user_id=123)
    """
    if not REDIS_CLIENT:
        return False
    
    cache_key = get_cache_key(prefix, *args, **kwargs)
    
    try:
        await REDIS_CLIENT.delete(cache_key)
        logger.debug(f"Cache invalidated: {cache_key}")
        return True
    except Exception as e:
        logger.warning(f"Redis DELETE error for {cache_key}: {e}")
        return False


async def invalidate_pattern(pattern: str) -> int:
    """
    Удаляет все ключи, соответствующие шаблону.
    
    Args:
        pattern: Шаблон для поиска ключей (например, "profile:*")
        
    Returns:
        int: Количество удаленных ключей
        
    Example:
        # Удалить все профили
        await invalidate_pattern("profile:*")
        
        # Удалить всю историю чата конкретного пользователя
        await invalidate_pattern(f"chat_messages:{user_id}:*")
    """
    if not REDIS_CLIENT:
        return 0
    
    try:
        # Находим все ключи по шаблону
        cursor = 0
        deleted_count = 0
        
        while True:
            cursor, keys = await REDIS_CLIENT.scan(cursor, match=pattern, count=100)
            if keys:
                deleted_count += await REDIS_CLIENT.delete(*keys)
            
            if cursor == 0:
                break
        
        logger.info(f"Invalidated {deleted_count} keys matching pattern: {pattern}")
        return deleted_count
        
    except Exception as e:
        logger.error(f"Error invalidating pattern {pattern}: {e}")
        return 0


async def get_cache_stats() -> dict[str, Any]:
    """
    Получает статистику использования кэша.
    
    Returns:
        dict: Статистика Redis (memory, keys count, hit rate, etc.)
    """
    if not REDIS_CLIENT:
        return {"status": "disabled"}
    
    try:
        info = await REDIS_CLIENT.info()
        stats = await REDIS_CLIENT.info('stats')
        
        return {
            "status": "active",
            "used_memory_human": info.get("used_memory_human"),
            "total_keys": info.get("db0", {}).get("keys", 0),
            "keyspace_hits": stats.get("keyspace_hits", 0),
            "keyspace_misses": stats.get("keyspace_misses", 0),
            "hit_rate": _calculate_hit_rate(
                stats.get("keyspace_hits", 0),
                stats.get("keyspace_misses", 0)
            ),
            "connected_clients": info.get("connected_clients", 0),
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {"status": "error", "message": str(e)}


def _calculate_hit_rate(hits: int, misses: int) -> float:
    """Вычисляет процент попаданий в кэш."""
    total = hits + misses
    if total == 0:
        return 0.0
    return round((hits / total) * 100, 2)


async def warm_up_cache(warm_up_functions: list[Callable]) -> dict[str, int]:
    """
    Прогревает кэш, вызывая список функций.
    Используется при старте приложения для предзагрузки часто используемых данных.
    
    Args:
        warm_up_functions: Список async функций для вызова
        
    Returns:
        dict: Статистика прогрева (success_count, error_count)
        
    Example:
        async def preload_popular_profiles():
            for user_id in [1, 2, 3, 100, 200]:
                await get_profile(user_id)
        
        await warm_up_cache([preload_popular_profiles])
    """
    results = {"success": 0, "errors": 0}
    
    for func in warm_up_functions:
        try:
            await func()
            results["success"] += 1
        except Exception as e:
            logger.error(f"Error warming up cache with {func.__name__}: {e}")
            results["errors"] += 1
    
    logger.info(f"Cache warm-up completed: {results}")
    return results
