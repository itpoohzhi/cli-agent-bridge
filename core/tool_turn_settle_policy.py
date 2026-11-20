"""Чистая FSM-политика завершения tool-turn с EOF-grace и защитой от plan_leak (D1)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

SettleAction = Literal[
    "continue",
    "wait_eof_grace",
    "wait_done",
    "clean_complete",
    "forced_stop",
    "stall_error",
]


@dataclass(frozen=True)
class ToolTurnSettleConfig:
    """Параметры окна завершения tool-turn без хардкода."""

    settle_timeout_s: float = 5.0
    stall_timeout_s: float = 30.0
    eof_grace_s: float = 1.5
    eof_grace_enabled: bool = True


@dataclass(frozen=True)
class ToolTurnSettleState:
    """Снимок состояния парсера tool-turn на момент проверки."""

    now: float
    has_error: bool
    has_open_tool_call: bool
    has_calls: bool
    last_open_chunk_ts: float
    last_chunk_ts: float
    calls_closed_ts: float
    proc_exited: bool = False
    result_received: bool = False


@dataclass(frozen=True)
class SettleDecision:
    """Результат вычисления политики завершения tool-turn."""

    action: SettleAction
    should_stop: bool
    tool_turn_stop: bool
    tool_turn_clean_eof: bool
    error_message: str = ""


_CONTINUE = SettleDecision("continue", False, False, False)
_WAIT_GRACE = SettleDecision("wait_eof_grace", False, False, False)
_WAIT_DONE = SettleDecision("wait_done", False, False, False)
_CLEAN_COMPLETE = SettleDecision("clean_complete", True, False, True)
_FORCED_STOP = SettleDecision("forced_stop", True, True, False)
_STALL_MSG = "Incomplete <tool_call> tag: stream stalled before closing tag"


def suppress_post_call_content(*, has_calls: bool, has_open_tool_call: bool) -> bool:
    """Подавляет пост-вызовный текст модели после закрытия <tool_call> (устраняет plan_leak)."""
    return all((has_calls, not has_open_tool_call))


def _evaluate_open_call(
    state: ToolTurnSettleState, config: ToolTurnSettleConfig
) -> SettleDecision:
    stalled = (state.now - state.last_open_chunk_ts) >= config.stall_timeout_s
    decision = _CONTINUE
    if stalled:
        decision = (
            _FORCED_STOP
            if state.has_calls
            else SettleDecision("stall_error", True, True, False, _STALL_MSG)
        )
    return decision


def _evaluate_closed_calls(
    state: ToolTurnSettleState, config: ToolTurnSettleConfig
) -> SettleDecision:
    anchor_ts = max(state.calls_closed_ts, state.last_chunk_ts)
    quiet_s = state.now - anchor_ts
    grace_s = config.eof_grace_s if config.eof_grace_enabled else 0.0
    total_wait = config.settle_timeout_s + max(0.0, grace_s)
    past_settle = quiet_s >= config.settle_timeout_s
    past_total = quiet_s >= total_wait
    decision = _CONTINUE
    if state.proc_exited:
        decision = _WAIT_DONE
    elif past_total:
        decision = _CLEAN_COMPLETE if state.result_received else _FORCED_STOP
    elif state.result_received:
        decision = _WAIT_DONE
    elif past_settle:
        decision = _WAIT_GRACE
    return decision


def evaluate_tool_turn_settle(
    state: ToolTurnSettleState, config: ToolTurnSettleConfig
) -> SettleDecision:
    """Вычисляет детерминированное решение завершения tool-turn без побочных эффектов."""
    decision = _CONTINUE
    if state.has_error:
        decision = _FORCED_STOP
    elif state.has_open_tool_call:
        decision = _evaluate_open_call(state, config)
    elif state.has_calls:
        decision = _evaluate_closed_calls(state, config)
    return decision


def resolve_tool_turn_stop(
    turn_complete: Callable[[], bool] | None,
    *,
    proc_exited: bool,
    result_received: bool,
) -> SettleDecision | None:
    """Адаптер для коллбэка turn_complete или владельца с методом settle_decision."""
    result: SettleDecision | None = None
    if callable(turn_complete):
        owner = getattr(turn_complete, "__self__", None)
        method = getattr(owner, "settle_decision", None)
        if callable(method):
            raw = method(proc_exited=proc_exited, result_received=result_received)
            if isinstance(raw, SettleDecision):
                result = raw
        elif turn_complete():
            result = _FORCED_STOP
    return result


def decide_session_commit(
    *,
    state: str,
    rc: int | None,
    tool_turn_stop: bool,
    conversation_id: str,
    cid_valid: bool,
) -> Literal["commit", "invalidate", "noop"]:
    """Единое решение коммита горячего cid: запрещает коммит после forced_stop и ошибок."""
    decision: Literal["commit", "invalidate", "noop"] = "noop"
    rc_zero = all((isinstance(rc, int), not isinstance(rc, bool), not rc))
    clean_done = all((dict(done=True).get(state, False), rc_zero, not tool_turn_stop))
    if all((clean_done, bool(conversation_id), cid_valid)):
        decision = "commit"
    elif any((tool_turn_stop, not clean_done)):
        decision = "invalidate"
    return decision
