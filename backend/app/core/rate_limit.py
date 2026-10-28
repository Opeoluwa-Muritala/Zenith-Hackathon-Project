"""Pluggable fixed-window rate limiting with a process-local fallback."""

import logging
import time
from collections import defaultdict
from functools import lru_cache

from fastapi import HTTPException

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = defaultdict(list)
        logger.warning("rate_limiter_in_memory_fallback")

    async def hit(self, key: str, limit: int = 5, window_seconds: int = 60) -> None:
        now = time.monotonic()
        self._hits[key] = [value for value in self._hits[key] if now - value < window_seconds]
        if len(self._hits[key]) >= limit:
            raise HTTPException(429, "Try again later")
        self._hits[key].append(now)


class RedisRateLimiter:
    def __init__(self, url: str) -> None:
        from redis.asyncio import from_url

        self._client = from_url(url, decode_responses=True)

    async def hit(self, key: str, limit: int = 5, window_seconds: int = 60) -> None:
        redis_key = f"fetch:rate:{key}"
        count = await self._client.incr(redis_key)
        if count == 1:
            await self._client.expire(redis_key, window_seconds)
        if count > limit:
            ttl = await self._client.ttl(redis_key)
            raise HTTPException(429, "Try again later", headers={"Retry-After": str(max(1, ttl))})


@lru_cache
def get_rate_limiter() -> InMemoryRateLimiter | RedisRateLimiter:
    url = get_settings().redis_url
    return RedisRateLimiter(url) if url else InMemoryRateLimiter()
