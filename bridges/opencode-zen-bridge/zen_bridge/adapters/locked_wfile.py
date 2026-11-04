"""Обёртка wfile потокового запроса под замком с таймаутом сокета."""

from __future__ import annotations

import errno
import io
import socket
import threading
import time
from collections.abc import Callable
from typing import cast


class _LockedWfile:
    """wfile потокового запроса под общим замком с конечным таймаутом записи клиенту."""

    def __init__(
        self,
        inner: io.BufferedIOBase,
        lock: threading.Lock | threading.RLock,
        sock: socket.socket | None = None,
        deadline: float | None = None,
        deadline_fn: Callable[[], float | None] | None = None,
        on_client_gone: Callable[[], None] | None = None,
        write_timeout_s: float | Callable[[], float] = 15.0,
        log_fn: Callable[[str], None] | None = None,
    ) -> None:
        self._inner: io.BufferedIOBase = inner
        self._lock: threading.Lock | threading.RLock = lock
        self._sock: socket.socket | None = sock
        self._deadline: float | None = deadline
        self._deadline_fn: Callable[[], float | None] | None = deadline_fn
        self._on_client_gone: Callable[[], None] | None = on_client_gone
        self._write_timeout_s = write_timeout_s
        self._log = log_fn
        self.client_gone: bool = False
        self._timer: threading.Timer | None = None

    def _get_write_timeout(self) -> float:
        if callable(self._write_timeout_s):
            return float(self._write_timeout_s())
        return float(self._write_timeout_s)

    def _effective_deadline(self) -> float | None:
        if self._deadline_fn is not None:
            return self._deadline_fn()
        return self._deadline

    def _apply_write_timeout(self) -> None:
        sock = self._sock
        if sock is None:
            return
        set_timeout = getattr(sock, "settimeout", None)
        if not callable(set_timeout):
            return
        effective_deadline = self._effective_deadline()
        base_timeout = self._get_write_timeout()
        if effective_deadline is None:
            timeout = base_timeout
        else:
            remaining = effective_deadline - time.monotonic()
            timeout = min(base_timeout, max(0.05, remaining))
        try:
            _ = set_timeout(timeout)
        except OSError:
            pass

    def _mark_client_gone(self) -> None:
        if self.client_gone:
            return
        self.client_gone = True
        try:
            if self._on_client_gone is not None:
                try:
                    self._on_client_gone()
                except Exception as exc:
                    if self._log is not None:
                        self._log(f"client_gone callback error: {exc}")
        finally:
            self.abort_socket()

    def cancel_deadline_timer(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def abort_socket(self) -> None:
        if not self.client_gone:
            self._mark_client_gone()
            return
        sock = self._sock
        if sock is None:
            return
        try:
            _ = sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass

    def write(self, data: bytes) -> int:
        try:
            with self._lock:
                self._apply_write_timeout()
                return int(self._inner.write(data) or 0)
        except (OSError, ValueError) as exc:
            self.abort_socket()
            if isinstance(exc, (BrokenPipeError, ConnectionResetError)):
                raise
            raise BrokenPipeError(errno.EPIPE, "downstream write failed") from exc

    def flush(self) -> None:
        try:
            with self._lock:
                self._apply_write_timeout()
                self._inner.flush()
        except (OSError, ValueError) as exc:
            self.abort_socket()
            if isinstance(exc, (BrokenPipeError, ConnectionResetError)):
                raise
            raise BrokenPipeError(errno.EPIPE, "downstream flush failed") from exc

    def __getattr__(self, name: str) -> object:
        return cast(object, getattr(self._inner, name))
