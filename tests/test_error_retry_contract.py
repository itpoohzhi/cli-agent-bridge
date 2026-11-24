from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.error_taxonomy import (  # noqa: E402
    classify_upstream_error,
    error_response,
    extract_upstream_error_meta,
    sanitize_error_text,
)
from core.replay_policy import (  # noqa: E402
    apply_budget_to_proof,
    build_replay_proof,
    calculate_retry_budget,
    parse_retry_budget,
    quota_failover_eligibility,
)
from core.route_attempts import (  # noqa: E402
    AttemptPhase,
    RouteAttemptRunner,
    RouteFailover,
    RouteRefusal,
)
from core.route_health_policy import RetryBudgetConfig  # noqa: E402


def test_quota_contract_preserves_phrase_and_headers_without_secret() -> None:
    result = classify_upstream_error(
        "Individual quota reached; token=top-secret; retry-after: 17",
        headers={"Retry-After": "12"},
        request_id="req_123",
    )
    status, payload, headers = error_response(result)
    assert status == 429
    assert payload["error"] == {
        "message": "Individual quota reached; token=[REDACTED]; retry-after: 17",
        "type": "quota_exhausted",
        "code": "QUOTA",
        "request_id": "req_123",
        "retry_after": 12,
    }
    assert headers == {"X-Request-Id": "req_123", "Retry-After": "12"}
    assert result.retryable is False


@pytest.mark.parametrize(
    ("facts", "expected"),
    [
        ((0, False, 0, "connect"), True),
        ((0, False, 0, "send_headers"), False),
        ((0, False, 0, "before_first_byte"), False),
        ((1, False, 0, "connect"), False),
        ((0, True, 0, "connect"), False),
        ((0, False, 1, "connect"), False),
        ((0, False, 0, "response_body"), False),
    ],
)
def test_replay_proof_truth_table(facts: tuple[object, ...], expected: bool) -> None:
    assert build_replay_proof(*facts).allow_retry is expected


def test_attempt_budget_is_bounded_and_invalid_sizing_revokes_proof() -> None:
    budget = calculate_retry_budget(90, 2, remaining_s=60, backoff_s=3)
    assert budget.attempts == 3
    assert budget.attempt_s is not None
    assert budget.attempt_s <= 90 / 3
    proof = build_replay_proof(0, False, 0, "connect")
    invalid = calculate_retry_budget(None, 2)
    assert apply_budget_to_proof(proof, invalid).allow_retry is False


@pytest.mark.parametrize("value", [None, "", "0", "3", "-1", "1.0", "oops"])
def test_invalid_or_zero_retry_header_is_fail_closed(value: object) -> None:
    assert parse_retry_budget(value) == 0


def test_quota_failover_is_default_off_and_requires_distinct_group() -> None:
    assert not quota_failover_eligibility("account-a", ["account-b"]).eligible
    assert not quota_failover_eligibility(
        "account-a", ["account-a", ""], opt_in_enabled=True
    ).eligible
    result = quota_failover_eligibility(
        "account-a", ["account-a", "account-b"], opt_in_enabled=True
    )
    assert (result.eligible, result.target_quota_group) == (True, "account-b")


@pytest.mark.parametrize(
    ("opt_in", "groups", "expected"),
    [(False, ("a", "b"), ["first"]), (True, ("a", "a"), ["first"]),
     (True, ("a", "b"), ["first", "second"])],
)
def test_working_router_applies_quota_group_opt_in(
    opt_in: bool, groups: tuple[str, str], expected: list[str]
) -> None:
    seen: list[str] = []
    lease = SimpleNamespace(finish=lambda *_: None, close=lambda: None)

    def execute(backend: str, attempt: Any) -> str:
        seen.append(backend)
        if backend == "first":
            attempt.advance(AttemptPhase.SENDING)
            attempt.advance(AttemptPhase.RESPONSE_HEADERS, 429)
            raise RouteRefusal(
                429,
                response_body=b'{"error":{"type":"quota_exhausted","message":"quota reached"}}',
            )
        return "ok"

    ports = SimpleNamespace(ready=lambda _: True, acquire=lambda *_: lease,
        execute=execute, retry_token=lambda: True, cancelled=lambda: False)
    failovers = {
        name: RouteFailover(frozenset({429}), quota_group=group,
            quota_failover_opt_in=opt_in if name == "first" else False)
        for name, group in zip(("first", "second"), groups, strict=True)
    }
    runner = RouteAttemptRunner(("first", "second"), ports,
        RetryBudgetConfig(), lambda: 0.0, failover_by_backend=failovers)
    if len(expected) == 1:
        with pytest.raises(RouteRefusal):
            runner.run()
    else:
        assert runner.run() == "ok"
    assert seen == expected


