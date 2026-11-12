"""Чистые помощники фаз Muse MSP: env-лимиты, подсказки инструментов, маршруты."""

from __future__ import annotations

import json
import os
import re
from pathlib import PureWindowsPath
from typing import Any, Mapping

_DEFAULT_HINT_FIELDS = ("description", "path", "file_path", "pattern")
_PATH_FIELDS = frozenset({"path", "file_path"})
_SUCCESS_STATUSES = frozenset({"completed", "success"})
_ROUTES = {"main:commentary": "commentary", "foreign:finalAnswer": "sub_final"}
_SCOPE_DEFAULTS = {"main": "answer", "foreign": "ignore"}
_TOOL_NAME = re.compile(r"[A-Za-z0-9_.:-]{1,64}")


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        value = default
    if value < 0:
        value = default
    return value


def hint_max_chars() -> int:
    return _env_int("BRIDGE_MUSE_TOOL_HINT_MAX_CHARS", 80)


def args_max_chars() -> int:
    return _env_int("BRIDGE_MUSE_TOOL_ARGS_MAX_CHARS", 1_048_576)


def subagent_final_limit() -> int:
    return _env_int("BRIDGE_MUSE_SUBAGENT_FINAL_MAX_CHARS", 300)


def hint_fields() -> tuple[str, ...]:
    raw = os.environ.get("BRIDGE_MUSE_TOOL_HINT_FIELDS", ",".join(_DEFAULT_HINT_FIELDS))
    fields = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not fields:
        fields = _DEFAULT_HINT_FIELDS
    return fields


def _parse_args(raw: Mapping[str, Any]) -> Mapping[str, Any]:
    parsed_args: Mapping[str, Any] = {}
    value = raw.get("args")
    if isinstance(value, Mapping):
        parsed_args = value
    if isinstance(value, str):
        if len(value) <= args_max_chars():
            try:
                parsed = json.loads(value)
            except (RecursionError, ValueError):
                parsed = {}
            if isinstance(parsed, Mapping):
                parsed_args = parsed
    return parsed_args


def _clean_hint(name: str, value: str) -> str:
    text = " ".join(value.split())
    if name in _PATH_FIELDS:
        base = PureWindowsPath(text).name
        if base:
            text = base
    return text[: hint_max_chars()]


def tool_hint(raw: Mapping[str, Any]) -> str:
    """Первая подсказка из allowlist полей args; значения вне allowlist не выходят."""
    args = _parse_args(raw)
    hint = ""
    for name in hint_fields():
        value = args.get(name)
        if isinstance(value, str):
            if value.strip():
                if not hint:
                    hint = _clean_hint(name, value)
    return hint


def classify_route(scope: str, phase: str) -> str:
    """Маршрут agentMessage: answer/commentary главного хода, sub_final/ignore чужого."""
    route = _ROUTES.get(f"{scope}:{phase}", "")
    if not route:
        route = _SCOPE_DEFAULTS[scope]
    return route


def is_failed_status(status: Any) -> bool:
    """Неуспех — всё вне allowlist успеха: неизвестный/пустой статус не молчит."""
    text = status.strip().lower() if isinstance(status, str) else ""
    return text not in _SUCCESS_STATUSES


def one_line(text: str) -> str:
    return " ".join(text.split())[: subagent_final_limit()]


def sep_for(reasoning: str) -> str:
    sep = "\n\n" if reasoning else ""
    if reasoning.endswith("\n\n"):
        sep = ""
    elif reasoning.endswith("\n"):
        sep = "\n"
    return sep


def _suppress_unknown_tool() -> bool:
    return os.environ.get(
        "BRIDGE_MUSE_SUPPRESS_UNKNOWN_TOOL", "true"
    ).strip().lower() in ("1", "true", "yes", "on")


def _plain_tool_name(raw: Mapping[str, Any]) -> str:
    vals = [
        str(raw[k]).strip()
        for k in ("toolName", "tool", "name")
        if raw.get(k) is not None and str(raw[k]).strip()
    ]
    valid = next((v for v in vals if _TOOL_NAME.fullmatch(v)), "")
    return valid or ("unknown_tool" if (vals or not _suppress_unknown_tool()) else "")


def extract_tool_name(raw: Mapping[str, Any]) -> str:
    """Отображаемое имя инструмента; с подсказкой из allowlist args — «имя — подсказка»."""
    display = _plain_tool_name(raw)
    if display:
        hint = tool_hint(raw)
        if hint:
            display = f"{display} — {hint}"
    return display


def format_tool_started(name: str) -> str:
    return f"[Вызов инструмента: {name}]\n" if name else ""


def format_tool_completed(name: str) -> str:
    out = f"[Инструмент {name} завершён]\n" if name else ""
    if " — " in name:
        out = ""
    return out
