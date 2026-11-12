"""Чистые помощники фаз Muse MSP: env-лимиты, подсказки инструментов, маршруты."""

from __future__ import annotations

import json
import os
from pathlib import PureWindowsPath
from typing import Any, Mapping

_DEFAULT_HINT_FIELDS = ("description", "path", "file_path", "pattern")
_PATH_FIELDS = frozenset({"path", "file_path"})
_FAILED_STATUSES = frozenset(
    {"failed", "failure", "error", "errored", "cancelled", "canceled", "timeout"}
)
_ROUTES = {"main:commentary": "commentary", "foreign:finalAnswer": "sub_final"}
_SCOPE_DEFAULTS = {"main": "answer", "foreign": "ignore"}


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
        try:
            parsed = json.loads(value)
        except ValueError:
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
    text = status.strip().lower() if isinstance(status, str) else ""
    return text in _FAILED_STATUSES


def one_line(text: str) -> str:
    return " ".join(text.split())[: subagent_final_limit()]


def sep_for(reasoning: str) -> str:
    sep = "\n\n" if reasoning else ""
    if reasoning.endswith("\n\n"):
        sep = ""
    elif reasoning.endswith("\n"):
        sep = "\n"
    return sep
