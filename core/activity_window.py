from __future__ import annotations

import threading
import time
from typing import Callable


class ActivityWindow:
    def __init__(
        self,
        idle_timeout_s: float = 5.0,
        safety_cap_s: float = 3600.0,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._clock = clock
        self._idle_timeout_s = float(idle_timeout_s)
        self._safety_cap_s = float(safety_cap_s)
        now = self._clock()
        self._safety_deadline = now + self._safety_cap_s
        self._idle_deadline = min(self._safety_deadline, now + self._idle_timeout_s)
        self._lock = threading.Lock()

    def touch(self) -> None:
        with self._lock:
            now = self._clock()
            self._idle_deadline = min(self._safety_deadline, now + self._idle_timeout_s)

    def expired(self) -> bool:
        with self._lock:
            return self._clock() >= self._idle_deadline

    def remaining(self) -> float:
        with self._lock:
            return max(0.0, self._idle_deadline - self._clock())


class MessageReader:
    def __init__(self, window: ActivityWindow) -> None:
        self._window = window

    def read(self, chunks: list[bytes]) -> list[bytes]:
        result: list[bytes] = []
        for chunk in chunks:
            if chunk.strip():
                self._window.touch()
                result.append(chunk)
        return result


def message_has_useful_data(chunk: bytes) -> bool:
    return bool(chunk.strip())
