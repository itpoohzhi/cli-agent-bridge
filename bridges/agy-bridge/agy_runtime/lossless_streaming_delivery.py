"""Phase B streaming delivery, watchdog, and exception finalization."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from typing import cast

from core.lossless_contracts import LosslessLimits, LossReceipt as LossReceipt
from core.lossless_delivery_policy import CancelFlag, ChunkDeliveryOptions
from core.lossless_delivery_policy import DeliveryHooks, ack_phase_deadline_s
from core.lossless_delivery_policy import format_lossless_event, lossless_owns_process
from core.lossless_delivery_policy import parse_ack_event
from core.lossless_fsm import EventKind, SessionEvent, SessionSnapshot
from core.lossless_fsm import SessionState, step

from .chunk_delivery_adapter import ChunkDeliveryResult as ChunkDeliveryResult
from .lossless_delivery_sync import (
    FinalTurnContext as FinalTurnContext,
    FinalTurnIdleWatchdog as FinalTurnIdleWatchdog,
    LosslessDeliveryChannel as LosslessDeliveryChannel,
    _FinalTurnState as _FinalTurnState,
    make_delivery_result,
    resolve_log_fn as resolve_log_fn,
    run_request_id as run_request_id,
    summarize_receipt as summarize_receipt,
    terminal_http_status as terminal_http_status,
)
from .process_admission_guard import ProcessAdmissionGuard as ProcessAdmissionGuard

_CHANNEL_LOCK = threading.Lock()


def _emit(log: Callable[[str], None], ev: str, run: object, **kw: object) -> None:
    log(format_lossless_event(ev, {"req_id": run_request_id(run), **kw}))


def _io_error(snap: SessionSnapshot, reason: str) -> SessionEvent:
    ep, seq = snap.active_epoch, snap.expected_seq
    return SessionEvent(EventKind.IO_ERROR, epoch=ep, seq=seq, reason=reason)


def _teardown(guard: object, run: object) -> None:
    proc = getattr(run, "proc", None)
    fn = getattr(guard, "teardown_process", None)
    if proc:
        if callable(fn):
            fn(proc)


def get_or_create_channel(run: object) -> LosslessDeliveryChannel:
    """Return the cached LosslessDeliveryChannel on run, creating one if needed."""
    with _CHANNEL_LOCK:
        ch = getattr(run, "_lossless_channel", None)
        if not isinstance(ch, LosslessDeliveryChannel):
            ch = LosslessDeliveryChannel()
            setattr(run, "_lossless_channel", ch)
        return ch


def build_delivery_options(run: object, limits: LosslessLimits) -> ChunkDeliveryOptions:
    """Build ChunkDeliveryOptions bound to run's channel and cancellation flag."""
    ch = get_or_create_channel(run)
    valid = [
        cast(CancelFlag, c)
        for a in ("cancel_event", "_cancel_event", "_stop_watch")
        for c in (getattr(run, a, None),)
        if callable(getattr(c, "is_set", None))
    ]
    cancel = valid[0] if valid else None
    opts = ChunkDeliveryOptions(
        chunk_ack_timeout_s=limits.chunk_ack_timeout_s,
        request_id=run_request_id(run),
        log_fn=resolve_log_fn(run),
        epoch=int(getattr(run, "_lossless_epoch", 1)),
        hooks=DeliveryHooks(cancel_event=cancel, on_snapshot=ch.record_snapshot),
    )
    setattr(run, "_lossless_options", opts)
    return opts


def build_final_turn_context(
    run: object,
    guard: ProcessAdmissionGuard,
    limits: LosslessLimits,
    n_chunks: int | None = None,
) -> FinalTurnContext:
    """Build FinalTurnContext using cached or newly built options and channel."""
    opts = getattr(run, "_lossless_options", None)
    if not isinstance(opts, ChunkDeliveryOptions):
        opts = build_delivery_options(run, limits)
    setattr(run, "_lossless_guard", guard)
    saved = getattr(run, "_lossless_n_chunks", None)
    raw = n_chunks if isinstance(n_chunks, int) else saved
    stdin_chunks = max(1, str(getattr(run, "stdin_line", "")).count("\n"))
    chunks = max(1, raw) if isinstance(raw, int) else stdin_chunks
    return FinalTurnContext(get_or_create_channel(run), guard, limits, opts, chunks)


def finalize_delivery_exception(run: object, exc: BaseException) -> ChunkDeliveryResult:
    """Teardown owned process and transition non-terminal snapshot on exception."""
    slot = bool(getattr(run, "_slot_held", getattr(run, "slot_held", False)))
    pers = bool(getattr(run, "_persistent_mode", False))
    lease = bool(getattr(run, "_persistent_lease", None))
    owns = lossless_owns_process(slot_held=slot, persistent_mode=pers, has_lease=lease)
    if owns:
        _teardown(getattr(run, "_lossless_guard", None), run)
    ch = getattr(run, "_lossless_channel", None)
    snap = ch.latest_snapshot() if isinstance(ch, LosslessDeliveryChannel) else None
    if not isinstance(snap, SessionSnapshot):
        snap = SessionSnapshot(SessionState.INIT, active_epoch=1, max_chunks=1)
    reason = type(exc).__name__
    if not snap.is_terminal:
        snap, _ = step(snap, _io_error(snap, reason))
    res = make_delivery_result(snap, reason)
    setattr(run, "_lossless_result", res)
    log = resolve_log_fn(run)
    st, code = snap.state.value, res.http_status
    _emit(log, "delivery_result", run, state=st, http_status=code, reason=reason)
    return res


