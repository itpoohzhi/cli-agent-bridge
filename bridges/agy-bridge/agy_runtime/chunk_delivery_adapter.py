"""Sequential stream-json chunk delivery adapter with Phase A ACK draining."""

from __future__ import annotations

import queue
import subprocess
import threading
import time
from dataclasses import dataclass, replace
from typing import IO, Any, Protocol

from core.lossless_chunker import ChunkLimitExceededError, iter_ndjson_frames
from core.lossless_contracts import LosslessLimits, LossReceipt, build_loss_receipt
from core.lossless_delivery_policy import (
    ChunkDeliveryOptions, format_lossless_event, parse_ack_event as parse_ack_event,
)
from core.lossless_fsm import EffectKind, EventKind, SessionEvent, SessionSnapshot, SessionState, step

from .process_admission_guard import ProcessAdmissionGuard

_parse_ack_event = parse_ack_event
_ACK_LOG = {"timeout": "chunk_ack_timeout", "eof": "chunk_ack_eof"}


class CancelFlag(Protocol):
    def is_set(self) -> bool:
        ...


def _is_cancelled(cancel: CancelFlag | None) -> bool:
    res = cancel.is_set() if cancel else False
    return res


@dataclass(frozen=True)
class ChunkDeliveryResult:
    """Outcome of a lossless chunked delivery turn."""

    ok: bool
    state: SessionState
    chunks_delivered: int
    anchor_committed: bool
    stdout_lines: tuple[str, ...]
    final_turn_lines: tuple[str, ...] = ()
    http_status: int = 200
    receipt: LossReceipt | None = None
    reason: str = ""


class _AckReader:
    """Bounded stdout reader draining exactly K = N - 1 Phase A ACK lines."""

    def __init__(self, stdout: IO[bytes] | None, expected_acks: int) -> None:
        self._stdout = stdout
        self._expected_acks = expected_acks
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        if expected_acks:
            self._thread = threading.Thread(target=self._pump, name="agy-chunk-ack", daemon=True)
            self._thread.start()

    def _pump(self) -> None:
        acks, stdout = 0, self._stdout
        try:
            while stdout is not None and acks < self._expected_acks:
                raw = stdout.readline()
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").strip()
                self._queue.put(line)
                acks += int(parse_ack_event(line)[0])
        except (OSError, ValueError):
            pass
        finally:
            self._queue.put(None)

    def _pop_line(self, deadline: float, cancel: CancelFlag | None) -> tuple[str, str | None]:
        res: tuple[str, str | None] = ("timeout", None)
        while (rem := deadline - time.monotonic()) > 0:
            if _is_cancelled(cancel):
                res = ("cancelled", None)
                break
            try:
                line = self._queue.get(timeout=min(0.05, rem))
            except queue.Empty:
                continue
            if line is None:
                res = ("eof", None)
                break
            if line:
                res = ("line", line)
                break
        return res

    def wait_ack(self, collected: list[str], options: ChunkDeliveryOptions) -> tuple[str, int | None]:
        """Wait for one ACK line while buffering lines and notifying on_line."""
        hooks = options.hooks
        cancel, on_line = (hooks.cancel_event, hooks.on_line) if hooks else (None, None)
        deadline = time.monotonic() + options.chunk_ack_timeout_s
        res: tuple[str, int | None] = ("timeout", None)
        while True:
            status, line = self._pop_line(deadline, cancel)
            if line is None:
                res = (status, None)
                break
            collected.append(line)
            if on_line:
                on_line(line)
            is_ack, ev_epoch = parse_ack_event(line)
            if is_ack:
                res = ("ack", ev_epoch)
                break
        return res

    def join(self, timeout_s: float) -> bool:
        """Join the ACK reader thread up to timeout_s and report completion."""
        alive = False
        if self._thread:
            self._thread.join(timeout=timeout_s)
            alive = self._thread.is_alive()
        return not alive


@dataclass(frozen=True)
class _DeliveryContext:
    raw_bytes: bytes
    limits: LosslessLimits
    guard: ProcessAdmissionGuard
    proc: subprocess.Popen[bytes]
    collected: list[str]
    options: ChunkDeliveryOptions
    reader: _AckReader | None


