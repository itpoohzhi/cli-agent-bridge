from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from core.adaptive_admission import (
    AdaptiveAdmissionRegistry,
    AdmissionKey,
    AdmissionSnapshot,
    OutcomeKind,
    canonical_key,
)


def make_key(
    index: int,
    *,
    backend: str = "agy_upstream",
    model: str | None = None,
) -> AdmissionKey:
    return canonical_key("chat", backend, model or f"model-{index}")


def bucket_limit(snapshot: AdmissionSnapshot, key: AdmissionKey) -> int:
    for candidate, limit in snapshot.bucket_limits:
        if candidate == key:
            return limit
    raise AssertionError(f"missing bucket: {key}")


def warm_to_ceiling(registry: AdaptiveAdmissionRegistry, key: AdmissionKey) -> None:
    for index in range(100):
        decision = registry.acquire(key, float(index))
        assert decision.admitted
        registry.release(
            decision.ticket_id,
            float(index),
            outcome=OutcomeKind.OK,
            ttfc_ms=1000.0,
        )
        if bucket_limit(registry.health_snapshot(float(index)), key) == 16:
            return
    raise AssertionError("bucket did not reach the hard ceiling")


def test_module_is_zero_io_by_ast() -> None:
    path = Path(__file__).parents[1] / "core" / "adaptive_admission.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    allowed = {"__future__", "collections", "dataclasses", "enum", "typing", "math"}
    forbidden_imports = {
        "os", "sys", "socket", "subprocess", "sqlite3", "threading", "time",
        "datetime", "pathlib", "shutil", "tempfile",
    }
    forbidden_calls = {"open", "print", "input", "__import__"}
    assert source.splitlines()[0] == "from __future__ import annotations"
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "") in allowed
        elif isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] not in forbidden_imports for alias in node.names)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in forbidden_calls


def test_capacity_cuts_follow_floor_progression() -> None:
    registry = AdaptiveAdmissionRegistry()
    key = make_key(0)
    now_s = 0.0
    for expected in (4, 2, 1):
        decision = registry.acquire(key, now_s)
        assert decision.admitted
        registry.release(
            decision.ticket_id,
            now_s,
            outcome=OutcomeKind.CAPACITY_EXHAUSTED,
        )
        assert bucket_limit(registry.health_snapshot(now_s), key) == expected
        now_s += 100.0


def test_hierarchical_ceiling_accounts_for_external_holders() -> None:
    registry = AdaptiveAdmissionRegistry()
    first_key = make_key(1)
    second_key = make_key(2)
    warm_to_ceiling(registry, first_key)
    tickets: list[int] = []
    for _ in range(8):
        decision = registry.acquire(first_key, 200.0, external_held=5)
        assert decision.admitted
        tickets.append(decision.ticket_id)
    for _ in range(3):
        decision = registry.acquire(second_key, 200.0, external_held=5)
        assert decision.admitted
        tickets.append(decision.ticket_id)
    blocked = registry.acquire(second_key, 200.0, external_held=5)
    assert not blocked.admitted
    assert blocked.status_code == 503
    assert blocked.retry_after_s > 0.0
    assert blocked.reason == "backend_ceiling"
    for ticket_id in tickets:
        registry.release(ticket_id, 201.0, outcome=OutcomeKind.CANCELLED)


def test_ewma_gate_grows_healthy_and_freezes_saturated_bucket() -> None:
    healthy = AdaptiveAdmissionRegistry()
    healthy_key = make_key(3)
    for index in range(8):
        decision = healthy.acquire(healthy_key, float(index))
        assert decision.admitted
        healthy.release(
            decision.ticket_id,
            float(index),
            outcome=OutcomeKind.OK,
            ttfc_ms=38815.0,
        )
    assert bucket_limit(healthy.health_snapshot(8.0), healthy_key) == 9
    saturated = AdaptiveAdmissionRegistry()
    saturated_key = make_key(4)
    for index in range(8):
        decision = saturated.acquire(saturated_key, float(index))
        assert decision.admitted
        saturated.release(
            decision.ticket_id,
            float(index),
            outcome=OutcomeKind.OK,
            ttfc_ms=114800.0,
        )
    assert bucket_limit(saturated.health_snapshot(8.0), saturated_key) == 8


