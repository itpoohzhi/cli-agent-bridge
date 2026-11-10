# ruff: noqa: I001
from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.activity_window import ActivityWindow
from core.effort_policy import resolve_alias_effort
from core.route_health_policy import AttemptDecision, CanonDigestResult, FailureCategory, HealthReason, NormalizedModelRoute, RetryBudgetConfig, RetryReason, RouteHealthStatus, advance_sliding_deadline, classify_provider_failure, compute_attempt_decision, detect_effective_env_drift, evaluate_route_health, inspect_canon_payload, normalize_model_route, redact_diagnostic_text, validate_retry_config  # fmt: skip  # noqa: E501,I001
from core.stream_interruption_recovery import evaluate_stream_retry_eligibility, is_transient_stream_interruption  # fmt: skip  # noqa: E501,I001


INCIDENT_AUTH_SNAPSHOT = "403 OAuth refresh rejected: token refresh failed"
AGY_RETRY_SNAPSHOT = "per_attempt_upper duration_s=18.288681"
RUNTIME_DRIFT_SNAPSHOT = "configured=1500 effective=300"
CAPACITY_401_SNAPSHOT = "capacity unavailable; retry after 401 seconds"


@pytest.mark.parametrize("suffix", ("low", "medium", "high"))
def test_alias_suffix_matrix(suffix: str) -> None:
    route = normalize_model_route(f"claude-opus-5-5-{suffix}")
    assert route == NormalizedModelRoute("claude-opus-5-5", suffix, True)


def test_alias_normalization_and_live_effort_policy() -> None:
    route = normalize_model_route(" Claude-Opus-5-5-HIGH ", " LOW "); assert route == NormalizedModelRoute("Claude-Opus-5-5", "low", True)  # fmt: skip  # noqa: E501,E702
    catalogue = {"claude-opus-5-5": object()}
    assert resolve_alias_effort(
        " CLAUDE-OPUS-5-5-HIGH ", catalogue, ("low", "medium", "high"), True
    ) == ("claude-opus-5-5", "high")


@pytest.mark.parametrize("model,effort", (("", None), ("   ", None), ("m", "ultra")))
def test_alias_rejects_invalid_input(model: str, effort: str | None) -> None:
    with pytest.raises(ValueError):
        _ = normalize_model_route(model, effort)


def test_redaction_masks_all_secrets_controls_and_truncates() -> None:
    secrets = (
        "Bearer bearer.value Basic basic.value ya29.oauth 1//refresh sk-key AIzaGoogle "
        "refresh_token=refresh access_token:access client_secret=client api_key=api "
        "password=pwd secret=sec token=tok cookie=cookie user@example.com\x00\n"
    )
    result = redact_diagnostic_text(secrets + "x" * 300)
    assert len(result) <= 256 and len(redact_diagnostic_text("x" * 300)) == 256
    assert result.count("<redacted>") >= 7
    assert all(value not in result for value in ("bearer.value", "ya29.", "1//", "@"))
    assert "\x00" not in result and "\n" not in result
    assert "TOPSECRET" not in redact_diagnostic_text('{"access_token":"TOPSECRET"}')
    assert "secret2" not in redact_diagnostic_text("Cookie: a=1; sid=secret2")
    assert all(value not in redact_diagnostic_text(r'{"access_token":"prefix\"LEAK"}') for value in ("prefix", "LEAK"))  # fmt: skip  # noqa: E501
    edge_cases = (r'{"pass\u0077ord":"TOPSECRET42"}', '{"password":"TOPSECRET42', "id_token=TOPSECRET42", "password=correct horse", "password\x00=TOPSECRET42", "password=TOP\x00SECRET42", 'Bearer "TOPSECRET42"')  # fmt: skip  # noqa: E501
    assert all("TOPSECRET42" not in redact_diagnostic_text(text) for text in edge_cases)


@pytest.mark.parametrize(
    "case",
    (
        (401, "anything", FailureCategory.AUTH_REFRESH_EXHAUSTED, False),
        (403, "OAuth rejected", FailureCategory.AUTH_REFRESH_EXHAUSTED, False),
        (503, "token refresh failed", FailureCategory.AUTH_REFRESH_EXHAUSTED, False),
        (429, "quota exceeded", FailureCategory.LIMIT_BLOCKED, False),
        (503, "quota exceeded", FailureCategory.LIMIT_BLOCKED, False),
        (503, "SSL_ERROR_SYSCALL", FailureCategory.UPSTREAM_TLS_STALL, False),
        (429, "busy", FailureCategory.CAPACITY_EXHAUSTED, True),
        (503, CAPACITY_401_SNAPSHOT, FailureCategory.CAPACITY_EXHAUSTED, True),
        (400, "model_capacity_exhausted", FailureCategory.CAPACITY_EXHAUSTED, True),
        (0, "HTTP 401: invalid auth", FailureCategory.AUTH_REFRESH_EXHAUSTED, False),
        (403, "max_tokens exceeded", FailureCategory.FATAL_REQUEST_ERROR, False),
    ),
)
def test_failure_classification_matrix(
    case: tuple[int, str, FailureCategory, bool],
) -> None:
    status, reason, category, retryable = case
    result = classify_provider_failure(status, reason)
    assert (result.category, result.retryable) == (category, retryable)


