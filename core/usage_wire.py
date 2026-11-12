"""Нормализация cache-токенов для OpenAI-совместимого wire-контракта `usage`.

Чистый модуль (REQ-CACHE-001, AD-004): никакого I/O и логирования. Решение
о предупреждении при `inconsistent=True` принимает вызывающий слой.
"""

from __future__ import annotations

from collections.abc import Mapping

# Ключи cache-read токенов в usage апстримов (порядок = приоритет).
CACHE_READ_KEYS: tuple[str, ...] = (
    "cacheReadTokens",
    "cache_read_tokens",
    "cache_read_input_tokens",
    "cachedTokens",
)


def _is_count(value: object) -> bool:
    """Целое счётное значение; `bool` допустимым числом не является."""
    return isinstance(value, int) and not isinstance(value, bool)


def normalize_prompt_cache_details(
    prompt_tokens: int | None,
    cache_read_tokens: int | None,
    cache_creation_tokens: int | None = None,
) -> tuple[dict[str, int] | None, bool]:
    """`prompt_tokens_details` для wire-`usage` и флаг несогласованности.

    Возвращает `(details, inconsistent)`:
    - `cache_read_tokens is None` или `prompt_tokens is None` — `(None, False)`;
      отсутствие данных кэша — не ошибка, ключ на wire не выдаётся;
    - не-`int` (включая `bool`) или отрицательные значения — `(None, False)`;
    - `cache_read_tokens > prompt_tokens` — `(None, True)`; подгонка значения
      под `prompt_tokens` (clamp) запрещена;
    - иначе — `({"cached_tokens": cache_read_tokens}, False)`.

    `cache_creation_tokens` на wire не выдаётся (семантика creation не
    доказана, deferred): параметр принят для совместимости сигнатуры и на
    результат не влияет.
    """
    if cache_read_tokens is None or prompt_tokens is None:
        return None, False
    if not _is_count(cache_read_tokens) or not _is_count(prompt_tokens):
        return None, False
    if cache_read_tokens < 0 or prompt_tokens < 0:
        return None, False
    if cache_read_tokens > prompt_tokens:
        return None, True
    return {"cached_tokens": cache_read_tokens}, False


def extract_cache_read_tokens(usage: Mapping | None) -> int | None:
    """Cache-read токены из usage апстрима; нет валидного значения — `None`.

    Берётся первый ключ из `CACHE_READ_KEYS` с неотрицательным `int` (не `bool`).
    Значений не выдумываем: отсутствие данных — `None`, ключ на wire не появится.
    """
    if not isinstance(usage, Mapping):
        return None
    for key in CACHE_READ_KEYS:
        value = usage.get(key)
        if _is_count(value) and value >= 0:
            return value
    return None
