"""L1: политика невидимого повтора и бюджет (AD-003, VER-005)."""

from __future__ import annotations

import ast
import math
import sys
from dataclasses import replace
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import core.invisible_retry_policy as policy  # noqa: E402
from core.transport_failure_contracts import (  # noqa: E402
    DeliveryFacts,
    RetryAttemptState,
    RetryBudgetConfig,
)

_CFG = RetryBudgetConfig(max_retries=1, retry_total_budget_s=1020.0, client_timeout_s=600.0, pause_max_s=15.0)
_CLEAN = DeliveryFacts()


def _state(attempt: int = 1, elapsed: float = 23.0, last: float = 23.0, recent: int = 0, jitter: float = 0.0) -> RetryAttemptState:
    return RetryAttemptState(attempt, elapsed, last, recent, jitter)


def test_t_total_eff_is_min_of_total_and_client_timeout() -> None:
    assert policy.t_total_eff(_CFG) == 600.0
    assert policy.t_total_eff(replace(_CFG, client_timeout_s=2000.0)) == 1020.0


def test_t_attempt_cap_matches_architecture_value() -> None:
    assert policy.t_attempt_cap(_CFG) == pytest.approx(292.5)


def test_keepalive_only_facts_allow_retry() -> None:
    facts = DeliveryFacts(keepalive_count=7)
    decision = policy.may_retry_invisibly(facts, _CFG, _state())
    assert decision.allowed is True
    assert decision.reason == "retry_allowed"
    assert decision.retry_timeout_s == pytest.approx(292.5)


@pytest.mark.parametrize(
    "facts",
    [
        DeliveryFacts(content_bytes=1),
        DeliveryFacts(reasoning_bytes=1),
        DeliveryFacts(tool_calls=1),
        DeliveryFacts(tool_events=1),
        DeliveryFacts(keepalive_count=3, content_bytes=5),
    ],
)
def test_any_delivery_forbids_invisible_retry(facts: DeliveryFacts) -> None:
    decision = policy.may_retry_invisibly(facts, _CFG, _state())
    assert (decision.allowed, decision.reason) == (False, "content_delivered")


@pytest.mark.parametrize("max_retries", [0, -1, -5])
def test_non_positive_max_retries_disables_retry(max_retries: int) -> None:
    decision = policy.may_retry_invisibly(_CLEAN, replace(_CFG, max_retries=max_retries), _state())
    assert (decision.allowed, decision.reason) == (False, "retries_disabled")


@pytest.mark.parametrize("attempt", [0, -1, 2, 3])
def test_attempt_outside_retry_range_is_denied(attempt: int) -> None:
    decision = policy.may_retry_invisibly(_CLEAN, _CFG, _state(attempt=attempt))
    assert (decision.allowed, decision.reason) == (False, "max_retries_exhausted")


@pytest.mark.parametrize(
    "cfg",
    [
        replace(_CFG, retry_total_budget_s=0.0),
        replace(_CFG, retry_total_budget_s=-10.0),
        replace(_CFG, client_timeout_s=0.0),
        replace(_CFG, client_timeout_s=-1.0),
        replace(_CFG, client_timeout_s=math.nan),
        replace(_CFG, retry_total_budget_s=10.0, pause_max_s=15.0),
    ],
)
def test_degenerate_budget_is_denied(cfg: RetryBudgetConfig) -> None:
    decision = policy.may_retry_invisibly(_CLEAN, cfg, _state(elapsed=0.0, last=0.0))
    assert (decision.allowed, decision.reason) == (False, "budget_non_positive")


def test_gate_elapsed_pause_last_attempt_within_total() -> None:
    """elapsed + pause + last_attempt <= T_total_eff; граница включительно."""
    edge = policy.may_retry_invisibly(_CLEAN, _CFG, _state(elapsed=500.0, last=100.0))
    over = policy.may_retry_invisibly(_CLEAN, _CFG, _state(elapsed=501.0, last=100.0))
    assert edge.allowed is True
    assert edge.retry_timeout_s == pytest.approx(100.0)
    assert (over.allowed, over.reason) == (False, "budget_exhausted")


def test_remaining_budget_non_positive_denies_retry() -> None:
    decision = policy.may_retry_invisibly(_CLEAN, _CFG, _state(elapsed=600.0, last=0.0))
    assert (decision.allowed, decision.reason) == (False, "budget_exhausted")


def test_retry_timeout_is_capped_by_remaining_after_pause() -> None:
    state = _state(elapsed=400.0, last=10.0, jitter=1.0)
    decision = policy.may_retry_invisibly(_CLEAN, _CFG, state)
    assert decision.allowed is True
    assert decision.pause_s == pytest.approx(15.0)
    assert decision.retry_timeout_s == pytest.approx(600.0 - 400.0 - 15.0)


def test_pause_is_full_jitter_without_recent_failures() -> None:
    assert policy.compute_pause_s(_CFG, _state(jitter=0.0)) == 0.0
    assert policy.compute_pause_s(_CFG, _state(jitter=0.5)) == pytest.approx(7.5)
    assert policy.compute_pause_s(_CFG, _state(jitter=1.0)) == pytest.approx(15.0)


def test_correlated_window_adds_monotonic_pause_capped_at_pause_max() -> None:
    pauses = [policy.compute_pause_s(_CFG, _state(recent=n, jitter=0.0)) for n in (0, 1, 3, 10, 1000)]
    assert pauses == sorted(pauses)
    assert pauses[0] == 0.0
    assert all(0.0 <= p <= 15.0 for p in pauses)
    assert policy.compute_pause_s(_CFG, _state(recent=50, jitter=1.0)) == 15.0


@pytest.mark.parametrize("jitter", [-1.0, 2.0, math.nan, math.inf, "x"])
def test_invalid_jitter_is_clamped_into_pause_range(jitter: object) -> None:
    pause = policy.compute_pause_s(_CFG, _state(jitter=jitter))  # type: ignore[arg-type]
    assert 0.0 <= pause <= 15.0


def test_negative_recent_failures_do_not_reduce_pause() -> None:
    assert policy.compute_pause_s(_CFG, _state(recent=-5, jitter=0.0)) == 0.0


def test_negative_elapsed_and_last_are_treated_as_zero() -> None:
    decision = policy.may_retry_invisibly(_CLEAN, _CFG, _state(elapsed=-5.0, last=-1.0))
    assert decision.allowed is True


def test_decision_is_deterministic() -> None:
    state = _state(recent=3, jitter=0.25)
    assert policy.may_retry_invisibly(_CLEAN, _CFG, state) == policy.may_retry_invisibly(_CLEAN, _CFG, state)


def test_module_is_pure_domain_without_forbidden_imports() -> None:
    """BND-001: ни threading/time/os/asyncio, ни обращений к environ."""
    tree = ast.parse(Path(policy.__file__).read_text(encoding="utf-8"))
    imported = {
        (n.module or "") if isinstance(n, ast.ImportFrom) else a.name
        for n in ast.walk(tree)
        if isinstance(n, (ast.Import, ast.ImportFrom))
        for a in (n.names if isinstance(n, ast.Import) else [n])
    }
    forbidden = {"os", "time", "threading", "asyncio", "subprocess", "socket", "random"}
    assert not {i.split(".")[0] for i in imported} & forbidden
    assert "environ" not in Path(policy.__file__).read_text(encoding="utf-8")