def _fsm_step(
    snap: SessionSnapshot, event: SessionEvent, options: ChunkDeliveryOptions
) -> tuple[SessionSnapshot, tuple[Any, ...]]:
    nxt, effects = step(snap, event)
    cb = options.hooks.on_snapshot if options.hooks else None
    if cb:
        cb(nxt)
    return nxt, tuple(effects)


def _io_err(epoch: int, seq: int, reason: str) -> SessionEvent:
    return SessionEvent(EventKind.IO_ERROR, epoch=epoch, seq=seq, reason=reason)


def _apply_failure_effects(ctx: _DeliveryContext, effects: tuple[Any, ...], reason: str) -> int:
    http_status, torndown = 400, False
    for eff in effects:
        if eff.kind is EffectKind.TEARDOWN_PGID:
            ctx.guard.teardown_process(ctx.proc)
            torndown = True
        elif eff.kind is EffectKind.EMIT_LOSS_RECEIPT and eff.http_status:
            http_status = eff.http_status
    if reason == "ack_reader_stuck" and not torndown:
        ctx.guard.teardown_process(ctx.proc)
        torndown = True
    if torndown:
        ev = format_lossless_event("teardown", {"req_id": ctx.options.request_id, "reason": reason})
        ctx.options.log_fn(ev)
    return http_status


def _finalize_failure(ctx: _DeliveryContext, snap: SessionSnapshot, event: SessionEvent) -> ChunkDeliveryResult:
    """Step FSM on failure event, apply teardown effects, and build receipt."""
    snap, effects = _fsm_step(snap, event, ctx.options)
    reason = event.reason
    http_status = _apply_failure_effects(ctx, effects, reason)
    salt = ctx.options.hooks.salt if ctx.options.hooks else None
    receipt = build_loss_receipt(
        reason=reason, http_status=http_status, prompt_raw=ctx.raw_bytes, delivered_bytes=0,
        chunk_count=snap.acked_chunks, chunk_index=event.seq, digest_mode=ctx.limits.digest_mode, salt=salt,
    )
    return ChunkDeliveryResult(
        ok=False, state=snap.state, chunks_delivered=snap.acked_chunks, anchor_committed=False,
        stdout_lines=tuple(ctx.collected), http_status=http_status, receipt=receipt, reason=reason,
    )


def _write_frame(
    ctx: _DeliveryContext, snap: SessionSnapshot, frame: object
) -> tuple[SessionSnapshot, ChunkDeliveryResult | None]:
    """Emit SEND_CHUNK and write one NDJSON frame to proc.stdin."""
    idx, f_epoch = int(getattr(frame, "index")), int(getattr(frame, "epoch"))
    is_syn = bool(getattr(frame, "is_synthetic"))
    ndjson: bytes = getattr(frame, "ndjson_bytes")
    ep = ctx.options.epoch
    cancel = ctx.options.hooks.cancel_event if ctx.options.hooks else None
    err: ChunkDeliveryResult | None = None
    if _is_cancelled(cancel):
        err = _finalize_failure(ctx, snap, SessionEvent(EventKind.CANCEL, epoch=ep, seq=idx, reason="client_cancelled"))
    else:
        send_ev = SessionEvent(EventKind.SEND_CHUNK, epoch=f_epoch, seq=idx, is_synthetic=is_syn)
        snap, _ = _fsm_step(snap, send_ev, ctx.options)
        stdin = ctx.proc.stdin
        if snap.is_terminal:
            err = _finalize_failure(ctx, snap, _io_err(ep, idx, "stdin_unavailable"))
        elif not stdin:
            err = _finalize_failure(ctx, snap, _io_err(ep, idx, "stdin_unavailable"))
        else:
            try:
                stdin.write(ndjson)
                stdin.flush()
            except (BrokenPipeError, OSError, ValueError):
                err = _finalize_failure(ctx, snap, _io_err(ep, idx, "stdin_write_failed"))
    return snap, err


