import threading
import time
import sys
import logging

from pathlib import Path
from typing import Any, Optional, Union
from ..core.models import CacheConfig

logger = logging.getLogger("ikiapikit")


class LruCache:
    """
    Thread-safe in-memory LRU cache with per-entry TTL.

    Keys are strings; values are arbitrary Python objects.
    Evicts the least-recently-used entry when max_entries is reached.
    """

    def __init__(self, ttl: int = 300, max_entries: int = 1_000):
        self.ttl = ttl
        self.max_entries = max_entries
        self.enabled = True
        # key → (value, expires_at)
        self._store: dict[str, tuple[Any, float]] = {}
        # LRU order, oldest first
        self._order: list[str] = []
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._total_calls = 0

    # ── public API ────────────────────────────────────────────────────────────

    def make_key(self, method: str, url: str, params: Optional[dict]) -> str:
        param_str = str(sorted((params or {}).items()))
        return f"{method}:{url}:{param_str}"

    def get(self, key: str) -> Optional[Any]:
        self._total_calls += 1
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            value, expires_at = entry
            if self.ttl > 0 and time.monotonic() > expires_at:
                del self._store[key]
                if key in self._order:
                    self._order.remove(key)
                self._misses += 1
                return None
            # move to most-recently-used position
            if key in self._order:
                self._order.remove(key)
            self._order.append(key)
            self._hits += 1
            return value

    def set(self, key: str, value: Any, ttl_override: Optional[int] = None) -> None:
        effective_ttl = ttl_override if ttl_override is not None else self.ttl
        expires_at = time.monotonic() + effective_ttl if effective_ttl > 0 else float("inf")
        with self._lock:
            if key in self._store:
                self._order.remove(key)
            elif len(self._store) >= self.max_entries and self._order:
                # evict LRU
                lru_key = self._order.pop(0)
                del self._store[lru_key]
            self._store[key] = (value, expires_at)
            self._order.append(key)

    def invalidate(self, url: str) -> None:
        """Remove all cache entries whose key contains the given URL."""
        with self._lock:
            to_delete = [k for k in self._store if url in k]
            for k in to_delete:
                del self._store[k]
                if k in self._order:
                    self._order.remove(k)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._order.clear()

    def stats(self) -> dict:
        with self._lock:
            mem = sum(sys.getsizeof(v) for v, _ in self._store.values())
            hit_rate = (self._hits / self._total_calls *
                        100) if self._total_calls else 0.0
            return {
                "entries": len(self._store),
                "hits": self._hits,
                "misses": self._misses,
                "total_calls": self._total_calls,
                "hit_rate_pct": round(hit_rate, 1),
                "memory_bytes": mem,
                "ttl_seconds": self.ttl,
                "max_entries": self.max_entries,
            }

    # ── test helpers ──────────────────────────────────────────────────────────

    def _force_expire_all(self) -> None:
        """Test helper — immediately expire all entries."""
        with self._lock:
            self._store = {k: (v, 0.0) for k, (v, _) in self._store.items()}


class NoCache:
    """Null-object cache — always misses. Used when cache=False."""

    enabled = False

    def make_key(self, method: str, url: str, params: Optional[dict]) -> str:
        return ""

    def get(self, key: str) -> None:
        return None

    def set(self, key: str, value: Any, ttl_override: Optional[int] = None) -> None:
        pass

    def invalidate(self, url: str) -> None:
        pass

    def clear(self) -> None:
        pass

    def stats(self) -> dict:
        return {"entries": 0, "hits": 0, "misses": 0, "total_calls": 0,
                "hit_rate_pct": 0.0, "memory_bytes": 0, "ttl_seconds": 0,
                "max_entries": 0}


class DiskCacheAdapter:
    """Thin adapter so diskcache has the same interface as _LruCache."""

    enabled = True

    def __init__(self, dc: Any, ttl: int = 300):
        self._dc = dc
        self.ttl = ttl
        self._hits = 0
        self._misses = 0
        self._total_calls = 0

    def make_key(self, method: str, url: str, params: Optional[dict]) -> str:
        param_str = str(sorted((params or {}).items()))
        return f"{method}:{url}:{param_str}"

    def get(self, key: str) -> Optional[Any]:
        self._total_calls += 1
        value = self._dc.get(key)
        if value is None:
            self._misses += 1
        else:
            self._hits += 1
        return value

    def set(self, key: str, value: Any, ttl_override: Optional[int] = None) -> None:
        expire = ttl_override if ttl_override is not None else self.ttl
        self._dc.set(key, value, expire=expire or None)

    def invalidate(self, url: str) -> None:
        for k in list(self._dc.iterkeys()):
            if url in k:
                del self._dc[k]

    def clear(self) -> None:
        self._dc.clear()

    def _force_expire_all(self) -> None:
        self.clear()

    def stats(self) -> dict:
        hit_rate = (self._hits / self._total_calls *
                    100) if self._total_calls else 0.0
        return {
            "entries": len(self._dc),
            "hits": self._hits,
            "misses": self._misses,
            "total_calls": self._total_calls,
            "hit_rate_pct": round(hit_rate, 1),
            "memory_bytes": self._dc.volume(),
            "ttl_seconds": self.ttl,
            "max_entries": -1,
        }


def build_cache(cache: Union[bool, CacheConfig, None]) -> Union[LruCache, NoCache]:
    """Factory: build the appropriate cache backend from user input."""
    if cache is None or cache is False:
        return NoCache()
    if cache is True:
        return LruCache()
    if isinstance(cache, CacheConfig):
        if not cache.enabled:
            return NoCache()
        if cache.backend == "disk":
            try:
                import diskcache
                dc = diskcache.Cache(
                    cache.disk_path or str(Path.home() / ".cache" / "apikit"),
                    size_limit=500 * 1024 * 1024,
                )
                # Wrap diskcache in a thin adapter so the API is identical
                return DiskCacheAdapter(dc, ttl=cache.ttl)
            except ImportError:
                logger.warning(
                    "diskcache not installed — falling back to memory cache. "
                    "Install with: pip install diskcache"
                )
        return LruCache(ttl=cache.ttl, max_entries=cache.max_entries)
    return NoCache()
