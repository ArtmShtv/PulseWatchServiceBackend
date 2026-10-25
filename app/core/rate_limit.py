import logging
from functools import lru_cache
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, status
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, client, scope: str, limit: int, window_seconds: int) -> None:
        self.client = client
        self.scope = scope
        self.limit = limit
        self.window_seconds = window_seconds

    async def hit(self, key: str) -> int | None:
        redis_key = f"ratelimit:{self.scope}:{key}"
        await self.client.set(redis_key, 0, ex=self.window_seconds, nx=True)
        attempts = await self.client.incr(redis_key)
        if attempts <= self.limit:
            return None
        ttl = await self.client.ttl(redis_key)
        return max(ttl, 1)


@lru_cache
def get_login_limiter() -> RateLimiter:
    return RateLimiter(
        aioredis.from_url(settings.REDIS_URL),
        scope="login",
        limit=settings.LOGIN_RATE_LIMIT,
        window_seconds=settings.LOGIN_RATE_WINDOW_SECONDS,
    )


async def limit_login_attempts(
    request: Request,
    limiter: Annotated[RateLimiter, Depends(get_login_limiter)],
) -> None:
    client_ip = request.client.host if request.client else "unknown"
    try:
        retry_after = await limiter.hit(client_ip)
    except RedisError:
        logger.warning("Rate limiter unavailable, allowing request", exc_info=True)
        return

    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts, try again later",
            headers={"Retry-After": str(retry_after)},
        )
