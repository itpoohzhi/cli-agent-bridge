"""Чистые контракты usage-полей: нормализация, reasoning-токены, конвертации для ходов и телеметрии (0 I/O)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeGuard

from core.telemetry_util import first, present

_PRESENCE_KEYS: tuple[str, ...] = (
    "input_tokens",
    "prompt_tokens",
    "output_tokens",
    "completion_tokens",
    "cache_read_tokens",
    "cache_read_input_tokens",
    "cached_tokens",
    "reasoning_tokens",
    "total_tokens",
)
_TURN_USAGE_FIELDS: tuple[tuple[str, str], ...] = (
    ("input_tokens", "prompt_tokens"),
    ("output_tokens", "completion_tokens"),
    ("cache_read_tokens", "cache_read_tokens"),
    ("reasoning_tokens", "reasoning_tokens"),
)


def _is_counter(value: Any) -> TypeGuard[int]:
    """Целочисленный неотрицательный счётчик токенов: int без bool и без отрицательных значений."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_number(value: Any) -> TypeGuard[int | float]:
    """Числовое поле usage для признака usage_present: int/float, но не bool."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _nested(raw: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    """Вложенный mapping из usage по ключу; отсутствие или не-mapping дают пустой словарь."""
    value = raw.get(key)
    return value if isinstance(value, Mapping) else {}


def _usage_present(raw: Mapping[str, Any]) -> bool:
    """Usage реально передан: явный usage_present=True или числовое поле среди известных ключей."""
    if raw.get("usage_present") is True:
        return True
    return any(_is_number(raw.get(key)) for key in _PRESENCE_KEYS)


def extract_reasoning_tokens(raw: Mapping[str, Any]) -> int | None:
    """reasoning_tokens из usage: прямой ключ, completion_tokens_details или output_tokens_details."""
    sources = (raw, _nested(raw, "completion_tokens_details"), _nested(raw, "output_tokens_details"))
    for source in sources:
        value = source.get("reasoning_tokens")
        if _is_counter(value):
            return value
    return None


def normalize_usage_fields(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    """Плоские нормализованные поля usage: input/output/cache_read/reasoning + usage_present (None -> все None)."""
    if raw is None:
        return {
            "input_tokens": None,
            "output_tokens": None,
            "cache_read_tokens": None,
            "reasoning_tokens": None,
            "usage_present": None,
        }
    return {
        "input_tokens": first(raw.get("input_tokens"), raw.get("prompt_tokens")),
        "output_tokens": first(raw.get("output_tokens"), raw.get("completion_tokens")),
        "cache_read_tokens": first(
            raw.get("cache_read_tokens"),
            raw.get("cache_read_input_tokens"),
            raw.get("cached_tokens"),
            _nested(raw, "prompt_tokens_details").get("cached_tokens"),
        ),
        "reasoning_tokens": extract_reasoning_tokens(raw),
        "usage_present": _usage_present(raw),
    }


def enrich_turn_usage_dict(base_usage: Mapping[str, Any], turn_usage: Any) -> dict[str, Any]:
    """Копия базового usage хода, дополненная полями TurnUsage (None не перезаписывает базу); usage_present=True."""
    enriched = dict(base_usage)
    for key, attr in _TURN_USAGE_FIELDS:
        value = getattr(turn_usage, attr, None)
        if value is not None:
            enriched[key] = value
    enriched["usage_present"] = True
    return enriched


def telemetry_usage_updates(usage: Mapping[str, Any] | None) -> dict[str, Any]:
    """Поля usage -> метаданные телеметрии события: prompt/completion/cached/reasoning + usage_present."""
    fields = normalize_usage_fields(usage)
    updates = present(
        {
            "prompt_tokens": fields["input_tokens"],
            "completion_tokens": fields["output_tokens"],
            "cached_tokens": fields["cache_read_tokens"],
            "reasoning_tokens": fields["reasoning_tokens"],
        }
    )
    updates["usage_present"] = fields["usage_present"]
    return updates


def _total_tokens(prompt: Any, completion: Any) -> int | None:
    """total_tokens = prompt + completion при положительной сумме; иначе None (обратная совместимость)."""
    if not (_is_number(prompt) or _is_number(completion)):
        return None
    total = (int(prompt) if _is_number(prompt) else 0) + (int(completion) if _is_number(completion) else 0)
    return total if total > 0 else None


def finalize_event_usage(meta: dict[str, Any]) -> dict[str, Any]:
    """Блок usage события: pop полей из meta, total_tokens и вывод usage_present по наличию токенов."""
    prompt = meta.pop("prompt_tokens", None)
    completion = meta.pop("completion_tokens", None)
    cached = meta.pop("cached_tokens", None)
    reasoning = meta.pop("reasoning_tokens", None)
    usage_present = meta.pop("usage_present", None)
    if usage_present is None:
        usage_present = any(value is not None for value in (prompt, completion, cached, reasoning))
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "cached_tokens": cached,
        "reasoning_tokens": reasoning,
        "total_tokens": _total_tokens(prompt, completion),
        "usage_present": usage_present,
    }
