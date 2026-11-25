"""Errors and internal turn-state bundles for resident runtime orchestration."""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from core.stdio_resident.types import SlotBinding


class PreDispatchResidentError(RuntimeError):
    """Typed failure before upstream turn payload is committed to client."""

    http_status = 502

    def __init__(self, code: str = "warm_slot_mismatch_after_retry", status: int = 502) -> None:
        self.code = code
        self.http_status = status
        super().__init__(code)


class ResidentCancelledError(RuntimeError):
    """The caller cancelled a resident turn; never retried."""


class ResourceLimitError(RuntimeError):
    """Emulated-tool buffered output exceeded byte limit."""

    http_status = 502
    code = "output_limit_exceeded"


class ResidentStreamError(RuntimeError):
    """Malformed upstream wire text or surrogate encoding."""

    http_status = 502
    code = "invalid_upstream_encoding"

    def __init__(self, message: str = "", code: str = "invalid_upstream_encoding") -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ResidentTurnOptions:
    """Execution callbacks and caps for one resident runtime turn."""

    argv_builder: Callable[[], list[str]]
    cancel_event: threading.Event | None = None
    require_auth: bool = False
    extra_turn_context: Mapping[str, object] | None = None
    max_output_bytes: int | None = None
    terminal_validator: Callable[[str], None] | None = None
    keepalive: Callable[[], bool] | None = None


@dataclass(slots=True)
class _LockEntry:
    lock: threading.Lock = field(default_factory=threading.Lock)
    waiters: int = 0


@dataclass(slots=True)
class _TurnState:
    envelope: Any
    options: ResidentTurnOptions
    session_key: str
    slot: Any
    plan: Any
    non_committable: bool
    slot_released: bool = False
    committed_ok: bool = False
    released_gen: int | None = None
    dispatched: bool = False
    evicted: list[SlotBinding] = field(default_factory=list)
