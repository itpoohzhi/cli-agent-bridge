"""Связка классификатора passthrough с fencing и штрафами маршрута.

Модуль не инициирует retry/fallback. LeaseFenced остаётся терминальной ошибкой
вызывающего слоя; подтверждение HTTP 200 само по себе не закрывает штраф.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from core.route_penalty_state import LeaseFenced as LeaseFenced
from core.route_penalty_state import RoutePenaltyState, State
from core.stream_outcome import OutcomeKind, StreamOutcome, StreamOutcomeClassifier


class OutcomeLease(Protocol):
    """Проверка владения перед каждым внешним эффектом."""

    def check_current(self) -> None:
        """При потере владения выбрасывает LeaseFenced."""
        ...


class OutcomeEffects(Protocol):
    """Упорядоченные эффекты без неявных повторов или fallback."""

    def fsm(self, outcome: StreamOutcome) -> None:
        """Применяет исход к автомату."""
        ...

    def penalty(self, outcome: StreamOutcome) -> None:
        """Обновляет штрафные счётчики по классифицированному исходу."""
        ...

    def tool_result(self, outcome: StreamOutcome) -> None:
        """Фиксирует результат инструментов."""
        ...

    def sse_finalization(self, outcome: StreamOutcome) -> None:
        """Завершает ответ, если владение ещё действительно."""
        ...


def commit_outcome(
    lease: OutcomeLease, outcome: StreamOutcome, effects: OutcomeEffects
) -> StreamOutcome:
    """Выполняет эффекты до первого fencing/сбоя без компенсации и повторов.

    Каждый эффект получает исход, а не HTTP-статус. Эффекты обязаны сохранять
    fencing при собственной записи; уже выполненные эффекты не откатываются.
    """
    for effect in (
        effects.fsm,
        effects.penalty,
        effects.tool_result,
        effects.sse_finalization,
    ):
        lease.check_current()
        effect(outcome)
    return outcome


@dataclass(frozen=True, slots=True)
class PenaltyTarget:
    """Ребро, актуальная проба и переданный вызывающим кодом cooldown."""

    store: RoutePenaltyState
    edge: str
    lease: State
    cooldown_s: float


def finish_outcome(
    classifier: StreamOutcomeClassifier,
    target: PenaltyTarget,
    client_aborted: bool = False,
) -> StreamOutcome:
    """Фиксирует EOF/отмену и один атомарно fenced переход хранилища.

    Только OK закрывает штраф. Отмена освобождает lease без нового штрафа.
    Отказ долговечной записи не выдаётся за успешный commit.
    """
    outcome = classifier.finish(client_aborted=client_aborted)
    if outcome.kind is OutcomeKind.CLIENT_ABORT:
        state = target.store.abort(
            target.edge, target.lease.lease_epoch, target.lease.lease_token
        )
    else:
        cooldown = None if outcome.kind is OutcomeKind.OK else target.cooldown_s
        state = target.store.finish(target.edge, target.lease, cooldown)
    if state is None:
        raise OSError("Не удалось сохранить исход passthrough")
    return outcome
