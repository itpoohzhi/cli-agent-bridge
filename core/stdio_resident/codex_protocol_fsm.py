"""Pure zero-I/O protocol FSM for Codex app-server v2 (0.171.0-alpha.13)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import TypeAlias, cast

JsonMap: TypeAlias = Mapping[str, object]


class ProtocolPhase(str, Enum):
    IDLE, INITIALIZING, INITIALIZED = "IDLE", "INITIALIZING", "INITIALIZED"
    THREAD_STARTING, THREAD_READY, TURN_ACTIVE = "THREAD_STARTING", "THREAD_READY", "TURN_ACTIVE"
    COMPLETED, FAILED, CANCELLED = "COMPLETED", "FAILED", "CANCELLED"


class EventKind(str, Enum):
    START_INITIALIZE, START_THREAD, START_TURN = "start_initialize", "start_thread", "start_turn"
    SERVER_FRAME, CANCEL_TURN = "server_frame", "cancel_turn"
    ADVANCE_EPOCH, TRANSPORT_ERROR = "advance_epoch", "transport_error"


class EffectKind(str, Enum):
    SEND_FRAME, EMIT_DELTA, EMIT_TURN_ACK = "send_frame", "emit_delta", "emit_turn_ack"
    EMIT_TERMINAL, EMIT_ERROR = "emit_terminal", "emit_error"


@dataclass(frozen=True)
class ProtocolEvent:
    kind: EventKind
    payload: JsonMap = field(default_factory=dict[str, object])
    epoch: int | None = None


@dataclass(frozen=True)
class ProtocolEffect:
    kind: EffectKind
    payload: JsonMap = field(default_factory=dict[str, object])


@dataclass(frozen=True)
class ProtocolState:
    phase: ProtocolPhase = ProtocolPhase.IDLE
    epoch: int = 0
    next_request_id: int = 1
    pending_request_id: int | str | None = None
    interrupt_request_id: int | str | None = None
    thread_id: str | None = None
    turn_id: str | None = None
    zero_canon: bool = False
    requested_model: str | None = None
    requested_effort: str | None = None
    actual_model: str | None = None
    actual_effort: str | None = None
    user_agent: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    pending_utf8: bytes = b""


TransitionResult: TypeAlias = tuple[ProtocolState, tuple[ProtocolEffect, ...]]
_Handler: TypeAlias = Callable[[ProtocolState, JsonMap], TransitionResult]

_DELTAS: Mapping[str, str] = {
    "item/agentMessage/delta": "content",
    "item/reasoning/textDelta": "reasoning",
    "item/reasoning/summaryTextDelta": "reasoning_summary",
}
_TOOL_METHODS = frozenset(
    "item/tool/call item/tool/requestUserInput applyPatchApproval execCommandApproval "
    "item/commandExecution/requestApproval item/fileChange/requestApproval "
    "item/permissions/requestApproval item/commandExecution/outputDelta "
    "item/fileChange/outputDelta item/commandExecution/terminalInteraction "
    "item/fileChange/patchUpdated item/mcpToolCall/progress".split()
)
_TOOL_ITEMS = frozenset(
    "commandExecution fileChange mcpToolCall dynamicToolCall collabAgentToolCall webSearch".split()
)
_THREAD_PHASES = frozenset(
    (ProtocolPhase.INITIALIZED, ProtocolPhase.THREAD_READY, ProtocolPhase.COMPLETED, ProtocolPhase.CANCELLED)
)
_TURN_PHASES = frozenset((ProtocolPhase.THREAD_READY, ProtocolPhase.COMPLETED, ProtocolPhase.CANCELLED))


def _as_map(val: object) -> JsonMap | None:
    return cast(JsonMap, val) if isinstance(val, Mapping) else None


def _str(val: object) -> str | None:
    return val if isinstance(val, str) and val else None


def _rpc(method: str, params: JsonMap, rid: int | None = None) -> ProtocolEffect:
    frame: dict[str, object] = {"jsonrpc": "2.0", "method": method}
    if rid is not None:
        frame["id"], frame["params"] = rid, params
    return ProtocolEffect(EffectKind.SEND_FRAME, frame)


def _fail(s: ProtocolState, code: str, msg: str) -> TransitionResult:
    nxt = replace(
        s, phase=ProtocolPhase.FAILED, pending_request_id=None,
        interrupt_request_id=None, error_code=code, error_message=msg,
    )
    return nxt, (ProtocolEffect(EffectKind.EMIT_ERROR, {"code": code, "message": msg}),)


def _term(s: ProtocolState, phase: ProtocolPhase, status: str, bump: bool = False) -> TransitionResult:
    nxt = replace(
        s, phase=phase, epoch=s.epoch + int(bump),
        pending_request_id=None, interrupt_request_id=None,
    )
    meta: dict[str, object] = {"status": status, "thread_id": s.thread_id, "turn_id": s.turn_id}
    return nxt, (ProtocolEffect(EffectKind.EMIT_TERMINAL, meta),)


def _err(err: object, default: str) -> str:
    m = _as_map(err)
    return (_str(m.get("message")) if m is not None else None) or (str(err) if err else default)


def _extract_id(res: JsonMap | None, obj: str, flat: str) -> str | None:
    if res is None:
        return None
    nested = _as_map(res.get(obj))
    return _str(nested.get("id")) if nested is not None else _str(res.get(flat))


def _is_tool_event(method: str, params: JsonMap) -> bool:
    if method in _TOOL_METHODS:
        return True
    item = _as_map(params.get("item")) if method in ("item/started", "item/completed") else None
    return item is not None and item.get("type") in _TOOL_ITEMS


def _start_initialize(s: ProtocolState, p: JsonMap) -> TransitionResult:
    if s.phase is not ProtocolPhase.IDLE:
        return _fail(s, "resident_protocol_failed", "initialize requires IDLE")
    info = {
        "name": _str(p.get("client_name")) or "cli-agent-bridge",
        "version": _str(p.get("client_version")) or "1.0",
    }
    nxt = replace(s, phase=ProtocolPhase.INITIALIZING, pending_request_id=1, next_request_id=2)
    return nxt, (_rpc("initialize", {"clientInfo": info}, 1),)


def _start_thread(s: ProtocolState, p: JsonMap) -> TransitionResult:
    if s.phase not in _THREAD_PHASES:
        return _fail(s, "resident_protocol_failed", "thread/start invalid phase")
    rid, zc = s.next_request_id, bool(p.get("zero_canon", s.zero_canon))
    model, cwd = _str(p.get("model")), _str(p.get("cwd"))
    params: dict[str, object] = {"ephemeral": bool(p.get("ephemeral", True))}
    if model is not None:
        params["model"] = model
    if cwd is not None:
        params["cwd"] = cwd
    if zc:
        params["sandbox"], params["approvalPolicy"] = "read-only", "never"
    nxt = ProtocolState(
        phase=ProtocolPhase.THREAD_STARTING, epoch=s.epoch + 1, next_request_id=rid + 1,
        pending_request_id=rid, zero_canon=zc, requested_model=model,
        user_agent=s.user_agent, pending_utf8=s.pending_utf8,
    )
    return nxt, (_rpc("thread/start", params, rid),)


def _start_turn(s: ProtocolState, p: JsonMap) -> TransitionResult:
    if s.phase not in _TURN_PHASES or s.thread_id is None:
        return _fail(s, "resident_protocol_failed", "turn/start needs server threadId")
    rid, zc = s.next_request_id, bool(p.get("zero_canon", s.zero_canon))
    raw_in = p.get("input")
    items: list[object] = (
        list(cast(list[object], raw_in))
        if isinstance(raw_in, list)
        else [{"type": "text", "text": str(p.get("prompt", ""))}]
    )
    model = _str(p.get("model")) or s.requested_model
    effort = _str(p.get("effort")) or s.requested_effort
    params: dict[str, object] = {"threadId": s.thread_id, "input": items}
    if model is not None:
        params["model"] = model
    if effort is not None:
        params["effort"] = effort
    if zc:
        params["approvalPolicy"] = "never"
        params["sandboxPolicy"] = {"type": "readOnly", "networkAccess": False}
    nxt = replace(
        s, phase=ProtocolPhase.TURN_ACTIVE, epoch=s.epoch + 1, pending_request_id=rid,
        interrupt_request_id=None, next_request_id=rid + 1, turn_id=None, zero_canon=zc,
        requested_model=model, requested_effort=effort, error_code=None, error_message=None,
    )
    return nxt, (_rpc("turn/start", params, rid),)


def _cancel_turn(s: ProtocolState, _p: JsonMap) -> TransitionResult:
    if s.phase is not ProtocolPhase.TURN_ACTIVE:
        return s, ()
    if s.thread_id and s.turn_id:
        rid = s.next_request_id
        params = {"threadId": s.thread_id, "turnId": s.turn_id}
        nxt = replace(s, interrupt_request_id=rid, next_request_id=rid + 1)
        return nxt, (_rpc("turn/interrupt", params, rid),)
    return _term(s, ProtocolPhase.CANCELLED, "interrupted", bump=True)


def _advance_epoch(s: ProtocolState, _p: JsonMap) -> TransitionResult:
    active = s.phase in _TURN_PHASES or s.phase is ProtocolPhase.TURN_ACTIVE
    phase = ProtocolPhase.THREAD_READY if active and s.thread_id else s.phase
    nxt = replace(
        s, phase=phase, epoch=s.epoch + 1, turn_id=None,
        pending_request_id=None, interrupt_request_id=None,
    )
    return nxt, ()


def _on_handshake_frame(s: ProtocolState, frame: JsonMap) -> TransitionResult:
    if "id" not in frame:
        return s, ()
    if frame.get("error") is not None:
        return _fail(s, "resident_protocol_failed", _err(frame.get("error"), "rpc err"))
    if frame.get("id") != s.pending_request_id:
        return s, ()
    res = _as_map(frame.get("result"))
    if res is None:
        return _fail(s, "resident_protocol_failed", "handshake missing result")
    if s.phase is ProtocolPhase.INITIALIZING:
        nxt = replace(
            s, phase=ProtocolPhase.INITIALIZED, pending_request_id=None,
            user_agent=_str(res.get("userAgent")),
        )
        return nxt, (_rpc("initialized", {}),)
    tid = _extract_id(res, "thread", "threadId")
    if tid is None:
        return _fail(s, "resident_protocol_failed", "thread/start missing threadId")
    nxt = replace(
        s, phase=ProtocolPhase.THREAD_READY, pending_request_id=None, thread_id=tid,
        actual_model=_str(res.get("model")), actual_effort=_str(res.get("reasoningEffort")),
    )
    return nxt, ()


def _on_turn_response(s: ProtocolState, frame: JsonMap) -> TransitionResult:
    if frame.get("error") is not None:
        return _fail(s, "resident_protocol_failed", _err(frame.get("error"), "rpc err"))
    fid = frame.get("id")
    if fid == s.interrupt_request_id:
        return replace(s, interrupt_request_id=None), ()
    if fid != s.pending_request_id:
        return s, ()
    bound = _extract_id(_as_map(frame.get("result")), "turn", "turnId") or s.turn_id
    ack = ProtocolEffect(EffectKind.EMIT_TURN_ACK, {"thread_id": s.thread_id, "turn_id": bound})
    return replace(s, pending_request_id=None, turn_id=bound), (ack,)


def _on_turn_completed(s: ProtocolState, p: JsonMap) -> TransitionResult:
    turn = _as_map(p.get("turn"))
    if turn is None or p.get("threadId") != s.thread_id or s.turn_id is None or turn.get("id") != s.turn_id:
        return s, ()
    status = turn.get("status")
    if status == "completed":
        return _term(s, ProtocolPhase.COMPLETED, "completed")
    if status == "interrupted":
        return _term(s, ProtocolPhase.CANCELLED, "interrupted")
    if status == "failed":
        nxt, errs = _fail(s, "turn_failed", _err(turn.get("error"), "turn failed"))
        meta: dict[str, object] = {"status": "failed", "thread_id": s.thread_id, "turn_id": s.turn_id}
        return nxt, (*errs, ProtocolEffect(EffectKind.EMIT_TERMINAL, meta))
    return _fail(s, "resident_protocol_failed", f"unexpected status: {status!r}")


def _on_delta(s: ProtocolState, channel: str, p: JsonMap) -> TransitionResult:
    delta = p.get("delta")
    if s.turn_id is None or p.get("threadId") != s.thread_id or p.get("turnId") != s.turn_id or not isinstance(delta, str):
        return s, ()
    data: dict[str, object] = {
        "channel": channel, "delta": delta, "item_id": str(p.get("itemId", "")),
        "thread_id": s.thread_id, "turn_id": s.turn_id,
    }
    return s, (ProtocolEffect(EffectKind.EMIT_DELTA, data),)


def _on_turn_started(s: ProtocolState, p: JsonMap) -> TransitionResult:
    tid = _extract_id(p, "turn", "turnId")
    if p.get("threadId") == s.thread_id and s.turn_id is None and tid is not None:
        ack = ProtocolEffect(EffectKind.EMIT_TURN_ACK, {"thread_id": s.thread_id, "turn_id": tid})
        return replace(s, turn_id=tid), (ack,)
    return s, ()


def _on_turn_notification(s: ProtocolState, method: str, p: JsonMap) -> TransitionResult:
    if method == "turn/started":
        return _on_turn_started(s, p)
    if method == "turn/completed":
        return _on_turn_completed(s, p)
    if method in _DELTAS:
        return _on_delta(s, _DELTAS[method], p)
    if method == "error":
        if p.get("willRetry") is True or p.get("threadId") not in (None, s.thread_id):
            return s, ()
        return _fail(s, "resident_protocol_failed", _err(p.get("error"), "upstream err"))
    if s.zero_canon and _is_tool_event(method, p) and p.get("threadId") in (None, s.thread_id):
        return _fail(s, "zero_canon_tool_event_forbidden", f"forbidden tool: {method}")
    return s, ()


def _on_turn_frame(s: ProtocolState, frame: JsonMap) -> TransitionResult:
    if "id" in frame and ("result" in frame or "error" in frame):
        return _on_turn_response(s, frame)
    method = _str(frame.get("method"))
    return _on_turn_notification(s, method, _as_map(frame.get("params")) or {}) if method is not None else (s, ())


_FRAMES: Mapping[ProtocolPhase, _Handler] = {
    ProtocolPhase.INITIALIZING: _on_handshake_frame,
    ProtocolPhase.THREAD_STARTING: _on_handshake_frame,
    ProtocolPhase.TURN_ACTIVE: _on_turn_frame,
}
_CMDS: Mapping[EventKind, _Handler] = {
    EventKind.START_INITIALIZE: _start_initialize, EventKind.START_THREAD: _start_thread,
    EventKind.START_TURN: _start_turn, EventKind.CANCEL_TURN: _cancel_turn,
    EventKind.ADVANCE_EPOCH: _advance_epoch,
}


def transition(state: ProtocolState, event: ProtocolEvent) -> TransitionResult:
    """Pure transition(state, event) -> (new_state, effects) with zero I/O."""
    if event.kind is EventKind.SERVER_FRAME:
        if event.epoch is not None and event.epoch != state.epoch:
            return state, ()
        if "jsonrpc" in event.payload and event.payload["jsonrpc"] != "2.0":
            return _fail(state, "resident_protocol_failed", "invalid jsonrpc version")
        handler = _FRAMES.get(state.phase)
        return handler(state, event.payload) if handler is not None else (state, ())
    if event.kind is EventKind.TRANSPORT_ERROR:
        code = _str(event.payload.get("code")) or "upstream_incomplete_stream"
        return _fail(state, code, _str(event.payload.get("message")) or "transport err")
    cmd = _CMDS.get(event.kind)
    return cmd(state, event.payload) if cmd is not None else _fail(state, "resident_protocol_failed", f"unknown event: {event.kind!r}")
