"""Bridge dispatch failures into sanitized terminal SSE frames after headers are sent."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, Protocol

from core.codex_zero_canon_policy import ERROR_TAXONOMY
from core.log_redaction import redact_log_text
from core.runtime_env import positive_int
from core.stdio_resident.turn_error_sse import (
    DONE_FRAME,
    ResidentTurnError,
    TurnErrorResponse,
    build_turn_error,
)

DEFAULT_LOG_MAX_CHARS: Final[int] = 160
SSE_ERROR_LOG_MAX_CHARS_ENV: Final[str] = "BRIDGE_SSE_ERROR_LOG_MAX_CHARS"
_GENERIC_TURN_ERROR_CODE: Final[str] = "resident_turn_failed"
_SAFE_LOG_CODES: Final[frozenset[str]] = frozenset(
    (
        *ERROR_TAXONOMY.keys(),
        "zero_canon_unsupported_by_driver",
        "zero_canon_attestation_failed",
        "invalid_review_profile",
        "unsupported_model_effort",
        "output_limit_exceeded",
        _GENERIC_TURN_ERROR_CODE,
        "slot_lease_timeout",
        "turn_timeout",
        "rate_limit_exceeded",
    )
)


class _LeaseProtocol(Protocol):
    def record_failure(self, exc: BaseException) -> None: ...

    def record_discard(self, reason: str) -> None: ...


@dataclass(frozen=True, slots=True)
class SseErrorContext:
    handler: object
    lease: _LeaseProtocol
    emit: Callable[[str], bool]
    stream_error_frame: Callable[..., str]
    log_fn: Callable[[str], None]


def sanitize_log_text(
    raw: str,
    *,
    extra_code: str = "",
    max_chars: int | None = None,
) -> str:
    """Redact secrets via redact_log_text BEFORE truncation or logging."""
    safe_tokens = _SAFE_LOG_CODES | {extra_code} if extra_code else _SAFE_LOG_CODES
    redacted = redact_log_text(raw, extra_safe_tokens=safe_tokens)
    limit = (
        positive_int(os.environ, SSE_ERROR_LOG_MAX_CHARS_ENV, DEFAULT_LOG_MAX_CHARS)
        if max_chars is None
        else max(1, max_chars)
    )
    return redacted[:limit]


_sanitize_log_text = sanitize_log_text


def _error_http_status(status: int) -> int:
    """Never record HTTP < 400 as a pre-chunk failure status."""
    return status if status >= 400 else 502


def _emit_turn_error_response(
    ctx: SseErrorContext,
    resp: TurnErrorResponse,
    *,
    has_live_bytes: bool,
    log_tag: str,
) -> None:
    """Emit a sanitized TurnErrorResponse without recording incomplete success."""
    status = resp.status if has_live_bytes else _error_http_status(resp.status)
    if not has_live_bytes:
        setattr(ctx.handler, "_response_status", status)
    safe_err = _sanitize_log_text(resp.message, extra_code=resp.code)
    ctx.log_fn(f"{log_tag} status={status} code={resp.code} err={safe_err!r}")
    _ = ctx.emit(resp.sse)


def _emit_midstream_error(ctx: SseErrorContext, resp: TurnErrorResponse) -> None:
    """Emit a sanitized mid-stream error frame with finish_reason=None and [DONE]."""
    safe_err = _sanitize_log_text(resp.message, extra_code=resp.code)
    ctx.log_fn(
        f"live_dispatch_failed status={resp.status} code={resp.code} err={safe_err!r}"
    )
    if resp.code == _GENERIC_TURN_ERROR_CODE:
        frame = ctx.stream_error_frame(resp.message, finish_reason=None)
    else:
        frame = ctx.stream_error_frame(
            resp.message,
            code=resp.code,
            error_type=resp.error_type,
            finish_reason=None,
        )
    _ = ctx.emit(frame)
    _ = ctx.emit(DONE_FRAME)


def handle_sse_stream_exception(
    exc: BaseException, live_sent: int, ctx: SseErrorContext
) -> bool:
    """Handle an SSE dispatch failure, returning whether the caller should return."""
    if bool(getattr(ctx.handler, "_client_write_dead", False)):
        safe_err = _sanitize_log_text(repr(exc))
        ctx.log_fn(f"client_write_dead: dispatch error suppressed err={safe_err!r}")
        ctx.lease.record_discard("client_disconnected")
        return True
    effective_live = live_sent if live_sent > 0 else 0
    has_live_bytes = effective_live > 0
    headers_sent = bool(getattr(ctx.handler, "_headers_already_sent", False))
    if not has_live_bytes and not headers_sent:
        return False
    ctx.lease.record_failure(exc)
    resp = build_turn_error(exc, live_sent=effective_live)
    if isinstance(exc, ResidentTurnError):
        _emit_turn_error_response(
            ctx, resp, has_live_bytes=has_live_bytes, log_tag="sse_resident_error"
        )
        return True
    if not has_live_bytes:
        _emit_turn_error_response(
            ctx, resp, has_live_bytes=False, log_tag="sse_pre_chunk_failed"
        )
        return True
    _emit_midstream_error(ctx, resp)
    return True
