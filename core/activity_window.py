from __future__ import annotations

import time
from math import isfinite
from typing import Callable, final  # noqa: UP035

from core.route_health_policy import advance_sliding_deadline


@final
class ActivityWindow:
    def __init__(
        self,
        idle_timeout_s: float,
        safety_cap_s: float,
        *,
        attempt_budget_s: float | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._clock: Callable[[], float] = clock
        self._idle_timeout_s: float = float(idle_timeout_s)
        cap = float(safety_cap_s)
        if attempt_budget_s is not None:
            budget = float(attempt_budget_s)
            if not isfinite(budget) or budget <= 0.0:
                raise ValueError("attempt_budget_s must be positive and finite")
            cap = min(cap, budget)
        self._safety_cap_s: float = cap
        self._start_s: float = self._clock()
        self._safety_deadline: float = self._start_s + self._safety_cap_s
        self._idle_deadline: float = advance_sliding_deadline(
            self._start_s, self._start_s, self._idle_timeout_s, self._safety_cap_s
        )

    @property
    def idle_deadline(self) -> float:
        return self._idle_deadline

    @property
    def safety_deadline(self) -> float:
        return self._safety_deadline

    def touch(self) -> float:
        now = self._clock()
        if now < self._safety_deadline:
            self._idle_deadline = advance_sliding_deadline(
                now, self._start_s, self._idle_timeout_s, self._safety_cap_s
            )
        return self._idle_deadline

    def is_expired(self) -> bool:
        now = self._clock()
        return now >= self._idle_deadline or now >= self._safety_deadline

    @property
    def expired(self) -> bool:
        return self.is_expired()


SlidingActivityWindow = ActivityWindow
