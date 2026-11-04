"""Domain values and deadline accounting, independent of transports."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class ErrorClassification(Enum):
    TRANSIENT = "transient"
    FATAL = "fatal"

    @classmethod
    def from_status_code(cls, status_code: int | None) -> ErrorClassification:
        """A missing HTTP status represents a network failure."""
        if status_code is None or status_code in (429, 500, 502, 503, 504):
            return cls.TRANSIENT
        return cls.FATAL


class ZenError(Exception):
    """A transport-independent error with an explicit fallback policy."""

    message: str
    classification: ErrorClassification
    status_code: int
    retryable: bool

    def __init__(
        self,
        message: str,
        classification: ErrorClassification,
        status_code: int = 500,
        retryable: bool = True,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.classification = classification
        self.status_code = status_code
        self.retryable = retryable

    @classmethod
    def from_status_code(
        cls,
        message: str,
        status_code: int | None = None,
    ) -> ZenError:
        """Translate an HTTP status or network failure into a domain error."""
        classification = ErrorClassification.from_status_code(status_code)
        return cls(
            message=message,
            classification=classification,
            status_code=500 if status_code is None else status_code,
            retryable=classification is ErrorClassification.TRANSIENT,
        )


@dataclass
class StreamChunk:
    content: str = ""
    reasoning_content: str = ""
    finish_reason: str | None = None
    is_raw: bool = False
    index: int = 0


@dataclass
class RequestEnvelope:
    messages: list[dict[str, Any]]
    model: str
    stream: bool = True
    timeout_s: float = 60.0
    extra_params: dict[str, Any] | None = None


@dataclass
class DeadlineBudget:
    """A shared time allowance measured by an injectable monotonic clock."""

    timeout_s: float
    clock: Callable[[], float] = time.monotonic
    start_time: float = field(init=False)

    def __post_init__(self) -> None:
        self.start_time = self.clock()

    def remaining_s(self) -> float:
        return max(0.0, self.timeout_s - (self.clock() - self.start_time))

    def is_expired(self) -> bool:
        return self.remaining_s() <= 0.0

    def create_child(
        self,
        child_timeout_s: float | None = None,
    ) -> DeadlineBudget:
        remaining = self.remaining_s()
        timeout = (
            remaining
            if child_timeout_s is None
            else min(child_timeout_s, remaining)
        )
        child = DeadlineBudget(timeout_s=timeout, clock=self.clock)
        # Account for time between sampling the parent and starting the child.
        child.timeout_s = min(
            child.timeout_s,
            max(0.0, self.start_time + self.timeout_s - child.start_time),
        )
        return child
