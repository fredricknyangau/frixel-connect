import time
from fastapi import Request, HTTPException, status
from app.core.redis import get_redis_pool

class RateLimiter:
    """
    Redis-backed sliding window rate limiter.
    Limits requests to a specific endpoint per IP address.
    """
    def __init__(self, requests: int, window: int):
        self.requests = requests
        self.window = window

    async def __call__(self, request: Request):
        ip = request.client.host if request.client else "127.0.0.1"
        path = request.url.path
        key = f"rate_limit:{path}:{ip}"
        
        redis = get_redis_pool()
        now = time.time()
        
        async with redis.pipeline(transaction=True) as pipe:
            # 1. Add current request timestamp to the sorted set
            pipe.zadd(key, {str(now): now})
            # 2. Remove all timestamps older than the window
            pipe.zremrangebyscore(key, 0, now - self.window)
            # 3. Count remaining valid items
            pipe.zcard(key)
            # 4. Set expiry to automatically clean up inactive IPs
            pipe.expire(key, self.window)
            
            results = await pipe.execute()
            
        count = results[2]  # The result of zcard
        
        if count > self.requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later."
            )
