# ruff: noqa: E501,E701,E702,I001
# fmt: off
from __future__ import annotations

import sys
import time
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
P = "connection reset"; Z = "TOPSECRET42"; AF = (F.AUTH_REFRESH_EXHAUSTED, False); CE = (F.CAPACITY_EXHAUSTED, True); FF = (F.FATAL_REQUEST_ERROR, False); LB = (F.LIMIT_BLOCKED, False); TS = (F.UPSTREAM_TLS_STALL, False); B8 = "abcdefghi" * 8000

@pytest.mark.parametrize("suffix", ("low", "medium", "high"))
def test_alias_suffix(suffix: str) -> None:
    assert n(f"claude-opus-5-5-{suffix}") == M("claude-opus-5-5", suffix, True)

def test_alias_policy() -> None:
    assert n(" Claude-Opus-5-5-HIGH ", " LOW ") == M("Claude-Opus-5-5", "low", True)
    assert e(" CLAUDE-OPUS-5-5-HIGH ", {"claude-opus-5-5": object()}, ("low", "medium", "high"), True) == ("claude-opus-5-5", "high")
    assert n("alpha-high", known_models=("alpha", "alpha-high")) == M("alpha-high", None, False); assert e("bad model-high", {"bad model": object()}, ("low", "medium", "high"), True) is None
    assert e("ALPHA-HIGH", {"ALPHA": object(), "alpha-high": object()}, ("high",), True) is None; assert n("alpha", known_models={"alpha", "Alpha"}).canonical_model == "alpha" and n("ALPHA", known_models={"alpha", "Alpha"}).canonical_model == "Alpha"
    assert e("alpha-high", {"alpha": object(), "Alpha-High": object()}, ("high",), True) is None

@pytest.mark.parametrize("model,level", (("", None), ("   ", None), ("m", "ultra"), ("blocked -high", None), ("alpha\u200b-high", None), ("claude\ud800-high", None)))
def test_alias_invalid(model: str, level: str | None) -> None:
    with pytest.raises(ValueError): _ = n(model, level)
    with pytest.raises(ValueError): _ = n("m", "bad suffix", ("bad suffix",))
    with pytest.raises(ValueError): _ = n("m", "\u200b", ("\u200b",))

def test_redaction() -> None:
    secrets = "Bearer bearer.value Basic basic.value ya29.oauth 1//refresh sk-key AIzaGoogle refresh_token=refresh access_token:access client_secret=client api_key=api password=pwd secret=sec token=tok cookie=cookie user@example.com\x00\n"
    z = x(secrets + "x" * 300)
    assert len(z) <= 256 and len(x("x" * 300)) == 256
    assert z.count("<redacted>") >= 7
    assert all(value not in z for value in ("bearer.value", "ya29.", "1//", "@", "\x00", "\n"))
    for text in CASES: assert "<redacted>" in x(text) and "TOPSECRET" not in x(text) and "SECRET42" not in x(text)
    assert all("TOPSECRET42" not in x(text) for text in (r"pass\u005cu005cu0077ord=TOPSECRET42", r'Bearer \\"TOPSECRET42\\"', r'{\\"access_token\\":\\"TOPSECRET42\\"}'))
    assert all("TOPSECRET42" not in x(text) for text in ("https://TOPSECRET42" + "%61" * 21839 + "@example.com", "%20" * 21839 + "https://TOPSECRET42@example.com", "%20" * 400000 + "https://TOPSECRET42@example.com", "https://TOPSECRET42" + "%61" * 400000 + "@example.com"))
    assert x("a" * 4194305) == "<redacted>"
    assert x(r"\uD800").encode("utf-8") == b" " and x("\ud800").encode("utf-8") == b" "

def test_redaction_pathological_url_is_linear() -> None:
    started = time.perf_counter(); assert "TOPSECRET42" not in x("http://" + ":a " * 21840)
    assert time.perf_counter() - started < 2.0