def _await_phase_a_result(
    ctx: FinalTurnContext, wait_timeout_s: float | None
) -> tuple[bool, ChunkDeliveryResult | None]:
    ack_s, grace_s = ctx.options.chunk_ack_timeout_s, ctx.limits.kill_grace_s
    dl = ack_phase_deadline_s(ctx.n_chunks, ack_s, grace_s)
    if wait_timeout_s is not None:
        dl = float(wait_timeout_s)
    return ctx.channel.wait(dl), ctx.channel.result()


def _fallback_snap(ctx: FinalTurnContext, state: SessionState) -> SessionSnapshot:
    ep, mc = ctx.options.epoch, ctx.limits.max_chunks
    return SessionSnapshot(state, active_epoch=ep, max_chunks=mc)


def _handle_ack_phase_timeout(run: object, ctx: FinalTurnContext) -> None:
    _teardown(ctx.guard, run)
    if not ctx.channel.wait(min(ctx.limits.kill_grace_s, 0.2)):
        snap = ctx.channel.mark_timed_out()
        if not isinstance(snap, SessionSnapshot):
            snap = _fallback_snap(ctx, SessionState.INIT)
        if not snap.is_terminal:
            snap, _ = step(snap, _io_error(snap, "ack_phase_timeout"))
        res = make_delivery_result(snap, "ack_phase_timeout")
        setattr(run, "_lossless_result", res)
        _emit(ctx.options.log_fn, "ack_phase_timeout", run, state=snap.state.value)
        _emit(ctx.options.log_fn, "teardown", run, reason="ack_phase_timeout")


def _apply_ack_line(
    state: _FinalTurnState, ctx: FinalTurnContext, run: object, ev_epoch: int | None
) -> bool:
    cur = state.snapshot()
    ep = ev_epoch if isinstance(ev_epoch, int) else cur.active_epoch
    seq = cur.expected_seq
    ev = SessionEvent(EventKind.ACK_FINAL, epoch=ep, seq=seq, is_synthetic=False)
    changed, nxt = state.transition(ev)
    if changed and nxt.state == SessionState.EPOCH_MISMATCH:
        _teardown(ctx.guard, run)
        _emit(ctx.options.log_fn, "teardown", run, reason="epoch_mismatch")
    return changed and nxt.state == SessionState.COMPLETED


def _stream_under_watchdog(
    run: object,
    base_iter: Callable[[object], Iterator[str]],
    ctx: FinalTurnContext,
    snap: SessionSnapshot,
) -> Iterator[str]:
    state = _FinalTurnState(snap, run)

    def _on_timeout(waited_s: float) -> None:
        if state.transition(_io_error(snap, "final_turn_idle_timeout"))[0]:
            _teardown(ctx.guard, run)
            log = ctx.options.log_fn
            _emit(log, "final_turn_idle_timeout", run, waited_s=round(waited_s, 3))
            _emit(log, "teardown", run, reason="final_turn_idle_timeout")

    watchdog = FinalTurnIdleWatchdog(ctx.limits.final_turn_idle_timeout_s, _on_timeout)
    watchdog.start()
    try:
        try:
            for line in base_iter(run):
                watchdog.touch()
                if (ack := parse_ack_event(line))[0]:
                    if _apply_ack_line(state, ctx, run, ack[1]):
                        yield line
                    break
                yield line
        except (ValueError, OSError):
            pass
        state.transition(_io_error(state.snapshot(), "final_turn_eof"))
    finally:
        watchdog.stop()


def stream_final_turn(
    run: object,
    base_iter: Callable[[object], Iterator[str]],
    ctx: FinalTurnContext,
    *,
    wait_timeout_s: float | None = None,
) -> Iterator[str]:
    """Await Phase A completion and stream the final turn under an idle watchdog."""
    signalled, res = _await_phase_a_result(ctx, wait_timeout_s)
    log = ctx.options.log_fn
    if not signalled:
        _handle_ack_phase_timeout(run, ctx)
    elif not res:
        _teardown(ctx.guard, run)
        _emit(log, "delivery_result", run, ok=False)
    elif not res.ok:
        _emit(log, "delivery_result", run, state=res.state.value, ok=False)
    else:
        snap = ctx.channel.latest_snapshot()
        if not isinstance(snap, SessionSnapshot):
            snap = _fallback_snap(ctx, SessionState.AWAITING_ACK)
        yield from _stream_under_watchdog(run, base_iter, ctx, snap)
