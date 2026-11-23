"""Wire Codex app-server v2 protocol state into HTTP Zero-Canon attestation proofs."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, Final

from core.stdio_resident.codex_protocol_fsm import ProtocolPhase, ProtocolState
from core.stdio_resident.turn_error_sse import ResidentTurnError, build_turn_error
from core.subbridge_zero_canon import is_zero_canon_profile
from core.zero_canon_attestation_http import (
    KIND_EPHEMERAL,
    ZeroCanonAdmissionProof,
    ZeroCanonCompletionProof,
    emit_turn_headers,
)

StreamWriter = Callable[[str, str], bool]
_CODEX_V2_PROTOCOL: Final[str] = "codex-app-server-v2"
_COMPLETED_ONLY: Final[frozenset[ProtocolPhase]] = frozenset({ProtocolPhase.COMPLETED})
_ADMITTED_PHASES: Final[frozenset[ProtocolPhase]] = frozenset(
    {ProtocolPhase.TURN_ACTIVE, ProtocolPhase.COMPLETED}
)


def should_wire_v2_zero_canon(protocol: str, profile: str, handler: object | None) -> bool:
    """Return True when Codex v2 Zero-Canon attestation must be attached to handler."""
    return protocol == _CODEX_V2_PROTOCOL and is_zero_canon_profile(profile) and handler is not None


def _is_usable_state(state: object, phases: frozenset[ProtocolPhase]) -> bool:
    return isinstance(state, ProtocolState) and state.phase in phases and bool(state.turn_id)


def _select_state(driver: object, *, require_completed: bool) -> ProtocolState | None:
    current = getattr(driver, "protocol_state", None)
    last = getattr(driver, "last_turn_state", None)
    if require_completed:
        for candidate in (current, last):
            if _is_usable_state(candidate, _COMPLETED_ONLY):
                return candidate
        return None
    if _is_usable_state(current, _ADMITTED_PHASES):
        return current
    return last if _is_usable_state(last, _COMPLETED_ONLY) else None


def _proof_from_state(
    state: ProtocolState | None, *, model: str, effort: str
) -> ZeroCanonAdmissionProof | None:
    if state is None or not state.zero_canon:
        return None
    tid, turn_id = (state.thread_id or "").strip(), (state.turn_id or "").strip()
    if not tid or tid.lower().startswith("th-") or not turn_id:
        return None
    return ZeroCanonAdmissionProof(
        model=model,
        effort=effort,
        thread_id=tid,
        turn_id=turn_id,
        execution_kind=KIND_EPHEMERAL,
        clean_home_verified=True,
        handshake_acked=True,
        requested_model=model,
        requested_effort=effort,
    )


def build_v2_admission_proof(
    driver: object, *, model: str, effort: str
) -> ZeroCanonAdmissionProof | None:
    """Build verified pre-stream admission proof from Codex v2 driver protocol state."""
    return _proof_from_state(_select_state(driver, require_completed=False), model=model, effort=effort)


def build_v2_completion_proof(
    driver: object, *, model: str, effort: str
) -> ZeroCanonCompletionProof | None:
    """Build verified terminal completion proof only after ProtocolPhase.COMPLETED."""
    adm = _proof_from_state(_select_state(driver, require_completed=True), model=model, effort=effort)
    if adm is None:
        return None
    return ZeroCanonCompletionProof(admission=adm, terminal_status="completed", tool_events_seen=0, error_code=None)


def wrap_v2_sse_writer(
    sse_writer: StreamWriter | None, driver: object, handler: object | None, model: str, effort: str
) -> StreamWriter | None:
    """Attach admission proof to handler immediately before the first emitted SSE event."""
    if sse_writer is None or handler is None:
        return sse_writer
    attached = False

    def _wrapped(kind: str, text: str) -> bool:
        nonlocal attached
        if not attached:
            attached = True
            if (proof := build_v2_admission_proof(driver, model=model, effort=effort)) is not None:
                setattr(handler, "_zero_canon_admission", proof)
        return sse_writer(kind, text)

    return _wrapped


def record_v2_turn_completion(
    driver: object, handler: object | None, *, model: str, effort: str, has_sse: bool
) -> None:
    """Attach completion proof (and fallback admission for 0-chunk SSE) after clean return."""
    if handler is None:
        return
    if has_sse and getattr(handler, "_zero_canon_admission", None) is None:
        if (adm := build_v2_admission_proof(driver, model=model, effort=effort)) is not None:
            setattr(handler, "_zero_canon_admission", adm)
    if (comp := build_v2_completion_proof(driver, model=model, effort=effort)) is not None:
        setattr(handler, "_zero_canon_completion", comp)


def should_defer_zero_canon_sse_headers(handler: object, ctx: Mapping[str, Any]) -> bool:
    """Return True when SSE HTTP 200 headers must wait for Codex Zero-Canon admission."""
    if ctx.get("attached_existing"):
        return False
    if str(ctx.get("backend") or "").strip().lower() != "codex":
        return False
    profile = getattr(handler, "_review_profile", None)
    return isinstance(profile, str) and is_zero_canon_profile(profile)


def emit_sse_response_headers(
    handler: Any,
    ctx: Mapping[str, Any],
    managed_turn: Any,
    trace_headers: Sequence[tuple[str, str]],
    pruned: tuple[str, str | None],
) -> None:
    """Emit SSE HTTP 200 response headers with verified Zero-Canon admission attestation."""
    handler._response_status = 200
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("X-Accel-Buffering", "no")
    adm = ctx.get("zero_canon_admission") or getattr(handler, "_zero_canon_admission", None)
    emit_turn_headers(handler, managed_turn, trace_headers, pruned, attestation=(adm, "admitted"))
    handler._headers_already_sent = True
    handler.close_connection = True


def ensure_deferred_sse_headers(
    handler: Any,
    emit_headers: Callable[[], None],
    on_disconnect: Callable[[], None],
    emit_role: Callable[[], bool] | None = None,
) -> bool:
    """Idempotently emit SSE headers once, handling pre-header disconnect and optional role frame."""
    if getattr(handler, "_headers_already_sent", False):
        return True
    try:
        emit_headers()
    except (BrokenPipeError, ConnectionResetError, OSError):
        on_disconnect()
        return False
    return True if emit_role is None else emit_role()


def send_pre_stream_sse_error(handler: Any, lease: Any, exc: BaseException) -> bool:
    """Send pre-stream HTTP error JSON when deferred SSE headers were never flushed."""
    if getattr(handler, "_headers_already_sent", False) or getattr(handler, "_client_write_dead", False):
        return False
    lease.record_failure(exc)
    resp = exc.response if isinstance(exc, ResidentTurnError) else build_turn_error(exc, live_sent=0)
    handler._send(resp.status if resp.status >= 400 else 502, resp.body)
    return True


def finalize_deferred_sse_headers(
    handler: Any, err: Mapping[str, Any] | None, ensure_headers: Callable[[], bool]
) -> bool:
    """Flush deferred SSE headers before terminal frames, or return HTTP error JSON if unstarted."""
    if getattr(handler, "_headers_already_sent", False):
        return True
    if err is not None:
        handler._send(int(err.get("code") or 502), {"error": err})
        return False
    return ensure_headers()
