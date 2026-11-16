"""Чистая проверка имён и формы аргументов, включая вложенные parallel-вызовы."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import replace
from typing import Any

from core.backend_adapter import ToolCall

_PARALLEL_NAME = "parallel"
_PARALLEL_LIST_KEYS = ("tool_uses", "calls", "tools")
_SUBCALL_NAME_KEYS = ("recipient_name", "name")
_SUBCALL_ARGS_KEYS = ("parameters", "arguments")
# Умолчание; владелец маршрута передаёт настроенную глубину (BND-001).
DEFAULT_MAX_PARALLEL_DEPTH = 8


def _normalize_arguments(value: Any) -> dict | None:
    """arguments -> JSON-объект; None, если значение задано, но объектом не является.

    None отличает невалидные аргументы (строку-не-JSON, список, число, null) от
    отсутствия ключа: вызывающий код не вправе молча подменять их на пустой словарь
    и запускать инструмент с пустыми аргументами.
    """
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text:
            try:
                parsed = json.loads(text)
            except ValueError:
                return None
            if isinstance(parsed, dict):
                return parsed
    return None


def _normalize_tool_call(item: Any) -> dict:
    """Один OpenAI tool_call -> {"id", "name", "arguments"}.

    id сохраняется, чтобы результат [tool result <id>] однозначно сопоставлялся
    с конкретным вызовом при нескольких одинаковых инструментах.
    """
    if not isinstance(item, dict):
        return {"id": "", "name": "", "arguments": {}}
    fn = item.get("function") if isinstance(item.get("function"), dict) else {}
    name = fn.get("name") or item.get("name") or ""
    args = fn.get("arguments")
    if args is None:
        args = item.get("arguments")
    normalized = _normalize_arguments(args)
    return {
        "id": str(item.get("id") or ""),
        "name": str(name),
        "arguments": normalized if normalized is not None else {},
    }


def _with_arguments(tool_call: Any, arguments: Any) -> Any:
    """Копия вызова с новыми arguments (тип и остальные поля вызова сохраняются)."""
    if isinstance(tool_call, ToolCall):
        return replace(
            tool_call, function=replace(tool_call.function, arguments=arguments)
        )
    if isinstance(tool_call.get("function"), dict):
        return dict(
            tool_call, function=dict(tool_call["function"], arguments=arguments)
        )
    return dict(tool_call, arguments=arguments)


def _call_name_and_args(tool_call: Any) -> tuple[str, Any]:
    """Имя и arguments из ToolCall либо OpenAI-словаря; ("", None) для чужого типа."""
    if isinstance(tool_call, ToolCall):
        return tool_call.function.name, tool_call.function.arguments
    if isinstance(tool_call, dict):
        fn = tool_call.get("function")
        if isinstance(fn, dict):
            return str(fn.get("name") or ""), fn.get("arguments")
        return str(tool_call.get("name") or ""), tool_call.get("arguments")
    return "", None


def _parallel_items(arguments: Any) -> list[Any] | None:
    """Список вложенных вызовов parallel; None — списка нет."""
    parsed = _normalize_arguments(arguments)
    if parsed is None:
        return None
    return next(
        (
            parsed[key]
            for key in _PARALLEL_LIST_KEYS
            if isinstance(parsed.get(key), list)
        ),
        None,
    )


def _subcall_name(item: dict) -> str:
    """Имя вложенного вызова без префикса functions.; пусто — имени нет."""
    name = next((str(item[k]) for k in _SUBCALL_NAME_KEYS if item.get(k)), "")
    return name.removeprefix("functions.").strip()


def _subcall_arguments(item: dict) -> Any:
    """Аргументы вложенного вызова с прежним приоритетом ключей."""
    return next((item[k] for k in _SUBCALL_ARGS_KEYS if k in item), None)


def has_unnamed_call(
    tool_call: ToolCall | dict,
    *,
    max_parallel_depth: int = DEFAULT_MAX_PARALLEL_DEPTH,
) -> bool:
    """Вызов или вложенный parallel без имени, который санитайзер отбросит.

    Позволяет завершить ход fail-closed, а не молчаливым stop.
    Не-словарные элементы parallel тоже считаются безымянными.
    """
    name, arguments = _call_name_and_args(tool_call)
    return _has_unnamed(name, arguments, 0, max_parallel_depth)


def has_any_unnamed_call(
    tool_calls: Iterable[ToolCall | dict],
    *,
    max_parallel_depth: int = DEFAULT_MAX_PARALLEL_DEPTH,
) -> bool:
    """Хотя бы один вызов пакета или вложенный parallel без имени."""
    return any(
        has_unnamed_call(c, max_parallel_depth=max_parallel_depth) for c in tool_calls
    )


def _has_unnamed(name: str, arguments: Any, depth: int, max_depth: int) -> bool:
    if not name or not name.strip():
        return True
    if name.rsplit(".", 1)[-1] != _PARALLEL_NAME or depth >= max_depth:
        return False
    for item in _parallel_items(arguments) or ():
        if _unnamed_parallel_item(item, depth + 1, max_depth):
            return True
    return False


def _unnamed_parallel_item(item: Any, depth: int, max_depth: int) -> bool:
    if not isinstance(item, dict):
        return True
    return _has_unnamed(_subcall_name(item), _subcall_arguments(item), depth, max_depth)
