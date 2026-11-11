from __future__ import annotations

import hashlib
import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from enum import Enum
from math import floor
from typing import Final


class EffortLevel(str, Enum):  # noqa: UP042
    LOW = "low"; MEDIUM = "medium"; HIGH = "high"  # fmt: skip  # noqa: E702


class FailureCategory(str, Enum):  # noqa: UP042
    AUTH_REFRESH_EXHAUSTED = "AUTH_REFRESH_EXHAUSTED"; LIMIT_BLOCKED = "LIMIT_BLOCKED"  # fmt: skip  # noqa: E501,E702
    UPSTREAM_TLS_STALL = "UPSTREAM_TLS_STALL"; CAPACITY_EXHAUSTED = "CAPACITY_EXHAUSTED"  # fmt: skip  # noqa: E501,E702
    FATAL_REQUEST_ERROR = "FATAL_REQUEST_ERROR"


class HealthReason(str, Enum):  # noqa: UP042
    READY = "READY"; LIMIT_BLOCKED = "LIMIT_BLOCKED"  # fmt: skip  # noqa: E702
    STALE_HEALTH_PROBE = "STALE_HEALTH_PROBE"; ENV_DRIFT_DETECTED = "ENV_DRIFT_DETECTED"  # fmt: skip  # noqa: E501,E702


class RetryReason(str, Enum):  # noqa: UP042
    BUDGET_OK = "BUDGET_OK"; BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"  # fmt: skip  # noqa: E702
    NON_RETRYABLE_CATEGORY = "NON_RETRYABLE_CATEGORY"
    MAX_ATTEMPTS_REACHED = "MAX_ATTEMPTS_REACHED"


DEFAULT_CANON_MARKER: Final[str] = "<!-- КАНОН-КОНЕЦ -->"
REDACTED_TOKEN: Final[str] = "<redacted>"
MAX_DIAGNOSTIC_CHARS: Final[int] = 256
_EFFORTS: Final[frozenset[str]] = frozenset(item.value for item in EffortLevel)
_CAPACITY_STATUSES: Final[frozenset[int]] = frozenset((429, 502, 503, 504))
_SECRET_PATTERNS: Final[tuple[str, ...]] = (r"(?i)\b[a-z][a-z0-9+.-]*://(?:[^\s\"']*:[^\r\n@]+@[^\s/\"']+|[^\s/\"'@]*:(?![0-9]{1,5}(?:[/?#\s\"']|$))[^\s/\"'@]+)", r"(?i)(?:\\*[\"'])?[a-z0-9_.-]{0,32}a\s*u\s*t\s*h\s*o\s*r\s*i\s*z\s*a\s*t\s*i\s*o\s*n[a-z0-9_.-]{0,32}\b(?:\\*[\"'])?\s*[:=]\s*[^\r\n]+", r"(?i)\b(?:b\s*e\s*a\s*r\s*e\s*r|b\s*a\s*s\s*i\s*c)\s+(?:\\*\"(?:\\.|[^\"\r\n\\])*\\*(?:\"|$)|\\*'(?:\\.|[^'\r\n\\])*\\*(?:'|$)|[^\s,;\"']+(?:\s+(?!b\s*a\s*s\s*i\s*c\b|b\s*e\s*a\s*r\s*e\s*r\b|ya29\.|1//|sk-|AIza|[a-z0-9_.-]+\s*[:=]|[^\s@]+@[^\s@]+\.[a-z]{2,})[^\s,;\"']+)*)", r"(?i)(?:\\*[\"'])?[a-z0-9_.-]{0,32}c\s*o\s*o\s*k\s*i\s*e[a-z0-9_.-]{0,32}\b(?:\\*[\"'])?\s*[:=]\s*[^\r\n]+", r"(?i)(?:\\*[\"'])?[a-z0-9_.-]{0,32}(?:r\s*e\s*f\s*r\s*e\s*s\s*h[\s_]*t\s*o\s*k\s*e\s*n|a\s*c\s*c\s*e\s*s\s*s[\s_]*t\s*o\s*k\s*e\s*n|i\s*d[\s_]*t\s*o\s*k\s*e\s*n|c\s*l\s*i\s*e\s*n\s*t[\s_]*s\s*e\s*c\s*r\s*e\s*n?t|x[\s_-]*a\s*p\s*i[\s_-]*k\s*e\s*y|a\s*p\s*i[\s_-]*k\s*e\s*y|p\s*a\s*s\s*s\s*w\s*o\s*r\s*d|p\s*a\s*s\s*s\s*w\s*d|p\s*w\s*d|s\s*e\s*c\s*r\s*e\s*t|t\s*o\s*k\s*e\s*n)[a-z0-9_.-]{0,32}\b(?:\\*[\"'])?\s*%*\s*[:=]\s*(?:\\*\[[^\r\n\]]*(?:\]|$)|\\*\{[^\r\n\}]*(?:\}|$)|[bB]?\\*\"(?:\\.|[^\"\r\n\\])*\\*(?:\"|$)|[bB]?\\*'(?:\\.|[^'\r\n\\])*\\*(?:'|$)|\([^\r\n\)]*(?:\)|$)|[^\r\n]+)", r"(?i)\b(?:i\s*n\s*v\s*a\s*l\s*i\s*d|e\s*x\s*p\s*i\s*r\s*e\s*d|b\s*a\s*d|r\s*e\s*v\s*o\s*k\s*e\s*d|l\s*e\s*a\s*k\s*e\s*d)\s+(?:r\s*e\s*f\s*r\s*e\s*s\s*h[\s_]*t\s*o\s*k\s*e\s*n|a\s*c\s*c\s*e\s*s\s*s[\s_]*t\s*o\s*k\s*e\s*n|i\s*d[\s_]*t\s*o\s*k\s*e\s*n|a\s*p\s*i[\s_-]*k\s*e\s*y|c\s*l\s*i\s*e\s*n\s*t[\s_]*s\s*e\s*c\s*r\s*e\s*t|p\s*a\s*s\s*s\s*w\s*o\s*r\s*d|p\s*a\s*s\s*s\s*w\s*d|p\s*w\s*d|s\s*e\s*c\s*r\s*e\s*t|t\s*o\s*k\s*e\s*n)\s+[^\r\n,;\"']+", r"\beyJ[A-Za-z0-9_-]{4,}\.eyJ[A-Za-z0-9_-]{4,}\.[A-Za-z0-9._-]*", r"\bya29\.[A-Za-z0-9._-]+", r"\b1//[A-Za-z0-9._-]+", r"\bsk-[A-Za-z0-9._-]+", r"\bAIza[A-Za-z0-9_-]+", r"(?<![A-Za-z0-9.!#$%&'*+/=?^_`{|}~-])[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")  # fmt: skip  # noqa: E501
_SECRET_REGEXES: Final[tuple[re.Pattern[str], ...]] = tuple(re.compile(pattern) for pattern in _SECRET_PATTERNS)  # fmt: skip  # noqa: E501
@dataclass(frozen=True)
class NormalizedModelRoute:
    canonical_model: str; reasoning_effort: str | None  # fmt: skip  # noqa: E702
    alias_applied: bool
