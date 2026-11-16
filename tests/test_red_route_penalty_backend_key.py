"""C0-1/C2-3: backend isolation, host-first, terminal fencing и durable audit."""
from __future__ import annotations
import errno
import fcntl
import hashlib
import importlib
import itertools
import json
import os
from dataclasses import replace
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
    for name in ("CAB_HOST_ID_OVERRIDE", "CAB_HOST_ID_PATH", "BRIDGE_MAX_START_FAILS", "BRIDGE_COOLDOWN_SECONDS"):
        monkeypatch.delenv(name, raising=False)
    for obj, name in ((socket, "socket"), (socket, "create_connection"), (time, "sleep"), (subprocess, "Popen")):
        monkeypatch.setattr(obj, name, _forbidden)
    monkeypatch.setattr(time, "time", lambda: 1000.0)

@pytest.fixture
def tracker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    identity = _module("lease_identity")
    monkeypatch.setattr(identity, "host_id", lambda: "local")
    monkeypatch.setattr(identity, "boot_id", lambda: 10)
    monkeypatch.setattr(identity, "process_started_at_utc", lambda _: 20)
    monkeypatch.setattr(os, "kill", Mock())
    return _module("model_penalty").ModelPenaltyTracker(tmp_path / "state.json", max_start_fails=1)

def test_backend_failure_does_not_penalize_other_backend(tracker: Any) -> None:
    tracker.record_start_failure("model", "startup_failed", backend="codex")
    assert tracker.is_penalized("model", backend="codex")[0] is True
    assert tracker.is_penalized("model", backend="droid") == (False, 0.0)
    tracker.record_start_success("model", backend="droid")
    assert tracker.is_penalized("model", backend="codex")[0] is True

@pytest.mark.parametrize("module,kind", [("route_penalty_state", "RoutePenaltyState"), ("model_penalty", "ModelPenaltyTracker")])
def test_legacy_is_ignored_and_unknown_projection_survives(tmp_path: Path, module: str, kind: str) -> None:
    path = tmp_path / "penalties.json"
    legacy = dict(fails=3, penalized_until=2000, last_fail_at=999, last_error="old", penalty_trips=1, projection={"future": [1]})
    metadata = {"quarantine_enabled": True, "future": {"opaque": "keep"}}
    path.write_text(json.dumps({"model": legacy, "_meta": metadata, EDGE: {"projection": [2]}}))
    tracker = getattr(_module(module), kind)(storage_path=path)
    assert tracker.is_penalized("model", backend="codex") == (False, 0.0)
    assert tracker.is_penalized("model", backend=None)[0] is True
    assert tracker.ignored_legacy == 1
    tracker.record_start_failure("model", "startup_failed", backend="codex")
    reloaded = json.loads(path.read_text())
    assert reloaded["model"] == legacy and reloaded["_meta"]["future"] == metadata["future"]
    assert reloaded[EDGE]["projection"] == [2]
    assert getattr(_module(module), kind)(path).is_penalized("model", backend="droid") == (False, 0.0)

@pytest.mark.parametrize("raw", ['  abcd-1234  ', "", None, "ambiguous"])
def test_host_id_uses_only_normalized_hardware_uuid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raw: str | None) -> None:
    fallback = tmp_path / ".config/cli-agent-bridge/host_id"
    fallback.parent.mkdir(parents=True)
    fallback.write_text("persisted-home-identity")
    output = f'    "IOPlatformUUID" = "{raw}"\n' if raw else ""
    if raw == "ambiguous":
        output = '"IOPlatformUUID" = "one"\n"IOPlatformUUID" = "two"\n'
    run = Mock(return_value=subprocess.CompletedProcess([], 0, output, ""))
    monkeypatch.setattr(subprocess, "run", run)
    expected = hashlib.sha256(b"ABCD-1234").hexdigest() if raw == "  abcd-1234  " else None
    assert _module("lease_identity").host_id() == expected
    assert run.call_args.args[0] == ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"]
    assert fallback.read_text() == "persisted-home-identity"

