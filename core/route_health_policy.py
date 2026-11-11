# ruff: noqa: E501,E701,E702
# fmt: off
from __future__ import annotations

import hashlib
import html
import math
import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal
from enum import Enum
from typing import Final


class EffortLevel(str, Enum):  # noqa: UP042
    LOW = "low"; MEDIUM = "medium"; HIGH = "high"
class FailureCategory(str, Enum):  # noqa: UP042
    AUTH_REFRESH_EXHAUSTED = "AUTH_REFRESH_EXHAUSTED"; LIMIT_BLOCKED = "LIMIT_BLOCKED"
    UPSTREAM_TLS_STALL = "UPSTREAM_TLS_STALL"; CAPACITY_EXHAUSTED = "CAPACITY_EXHAUSTED"
    FATAL_REQUEST_ERROR = "FATAL_REQUEST_ERROR"
class HealthReason(str, Enum):  # noqa: UP042
    READY = "READY"; LIMIT_BLOCKED = "LIMIT_BLOCKED"
    STALE_HEALTH_PROBE = "STALE_HEALTH_PROBE"; ENV_DRIFT_DETECTED = "ENV_DRIFT_DETECTED"
class RetryReason(str, Enum):  # noqa: UP042
    BUDGET_OK = "BUDGET_OK"; BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    NON_RETRYABLE_CATEGORY = "NON_RETRYABLE_CATEGORY"
    MAX_ATTEMPTS_REACHED = "MAX_ATTEMPTS_REACHED"
DEFAULT_CANON_MARKER: Final[str] = "<!-- КАНОН-КОНЕЦ -->"
REDACTED_TOKEN: Final[str] = "<redacted>"
MAX_DIAGNOSTIC_CHARS: Final[int] = 256
_EFFORTS: Final[frozenset[str]] = frozenset(item.value for item in EffortLevel)
_CAPACITY_STATUSES: Final[frozenset[int]] = frozenset((429, 502, 503, 504))
def _spaced(value: str) -> str:
    glue = r"(?:[\s\\]|\\[bfnrtv])*"
    return glue.join(value).replace(f"{glue}_{glue}", r"(?:[\s\\_-]|\\[bfnrtv])*")
