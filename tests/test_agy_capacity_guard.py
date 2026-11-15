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
    from core.log_redaction import redact_log_text

    return redact_log_text(text)


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


@pytest.mark.parametrize(
    ("text", "secret"),
    [
        (("x" * 4072) + " S3cr3tT0k3nV4lu3_23char4567890", "S3cr3tT0k3nV4lu3"),
        (("x" * 4085) + " ghp_1234567890abcdef", "ghp_"),
        (("x " * 2040) + "ghp_1234567890abcdef", "ghp_"),
    ],
)
def test_window_cut_never_bisects_secret_token(text: str, secret: str) -> None:
    from core.agy_capacity_guard import summarize_capacity_text

    assert secret not in summarize_capacity_text(text, _default_redact, {})
    assert secret not in str(capacity_error_body(text)["message"])
    # сводка шире окна: секрет на границе окна виден в выводе, если бы он был обрублен, а не замаскирован
    env = {"AGY_CAPACITY_SUMMARY_MAX_CHARS": "100000"}
    full = summarize_capacity_text(text, _default_redact, env)
    assert secret not in full and full.endswith("***"), full[-40:]


def test_window_cut_drops_long_tail_token_instead_of_bisecting_it() -> None:
    from core.agy_capacity_guard import summarize_capacity_text

    env = {
        "AGY_CAPACITY_REDACT_WINDOW_CHARS": "20",
        "AGY_CAPACITY_REDACT_MARGIN_CHARS": "5",
        "AGY_CAPACITY_SUMMARY_MAX_CHARS": "30",
    }
    # токен начинается до окна (35) и длиннее запаса: он отбрасывается целиком, а не обрубается
    assert summarize_capacity_text("a " * 9 + "y" * 2000, lambda s: s, env) == "a a a a a a a a a"


def test_capacity_error_body_respects_explicit_env() -> None:
    env = {"AGY_CAPACITY_SUMMARY_MAX_CHARS": "12"}
    message = str(capacity_error_body("No capacity available " + "word " * 50, env=env)["message"])
    assert message == "upstream model has no capacity available: No capacity "
    assert len(str(capacity_error_body("No capacity available " + "word " * 50)["message"])) > len(message) + 100


# ---- Cycle 5 RW-002/RW-003: срез окна не оставляет обрубок секрета ------------------------------------------


@pytest.mark.parametrize(
    ("detail", "stub"),
    [
        ("\t" * 32764 + "S3cr" + "x" * 4100, "S3cr"),
        ("Error:\r" + "\t" * 32753 + "eyJhbGci" + "A" * 4200, "eyJhbGci"),
        ("\t" * 32760 + "S3crK3y" * 800, "S3cr"),
        ("\xa0" * 4092 + "S3cr" + "B" * 600, "S3cr"),
        ("\v" * 4092 + "S3cr" + "B" * 600, "S3cr"),
        ('{"pad":"' + "A" * 4077 + '","x":"' + "S3cr" + "B" * 600 + '"}', "S3cr"),
        ("Error:" + "k=" * 3000 + "S3cr" + "B" * 600, "S3cr"),
    ],
)
def test_cut_never_leaves_secret_stub_for_any_whitespace_or_compact_input(detail: str, stub: str) -> None:
    from core.agy_capacity_guard import summarize_capacity_text
    from core.log_redaction import redact_log_text

    message = str(capacity_error_body(detail)["message"])
    assert stub not in message, message
    assert stub not in summarize_capacity_text(detail, redact_log_text, {})


def test_cut_at_space_guards_non_positive_target_and_any_unicode_whitespace() -> None:
    from core.agy_capacity_guard import _cut_at_space

    assert _cut_at_space("abc", 0, 5) == 0 and _cut_at_space("", 0, 5) == 0
    for sep in ("\t", "\r", "\v", "\f", "\xa0"):
        text = "ab" + sep + "S3cr" + "x" * 50
        assert _cut_at_space(text, 6, 4) == 2, repr(sep)


def test_cut_drops_boundary_token_in_compact_text_but_keeps_single_run() -> None:
    from core.agy_capacity_guard import _cut_at_space, summarize_capacity_text

    assert _cut_at_space('{"a":"S3cr' + "B" * 50, 10, 4) == 6
    assert len(summarize_capacity_text("x" * 100000, lambda s: s, {})) == 200


def test_cut_is_linear_on_long_inputs() -> None:
    import time

    from core.agy_capacity_guard import summarize_capacity_text

    started = time.monotonic()
    for text in ("\t" * 200000 + "x" * 200000, '{"a":"' * 60000, "k=" * 200000):
        summarize_capacity_text(text, lambda s: s, {})
    assert time.monotonic() - started < 1.0
