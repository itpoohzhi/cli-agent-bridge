from __future__ import annotations

# Чистый zero-IO модуль телеметрии claude-bridge (AD-001, AD-002, REQ-001).
#
# Форматирование `done`-суффикса и проекция wire-`usage`. Без I/O, логирования
# и чтения окружения: флаг cache_creation передаёт вызывающий слой.

from collections.abc import Mapping

from core.usage_wire import CACHE_CREATION_KEYS, extract_cache_creation_tokens

DONE_USAGE_FIELDS: tuple[str, ...] = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)
_DIGEST_PREFIX_LEN = 16
# Отсутствующее значение usage (None) выводится как `-`.
_MISSING: dict[str, str] = {"None": "-"}


def format_done_usage_suffix(
    usage: Mapping[str, object] | None, chat_digest: str | None
) -> str:
    """Фрагмент `done`-лога: 4 usage-поля и `chat_key` (только префикс digest)."""
    source = usage or {}
    parts = [
        f"{name}={_MISSING.get(str(value), value)}"
        for name in DONE_USAGE_FIELDS
        for value in (source.get(name),)
    ]
    parts.append(f"chat_key={(chat_digest or '-')[:_DIGEST_PREFIX_LEN]}")
    return " ".join(parts)


def project_wire_usage(
    wire_usage: Mapping[str, object],
    raw_usage: Mapping[str, object] | None,
    *,
    include_cache_creation: bool,
) -> dict[str, object]:
    """Копия wire-`usage`; top-level `cache_creation_input_tokens` — только по флагу.

    Флаг выключен: ключи `cache_creation*` не выдаются (AD-004 сохранён).
    """
    projected: dict[str, object] = dict(wire_usage)
    for key in CACHE_CREATION_KEYS:
        projected.pop(key, None)
    created = extract_cache_creation_tokens(raw_usage)
    if include_cache_creation and created is not None:
        projected["cache_creation_input_tokens"] = created
    return projected
