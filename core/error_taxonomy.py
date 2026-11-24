"""Vendor-neutral classification of upstream terminal errors."""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from core.replay_policy import ReplayProof

_QUOTA_RE: Final[re.Pattern[str]] = re.compile(
    r"individual quota reached|usage_limit_reached|resource_exhausted|\bquota\b|\b429\b",
    re.IGNORECASE,
)
_INTERRUPTED_RE: Final[re.Pattern[str]] = re.compile(
    r"\bpi_ai_error\b|\binterrupted\b|upstream[_ -]interrupted", re.IGNORECASE
)
_TRANSPORT_RE: Final[re.Pattern[str]] = re.compile(
    r"connection|network|socket|premature[ _-]?eof|econn(?:reset|refused)|broken pipe",
    re.IGNORECASE,
)
_RETRY_AFTER_RE: Final[re.Pattern[str]] = re.compile(
    r"retry[ -]?after\s*[:=]?\s*(\d+(?:\.\d+)?)", re.IGNORECASE
)
_KEY_NAMES: Final[str] = r"(?:api[_-]?key|apikey|access_token|refresh_token|token|secret|password|authorization|x-api-key)"
_SECRET_RE: Final[re.Pattern[str]] = re.compile(
    rf"((?:\\?[\"']?{_KEY_NAMES}\\?[\"']?)\s*[:=]\s*)"
    r'(?:(\\")((?:bearer|basic)\s+)?(?:(?!\\").)*(?:\\"|$)|'
    r"(\\')((?:bearer|basic)\s+)?(?:(?!\\').)*(?:\\'|$)|"
    r'(")((?:bearer|basic)\s+)?(?:\\.|[^"\\])*(?:"|$)|'
    r"(')((?:bearer|basic)\s+)?(?:\\.|[^'\\])*(?:'|$)|"
    r"((?:bearer|basic)\s+)?[^\s,;\"'\\]+)|"
    r"(bearer\s+)[a-z0-9._~+/=-]+|"
    r"(?:sk-[a-z0-9_-]{8,}|ghp_[a-z0-9]{8,}|eyj[a-z0-9_-]+\.[a-z0-9_-]+\.[a-z0-9_-]+)",
    re.IGNORECASE,
)
_REQUEST_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_CANCELLATION_MARKERS: Final[tuple[tuple[str, str], ...]] = (
    ("client_disconnect", "client_disconnect"),
    ("client disconnected", "client_disconnect"),
    ("user_cancel", "user_cancel"),
    ("cancelled by user", "user_cancel"),
    ("supervisor_drain", "supervisor_drain"),
    ("supervisor drain", "supervisor_drain"),
    ("timeout", "timeout"),
    ("upstream_interrupted", "upstream_interrupted"),
    ("upstream interrupted", "upstream_interrupted"),
)


@dataclass(frozen=True)
class ClassifiedError:
    """Structured OpenAI-compatible error plus internal retry semantics."""

    category: str
    http_status: int
    type: str
    code: str | int
    message: str
    retryable: bool
    retry_after: int | None = None
    request_id: str = ""
    cancellation_subtype: str | None = None

    def error_body(self) -> dict[str, object]:
        """Render the public error object without internal retry state."""
        body: dict[str, object] = {
            "message": self.message,
            "type": self.type,
            "code": self.code,
        }
        if self.request_id:
            body["request_id"] = self.request_id
        if self.retry_after is not None:
            body["retry_after"] = self.retry_after
        if self.cancellation_subtype is not None:
            body["cancellation_subtype"] = self.cancellation_subtype
        return body

    def response_headers(self) -> dict[str, str]:
        """Render additive correlation and retry headers."""
        headers = {"X-Request-Id": self.request_id} if self.request_id else {}
        if self.retry_after is not None:
            headers["Retry-After"] = str(self.retry_after)
        return headers