@pytest.mark.parametrize(
    ("message", "subtype"),
    [
        ("PI_AI_ERROR: interrupted", "unspecified"),
        ("interrupted: client_disconnect", "client_disconnect"),
        ("PI_AI_ERROR timeout", "timeout"),
        ("upstream_interrupted", "upstream_interrupted"),
    ],
)
def test_interrupted_is_terminal_with_causal_subtype(
    message: str, subtype: str
) -> None:
    result = classify_upstream_error(message)
    assert result.retryable is False
    assert result.cancellation_subtype == subtype


def test_transport_retry_requires_replay_proof() -> None:
    message = "socket premature EOF before response"
    assert not classify_upstream_error(message).retryable
    proof = build_replay_proof(0, False, 0, "before_first_byte", True)
    assert classify_upstream_error(message, replay_proof=proof).retryable


def test_authorization_bearer_value_is_fully_redacted() -> None:
    secret = "fake-secret-token"
    result = classify_upstream_error(f"failure Authorization: Bearer {secret}")
    assert result.message == "failure Authorization: Bearer [REDACTED]"
    assert secret not in result.error_body()["message"]


@pytest.mark.parametrize(
    ("raw", "safe"),
    [
        ('"api_key": "opaque123"', '"api_key": "[REDACTED]"'),
        ('"token": "secret456"', '"token": "[REDACTED]"'),
        ('"authorization": "Basic dXNlcjpwYXNz"', '"authorization": "Basic [REDACTED]"'),
        ("token=opaque-val", "token=[REDACTED]"),
        ("Authorization: Basic dXNlcjpwYXNz", "Authorization: Basic [REDACTED]"),
        ("Authorization: Bearer xyz", "Authorization: Bearer [REDACTED]"),
        ("access_token='opaque'", "access_token='[REDACTED]'"),
        ("x-api-key=opaque", "x-api-key=[REDACTED]"),
    ],
)
def test_secret_fields_keep_diagnostic_prefix(raw: str, safe: str) -> None:
    assert sanitize_error_text(raw) == safe


@pytest.mark.parametrize(
    ("out", "expected"),
    [
        ({"status_code": 429, "headers": {"Retry-After": "4"}}, (429, {"Retry-After": "4"})),
        ({"upstream_status_code": None, "status_code": 429,
          "upstream_headers": None, "headers": {"Retry-After": "4"}},
         (429, {"Retry-After": "4"})),
        ({"upstream_status_code": 503, "status_code": 429,
          "upstream_headers": {"X": "canonical"}, "headers": {"X": "legacy"}},
         (503, {"X": "canonical"})),
    ],
)
def test_extract_upstream_error_meta_fallbacks(
    out: dict[str, object], expected: tuple[object, object]
) -> None:
    assert extract_upstream_error_meta(out) == expected


def test_structured_429_preserves_retry_after_without_quota_wording() -> None:
    result = classify_upstream_error(
        "request rejected", status_code=429, headers={"retry-after": "19"}
    )
    status, _, headers = error_response(result)
    assert (status, headers["Retry-After"]) == (429, "19")


def test_non_quota_error_keeps_legacy_agy_error_shape() -> None:
    result = classify_upstream_error("upstream rejected the request")
    assert (result.http_status, result.type, result.code) == (502, "agy_error", 502)


def test_interrupted_adds_subtype_without_changing_legacy_type() -> None:
    result = classify_upstream_error("PI_AI_ERROR: client_disconnect")
    assert (result.http_status, result.type, result.code) == (502, "agy_error", 502)
    assert result.cancellation_subtype == "client_disconnect"


