from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from decimal import ROUND_FLOOR, Decimal
from enum import Enum
from typing import final

import core.route_health_policy as routes


class ActivityState(Enum):
    INIT = "init"
    PROGRESS = "progress"
    IDLE_EXPIRED = "idle_expired"
    CAP_EXPIRED = "cap_expired"
    COMPLETED = "completed"


_COMPLETED = ActivityState.COMPLETED
_EXPIRED = frozenset((ActivityState.IDLE_EXPIRED, ActivityState.CAP_EXPIRED))


@dataclass(frozen=True)
class ActivitySnapshot:
    state: ActivityState
    had_progress: bool
    deadline_s: float
    timeout_reason: str
    timeout_limit_s: float
    elapsed_s: float


@dataclass(frozen=True)
class FinalStreamOutcome:
    state: str
    rc: int
    err: str
    timeout_limit_s: float
    had_progress: bool
    elapsed_s: float
    req_id: str
    cid: str


@dataclass(frozen=True)
class SlidingBudgetInput:
    total_budget_s: float
    reserve_s: float
    elapsed_s: float
    sliding_enabled: bool
    max_attempts: int
    attempt_index: int
    first_event_timeout_s: float
    backoff_cap_s: float


def _require(ok: bool, msg: str) -> None:
    if not ok:
        raise ValueError(msg)


def _is_finite_number(item: int | float) -> bool:
    return type(item) in (int, float) and math.isfinite(item)


def is_useful_delta(kind: str, payload: object) -> bool:
    kinds = {"content", "text", "reasoning", "reasoning_content", "tool_calls"}
    payloads = (str, bytes, bytearray, Mapping, list, tuple)
    return kind in kinds and isinstance(payload, payloads) and bool(payload)


def compute_sliding_attempt_budget_s(value: SlidingBudgetInput) -> float:
    _validate_budget_input(value)
    if not value.sliding_enabled:
        return _legacy_attempt_budget_s(value)
    horizon = Decimal(str(value.total_budget_s)) - Decimal(str(value.reserve_s))
    horizon -= Decimal(str(value.elapsed_s))
    horizon = max(Decimal(0), horizon)
    return float(horizon.quantize(Decimal("0.001"), rounding=ROUND_FLOOR))


def _validate_budget_input(value: SlidingBudgetInput) -> None:
    numbers = (
        value.total_budget_s,
        value.reserve_s,
        value.elapsed_s,
        value.first_event_timeout_s,
        value.backoff_cap_s,
    )
    finite = all(_is_finite_number(item) and item >= 0 for item in numbers)
    _require(finite, "budget values must be finite and non-negative")
    max_attempts = value.max_attempts
    attempts = type(max_attempts) is int and max_attempts >= 1
    _require(attempts, "max_attempts must be positive")
    attempt_index = value.attempt_index
    index = type(attempt_index) is int and 0 <= attempt_index < max_attempts
    _require(index, "attempt_index is outside max_attempts")


def _legacy_attempt_budget_s(value: SlidingBudgetInput) -> float:
    config = routes.RetryBudgetConfig(
        total_budget_s=value.total_budget_s,
        reserve_s=value.reserve_s,
        max_attempts=value.max_attempts,
    )
    decision = routes.compute_attempt_decision(
        config, value.attempt_index, value.elapsed_s
    )
    if not decision.allow_retry:
        return 0.0
    remaining = config.max_attempts - 1 - value.attempt_index
    horizon = Decimal(str(config.total_budget_s)) - Decimal(str(config.reserve_s))
    horizon -= Decimal(str(value.elapsed_s))
    reserved = value.first_event_timeout_s + value.backoff_cap_s
    horizon -= remaining * Decimal(str(reserved))
    cap = float(horizon.quantize(Decimal("0.001"), rounding=ROUND_FLOOR))
    effective = min(decision.attempt_budget_s, cap)
    floor = max(value.first_event_timeout_s, config.min_attempt_budget_s)
    return effective if effective >= floor else 0.0


