from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.route_health_policy import (
    AttemptDecision,
    CanonDigestResult,
    FailureClassification,
    NormalizedModelRoute,
    RetryBudgetConfig,
    RouteHealthStatus,
    advance_sliding_deadline,
    classify_provider_failure,
    compute_attempt_decision,
    detect_effective_env_drift,
    evaluate_route_health,
    inspect_canon_payload,
    normalize_model_route,
    redact_diagnostic_text,
    validate_retry_config,
)


SNAPSHOTS = Path(
    "/tmp/cel-runs/fix-auth-and-transport-latency/analysis/auth-and-transport"
)
NON_RETRY = AttemptDecision(False, 0.0, "NON_RETRYABLE_CATEGORY")
MAXED = AttemptDecision(False, 0.0, "MAX_ATTEMPTS_REACHED")


@pytest.mark.parametrize("suffix", ("low", "medium", "high"))
def test_alias_suffix_matrix(suffix: str) -> None:
    route = normalize_model_route(f"claude-opus-5-5-{suffix}")
    assert route == NormalizedModelRoute("claude-opus-5-5", suffix, True)


def test_alias_explicit_effort_and_plain_model() -> None:
    aliased = normalize_model_route(" claude-opus-5-5-high ", "low")
    plain = normalize_model_route(" claude-opus-5-5 ", "medium")
    suffix_only = normalize_model_route("-high")
    assert aliased == NormalizedModelRoute("claude-opus-5-5", "low", True)
    assert plain == NormalizedModelRoute("claude-opus-5-5", "medium", False)
    assert suffix_only == NormalizedModelRoute("-high", None, False)


@pytest.mark.parametrize("model,effort", (("", None), ("   ", None), ("m", "ultra")))
def test_alias_rejects_invalid_input(model: str, effort: str | None) -> None:
    with pytest.raises(ValueError):
        normalize_model_route(model, effort)


def test_redaction_masks_secrets_email_controls_and_truncates() -> None:
    raw = "Bearer abc.DEF-123 sk-secret AIzaAbCdEf123 user@example.com\n" + "x" * 300
    result = redact_diagnostic_text(raw)
    assert result == "<redacted> <redacted> <redacted> <redacted> " + "x" * 212
    assert len(result) == 256


@pytest.mark.parametrize(
    ("status", "reason", "category", "retryable", "failover"),
    (
        (
            503,
            "token refresh failed quota exceeded",
            "AUTH_REFRESH_EXHAUSTED",
            False,
            True,
        ),
        (403, "OAuth refresh rejected", "AUTH_REFRESH_EXHAUSTED", False, True),
        (429, "LIMIT-BLOCKED", "LIMIT_BLOCKED", False, True),
        (503, "quota exceeded", "LIMIT_BLOCKED", False, True),
        (502, "spending cap", "LIMIT_BLOCKED", False, True),
        (503, "SSL_ERROR_SYSCALL", "UPSTREAM_TLS_STALL", False, True),
        (504, "TLS handshake timeout", "UPSTREAM_TLS_STALL", False, True),
        (429, "busy", "CAPACITY_EXHAUSTED", True, True),
        (502, "bad gateway", "CAPACITY_EXHAUSTED", True, True),
        (400, "model_capacity_exhausted", "CAPACITY_EXHAUSTED", True, True),
        (504, "gateway timeout", "CAPACITY_EXHAUSTED", True, True),
        (403, "forbidden", "FATAL_REQUEST_ERROR", False, False),
        (400, "invalid request", "FATAL_REQUEST_ERROR", False, False),
    ),
)
def test_failure_classification_matrix(
    status: int, reason: str, category: str, retryable: bool, failover: bool
) -> None:
    result = classify_provider_failure(status, reason)
    assert result == FailureClassification(category, retryable, failover, reason)


def test_failure_reason_is_sanitized() -> None:
    result = classify_provider_failure(400, "Bearer hidden user@example.com")
    assert result.sanitized_reason == "<redacted> <redacted>"


@pytest.mark.parametrize(
    ("age", "limit", "drift", "available", "reason"),
    (
        (0.0, 0.0, (), True, "READY"),
        (5.0, 5.0, (), True, "READY"),
        (5.001, 5.0, (), False, "STALE_HEALTH_PROBE"),
        (-0.001, 5.0, (), False, "STALE_HEALTH_PROBE"),
        (1.0, 5.0, ("Z", "A"), False, "ENV_DRIFT_DETECTED"),
    ),
)
def test_route_health_boundaries(
    age: float, limit: float, drift: tuple[str, ...], available: bool, reason: str
) -> None:
    result = evaluate_route_health("model", (), age, limit, drift)
    assert result == RouteHealthStatus("model", available, reason, tuple(sorted(drift)))


def test_route_health_block_precedes_stale_and_normalizes_alias() -> None:
    result = evaluate_route_health("m-high", ("m",), -1.0, 0.0, ("B",))
    assert result == RouteHealthStatus("m", False, "LIMIT_BLOCKED", ("B",))


