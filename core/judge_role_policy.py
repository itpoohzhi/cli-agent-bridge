"""Политика судейской роли Совета: распознавание роли и кламп автономности (AD-001).

Судьи и места Совета больше не отвергаются безусловно на границе шлюза: роль
допускается к read-only ходу, а мутирующая автономность запрещается здесь, в
универсальном ядре, одинаково для всех потребителей.

Ошибка контракта автономности объявлена в этом же модуле: это базовый модуль ролей,
`core.gateway_execution_policy` реэкспортирует её и импортирует проверку роли, поэтому
зависимость остаётся однонаправленной и цикл импортов универсального ядра не возникает.
"""

from __future__ import annotations

import os

# Префиксы судейских ролей по умолчанию; переопределяются env DROID_JUDGE_SUBAGENT_PREFIXES.
JUDGE_SUBAGENT_PREFIXES: tuple[str, ...] = ("panel-judge-", "judge-", "seat-")
JUDGE_PREFIXES_ENV = "DROID_JUDGE_SUBAGENT_PREFIXES"
JUDGE_AUTONOMY_OFF = "off"


class AutonomyViolation(ValueError):
    """Ошибка автономности с причиной для HTTP-границы."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason: str = reason


def _normalize_prefixes(raw: str) -> tuple[str, ...]:
    """Нормализовать перечень префиксов: пустые и дикие элементы отброшены.

    Пустая строка или `*` не должны превращаться в разрешение судейской роли
    на любую мутацию: после отбраковки набор либо пуст (дефолт), либо конкретен.
    """
    return tuple(
        item.strip().lower()
        for item in raw.split(",")
        if item.strip() and item.strip() != "*"
    )


def judge_subagent_prefixes() -> tuple[str, ...]:
    """Действующий перечень судейских префиксов; пустой env откатывается на дефолт."""
    configured = _normalize_prefixes(os.environ.get(JUDGE_PREFIXES_ENV, ""))
    return configured or JUDGE_SUBAGENT_PREFIXES


def is_judge_subagent(subagent_id: str | None) -> bool:
    """Считать роль судейской, если нормализованный идентификатор начинается с префикса."""
    candidate = str(subagent_id or "").strip().lower()
    return bool(candidate) and candidate.startswith(judge_subagent_prefixes())


def validate_judge_autonomy(subagent_id: str | None, autonomy: str) -> None:
    """Запретить мутирующую автономность судейской роли.

    Пустое значение означает дефолт ``off``; любой другой уровень (`low`, `medium`,
    `high`) для судьи — нарушение роли, а не повод молча понизить права.
    """
    if not is_judge_subagent(subagent_id):
        return
    normalized = str(autonomy or "").strip().lower()
    if normalized in ("", JUDGE_AUTONOMY_OFF):
        return
    raise AutonomyViolation(
        "autonomy_role_forbidden",
        f"judge subagent role {subagent_id!r} cannot have mutating autonomy {autonomy!r}",
    )
