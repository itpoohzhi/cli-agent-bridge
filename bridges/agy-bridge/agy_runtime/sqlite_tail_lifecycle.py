"""Failure-isolated lifecycle helpers for transcript SQLite tails."""
# pyright: reportPrivateUsage=false

from __future__ import annotations

import logging
import sqlite3
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

_LOGGER = logging.getLogger(__name__)


class _PlanLike(Protocol):
    @property
    def mode(self) -> str: ...


class _FinishTail(Protocol):
    _finished: bool
    _conn_lock: threading.Lock
    _active_conn: sqlite3.Connection | None
    probe_gen: int | None
    selects_ok: int
    failed: bool
    _owned_cid: str
    turn_id: str

    @property
    def plan(self) -> _PlanLike: ...


class _PoolLike(Protocol):
    def release_thread(self) -> None: ...


class _QueryPoolLike(Protocol):
    def query_rows(
        self, db_path: str | Path, sql: str
    ) -> list[tuple[object, ...]]: ...


class _PollTail(Protocol):
    last_poll: str
    sqlite_active: bool

    def _cid8(self) -> str: ...
    def _sqlite_off(self, reason: str) -> None: ...


def _log_cleanup_error(stage: str, exc: BaseException) -> None:
    _LOGGER.warning(
        "sqlite-tail-cleanup-failed stage=%s err=%s",
        stage,
        type(exc).__name__,
        exc_info=True,
    )


def _close_connection(
    tail: _FinishTail, close_conn: Callable[[sqlite3.Connection], None]
) -> None:
    try:
        with tail._conn_lock:
            conn = tail._active_conn
            tail._active_conn = None
        if conn is not None:
            close_conn(conn)
    except Exception as exc:
        _log_cleanup_error("connection", exc)


def _release_pool(pool_provider: Callable[[], _PoolLike | None]) -> None:
    try:
        pool = pool_provider()
        if pool is not None:
            pool.release_thread()
    except Exception as exc:
        _log_cleanup_error("pool", exc)


def _report_breaker(
    tail: _FinishTail,
    breaker_report: Callable[[int | None, int, bool], None],
) -> None:
    try:
        if tail.plan.mode in ("LIVE", "SHADOW"):
            breaker_report(tail.probe_gen, tail.selects_ok, tail.failed)
    except Exception as exc:
        _log_cleanup_error("breaker", exc)


def _release_cid(
    tail: _FinishTail, cid_release: Callable[[str, str], None]
) -> None:
    try:
        if tail._owned_cid:
            cid_release(tail._owned_cid, tail.turn_id)
    except Exception as exc:
        _log_cleanup_error("cid", exc)


def finish_transcript_tail(
    tail: _FinishTail,
    close_conn: Callable[[sqlite3.Connection], None],
    pool_provider: Callable[[], _PoolLike | None],
    breaker_report: Callable[[int | None, int, bool], None],
    cid_release: Callable[[str, str], None],
) -> None:
    """Finish a tail once while isolating each cleanup stage."""
    if tail._finished:
        return
    tail._finished = True
    _close_connection(tail, close_conn)
    _release_pool(pool_provider)
    _report_breaker(tail, breaker_report)
    _release_cid(tail, cid_release)


def is_pool_backoff_error(exc: BaseException) -> bool:
    return isinstance(exc, RuntimeError) and "sqlite_ro_pool_backoff" in str(exc)


def is_cold_wal_error(exc: BaseException, db_path: Path | None) -> bool:
    return isinstance(exc, sqlite3.OperationalError) and "unable to open database file" in str(exc).lower() and db_path is not None and (not db_path.exists() or not Path(f"{db_path}-wal").exists())


def safe_sqlite_max_idx(
    pool: _QueryPoolLike, db_path: str | Path, sql: str
) -> int | None:
    try:
        rows = pool.query_rows(db_path, sql)
    except (sqlite3.Error, RuntimeError):
        return None
    value = rows[0][0] if rows else None
    return value if isinstance(value, int) else None


def handle_poll_exception(
    tail: _PollTail, exc: BaseException, log: Callable[[str], None]
) -> None:
    if is_pool_backoff_error(exc):
        tail.last_poll = "skip"
        logged = cast(bool, getattr(tail, "_sqlite_pool_backoff_logged", False))
        if not logged:
            setattr(tail, "_sqlite_pool_backoff_logged", True)
            log(f"sqlite-pool-backoff cid={tail._cid8()}")
        return
    tail.last_poll = "error"
    log(f"sqlite-error cid={tail._cid8()} err={type(exc).__name__}")
    tail._sqlite_off("internal")
