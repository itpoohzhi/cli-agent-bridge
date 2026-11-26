"""Ошибки валидации `reasoning_effort`: общий базовый класс без циклических импортов."""

from __future__ import annotations


class EffortValidationError(ValueError):
    """Ошибка валидации `reasoning_effort` на passthrough-маршруте."""


class EffortBelowFloorError(EffortValidationError):
    """Запрошенный уровень известной шкалы ниже минимума, разрешённого моделью.

    Уровень никогда не повышается молча: вызывающий отвечает HTTP 400
    `unsupported_reasoning_effort` либо пропускает регистрацию алиаса.
    """
