"""Session-scoped turn execution for resident stdio processes."""

# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import tempfile
import threading
import time
from collections.abc import Callable, Generator, Iterator, Mapping
from contextlib import suppress
from dataclasses import dataclass
from enum import Enum
from typing import IO, Any, cast

from core.stdio_resident.config import StdioPoolConfig
from core.stdio_resident.process_pool import ResidentProcessPool, SlotLeaseTimeoutError
from core.stdio_resident.process_io import TIMEOUT
from core.stdio_resident.protocol_driver import DecodedChunk, StdioProtocolDriver
from core.stdio_resident.types import ExecutionFingerprint, SlotAffinityKey
from core.stdio_resident.zero_canon_router import ZeroCanonIsolation, zero_canon_isolation

__all__ = ["SessionTurnMode", "SessionTurnResult", "SlotLeaseTimeoutError", "StdioSessionManager"]


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
        self, pool: ResidentProcessPool, driver: StdioProtocolDriver,
        config: StdioPoolConfig | None = None,
    ) -> None:
        self._pool: ResidentProcessPool = pool
        self._driver: StdioProtocolDriver = driver
        self._config: StdioPoolConfig | None = config
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
        stream = self._execute_turn(affinity_key, prompt, argv_builder, cwd, env, turn_context, cancel_event)
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
        is_ephemeral: bool = False,
    ) -> Iterator[DecodedChunk]:
        """Yield decoded chunks until the protocol reports turn completion."""
        return self._execute_turn(affinity_key, prompt, argv_builder, cwd, env, turn_context, cancel_event, is_ephemeral=is_ephemeral)

    def _execute_turn(
        self,
        affinity_key: SlotAffinityKey,
        prompt: str,
        argv_builder: Callable[[], list[str]],
        cwd: str,
        env: Mapping[str, str] | None,
        turn_context: Mapping[str, Any] | None,
        cancel_event: threading.Event | None,
        is_ephemeral: bool = False,
    ) -> Generator[DecodedChunk, None, SessionTurnResult]:
        session_key = self._session_key(affinity_key)
        with self._get_session_lock(session_key), zero_canon_isolation(self._driver, affinity_key.review_profile) as iso:
            is_ephemeral = is_ephemeral or iso.active  # Zero-Canon не смешивается с пулом
            cfg = self._config or getattr(self._pool, "_config", None) or StdioPoolConfig()
            turn_idle_s = float(getattr(cfg, "turn_idle_timeout_s", 180.0))
            turn_total_s = float(getattr(cfg, "turn_total_timeout_s", 600.0))
            handshake_timeout_s = float(getattr(cfg, "handshake_timeout_s", 10.0))
            leave_timeout_s = float(getattr(cfg, "leave_timeout_s", 2.0))
            verify_fn = getattr(self._driver, "verify_environment", None)
            if callable(verify_fn):
                ok, reason = verify_fn()
                if not ok:
                    raise RuntimeError(reason or "driver environment verification failed")
            sandbox_args_fn = getattr(self._driver, "build_sandbox_args", None)
            sandbox_args = list(sandbox_args_fn()) if callable(sandbox_args_fn) else []
            base_argv = iso.argv(list(argv_builder()), affinity_key.model, affinity_key.effort)
            argv = base_argv + [f for f in sandbox_args if f not in base_argv]
            fp_fn = getattr(self._driver, "compute_fingerprint", None)
            fingerprint = self._build_fingerprint(argv, cwd, env, str(fp_fn()) if callable(fp_fn) else "")
            self._invalidate_changed_slot(session_key, fingerprint)
            turn_sandbox = tempfile.mkdtemp(prefix="turn-")
            os.chmod(turn_sandbox, 0o700)
            spawn_env = self._resolve_spawn_env(env, iso)
            turn_context_for_turn: dict[str, Any] = {**(turn_context or {}), "turn_sandbox": turn_sandbox}
            try:
                slot = self._pool.acquire(affinity_key, lambda: list(argv), cwd, spawn_env, is_ephemeral=is_ephemeral)
            except BaseException:
                with suppress(FileNotFoundError):
                    shutil.rmtree(turn_sandbox)
                raise
            with self._state_lock:
                self._fingerprints[session_key] = fingerprint.digest
                self._slot_ids[session_key] = slot.slot_id
            turn_generation = slot.handle.generation
            mode = SessionTurnMode.HOT if turn_generation > 0 and slot.affinity_key == affinity_key else SessionTurnMode.COLD
            chunks: list[DecodedChunk] = []
            terminal_received = teardown_completed = released = is_tool_stop = False
            lease_id = getattr(slot, "lease_id", None)
            lock_path = f"{turn_sandbox}.lock"
            lock_file: IO[str] | None = None
            total_deadline = time.monotonic() + turn_total_s
            try:
                lock_file = self._acquire_lock(lock_path, slot.handle)
                if turn_generation == 0:
                    handshake_fn = getattr(self._driver, "run_handshake", None)
                    if callable(handshake_fn) and handshake_fn(slot.handle, timeout_s=handshake_timeout_s) is False:
                        raise RuntimeError("protocol handshake failed")
                prepare_fn = getattr(self._driver, "prepare_turn", None)
                if callable(prepare_fn) and prepare_fn(slot.handle, turn_context_for_turn, timeout_s=handshake_timeout_s) is False:
                    raise RuntimeError("turn preparation failed")
                slot.handle.write(self._driver.encode_turn(prompt, turn_context_for_turn))
                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        cancel_payload = self._driver.build_cancel_payload()
                        if cancel_payload is not None:
                            slot.handle.write(cancel_payload)
                        self._pool.release(slot.slot_id, cancel=True, lease_id=lease_id)
                        released = True
                        self._forget_slot(session_key, slot.slot_id)
                        break
                    remaining_total_s = total_deadline - time.monotonic()
                    if remaining_total_s <= 0.0:
                        raise RuntimeError("turn total timeout exceeded")
                    timeout = min(turn_idle_s, remaining_total_s)
                    read_outcome = getattr(slot.handle, "read_line_outcome", None)
                    kind, tagged_line = read_outcome(timeout_s=timeout) if callable(read_outcome) else ("", slot.handle.read_line(timeout_s=timeout))
                    if kind == TIMEOUT:
                        raise TimeoutError(f"resident process idle {timeout:g}s without output")
                    if tagged_line is None:
                        raise RuntimeError("resident process ended before the terminal marker")
                    raw_line = tagged_line.line
                    decoded = self._driver.decode_line(raw_line)
                    if decoded is not None:
                        if (chunk_error := getattr(decoded, "error", None)) is not None:
                            self._pool.release(slot.slot_id, cancel=True, lease_id=lease_id)
                            released = True
                            self._forget_slot(session_key, slot.slot_id)
                            raise RuntimeError(chunk_error)
                        reply_bytes = getattr(decoded, "reply_bytes", None)
                        if reply_bytes is not None:
                            slot.handle.write(reply_bytes)
                    terminal_received = self._driver.is_terminal(raw_line, decoded)
                    if terminal_received:
                        is_tool_stop = self._driver.is_tool_stop(raw_line, decoded)
                        teardown_fn = getattr(self._driver, "perform_turn_teardown", None)
                        if callable(teardown_fn) and teardown_fn(slot.handle, turn_context_for_turn, timeout_s=leave_timeout_s) is False:
                            raise RuntimeError("turn teardown failed")
                        self._cleanup_sandbox(turn_sandbox, lock_file, lock_path)
                        teardown_completed = True
                        self._pool.release(slot.slot_id, success=True, lease_id=lease_id)
                        released = True
                    if decoded is not None:
                        chunks.append(decoded)
                        yield decoded
                    if terminal_received:
                        break
            finally:
                if not teardown_completed:
                    if not released:
                        self._pool.release(slot.slot_id, cancel=True, lease_id=lease_id)
                        self._forget_slot(session_key, slot.slot_id)
                    if getattr(slot.handle, "_pgid_dead", True):
                        self._cleanup_sandbox(turn_sandbox, lock_file, lock_path)
                    elif lock_file is not None:
                        with suppress(OSError):
                            lock_file.close()
            return SessionTurnResult(mode=mode, chunks=chunks, pid=slot.handle.pid, generation=turn_generation, is_tool_stop=is_tool_stop)

    def _resolve_spawn_env(self, env: Mapping[str, str] | None, iso: ZeroCanonIsolation | None = None) -> Mapping[str, str] | None:
        base_env = dict(os.environ if env is None else env)
        if iso is not None and (isolated := iso.env(base_env)) is not None:
            return isolated
        build_env_fn = getattr(self._driver, "build_env", None)
        if not callable(build_env_fn):
            return env
        built_env = build_env_fn(base_env, turn_sandbox=None)
        return None if (env is None and built_env == base_env) else built_env

    @staticmethod
    def _acquire_lock(lock_path: str, handle: Any) -> IO[str]:
        lock_file = open(lock_path, "w", encoding="utf-8")
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            pid = getattr(handle, "pid", 0)
            payload = {"pid": pid, "pgid": getattr(handle, "_pgid", pid), "start_time": getattr(handle, "_start_time", "")}
            lock_file.write(json.dumps(payload, separators=(",", ":")))
            lock_file.flush()
        except BaseException:
            lock_file.close()
            raise
        return lock_file

    @staticmethod
    def _cleanup_sandbox(turn_sandbox: str, lock_file: IO[str] | None, lock_path: str | None) -> None:
        with suppress(FileNotFoundError):
            shutil.rmtree(turn_sandbox)
        if lock_file is not None:
            with suppress(OSError):
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            with suppress(OSError):
                lock_file.close()
        if lock_path is not None:
            with suppress(FileNotFoundError):
                os.unlink(lock_path)

    def _invalidate_changed_slot(self, session_key: str, fingerprint: ExecutionFingerprint) -> None:
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
        return "\0".join((affinity_key.owner_hash, affinity_key.chat_key, affinity_key.review_profile))

    @staticmethod
    def _build_fingerprint(argv: list[str], cwd: str, env: Mapping[str, str] | None, driver_fp: str = "") -> ExecutionFingerprint:
        digest = hashlib.sha256()
        for argument in argv:
            digest.update(argument.encode())
            digest.update(b"\0")
        digest.update(cwd.encode())
        digest.update(b"\0")
        if driver_fp:
            digest.update(driver_fp.encode())
            digest.update(b"\0")
        environment = os.environ if env is None else env
        for key, value in sorted(environment.items()):
            digest.update(key.encode())
            digest.update(b"=")
            digest.update(value.encode())
            digest.update(b"\0")
        return ExecutionFingerprint(digest.hexdigest())