_LEAD: Final[str] = r"(?:\\[bfnrtv]|\\)*"
_BOUND: Final[str] = r"(?:(?<=\\[bfnrtv])|\b|\\+)"
_K_SPACED: Final[str] = "|".join(map(_spaced, "private_key secret_key access_key signing_key master_key encryption_key session_key ssh_key passphrase refresh_token access_token id_token client_secret x_api_key api_key password passwd pwd secret token".split()))
_K_PLAIN: Final[str] = _K_SPACED
_STOP_TOK: Final[str] = rf"{_spaced('basic')}\b|{_spaced('bearer')}\b|ya29\.|1//|sk-|AIza|[a-z0-9_.\[\]-]+\s*[:=]|[^\s@]+@[^\s@]+\.[^\W\d_]{{2,}}"  # noqa: E501
_SECRET_PATTERNS: Final[tuple[str, ...]] = (r"(?i)(?:(?<=\\[bfnrtv])|(?<![/:a-z0-9+.-]))[a-z][a-z0-9+.-]*://(?!\s)(?:[^\s]+(?:\s+(?![a-z][a-z0-9+.-]*://)[^\s]+){0,4}@[^\s\"']*|[^\s/\"'@:]*:(?![0-9]{1,5}(?:[/?#\s\"']|$))[^\s/\"'@]+)", rf"(?i)(?:\\*[\"'])?[a-z0-9_.-]{{0,32}}{_LEAD}{_spaced('authorization')}(?:\\*[\"'\[\]0-9a-z_.-])*\s*[:=]\s*[^\r\n]+", rf"(?i){_BOUND}(?:{_spaced('bearer')}|{_spaced('basic')})\s+\S+(?:\s+(?!{_STOP_TOK})\S+)*", rf"(?i)(?:\\*[\"'])?[a-z0-9_.-]{{0,32}}{_LEAD}{_spaced('cookie')}(?:\\*[\"'\[\]0-9a-z_.-])*\s*[:=]\s*[^\r\n]+", rf"(?i)(?:\\*[\"'])?[a-z0-9_.-]{{0,32}}{_LEAD}(?:{_K_SPACED})(?:\\*[\"'\[\]0-9a-z_.-])*\s*%*\s*[:=]\s*[^\r\n]+", rf"(?i){_BOUND}(?:{_spaced('invalid')}|{_spaced('expired')}|{_spaced('bad')}|{_spaced('revoked')}|{_spaced('leaked')})\s+{_LEAD}(?:{_K_SPACED})\b(?!\s+(?:count|limit|length|size|budget|number)\b)\s+\S+", rf"(?i)(?:^|(?<=[\s\"'\[\(,;]))(?:--?[a-z0-9_-]{{0,32}}{_LEAD}(?:{_K_PLAIN})[a-z0-9_-]{{0,32}}|-[pk](?=(?:\\*[\"']\s*,\s*|\s+)(?![0-9]+\b)))(?:\\*[\"']\s*,\s*|[\s=]+)\S+(?:\s+(?!--?[a-z0-9]|{_STOP_TOK})\S+)*", rf"(?i)<\s*(?:[a-z0-9_.-]{{1,32}}:)?[a-z0-9_.-]{{0,32}}{_LEAD}(?:{_K_PLAIN}|{_spaced('cookie')}|{_spaced('authorization')})[a-z0-9_.-]{{0,32}}\b[^>]*>[^\r\n]*", r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|$)", rf"{_BOUND}eyJ[A-Za-z0-9_-]{{4,}}\.eyJ[A-Za-z0-9_-]{{4,}}\.[A-Za-z0-9._-]*", rf"{_BOUND}(?:ya29\.[A-Za-z0-9._-]+|1//[A-Za-z0-9._-]+|sk-[A-Za-z0-9._-]+|AIza[A-Za-z0-9_-]+|gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|xox[aboprs]-[A-Za-z0-9-]+|(?:sk|rk)_(?:live|test)_[A-Za-z0-9]+|AKIA[0-9A-Z]{{16}}|glpat-[A-Za-z0-9._-]+|npm_[A-Za-z0-9]+|hf_[A-Za-z0-9]+|pypi-[A-Za-z0-9_-]+)", r"(?:\\+[bfnrtv]|(?<![\w.!#$%&'*+/=?^`{|}~-]))[\w.!#$%&'*+/=?^`{|}~-]+@[\w.-]+\.[^\W\d_]{2,}\b")
_SECRET_REGEXES: Final[tuple[re.Pattern[str], ...]] = tuple(re.compile(pattern) for pattern in _SECRET_PATTERNS)
_URL_SECRET_HINT_RE: Final[re.Pattern[str]] = re.compile(r"://[^\s/\"'@:]*:[^/\s\"'@]", re.IGNORECASE)
def _has_url_userinfo(text: str) -> bool: return any((pos := (window := "".join(tokens[index : index + 5])).find("://")) >= 0 and window.find("@", pos + 3) >= 0 for index in range(len(tokens))) if (tokens := re.split(r"\s+", text)) else False
_INVISIBLE_RE: Final[re.Pattern[str]] = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u00ad\u0300-\u036f\u061c\u115f\u1160\u17b4\u17b5\u180b-\u180f\u1ab0-\u1aff\u1dc0-\u1dff\u200b-\u200f\u202a-\u202e\u2060-\u206f\u20d0-\u20ff\u3164\ud800-\udfff\ufe00-\ufe2f\ufeff\uffa0\ufff0-\ufffb]+")
_WS_RE: Final[re.Pattern[str]] = re.compile(r"[\x00-\x06\x08-\x1a\x1c-\x20\x7f\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+")  # noqa: E501
@dataclass(frozen=True)
class NormalizedModelRoute:
    canonical_model: str; reasoning_effort: str | None
    alias_applied: bool
def _match_known(target: str, known_models: Collection[str]) -> str | None:
    lowered = target.lower()
    matches = sorted((c != target, c) for item in known_models if (c := item.strip()) and c.lower() == lowered)
    return matches[0][1] if matches else None
def _resolve_route_suffix(model: str, explicit: str | None, allowed: frozenset[str], known_models: Collection[str] | None) -> NormalizedModelRoute:
    if known_models is not None and (exact := _match_known(model, known_models)) is not None: return NormalizedModelRoute(exact, explicit, False)
    for suffix in sorted(allowed, key=len, reverse=True):
        marker = f"-{suffix}"
        if len(model) > len(marker) and model.lower().endswith(marker):
            base, effort = model[: -len(marker)], explicit or suffix
            canon = base if known_models is None else _match_known(base, known_models)
            if canon is not None: return NormalizedModelRoute(canon, effort, True)
    return NormalizedModelRoute(model, explicit, False)
