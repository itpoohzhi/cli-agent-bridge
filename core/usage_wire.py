"""Нормализация cache-токенов для OpenAI-совместимого wire-контракта `usage`.

Чистый модуль (REQ-CACHE-001, AD-004): никакого I/O и логирования. Решение
о предупреждении при `inconsistent=True` принимает вызывающий слой.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeGuard

# Ключи cache-read токенов в usage апстримов (порядок = приоритет).
CACHE_READ_KEYS: tuple[str, ...] = (
    "cacheReadTokens",
    "cache_read_tokens",
    "cache_read_input_tokens",
    "cachedTokens",
)

# Ключи cache-creation токенов (порядок = приоритет).
CACHE_CREATION_KEYS: tuple[str, ...] = (
    "cacheCreationTokens",
    "cache_creation_tokens",
    "cache_creation_input_tokens",
)


def _is_count(value: object) -> TypeGuard[int]:
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


def _first_count(usage: Mapping | None, keys: tuple[str, ...]) -> int | None:
    if not isinstance(usage, Mapping):
        return None
    for key in keys:
        value = usage.get(key)
        if _is_count(value) and value >= 0:
            return value
    return None


def extract_cache_read_tokens(usage: Mapping | None) -> int | None:
    """Cache-read токены из usage апстрима; нет валидного значения — `None`.

    Берётся первый ключ из `CACHE_READ_KEYS` с неотрицательным `int` (не `bool`).
    Значений не выдумываем: отсутствие данных — `None`, ключ на wire не появится.
    """
    return _first_count(usage, CACHE_READ_KEYS)


def extract_cache_creation_tokens(usage: Mapping | None) -> int | None:
    """Cache-creation токены из usage апстрима; нет валидного значения — `None`."""
    return _first_count(usage, CACHE_CREATION_KEYS)


def build_wire_usage(
    input_tokens: object,
    output_tokens: object,
    cache_read_tokens: object,
    cache_creation_tokens: int | None = None,
    *,
    input_includes_cache: bool,
) -> tuple[dict, bool]:
    """Wire-`usage` OpenAI-контракта и флаг несогласованности кэша.

    Единственное место арифметики кэша для мостов. OpenAI-семантика: cached
    входит в `prompt_tokens`. Возвращает `(wire, inconsistent)`.

    `input_includes_cache=True` (апстрим уже включил кэш в `input_tokens`):
    `prompt_tokens = input_tokens`; реальная проверка апстрима —
    `cache_read <= input_tokens`; нарушение -> `inconsistent=True`, детали на
    wire не выдаются (clamp запрещён), вызывающий слой логирует
    `usage_cache_inconsistent`.

    `input_includes_cache=False` (Anthropic/claude: `input_tokens` БЕЗ кэша):
    `prompt_tokens = input_tokens + cache_read + cache_creation`,
    `cached_tokens = cache_read`. Проверка `cached > prompt` здесь невозможна by
    construction (cache_read сам слагаемое prompt) и НЕ вычисляется; кэш-чтение
    выдаётся как есть. `inconsistent=True` только для заданного, но
    нечислового/отрицательного `cache_read` (мусор апстрима).

    Политика нуля единая: `cached_tokens=0` выдаётся, когда апстрим явно сообщил
    нулевой cache-read; отсутствие данных (`None`) — `prompt_tokens_details`
    не выдаётся. `cache_creation` на wire не выдаётся (AD-004).
    """
    prompt = input_tokens if _is_count(input_tokens) and input_tokens >= 0 else 0
    completion = output_tokens if _is_count(output_tokens) and output_tokens >= 0 else 0
    read_value: int | None = (
        cache_read_tokens if _is_count(cache_read_tokens) and cache_read_tokens >= 0 else None
    )
    inconsistent = cache_read_tokens is not None and read_value is None
    details: dict[str, int] | None = None
    if input_includes_cache:
        details, mismatch = normalize_prompt_cache_details(prompt, read_value)
        inconsistent = inconsistent or mismatch
    else:
        for extra in (cache_read_tokens, cache_creation_tokens):
            if _is_count(extra) and extra >= 0:
                prompt += extra
        if read_value is not None:
            details = {"cached_tokens": read_value}
    wire: dict = {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
    }
    if details is not None:
        wire["prompt_tokens_details"] = details
    return wire, inconsistent
