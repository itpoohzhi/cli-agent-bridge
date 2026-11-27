"""Схема `backends.<id>.params`: валидация и сериализация диалекта параметров (REQ-004).

Один модуль на оба компилятора каталога и на загрузчик (`backend_adapter`): без дублирования
кода и без обратных импортов (`provider_manifest` импортирует `backend_adapter`, не наоборот).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.param_adapter import GLOBAL_WHITELIST

BACKEND_PARAMS_INVALID = "backend_params_invalid"
BACKEND_PARAMS_KEYS = frozenset(
    {"effort_field", "effort_map", "adaptive_whitelist", "strip_always", "cache_control_strategy"}
)
_EFFORT_FIELDS = ("reasoning_effort", "effort", "none")
_DEFAULT_EFFORT_FIELD = "reasoning_effort"
_CACHE_STRATEGIES = (None, "anthropic_ephemeral")


def _str_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value)


def _effort_map_ok(value: Any) -> bool:
    """`effort_map`: уровень -> строка либо патч-объект с непустыми строковыми ключами."""
    if not isinstance(value, Mapping):
        return False
    return all(
        isinstance(level, str) and level
        and (isinstance(patch, str) or (isinstance(patch, Mapping) and all(isinstance(k, str) for k in patch)))
        for level, patch in value.items()
    )


def validate_backend_params(params: Any) -> str:
    """Причина отказа `backends.<id>.params` ('' — валидно; `None` — ключ не задан)."""
    if params is None:
        return ""
    if not isinstance(params, Mapping) or set(params) - BACKEND_PARAMS_KEYS:
        return BACKEND_PARAMS_INVALID
    if params.get("effort_field", _DEFAULT_EFFORT_FIELD) not in _EFFORT_FIELDS:
        return BACKEND_PARAMS_INVALID
    if not _effort_map_ok(params.get("effort_map", {})):
        return BACKEND_PARAMS_INVALID
    for key in ("adaptive_whitelist", "strip_always"):
        if key in params and not _str_list(params[key]):
            return BACKEND_PARAMS_INVALID
    if any(item not in GLOBAL_WHITELIST for item in params.get("adaptive_whitelist", ())):
        return BACKEND_PARAMS_INVALID
    if params.get("cache_control_strategy") not in _CACHE_STRATEGIES:
        return BACKEND_PARAMS_INVALID
    return ""


def _is_default(params: Any) -> bool:
    return (
        params.effort_field == _DEFAULT_EFFORT_FIELD
        and not params.effort_map
        and tuple(params.adaptive_whitelist) == tuple(GLOBAL_WHITELIST)
        and not params.strip_always
        and getattr(params, "cache_control_strategy", None) is None
    )


def extract_backend_params(manifest: Any) -> dict[str, Any]:
    """`{"params": {...}}` для записи backend либо `{}`, если диалект манифеста дефолтный."""
    params = getattr(manifest, "params", None)
    if params is None or _is_default(params):
        return {}
    out: dict[str, Any] = {
        "effort_field": params.effort_field,
        "effort_map": {k: _plain(v) for k, v in params.effort_map.items()},
        "adaptive_whitelist": list(params.adaptive_whitelist),
        "strip_always": list(params.strip_always),
    }
    strategy = getattr(params, "cache_control_strategy", None)
    if strategy is not None:
        out["cache_control_strategy"] = strategy
    return {"params": out}


def serialize_sidecar_params(params: Any) -> dict[str, Any]:
    """`params` для сайдкара `catalog-lock/1` (включая `tool_emulation`)."""
    out: dict[str, Any] = {
        "effort_field": params.effort_field,
        "effort_map": dict(params.effort_map),
        "adaptive_whitelist": list(params.adaptive_whitelist),
        "strip_always": list(params.strip_always),
        "tool_emulation": params.tool_emulation,
    }
    strategy = getattr(params, "cache_control_strategy", None)
    if strategy is not None:
        out["cache_control_strategy"] = strategy
    return out


def _plain(value: Any) -> Any:
    """Глубокая копия JSON-совместимого значения (Mapping -> dict)."""
    if isinstance(value, Mapping):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value