def _deliver_synthetic(
    ctx: _DeliveryContext, snap: SessionSnapshot, frame: object
) -> tuple[SessionSnapshot, ChunkDeliveryResult | None]:
    """Write a synthetic frame and wait for its Phase A ACK."""
    snap, err = _write_frame(ctx, snap, frame)
    if not err and ctx.reader:
        idx, ep = int(getattr(frame, "index")), ctx.options.epoch
        status, ack_epoch = ctx.reader.wait_ack(ctx.collected, ctx.options)
        if status == "ack":
            if isinstance(ack_epoch, int) and ack_epoch != ep:
                mismatch_ev = SessionEvent(EventKind.EPOCH_MISMATCH, epoch=ack_epoch, seq=idx, reason="epoch_mismatch")
                err = _finalize_failure(ctx, snap, mismatch_ev)
            else:
                ack_ev = SessionEvent(EventKind.ACK_OK, epoch=ep, seq=idx, is_synthetic=True)
                snap, _ = _fsm_step(snap, ack_ev, ctx.options)
        elif status == "cancelled":
            err = _finalize_failure(ctx, snap, SessionEvent(EventKind.CANCEL, epoch=ep, seq=idx, reason="client_cancelled"))
        else:
            log_ev = _ACK_LOG.get(status)
            if log_ev:
                ctx.options.log_fn(format_lossless_event(log_ev, {"req_id": ctx.options.request_id, "seq": idx}))
            err = _finalize_failure(ctx, snap, _io_err(ep, idx, f"chunk_ack_{status}"))
    return snap, err


def _execute_delivery(ctx: _DeliveryContext, snap: SessionSnapshot, frames: list[object]) -> ChunkDeliveryResult:
    """Drain K = N - 1 synthetic ACKs via _AckReader, then send final frame N."""
    opts, k = ctx.options, len(frames) - 1
    opts.log_fn(format_lossless_event("delivery_start", {"req_id": opts.request_id, "chunks": len(frames), "epoch": opts.epoch}))
    reader = _AckReader(ctx.proc.stdout, k) if k else None
    run_ctx = replace(ctx, reader=reader)
    err: ChunkDeliveryResult | None = None
    for frame in frames[:-1]:
        snap, err = _deliver_synthetic(run_ctx, snap, frame)
        if err:
            break
    if not err and reader:
        if not reader.join(opts.chunk_ack_timeout_s):
            idx = int(getattr(frames[-1], "index"))
            err = _finalize_failure(run_ctx, snap, _io_err(opts.epoch, idx, "ack_reader_stuck"))
    if not err:
        snap, err = _write_frame(run_ctx, snap, frames[-1])
    res = err if err else ChunkDeliveryResult(
        ok=True, state=snap.state, chunks_delivered=snap.acked_chunks, anchor_committed=False,
        stdout_lines=tuple(ctx.collected), final_turn_lines=(), http_status=200, reason="",
    )
    return res


def _close_stdin(proc: subprocess.Popen[bytes]) -> None:
    if proc.stdin:
        try:
            proc.stdin.close()
        except (OSError, ValueError):
            pass


def _default_options(limits: LosslessLimits) -> ChunkDeliveryOptions:
    return ChunkDeliveryOptions(chunk_ack_timeout_s=limits.chunk_ack_timeout_s, request_id="unknown", log_fn=lambda _m: None)


def deliver_chunked_prompt(
    proc: subprocess.Popen[bytes], prompt_text: str, limits: LosslessLimits,
    guard: ProcessAdmissionGuard, *, options: ChunkDeliveryOptions | None = None,
) -> ChunkDeliveryResult:
    """Deliver prompt_text as NDJSON frames; Phase A drains K = N - 1 ACKs."""
    opts = options if options else _default_options(limits)
    raw_bytes = prompt_text.encode("utf-8")
    snap = SessionSnapshot(state=SessionState.INIT, active_epoch=opts.epoch, max_chunks=limits.max_chunks)
    ctx = _DeliveryContext(raw_bytes, limits, guard, proc, [], opts, None)
    try:
        frames = list(iter_ndjson_frames(
            prompt_text, safe_frame_bytes=limits.safe_frame_bytes, max_chunks=limits.max_chunks, epoch=opts.epoch,
        ))
        return _execute_delivery(ctx, snap, frames)
    except ChunkLimitExceededError:
        ev = SessionEvent(EventKind.OVERFLOW, epoch=opts.epoch, seq=snap.expected_seq, reason="chunk_limit_exceeded")
        return _finalize_failure(ctx, snap, ev)
    finally:
        _close_stdin(proc)
