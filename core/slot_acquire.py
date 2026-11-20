"""Отменяемый захват слота семафора с проверкой ухода клиента (`client_gone`)."""

from __future__ import annotations

import math
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

ENV_QUEUE_POLL_S = "BRIDGE_PASSTHROUGH_QUEUE_POLL_S"
DEFAULT_QUEUE_POLL_S = 0.1
MIN_QUEUE_POLL_S = 0.01
MAX_QUEUE_POLL_S = 5.0


def queue_poll_s(environ: Mapping[str, str] | None = None) -> float:
    """Интервал опроса ухода клиента при ожидании слота passthrough (из env)."""
    source = os.environ if environ is None else environ
    raw = str(source.get(ENV_QUEUE_POLL_S, "")).strip()
    if not raw:
        return DEFAULT_QUEUE_POLL_S
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_QUEUE_POLL_S
    if not math.isfinite(value):
        return DEFAULT_QUEUE_POLL_S
    return max(MIN_QUEUE_POLL_S, min(MAX_QUEUE_POLL_S, value))


def acquire_slot_cancellable(
    slots: Any,
    timeout_s: float,
    client_gone: Callable[[], bool],
    poll_s: float | None = None,
) -> str:
    """Захватить слот с отменой при уходе клиента: `'ok' | 'client_gone' | 'timeout'`."""
    if client_gone():
        return "client_gone"
    if slots.acquire(blocking=False):
        return "ok"
    deadline = time.monotonic() + max(0.0, timeout_s)
    step = max(MIN_QUEUE_POLL_S, queue_poll_s() if poll_s is None else poll_s)
    while True:
        if client_gone():
            return "client_gone"
        remaining = deadline - time.monotonic()
        if remaining <= 0.0:
            return "timeout"
        if slots.acquire(timeout=min(step, remaining)):
            return "ok"


@dataclass(frozen=True)
class SlotWaitOptions:
    """Параметры отменяемого ожидания слота (<= 5 args на acquire_slot_timed)."""

    poll_s: float | None = None
    keepalive: Callable[[], bool] | None = None
    keepalive_interval_s: float = 15.0
    clock: Callable[[], float] = time.monotonic


def _maybe_keepalive(
    opts: SlotWaitOptions, now: float, last_ka: float
) -> tuple[bool, float]:
    """Отправляет keepalive строго при interval > 0 и (now - last_ka) >= interval (не на t=0)."""
    alive = True
    updated = last_ka
    due = all((callable(opts.keepalive), opts.keepalive_interval_s > 0.0, (now - last_ka) >= opts.keepalive_interval_s))
    if due and callable(opts.keepalive):
        alive = bool(opts.keepalive())
        updated = now
    return alive, updated


def acquire_slot_timed(
    slots: Any,
    timeout_s: float,
    client_gone: Callable[[], bool],
    opts: SlotWaitOptions | None = None,
) -> tuple[str, int]:
    """Захватывает слот с замером queue_wait_ms и троттлингом keepalive (никогда на t=0)."""
    cfg = opts if isinstance(opts, SlotWaitOptions) else SlotWaitOptions()
    started = cfg.clock()
    outcome = ""
    if client_gone():
        outcome = "client_gone"
    elif slots.acquire(blocking=False):
        outcome = "ok"
    if not outcome:
        deadline = started + max(0.0, timeout_s)
        step = max(MIN_QUEUE_POLL_S, cfg.poll_s if isinstance(cfg.poll_s, (int, float)) else queue_poll_s())
        last_ka = started
        while not outcome:
            now = cfg.clock()
            alive, last_ka = _maybe_keepalive(cfg, now, last_ka)
            remaining = deadline - now
            if any((client_gone(), not alive)):
                outcome = "client_gone"
            elif remaining <= 0.0:
                outcome = "timeout"
            elif slots.acquire(timeout=min(step, remaining)):
                outcome = "ok"
    wait_ms = max(0, int(round((cfg.clock() - started) * 1000.0)))
    return outcome, wait_ms
