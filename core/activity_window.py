from __future__ import annotations

import time
from typing import Callable


class ActivityWindow:
    def __init__(
        self,
        idle_timeout_s: float,
        safety_cap_s: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._clock = clock
        self._idle_timeout_s = float(idle_timeout_s)
        self._safety_cap_s = float(safety_cap_s)
        now = self._clock()
        self._safety_deadline: float = now + self._safety_cap_s
        self._idle_deadline: float = min(self._safety_deadline, now + self._idle_timeout_s)

    @property
    def idle_deadline(self) -> float:
        return self._idle_deadline

    @property
    def safety_deadline(self) -> float:
        return self._safety_deadline

    def touch(self) -> float:
        now = self._clock()
        if now < self._safety_deadline:
            self._idle_deadline = min(self._safety_deadline, now + self._idle_timeout_s)
        return self._idle_deadline

    def is_expired(self) -> bool:
        now = self._clock()
        return now >= self._idle_deadline or now >= self._safety_deadline

    @property
    def expired(self) -> bool:
        return self.is_expired()


SlidingActivityWindow = ActivityWindow
