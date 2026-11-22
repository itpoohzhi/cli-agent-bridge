"""Bridge dispatch failures into terminal SSE frames after headers are sent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from core.stdio_resident.turn_error_sse import DONE_FRAME, ResidentTurnError, build_turn_error


@dataclass(frozen=True, slots=True)
class SseErrorContext:
    handler: Any
    lease: Any
    emit: Callable[[str], bool]
    stream_error_frame: Callable[..., str]
    log_fn: Callable[[str], None]


def handle_sse_stream_exception(
    exc: BaseException, live_sent: int, ctx: SseErrorContext
) -> bool:
    """Handle an SSE dispatch failure, returning whether the caller should return."""
    if getattr(ctx.handler, "_client_write_dead", False):
        ctx.log_fn(f"client_write_dead: dispatch error suppressed err={repr(exc)[:160]!r}")
        ctx.lease.record_discard("client_disconnected")
        return True
    headers_sent = bool(getattr(ctx.handler, "_headers_already_sent", False))
    if not live_sent and not headers_sent:
        return False
    ctx.lease.record_failure(exc)
    if isinstance(exc, ResidentTurnError):
        resp = exc.response
        if not live_sent:
            ctx.handler._response_status = resp.status
        ctx.log_fn(f"sse_resident_error status={resp.status} code={resp.code} err={resp.message[:160]!r}")
        ctx.emit(resp.sse)
        return True
    if not live_sent:
        resp = build_turn_error(exc, live_sent=0)
        ctx.handler._response_status = resp.status
        ctx.log_fn(f"sse_pre_chunk_failed status={resp.status} err={resp.message[:160]!r}")
        ctx.emit(resp.sse)
        return True
    ctx.log_fn(f"live_dispatch_failed err={repr(exc)[:160]!r}")
    ctx.emit(ctx.stream_error_frame(str(exc)[:500] or exc.__class__.__name__, finish_reason=None))
    ctx.emit(DONE_FRAME)
    return True
