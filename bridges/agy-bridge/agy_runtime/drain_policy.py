"""Ранний выход post-EOF drain agy-bridge: Zero-I/O предикат + исполнитель цикла."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

FAST_SILENCE_FLOOR_MS: Final[float] = 15.0
FAST_MAX_WAIT_MS: Final[float] = 25.0
_FAST_POLL_STEP_S: Final[float] = 0.005


@dataclass(frozen=True, slots=True)
class DrainSnapshot:
    eof_seen: bool
    tools_used: int
    final_planner_seen: bool
    pending_steps: int
    elapsed_after_eof_ms: float
    last_byte_age_ms: float
    fast_drain_enabled: bool


@dataclass(frozen=True, slots=True)
class DrainDecision:
    should_exit: bool
    max_wait_ms: float
    reason: str


def decide_drain(snap: DrainSnapshot) -> DrainDecision:
    """4-факторный предикат раннего выхода; всё прочее — legacy (should_exit=False, 400 мс)."""
    fast = all((snap.fast_drain_enabled, snap.eof_seen, snap.tools_used == 0,
                snap.final_planner_seen, snap.pending_steps == 0))
    if not fast:
        return DrainDecision(False, 400.0, "legacy_window")
    if snap.last_byte_age_ms >= FAST_SILENCE_FLOOR_MS or snap.elapsed_after_eof_ms >= FAST_MAX_WAIT_MS:
        return DrainDecision(True, FAST_MAX_WAIT_MS, "final_planner_fast_exit")
    return DrainDecision(False, FAST_MAX_WAIT_MS, "waiting_silence_floor")


def tools_used_of(tail: Any) -> int:
    """Fail-closed: любой признак tool-шага даёт > 0."""
    run_ref = getattr(tail, "run_ref", None)
    seen = getattr(tail, "seen", None) or {}
    counts = [getattr(tail, "tools_count", 0), getattr(run_ref, "tools_count", 0)]
    for holder in (tail, run_ref):
        steps = getattr(holder, "_tool_step_indices", None) or ()
        counts.append(len(steps))
        counts.append(sum(1 for k in seen if k in steps))
    return max(int(c) for c in counts if isinstance(c, int))


def run_post_eof_drain(
    tail: Any, *, drain_window_s: float, drain_max_s: float, drain_min_s: float,
    poll_step_s: float, fast_drain_enabled: bool,
    on_deadline_pending: Callable[[], None], log_fn: Callable[[str], None],
) -> None:
    """Процесс вышел: дочитать источники в окне drain_window_s (<= drain_max_s).

    Досрочно: END_TURN/TURN_COMPLETE после drain_min_s (exit=end_turn), stop_event
    (exit=stop) или 4-факторный fast-exit (exit=final_planner_fast_exit, флаг-gated).
    """
    t = tail  # _TranscriptTail живёт в server.py (монолит) — контракт утиной типизации
    started = time.monotonic()
    dl = t.drain_deadline
    deadline = min(dl if dl > 0 else started + drain_window_s, started + drain_max_s)
    earliest, emitted_before, exit_kind = started + drain_min_s, t.emitted, "window"
    fast_complete = bool(getattr(t, "fast_complete_drain", False))
    fast_earliest = started + float(getattr(t, "fast_drain_min_s", 0.015))
    while True:
        if t.stop_event.is_set():
            exit_kind = "stop"
            break
        iter_emitted = t.emitted
        t._read_transcript()
        if t.sqlite_active:
            _ = t._poll_sqlite()
        now = time.monotonic()
        if now >= earliest and t.end_marker:
            exit_kind = "end_turn"
            break
        if fast_complete and now >= fast_earliest and t.final_planner and t.emitted == iter_emitted and t._pending_steps() == 0:
            exit_kind = "fast_complete"
            break
        if fast_drain_enabled:
            lb = getattr(t, "_last_byte_at", 0.0)
            snap = DrainSnapshot(
                True, tools_used_of(t),
                bool(getattr(t, "final_planner", False) or getattr(t, "_plain_final", False)),
                t._pending_steps(), (now - started) * 1000.0,
                (now - lb) * 1000.0 if lb > 0 else (now - started) * 1000.0, True)
            if (dec := decide_drain(snap)).should_exit:
                exit_kind = dec.reason
                break
        if now >= deadline:
            break
        step = min(poll_step_s, _FAST_POLL_STEP_S) if fast_drain_enabled else poll_step_s
        time.sleep(min(step, max(0.0, deadline - now)))
    pending = t._pending_steps()
    complete = pending == 0 and (t.final_planner or t.end_marker)
    t.drain_outcome = "complete" if complete else "window_complete"
    if exit_kind != "stop" and pending > 0:
        on_deadline_pending()
    tag = getattr(getattr(t, "run_ref", None), "tag", "")
    log_fn(
        f"drain cid={t._cid8()} ms={int((time.monotonic() - started) * 1000)} "
        f"emitted={t.emitted - emitted_before} outcome={t.drain_outcome} "
        f"pending_steps={pending} exit={exit_kind} {tag}"
    )
