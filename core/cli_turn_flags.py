"""Флаги CLI для ходов без нативных инструментов (текст, эмуляция и Zero-Canon)."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping

SLASH_COMMANDS_FLAG_ENV = "AGY_BRIDGE_DISABLE_SLASH_COMMANDS"
_TEXT_ONLY_CLI_MODES = frozenset(("ask", "plan"))


def build_turn_cli_flags(
    mode: str,
    environ: Mapping[str, str] | None = None,
    zero_canon: bool = False,
) -> list[str]:
    """Флаги CLI для хода; при `zero_canon=True` блокирует слэш-команды во всех режимах."""
    if zero_canon:
        return ["--disable-slash-commands"]
    if mode not in _TEXT_ONLY_CLI_MODES:
        return []
    source = os.environ if environ is None else environ
    raw = str(source.get(SLASH_COMMANDS_FLAG_ENV, "1")).strip().lower()
    return [] if raw in ("0", "false", "no", "off") else ["--disable-slash-commands"]


def text_turn_cli_flags(
    mode: str,
    environ: Mapping[str, str] | None = None,
    zero_canon: bool = False,
) -> list[str]:
    """Обратно совместимая обёртка над `build_turn_cli_flags`."""
    return build_turn_cli_flags(mode, environ, zero_canon=zero_canon)


def format_print_timeout(val: object) -> str:
    """Добавляет единицу секунд к числу, сохраняя явные единицы CLI."""
    if val is None or isinstance(val, bool):
        return "0s"
    if isinstance(val, (int, float)):
        if val <= 0:
            return "0s"
        if int(val) == val:
            return f"{int(val)}s"
        return f"{val}s"
    raw = str(val).strip()
    if not raw or raw in ("0", "0s"):
        return "0s"
    try:
        num = float(raw)
        if num <= 0:
            return "0s"
        if num.is_integer():
            return f"{int(num)}s"
        return f"{num}s"
    except ValueError:
        pass
    if re.match(r"^\d+(?:\.\d+)?(?:ms|s|m|h)$", raw):
        return raw
    return "0s"
