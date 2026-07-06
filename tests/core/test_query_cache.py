"""Tests for query cache backends."""

import sys
import time
from unittest.mock import MagicMock, patch

import pytest

from business_analyzer.core.query_cache import (
    MemoryQueryCache,
    RedisQueryCache,
    create_query_cache,
)


class TestMemoryQueryCache:
    def test_set_and_get(self):
        cache = MemoryQueryCache(ttl=60)
        cache.set("  Ventas Mayo  ", {"sql": "SELECT 1"})
        assert cache.get("ventas mayo") == {"sql": "SELECT 1"}

    def test_expired_entry_returns_none(self):
        cache = MemoryQueryCache(ttl=1)
        cache.set("q", "v")
        cache._cache["q"]["t"] = time.time() - 2
        assert cache.get("q") is None

    @patch.dict("os.environ", {"CACHE_BACKEND": "memory"})
    def test_create_defaults_to_memory(self):
        cache = create_query_cache(120)
        assert isinstance(cache, MemoryQueryCache)


class TestRedisQueryCache:
    @patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379/1"})
    def test_round_trip(self):
        mock_client = MagicMock()
        stored = {}

        def _setex(key, ttl, value):
            stored[key] = value

        def _get(key):
            return stored.get(key)

        mock_client.setex.side_effect = _setex
        mock_client.get.side_effect = _get
        mock_client.ping.return_value = True

        mock_redis_mod = MagicMock()
        mock_redis_mod.from_url.return_value = mock_client
        with patch.dict(sys.modules, {"redis": mock_redis_mod}):
            cache = RedisQueryCache(ttl=300)
        cache.set("ventas", {"rows": 3})
        assert cache.get("ventas") == {"rows": 3}

    @patch.dict("os.environ", {"CACHE_BACKEND": "redis"})
    def test_create_falls_back_on_redis_error(self):
        with patch(
            "business_analyzer.core.query_cache.RedisQueryCache",
            side_effect=ConnectionError("down"),
        ):
            cache = create_query_cache(60)
        assert isinstance(cache, MemoryQueryCache)
