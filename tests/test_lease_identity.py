"""L1: аппаратная идентичность, защита UNKNOWN и долговечная очистка."""
from __future__ import annotations
import ast
import errno
import hashlib
import itertools
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from typing import Any
from unittest.mock import Mock
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import lease_identity as api
OWNER = dict(owner_host="foreign", boot_id=10, owner_pid=123,
             owner_started_at_utc=20, lease_epoch=7, lease_token="token")
@pytest.fixture
def setup(tmp_path: Path) -> tuple[Any, Any]:
    context = api.LeaseMaintenanceContext(tmp_path / "state.json", tmp_path / "audit.jsonl", "local")
    context.lease_path.write_text(json.dumps(dict(OWNER, edge_key="edge")))
    request = api.ClearForeignLeaseRequest("edge", "operator", True, **{f"expected_{key}": value for key, value in OWNER.items()})
    return request, context
@pytest.mark.parametrize("output,expected", [
    ('"IOPlatformUUID" = " abcd-1234 "\n', hashlib.sha256(b"ABCD-1234").hexdigest()),
    ("", None), ('"IOPlatformUUID" = ""', None),
    ('"IOPlatformUUID" = "one"\n"IOPlatformUUID" = "two"', None)])
def test_hardware(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output: str, expected: Any) -> None:
    fallback = tmp_path / ".config/cli-agent-bridge/host_id"
    fallback.parent.mkdir(parents=True)
    fallback.write_text("forbidden")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CAB_HOST_ID_OVERRIDE", "not-production")
    run = Mock(return_value=subprocess.CompletedProcess([], 0, output, ""))
    monkeypatch.setattr(subprocess, "run", run)
    assert api.host_id() == expected
    assert run.call_args.args[0] == ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"]
    assert api.host_id(test_override=True) == "not-production"
    assert fallback.read_text() == "forbidden"
@pytest.mark.parametrize("function,output,expected", [
    ("boot_id", "{ sec = 123, usec = 456 } Mon Nov 16 00:00:00 2026", 123),
    ("boot_id", "123", None), ("boot_id", "{ sec = 1, usec = 0 }{ sec = 2, usec = 0 }", None),
    ("process_birth_utc", "Thu Jan  1 00:00:20 1970\n", 20),
    ("process_birth_utc", "bad", None), ("process_birth_utc", "", None)])
def test_times(monkeypatch: pytest.MonkeyPatch, function: str, output: str, expected: Any) -> None:
    run = Mock(return_value=subprocess.CompletedProcess([], 0, output, ""))
    monkeypatch.setattr(subprocess, "run", run)
    args = (123,) if function == "process_birth_utc" else ()
    assert getattr(api, function)(*args) == expected
    if args:
        assert run.call_args.args[0] == ["ps", "-p", "123", "-o", "lstart="]
        assert {key: run.call_args.kwargs["env"][key] for key in ("TZ", "LC_ALL")} == {
            "TZ": "UTC", "LC_ALL": "C"}
    else:
        assert run.call_args.args[0] == ["sysctl", "-n", "kern.boottime"]
    run.side_effect = OSError("unavailable")
    assert getattr(api, function)(*args) is None
@pytest.mark.parametrize("field,value", [(key, None) for key in tuple(OWNER)[:4]] +
                         [("owner_pid", 0), ("owner_pid", -1), ("owner_pid", True)])
def test_incomplete(monkeypatch: pytest.MonkeyPatch, field: str, value: Any) -> None:
    kill, birth = Mock(), Mock(return_value=20)
    monkeypatch.setattr(os, "kill", kill)
    monkeypatch.setattr(api, "process_started_at_utc", birth)
    assert api.is_alive_or_unknown(dict(OWNER, **{field: value}), "local", 10)
    kill.assert_not_called()
    birth.assert_not_called()
@pytest.mark.parametrize("case", list(itertools.product(
    ("local", "foreign", None), (10, 11, None),
    (None, errno.ESRCH, errno.EPERM, errno.EIO), (20, 21, None))))
def test_truth_table(monkeypatch: pytest.MonkeyPatch, case: tuple[Any, ...]) -> None:
    host, boot, error, birth = case
    kill = Mock(side_effect=OSError(error, "probe") if error else None)
    monkeypatch.setattr(os, "kill", kill)
    monkeypatch.setattr(api, "process_started_at_utc", Mock(return_value=birth))
    expected = True
    if host == "local" and boot is not None:
        expected = boot == 10
        if expected:
            expected = error not in (None, errno.ESRCH, errno.EPERM) or (
                error != errno.ESRCH and birth in (None, 20))
    assert api.is_alive_or_unknown(dict(OWNER, owner_host="local"), host, boot) is expected
    if host != "local" or boot != 10:
        kill.assert_not_called()
@pytest.mark.parametrize("field", [*OWNER, *("missing_" + k for k in OWNER), "edge_key", "operator_id", "confirm_exclusive_storage"])
def test_mismatch(setup: tuple[Any, Any], field: str) -> None:
    request, context = setup
    if field.startswith("missing_"):
        lease = json.loads(context.lease_path.read_text())
        lease.pop(field[8:])
        context.lease_path.write_text(json.dumps(lease))
    else:
        name = f"expected_{field}" if field in OWNER else field
        value = getattr(request, name)
        wrong = value + 1 if type(value) is int else f"{value}-wrong"
        if field == "confirm_exclusive_storage":
            wrong = False
        if field == "operator_id":
            wrong = ""
        request = replace(request, **{name: wrong})
    before = context.lease_path.read_bytes()
    assert api.operator_clear_foreign_lease(request, context) != 0
    assert context.lease_path.read_bytes() == before
