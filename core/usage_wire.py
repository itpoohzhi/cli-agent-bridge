"""Нормализация cache-токенов для OpenAI-совместимого wire-контракта `usage`.

Чистый модуль (REQ-CACHE-001, AD-004): никакого I/O и логирования. Решение
о предупреждении при `inconsistent=True` принимает вызывающий слой.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeGuard, cast

from core.turn_usage import TurnUsage, UsageScope, UsageUpdate, normalize_usage_update

# Ключи cache-read токенов в usage апстримов (порядок = приоритет).
CACHE_READ_KEYS: tuple[str, ...] = (
    "prompt_cache_hit_tokens",
    "cacheReadTokens",
    "cache_read_tokens",
    "cache_read_input_tokens",
    "cachedTokens",
    "cached_tokens",
)

# Ключи cache-creation токенов (порядок = приоритет).
CACHE_CREATION_KEYS: tuple[str, ...] = (
    "cacheCreationTokens",
    "cache_creation_tokens",
    "cache_creation_input_tokens",
)


def _is_count(value: object) -> TypeGuard[int]:
    """Целое счётное значение (>= 0); `bool` допустимым числом не является."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


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


def _value(source: Any, key: str) -> Any:
    """Безопасное чтение поля из Mapping или SDK-объекта с атрибутами."""
    if isinstance(source, Mapping):
        return source.get(key)
    if source is None:
        return None
    try:
        return getattr(source, key, None)
    except (AttributeError, TypeError):
        return None


def _first_count(usage: Any, keys: tuple[str, ...]) -> int | None:
    if usage is None:
        return None
    for key in keys:
        val = _value(usage, key)
        if _is_count(val) and val >= 0:
            return val
    return None


def extract_cache_read_tokens(usage: Any) -> int | None:
    """Cache-read токены из usage апстрима; нет валидного значения — `None`.

    В первую очередь проверяет канонический `prompt_tokens_details.cached_tokens`,
    затем первый ключ из `CACHE_READ_KEYS` с неотрицательным `int` (не `bool`).
    Значений не выдумываем: отсутствие данных — `None`, ключ на wire не появится.
    """
    if usage is None:
        return None
    canonical = _first_count(
        _value(usage, "prompt_tokens_details"), ("cached_tokens",)
    )
    if canonical is not None:
        return canonical
    return _first_count(usage, CACHE_READ_KEYS)


def extract_cache_creation_tokens(usage: Any) -> int | None:
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


def positive_wire_usage(usage: object) -> dict | None:
    """Копия wire-`usage` с положительными счётчиками, иначе `None` (ошибка не обнуляет токены)."""
    if not isinstance(usage, Mapping):
        return None
    keys = ("prompt_tokens", "completion_tokens", "total_tokens", "cached_tokens", "reasoning_tokens")
    values: list[object] = [
        *(usage.get(k) for k in keys),  # pyright: ignore[reportUnknownMemberType]
        _wire_nested(usage, "prompt_tokens_details", "cached_tokens"),  # pyright: ignore[reportUnknownArgumentType]
        _wire_nested(usage, "completion_tokens_details", "reasoning_tokens"),  # pyright: ignore[reportUnknownArgumentType]
        _wire_nested(usage, "output_tokens_details", "reasoning_tokens"),  # pyright: ignore[reportUnknownArgumentType]
    ]
    positive = any(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in values)
    return dict(usage) if positive else None  # pyright: ignore[reportUnknownArgumentType]


def build_turn_wire_usage(usage: TurnUsage) -> dict[str, Any]:
    """Serialize canonical TurnUsage to OpenAI wire `usage` dict (single SSOT)."""
    wire: dict[str, Any] = {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
    }
    if usage.cache_read_tokens is not None:
        wire["prompt_tokens_details"] = {"cached_tokens": usage.cache_read_tokens}
    if usage.reasoning_tokens is not None:
        wire["completion_tokens_details"] = {"reasoning_tokens": usage.reasoning_tokens}
    return wire


def _wire_nested(mapping: Mapping[str, Any], parent: str, child: str) -> Any:
    sub = mapping.get(parent)
    return sub.get(child) if isinstance(sub, Mapping) else None


def turn_usage_from_wire(value: object, source: str) -> TurnUsage | None:
    """Parse an OpenAI wire `usage` mapping into canonical TurnUsage (fail-closed)."""
    if not isinstance(value, Mapping):
        return None
    mapping = cast(Mapping[str, Any], value)
    cached = _wire_nested(mapping, "prompt_tokens_details", "cached_tokens")
    if cached is None and "cached_tokens" in mapping:
        cached = mapping.get("cached_tokens")
    reasoning = _wire_nested(mapping, "completion_tokens_details", "reasoning_tokens")
    if reasoning is None and "reasoning_tokens" in mapping:
        reasoning = mapping.get("reasoning_tokens")
    update = UsageUpdate(
        input_tokens=mapping.get("prompt_tokens"),
        output_tokens=mapping.get("completion_tokens"),
        cache_read_tokens=cached,
        cache_creation_tokens=None,
        reasoning_tokens=reasoning,
        reported_total_tokens=mapping.get("total_tokens"),
        input_includes_cache=True,
        output_includes_reasoning=True,
        source=source,
        scope=UsageScope.TURN_SNAPSHOT,
    )
    return normalize_usage_update(update).usage