def normalize_model_route(model_id: str, explicit_effort: str | None = None, allowed_suffixes: Collection[str] | None = None, known_models: Collection[str] | None = None) -> NormalizedModelRoute:
    model = model_id.strip()
    if len(model.split()) != 1 or _INVISIBLE_RE.search(model):
        raise ValueError("model_id must not be empty or contain whitespace")
    allowed = _EFFORTS
    if allowed_suffixes is not None:
        allowed = frozenset(s for suffix in allowed_suffixes if (s := suffix.strip().lower()) and len(s.split()) == 1 and not _INVISIBLE_RE.search(s))
    explicit = explicit_effort.strip().lower() if explicit_effort is not None else None
    if explicit is not None and explicit not in allowed:
        raise ValueError("explicit_effort is not in allowed_suffixes")
    return _resolve_route_suffix(model, explicit, allowed, known_models)
_ANSI_RE: Final[re.Pattern[str]] = re.compile(r"(?:(?:\x1b|\\+(?:u001|x1)[bB])\[|(?:\x9b|\\+(?:u009|x9)[bB]))[0-?]*[ -/]*[@-~]|(?:\x1b|\\+(?:u001|x1)[bB])[\]P_X^][^\x07\x1b\x9c\\]*(?:\x07|\x9c|\x1b\\|\\+(?:u0007|x07|u009[cC]|x9[cC])|\\+(?:u001|x1)[bB]\\\\)|(?:\x1b|\\+(?:u001|x1)[bB])[\]P_X^]")
_PCT_RUN_RE: Final[re.Pattern[str]] = re.compile(r"(?:%[0-9a-fA-F]{2})+")
_ESCAPE_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"(?:\\+|%)[uU]((?<=U)[0-9a-fA-F]{8}|[0-9a-fA-F]{4})|\\+x([0-9a-fA-F]{2})|\\+([0-7]{1,3})|&#(?:[xX]([0-9a-fA-F]{1,6})(?![0-9a-fA-F])|([0-9]{1,7})(?![0-9]));?")
_BS_STRIP_RE: Final[re.Pattern[str]] = re.compile(r"\\+(?=(?:[^uUx0-7bfnrtv\"'\\]|u(?![0-9a-fA-F]{4})|U(?![0-9a-fA-F]{4})|x(?![0-9a-fA-F]{2})))")  # noqa: E501
_CTRL_ESC_RE: Final[re.Pattern[str]] = re.compile(r"\\+([bfnrtv])")
_HTTP_CODE_RE_TPL: Final[str] = r"(?:\bhttp(?:[/\s]*\d(?:\.\d)?)?\s+{}\b|(?:\\*[\"'])?\bstatus(?:[_ -]?code)?\b(?:\\*[\"'])?\s*[:=]\s*{}\b|(?:^\s*|\b(?:error|code)\s*:\s*){}\b)"
def _reject_oversize(fail_closed: bool, text: str, limit: int) -> bool:
    return fail_closed and len(text) > limit
def _has_residual_encoding(safe: str) -> bool:
    entities = re.search(rf"(?i)(?:{_K_PLAIN})&+=", safe)
    escapes = re.search(r"(?:\\+|%)[uU][0-9a-fA-F]{4,8}|\\+(?:x[0-9a-fA-F]{2}|[0-7]{1,3})|%[0-9a-fA-F]{2}|&#[xX]?[0-9a-fA-F]+|[\x1b\x90\x98\x9b-\x9f]", safe)
    return any((html.unescape(safe) != safe, entities, escapes))
def _decode_pct(match: re.Match[str]) -> str:
    return "".join(" " if ch in "\t\r\n\u2028\u2029" else ch if ch in "\x07\x1b\x9b\x9c" else "" if ord(ch) <= 0x1F or 0x7F <= ord(ch) <= 0x9F or _INVISIBLE_RE.fullmatch(ch) else ch for ch in bytes.fromhex(match.group(0).replace("%", "")).decode("utf-8", "replace"))