def test_status_only_429_and_quota_429_have_distinct_failover_contracts() -> None:
    def run(body: bytes, opt_in: bool, groups: tuple[str, str]) -> list[str]:
        seen: list[str] = []
        lease = SimpleNamespace(finish=lambda *_: None, close=lambda: None)
        def execute(backend: str, attempt: Any) -> str:
            seen.append(backend)
            if backend == "first":
                attempt.advance(AttemptPhase.SENDING)
                attempt.advance(AttemptPhase.RESPONSE_HEADERS, 429)
                raise RouteRefusal(429, response_body=body)
            return "ok"
        ports = SimpleNamespace(ready=lambda _: True, acquire=lambda *_: lease,
            execute=execute, retry_token=lambda: True, cancelled=lambda: False)
        failovers = {name: RouteFailover(frozenset({429}), quota_group=group,
            quota_failover_opt_in=opt_in if name == "first" else False)
            for name, group in zip(("first", "second"), groups, strict=True)}
        runner = RouteAttemptRunner(("first", "second"), ports, RetryBudgetConfig(),
            lambda: 0.0, failover_by_backend=failovers)
        try:
            runner.run()
        except RouteRefusal:
            pass
        return seen

    assert run(b"", False, ("", "")) == ["first", "second"]
    quota = b'{"error":{"type":"quota_exhausted","message":"quota reached"}}'
    assert run(quota, False, ("a", "b")) == ["first"]
    assert run(quota, True, ("a", "a")) == ["first"]
    assert run(quota, True, ("", "b")) == ["first"]
    assert run(quota, True, ("a", "b")) == ["first", "second"]


def test_bare_secret_literals_redacted_without_stop_iteration() -> None:
    raw = (
        "upstream failed sk-proj1234567890 ghp_abcdef1234567890 "
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.sig12345678"
    )
    msg = classify_upstream_error(raw).message
    assert "sk-proj1234567890" not in msg
    assert "ghp_abcdef1234567890" not in msg
    assert "eyJhbGciOiJIUzI1NiJ9" not in msg
    assert msg.count("[REDACTED]") == 3


def test_quoted_secrets_with_escaped_and_nested_quotes_and_spaces() -> None:
    raw = (
        '{"password": "a\'b", "secret": "ab\\"cd"} '
        'password="my secret phrase" authorization="Basic dXNlcjpwYXNz"'
    )
    msg = classify_upstream_error(raw).message
    for leak in ("a'b", 'ab\\"cd', "my secret phrase", "dXNlcjpwYXNz"):
        assert leak not in msg
    assert "Basic [REDACTED]" in msg
    assert msg.count("[REDACTED]") == 4


def test_escaped_nested_json_and_truncated_unclosed_quote_redacted() -> None:
    for raw, leak in (
        (r'{\"password\": \"hunter2\"}', "hunter2"),
        (r'api_key=\"abc123opaque\"', "abc123opaque"),
        ('"token": "truncated_secret_value', "truncated_secret_value"),
        (r"password=\hunter2", "hunter2"),
        (r"password=abc\def", "def"),
    ):
        msg = classify_upstream_error(raw).message
        assert leak not in msg
        assert "[REDACTED]" in msg


def test_quota_body_with_non_429_status_still_enforces_opt_in() -> None:
    lease = SimpleNamespace(handle=object(), finish=lambda *_: None, close=lambda: None)
    quota_body = b'{"error":{"type":"resource_exhausted","message":"quota exceeded"}}'

    def run(opt_in: bool, groups: tuple[str, str]) -> list[str]:
        seen: list[str] = []

        def execute(backend: str, attempt: Any) -> str:
            seen.append(backend)
            if backend == "first":
                attempt.advance(AttemptPhase.SENDING)
                attempt.advance(AttemptPhase.RESPONSE_HEADERS, 503)
                raise RouteRefusal(503, response_body=quota_body)
            return "ok"

        ports = SimpleNamespace(
            ready=lambda _: True, acquire=lambda *_: lease,
            execute=execute, retry_token=lambda: True, cancelled=lambda: False,
        )
        failovers = {
            name: RouteFailover(frozenset({503}), quota_group=group,
                                quota_failover_opt_in=opt_in if name == "first" else False)
            for name, group in zip(("first", "second"), groups, strict=True)
        }
        runner = RouteAttemptRunner(("first", "second"), ports, RetryBudgetConfig(),
                                    lambda: 0.0, failover_by_backend=failovers)
        try:
            runner.run()
        except RouteRefusal:
            pass
        return seen

    assert run(False, ("a", "b")) == ["first"]
    assert run(True, ("a", "a")) == ["first"]
    assert run(True, ("a", "b")) == ["first", "second"]
