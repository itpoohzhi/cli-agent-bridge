"""Отчёт о разрешении хода (AD-009, BND-001): строка `turn-resolved` и поля для `/health`.

Детерминированная однострочная строка без секретов и без переводов строк; снимок флагов —
словарь по именам env. Чистые функции: источник флагов и логгер — на стороне вызывающего.
"""

from __future__ import annotations

import re
from dataclasses import fields

from core.transport_failure_contracts import (
    FLAG_ENV_BY_FIELD,
    FailureKind,
    RecoveryFlagSnapshot,
    TurnResolutionReport,
)

MAX_REASON_CHARS = 120
_UNSAFE = re.compile(r"[^A-Za-z0-9_.:\-]+")


def flags_snapshot_dict(flags: RecoveryFlagSnapshot) -> dict[str, bool]:
    """Снимок флагов по именам env в фиксированном порядке (для `/health`)."""
    return {env: bool(getattr(flags, field)) for field, env in FLAG_ENV_BY_FIELD}


def _safe(value: object, limit: int = MAX_REASON_CHARS) -> str:
    """Один токен без пробелов/переводов строк и спецсимволов; пусто → `none`."""
    token = _UNSAFE.sub("_", str(value)).strip("_")
    return token[:limit] or "none"


def build_turn_resolution_report(
    reason: str,
    flags: RecoveryFlagSnapshot | None = None,
    attempts: int = 0,
    failure_kind: FailureKind = FailureKind.UNCLASSIFIED,
) -> TurnResolutionReport:
    """Собрать отчёт; `flags=None` — все флаги выключены."""
    snapshot = flags if flags is not None else RecoveryFlagSnapshot()
    return TurnResolutionReport(_safe(reason), snapshot, max(0, int(attempts)), failure_kind)


def format_turn_resolved(report: TurnResolutionReport) -> str:
    """Строка лога: `turn-resolved reason=… kind=… attempts=… flags_on=a,b|none`."""
    on = [f.name for f in fields(report.flags) if getattr(report.flags, f.name)]
    return (
        f"turn-resolved reason={_safe(report.reason)} kind={report.failure_kind.value} "
        f"attempts={max(0, int(report.attempts))} flags_on={','.join(on) or 'none'}"
    )


def health_fields(report: TurnResolutionReport) -> dict[str, object]:
    """Аддитивные поля `/health`: `resilience_flags` и последнее решение."""
    return {
        "resilience_flags": flags_snapshot_dict(report.flags),
        "last_turn_resolved": format_turn_resolved(report),
    }
