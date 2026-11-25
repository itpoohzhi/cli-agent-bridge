"""Кэш SHA-256 бинаря agy без TTL-протухания и с неблокирующим обновлением."""

from __future__ import annotations

import hashlib
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass

FLAG_STAT_SHA_CACHE = "AGY_STAT_SHA_CACHE_ENABLED"
_CHUNK_BYTES = 1024 * 1024
_MAX_TORN_RETRIES = 3

StatKey = tuple[int, int, int, int]


@dataclass(frozen=True)
class _Snapshot:
    stat_key: StatKey
    digest: str


class StatShaCache:
    """Хранит подтверждённый SHA-256 по StatKey с синхронным cold-miss и async-рефрешем."""

    def __init__(self, chunk_bytes: int = _CHUNK_BYTES) -> None:
        self._chunk_bytes = chunk_bytes
        self._lock = threading.Lock()
        self._snapshots: dict[str, _Snapshot] = {}
        self._refreshing: set[str] = set()
        self._pending: set[str] = set()

    @staticmethod
    def _stat_key(resolved: str) -> StatKey:
        info = os.stat(resolved)
        return (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_size)

    def _compute_checked(self, resolved: str) -> _Snapshot | None:
        for _ in range(_MAX_TORN_RETRIES):
            try:
                pre = self._stat_key(resolved)
                hasher = hashlib.sha256()
                with open(resolved, "rb") as handle:
                    for chunk in iter(lambda: handle.read(self._chunk_bytes), b""):
                        hasher.update(chunk)
                post = self._stat_key(resolved)
            except OSError:
                return None
            if pre == post:
                return _Snapshot(pre, hasher.hexdigest())
        return None

    def _schedule_refresh(self, resolved: str) -> None:
        with self._lock:
            if resolved in self._refreshing:
                self._pending.add(resolved)
                return
            self._refreshing.add(resolved)
        threading.Thread(
            target=self._refresh_worker,
            args=(resolved,),
            daemon=True,
            name="agy-stat-sha-refresh",
        ).start()

    def _refresh_worker(self, resolved: str) -> None:
        while True:
            snap = self._compute_checked(resolved)
            with self._lock:
                if snap is not None:
                    self._snapshots[resolved] = snap
                if resolved in self._pending:
                    self._pending.discard(resolved)
                    continue
                self._refreshing.discard(resolved)
                return

    def get_sha256(
        self, path: object, legacy_fn: Callable[[object], str] | None = None
    ) -> str:
        """Возвращает SHA-256: lock-free при warm hit/refresh, синхронно на cold miss."""
        if not cache_enabled() and legacy_fn is not None:
            return legacy_fn(path)
        resolved = os.path.expanduser(str(path))
        try:
            current = self._stat_key(resolved)
        except OSError:
            return ""
        with self._lock:
            snap = self._snapshots.get(resolved)
        if snap is not None:
            if snap.stat_key != current:
                self._schedule_refresh(resolved)
            return snap.digest
        cold = self._compute_checked(resolved)
        if cold is None:
            return ""
        with self._lock:
            self._snapshots.setdefault(resolved, cold)
            return self._snapshots[resolved].digest

    def warm_up(self, path: object) -> str:
        """Синхронно прогревает кэш при старте процесса до приёма HTTP."""
        return self.get_sha256(path)

    def clear(self) -> None:
        """Очищает кэш снимков (используется test-guard сбросами)."""
        with self._lock:
            self._snapshots.clear()
            self._pending.clear()


def cache_enabled() -> bool:
    """True если AGY_STAT_SHA_CACHE_ENABLED включён (default 1)."""
    raw = os.environ.get(FLAG_STAT_SHA_CACHE, "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


DEFAULT_STAT_SHA_CACHE = StatShaCache()
