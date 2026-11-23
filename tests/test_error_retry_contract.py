from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.error_taxonomy import classify_upstream_error, error_response  # noqa: E402
from core.replay_policy import (  # noqa: E402
    apply_budget_to_proof,
    build_replay_proof,
    calculate_retry_budget,
    parse_retry_budget,
    quota_failover_eligibility,
)


def test_quota_contract_preserves_phrase_and_headers_without_secret() -> None:
    result = classify_upstream_error(
        "Individual quota reached; token=top-secret; retry-after: 17",
        headers={"Retry-After": "12"},
        request_id="req_123",
    )
    status, payload, headers = error_response(result)
    assert status == 429
    assert payload["error"] == {
        "message": "Individual quota reached; [REDACTED]; retry-after: 17",
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
        ((0, False, 0, "send_headers"), True),
        ((0, False, 0, "before_first_byte"), True),
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
    proof = build_replay_proof(0, False, 0, "before_first_byte")
    assert classify_upstream_error(message, replay_proof=proof).retryable


def test_non_quota_error_keeps_legacy_agy_error_shape() -> None:
    result = classify_upstream_error("upstream rejected the request")
    assert (result.http_status, result.type, result.code) == (502, "agy_error", 502)


def test_interrupted_adds_subtype_without_changing_legacy_type() -> None:
    result = classify_upstream_error("PI_AI_ERROR: client_disconnect")
    assert (result.http_status, result.type, result.code) == (502, "agy_error", 502)
    assert result.cancellation_subtype == "client_disconnect"
