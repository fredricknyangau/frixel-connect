"""
app/core/redis.py
==================
Shared Redis connection pool initialization and accessor utilities.
Uses arq connection helpers to integrate cleanly with the worker.
"""

import logging
from typing import Optional
from arq.connections import RedisSettings, ArqRedis, create_pool
from app.config import settings

logger = logging.getLogger(__name__)

# Module-level global reference to the Redis pool
redis_pool: Optional[ArqRedis] = None


async def init_redis() -> ArqRedis:
    """
    Initialises the global ArqRedis connection pool.
    Should be called during application startup (FastAPI lifespan).
    """
    global redis_pool
    if redis_pool is None:
        redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
        redis_pool = await create_pool(redis_settings)
        logger.info("Redis: connection pool initialised successfully.")
    return redis_pool


async def close_redis() -> None:
    """
    Closes the global Redis connection pool.
    Should be called during application shutdown (FastAPI lifespan).
    """
    global redis_pool
    if redis_pool is not None:
        await redis_pool.close()
        redis_pool = None
        logger.info("Redis: connection pool closed.")


def get_redis_pool() -> ArqRedis:
    """
    Retrieves the active global ArqRedis pool.
    Raises RuntimeError if the pool is not yet initialised.
    """
    if redis_pool is None:
        raise RuntimeError(
            "Redis connection pool is not initialised. "
            "Verify that init_redis() was called at startup."
        )
    return redis_pool
