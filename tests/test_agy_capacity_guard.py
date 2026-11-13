"""L1: fast-fail детектор capacity-503 (core/agy_capacity_guard.py)."""

from __future__ import annotations

import pytest

from core.agy_capacity_guard import (
    CAPACITY_REASON,
    capacity_error_body,
    fast_fail_enabled,
    is_capacity_exhausted_text,
    should_fast_fail_agy_capacity_503,
)

REAL_LINE = (
    "503 UNAVAILABLE: No capacity available for model gemini-3.8-flash-medium on the server"
)


@pytest.mark.parametrize(
    "line",
    [
        REAL_LINE,
        "error: MODEL_CAPACITY_EXHAUSTED",
        'status 503 {"message":"No capacity available for model x"}',
    ],
)
def test_detects_capacity_markers(line: str) -> None:
    assert is_capacity_exhausted_text(line)
    assert should_fast_fail_agy_capacity_503(line, {})


@pytest.mark.parametrize(
    "line",
    ["", "No capacity available in my calendar", "503 Service Unavailable", "all fine", None, 7],
)
def test_ignores_unrelated_lines(line: object) -> None:
    assert not is_capacity_exhausted_text(line, {})


def test_kill_switch_default_on_and_garbage_is_default() -> None:
    assert fast_fail_enabled({})
    assert fast_fail_enabled({"AGY_FAST_FAIL_ON_CAPACITY_503": "garbage"})
    for off in ("0", "false", "No", "OFF"):
        env = {"AGY_FAST_FAIL_ON_CAPACITY_503": off}
        assert not fast_fail_enabled(env)
        assert not should_fast_fail_agy_capacity_503(REAL_LINE, env)


def test_custom_markers_and_line_cap() -> None:
    assert is_capacity_exhausted_text("quota boom", {"AGY_CAPACITY_MARKERS": "Quota Boom"})
    assert not is_capacity_exhausted_text(REAL_LINE, {"AGY_CAPACITY_MARKERS": "other"})
    tail = "x" * 20 + REAL_LINE
    assert not is_capacity_exhausted_text(tail, {"AGY_CAPACITY_MAX_LINE_CHARS": "10"})
    assert is_capacity_exhausted_text(tail, {"AGY_CAPACITY_MAX_LINE_CHARS": "bad"})


def test_error_body_is_deterministic_503() -> None:
    body = capacity_error_body(REAL_LINE)
    assert body["code"] == 503 and body["type"] == CAPACITY_REASON == "model_capacity_exhausted"
    assert "gemini-3.8-flash-medium" in str(body["message"])
