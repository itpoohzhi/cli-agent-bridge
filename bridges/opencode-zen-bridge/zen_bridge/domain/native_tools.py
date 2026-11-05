"""Адаптация аргументов и имён нативных инструментов к спецификации DSH."""

from __future__ import annotations

import shlex
from typing import Any, cast

# Модель часто зовёт встроенный инструмент opencode с тем же именем, что у DSH
# (bash/read/edit/write/glob/grep). Отклонённый вызов переводим в tool_call DSH.
NATIVE_ARG_ALIASES: dict[str, str] = {
    "filePath": "file_path",
    "oldString": "old_string",
    "newString": "new_string",
    "replaceAll": "replace_all",
    "timeout": "timeoutMs",
}

# 2026-10-08 (18:46, живая сессия): Muse вызвал встроенный `todowrite`, DSH-инструмента
# с таким именем нет (у DSH — `todo_write`) -> mapped=False, 87 символов преамбулы и
# finish "stop", DSH закончил ход после одного шага. Встроенный инструмент opencode
# -> кандидаты DSH (по порядку; первый предложенный в запросе выигрывает).
NATIVE_TOOL_ALIASES: dict[str, tuple[str, ...]] = {
    "todowrite": ("todo_write", "TodoWrite", "write_todos"),
    "webfetch": ("web_fetch", "WebFetch", "fetch"),
    "websearch": ("web_search", "WebSearch"),
    "codesearch": ("web_search", "WebSearch"),
    "task": ("subagent", "Task", "agent"),
    "patch": ("apply_patch", "patch"),
    "apply_patch": ("apply_patch", "patch"),
    "skill": ("skill", "Skill"),
    "question": ("ask_user_question", "AskUserQuestion"),
    "plan_exit": ("exit_plan_mode", "ExitPlanMode"),
    "exitplanmode": ("exit_plan_mode", "ExitPlanMode"),
    "read": ("read", "Read", "read_file"),
    "write": ("write", "Write", "write_file"),
    "edit": ("edit", "Edit"),
    "bash": ("bash", "Bash", "shell"),
    # opencode v2.1.2: встроенный шелл называется `shell`, а не `bash`.
    "shell": ("bash", "Bash", "shell"),
    "glob": ("glob", "Glob"),
    "grep": ("grep", "Grep"),
}

# Подстрока имени DSH-инструмента, если точного кандидата нет (MCP-поиск и т.п.).
NATIVE_TOOL_NAME_PATTERNS: dict[str, tuple[str, ...]] = {
    "websearch": ("web_search", "websearch"),
    "codesearch": ("web_search", "websearch"),
}

