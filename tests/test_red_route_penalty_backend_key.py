"""C0-1: RED-контракт VER-004/006; будущие API импортируются только при вызове."""

from __future__ import annotations

import errno
import fcntl
import hashlib
import importlib
import inspect
import itertools
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import time
from typing import Any
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
EDGE = "model::codex"
OWNER = dict(owner_host="foreign", boot_id=10, owner_pid=123,
             owner_started_at_utc=20, lease_epoch=7, lease_token="token")


def _module(name: str) -> Any:
    return importlib.import_module(f"core.{name}")


def _forbidden(*args: Any, **kwargs: Any) -> Any:
    pytest.fail("L1 запрещает реальный socket, sleep или subprocess")


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("BRIDGE_MODEL_PENALTIES_PATH", str(tmp_path / "v1.json"))
    monkeypatch.setenv("BRIDGE_STATE_DIR", str(tmp_path))
    monkeypatch.delenv("CAB_HOST_ID_OVERRIDE", raising=False)
    monkeypatch.delenv("CAB_HOST_ID_PATH", raising=False)
    for obj, name in ((socket, "socket"), (socket, "create_connection"),
                      (time, "sleep"), (subprocess, "Popen")):
        monkeypatch.setattr(obj, name, _forbidden)
    monkeypatch.setattr(time, "time", lambda: 1000.0)


def test_backend_failure_does_not_penalize_other_backend(tmp_path: Path) -> None:
    tracker_type = _module("model_penalty").ModelPenaltyTracker
    assert "backend" in inspect.signature(tracker_type.is_penalized).parameters, (
        "VER-006: v1 model-only keys cannot isolate backend edges"
    )
    tracker = tracker_type(tmp_path / "penalties.json", max_start_fails=1)
    tracker.record_start_failure("model", "startup_failed", backend="codex")
    assert tracker.is_penalized("model", backend="codex")[0] is True
    assert tracker.is_penalized("model", backend="droid") == (False, 0.0)
    tracker.record_start_success("model", backend="droid")
    assert tracker.is_penalized("model", backend="codex")[0] is True


def test_legacy_is_ignored_and_unknown_projection_survives(tmp_path: Path) -> None:
    path = tmp_path / "penalties.json"
    legacy = dict(fails=3, penalized_until=2000, last_fail_at=999,
                  last_error="old", penalty_trips=1, projection={"future": [1]})
    metadata = {"quarantine_enabled": True, "future": {"opaque": "keep"}}
    path.write_text(json.dumps({"model": legacy, "_meta": metadata}))
    tracker = _module("route_penalty_state").RoutePenaltyState(storage_path=path)
    assert tracker.is_penalized("model", backend="codex") == (False, 0.0)
    assert tracker.is_penalized("model", backend=None)[0] is True
    assert tracker.ignored_legacy == 1
    tracker.record_start_failure("other", "startup_failed", backend="droid")
    reloaded = json.loads(path.read_text())
    assert reloaded["model"] == legacy
    assert reloaded["_meta"]["future"] == metadata["future"]
    again = _module("route_penalty_state").RoutePenaltyState(storage_path=path)
    assert again.is_penalized("model", backend="droid") == (False, 0.0)
    assert again.ignored_legacy == 1


@pytest.mark.parametrize("raw", ['  abcd-1234  ', "", None, "ambiguous"])
def test_host_id_uses_only_normalized_hardware_uuid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raw: str | None,
) -> None:
    identity = _module("lease_identity")
    fallback = tmp_path / ".config/cli-agent-bridge/host_id"
    fallback.parent.mkdir(parents=True)
    fallback.write_text("persisted-home-identity")
    output = f'    "IOPlatformUUID" = "{raw}"\n' if raw else ""
    if raw == "ambiguous":
        output = '"IOPlatformUUID" = "one"\n"IOPlatformUUID" = "two"\n'
    run = Mock(return_value=subprocess.CompletedProcess([], 0, output, ""))
    monkeypatch.setattr(subprocess, "run", run)
    expected = hashlib.sha256(b"ABCD-1234").hexdigest() if raw == "  abcd-1234  " else None
    assert identity.host_id() == expected
    assert run.call_args.args[0] == ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"]
    assert fallback.read_text() == "persisted-home-identity"


@pytest.mark.parametrize("missing", ["owner_host", "boot_id", "owner_pid",
                                    "owner_started_at_utc"])
