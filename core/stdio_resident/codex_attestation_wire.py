"""Wire Codex app-server v2 protocol state into HTTP Zero-Canon attestation proofs."""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from core.codex_zero_canon_policy import CodexZeroCanonPolicyError
from core.stdio_resident.codex_protocol_fsm import ProtocolPhase, ProtocolState
from core.stdio_resident.turn_error_sse import ResidentTurnError, build_turn_error, sanitize_error_message
from core.subbridge_zero_canon import is_zero_canon_profile
from core.zero_canon_attestation_http import (
    KIND_EPHEMERAL,
    ZeroCanonAdmissionProof,
    ZeroCanonCompletionProof,
    ZeroCanonHttpError,
    build_attestation_header,
    emit_turn_headers,
)

StreamWriter = Callable[[str, str], bool]
_CODEX_V2_PROTOCOL: Final[str] = "codex-app-server-v2"
_ATTESTATION_CODE: Final[str] = "zero_canon_attestation_failed"
_COMPLETED_ONLY: Final[frozenset[ProtocolPhase]] = frozenset({ProtocolPhase.COMPLETED})
_ADMITTED_PHASES: Final[frozenset[ProtocolPhase]] = frozenset({ProtocolPhase.TURN_ACTIVE, ProtocolPhase.COMPLETED})


def should_wire_v2_zero_canon(protocol: str, profile: str, handler: object | None) -> bool:
    """Return True when Codex v2 Zero-Canon attestation must be attached to handler."""
    return protocol == _CODEX_V2_PROTOCOL and is_zero_canon_profile(profile) and handler is not None


def _is_usable_state(state: object, phases: frozenset[ProtocolPhase]) -> bool:
    return isinstance(state, ProtocolState) and state.phase in phases and bool(state.turn_id)


def _select_state(driver: object, *, require_completed: bool) -> ProtocolState | None:
    current, last = getattr(driver, "protocol_state", None), getattr(driver, "last_turn_state", None)
    if require_completed:
        return next((c for c in (current, last) if _is_usable_state(c, _COMPLETED_ONLY)), None)
    if _is_usable_state(current, _ADMITTED_PHASES):
        return current
    return last if _is_usable_state(last, _COMPLETED_ONLY) else None


def _proof_from_state(state: ProtocolState | None, *, model: str, effort: str) -> ZeroCanonAdmissionProof | None:
    if state is None or not state.zero_canon:
        return None
    tid, turn_id = (state.thread_id or "").strip(), (state.turn_id or "").strip()
    if not tid or tid.lower().startswith("th-") or not turn_id:
        return None
    return ZeroCanonAdmissionProof(
        model=model, effort=effort, thread_id=tid, turn_id=turn_id, execution_kind=KIND_EPHEMERAL,
        clean_home_verified=True, handshake_acked=True, requested_model=model, requested_effort=effort,
    )


def build_v2_admission_proof(driver: object, *, model: str, effort: str) -> ZeroCanonAdmissionProof | None:
    """Build verified pre-stream admission proof from Codex v2 driver protocol state."""
    return _proof_from_state(_select_state(driver, require_completed=False), model=model, effort=effort)


def build_v2_completion_proof(driver: object, *, model: str, effort: str) -> ZeroCanonCompletionProof | None:
    """Build verified terminal completion proof only after ProtocolPhase.COMPLETED."""
    adm = _proof_from_state(_select_state(driver, require_completed=True), model=model, effort=effort)
    if adm is None:
        return None
    return ZeroCanonCompletionProof(admission=adm, terminal_status="completed", tool_events_seen=0, error_code=None)


def wrap_v2_sse_writer(
    sse_writer: StreamWriter | None, driver: object, handler: object | None, model: str, effort: str
) -> StreamWriter | None:
    """Attach verified admission proof before the first SSE event, failing closed if absent."""
    if sse_writer is None or handler is None:
        return sse_writer
    attached = False

    def _wrapped(kind: str, text: str) -> bool:
        nonlocal attached
        if not attached:
            proof = build_v2_admission_proof(driver, model=model, effort=effort)
            if proof is None:
                raise ZeroCanonHttpError(_ATTESTATION_CODE, "missing verified Zero-Canon admission proof", http_status=502)
            setattr(handler, "_zero_canon_admission", proof)
            attached = True
        return sse_writer(kind, text)

    return _wrapped


