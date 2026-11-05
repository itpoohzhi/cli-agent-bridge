"""Circuit Breaker, Serve Health и контейнер защит уровня процесса."""

from __future__ import annotations

import random
import threading
import time
from collections.abc import Callable

from zen_bridge.adapters.resilience import _RetryBudget, _SlotBulkhead, _SpawnRateLimiter


class _ServeHealth:
    """Sticky деградация serve по протокольным отказам: 3 отказа, TTL 120 с."""

    def __init__(self, threshold: int = 3, ttl_s: float = 120.0) -> None:
        self.threshold = threshold
        self.ttl_s = ttl_s
        self.failures = 0
        self._degraded_until = 0.0
        self._lock = threading.Lock()

    def record_failure(self, now: float | None = None) -> None:
        """Засчитать протокольный отказ serve."""
        with self._lock:
            self.failures += 1
            if self.failures >= self.threshold:
                self._degraded_until = (
                    time.monotonic() if now is None else now
                ) + self.ttl_s

    def record_success(self) -> None:
        """Сбросить деградацию после успешной попытки."""
        with self._lock:
            self.failures = 0
            self._degraded_until = 0.0

    def is_degraded(self, now: float | None = None) -> bool:
        """Истёк ли sticky TTL деградации."""
        with self._lock:
            at = time.monotonic() if now is None else now
            if self._degraded_until and at >= self._degraded_until:
                self.failures = 0
                self._degraded_until = 0.0
                return False
            return bool(self._degraded_until and at < self._degraded_until)


class _UpstreamBreaker:
    """Circuit Breaker зависимости: CLOSED -> OPEN -> HALF_OPEN."""

    def __init__(
        self,
        fail_threshold: int = 5,
        reset_timeout_s: float = 30.0,
        clock_fn: Callable[[], float] = time.monotonic,
        rng_fn: Callable[[float, float], float] = random.uniform,
        max_half_open_probes: int = 1,
        log_fn: Callable[[str], None] | None = None,
    ) -> None:
        self._threshold = fail_threshold
        self._reset_s = reset_timeout_s
        self._clock = clock_fn
        self._rng = rng_fn
        self._max_probes = max_half_open_probes
        self._log_fn = log_fn
        self._lock = threading.Lock()
        self._state = "CLOSED"
        self._failures = 0
        self._open_until = 0.0
        self._probes = 0
        self._probe_started = 0.0
        self.max_half_open_probes = max_half_open_probes

    def _say(self, msg: str) -> None:
        if self._log_fn is not None:
            self._log_fn(msg)

    def _refresh(self, now: float) -> None:
        if self._state == "OPEN" and now >= self._open_until:
            self._state = "HALF_OPEN"
            self._probes = 0
            self._say("circuit_breaker state=HALF_OPEN")

    @property
    def state(self) -> str:
        with self._lock:
            self._refresh(self._clock())
            return self._state

    def is_blocking(self) -> bool:
        return self.state == "OPEN"

    def allow(self) -> bool:
        with self._lock:
            now = self._clock()
            self._refresh(now)
            if self._state == "CLOSED":
                return True
            if self._state == "OPEN":
                return False
            if (
                self._probes >= self._max_probes
                and now - self._probe_started < self._reset_s
            ):
                return False
            self._probes = 1 if self._probes >= self._max_probes else self._probes + 1
            self._probe_started = now
            return True

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            if self._state != "CLOSED":
                self._state = "CLOSED"
                self._probes = 0
                self._say("circuit_breaker state=CLOSED")

    def record_failure(self) -> None:
        with self._lock:
            now = self._clock()
            self._refresh(now)
            if self._state == "OPEN":
                return
            self._failures += 1
            if self._state == "HALF_OPEN" or self._failures >= self._threshold:
                cooldown = self._reset_s * self._rng(0.8, 1.2)
                self._state = "OPEN"
                self._open_until = now + cooldown
                self._probes = 0
                self._say(
                    f"circuit_breaker state=OPEN failures={self._failures} cooldown_s={cooldown:.1f}"
                )


class _Resilience:
    """Набор process-level защит одного сервера."""

    def __init__(
        self,
        max_concurrent: int = 16,
        max_waiters: int = 64,
        spawn_rate_per_s: float = 1.0,
        spawn_burst: float = 1.0,
        fail_threshold: int = 5,
        reset_timeout_s: float = 30.0,
        log_fn: Callable[[str], None] | None = None,
        serve_health: _ServeHealth | None = None,
    ) -> None:
        self.slots = _SlotBulkhead(
            max_concurrent=max_concurrent, max_waiters=max_waiters
        )
        self.spawn_limiter = _SpawnRateLimiter(spawn_rate_per_s, spawn_burst)
        self.retry_budget = _RetryBudget()
        self.breaker = _UpstreamBreaker(
            fail_threshold=fail_threshold,
            reset_timeout_s=reset_timeout_s,
            log_fn=log_fn,
        )
        self.serve_health = serve_health if serve_health is not None else _ServeHealth()
