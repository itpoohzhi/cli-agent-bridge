from __future__ import annotations

from typing import Any, Iterator

from zen_bridge.adapters.cli_fallback import ZenCliFallback
from zen_bridge.adapters.http_upstream import ZenHttpUpstream
from zen_bridge.domain.models import (
    DeadlineBudget,
    ErrorClassification,
    RequestEnvelope,
    StreamChunk,
    ZenError,
)
from zen_bridge.domain.reasoning_parser import ReasoningFSM


def refund_limiter_token(
    limiter: Any, was_process_spawned: bool = False
) -> None:
    if was_process_spawned is not False:
        return
    refund = getattr(limiter, "refund", None)
    if callable(refund):
        refund()


class ZenChatService:
    """Coordinate transports without replaying an already-visible stream.

    Chunks are forwarded unchanged; optional ReasoningFSM enrichment can be
    applied by the caller to the resulting single coordinated stream.
    """

    reasoning_fsm: ReasoningFSM | None = None

    def __init__(
        self,
        http_upstream: ZenHttpUpstream,
        cli_fallback: ZenCliFallback,
        spawn_limiter: Any = None,
    ) -> None:
        self.http_upstream = http_upstream
        self.cli_fallback = cli_fallback
        self.spawn_limiter = spawn_limiter

    def coordinate_stream_fallback(
        self,
        envelope: RequestEnvelope,
        budget: DeadlineBudget | None = None,
    ) -> Iterator[StreamChunk]:
        if budget is None:
            budget = DeadlineBudget(timeout_s=envelope.timeout_s)
        try:
            yield from self._http_stream(envelope, budget)
            return
        except _StreamStartedError as exc:
            raise exc.error from None
        except ZenError as exc:
            if exc.classification != ErrorClassification.TRANSIENT:
                raise
            refund_limiter_token(
                self.spawn_limiter, was_process_spawned=False
            )
            if budget.remaining_s() <= 0:
                raise self._deadline_error() from exc
        yield from self.cli_fallback.execute_stream(envelope, budget)

    def _http_stream(
        self, envelope: RequestEnvelope, budget: DeadlineBudget
    ) -> Iterator[StreamChunk]:
        emitted = False
        try:
            for chunk in self.http_upstream.execute_stream(envelope, budget):
                emitted = True
                yield chunk
        except ZenError as exc:
            if emitted:
                raise _StreamStartedError(exc) from exc
            raise

    @staticmethod
    def _deadline_error() -> ZenError:
        return ZenError(
            classification=ErrorClassification.TRANSIENT,
            status_code=504,
            message=(
                "Gateway Timeout: deadline budget exhausted "
                "before CLI fallback"
            ),
        )


class _StreamStartedError(Exception):
    """Keep partial HTTP failures outside the fallback decision."""

    def __init__(self, error: ZenError) -> None:
        super().__init__(str(error))
        self.error = error
