"""Deterministic domain tests and simulations of HTTP-to-CLI fallback."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from zen_bridge.domain.models import (
    DeadlineBudget,
    ErrorClassification,
    ZenError,
)


@dataclass
class FakeClock:
    now: float = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        if seconds < 0.0:
            raise ValueError("A monotonic clock cannot move backwards")
        self.now += seconds


def _spend(
    budget: DeadlineBudget,
    duration_s: float,
    clock: FakeClock,
) -> None:
    """Simulate work that observes its supplied deadline."""
    remaining = budget.remaining_s()
    clock.advance(min(duration_s, remaining))
    if duration_s > remaining:
        raise TimeoutError("deadline exhausted")


@dataclass
class FakeLimiter:
    """One token, replenished after a simulated wait when unavailable."""

    tokens: int = 1
    refill_wait_s: float = 8.0

    def acquire(self, budget: DeadlineBudget, clock: FakeClock) -> None:
        if self.tokens == 0:
            _spend(budget, self.refill_wait_s, clock)
            self.tokens = 1
        self.tokens -= 1

    def refund(self) -> None:
        self.tokens = min(1, self.tokens + 1)


def _attempt_http(
    limiter: FakeLimiter,
    budget: DeadlineBudget,
    clock: FakeClock,
) -> None:
    """An HTTP attempt consumes a token and four seconds before a 504."""
    limiter.acquire(budget, clock)
    _spend(budget, 4.0, clock)
    raise ZenError.from_status_code("gateway timeout", 504)


def _attempt_cli(
    limiter: FakeLimiter,
    budget: DeadlineBudget,
    clock: FakeClock,
) -> str:
    limiter.acquire(budget, clock)
    _spend(budget, 3.0, clock)
    return "cli response"


def test_deadline_budget_decreases_with_clock() -> None:
    clock = FakeClock(now=100.0)
    budget = DeadlineBudget(timeout_s=10.0, clock=clock)

    assert budget.start_time == 100.0
    assert budget.remaining_s() == pytest.approx(10.0)

    clock.advance(2.5)

    assert budget.remaining_s() == pytest.approx(7.5)
    assert not budget.is_expired()


def test_deadline_budget_child_bounded_by_parent() -> None:
    clock = FakeClock()
    parent = DeadlineBudget(timeout_s=10.0, clock=clock)
    clock.advance(4.0)

    inherited = parent.create_child()
    oversized = parent.create_child(20.0)
    shorter = parent.create_child(2.0)

    assert inherited.remaining_s() == pytest.approx(6.0)
    assert oversized.remaining_s() == pytest.approx(6.0)
    assert shorter.remaining_s() == pytest.approx(2.0)
    assert inherited.clock is clock

    clock.advance(2.0)

    assert inherited.remaining_s() == pytest.approx(4.0)
    assert oversized.remaining_s() <= parent.remaining_s()
    assert shorter.is_expired()

    clock.advance(5.0)

    assert parent.is_expired()
    assert inherited.is_expired()
    assert oversized.is_expired()
    assert parent.create_child(20.0).is_expired()


def test_deadline_budget_expired() -> None:
    clock = FakeClock()
    budget = DeadlineBudget(timeout_s=5.0, clock=clock)

    clock.advance(5.0)

    assert budget.is_expired()
    assert budget.remaining_s() == 0.0

    clock.advance(10.0)

    assert budget.is_expired()
    assert budget.remaining_s() == 0.0


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (None, ErrorClassification.TRANSIENT),
        (429, ErrorClassification.TRANSIENT),
        (502, ErrorClassification.TRANSIENT),
        (503, ErrorClassification.TRANSIENT),
        (504, ErrorClassification.TRANSIENT),
        (400, ErrorClassification.FATAL),
        (401, ErrorClassification.FATAL),
        (403, ErrorClassification.FATAL),
    ],
)
def test_error_classification_transient_vs_fatal(
    status_code: int | None,
    expected: ErrorClassification,
) -> None:
    error = ZenError.from_status_code("upstream failure", status_code)

    assert ErrorClassification.from_status_code(status_code) is expected
    assert error.classification is expected
    assert error.retryable is (expected is ErrorClassification.TRANSIENT)
    assert error.status_code == (500 if status_code is None else status_code)
    assert error.message == "upstream failure"
    assert str(error) == "upstream failure"


def test_fallback_repro_504_exhaustion_without_budget_refund() -> None:
    """Reproduce both bugs: a leaked token and a restarted timeout."""
    clock = FakeClock()
    budget = DeadlineBudget(timeout_s=10.0, clock=clock)
    limiter = FakeLimiter()

    with pytest.raises(ZenError) as failure:
        _attempt_http(limiter, budget, clock)

    assert failure.value.status_code == 504
    assert failure.value.classification is ErrorClassification.TRANSIENT
    assert limiter.tokens == 0
    assert budget.remaining_s() == pytest.approx(6.0)

    # Bug: no refund, and the original timeout replaces remaining_s().
    restarted_budget = DeadlineBudget(timeout_s=10.0, clock=clock)
    with pytest.raises(TimeoutError, match="deadline exhausted"):
        _attempt_cli(limiter, restarted_budget, clock)

    assert clock.now == pytest.approx(14.0)
    assert budget.is_expired()
    assert restarted_budget.is_expired()
    assert limiter.tokens == 0


def test_fallback_success_with_budget_preservation_and_refund() -> None:
    """Refund admission and propagate only the original remaining time."""
    clock = FakeClock()
    budget = DeadlineBudget(timeout_s=10.0, clock=clock)
    limiter = FakeLimiter()

    with pytest.raises(ZenError) as failure:
        _attempt_http(limiter, budget, clock)

    assert failure.value.retryable
    assert failure.value.classification is ErrorClassification.TRANSIENT
    assert limiter.tokens == 0

    limiter.refund()
    fallback_budget = budget.create_child()
    assert limiter.tokens == 1
    assert fallback_budget.timeout_s == pytest.approx(6.0)

    result = _attempt_cli(limiter, fallback_budget, clock)

    assert result == "cli response"
    assert clock.now == pytest.approx(7.0)
    assert budget.remaining_s() == pytest.approx(3.0)
    assert fallback_budget.remaining_s() == pytest.approx(3.0)
    assert not budget.is_expired()
    assert not fallback_budget.is_expired()
    assert limiter.tokens == 0
