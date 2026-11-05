"""Оценка токенов и расчет контекстных бюджетов (ADR-001.2)."""

from __future__ import annotations

import os
import re
from typing import Any

from .prompt_builder import (
    DEFAULT_SYSTEM_HINT,
    _tool_choice_none,
    _tools_section,
)

_TOKEN_RE = re.compile(r"\s+")
DEFAULT_CONTEXT_LIMIT = int(os.environ.get("MUSE_BRIDGE_DEFAULT_CONTEXT_LIMIT", "400000"))


def _estimate_tokens(text: str) -> int:
    """Консервативная оценка токенов по UTF-8 байтам и символам (ADR-001.2 §2.5)."""
    if not text:
        return 0
    return max(len(text) // 3, len(text.encode("utf-8")) // 3)


def _estimate_usage_tokens(text: str) -> int:
    """Оценка клиентских метрик usage по словам на exec-ветке."""
    if not text or not text.strip():
        return 0
    return max(1, int(len(_TOKEN_RE.split(text.strip())) * 1.3))


def _context_limit(model: str, allowed_models: dict[str, Any] | None = None) -> int:
    """Единый источник лимита окна модели из ALLOWED_MODELS (ADR-001.1)."""
    if allowed_models and isinstance(allowed_models.get(model), dict):
        val = allowed_models[model].get("context_length")
        if isinstance(val, int) and val > 0:
            return val
    return DEFAULT_CONTEXT_LIMIT


def _context_target(limit: int) -> int:
    """Целевой бюджет проактивного прунинга с гистерезисом 80% (ADR-001.1)."""
    return (limit * 4) // 5


def _context_retry_target(limit: int) -> int:
    """Аварийный бюджет однократного retry 50% (ADR-001.1)."""
    return limit // 2


def _overhead_tokens_estimate(
    has_system: bool,
    tools: list[dict[str, Any]] | None,
    tool_choice: Any,
    raw_tools: Any,
) -> int:
    """Оценка фиксированной шапки промпта ([system], схемы инструментов, DEFAULT_SYSTEM_HINT)."""
    clean_tools = (
        [t for t in tools if isinstance(t, dict)] if isinstance(tools, list) else []
    )
    emulate_tools = bool(clean_tools) and not _tool_choice_none(tool_choice)
    overhead = 0
    if has_system:
        overhead += _estimate_tokens("[system]\n") + 1
    if emulate_tools:
        overhead += _estimate_tokens(_tools_section(clean_tools, tool_choice)) + 1
    elif (raw_tools is not None and bool(raw_tools) or bool(tools)) and not has_system:
        overhead += _estimate_tokens(f"[system]\n{DEFAULT_SYSTEM_HINT}") + 1
    return overhead