def test_recovery_allows_one_probe_and_backoff_grows() -> None:
    registry = AdaptiveAdmissionRegistry()
    key = make_key(5)
    initial = registry.acquire(key, 0.0)
    registry.release(initial.ticket_id, 0.0, outcome=OutcomeKind.CAPACITY_EXHAUSTED)
    first_wait = registry.acquire(key, 1.0)
    assert not first_wait.admitted
    probe = registry.acquire(key, 2.0)
    assert probe.admitted
    concurrent = registry.acquire(key, 2.0)
    assert not concurrent.admitted
    assert concurrent.reason == "recovering_probe"
    registry.release(probe.ticket_id, 2.0, outcome=OutcomeKind.CAPACITY_EXHAUSTED)
    second_wait = registry.acquire(key, 2.1)
    assert not second_wait.admitted
    assert second_wait.retry_after_s > first_wait.retry_after_s
    next_probe = registry.acquire(key, 6.0)
    assert next_probe.admitted
    registry.release(next_probe.ticket_id, 6.0, outcome=OutcomeKind.CANCELLED)


def test_active_buckets_force_bounded_overflow_during_140_key_churn() -> None:
    registry = AdaptiveAdmissionRegistry()
    tickets: list[int] = []
    for index in range(128):
        key = make_key(index, backend=f"backend-{index}")
        decision = registry.acquire(key, 0.0)
        assert decision.admitted and not decision.overflowed
        tickets.append(decision.ticket_id)
    overflow = registry.acquire(make_key(128, backend="overflow-0"), 0.0)
    assert overflow.admitted and overflow.overflowed
    for index in range(1, 20):
        rejected = registry.acquire(
            make_key(128 + index, backend=f"overflow-{index}"),
            0.0,
        )
        assert not rejected.admitted and rejected.overflowed
    snapshot = registry.health_snapshot(0.0)
    assert len(snapshot.bucket_limits) == 128
    assert snapshot.pinned_buckets == 128
    assert snapshot.overflow_active
    registry.release(overflow.ticket_id, 1.0, outcome=OutcomeKind.CANCELLED)
    for ticket_id in tickets:
        registry.release(ticket_id, 1.0, outcome=OutcomeKind.CANCELLED)


def test_idle_degraded_bucket_unpins_after_stale_ttl() -> None:
    registry = AdaptiveAdmissionRegistry()
    for index in range(128):
        decision = registry.acquire(make_key(index), 0.0)
        assert decision.admitted
        registry.release(
            decision.ticket_id,
            0.0,
            outcome=OutcomeKind.CAPACITY_EXHAUSTED,
        )
    overflow = registry.acquire(make_key(200), 1.0)
    assert overflow.admitted and overflow.overflowed
    registry.release(overflow.ticket_id, 1.0, outcome=OutcomeKind.CANCELLED)
    replacement = registry.acquire(make_key(201), 301.0)
    assert replacement.admitted
    assert not replacement.overflowed
    assert len(registry.health_snapshot(301.0).bucket_limits) == 128
    registry.release(replacement.ticket_id, 301.0, outcome=OutcomeKind.CANCELLED)


def test_retry_jitter_counter_decay_and_snapshot_immutability() -> None:
    key = make_key(6)
    first_registry = AdaptiveAdmissionRegistry()
    first = first_registry.acquire(key, 0.0)
    first_registry.release(
        first.ticket_id, 0.0, outcome=OutcomeKind.CAPACITY_EXHAUSTED
    )
    first_retry = first_registry.acquire(key, 0.5)
    second_registry = AdaptiveAdmissionRegistry()
    second = second_registry.acquire(key, 0.0)
    second_registry.release(
        second.ticket_id, 0.0, outcome=OutcomeKind.CAPACITY_EXHAUSTED
    )
    second_retry = second_registry.acquire(key, 0.5)
    assert first_retry.retry_after_s == second_retry.retry_after_s
    probe = first_registry.acquire(key, 31.0)
    assert probe.admitted
    first_registry.release(
        probe.ticket_id, 31.0, outcome=OutcomeKind.CAPACITY_EXHAUSTED
    )
    assert first_registry.health_snapshot(31.0).capacity_hits_60s == 2
    snapshot = first_registry.health_snapshot(61.0)
    assert snapshot.capacity_hits_60s == 1
    assert first_registry.health_snapshot(92.0).capacity_hits_60s == 0
    with pytest.raises(FrozenInstanceError):
        setattr(snapshot, "shed_total", 999)
