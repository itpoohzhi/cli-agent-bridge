"""Usage-блок из хвоста ответа апстрима (JSON или SSE): универсально для OpenAI- и Anthropic-подобных форматов."""

from __future__ import annotations

import functools
import json
import re
from collections.abc import Mapping
from typing import Any

from core import defaults as D
from core.telemetry_util import first, present

_USAGE_KEY = re.compile(r'"usage"\s*:\s*')
_DECODER = json.JSONDecoder()


@functools.lru_cache(maxsize=1)
def tail_limit() -> int:
    """Размер хвоста ответа для разбора usage: BRIDGE_TELEMETRY_USAGE_TAIL_BYTES (читается один раз на процесс)."""
    return max(1, D.get_env_int("BRIDGE_TELEMETRY_USAGE_TAIL_BYTES", D.BRIDGE_TELEMETRY_USAGE_TAIL_BYTES))


def _details(raw: Mapping[str, Any]) -> Mapping[str, Any]:
    details = raw.get("prompt_tokens_details")
    result = details if isinstance(details, Mapping) else {}
    return result


def normalize_usage(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Поля usage апстрима -> ключи CLI-веток (_telemetry_usage): input/output/cache_read; нет значения -> None."""
    return {
        "input_tokens": first(raw.get("input_tokens"), raw.get("prompt_tokens")),
        "output_tokens": first(raw.get("output_tokens"), raw.get("completion_tokens")),
        "cache_read_tokens": first(
            raw.get("cache_read_input_tokens"), raw.get("cached_tokens"), _details(raw).get("cached_tokens")),
    }


def _objects(tail: bytes) -> list[Mapping[str, Any]]:
    """Все JSON-объекты после ключа "usage" в хвосте; оборванные и null-значения пропускаются."""
    text = tail.decode("utf-8", errors="ignore")
    found: list[Mapping[str, Any]] = []
    for match in _USAGE_KEY.finditer(text):
        try:
            value, _ = _DECODER.raw_decode(text, match.end())
        except ValueError:
            continue
        if isinstance(value, Mapping):
            found.append(value)
    return found


def extract_usage(tail: bytes) -> dict[str, Any] | None:
    """Usage хвоста ответа в нормализованном виде (поздние объекты дополняют ранние); None — usage в хвосте нет."""
    merged: dict[str, Any] = {}
    for usage in _objects(tail):
        merged.update(present(normalize_usage(usage)))
    return merged or None
