# mypy: ignore-errors
"""Query result cache — in-memory default, optional Redis backend."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)

_CACHE_PREFIX = "depotru:query:"


class QueryCache(Protocol):
    def get(self, key: str) -> Optional[Any]:
        ...

    def set(self, key: str, value: Any) -> None:
        ...


class MemoryQueryCache:
    """Thread-local-friendly in-process TTL cache."""

    def __init__(self, ttl: int = 300) -> None:
        self.ttl = ttl
        self._cache: dict[str, dict[str, Any]] = {}

    def _normalize(self, key: str) -> str:
        return (key or "").lower().strip()

    def get(self, key: str) -> Optional[Any]:
        k = self._normalize(key)
        entry = self._cache.get(k)
        if not entry:
            return None
        if time.time() - entry["t"] > self.ttl:
            del self._cache[k]
            return None
        return entry["v"]

    def set(self, key: str, value: Any) -> None:
        self._cache[self._normalize(key)] = {"v": value, "t": time.time()}


class RedisQueryCache:
    """Distributed TTL cache backed by Redis."""

    def __init__(self, ttl: int = 300, url: Optional[str] = None) -> None:
        self.ttl = ttl
        try:
            import redis
        except ImportError as exc:
            raise ImportError(
                "Redis cache requires the 'redis' package. "
                "Install with: pip install redis"
            ) from exc

        redis_url = url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._client = redis.from_url(redis_url, decode_responses=True)
        self._client.ping()
        logger.info("Redis query cache connected")

    def _normalize(self, key: str) -> str:
        return _CACHE_PREFIX + (key or "").lower().strip()

    def get(self, key: str) -> Optional[Any]:
        raw = self._client.get(self._normalize(key))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def set(self, key: str, value: Any) -> None:
        payload = json.dumps(value, default=str)
        self._client.setex(self._normalize(key), self.ttl, payload)


# Backward-compatible alias used by ai/base.py
SimpleQueryCache = MemoryQueryCache


def create_query_cache(ttl: Optional[int] = None) -> QueryCache:
    """Build cache from CACHE_BACKEND env (memory | redis)."""
    cache_ttl = ttl if ttl is not None else int(os.getenv("CACHE_TTL_SECONDS", "300"))
    backend = os.getenv("CACHE_BACKEND", "memory").lower().strip()

    if backend == "redis":
        try:
            return RedisQueryCache(ttl=cache_ttl)
        except Exception as exc:
            logger.warning("Redis cache unavailable (%s); using memory", exc)
            return MemoryQueryCache(ttl=cache_ttl)

    return MemoryQueryCache(ttl=cache_ttl)
