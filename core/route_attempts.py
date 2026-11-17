"""Фазы POST и один владелец бюджета/lease без вложенных повторов."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from core.route_health_policy import (
    AttemptDecision, RetryBudgetConfig, RetryReason, compute_attempt_decision,
    validate_retry_config,
)
from core.routing_contract import PreSendTransientError

DEFAULT_ROUTE_FAILOVER_STATUSES = frozenset({401, 429, 503})
# Статусы, которые провайдер вообще вправе объявить отказом слота (per-route opt-in).
ALLOWED_FAILOVER_STATUSES = frozenset({401, 402, 403, 429, 503})
ENV_POOL_EXHAUSTED_RETRY_AFTER_S = "BRIDGE_POOL_EXHAUSTED_RETRY_AFTER_S"
DEFAULT_POOL_EXHAUSTED_RETRY_AFTER_S = 60
# Маркеры исчерпания слота не зашиты в ядро: провайдер объявляет их декларативно
# (`failover.message_markers` манифеста -> `failover_message_markers` бэкенда).
# Безопасные причины для сводной ошибки: без quota-лексики и типов, маскируемых клиентом.
_SAFE_REASONS = {
    401: "upstream rejected the slot key (HTTP 401)",
    402: "payment required by upstream (HTTP 402)",
    403: "slot not active: subscription required or access denied by upstream (HTTP 403)",
    429: "upstream limit reached for this slot (HTTP 429)",
    503: "upstream unavailable (HTTP 503)",
}


def parse_upstream_error(body: bytes) -> tuple[str, str]:
    """Извлекает `(error.type|code, error.message)` из JSON-тела отказа; мусор — пустые строки."""
    try:
        payload = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        return "", ""
    if not isinstance(payload, Mapping):
        return "", ""
    error = payload.get("error")
    node: Mapping[object, object] = error if isinstance(error, Mapping) else payload
    kind = node.get("type") or node.get("code") or ""
    message = node.get("message") or ""
    return (kind if isinstance(kind, str) else "", message if isinstance(message, str) else "")


def is_route_refusal_status(
    status: int,
    body: bytes = b"",
    *,
    extra_statuses: Iterable[int] = (),
    extra_error_types: Iterable[str] = (),
    message_markers: Iterable[str] = (),
) -> bool:
    """Отказ слота: глобальные статусы или per-route расширение по телу ошибки.

    Расширение действует только для статусов из `extra_statuses` конкретного
    маршрута. Если маршрут объявил `extra_error_types` и/или `message_markers`,
    отказом считается только совпадение типа ошибки или маркера в сообщении
    (без захардкоженных провайдерных эвристик ядра: 402 сам по себе и чужие
    маркеры ничего не форсируют), чтобы не-Go 403 (`internal_model_forbidden`)
    не повторялся другим ключом. Статус-only opt-in (ни типов, ни маркеров)
    считает сам статус из `extra_statuses` явным объявлением отказа слота.
    """
    if status in DEFAULT_ROUTE_FAILOVER_STATUSES:
        return True
    if status not in frozenset(extra_statuses) & ALLOWED_FAILOVER_STATUSES:
        return False
    types = frozenset(extra_error_types)
    markers = tuple(marker.lower() for marker in message_markers if marker)
    if not types and not markers:
        return True
    kind, message = parse_upstream_error(body)
    if kind and kind in types:
        return True
    lowered = message.lower()
    return any(marker in lowered for marker in markers)


def effective_failover_statuses(
    allowed_statuses: Iterable[int] = DEFAULT_ROUTE_FAILOVER_STATUSES,
    extra_statuses: Iterable[int] = (),
) -> frozenset[int]:
    """Итоговое множество replay-статусов: разрешённые вызывающим плюс opt-in провайдера.

    Пересечение с `ALLOWED_FAILOVER_STATUSES` сохраняет инвариант: статусы
    вроде 502, не доказывающие отсутствие исполнения, replay не разрешают.
    """
    return (frozenset(allowed_statuses) | frozenset(extra_statuses)) & ALLOWED_FAILOVER_STATUSES


@dataclass(frozen=True, slots=True)
class RouteFailover:
    """Единый per-route контракт failover одного бэкенда/маршрута.

    Вычисляется строго из конфига конкретного бэкенда и никогда не объединяется
    по модели: non-opt-in сосед по модели не наследует чужие статусы/маркеры.
    `pool`/`pool_label` задают принадлежность слота пулу сводной ошибки 429
    независимо от `quota_group` учёта квот.
    """

    statuses: frozenset[int] = frozenset()
    error_types: frozenset[str] = frozenset()
    message_markers: tuple[str, ...] = ()
    pool: str = ""
    pool_label: str = ""

    @property
    def opt_in(self) -> bool:
        return bool(self.statuses)

    @property
    def pool_key(self) -> str:
        return self.pool or self.pool_label

    @property
    def label(self) -> str:
        return self.pool_label or self.pool or "provider pool"

    def effective_statuses(
        self, allowed_statuses: Iterable[int] = DEFAULT_ROUTE_FAILOVER_STATUSES,
    ) -> frozenset[int]:
        return effective_failover_statuses(allowed_statuses, self.statuses)

    def matches(self, status: int, body: bytes = b"") -> bool:
        return is_route_refusal_status(
            status, body, extra_statuses=self.statuses,
            extra_error_types=self.error_types, message_markers=self.message_markers,
        )


def _str_values(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, (list, tuple, frozenset, set)):
        return ()
    return tuple(value for value in raw if isinstance(value, str) and value)


def failover_from_mapping(config: Mapping[str, object] | None) -> RouteFailover:
    """Читает per-backend `failover_*` из конфига бэкенда; мусор игнорируется."""
    if not isinstance(config, Mapping):
        return RouteFailover()
    raw_statuses = config.get("failover_statuses")
    statuses = frozenset(
        value for value in raw_statuses
        if type(value) is int and value in ALLOWED_FAILOVER_STATUSES
    ) if isinstance(raw_statuses, (list, tuple, frozenset, set)) else frozenset()
    pool = config.get("failover_pool")
    pool_label = config.get("failover_pool_label")
    return RouteFailover(
        statuses=statuses,
        error_types=frozenset(_str_values(config.get("failover_error_types"))),
        message_markers=tuple(
            marker.lower() for marker in _str_values(config.get("failover_message_markers"))
        ),
        pool=pool if isinstance(pool, str) else "",
        pool_label=pool_label if isinstance(pool_label, str) else "",
    )


def failover_config_from_mapping(
    config: Mapping[str, object] | None,
) -> tuple[frozenset[int], frozenset[str]]:
    """Совместимая пара `(statuses, error_types)` поверх `failover_from_mapping`."""
    failover = failover_from_mapping(config)
    return failover.statuses, failover.error_types


@dataclass(frozen=True, slots=True)
class PresendEvaluation:
    """Итог presend-классификации; `body=None` — тело не читалось (терминальный ответ)."""

    is_refusal: bool
    body: bytes | None = None


def evaluate_presend_candidate(
    status: int, read_body: Callable[[], bytes], failover: RouteFailover,
) -> PresendEvaluation:
    """Единый presend-классификатор: читает тело только у кандидата по статусу.

    Уже прочитанное тело возвращается вызывающему явно (`body`), а не вешается
    атрибутом на системный `HTTPResponse`; терминальные ответы не читаются.
    """
    if status not in failover.effective_statuses():
        return PresendEvaluation(False, None)
    body = read_body()
    return PresendEvaluation(failover.matches(status, body), body)


def _retry_after_s(headers: Sequence[tuple[str, str]]) -> int | None:
    for name, value in headers:
        if name.lower() == "retry-after":
            try:
                parsed = int(float(value.strip()))
            except ValueError:
                return None
            return parsed if parsed > 0 else None
    return None


def build_pool_exhausted_error(
    refusals: Sequence[tuple[str, "RouteRefusal"]],
    *,
    pool_label: str = "provider pool",
    environ: Mapping[str, str] | None = None,
) -> tuple[int, tuple[tuple[str, str], ...], bytes]:
    """Сводная терминальная ошибка пула: HTTP 429 `rate_limit_error` с причиной по каждому слоту.

    429 выбран потому, что клиент показывает его `error.message` дословно, а
    401/403/402 маскирует статичным текстом. Причины берутся из безопасной
    таблицы по статусу, а не из тела upstream: сырой текст может содержать
    лексику, переключающую клиентский классификатор в маскирующий код.
    """
    env = os.environ if environ is None else environ
    try:
        default_retry = int(env.get(ENV_POOL_EXHAUSTED_RETRY_AFTER_S, "") or DEFAULT_POOL_EXHAUSTED_RETRY_AFTER_S)
    except ValueError:
        default_retry = DEFAULT_POOL_EXHAUSTED_RETRY_AFTER_S
    retry_after = max(
        [default_retry] + [value for _, error in refusals
                           if (value := _retry_after_s(error.response_headers)) is not None]
    )
    parts = [
        f"[{slot}: {_SAFE_REASONS.get(error.status_code, f'upstream HTTP {error.status_code}')}]"
        for slot, error in refusals
    ]
    message = f"All {pool_label} slots exhausted: " + ", ".join(parts)
    body = json.dumps(
        {"error": {"type": "rate_limit_error", "message": message}}, ensure_ascii=False,
    ).encode("utf-8")
    headers = (
        ("Content-Type", "application/json"),
        ("Retry-After", str(retry_after)),
        ("Content-Length", str(len(body))),
    )
    return 429, headers, body


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
        return status in frozenset(statuses)
    return False


def decide_attempt(
    config: RetryBudgetConfig,
    attempt_index: int,
    elapsed_s: float,
    outcome: AttemptState | Mapping[str, object] | None,
    allowed_statuses: Iterable[int] = DEFAULT_ROUTE_FAILOVER_STATUSES,
    extra_statuses: Iterable[int] = (),
    failover: RouteFailover | None = None,
) -> AttemptDecision:
    """Сначала общий PR17 budget, затем отдельное доказательство no-replay.

    `failover` — контракт именно того маршрута, чей `outcome` оценивается;
    при заданном `failover` его статусы заменяют плоский `extra_statuses`.
    """
    decision = compute_attempt_decision(config, attempt_index, elapsed_s)
    if not decision.allow_retry or outcome is None:
        return decision
    extra = failover.statuses if failover is not None else extra_statuses
    if _replay_safe(outcome, effective_failover_statuses(allowed_statuses, extra)):
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


class RouteAttemptRunner:
    """Одноразовый request owner, без общего списка посещённых маршрутов."""

    def __init__(
        self, routes: Iterable[str], ports: AttemptPorts,
        config: RetryBudgetConfig, clock: Callable[[], float],
        allowed_statuses: Iterable[int] = DEFAULT_ROUTE_FAILOVER_STATUSES,
        extra_statuses: Iterable[int] = (),
        failover_by_backend: Mapping[str, RouteFailover] | None = None,
    ) -> None:
        self._routes = iter(routes)
        self._ports = ports
        self._config = validate_retry_config(config)
        self._clock = clock
        self._started_s = clock()
        self._visited: set[str] = set()
        self._attempts = 0
        self._used = False
        self._last_state: AttemptState | None = None
        self._last_error: BaseException | None = None
        self._allowed_statuses = tuple(allowed_statuses)
        # Плоский `extra_statuses` — только legacy-дефолт для бэкендов без записи
        # в `failover_by_backend`; per-route контракт имеет приоритет по бэкенду.
        self._statuses = effective_failover_statuses(allowed_statuses, extra_statuses)
        self._failover_by_backend = dict(failover_by_backend or {})
        self._active_statuses = self._statuses

    def _statuses_for(self, backend: str) -> frozenset[int]:
        failover = self._failover_by_backend.get(backend)
        if failover is None:
            return self._statuses
        return failover.effective_statuses(self._allowed_statuses)

    def _check_cancelled(self) -> None:
        if self._ports.cancelled():
            raise AttemptCancelled("client_gone")

    def _context(self) -> RouteAttempt:
        self._check_cancelled()
        now = self._clock()
        decision = decide_attempt(
            self._config, self._attempts, now - self._started_s, self._last_state,
            self._active_statuses,
        )
        if not decision.allow_retry:
            raise RouteUnavailable(decision.reason.value)
        return RouteAttempt(decision.attempt_budget_s, now + decision.attempt_budget_s, self._clock)

    def _execute(self, backend: str, lease: AttemptLease) -> tuple[bool, object]:
        attempt = RouteAttempt(0.0, self._started_s, self._clock)
        error: BaseException | None = None
        try:
            self._check_cancelled()
            if self._attempts and not self._ports.retry_token():
                raise RouteUnavailable("retry_tokens_exhausted")
            if not self._ports.ready(backend):
                error = RouteUnavailable("route_revoked")
                return False, None
            attempt = self._context()
            self._attempts += 1
            # Статусы переключаются только после оценки предыдущей попытки:
            # её исход судит контракт её собственного бэкенда, не следующего.
            self._active_statuses = self._statuses_for(backend)
            attempt.advance(AttemptPhase.CONNECTING)
            return True, self._ports.execute(backend, attempt)
        except BaseException as exc:
            error = exc
            self._last_state = attempt.state
            raise
        finally:
            self._release(lease, attempt, error)

    def _release(
        self, lease: AttemptLease, attempt: RouteAttempt, error: BaseException | None,
    ) -> None:
        # Ошибка cleanup не является разрешением повторить даже безопасный POST.
        state, last_state = attempt.state, self._last_state
        self._last_state = None
        attempt.advance(AttemptPhase.TERMINAL)
        try:
            lease.finish(state, error)
        finally:
            lease.close()
        self._last_state = last_state

    def _retryable_error(self, error: BaseException) -> bool:
        state = self._last_state
        if state is None:
            return False
        if isinstance(error, RouteRefusal):
            if state.phase != AttemptPhase.RESPONSE_HEADERS:
                return False
            if state.status_code != error.status_code:
                return False
        elif not isinstance(error, PreSendTransientError):
            return False
        elif state.phase != AttemptPhase.CONNECTING:
            return False
        return _replay_safe(state, self._active_statuses)

    def _route(self, backend: str) -> tuple[bool, object]:
        context = self._context()
        self._last_state = None
        if not self._ports.ready(backend):
            return False, None
        lease = self._ports.acquire(backend, context.remaining_s())
        if lease is None:
            return False, None
        return self._execute(backend, lease)

    def run(self) -> object:
        """Посещает backend один раз; только доказанный отказ допускает следующий."""
        if self._used:
            raise RuntimeError("attempt_runner_already_used")
        self._used = True
        try:
            return self._run_routes()
        except RouteUnavailable:
            if self._last_error is not None:
                raise self._last_error from None
            raise

    def _run_routes(self) -> object:
        for backend in self._routes:
            self._check_cancelled()
            if backend in self._visited:
                continue
            self._visited.add(backend)
            try:
                completed, result = self._route(backend)
            except (PreSendTransientError, RouteRefusal) as exc:
                if not self._retryable_error(exc):
                    raise
                self._last_error = exc
            else:
                if completed:
                    return result
        if self._last_error is not None:
            raise self._last_error
        raise RouteUnavailable("route_unavailable")
