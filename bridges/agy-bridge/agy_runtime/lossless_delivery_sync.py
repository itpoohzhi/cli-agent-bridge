"""Sync primitives, state wrapper, and metadata helpers for lossless delivery."""

from __future__ import annotations

import inspect
import logging
import os
import sys
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, cast

from core.lossless_contracts import LosslessLimits, LossReceipt
from core.lossless_delivery_policy import MAX_FINAL_TURN_TOTAL_S, ChunkDeliveryOptions
from core.lossless_fsm import SessionEvent, SessionSnapshot, SessionState, step

from .chunk_delivery_adapter import ChunkDeliveryResult
from .process_admission_guard import ProcessAdmissionGuard

_STATUS_BY_STATE: Final[Mapping[SessionState, int]] = MappingProxyType(
    {
        SessionState.COMPLETED: 200,
        SessionState.REJECTED: 413,
        SessionState.CANCELLED: 499,
        SessionState.EPOCH_MISMATCH: 409,
    }
)
_RECEIPT_KEYS: Final[tuple[str, ...]] = tuple(
    "ok state chunks_delivered anchor_committed http_status reason".split()
)


def terminal_http_status(state: SessionState) -> int:
    """Map a terminal SessionState to its HTTP status code."""
    return _STATUS_BY_STATE.get(state, 400)


def resolve_log_fn(run: object) -> Callable[[str], None]:
    """Resolve callable _log on run, run's module, or fallback warning logger."""
    found = [
        cast(Callable[[str], None], fn)
        for owner in (run, sys.modules.get(type(run).__module__))
        if callable(fn := getattr(owner, "_log", None))
    ]
    log_fn = found[0] if found else logging.getLogger("agy_bridge.lossless").warning
    return log_fn


def run_request_id(run: object) -> str:
    """Return run.req_id or fallback pid=<pid>."""
    req_id = getattr(run, "req_id", None)
    res = str(req_id) if req_id else f"pid={os.getpid()}"
    return res


def summarize_receipt(receipt: LossReceipt | None) -> str:
    """Format allow-listed receipt metadata as key=value pairs."""
    summary = ""
    if receipt:
        raw: object = receipt
        pairs = (
            ((k, raw.get(k)) for k in _RECEIPT_KEYS)
            if isinstance(raw, Mapping)
            else ((k, getattr(raw, k, None)) for k in _RECEIPT_KEYS)
        )
        summary = " ".join(f"{k}={v}" for k, v in pairs if v is not None)
    return summary


def make_delivery_result(snap: SessionSnapshot, reason: str) -> ChunkDeliveryResult:
    """Build a ChunkDeliveryResult from a SessionSnapshot."""
    return ChunkDeliveryResult(
        ok=snap.state == SessionState.COMPLETED,
        state=snap.state,
        chunks_delivered=snap.acked_chunks,
        anchor_committed=snap.anchor_committed,
        stdout_lines=(),
        http_status=terminal_http_status(snap.state),
        reason=reason,
    )


class LosslessDeliveryChannel:
    """Thread-safe single-slot handoff and latest-snapshot owner for Phase A/B."""

    def __init__(self, initial_snap: SessionSnapshot | None = None) -> None:
        self._lock, self._done = threading.Lock(), threading.Event()
        self._latest_snap, self._timed_out = initial_snap, False
        self._result: ChunkDeliveryResult | None = None

    def record_snapshot(self, snap: SessionSnapshot | None) -> None:
        with self._lock:
            if not self._timed_out:
                self._latest_snap = snap

    def latest_snapshot(self) -> SessionSnapshot | None:
        with self._lock:
            return self._latest_snap

    def publish(
        self, res: ChunkDeliveryResult | None, run: object | None = None
    ) -> None:
        with self._lock:
            if not self._timed_out:
                self._result = res
                if run:
                    setattr(run, "_lossless_result", res)
                self._done.set()

    def mark_timed_out(self) -> SessionSnapshot | None:
        with self._lock:
            self._timed_out = True
            return self._latest_snap

    def wait(self, timeout_s: float) -> bool:
        return self._done.wait(timeout_s)

    def result(self) -> ChunkDeliveryResult | None:
        with self._lock:
            return self._result


class FinalTurnIdleWatchdog:
    """Sliding idle-window + absolute-cap watchdog firing on_timeout at most once."""

    def __init__(
        self,
        idle_timeout_s: float,
        on_timeout: Callable[..., object],
        *,
        clock: Callable[[], float] = time.monotonic,
        max_total_s: float = MAX_FINAL_TURN_TOTAL_S,
    ) -> None:
        self._lock, self._stop = threading.Lock(), threading.Event()
        self._idle, self._cap = idle_timeout_s, max_total_s
        self._clock, self._on_timeout = clock, on_timeout
        self._start = self._last = clock()
        self._fired, self._fire_count = False, 0
        self._thread: threading.Thread | None = None

    @property
    def fire_count(self) -> int:
        with self._lock:
            return self._fire_count

    def touch(self) -> None:
        with self._lock:
            self._last = self._clock()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._fired = True
            self._stop.set()
            thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=1.0)

    def _run(self) -> None:
        while not self._stop.is_set():
            waited_s, rem = -1.0, 0.0
            with self._lock:
                if self._fired:
                    break
                now = self._clock()
                dl = min(self._last + self._idle, self._start + self._cap)
                if (rem := dl - now) <= 0.0:
                    self._fired, waited_s = True, max(0.0, now - self._start)
                    self._fire_count += 1
            if waited_s >= 0.0:
                p = inspect.signature(self._on_timeout).parameters
                self._on_timeout(waited_s) if p else self._on_timeout()
                break
            self._stop.wait(rem)


class _FinalTurnState:
    """Lock-protected FSM state and result updater for the final turn."""

    def __init__(self, snap: SessionSnapshot, run: object) -> None:
        self._lock, self._snap, self._run = threading.Lock(), snap, run

    def snapshot(self) -> SessionSnapshot:
        with self._lock:
            return self._snap

    def transition(self, event: SessionEvent) -> tuple[bool, SessionSnapshot]:
        with self._lock:
            changed = not self._snap.is_terminal
            if changed:
                self._snap, _ = step(self._snap, event)
                res = make_delivery_result(self._snap, event.reason)
                setattr(self._run, "_lossless_result", res)
            return changed, self._snap


@dataclass(frozen=True, slots=True)
class FinalTurnContext:
    """Coordinated Phase A/B context passed into stream_final_turn."""

    channel: LosslessDeliveryChannel
    guard: ProcessAdmissionGuard
    limits: LosslessLimits
    options: ChunkDeliveryOptions
    n_chunks: int
