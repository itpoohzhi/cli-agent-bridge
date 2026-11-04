"""Парсинг и санитизация блоков вызова инструментов <tool_call>."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Callable

_MAX_EXTRA_BRACES = 8
_SANITIZE_LIMITS = {
    "max_name_len": 64,
    "max_args_len": 32768,
    "max_calls": 32,
    "max_depth": 16,
}


def _strip_code_fence(inner: str) -> str:
    """Удаляет обрамляющие markdown-блоки кода."""
    text = inner.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


def _recover_trailing_braces(text: str) -> dict | None:
    """Восстанавливает JSON при случайных лишних закрывающих фигурных скобках."""
    raw = _strip_code_fence(text)
    idx = 0
    obj: object = None
    dec = json.JSONDecoder()
    try:
        obj, idx = dec.raw_decode(raw)
    except ValueError:
        return None
    tail = raw[idx:]
    if (
        isinstance(obj, dict)
        and 1 <= tail.count("}") <= _MAX_EXTRA_BRACES
        and not tail.strip(" \t\r\n}")
    ):
        return obj
    return None


def _loads_tolerant(text: str) -> Any:
    """json.loads с устойчивостью к закрывающим скобкам и рекурсии."""
    try:
        return json.loads(text)
    except (ValueError, RecursionError) as exc:
        recovered = _recover_trailing_braces(text)
        if recovered is None:
            if isinstance(exc, RecursionError):
                raise ValueError("JSON is nested too deeply") from exc
            raise
        return recovered


def _parse_tool_call_block(inner: str) -> dict | None:
    """Парсит содержимое блока tool_call в словарь name/arguments."""
    try:
        obj = _loads_tolerant(_strip_code_fence(inner))
    except ValueError:
        return None
    if not isinstance(obj, dict) or "name" not in obj or not isinstance(obj["name"], str):
        return None
    args = obj.get("arguments", {})
    if not isinstance(args, dict):
        return None
    return {"name": obj["name"], "arguments": args}


def _split_tool_call_inner(content: str) -> tuple[str, list[dict]]:
    """Разбивает строку на чистый текст и блоки tool_call."""
    pieces: list[str] = []
    calls: list[dict] = []
    pos = 0
    pattern = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL)
    for match in pattern.finditer(content):
        pieces.append(content[pos : match.start()])
        parsed = _parse_tool_call_block(match.group(1))
        if parsed is not None:
            calls.append(parsed)
        else:
            pieces.append(match.group(0))
        pos = match.end()
    pieces.append(content[pos:])
    return "".join(pieces), calls


class ToolCallParser:
    """Инкрементальный парсер потока токенов с выделением <tool_call>."""

    def __init__(
        self,
        emit_text: Callable[[str], None],
        emit_call: Callable[[dict], None],
    ) -> None:
        self.emit_text = emit_text
        self.emit_call = emit_call
        self.buf = ""

    def feed(self, chunk: str) -> None:
        self.buf += chunk
        open_tag = "<tool_call>"
        close_tag = "</tool_call>"
        while True:
            start = self.buf.find(open_tag)
            if start == -1:
                cutoff = len(self.buf) - len(open_tag) + 1
                if cutoff > 0:
                    self.emit_text(self.buf[:cutoff])
                    self.buf = self.buf[cutoff:]
                break
            if start > 0:
                self.emit_text(self.buf[:start])
                self.buf = self.buf[start:]
            end = self.buf.find(close_tag)
            if end == -1:
                break
            inner = self.buf[len(open_tag) : end]
            self.buf = self.buf[end + len(close_tag) :]
            parsed = _parse_tool_call_block(inner)
            if parsed is not None:
                self.emit_call(parsed)
            else:
                self.emit_text(open_tag + inner + close_tag)

    def finish(self) -> None:
        if self.buf:
            text, calls = _split_tool_call_inner(self.buf)
            if text:
                self.emit_text(text)
            for call in calls:
                self.emit_call(call)
            self.buf = ""


def _split_tool_calls(
    chunks: list[str],
    tool_schemas: list[dict] | None = None,
    sanitize_func: Callable[..., list[dict]] | None = None,
) -> tuple[str, list[dict]]:
    """Собирает чанки, извлекает tool_calls и форматирует их в OpenAI-схему."""
    pieces: list[str] = []
    calls: list[dict] = []

    def add_call(call: dict) -> None:
        calls.append(
            {
                "index": len(calls),
                "id": "call_" + uuid.uuid4().hex[:24],
                "type": "function",
                "function": {
                    "name": call["name"],
                    "arguments": json.dumps(call["arguments"], ensure_ascii=False),
                },
            }
        )

    parser = ToolCallParser(pieces.append, add_call)
    for chunk in chunks:
        parser.feed(chunk)
    parser.finish()
    if sanitize_func is not None and tool_schemas is not None:
        calls = sanitize_func(calls, tool_schemas, **_SANITIZE_LIMITS)
    return "".join(pieces), calls