@pytest.mark.parametrize("missing", ["owner_host", "boot_id", "owner_pid", "owner_started_at_utc"])
def test_incomplete_identity_protects_before_kill(monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
    identity, kill, birth = _module("lease_identity"), Mock(), Mock(return_value=20)
    monkeypatch.setattr(os, "kill", kill)
    monkeypatch.setattr(identity, "process_started_at_utc", birth)
    assert identity.is_alive_or_unknown({**OWNER, "owner_host": "local", missing: None}, "local", 10) is True
    kill.assert_not_called()
    birth.assert_not_called()

@pytest.mark.parametrize("case", [
    ("foreign", 10, None, 20, True), (None, 10, None, 20, True),
    ("local", None, None, 20, True), ("local", 11, None, 20, False),
    ("local", 10, errno.ESRCH, 20, False), ("local", 10, None, 20, True),
    ("local", 10, errno.EPERM, 20, True), ("local", 10, None, 21, False),
    ("local", 10, errno.EPERM, 21, False), ("local", 10, None, None, True),
    ("local", 10, errno.EPERM, None, True), ("local", 10, errno.EIO, 21, True),
])
def test_liveness_truth_table(monkeypatch: pytest.MonkeyPatch, case: tuple[Any, ...]) -> None:
    identity = _module("lease_identity")
    host, boot, error, birth, expected = case
    kill = Mock(side_effect=OSError(error, "probe") if error else None)
    monkeypatch.setattr(os, "kill", kill)
    monkeypatch.setattr(identity, "process_started_at_utc", Mock(return_value=birth))
    assert identity.is_alive_or_unknown({**OWNER, "owner_host": "local"}, host, boot) is expected
    if host != "local" or boot != 10:
        kill.assert_not_called()

@pytest.mark.parametrize("failure", ["replace", "fsync", "flock"])
def test_storage_error_denies_memory_only_ownership(tracker: Any, monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    monkeypatch.setattr(fcntl if failure == "flock" else os, failure, Mock(side_effect=OSError("unavailable")))
    tracker = _module("model_penalty").ModelPenaltyTracker(tracker.storage_path)
    assert tracker.acquire(EDGE) is None
    assert not tracker.owns(EDGE, OWNER["lease_epoch"], OWNER["lease_token"])

@pytest.mark.parametrize("kind", ["alive", "foreign", "unknown", "dead", "reuse", "reboot"])
def test_host_first_reclaim(tracker: Any, monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    lease = tracker.acquire(EDGE)
    assert lease is not None
    monkeypatch.setattr(time, "time", lambda: 2000.0)
    api = _module("lease_identity")
    changes = {"foreign": ("host_id", lambda: "foreign"), "unknown": ("process_started_at_utc", lambda _: None),
               "reuse": ("process_started_at_utc", lambda _: 21), "reboot": ("boot_id", lambda: 11)}
    if kind in changes:
        name, value = changes[kind]
        monkeypatch.setattr(api, name, value)
    if kind == "dead":
        monkeypatch.setattr(os, "kill", Mock(side_effect=ProcessLookupError(errno.ESRCH, "dead")))
    replacement = tracker.acquire(EDGE)
    assert (replacement is not None) is (kind in ("dead", "reuse", "reboot"))
    if replacement is not None:
        assert replacement.lease_epoch == lease.lease_epoch + 1 and replacement.lease_token != lease.lease_token

@pytest.mark.parametrize("action", ["record_success", "record_failure", "commit"])
@pytest.mark.parametrize("invalid", ["expired", "epoch", "token", "revoked"])
def test_terminal_fencing(tracker: Any, monkeypatch: pytest.MonkeyPatch, action: str, invalid: str) -> None:
    lease = tracker.acquire(EDGE)
    assert lease is not None
    document = json.loads(tracker.storage_path.read_text())
    if invalid == "expired":
        monkeypatch.setattr(time, "time", lambda: lease.lease_until)
    elif invalid == "revoked":
        del document[EDGE]
    else:
        document[EDGE]["lease_" + invalid] = 99 if invalid == "epoch" else "revoked"
    tracker.storage_path.write_text(json.dumps(document))
    before, effect = tracker.storage_path.read_bytes(), Mock()
    args = (EDGE, lease, effect) if action == "commit" else (EDGE, lease)
    with pytest.raises(_module("model_penalty").LeaseFenced):
        getattr(tracker, action)(*args)
    assert tracker.storage_path.read_bytes() == before
    effect.assert_not_called()

@pytest.mark.parametrize("action", ["record_success", "record_failure"])
@pytest.mark.parametrize("cooldown", [0, 10])
def test_owned_terminal_and_commit(tracker: Any, monkeypatch: pytest.MonkeyPatch, action: str, cooldown: int) -> None:
    lease = tracker.acquire(EDGE)
    assert lease is not None
    tracker.cooldown_seconds, tracker._has_custom_cooldown = cooldown, True
    monkeypatch.setattr(time, "time", lambda: next(clock))
    clock = itertools.count(1001, 0.001)
    assert not tracker.owns(EDGE, True, lease.lease_token)
    with pytest.raises(_module("model_penalty").LeaseFenced):
        tracker.record_start_success("model", backend="codex")
    with pytest.raises(_module("model_penalty").LeaseFenced):
        tracker.record_start_failure("model", backend="codex")
    assert tracker.commit(EDGE, lease, lambda: "committed") == "committed"
    result = getattr(tracker, action)(EDGE, lease)
    assert result.phase == ("CLOSED" if action == "record_success" else "OPEN")
    with pytest.raises(_module("model_penalty").LeaseFenced):
        tracker.commit(EDGE, lease, lambda: pytest.fail("stale commit"))

@pytest.fixture(params=["identity", "tracker"])
def maintenance_api(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_MAINTENANCE_API", str(request.param))

def _maintenance(tmp_path: Path) -> tuple[Any, Any, Any]:
    api = _module("lease_identity")
    lease, audit = tmp_path / "lease.json", tmp_path / "audit.jsonl"
    lease.write_text(json.dumps({**OWNER, "edge_key": EDGE}))
    context = api.LeaseMaintenanceContext(lease_path=lease, audit_path=audit, host_id="local")
    fields = {f"expected_{key}": value for key, value in OWNER.items()}
    request = api.ClearForeignLeaseRequest(edge_key=EDGE, operator_id="operator", confirm_exclusive_storage=True, **fields)
    return (_module("model_penalty").ModelPenaltyTracker(lease) if os.environ["TEST_MAINTENANCE_API"] == "tracker" else api), context, request

@pytest.mark.usefixtures("maintenance_api")
@pytest.mark.parametrize("field", [*OWNER, "operator_id", "confirm_exclusive_storage", "local_host", "edge_key"])
def test_foreign_clear_rejects_each_mismatch_without_changing_bytes(tmp_path: Path, field: str) -> None:
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
    real_sync, real_flock, held = os.fsync, fcntl.flock, [False]
    def flock(fd: int, operation: int) -> None:
        real_flock(fd, operation)
        held[0] = operation != fcntl.LOCK_UN
    def sync(fd: int) -> None:
        assert held[0], "fsync должен выполняться под sidecar lock"
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
    return [kind for kind, present, rows in events if rows and present == exists and rows[-1]["phase"] == phase]

@pytest.mark.usefixtures("maintenance_api")
def test_clear_durable_intent_precedes_removal_and_commit_follows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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

@pytest.mark.usefixtures("maintenance_api")
@pytest.mark.parametrize("fail_at", [1, 2, 3, 4, 5])
def test_audit_fsync_failure_never_reports_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fail_at: int) -> None:
    api, context, request = _maintenance(tmp_path)
    before = context.lease_path.read_bytes()
    monkeypatch.setattr(os, "fsync", Mock(side_effect=itertools.chain([None] * (fail_at - 1), itertools.repeat(OSError("audit unavailable")))))
    assert api.operator_clear_foreign_lease(request, context) != 0
    if fail_at <= 2:
        assert context.lease_path.read_bytes() == before
    else:
        assert not context.lease_path.exists() and _audit_rows(context.audit_path)[0]["phase"] == "intent"

@pytest.mark.usefixtures("maintenance_api")
def test_delete_error_records_durable_failed_phase(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    api, context, request = _maintenance(tmp_path)
    before, events = context.lease_path.read_bytes(), _observe_sync(context, monkeypatch)
    monkeypatch.setattr(os, "unlink", Mock(side_effect=OSError("delete denied")))
    assert api.operator_clear_foreign_lease(request, context) != 0
    assert context.lease_path.read_bytes() == before
    assert [row["phase"] for row in _audit_rows(context.audit_path)] == ["intent", "failed"]
    assert _phase_syncs(events, "failed", True) == ["file", "dir"]

@pytest.mark.usefixtures("maintenance_api")
@pytest.mark.parametrize("suffix", ['{"phase":', '{"broken":\n'])
def test_audit_recovery_under_lock_and_unreconciled_intent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str) -> None:
    api, context, request = _maintenance(tmp_path)
    prefix = json.dumps(dict(OWNER, phase="intent", audit_id="interrupted", ts_utc=999, operator_id="operator", edge_key=EDGE)) + "\n"
    context.audit_path.write_text(prefix + suffix)
    before, events = context.lease_path.read_bytes(), _observe_sync(context, monkeypatch)
    assert api.operator_clear_foreign_lease(request, context) != 0
    assert context.lease_path.read_bytes() == before
    if not suffix.endswith("\n"):
        assert context.audit_path.read_text() == prefix and context.unreconciled_intent == "interrupted"
        assert _phase_syncs(events, "intent", True)[0] == "file"
    else:
        assert context.audit_path.read_text() == prefix + suffix

@pytest.mark.usefixtures("maintenance_api")
def test_shared_tracker_clear_preserves_other_edges_and_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, context, request = _maintenance(tmp_path)
    keep = {"other::droid": {"projection": ["keep"]}, "_meta": {"unknown": [1]}}
    context.lease_path.write_text(json.dumps({EDGE: OWNER, **keep}))
    tracker = _module("model_penalty").ModelPenaltyTracker(context.lease_path)
    events = _observe_sync(context, monkeypatch)
    assert tracker.operator_clear_foreign_lease(request, context) == 0
    assert json.loads(context.lease_path.read_text()) == keep
    assert _phase_syncs(events, "intent", True)[:2] == ["file", "dir"]
    assert _phase_syncs(events, "committed", True) == ["file", "dir"]
    assert not tracker.owns(EDGE, OWNER["lease_epoch"], OWNER["lease_token"])
