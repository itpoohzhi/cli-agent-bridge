"""Политика recovery «служебная ошибка functionCall → валидный tool_call» (AD-005, BND-001).

Fail-closed по INV-S1..S8: любое сомнение → REJECT, поведение равно базе.
  S1 tool_events == 0 и content_bytes == 0; S2 кандидат строго после ошибки и complete;
  S3 strict-parse ВСЕХ блоков без остатка (9/10 → REJECT целиком);
  S4 наружу идут только структурированные вызовы (сырая разметка в решение не попадает);
  S5 дедуп только по идентичному непустому call_id либо точному половинному зеркалу
     [c_1..c_m, c_1..c_m] при пустых call_id; неоднозначность → REJECT; S6 once-per-turn.
"""

from __future__ import annotations

import json

from core.transport_failure_contracts import (
    DeliveryFacts,
    ParsedToolCall,
    StepRecord,
    ToolCallParser,
    ToolCallRecoveryDecision,
    TurnStepsSnapshot,
)

ERROR_KIND = "error"
PLANNER_KIND = "planner"


def _reject(reason: str) -> ToolCallRecoveryDecision:
    return ToolCallRecoveryDecision(False, (), reason)


def _canon(call: ParsedToolCall) -> tuple[str, str]:
    """Каноническая пара (name, arguments): ключи JSON отсортированы, пробелы нормализованы."""
    try:
        args = json.dumps(json.loads(call.arguments_json), sort_keys=True, separators=(",", ":"))
    except ValueError:
        args = call.arguments_json
    return (call.name, args)


def _dedup_by_call_id(calls: tuple[ParsedToolCall, ...]) -> tuple[ParsedToolCall, ...] | None:
    """Схлопнуть дубли с одинаковым непустым call_id; расхождение содержимого → `None`."""
    seen: dict[str, tuple[str, str]] = {}
    out: list[ParsedToolCall] = []
    for call in calls:
        key = _canon(call)
        if call.call_id in seen:
            if seen[call.call_id] != key:
                return None
            continue
        seen[call.call_id] = key
        out.append(call)
    return tuple(out)


def _dedup_without_call_id(calls: tuple[ParsedToolCall, ...]) -> tuple[ParsedToolCall, ...] | None:
    """Без call_id: повторы допустимы только как точное половинное зеркало, иначе `None`."""
    keys = [_canon(c) for c in calls]
    if len(set(keys)) == len(keys):
        return calls
    half, odd = divmod(len(calls), 2)
    if odd or keys[:half] != keys[half:] or len(set(keys[:half])) != half:
        return None
    return calls[:half]


def _dedup(calls: tuple[ParsedToolCall, ...]) -> tuple[ParsedToolCall, ...] | None:
    ids = [bool(c.call_id) for c in calls]
    if all(ids):
        return _dedup_by_call_id(calls)
    if not any(ids):
        return _dedup_without_call_id(calls)
    return None


def _candidate(steps: tuple[StepRecord, ...]) -> StepRecord | str:
    """Последний шаг планировщика строго после последней ошибки (INV-S2) либо причина отказа."""
    errors = [s.index for s in steps if s.kind == ERROR_KIND]
    if not errors:
        return "no_error_step"
    later = [s for s in steps if s.kind == PLANNER_KIND and s.index > max(errors)]
    if not later:
        return "no_step_after_error"
    last = max(later, key=lambda s: s.index)
    return last if last.complete else "candidate_incomplete"


def _delivery_denial(facts: DeliveryFacts | None) -> str:
    if facts is not None and (facts.tool_events > 0 or facts.content_bytes > 0):
        return "client_output_already_delivered"
    return ""


def evaluate_recovery(
    snapshot: TurnStepsSnapshot, parser: ToolCallParser, facts: DeliveryFacts | None = None
) -> ToolCallRecoveryDecision:
    """Решить, можно ли восстановить ход структурированными вызовами; иначе REJECT."""
    if snapshot.recovery_attempted:
        return _reject("once_per_turn")
    reason = _delivery_denial(facts)
    if reason:
        return _reject(reason)
    step = _candidate(snapshot.steps)
    if isinstance(step, str):
        return _reject(step)
    parsed = parser.parse_all(step.text.strip())
    if not parsed:
        return _reject("strict_parse_failed")
    calls = _dedup(parsed)
    if not calls:
        return _reject("ambiguous_multiplicity")
    return ToolCallRecoveryDecision(True, calls, "recovered")
