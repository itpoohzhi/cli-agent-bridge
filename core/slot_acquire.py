"""Отменяемый захват слота семафора с проверкой ухода клиента (`client_gone`)."""

from __future__ import annotations

import math
import os
import time
from collections.abc import Callable, Mapping
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
