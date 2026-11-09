"""Чистая классификация причин сбоя для карантина моделей."""

from enum import Enum, auto
import re


class FailureKind(Enum):
    """Категории сбоев, влияющие на решение о штрафе модели."""

    MODEL_START_FAILURE = auto()
    INFRASTRUCTURE_FAILURE = auto()
    CLIENT_GONE = auto()
    INTENTIONAL_SHUTDOWN = auto()
    AUTH_FAILURE = auto()


INFRASTRUCTURE_TOKENS = (
    "http_502",
    "http_504",
    "connection refused",
    "connectionrefused",
    "connect_error",
    "network_error",
    "broken pipe",
    "bad gateway",
    "gateway timeout",
    "connection reset",
    "connectionreset",
    "econnreset",
)

CLIENT_GONE_TOKENS = (
    "client_gone",
    "client_gone_502",
    "client disconnected",
    "client_disconnected",
)
SHUTDOWN_TOKENS = (
    "sigterm drain",
    "drain_timeout",
    "graceful_shutdown",
)
AUTH_TOKENS = ("http_401", "unauthenticated", "unauthorized")


def _contains_token(value: str, tokens: tuple[str, ...]) -> bool:
    """Проверить наличие хотя бы одного маркера в нормализованной строке."""
    return any(
        re.search(r"\b" + re.escape(token) + r"\b", value) is not None
        for token in tokens
    )


def classify_failure(
    error_reason: str | None, strict_classify: bool = False
) -> FailureKind:
    """Классифицировать причину сбоя без побочных эффектов.

    В совместимом режиме только инфраструктурные ошибки исключаются из
    штрафов. Строгий режим дополнительно отделяет уход клиента, штатное
    завершение и ошибки авторизации.
    """
    if not error_reason:
        return FailureKind.MODEL_START_FAILURE
    lower = str(error_reason).strip().lower()
    if any(token in lower for token in INFRASTRUCTURE_TOKENS):
        return FailureKind.INFRASTRUCTURE_FAILURE
    if not strict_classify:
        return FailureKind.MODEL_START_FAILURE
    if _contains_token(lower, CLIENT_GONE_TOKENS):
        return FailureKind.CLIENT_GONE
    if _contains_token(lower, SHUTDOWN_TOKENS):
        return FailureKind.INTENTIONAL_SHUTDOWN
    if _contains_token(lower, AUTH_TOKENS):
        return FailureKind.AUTH_FAILURE
    return FailureKind.MODEL_START_FAILURE


NON_PENALIZING_KINDS = frozenset(
    {
        FailureKind.INFRASTRUCTURE_FAILURE,
        FailureKind.CLIENT_GONE,
        FailureKind.INTENTIONAL_SHUTDOWN,
        FailureKind.AUTH_FAILURE,
    }
)


def is_penalizing_failure(kind: FailureKind) -> bool:
    """Вернуть True, если тип сбоя штрафует модель (fail-closed для новых типов)."""
    return kind not in NON_PENALIZING_KINDS
