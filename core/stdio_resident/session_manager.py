"""Session-scoped turn execution for resident stdio processes."""

# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import hashlib
import inspect
import math
import os
import shutil
import tempfile
import threading
import time
from collections.abc import Callable, Generator, Iterator, Mapping
from contextlib import suppress
from dataclasses import dataclass
from enum import Enum
from typing import IO, Any, Final, cast

from core.stdio_resident.config import StdioPoolConfig
from core.stdio_resident.process_io import TIMEOUT
from core.stdio_resident.process_pool import ResidentProcessPool, SlotLeaseTimeoutError
from core.stdio_resident.protocol_driver import DecodedChunk, StdioProtocolDriver
from core.stdio_resident.types import ExecutionFingerprint, SlotAffinityKey
from core.stdio_resident.zero_canon_router import ZeroCanonIsolation, zero_canon_isolation
from core.zero_canon_fs import acquire_turn_lock, cleanup_turn_sandbox

__all__ = ["SessionTurnMode", "SessionTurnResult", "SlotLeaseTimeoutError", "StdioSessionManager", "TurnTimeoutError"]

DEFAULT_FIRST_PROGRESS_TIMEOUT_S: Final[float] = 60.0
DEFAULT_TURN_IDLE_TIMEOUT_S: Final[float] = 180.0
DEFAULT_SAFETY_CAP_S: Final[float] = 900.0
_TIMEOUT_CODES: Final[dict[str, str]] = {
    "first_progress": "first_progress_timeout",
    "idle": "idle_timeout",
    "safety_cap": "safety_cap_timeout",
}


class TurnTimeoutError(TimeoutError):
    """Typed timeout separating first-progress, idle, and safety cap."""

    http_status: int = 504

    def __init__(self, timeout_kind: str, message: str) -> None:
        self.timeout_kind: str = timeout_kind
        self.code: str = _TIMEOUT_CODES.get(timeout_kind, "turn_timeout")
        super().__init__(f"{self.code}: {message}")


class SessionTurnMode(str, Enum):
    """How the process backing a turn was obtained."""

    COLD, HOT, REBASE, EPHEMERAL = "cold", "hot", "rebase", "ephemeral"


@dataclass(frozen=True, slots=True)
class SessionTurnResult:
    """Materialized outcome and process identity for one turn."""

    mode: SessionTurnMode
    chunks: list[DecodedChunk]
    pid: int
    generation: int
    is_tool_stop: bool = False


@dataclass(frozen=True, slots=True)
class _TurnRequest:
    affinity_key: SlotAffinityKey
    prompt: str
    argv_builder: Callable[[], list[str]]
    cwd: str
    env: Mapping[str, str] | None = None
    turn_context: Mapping[str, Any] | None = None
    cancel_event: threading.Event | None = None
    is_ephemeral: bool = False


@dataclass(slots=True)
class _TurnDeadlines:
    idle_s: float
    safety_deadline: float
    first_progress_deadline: float
    idle_deadline: float
    has_progress: bool = False

    def record_useful(self, now: float) -> None:
        self.has_progress = True
        if now < self.safety_deadline:
            self.idle_deadline = max(self.idle_deadline, min(self.safety_deadline, now + self.idle_s))

    def next_timeout(self, now: float) -> float:
        if now >= self.safety_deadline:
            raise TurnTimeoutError("safety_cap", "turn safety cap exceeded")
        active = min(self.idle_deadline if self.has_progress else self.first_progress_deadline, self.safety_deadline)
        if now >= active:
            kind = "idle" if self.has_progress else "first_progress"
            raise TurnTimeoutError(kind, f"resident process {kind} timeout exceeded")
        return active - now

    def timeout_error(self, now: float) -> TurnTimeoutError:
        active = self.idle_deadline if self.has_progress else self.first_progress_deadline
        if now >= self.safety_deadline or self.safety_deadline <= active:
            return TurnTimeoutError("safety_cap", "turn safety cap exceeded")
        kind = "idle" if self.has_progress else "first_progress"
        return TurnTimeoutError(kind, f"resident process {kind} timeout exceeded")