def classify_upstream_error(
    error: object,
    status_code: int | None = None,
    headers: Mapping[str, object] | None = None,
    request_id: object = "",
    replay_proof: ReplayProof | None = None,
) -> ClassifiedError:
    """Classify an upstream failure; uncertain outcomes are terminal."""
    message = sanitize_error_text(error)
    safe_id = _sanitize_request_id(request_id)
    retry_after = _retry_after(message, headers)
    if status_code == 429 or _QUOTA_RE.search(message):
        return ClassifiedError(
            "QUOTA", 429, "quota_exhausted", "QUOTA", message,
            False, retry_after, safe_id,
        )
    if _INTERRUPTED_RE.search(message):
        subtype = cancellation_subtype(message)
        return ClassifiedError(
            "PI_AI_ERROR", 502, "agy_error", 502, message,
            False, None, safe_id, subtype,
        )
    if _TRANSPORT_RE.search(message):
        retryable = bool(replay_proof is not None and replay_proof.allow_retry)
        return ClassifiedError(
            "TRANSPORT", 502, "agy_error", 502, message,
            retryable, None, safe_id,
        )
    return ClassifiedError(
        "UPSTREAM", 502, "agy_error", 502,
        message, False, None, safe_id,
    )


def sanitize_error_text(error: object, max_length: int = 500) -> str:
    """Keep diagnostic wording while removing common credential forms."""
    text = str(error or "upstream error").replace("\x00", "")
    text = _SECRET_RE.sub(_redact_secret, text)
    text = " ".join(text.split())
    return text[:max_length] or "upstream error"


def cancellation_subtype(error: object) -> str:
    """Return a causal subtype only when the sanitized text proves it."""
    lowered = sanitize_error_text(error).lower()
    for marker, subtype in _CANCELLATION_MARKERS:
        if marker in lowered:
            return subtype
    return "unspecified"


def error_response(error: ClassifiedError) -> tuple[int, dict[str, object], dict[str, str]]:
    """Return status, OpenAI envelope and response headers for HTTP facades."""
    return error.http_status, {"error": error.error_body()}, error.response_headers()


def upstream_error_body(
    error: object,
    request_id: object = "",
    status_code: int | None = None,
    headers: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Thin-facade shape carrying HTTP metadata outside the public body."""
    classified = classify_upstream_error(error, status_code, headers, request_id)
    body = classified.error_body()
    body.update(_status=classified.http_status, _headers=classified.response_headers())
    return body


def extract_upstream_error_meta(
    out: Mapping[str, object],
) -> tuple[int | None, Mapping[str, object] | None]:
    """Prefer non-null canonical metadata, falling back to legacy fields."""
    status = out.get("upstream_status_code")
    headers = out.get("upstream_headers")
    if status is None:
        status = out.get("status_code")
    if headers is None:
        headers = out.get("headers")
    return (
        status if type(status) is int else None,
        dict(headers.items()) if callable(getattr(headers, "items", None)) else None,
    )


def is_precommit_transport_error(error: object) -> bool:
    """Identify transport errors; the caller must separately prove pre-commit facts."""
    return classify_upstream_error(error).category == "TRANSPORT"


def blocks_pre_delivery_replay(error: object) -> bool:
    """Block legacy pre-delivery replay only for terminal incident classes."""
    return classify_upstream_error(error).category in {"QUOTA", "PI_AI_ERROR"}


def _retry_after(message: str, headers: Mapping[str, object] | None) -> int | None:
    raw = _header(headers, "retry-after")
    if raw is None and (match := _RETRY_AFTER_RE.search(message)):
        raw = match.group(1)
    try:
        parsed = int(float(str(raw).strip()))
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if parsed >= 0 else None


def _header(headers: Mapping[str, object] | None, name: str) -> object | None:
    items_fn = getattr(headers, "items", None)
    if not callable(items_fn):
        return None
    return next((value for key, value in items_fn() if str(key).lower() == name), None)


def _sanitize_request_id(value: object) -> str:
    text = str(value) if isinstance(value, str) else ""
    return text if _REQUEST_ID_RE.fullmatch(text) else ""


def _redact_secret(match: re.Match[str]) -> str:
    if match.group(1):
        quote = match.group(2) or match.group(4) or match.group(6) or match.group(8) or ""
        scheme = match.group(3) or match.group(5) or match.group(7) or match.group(9) or match.group(10) or ""
        return f"{match.group(1)}{quote}{scheme}[REDACTED]{quote}"
    return (match.group(11) or "") + "[REDACTED]"


# Short aliases are useful to transports while retaining descriptive public names.
classify_error = classify_upstream_error
normalize_upstream_error = classify_upstream_error