def _match_known(target: str, known_models: Collection[str]) -> str | None:
    lowered = target.lower()
    matches = sorted(candidate for item in known_models if (candidate := item.strip()) and candidate.lower() == lowered)  # fmt: skip  # noqa: E501
    return matches[0] if matches else None

def _resolve_route_suffix(model: str, explicit: str | None, allowed: frozenset[str], known_models: Collection[str] | None) -> NormalizedModelRoute:  # fmt: skip  # noqa: E501
    if known_models is not None and (exact := _match_known(model, known_models)) is not None: return NormalizedModelRoute(exact, explicit, False)  # fmt: skip  # noqa: E501,E701
    for suffix in sorted(allowed, key=len, reverse=True):
        marker = f"-{suffix}"
        if len(model) > len(marker) and model.lower().endswith(marker):
            base, effort = model[: -len(marker)], explicit or suffix
            canon = base if known_models is None else _match_known(base, known_models)
            if canon is not None: return NormalizedModelRoute(canon, effort, True)  # fmt: skip  # noqa: E501,E701
    return NormalizedModelRoute(model, explicit, False)

def normalize_model_route(model_id: str, explicit_effort: str | None = None, allowed_suffixes: Collection[str] | None = None, known_models: Collection[str] | None = None) -> NormalizedModelRoute:  # fmt: skip  # noqa: E501
    model = model_id.strip()
    if len(model.split()) != 1:
        raise ValueError("model_id must not be empty or contain whitespace")
    allowed = _EFFORTS
    if allowed_suffixes is not None:
        allowed = frozenset(suffix.strip().lower() for suffix in allowed_suffixes if suffix.strip())  # fmt: skip  # noqa: E501
    explicit = explicit_effort.strip().lower() if explicit_effort is not None else None
    if explicit is not None and explicit not in allowed:
        raise ValueError("explicit_effort is not in allowed_suffixes")
    return _resolve_route_suffix(model, explicit, allowed, known_models)
