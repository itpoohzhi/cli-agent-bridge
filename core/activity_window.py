import time


class SlidingActivityWindow:
    def __init__(self, idle_timeout_s: float, safety_cap_s: float | None = None):
        self._idle_timeout_s = float(idle_timeout_s)
        self._safety_cap_s = float(
            safety_cap_s if safety_cap_s is not None else idle_timeout_s
        )
        self._last_touch = time.monotonic()
        self._deadline = self._compute_deadline(self._last_touch)

    def _compute_deadline(self, now: float) -> float:
        deadline = now + self._idle_timeout_s
        cap = now + self._safety_cap_s
        return min(deadline, cap)

    def touch(self) -> None:
        self._last_touch = time.monotonic()
        self._deadline = self._compute_deadline(self._last_touch)

    @property
    def idle_deadline(self) -> float:
        return self._deadline

    @property
    def expired(self) -> bool:
        return time.monotonic() > self._deadline
