"""Классы устойчивости и защиты процессов: gate, bulkhead, rate limiter, retry budget."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable


class _StartupGate:
    """Сериализует старт `opencode run`: sqlite opencode роняет «database is locked»."""

    def __init__(
        self,
        wait_s: float = 30.0,
        gate_s: float = 3.0,
        lock: threading.Lock | None = None,
        log_fn: Callable[[str], None] | None = None,
    ) -> None:
        self._wait_s = wait_s
        self._gate_s = gate_s
        self._lock = lock or threading.Lock()
        self._log = log_fn
        self._held = False
        self._guard = threading.Lock()
        self._timer: threading.Timer | None = None

    def acquire(
        self,
        deadline: float | None = None,
        is_client_gone: Callable[[], bool] | None = None,
    ) -> None:
        wait_until = time.monotonic() + max(0.0, self._wait_s)
        while True:
            now = time.monotonic()
            if (is_client_gone is not None and is_client_gone()) or (
                deadline is not None and now >= deadline
            ):
                return
            remaining = max(
                0.0,
                min(wait_until, deadline if deadline is not None else wait_until) - now,
            )
            if self._lock.acquire(timeout=min(0.05, remaining)):
                break
            if time.monotonic() >= wait_until:
                if self._log is not None:
                    self._log(
                        f"startup_gate_timeout wait_s={self._wait_s:.1f}, starting without the gate"
                    )
                return
        with self._guard:
            self._held = True
        timer = threading.Timer(self._gate_s, self.release)
        timer.daemon = True
        self._timer = timer
        timer.start()

    def release(self) -> None:
        with self._guard:
            if not self._held:
                return
            self._held = False
            timer, self._timer = self._timer, None
        if timer is not None:
            timer.cancel()
        self._lock.release()


class _SlotBulkhead:
    """Слоты параллельных `opencode run` с ограниченным ожиданием (bulkhead)."""

    def __init__(
        self,
        max_concurrent: int = 16,
        max_waiters: int = 64,
        wait_timeout_s: float = 120.0,
        clock_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max = max_concurrent
        self._max_waiters = max_waiters
        self._wait_timeout_s = wait_timeout_s
        self._clock = clock_fn
        self._cond = threading.Condition(threading.Lock())
        self.in_use = 0
        self.waiters = 0

    def acquire_ex(self, timeout: float | None = None) -> str:
        wait = (
            self._wait_timeout_s
            if timeout is None
            else min(timeout, self._wait_timeout_s)
        )
        with self._cond:
            if self.in_use < self._max:
                self.in_use += 1
                return "ok"
            if self.waiters >= self._max_waiters:
                return "overflow"
            self.waiters += 1
            try:
                deadline = self._clock() + wait
                while self.in_use >= self._max:
                    remaining = deadline - self._clock()
                    if remaining <= 0:
                        return "timeout"
                    self._cond.wait(remaining)
                self.in_use += 1
                return "ok"
            finally:
                self.waiters -= 1

    def acquire(self, timeout: float | None = None) -> bool:
        return self.acquire_ex(timeout) == "ok"

    def release(self) -> None:
        with self._cond:
            if self.in_use > 0:
                self.in_use -= 1
            self._cond.notify()


class _SpawnRateLimiter:
    """Token bucket запусков процессов (GCRA-подобный механизм)."""

    def __init__(
        self,
        rate_rps: float = 1.0,
        burst: float = 1.0,
        clock_fn: Callable[[], float] = time.monotonic,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self._rate = max(rate_rps, 1e-9)
        self._burst = max(burst, 1.0)
        self._clock = clock_fn
        self._sleep = sleep_fn
        self._lock = threading.Lock()
        self._tokens = self._burst
        self._last = clock_fn()

    def acquire(
        self,
        max_wait_s: float | None = None,
        deadline: float | None = None,
        is_client_gone: Callable[[], bool] | None = None,
    ) -> bool:
        if (is_client_gone is not None and is_client_gone()) or (
            deadline is not None and self._clock() >= deadline
        ):
            return False
        with self._lock:
            now = self._clock()
            self._tokens = min(
                self._burst, self._tokens + max(0.0, now - self._last) * self._rate
            )
            self._last = now
            wait = max(0.0, (1.0 - self._tokens) / self._rate)
            if max_wait_s is not None and wait > max_wait_s:
                return False
            if deadline is not None and wait >= deadline - now:
                return False
            self._tokens -= 1.0
        if deadline is None and is_client_gone is None:
            if wait > 0:
                self._sleep(wait)
            return True
        ready_at = now + wait
        while True:
            now = self._clock()
            if (is_client_gone is not None and is_client_gone()) or (
                deadline is not None and now >= deadline
            ):
                self.refund()
                return False
            if now >= ready_at:
                break
            self._sleep(
                min(
                    0.05,
                    ready_at - now,
                    deadline - now if deadline is not None else 0.05,
                )
            )
        return True

    def refund(self, amount: float = 1.0) -> None:
        with self._lock:
            self._tokens = min(self._burst, self._tokens + amount)


class _RetryBudget:
    """Process-level бюджет повторных запусков."""

    def __init__(
        self,
        capacity: float = 10.0,
        per_request_refill: float = 0.1,
        reserve_rps: float = 0.2,
        clock_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self._capacity = capacity
        self._per_request = per_request_refill
        self._reserve_rps = reserve_rps
        self._clock = clock_fn
        self._lock = threading.Lock()
        self.tokens = float(self._capacity)
        self._last = clock_fn()

    def _refill_time(self) -> None:
        now = self._clock()
        self.tokens = min(
            self._capacity, self.tokens + max(0.0, now - self._last) * self._reserve_rps
        )
        self._last = now

    def on_request(self) -> None:
        with self._lock:
            self._refill_time()
            self.tokens = min(self._capacity, self.tokens + self._per_request)

    def try_acquire_retry(self) -> bool:
        with self._lock:
            self._refill_time()
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            return False