_INVISIBLE_RE: Final[re.Pattern[str]] = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u00ad\u0300-\u036f\u061c\u115f\u1160\u17b4\u17b5\u180b-\u180f\u1ab0-\u1aff\u1dc0-\u1dff\u200b-\u200f\u202a-\u202e\u2060-\u206f\u20d0-\u20ff\u3164\ufe00-\ufe2f\ufeff\uffa0\ufff0-\ufffb]+")  # fmt: skip  # noqa: E501
_ANSI_RE: Final[re.Pattern[str]] = re.compile(r"(?:(?:\x1b|\\+(?:u001|x1)[bB])\[|(?:\x9b|\\+(?:u009|x9)[bB]))[0-?]*[ -/]*[@-~]|(?:(?:\x1b|\\+(?:u001|x1)[bB])[\]P_X^]|(?:\x9d|\x90|\x98|\x9e|\x9f|\\+(?:u009|x9)[dD08eEfF]))[^\x07\x1b\x9c]*(?:\x07|\x9c|\x1b\\|\\+(?:u0007|x07|u009[cC]|x9[cC])|\\+(?:u001|x1)[bB]\\\\|$)")  # fmt: skip  # noqa: E501
_ESCAPE_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"\\+(?:u([0-9a-fA-F]{4})|x([0-9a-fA-F]{2})|([0-7]{1,3}))|%([0-9a-fA-F]{2})|&#(?:[xX]([0-9a-fA-F]{1,6})(?![0-9a-fA-F])|([0-9]{1,7})(?![0-9]));?")  # fmt: skip  # noqa: E501


def _decode_escape(match: re.Match[str]) -> str:
    hex_s, oct_s, dec_s = match.group(1) or match.group(2) or match.group(4) or match.group(5), match.group(3), match.group(6)  # fmt: skip  # noqa: E501
    code = int(hex_s, 16) if hex_s else (int(oct_s, 8) if oct_s else int(dec_s, 10))
    if code in (0x09, 0x0A, 0x0D): return " "  # fmt: skip  # noqa: E701
    if code in (0x07, 0x1B, 0x90, 0x98, 0x9B, 0x9C, 0x9D, 0x9E, 0x9F): return chr(code)  # fmt: skip  # noqa: E501,E701
    if code <= 0x1F or 0x7F <= code <= 0x9F or code > 0x10FFFF or 0xD800 <= code <= 0xDFFF or _INVISIBLE_RE.fullmatch(chr(code)): return ""  # fmt: skip  # noqa: E501,E701
    return chr(code) if code <= 0x7E else " "


def _normalize_diagnostic_text(raw_text: str, *, max_len: int = 4096, fail_closed: bool = True) -> str:  # fmt: skip  # noqa: E501
    compact = re.sub(r"(.)\1{255,}", lambda m: m.group(1) * 256, re.sub(r"[\t\r\n ]+", " ", _INVISIBLE_RE.sub("", _ANSI_RE.sub("", raw_text[:262144]))))[:max_len]  # fmt: skip  # noqa: E501
    safe = compact
    for _ in range(8):
        previous = safe; safe = _ESCAPE_TOKEN_RE.sub(_decode_escape, safe)  # fmt: skip  # noqa: E702
        safe = _INVISIBLE_RE.sub("", _ANSI_RE.sub("", re.sub(r"\\+[bfnrtv]", " ", safe)))  # fmt: skip  # noqa: E501
        if previous == safe: break  # fmt: skip  # noqa: E701
    if fail_closed and re.search(r"\\+(?:u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|[0-7]{1,3})|%[0-9a-fA-F]{2}|&#[xX]?[0-9a-fA-F]+|[\x1b\x90\x98\x9b-\x9f]", safe): return REDACTED_TOKEN  # fmt: skip  # noqa: E501,E701
    return re.sub(r"[\x00-\x20\x7f\ud800-\udfff]+", " ", safe)


def redact_diagnostic_text(raw_text: str) -> str:
    safe = _normalize_diagnostic_text(raw_text, max_len=65536)
    for regex in _SECRET_REGEXES:
        safe = regex.sub(REDACTED_TOKEN, safe)
    return safe[:MAX_DIAGNOSTIC_CHARS] or (" " if raw_text else "")

@dataclass(frozen=True)
class FailureClassification:
    category: FailureCategory; retryable: bool  # fmt: skip  # noqa: E702
    failover_eligible: bool; sanitized_reason: str  # fmt: skip  # noqa: E702