@dataclass(slots=True)
class _ActiveTurn:
    slot: Any
    session_key: str
    mode: SessionTurnMode
    turn_sandbox: str
    lock_path: str
    turn_context: dict[str, Any]
    lease_id: str | None
    turn_generation: int
    lock_file: IO[str] | None = None
    turn_started: bool = False
    teardown_completed: bool = False
    released: bool = False
    is_tool_stop: bool = False


def _parse_pos_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) and parsed > 0.0 else None


def _pick_timeout(ctx: Mapping[str, Any], cfg: object, names: tuple[str, ...], env_key: str) -> float | None:
    for name in names:
        if (val := _parse_pos_float(ctx.get(name))) is not None:
            return val
    for name in names:
        if (val := _parse_pos_float(getattr(cfg, name, None))) is not None:
            return val
    return _parse_pos_float(os.environ.get(env_key))


def _resolve_deadlines(cfg: object, ctx: Mapping[str, Any], now: float) -> _TurnDeadlines:
    idle_s = _pick_timeout(ctx, cfg, ("idle_timeout_s", "turn_idle_timeout_s"), "BRIDGE_STDIO_TURN_IDLE_TIMEOUT_S")
    idle_val = DEFAULT_TURN_IDLE_TIMEOUT_S if idle_s is None else idle_s
    first_raw = _pick_timeout(ctx, cfg, ("first_progress_timeout_s", "turn_first_progress_timeout_s"), "BRIDGE_STDIO_FIRST_PROGRESS_TIMEOUT_S")
    first_val = min(DEFAULT_FIRST_PROGRESS_TIMEOUT_S if first_raw is None else first_raw, idle_val)
    cap_raw = _pick_timeout(ctx, cfg, ("safety_cap_s", "turn_safety_cap_s"), "BRIDGE_STDIO_SAFETY_CAP_S")
    legacy_total = _parse_pos_float(getattr(cfg, "turn_total_timeout_s", None)) or DEFAULT_SAFETY_CAP_S
    cap_val = max(DEFAULT_SAFETY_CAP_S, idle_val, legacy_total) if cap_raw is None else cap_raw
    safety_dl = now + cap_val
    return _TurnDeadlines(idle_val, safety_dl, min(safety_dl, now + first_val), min(safety_dl, now + idle_val))


def _collect_id_maps(raw: object) -> list[Mapping[str, Any]]:
    if not isinstance(raw, Mapping):
        return []
    root = cast(Mapping[str, Any], raw)
    nodes: list[Mapping[str, Any]] = [root]
    for key in ("params", "result", "turn"):
        sub = root.get(key)
        if isinstance(sub, Mapping):
            sub_map = cast(Mapping[str, Any], sub)
            nodes.append(sub_map)
            if isinstance(sub_map.get("turn"), Mapping):
                nodes.append(cast(Mapping[str, Any], sub_map["turn"]))
    return nodes


def _track_fsm_ids(decoded: DecodedChunk, ctx: dict[str, Any]) -> None:
    for src in _collect_id_maps(getattr(decoded, "raw", None)):
        tid = src.get("thread_id") or src.get("threadId")
        if isinstance(tid, str) and tid:
            ctx["thread_id"] = tid
        turn_id = src.get("turn_id") or src.get("turnId") or (src.get("id") if "status" in src else None)
        if isinstance(turn_id, str) and turn_id:
            ctx["turn_id"] = turn_id


def _resolve_fsm_ids(driver: object, ctx: Mapping[str, Any]) -> tuple[str | None, str | None]:
    state = getattr(driver, "fsm_state", None) or getattr(driver, "state", None)
    tid = getattr(state, "thread_id", None) or ctx.get("thread_id") or ctx.get("threadId")
    turn_id = getattr(state, "turn_id", None) or ctx.get("turn_id") or ctx.get("turnId")
    return (tid if isinstance(tid, str) else None), (turn_id if isinstance(turn_id, str) else None)


