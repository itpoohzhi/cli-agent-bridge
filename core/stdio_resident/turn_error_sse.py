"""SSE error-фрейм и HTTP-статус для сбоя резидентного хода (в т.ч. до первого чанка)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Final

from core.codex_zero_canon_policy import (
    ERR_TOOL_EVENT_FORBIDDEN,
    ERROR_TAXONOMY,
    CodexZeroCanonPolicyError,
    classify_error,
)
from core.log_redaction import redact_log_text
from core.runtime_env import positive_int
from core.stdio_resident.process_pool import SlotLeaseTimeoutError

DONE_FRAME: Final[str] = "data: [DONE]\n\n"
DEFAULT_ERROR_MAX_CHARS: Final[int] = 500
ERROR_MAX_CHARS_ENV: Final[str] = "BRIDGE_STDIO_ERROR_MAX_CHARS"

_RATE_LIMIT_MARKERS: Final[tuple[str, ...]] = (
    "429",
    "rate limit",
    "rate_limit",
    "quota",
    "too many requests",
)
_PROTOCOL_MARKERS: Final[tuple[str, ...]] = (
    "handshake",
    "malformed json",
    "invalid json",
    "resident_protocol_failed",
    "protocol failed",
)
_INCOMPLETE_MARKERS: Final[tuple[str, ...]] = (
    "eof",
    "empty done",
    "missing terminal",
    "incomplete stream",
    "unexpected end",
    "ended before the terminal marker",
    "upstream_incomplete_stream",
)
_SAFE_ERROR_CODES: Final[frozenset[str]] = frozenset(
    (
        *ERROR_TAXONOMY.keys(),
        "zero_canon_unsupported_by_driver",
        "zero_canon_attestation_failed",
        "invalid_review_profile",
        "unsupported_model_effort",
        "output_limit_exceeded",
        "resident_turn_failed",
        "slot_lease_timeout",
        "turn_timeout",
        "rate_limit_exceeded",
    )
)


@dataclass(frozen=True, slots=True)
class TurnErrorResponse:
    """Готовый ответ: статус (200, если заголовки уже ушли), SSE-фрейм и JSON-тело."""

    status: int
    error_type: str
    code: str
    message: str
    sse: str
    body: dict[str, object]


def _error_type_for(status: int, code: str) -> str:
    if code == ERR_TOOL_EVENT_FORBIDDEN:
        return "policy_error"
    if code == "output_limit_exceeded":
        return "resource_limit_error"
    if status == 504 or code.endswith("_timeout"):
        return "timeout_error"
    if status == 429:
        return "rate_limit_error"
    if status == 503:
        return "service_unavailable"
    if status == 400:
        return "invalid_request_error"
    return "upstream_error"


def _classify_typed_error(error: BaseException) -> tuple[int, str, str] | None:
    if isinstance(error, ResidentTurnError):
        resp = error.response
        return resp.status, resp.error_type, resp.code
    if isinstance(error, SlotLeaseTimeoutError):
        return 503, "service_unavailable", "slot_lease_timeout"
    if isinstance(error, CodexZeroCanonPolicyError):
        return (
            error.http_status,
            _error_type_for(error.http_status, error.code),
            error.code,
        )
    code = getattr(error, "code", None)
    if isinstance(code, str) and code:
        default_status = ERROR_TAXONOMY[code][0] if code in ERROR_TAXONOMY else 502
        raw_status = getattr(error, "http_status", default_status)
        status = raw_status if isinstance(raw_status, int) else default_status
        return status, _error_type_for(status, code), code
    timeout_kind = getattr(error, "timeout_kind", None)
    if isinstance(timeout_kind, str) and timeout_kind:
        classified = classify_error(str(error), timeout_kind=timeout_kind)
        return classified.http_status, "timeout_error", classified.error_class
    return None


def _resolve_timeout_code(lower_text: str) -> str:
    if "first_progress" in lower_text or "first-progress" in lower_text:
        return "first_progress_timeout"
    if "safety_cap" in lower_text or "safety cap" in lower_text:
        return "safety_cap_timeout"
    if "idle_timeout" in lower_text:
        return "idle_timeout"
    return "turn_timeout"


_TIMEOUT_CODE_NAMES: Final[tuple[str, ...]] = (
    "first_progress_timeout",
    "idle_timeout",
    "safety_cap_timeout",
)


def _has_marker(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _match_timeout_code(lower: str) -> str | None:
    return next((code for code in _TIMEOUT_CODE_NAMES if code in lower), None)


def _classify_message_text(lower: str) -> tuple[int, str, str]:
    if ERR_TOOL_EVENT_FORBIDDEN in lower:
        return 502, "policy_error", ERR_TOOL_EVENT_FORBIDDEN
    if "output_limit_exceeded" in lower:
        return 502, "resource_limit_error", "output_limit_exceeded"
    if "slot_lease_timeout" in lower or "waiting for a resident process slot" in lower:
        return 503, "service_unavailable", "slot_lease_timeout"
    if "no available accounts" in lower or "credential_unavailable" in lower:
        return 503, "service_unavailable", "credential_unavailable"
    if _has_marker(lower, _RATE_LIMIT_MARKERS):
        classified = classify_error(lower, status_code=429)
        return classified.http_status, "rate_limit_error", classified.error_class
    if _has_marker(lower, _INCOMPLETE_MARKERS):
        return 502, "upstream_error", "upstream_incomplete_stream"
    if _has_marker(lower, _PROTOCOL_MARKERS):
        return 502, "upstream_error", "resident_protocol_failed"
    if (timeout_code := _match_timeout_code(lower)) is not None:
        return 504, "timeout_error", timeout_code
    return 502, "upstream_error", "resident_turn_failed"


def classify_turn_error(error: BaseException) -> tuple[int, str, str]:
    """Возвращает `(status, error_type, code)` по семантике сбоя, не по имени агента."""
    typed = _classify_typed_error(error)
    if typed is not None:
        return typed
    lower = str(error).lower()
    if isinstance(error, TimeoutError):
        return 504, "timeout_error", _resolve_timeout_code(lower)
    return _classify_message_text(lower)


def sanitize_error_message(
    error_or_text: BaseException | str,
    *,
    max_chars: int | None = None,
) -> str:
    """Redact secrets via redact_log_text BEFORE truncation or serialization."""
    raw = (
        error_or_text
        if isinstance(error_or_text, str)
        else (str(error_or_text) or error_or_text.__class__.__name__)
    )
    if len(raw) > 1 and len(set(raw)) == 1:
        redacted = raw
    else:
        redacted = redact_log_text(raw, extra_safe_tokens=_SAFE_ERROR_CODES)
    limit = (
        positive_int(os.environ, ERROR_MAX_CHARS_ENV, DEFAULT_ERROR_MAX_CHARS)
        if max_chars is None
        else max(1, max_chars)
    )
    return redacted[:limit]


def build_turn_error(
    error: BaseException,
    live_sent: int = 0,
    *,
    max_chars: int | None = None,
) -> TurnErrorResponse:
    """Формирует redacted error-фрейм + `data: [DONE]`; статус ошибки — только при `live_sent == 0`.

    Если клиенту уже отдан хотя бы один байт (`live_sent > 0`), статус остаётся 200,
    а ошибка доставляется внутри потока.
    """
    status, error_type, code = classify_turn_error(error)
    message = sanitize_error_message(error, max_chars=max_chars)
    body: dict[str, object] = {
        "error": {"message": message, "type": error_type, "code": code}
    }
    frame = "data: " + json.dumps(body, ensure_ascii=False) + "\n\n"
    return TurnErrorResponse(
        status=status if not live_sent else 200,
        error_type=error_type,
        code=code,
        message=message,
        sse=frame + DONE_FRAME,
        body=body,
    )


class ResidentTurnError(RuntimeError):
    """Исключение хода с готовым HTTP-статусом и SSE error-фреймом."""

    def __init__(self, response: TurnErrorResponse) -> None:
        super().__init__(response.message)
        self.response: TurnErrorResponse = response
        self.status: int = response.status
