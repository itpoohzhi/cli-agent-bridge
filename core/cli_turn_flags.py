"""Флаги CLI для ходов без нативных инструментов (текст и эмуляция клиентских tools)."""

from __future__ import annotations

import os
from collections.abc import Mapping

SLASH_COMMANDS_FLAG_ENV = "AGY_BRIDGE_DISABLE_SLASH_COMMANDS"
_TEXT_ONLY_CLI_MODES = frozenset(("ask", "plan"))


def text_turn_cli_flags(mode: str, environ: Mapping[str, str] | None = None) -> list[str]:
    """Флаги, изолирующие ход `ask`/`plan` от слэш-команд (`AGY_BRIDGE_DISABLE_SLASH_COMMANDS=0` — выкл)."""
    if mode not in _TEXT_ONLY_CLI_MODES:
        return []
    source = os.environ if environ is None else environ
    raw = str(source.get(SLASH_COMMANDS_FLAG_ENV, "1")).strip().lower()
    return [] if raw in ("0", "false", "no", "off") else ["--disable-slash-commands"]