def _is_auth_failure(status_code: int, reason: str) -> bool:
    terms = ("token refresh failed", "tokenrefresh failed", "oauth refresh", "invalid_grant", "invalid api key", "api key not valid", "api key expired", "api_key_invalid", "invalid token", "unauthorized", "unauthenticated")  # fmt: skip  # noqa: E501
    if any(term in reason for term in terms):
        return True
    if status_code == 401 or (status_code == 0 and bool(re.search(r"(?:\bhttp(?:[/\s]*\d(?:\.\d)?)?\s+401\b|(?:\\*[\"'])?\bstatus(?:[_ -]?code)?\b(?:\\*[\"'])?\s*[:=]\s*401\b|(?:^\s*|:\s*)401\b)", reason))):  # fmt: skip  # noqa: E501
        return True
    is_403 = status_code == 403 or (status_code == 0 and bool(re.search(r"(?:\bhttp(?:[/\s]*\d(?:\.\d)?)?\s+403\b|(?:\\*[\"'])?\bstatus(?:[_ -]?code)?\b(?:\\*[\"'])?\s*[:=]\s*403\b|(?:^\s*|:\s*)403\b)", reason)))  # fmt: skip  # noqa: E501
    return is_403 and any(term in reason for term in ("oauth", "refresh", "unauthenticated"))  # fmt: skip  # noqa: E501


def classify_provider_failure(status_code: int, raw_reason: str) -> FailureClassification:  # fmt: skip  # noqa: E501
    reason = _normalize_diagnostic_text(raw_reason, max_len=65536, fail_closed=False).lower()  # noqa: E501
    sanitized = redact_diagnostic_text(raw_reason)
    if _is_auth_failure(status_code, reason):
        values = (FailureCategory.AUTH_REFRESH_EXHAUSTED, False, True, sanitized)
    elif any(term in reason for term in ("limit-blocked", "quota exceeded", "spending cap")):  # fmt: skip  # noqa: E501
        values = (FailureCategory.LIMIT_BLOCKED, False, True, sanitized)
    elif "ssl_error_syscall" in reason or "tls handshake timeout" in reason:
        values = (FailureCategory.UPSTREAM_TLS_STALL, False, True, sanitized)
    elif status_code in _CAPACITY_STATUSES or "model_capacity_exhausted" in reason or (status_code == 0 and bool(re.search(r"\bhttp(?:[/\s]*\d(?:\.\d)?)?\s+(?:429|502|503|504)\b", reason))):  # fmt: skip  # noqa: E501
        values = (FailureCategory.CAPACITY_EXHAUSTED, True, True, sanitized)
    else:
        values = (FailureCategory.FATAL_REQUEST_ERROR, False, False, sanitized)
    return FailureClassification(*values)


@dataclass(frozen=True)
class RouteHealthStatus:
    model_id: str; available: bool  # fmt: skip  # noqa: E702
    status_reason: HealthReason; env_drift_keys: tuple[str, ...]  # fmt: skip  # noqa: E702

def _route_targets(model_id: str | NormalizedModelRoute) -> tuple[str, frozenset[str]]:  # fmt: skip  # noqa: E501
    route = model_id if isinstance(model_id, NormalizedModelRoute) else normalize_model_route(model_id)  # fmt: skip  # noqa: E501
    canon, eff = route.canonical_model.strip(), route.reasoning_effort
    if len(canon.split()) != 1 or (eff is not None and len(eff.strip().split()) != 1): raise ValueError("invalid NormalizedModelRoute")  # fmt: skip  # noqa: E501,E701
    alias = f"{canon}-{eff.strip().lower()}".lower() if eff else canon.lower()
    return canon, frozenset((canon.lower(), alias))


def evaluate_route_health(model_id: str | NormalizedModelRoute, blocked_models: tuple[str, ...], probe_age_s: float, max_stale_age_s: float, env_drift_keys: tuple[str, ...] = ()) -> RouteHealthStatus:  # fmt: skip  # noqa: E501
    _require_finite(probe_age_s, "probe_age_s")
    _require_finite(max_stale_age_s, "max_stale_age_s")
    if max_stale_age_s < 0:
        raise ValueError("max_stale_age_s must be non-negative")
    canonical, targets = _route_targets(model_id)
    blocked = {item.strip().lower() for item in blocked_models if item.strip()}
    drift = tuple(sorted(env_drift_keys))
    if targets & blocked:
        reason = HealthReason.LIMIT_BLOCKED
    elif not 0 <= probe_age_s <= max_stale_age_s:
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
    total_budget_s: float = 90.0; reserve_s: float = 5.0  # fmt: skip  # noqa: E702
    min_attempt_budget_s: float = 4.0; max_attempts: int = 3  # fmt: skip  # noqa: E702
    idle_timeout_s: float = 30.0


