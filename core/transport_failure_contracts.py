"""Контракты устойчивости хода к сетевым сбоям и промежуточным ошибкам functionCall (BND-001).

Только frozen-датаклассы, Enum и Protocol без логики и без I/O: общий словарь типов
для классификатора, политик повтора/удержания сессии/recovery, трекеров и отчёта.
Агент-агностично: ничто здесь не зависит от имени подключаемого CLI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable

DEFAULT_TRANSIENT_PATTERNS: tuple[str, ...] = (
    r"tls handshake timeout",
    r"unexpected eof",
    r":\s*eof\b",
    r"i/o timeout",
    r"connection refused",
    r"connection reset(?: by peer)?",
    r"context deadline exceeded",
)
DEFAULT_FATAL_PATTERNS: tuple[str, ...] = (
    r"\b(?:http|status|code)\s*[:=]?\s*(?:400|401|403)\b",
    r"\b(?:400|401|403)\s+(?:bad request|unauthorized|forbidden)\b",
    r"\bbad request\b",
    r"\bunauthorized\b",
    r"\bforbidden\b",
    r"invalid model",
    r"quota",
)


FLAG_ENV_BY_FIELD: tuple[tuple[str, str], ...] = (
    ("transport_failure_classifier", "BRIDGE_TRANSPORT_FAILURE_CLASSIFIER_ENABLED"),
    ("keepalive_only_preretry", "BRIDGE_KEEPALIVE_ONLY_PRERETRY_ENABLED"),
    ("retry_window_pause", "BRIDGE_RETRY_WINDOW_PAUSE_ENABLED"),
    ("hot_session_retain_on_transient", "BRIDGE_HOT_SESSION_RETAIN_ON_TRANSIENT_ENABLED"),
    ("toolcall_error_recovery", "BRIDGE_TOOLCALL_ERROR_RECOVERY_ENABLED"),
    ("vendor_retry_phrase_mask", "BRIDGE_VENDOR_RETRY_PHRASE_MASK_ENABLED"),
)


class FailureKind(Enum):
    """Класс транспортного сбоя: решение о повторе принимает политика, не классификатор."""

    NETWORK_TRANSIENT = "network_transient"
    FATAL = "fatal"
    UNCLASSIFIED = "unclassified"


@dataclass(frozen=True)
class TransportFailureConfig:
    """Конфигурируемые regex классификатора и предел длины анализируемого текста."""

    transient_patterns: tuple[str, ...] = DEFAULT_TRANSIENT_PATTERNS
    fatal_patterns: tuple[str, ...] = DEFAULT_FATAL_PATTERNS
    max_chars: int = 2000


@dataclass(frozen=True)
class FailureClassification:
    """Результат классификации: класс, причина и совпавший шаблон (для диагностики)."""

    kind: FailureKind
    reason: str
    matched: str = ""


@dataclass(frozen=True)
class DeliveryFacts:
    """Что уже доставлено клиенту; keepalive и пустая role-дельта — не доставка."""

    keepalive_count: int = 0
    content_bytes: int = 0
    reasoning_bytes: int = 0
    tool_calls: int = 0
    tool_events: int = 0

    @property
    def delivered(self) -> bool:
        """Клиенту ушло content/tool_calls/reasoning/tool_events."""
        return any((self.content_bytes, self.reasoning_bytes, self.tool_calls, self.tool_events))


@dataclass(frozen=True)
class RetryBudgetConfig:
    """Бюджет невидимого повтора (AD-003); значения — из конфигурации вызывающего."""

    max_retries: int = 1
    retry_total_budget_s: float = 1020.0
    client_timeout_s: float = 600.0
    pause_max_s: float = 15.0
    window_s: float = 60.0


@dataclass(frozen=True)
class RetryAttemptState:
    """Состояние цикла: завершено попыток, прошло секунд, длительность последней, фон сбоев."""

    attempt: int
    elapsed_s: float
    last_attempt_s: float
    recent_failures: int = 0
    jitter_unit: float = 0.0


@dataclass(frozen=True)
class RetryBudgetDecision:
    """Решение о повторе: разрешён ли, пауза перед ним и таймаут повторной попытки."""

    allowed: bool
    reason: str
    pause_s: float = 0.0
    retry_timeout_s: float = 0.0


@dataclass(frozen=True)
class HotSessionFacts:
    """Факты неудавшегося хода для решения об удержании горячей сессии."""

    kind: FailureKind
    turns: int
    conversation: str


@dataclass(frozen=True)
class HotSessionDecision:
    """Решение об удержании горячей сессии и причина."""

    retain: bool
    reason: str


@dataclass(frozen=True)
class ParsedToolCall:
    """Один строго разобранный вызов инструмента; пустой `call_id` — идентификатора нет."""

    call_id: str
    name: str
    arguments_json: str


@runtime_checkable
class ToolCallParser(Protocol):
    """Порт strict-parse: все `<tool_call>` шага без остатка либо `None` при любой ошибке."""

    def parse_all(self, text: str) -> tuple[ParsedToolCall, ...] | None: ...


@dataclass(frozen=True)
class StepRecord:
    """Шаг хода: служебная ошибка (`error`) или шаг планировщика (`planner`)."""

    index: int
    kind: str
    text: str
    complete: bool = True


@dataclass(frozen=True)
class TurnStepsSnapshot:
    """Неизменяемая проекция шагов хода для `evaluate_recovery`."""

    steps: tuple[StepRecord, ...] = ()
    recovery_attempted: bool = False


@dataclass(frozen=True)
class ToolCallRecoveryDecision:
    """Итог recovery: либо структурированные вызовы, либо REJECT с причиной (fail-closed)."""

    recovered: bool
    calls: tuple[ParsedToolCall, ...] = ()
    reason: str = ""


@dataclass(frozen=True)
class RecoveryFlagSnapshot:
    """Снимок шести независимых kill-switch флагов (default False)."""

    transport_failure_classifier: bool = False
    keepalive_only_preretry: bool = False
    retry_window_pause: bool = False
    hot_session_retain_on_transient: bool = False
    toolcall_error_recovery: bool = False
    vendor_retry_phrase_mask: bool = False


@dataclass(frozen=True)
class TurnResolutionReport:
    """Причина разрешения хода и снимок флагов для лога и `/health`."""

    reason: str
    flags: RecoveryFlagSnapshot = field(default_factory=RecoveryFlagSnapshot)
    attempts: int = 0
    failure_kind: FailureKind = FailureKind.UNCLASSIFIED
