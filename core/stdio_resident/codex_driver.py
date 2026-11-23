"""OpenAI Codex CLI app-server JSON-RPC drivers (legacy & v2 FSM) for resident stdio."""

# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import json
import threading
import time
import weakref
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar, cast, override

from core.stdio_resident.codex_protocol_fsm import (
    EffectKind, EventKind, ProtocolEffect, ProtocolEvent, ProtocolPhase, ProtocolState, transition,
)
from core.stdio_resident.protocol_driver import DecodedChunk, DriverCapabilities, StreamJsonDriver
from core.subbridge_zero_canon import is_zero_canon_profile
from core.zero_canon_fs import prepare_codex_zero_canon_home

_DENIED_ZC_CFG = ("mcp_servers", "plugins", "notify", "hooks")
_TERMINAL_STATUSES = frozenset({"completed", "failed", "interrupted"})


def _mapping(value: object) -> dict[str, Any] | None:
    return cast(dict[str, Any], value) if isinstance(value, dict) else None


def _encode_frame(payload: Mapping[str, object]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def _has_flag(argv: list[str], flag: str) -> bool:
    return any(item == flag or item.startswith(f"{flag}=") for item in argv)


def _append_cli_args(argv: list[str], raw_args: object) -> None:
    if not isinstance(raw_args, list | tuple):
        return
    for raw in raw_args:
        arg = str(raw)
        if arg and arg not in argv:
            argv.append(arg)


def _build_codex_argv(base_argv: list[str], options: Mapping[str, Any]) -> list[str]:
    argv = list(base_argv) if "app-server" in base_argv else [*base_argv, "app-server"]
    _append_cli_args(argv, options.get("cli_args"))
    for name, value in options.items():
        if not isinstance(name, str) or not name.startswith("--"):
            continue
        if value is None or value is False or _has_flag(argv, name):
            continue
        argv.append(name)
        if value is not True:
            argv.append(str(value))
    return argv


def _extract_cfg_arg(argv: list[str], idx: int) -> tuple[str | None, int]:
    tok = argv[idx]
    if tok in ("-c", "--config") and idx + 1 < len(argv):
        return argv[idx + 1], 2
    if tok.startswith(("-c=", "--config=")):
        return tok.split("=", 1)[1], 1
    return None, 1


def _is_denied_cfg_key(key: str) -> bool:
    return any(key == d or key.startswith(f"{d}.") for d in _DENIED_ZC_CFG)


def _zero_canon_overrides(model: str, effort: str) -> dict[str, str]:
    overrides = {"project_doc_max_bytes": "0"}
    if model and model != "default":
        overrides["model"] = json.dumps(model)
    if effort and effort != "default":
        overrides["model_reasoning_effort"] = json.dumps(effort)
    return overrides


def _build_zero_canon_argv(argv: list[str], model: str = "", effort: str = "") -> list[str]:
    overrides = _zero_canon_overrides(model, effort)
    cleaned, idx = [], 0
    while idx < len(argv):
        cfg_val, step = _extract_cfg_arg(argv, idx)
        if cfg_val is not None:
            key = cfg_val.split("=", 1)[0].strip()
            if _is_denied_cfg_key(key):
                raise ValueError(f"forbidden_codex_zero_canon_config:{key}")
            if key in overrides:
                idx += step
                continue
        cleaned.append(argv[idx])
        idx += 1
    res = cleaned if "app-server" in cleaned else [*cleaned, "app-server"]
    for k, v in overrides.items():
        res.extend(("-c", f"{k}={v}"))
    return res


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


def _format_effect_error(payload: Mapping[str, object]) -> str:
    code, msg = str(payload.get("code") or ""), str(payload.get("message") or "")
    if code and msg:
        return f"{code}: {msg}"
    return code or msg or "resident_protocol_failed"


def _effects_to_chunk(effects: tuple[ProtocolEffect, ...], payload: dict[str, Any]) -> DecodedChunk | None:
    if not effects:
        return None
    text_parts, reasoning_parts, error, is_term = [], [], None, False
    for eff in effects:
        if eff.kind is EffectKind.EMIT_DELTA:
            target = text_parts if eff.payload.get("channel") == "content" else reasoning_parts
            target.append(str(eff.payload.get("delta", "")))
        elif eff.kind is EffectKind.EMIT_ERROR:
            error = _format_effect_error(eff.payload)
        elif eff.kind is EffectKind.EMIT_TERMINAL:
            is_term = True
            if eff.payload.get("status") == "interrupted" and error is None:
                error = "turn_interrupted"
    return DecodedChunk(text="".join(text_parts), reasoning="".join(reasoning_parts), is_terminal=is_term, raw=payload, error=error)


def _legacy_error_text(payload: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    error = _mapping(payload.get("error"))
    if error is not None:
        return error, str(error.get("message") or error)
    raw_err = payload.get("error")
    return None, (str(raw_err) if raw_err is not None else None)


def _is_legacy_terminal(payload: Mapping[str, Any]) -> bool:
    return payload.get("method") == "turn/completed" or ("id" in payload and ("result" in payload or "error" in payload))


def _build_thread_params(ctx: Mapping[str, Any], zc: bool) -> dict[str, object]:
    params: dict[str, object] = {"ephemeral": True, "zero_canon": zc}
    model, cwd = ctx.get("model"), ctx.get("cwd")
    if isinstance(model, str) and model and model != "default":
        params["model"] = model
    if isinstance(cwd, str) and cwd:
        params["cwd"] = cwd
    return params


def _build_turn_params(prompt: str, ctx: Mapping[str, Any], zc: bool) -> dict[str, object]:
    params: dict[str, object] = {"prompt": prompt, "zero_canon": zc}
    if isinstance(ctx.get("input"), list):
        params["input"] = ctx["input"]
    for key in ("model", "effort"):
        val = ctx.get(key)
        if isinstance(val, str) and val and val != "default":
            params[key] = val
    return params


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


@dataclass(slots=True)
class _V2SlotState:
    state: ProtocolState
    last_turn_state: ProtocolState | None = None
    zero_canon: bool = False
    last_effects: tuple[ProtocolEffect, ...] = ()


class CodexAppServerV2Driver(StreamJsonDriver):
    """Contract-first Codex app-server v2 driver executing pure codex_protocol_fsm effects."""

    _capabilities: ClassVar[DriverCapabilities] = DriverCapabilities(
        protocol_name="codex-app-server-v2", supports_soft_cancel=True, supports_multi_turn=True
    )

    def __init__(self) -> None:
        self._tls: threading.local = threading.local()
        self._slot_lock: threading.Lock = threading.Lock()
        self._slot_states: weakref.WeakKeyDictionary[object, _V2SlotState] = weakref.WeakKeyDictionary()
        self._fallback_slots: dict[int, _V2SlotState] = {}

    def _ctx(self) -> _V2SlotState:
        ctx = cast(_V2SlotState | None, getattr(self._tls, "ctx", None))
        if ctx is None:
            ctx = _V2SlotState(state=ProtocolState())
            self._tls.ctx = ctx
        return ctx

    def _bind_handle_state(self, handle: Any, slot: _V2SlotState) -> None:
        self._tls.ctx = slot
        if handle is None:
            return
        with self._slot_lock:
            try:
                self._slot_states[handle] = slot
            except TypeError:
                self._fallback_slots[id(handle)] = slot

    def _lookup_handle_state(self, handle: Any) -> _V2SlotState | None:
        if handle is None:
            return None
        with self._slot_lock:
            try:
                found = self._slot_states.get(handle)
            except TypeError:
                found = None
            return found if found is not None else self._fallback_slots.get(id(handle))

    def _release_handle_state(self, handle: Any) -> None:
        if handle is None:
            return
        with self._slot_lock:
            try:
                self._slot_states.pop(handle, None)
            except TypeError:
                pass
            _ = self._fallback_slots.pop(id(handle), None)

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
        return self._ctx().zero_canon

    @_zero_canon.setter
    def _zero_canon(self, value: bool) -> None:
        self._ctx().zero_canon = value

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

    def build_zero_canon_env(self, base_env: Mapping[str, str], root: str) -> dict[str, str]:
        self._tls.ctx = _V2SlotState(state=ProtocolState(zero_canon=True), zero_canon=True)
        return prepare_codex_zero_canon_home(base_env, root)

    def build_zero_canon_argv(self, argv: list[str], model: str = "", effort: str = "") -> list[str]:
        return _build_zero_canon_argv(argv, model=model, effort=effort)

    def handshake_payload(self) -> bytes:
        _, effects = transition(ProtocolState(), ProtocolEvent(EventKind.START_INITIALIZE))
        return _first_send_frame(effects) or b""

    @override
    def run_handshake(self, handle: Any, timeout_s: float = 10.0) -> bool:
        zc = self._ctx().zero_canon
        slot = _V2SlotState(state=ProtocolState(zero_canon=zc), zero_canon=zc)
        self._bind_handle_state(handle, slot)
        try:
            self._send_effects(handle, self._apply(ProtocolEvent(EventKind.START_INITIALIZE)))
            return self._await_phase(handle, ProtocolPhase.INITIALIZED, timeout_s)
        except Exception:
            return False

    @override
    def prepare_turn(self, handle: Any, turn_context: Any, timeout_s: float = 5.0) -> bool:
        if (bound := self._lookup_handle_state(handle)) is not None:
            self._tls.ctx = bound
        ctx = _mapping(turn_context) or {}
        zc = self._zero_canon or is_zero_canon_profile(str(ctx.get("review_profile") or ""))
        self._zero_canon = zc
        self._last_turn_state = None
        if self._state.phase is ProtocolPhase.IDLE:
            return False
        if not zc and self._state.thread_id is not None and not ctx.get("new_thread"):
            return True
        try:
            effects = self._apply(ProtocolEvent(EventKind.START_THREAD, _build_thread_params(ctx, zc)))
            if self._state.phase is ProtocolPhase.FAILED:
                return False
            self._send_effects(handle, effects)
            return self._await_phase(handle, ProtocolPhase.THREAD_READY, timeout_s)
        except Exception:
            return False

    @override
    def encode_turn(self, prompt: str, turn_context: Mapping[str, Any] | None = None) -> bytes:
        if self._state.thread_id is None:
            raise ValueError("codex_v2_missing_server_thread_id")
        self._last_turn_state = None
        ctx = dict(turn_context or {})
        zc = self._zero_canon or is_zero_canon_profile(str(ctx.get("review_profile") or ""))
        effects = self._apply(ProtocolEvent(EventKind.START_TURN, _build_turn_params(prompt, ctx, zc)))
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
            probe = ProtocolState(
                phase=ProtocolPhase.TURN_ACTIVE, thread_id=tid if isinstance(tid, str) else None,
                turn_id=turn_id if isinstance(turn_id, str) else None, zero_canon=self._zero_canon,
            )
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
        return _effects_to_chunk(effects, payload)

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
        return True if self._state.phase is ProtocolPhase.IDLE else (
            params.get("threadId") == self._state.thread_id and turn.get("id") == self._state.turn_id
        )

    @override
    def is_tool_stop(self, raw_line: str, decoded: DecodedChunk | None) -> bool:
        return bool(decoded.is_tool_stop) if decoded is not None else False

    @override
    def build_cancel_payload(self) -> bytes | None:
        if self._state.phase is ProtocolPhase.TURN_ACTIVE:
            return _first_send_frame(self._apply(ProtocolEvent(EventKind.CANCEL_TURN)))
        return _encode_frame({
            "jsonrpc": "2.0", "id": self._state.next_request_id, "method": "turn/interrupt",
            "params": {"threadId": self._state.thread_id or "", "turnId": self._state.turn_id or ""},
        })

    def advance_epoch(self) -> int:
        _ = self._apply(ProtocolEvent(EventKind.ADVANCE_EPOCH))
        return self._state.epoch

    @override
    def perform_turn_teardown(self, handle: Any, turn_context: Any, timeout_s: float = 2.0) -> bool:
        _ = (turn_context, timeout_s)
        slot = self._ctx()
        slot.last_turn_state = slot.state
        _ = self.advance_epoch()
        if slot.zero_canon:
            self._release_handle_state(handle)
        return True
