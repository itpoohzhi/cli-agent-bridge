from __future__ import annotations

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
    ColdFsProbe,
    ColdFsState,
    ColdWaitCause,
    ResumeAnchorCause,
    ResumeAnchorConfig,
    classify_fs_probe,
    classify_resume_db_error,
    decide_tail_cold_wal_wait,
    format_resume_off,
    format_sqlite_open_fail,
    is_retryable_resume_cause,
)


@pytest.mark.parametrize(
    ("probe", "expected"),
    [
        (ColdFsProbe(valid_path=False), ColdFsState.INVALID_PATH),
        (ColdFsProbe(fs_error=True), ColdFsState.FS_OSERROR),
        (
            ColdFsProbe(db_is_file=True, db_readable=False),
            ColdFsState.DB_UNREADABLE,
        ),
        (
            ColdFsProbe(db_is_file=True, db_readable=True),
            ColdFsState.DB_READABLE_NO_WAL,
        ),
        (
            ColdFsProbe(db_is_file=True, db_readable=True, wal_exists=True),
            ColdFsState.DB_READY_WITH_WAL,
        ),
        (ColdFsProbe(db_exists=True), ColdFsState.DB_UNREADABLE),
        (ColdFsProbe(db_is_symlink=True), ColdFsState.DB_UNREADABLE),
        (ColdFsProbe(wal_exists=True), ColdFsState.DB_READY_WITH_WAL),
        (
            ColdFsProbe(parent_is_dir=False),
            ColdFsState.PARENT_UNAVAILABLE,
        ),
        (
            ColdFsProbe(parent_is_dir=True, parent_accessible=False),
            ColdFsState.PARENT_UNAVAILABLE,
        ),
        (
            ColdFsProbe(parent_is_dir=True, parent_accessible=True),
            ColdFsState.DB_MISSING_PARENT_OK,
        ),
    ],
)
def test_classify_fs_probe(probe: ColdFsProbe, expected: ColdFsState) -> None:
    assert classify_fs_probe(probe) is expected


@pytest.mark.parametrize(
    ("operational", "message", "selects", "state", "budget", "allowed", "cause"),
    [
        (
            False,
            "unable to open database file",
            0,
            ColdFsState.DB_MISSING_PARENT_OK,
            False,
            False,
            ColdWaitCause.NON_OPERATIONAL,
        ),
        (
            True,
            "unable to open database file",
            1,
            ColdFsState.DB_MISSING_PARENT_OK,
            False,
            False,
            ColdWaitCause.POST_SELECT,
        ),
        (
            True,
            "disk I/O error",
            0,
            ColdFsState.DB_MISSING_PARENT_OK,
            False,
            False,
            ColdWaitCause.NON_WHITELIST_MSG,
        ),
        (
            True,
            "unable to open database file",
            0,
            ColdFsState.DB_READY_WITH_WAL,
            False,
            False,
            ColdWaitCause.WAL_EXISTS,
        ),
        (
            True,
            "unable to open database file",
            0,
            ColdFsState.DB_UNREADABLE,
            False,
            False,
            ColdWaitCause.DB_UNREADABLE,
        ),
        (
            True,
            "unable to open database file",
            0,
            ColdFsState.PARENT_UNAVAILABLE,
            False,
            False,
            ColdWaitCause.PARENT_UNAVAILABLE,
        ),
        (
            True,
            "unable to open database file",
            0,
            ColdFsState.FS_OSERROR,
            False,
            False,
            ColdWaitCause.FS_OSERROR,
        ),
        (
            True,
            "unable to open database file",
            0,
            ColdFsState.INVALID_PATH,
            False,
            False,
            ColdWaitCause.INVALID_PATH,
        ),
        (
            True,
            "unable to open database file",
            0,
            ColdFsState.DB_READABLE_NO_WAL,
            False,
            True,
            ColdWaitCause.COLD_WAIT,
        ),
        (
            True,
            "unable to open database file",
            0,
            ColdFsState.DB_MISSING_PARENT_OK,
            True,
            False,
            ColdWaitCause.BUDGET_EXCEEDED,
        ),
    ],
)
def test_decide_tail_cold_wal_wait(
    operational: bool,
    message: str,
    selects: int,
    state: ColdFsState,
    budget: bool,
    allowed: bool,
    cause: ColdWaitCause,
) -> None:
    decision = decide_tail_cold_wal_wait(operational, message, selects, state, budget)
    assert (decision.is_cold_wait, decision.cause) == (allowed, cause)


@pytest.mark.parametrize(
    ("pool_backoff", "message", "expected"),
    [
        (True, "sqlite_ro_pool_backoff", ResumeAnchorCause.POOL_BACKOFF_EXHAUSTED),
        (False, "database is locked", ResumeAnchorCause.DB_LOCKED_EXHAUSTED),
        (False, "database table is busy", ResumeAnchorCause.DB_LOCKED_EXHAUSTED),
        (False, "unable to open database file", ResumeAnchorCause.DB_LOCKED_EXHAUSTED),
        (False, "database disk image is malformed", ResumeAnchorCause.DB_ERROR),
    ],
)
def test_classify_resume_db_error(
    pool_backoff: bool, message: str, expected: ResumeAnchorCause
) -> None:
    assert classify_resume_db_error(pool_backoff, message) is expected


def test_retryable_resume_causes_are_explicit() -> None:
    assert is_retryable_resume_cause(ResumeAnchorCause.POOL_BACKOFF_EXHAUSTED)
    assert is_retryable_resume_cause(ResumeAnchorCause.DB_LOCKED_EXHAUSTED)
    assert not is_retryable_resume_cause(ResumeAnchorCause.DB_ERROR)


@pytest.mark.parametrize(
    "config",
    [
        ResumeAnchorConfig(max_retries=0, retry_delay_s=0.0, max_retry_delay_s=0.0),
        ResumeAnchorConfig(),
    ],
)
def test_resume_anchor_config_accepts_valid_values(config: ResumeAnchorConfig) -> None:
    assert config.max_retries >= 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_retries": -1},
        {"max_retries": True},
        {"retry_delay_s": float("nan")},
        {"max_retry_delay_s": float("inf")},
        {"retry_delay_s": 1.0, "max_retry_delay_s": 0.5},
        {"backoff_direct_ro": 1},
    ],
)
def test_resume_anchor_config_rejects_invalid_values(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        ResumeAnchorConfig(**kwargs)  # type: ignore[arg-type]


def test_diagnostic_formatters_preserve_prefixes() -> None:
    assert (
        format_resume_off("cid12345", "resume_unanchored", ResumeAnchorCause.DB_MISSING)
        == "sqlite-off cid=cid12345 reason=resume_unanchored cause=db_missing"
    )
    assert format_resume_off("cid12345", "breaker", None).endswith("reason=breaker")
    assert format_sqlite_open_fail(
        "cid12345", "OperationalError", ColdWaitCause.BUDGET_EXCEEDED, True
    ) == (
        "sqlite-open-fail cid=cid12345 err=OperationalError cold=0 "
        "wal_wait_budget_exceeded=1 cause=budget_exceeded"
    )
