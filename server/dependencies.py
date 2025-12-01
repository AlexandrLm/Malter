"""
FastAPI Dependencies for Dependency Injection.
"""

from typing import AsyncGenerator, Optional
from google import genai
import redis.asyncio as redis

from config import settings, GEMINI_CLIENT, REDIS_POOL

async def get_gemini_client() -> Optional[genai.Client]:
    """
    Dependency to get Gemini Client.
    In the future, this could handle client rotation or per-request configuration.
    Currently returns the global client initialized in config.
    """
    # Note: We are using the global client from config for now to reuse the connection/init logic.
    # In a pure DI world, we might initialize it here or in lifespan.
    return GEMINI_CLIENT

async def get_redis_client() -> AsyncGenerator[redis.Redis, None]:
    """
    Dependency to get Redis Client from the pool.
    """
    if not REDIS_POOL:
        yield None
        return

    client = redis.Redis(connection_pool=REDIS_POOL)
    try:
        yield client
    finally:
        await client.close()
