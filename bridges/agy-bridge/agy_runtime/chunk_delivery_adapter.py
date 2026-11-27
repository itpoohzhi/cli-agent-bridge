"""Sequential stream-json chunk delivery adapter with concurrent stdout draining and PGID teardown."""

from __future__ import annotations

import json
import queue
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass

from core.lossless_chunker import ChunkLimitExceededError, iter_ndjson_frames
from core.lossless_contracts import (
    LosslessLimits,
    LossReceipt,
    build_loss_receipt,
)
from core.lossless_fsm import (
    EffectKind,
    EventKind,
    SessionEvent,
    SessionSnapshot,
    SessionState,
    step,
)

from .process_admission_guard import ProcessAdmissionGuard


@dataclass(frozen=True)
class ChunkDeliveryResult:
    """Outcome of a lossless chunked delivery turn."""

    ok: bool
    state: SessionState
    chunks_delivered: int
    anchor_committed: bool
    stdout_lines: tuple[str, ...]
    http_status: int = 200
    receipt: LossReceipt | None = None
    reason: str = ""


def _parse_ack_event(raw_line: str) -> tuple[bool, int | None]:
    """Recognize terminal per-turn stream-json event (type/event == result)."""
    try:
        obj = json.loads(raw_line)
    except ValueError:
        return False, None
    if not isinstance(obj, dict):
        return False, None
    kind = str(obj.get("type") or obj.get("event") or "").strip().lower()
    if kind != "result":
        return False, None
    raw_epoch = obj.get("epoch")
    epoch = raw_epoch if isinstance(raw_epoch, int) and not isinstance(raw_epoch, bool) else None
    return True, epoch


def _start_stdout_reader(
    proc: subprocess.Popen[bytes],
    out_queue: queue.Queue[str | None],
) -> threading.Thread:
    """Drain stdout concurrently on a background thread to prevent macOS 16-64 KiB pipe deadlock."""

    def _pump() -> None:
        stdout = proc.stdout
        if stdout is None:
            out_queue.put(None)
            return
        try:
            while True:
                raw = stdout.readline()
                if not raw:
                    break
                out_queue.put(raw.decode("utf-8", errors="replace").strip())
        except (OSError, ValueError):
            pass
        finally:
            out_queue.put(None)

    thread = threading.Thread(target=_pump, name="agy-chunk-stdout", daemon=True)
    thread.start()
    return thread


def _wait_for_turn_ack(
    out_queue: queue.Queue[str | None],
    collected: list[str],
    *,
    timeout_s: float,
    cancel_event: threading.Event | None,
    on_line: Callable[[str], None] | None,
) -> tuple[str, int | None]:
    """Wait for a single turn's result line while honouring cancellation without busy-wait."""
    step_s = 0.05
    waited = 0.0
    while waited < timeout_s:
        if cancel_event is not None and cancel_event.is_set():
            return "cancelled", None
        try:
            line = out_queue.get(timeout=min(step_s, max(0.01, timeout_s - waited)))
        except queue.Empty:
            waited += step_s
            continue
        if line is None:
            return "eof", None
        if line:
            collected.append(line)
            if on_line is not None:
                on_line(line)
            is_ack, ev_epoch = _parse_ack_event(line)
            if is_ack:
                return "ack", ev_epoch
    return "timeout", None


def _finalize_failure(
    snap: SessionSnapshot,
    kind: EventKind,
    *,
    epoch: int,
    seq: int,
    reason: str,
    raw_bytes: bytes,
    limits: LosslessLimits,
    guard: ProcessAdmissionGuard,
    proc: subprocess.Popen[bytes],
    collected: list[str],
    salt: bytes | None,
) -> ChunkDeliveryResult:
    snap, effects = step(snap, SessionEvent(kind=kind, epoch=epoch, seq=seq, reason=reason))
    http_status = 400
    for eff in effects:
        if eff.kind is EffectKind.TEARDOWN_PGID:
            guard.teardown_process(proc)
        elif eff.kind is EffectKind.EMIT_LOSS_RECEIPT and eff.http_status:
            http_status = eff.http_status
    receipt = build_loss_receipt(
        reason=reason,
        http_status=http_status,
        prompt_raw=raw_bytes,
        delivered_bytes=0,
        chunk_count=snap.acked_chunks,
        chunk_index=seq,
        digest_mode=limits.digest_mode,
        salt=salt,
    )
    return ChunkDeliveryResult(
        ok=False,
        state=snap.state,
        chunks_delivered=snap.acked_chunks,
        anchor_committed=False,
        stdout_lines=tuple(collected),
        http_status=http_status,
        receipt=receipt,
        reason=reason,
    )