def _decode_escape(match: re.Match[str]) -> str:
    hex_s, oct_s, dec_s = match.group(1) or match.group(2) or match.group(4), match.group(3), match.group(5)
    code = int(hex_s, 16) if hex_s else (int(oct_s, 8) if oct_s else int(dec_s, 10))
    if code in (0x09, 0x0A, 0x0D, 0x2028, 0x2029): return " "
    if code in (0x07, 0x1B, 0x9B, 0x9C): return chr(code)
    if code <= 0x1F or 0x7F <= code <= 0x9F or code > 0x10FFFF or 0xD800 <= code <= 0xDFFF or _INVISIBLE_RE.fullmatch(chr(code)): return ""
    return chr(code)
def _normalize_diagnostic_text(raw_text: str, *, max_len: int = 4096, fail_closed: bool = True) -> str:
    if _reject_oversize(fail_closed, raw_text, 4194304): return REDACTED_TOKEN
    if raw_text.isascii() and raw_text.isprintable() and not any(ch in raw_text for ch in "\\%&"): return REDACTED_TOKEN if _reject_oversize(fail_closed, safe := _WS_RE.sub(" ", raw_text), max_len) else safe[:max_len]
    cleaned = _WS_RE.sub(" ", _INVISIBLE_RE.sub("", _ANSI_RE.sub("", raw_text[:4194304])))
    safe = f"{cleaned[:1048576]} {cleaned[-65536:]}" if not fail_closed and len(cleaned) > 1048576 else cleaned
    for _ in range(8):
        previous = safe; safe = _PCT_RUN_RE.sub(_decode_pct, safe); safe = _ESCAPE_TOKEN_RE.sub(_decode_escape, safe)
        safe = html.unescape(_BS_STRIP_RE.sub("", _CTRL_ESC_RE.sub(lambda m: f"\\{m.group(1)}", safe)))
        safe = _WS_RE.sub(" ", _INVISIBLE_RE.sub("", _ANSI_RE.sub("", safe)))
        if fail_closed and any(ch in safe for ch in "\x1b\x90\x98\x9b\x9c"): return REDACTED_TOKEN
        if previous == safe: break
    else:
        if fail_closed: return REDACTED_TOKEN
    if _reject_oversize(fail_closed, safe, max_len): return REDACTED_TOKEN
    if fail_closed and _has_residual_encoding(safe): return REDACTED_TOKEN
    return safe[:max_len]
def _redact_patterns(text: str) -> str:
    regexes = _SECRET_REGEXES if "@" in text else (_SECRET_REGEXES[:-1] if _URL_SECRET_HINT_RE.search(text) else _SECRET_REGEXES[1:-1]); has_url_secret = bool(_URL_SECRET_HINT_RE.search(text)) or _has_url_userinfo(text); chars = frozenset(text.lower())
    if not (has_url_secret or ("@" in text and "." in text) or "-" in text or ("<" in text and ">" in text) or "eyJ" in text or any(marker in text for marker in ("ya29.", "1//", "AIza", "ghp_", "gho_", "ghu_", "ghs_", "ghr_", "github_pat_", "xoxa-", "xoxb-", "xoxo-", "xoxp-", "xoxr-", "xoxs-", "sk_", "rk_", "AKIA", "glpat-", "npm_", "hf_", "pypi-")) or any(frozenset(word.replace("_", "")) <= chars for word in "authorization bearer basic cookie invalid expired bad revoked leaked private_key secret_key access_key signing_key master_key encryption_key session_key ssh_key passphrase refresh_token access_token id_token client_secret x_api_key api_key password passwd pwd secret token".split())): return text
    has_kv = ":" in text or "=" in text
    for regex in regexes:
        if (regex is _SECRET_REGEXES[0] and not has_url_secret) or (regex is _SECRET_REGEXES[6] and "-" not in text) or (regex is _SECRET_REGEXES[7] and ("<" not in text or ">" not in text)): continue
        if has_kv or regex not in (_SECRET_REGEXES[1], _SECRET_REGEXES[3], _SECRET_REGEXES[4]): text = regex.sub(REDACTED_TOKEN, text)
    return text
def redact_diagnostic_text(raw_text: str) -> str:
    if _reject_oversize(True, raw_text, 4194304): return REDACTED_TOKEN
    normalized = _normalize_diagnostic_text(raw_text, max_len=1048576, fail_closed=True)
    unfolded = _CTRL_ESC_RE.sub(" ", _redact_patterns(normalized))
    safe = _redact_patterns(unfolded)
    return safe[:MAX_DIAGNOSTIC_CHARS] or (" " if raw_text else "")