def record_v2_turn_completion(
    driver: object, handler: object | None, *, model: str, effort: str, has_sse: bool = False
) -> None:
    """Attach verified ProtocolPhase.COMPLETED proof after clean return."""
    _ = has_sse
    if handler is None:
        return
    if (comp := build_v2_completion_proof(driver, model=model, effort=effort)) is not None:
        setattr(handler, "_zero_canon_completion", comp)


def should_defer_zero_canon_sse_headers(handler: object, ctx: Mapping[str, Any]) -> bool:
    """Return True when SSE HTTP 200 headers must wait for Codex Zero-Canon admission."""
    if ctx.get("attached_existing") or str(ctx.get("backend") or "").strip().lower() != "codex":
        return False
    profile = getattr(handler, "_review_profile", None)
    return isinstance(profile, str) and is_zero_canon_profile(profile)


def _clear_attestation_attrs(handler: Any, ctx: Mapping[str, Any] | None = None) -> None:
    for attr in ("_zero_canon_admission", "_zero_canon_completion"):
        if hasattr(handler, attr):
            setattr(handler, attr, None)
    if isinstance(ctx, MutableMapping):
        ctx.pop("zero_canon_admission", None)
        ctx.pop("zero_canon_completion", None)


def _is_attestation_error(exc: BaseException) -> bool:
    if isinstance(exc, ResidentTurnError) and exc.response.code == _ATTESTATION_CODE:
        return True
    return any(isinstance(e, ZeroCanonHttpError) and e.code == _ATTESTATION_CODE for e in (exc, exc.__cause__))


def _error_status_from_mapping(err: Mapping[str, Any]) -> int:
    raw = err.get("code")
    return raw if isinstance(raw, int) and raw >= 400 else 502


