# fmt: off
"""Чистый КА изоляции каналов reasoning_content / content / tool_calls (Zero I/O)."""
from __future__ import annotations
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import Enum
from typing import TypeAlias, cast

JsonMap: TypeAlias = Mapping[str, object]
MutableJsonMap: TypeAlias = dict[str, object]

class ChannelPhase(Enum):
    IDLE = "idle"
    STREAMING_PREAMBLE = "streaming_preamble"
    TOOL_STEP_ACTIVE = "tool_step_active"
    COMPLETED = "completed"
    CLOSED = "closed"

_IDLE, _PRE = ChannelPhase.IDLE, ChannelPhase.STREAMING_PREAMBLE
_ACT = ChannelPhase.TOOL_STEP_ACTIVE

@dataclass(frozen=True, slots=True)
class ChannelFsmState:
    phase: ChannelPhase = ChannelPhase.IDLE
    session_epoch: int = 1
    pending_utf8: bytes = b""
    buffered_preamble: tuple[str, ...] = ()
    staged_calls: tuple[str, ...] = ()
    has_seen_tool_call: bool = False
    buffer_preambles: bool = True
    isolate_enabled: bool = True
    reasoning_tail: str = ""
@dataclass(frozen=True, slots=True)
class BytesReceived:
    data: bytes
    epoch: int = 1
@dataclass(frozen=True, slots=True)
class ContentDeltaEvent:
    text: str
    epoch: int = 1
@dataclass(frozen=True, slots=True)
class ReasoningDeltaEvent:
    text: str
    epoch: int = 1
@dataclass(frozen=True, slots=True)
class ToolCallsEvent:
    calls_json: str
    epoch: int = 1
@dataclass(frozen=True, slots=True)
class FlushStepEvent:
    epoch: int = 1
@dataclass(frozen=True, slots=True)
class CancelStepEvent:
    epoch: int = 1
@dataclass(frozen=True, slots=True)
class EmitContentEffect:
    text: str
@dataclass(frozen=True, slots=True)
class EmitReasoningEffect:
    text: str
@dataclass(frozen=True, slots=True)
class EmitToolCallsEffect:
    calls_json: str
@dataclass(frozen=True, slots=True)
class ProtocolErrorEffect:
    code: str
    message: str

ChannelFsmEvent: TypeAlias = (
    BytesReceived | ContentDeltaEvent | ReasoningDeltaEvent
    | ToolCallsEvent | FlushStepEvent | CancelStepEvent
)
ChannelFsmEffect: TypeAlias = (
    EmitContentEffect | EmitReasoningEffect | EmitToolCallsEffect | ProtocolErrorEffect
)
_StepOut: TypeAlias = tuple[ChannelFsmState, tuple[ChannelFsmEffect, ...]]

def decode_utf8_chunk(
    pending: bytes, chunk: bytes, *, final: bool = False
) -> tuple[str, bytes, str | None]:
    buf = pending + chunk
    if not buf:
        return "", b"", None
    try:
        return buf.decode("utf-8"), b"", None
    except UnicodeDecodeError:
        suf = 0
        for w in range(1, 0 if final else min(3, len(buf)) + 1):
            try:
                _ = buf[len(buf) - w :].decode("utf-8")
            except UnicodeDecodeError as exc:
                if exc.start == 0 and exc.end == w and "end of data" in exc.reason:
                    suf = w
                    break
        head, rem = buf[: len(buf) - suf], buf[len(buf) - suf :]
        try:
            return head.decode("utf-8"), rem, None
        except UnicodeDecodeError as exc:
            diag = f"utf-8 decode error ({exc.reason}) at byte {exc.start}"
            return head.decode("utf-8", errors="replace"), rem, diag

def _end_state(s: ChannelFsmState, ph: ChannelPhase) -> ChannelFsmState:
    return ChannelFsmState(ph, s.session_epoch, b"", (), (),
        s.has_seen_tool_call, s.buffer_preambles, s.isolate_enabled)
