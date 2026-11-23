"""Attempt-scoped мост между SSE runner и циклом ожидания upstream."""

from __future__ import annotations

from typing import Any, final

from core.stream_activity_policy import ActivitySnapshot, SlidingActivityWindow

# pyright: reportAny=false, reportExplicitAny=false


@final
class ActivityRuntime:
    """Единый авторитетный дедлайн одной попытки для producer и consumer."""

    def __init__(self, window: SlidingActivityWindow) -> None:
        self.window = window

    def current_deadline(self) -> float:
        return self.window.current_deadline()

    def check_expired(self, now: float) -> ActivitySnapshot:
        return self.window.check_expired(now)

    def record_signal(self, kind: str, payload: object, now: float) -> bool:
        return self.window.record_signal(kind, payload, now)

    def mark_completed(
        self, now: float, *, succeeded: bool = False
    ) -> ActivitySnapshot:
        return self.window.mark_completed(now, succeeded=succeeded)


def execute_scope(
    handler: Any, run: Any, policy: Any, deadline: float, last_wd_check: float
) -> tuple[Any, Any, float, float]:
    """Передать runtime циклу и выключить только конкурирующие legacy-таймеры."""
    runtime = getattr(handler, "_activity_runtime", None)
    if runtime is not None:
        run.got_event = True
        return None, runtime, float("inf"), float("inf")
    return policy, runtime, deadline, last_wd_check


def defer_done(handler: Any) -> Any:
    """Передать runner исключительное право записи до конца попытки."""
    original = getattr(handler, "_log_done", None)
    handler._defer_done_log = True
    handler._log_done = lambda *_args: None
    return original


def clear_handler(handler: Any, done_log: Any) -> None:
    """Восстановить logger и сбросить runtime на границе keep-alive запроса."""
    handler._log_done = done_log
    handler._defer_done_log = False
    handler._attempt_budget_s = None
    handler._activity_runtime = None
