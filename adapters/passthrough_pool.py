"""Ограниченный потокобезопасный пул свободных HTTP-соединений."""

from __future__ import annotations

import contextlib
import http.client
import math
import select
import socket
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Any, NamedTuple

from core.admission_idle_policy import TTL_SWEEP_FLAG
from core.recovery_flags import read_recovery_switch


class _IdleConnection(NamedTuple):
    connection: http.client.HTTPConnection
    released_s: float


_Key = tuple[str, int]
_SWEEP_BATCH = 32


class PassthroughConnectionPool:
    """LIFO-пул с общим лимитом, без владения соединениями активных запросов.

    Лимиты передаёт владелец из PassthroughLimits. После close_all выдача новых
    соединений допустима, но возврат в keepalive запрещён, как в прежнем пуле.
    """

    def __init__(
        self,
        max_keepalive: int = 32,
        keepalive_expiry_s: float = 30.0,
        select_fn: Callable[..., Any] = lambda r, w, x, timeout=0: select.select(
            r, w, x, timeout
        ),
        monotonic_fn: Callable[[], float] = lambda: time.monotonic(),
        connection_fn: Callable[
            ..., http.client.HTTPConnection
        ] = lambda host, port, timeout: http.client.HTTPConnection(
            host, port, timeout=timeout
        ),
    ) -> None:
        if type(max_keepalive) is not int or max_keepalive < 0:
            raise ValueError("invalid_keepalive_limit")
        if not math.isfinite(keepalive_expiry_s) or keepalive_expiry_s <= 0:
            raise ValueError("invalid_keepalive_expiry")
        self._max_keepalive: int = max_keepalive
        self._keepalive_expiry_s: float = keepalive_expiry_s
        self._select = select_fn
        self._monotonic = monotonic_fn
        self._connection_fn = connection_fn
        self._idle: dict[_Key, list[_IdleConnection]] = {}
        self._fifo: deque[tuple[_Key, _IdleConnection]] = deque()
        self._live: set[int] = set()
        self._idle_count: int = 0
        self._lock: threading.Lock = threading.Lock()
        self._closed: bool = False
        self._active_ttl_sweep: bool | None = None
        self._evicted_expired: int = 0

    def set_active_ttl_sweep(self, enabled: bool | None) -> None:
        """False локально гасит sweep; True/None не обходят env/config kill-switch."""
        self._active_ttl_sweep = enabled

    def _sweep_enabled(self) -> bool:
        """Fail-closed: env/config флаг (default False) всегда может остановить sweep."""
        flag = self._active_ttl_sweep
        return flag is not False and read_recovery_switch(TTL_SWEEP_FLAG)

    def _evict_head_locked(self, now: float, limit: float) -> list[_IdleConnection]:
        """Снимает протухшую голову FIFO (stale-записи пропускаются); вызывать под lock."""
        expired: list[_IdleConnection] = []
        while self._fifo and len(expired) < limit:
            key, entry = self._fifo[0]
            live = id(entry) in self._live
            if live and now - entry.released_s <= self._keepalive_expiry_s:
                break
            _ = self._fifo.popleft()
            if live:
                self._live.discard(id(entry))
                self._idle[key].remove(entry)
                if not self._idle[key]:
                    del self._idle[key]
                expired.append(entry)
        self._idle_count -= len(expired)
        self._evicted_expired += len(expired)
        return expired

    def sweep_expired(self, max_items: int | None = None) -> int:
        """Вытесняет до max_items протухших idle; непротухшая голова — O(1); close вне lock."""
        limit = math.inf if max_items is None else max_items
        with self._lock:
            expired = self._evict_head_locked(self._monotonic(), limit)
        for entry in expired:
            with contextlib.suppress(OSError):
                entry.connection.close()
        return len(expired)

    @property
    def idle_count(self) -> int:
        """Текущее число свободных соединений в пуле."""
        with self._lock:
            return self._idle_count

    def stats(self) -> dict[str, int]:
        """Снимок пула: idle, max_keepalive, evicted_expired."""
        with self._lock:
            return {
                "idle": self._idle_count,
                "max_keepalive": self._max_keepalive,
                "evicted_expired": self._evicted_expired,
            }

    def _pop(self, key: _Key) -> _IdleConnection | None:
        with self._lock:
            entries = self._idle.get(key)
            if not entries:
                return None
            entry = entries.pop()
            self._live.discard(id(entry))
            self._idle_count -= 1
            if not entries:
                del self._idle[key]
            return entry

    def _reuse(self, entry: _IdleConnection, timeout: float) -> bool:
        connection = entry.connection
        sock = connection.sock
        if sock is None:
            return False
        if self._monotonic() - entry.released_s > self._keepalive_expiry_s:
            return False
        try:
            readable, _, _ = self._select([sock], [], [], 0)
            # EOF и незапрошенные данные одинаково запрещают переиспользование.
            if readable:
                try:
                    sock.recv(1, socket.MSG_PEEK)
                except OSError:
                    pass
                return False
            connection.timeout = timeout
            _ = sock.settimeout(timeout)
        except (OSError, ValueError):
            return False
        return True

    def get_connection(
        self,
        host: str,
        port: int,
        timeout: float,
        *,
        fresh: bool = False,
    ) -> tuple[http.client.HTTPConnection, bool]:
        """Передаёт вызывающему подключённое соединение; ошибок send здесь нет."""
        if self._sweep_enabled():
            self.sweep_expired(_SWEEP_BATCH)
        while not fresh:
            entry = self._pop((host, port))
            if entry is None:
                break
            try:
                if self._reuse(entry, timeout):
                    return entry.connection, True
            except BaseException:
                entry.connection.close()
                raise
            entry.connection.close()
        connection = self._connection_fn(host, port, timeout)
        try:
            connection.connect()
        except BaseException:
            connection.close()
            raise
        return connection, False

    def release_connection(
        self,
        host: str,
        port: int,
        conn: http.client.HTTPConnection,
        can_reuse: bool = True,
    ) -> None:
        """Принимает владение ровно один раз: сохраняет либо закрывает сокет."""
        if self._sweep_enabled():
            self.sweep_expired(_SWEEP_BATCH)
        if can_reuse and conn.sock is not None:
            with self._lock:
                if not self._closed and self._idle_count < self._max_keepalive:
                    entry = _IdleConnection(conn, self._monotonic())
                    self._idle.setdefault((host, port), []).append(entry)
                    self._fifo.append(((host, port), entry))
                    self._live.add(id(entry))
                    self._idle_count += 1
                    if len(self._fifo) > 2 * self._max_keepalive + _SWEEP_BATCH:
                        self._fifo = deque(
                            e for e in self._fifo if id(e[1]) in self._live
                        )
                    return
        conn.close()

    def close_all(self) -> None:
        """Идемпотентно отделяет idle-сокеты; активные закроются при возврате."""
        with self._lock:
            self._closed = True
            idle, self._idle = self._idle, {}
            self._fifo.clear()
            self._live.clear()
            self._idle_count = 0
        for entries in idle.values():
            for entry in entries:
                entry.connection.close()