def test_transient_recovery_excludes_non_retryable_failures() -> None:
    assert is_transient_stream_interruption("connection reset") is True
    assert is_transient_stream_interruption("connection reset quota exceeded") is False
    assert is_transient_stream_interruption("connection reset token refresh failed") is False  # fmt: skip  # noqa: E501
    assert is_transient_stream_interruption("connection reset TLS handshake timeout") is False  # fmt: skip  # noqa: E501
    auth = "connection reset HTTP 401 Unauthorized"
    assert is_transient_stream_interruption(auth) is False
    retry = evaluate_stream_retry_eligibility(error_text=auth, delivered=False)
    assert retry.can_retry is False
    allowed = evaluate_stream_retry_eligibility(error_text="connection reset", delivered=False)  # fmt: skip  # noqa: E501
    assert allowed.can_retry is True and allowed.attempt_budget_s > 0.0
    exhausted = evaluate_stream_retry_eligibility(error_text="connection reset", delivered=False, elapsed_s=86.0)  # fmt: skip  # noqa: E501
    assert exhausted.can_retry is False and exhausted.attempt_budget_s == 0.0
    invalid = ({"max_attempts": 0}, {"elapsed_s": float("nan")}, {"elapsed_s": -1.0})  # fmt: skip  # noqa: E501
    assert all(not evaluate_stream_retry_eligibility(error_text="connection reset", delivered=False, **kw).can_retry for kw in invalid)  # fmt: skip  # noqa: E501
    stricter = evaluate_stream_retry_eligibility(error_text="connection reset", delivered=False, attempt=1, max_attempts=3, budget_config=RetryBudgetConfig(max_attempts=1))  # fmt: skip  # noqa: E501
    assert stricter.can_retry is False and stricter.keep_hot_session is True


@pytest.mark.parametrize("case", ((0.0, 0.0, (), True, HealthReason.READY), (5.001, 5.0, (), False, HealthReason.STALE_HEALTH_PROBE), (-0.001, 5.0, (), False, HealthReason.STALE_HEALTH_PROBE), (1.0, 5.0, ("Z", "A"), False, HealthReason.ENV_DRIFT_DETECTED)))  # fmt: skip  # noqa: E501
def test_route_health_boundaries(
    case: tuple[float, float, tuple[str, ...], bool, HealthReason],
) -> None:
    age, limit, drift, available, reason = case
    result = evaluate_route_health("model", (), age, limit, drift)
    assert result == RouteHealthStatus("model", available, reason, tuple(sorted(drift)))


def test_route_health_block_precedes_stale_and_normalizes_alias() -> None:
    result = evaluate_route_health(
        "Claude-Opus-5-5-High", ("claude-opus-5-5",), 1.0, 10.0
    )
    assert result == RouteHealthStatus(
        "Claude-Opus-5-5", False, HealthReason.LIMIT_BLOCKED, ()
    )


@pytest.mark.parametrize(
    "age,limit",
    ((float("nan"), 1.0), (float("inf"), 1.0), (1.0, float("inf")), (1.0, -1.0)),
)
def test_route_health_rejects_invalid_numbers(age: float, limit: float) -> None:
    with pytest.raises(ValueError):
        _ = evaluate_route_health("model", (), age, limit)


def test_env_drift_and_embedded_runtime_snapshot() -> None:
    assert "1500" in RUNTIME_DRIFT_SNAPSHOT and "300" in RUNTIME_DRIFT_SNAPSHOT
    drift = detect_effective_env_drift(
        {"A": "1", "TIMEOUT": "1500"}, {"A": "1", "TIMEOUT": "300"}, ("TIMEOUT", "A")
    )
    assert drift == ("TIMEOUT",)


@pytest.mark.parametrize(
    "config",
    (
        RetryBudgetConfig(total_budget_s=0.0),
        RetryBudgetConfig(reserve_s=-0.001),
        RetryBudgetConfig(reserve_s=90.0),
        RetryBudgetConfig(min_attempt_budget_s=0.0),
        RetryBudgetConfig(max_attempts=0),
        RetryBudgetConfig(idle_timeout_s=0.0),
        RetryBudgetConfig(total_budget_s=float("inf")),
        RetryBudgetConfig(reserve_s=float("nan")),
        RetryBudgetConfig(max_attempts=1.5),
    ),
)
def test_retry_config_rejects_invalid_fields(config: RetryBudgetConfig) -> None:
    with pytest.raises(ValueError):
        _ = validate_retry_config(config)


