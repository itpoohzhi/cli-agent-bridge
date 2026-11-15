"""Фазы POST и один владелец бюджета/lease без вложенных повторов."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from core.route_health_policy import (
    AttemptDecision, RetryBudgetConfig, RetryReason, compute_attempt_decision,
)

DEFAULT_ROUTE_FAILOVER_STATUSES = frozenset({401, 429, 503})


class AttemptPhase(str, Enum):
    """Монотонные фазы: начало SENDING уже означает возможное исполнение."""

    ELIGIBLE = "ELIGIBLE"
    CONNECTING = "CONNECTING"
    SENDING = "SENDING"
    RESPONSE_HEADERS = "RESPONSE_HEADERS"
    COMMITTED = "COMMITTED"
    TERMINAL = "TERMINAL"


@dataclass(frozen=True, slots=True)
class AttemptState:
    """Накопленные факты попытки; commit и начало write необратимы."""

    phase: AttemptPhase = AttemptPhase.ELIGIBLE
    body_sent: bool = False
    committed: bool = False
    status_code: int = 0


def transition(state: AttemptState, phase: AttemptPhase, status_code: int = 0) -> AttemptState:
    """Чистый переход, не разрешающий возврат в безопасную pre-send фазу."""
    order = tuple(AttemptPhase)
    current, target = order.index(state.phase), order.index(phase)
    if target != current + 1 and phase != AttemptPhase.TERMINAL:
        raise ValueError("attempt_phase_transition_invalid")
    return AttemptState(
        phase, state.body_sent or phase == AttemptPhase.SENDING,
        state.committed or phase == AttemptPhase.COMMITTED,
        status_code or state.status_code,
    )


def _replay_safe(outcome: AttemptState | Mapping[str, object], statuses: Iterable[int]) -> bool:
    if isinstance(outcome, AttemptState):
        phase, sent, committed, status = (
            outcome.phase, outcome.body_sent, outcome.committed, outcome.status_code,
        )
    else:
        phase, sent, committed, status = (
            outcome.get("phase"), outcome.get("body_sent"),
            outcome.get("committed", True), outcome.get("status_code"),
        )
    if committed is not False or type(status) is not int or type(sent) is not bool:
        return False
    if phase == AttemptPhase.CONNECTING:
        return sent is False and status == 0
    if phase == AttemptPhase.RESPONSE_HEADERS:
        return status in DEFAULT_ROUTE_FAILOVER_STATUSES and status in statuses
    return False


def decide_attempt(
    config: RetryBudgetConfig,
    attempt_index: int,
    elapsed_s: float,
    outcome: AttemptState | Mapping[str, object] | None,
    allowed_statuses: Iterable[int] = DEFAULT_ROUTE_FAILOVER_STATUSES,
) -> AttemptDecision:
    """Сначала общий PR17 budget, затем отдельное доказательство no-replay."""
    decision = compute_attempt_decision(config, attempt_index, elapsed_s)
    if not decision.allow_retry or outcome is None:
        return decision
    if _replay_safe(outcome, allowed_statuses):
        return decision
    return AttemptDecision(False, 0.0, RetryReason.NON_RETRYABLE_CATEGORY)


class RouteRefusal(RuntimeError):
    """Явный HTTP-отказ до commit; произвольный retryable payload не подходит."""

    def __init__(
        self, status_code: int, response_headers: tuple[tuple[str, str], ...] = (),
        response_body: bytes = b"",
    ) -> None:
        super().__init__("route_refused")
        self.status_code = status_code
        self.response_headers = response_headers
        self.response_body = response_body


class RouteUnavailable(RuntimeError):
    """Нет допущенной попытки или исчерпан исходный бюджет."""


class AttemptCancelled(RuntimeError):
    """Клиент ушёл; это discard, а не отказ origin."""


class AttemptLease(Protocol):
    """Единственный владелец record/release; close обязан быть ограниченным."""

    def finish(self, state: AttemptState, error: BaseException | None) -> None: ...

    def close(self) -> None: ...


class AttemptPorts(Protocol):
    """Транспорт и существующий resilience/token budget остаются снаружи."""

    def ready(self, backend: str) -> bool: ...

    def acquire(self, backend: str, remaining_deadline_s: float) -> AttemptLease | None: ...

    def execute(self, backend: str, attempt: RouteAttempt) -> object: ...

    def retry_token(self) -> bool:
        """Неблокирующий debit общего process-wide retry budget."""
        ...

    def cancelled(self) -> bool: ...


class RouteAttempt:
    """Контекст одной физической попытки; execute отмечает фазы до I/O.

    budget_s/deadline_s применяются к connect/send, но не убивают активный
    ответ. Поток использует существующее sliding activity window адаптера.
    Любые local presend/nonstream/capacity retries внутри execute запрещены.
    """

    def __init__(self, budget_s: float, deadline_s: float, clock: Callable[[], float]) -> None:
        self.budget_s = budget_s
        self.deadline_s = deadline_s
        self._state = AttemptState()
        self.local_retries_enabled = False
        self._clock = clock

    def advance(self, phase: AttemptPhase, status_code: int = 0) -> None:
        self._state = transition(self._state, phase, status_code)

    @property
    def state(self) -> AttemptState:
        return self._state

    def remaining_s(self) -> float:
        """Порт перепроверяет остаток перед connect/send и после ожиданий."""
        return max(0.0, self.deadline_s - self._clock())

__all__ = ('AttemptPhase', 'AttemptState', 'transition', '_replay_safe', 'decide_attempt', 'RouteRefusal', 'RouteUnavailable', 'AttemptCancelled', 'AttemptLease', 'AttemptPorts', 'RouteAttempt')
