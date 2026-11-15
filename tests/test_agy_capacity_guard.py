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


def test_bare_prose_with_reason_code_does_not_fast_fail() -> None:
    for prose in (
        "the reason code model_capacity_exhausted is documented in the runbook",
        "Note: model_capacity_exhausted means the upstream is full",
    ):
        assert not is_capacity_exhausted_text(prose, {})
        assert not should_fast_fail_agy_capacity_503(prose, {})
    assert is_capacity_exhausted_text("reason=model_capacity_exhausted", {"AGY_CAPACITY_MARKERS": "model_capacity_exhausted"})
    assert is_capacity_exhausted_text('{"code": 503, "reason": "MODEL_CAPACITY_EXHAUSTED"}', {})
    assert is_capacity_exhausted_text("RESOURCE_EXHAUSTED model_capacity_exhausted", {})


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


# ---- RW-001: bound -> normalize -> redact -> clamp, запас окна маскирования ----------------------


def _default_redact(text: str) -> str:
    from core.log_redaction import mask_credential_context, mask_long_tokens, safe_log_tokens

    return mask_long_tokens(mask_credential_context(text), safe_tokens=safe_log_tokens())


@pytest.mark.parametrize(
    "secret",
    ["ghp_1234567890abcdef", "sk-abcdef1234567890", "AIzaSyA1234567890bcd", "tok" + "A1b2C3d4E5" * 3],
)
def test_error_body_whitespace_prefix_does_not_cut_secret_at_window(secret: str) -> None:
    for pad in (4086, 4090, 4096, 4000, 5000):
        message = str(capacity_error_body(" " * pad + secret)["message"])
        assert secret[:10] not in message, (pad, message)
    message = str(capacity_error_body("\n".join([""] * 4090) + secret)["message"])
    assert secret[:10] not in message


@pytest.mark.parametrize(("window", "summary"), [("200", "200"), ("50", "4096"), ("4096", "4096")])
def test_redact_window_keeps_margin_over_summary(window: str, summary: str) -> None:
    from core.agy_capacity_guard import redact_margin_chars, redact_window_chars, summarize_capacity_text, summary_max_chars

    env = {"AGY_CAPACITY_REDACT_WINDOW_CHARS": window, "AGY_CAPACITY_SUMMARY_MAX_CHARS": summary}
    assert redact_margin_chars(env) == 512
    assert redact_window_chars(env) >= summary_max_chars(env) + redact_margin_chars(env)
    limit = summary_max_chars(env)
    for secret in ("ghp_1234567890abcdef", "sk-abcdef1234567890", "x" * 30):
        text = "a " * ((limit - 10) // 2) + secret
        # без запаса секрет, начинающийся у предела сводки, резался бы до redact()
        out = summarize_capacity_text(text, _default_redact, env)
        assert secret[:8] not in out, out


def test_redact_margin_is_configurable_and_garbage_falls_back() -> None:
    from core.agy_capacity_guard import redact_margin_chars, redact_window_chars

    assert redact_margin_chars({"AGY_CAPACITY_REDACT_MARGIN_CHARS": "1024"}) == 1024
    assert redact_margin_chars({"AGY_CAPACITY_REDACT_MARGIN_CHARS": "bad"}) == 512
    env = {"AGY_CAPACITY_REDACT_WINDOW_CHARS": "10", "AGY_CAPACITY_SUMMARY_MAX_CHARS": "100", "AGY_CAPACITY_REDACT_MARGIN_CHARS": "1024"}
    assert redact_window_chars(env) == 1124


def test_summarize_normalizes_whitespace_before_window_and_bounds_raw_input() -> None:
    from core.agy_capacity_guard import raw_max_chars, summarize_capacity_text

    secret = "ghp_1234567890abcdef"
    assert secret[:8] not in summarize_capacity_text(" " * 4086 + secret, _default_redact, {})
    assert raw_max_chars({}) == 32768
    assert raw_max_chars({"AGY_CAPACITY_REDACT_WINDOW_CHARS": "100000"}) == 400000
    assert len(summarize_capacity_text("x" * 100000, lambda s: s, {})) == 200
    # потолок сырого входа не меньше окна маскирования * 4, даже если задан меньше
    env = {"AGY_CAPACITY_RAW_MAX_CHARS": "10", "AGY_CAPACITY_REDACT_WINDOW_CHARS": "10", "AGY_CAPACITY_SUMMARY_MAX_CHARS": "10"}
    assert raw_max_chars(env) == (10 + 512) * 4
    # хвост за потолком сырого входа отбрасывается ДО нормализации
    env = {"AGY_CAPACITY_RAW_MAX_CHARS": "40000"}
    assert summarize_capacity_text(" " * 39990 + "ab" + " " * 20 + "TAIL", lambda s: s, env) == "ab"


def test_raw_cap_never_bisects_secret_token() -> None:
    from core.agy_capacity_guard import raw_max_chars, summarize_capacity_text

    secret = "ghp_1234567890abcdef"
    text = " " * 32762 + secret + " no capacity available 503"
    assert raw_max_chars({}) == 32768 and len(text) - len(secret) - 26 == 32762
    summary = summarize_capacity_text(text, _default_redact, {})
    assert "ghp_" not in summary and summary.startswith("***"), summary
    message = str(capacity_error_body(text)["message"])
    assert "ghp_" not in message and "***" in message, message