def _emit_reason(text: str, tail: str, edge: bool) -> tuple[EmitReasoningEffect, str]:
    sep = ""
    if edge and tail and not tail.endswith("\n\n") and not text[0].isspace():
        sep = "\n" if tail.endswith("\n") else "\n\n"
    out = f"{sep}{text}"
    return EmitReasoningEffect(out), (tail + out).replace("\r\n", "\n")[-3:]
def _flush_preamble(s: ChannelFsmState) -> tuple[tuple[ChannelFsmEffect, ...], str]:
    raw = "".join(s.buffered_preamble)
    if not raw.strip():
        return (), s.reasoning_tail
    payload = raw.lstrip() if s.reasoning_tail else raw
    eff, tail = _emit_reason(payload, s.reasoning_tail, True)
    return (eff,), tail
def _handle_content(s: ChannelFsmState, text: str) -> _StepOut:
    if not text:
        return s, ()
    ph = _PRE if s.phase is _IDLE else s.phase
    if not s.isolate_enabled or (not s.has_seen_tool_call and not s.buffer_preambles):
        return replace(s, phase=ph), (EmitContentEffect(text),)
    if not s.has_seen_tool_call:
        return replace(s, phase=ph, buffered_preamble=(*s.buffered_preamble, text)), ()
    edge = s.phase is _ACT
    if edge and not text.strip():
        return s, ()
    eff, tail = _emit_reason(text.lstrip() if edge else text, s.reasoning_tail, edge)
    return replace(s, phase=_PRE, reasoning_tail=tail), (eff,)
def _handle_tool_calls(s: ChannelFsmState, calls_json: str) -> _StepOut:
    if not s.isolate_enabled:
        if not calls_json:
            return s, ()
        return replace(s, phase=_ACT, has_seen_tool_call=True), (
            EmitToolCallsEffect(calls_json),)
    try:
        loaded = cast(object, json.loads(calls_json))
    except ValueError as exc:
        return s, (ProtocolErrorEffect("invalid_tool_calls_json", str(exc)),)
    seq = cast("Sequence[object]", loaded) if isinstance(loaded, list) else (loaded,)
    if not all(isinstance(it, Mapping) for it in seq):
        err = ProtocolErrorEffect("invalid_tool_calls_payload", "expected object")
        return s, (err,)
    dumps = json.dumps
    parsed = tuple(dumps(dict(cast("JsonMap", it)), ensure_ascii=False) for it in seq)
    effs, tail = _flush_preamble(s)
    nxt = ChannelFsmState(_ACT, s.session_epoch, s.pending_utf8, (),
        (*s.staged_calls, *parsed), True, s.buffer_preambles, s.isolate_enabled, tail)
    return nxt, effs
def _handle_flush(s: ChannelFsmState) -> _StepOut:
    effs: list[ChannelFsmEffect] = []
    if s.pending_utf8:
        dec, _, err = decode_utf8_chunk(s.pending_utf8, b"", final=True)
        s = replace(s, pending_utf8=b"")
        if err:
            effs.append(ProtocolErrorEffect("utf8_decode_error", err))
        if dec:
            s, sub = _handle_content(s, dec)
            effs.extend(sub)
    if s.isolate_enabled and (s.staged_calls or s.has_seen_tool_call):
        effs.extend(_flush_preamble(s)[0])
        if s.staged_calls:
            merged = [{**dict(cast("JsonMap", cast(object, json.loads(r)))), "index": i}
                for i, r in enumerate(s.staged_calls)]
            effs.append(EmitToolCallsEffect(json.dumps(merged, ensure_ascii=False)))
    elif "".join(s.buffered_preamble):
        effs.append(EmitContentEffect("".join(s.buffered_preamble)))
    return _end_state(s, ChannelPhase.COMPLETED), tuple(effs)