@pytest.mark.parametrize("case", (
    (401, "anything", *AF), (403, "OAuth rejected", *AF),
    (503, "token refresh failed", *AF), (503, "token \x1b[31mrefresh\x1b[0m failed", *AF), (503, r"token \033[31mrefresh\033[0m failed", *AF), (503, r"token\u0020refresh\u0020failed", *AF), (503, "token ref\x00resh\nfailed", *AF), (429, "quota exceeded", *LB),
    (503, "quota exceeded", *LB), (503, "SSL_ERROR_SYSCALL", *TS),
    (429, "busy", *CE), (503, Q, *CE),
    (400, "model_capacity_exhausted", *CE), (0, "HTTP 401: invalid auth", *AF), (0, "HTTP 403: OAuth rejected", *AF), (0, "\n403 OAuth rejected", *AF),
    (403, "max_tokens exceeded", *FF), (403, "API key not valid", *AF), (0, "retry after: 401 seconds", *FF), (0, "retry after: 429 seconds", *FF), (0, "Error: 503 Service Unavailable", *CE), (0, '{"status": 429}', *CE), (400, "invalid token count: context window exceeded", *FF), (503, "x" * 1048576 + " token refresh failed " + "y" * 65537, *AF), (503, "%20" * 400000 + "token refresh failed", *AF), (503, "token &#155;31mrefresh&#155;0m failed", *AF), (503, "token %C2%9B31mrefresh%C2%9B0m failed", *AF),
))
def test_failures(case: tuple[int, str, F, bool]) -> None:
    status, reason, category, retryable = case; z = c(status, reason)
    assert (z.category, z.retryable) == (category, retryable)

CASES = (f'{{"access_token":"{Z}"}}', rf'{{\"access_token\":\"{Z}\"}}', f'{{"cookie":["sid={Z}"]}}', f"pass\u200bword={Z}", f"pass\u0301word={Z}", f"pass\x1b[31mword={Z}", f"Cookie: sid={Z}", f"pass\\u005cu0077ord={Z}", f"password={Z} horse", f"pass\x00word={Z}", f'Bearer "{Z}"', rf'Bearer \"{Z}\"', f"Authorization: Digest {Z}", f"eyJaaaa.eyJbbbb.{Z}", f"AWS_SECRET_ACCESS_KEY={Z}", f"password\\x3d{Z}", f"line1\\nBearer {Z}", f"https://:{Z}@localhost:8080", f"https://alice:{Z}" + "A" * 70000 + "@example.com", f"pass\x9b31mword={Z}", f"pass\\u0000word={Z}", "pass" + r"\u005c" + "u005c" * 7 + f"u0077ord={Z}", "pass" + r"\134" + "134" * 7 + f"167ord={Z}", f"pass\x1b]0;x\x07word={Z}", f"pass\x1bP\x1b\\word={Z}", f"Authorization%3A%20Bearer%20{Z}", f"pass\\bword={Z}", f"pass\\167ord={Z}", f"pass&#119;ord={Z}", "password" + "%25" * 8 + f"3D{Z}", f"https://ali%40ce:{Z}@localhost", f"invalid token {Z}", f"--password {Z}", f"-p {Z}", f"upstream https://ali%2Fce:{Z}@localhost", f"pass\\033[31mword={Z}", f"pass%1B[31mword={Z}", f"pass&#27;[31mword={Z}", " " * 65536 + f"Bearer {Z}", "ghp_" + "A" * 36, f"xoxb-{Z}", f"-----BEGIN RSA PRIVATE KEY----- {Z}", "user@пример.рф", f"pass%u0077ord={Z}", f"pass\\U00000077ord={Z}", f"private_key={Z}", "password=TOP\u2028SECRET42", f"https://{Z}@localhost/p", f"https://ali%20ce:{Z}@localhost", "--password TOP\nSECRET42", rf"password\={Z}", rf"pass\%u0077ord={Z}", f"<password>{Z}</password>", f"password&equals;{Z}", rf"password%3\D{Z}", rf"password&\equals;{Z}", "password" + "&amp;" * 8 + f"equals;{Z}", "password&" + "amp;" * 8 + f"equals;{Z}", rf"password&\u005cequals;{Z}", rf"https:\/\/alice:{Z}@localhost", f"Bearer b'{Z}'", f'["cli", "--password", "{Z}"]', f"https://{Z}" + B8 + "@example.com", f"pass%C2%9B31mword={Z}", f"pass&#155;31mword={Z}", rf"pass\23331mword={Z}", f"pass%1B]0;x%C2%9Cword={Z}", f"sk-\ud800proj-{Z}", f"https\ud800://alice:{Z}@localhost", f"--pass\ud800word {Z}")

