"""Effect-shell для жизненного цикла SQLite tail и resume anchor."""
# pyright: reportPrivateUsage=false

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from . import sqlite_cold_resume_policy as policy

_LOGGER = logging.getLogger(__name__)


class _PoolLike(Protocol):
    def release_thread(self) -> None: ...
    def query_rows(self, db_path: str | Path, sql: str) -> list[tuple[object, ...]]: ...


# fmt: off
format_resume_off = policy.format_resume_off; ResumeAnchorCause = policy.ResumeAnchorCause  # noqa: E702 - compact exports preserve M-MOD cap
class _TailLike(Protocol):
    _finished: bool; _conn_lock: threading.Lock  # noqa: E702 - compact protocol preserves M-MOD cap
    _active_conn: sqlite3.Connection | None; probe_gen: int | None  # noqa: E702 - M-MOD cap
    selects_ok: int; failed: bool; _owned_cid: str; turn_id: str  # noqa: E702 - M-MOD cap
    plan: object; last_poll: str; resumed: bool; _db_path: Path | None  # noqa: E702 - M-MOD cap
    _interrupted: bool; _open_fail_logged: bool  # noqa: E702 - M-MOD cap
    _wal_wait_budget_exceeded: bool; stop_event: threading.Event  # noqa: E702 - M-MOD cap
    def _cid8(self) -> str: ...
    def _sqlite_off(self, reason: str) -> None: ...
    def _get_wal_wait_polls(self) -> int: ...
    def _set_wal_wait_polls(self, count: int) -> None: ...
    def _wal_wait_limit(self, max_polls: int | None) -> int: ...
# fmt: on


@dataclass(frozen=True, slots=True)
class ResumeAnchorDeps:
    """Инъектируемые эффекты resume anchor для детерминированных тестов."""

    open_ro: Callable[[Path], sqlite3.Connection]
    close: Callable[[sqlite3.Connection], None]
    sleep_fn: Callable[[float], None] = time.sleep
    config: policy.ResumeAnchorConfig | None = None


def _cleanup(stage: str, action: Callable[[], None]) -> None:
    try:
        action()
    except Exception as exc:
        _LOGGER.warning(
            "sqlite-tail-cleanup-failed stage=%s err=%s",
            stage,
            type(exc).__name__,
            exc_info=True,
        )


def finish_transcript_tail(
    tail: _TailLike,
    close_conn: Callable[[sqlite3.Connection], None],
    pool_provider: Callable[[], _PoolLike | None],
    breaker_report: Callable[[int | None, int, bool], None],
    cid_release: Callable[[str, str], None],
) -> None:
    """Завершить tail один раз с изоляцией каждого cleanup-этапа."""
    if tail._finished:
        return
    tail._finished = True

    def close() -> None:
        with tail._conn_lock:
            conn, tail._active_conn = tail._active_conn, None
        if conn is not None:
            close_conn(conn)

    _cleanup("connection", close)
    _cleanup(
        "pool", lambda: (pool := pool_provider()) is not None and pool.release_thread()
    )
    if getattr(tail.plan, "mode", "") in ("LIVE", "SHADOW"):
        _cleanup(
            "breaker",
            lambda: breaker_report(tail.probe_gen, tail.selects_ok, tail.failed),
        )
    if tail._owned_cid:
        _cleanup("cid", lambda: cid_release(tail._owned_cid, tail.turn_id))


def probe_cold_fs(db_path: Path | None) -> policy.ColdFsProbe:
    """Собрать безопасный снимок БД, WAL и родительского каталога."""
    if db_path is None:
        return policy.ColdFsProbe(valid_path=False)
    try:
        is_file = db_path.is_file()
        exists = db_path.exists()
        symlink = db_path.is_symlink()
        readable = is_file and os.access(db_path, os.R_OK)
        parent = db_path.parent
        parent_is_dir = parent.is_dir()
        parent_accessible = parent_is_dir and os.access(parent, os.R_OK | os.X_OK)
        wal_exists = Path(f"{db_path}-wal").exists()
    except OSError:
        return policy.ColdFsProbe(fs_error=True)
    return policy.ColdFsProbe(
        is_file, exists, symlink, readable, parent_is_dir, parent_accessible, wal_exists
    )


