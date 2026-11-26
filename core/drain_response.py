"""Pure wire-format builders and safe single-line drain diagnostics.

Leaf stdlib module (no I/O, OS, process, or network dependencies) shared by the
hub lifecycle manager, HTTP facade, and sub-bridges to emit unified HTTP 503
drain responses, OpenAI-compatible SSE drain error frames, and sanitized
single-line ``key=value`` diagnostic events.
"""

from __future__ import annotations

from collections.abc import Mapping
import json
import re

from core.drain_policy import resolve_retry_after_s

DRAIN_HTTP_STATUS: int = 503
DEFAULT_DRAIN_MESSAGE: str = "bridge is draining for restart"
DEFAULT_SSE_MODEL: str = "bridge-stream"
DRAIN_HEADER_NAME: str = "X-Bridge-Draining"
DRAIN_HEADER_VALUE: str = "true"
HTTP_ERROR_TYPE: str = "overloaded"
SSE_ERROR_TYPE: str = "overloaded_error"

_MAX_SCAN_LEN: int = 256
_MAX_VALUE_LEN: int = 64
_POS_INF: float = float("inf")
_NEG_INF: float = float("-inf")

_SECRET_HEADER_RE = re.compile(
    r"(?i)\b(?:bearer|basic)\s+\S+"
    + r"|\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token"
    + r"|auth(?:orization)?|token|secret|password|passwd|cookie)\s*[:=]\s*\S+"
)
_SECRET_TOKEN_RE = re.compile(
    r"\b(?:(?:sk|pk|rk)[-_][A-Za-z0-9_.-]{6,}"
    + r"|(?:gh[pousr]|github_pat)_[A-Za-z0-9_]{6,}"
    + r"|xox[baprs]-[A-Za-z0-9-]{6,}"
    + r"|AIza[0-9A-Za-z_-]{16,}"
    + r"|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})"
)
_UNSAFE_CHARS_RE = re.compile(r"[^A-Za-z0-9_.-]+")

ALLOWED_EVENT_FIELDS: frozenset[str] = frozenset(
    {
        "active",
        "active_turns",
        "actor",
        "budget_s",
        "clamped",
        "code",
        "configured_timeout_s",
        "count",
        "drain_elapsed_s",
        "effective_timeout_s",
        "err",
        "error",
        "exit_timeout_s",
        "grace_s",
        "hold_s",
        "interrupted_turns",
        "is_subagent",
        "pgid",
        "pid",
        "ppid",
        "reason",
        "retry_after_s",
        "rid",
        "signal",
        "signal_num",
        "source",
        "state",
        "status",
        "subagent_id",
        "timeout_s",
        "turn_id",
    }
)

__all__ = [
    "ALLOWED_EVENT_FIELDS",
    "DEFAULT_DRAIN_MESSAGE",
    "DEFAULT_SSE_MODEL",
    "DRAIN_HEADER_NAME",
    "DRAIN_HEADER_VALUE",
    "DRAIN_HTTP_STATUS",
    "HTTP_ERROR_TYPE",
    "SSE_ERROR_TYPE",
    "build_drain_http_response",
    "build_drain_sse_error",
    "format_drain_event",
]


def _sanitize_token(raw: str, *, fallback: str = "unknown") -> str:
    """Strip newlines, redact secrets, and restrict to safe single-token chars."""
    head = raw[:_MAX_SCAN_LEN].split("\r", 1)[0].split("\n", 1)[0]
    cleaned = _SECRET_TOKEN_RE.sub("redacted", _SECRET_HEADER_RE.sub("redacted", head))
    token = _UNSAFE_CHARS_RE.sub("_", cleaned).strip("_")[:_MAX_VALUE_LEN]
    return token or fallback


def _format_scalar(value: object) -> str:
    """Render a scalar diagnostic value into a safe single-line token."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        is_finite = value == value and value not in (_POS_INF, _NEG_INF)
        return f"{value:.3f}" if is_finite else "0.000"
    return _sanitize_token(value if isinstance(value, str) else str(value))


def _merge_event_fields(
    fields: Mapping[str, object] | None,
    extra: Mapping[str, object],
) -> dict[str, object]:
    """Keep whitelisted non-None diagnostic fields in insertion order."""
    merged: dict[str, object] = {}
    for source in (fields, extra):
        if source is None:
            continue
        for key, value in source.items():
            if key in ALLOWED_EVENT_FIELDS and value is not None:
                merged[key] = value
    return merged


def build_drain_http_response(
    env: Mapping[str, str],
    *,
    is_subagent: bool = False,
    retry_after_s: int | None = None,
    message: str = DEFAULT_DRAIN_MESSAGE,
    legacy_default: int | None = None,
) -> tuple[int, dict[str, str], dict[str, dict[str, str | int]]]:
    """Build a unified HTTP 503 drain response with bounded Retry-After."""
    retry = resolve_retry_after_s(
        env,
        explicit=retry_after_s,
        is_subagent=is_subagent,
        legacy_default=legacy_default,
    )
    headers = {"Retry-After": str(retry), DRAIN_HEADER_NAME: DRAIN_HEADER_VALUE}
    body: dict[str, dict[str, str | int]] = {
        "error": {
            "message": message or DEFAULT_DRAIN_MESSAGE,
            "type": HTTP_ERROR_TYPE,
            "code": DRAIN_HTTP_STATUS,
        }
    }
    return DRAIN_HTTP_STATUS, headers, body


def build_drain_sse_error(
    env: Mapping[str, str],
    *,
    model: str = "",
    message: str = DEFAULT_DRAIN_MESSAGE,
    is_subagent: bool = False,
    retry_after_s: int | None = None,
) -> str:
    """Build an OpenAI-compatible SSE terminal drain error frame plus [DONE]."""
    retry = resolve_retry_after_s(
        env,
        explicit=retry_after_s,
        is_subagent=is_subagent,
    )
    payload: dict[str, object] = {
        "object": "chat.completion.chunk",
        "model": model or DEFAULT_SSE_MODEL,
        "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
        "error": {
            "message": message or DEFAULT_DRAIN_MESSAGE,
            "type": SSE_ERROR_TYPE,
            "code": DRAIN_HTTP_STATUS,
            "retry_after": retry,
        },
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"data: {encoded}\n\ndata: [DONE]\n\n"


def format_drain_event(
    event: str,
    fields: Mapping[str, object] | None = None,
    **extra: object,
) -> str:
    """Format a single-line sanitized ``event key=value`` drain diagnostic."""
    safe_event = _sanitize_token(event, fallback="drain_event")
    merged = _merge_event_fields(fields, extra)
    parts = [safe_event, *(f"{k}={_format_scalar(v)}" for k, v in merged.items())]
    return " ".join(parts)