def test_incomplete_identity_protects_before_kill(
    monkeypatch: pytest.MonkeyPatch, missing: str,
) -> None:
    identity = _module("lease_identity")
    owner = {**OWNER, "owner_host": "local", missing: None}
    kill = Mock()  # kill_ok=True, cur_birth=int: обязательная регрессия r9.
    birth = Mock(return_value=20)
    monkeypatch.setattr(os, "kill", kill)
    monkeypatch.setattr(identity, "process_started_at_utc", birth)
    assert identity.is_alive_or_unknown(owner, "local", 10) is True
    kill.assert_not_called()
    birth.assert_not_called()


@pytest.mark.parametrize("case", [
    ("foreign", 10, None, 20, True), (None, 10, None, 20, True),
    ("local", None, None, 20, True), ("local", 11, None, 20, False),
    ("local", 10, errno.ESRCH, 20, False),
    ("local", 10, None, 20, True), ("local", 10, errno.EPERM, 20, True),
    ("local", 10, None, 21, False), ("local", 10, errno.EPERM, 21, False),
    ("local", 10, None, None, True), ("local", 10, errno.EPERM, None, True),
    ("local", 10, errno.EIO, 21, True),
])
def test_liveness_truth_table(monkeypatch: pytest.MonkeyPatch, case: tuple[Any, ...]) -> None:
    identity = _module("lease_identity")
    host, boot, error, birth, expected = case
    kill = Mock(side_effect=OSError(error, "probe") if error else None)
    monkeypatch.setattr(os, "kill", kill)
    monkeypatch.setattr(identity, "process_started_at_utc", Mock(return_value=birth))
    owner = {**OWNER, "owner_host": "local"}
    assert identity.is_alive_or_unknown(owner, host, boot) is expected
    if host != "local" or boot != 10:
        kill.assert_not_called()


