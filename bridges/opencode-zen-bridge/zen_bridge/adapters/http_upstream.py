from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Iterator

from zen_bridge.domain.models import (
    DeadlineBudget,
    ErrorClassification,
    RequestEnvelope,
    StreamChunk,
    ZenError,
)


class CircuitBreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 3,
        reset_timeout_s: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if failure_threshold < 1 or reset_timeout_s < 0:
            raise ValueError("Invalid circuit breaker configuration")
        self._failure_threshold = failure_threshold
        self._reset_timeout_s = reset_timeout_s
        self._clock = clock
        self._failures = 0
        self._opened_at = 0.0
        self._state = CircuitBreakerState.CLOSED

    @property
    def state(self) -> CircuitBreakerState:
        if self._state is CircuitBreakerState.OPEN:
            elapsed = self._clock() - self._opened_at
            if elapsed >= self._reset_timeout_s:
                self._state = CircuitBreakerState.HALF_OPEN
        return self._state

    def is_available(self) -> bool:
        return self.state is not CircuitBreakerState.OPEN

    def record_success(self) -> None:
        self._failures = 0
        self._state = CircuitBreakerState.CLOSED

    def record_failure(self) -> None:
        self._failures += 1
        if (
            self._state is CircuitBreakerState.HALF_OPEN
            or self._failures >= self._failure_threshold
        ):
            self._opened_at = self._clock()
            self._state = CircuitBreakerState.OPEN


@dataclass(frozen=True)
class UpstreamLimits:
    max_retries: int = 1
    backoff_base_s: float = 0.1
    read_timeout_cap_s: float = 60.0

    def __post_init__(self) -> None:
        if self.max_retries < 0 or self.backoff_base_s < 0:
            raise ValueError("Retry limits must be nonnegative")
        if self.read_timeout_cap_s <= 0:
            raise ValueError("Read timeout cap must be positive")


class ZenHttpUpstream:
    """HTTP adapter; base_url is the complete streaming endpoint URL.

    RequestEnvelope supplies a JSON-serializable payload and optional headers.
    Each decoded SSE data object becomes StreamChunk(data=object).
    """

    def __init__(
        self,
        base_url: str,
        circuit_breaker: CircuitBreaker | None = None,
        limits: UpstreamLimits | None = None,
    ) -> None:
        self.base_url = base_url
        self.circuit_breaker = (
            circuit_breaker if circuit_breaker is not None else CircuitBreaker()
        )
        self.limits = limits if limits is not None else UpstreamLimits()

    def execute_stream(
        self, envelope: RequestEnvelope, budget: DeadlineBudget
    ) -> Iterator[StreamChunk]:
        emitted = False
        for attempt in range(self.limits.max_retries + 1):
            if not self.circuit_breaker.is_available():
                raise self._transient("Upstream circuit breaker is open")
            try:
                for chunk in self._read_stream(envelope, budget):
                    emitted = True
                    yield chunk
            except (urllib.error.URLError, OSError, ZenError) as exc:
                error = self._classify_error(exc)
                if error.classification is not ErrorClassification.TRANSIENT:
                    raise error from exc
                self.circuit_breaker.record_failure()
                if emitted or attempt >= self.limits.max_retries:
                    raise error from exc
                if not self._wait_for_retry(attempt, budget):
                    raise error from exc
            else:
                self.circuit_breaker.record_success()
                return

    def _read_stream(
        self, envelope: RequestEnvelope, budget: DeadlineBudget
    ) -> Iterator[StreamChunk]:
        request = self._make_request(envelope)
        timeout = min(budget.remaining_s(), self.limits.read_timeout_cap_s)
        if timeout <= 0:
            raise TimeoutError("Upstream deadline exhausted")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            for raw_line in response:
                if budget.remaining_s() <= 0:
                    raise TimeoutError("Upstream deadline exhausted")
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    return
                if data:
                    yield self._decode_chunk(data)

    def _make_request(self, envelope: RequestEnvelope) -> urllib.request.Request:
        headers = {
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
        }
        headers.update(getattr(envelope, "headers", None) or {})
        body = json.dumps(envelope.payload).encode("utf-8")
        return urllib.request.Request(
            self.base_url, data=body, headers=headers, method="POST"
        )

    def _decode_chunk(self, data: str) -> StreamChunk:
        try:
            payload = json.loads(data)
        except (ValueError, UnicodeError) as exc:
            raise ZenError(
                message="Invalid upstream SSE JSON",
                classification=ErrorClassification.FATAL,
                retryable=False,
            ) from exc
        if isinstance(payload, dict) and payload.get("error"):
            raise self._transient("Upstream reported a streaming error")
        return StreamChunk(data=payload)

    def _classify_error(self, exc: Exception) -> ZenError:
        if isinstance(exc, ZenError):
            return exc
        if isinstance(exc, urllib.error.HTTPError):
            status = exc.code
            exc.close()
            if 400 <= status < 500 and status not in (408, 429):
                return ZenError(
                    message=f"Upstream rejected request: HTTP {status}",
                    classification=ErrorClassification.FATAL,
                    retryable=False,
                )
            return self._transient(f"Upstream unavailable: HTTP {status}")
        return self._transient(f"Upstream transport failure: {exc}")

    def _wait_for_retry(self, attempt: int, budget: DeadlineBudget) -> bool:
        if not self.circuit_breaker.is_available():
            return False
        delay = self.limits.backoff_base_s * (2**attempt)
        if budget.remaining_s() <= delay:
            return False
        if delay:
            time.sleep(delay)
        return budget.remaining_s() > 0

    @staticmethod
    def _transient(message: str) -> ZenError:
        return ZenError(
            message=message,
            classification=ErrorClassification.TRANSIENT,
            retryable=True,
        )
