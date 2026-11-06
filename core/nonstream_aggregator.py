"""SSE stream -> one chat.completion (ADR-0015 AD-001)."""

from __future__ import annotations

import http.client
import json
import socket
import time
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from core.liveness_signals import SEMANTIC_TEXT_KEYS, SIGNAL_S, T_LITERALS, classify_chunk, internal_stream_requested, parse_sse_json

_Obj = dict[str, Any]
SignalHook = Callable[[str, frozenset[str]], None]
_META_KEYS = ("id", "created", "model", "system_fingerprint")


class NonstreamError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _bad(code: str, message: str) -> NonstreamError:
    return NonstreamError(502, code, message)


def _merge_first(target: _Obj, key: str, value: Any, what: str) -> None:
    if value is None or value == "":
        return
    if key not in target:
        target[key] = value
    elif target[key] != value:
        raise _bad("upstream_metadata_conflict", f"conflicting {what}")


def choice_index(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _apply_function(entry: _Obj, function: _Obj, what: str) -> None:
    _merge_first(entry, "name", function.get("name"), what + " name")
    if isinstance(function.get("arguments"), str):
        entry["args"].append(function["arguments"])


def _apply_call(calls: dict[int, _Obj], call: _Obj) -> None:
    idx = call.get("index")
    if not isinstance(idx, int) or isinstance(idx, bool):
        idx = max(calls) if calls and not call.get("id") else len(calls)
    entry = calls.setdefault(idx, {"args": []})
    for key in ("id", "type"):
        _merge_first(entry, key, call.get(key), f"tool_call {key}")
    if isinstance(call.get("function"), dict):
        _apply_function(entry, call["function"], "tool_call")


def _apply_delta(state: _Obj, delta: _Obj) -> None:
    _merge_first(state, "role", delta.get("role"), "role")
    if isinstance(delta.get("function_call"), dict):
        _apply_function(state.setdefault("fcall", {"args": []}), delta["function_call"], "function_call")
    for key in SEMANTIC_TEXT_KEYS:
        if isinstance(delta.get(key), str) and delta[key]:
            state["text"].setdefault(key, []).append(delta[key])
    calls = delta.get("tool_calls")
    for call in calls if isinstance(calls, list) else ():
        if isinstance(call, dict):
            _apply_call(state["calls"], call)


def _fn(entry: _Obj) -> _Obj:
    return {"name": entry.get("name", ""), "arguments": "".join(entry["args"])}


def _render_choice(index: int, state: _Obj) -> _Obj:
    text = {key: "".join(parts) for key, parts in state["text"].items()}
    calls: _Obj = {}
    if state["calls"]:
        calls["tool_calls"] = [
            {"id": c.get("id", ""), "type": c.get("type") or "function", "function": _fn(c)} for _, c in sorted(state["calls"].items())
        ]
    if state.get("fcall"):
        calls["function_call"] = _fn(state["fcall"])
    message = {"role": state.get("role") or "assistant", "content": text.pop("content", "") or (None if calls else ""), **text, **calls}
    return {"index": index, "message": message, "finish_reason": state["finish"]}


class NonstreamAggregator:
    """Chunk accumulator for one response."""

    def __init__(self, max_body_bytes: int) -> None:
        self._max, self._raw_bytes, self._signals = max_body_bytes, 0, 0
        self._meta: _Obj = {}
        self._choices: dict[int, _Obj] = {}
        self._usage: _Obj | None = None
        self.done = False

    def _too_large(self) -> NonstreamError:
        return _bad("upstream_response_too_large", "response exceeds limit")

    def add_event(self, raw: bytes, data: str | None, on_signal: SignalHook | None = None) -> None:
        self._raw_bytes += len(raw)
        if self._raw_bytes > self._max:
            raise self._too_large()
        text = (data or "").strip()
        self.done = self.done or text == "[DONE]"
        chunk = parse_sse_json(data)
        if text and text not in T_LITERALS and not isinstance(chunk, dict):
            raise _bad("upstream_malformed_chunk", "malformed chunk")
        kind, keys = classify_chunk(chunk)
        if on_signal is not None:
            on_signal(kind, keys)
        if chunk is not None:
            self._signals += kind == SIGNAL_S
            self.consume_chunk(chunk)

    def consume_chunk(self, chunk: _Obj) -> None:
        if chunk.get("error"):
            raise _bad("upstream_stream_error", "upstream error chunk")
        for key in _META_KEYS:
            _merge_first(self._meta, key, chunk.get(key), key)
        if isinstance(chunk.get("usage"), dict):
            self._usage = chunk["usage"]
        choices = chunk.get("choices")
        for choice in choices if isinstance(choices, list) else ():
            if not isinstance(choice, dict):
                continue
            state = self._choices.setdefault(choice_index(choice.get("index")), {"text": {}, "calls": {}, "finish": None})
            if isinstance(choice.get("delta"), dict):
                _apply_delta(state, choice["delta"])
            if isinstance(choice.get("finish_reason"), str) and choice["finish_reason"]:
                state["finish"] = choice["finish_reason"]

    def _check_complete(self) -> None:
        if not self.done:
            raise _bad("upstream_incomplete_stream", "stream ended before [DONE]")
        if self._signals == 0 or not self._choices:
            raise _bad("upstream_empty_stream", "stream had no useful chunk")
        if any(not state["finish"] for state in self._choices.values()):
            raise _bad("upstream_incomplete_stream", "choice has no finish_reason")

    def finalize(self) -> _Obj:
        self._check_complete()
        meta = self._meta
        out: _Obj = {
            "id": meta.get("id") or "chatcmpl-passthrough", "object": "chat.completion",
            "created": meta.get("created") or int(time.time()), "model": meta.get("model") or "",
        }
        if meta.get("system_fingerprint"):
            out["system_fingerprint"] = meta["system_fingerprint"]
        out["choices"] = [_render_choice(i, self._choices[i]) for i in sorted(self._choices)]
        if self._usage is not None:
            out["usage"] = self._usage
        return out

    def encode(self) -> bytes:
        body = json.dumps(self.finalize(), ensure_ascii=False).encode("utf-8")
        if len(body) > self._max:
            raise self._too_large()
        return body


def aggregate_events(
    events: Iterable[tuple[bytes, str | None]], on_signal: SignalHook | None, max_body_bytes: int,
    expired: Callable[[], str] | None = None,
) -> bytes:
    """SSE up to [DONE] -> body; else 502/504 (break/EOF on an expired window is 504)."""
    agg = NonstreamAggregator(max_body_bytes)
    timeout = NonstreamError(504, "upstream_timeout", "upstream timeout")
    try:
        for raw, data in events:
            agg.add_event(raw, data, on_signal)
            if agg.done:
                break
        return agg.encode()
    except (TimeoutError, socket.timeout):
        raise timeout from None
    except (NonstreamError, OSError, http.client.HTTPException) as exc:
        if expired is not None and expired():
            raise timeout from None
        if isinstance(exc, NonstreamError):
            raise
        raise _bad("upstream_stream_error", "stream failed") from None


def internal_stream_body(path: str, request: Mapping[str, Any], raw_body: bytes) -> bytes | None:
    """Body with internal stream=true; None when not applicable."""
    try:
        data = json.loads(raw_body) if internal_stream_requested(path, request) else None
    except ValueError:
        data = None
    if not isinstance(data, dict):
        return None
    return json.dumps({**data, "stream": True}, ensure_ascii=False).encode("utf-8")


def request_deadlines(limits: Any, aggregate: bool) -> tuple[float, float]:
    """(request deadline, socket-open deadline)."""
    now, ns = time.monotonic(), limits.nonstream
    cap = now + (ns.safety_cap_s if aggregate else limits.total_timeout_s)
    return cap, min(cap, now + ns.first_progress_timeout_s) if aggregate else cap


def relax_socket_timeout(sock: socket.socket | None, deadline: float, read_timeout_s: float) -> None:
    if sock is not None:
        sock.settimeout(max(0.001, min(read_timeout_s, deadline - time.monotonic())))