def test_storage_error_denies_memory_only_ownership(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _module("route_penalty_state").RoutePenaltyState
    tracker = state(storage_path=tmp_path / "state.json")
    monkeypatch.setattr(os, "replace", Mock(side_effect=OSError("disk unavailable")))
    owner = {**OWNER, "owner_host": "local"}
    assert not tracker.acquire(EDGE, owner)
    assert not tracker.owns(EDGE, owner["lease_epoch"], owner["lease_token"])
    assert not state(storage_path=tmp_path / "state.json").owns(
        EDGE, owner["lease_epoch"], owner["lease_token"],
    )


def _maintenance(tmp_path: Path) -> tuple[Any, Any, Any]:
    api = _module("lease_identity")
    lease, audit = tmp_path / "lease.json", tmp_path / "audit.jsonl"
    lease.write_text(json.dumps({**OWNER, "edge_key": EDGE}))
    context = api.LeaseMaintenanceContext(lease_path=lease, audit_path=audit,
                                         host_id="local")
    fields = {f"expected_{key}": value for key, value in OWNER.items()}
    request = api.ClearForeignLeaseRequest(edge_key=EDGE, operator_id="operator",
                                          confirm_exclusive_storage=True, **fields)
    return api, context, request


@pytest.mark.parametrize("field", [*OWNER, "operator_id", "confirm_exclusive_storage",
                                    "local_host", "edge_key"])
def test_foreign_clear_rejects_each_mismatch_without_changing_bytes(
    tmp_path: Path, field: str,
) -> None:
    from dataclasses import replace

    api, context, request = _maintenance(tmp_path)
    if field == "local_host":
        context = replace(context, host_id="foreign")
    else:
        name = f"expected_{field}" if field in OWNER else field
        value = getattr(request, name)
        wrong = value + 1 if type(value) is int else f"{value}-wrong"
        if field in ("operator_id", "confirm_exclusive_storage"):
            wrong = "" if field == "operator_id" else False
        request = replace(request, **{name: wrong})
    before = context.lease_path.read_bytes()
    assert api.operator_clear_foreign_lease(request, context) != 0
    assert context.lease_path.read_bytes() == before


def _audit_rows(path: Path) -> list[Any]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def _observe_sync(context: Any, monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    events: list[Any] = []
    real_sync, real_flock = os.fsync, fcntl.flock
    held = [False]

    def flock(fd: int, operation: int) -> None:
        real_flock(fd, operation)
        held[0] = operation != fcntl.LOCK_UN

    def sync(fd: int) -> None:
        assert held[0], "audit/recovery fsync должен выполняться под sidecar lock"
        info = os.fstat(fd)
        kind = "dir" if stat.S_ISDIR(info.st_mode) else "other"
        if context.audit_path.exists() and info.st_ino == context.audit_path.stat().st_ino:
            kind = "file"
        if kind == "dir":
            assert info.st_ino == context.audit_path.parent.stat().st_ino
        rows = _audit_rows(context.audit_path) if context.audit_path.exists() else []
        events.append((kind, context.lease_path.exists(), rows))
        real_sync(fd)

    monkeypatch.setattr(fcntl, "flock", flock)
    monkeypatch.setattr(os, "fsync", sync)
    return events


def _phase_syncs(events: list[Any], phase: str, exists: bool) -> list[str]:
    return [kind for kind, present, rows in events
            if rows and present == exists and rows[-1]["phase"] == phase]


def test_clear_durable_intent_precedes_removal_and_commit_follows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    api, context, request = _maintenance(tmp_path)
    events = _observe_sync(context, monkeypatch)
    assert api.operator_clear_foreign_lease(request, context) == 0
    assert not context.lease_path.exists()
    rows = _audit_rows(context.audit_path)
    assert [row["phase"] for row in rows] == ["intent", "committed"]
    assert rows[0]["audit_id"] == rows[1]["audit_id"]
    assert rows[0]["operator_id"] == "operator" and rows[0]["edge_key"] == EDGE
    assert all(rows[0][key] == value for key, value in OWNER.items())
    assert _phase_syncs(events, "intent", True) == ["file", "dir"]
    assert _phase_syncs(events, "committed", False) == ["file", "dir"]


@pytest.mark.parametrize("fail_at", [1, 2])
def test_pre_removal_audit_fsync_failure_leaves_lease_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fail_at: int,
) -> None:
    api, context, request = _maintenance(tmp_path)
    before = context.lease_path.read_bytes()
    failures = itertools.repeat(OSError("audit unavailable"))
    sync = Mock(side_effect=itertools.chain([None] * (fail_at - 1), failures))
    monkeypatch.setattr(os, "fsync", sync)
    assert api.operator_clear_foreign_lease(request, context) != 0
    assert context.lease_path.read_bytes() == before


def test_delete_error_records_durable_failed_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    api, context, request = _maintenance(tmp_path)
    before = context.lease_path.read_bytes()
    events = _observe_sync(context, monkeypatch)
    monkeypatch.setattr(os, "unlink", Mock(side_effect=OSError("delete denied")))
    assert api.operator_clear_foreign_lease(request, context) != 0
    assert context.lease_path.read_bytes() == before
    assert [row["phase"] for row in _audit_rows(context.audit_path)] == ["intent", "failed"]
    assert _phase_syncs(events, "failed", True) == ["file", "dir"]


@pytest.mark.parametrize("suffix", ['{"phase":', '{"broken":\n'])
def test_audit_recovery_under_lock_and_unreconciled_intent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str,
) -> None:
    api, context, request = _maintenance(tmp_path)
    intent = dict(OWNER, phase="intent", audit_id="interrupted", ts_utc=999,
                  operator_id="operator", edge_key=EDGE)
    prefix = json.dumps(intent) + "\n"
    context.audit_path.write_text(prefix + suffix)
    before = context.lease_path.read_bytes()
    events = _observe_sync(context, monkeypatch)
    assert api.operator_clear_foreign_lease(request, context) != 0
    assert context.lease_path.read_bytes() == before
    if not suffix.endswith("\n"):
        assert context.audit_path.read_text() == prefix
        assert context.unreconciled_intent == "interrupted"
        assert _phase_syncs(events, "intent", True)[0] == "file"
    else:
        assert context.audit_path.read_text() == prefix + suffix


def test_terminal_audit_failure_never_reports_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    api, context, request = _maintenance(tmp_path)
    real_sync = os.fsync

    def sync(fd: int) -> None:
        if not context.lease_path.exists():
            raise OSError("power loss after removal")
        real_sync(fd)

    monkeypatch.setattr(os, "fsync", sync)
    assert api.operator_clear_foreign_lease(request, context) != 0
    assert not context.lease_path.exists()
    assert _audit_rows(context.audit_path)[0]["phase"] == "intent"
