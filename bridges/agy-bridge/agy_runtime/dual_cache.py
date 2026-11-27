"""Bounded/unbounded dual-mode key-value cache extracted from hygiene_runtime."""

from __future__ import annotations

import threading
import time
from typing import final

from .state_hygiene_policy import BoundedLruTtl, CachePolicyConfig


@final
class DualCache:
    """Thread-safe cache switching cleanly between bounded LRU+TTL and plain dict."""

    def __init__(self, cfg: CachePolicyConfig) -> None:
        self._lock, self._lru, self._raw = threading.Lock(), BoundedLruTtl[str](cfg), dict[str, str]()

    def get(self, key: str, bounded: bool) -> str | None:
        with self._lock:
            return self._lru.get(key, time.monotonic()) if bounded else self._raw.get(key)

    def put(self, key: str, val: str, bounded: bool) -> None:
        with self._lock:
            if bounded:
                _ = self._lru.put(key, val, len(val.encode("utf-8")), time.monotonic())
            else:
                self._raw[key] = val

    def claim(self, key: str, val: str, bounded: bool) -> bool:
        now = time.monotonic()
        with self._lock:
            if bounded:
                return False if self._lru.get(key, now) is not None else self._lru.put(key, val, len(val.encode("utf-8")), now)
            return False if key in self._raw else (self._raw.__setitem__(key, val) is None)

    def remove(self, key: str) -> None:
        with self._lock:
            _ = (self._raw.pop(key, None), self._lru.remove(key))

    def clear_or_prune(self, clear: bool, bounded: bool) -> int:
        with self._lock:
            if clear:
                self._raw.clear()
                self._lru.clear()
                return 0
            return self._lru.purge_expired(time.monotonic()) if bounded else 0

    def count(self, bounded: bool) -> int:
        with self._lock:
            return len(self._lru) if bounded else len(self._raw)
