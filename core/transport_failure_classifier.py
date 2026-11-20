"""Классификатор транспортных сбоев (AD-001, BND-001): Go-формы сети → NETWORK_TRANSIENT.

Чистая функция без I/O. Фатальные формы (HTTP 400/401/403, invalid model, quota) —
всегда вето (FM-09): даже при совпадении транзиентного маркера результат FATAL.
Агент-агностично: смотрим только на текст ошибки, не на имя CLI.
"""

from __future__ import annotations

import re
from functools import lru_cache
from urllib.parse import unquote

from core.transport_failure_contracts import (
    FailureClassification,
    FailureKind,
    TransportFailureConfig,
)

_DEFAULT_CONFIG = TransportFailureConfig()
_MAX_UNQUOTE_ROUNDS = 3


@lru_cache(maxsize=64)
def _compile(patterns: tuple[str, ...]) -> tuple[re.Pattern[str], ...] | None:
    """Скомпилировать шаблоны; невалидный regex → `None` (вызывающий решает fail-closed)."""
    try:
        return tuple(re.compile(p, re.IGNORECASE) for p in patterns)
    except re.error:
        return None


def _normalize(text: str, max_chars: int) -> str:
    """Декодировать `%25xx`-обфускацию, схлопнуть пробелы, ограничить длину головой+хвостом."""
    for _ in range(_MAX_UNQUOTE_ROUNDS):
        decoded = unquote(text)
        if decoded == text:
            break
        text = decoded
    text = " ".join(text.split())
    if max_chars > 0 and len(text) > max_chars:
        half = max_chars // 2
        text = text[:half] + " " + text[-half:]
    return text


def _first_match(patterns: tuple[re.Pattern[str], ...], text: str) -> str:
    for pattern in patterns:
        found = pattern.search(text)
        if found:
            return found.group(0)
    return ""


def classify_transport_failure(
    text: object, config: TransportFailureConfig | None = None
) -> FailureClassification:
    """Классифицировать текст ошибки: FATAL (вето) > NETWORK_TRANSIENT > UNCLASSIFIED."""
    cfg = config if config is not None else _DEFAULT_CONFIG
    if not isinstance(text, str) or not text.strip():
        return FailureClassification(FailureKind.UNCLASSIFIED, "empty_or_non_text")
    fatal = _compile(tuple(cfg.fatal_patterns))
    if fatal is None:
        return FailureClassification(FailureKind.UNCLASSIFIED, "invalid_fatal_pattern")
    normalized = _normalize(text, cfg.max_chars)
    hit = _first_match(fatal, normalized)
    if hit:
        return FailureClassification(FailureKind.FATAL, "fatal_veto", hit)
    transient = _compile(tuple(cfg.transient_patterns))
    hit = _first_match(transient, normalized) if transient else ""
    if hit:
        return FailureClassification(FailureKind.NETWORK_TRANSIENT, "go_network_form", hit)
    return FailureClassification(FailureKind.UNCLASSIFIED, "no_marker")