# Значения enum, которых нет у DSH (opencode todo: cancelled).
ENUM_VALUE_ALIASES: dict[str, str] = {"cancelled": "completed", "canceled": "completed"}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    """JSON-объект как есть, иначе пустой словарь."""
    return cast("dict[str, Any]", value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    """JSON-массив как есть, иначе пустой список."""
    return cast("list[Any]", value) if isinstance(value, list) else []


def _tool_schemas(tools: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Инструменты запроса -> {name: parameters-schema}."""
    out: dict[str, dict[str, Any]] = {}
    for item in tools:
        fn = item.get("function") if isinstance(item.get("function"), dict) else item
        if isinstance(fn, dict) and isinstance(fn.get("name"), str) and fn["name"]:
            out[fn["name"]] = _dict_or_empty(fn.get("parameters"))
    return out


def _fit_value(value: Any, schema: Any) -> tuple[bool, Any]:
    """Значение -> (ok, приведённое к схеме): ключи-алиасы, лишние ключи, enum."""
    if not isinstance(schema, dict):
        return True, value
    enum = schema.get("enum")
    if isinstance(enum, list) and enum and value not in enum:
        alias = ENUM_VALUE_ALIASES.get(value) if isinstance(value, str) else None
        if alias in enum:
            return True, alias
        return False, None
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        fitted = []
        for item in value:
            ok, item = _fit_value(item, schema["items"])
            if not ok:
                return False, None
            fitted.append(item)
        return True, fitted
    if isinstance(value, dict) and isinstance(schema.get("properties"), dict):
        props = schema["properties"]
        strict = schema.get("additionalProperties") is False
        mapped: dict[str, Any] = {}
        for raw_key, sub in value.items():
            key: str = NATIVE_ARG_ALIASES.get(str(raw_key), str(raw_key))
            if key not in props:
                if strict:
                    continue
                mapped[key] = sub
                continue
            ok, sub = _fit_value(sub, props[key])
            if not ok:
                return False, None
            mapped[key] = sub
        required = _list_or_empty(schema.get("required"))
        if any(r not in mapped for r in required):
            return False, None
        return True, mapped
    return True, value


def _fit_args(
    target: str, args: dict[str, Any], schema: dict[str, Any]
) -> dict[str, Any] | None:
    """Аргументы встроенного инструмента -> аргументы DSH-инструмента `target` или None."""
    props = _dict_or_empty(schema.get("properties"))
    mapped: dict[str, Any] = {}
    leftovers: list[str] = []
    for key, value in args.items():
        key = NATIVE_ARG_ALIASES.get(key, key)
        if props and key not in props:
            if isinstance(value, str) and value.strip():
                leftovers.append(value)
            continue
        ok, value = _fit_value(value, props.get(key))
        if not ok:
            return None
        mapped[key] = value
    required = _list_or_empty(schema.get("required"))
    if "description" in required and "description" not in mapped:
        mapped["description"] = (
            f"{target}: {str(mapped.get('command') or '')[:80]}".strip()
        )
    missing = [r for r in required if r not in mapped]
    if (
        len(missing) == 1
        and len(leftovers) == 1
        and (props.get(missing[0]) or {}).get("type") in ("string", None)
    ):
        mapped[missing[0]] = leftovers[0]
        missing = []
    if missing:
        return None
    return mapped


def _pick_target(tool: str, schemas: dict[str, dict[str, Any]]) -> str | None:
    """Имя DSH-инструмента для встроенного `tool` (сначала то же имя)."""
    for name in (tool, *NATIVE_TOOL_ALIASES.get(tool.lower(), ())):
        if name in schemas:
            return name
    for pattern in NATIVE_TOOL_NAME_PATTERNS.get(tool.lower(), ()):
        for name in schemas:
            if pattern in name.lower():
                return name
    return None


def _native_to_tool_calls(
    tool: Any, args: Any, tools: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Вызов встроенного инструмента opencode -> список {"name","arguments"} DSH."""
    if not isinstance(tool, str) or not isinstance(args, dict):
        return []
    schemas = _tool_schemas(tools)
    low = tool.lower()
    if low in ("list", "ls") and tool not in schemas:
        path = str(args.get("path") or ".")
        if "bash" in schemas:
            fitted = _fit_args(
                "bash", {"command": f"ls -la {shlex.quote(path)}"}, schemas["bash"]
            )
            if fitted is not None:
                return [{"name": "bash", "arguments": fitted}]
        if "glob" in schemas:
            fitted = _fit_args("glob", {"pattern": "*", "path": path}, schemas["glob"])
            if fitted is not None:
                return [{"name": "glob", "arguments": fitted}]
        return []
    if low == "multiedit" and tool not in schemas:
        target = _pick_target("edit", schemas)
        edits = args.get("edits")
        if target is None or not isinstance(edits, list) or not edits:
            return []
        calls: list[dict[str, Any]] = []
        for edit in edits:
            if not isinstance(edit, dict):
                return []
            merged = {
                "filePath": args.get("filePath"),
                **{k: v for k, v in edit.items() if v is not None},
            }
            fitted = _fit_args(target, merged, schemas[target])
            if fitted is None:
                return []
            calls.append({"name": target, "arguments": fitted})
        return calls
    target = _pick_target(tool, schemas)
    if target is None:
        return []
    fitted = _fit_args(target, args, schemas[target])
    return [] if fitted is None else [{"name": target, "arguments": fitted}]


def _native_to_tool_call(
    tool: Any, args: Any, tools: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Совместимость: первый DSH-вызов для встроенного инструмента или None."""
    calls = _native_to_tool_calls(tool, args, tools)
    return calls[0] if calls else None
