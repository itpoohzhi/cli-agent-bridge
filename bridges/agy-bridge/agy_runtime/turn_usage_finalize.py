"""Финализация usage и bounded terminal_drain до usage_snapshot в agy-bridge (D4, W3)."""

from __future__ import annotations

import time
from collections.abc import Callable, MutableMapping
from typing import cast

from core.turn_usage_fsm import StepUsageSnapshot, resolve_turn_usage


def _remaining(deadline: float, clock: Callable[[], float]) -> float:
    return max(0.0, deadline - clock())


def ensure_drained_before_usage(
    run: object,
    out: MutableMapping[str, object],
    *,
    drain_max_s: float,
    enabled: bool = True,
    clock: Callable[[], float] = time.monotonic,
) -> bool:
    """Short-circuit (0 мс) на штатном _finish_done; иначе bounded terminal_drain + retained_events + join."""
    early = any((bool(out.get("tool_turn_stop")), bool(out.get("tool_turn_clean_eof"))))
    did_drain = False
    if all((enabled, early)):
        deadline = clock() + max(0.0, float(drain_max_s))
        drain_fn = getattr(run, "terminal_drain", None)
        if callable(drain_fn):
            rem = _remaining(deadline, clock)
            drained = drain_fn(rem)
            if isinstance(drained, (list, tuple)):
                if drained:
                    existing = out.get("retained_events")
                    buf = list(cast("list[object]", existing)) if isinstance(existing, list) else []
                    buf.extend(cast("list[object] | tuple[object, ...]", drained))
                    out["retained_events"] = buf
        tail = getattr(run, "_tail", None)
        if isinstance(tail, type(None)):
            tail = getattr(run, "tail", None)
        thread = getattr(tail, "thread", None)
        join_fn = getattr(thread, "join", None)
        rem_join = _remaining(deadline, clock)
        if all((callable(join_fn), rem_join > 0.0)):
            if callable(join_fn):
                _ = join_fn(timeout=rem_join)
        did_drain = True
    return did_drain


def resolve_and_log_step_usage(
    out: MutableMapping[str, object],
    snap: StepUsageSnapshot | None,
    window: int | None,
    resume: bool,
    log_fn: Callable[[str], None],
) -> dict[str, object]:
    """Вычисляет usage через core.turn_usage_fsm, логирует диагностику и возвращает resolved."""
    res = resolve_turn_usage(out, snap, window, resume)
    for msg in res.log_messages:
        log_fn(msg)
    return res.resolved


def format_usage_log_fields(
    resolved: object,
    safe_val: Callable[[str], str],
    num_text: Callable[[object], str],
) -> str:
    """Форматирует числовую диагностику usage для строки done."""
    out = ""
    if isinstance(resolved, dict):
        info = cast("dict[str, object]", resolved)
        raw_wire = info.get("wire")
        wire = cast("dict[str, object]", raw_wire) if isinstance(raw_wire, dict) else {}
        raw_src = info.get("source")
        src = safe_val(raw_src) if isinstance(raw_src, str) else ""
        raw_reason = info.get("reason")
        reason = safe_val(raw_reason) if isinstance(raw_reason, str) else ""
        out = (
            " usage_source=%s reason=%s step_idx=%s prompt=%s cached=%s completion=%s "
            "total=%s completeness=%d inconsistent=%d raw_in=%s raw_out=%s "
            "raw_thinking=%s raw_total=%s raw_cache=%s"
            % (
                src,
                reason if reason else "-",
                num_text(info.get("step_idx")),
                num_text(wire.get("prompt_tokens")),
                num_text(info.get("cached")),
                num_text(wire.get("completion_tokens")),
                num_text(wire.get("total_tokens")),
                int(bool(info.get("completeness"))),
                int(bool(info.get("inconsistent"))),
                num_text(info.get("raw_in")),
                num_text(info.get("raw_out")),
                num_text(info.get("raw_thinking")),
                num_text(info.get("raw_total")),
                num_text(info.get("raw_cache")),
            )
        )
    return out