def rows(context: Any) -> list[Any]:
    return [json.loads(line) for line in context.audit_path.read_text().splitlines()]
def test_durability(setup: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    request, context = setup
    events, sync = [], os.fsync
    def observe(fd: int) -> None:
        events.append((stat.S_ISDIR(os.fstat(fd).st_mode), context.lease_path.exists()))
        sync(fd)
    monkeypatch.setattr(os, "fsync", observe)
    assert api.operator_clear_foreign_lease(request, context) == 0
    assert [row["phase"] for row in rows(context)] == ["intent", "committed"]
    assert rows(context)[0]["lease_fingerprint"] == OWNER
    assert events == [(False, True), (True, True), (True, False), (False, False), (True, False)]
    assert context.lock_path.exists()
    with pytest.raises(FrozenInstanceError):
        request.operator_id = "changed"
@pytest.mark.parametrize("point", range(1, 6))
def test_sync_failures(setup: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch, point: int) -> None:
    request, context = setup
    before = context.lease_path.read_bytes()
    monkeypatch.setattr(os, "fsync", Mock(side_effect=itertools.chain(
        [None] * (point - 1), itertools.repeat(OSError("private details")))))
    assert api.operator_clear_foreign_lease(request, context) != 0
    if point <= 2:
        assert context.lease_path.read_bytes() == before
    else:
        assert not context.lease_path.exists()
def test_failure_and_recovery(setup: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    request, context = setup
    before = context.lease_path.read_bytes()
    monkeypatch.setattr(os, "unlink", Mock(side_effect=OSError("SECRET")))
    assert api.operator_clear_foreign_lease(request, context) != 0
    assert [row["phase"] for row in rows(context)] == ["intent", "failed"]
    assert "SECRET" not in context.audit_path.read_text()
    assert api.operator_clear_foreign_lease(request, context) != 0
    assert context.unreconciled_intent == rows(context)[0]["audit_id"]
    assert context.lease_path.read_bytes() == before
@pytest.mark.parametrize("tail", [b'{"phase":', b'{"broken":\n'])
def test_partial_recovery(setup: tuple[Any, Any], tail: bytes) -> None:
    request, context = setup
    prefix = b'{"phase":"intent","audit_id":"interrupted"}\n'
    context.audit_path.write_bytes(prefix + tail)
    before = context.lease_path.read_bytes()
    assert api.operator_clear_foreign_lease(request, context) != 0
    assert context.lease_path.read_bytes() == before
    assert context.audit_path.read_bytes() == (prefix if not tail.endswith(b"\n") else prefix + tail)
    if not tail.endswith(b"\n"):
        assert context.unreconciled_intent == "interrupted"
def test_store_preserves_others(setup: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    request, context = setup
    events, sync = [], os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: (events.append(stat.S_ISDIR(os.fstat(fd).st_mode)), sync(fd)))
    context.lease_path.write_text(json.dumps({"edge": OWNER, "other": OWNER, "_meta": {"v": 2}}))
    assert api.operator_clear_foreign_lease(request, context) == 0
    assert json.loads(context.lease_path.read_text()) == {"other": OWNER, "_meta": {"v": 2}}
    assert events == [False, True, False, True, False, True]
@pytest.mark.parametrize("field", tuple(OWNER)[1:5])
def test_exact_types(setup: tuple[Any, Any], field: str) -> None:
    request, context = setup
    before = context.lease_path.read_bytes()
    assert api.operator_clear_foreign_lease(replace(request, **{f"expected_{field}": True}), context)
    assert context.lease_path.read_bytes() == before
@pytest.mark.parametrize("stage", ["intent", "removed", "committed", "cli"])
def test_crash_and_cli(setup: tuple[Any, Any], stage: str) -> None:
    request, context = setup
    script = (
        "import json,os,sys; from pathlib import Path; from core import lease_identity as a\n"
        "r=a.ClearForeignLeaseRequest(**json.loads(sys.argv[1])); c=a.LeaseMaintenanceContext(Path(sys.argv[2]),Path(sys.argv[3]),'local')\n"
        "original=a._append\n"
        "def append(path,row):\n"
        " if sys.argv[4]=='removed' and row['phase']=='committed': os._exit(1)\n"
        " original(path,row)\n"
        " if sys.argv[4]==row['phase']: os._exit(1)\n"
        "a._append=append\n"
        "raise SystemExit(a.operator_clear_foreign_lease(r,c))\n")
    command = [sys.executable, "-c", script, json.dumps(vars(request)), str(context.lease_path), str(context.audit_path), stage]
    if stage == "cli":
        options = ["--" + k.replace("_", "-") for k in vars(request)]
        options = [item for k, flag in zip(vars(request), options) for item in ([flag] if k == "confirm_exclusive_storage" else [flag, str(getattr(request, k))])]
        command = [sys.executable, "-m", "core.lease_identity", "clear-foreign-lease", "--lease-path", str(context.lease_path), "--audit-path", str(context.audit_path), *options]
    result = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], capture_output=True, timeout=10)
    assert result.returncode == (0 if stage == "cli" else 1), result.stderr
    assert context.lease_path.exists() is (stage == "intent")
    assert_recovery(request, context, stage)
def assert_recovery(request: Any, context: Any, stage: str) -> None:
    assert api.operator_clear_foreign_lease(request, context) != 0
    assert bool(context.unreconciled_intent) is (stage in ("intent", "removed"))
def test_bounds() -> None:
    for path, cap in ((Path(api.__file__), 180), (Path(__file__), 200)):
        source = path.read_text()
        assert len(source.splitlines()) <= cap
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert (node.end_lineno or node.lineno) - node.lineno + 1 <= 40
                assert len(node.args.args) + len(node.args.kwonlyargs) <= 5
