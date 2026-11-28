"""Streaming SSE consumer and env knobs for local loopback Zero-Canon Claude proxy."""
# pyright: reportExplicitAny=false, reportAny=false

from __future__ import annotations

import inspect
import os
from collections.abc import Callable, Mapping
from typing import Any

from core.stdio_resident.bridge_proxy_sse import (
    SseParsedEvent,
    SseStreamState,
    flush_sse_state,
    step_sse_bytes,
)
from core.turn_usage import TurnUsage
from core.usage_wire import turn_usage_from_wire

STREAM_ENABLED_ENV = "BRIDGE_ZC_CLAUDE_STREAM_ENABLED"
STREAM_CHUNK_ENV = "BRIDGE_ZC_CLAUDE_STREAM_CHUNK_BYTES"
_STREAM_OFF_VALUES = frozenset({"0", "false", "off"})
_DEFAULT_STREAM_CHUNK_BYTES = 4096


def bridge_stream_enabled(environ: Mapping[str, str] | None = None) -> bool:
    """Kill-switch потокового SSE-проброса Zero-Canon Claude (по умолчанию включён)."""
    env = os.environ if environ is None else environ
    return str(env.get(STREAM_ENABLED_ENV, "1")).strip().lower() not in _STREAM_OFF_VALUES


def bridge_stream_chunk_bytes(environ: Mapping[str, str] | None = None) -> int:
    """Размер чанка чтения SSE из env (без хардкода буфера; default 4096)."""
    env = os.environ if environ is None else environ
    try:
        size = int(str(env.get(STREAM_CHUNK_ENV, _DEFAULT_STREAM_CHUNK_BYTES)).strip())
    except (TypeError, ValueError):
        return _DEFAULT_STREAM_CHUNK_BYTES
    return size if size > 0 else _DEFAULT_STREAM_CHUNK_BYTES


def is_sse_response(resp: Any) -> bool:
    """Проверяет Content-Type ответа на `text/event-stream`."""
    headers = getattr(resp, "headers", None)
    getter = getattr(headers, "get", None)
    ctype = str(getter("Content-Type", "") or "") if callable(getter) else ""
    return "text/event-stream" in ctype.lower()


def looks_like_sse(text: str) -> bool:
    """Fallback-эвристика: тело начинается с SSE-кадра (`data:` или `:`)."""
    return text.lstrip().startswith(("data:", ":"))


def accepts_sse_writer(fn: Callable[..., Any]) -> bool:
    """Legacy/mock `bridge_proxy_fn` без `sse_writer` не должен ломаться."""
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
    return "sse_writer" in params or any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())


class BridgeRelayTracker:
    """Счётчик live-дельт для точного `live_sent` и дедупликации fallback-эмиссии."""

    def __init__(self, sse_writer: Callable[[str, str], Any] | None) -> None:
        self.live_sent: int = 0
        self.streamed: set[str] = set()
        self._writer: Callable[[str, str], Any] | None = sse_writer

    def relay(self, kind: str, value: str) -> Any:
        self.streamed.add(kind)
        self.live_sent += 1
        return self._writer(kind, value) if self._writer is not None else None

    def build_extra(
        self, proxy_options: Any, bridge_proxy_fn: Callable[..., Any]
    ) -> dict[str, Any]:
        extra: dict[str, Any] = {"proxy_options": proxy_options} if proxy_options else {}
        if self._writer is not None and bridge_stream_enabled() and accepts_sse_writer(bridge_proxy_fn):
            extra["sse_writer"] = self.relay
        return extra


def emit_result_once(
    text: str, reasoning: str, sse_writer: Callable[[str, str], Any]
) -> None:
    """Однократная эмиссия JSON-fallback ответа в `sse_writer`."""
    if text:
        _ = sse_writer("content", text)
    if reasoning:
        _ = sse_writer("reasoning_content", reasoning)


class _SseSink:
    """Локальный накопитель чанков одного SSE-хода."""

    def __init__(
        self, sse_writer: Callable[[str, str], Any] | None, usage_enabled: bool
    ) -> None:
        self.content: list[str] = []
        self.reasoning: list[str] = []
        self.tool_calls: list[dict[str, Any]] = []
        self.usage_sink: list[TurnUsage] = []
        self._writer: Callable[[str, str], Any] | None = sse_writer
        self._usage_enabled: bool = usage_enabled

    def consume(self, events: list[SseParsedEvent]) -> None:
        for ev in events:
            if self._usage_enabled and ev.usage_raw is not None:
                parsed_u = turn_usage_from_wire(ev.usage_raw, "claude_zero_canon_bridge")
                if parsed_u is not None:
                    self.usage_sink.append(parsed_u)
            if ev.error_message:
                raise RuntimeError(f"upstream_bridge_stream_error: {ev.error_message}")
            if ev.content:
                self.content.append(ev.content)
                if self._writer is not None:
                    _ = self._writer("content", ev.content)
            if ev.reasoning:
                self.reasoning.append(ev.reasoning)
                if self._writer is not None:
                    _ = self._writer("reasoning_content", ev.reasoning)
            self.tool_calls.extend(ev.tool_calls)

    def finalize(self) -> tuple[str, str, TurnUsage | None, tuple[dict[str, Any], ...]]:
        usage = (self.usage_sink[-1] if self.usage_sink else None) if self._usage_enabled else None
        return "".join(self.content), "".join(self.reasoning), usage, tuple(self.tool_calls)


def _read_sse_chunk(read: Callable[..., Any], size: int) -> bytes:
    try:
        data = read(size)
    except TypeError:
        data = read()
    return bytes(data) if data else b""


def consume_sse_stream(
    resp: Any,
    usage_enabled: bool,
    sse_writer: Callable[[str, str], Any] | None,
) -> tuple[str, str, TurnUsage | None, tuple[dict[str, Any], ...]]:
    """Инкрементально читает SSE-поток, эмитя дельты по мере поступления."""
    sink = _SseSink(sse_writer, usage_enabled)
    state = SseStreamState()
    size = bridge_stream_chunk_bytes()
    read1 = getattr(resp, "read1", None)
    read = read1 if callable(read1) else resp.read
    while not state.done:
        chunk = _read_sse_chunk(read, size)
        if not chunk:
            break
        state, events = step_sse_bytes(state, chunk)
        sink.consume(events)
    state, events = flush_sse_state(state)
    sink.consume(events)
    if not state.done:
        raise RuntimeError("upstream_incomplete_stream: SSE stream ended before [DONE]")
    return sink.finalize()


def consume_sse_blob(
    raw: bytes,
    usage_enabled: bool,
    sse_writer: Callable[[str, str], Any] | None,
) -> tuple[str, str, TurnUsage | None, tuple[dict[str, Any], ...]]:
    """Разбирает уже вычитанный SSE-буфер через тот же КА."""
    sink = _SseSink(sse_writer, usage_enabled)
    state, events = step_sse_bytes(SseStreamState(), raw)
    sink.consume(events)
    state, events = flush_sse_state(state)
    sink.consume(events)
    if not state.done:
        raise RuntimeError("upstream_incomplete_stream: SSE stream ended before [DONE]")
    return sink.finalize()