@dataclass(frozen=True)
class AttemptDecision:
    allow_retry: bool
    attempt_budget_s: float
    reason: RetryReason


def _require_finite(value: float, field: str) -> None:
    if type(value) not in (int, float) or not (-1e308 <= value <= 1e308):
        raise ValueError(f"{field} must be finite")


def validate_retry_config(config: RetryBudgetConfig) -> RetryBudgetConfig:
    _require_finite(config.total_budget_s, "total_budget_s")
    _require_finite(config.reserve_s, "reserve_s")
    _require_finite(config.min_attempt_budget_s, "min_attempt_budget_s")
    _require_finite(config.idle_timeout_s, "idle_timeout_s")
    invalid = (not 0 < config.total_budget_s <= 86400.0, config.reserve_s < 0 or config.reserve_s >= config.total_budget_s, not 0.001 <= config.min_attempt_budget_s <= 86400.0, type(config.max_attempts) is not int or not 1 <= config.max_attempts <= 1000, not 0 < config.idle_timeout_s <= 86400.0)  # fmt: skip  # noqa: E501
    if any(invalid):
        raise ValueError("invalid retry budget configuration")
    return config


def compute_attempt_decision(config: RetryBudgetConfig, attempt_index: int, elapsed_s: float, last_failure_category: str | None = None) -> AttemptDecision:  # fmt: skip  # noqa: E501
    _ = validate_retry_config(config)
    _require_finite(elapsed_s, "elapsed_s")
    if type(attempt_index) is not int or attempt_index < 0 or elapsed_s < 0:
        raise ValueError("attempt_index and elapsed_s must be non-negative")
    if last_failure_category not in (None, FailureCategory.CAPACITY_EXHAUSTED):
        return AttemptDecision(False, 0.0, RetryReason.NON_RETRYABLE_CATEGORY)
    if attempt_index >= config.max_attempts:
        return AttemptDecision(False, 0.0, RetryReason.MAX_ATTEMPTS_REACHED)
    usable_s = config.total_budget_s - config.reserve_s - elapsed_s
    if usable_s <= 0.0:
        return AttemptDecision(False, 0.0, RetryReason.BUDGET_EXHAUSTED)
    per_attempt_s = usable_s / (config.max_attempts - attempt_index)
    budget_s = floor(round(per_attempt_s * 1000.0, 9)) / 1000.0
    if budget_s < config.min_attempt_budget_s:
        return AttemptDecision(False, 0.0, RetryReason.BUDGET_EXHAUSTED)
    return AttemptDecision(True, budget_s, RetryReason.BUDGET_OK)


def advance_sliding_deadline(now_s: float, start_s: float, idle_timeout_s: float, safety_cap_s: float) -> float:  # fmt: skip  # noqa: E501
    _require_finite(now_s, "now_s")
    _require_finite(start_s, "start_s")
    _require_finite(idle_timeout_s, "idle_timeout_s")
    _require_finite(safety_cap_s, "safety_cap_s")
    if idle_timeout_s <= 0 or safety_cap_s <= 0 or now_s < start_s:
        raise ValueError("invalid deadline window parameters")
    candidate = now_s + idle_timeout_s
    hard_limit = start_s + safety_cap_s
    _require_finite(candidate, "candidate")
    _require_finite(hard_limit, "hard_limit")
    return min(candidate, hard_limit)


@dataclass(frozen=True)
class CanonDigestResult:
    has_canon_end_marker: bool; sha256_hex: str  # fmt: skip  # noqa: E702
    byte_length: int; unchanged: bool = False  # fmt: skip  # noqa: E702


def inspect_canon_payload(text: str, marker: str = DEFAULT_CANON_MARKER, previous_sha256: str | None = None) -> CanonDigestResult:  # fmt: skip  # noqa: E501
    clean_marker = marker.strip()
    if not clean_marker:
        raise ValueError("marker must not be empty")
    payload = text.encode("utf-8")
    has_marker = text.rstrip().endswith(clean_marker)
    sha = hashlib.sha256(payload).hexdigest()
    unchanged = bool(has_marker and previous_sha256 is not None and sha == previous_sha256.strip().lower())  # fmt: skip  # noqa: E501
    return CanonDigestResult(has_marker, sha, len(payload), unchanged)