def step(
    state: ChannelFsmState, event: ChannelFsmEvent
) -> tuple[ChannelFsmState, tuple[ChannelFsmEffect, ...]]:
    if state.phase is ChannelPhase.CLOSED or event.epoch != state.session_epoch:
        return state, ()
    if isinstance(event, CancelStepEvent):
        return _end_state(state, ChannelPhase.CLOSED), ()
    if isinstance(event, BytesReceived):
        dec, rem, err = decode_utf8_chunk(state.pending_utf8, event.data)
        mid = replace(state, pending_utf8=rem)
        sub = _handle_content(mid, dec) if dec else (mid, ())
        errs = (ProtocolErrorEffect("utf8_decode_error", err),) if err else ()
        return sub[0], (*errs, *sub[1])
    if isinstance(event, ContentDeltaEvent):
        return _handle_content(state, event.text)
    if isinstance(event, ReasoningDeltaEvent):
        if not event.text:
            return state, ()
        ph = _PRE if state.phase is _IDLE else state.phase
        comb = (state.reasoning_tail + event.text).replace("\r\n", "\n")
        tail = comb[-3:] if state.isolate_enabled else ""
        nxt = replace(state, phase=ph, reasoning_tail=tail)
        return nxt, (EmitReasoningEffect(event.text),)
    if isinstance(event, ToolCallsEvent):
        return _handle_tool_calls(state, event.calls_json)
    return _handle_flush(state)
def _push_frags(effs: Sequence[ChannelFsmEffect], out: list[tuple[str, str]]) -> None:
    for e in effs:
        if isinstance(e, EmitContentEffect):
            out.append(("content", e.text))
        elif isinstance(e, EmitReasoningEffect):
            out.append(("reasoning_content", e.text))
        elif isinstance(e, EmitToolCallsEffect):
            out.append(("tool_calls", e.calls_json))
        elif isinstance(e, ProtocolErrorEffect):
            raise ValueError(f"FSM protocol error ({e.code}): {e.message}")
def normalize_staged_fragments(
    fragments: Sequence[tuple[str, str]], *, isolate_enabled: bool = True
) -> tuple[tuple[str, str], ...]:
    if not fragments or not isolate_enabled:
        return tuple(fragments)
    has_tools = any(ch == "tool_calls" for ch, _ in fragments)
    state = ChannelFsmState(buffer_preambles=True, isolate_enabled=True)
    out: list[tuple[str, str]] = []
    prev = ""
    for ch, val in fragments:
        if ch == "content":
            glued = has_tools and prev[-2:-1].islower() and (
                prev.endswith(".") and val[:1].isupper()
            )
            state, effs = step(state, ContentDeltaEvent(f"\n\n{val}" if glued else val))
            prev = val if val.strip() else prev
        elif ch == "reasoning_content":
            state, effs = step(state, ReasoningDeltaEvent(val))
        elif ch == "tool_calls":
            prev = ""
            state, effs = step(state, ToolCallsEvent(val))
        else:
            out.append((ch, val))
            continue
        _push_frags(effs, out)
    _push_frags(step(state, FlushStepEvent())[1], out)
    return tuple(out)
def _merge_reason(prev: str, text: str) -> str:
    need_sep = bool(prev) and not prev.endswith("\n") and not text.startswith("\n")
    return f"{prev}\n\n{text}" if need_sep else f"{prev}{text}"

def isolate_choice_delta(
    delta: JsonMap, *, has_active_tools: bool, isolate_enabled: bool = True
) -> MutableJsonMap:
    out: MutableJsonMap = dict(delta)
    raw = out.get("content")
    if not isolate_enabled or not has_active_tools or not isinstance(raw, str):
        return out
    _ = out.pop("content", None)
    if raw.strip():
        prev_obj = out.get("reasoning_content")
        prev = prev_obj if isinstance(prev_obj, str) else ""
        out["reasoning_content"] = _merge_reason(prev, raw)
    return out

def normalize_nonstream_assistant_fields(
    content: str, reasoning: str, *, has_tools: bool, isolate_enabled: bool = True
) -> tuple[str, str]:
    if not isolate_enabled or not has_tools or not content:
        return content, reasoning
    if not content.strip():
        return "", reasoning
    return "", _merge_reason(reasoning, content)