def _build_cancel_payload(driver: object, ctx: Mapping[str, Any]) -> bytes | None:
    fn = getattr(driver, "build_cancel_payload", None)
    if not callable(fn):
        return None
    params: Mapping[str, Any] = {}
    with suppress(TypeError, ValueError):
        params = inspect.signature(fn).parameters
    if "thread_id" in params and "turn_id" in params:
        tid, turn_id = _resolve_fsm_ids(driver, ctx)
        return cast(bytes | None, fn(thread_id=tid, turn_id=turn_id))
    if "turn_context" in params:
        return cast(bytes | None, fn(turn_context=ctx))
    return cast(bytes | None, fn())


def _read_next_line(handle: Any, timeout_s: float) -> tuple[str, Any]:
    read_stdout = getattr(handle, "read_stdout_outcome", None)
    if callable(read_stdout):
        return cast(tuple[str, Any], read_stdout(timeout_s=timeout_s))
    read_outcome = getattr(handle, "read_line_outcome", None)
    if callable(read_outcome):
        return cast(tuple[str, Any], read_outcome(timeout_s=timeout_s))
    return ("", handle.read_line(timeout_s=timeout_s))


def _resolve_turn_mode(is_ephemeral: bool, slot: Any, affinity_key: SlotAffinityKey) -> SessionTurnMode:
    if is_ephemeral:
        return SessionTurnMode.EPHEMERAL
    if slot.handle.generation > 0 and slot.affinity_key == affinity_key:
        return SessionTurnMode.HOT
    return SessionTurnMode.COLD


