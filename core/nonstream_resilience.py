"""Контракт повторов для внутренней агрегации non-stream ответа."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Protocol

_MAX_RETRIES_NAME = "BRIDGE_NONSTREAM_INCOMPLETE_RETRY_MAX"
_MAX_INFLIGHT_NAME = "BRIDGE_NONSTREAM_RETRY_MAX_INFLIGHT"
_DEFAULT_MAX_RETRIES = 1
_MIN_MAX_RETRIES = 0
_MAX_MAX_RETRIES = 1
_DEFAULT_MAX_INFLIGHT = 4
_MIN_MAX_INFLIGHT = 1
_MAX_MAX_INFLIGHT = 4


class _Environment(Protocol):
    def get(self, key: str, default: str = "") -> str: ...


def _retry_limit(raw: object) -> int:
    try:
        value = int(str(raw).strip())
    except ValueError:
        return _DEFAULT_MAX_RETRIES
    if _MIN_MAX_RETRIES <= value <= _MAX_MAX_RETRIES:
        return value
    return _DEFAULT_MAX_RETRIES


def _bulkhead_limit(raw: object) -> int:
    try:
        value = int(str(raw).strip())
    except ValueError:
        return _DEFAULT_MAX_INFLIGHT
    if _MIN_MAX_INFLIGHT <= value <= _MAX_MAX_INFLIGHT:
        return value
    return _DEFAULT_MAX_INFLIGHT


@dataclass(frozen=True)
class NonstreamRetryPolicy:
    """Ограничивает повторы незавершённого потока до первого токена."""

    max_retries: int = _DEFAULT_MAX_RETRIES

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_retries, bool)
            or not _MIN_MAX_RETRIES <= self.max_retries <= _MAX_MAX_RETRIES
        ):
            raise ValueError("max_retries должен быть равен 0 или 1")

    @classmethod
    def from_env(cls, environ: _Environment | None = None) -> NonstreamRetryPolicy:
        """Строит политику из переданного окружения или ``os.environ``."""
        source = os.environ if environ is None else environ
        return cls(max_retries=_retry_limit(source.get(_MAX_RETRIES_NAME, "")))


class NonstreamRetryBulkhead:
    """Ограничивает число одновременных повторов одного бэкенда."""

    def __init__(self, max_inflight: int = _DEFAULT_MAX_INFLIGHT) -> None:
        if (
            isinstance(max_inflight, bool)
            or not _MIN_MAX_INFLIGHT <= max_inflight <= _MAX_MAX_INFLIGHT
        ):
            raise ValueError("max_inflight должен быть в диапазоне от 1 до 4")
        self.max_inflight: int = max_inflight
        self._slots: threading.BoundedSemaphore = threading.BoundedSemaphore(
            value=max_inflight
        )

    @classmethod
    def from_env(cls, environ: _Environment | None = None) -> NonstreamRetryBulkhead:
        """Строит ограничитель из переданного окружения или ``os.environ``."""
        source = os.environ if environ is None else environ
        return cls(max_inflight=_bulkhead_limit(source.get(_MAX_INFLIGHT_NAME, "")))

    def try_acquire(self) -> bool:
        """Неблокирующе занимает слот повтора."""
        return self._slots.acquire(blocking=False)

    def release(self) -> None:
        """Освобождает ранее занятый слот."""
        self._slots.release()