@pytest.mark.parametrize(
    "category",
    (
        FailureCategory.AUTH_REFRESH_EXHAUSTED,
        FailureCategory.LIMIT_BLOCKED,
        FailureCategory.UPSTREAM_TLS_STALL,
        FailureCategory.FATAL_REQUEST_ERROR,
        "AUTH",
        "UNKNOWN",
    ),
)
def test_retry_decision_is_fail_closed(category: str) -> None:
    expected = AttemptDecision(False, 0.0, RetryReason.NON_RETRYABLE_CATEGORY)
    assert compute_attempt_decision(RetryBudgetConfig(), 0, 0.0, category) == expected


def test_retry_budget_rounds_down_and_honors_boundaries() -> None:
    config = RetryBudgetConfig(109.732084, 0.0, 4.0, 6, 30.0)
    decision = compute_attempt_decision(config, 0, 0.0)
    assert decision == AttemptDecision(True, 18.288, RetryReason.BUDGET_OK)
    assert decision.attempt_budget_s <= float(AGY_RETRY_SNAPSHOT.rsplit("=", 1)[1])
    assert (
        compute_attempt_decision(config, 6, 0.0).reason
        is RetryReason.MAX_ATTEMPTS_REACHED
    )
    tight = RetryBudgetConfig(1.0009, 0.0, 1.0005, 1, 30.0)
    decision = compute_attempt_decision(tight, 0, 0.0)
    assert decision.reason is RetryReason.BUDGET_EXHAUSTED
    assert compute_attempt_decision(RetryBudgetConfig(), 0, 1e308).reason is RetryReason.BUDGET_EXHAUSTED  # fmt: skip  # noqa: E501


@pytest.mark.parametrize("index,elapsed", ((-1, 0.0), (2.5, 0.0), (True, 0.0), (0, -0.001), (0, float("inf"))))  # fmt: skip  # noqa: E501
def test_retry_decision_rejects_invalid_inputs(index: object, elapsed: float) -> None:
    with pytest.raises(ValueError):
        _ = compute_attempt_decision(RetryBudgetConfig(), index, elapsed)


def test_sliding_deadline_and_live_activity_window() -> None:
    assert advance_sliding_deadline(18.0, 0.0, 5.0, 20.0) == 20.0
    ticks = iter((10.0, 12.0))
    window = ActivityWindow(5.0, 20.0, clock=lambda: next(ticks))
    assert window.idle_deadline == 15.0
    assert window.touch() == 17.0
    capped = ActivityWindow(20.0, 30.0, attempt_budget_s=12.0, clock=lambda: 10.0)
    assert capped.safety_deadline == 22.0 and capped.idle_deadline == 22.0
    with pytest.raises(ValueError):
        _ = advance_sliding_deadline(1e308, 0.0, 1e308, 1e308)


@pytest.mark.parametrize(
    "args",
    (
        (float("nan"), 0.0, 1.0, 1.0),
        (0.0, float("inf"), 1.0, 1.0),
        (0.0, 0.0, 0.0, 1.0),
        (0.0, 0.0, 1.0, 0.0),
        (0.0, 1.0, 1.0, 1.0),
    ),
)
def test_sliding_deadline_rejects_invalid_parameters(args: tuple[float, ...]) -> None:
    with pytest.raises(ValueError):
        _ = advance_sliding_deadline(*args)


def test_canon_digest_requires_tail_marker_and_tracks_changes() -> None:
    text = "Я<!-- КАНОН-КОНЕЦ -->\n"
    first = inspect_canon_payload(text)
    same = inspect_canon_payload(text, previous_sha256=first.sha256_hex)
    changed = inspect_canon_payload(text + "x", previous_sha256=first.sha256_hex)
    middle = inspect_canon_payload("<!-- КАНОН-КОНЕЦ -->\ntruncated")
    assert first == CanonDigestResult(True, first.sha256_hex, len(text.encode()), False)
    assert same.unchanged is True
    assert changed.unchanged is False and changed.has_canon_end_marker is False
    assert middle.has_canon_end_marker is False


def test_incident_snapshot_and_frozen_result() -> None:
    result = classify_provider_failure(403, INCIDENT_AUTH_SNAPSHOT); assert result.category is FailureCategory.AUTH_REFRESH_EXHAUSTED  # fmt: skip  # noqa: E501,E702
    route = normalize_model_route("m")
    with pytest.raises(FrozenInstanceError):
        setattr(route, "canonical_model", "changed")  # noqa: B010
