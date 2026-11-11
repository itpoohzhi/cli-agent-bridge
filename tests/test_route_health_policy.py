# ruff: noqa: E501,E701,E702,I001
# fmt: off
from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.activity_window import ActivityWindow as W
from core.effort_policy import resolve_alias_effort as e
from core.route_health_policy import AttemptDecision as A, CanonDigestResult as D, FailureCategory as F, HealthReason as H, NormalizedModelRoute as M, RetryBudgetConfig as C, RetryReason as R, RouteHealthStatus as S, advance_sliding_deadline as d, classify_provider_failure as c, compute_attempt_decision as a, detect_effective_env_drift as v, evaluate_route_health as h, inspect_canon_payload as k, normalize_model_route as n, redact_diagnostic_text as x, validate_retry_config as y
from core.stream_interruption_recovery import evaluate_stream_retry_eligibility as r, is_transient_stream_interruption as t

U = "403 OAuth refresh rejected: token refresh failed"
T = "per_attempt_upper duration_s=18.288681"
V = "configured=1500 effective=300"
Q = "capacity unavailable; retry after 401 seconds"
P = "connection reset"

@pytest.mark.parametrize("suffix", ("low", "medium", "high"))
def test_alias_suffix(suffix: str) -> None:
    assert n(f"claude-opus-5-5-{suffix}") == M("claude-opus-5-5", suffix, True)

def test_alias_policy() -> None:
    assert n(" Claude-Opus-5-5-HIGH ", " LOW ") == M("Claude-Opus-5-5", "low", True)
    assert e(" CLAUDE-OPUS-5-5-HIGH ", {"claude-opus-5-5": object()}, ("low", "medium", "high"), True) == ("claude-opus-5-5", "high")
    assert n("alpha-high", known_models=("alpha", "alpha-high")) == M("alpha-high", None, False); assert e("bad model-high", {"bad model": object()}, ("low", "medium", "high"), True) is None

@pytest.mark.parametrize("model,level", (("", None), ("   ", None), ("m", "ultra"), ("blocked -high", None)))
def test_alias_invalid(model: str, level: str | None) -> None:
    with pytest.raises(ValueError): _ = n(model, level)

def test_redaction() -> None:
    secrets = "Bearer bearer.value Basic basic.value ya29.oauth 1//refresh sk-key AIzaGoogle refresh_token=refresh access_token:access client_secret=client api_key=api password=pwd secret=sec token=tok cookie=cookie user@example.com\x00\n"
    z = x(secrets + "x" * 300)
    assert len(z) <= 256 and len(x("x" * 300)) == 256
    assert z.count("<redacted>") >= 7
    assert all(value not in z for value in ("bearer.value", "ya29.", "1//", "@", "\x00", "\n"))
    cases = ('{"access_token":"TOPSECRET"}', r'{\"access_token\":\"TOPSECRET\"}', "Cookie: a=1; sid=secret2", r'{"access_token":"prefix\"LEAK"}', r'{"pass\u0077ord":"TOPSECRET42"}', r'pass\u005cu0077ord=TOPSECRET42', '{"password":"TOPSECRET42', "id_token=TOPSECRET42", "password=correct horse", "pass\x00word=TOPSECRET42", "password\x00=TOPSECRET42", "password=TOP\x00SECRET42", 'Bearer "TOPSECRET42"', r'Bearer \"TOPSECRET\"', 'password="TOPSECRET\\', r"password=TOP\u000aSECRET", "Authorization: Token TOPSECRET42", "pass\x01word=TOPSECRET42", "pass\x1fword=TOPSECRET42", "pass\x7fword=TOPSECRET42")
    assert all("<redacted>" in x(text) for text in cases)
    assert all("TOPSECRET42" not in x(text) for text in (r"pass\u005cu005cu0077ord=TOPSECRET42", r'Bearer \\"TOPSECRET42\\"', r'{\\"access_token\\":\\"TOPSECRET42\\"}'))
    assert all("TOPSECRET42" not in x(text) and "<redacted>" in x(text) for text in (r"pass\u0000word=TOPSECRET42", "pass" + r"\u005c" + "u005c" * 7 + "u0077ord=TOPSECRET42"))
    assert x(r"\uD800").encode("utf-8") == b" "