@final
class SlidingActivityWindow:
    def __init__(self, started_at: float, first_event_timeout_s: float,
                 sliding_idle_timeout_s: float, safety_cap_s: float) -> None:
        values = (started_at, first_event_timeout_s,
                  sliding_idle_timeout_s, safety_cap_s)
        finite = all(_is_finite_number(item) for item in values)
        _require(finite, "activity window values must be finite")
        positive = min(first_event_timeout_s, sliding_idle_timeout_s, safety_cap_s) > 0
        _require(positive, "activity timeouts must be positive")
        self._started_at = float(started_at)
        self._first_event_timeout_s = float(first_event_timeout_s)
        self._sliding_idle_timeout_s = float(sliding_idle_timeout_s)
        self._safety_deadline = self._started_at + float(safety_cap_s)
        self._idle_deadline = min(
            self._started_at + self._first_event_timeout_s, self._safety_deadline
        )
        self._had_progress = False
        self._state = ActivityState.INIT

    def current_deadline(self) -> float:
        return min(self._idle_deadline, self._safety_deadline)

    def record_signal(self, kind: str, payload: object, now: float) -> bool:
        blocked = self._state is _COMPLETED or self.check_expired(now).state in _EXPIRED
        return (
            not blocked and is_useful_delta(kind, payload) and self._progress(now)
        )

    def _progress(self, now: float) -> bool:
        self._had_progress = True
        self._state = ActivityState.PROGRESS
        idle_deadline = now + self._sliding_idle_timeout_s
        self._idle_deadline = min(idle_deadline, self._safety_deadline)
        return True

    def check_expired(self, now: float) -> ActivitySnapshot:
        deadline = self.current_deadline()
        if self._state is not ActivityState.COMPLETED and now >= deadline:
            self._state = (
                ActivityState.CAP_EXPIRED
                if now >= self._safety_deadline
                else ActivityState.IDLE_EXPIRED
            )
        return self._snapshot(now)

    def mark_completed(self, now: float) -> ActivitySnapshot:
        snapshot = self.check_expired(now)
        if snapshot.state not in _EXPIRED:
            self._state = ActivityState.COMPLETED
            snapshot = self._snapshot(now)
        return snapshot

    def _snapshot(self, now: float) -> ActivitySnapshot:
        outcomes = {
            (ActivityState.CAP_EXPIRED, False): (
                "retry_budget_exhausted", self._safety_deadline - self._started_at
            ),
            (ActivityState.CAP_EXPIRED, True): (
                "retry_budget_exhausted", self._safety_deadline - self._started_at
            ),
            (ActivityState.IDLE_EXPIRED, False): (
                "first_event_timeout", self._first_event_timeout_s
            ),
            (ActivityState.IDLE_EXPIRED, True): (
                "sliding_idle_timeout", self._sliding_idle_timeout_s
            ),
        }
        reason, limit = outcomes.get((self._state, self._had_progress), ("", 0.0))
        return ActivitySnapshot(
            self._state, self._had_progress, self.current_deadline(), reason, limit,
            max(0.0, now - self._started_at),
        )


def render_final_outcome(raw_out: Mapping[str, object], snapshot: ActivitySnapshot, *,
                         req_id: str = "", cid: str = "") -> dict[str, object]:
    outcome = _final_outcome(raw_out, snapshot, req_id=req_id, cid=cid)
    return asdict(outcome)


build_final_outcome = render_final_outcome


def _final_outcome(raw_out: Mapping[str, object], snapshot: ActivitySnapshot, *,
                   req_id: str, cid: str) -> FinalStreamOutcome:
    expired = snapshot.state in _EXPIRED
    raw_rc = raw_out.get("rc", 0)
    raw_limit = raw_out.get("timeout_limit_s", snapshot.timeout_limit_s)
    valid_limit = type(raw_limit) in (int, float) and math.isfinite(raw_limit)
    limit = raw_limit if valid_limit else 0.0
    return FinalStreamOutcome(
        state="timeout" if expired else str(raw_out.get("state", "")),
        rc=124 if expired else raw_rc if type(raw_rc) is int else 0,
        err="retry_budget_exhausted" if expired else routes.redact_diagnostic_text(
            str(raw_out.get("err", ""))
        ),
        timeout_limit_s=snapshot.timeout_limit_s if expired else max(0.0, float(limit)),
        had_progress=snapshot.had_progress if expired else bool(
            raw_out.get("had_progress", snapshot.had_progress)
        ),
        elapsed_s=snapshot.elapsed_s,
        req_id=routes.redact_diagnostic_text(
            req_id if req_id else str(raw_out.get("req_id", ""))
        ),
        cid=routes.redact_diagnostic_text(
            cid if cid else str(raw_out.get("cid", ""))
        ),
    )