@dataclass(frozen=True)
class FailureClassification:
    category: FailureCategory; retryable: bool
    failover_eligible: bool; sanitized_reason: str
def _is_auth_failure(status_code: int, reason: str) -> bool:
    auth_re = r"token\s*refresh\s+failed|oauth\s+refresh|invalid_grant|invalid\s+api\s+key|api\s+key\s+(?:not\s+valid|expired)|api_key_invalid|unauthorized|unauthenticated|\binvalid\s+token\b(?!\s+(?:count|limit|length|size|budget|number)\b)"
    code_401 = status_code == 401 or (status_code == 0 and bool(re.search(_HTTP_CODE_RE_TPL.format(401, 401, 401), reason)))
    code_403 = status_code == 403 or (status_code == 0 and bool(re.search(_HTTP_CODE_RE_TPL.format(403, 403, 403), reason)))
    return bool(re.search(auth_re, reason)) or code_401 or (code_403 and bool(re.search(r"oauth|refresh|unauthenticated", reason)))
def classify_provider_failure(status_code: int, raw_reason: str) -> FailureClassification:
    normalized = _normalize_diagnostic_text(raw_reason, max_len=1114113, fail_closed=False)
    reason = " ".join((_CTRL_ESC_RE.sub(" ", normalized), _CTRL_ESC_RE.sub(r"\1", normalized), raw_reason[:4194304])).lower()
    sanitized = redact_diagnostic_text(raw_reason)
    if _is_auth_failure(status_code, reason):
        values = (FailureCategory.AUTH_REFRESH_EXHAUSTED, False, True, sanitized)
    elif any(term in reason for term in ("limit-blocked", "quota exceeded", "spending cap")):
        values = (FailureCategory.LIMIT_BLOCKED, False, True, sanitized)
    elif "ssl_error_syscall" in reason or "tls handshake timeout" in reason:
        values = (FailureCategory.UPSTREAM_TLS_STALL, False, True, sanitized)
    elif status_code in _CAPACITY_STATUSES or "model_capacity_exhausted" in reason or (status_code == 0 and bool(re.search(_HTTP_CODE_RE_TPL.format(*((r"(?:429|502|503|504)",) * 3)), reason))):
        values = (FailureCategory.CAPACITY_EXHAUSTED, True, True, sanitized)
    else:
        values = (FailureCategory.FATAL_REQUEST_ERROR, False, False, sanitized)
    return FailureClassification(*values)
@dataclass(frozen=True)
class RouteHealthStatus:
    model_id: str; available: bool
    status_reason: HealthReason; env_drift_keys: tuple[str, ...]
def _route_targets(model_id: str | NormalizedModelRoute, known_models: Collection[str] | None = None) -> tuple[str, frozenset[str]]:
    route = model_id if isinstance(model_id, NormalizedModelRoute) else normalize_model_route(model_id, known_models=known_models)
    canon, eff = route.canonical_model.strip(), route.reasoning_effort
    if len(canon.split()) != 1 or _INVISIBLE_RE.search(canon) or (eff is not None and (len(eff.strip().split()) != 1 or bool(_INVISIBLE_RE.search(eff)))): raise ValueError("invalid NormalizedModelRoute")
    alias = f"{canon}-{eff.strip().lower()}".lower() if eff else canon.lower()
    return canon, frozenset((canon.lower(), alias))
def evaluate_route_health(model_id: str | NormalizedModelRoute, blocked_models: tuple[str, ...], probe_age_s: float, max_stale_age_s: float, env_drift_keys: tuple[str, ...] = (), known_models: Collection[str] | None = None) -> RouteHealthStatus:
    _require_finite(probe_age_s, "probe_age_s")
    _require_finite(max_stale_age_s, "max_stale_age_s")
    if max_stale_age_s < 0:
        raise ValueError("max_stale_age_s must be non-negative")
    canonical, targets = _route_targets(model_id, known_models)
    blocked = {item.strip().lower() for item in blocked_models if item.strip()}
    drift = tuple(sorted({k for key in env_drift_keys if (k := key.strip())}))
    if targets & blocked:
        reason = HealthReason.LIMIT_BLOCKED
    elif not 0 <= probe_age_s <= max_stale_age_s:
        reason = HealthReason.STALE_HEALTH_PROBE
    elif drift:
        reason = HealthReason.ENV_DRIFT_DETECTED
    else:
        return RouteHealthStatus(canonical, True, HealthReason.READY, drift)
    return RouteHealthStatus(canonical, False, reason, drift)
