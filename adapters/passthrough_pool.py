"""Ограниченный потокобезопасный пул свободных HTTP-соединений."""

from __future__ import annotations

import http.client
import math
import select
import socket
import threading
import time
from collections.abc import Callable
from typing import Any, NamedTuple


class _IdleConnection(NamedTuple):
    connection: http.client.HTTPConnection
    released_s: float


class PassthroughConnectionPool:
    """LIFO-пул с общим лимитом, без владения соединениями активных запросов.

    Лимиты передаёт владелец из PassthroughLimits. После close_all выдача новых
    соединений допустима, но возврат в keepalive запрещён, как в прежнем пуле.
    """

    def __init__(
        self,
        max_keepalive: int = 32,
        keepalive_expiry_s: float = 30.0,
        select_fn: Callable[..., Any] = lambda r, w, x, timeout=0: select.select(r, w, x, timeout),
        monotonic_fn: Callable[[], float] = lambda: time.monotonic(),
        connection_fn: Callable[..., http.client.HTTPConnection] = lambda host, port, timeout: http.client.HTTPConnection(host, port, timeout=timeout),
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
        self._idle: dict[tuple[str, int], list[_IdleConnection]] = {}
        self._idle_count: int = 0
        self._lock: threading.Lock = threading.Lock()
        self._closed: bool = False

    def _pop(self, key: tuple[str, int]) -> _IdleConnection | None:
        with self._lock:
            entries = self._idle.get(key)
            if not entries:
                return None
            entry = entries.pop()
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
        if can_reuse and conn.sock is not None:
            with self._lock:
                if not self._closed and self._idle_count < self._max_keepalive:
                    entries = self._idle.setdefault((host, port), [])
                    entries.append(_IdleConnection(conn, self._monotonic()))
                    self._idle_count += 1
                    return
        conn.close()

    def close_all(self) -> None:
        """Идемпотентно отделяет idle-сокеты; активные закроются при возврате."""
        with self._lock:
            self._closed = True
            idle, self._idle = self._idle, {}
            self._idle_count = 0
        for entries in idle.values():
            for entry in entries:
                entry.connection.close()
