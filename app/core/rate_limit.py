"""
app/core/rate_limit.py
======================
Redis-backed sliding window rate limiter with per-tenant scoping (T8).

Rate limit key format:
  Authenticated: rate_limit:{endpoint}:{tenant_id}:{ip}
  Unauthenticated: rate_limit:{endpoint}:{ip}
"""

import time

from fastapi import HTTPException, Request, status

from app.core.redis import get_redis_pool


def get_client_ip(request: Request) -> str:
    """Extract client IP, preferring X-Real-IP when behind a reverse proxy."""
    forwarded = request.headers.get("X-Real-IP") or request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


class RateLimiter:
    """
    Sliding window rate limit scoped to (endpoint, tenant_id, ip).

    tenant_id scoping closes T8: alternating tokens from two tenant accounts
    no longer share one IP bucket. Each tenant gets an independent limit.
    """

    def __init__(
        self,
        requests: int,
        window: int,
        endpoint: str | None = None,
    ):
        self.requests = requests
        self.window = window
        self.endpoint = endpoint

    def key(
        self,
        endpoint: str,
        tenant_id: str | None,
        ip: str,
    ) -> str:
        if tenant_id:
            return f"rate_limit:{endpoint}:{tenant_id}:{ip}"
        return f"rate_limit:{endpoint}:{ip}"

    async def check(
        self,
        endpoint: str,
        tenant_id: str | None,
        ip_address: str,
    ) -> None:
        """
        Raises HTTP 429 with Retry-After if the limit is exceeded.
        """
        redis = get_redis_pool()
        key = self.key(endpoint, tenant_id, ip_address)
        now = time.time()

        async with redis.pipeline(transaction=True) as pipe:
            pipe.zadd(key, {str(now): now})
            pipe.zremrangebyscore(key, 0, now - self.window)
            pipe.zcard(key)
            pipe.expire(key, self.window)
            results = await pipe.execute()

        count = results[2]
        if count > self.requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(self.window)},
            )

    async def __call__(self, request: Request) -> None:
        """
        FastAPI dependency for unauthenticated endpoints (login, setup, etc.).
        Uses IP-only key when no tenant context is available.
        """
        endpoint = self.endpoint or request.url.path
        await self.check(endpoint, None, get_client_ip(request))
