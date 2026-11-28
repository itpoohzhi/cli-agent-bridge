"""Чистый КА разбора OpenAI-совместимого SSE (F-FSM-I1/I2, M-MOD-I3): 0 I/O-импортов."""
# pyright: reportAny=false, reportExplicitAny=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any


@dataclass(frozen=True)
class SseStreamState:
    """Иммутабельное состояние: хвост UTF-8, хвост строки, признак `[DONE]`."""

    pending_utf8: bytes = b""
    line_buf: str = ""
    done: bool = False


@dataclass(frozen=True)
class SseParsedEvent:
    """Разобранное содержимое одного `data:`-фрейма."""

    content: str = ""
    reasoning: str = ""
    tool_calls: tuple[dict[str, Any], ...] = ()
    usage_raw: dict[str, Any] | None = None
    is_done: bool = False
    error_message: str | None = None


def _decode_utf8(raw: bytes) -> tuple[str, bytes]:
    """Декодирует завершённый префикс; незавершённую UTF-8 последовательность оставляет в хвосте."""
    for keep in range(min(3, len(raw)) + 1):
        head = raw[: len(raw) - keep]
        try:
            return head.decode("utf-8"), raw[len(head) :]
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace"), b""


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _tool_calls(delta: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    raw = delta.get("tool_calls")
    if not isinstance(raw, list):
        return ()
    return tuple(c for c in raw if isinstance(c, dict))


def _parse_data(payload: str) -> SseParsedEvent | None:
    if payload == "[DONE]":
        return SseParsedEvent(is_done=True)
    if not payload:
        return None
    try:
        parsed = json.loads(payload)
    except ValueError:
        return None
    if not isinstance(parsed, dict):
        return None
    usage = parsed.get("usage")
    usage_raw = usage if isinstance(usage, dict) else None
    err = parsed.get("error")
    if err:
        if isinstance(err, dict):
            msg = str(err.get("message") or err.get("code") or err)
        elif isinstance(err, str):
            msg = err
        else:
            msg = str(err)
        return SseParsedEvent(usage_raw=usage_raw, error_message=msg)
    choices = parsed.get("choices")
    first = choices[0] if isinstance(choices, list) and choices else None
    delta = first.get("delta") if isinstance(first, dict) else None
    if not isinstance(delta, dict):
        return SseParsedEvent(usage_raw=usage_raw) if usage_raw is not None else None
    content = _text(delta.get("content"))
    reasoning = _text(delta.get("reasoning_content"))
    calls = _tool_calls(delta)
    if not (content or reasoning or calls or usage_raw is not None):
        return None
    return SseParsedEvent(content, reasoning, calls, usage_raw)


def _parse_line(line: str) -> SseParsedEvent | None:
    if not line or line.startswith(":"):
        return None
    if not line.startswith("data:"):
        return None
    return _parse_data(line[len("data:") :].strip())


def _consume(state: SseStreamState, text: str) -> tuple[SseStreamState, list[SseParsedEvent]]:
    lines = (state.line_buf + text).split("\n")
    tail = lines.pop()
    events: list[SseParsedEvent] = []
    done = state.done
    for raw_line in lines:
        ev = _parse_line(raw_line.rstrip("\r"))
        if ev is None:
            continue
        events.append(ev)
        if ev.is_done:
            done = True
            break
    return replace(state, line_buf="" if done else tail, done=done), events


def step_sse_bytes(state: SseStreamState, chunk: bytes) -> tuple[SseStreamState, list[SseParsedEvent]]:
    """Чистый шаг КА: любой разрез байтов (UTF-8/`\\r\\n`) даёт тот же поток событий."""
    if state.done:
        return state, []
    text, pending = _decode_utf8(state.pending_utf8 + chunk)
    next_state, events = _consume(replace(state, pending_utf8=pending), text)
    if next_state.done:
        next_state = replace(next_state, pending_utf8=b"")
    return next_state, events


def flush_sse_state(state: SseStreamState) -> tuple[SseStreamState, list[SseParsedEvent]]:
    """Финальный сброс: дозабирает хвост строки без завершающего перевода строки."""
    if state.done:
        return replace(state, pending_utf8=b"", line_buf=""), []
    line = state.line_buf + state.pending_utf8.decode("utf-8", "replace")
    fresh = replace(state, pending_utf8=b"", line_buf="")
    if not line.strip():
        return fresh, []
    return _consume(fresh, line + "\n")
