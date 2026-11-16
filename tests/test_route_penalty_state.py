"""L1: HALF_OPEN, fencing, долговечность и численные границы VER-023."""
from __future__ import annotations

import ast
import errno
import fcntl
import json
import multiprocessing
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import lease_identity
from core.route_penalty_state import (
    Event, LeaseConfig, LeaseFenced, Liveness, Phase, RoutePenaltyState, State, edge_key, step,
)

OWNER = dict(owner_host="local", boot_id=10, owner_pid=123, owner_started_at_utc=20)

@pytest.fixture
def tracker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RoutePenaltyState:
    monkeypatch.setattr("time.time", lambda: 1000.0)
    monkeypatch.setattr(lease_identity, "host_id", lambda: "local")
    monkeypatch.setattr(lease_identity, "boot_id", lambda: 10)
    monkeypatch.setattr(lease_identity, "process_started_at_utc", lambda _: 20)
    monkeypatch.setattr(os, "kill", lambda *_: None)
    return RoutePenaltyState(tmp_path / "state.json")

@pytest.mark.parametrize("key,low,high,default", [
    ("BRIDGE_HALF_OPEN_LEASE_TTL_S", 5, 600, 60),
    ("CLOCK_SKEW_TOLERANCE_S", 0, 60, 5),
])
@pytest.mark.parametrize("sample", ["low", "high", "below", "above", "invalid"])
def test_numeric_bounds(key: str, low: int, high: int, default: int, sample: str) -> None:
    values: dict[str, Any] = dict(low=low, high=str(high), below=low - .01, above=high + .01, invalid="nan")
    config = LeaseConfig.from_mapping({key: values[sample]})
    actual = config.lease_ttl_s if key.startswith("BRIDGE") else config.clock_skew_tolerance_s
    expected = {"low": low, "high": high}.get(sample, default)
    assert actual == expected

@pytest.mark.parametrize("value", [None, True, False, "", "bad", "inf", "-inf", float("nan"), [], 10**400])
def test_invalid_config_falls_back(value: Any) -> None:
    config = LeaseConfig.from_mapping(dict(BRIDGE_HALF_OPEN_LEASE_TTL_S=value, CLOCK_SKEW_TOLERANCE_S=value))
    assert config == LeaseConfig()