@pytest.mark.parametrize("case", (
    (401, "anything", F.AUTH_REFRESH_EXHAUSTED, False), (403, "OAuth rejected", F.AUTH_REFRESH_EXHAUSTED, False),
    (503, "token refresh failed", F.AUTH_REFRESH_EXHAUSTED, False), (429, "quota exceeded", F.LIMIT_BLOCKED, False),
    (503, "quota exceeded", F.LIMIT_BLOCKED, False), (503, "SSL_ERROR_SYSCALL", F.UPSTREAM_TLS_STALL, False),
    (429, "busy", F.CAPACITY_EXHAUSTED, True), (503, Q, F.CAPACITY_EXHAUSTED, True),
    (400, "model_capacity_exhausted", F.CAPACITY_EXHAUSTED, True), (0, "HTTP 401: invalid auth", F.AUTH_REFRESH_EXHAUSTED, False),
    (403, "max_tokens exceeded", F.FATAL_REQUEST_ERROR, False), (403, "API key not valid", F.AUTH_REFRESH_EXHAUSTED, False),
))
def test_failures(case: tuple[int, str, F, bool]) -> None:
    status, reason, category, retryable = case; z = c(status, reason)
    assert (z.category, z.retryable) == (category, retryable)

def test_retry_filter() -> None:
    assert t(P) is True and t(P + "; HTTP 429 Too Many Requests") is True
    blocked = (P + " quota exceeded", P + " token refresh failed", P + " TLS handshake timeout", P + " HTTP 401 Unauthorized", P + " HTTP 403 Forbidden", "connection reset: Bad Request", "HTTP/1.1 405 Method Not Allowed; connection reset", P + "; HTTP 440 Login Time-out", P + "; HTTP 498 Invalid Token", P + "; HTTP 499", "connection reset: token\x00refresh failed", "A" * 4096 + P + "; token refresh failed", P + " " + "A" * 4096 + " token refresh failed", "connection reset; HTTP\x01403", 'connection reset; {"status":401}', "connection reset; status_code=404", P + "; API key not valid")
    assert all(t(text) is False for text in blocked)
    assert all(r(error_text=text, delivered=False).can_retry is False for text in blocked[3:])
    allowed = r(error_text=P, delivered=False)
    assert allowed.can_retry is True and allowed.attempt_budget_s > 0.0
    exhausted = r(error_text=P, delivered=False, elapsed_s=86.0)
    assert exhausted.can_retry is False and exhausted.attempt_budget_s == 0.0
    invalid = ({"max_attempts": 0}, {"elapsed_s": float("nan")}, {"elapsed_s": -1.0}, {"budget_config": C(max_attempts=0)}, {"elapsed_s": 10**1000}, {"budget_config": C(total_budget_s=10**1000)})
    assert all(not r(error_text=P, delivered=False, **kw).can_retry for kw in invalid)
    assert r(error_text=None, delivered=False).can_retry is False and r(error_text=P, delivered=False, budget_config="bad").can_retry is False
    assert t(P, source="MODEL_CONTENT") is False and r(error_text=P, delivered=False, source="MODEL_CONTENT").can_retry is False
    stricter = r(error_text=P, delivered=False, attempt=1, max_attempts=3, budget_config=C(max_attempts=1))
    assert stricter.can_retry is False and stricter.keep_hot_session is True

@pytest.mark.parametrize("case", ((0.0, 0.0, (), True, H.READY), (5.001, 5.0, (), False, H.STALE_HEALTH_PROBE), (-0.001, 5.0, (), False, H.STALE_HEALTH_PROBE), (1.0, 5.0, ("Z", "A"), False, H.ENV_DRIFT_DETECTED)))
def test_health_limits(case: tuple[float, float, tuple[str, ...], bool, H]) -> None:
    age, limit, changed, available, reason = case
    assert h("model", (), age, limit, changed) == S("model", available, reason, tuple(sorted(changed)))

def test_health_order() -> None:
    assert h("Claude-Opus-5-5-High", ("claude-opus-5-5",), 1.0, 10.0) == S("Claude-Opus-5-5", False, H.LIMIT_BLOCKED, ())
    assert h(n("alpha-high", known_models=("alpha", "alpha-high")), ("alpha",), 1.0, 10.0) == S("alpha-high", True, H.READY, ()); assert h("alpha", ("alpha-high",), 1.0, 10.0) == S("alpha", True, H.READY, ())

