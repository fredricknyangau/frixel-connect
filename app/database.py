from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg
from asyncpg import Pool

from app.config import settings

_pool: Pool | None = None


async def create_pool() -> None:
    """Called once at application startup."""
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=settings.DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )


async def close_pool() -> None:
    """Called once at application shutdown."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """
    Async context manager that yields a connection from the pool.

    Usage in a route:
        async with get_db() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    """
    if _pool is None:
        raise RuntimeError("Database pool is not initialised. Was create_pool() called?")

    async with _pool.acquire() as connection:
        yield connection