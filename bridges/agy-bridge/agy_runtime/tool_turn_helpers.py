"""Тонкие runtime-хелперы `_ToolTurn` для `agy-bridge` (cap-cutoff, bytes, settle)."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any, cast

from core.continuity_anchor_policy import mint_bridge_call_id
from core.runtime_env import synthesize_required_bash_desc_enabled
from core.tool_call_cap_policy import ToolCallCapDecision, evaluate_bytes_cap, evaluate_call_cap
from core.tool_call_schema_policy import ToolCallLimitExceededError
from core.tool_emulation import has_unnamed_call, sanitize_tool_call
from core.tool_turn_settle_policy import ToolTurnSettleState


def build_tool_entry(index: int, call: Mapping[str, Any], call_id: str) -> dict[str, object]:
    """Формирует OpenAI-совместимую запись tool_call для санитизации."""
    return {
        "index": index,
        "id": call_id,
        "type": "function",
        "function": {
            "name": str(call.get("name") or ""),
            "arguments": json.dumps(call.get("arguments") or {}, ensure_ascii=False),
        },
    }


def apply_cap_decision(
    turn: Any, decision: ToolCallCapDecision, log_fn: Callable[[str], None]
) -> bool:
    """Применяет решение политики лимитов к `_ToolTurn` с явным логированием."""
    if decision.log_line:
        log_fn(decision.log_line)
    if decision.action == "cap_cutoff":
        turn._cap_cutoff = True
        turn._normalizer.suppress_tail()
        return True
    if decision.action == "limit_error":
        turn._limit_error = ToolCallLimitExceededError(
            decision.limit_kind, decision.observed, decision.limit, decision.error_message
        )
        turn.error = decision.error_message
        return False
    return True


def _publish_sanitized(
    turn: Any, published: list[dict[str, object]], log_fn: Callable[[str], None]
) -> None:
    post = evaluate_call_cap(
        current_calls=len(turn.calls),
        incoming_calls=len(published),
        max_calls=turn._max_calls,
        cap_cutoff_enabled=turn._cap_cutoff_enabled,
    )
    if post.action == "limit_error":
        _ = apply_cap_decision(turn, post, log_fn)
        return
    accepted = published[: post.accept_count]
    if accepted:
        turn.calls.extend(accepted)
        if turn.ok and not turn._on_calls(accepted):
            turn.ok = False
    if post.action == "cap_cutoff":
        _ = apply_cap_decision(turn, post, log_fn)


def handle_tool_call(
    turn: Any, call: Mapping[str, Any], log_fn: Callable[[str], None]
) -> None:
    """Обрабатывает входящий вызов `_ToolTurn._call` с учётом cap-cutoff и parallel-среза."""
    if turn.error or turn._cap_cutoff:
        return
    pre = evaluate_call_cap(
        current_calls=len(turn.calls),
        incoming_calls=1,
        max_calls=turn._max_calls,
        cap_cutoff_enabled=turn._cap_cutoff_enabled,
    )
    if pre.action != "allow":
        _ = apply_cap_decision(turn, pre, log_fn)
        return
    entry = build_tool_entry(len(turn.calls), call, mint_bridge_call_id())
    if has_unnamed_call(entry):
        turn.error = turn.error or "tool call without function name dropped"
        turn.ok = False
        return
    synth = synthesize_required_bash_desc_enabled()
    sanitized = sanitize_tool_call(entry, turn._schemas, synthesize_required_description=synth)
    published = [dict(cast("dict[str, object]", item), index=len(turn.calls) + i) for i, item in enumerate(sanitized)]
    if published:
        _publish_sanitized(turn, published, log_fn)


def should_ignore_feed(turn: Any, text: str) -> bool:
    """True, если ход уже завершён/отсечён/с ошибкой или дельта пуста."""
    return any((
        bool(turn.error), bool(turn._finished), bool(turn._cap_cutoff),
        not text, turn._normalizer.post_call_suppressed is True,
    ))


def check_bytes_limit(
    turn: Any, chunk_bytes: int, log_fn: Callable[[str], None]
) -> bool:
    """Проверяет байтовый бюджет `_ToolTurn` и классифицирует превышение."""
    decision = evaluate_bytes_cap(
        current_bytes=turn._total_bytes, chunk_bytes=chunk_bytes, max_bytes=turn._max_bytes
    )
    if decision.action == "allow":
        turn._total_bytes += chunk_bytes
        return True
    _ = apply_cap_decision(turn, decision, log_fn)
    return False


def build_settle_state(
    turn: Any, now: float, *, proc_exited: bool, result_received: bool
) -> ToolTurnSettleState:
    """Собирает снимок `ToolTurnSettleState` с учётом `cap_cutoff`."""
    return ToolTurnSettleState(
        now=now,
        has_error=bool(turn.error),
        has_open_tool_call=turn._normalizer.has_open_tool_call(),
        has_calls=bool(turn.calls),
        last_open_chunk_ts=turn._last_open_chunk_ts,
        last_chunk_ts=turn._last_chunk_ts,
        calls_closed_ts=turn._calls_closed_ts,
        proc_exited=proc_exited,
        result_received=result_received,
        post_call_suppressed=turn._normalizer.post_call_suppressed is True,
        cap_cutoff=bool(turn._cap_cutoff),
    )