@pytest.mark.parametrize("age,limit", ((float("nan"), 1.0), (float("inf"), 1.0), (1.0, float("inf")), (1.0, -1.0)))
def test_health_invalid(age: float, limit: float) -> None:
    with pytest.raises(ValueError): _ = h("model", (), age, limit)

def test_env_drift() -> None:
    assert "1500" in V and "300" in V
    assert v({"A": "1", "TIMEOUT": "1500"}, {"A": "1", "TIMEOUT": "300"}, ("TIMEOUT", "A")) == ("TIMEOUT",)

@pytest.mark.parametrize("config", (C(total_budget_s=0.0), C(reserve_s=-0.001), C(reserve_s=90.0), C(min_attempt_budget_s=0.0), C(max_attempts=0), C(idle_timeout_s=0.0), C(total_budget_s=float("inf")), C(reserve_s=float("nan")), C(max_attempts=1.5)))  # type: ignore[arg-type]
def test_config_invalid(config: C) -> None:
    with pytest.raises(ValueError): _ = y(config)

@pytest.mark.parametrize("category", (F.AUTH_REFRESH_EXHAUSTED, F.LIMIT_BLOCKED, F.UPSTREAM_TLS_STALL, F.FATAL_REQUEST_ERROR, "U", "UNKNOWN"))
def test_retry_closed(category: str) -> None:
    assert a(C(), 0, 0.0, category) == A(False, 0.0, R.NON_RETRYABLE_CATEGORY)

def test_retry_budget() -> None:
    config = C(109.732084, 0.0, 4.0, 6, 30.0); j = a(config, 0, 0.0)
    assert j == A(True, 18.288, R.BUDGET_OK)
    assert j.attempt_budget_s <= float(T.rsplit("=", 1)[1])
    assert a(config, 6, 0.0).reason is R.MAX_ATTEMPTS_REACHED
    assert a(C(1.0009, 0.0, 1.0005, 1, 30.0), 0, 0.0).reason is R.BUDGET_EXHAUSTED
    assert a(C(), 0, 1e308).reason is R.BUDGET_EXHAUSTED

@pytest.mark.parametrize("index,elapsed", ((-1, 0.0), (2.5, 0.0), (True, 0.0), (0, -0.001), (0, float("inf"))))
def test_attempt_invalid(index: object, elapsed: float) -> None:
    with pytest.raises(ValueError): _ = a(C(), index, elapsed)

def test_window() -> None:
    assert d(18.0, 0.0, 5.0, 20.0) == 20.0
    ticks = iter((10.0, 12.0)); window = W(5.0, 20.0, clock=lambda: next(ticks))
    assert window.idle_deadline == 15.0 and window.touch() == 17.0
    capped = W(20.0, 30.0, attempt_budget_s=12.0, clock=lambda: 10.0)
    assert capped.safety_deadline == 22.0 and capped.idle_deadline == 22.0
    with pytest.raises(ValueError): _ = d(1e308, 0.0, 1e308, 1e308)

@pytest.mark.parametrize("args", ((float("nan"), 0.0, 1.0, 1.0), (0.0, float("inf"), 1.0, 1.0), (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 1.0, 0.0), (0.0, 1.0, 1.0, 1.0)))
def test_window_invalid(args: tuple[float, ...]) -> None:
    with pytest.raises(ValueError): _ = d(*args)

def test_canon() -> None:
    text = "Я<!-- КАНОН-КОНЕЦ -->\n"; first = k(text)
    same = k(text, previous_sha256=first.sha256_hex); changed = k(text + "x", previous_sha256=first.sha256_hex)
    middle = k("<!-- КАНОН-КОНЕЦ -->\ntruncated")
    assert first == D(True, first.sha256_hex, len(text.encode()), False)
    assert same.unchanged is True
    assert changed.unchanged is False and changed.has_canon_end_marker is False
    assert middle.has_canon_end_marker is False

def test_frozen_result() -> None:
    assert c(403, U).category is F.AUTH_REFRESH_EXHAUSTED
    z = n("m")
    with pytest.raises(FrozenInstanceError): setattr(z, "canonical_model", "changed")  # noqa: B010