class StdioSessionManager:
    """Execute isolated turns through affinity-bound resident processes."""

    def __init__(
        self, pool: ResidentProcessPool, driver: StdioProtocolDriver, config: StdioPoolConfig | None = None, *, clock: Callable[[], float] | None = None
    ) -> None:
        self._pool, self._driver, self._config = pool, driver, config
        self._clock: Callable[[], float] = clock or time.monotonic
        self._fingerprints: dict[str, str] = {}
        self._slot_ids: dict[str, str] = {}
        self._session_locks: dict[str, threading.Lock] = {}
        self._state_lock: threading.Lock = threading.Lock()

    def execute_turn(
        self, affinity_key: SlotAffinityKey, prompt: str, argv_builder: Callable[[], list[str]], cwd: str,
        env: Mapping[str, str] | None = None, turn_context: Mapping[str, Any] | None = None, cancel_event: threading.Event | None = None,
    ) -> SessionTurnResult:
        """Execute and materialize one turn, including process metadata."""
        chunks: list[DecodedChunk] = []
        stream = self._run_turn(_TurnRequest(affinity_key, prompt, argv_builder, cwd, env, turn_context, cancel_event))
        while True:
            try:
                chunks.append(next(stream))
            except StopIteration as stop:
                res = cast(SessionTurnResult, stop.value)
                return SessionTurnResult(res.mode, chunks, res.pid, res.generation, res.is_tool_stop)

    def execute_turn_stream(
        self, affinity_key: SlotAffinityKey, prompt: str, argv_builder: Callable[[], list[str]], cwd: str,
        env: Mapping[str, str] | None = None, turn_context: Mapping[str, Any] | None = None,
        cancel_event: threading.Event | None = None, is_ephemeral: bool = False,
    ) -> Iterator[DecodedChunk]:
        """Yield decoded chunks until completion without accumulating them in memory."""
        return self._run_turn(_TurnRequest(affinity_key, prompt, argv_builder, cwd, env, turn_context, cancel_event, is_ephemeral))

    def _run_turn(self, req: _TurnRequest) -> Generator[DecodedChunk, None, SessionTurnResult]:
        session_key = self._session_key(req.affinity_key)
        with self._get_session_lock(session_key), zero_canon_isolation(self._driver, req.affinity_key.review_profile) as iso:
            cfg = self._config or getattr(self._pool, "_config", None) or StdioPoolConfig()
            active = self._acquire_turn(req, iso, session_key)
            deadlines = _resolve_deadlines(cfg, active.turn_context, self._clock())
            try:
                self._start_protocol(active, req.prompt, float(getattr(cfg, "handshake_timeout_s", 10.0)))
                yield from self._stream_turn(active, req.cancel_event, deadlines, float(getattr(cfg, "leave_timeout_s", 2.0)))
            finally:
                self._finalize_turn(active)
            return SessionTurnResult(active.mode, [], active.slot.handle.pid, active.turn_generation, active.is_tool_stop)

    def _build_launch_spec(self, req: _TurnRequest, iso: ZeroCanonIsolation) -> tuple[list[str], str, ExecutionFingerprint]:
        verify_fn = getattr(self._driver, "verify_environment", None)
        if callable(verify_fn):
            ok, reason = cast(tuple[bool, str], verify_fn())
            if not ok:
                raise RuntimeError(reason or "driver environment verification failed")
        sandbox_fn = getattr(self._driver, "build_sandbox_args", None)
        sandbox_args = list(cast(list[str], sandbox_fn())) if callable(sandbox_fn) else []
        base_argv = iso.argv(list(req.argv_builder()), req.affinity_key.model, req.affinity_key.effort)
        argv = base_argv + [flag for flag in sandbox_args if flag not in base_argv]
        effective_cwd = iso.cwd if (iso.active and iso.cwd) else req.cwd
        fp_fn = getattr(self._driver, "compute_fingerprint", None)
        return argv, effective_cwd, self._build_fingerprint(argv, effective_cwd, req.env, str(fp_fn()) if callable(fp_fn) else "")

    def _acquire_turn(self, req: _TurnRequest, iso: ZeroCanonIsolation, session_key: str) -> _ActiveTurn:
        is_ephemeral = req.is_ephemeral or iso.active
        argv, effective_cwd, fp = self._build_launch_spec(req, iso)
        if not is_ephemeral:
            self._invalidate_changed_slot(session_key, fp)
        turn_sandbox = tempfile.mkdtemp(prefix="turn-")
        os.chmod(turn_sandbox, 0o700)
        ctx: dict[str, Any] = {**(req.turn_context or {}), "turn_sandbox": turn_sandbox, "cwd": effective_cwd, "review_profile": req.affinity_key.review_profile}
        try:
            slot = self._pool.acquire(req.affinity_key, lambda: list(argv), effective_cwd, self._resolve_spawn_env(req.env, iso), is_ephemeral=is_ephemeral)
        except BaseException:
            with suppress(FileNotFoundError):
                shutil.rmtree(turn_sandbox)
            raise
        if not is_ephemeral:
            with self._state_lock:
                self._fingerprints[session_key], self._slot_ids[session_key] = fp.digest, slot.slot_id
        mode = _resolve_turn_mode(is_ephemeral, slot, req.affinity_key)
        return _ActiveTurn(slot, session_key, mode, turn_sandbox, f"{turn_sandbox}.lock", ctx, getattr(slot, "lease_id", None), slot.handle.generation)

    def _start_protocol(self, active: _ActiveTurn, prompt: str, handshake_s: float) -> None:
        active.lock_file = self._acquire_lock(active.lock_path, active.slot.handle)
        if active.turn_generation == 0:
            handshake_fn = getattr(self._driver, "run_handshake", None)
            if callable(handshake_fn) and handshake_fn(active.slot.handle, timeout_s=handshake_s) is False:
                raise RuntimeError("protocol handshake failed")
        prepare_fn = getattr(self._driver, "prepare_turn", None)
        if callable(prepare_fn) and prepare_fn(active.slot.handle, active.turn_context, timeout_s=handshake_s) is False:
            raise RuntimeError("turn preparation failed")
        active.slot.handle.write(self._driver.encode_turn(prompt, active.turn_context))
        active.turn_started = True

    def _stream_turn(
        self, active: _ActiveTurn, cancel_event: threading.Event | None, deadlines: _TurnDeadlines, leave_s: float
    ) -> Generator[DecodedChunk, None, None]:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                self._cancel_active(active, send_payload=True)
                break
            kind, tagged_line = _read_next_line(active.slot.handle, deadlines.next_timeout(self._clock()))
            if kind == TIMEOUT:
                raise deadlines.timeout_error(self._clock())
            if tagged_line is None:
                active.turn_started = False
                raise RuntimeError("resident process ended before the terminal marker")
            if getattr(tagged_line, "is_stderr", False):
                continue
            decoded = self._process_line(active, tagged_line.line, deadlines, leave_s)
            if decoded is not None:
                yield decoded
            if active.teardown_completed:
                break

    def _process_line(self, active: _ActiveTurn, raw_line: str, deadlines: _TurnDeadlines, leave_s: float) -> DecodedChunk | None:
        decoded = self._driver.decode_line(raw_line)
        if decoded is not None:
            _track_fsm_ids(decoded, active.turn_context)
            if (chunk_error := getattr(decoded, "error", None)) is not None:
                self._cancel_active(active, send_payload=False)
                raise RuntimeError(chunk_error)
            if decoded.text or decoded.reasoning or decoded.tool_calls:
                deadlines.record_useful(self._clock())
            if (reply_bytes := getattr(decoded, "reply_bytes", None)) is not None:
                active.slot.handle.write(reply_bytes)
        if self._driver.is_terminal(raw_line, decoded):
            active.is_tool_stop = self._driver.is_tool_stop(raw_line, decoded)
            teardown_fn = getattr(self._driver, "perform_turn_teardown", None)
            if callable(teardown_fn) and teardown_fn(active.slot.handle, active.turn_context, timeout_s=leave_s) is False:
                raise RuntimeError("turn teardown failed")
            self._cleanup_sandbox(active.turn_sandbox, active.lock_file, active.lock_path)
            active.teardown_completed = True
            self._pool.release(active.slot.slot_id, success=True, lease_id=active.lease_id)
            active.released = True
        return decoded

    def _cancel_active(self, active: _ActiveTurn, *, send_payload: bool = True) -> None:
        if send_payload and active.turn_started:
            if (payload := _build_cancel_payload(self._driver, active.turn_context)) is not None:
                with suppress(Exception):
                    active.slot.handle.write(payload)
        if not active.released:
            try:
                self._pool.release(active.slot.slot_id, cancel=True, lease_id=active.lease_id)
            finally:
                active.released = True
                self._forget_slot(active.session_key, active.slot.slot_id)

    def _finalize_turn(self, active: _ActiveTurn) -> None:
        if active.teardown_completed:
            return
        try:
            if not active.released:
                self._cancel_active(active, send_payload=active.turn_started)
        finally:
            if getattr(active.slot.handle, "_pgid_dead", True):
                self._cleanup_sandbox(active.turn_sandbox, active.lock_file, active.lock_path)
            elif active.lock_file is not None:
                with suppress(OSError):
                    active.lock_file.close()

    def _resolve_spawn_env(self, env: Mapping[str, str] | None, iso: ZeroCanonIsolation | None = None) -> Mapping[str, str] | None:
        if iso is not None and iso.active:
            if (isolated := iso.env(dict(os.environ))) is not None:
                return isolated
        base_env = dict(os.environ)
        if env is not None:
            base_env.update(env)
        build_env_fn = getattr(self._driver, "build_env", None)
        if not callable(build_env_fn):
            return env
        built_env = cast(Mapping[str, str], build_env_fn(base_env, turn_sandbox=None))
        return None if (env is None and built_env == base_env) else built_env

    @staticmethod
    def _acquire_lock(lock_path: str, handle: Any) -> IO[str]:
        return cast(IO[str], acquire_turn_lock(lock_path, handle))

    @staticmethod
    def _cleanup_sandbox(turn_sandbox: str, lock_file: IO[str] | None, lock_path: str | None) -> None:
        cleanup_turn_sandbox(turn_sandbox, lock_file, lock_path)

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
                lock = self._session_locks[session_key] = threading.Lock()
            return lock

    @staticmethod
    def _session_key(affinity_key: SlotAffinityKey) -> str:
        return "\0".join((affinity_key.owner_hash, affinity_key.chat_key, affinity_key.review_profile))

    @staticmethod
    def _build_fingerprint(argv: list[str], cwd: str, env: Mapping[str, str] | None, driver_fp: str = "") -> ExecutionFingerprint:
        digest = hashlib.sha256()
        for item in (*argv, cwd, *((driver_fp,) if driver_fp else ())):
            digest.update(item.encode() + b"\0")
        for key, value in sorted((os.environ if env is None else env).items()):
            digest.update(f"{key}={value}\0".encode())
        return ExecutionFingerprint(digest.hexdigest())
