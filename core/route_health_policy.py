from __future__ import annotations

import hashlib
import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from enum import Enum
from math import floor, isfinite
from typing import Final


class EffortLevel(str, Enum):
    LOW = "low"; MEDIUM = "medium"; HIGH = "high"  # fmt: skip  # noqa: E702


class FailureCategory(str, Enum):
    AUTH_REFRESH_EXHAUSTED = "AUTH_REFRESH_EXHAUSTED"; LIMIT_BLOCKED = "LIMIT_BLOCKED"  # fmt: skip  # noqa: E501,E702
    UPSTREAM_TLS_STALL = "UPSTREAM_TLS_STALL"; CAPACITY_EXHAUSTED = "CAPACITY_EXHAUSTED"  # fmt: skip  # noqa: E501,E702
    FATAL_REQUEST_ERROR = "FATAL_REQUEST_ERROR"


class HealthReason(str, Enum):
    READY = "READY"; LIMIT_BLOCKED = "LIMIT_BLOCKED"  # fmt: skip  # noqa: E702
    STALE_HEALTH_PROBE = "STALE_HEALTH_PROBE"
    ENV_DRIFT_DETECTED = "ENV_DRIFT_DETECTED"


class RetryReason(str, Enum):
    BUDGET_OK = "BUDGET_OK"; BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"  # fmt: skip  # noqa: E702
    NON_RETRYABLE_CATEGORY = "NON_RETRYABLE_CATEGORY"
    MAX_ATTEMPTS_REACHED = "MAX_ATTEMPTS_REACHED"


DEFAULT_CANON_MARKER: Final[str] = "<!-- КАНОН-КОНЕЦ -->"
REDACTED_TOKEN: Final[str] = "<redacted>"
MAX_DIAGNOSTIC_CHARS: Final[int] = 256
_EFFORTS: Final[frozenset[str]] = frozenset(item.value for item in EffortLevel)
_CAPACITY_STATUSES: Final[frozenset[int]] = frozenset((429, 502, 503, 504))
_SECRET_PATTERNS: Final[tuple[str, ...]] = (r"(?i)\b(?:bearer|basic)\s+\S+", r"(?i)\b(?:refresh_token|access_token|client_secret|api_key|password|secret|token|cookie)\s*[:=]\s*\S+", r"\bya29\.[A-Za-z0-9._-]+", r"\b1//[A-Za-z0-9._-]+", r"\bsk-[A-Za-z0-9._-]+", r"\bAIza[A-Za-z0-9_-]+", r"\b[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")  # fmt: skip  # noqa: E501


@dataclass(frozen=True)
class NormalizedModelRoute:
    canonical_model: str
    reasoning_effort: str | None
    alias_applied: bool


def normalize_model_route(model_id: str, explicit_effort: str | None = None, allowed_suffixes: Collection[str] | None = None) -> NormalizedModelRoute:  # fmt: skip  # noqa: E501
    model = model_id.strip()
    if not model:
        raise ValueError("model_id must not be empty")
    allowed = _EFFORTS
    if allowed_suffixes is not None:
        allowed = frozenset(
            suffix.strip().lower() for suffix in allowed_suffixes if suffix.strip()
        )
    if explicit_effort is not None:
        explicit = explicit_effort.strip().lower()
        if explicit not in _EFFORTS:
            raise ValueError("explicit_effort must be low, medium, or high")
    else:
        explicit = None
    for suffix in sorted(allowed, key=len, reverse=True):
        marker = f"-{suffix}"
        if len(model) > len(marker) and model.lower().endswith(marker):
            return NormalizedModelRoute(model[: -len(marker)], explicit or suffix, True)
    return NormalizedModelRoute(model, explicit, False)


def redact_diagnostic_text(raw_text: str) -> str:
    safe = raw_text
    for pattern in _SECRET_PATTERNS:
        safe = re.sub(pattern, REDACTED_TOKEN, safe)
    safe = re.sub(r"[\x00-\x1f\x7f]+", " ", safe)
    return safe[:MAX_DIAGNOSTIC_CHARS]


@dataclass(frozen=True)
class FailureClassification:
    category: FailureCategory
    retryable: bool
    failover_eligible: bool
    sanitized_reason: str


def _is_auth_failure(status_code: int, reason: str) -> bool:
    terms = ("token refresh failed", "oauth refresh", "invalid_grant", "invalid api key")  # fmt: skip  # noqa: E501
    if any(term in reason for term in terms):
        return True
    if status_code == 401:
        return True
    auth_terms = ("oauth", "refresh", "unauthenticated")
    return status_code == 403 and any(term in reason for term in auth_terms)


def classify_provider_failure(status_code: int, raw_reason: str) -> FailureClassification:  # fmt: skip  # noqa: E501
    reason = raw_reason.lower()
    sanitized = redact_diagnostic_text(raw_reason)
    if _is_auth_failure(status_code, reason):
        values = (FailureCategory.AUTH_REFRESH_EXHAUSTED, False, True, sanitized)
    elif any(term in reason for term in ("limit-blocked", "quota exceeded", "spending cap")):  # fmt: skip  # noqa: E501
        values = (FailureCategory.LIMIT_BLOCKED, False, True, sanitized)
    elif "ssl_error_syscall" in reason or "tls handshake timeout" in reason:
        values = (FailureCategory.UPSTREAM_TLS_STALL, False, True, sanitized)
    elif status_code in _CAPACITY_STATUSES or "model_capacity_exhausted" in reason:
        values = (FailureCategory.CAPACITY_EXHAUSTED, True, True, sanitized)
    else:
        values = (FailureCategory.FATAL_REQUEST_ERROR, False, False, sanitized)
    return FailureClassification(*values)


