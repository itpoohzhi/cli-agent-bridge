"""Политика моделей без оси effort: каталог объявил `efforts == ["off"]`."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final, cast

from core.effort_errors import EffortValidationError as EffortValidationError
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
_MSG_NOT_STRING: Final[str] = "reasoning_effort must be a string"
_MSG_NOT_ALLOWED: Final[str] = "reasoning_effort is not allowed for this model"


def effortless_clamp_enabled() -> bool:
    """Состояние флага `BRIDGE_EFFORTLESS_CLAMP_ENABLED` (по умолчанию True)."""
    return _EFFORTLESS_CLAMP_SOURCE.enabled(fallback=True)


def _effort_items(efforts: object) -> Iterable[object]:
    """Элементы допустимой коллекции effort; прочие типы не задают шкалу."""
    items = (
        cast("Iterable[object]", efforts)
        if isinstance(efforts, (list, tuple, set, frozenset))
        else ()
    )
    return items


def is_effortless(efforts: object) -> bool:
    """Модель принимает только `off`: у неё нет оси effort."""
    items = _effort_items(efforts)
    return bool(items) and all(
        isinstance(item, str) and item.strip().lower() == OFF for item in items
    )


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
    """Проверить `reasoning_effort` для effortless-модели и вернуть исходный уровень при клампе.

    JSON `null` (его шлют стандартные OpenAI SDK для незаданного поля) равнозначен
    отсутствию параметра: уровня нет, клампа нет.
    """
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise EffortValidationError(_MSG_NOT_STRING)
    candidate = raw.strip().lower()
    clamped_from = None
    if candidate and candidate != OFF:
        if not _clamps_to_off(candidate, (OFF,), EFFORT_LEVELS, clamp_enabled):
            raise EffortValidationError(_MSG_NOT_ALLOWED)
        clamped_from = candidate
    return clamped_from


def strip_effortless_effort(
    req: dict[str, object],
    spec: ModelEffortSpec,
    res: EffortResolution,
    clamp_enabled: bool | None = None,
) -> tuple[dict[str, object], EffortResolution]:
    """Проверить и убрать `reasoning_effort` из запроса модели без оси effort."""
    clean, resolution = req, res
    if is_effortless(spec.efforts):
        if "reasoning_effort" in req:
            clamped_from = _resolve_clamped_from(req["reasoning_effort"], clamp_enabled)
            clean = dict(req)
            _ = clean.pop("reasoning_effort", None)
            resolution = EffortResolution(OFF, True, clamped_from)
        elif res.apply:
            resolution = replace(res, apply=False)
    return clean, resolution


def effort_cli_args(effort: str | None) -> list[str]:
    """Аргументы CLI: для пустого и `off` флаг `--effort` не передаётся."""
    args: list[str] = []
    if effort is not None and effort.strip().lower() not in ("", OFF):
        args = ["--effort", effort]
    return args


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
    fields: tuple[object, str | None]
    if isinstance(model, ModelEffortSpec):
        fields = model.efforts, model.default
    else:
        raw_default = model.get("default_effort")
        fields = (
            model.get("efforts"),
            raw_default if isinstance(raw_default, str) else None,
        )
    return fields


def _supported_effort_map(efforts: object) -> dict[str, str]:
    """Непустые строковые уровни; последнее совпадение задаёт написание."""
    return {
        item.strip().lower(): item.strip()
        for item in _effort_items(efforts)
        if isinstance(item, str) and item.strip()
    }


def _clamps_to_off(
    candidate_key: str,
    efforts: object,
    levels: Sequence[str],
    clamp_enabled: bool | None,
) -> bool:
    """Известный шкале уровень для модели без оси effort клампится в `off`."""
    enabled = False
    if is_effortless(efforts):
        known = {item.strip().lower() for item in levels if item.strip()}
        if candidate_key in known:
            enabled = (
                effortless_clamp_enabled() if clamp_enabled is None else clamp_enabled
            )
    return enabled


def _resolve_candidate_effort(
    candidate: str,
    efforts: object,
    levels: Sequence[str],
    clamp_enabled: bool | None,
) -> EffortDecision:
    """Разрешить непустой строковый effort по шкале модели и политике клампа."""
    key = candidate.lower()
    supported = _supported_effort_map(efforts)
    decision = EffortDecision(None, None, _MSG_NOT_ALLOWED)
    if key in supported:
        decision = EffortDecision(supported[key], SOURCE_REQUEST, None)
    elif _clamps_to_off(key, efforts, levels, clamp_enabled):
        decision = EffortDecision(OFF, SOURCE_CLAMPED, None)
    return decision


def resolve_request_effort(
    raw: object,
    model: Mapping[str, object] | ModelEffortSpec,
    levels: Sequence[str],
    *,
    clamp_enabled: bool | None = None,
) -> EffortDecision:
    """Effort запроса по записи каталога; ошибки — тексты 400 `unsupported_reasoning_effort`."""
    efforts, default_effort = _model_effort_fields(model)
    decision = EffortDecision(default_effort, SOURCE_DEFAULT, None)
    if raw is not None:
        if not isinstance(raw, str):
            decision = EffortDecision(None, None, _MSG_NOT_STRING)
        elif candidate := raw.strip():
            decision = _resolve_candidate_effort(
                candidate, efforts, levels, clamp_enabled
            )
    return decision