def is_cold_wal_error(exc: BaseException, db_path: Path | None) -> bool:
    """Строгий pool-классификатор: только читаемая БД без WAL."""
    if not isinstance(exc, sqlite3.OperationalError):
        return False
    if "unable to open database file" not in str(exc).lower():
        return False
    state = policy.classify_fs_probe(probe_cold_fs(db_path))
    return state is policy.ColdFsState.DB_READABLE_NO_WAL


def should_skip_cold_db_poll(tail: _TailLike, log: Callable[[str], None]) -> bool:
    """Не открывать ещё не созданную БД свежего хода и логировать один раз."""
    if cast(bool, getattr(tail, "resumed", True)) or tail.selects_ok != 0:
        return False
    if (
        policy.classify_fs_probe(probe_cold_fs(tail._db_path))
        is not policy.ColdFsState.DB_MISSING_PARENT_OK
    ):
        return False
    if not cast(bool, getattr(tail, "_sqlite_cold_db_wait_logged", False)):
        setattr(tail, "_sqlite_cold_db_wait_logged", True)
        log(f"sqlite-cold-db-wait cid={tail._cid8()} db=0")
    return True


def load_resume_anchor_config(
    environ: Mapping[str, str] | None = None,
) -> policy.ResumeAnchorConfig:
    """Загрузить строгую конфигурацию `AGY_SQLITE_ANCHOR_*`."""
    source = os.environ if environ is None else environ
    retries = int(source.get("AGY_SQLITE_ANCHOR_MAX_RETRIES", "3"))
    delay = float(source.get("AGY_SQLITE_ANCHOR_RETRY_DELAY_S", "0.05"))
    cap = float(source.get("AGY_SQLITE_ANCHOR_MAX_RETRY_DELAY_S", "0.25"))
    raw_direct = (
        source.get("AGY_SQLITE_ANCHOR_BACKOFF_DIRECT_RO", "true").strip().lower()
    )
    if raw_direct not in {"1", "0", "true", "false", "yes", "no", "on", "off"}:
        raise ValueError("invalid AGY_SQLITE_ANCHOR_BACKOFF_DIRECT_RO")
    return policy.ResumeAnchorConfig(
        retries, delay, cap, raw_direct in {"1", "true", "yes", "on"}
    )


def _anchor_value(rows: list[tuple[object, ...]]) -> int | None:
    value = rows[0][0] if rows else None
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _read_anchor(
    pool: _PoolLike | None,
    db_path: Path,
    sql: str,
    deps: ResumeAnchorDeps,
) -> int | None:
    if pool is not None:
        return _anchor_value(pool.query_rows(db_path, sql))
    conn = deps.open_ro(db_path)
    try:
        row = cast("tuple[object, ...] | None", conn.execute(sql).fetchone())
        return _anchor_value([row] if row is not None else [])
    finally:
        deps.close(conn)


def is_pool_backoff_error(exc: BaseException) -> bool:
    named = type(exc).__name__ == "SqliteRoPoolBackoffError"
    return named and "sqlite_ro_pool_backoff" in str(exc)


def resolve_resume_db_max_idx(
    pool: _PoolLike | None,
    db_path: Path,
    sql: str,
    deps: ResumeAnchorDeps,
) -> tuple[int | None, policy.ResumeAnchorCause | None]:
    """Прочитать db_max с isolated RO fallback и ограниченными ретраями."""
    state = policy.classify_fs_probe(probe_cold_fs(db_path))
    if (fs_cause := policy.resume_fs_failure_cause(state)) is not None:
        return None, fs_cause
    try:
        config = deps.config or load_resume_anchor_config()
    except (TypeError, ValueError):
        return None, policy.ResumeAnchorCause.DB_ERROR
    active_pool, retries, delay = pool, 0, config.retry_delay_s
    while True:
        try:
            value = _read_anchor(active_pool, db_path, sql, deps)
            if value is None:
                return None, policy.ResumeAnchorCause.DB_ERROR
            return value, None
        except (sqlite3.Error, RuntimeError) as exc:
            backoff = is_pool_backoff_error(exc)
            if backoff and config.backoff_direct_ro and active_pool is not None:
                active_pool = None
                continue
            fs_state = policy.classify_fs_probe(probe_cold_fs(db_path))
            cause = policy.classify_resume_db_error(backoff, str(exc), fs_state)
            if (
                not policy.is_retryable_resume_cause(cause)
                or retries >= config.max_retries
            ):
                return None, cause
            deps.sleep_fn(delay)
            retries += 1
            delay = min(delay * 2.0, config.max_retry_delay_s)