@dataclass(frozen=True)
class RouteHealthStatus:
    model_id: str
    available: bool
    status_reason: HealthReason
    env_drift_keys: tuple[str, ...]


def evaluate_route_health(model_id: str, blocked_models: tuple[str, ...], probe_age_s: float, max_stale_age_s: float, env_drift_keys: tuple[str, ...] = ()) -> RouteHealthStatus:  # fmt: skip  # noqa: E501
    _require_finite(probe_age_s, "probe_age_s")
    _require_finite(max_stale_age_s, "max_stale_age_s")
    if max_stale_age_s < 0:
        raise ValueError("max_stale_age_s must be non-negative")
    canonical = normalize_model_route(model_id).canonical_model
    blocked = tuple(normalize_model_route(item).canonical_model for item in blocked_models)  # fmt: skip  # noqa: E501
    drift = tuple(sorted(env_drift_keys))
    if canonical in blocked:
        reason = HealthReason.LIMIT_BLOCKED
    elif probe_age_s > max_stale_age_s or probe_age_s < 0:
        reason = HealthReason.STALE_HEALTH_PROBE
    elif drift:
        reason = HealthReason.ENV_DRIFT_DETECTED
    else:
        return RouteHealthStatus(canonical, True, HealthReason.READY, drift)
    return RouteHealthStatus(canonical, False, reason, drift)


def detect_effective_env_drift(expected_env: Mapping[str, str], live_env: Mapping[str, str], tracked_keys: tuple[str, ...]) -> tuple[str, ...]:  # fmt: skip  # noqa: E501
    changed = (key for key in tracked_keys if expected_env.get(key) != live_env.get(key))  # fmt: skip  # noqa: E501
    return tuple(sorted(changed))


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
    reason: RetryReason


def _require_finite(value: float, field: str) -> None:
    if not isfinite(value):
        raise ValueError(f"{field} must be finite")


def validate_retry_config(config: RetryBudgetConfig) -> RetryBudgetConfig:
    _require_finite(config.total_budget_s, "total_budget_s")
    _require_finite(config.reserve_s, "reserve_s")
    _require_finite(config.min_attempt_budget_s, "min_attempt_budget_s")
    _require_finite(config.idle_timeout_s, "idle_timeout_s")
    invalid = (config.total_budget_s <= 0, config.reserve_s < 0 or config.reserve_s >= config.total_budget_s, config.min_attempt_budget_s <= 0, type(config.max_attempts) is not int or config.max_attempts < 1, config.idle_timeout_s <= 0)  # fmt: skip  # noqa: E501
    if any(invalid):
        raise ValueError("invalid retry budget configuration")
    return config


def compute_attempt_decision(config: RetryBudgetConfig, attempt_index: int, elapsed_s: float, last_failure_category: str | None = None) -> AttemptDecision:  # fmt: skip  # noqa: E501
    _ = validate_retry_config(config)
    if attempt_index < 0 or elapsed_s < 0 or not isfinite(elapsed_s):
        raise ValueError("attempt_index and elapsed_s must be non-negative")
    if last_failure_category not in (None, FailureCategory.CAPACITY_EXHAUSTED):
        return AttemptDecision(False, 0.0, RetryReason.NON_RETRYABLE_CATEGORY)
    if attempt_index >= config.max_attempts:
        return AttemptDecision(False, 0.0, RetryReason.MAX_ATTEMPTS_REACHED)
    usable_s = config.total_budget_s - config.reserve_s - elapsed_s
    per_attempt_s = usable_s / (config.max_attempts - attempt_index)
    if per_attempt_s < config.min_attempt_budget_s:
        return AttemptDecision(False, 0.0, RetryReason.BUDGET_EXHAUSTED)
    budget_s = floor(per_attempt_s * 1000.0) / 1000.0
    return AttemptDecision(True, budget_s, RetryReason.BUDGET_OK)


def advance_sliding_deadline(now_s: float, start_s: float, idle_timeout_s: float, safety_cap_s: float) -> float:  # fmt: skip  # noqa: E501
    _require_finite(now_s, "now_s")
    _require_finite(start_s, "start_s")
    _require_finite(idle_timeout_s, "idle_timeout_s")
    _require_finite(safety_cap_s, "safety_cap_s")
    if idle_timeout_s <= 0 or safety_cap_s <= 0 or now_s < start_s:
        raise ValueError("invalid deadline window parameters")
    return min(now_s + idle_timeout_s, start_s + safety_cap_s)


@dataclass(frozen=True)
class CanonDigestResult:
    has_canon_end_marker: bool
    sha256_hex: str
    byte_length: int
    unchanged: bool = False


def inspect_canon_payload(text: str, marker: str = DEFAULT_CANON_MARKER, previous_sha256: str | None = None) -> CanonDigestResult:  # fmt: skip  # noqa: E501
    if not marker:
        raise ValueError("marker must not be empty")
    payload = text.encode("utf-8")
    has_marker = text.rstrip().endswith(marker)
    sha = hashlib.sha256(payload).hexdigest()
    unchanged = bool(has_marker and previous_sha256 is not None and sha == previous_sha256)  # fmt: skip  # noqa: E501
    return CanonDigestResult(has_marker, sha, len(payload), unchanged)
