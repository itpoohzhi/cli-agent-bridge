"""Политика моделей без оси effort: каталог объявил `efforts == ["off"]`."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final, cast

from core.effort_policy import (
    EFFORT_LEVELS,
    EffortResolution,
    ModelEffortCardFields,
    ModelEffortSpec,
)
from core.runtime_env import DynamicFlagSource

OFF: Final[str] = "off"
SOURCE_DEFAULT: Final[str] = "default"
SOURCE_REQUEST: Final[str] = "request"
SOURCE_CLAMPED: Final[str] = "clamped"
FLAG_EFFORTLESS_CLAMP: Final[str] = "BRIDGE_EFFORTLESS_CLAMP_ENABLED"
_EFFORTLESS_CLAMP_SOURCE: Final[DynamicFlagSource] = DynamicFlagSource(
    FLAG_EFFORTLESS_CLAMP, default=True
)
_KNOWN_EFFORT_LEVELS: Final[frozenset[str]] = frozenset(EFFORT_LEVELS)
_MSG_NOT_STRING: Final[str] = "reasoning_effort must be a string"
_MSG_NOT_ALLOWED: Final[str] = "reasoning_effort is not allowed for this model"


class EffortValidationError(ValueError):
    """Ошибка валидации `reasoning_effort` на passthrough-маршруте."""


def effortless_clamp_enabled() -> bool:
    """Состояние флага `BRIDGE_EFFORTLESS_CLAMP_ENABLED` (по умолчанию True)."""
    return _EFFORTLESS_CLAMP_SOURCE.enabled(fallback=True)


def is_effortless(efforts: object) -> bool:
    """Модель принимает только `off`: у неё нет оси effort."""
    if not isinstance(efforts, (list, tuple, set, frozenset)) or not efforts:
        return False
    items = cast("Iterable[object]", efforts)
    return all(isinstance(item, str) and item.strip().lower() == OFF for item in items)


def effortless_specs(
    specs: Mapping[str, ModelEffortSpec],
) -> dict[str, ModelEffortSpec]:
    """Подсловарь спек моделей без оси effort."""
    return {name: spec for name, spec in specs.items() if is_effortless(spec.efforts)}


def card_effort_fields(fields: ModelEffortCardFields) -> dict[str, object]:
    """Поля effort карточки `/v1/models`."""
    result: dict[str, object] = {
        "supported_reasoning_efforts": list(fields.supported_efforts),
        "default_reasoning_effort": fields.default_effort,
    }
    if is_effortless(fields.supported_efforts):
        result["supports_thinking"] = False
    return result


def _resolve_clamped_from(raw: object, clamp_enabled: bool | None) -> str | None:
    """Проверить `reasoning_effort` для effortless-модели и вернуть исходный уровень при клампе."""
    if not isinstance(raw, str):
        raise EffortValidationError(_MSG_NOT_STRING)
    candidate = raw.strip().lower()
    if not candidate or candidate == OFF:
        return None
    if candidate not in _KNOWN_EFFORT_LEVELS:
        raise EffortValidationError(_MSG_NOT_ALLOWED)
    enabled = effortless_clamp_enabled() if clamp_enabled is None else clamp_enabled
    if not enabled:
        raise EffortValidationError(_MSG_NOT_ALLOWED)
    return candidate


def strip_effortless_effort(
    req: dict[str, object],
    spec: ModelEffortSpec,
    res: EffortResolution,
    clamp_enabled: bool | None = None,
) -> tuple[dict[str, object], EffortResolution]:
    """Проверить и убрать `reasoning_effort` из запроса модели без оси effort."""
    if not is_effortless(spec.efforts):
        return req, res
    if "reasoning_effort" not in req:
        return req, replace(res, apply=False) if res.apply else res
    clamped_from = _resolve_clamped_from(req["reasoning_effort"], clamp_enabled)
    clean = dict(req)
    _ = clean.pop("reasoning_effort", None)
    return clean, EffortResolution(OFF, True, clamped_from)


def effort_cli_args(effort: str | None) -> list[str]:
    """Аргументы CLI: для пустого и `off` флаг `--effort` не передаётся."""
    if effort is None or effort.strip().lower() in ("", OFF):
        return []
    return ["--effort", effort]


@dataclass(frozen=True, slots=True)
class EffortDecision:
    """Итог разбора effort: уровень и источник либо текст ошибки 400."""

    effort: str | None
    source: str | None
    error: str | None


def _model_effort_fields(
    model: Mapping[str, object] | ModelEffortSpec,
) -> tuple[object, str | None]:
    """Извлечь `efforts` и `default_effort` из записи каталога или `ModelEffortSpec`."""
    if isinstance(model, ModelEffortSpec):
        return model.efforts, model.default
    raw_default = model.get("default_effort")
    return model.get("efforts"), raw_default if isinstance(raw_default, str) else None


def _supported_effort_map(efforts: object) -> dict[str, str]:
    if not isinstance(efforts, (list, tuple, set, frozenset)):
        return {}
    items = cast("Iterable[object]", efforts)
    return {
        item.strip().lower(): item.strip()
        for item in items
        if isinstance(item, str) and item.strip()
    }


def _clamps_to_off(
    candidate_key: str,
    efforts: object,
    levels: Sequence[str],
    clamp_enabled: bool | None,
) -> bool:
    """Известный шкале уровень для модели без оси effort клампится в `off`."""
    if not is_effortless(efforts):
        return False
    known = {item.strip().lower() for item in levels if item.strip()}
    if candidate_key not in known:
        return False
    return effortless_clamp_enabled() if clamp_enabled is None else clamp_enabled


def resolve_request_effort(
    raw: object,
    model: Mapping[str, object] | ModelEffortSpec,
    levels: Sequence[str],
    *,
    clamp_enabled: bool | None = None,
) -> EffortDecision:
    """Effort запроса по записи каталога; ошибки — тексты 400 `unsupported_reasoning_effort`."""
    efforts, default_effort = _model_effort_fields(model)
    if raw is None:
        return EffortDecision(default_effort, SOURCE_DEFAULT, None)
    if not isinstance(raw, str):
        return EffortDecision(None, None, _MSG_NOT_STRING)
    candidate = raw.strip()
    if not candidate:
        return EffortDecision(default_effort, SOURCE_DEFAULT, None)
    key = candidate.lower()
    supported = _supported_effort_map(efforts)
    if key in supported:
        return EffortDecision(supported[key], SOURCE_REQUEST, None)
    if _clamps_to_off(key, efforts, levels, clamp_enabled):
        return EffortDecision(OFF, SOURCE_CLAMPED, None)
    return EffortDecision(None, None, _MSG_NOT_ALLOWED)