def test_retry_filter() -> None:
    assert t(P) is True and t(P + "; HTTP 429 Too Many Requests") is True
    blocked = (P + " quota exceeded", P + " token refresh failed", P + " TLS handshake timeout", P + " HTTP 401 Unauthorized", P + " HTTP 403 Forbidden", "connection reset: Bad Request", "HTTP/1.1 405 Method Not Allowed; connection reset", P + "; HTTP 440 Login Time-out", P + "; HTTP 498 Invalid Token", P + "; HTTP 499", "connection reset: token\x00refresh failed", "A" * 4096 + P + "; token refresh failed", P + " " + "A" * 4096 + " token refresh failed", "connection reset; HTTP\x01403", 'connection reset; {"status":401}', "connection reset; status_code=404", P + "; API key not valid", "connection reset; token \x1b[31mrefresh\x1b[0m failed", "connection reset; HTTP 4\u200b03 Forbidden", r"connection reset; HTTP\u0020403 Forbidden")
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
    assert h(n("alpha-high", known_models=("alpha", "alpha-high")), ("alpha",), 1.0, 10.0) == S("alpha-high", True, H.READY, ()); assert h("alpha", ("alpha-high",), 1.0, 10.0) == S("alpha", True, H.READY, ()); assert h(n("alpha-high"), ("alpha-high",), 1.0, 10.0).status_reason is H.LIMIT_BLOCKED; assert h(n("alpha-high", known_models=("alpha", "alpha-high")), ("alpha-high-high",), 1.0, 10.0).status_reason is H.READY; assert h(n("claude-opus-5-5-high"), ("claude-opus-5-5-high",), 1.0, 10.0).status_reason is H.LIMIT_BLOCKED; assert h("alpha-high", ("alpha-low",), 1.0, 10.0) == h(n("alpha-high"), ("alpha-low",), 1.0, 10.0); assert h(n("m", "high"), ("m-high",), 1.0, 10.0).status_reason is H.LIMIT_BLOCKED

@pytest.mark.parametrize("age,limit", ((float("nan"), 1.0), (float("inf"), 1.0), (1.0, float("inf")), (1.0, -1.0)))
def test_health_invalid(age: float, limit: float) -> None:
    with pytest.raises(ValueError): _ = h("model", (), age, limit)
    with pytest.raises(ValueError): _ = h(M("blocked\u200b", None, False), ("blocked",), 0.0, 1.0)
    with pytest.raises(ValueError): _ = h(M("blocked\ud800", None, False), ("blocked",), 0.0, 1.0)

def test_env_drift() -> None:
    assert "1500" in V and "300" in V
    assert v({"A": "1", "TIMEOUT": "1500"}, {"A": "1", "TIMEOUT": "300"}, ("TIMEOUT", "A")) == ("TIMEOUT",); assert v({"A": "1"}, {"A": "2"}, ("A", "A", " ")) == ("A",) and h("m", (), 0.0, 5.0, (" ",)).available is True

@pytest.mark.parametrize("config", (C(total_budget_s=0.0), C(reserve_s=-0.001), C(reserve_s=90.0), C(min_attempt_budget_s=0.0), C(max_attempts=0), C(max_attempts=10**1000), C(idle_timeout_s=0.0), C(total_budget_s=float("inf")), C(reserve_s=float("nan")), C(max_attempts=1.5)))  # type: ignore[arg-type]
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
    assert a(C(1.0009999999996, 0.0, 1.0, 1, 30.0), 0, 0.0) == A(True, 1.0, R.BUDGET_OK)
    assert a(C(5.29, 1.0, 4.29, 1, 30.0), 0, 0.0) == A(True, 4.29, R.BUDGET_OK)
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
    assert d(1.5e308, 1.5e308, 1.0, 2.0) == 1.5e308 + 1.0
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
    surrogate = k("x\ud800<!-- КАНОН-КОНЕЦ -->")
    assert surrogate.has_canon_end_marker is True and surrogate.byte_length == len("x?<!-- КАНОН-КОНЕЦ -->".encode())

