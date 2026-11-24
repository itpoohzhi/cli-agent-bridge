from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Final

import pytest

ROOT: Final = Path(__file__).resolve().parents[1]
AGY_BRIDGE: Final = ROOT / "bridges" / "agy-bridge"
for _path in (str(ROOT), str(AGY_BRIDGE)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from agy_runtime.sqlite_cold_resume_policy import (  # noqa: E402
    ResumeAnchorCause,
    ResumeAnchorConfig,
)
from agy_runtime.sqlite_tail_lifecycle import (  # noqa: E402
    ResumeAnchorDeps,
    is_cold_wal_error,
    load_resume_anchor_config,
    probe_cold_fs,
    resolve_resume_db_max_idx,
    should_skip_cold_db_poll,
)
from agy_runtime.slot_and_session import SqliteRoPoolBackoffError  # noqa: E402

SQL = "SELECT COALESCE(MAX(idx), -1) FROM steps"


class _SequencePool:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.calls = 0

    def query_rows(self, *_args: object) -> list[tuple[object, ...]]:
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, BaseException):
            raise outcome
        return [(outcome,)]


class _Cursor:
    def __init__(self, outcome: object) -> None:
        self.outcome = outcome

    def fetchone(self) -> tuple[object]:
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return (self.outcome,)


class _Connection:
    def __init__(self, outcome: object) -> None:
        self.outcome = outcome

    def execute(self, _sql: str) -> _Cursor:
        return _Cursor(self.outcome)


class _FreshTail:
    resumed = False
    selects_ok = 0

    def __init__(self, path: Path) -> None:
        self._db_path = path

    def _cid8(self) -> str:
        return "cid12345"


def _read_only(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro"
    return sqlite3.connect(uri, uri=True, isolation_level=None)


def _create_steps_db(path: Path, indices: tuple[int, ...] = (2, 7)) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE steps (idx INTEGER NOT NULL)")
        conn.executemany(
            "INSERT INTO steps(idx) VALUES (?)", ((idx,) for idx in indices)
        )


def test_missing_db_can_appear_then_anchor_without_pool_poisoning(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "late.db"
    logs: list[str] = []
    tail = _FreshTail(db_path)
    assert should_skip_cold_db_poll(tail, logs.append) is True
    assert should_skip_cold_db_poll(tail, logs.append) is True
    assert logs == ["sqlite-cold-db-wait cid=cid12345 db=0"]

    _create_steps_db(db_path)
    deps = ResumeAnchorDeps(_read_only, sqlite3.Connection.close, lambda _delay: None)
    value, cause = resolve_resume_db_max_idx(None, db_path, SQL, deps)

    assert (value, cause) == (7, None)
    assert should_skip_cold_db_poll(tail, logs.append) is False


@pytest.mark.parametrize("message", ["database is locked", "database table is busy"])
def test_transient_locked_or_busy_retries_with_injected_sleep(
    tmp_path: Path, message: str
) -> None:
    db_path = tmp_path / "locked.db"
    db_path.write_bytes(b"sqlite")
    pool = _SequencePool([sqlite3.OperationalError(message)] * 2 + [9])
    sleeps: list[float] = []
    deps = ResumeAnchorDeps(
        lambda _path: _Connection(0),
        lambda _conn: None,
        sleeps.append,
        ResumeAnchorConfig(max_retries=3, retry_delay_s=0.05, max_retry_delay_s=0.08),
    )

    assert resolve_resume_db_max_idx(pool, db_path, SQL, deps) == (9, None)
    assert pool.calls == 3
    assert sleeps == [0.05, 0.08]


def test_pool_backoff_fallback_closes_connection_on_failure(tmp_path: Path) -> None:
    db_path = tmp_path / "fallback.db"
    db_path.write_bytes(b"sqlite")
    pool = _SequencePool([SqliteRoPoolBackoffError("sqlite_ro_pool_backoff")])
    connection = _Connection(sqlite3.OperationalError("database is locked"))
    closed: list[object] = []
    deps = ResumeAnchorDeps(
        lambda _path: connection,
        closed.append,
        lambda _delay: None,
        ResumeAnchorConfig(max_retries=0),
    )

    value, cause = resolve_resume_db_max_idx(pool, db_path, SQL, deps)

    assert value is None
    assert cause is ResumeAnchorCause.DB_LOCKED_EXHAUSTED
    assert closed == [connection]


def test_missing_resume_db_is_fast_fail_closed(tmp_path: Path) -> None:
    pool = _SequencePool([5])
    sleeps: list[float] = []
    deps = ResumeAnchorDeps(
        lambda _path: _Connection(5),
        lambda _conn: None,
        sleeps.append,
        ResumeAnchorConfig(max_retries=3),
    )

    value, cause = resolve_resume_db_max_idx(pool, tmp_path / "missing.db", SQL, deps)

    assert (value, cause) == (None, ResumeAnchorCause.DB_MISSING)
    assert pool.calls == 0
    assert sleeps == []


@pytest.mark.parametrize(
    "environ",
    [
        {"AGY_SQLITE_ANCHOR_MAX_RETRIES": "-1"},
        {"AGY_SQLITE_ANCHOR_RETRY_DELAY_S": "nan"},
        {"AGY_SQLITE_ANCHOR_MAX_RETRY_DELAY_S": "-0.1"},
        {"AGY_SQLITE_ANCHOR_BACKOFF_DIRECT_RO": "sometimes"},
    ],
)
def test_invalid_anchor_env_is_rejected(environ: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        load_resume_anchor_config(environ)


def test_invalid_anchor_env_fails_closed_in_resolver(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "invalid-config.db"
    db_path.write_bytes(b"sqlite")
    pool = _SequencePool([5])
    monkeypatch.setenv("AGY_SQLITE_ANCHOR_MAX_RETRIES", "invalid")
    deps = ResumeAnchorDeps(lambda _path: _Connection(5), lambda _conn: None)

    assert resolve_resume_db_max_idx(pool, db_path, SQL, deps) == (
        None,
        ResumeAnchorCause.DB_ERROR,
    )
    assert pool.calls == 0


def test_permission_error_is_never_cold_wait(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "denied.db"
    error = sqlite3.OperationalError("unable to open database file")
    monkeypatch.setattr(
        Path, "is_file", lambda _path: (_ for _ in ()).throw(PermissionError())
    )

    assert probe_cold_fs(db_path).fs_error is True
    assert is_cold_wal_error(error, db_path) is False


def test_env_defaults_and_overrides() -> None:
    config = load_resume_anchor_config({})
    assert config == ResumeAnchorConfig()
    overridden = load_resume_anchor_config(
        {
            "AGY_SQLITE_ANCHOR_MAX_RETRIES": "5",
            "AGY_SQLITE_ANCHOR_RETRY_DELAY_S": "0.01",
            "AGY_SQLITE_ANCHOR_MAX_RETRY_DELAY_S": "0.1",
            "AGY_SQLITE_ANCHOR_BACKOFF_DIRECT_RO": "off",
        }
    )
    assert overridden == ResumeAnchorConfig(5, 0.01, 0.1, False)
