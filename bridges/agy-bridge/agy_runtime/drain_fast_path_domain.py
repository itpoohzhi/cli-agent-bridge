"""Чистый Zero-I/O домен быстрого выхода из дрена (AD-001, волна W0-A).

Предикат ``decide_fast_exit`` принимает только иммутабельный снимок фактов
``DrainFacts`` и возвращает детерминированное решение ``DrainFastExitDecision``
без какого-либо I/O, чтения окружения и обращения к часам (M-MOD-I3).
Все дефолты ``DrainFacts`` fail-closed: неизвестное состояние никогда
не разрешает быстрый выход ``fast_clean``.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["DrainFacts", "DrainFastExitDecision", "decide_fast_exit"]


@dataclass(frozen=True, slots=True)
class DrainFacts:
    """Снимок фактов дрена; каждый дефолт fail-closed (выход запрещён)."""

    flag_enabled: bool = False
    authoritative_read_done: bool = False
    clean_rc: bool = False
    pending_steps: int = 1
    buffered_events: int = 1
    has_tool_trace: bool = True
    has_progressive_chunks: bool = True
    failed: bool = True
    interrupted: bool = True
    stopped: bool = False


@dataclass(frozen=True, slots=True)
class DrainFastExitDecision:
    """Решение о быстром выходе: флаг и явная причина отказа/успеха."""

    should_fast_exit: bool
    reason: str


def decide_fast_exit(facts: DrainFacts) -> DrainFastExitDecision:
    """Разрешить ``fast_clean`` только при полном наборе чистых фактов.

    Порядок проверок детерминирован: первая нарушенная предпосылка даёт
    причину отказа. Отрицательные счётчики нечистые (``!= 0`` -> отказ).
    Предикат не зависит от ``end_marker``: поля нет в контракте фактов.
    """
    checks: tuple[tuple[bool, str], ...] = (
        (facts.flag_enabled is True, "flag_disabled"),
        (facts.authoritative_read_done is True, "no_authoritative_read"),
        (facts.stopped is False, "stopped"),
        (facts.clean_rc is True, "nonzero_rc"),
        (facts.pending_steps == 0, "pending_steps"),
        (facts.buffered_events == 0, "buffered_events"),
        (facts.has_tool_trace is False, "tool_trace"),
        (facts.has_progressive_chunks is False, "progressive_chunks"),
        (facts.failed is False, "failed"),
        (facts.interrupted is False, "interrupted"),
    )
    for ok, reason in checks:
        if not ok:
            return DrainFastExitDecision(should_fast_exit=False, reason=reason)
    return DrainFastExitDecision(should_fast_exit=True, reason="fast_clean")
