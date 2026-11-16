"""Session-scoped turn execution for resident stdio processes."""

# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import hashlib
import os
import threading
from collections.abc import Callable, Generator, Iterator, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, cast

from core.stdio_resident.process_pool import (
    ResidentProcessPool,
    SlotLeaseTimeoutError,
)
from core.stdio_resident.protocol_driver import DecodedChunk, StdioProtocolDriver
from core.stdio_resident.types import ExecutionFingerprint, SlotAffinityKey

__all__ = [
    "SessionTurnMode",
    "SessionTurnResult",
    "SlotLeaseTimeoutError",
    "StdioSessionManager",
]


class SessionTurnMode(str, Enum):
    """How the process backing a turn was obtained."""

    COLD = "cold"
    HOT = "hot"
    REBASE = "rebase"
    EPHEMERAL = "ephemeral"


@dataclass(frozen=True, slots=True)
class SessionTurnResult:
    """Materialized outcome and process identity for one turn."""

    mode: SessionTurnMode
    chunks: list[DecodedChunk]
    pid: int
    generation: int
    is_tool_stop: bool = False


class StdioSessionManager:
    """Execute isolated turns through affinity-bound resident processes."""

    def __init__(
        self,
        pool: ResidentProcessPool,
        driver: StdioProtocolDriver,
    ) -> None:
        self._pool: ResidentProcessPool = pool
        self._driver: StdioProtocolDriver = driver
        self._fingerprints: dict[str, str] = {}
        self._slot_ids: dict[str, str] = {}
        self._session_locks: dict[str, threading.Lock] = {}
        self._state_lock: threading.Lock = threading.Lock()

    def execute_turn(
        self,
        affinity_key: SlotAffinityKey,
        prompt: str,
        argv_builder: Callable[[], list[str]],
        cwd: str,
        env: Mapping[str, str] | None = None,
        turn_context: Mapping[str, Any] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> SessionTurnResult:
        """Execute and materialize one turn, including process metadata."""

        stream = self._execute_turn(
            affinity_key=affinity_key,
            prompt=prompt,
            argv_builder=argv_builder,
            cwd=cwd,
            env=env,
            turn_context=turn_context,
            cancel_event=cancel_event,
        )
        while True:
            try:
                _ = next(stream)
            except StopIteration as stop:
                return cast(SessionTurnResult, stop.value)

    def execute_turn_stream(
        self,
        affinity_key: SlotAffinityKey,
        prompt: str,
        argv_builder: Callable[[], list[str]],
        cwd: str,
        env: Mapping[str, str] | None = None,
        turn_context: Mapping[str, Any] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Iterator[DecodedChunk]:
        """Yield decoded chunks until the protocol reports turn completion."""

        return self._execute_turn(
            affinity_key=affinity_key,
            prompt=prompt,
            argv_builder=argv_builder,
            cwd=cwd,
            env=env,
            turn_context=turn_context,
            cancel_event=cancel_event,
        )

    def _execute_turn(
        self,
        affinity_key: SlotAffinityKey,
        prompt: str,
        argv_builder: Callable[[], list[str]],
        cwd: str,
        env: Mapping[str, str] | None,
        turn_context: Mapping[str, Any] | None,
        cancel_event: threading.Event | None,
    ) -> Generator[DecodedChunk, None, SessionTurnResult]:
        session_key = self._session_key(affinity_key)
        session_lock = self._get_session_lock(session_key)
        with session_lock:
            argv = list(argv_builder())
            fingerprint = self._build_fingerprint(argv, cwd, env)
            self._invalidate_changed_slot(session_key, fingerprint)

            slot = self._pool.acquire(
                affinity_key,
                lambda: list(argv),
                cwd,
                env,
            )
            with self._state_lock:
                self._fingerprints[session_key] = fingerprint.digest
                self._slot_ids[session_key] = slot.slot_id

            turn_generation = slot.handle.generation
            mode = (
                SessionTurnMode.HOT
                if turn_generation > 0 and slot.affinity_key == affinity_key
                else SessionTurnMode.COLD
            )
            chunks: list[DecodedChunk] = []
            terminal_received = False
            released = False
            is_tool_stop = False

            try:
                slot.handle.write(self._driver.encode_turn(prompt, turn_context))
                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        cancel_payload = self._driver.build_cancel_payload()
                        if cancel_payload is not None:
                            slot.handle.write(cancel_payload)
                        self._pool.release(slot.slot_id, cancel=True)
                        released = True
                        self._forget_slot(session_key, slot.slot_id)
                        break

                    tagged_line = slot.handle.read_line()
                    if tagged_line is None:
                        raise RuntimeError(
                            "resident process ended before the terminal marker"
                        )
                    raw_line = tagged_line.line
                    decoded = self._driver.decode_line(raw_line)
                    terminal_received = self._driver.is_terminal(raw_line, decoded)
                    if terminal_received:
                        is_tool_stop = self._driver.is_tool_stop(raw_line, decoded)
                        self._pool.release(slot.slot_id, success=True)
                        released = True
                    if decoded is not None:
                        chunks.append(decoded)
                        yield decoded
                    if terminal_received:
                        break
            finally:
                if not terminal_received and not released:
                    self._pool.release(slot.slot_id, cancel=True)
                    self._forget_slot(session_key, slot.slot_id)

            return SessionTurnResult(
                mode=mode,
                chunks=chunks,
                pid=slot.handle.pid,
                generation=turn_generation,
                is_tool_stop=is_tool_stop,
            )

    def _invalidate_changed_slot(
        self,
        session_key: str,
        fingerprint: ExecutionFingerprint,
    ) -> None:
        with self._state_lock:
            previous = self._fingerprints.get(session_key)
            if previous is None or previous == fingerprint.digest:
                return
            slot_id = self._slot_ids.pop(session_key, None)
            _ = self._fingerprints.pop(session_key, None)
        if slot_id is not None:
            self._pool.release(slot_id, cancel=True)

    def _forget_slot(self, session_key: str, slot_id: str) -> None:
        with self._state_lock:
            if self._slot_ids.get(session_key) == slot_id:
                _ = self._slot_ids.pop(session_key, None)

    def _get_session_lock(self, session_key: str) -> threading.Lock:
        with self._state_lock:
            lock = self._session_locks.get(session_key)
            if lock is None:
                lock = threading.Lock()
                self._session_locks[session_key] = lock
            return lock

    @staticmethod
    def _session_key(affinity_key: SlotAffinityKey) -> str:
        return "\0".join((affinity_key.owner_hash, affinity_key.chat_key))

    @staticmethod
    def _build_fingerprint(
        argv: list[str],
        cwd: str,
        env: Mapping[str, str] | None,
    ) -> ExecutionFingerprint:
        digest = hashlib.sha256()
        for argument in argv:
            digest.update(argument.encode())
            digest.update(b"\0")
        digest.update(cwd.encode())
        digest.update(b"\0")
        environment = os.environ if env is None else env
        for key, value in sorted(environment.items()):
            digest.update(key.encode())
            digest.update(b"=")
            digest.update(value.encode())
            digest.update(b"\0")
        return ExecutionFingerprint(digest.hexdigest())