@dataclass(slots=True)
class ZeroCanonSseHeaderGate:
    """Cohesive fail-closed controller for deferred Zero-Canon SSE response headers."""

    handler: Any
    ctx: Mapping[str, Any]
    managed_turn: Any
    trace_headers: Sequence[tuple[str, str]]
    pruned: tuple[str, str | None]
    defer_zc_headers: bool
    initial_frame_fn: Callable[[], bool] | None = None
    on_disconnect: Callable[[], None] | None = None
    header_write_failed: bool = False
    failed_closed: bool = False

    @classmethod
    def for_request(
        cls, handler: Any, ctx: Mapping[str, Any], trace_headers: Sequence[tuple[str, str]] = (),
        pruned: tuple[str, str | None] = ("", None), *, initial_frame_fn: Callable[[], bool] | None = None,
    ) -> ZeroCanonSseHeaderGate:
        """Create a request-scoped SSE header gate."""
        managed = ctx.get("managed_turn") or getattr(handler, "_active_managed_turn", None)
        return cls(handler, ctx, managed, trace_headers, pruned, should_defer_zero_canon_sse_headers(handler, ctx), initial_frame_fn)

    def _optional_admission(self) -> tuple[Any, str] | None:
        adm = self.ctx.get("zero_canon_admission") or getattr(self.handler, "_zero_canon_admission", None)
        return (adm, "admitted") if adm is not None else None

    def _resolve_verified_proof(self, phase: str) -> tuple[Any, str | None]:
        if phase == "admitted":
            proof = self.ctx.get("zero_canon_admission") or getattr(self.handler, "_zero_canon_admission", None)
            if not isinstance(proof, ZeroCanonAdmissionProof):
                return None, "missing verified Zero-Canon admission proof"
        elif phase == "completed":
            proof = self.ctx.get("zero_canon_completion") or getattr(self.handler, "_zero_canon_completion", None)
            if not isinstance(proof, ZeroCanonCompletionProof):
                return None, "missing verified Zero-Canon completion proof"
        else:
            return None, f"unsupported attestation phase: {phase}"
        try:
            build_attestation_header(proof, phase=phase)
        except CodexZeroCanonPolicyError as exc:
            return None, str(exc)
        return proof, None

    def _fail_closed(self, detail: str) -> bool:
        safe = sanitize_error_message(detail)
        msg = safe if _ATTESTATION_CODE in safe else f"{_ATTESTATION_CODE}: {safe}"
        self.failed_closed, self.handler._response_status = True, 502
        _clear_attestation_attrs(self.handler, self.ctx)
        try:
            self.handler._send(502, {"error": {"message": msg, "type": "upstream_error", "code": _ATTESTATION_CODE}})
        finally:
            self.handler._headers_already_sent = True
        return False

    def _emit_sse_200(self, attestation: tuple[Any, str] | None) -> bool:
        h = self.handler
        try:
            h._response_status = 200
            h.send_response(200)
            for k, v in (("Content-Type", "text/event-stream"), ("Cache-Control", "no-cache"), ("X-Accel-Buffering", "no")):
                h.send_header(k, v)
            emit_turn_headers(h, self.managed_turn, self.trace_headers, self.pruned, attestation=attestation)
            h._headers_already_sent, h.close_connection = True, True
            return True
        except (BrokenPipeError, ConnectionResetError, OSError):
            self.header_write_failed = True
            if self.on_disconnect is not None:
                self.on_disconnect()
            return False

    def _emit_initial_frame(self, emit_initial: bool) -> bool:
        return True if (not emit_initial or self.initial_frame_fn is None) else bool(self.initial_frame_fn())

    def ensure_headers(self, *, phase: str = "admitted", emit_initial: bool = True) -> bool:
        """Idempotently validate attestation and emit SSE 200 headers (+ optional initial frame)."""
        if self.failed_closed:
            return False
        if getattr(self.handler, "_headers_already_sent", False):
            return True
        if self.defer_zc_headers:
            proof, err_detail = self._resolve_verified_proof(phase)
            if err_detail is not None:
                return self._fail_closed(err_detail)
            attestation: tuple[Any, str] | None = (proof, phase)
        else:
            attestation = self._optional_admission()
        return self._emit_sse_200(attestation) and self._emit_initial_frame(emit_initial)

    def ensure_initial_headers(self) -> bool:
        """Emit initial SSE headers + role frame immediately unless Zero-Canon defers them."""
        return True if self.defer_zc_headers else self.ensure_headers(phase="admitted", emit_initial=True)

    def ensure_live_headers(self) -> bool:
        """Emit deferred SSE headers on first live chunk, failing closed without admission proof."""
        return self.ensure_headers(phase="admitted", emit_initial=True)

    def allow_keepalive(self) -> bool:
        """Return False while deferred Zero-Canon headers remain unsent or after fail-closed."""
        if self.failed_closed:
            return False
        return not self.defer_zc_headers or bool(getattr(self.handler, "_headers_already_sent", False))

    def handle_pre_stream_error(self, exc: BaseException, lease: Any) -> bool:
        """Send pre-stream HTTP error JSON when deferred SSE headers were never flushed."""
        if not self.defer_zc_headers or self.failed_closed:
            return False
        if getattr(self.handler, "_headers_already_sent", False) or getattr(self.handler, "_client_write_dead", False):
            return False
        lease.record_failure(exc)
        if _is_attestation_error(exc):
            self._fail_closed(sanitize_error_message(exc))
            return True
        resp = exc.response if isinstance(exc, ResidentTurnError) else build_turn_error(exc, live_sent=0)
        status = resp.status if resp.status >= 400 else 502
        self.failed_closed, self.handler._response_status = True, status
        self.handler._send(status, resp.body)
        return True

    def finalize_zero_chunk_headers(self, err: Mapping[str, Any] | None = None) -> bool:
        """Finalize deferred headers on 0-chunk turn using verified phase=completed proof."""
        if self.failed_closed:
            return False
        if not self.defer_zc_headers or getattr(self.handler, "_headers_already_sent", False):
            return True
        if err is not None:
            status = _error_status_from_mapping(err)
            self.handler._response_status = status
            self.handler._send(status, {"error": err})
            return False
        return self.ensure_headers(phase="completed", emit_initial=True)
