"""Per-turn pure take-last accumulator for canonical TurnUsage."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Final

from core.turn_usage import TurnUsage, UsageUpdate, normalize_usage_update

MAX_REJECTION_LOGS_PER_TURN: Final[int] = 4

_LOGGER = logging.getLogger(__name__)


def _default_log(message: str) -> None:
    _LOGGER.warning("%s", message)


class UsageAccumulator:
    """Per-turn take-last usage accumulator with bounded diagnostic logging."""

    def __init__(self, *, log_fn: Callable[[str], None] | None = None) -> None:
        self._current: TurnUsage | None = None
        self._log_count: int = 0
        self._log_fn: Callable[[str], None] = log_fn or _default_log

    @property
    def current(self) -> TurnUsage | None:
        """Latest valid TurnUsage observed in this turn, or None."""
        return self._current

    @property
    def rejection_log_count(self) -> int:
        """Number of diagnostic rejection/advisory messages emitted this turn."""
        return self._log_count

    def _emit_bounded(self, message: str) -> None:
        if self._log_count < MAX_REJECTION_LOGS_PER_TURN:
            self._log_count += 1
            self._log_fn(message)

    def record_rejection(self, source: str, reason: str) -> None:
        """Log a rejected usage frame within the per-turn log budget."""
        safe_src = source or "unknown"
        self._emit_bounded(f"usage_update_rejected source={safe_src} reason={reason}")

    def observe(self, update: UsageUpdate | None) -> TurnUsage | None:
        """Observe one UsageUpdate; valid TURN_SNAPSHOT replaces current wholesale."""
        if update is None:
            return self._current
        result = normalize_usage_update(update)
        if result.usage is None:
            self.record_rejection(update.source, result.reason or "invalid")
            return self._current
        if result.advisory is not None:
            safe_src = update.source or "unknown"
            self._emit_bounded(
                f"usage_update_advisory source={safe_src} reason={result.advisory}"
            )
        self._current = result.usage
        return self._current

    def observe_turn_usage(self, usage: TurnUsage | None) -> TurnUsage | None:
        """Replace current with an already-validated TurnUsage (e.g. proxy wire)."""
        if usage is not None:
            self._current = usage
        return self._current