def test_frozen_result() -> None:
    assert c(403, U).category is F.AUTH_REFRESH_EXHAUSTED
    z = n("m")
    with pytest.raises(FrozenInstanceError): setattr(z, "canonical_model", "changed")  # noqa: B010
    assert (ep := __import__("core.effort_policy", fromlist=["*"])) and ep.clamp_effort_downward("high", ("low", "high"), "low") == ("high", False) and ep.clamp_effort_downward("medium", ("low", "high"), "low") == ("low", True) and ep.clamp_effort_downward("unknown", ("low", "high"), "low") == ("low", True) and (spec := ep.ModelEffortSpec.from_catalog_entry({"efforts": ["LOW", "high", "bad"], "default_effort": "HIGH"})) == ep.ModelEffortSpec(("low", "high"), "high") and spec.pinned_to("medium") == ep.ModelEffortSpec(("low",), "low") and ep.resolve_model_effort_fields("m", {"m": spec}) == ep.ModelEffortCardFields("high", ("low", "high")) and ep.resolve_model_effort_fields("x", {}) is None and ep.catalog_effort_specs({"m": {"efforts": ["low", "high"], "default_effort": "high"}, "n": {}}, {"m-high": ("m", "high"), "n-high": ("n", "high")}) == {"m": spec, "m-high": ep.ModelEffortSpec(("high",), "high")} and ep.resolve_passthrough_effort("medium", None, spec, enabled=True) == ep.EffortResolution("low", True, "medium") and ep.resolve_passthrough_effort(None, "high", spec, enabled=True) == ep.EffortResolution("high", True) and ep.resolve_passthrough_effort("LOW", None, spec, enabled=True) == ep.EffortResolution("low", True) and ep.resolve_passthrough_effort("high", None, spec, enabled=True) == ep.EffortResolution() and ep.resolve_passthrough_effort(None, "high", spec, enabled=False) == ep.EffortResolution("high", True) and ep.resolve_passthrough_effort("low", "high", spec, enabled=False) == ep.EffortResolution() and ep.sanitize_effort_for_log("a\x00b", 2) == "ab" and ep.describe_clamp("effort", "high", "low", "model", 8) == "clamp effort 'high' -> 'low' for model model" and isinstance(pytest.raises(ValueError, W, 1.0, 2.0, attempt_budget_s=0.0).value, ValueError) and isinstance(pytest.raises(ValueError, W, 1.0, 2.0, attempt_budget_s=float("nan")).value, ValueError) and W(5.0, 20.0, clock=iter((10.0, 11.0)).__next__).expired is False and W(5.0, 20.0, clock=iter((10.0, 16.0)).__next__).expired is True and W(5.0, 20.0, clock=iter((10.0, 16.0)).__next__).touch() == 15.0 and (rp := __import__("core.route_health_policy", fromlist=["*"])) and rp._decode_escape(rp._ESCAPE_TOKEN_RE.match(r"\u0009")) == " " and rp._decode_escape(rp._ESCAPE_TOKEN_RE.match(r"\uD800")) == "" and rp._decode_pct(rp._PCT_RUN_RE.match("%00")) == "" and rp._normalize_diagnostic_text("abc", max_len=10, fail_closed=False) == "abc" and rp._is_auth_failure(0, "HTTP 403: plain") is False and rp._is_auth_failure(200, "http 403: oauth") is False and rp._is_auth_failure(0, "http 403: oauth refresh") is True and rp._route_targets(M("m", "high", False)) == ("m", frozenset(("m", "m-high"))) and isinstance(pytest.raises(ValueError, h, M("m", "bad effort", False), (), 0.0, 1.0).value, ValueError) and isinstance(pytest.raises(ValueError, k, "x", "").value, ValueError) and (sr := __import__("core.stream_interruption_recovery", fromlist=["*"])) and t("connection reset; %2541") is False and t("ordinary") is False and sr.settle_error("", "old", "ERROR") == "old" and sr.settle_error("new", "old", "ERROR") == "new" and (tail := sr.InterruptionTailState()) and tail.note_error_record("ERROR_MESSAGE", {"content": P}, 2) is None and tail.note_planner_record({"content": "done", "status": "DONE"}, 3) is None and sr.trusted_final_text("", "error", tail) == "done" and sr.tail_turn_facts(tail) == {"completion_done_without_tools": True, "last_completion_seq": 3, "last_error_seq": 2, "drain_complete": True, "had_transient_error": True} and sr.resolve_done_turn_outcome(rc=0, result_error="", result_status="DONE", final_text="done", emitted_text="done").reason == "clean_done" and sr.resolve_done_turn_outcome(rc=1, result_error=P, result_status="ERROR", final_text="done", emitted_text="", completion_done_without_tools=True, last_completion_seq=3, last_error_seq=2, drain_complete=True).state == "done" and sr.resolve_done_turn_outcome(rc=1, result_error=P, result_status="ERROR", final_text="done", emitted_text="", completion_done_without_tools=True, last_completion_seq=3, last_error_seq=2, drain_complete=True).self_healed is True and sr.resolve_done_turn_outcome(rc=1, result_error="fatal", result_status="ERROR", final_text="", emitted_text="", drain_complete=True).reason == "non_transient_result_error" and r(error_text=P, delivered=False, unknown=True).can_retry is False and sr.evaluate_graceful_interruption(error_text=P, delivered_content=True).reason == "graceful_partial_close" and sr.evaluate_graceful_interruption(error_text=P, delivered_content=True, delivered_tool_calls=True).reason == "graceful_blocked"  # pyright: ignore[reportAny]
