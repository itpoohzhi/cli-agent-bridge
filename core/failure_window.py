"""Окно недавних сбоев (AD-003, BND-002): владелец состояния `FailureWindow._events`.

Потокобезопасный (threading.Lock), ограниченный `deque(maxlen)` с TTL-эвикцией по `window_s`.
Время инжектируется параметром `now` (в тестах — FakeClock); изнутри часы не читаются.
Наружу отдаются только числа и копии-кортежи, но не сам контейнер.
"""

from __future__ import annotations

import threading
from collections import deque

DEFAULT_WINDOW_S = 60.0
DEFAULT_MAXLEN = 256


class FailureWindow:
    """Метки времени недавних транспортных сбоев в скользящем окне."""

    def __init__(self, window_s: float = DEFAULT_WINDOW_S, maxlen: int = DEFAULT_MAXLEN) -> None:
        if not window_s > 0:
            raise ValueError("window_s must be positive")
        if int(maxlen) < 1:
            raise ValueError("maxlen must be >= 1")
        self._window_s = float(window_s)
        self._lock = threading.Lock()
        self._events: deque[float] = deque(maxlen=int(maxlen))

    def _evict(self, now: float) -> None:
        """Убрать события старше окна (вызывать под замком)."""
        horizon = now - self._window_s
        while self._events and self._events[0] <= horizon:
            _ = self._events.popleft()

    def record(self, now: float) -> int:
        """Зафиксировать сбой в момент `now`; вернуть число событий в окне."""
        with self._lock:
            self._evict(now)
            self._events.append(now)
            return len(self._events)

    def recent_count(self, now: float) -> int:
        """Число сбоев в окне `(now - window_s, now]` после эвикции."""
        with self._lock:
            self._evict(now)
            return len(self._events)

    def snapshot(self, now: float) -> tuple[float, ...]:
        """Неизменяемая копия меток времени в окне."""
        with self._lock:
            self._evict(now)
            return tuple(self._events)

    def clear(self) -> None:
        """Сбросить окно (тесты, рестарт политики)."""
        with self._lock:
            self._events.clear()
