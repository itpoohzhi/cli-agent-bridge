"""OpenAI Codex CLI app-server JSON-RPC drivers (legacy & v2 FSM) for resident stdio."""

# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import json
import os
import threading
import time
import weakref
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, ClassVar, Final, cast, override

from core.codex_zero_canon_slim import enrich_zero_canon_thread_params
from core.stdio_resident.codex_cli_args import append_cli_args as _append_cli_args, build_codex_argv as _build_codex_argv, build_zero_canon_argv as _build_zero_canon_argv, extract_cfg_arg as _extract_cfg_arg, has_flag as _has_flag, is_denied_cfg_key as _is_denied_cfg_key, zero_canon_overrides as _zero_canon_overrides  # noqa: F401  (приватные алиасы для обратной совместимости)
from core.stdio_resident.codex_protocol_fsm import EffectKind, EventKind, ProtocolEffect, ProtocolEvent, ProtocolPhase, ProtocolState, transition
from core.stdio_resident.codex_std_home import is_codex_std_clean_home_enabled, is_codex_usage_frame_guard_enabled, prepare_codex_std_home
from core.stdio_resident.codex_usage import codex_v2_effects_to_chunk, extract_codex_legacy_usage
from core.stdio_resident.protocol_driver import DecodedChunk, DriverCapabilities, StreamJsonDriver
from core.subbridge_zero_canon import is_zero_canon_profile
from core.zc_admission import TurnProofRecorder, build_thread_params as _build_thread_params, build_turn_params as _build_turn_params
from core.zero_canon_fs import prepare_codex_zero_canon_home

_TERMINAL_STATUSES = frozenset({"completed", "failed", "interrupted"})
def _mapping(value: object) -> dict[str, Any] | None:
    return cast(dict[str, Any], value) if isinstance(value, dict) else None


