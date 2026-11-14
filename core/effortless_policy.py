"""Политика моделей без оси effort: каталог объявил `efforts == ["off"]`."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from core.effort_policy import EffortResolution, ModelEffortCardFields, ModelEffortSpec
from core.runtime_env import DynamicFlagSource

OFF = "off"
FLAG_EFFORTLESS_CLAMP = "BRIDGE_EFFORTLESS_CLAMP_ENABLED"
_EFFORTLESS_CLAMP_SOURCE = DynamicFlagSource(FLAG_EFFORTLESS_CLAMP, default=True)
_MSG_NOT_STRING = "reasoning_effort must be a string"
_MSG_NOT_ALLOWED = "reasoning_effort is not allowed for this model"


def is_effortless(efforts: Sequence[object] | None) -> bool:
    """Модель принимает только `off`: у неё нет оси effort."""
    if not efforts or isinstance(efforts, (str, bytes)):
        return False
    return {str(item).strip().lower() for item in efforts} == {OFF}


def effortless_specs(
    specs: Mapping[str, ModelEffortSpec],
) -> dict[str, ModelEffortSpec]:
    """Подсловарь спек моделей без оси effort."""
    return {name: spec for name, spec in specs.items() if is_effortless(spec.efforts)}


def card_effort_fields(fields: ModelEffortCardFields) -> dict[str, object]:
    """Поля effort карточки `/v1/models`."""
    return {
        "supports_thinking": not is_effortless(fields.supported_efforts),
        "supported_reasoning_efforts": list(fields.supported_efforts),
        "default_reasoning_effort": fields.default_effort,
    }


def strip_effortless_effort(
    req: dict[str, Any], spec: ModelEffortSpec, res: EffortResolution
) -> tuple[dict[str, Any], EffortResolution]:
    """Убрать `reasoning_effort` из запроса модели без оси effort."""
    if not is_effortless(spec.efforts) or "reasoning_effort" not in req:
        return req, res
    raw = req["reasoning_effort"]
    asked = isinstance(raw, str) and raw.strip().lower() != OFF
    clean = {key: value for key, value in req.items() if key != "reasoning_effort"}
    return clean, EffortResolution(OFF, True, raw if asked else None)


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


def _clamps_to_off(
    candidate: str,
    model: Mapping[str, Any],
    levels: Sequence[str],
    clamp_enabled: bool | None,
) -> bool:
    """Известный шкале уровень для модели без оси effort клампится в `off`."""
    if not is_effortless(model.get("efforts")):
        return False
    if candidate.lower() not in {str(item).strip().lower() for item in levels}:
        return False
    if clamp_enabled is None:
        return _EFFORTLESS_CLAMP_SOURCE.enabled(fallback=True)
    return clamp_enabled


def resolve_request_effort(
    raw: object,
    model: Mapping[str, Any],
    levels: Sequence[str],
    *,
    clamp_enabled: bool | None = None,
) -> EffortDecision:
    """Effort запроса по записи каталога; ошибки — тексты 400 `unsupported_reasoning_effort`."""
    if raw is None:
        return EffortDecision(model.get("default_effort"), "default", None)
    if not isinstance(raw, str):
        return EffortDecision(None, None, _MSG_NOT_STRING)
    candidate = raw.strip()
    if not candidate:
        return EffortDecision(model.get("default_effort"), "default", None)
    if candidate in (model.get("efforts") or ()):
        return EffortDecision(candidate, "request", None)
    if _clamps_to_off(candidate, model, levels, clamp_enabled):
        return EffortDecision(OFF, "clamped", None)
    return EffortDecision(None, None, _MSG_NOT_ALLOWED)
