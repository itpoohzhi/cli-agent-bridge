from __future__ import annotations

import importlib.util
import os
import sqlite3
import sys
import threading
from pathlib import Path
from typing import Final

import pytest

ROOT: Final = Path(__file__).resolve().parents[1]
AGY_BRIDGE: Final = ROOT / "bridges" / "agy-bridge"
for _path in (str(ROOT), str(AGY_BRIDGE)):
    if _path not in sys.path:
        sys.path.insert(0, _path)
os.environ.setdefault("AGY_BRIDGE_KEY", "test-key-sqlite-cold-resume")

from agy_runtime.slot_and_session import SqliteRoPoolBackoffError  # noqa: E402


CID = "82188e72-0658-4ad5-b843-a0b250df9349"


def _load_bridge():
    spec = importlib.util.spec_from_file_location(
        "agy_bridge_sqlite_cold_red", AGY_BRIDGE / "server.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


srv = _load_bridge()


class _AlwaysBucket:
    def take(self) -> bool:
        return True


class _FailingPool:
    def __init__(self, exc: BaseException) -> None:
        self.exc = exc
        self.calls = 0

    def run_ro(self, *_args: object, **_kwargs: object) -> None:
        self.calls += 1
        raise self.exc


class _BackoffPool:
    def __init__(self) -> None:
        self.calls = 0

    def query_rows(self, *_args: object) -> list[tuple[object, ...]]:
        self.calls += 1
        raise SqliteRoPoolBackoffError("sqlite_ro_pool_backoff")


class _Row:
    def __init__(self, value: int) -> None:
        self.value = value

    def fetchone(self) -> tuple[int]:
        return (self.value,)


class _DirectConn:
    def __init__(self, value: int) -> None:
        self.value = value

    def execute(self, _sql: str) -> _Row:
        return _Row(self.value)


def _tail(monkeypatch: pytest.MonkeyPatch, db_path: Path, *, resumed: bool = False):
    plan = srv._TurnPlan()
    plan.mode = "LIVE"
    monkeypatch.setattr(srv, "_db_path_for", lambda _cid: db_path)
    monkeypatch.setattr(srv, "_cid_acquire", lambda *_args: True)
    tail = srv._TranscriptTail(
        lambda *_args: True,
        threading.Event(),
        threading.Event(),
        resumed,
        plan=plan,
        turn_id="turn-cold",
    )
    tail.bucket = _AlwaysBucket()
    tail.bind(CID)
    tail._sqlite_permitted = lambda: True
    return tail


def test_fresh_missing_db_never_checks_out_pool_or_burns_budget(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pool = _FailingPool(sqlite3.OperationalError("unable to open database file"))
    logs: list[str] = []
    monkeypatch.setattr(srv, "_sqlite_ro_pool", lambda: pool)
    monkeypatch.setattr(srv, "_log", logs.append)
    tail = _tail(monkeypatch, tmp_path / "fresh.db")

    for _ in range(40):
        assert tail._poll_sqlite() is None

    assert pool.calls == 0
    assert tail._get_wal_wait_polls() == 0
    assert tail.failed is False
    assert sum("sqlite-cold-db-wait" in line for line in logs) == 1
    assert not any("sqlite-open-fail" in line for line in logs)


def test_tail_rejects_permission_error_as_fs_oserror(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    logs: list[str] = []
    monkeypatch.setattr(srv, "_log", logs.append)
    tail = _tail(monkeypatch, tmp_path / "denied.db")
    error = sqlite3.OperationalError("unable to open database file")
    monkeypatch.setattr(
        Path, "is_file", lambda _path: (_ for _ in ()).throw(PermissionError())
    )

    assert tail._handle_cold_wal_wait(error) is False
    tail._on_sqlite_error(error)

    assert tail.failed is True
    assert any(
        "sqlite-open-fail" in line and "cause=fs_oserror" in line for line in logs
    )


def test_resume_pool_backoff_uses_isolated_ro_anchor(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "resume.db"
    db_path.write_bytes(b"sqlite")
    pool = _BackoffPool()
    connection = _DirectConn(7)
    closed: list[object] = []
    monkeypatch.setattr(srv, "_transcript_anchor", lambda *_args: (4, 20))
    monkeypatch.setattr(srv, "_is_sqlite_reasoning_enabled", lambda: True)
    monkeypatch.setattr(srv, "_breaker_blocks_now", lambda: False)
    monkeypatch.setattr(srv, "_db_path_for", lambda _cid: db_path)
    monkeypatch.setattr(srv, "_sqlite_ro_pool", lambda: pool)
    monkeypatch.setattr(srv, "_sqlite_open_ro", lambda _path: connection)
    monkeypatch.setattr(srv, "_sqlite_close", closed.append)

    plan = srv._prespawn_plan(CID, True)

    assert plan.anchored is True
    assert plan.base_idx == 8
    assert pool.calls == 1
    assert closed == [connection]


def test_missing_resume_db_fails_closed_without_retry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pool = _BackoffPool()
    monkeypatch.setattr(srv, "_transcript_anchor", lambda *_args: (2, 10))
    monkeypatch.setattr(srv, "_is_sqlite_reasoning_enabled", lambda: True)
    monkeypatch.setattr(srv, "_breaker_blocks_now", lambda: False)
    monkeypatch.setattr(srv, "_db_path_for", lambda _cid: tmp_path / "missing.db")
    monkeypatch.setattr(srv, "_sqlite_ro_pool", lambda: pool)

    plan = srv._prespawn_plan(CID, True)

    assert plan.anchored is False
    assert plan.reason == "resume_unanchored"
    assert plan.cause == "db_missing"
    assert pool.calls == 0


def test_resume_unanchored_log_keeps_prefix_and_adds_cause(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    logs: list[str] = []
    plan = srv._TurnPlan()
    plan.mode = "OFF"
    plan.reason = "resume_unanchored"
    plan.cause = "transcript_error"
    monkeypatch.setattr(srv, "_log", logs.append)
    monkeypatch.setattr(srv, "_cid_acquire", lambda *_args: True)
    tail = srv._TranscriptTail(
        lambda *_args: True,
        threading.Event(),
        threading.Event(),
        True,
        plan=plan,
    )
    monkeypatch.setattr(srv, "_db_path_for", lambda _cid: tmp_path / "unused.db")
    tail.bind(CID)

    assert any(
        line.startswith("sqlite-off cid=82188e72 reason=resume_unanchored")
        and line.endswith("cause=transcript_error")
        for line in logs
    )
