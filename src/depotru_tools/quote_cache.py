"""Short TTL cache for exact-SKU J3 quote rows (BFF-PRECIO-SKU).

Why: one ``catalog.quote_search`` by SKU costs ~2.4 s of SQL Server time
(the LIKE/REPLACE predicate forces a full-inventory aggregate; see
``docs/reference/j3-quote-sku-lookup-explain.md``). Repeat lookups of the
same SKU within a short window must not repay it, and N concurrent misses
for the same SKU must collapse into ONE query (single-flight), not a
stampede.

Contract:
- TTL is short (default 120 s, ``QUOTE_SKU_CACHE_TTL_SECONDS``; ``0``
  disables caching) so a price change in J3 is visible quickly. This is a
  latency guard, not a price cache of record.
- Bounded size (``QUOTE_SKU_CACHE_MAX_ENTRIES``, default 1024); the oldest
  entry is evicted first.
- Failures are never cached; empty results (SKU not found) ARE cached — a
  missing SKU is a valid answer for the window.
- Cached row lists are handed out as copies; callers must treat rows as
  immutable.
"""

from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict
from typing import Callable, Sequence


def _ttl_from_env() -> float:
    raw = os.getenv("QUOTE_SKU_CACHE_TTL_SECONDS")
    if raw is None:
        return 120.0
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 120.0


def _max_entries_from_env() -> int:
    raw = os.getenv("QUOTE_SKU_CACHE_MAX_ENTRIES")
    if raw is None:
        return 1024
    try:
        return max(16, int(raw))
    except ValueError:
        return 1024


class _Flight:
    """One in-flight computation shared by concurrent callers."""

    __slots__ = ("event", "rows", "error")

    def __init__(self) -> None:
        self.event = threading.Event()
        self.rows: list[dict] | None = None
        self.error: BaseException | None = None


class QuoteSkuCache:
    """Thread-safe TTL cache with per-key single-flight."""

    def __init__(self, ttl_seconds: float = 120.0, max_entries: int = 1024) -> None:
        self.ttl_seconds = float(ttl_seconds)
        self.max_entries = int(max_entries)
        self._lock = threading.Lock()
        self._data: OrderedDict[str, tuple[float, list[dict]]] = OrderedDict()
        self._inflight: dict[str, _Flight] = {}
        self.hits = 0
        self.misses = 0

    def _get_live(self, key: str) -> list[dict] | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        stored_at, rows = entry
        if self.ttl_seconds <= 0 or (time.monotonic() - stored_at) >= self.ttl_seconds:
            self._data.pop(key, None)
            return None
        return rows

    def resolve(self, key: str, compute: Callable[[str], Sequence[dict]]) -> list[dict]:
        """Return cached rows for ``key`` or compute them exactly once.

        Concurrent ``resolve`` calls for the same key block on one
        ``compute``; the first exception propagates to every waiter, is not
        cached, and the failed flight is discarded so the next ``resolve``
        retries ``compute`` instead of replaying the stale error.
        """
        if self.ttl_seconds <= 0:
            return list(compute(key))
        with self._lock:
            rows = self._get_live(key)
            if rows is not None:
                self.hits += 1
                return list(rows)
            self.misses += 1
            flight = self._inflight.get(key)
            if flight is None:
                flight = _Flight()
                self._inflight[key] = flight
                owner = True
            else:
                owner = False
        if not owner:
            flight.event.wait()
            if flight.error is not None:
                raise flight.error
            assert flight.rows is not None
            return list(flight.rows)
        try:
            rows = list(compute(key))
        except BaseException as exc:  # noqa: BLE001 — shared with waiters
            flight.error = exc
            # Discard the dead flight BEFORE waking waiters: a failed compute
            # must not poison the key, or every later resolve would replay
            # this stale error instead of retrying compute.
            with self._lock:
                self._inflight.pop(key, None)
            flight.event.set()
            raise
        with self._lock:
            flight.rows = rows
            self._inflight.pop(key, None)
            self._data[key] = (time.monotonic(), rows)
            while len(self._data) > self.max_entries:
                self._data.popitem(last=False)
        flight.event.set()
        return list(rows)

    def peek(self, key: str) -> list[dict] | None:
        """Live cached rows for ``key`` without counters (no compute)."""
        with self._lock:
            return self._get_live(key)

    def store(self, key: str, rows: Sequence[dict]) -> None:
        """Insert rows for ``key`` (used by the batch fetch to fill siblings)."""
        if self.ttl_seconds <= 0:
            return
        with self._lock:
            self._data[key] = (time.monotonic(), list(rows))
            while len(self._data) > self.max_entries:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._inflight.clear()
            self.hits = 0
            self.misses = 0


_cache: QuoteSkuCache | None = None
_cache_lock = threading.Lock()


def get_quote_sku_cache() -> QuoteSkuCache:
    """Process-wide cache; knobs are read at first use (test-friendly)."""
    global _cache
    with _cache_lock:
        if _cache is None:
            _cache = QuoteSkuCache(
                ttl_seconds=_ttl_from_env(),
                max_entries=_max_entries_from_env(),
            )
        return _cache


def reset_quote_sku_cache() -> None:
    """Drop the singleton (tests) so env knobs apply again."""
    global _cache
    with _cache_lock:
        _cache = None
