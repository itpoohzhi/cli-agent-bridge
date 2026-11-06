"""Общая политика автономности, ролей и входящих запросов разрешения."""

from __future__ import annotations

import os
from collections.abc import Iterable
from enum import StrEnum
from typing import cast

AUTONOMY_LEVELS = ("low", "medium", "high")
AUTONOMY_OFF = "off"


class Autonomy(StrEnum):
    """Допустимые уровни прав, проверяемые конструктором перечисления."""

    OFF = "off"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RpcError(Exception):
    """Ошибка протокола или обязательного read-back."""


class RpcPermissionDenied(RpcError):
    """Нарушение разрешений, при котором replay недопустим."""


def require(condition: bool, error: Exception) -> None:
    """Единая fail-closed граница для декларативных проверок контракта."""
    if not condition:
        raise error


def validate_boolean_flags(
    settings: dict,
    flags: Iterable[str] = ("disableBuiltinSkills", "autoRejectPermissionRequests"),
    error_type: type[Exception] = RpcError,
) -> None:
    """Сообщённые защитные флаги обязаны быть именно bool true."""
    for flag in flags:
        value = settings.get(flag, True)
        require(
            all((isinstance(value, bool), value)),
            error_type(f"settings read-back: {flag} is {value!r}, expected true"),
        )


class AutonomyViolation(ValueError):
    """Ошибка автономности с причиной для HTTP-границы."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def allow_high_autonomy(namespace: str) -> bool:
    """Высокие права разрешает только явный opt-in в конфигурации."""
    return os.environ.get(f"{namespace}_ALLOW_HIGH_AUTONOMY", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def default_autonomy(namespace: str) -> str:
    """Некорректный или запрещённый дефолт понижает права до off."""
    try:
        value = Autonomy(os.environ.get(f"{namespace}_DEFAULT_AUTONOMY", "off").strip())
    except ValueError:
        value = Autonomy.OFF
    if not allow_high_autonomy(namespace):
        value = {Autonomy.HIGH: Autonomy.OFF}.get(value, value)
    return value


def resolve_autonomy(raw: object, namespace: str) -> tuple[str, str]:
    """Проверить запрос до запуска процесса и сохранить источник значения."""
    if raw is None:
        raw = ""
    require(
        isinstance(raw, str),
        AutonomyViolation("unsupported_autonomy", "autonomy must be a string"),
    )
    candidate = cast(str, raw).strip()
    value, source = (
        (candidate, "request")
        if candidate
        else (default_autonomy(namespace), "default")
    )
    try:
        value = Autonomy(value)
    except ValueError as exc:
        raise AutonomyViolation(
            "unsupported_autonomy", "autonomy is not allowed (low|medium|high|off)"
        ) from exc
    allowed = set(Autonomy)
    if not allow_high_autonomy(namespace):
        allowed.discard(Autonomy.HIGH)
    require(
        value in allowed,
        AutonomyViolation(
            "autonomy_forbidden",
            f"high autonomy requires {namespace}_ALLOW_HIGH_AUTONOMY",
        ),
    )
    return value, source


def denied_subagent(subagent_id: str, prefixes: str) -> bool:
    """Проверить настраиваемые префиксы роли без зависимости от агента."""
    normalized = tuple(
        prefix.strip().lower() for prefix in prefixes.split(",") if prefix.strip()
    )
    return subagent_id.strip().lower().startswith(normalized)


def permission_event(*names: object) -> bool:
    """Запрос разрешения недопустим независимо от транспорта и вида кадра."""
    return any("permission" in str(name).lower() for name in names)


def permission_frame(frame: dict) -> bool:
    """Проверить метод и вложенную нотификацию входящего кадра."""
    params = frame.get("params")
    note = params.get("notification") if isinstance(params, dict) else None
    event_type = note.get("type") if isinstance(note, dict) else ""
    return permission_event(frame.get("method", ""), event_type)