def test_environment_and_explicit_config(tracker: RoutePenaltyState, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_HALF_OPEN_LEASE_TTL_S", "600")
    monkeypatch.setenv("CLOCK_SKEW_TOLERANCE_S", "0")
    assert RoutePenaltyState(tracker.storage_path).config == LeaseConfig(600, 0)
    assert RoutePenaltyState(tracker.storage_path, LeaseConfig(5, 60)).config == LeaseConfig(5, 60)

def test_pure_lifecycle_and_abort_remaining_cooldown() -> None:
    opened = step(State(), Event("failure", 1000, 60))
    assert step(opened, Event("acquire", 1059, lease_token="a")) is opened
    lease = step(opened, Event("acquire", 1060, lease_token="a"))
    assert (lease.phase, lease.lease_epoch, lease.lease_until) == (Phase.HALF_OPEN, 1, 1120)
    aborted = step(lease, Event("abort", 1040, lease_epoch=1, lease_token="a"))
    assert (aborted.phase, aborted.penalized_until - 1040) == (Phase.OPEN, 20)
    assert step(aborted, Event("acquire", 1050, lease_token="b")) is aborted
    assert step(aborted, Event("acquire", 1060, lease_token="b")).lease_epoch == 2

@pytest.mark.parametrize("liveness", list(Liveness))
@pytest.mark.parametrize("now", [1059, 1060, 1064.999, 1065, 2000])
def test_reclaim_truth_table(liveness: Liveness, now: float) -> None:
    old = step(State(), Event("acquire", 1000, lease_token="old"))
    result = step(old, Event("acquire", now, lease_token="new", liveness=liveness))
    reclaim = liveness == Liveness.DEAD and now >= 1065
    assert (result.lease_token, result.lease_epoch) == (("new", 2) if reclaim else ("old", 1))

@pytest.mark.parametrize("action", ["abort", "success", "failure"])
@pytest.mark.parametrize("fingerprint", [(0, "old"), (1, "wrong"), (2, "old")])
def test_stale_fencing(action: str, fingerprint: tuple[int, str]) -> None:
    lease = step(State(), Event("acquire", 1000, lease_token="old"))
    with pytest.raises(LeaseFenced):
        step(lease, Event(action, 1001, lease_epoch=fingerprint[0], lease_token=fingerprint[1]))

@pytest.mark.parametrize("action,phase,until", [("success", Phase.CLOSED, 0), ("failure", Phase.OPEN, 1031)])
def test_owned_result(action: str, phase: Phase, until: float) -> None:
    lease = step(State(), Event("acquire", 1000, lease_token="own"))
    result = step(lease, Event(action, 1001, 30, 1, "own"))
    assert (result.phase, result.penalized_until, result.lease_epoch, result.lease_token) == (phase, until, 1, "")
    with pytest.raises(LeaseFenced):
        step(result, Event("abort", 1002, lease_epoch=1, lease_token="own"))

@pytest.mark.parametrize("now", [-1, True, float("inf"), float("nan"), 10**400])
def test_invalid_epoch_seconds(now: Any) -> None:
    with pytest.raises(ValueError):
        step(State(), Event("acquire", now, lease_token="x"))

def test_backend_and_legacy_projection(tracker: RoutePenaltyState) -> None:
    document = {"model": {"penalized_until": 2000, "projection": [1]}, "_meta": {"future": {"opaque": True}}}
    tracker.storage_path.write_text(json.dumps(document))
    assert tracker.is_penalized("model", "a") == (False, 0)
    assert tracker.is_penalized("model")[0] and tracker.ignored_legacy == 1
    tracker.record_start_failure("model", "failure", "a")
    assert tracker.is_penalized("model", "a") == (True, 60)
    assert tracker.is_penalized("model", "b") == (False, 0)
    stored = json.loads(tracker.storage_path.read_text())
    assert {key: stored[key] for key in document} == document

def test_store_abort_and_revoked_token(tracker: RoutePenaltyState, monkeypatch: pytest.MonkeyPatch) -> None:
    lease = tracker.acquire("m::a", OWNER)
    assert lease is not None
    assert tracker.owns("m::a", lease.lease_epoch, lease.lease_token)
    monkeypatch.setattr("time.time", lambda: 999.0)
    restored = tracker.abort("m::a", lease.lease_epoch, lease.lease_token)
    assert restored is not None and restored.phase == Phase.OPEN
    with pytest.raises(LeaseFenced):
        tracker.abort("m::a", lease.lease_epoch, lease.lease_token)
    assert not tracker.owns("m::a", lease.lease_epoch, lease.lease_token)

@pytest.mark.parametrize("alive", [True, False])
def test_store_reclaim_uses_identity(tracker: RoutePenaltyState, monkeypatch: pytest.MonkeyPatch, alive: bool) -> None:
    old = tracker.acquire("m::a", OWNER)
    assert old is not None
    monkeypatch.setattr("time.time", lambda: 1065.0)
    monkeypatch.setattr(lease_identity, "is_alive_or_unknown", Mock(return_value=alive))
    new = tracker.acquire("m::a", OWNER)
    assert (new is not None) is not alive
    assert tracker.owns("m::a", old.lease_epoch, old.lease_token) is alive
    if new is not None:
        assert new.lease_epoch == old.lease_epoch + 1
        assert new.lease_token != old.lease_token

@pytest.mark.parametrize("kind", ["foreign", "missing", "permission", "birth", "dead"])
def test_real_identity_reclaim_rules(tracker: RoutePenaltyState, monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    first = tracker.acquire("m::a", OWNER)
    assert first is not None
    monkeypatch.setattr("time.time", lambda: 2000.0)
    if kind == "foreign":
        monkeypatch.setattr(lease_identity, "host_id", lambda: "other")
    elif kind == "missing":
        monkeypatch.setattr(lease_identity, "process_started_at_utc", lambda _: None)
    elif kind == "permission":
        monkeypatch.setattr(os, "kill", Mock(side_effect=PermissionError(errno.EPERM, "denied")))
    elif kind == "birth":
        monkeypatch.setattr(lease_identity, "process_started_at_utc", lambda _: 21)
    else:
        monkeypatch.setattr(os, "kill", Mock(side_effect=ProcessLookupError(errno.ESRCH, "dead")))
    assert bool(tracker.acquire("m::a", OWNER)) == (kind in ("birth", "dead"))

@pytest.mark.parametrize("failure", ["replace", "fsync", "flock"])
def test_io_failure_denies_ownership(tracker: RoutePenaltyState, monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    target = fcntl if failure == "flock" else os
    monkeypatch.setattr(target, failure, Mock(side_effect=OSError("unavailable")))
    assert tracker.acquire("m::a", OWNER) is None
    assert not tracker.owns("m::a", 1, "x")
    assert not tracker.storage_path.exists()

@pytest.mark.parametrize("raw", ["{", "[]", '{"m::a":{"phase":"BOGUS"}}', '{"m::a":{"lease_epoch":true}}'])
def test_corrupt_store_never_resets(tracker: RoutePenaltyState, raw: str) -> None:
    tracker.storage_path.write_text(raw)
    assert tracker.acquire("m::a", OWNER) is None
    assert tracker.is_penalized("m", "a")[0]
    assert tracker.storage_path.read_text() == raw

def test_competing_stores_and_stable_sidecar(tracker: RoutePenaltyState) -> None:
    stores = [RoutePenaltyState(tracker.storage_path) for _ in range(8)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        leases = list(pool.map(lambda store: store.acquire("m::a", OWNER), stores))
    assert sum(item is not None for item in leases) == 1
    inode = tracker.lock_path.stat().st_ino
    tracker.record_start_failure("other", backend="a")
    assert tracker.lock_path.stat().st_ino == inode
    assert RoutePenaltyState(tracker.storage_path).is_penalized("m", "b") == (False, 0)

def test_unknown_edge_fields_survive(tracker: RoutePenaltyState) -> None:
    tracker.storage_path.write_text('{"m::a":{"projection":{"next":[1]}}}')
    tracker.record_start_failure("m", backend="a")
    tracker.record_start_success("m", backend="a")
    row = json.loads(tracker.storage_path.read_text())["m::a"]
    assert row["projection"] == {"next": [1]}
    assert row["phase"] == "CLOSED"

@pytest.mark.parametrize("model,backend", [("", "a"), ("m::a", "b"), ("m", ""), ("m", "a::b")])
def test_ambiguous_keys_rejected(model: str, backend: str) -> None:
    with pytest.raises(ValueError):
        edge_key(model, backend)

def test_finish_and_reclaimed_abort(tracker: RoutePenaltyState, monkeypatch: pytest.MonkeyPatch) -> None:
    old = tracker.acquire("m::a", OWNER)
    assert old is not None
    monkeypatch.setattr("time.time", lambda: 1065.0)
    monkeypatch.setattr(lease_identity, "is_alive_or_unknown", lambda *_: False)
    new = tracker.acquire("m::a", OWNER)
    assert new is not None
    with pytest.raises(LeaseFenced):
        tracker.abort("m::a", old.lease_epoch, old.lease_token)
    assert tracker.finish("m::a", new, 30) == replace(new, phase=Phase.OPEN, penalized_until=1095, lease_until=0, lease_token="")
    with pytest.raises(LeaseFenced):
        tracker.finish("m::a", new)

def _process_acquire(path: Path, ready: Any, start: Any, result: Any) -> None:
    lease_identity.host_id = lambda: None
    lease_identity.boot_id = lambda: None
    ready.put(True)
    if not start.wait(10):
        raise RuntimeError("Не получен сигнал старта")
    result.put(bool(RoutePenaltyState(path).acquire("m::a", OWNER)))

def test_flock_between_processes(tracker: RoutePenaltyState) -> None:
    context = multiprocessing.get_context("spawn")
    ready, result, start = context.Queue(), context.Queue(), context.Event()
    processes = [context.Process(target=_process_acquire, args=(tracker.storage_path, ready, start, result)) for _ in range(3)]
    try:
        for process in processes:
            process.start()
        for _ in processes:
            ready.get(timeout=15)
        start.set()
        assert sum(result.get(timeout=15) for _ in processes) == 1
    finally:
        _join_processes(processes)
        ready.close()
        result.close()

def _join_processes(processes: list[Any]) -> None:
    for process in processes:
        process.join(15)
        if process.is_alive():
            process.terminate()
            process.join(5)
        assert process.exitcode == 0

def _complexity(node: ast.AST) -> int:
    branches = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.ExceptHandler, ast.With, ast.AsyncWith, ast.IfExp, ast.Assert)
    return 1 + sum(isinstance(n, branches) for n in ast.walk(node)) + sum(len(n.values) - 1 for n in ast.walk(node) if isinstance(n, ast.BoolOp)) + sum(len(n.ifs) for n in ast.walk(node) if isinstance(n, ast.comprehension))

@pytest.mark.parametrize("relative,cap", [("core/route_penalty_state.py", 220), ("tests/test_route_penalty_state.py", 250)])
def test_architecture_caps(relative: str, cap: int) -> None:
    source = (Path(__file__).resolve().parents[1] / relative).read_text()
    assert len(source.splitlines()) <= cap
    functions = [node for node in ast.walk(ast.parse(source)) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    for node in functions:
        args = node.args
        count = len(args.posonlyargs + args.args + args.kwonlyargs) + bool(args.vararg) + bool(args.kwarg)
        assert (node.end_lineno or node.lineno) - node.lineno + 1 <= 40, node.name
        assert count <= 5, node.name
        assert _complexity(node) <= 10, node.name
