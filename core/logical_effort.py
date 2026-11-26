"""Канонизация логического уровня мышления запроса (REQ-004, F-21).

`thinking: {"type": "disabled"}` и явные `reasoning_effort`/`effort` в значениях `off`/`none`
сводятся к логическому `"off"`; остальные уровни приводятся к нижнему регистру.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

LOGICAL_OFF = "off"
_OFF_SPELLINGS = frozenset({"off", "none"})
EFFORT_KEYS = ("reasoning_effort", "effort")


def is_thinking_disabled(request: Mapping[str, Any] | None) -> bool:
    """`thinking.type == "disabled"` без учёта регистра."""
    thinking = request.get("thinking") if isinstance(request, Mapping) else None
    return isinstance(thinking, Mapping) and str(thinking.get("type", "")).strip().lower() == "disabled"


def canonical_level(raw: object) -> str:
    """`off`/`none` -> `off`; прочие непустые строки -> нижний регистр; иначе `""`."""
    text = raw.strip().lower() if isinstance(raw, str) else ""
    return LOGICAL_OFF if text in _OFF_SPELLINGS else text


def explicit_effort(request: Mapping[str, Any] | None) -> str:
    """Явный effort запроса в канонической форме (`reasoning_effort` приоритетнее `effort`)."""
    if not isinstance(request, Mapping):
        return ""
    return next((level for key in EFFORT_KEYS if (level := canonical_level(request.get(key)))), "")


def canonicalize_logical_effort(
    *requests: Mapping[str, Any] | None,
    alias_effort: str | None = None,
    model: Mapping[str, Any] | None = None,
) -> str:
    """Явный effort > `thinking: disabled` (`off`) > alias_effort > default_effort модели.

    Запросы просматриваются по порядку; первый с явным effort либо отключённым thinking побеждает.
    """
    for request in requests:
        if level := explicit_effort(request):
            return level
        if is_thinking_disabled(request):
            return LOGICAL_OFF
    if level := canonical_level(alias_effort):
        return level
    return canonical_level(model.get("default_effort")) if isinstance(model, Mapping) else ""