def detect_effective_env_drift(expected_env: Mapping[str, str], live_env: Mapping[str, str], tracked_keys: tuple[str, ...]) -> tuple[str, ...]:
    changed = {k for key in tracked_keys if (k := key.strip()) and expected_env.get(k) != live_env.get(k)}
    return tuple(sorted(changed))
@dataclass(frozen=True)
class RetryBudgetConfig:
    total_budget_s: float = 90.0; reserve_s: float = 5.0
    min_attempt_budget_s: float = 4.0; max_attempts: int = 3
    idle_timeout_s: float = 30.0
@dataclass(frozen=True)
class AttemptDecision:
    allow_retry: bool
    attempt_budget_s: float
    reason: RetryReason
def _require_finite(value: float, field: str) -> None:
    try: finite = type(value) in (int, float) and math.isfinite(value)
    except OverflowError: finite = False
    if not finite:
        raise ValueError(f"{field} must be finite")
def validate_retry_config(config: RetryBudgetConfig) -> RetryBudgetConfig:
    _require_finite(config.total_budget_s, "total_budget_s")
    _require_finite(config.reserve_s, "reserve_s")
    _require_finite(config.min_attempt_budget_s, "min_attempt_budget_s")
    _require_finite(config.idle_timeout_s, "idle_timeout_s")
    invalid = (not 0 < config.total_budget_s <= 86400.0, config.reserve_s < 0 or config.reserve_s >= config.total_budget_s, not 0.001 <= config.min_attempt_budget_s <= 86400.0, Decimal(str(config.min_attempt_budget_s)) > Decimal(str(config.total_budget_s)) - Decimal(str(config.reserve_s)), type(config.max_attempts) is not int or not 1 <= config.max_attempts <= 1000, not 0 < config.idle_timeout_s <= 86400.0)
    if any(invalid):
        raise ValueError("invalid retry budget configuration")
    return config
def compute_attempt_decision(config: RetryBudgetConfig, attempt_index: int, elapsed_s: float, last_failure_category: str | None = None) -> AttemptDecision:
    _ = validate_retry_config(config)
    _require_finite(elapsed_s, "elapsed_s")
    if type(attempt_index) is not int or attempt_index < 0 or elapsed_s < 0:
        raise ValueError("attempt_index and elapsed_s must be non-negative")
    if last_failure_category not in (None, FailureCategory.CAPACITY_EXHAUSTED):
        return AttemptDecision(False, 0.0, RetryReason.NON_RETRYABLE_CATEGORY)
    if attempt_index >= config.max_attempts:
        return AttemptDecision(False, 0.0, RetryReason.MAX_ATTEMPTS_REACHED)
    usable_dec = Decimal(str(config.total_budget_s)) - Decimal(str(config.reserve_s)) - Decimal(str(elapsed_s))
    if usable_dec <= 0:
        return AttemptDecision(False, 0.0, RetryReason.BUDGET_EXHAUSTED)
    budget_s = float((usable_dec / Decimal(config.max_attempts - attempt_index)).quantize(Decimal("0.001"), rounding=ROUND_FLOOR))
    if budget_s < config.min_attempt_budget_s:
        return AttemptDecision(False, 0.0, RetryReason.BUDGET_EXHAUSTED)
    return AttemptDecision(True, budget_s, RetryReason.BUDGET_OK)
def advance_sliding_deadline(now_s: float, start_s: float, idle_timeout_s: float, safety_cap_s: float) -> float:
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
    has_canon_end_marker: bool; sha256_hex: str
    byte_length: int; unchanged: bool = False
def inspect_canon_payload(text: str, marker: str = DEFAULT_CANON_MARKER, previous_sha256: str | None = None) -> CanonDigestResult:
    clean_marker = marker.strip()
    if not clean_marker:
        raise ValueError("marker must not be empty")
    payload = text.encode("utf-8", "replace")
    has_marker = text.rstrip().endswith(clean_marker)
    sha = hashlib.sha256(payload).hexdigest()
    unchanged = bool(has_marker and previous_sha256 is not None and sha == previous_sha256.strip().lower())
    return CanonDigestResult(has_marker, sha, len(payload), unchanged)
