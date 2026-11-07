"""Общая политика автономности, ролей и входящих запросов разрешения."""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

AUTONOMY_LEVELS = ("low", "medium", "high")
AUTONOMY_OFF = "off"
# Префиксы ролей по умолчанию: мутировать вправе только coder-*, судьи и места запрещены.
MUTATING_SUBAGENT_DEFAULT = "coder-"
DENY_SUBAGENT_DEFAULT = "panel-judge-,judge-,seat-"


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
    settings: dict[str, object],
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
        self.reason: str = reason


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


@dataclass(frozen=True)
class AutonomyDecision:
    """Проверенный уровень прав и источник его значения."""

    value: str
    source: str


def _csv_env(name: str, default: str) -> tuple[str, ...]:
    """Нормализовать префиксы; пустые и дикие элементы отброшены, пустой набор — дефолт.

    Пустая строка или `*` в конфигурации не должны превращаться в разрешение всем:
    после отбраковки набор всегда непустой, а `startswith(())` ложен.
    """
    items = tuple(
        item.strip().lower()
        for item in os.environ.get(name, default).split(",")
        if item.strip() and item.strip() != "*"
    )
    return items or tuple(
        item.strip().lower() for item in default.split(",") if item.strip()
    )


def _check_mutating_role(
    value: str, namespace: str, subagent_id: str | None, require_subagent: bool
) -> None:
    """Мутации Droid требуют разрешённую роль; HTTP не допускает opt-out."""
    if namespace.upper() != "DROID" or value not in ("low", "medium"):
        return
    enforced = (
        os.environ.get("DROID_REQUIRE_SUBAGENT_FOR_MUTATION", "1").strip().lower()
    )
    if not (
        require_subagent
        or subagent_id is not None
        or enforced not in ("0", "false", "no")
    ):
        return
    prefixes = _csv_env(
        f"{namespace.upper()}_MUTATING_SUBAGENT_PREFIXES", MUTATING_SUBAGENT_DEFAULT
    )
    require(
        (subagent_id or "").strip().lower().startswith(prefixes),
        AutonomyViolation(
            "autonomy_role_forbidden",
            f"autonomy={value!r} requires mutating subagent prefix {prefixes}",
        ),
    )


def validate_autonomy_request(raw: object) -> str:
    """Проверить формат уровня прав без backend-специфичных ограничений.

    Сохраняет прежний контракт не-Droid маршрутов: не строковое значение или строка
    вне `low|medium|high|off` даёт `unsupported_autonomy`, а отсутствие и пустая
    строка остаются ``""`` (дефолт выбирает вызывающая сторона).
    """
    if raw is None:
        return ""
    require(
        isinstance(raw, str),
        AutonomyViolation("unsupported_autonomy", "autonomy must be a string"),
    )
    candidate = cast(str, raw).strip()
    if not candidate:
        return ""
    try:
        return Autonomy(candidate).value
    except ValueError as exc:
        raise AutonomyViolation(
            "unsupported_autonomy", "autonomy is not allowed (low|medium|high|off)"
        ) from exc


def resolve_autonomy_decision(
    raw: object,
    namespace: str = "DROID",
    subagent_id: str | None = None,
    *,
    require_subagent: bool = False,
) -> AutonomyDecision:
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
    _check_mutating_role(value, namespace, subagent_id, require_subagent)
    return AutonomyDecision(value, source)


def resolve_autonomy(
    raw: object,
    namespace: str = "DROID",
    subagent_id: str | None = None,
    *,
    require_subagent: bool = False,
) -> str:
    """Совместимый строковый интерфейс без потери проверок политики."""
    return resolve_autonomy_decision(
        raw, namespace, subagent_id, require_subagent=require_subagent
    ).value


def denied_subagent(namespace: str, *subagent_ids: str | None) -> bool:
    """Запретить роль по любому представлению идентификатора в рамках namespace.

    Проверяется объединение значений (raw-заголовок и trace из заголовка, extra_body
    или тела), чтобы запрет нельзя было обойти альтернативным источником.
    """
    prefixes = _csv_env(
        f"{namespace.upper()}_DENY_SUBAGENT_PREFIXES", DENY_SUBAGENT_DEFAULT
    )
    return any(
        candidate.strip().lower().startswith(prefixes)
        for candidate in (str(value or "") for value in subagent_ids)
        if candidate.strip()
    )


def permission_event(*names: object) -> bool:
    """Запрос разрешения недопустим независимо от транспорта и вида кадра."""
    return any("permission" in str(name).lower() for name in names)


def permission_frame(frame: dict[str, object]) -> bool:
    """Проверить метод и вложенную нотификацию входящего кадра."""
    params = frame.get("params")
    note = (
        cast(dict[str, object], params).get("notification")
        if isinstance(params, dict)
        else None
    )
    event_type = (
        cast(dict[str, object], note).get("type") if isinstance(note, dict) else ""
    )
    return permission_event(frame.get("method", ""), event_type)