def _encode_frame(payload: Mapping[str, object]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def _read_stdout_frame(handle: Any, timeout_s: float) -> Any:
    read_stdout = getattr(handle, "read_stdout_line", None)
    if callable(read_stdout):
        return read_stdout(timeout_s=timeout_s)
    deadline = time.monotonic() + max(0.0, timeout_s)
    while True:
        tagged = handle.read_line(timeout_s=max(0.0, deadline - time.monotonic()))
        if tagged is None or not getattr(tagged, "is_stderr", False):
            return tagged
        if time.monotonic() >= deadline:
            return None


def _first_send_frame(effects: tuple[ProtocolEffect, ...]) -> bytes | None:
    for eff in effects:
        if eff.kind is EffectKind.SEND_FRAME:
            return _encode_frame(eff.payload)
    return None


def _legacy_error_text(payload: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    error = _mapping(payload.get("error"))
    if error is not None:
        return error, str(error.get("message") or error)
    raw_err = payload.get("error")
    return None, (str(raw_err) if raw_err is not None else None)


def _is_legacy_terminal(payload: Mapping[str, Any]) -> bool:
    return payload.get("method") == "turn/completed" or ("id" in payload and ("result" in payload or "error" in payload))


def _verify_zc_clean_home(ctx: Mapping[str, Any]) -> bool:
    raw = ctx.get("zero_canon_root")
    if not (isinstance(raw, str) and raw.strip()):
        cwd = ctx.get("cwd")
        raw = cwd if isinstance(cwd, str) and os.path.basename(cwd.rstrip("/\\")).startswith("zc-") else ""
    p = raw.strip().rstrip("/\\") if isinstance(raw, str) else ""
    name = os.path.basename(p)
    if not p or not name.startswith("zc-") or name == "zc-codex-empty-cwd":
        return False
    leaf = os.path.join(os.path.realpath(os.path.dirname(p)), name)
    cdir = os.path.join(leaf, ".codex")
    cfg, auth = os.path.join(cdir, "config.toml"), os.path.join(cdir, "auth.json")
    return (os.path.isdir(leaf) and not os.path.islink(leaf) and os.path.isdir(cdir) and not os.path.islink(cdir)
            and os.path.isfile(cfg) and not os.path.islink(cfg) and not os.path.islink(auth))


class CodexAppServerDriver(StreamJsonDriver):
    """Legacy Codex app-server JSON-RPC driver preserved for flag-off parity."""

    _capabilities: ClassVar[DriverCapabilities] = DriverCapabilities(
        protocol_name="codex-app-server", supports_soft_cancel=True, supports_multi_turn=True
    )

    def __init__(self) -> None:
        self._next_id: int = 1

    @override
    def build_argv(self, base_argv: list[str], options: Mapping[str, Any]) -> list[str]:
        return _build_codex_argv(base_argv, options)

    @override
    def encode_turn(self, prompt: str, turn_context: Mapping[str, Any] | None = None) -> bytes:
        request_id, self._next_id = self._next_id, self._next_id + 1
        ctx = dict(turn_context or {})
        tid = str(ctx.get("thread_id") or ctx.get("threadId") or f"th-{request_id}")
        params: dict[str, Any] = {"threadId": tid, "input": [{"type": "text", "text": prompt}]}
        for key in ("model", "effort"):
            if key in ctx:
                params[key] = ctx[key]
        payload = {"jsonrpc": "2.0", "id": request_id, "method": str(ctx.get("action", "turn/start")), "params": params}
        return (json.dumps(payload, ensure_ascii=False) + "\n").encode()

    def _legacy_text(self, method: object, content: dict[str, Any], result: dict[str, Any] | None) -> tuple[str, str]:
        delta, text, reasoning = _mapping(content.get("delta")), "", ""
        if method in {"turn/delta", "turn/progress", "stream"}:
            raw_delta = content.get("delta")
            if isinstance(raw_delta, str):
                text = raw_delta
            elif delta is not None:
                text, reasoning = self._extract_string(delta, ("content", "text")), self._extract_string(delta, ("reasoning", "thought"))
            text = text or self._extract_string(content, ("text", "content"))
            reasoning = reasoning or self._extract_string(content, ("reasoning", "thought", "reasoning_content"))
        elif result is not None:
            text, reasoning = self._extract_string(result, ("output", "content", "text")), self._extract_string(result, ("reasoning", "thought", "reasoning_content"))
        return text, reasoning

    @override
    def decode_line(self, raw_line: str) -> DecodedChunk | None:
        payload = self._parse_object(raw_line)
        if payload is None or payload.get("jsonrpc") != "2.0":
            return None
        result = _mapping(payload.get("result"))
        content = result or _mapping(payload.get("params")) or {}
        text, reasoning = self._legacy_text(payload.get("method"), content, result)
        tool_calls = self._extract_tool_calls(content) or self._extract_tool_calls(payload)
        error, err_text = _legacy_error_text(payload)
        return DecodedChunk(
            text=text, reasoning=reasoning, tool_calls=tool_calls, is_terminal=_is_legacy_terminal(payload),
            is_tool_stop=bool(tool_calls) or self._tool_stop(content), raw=error if error is not None else payload, error=err_text,
            usage=extract_codex_legacy_usage(payload),
        )

    @override
    def is_terminal(self, raw_line: str, decoded: DecodedChunk | None) -> bool:
        if decoded is not None and decoded.is_terminal:
            return True
        p = self._parse_object(raw_line)
        return bool(p and p.get("jsonrpc") == "2.0" and _is_legacy_terminal(p))

    @override
    def is_tool_stop(self, raw_line: str, decoded: DecodedChunk | None) -> bool:
        if decoded is not None and decoded.is_tool_stop:
            return True
        p = self._parse_object(raw_line)
        res = (_mapping(p.get("result")) or p) if (p and p.get("jsonrpc") == "2.0") else None
        return bool(res is not None and (self._extract_tool_calls(res) or self._tool_stop(res)))

    @override
    def build_cancel_payload(self) -> bytes | None:
        return b'{"jsonrpc": "2.0", "method": "turn/cancel", "params": {}}\n'

    def build_zero_canon_env(self, base_env: Mapping[str, str], root: str) -> dict[str, str]:
        return prepare_codex_zero_canon_home(base_env, root)

    def build_zero_canon_argv(self, argv: list[str], model: str = "", effort: str = "") -> list[str]:
        return _build_zero_canon_argv(argv, model=model, effort=effort)

    def handshake_payload(self) -> bytes:
        return b'{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"clientInfo": {"name": "cli-agent-bridge", "version": "1.0"}}}\n'

    @override
    def run_handshake(self, handle: Any, timeout_s: float = 10.0) -> bool:
        try:
            handle.write(self.handshake_payload())
            line_obj = handle.read_line(timeout_s=timeout_s)
            parsed = self._parse_object(line_obj.line) if line_obj is not None else None
            return parsed is not None and "error" not in parsed
        except Exception:
            return False

    @classmethod
    def _tool_stop(cls, payload: Mapping[str, Any]) -> bool:
        return any(payload.get(k) is True or payload.get(k) in ("tool", "tool_call", "tool_calls", "tool_stop") for k in ("is_tool_stop", "tool_stop", "stop_reason", "status"))


_HANDLE_STATE_ATTR: Final[str] = "_codex_v2_slot_state"


@dataclass(slots=True)
class _V2SlotState:
    """Per-process FSM state; `state.zero_canon` is the single source of truth for Zero-Canon mode."""

    state: ProtocolState
    last_turn_state: ProtocolState | None = None
    last_effects: tuple[ProtocolEffect, ...] = ()
    bound_handle: object | None = None
    usage_guard_enabled: bool | None = None
    handshake_acked: bool = False
    turn_proof: TurnProofRecorder | None = None
    last_turn_proof: TurnProofRecorder | None = None


class CodexAppServerV2Driver(StreamJsonDriver):
    """Contract-first v2 driver: pure FSM effects; Zero-Canon truth in ProtocolState.zero_canon; per-thread
    _V2SlotState via TLS; per-handle state (attr or identity-checked weakref) survives cross-thread handoff."""

    _capabilities: ClassVar[DriverCapabilities] = DriverCapabilities(protocol_name="codex-app-server-v2", supports_soft_cancel=True, supports_multi_turn=True)

    def __init__(self) -> None:
        self._tls: threading.local = threading.local()
        self._slot_lock: threading.Lock = threading.Lock()
        self._weak_slots: dict[int, tuple[weakref.ReferenceType[object], _V2SlotState]] = {}

    def _ctx(self) -> _V2SlotState:
        ctx = cast(_V2SlotState | None, getattr(self._tls, "ctx", None))
        if ctx is None:
            ctx = _V2SlotState(state=ProtocolState())
            self._tls.ctx = ctx
        return ctx

    def _bind_handle_state(self, handle: Any, slot: _V2SlotState) -> None:
        slot.bound_handle = None
        self._tls.ctx = slot
        if handle is None:
            return
        try:
            setattr(handle, _HANDLE_STATE_ATTR, slot)
            return
        except (AttributeError, TypeError):
            pass
        key = id(handle)

        def _cleanup(dead_ref: weakref.ReferenceType[object], k: int = key) -> None:
            with self._slot_lock:
                cur = self._weak_slots.get(k)
                if cur is not None and cur[0] is dead_ref:
                    self._weak_slots.pop(k, None)

        try:
            ref = weakref.ref(handle, _cleanup)
        except TypeError:
            # Neither __dict__ nor __weakref__: hold identity reference for the turn (released in teardown).
            slot.bound_handle = handle
            return
        with self._slot_lock:
            self._weak_slots[key] = (ref, slot)

    def _lookup_handle_state(self, handle: Any) -> _V2SlotState | None:
        if handle is None:
            return None
        direct = getattr(handle, _HANDLE_STATE_ATTR, None)
        if isinstance(direct, _V2SlotState):
            return direct
        key = id(handle)
        with self._slot_lock:
            pair = self._weak_slots.get(key)
            if pair is None:
                return None
            ref, slot = pair
            if ref() is handle:
                return slot
            self._weak_slots.pop(key, None)
            return None

    def _release_handle_state(self, handle: Any) -> None:
        if handle is None:
            return
        try:
            if hasattr(handle, _HANDLE_STATE_ATTR):
                delattr(handle, _HANDLE_STATE_ATTR)
        except (AttributeError, TypeError):
            pass
        key = id(handle)
        with self._slot_lock:
            pair = self._weak_slots.get(key)
            if pair is not None and pair[0]() in (None, handle):
                self._weak_slots.pop(key, None)

    @property
    def _state(self) -> ProtocolState:
        return self._ctx().state

    @_state.setter
    def _state(self, value: ProtocolState) -> None:
        self._ctx().state = value

    @property
    def _last_turn_state(self) -> ProtocolState | None:
        return self._ctx().last_turn_state

    @_last_turn_state.setter
    def _last_turn_state(self, value: ProtocolState | None) -> None:
        self._ctx().last_turn_state = value

    @property
    def _zero_canon(self) -> bool:
        return self._ctx().state.zero_canon

    @_zero_canon.setter
    def _zero_canon(self, value: bool) -> None:
        ctx = self._ctx()
        ctx.state = replace(ctx.state, zero_canon=bool(value))

    @property
    def _last_effects(self) -> tuple[ProtocolEffect, ...]:
        return self._ctx().last_effects

    @_last_effects.setter
    def _last_effects(self, value: tuple[ProtocolEffect, ...]) -> None:
        self._ctx().last_effects = value

    @property
    def protocol_state(self) -> ProtocolState:
        return self._ctx().state

    @property
    def last_turn_state(self) -> ProtocolState | None:
        return self._ctx().last_turn_state

    @property
    def turn_proof(self) -> TurnProofRecorder | None:
        return self._ctx().turn_proof

    @property
    def last_turn_proof(self) -> TurnProofRecorder | None:
        return self._ctx().last_turn_proof

    def consume_last_turn_proof(self) -> TurnProofRecorder | None:
        p = self._ctx().last_turn_proof
        self._ctx().last_turn_proof = None
        return p

    def _apply(self, event: ProtocolEvent) -> tuple[ProtocolEffect, ...]:
        self._state, effects = transition(self._state, event)
        self._last_effects = effects
        return effects

    @staticmethod
    def _send_effects(handle: Any, effects: tuple[ProtocolEffect, ...]) -> None:
        for eff in effects:
            if eff.kind is EffectKind.SEND_FRAME:
                handle.write(_encode_frame(eff.payload))

    def _await_phase(self, handle: Any, target: ProtocolPhase, timeout_s: float) -> bool:
        deadline = time.monotonic() + max(0.0, timeout_s)
        while True:
            tagged = _read_stdout_frame(handle, max(0.0, deadline - time.monotonic()))
            if tagged is None:
                return False
            parsed = self._parse_object(tagged.line)
            if parsed is not None:
                self._send_effects(handle, self._apply(ProtocolEvent(EventKind.SERVER_FRAME, parsed, epoch=self._state.epoch)))
                if self._state.phase is target:
                    return True
                if self._state.phase is ProtocolPhase.FAILED:
                    return False
            if time.monotonic() >= deadline:
                return False

    @override
    def build_argv(self, base_argv: list[str], options: Mapping[str, Any]) -> list[str]:
        return _build_codex_argv(base_argv, options)

    @override
    def build_env(self, base_env: Mapping[str, str], turn_sandbox: str | None = None) -> dict[str, str]:
        if is_codex_std_clean_home_enabled(base_env):
            return prepare_codex_std_home(base_env, turn_sandbox)
        return dict(base_env)

    def build_zero_canon_env(self, base_env: Mapping[str, str], root: str) -> dict[str, str]:
        return prepare_codex_zero_canon_home(base_env, root)

    def build_zero_canon_argv(self, argv: list[str], model: str = "", effort: str = "") -> list[str]:
        return _build_zero_canon_argv(argv, model=model, effort=effort)

    def handshake_payload(self) -> bytes:
        _, effects = transition(ProtocolState(), ProtocolEvent(EventKind.START_INITIALIZE))
        return _first_send_frame(effects) or b""

    @override
    def run_handshake(self, handle: Any, timeout_s: float = 10.0) -> bool:
        slot = _V2SlotState(state=ProtocolState(zero_canon=False))
        self._bind_handle_state(handle, slot)
        try:
            self._send_effects(handle, self._apply(ProtocolEvent(EventKind.START_INITIALIZE)))
            ok = self._await_phase(handle, ProtocolPhase.INITIALIZED, timeout_s)
        except Exception:
            ok = False
        slot.handshake_acked = bool(ok and slot.state.phase is ProtocolPhase.INITIALIZED)
        if not ok:
            self._release_handle_state(handle)
            self._tls.ctx = None
        return ok

    @override
    def prepare_turn(self, handle: Any, turn_context: Any, timeout_s: float = 5.0) -> bool:
        if (bound := self._lookup_handle_state(handle)) is not None:
            self._tls.ctx = bound
        elif handle is not None:
            cur = cast(_V2SlotState | None, getattr(self._tls, "ctx", None))
            if cur is None or cur.bound_handle is not handle:
                self._tls.ctx = _V2SlotState(state=ProtocolState())
        ctx = _mapping(turn_context) or {}
        profile_raw = ctx.get("review_profile")
        zc = is_zero_canon_profile(profile_raw) if isinstance(profile_raw, str) and profile_raw.strip() else False
        self._last_turn_state = None
        slot = self._ctx()
        slot.last_turn_proof = None
        slot.turn_proof = None
        slot.usage_guard_enabled = is_codex_usage_frame_guard_enabled()
        if self._state.phase is ProtocolPhase.IDLE:
            return False
        if not zc and not self._state.zero_canon and self._state.thread_id is not None and not ctx.get("new_thread"):
            return True
        try:
            tp = enrich_zero_canon_thread_params(_build_thread_params(ctx, zc), zc, env=_mapping(ctx.get("env")))
            effects = self._apply(ProtocolEvent(EventKind.START_THREAD, tp))
            if self._state.phase is ProtocolPhase.FAILED:
                return False
            self._send_effects(handle, effects)
            ok = self._await_phase(handle, ProtocolPhase.THREAD_READY, timeout_s)
            if zc and ok:
                rec = TurnProofRecorder(handshake_acked=slot.handshake_acked, clean_home_verified=_verify_zc_clean_home(ctx))
                rec.record_thread(self._state.thread_id or "", self._state.epoch)
                slot.turn_proof = rec
            return ok
        except Exception:
            return False

    @override
    def encode_turn(self, prompt: str, turn_context: Mapping[str, Any] | None = None) -> bytes:
        if self._state.thread_id is None:
            raise ValueError("codex_v2_missing_server_thread_id")
        self._last_turn_state = None
        self._ctx().last_turn_proof = None
        ctx = dict(turn_context or {})
        profile_raw = ctx.get("review_profile")
        zc = is_zero_canon_profile(profile_raw) if isinstance(profile_raw, str) and profile_raw.strip() else self._state.zero_canon
        effects = self._apply(ProtocolEvent(EventKind.START_TURN, _build_turn_params(prompt, ctx, zc)))
        if (rec := self._ctx().turn_proof) is not None:
            rec.turn_epoch = self._state.epoch
        frame = _first_send_frame(effects)
        if frame is None or self._state.phase is ProtocolPhase.FAILED:
            raise RuntimeError(self._state.error_code or "resident_protocol_failed")
        return frame

    def _probe_effects(self, payload: Mapping[str, Any]) -> tuple[ProtocolEffect, ...]:
        if "id" in payload and ("result" in payload or "error" in payload):
            probe = ProtocolState(phase=ProtocolPhase.TURN_ACTIVE, pending_request_id=payload["id"], thread_id="probe", zero_canon=self._zero_canon)
        else:
            params = _mapping(payload.get("params")) or {}
            turn = _mapping(params.get("turn"))
            tid, turn_id = params.get("threadId"), params.get("turnId") or (turn.get("id") if turn else None)
            probe = ProtocolState(phase=ProtocolPhase.TURN_ACTIVE, thread_id=tid if isinstance(tid, str) else None,
                                  turn_id=turn_id if isinstance(turn_id, str) else None, zero_canon=self._zero_canon)
        _, effects = transition(probe, ProtocolEvent(EventKind.SERVER_FRAME, payload, epoch=probe.epoch))
        return effects

    @override
    def decode_line(self, raw_line: str) -> DecodedChunk | None:
        payload = self._parse_object(raw_line)
        if payload is None:
            return None
        effects = (
            self._apply(ProtocolEvent(EventKind.SERVER_FRAME, payload, epoch=self._state.epoch))
            if self._state.phase is not ProtocolPhase.IDLE
            else self._probe_effects(payload)
        )
        if (rec := self._ctx().turn_proof) is not None:
            if self._state.turn_id:
                rec.record_turn(self._state.turn_id, self._state.epoch)
            if any(e.kind is EffectKind.EMIT_ERROR and e.payload.get("code") == "zero_canon_tool_event_forbidden" for e in effects):
                rec.record_tool_event()
        guard = self._ctx().usage_guard_enabled
        if guard is None:
            guard = self._ctx().usage_guard_enabled = is_codex_usage_frame_guard_enabled()
        return codex_v2_effects_to_chunk(effects, payload, active_thread_id=self._state.thread_id,
                                         active_turn_id=self._state.turn_id, guard_enabled=guard)

    @override
    def is_terminal(self, raw_line: str, decoded: DecodedChunk | None) -> bool:
        if decoded is not None:
            return decoded.is_terminal
        p = self._parse_object(raw_line)
        if p is None or p.get("method") != "turn/completed":
            return False
        params = _mapping(p.get("params")) or {}
        turn = _mapping(params.get("turn"))
        if turn is None or turn.get("status") not in _TERMINAL_STATUSES:
            return False
        return True if self._state.phase is ProtocolPhase.IDLE else (params.get("threadId") == self._state.thread_id and turn.get("id") == self._state.turn_id)

    @override
    def is_tool_stop(self, raw_line: str, decoded: DecodedChunk | None) -> bool:
        return bool(decoded.is_tool_stop) if decoded is not None else False

    @override
    def build_cancel_payload(self) -> bytes | None:
        if self._state.phase is ProtocolPhase.TURN_ACTIVE:
            return _first_send_frame(self._apply(ProtocolEvent(EventKind.CANCEL_TURN)))
        return _encode_frame({"jsonrpc": "2.0", "id": self._state.next_request_id, "method": "turn/interrupt",
                              "params": {"threadId": self._state.thread_id or "", "turnId": self._state.turn_id or ""}})

    def advance_epoch(self) -> int:
        _ = self._apply(ProtocolEvent(EventKind.ADVANCE_EPOCH))
        return self._state.epoch

    @override
    def perform_turn_teardown(self, handle: Any, turn_context: Any, timeout_s: float = 2.0) -> bool:
        _ = timeout_s
        keep_warm_zc = bool(isinstance(turn_context, Mapping) and turn_context.get("keyed_zero_canon"))
        bound = self._lookup_handle_state(handle)
        slot = bound if bound is not None else self._ctx()
        self._tls.ctx = slot
        slot.last_turn_state = slot.state
        was_zero_canon = slot.state.zero_canon
        slot.last_turn_proof = slot.turn_proof.snapshot() if slot.turn_proof is not None else None
        slot.turn_proof = None
        _ = self.advance_epoch()
        if bound is None:
            # Release identity reference for bare non-weakref handles so GC can reclaim and no id() alias matches.
            slot.bound_handle = None
        if was_zero_canon and not keep_warm_zc:
            self._release_handle_state(handle)
        elif was_zero_canon:
            self._reset_thread_for_warm_reuse(slot)
        return True

    def _reset_thread_for_warm_reuse(self, slot: _V2SlotState) -> None:
        """Keyed Zero-Canon: FSM-состояние слота живёт дальше (без повторного `initialize`/респавна), тред — сбрасывается."""
        phase = ProtocolPhase.INITIALIZED if slot.handshake_acked else slot.state.phase
        if slot.state.phase is not ProtocolPhase.FAILED:
            slot.state = replace(slot.state, phase=phase, thread_id=None, turn_id=None, pending_request_id=None)
