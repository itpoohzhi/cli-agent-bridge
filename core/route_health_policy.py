"""Pure routing, health, retry, and canonical-payload policy primitives."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite


_EFFORTS = frozenset(("low", "medium", "high"))
_NON_RETRYABLE = frozenset(
    (
        "AUTH_REFRESH_EXHAUSTED",
        "LIMIT_BLOCKED",
        "UPSTREAM_TLS_STALL",
        "FATAL_REQUEST_ERROR",
    )
)
_CAPACITY_STATUSES = frozenset((429, 502, 503, 504))


@dataclass(frozen=True)
class NormalizedModelRoute:
    canonical_model: str
    reasoning_effort: str | None
    alias_applied: bool


def normalize_model_route(
    model_id: str, explicit_effort: str | None = None
) -> NormalizedModelRoute:
    """Normalize an optional effort suffix while preserving explicit effort."""
    model = model_id.strip()
    if not model:
        raise ValueError("model_id must not be empty")
    if explicit_effort is not None and explicit_effort not in _EFFORTS:
        raise ValueError("explicit_effort must be low, medium, or high")
    for suffix in _EFFORTS:
        marker = f"-{suffix}"
        if model.endswith(marker) and len(model) > len(marker):
            effort = explicit_effort if explicit_effort is not None else suffix
            return NormalizedModelRoute(model[: -len(marker)], effort, True)
    return NormalizedModelRoute(model, explicit_effort, False)


def redact_diagnostic_text(raw_text: str) -> str:
    """Return a bounded diagnostic without common credentials or identities."""
    safe = re.sub(r"(?i)\bbearer\s+\S+", "<redacted>", raw_text)
    safe = re.sub(r"\bsk-[A-Za-z0-9._-]+", "<redacted>", safe)
    safe = re.sub(r"\bAIza[A-Za-z0-9_-]+", "<redacted>", safe)
    safe = re.sub(
        r"\b[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "<redacted>",
        safe,
    )
    safe = re.sub(r"[\x00-\x1f\x7f]+", " ", safe)
    return safe[:256]


@dataclass(frozen=True)
class FailureClassification:
    category: str
    retryable: bool
    failover_eligible: bool
    sanitized_reason: str


def _is_auth_failure(status_code: int, reason: str) -> bool:
    if "token refresh failed" in reason or "oauth refresh" in reason:
        return True
    return status_code in (401, 403) and any(
        token in reason for token in ("oauth", "refresh", "token")
    )


def classify_provider_failure(
    status_code: int, raw_reason: str
) -> FailureClassification:
    """Classify a provider failure using ordered, provider-neutral evidence."""
    reason = raw_reason.lower()
    sanitized = redact_diagnostic_text(raw_reason)
    if _is_auth_failure(status_code, reason):
        return FailureClassification("AUTH_REFRESH_EXHAUSTED", False, True, sanitized)
    if any(
        term in reason for term in ("limit-blocked", "quota exceeded", "spending cap")
    ):
        return FailureClassification("LIMIT_BLOCKED", False, True, sanitized)
    if "ssl_error_syscall" in reason or "tls handshake timeout" in reason:
        return FailureClassification("UPSTREAM_TLS_STALL", False, True, sanitized)
    if status_code in _CAPACITY_STATUSES or "model_capacity_exhausted" in reason:
        return FailureClassification("CAPACITY_EXHAUSTED", True, True, sanitized)
    return FailureClassification("FATAL_REQUEST_ERROR", False, False, sanitized)


@dataclass(frozen=True)
class RouteHealthStatus:
    model_id: str
    available: bool
    status_reason: str
    env_drift_keys: tuple[str, ...]


def evaluate_route_health(
    model_id: str,
    blocked_models: tuple[str, ...],
    probe_age_s: float,
    max_stale_age_s: float,
    env_drift_keys: tuple[str, ...] = (),
) -> RouteHealthStatus:
    """Evaluate request admission separately from catalog display state."""
    canonical = normalize_model_route(model_id).canonical_model
    blocked = tuple(
        normalize_model_route(item).canonical_model for item in blocked_models
    )
    drift = tuple(sorted(env_drift_keys))
    if canonical in blocked:
        return RouteHealthStatus(canonical, False, "LIMIT_BLOCKED", drift)
    if probe_age_s > max_stale_age_s or probe_age_s < 0:
        return RouteHealthStatus(canonical, False, "STALE_HEALTH_PROBE", drift)
    if drift:
        return RouteHealthStatus(canonical, False, "ENV_DRIFT_DETECTED", drift)
    return RouteHealthStatus(canonical, True, "READY", drift)


def detect_effective_env_drift(
    expected_env: Mapping[str, str],
    live_env: Mapping[str, str],
    tracked_keys: tuple[str, ...],
) -> tuple[str, ...]:
    """Return tracked keys whose configured and effective values differ."""
    return tuple(
        sorted(
            key for key in tracked_keys if expected_env.get(key) != live_env.get(key)
        )
    )


@dataclass(frozen=True)
class RetryBudgetConfig:
    total_budget_s: float = 90.0
    reserve_s: float = 5.0
    min_attempt_budget_s: float = 4.0
    max_attempts: int = 3
    idle_timeout_s: float = 30.0


@dataclass(frozen=True)
class AttemptDecision:
    allow_retry: bool
    attempt_budget_s: float
    reason: str


def _require_finite(value: float, field: str) -> None:
    if not isfinite(value):
        raise ValueError(f"{field} must be finite")


def validate_retry_config(config: RetryBudgetConfig) -> RetryBudgetConfig:
    """Reject unsafe or nonsensical retry budget fields."""
    _require_finite(config.total_budget_s, "total_budget_s")
    _require_finite(config.reserve_s, "reserve_s")
    _require_finite(config.min_attempt_budget_s, "min_attempt_budget_s")
    _require_finite(config.idle_timeout_s, "idle_timeout_s")
    if config.total_budget_s <= 0:
        raise ValueError("total_budget_s must be positive")
    if config.reserve_s < 0 or config.reserve_s >= config.total_budget_s:
        raise ValueError("reserve_s must fit within total_budget_s")
    if config.min_attempt_budget_s <= 0:
        raise ValueError("min_attempt_budget_s must be positive")
    if type(config.max_attempts) is not int or config.max_attempts < 1:
        raise ValueError("max_attempts must be a positive integer")
    if config.idle_timeout_s <= 0:
        raise ValueError("idle_timeout_s must be positive")
    return config


def compute_attempt_decision(
    config: RetryBudgetConfig,
    attempt_index: int,
    elapsed_s: float,
    last_failure_category: str | None = None,
) -> AttemptDecision:
    """Admit an attempt only when its class and remaining budget permit it."""
    validate_retry_config(config)
    if attempt_index < 0 or elapsed_s < 0 or not isfinite(elapsed_s):
        raise ValueError("attempt_index and elapsed_s must be non-negative")
    if last_failure_category in _NON_RETRYABLE:
        return AttemptDecision(False, 0.0, "NON_RETRYABLE_CATEGORY")
    if attempt_index >= config.max_attempts:
        return AttemptDecision(False, 0.0, "MAX_ATTEMPTS_REACHED")
    usable_s = config.total_budget_s - config.reserve_s - elapsed_s
    remaining_slots = config.max_attempts - attempt_index
    per_attempt_s = usable_s / remaining_slots
    if per_attempt_s < config.min_attempt_budget_s:
        return AttemptDecision(False, 0.0, "BUDGET_EXHAUSTED")
    return AttemptDecision(True, round(per_attempt_s, 3), "BUDGET_OK")


def advance_sliding_deadline(
    now_s: float, start_s: float, idle_timeout_s: float, safety_cap_s: float
) -> float:
    """Advance an idle deadline without exceeding the absolute safety cap."""
    candidate = now_s + idle_timeout_s
    hard_limit = start_s + safety_cap_s
    return min(candidate, hard_limit)


@dataclass(frozen=True)
class CanonDigestResult:
    has_canon_end_marker: bool
    sha256_hex: str
    byte_length: int


def inspect_canon_payload(
    text: str, marker: str = "<!-- КАНОН-КОНЕЦ -->"
) -> CanonDigestResult:
    """Inspect exact UTF-8 bytes and the mandatory canonical end marker."""
    if not marker:
        raise ValueError("marker must not be empty")
    payload = text.encode("utf-8")
    return CanonDigestResult(
        marker in text, hashlib.sha256(payload).hexdigest(), len(payload)
    )
