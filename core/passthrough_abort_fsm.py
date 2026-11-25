"""Конечный автомат завершения passthrough-попытки: client_gone vs upstream_timeout."""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from enum import Enum

FLAG_PASSTHROUGH_ABORT_FSM = "BRIDGE_PASSTHROUGH_ABORT_FSM"


class AbortState(Enum):
    """Поглощающие терминальные состояния passthrough-запроса (first-writer-wins)."""

    ACTIVE = "active"
    COMPLETED = "completed"
    CLIENT_GONE = "client_gone"
    UPSTREAM_TIMEOUT = "upstream_timeout"
    EXPLICIT_CANCEL = "explicit_cancel"
    UPSTREAM_ERROR = "upstream_error"


_ABORTED_STATES = frozenset({
    AbortState.CLIENT_GONE, AbortState.UPSTREAM_TIMEOUT, AbortState.EXPLICIT_CANCEL, AbortState.UPSTREAM_ERROR,
})
_CANCEL_STATES = frozenset({AbortState.CLIENT_GONE, AbortState.EXPLICIT_CANCEL})
_TIMEOUT_STATES = frozenset({AbortState.UPSTREAM_TIMEOUT})
_FALSE_TOKENS = frozenset({"0", "false", "no", "off"})


def fsm_enabled() -> bool:
    """Возвращает True, если FSM-классификация включена (default 1)."""
    return not _FALSE_TOKENS.__contains__(os.environ.get(FLAG_PASSTHROUGH_ABORT_FSM, "1").strip().lower())


class PassthroughAbortFSM:
    """Thread-safe FSM разделения причин прерывания без маскировки реальных 504."""

    def __init__(self, abort_io: Callable[[], None] | None = None) -> None:
        self._lock = threading.Lock()
        self._state = AbortState.ACTIVE
        self._abort_io = abort_io

    @property
    def state(self) -> AbortState:
        """Текущее состояние автомата."""
        with self._lock:
            return self._state

    @property
    def is_aborted(self) -> bool:
        """True для любого прерванного терминала."""
        return _ABORTED_STATES.__contains__(self.state)

    def is_client_cancelled(self) -> bool:
        """True при разрыве клиента или явной отмене."""
        return _CANCEL_STATES.__contains__(self.state)

    def is_timeout(self) -> bool:
        """True только если терминалом зафиксирован UPSTREAM_TIMEOUT."""
        return _TIMEOUT_STATES.__contains__(self.state)

    def _transition(self, target: AbortState, *, trigger_abort: bool) -> bool:
        cb: Callable[[], None] | None = None
        with self._lock:
            if self._state is AbortState.ACTIVE:
                self._state = target
                cb = self._abort_io if trigger_abort else None
            else:
                return False
        if cb is not None:
            cb()
        return True

    def on_client_gone(self) -> bool:
        """Фиксирует отключение клиента; не затирает уже сработавший UPSTREAM_TIMEOUT."""
        return self._transition(AbortState.CLIENT_GONE, trigger_abort=True)

    def on_deadline(self) -> bool:
        """Фиксирует таймаут апстрима; не затирает уже зафиксированный CLIENT_GONE."""
        return self._transition(AbortState.UPSTREAM_TIMEOUT, trigger_abort=True)

    def on_explicit_cancel(self) -> bool:
        """Фиксирует явную отмену без классификации как 504."""
        return self._transition(AbortState.EXPLICIT_CANCEL, trigger_abort=True)

    def on_upstream_error(self) -> bool:
        """Фиксирует I/O-сбой апстрима (502), если ещё не в терминале."""
        return self._transition(AbortState.UPSTREAM_ERROR, trigger_abort=False)

    def on_completed(self) -> bool:
        """Фиксирует штатное завершение ответа."""
        return self._transition(AbortState.COMPLETED, trigger_abort=False)

    def clear_callback(self) -> None:
        """Разрывает обратную ссылку на runtime после завершения запроса."""
        with self._lock:
            self._abort_io = None

    def classify_timeout(
        self, error: BaseException, *, client_gone: bool, deadline_passed: bool, window_expired: bool
    ) -> bool:
        """Определяет, является ли ошибка тайм-аутом (504), не маскируя client_gone."""
        if self.is_client_cancelled() or client_gone:
            return False
        return bool(isinstance(error, TimeoutError) or self.is_timeout() or deadline_passed or window_expired)


def pick_reopen_fn(internal: bool, sink: object, cb: object) -> object:
    """Выбирает pre-routing reopen callback при отсутствии запрета."""
    from core.runtime_env import flag_enabled

    allowed = (internal, not getattr(sink, "accepts_presend_errors", False), not flag_enabled("BRIDGE_TRANSPORT_ROUTING_ENABLED"))
    return cb if all(allowed) else None


def abort_socket_locked(lock: threading.Lock, stop: threading.Event, aborted: threading.Event, sock: object) -> None:
    """Потокобезопасный shutdown сокета без закрытия дескриптора."""
    import socket as _socket

    with lock:
        if stop.is_set():
            return
        aborted.set()
        if isinstance(sock, _socket.socket):
            try:
                sock.shutdown(_socket.SHUT_RDWR)
            except OSError:
                return
