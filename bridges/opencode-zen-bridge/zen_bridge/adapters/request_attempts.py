"""Учёт запусков и aux-бюджета попыток HTTP-запроса."""

from __future__ import annotations

import random
import threading
import time
from collections.abc import Callable

from zen_bridge.adapters.breaker import _Resilience


class ServeStartupDeadlineExceeded(Exception):
    """Aux IO budget исчерпан до старта попытки."""


class _AuxIoBudget:
    """Общий бюджет вспомогательного I/O одного запроса через все попытки."""

    def __init__(
        self,
        budget_s: float = 60.0,
        clock_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self._budget_s = budget_s
        self._clock = clock_fn
        self._spent_s = 0.0
        self._lock = threading.Lock()

    def now_s(self) -> float:
        return self._clock()

    def spent_s(self) -> float:
        with self._lock:
            return self._spent_s

    def remaining_s(self) -> float:
        return max(0.0, self._budget_s - self.spent_s())

    def exhausted(self) -> bool:
        return self.remaining_s() <= 0.0

    def check(self) -> None:
        if self.exhausted():
            raise ServeStartupDeadlineExceeded("aux io budget exhausted")

    def deadline(self, request_deadline: float | None = None) -> float:
        phase_deadline = self._clock() + self.remaining_s()
        if request_deadline is None:
            return phase_deadline
        return min(phase_deadline, request_deadline)

    def debit_elapsed(self, started: float) -> None:
        elapsed = max(0.0, self._clock() - started)
        with self._lock:
            self._spent_s = min(self._budget_s, self._spent_s + elapsed)

    def debit_seconds(self, seconds: float) -> None:
        with self._lock:
            self._spent_s = min(self._budget_s, self._spent_s + max(0.0, seconds))


def _default_retry_backoff_s(retry: int, rng_fn: Callable[[float, float], float]) -> float:
    """Экспоненциальный backoff с jitter: 0.1s, 0.2s, 0.4s... (cap 2.0s)."""
    base = min(2.0, 0.1 * (2 ** max(0, retry - 1)))
    return base * rng_fn(0.8, 1.2)


class _RequestAttempts:
    """Учёт запусков одного HTTP-запроса."""

    def __init__(
        self,
        res: _Resilience,
        deadline: float,
        max_total: int | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        rng_fn: Callable[[float, float], float] = random.uniform,
        use_breaker: bool = True,
        max_quota_rotations: int | None = None,
        log_fn: Callable[[str], None] | None = None,
        backoff_fn: Callable[[int, Callable[[float, float], float]], float] | None = None,
    ) -> None:
        self.res = res
        self.t0 = time.monotonic()
        self.deadline = deadline
        self.use_breaker = use_breaker
        self.max_total = 5 if max_total is None else max_total
        self.max_quota_rotations = 3 if max_quota_rotations is None else max_quota_rotations
        self.quota_rotations = 0
        self.total_spawns = 0
        self.spawn_reasons: list[str] = []
        self._next_spawn_reason = "initial"
        self.retries = 0
        self.signal = 0
        self.exit_reason = ""
        self._pending_failure = False
        self._sleep = sleep_fn
        self._rng = rng_fn
        self._log = log_fn
        self._backoff = backoff_fn or _default_retry_backoff_s
        self.aux_budget = _AuxIoBudget()
        if hasattr(res, "retry_budget") and hasattr(res.retry_budget, "on_request"):
            res.retry_budget.on_request()

    def _say(self, msg: str) -> None:
        if self._log is not None:
            self._log(msg)

    def note_spawn(self, reason: str | None = None) -> None:
        self.total_spawns += 1
        self.spawn_reasons.append(reason or self._next_spawn_reason)
        self._next_spawn_reason = "continuation"

    def can_spawn(self) -> bool:
        limit = min(5, self.max_total) + self.quota_rotations
        return self.total_spawns < limit

    def remaining_s(self) -> float:
        return max(0.0, self.deadline - time.monotonic())

    def begin_attempt(self) -> bool:
        return (
            self.can_spawn()
            and time.monotonic() < self.deadline
            and (not self.use_breaker or self.res.breaker.allow())
        )

    def allow_quota_rotation(self, reason: str = "free_quota_proxy_rotate") -> bool:
        if self.quota_rotations >= self.max_quota_rotations:
            return False
        if self.total_spawns >= min(5, self.max_total) + self.quota_rotations:
            return False
        if time.monotonic() >= self.deadline or self.aux_budget.exhausted():
            return False
        if self.use_breaker and self.res.breaker.is_blocking():
            return False
        if self.use_breaker and not self.res.breaker.allow():
            return False
        self.quota_rotations += 1
        self._next_spawn_reason = reason
        return True

    def allow_retry(self, reason: str, charge_budget: bool = True) -> bool:
        if self.total_spawns >= self.max_total:
            self._say(f"retry denied ({reason}): MAX_TOTAL_SPAWNS={self.max_total} reached")
            return False
        if time.monotonic() >= self.deadline:
            return False
        if self.aux_budget.exhausted():
            self._say(f"retry denied ({reason}): aux io budget exhausted")
            return False
        if self.use_breaker and self.res.breaker.is_blocking():
            self._say(f"retry denied ({reason}): upstream circuit open")
            return False
        if charge_budget and not self.res.retry_budget.try_acquire_retry():
            self._say(f"retry denied ({reason}): retry budget exhausted")
            return False
        self.retries += 1
        self._next_spawn_reason = reason
        delay = self._backoff(self.retries, self._rng)
        delay = min(delay, self.remaining_s(), self.aux_budget.remaining_s())
        if delay > 0:
            aux_started = self.aux_budget.now_s()
            try:
                self._sleep(delay)
            finally:
                self.aux_budget.debit_elapsed(aux_started)
        return not self.use_breaker or self.res.breaker.allow()

    def attempt_done(self, transient_failure: bool, success: bool) -> None:
        if not self.use_breaker:
            return
        if success and not transient_failure:
            self._pending_failure = False
            self.res.breaker.record_success()
        else:
            self._pending_failure = transient_failure

    def commit(self) -> None:
        if self._pending_failure:
            self._pending_failure = False
            self.res.breaker.record_failure()
