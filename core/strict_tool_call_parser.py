"""Strict-parse блоков `<tool_call>` для recovery (AD-005, INV-S3): все блоки шага без остатка.

Любое отклонение (текст вне блоков, битый JSON, пустое имя, `arguments` не объект) → `None`:
вызывающая политика отвергает шаг целиком (fail-closed). Чистая функция без I/O и состояния;
агент-агностично: формат `<tool_call>{"name": …, "arguments": {…}}</tool_call>` — контракт шлюза.
"""

from __future__ import annotations

import json
import re

from core.transport_failure_contracts import ParsedToolCall

_BLOCK = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL)
_ONLY_BLOCKS = re.compile(r"\s*(?:<tool_call>.*?</tool_call>\s*)+", re.DOTALL)


def _arguments_json(raw: object) -> str | None:
    """Канонический JSON аргументов; строка-JSON допускается, не-объект → `None`."""
    value = raw
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, RecursionError):
            return None
    if not isinstance(value, dict):
        return None
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _parse_block(body: str) -> ParsedToolCall | None:
    """Один блок: объект с непустым `name` и объектом `arguments` (по умолчанию `{}`)."""
    try:
        obj = json.loads(body)
    except (ValueError, RecursionError):
        return None
    if not isinstance(obj, dict):
        return None
    name, args = obj.get("name"), _arguments_json(obj.get("arguments", {}))
    if not isinstance(name, str) or not name.strip() or args is None:
        return None
    call_id = obj.get("id")
    return ParsedToolCall(call_id if isinstance(call_id, str) else "", name.strip(), args)


class StrictToolCallParser:
    """Порт `ToolCallParser`: все `<tool_call>` текста без остатка либо `None`."""

    def parse_all(self, text: str) -> tuple[ParsedToolCall, ...] | None:
        """Разобрать каждый блок; хоть один дефект или лишний текст → `None`."""
        if not isinstance(text, str) or _ONLY_BLOCKS.fullmatch(text) is None:
            return None
        parsed = [_parse_block(body) for body in _BLOCK.findall(text)]
        if not parsed or any(item is None for item in parsed):
            return None
        return tuple(item for item in parsed if item is not None)


def calls_to_markup(calls: tuple[ParsedToolCall, ...]) -> str:
    """Каноническая разметка проверенных вызовов (вход структурного эмулятора tool_calls)."""
    parts = []
    for call in calls:
        body = {"name": call.name, "arguments": json.loads(call.arguments_json)}
        if call.call_id:
            body["id"] = call.call_id
        parts.append("<tool_call>" + json.dumps(body, ensure_ascii=False) + "</tool_call>")
    return "".join(parts)