def handle_cold_wal_wait(
    tail: _TailLike,
    exc: sqlite3.Error,
    max_polls: int | None,
    log: Callable[[str], None],
) -> bool:
    """Применить единую cold-WAL политику и бюджет tail."""
    tail._wal_wait_budget_exceeded = False
    state = policy.classify_fs_probe(probe_cold_fs(tail._db_path))
    decision = policy.decide_tail_cold_wal_wait(
        isinstance(exc, sqlite3.OperationalError), str(exc), tail.selects_ok, state
    )
    if not decision.is_cold_wait:
        setattr(tail, "_sqlite_open_fail_cause", decision.cause)
        return False
    waited, limit = tail._get_wal_wait_polls(), tail._wal_wait_limit(max_polls)
    if waited >= limit:
        tail._wal_wait_budget_exceeded = True
        setattr(tail, "_sqlite_open_fail_cause", policy.ColdWaitCause.BUDGET_EXCEEDED)
        return False
    tail._set_wal_wait_polls(waited + 1)
    if waited == 0:
        log(f"sqlite-wal-wait cid={tail._cid8()} err={type(exc).__name__} wal=0")
    return True


def handle_sqlite_error(
    tail: _TailLike, exc: sqlite3.Error, log: Callable[[str], None]
) -> None:
    """Обработать SQLite-ошибку tail и дополнить open-fail точной причиной."""
    message = str(exc).lower()
    if "interrupted" in message and (tail._interrupted or tail.stop_event.is_set()):
        return
    tail._wal_wait_budget_exceeded = False
    operational = isinstance(exc, sqlite3.OperationalError)
    schema = operational and ("no such table" in message or "no such column" in message)
    if schema:
        tail.failed = True
        setattr(tail, "_sqlite_open_fail_cause", policy.ColdWaitCause.NON_WHITELIST_MSG)
        log(f"sqlite-schema-mismatch cid={tail._cid8()}")
        tail._sqlite_off("schema")
    elif operational:
        if handle_cold_wal_wait(tail, exc, None, log):
            return
        tail.failed = True
    elif isinstance(exc, sqlite3.DatabaseError):
        tail.failed = True
        setattr(tail, "_sqlite_open_fail_cause", policy.ColdWaitCause.NON_OPERATIONAL)
        tail._sqlite_off("db_error")
    if not tail._open_fail_logged:
        tail._open_fail_logged = True
        cause = cast(
            policy.ColdWaitCause,
            getattr(
                tail, "_sqlite_open_fail_cause", policy.ColdWaitCause.NON_OPERATIONAL
            ),
        )
        log(
            policy.format_sqlite_open_fail(
                tail._cid8(), type(exc).__name__, cause, tail._wal_wait_budget_exceeded
            )
        )


def handle_poll_exception(
    tail: _TailLike, exc: BaseException, log: Callable[[str], None]
) -> None:
    if is_pool_backoff_error(exc):
        tail.last_poll = "skip"
        if not cast(bool, getattr(tail, "_sqlite_pool_backoff_logged", False)):
            setattr(tail, "_sqlite_pool_backoff_logged", True)
            log(f"sqlite-pool-backoff cid={tail._cid8()}")
        return
    tail.last_poll = "error"
    log(f"sqlite-error cid={tail._cid8()} err={type(exc).__name__}")
    tail._sqlite_off("internal")