def test_env_drift_is_sorted_and_compares_missing_values() -> None:
    result = detect_effective_env_drift(
        {"A": "1", "B": "2", "C": ""}, {"A": "1", "B": "3"}, ("C", "B", "A")
    )
    assert result == ("B", "C")
    assert detect_effective_env_drift({"A": "1"}, {"A": "1"}, ("A",)) == ()


def test_retry_config_defaults_and_validation() -> None:
    config = RetryBudgetConfig()
    assert config == RetryBudgetConfig(90.0, 5.0, 4.0, 3, 30.0)
    assert validate_retry_config(config) is config


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
        RetryBudgetConfig(min_attempt_budget_s=float("nan")),
        RetryBudgetConfig(idle_timeout_s=float("inf")),
        RetryBudgetConfig(max_attempts=1.5),
    ),
)
def test_retry_config_rejects_each_invalid_field(config: RetryBudgetConfig) -> None:
    with pytest.raises(ValueError):
        validate_retry_config(config)


@pytest.mark.parametrize(
    ("category", "index", "elapsed", "expected"),
    (
        ("AUTH_REFRESH_EXHAUSTED", 3, 0.0, NON_RETRY),
        ("LIMIT_BLOCKED", 0, 0.0, NON_RETRY),
        ("UPSTREAM_TLS_STALL", 0, 0.0, NON_RETRY),
        ("FATAL_REQUEST_ERROR", 0, 0.0, NON_RETRY),
        ("CAPACITY_EXHAUSTED", 3, 0.0, MAXED),
        (None, 2, 81.0, AttemptDecision(True, 4.0, "BUDGET_OK")),
        (None, 2, 81.001, AttemptDecision(False, 0.0, "BUDGET_EXHAUSTED")),
        (None, 0, 0.0, AttemptDecision(True, 28.333, "BUDGET_OK")),
    ),
)
def test_retry_decision_boundaries(
    category: str | None, index: int, elapsed: float, expected: AttemptDecision
) -> None:
    assert (
        compute_attempt_decision(RetryBudgetConfig(), index, elapsed, category)
        == expected
    )


@pytest.mark.parametrize(
    ("index", "elapsed"), ((-1, 0.0), (0, -0.001), (0, float("inf")))
)
def test_retry_decision_rejects_negative_inputs(index: int, elapsed: float) -> None:
    with pytest.raises(ValueError):
        compute_attempt_decision(RetryBudgetConfig(), index, elapsed)


def test_sliding_deadline_caps_and_preserves_equality() -> None:
    assert advance_sliding_deadline(10.0, 0.0, 5.0, 20.0) == 15.0
    assert advance_sliding_deadline(15.0, 0.0, 5.0, 20.0) == 20.0
    assert advance_sliding_deadline(18.0, 0.0, 5.0, 20.0) == 20.0


def test_canon_digest_marker_unicode_and_missing_marker() -> None:
    present = inspect_canon_payload("Я<!-- КАНОН-КОНЕЦ -->")
    absent = inspect_canon_payload("Я")
    assert present == CanonDigestResult(
        True, "9e3060af02f04fdea57468d22b5dee2e3521d418a2c6a00b19e40c197667aa9d", 32
    )
    assert absent == CanonDigestResult(
        False, "52b99c2a977b538a427c673096b80fa8e977b260ed63683753d187b0dbe28858", 2
    )


def test_canon_custom_marker_and_empty_marker() -> None:
    assert inspect_canon_payload("abc END", "END").has_canon_end_marker is True
    with pytest.raises(ValueError):
        inspect_canon_payload("abc", "")


def test_frozen_results_reject_mutation() -> None:
    route = normalize_model_route("m")
    with pytest.raises(FrozenInstanceError):
        route.canonical_model = "changed"  # type: ignore[misc]


def test_integration_policy_selection_from_real_snapshots() -> None:
    incident = (SNAPSHOTS / "incident-auth.log").read_text(encoding="utf-8")
    retry = (SNAPSHOTS / "agy-retry.log").read_text(encoding="utf-8")
    runtime = (SNAPSHOTS / "runtime-config-dump.md").read_text(encoding="utf-8")
    route = normalize_model_route("claude-opus-5-5-high")
    assert route.canonical_model == "claude-opus-5-5"
    assert classify_provider_failure(403, incident).category == "AUTH_REFRESH_EXHAUSTED"
    assert classify_provider_failure(429, "LIMIT-BLOCKED").category == "LIMIT_BLOCKED"
    config = RetryBudgetConfig(109.732084, 0.0, 4.0, 6, 30.0)
    assert compute_attempt_decision(config, 0, 0.0).attempt_budget_s == 18.289
    assert "per_attempt_upper duration_s=18.288681" in retry
    assert "=300 s" in runtime and "=1500 s" in runtime
    assert detect_effective_env_drift(
        {"TIMEOUT": "1500"}, {"TIMEOUT": "300"}, ("TIMEOUT",)
    ) == ("TIMEOUT",)
