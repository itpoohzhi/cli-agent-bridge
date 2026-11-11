"""Чистая классификация generic-сбоя upstream до отправки ответа клиенту."""

from __future__ import annotations

import enum as _enum
import math as _math

__all__ = ("PreCommitFailureClass", "classify_precommit_generic_failure")


class PreCommitFailureClass(_enum.Enum):
    """Двухзначный результат классификации generic PRE-COMMIT сбоя."""

    TIMEOUT = "timeout"
    UPSTREAM_UNAVAILABLE = "upstream_unavailable"


def classify_precommit_generic_failure(
    *,
    now_s: float | None,
    current_deadline_s: float | None,
    cap_deadline_s: float | None,
) -> PreCommitFailureClass:
    """Классифицирует общий сбой до фиксации ответа.

    Некорректное или неполное свидетельство безопасно трактуется как
    недоступность вышестоящего сервиса.
    """
    evidence = (now_s, current_deadline_s, cap_deadline_s)
    if not all(type(value) is float and _math.isfinite(value) for value in evidence):
        return PreCommitFailureClass.UPSTREAM_UNAVAILABLE
    assert isinstance(now_s, float)
    assert isinstance(current_deadline_s, float)
    assert isinstance(cap_deadline_s, float)
    effective_deadline_s = min(current_deadline_s, cap_deadline_s)
    if now_s >= effective_deadline_s:
        return PreCommitFailureClass.TIMEOUT
    return PreCommitFailureClass.UPSTREAM_UNAVAILABLE