@dataclass(frozen=True)
class _DeliveryContext:
    raw_bytes: bytes
    limits: LosslessLimits
    guard: ProcessAdmissionGuard
    proc: subprocess.Popen[bytes]
    out_queue: queue.Queue[str | None]
    collected: list[str]
    epoch: int
    frame_timeout_s: float
    cancel_event: threading.Event | None
    on_line: Callable[[str], None] | None
    salt: bytes | None


def _deliver_single_frame(
    snap: SessionSnapshot,
    frame: object,
    ctx: _DeliveryContext,
) -> tuple[SessionSnapshot, ChunkDeliveryResult | None]:
    idx = int(getattr(frame, "index"))
    f_epoch = int(getattr(frame, "epoch"))
    is_syn = bool(getattr(frame, "is_synthetic"))
    ndjson: bytes = getattr(frame, "ndjson_bytes")

    def _fail(kind: EventKind, reason: str, ev_epoch: int | None = None) -> ChunkDeliveryResult:
        return _finalize_failure(
            snap, kind, epoch=ctx.epoch if ev_epoch is None else ev_epoch, seq=idx, reason=reason,
            raw_bytes=ctx.raw_bytes, limits=ctx.limits, guard=ctx.guard,
            proc=ctx.proc, collected=ctx.collected, salt=ctx.salt,
        )

    if ctx.cancel_event is not None and ctx.cancel_event.is_set():
        return snap, _fail(EventKind.CANCEL, "client_cancelled")
    snap, _ = step(snap, SessionEvent(EventKind.SEND_CHUNK, epoch=f_epoch, seq=idx, is_synthetic=is_syn))
    stdin = ctx.proc.stdin
    if snap.is_terminal or stdin is None:
        return snap, _fail(EventKind.IO_ERROR, "stdin_unavailable")
    try:
        stdin.write(ndjson)
        stdin.flush()
    except (BrokenPipeError, OSError, ValueError):
        return snap, _fail(EventKind.IO_ERROR, "stdin_write_failed")

    status, ack_epoch = _wait_for_turn_ack(
        ctx.out_queue, ctx.collected, timeout_s=ctx.frame_timeout_s,
        cancel_event=ctx.cancel_event, on_line=ctx.on_line,
    )
    if status == "cancelled":
        return snap, _fail(EventKind.CANCEL, "client_cancelled")
    if status != "ack":
        return snap, _fail(EventKind.IO_ERROR, f"chunk_ack_{status}")
    if ack_epoch is not None and ack_epoch != ctx.epoch:
        return snap, _fail(EventKind.EPOCH_MISMATCH, "epoch_mismatch", ev_epoch=ack_epoch)
    ack_kind = EventKind.ACK_OK if is_syn else EventKind.ACK_FINAL
    snap, _ = step(snap, SessionEvent(ack_kind, epoch=ctx.epoch, seq=idx, is_synthetic=is_syn))
    return snap, None


def deliver_chunked_prompt(
    proc: subprocess.Popen[bytes],
    prompt_text: str,
    limits: LosslessLimits,
    guard: ProcessAdmissionGuard,
    *,
    epoch: int = 1,
    frame_timeout_s: float = 15.0,
    cancel_event: threading.Event | None = None,
    on_line: Callable[[str], None] | None = None,
    salt: bytes | None = None,
) -> ChunkDeliveryResult:
    """Deliver prompt_text as sequential NDJSON frames in one stream-json session."""
    raw_bytes = prompt_text.encode("utf-8")
    snap = SessionSnapshot(state=SessionState.INIT, active_epoch=epoch, max_chunks=limits.max_chunks)
    out_queue: queue.Queue[str | None] = queue.Queue()
    reader = _start_stdout_reader(proc, out_queue)
    collected: list[str] = []
    ctx = _DeliveryContext(
        raw_bytes, limits, guard, proc, out_queue, collected,
        epoch, frame_timeout_s, cancel_event, on_line, salt,
    )
    try:
        for frame in iter_ndjson_frames(
            prompt_text, safe_frame_bytes=limits.safe_frame_bytes, max_chunks=limits.max_chunks, epoch=epoch,
        ):
            snap, failure = _deliver_single_frame(snap, frame, ctx)
            if failure is not None:
                return failure
    except ChunkLimitExceededError:
        return _finalize_failure(
            snap, EventKind.OVERFLOW, epoch=epoch, seq=snap.expected_seq, reason="chunk_limit_exceeded",
            raw_bytes=raw_bytes, limits=limits, guard=guard, proc=proc, collected=collected, salt=salt,
        )
    finally:
        if proc.stdin is not None:
            try:
                proc.stdin.close()
            except OSError:
                pass
        reader.join(timeout=1.0)
    return ChunkDeliveryResult(
        ok=snap.state is SessionState.COMPLETED,
        state=snap.state,
        chunks_delivered=snap.acked_chunks,
        anchor_committed=snap.anchor_committed,
        stdout_lines=tuple(collected),
        http_status=200 if snap.state is SessionState.COMPLETED else 400,
        reason=snap.terminal_reason,
    )
