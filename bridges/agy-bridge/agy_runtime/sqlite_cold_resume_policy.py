"""Чистая политика cold-start SQLite и fail-closed resume anchor."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum


class ColdFsState(StrEnum):
    """Нормализованное состояние файлов SQLite без зависимости от I/O API."""

    DB_MISSING_PARENT_OK = "db_missing_parent_ok"
    DB_READABLE_NO_WAL = "db_readable_no_wal"
    DB_READY_WITH_WAL = "db_ready_with_wal"
    DB_UNREADABLE = "db_unreadable"
    PARENT_UNAVAILABLE = "parent_unavailable"
    FS_OSERROR = "fs_oserror"
    INVALID_PATH = "invalid_path"


class ColdWaitCause(StrEnum):
    """Причина принятия или отклонения cold-WAL ожидания tail."""

    COLD_WAIT = "cold_wait"
    WAL_EXISTS = "wal_exists"
    POST_SELECT = "post_select"
    NON_WHITELIST_MSG = "non_whitelist_msg"
    BUDGET_EXCEEDED = "budget_exceeded"
    DB_UNREADABLE = "db_unreadable"
    PARENT_UNAVAILABLE = "parent_unavailable"
    FS_OSERROR = "fs_oserror"
    NON_OPERATIONAL = "non_operational"
    INVALID_PATH = "invalid_path"


class ResumeAnchorCause(StrEnum):
    """Структурированная причина fail-closed resume anchor."""

    TRANSCRIPT_ERROR = "transcript_error"
    DB_MISSING = "db_missing"
    DB_UNREADABLE = "db_unreadable"
    PARENT_UNAVAILABLE = "parent_unavailable"
    FS_OSERROR = "fs_oserror"
    POOL_BACKOFF_EXHAUSTED = "pool_backoff_exhausted"
    DB_LOCKED_EXHAUSTED = "db_locked_exhausted"
    DB_ERROR = "db_error"


@dataclass(frozen=True, slots=True)
class ColdFsProbe:
    """Снимок фактов ФС, собранный effect-shell слоем."""

    db_is_file: bool = False
    db_exists: bool = False
    db_is_symlink: bool = False
    db_readable: bool = False
    parent_is_dir: bool = False
    parent_accessible: bool = False
    wal_exists: bool = False
    fs_error: bool = False
    valid_path: bool = True


@dataclass(frozen=True, slots=True)
class ColdWaitDecision:
    """Результат pure-классификации cold-WAL ошибки."""

    is_cold_wait: bool
    cause: ColdWaitCause


@dataclass(frozen=True, slots=True)
class ResumeAnchorConfig:
    """Ограниченная конфигурация повторов resume anchor."""

    max_retries: int = 3
    retry_delay_s: float = 0.05
    max_retry_delay_s: float = 0.25
    backoff_direct_ro: bool = True

    def __post_init__(self) -> None:
        if type(self.max_retries) is not int or self.max_retries < 0:
            raise ValueError("max_retries must be a non-negative integer")
        delays = (self.retry_delay_s, self.max_retry_delay_s)
        if any(not math.isfinite(value) or value < 0.0 for value in delays):
            raise ValueError("retry delays must be finite and non-negative")
        if self.retry_delay_s > self.max_retry_delay_s:
            raise ValueError("retry_delay_s exceeds max_retry_delay_s")
        if type(self.backoff_direct_ro) is not bool:
            raise ValueError("backoff_direct_ro must be bool")


def classify_fs_probe(probe: ColdFsProbe) -> ColdFsState:
    """Свести ФС-факты к одному безопасному состоянию."""
    if not probe.valid_path:
        return ColdFsState.INVALID_PATH
    if probe.fs_error:
        return ColdFsState.FS_OSERROR
    if probe.db_is_file:
        if not probe.db_readable:
            return ColdFsState.DB_UNREADABLE
        return (
            ColdFsState.DB_READY_WITH_WAL
            if probe.wal_exists
            else ColdFsState.DB_READABLE_NO_WAL
        )
    if probe.db_exists or probe.db_is_symlink:
        return ColdFsState.DB_UNREADABLE
    if probe.wal_exists:
        return ColdFsState.DB_READY_WITH_WAL
    if not probe.parent_is_dir or not probe.parent_accessible:
        return ColdFsState.PARENT_UNAVAILABLE
    return ColdFsState.DB_MISSING_PARENT_OK


def decide_tail_cold_wal_wait(
    operational: bool,
    message: str,
    selects_ok: int,
    state: ColdFsState,
    budget_exceeded: bool = False,
) -> ColdWaitDecision:
    """Разрешить cold wait только для whitelist ошибки и безопасной ФС."""
    if not operational:
        return ColdWaitDecision(False, ColdWaitCause.NON_OPERATIONAL)
    if selects_ok != 0:
        return ColdWaitDecision(False, ColdWaitCause.POST_SELECT)
    if "unable to open database file" not in message.lower():
        return ColdWaitDecision(False, ColdWaitCause.NON_WHITELIST_MSG)
    reject = {
        ColdFsState.DB_READY_WITH_WAL: ColdWaitCause.WAL_EXISTS,
        ColdFsState.DB_UNREADABLE: ColdWaitCause.DB_UNREADABLE,
        ColdFsState.PARENT_UNAVAILABLE: ColdWaitCause.PARENT_UNAVAILABLE,
        ColdFsState.FS_OSERROR: ColdWaitCause.FS_OSERROR,
        ColdFsState.INVALID_PATH: ColdWaitCause.INVALID_PATH,
    }.get(state)
    if reject is not None:
        return ColdWaitDecision(False, reject)
    cause = (
        ColdWaitCause.BUDGET_EXCEEDED if budget_exceeded else ColdWaitCause.COLD_WAIT
    )
    return ColdWaitDecision(not budget_exceeded, cause)


def resume_fs_failure_cause(state: ColdFsState | None) -> ResumeAnchorCause | None:
    """Преобразовать небезопасное состояние ФС в точную anchor-причину."""
    return {
        ColdFsState.DB_MISSING_PARENT_OK: ResumeAnchorCause.DB_MISSING,
        ColdFsState.DB_UNREADABLE: ResumeAnchorCause.DB_UNREADABLE,
        ColdFsState.PARENT_UNAVAILABLE: ResumeAnchorCause.PARENT_UNAVAILABLE,
        ColdFsState.FS_OSERROR: ResumeAnchorCause.FS_OSERROR,
        ColdFsState.INVALID_PATH: ResumeAnchorCause.DB_UNREADABLE,
    }.get(state)


def classify_resume_db_error(
    pool_backoff: bool,
    message: str,
    fs_state: ColdFsState | None = None,
) -> ResumeAnchorCause:
    """Классифицировать исчерпанную ошибку чтения resume anchor."""
    if pool_backoff:
        return ResumeAnchorCause.POOL_BACKOFF_EXHAUSTED
    lowered = message.lower()
    if "unable to open database file" in lowered:
        if fs_state is ColdFsState.DB_READABLE_NO_WAL:
            return ResumeAnchorCause.DB_LOCKED_EXHAUSTED
        return resume_fs_failure_cause(fs_state) or ResumeAnchorCause.DB_ERROR
    if any(token in lowered for token in ("locked", "busy")):
        return ResumeAnchorCause.DB_LOCKED_EXHAUSTED
    return ResumeAnchorCause.DB_ERROR


def is_retryable_resume_cause(cause: ResumeAnchorCause) -> bool:
    """Проверить, разрешён ли bounded retry для причины anchor."""
    return cause in (
        ResumeAnchorCause.POOL_BACKOFF_EXHAUSTED,
        ResumeAnchorCause.DB_LOCKED_EXHAUSTED,
    )


def format_resume_off(
    cid8: str, reason: str, cause: ResumeAnchorCause | str | None
) -> str:
    """Сохранить прежний префикс sqlite-off и аддитивно добавить cause."""
    base = f"sqlite-off cid={cid8} reason={reason}"
    return f"{base} cause={cause}" if reason == "resume_unanchored" and cause else base


def format_sqlite_open_fail(
    cid8: str,
    error_name: str,
    cause: ColdWaitCause,
    budget_exceeded: bool,
) -> str:
    """Сохранить прежние поля open-fail и аддитивно добавить cause."""
    budget = " wal_wait_budget_exceeded=1" if budget_exceeded else ""
    return f"sqlite-open-fail cid={cid8} err={error_name} cold=0{budget} cause={cause}"
