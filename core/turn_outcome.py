"""Классификация turn-ответов с общей fenced фиксацией исхода.

Нестриминговый ответ передаётся в нормализованном OpenAI-формате. Потоковый
путь использует finish_outcome после feed каждого чанка. Порядок эффектов,
CLIENT_ABORT и терминальный LeaseFenced совпадают с passthrough; retry и
fallback этот слой не запускает. Сам модуль не включает новые runtime-пути.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.passthrough_outcome import (
    OutcomeEffects as OutcomeEffects,
    OutcomeLease as OutcomeLease,
    PenaltyTarget as PenaltyTarget,
    commit_outcome as commit_outcome,
    finish_outcome as finish_outcome,
)
from core.route_penalty_state import LeaseFenced as LeaseFenced
from core.stream_outcome import StreamOutcome, StreamOutcomeClassifier


@dataclass(frozen=True, slots=True)
class TurnResponse:
    """Завершённое тело и метаданные ответа, а не признак успеха по HTTP 200."""

    body: bytes
    status: int = 200
    content_type: str = "application/json"


def finish_turn(
    response: TurnResponse,
    target: PenaltyTarget,
    client_aborted: bool = False,
) -> StreamOutcome:
    """Классифицирует turn и фиксирует результат только с текущим lease.

    Только OK закрывает штраф; ошибки открывают его на cooldown из target.
    Отмена освобождает пробу без нового штрафа. Ошибка записи или fencing
    пробрасывается вызывающему слою без повторов и последующих эффектов.
    """
    classifier = StreamOutcomeClassifier(response.status, response.content_type)
    classifier.feed(response.body)
    return finish_outcome(classifier, target, client_aborted=client_aborted)
