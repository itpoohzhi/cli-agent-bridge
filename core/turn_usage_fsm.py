"""Чистая FSM-политика расчёта step-scoped usage и строгого missing_usage (D4, W3)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, cast

from core.usage_normalizer import reconcile_turn_usage
from core.usage_wire import normalize_prompt_cache_details


class StepUsageSnapshot(Protocol):
    """Структурный протокол снимка транскрипта, совпадающий с _UsageSnapshot."""

    @property
    def last_step_usage(self) -> tuple[int, int, int | None, int] | None: ...
    @property
    def turn_output_tokens_sum(self) -> int: ...
    @property
    def observed_planner_steps(self) -> int: ...
    @property
    def observed_planner_steps_saturated(self) -> bool: ...
    @property
    def completeness(self) -> bool: ...
    @property
    def invalid_records_count(self) -> int: ...


@dataclass(frozen=True)
class TurnUsageResolution:
    """Результат вычисления usage (12 прежних ключей + emit_wire_usage) и лог-сообщения."""

    resolved: dict[str, object]
    log_messages: tuple[str, ...]


def _count_or_none(value: object) -> int | None:
    is_int = all((isinstance(value, int), not isinstance(value, bool)))
    result: int | None = None
    if is_int and isinstance(value, int):
        result = value if max(0, value) - value == 0 else None
    return result


def _num_text(value: object) -> str:
    count = _count_or_none(value)
    result = str(count) if isinstance(count, int) else "missing"
    return result


def _raw_cache_tokens(raw: Mapping[str, object]) -> tuple[int | None, bool]:
    snake = raw.get("cache_read_tokens")
    camel = raw.get("cacheReadTokens")
    both = all((not isinstance(snake, type(None)), not isinstance(camel, type(None))))
    conflict = all((both, snake != camel))
    picked = snake if not isinstance(snake, type(None)) else camel
    result = (None, True) if conflict else (_count_or_none(picked), False)
    return result


def _is_clean_result(out: Mapping[str, object]) -> bool:
    res_obj = out.get("result")
    res: Mapping[str, object] = cast("Mapping[str, object]", res_obj) if isinstance(res_obj, Mapping) else {}
    rc = out.get("rc")
    rc_zero = all((isinstance(rc, int), not isinstance(rc, bool), not rc))
    status_err = dict(ERROR=True).get(str(res.get("status") or "").upper(), False)
    return all((rc_zero, dict(done=True).get(str(out.get("state")), False), not status_err, not res.get("error")))


def _resolve_from_last_step(
    last: tuple[int, int, int | None, int],
    snap: StepUsageSnapshot,
    raw_out: int | None,
    raw_th: int | None,
) -> tuple[dict[str, object], tuple[str, ...]]:
    step_idx, last_in, last_cache, _last_out = last
    prompt = last_in + (last_cache if isinstance(last_cache, int) else 0)
    details, inconsistent = normalize_prompt_cache_details(prompt, last_cache)
    logs: tuple[str, ...] = ()
    completion = snap.turn_output_tokens_sum if snap.completeness else 0
    reason = "" if snap.completeness else "ledger_incomplete"
    if not snap.completeness:
        fmt = (
            "usage-step-ledger-incomplete observed_steps=%d saturated=%d "
            + "invalid_records=%d raw_output=%s raw_thinking=%s"
        )
        logs = (
            fmt
            % (
                snap.observed_planner_steps, int(snap.observed_planner_steps_saturated),
                snap.invalid_records_count, _num_text(raw_out), _num_text(raw_th),
            ),
        )
    data: dict[str, object] = {
        "source": "last_step", "reason": reason, "step_idx": step_idx,
        "prompt": prompt, "completion": completion, "details": details,
        "inconsistent": inconsistent, "emit_wire_usage": True,
    }
    return data, logs


def _over_window(raw_in: int | None, cache_sum: int, window: int | None) -> bool:
    result = False
    if isinstance(window, int):
        if isinstance(raw_in, int):
            result = any((raw_in >= window, (raw_in + cache_sum) > window))
    return result


def _result_reason(conflict: bool, missing: bool, success: bool, has_window: bool) -> str:
    reason = "within_window"
    if conflict:
        reason = "alias_conflict"
    elif missing:
        reason = "missing_usage"
    elif not success:
        reason = "not_success"
    elif not has_window:
        reason = "no_window"
    return reason


def _cum_log(
    raw_meta: tuple[int | None, int | None, int | None, int | None, bool],
    stats: tuple[int, int, int, int, int, int],
    inconsistent: bool,
) -> str:
    raw_in, raw_out, raw_th, raw_cache, _ = raw_meta
    window, divisor, prompt, turns, tools, obs_steps = stats
    fmt = (
        "usage-cumulative-fallback raw_in=%s raw_cache=%s window=%d n=%d "
        + "prompt=%d turns=%d tools=%d observed_steps=%d inconsistent=%d "
        + "raw_output=%s raw_thinking=%s"
    )
    return fmt % (
        _num_text(raw_in), _num_text(raw_cache), window, divisor, prompt,
        turns, tools, obs_steps, int(inconsistent), _num_text(raw_out), _num_text(raw_th),
    )


def _resolve_result_prompt(
    use_cum: bool,
    raw_in: int | None,
    cache_sum: int,
    window: int | None,
    divisor: int,
) -> tuple[str, int]:
    win_val = window if isinstance(window, int) else 0
    in_val = raw_in if isinstance(raw_in, int) else 0
    source = "cumulative_estimate" if use_cum else "result"
    prompt = min(in_val // divisor, win_val - 1) if use_cum else (in_val + cache_sum)
    return source, prompt


def _int_or_zero(value: object) -> int:
    val = _count_or_none(value)
    return val if isinstance(val, int) else 0


def _resolve_from_result(
    out: Mapping[str, object],
    snap: StepUsageSnapshot | None,
    window: int | None,
    resume: bool,
    raw_meta: tuple[int | None, int | None, int | None, int | None, bool],
) -> tuple[dict[str, object], tuple[str, ...]]:
    raw_in, raw_out, raw_th, raw_cache, conflict = raw_meta
    obs_steps = snap.observed_planner_steps if snap else 0
    success = _is_clean_result(out)
    cache_sum = raw_cache if isinstance(raw_cache, int) else 0
    use_cum = all((success, _over_window(raw_in, cache_sum, window)))
    turns = _int_or_zero(out.get("num_turns"))
    tools = _int_or_zero(out.get("tool_events"))
    divisor = max(2, turns + tools, obs_steps)
    missing = all((not isinstance(raw_in, int), not isinstance(raw_cache, int), not conflict))
    source, prompt = _resolve_result_prompt(use_cum, raw_in, cache_sum, window, divisor)
    reason = "over_window" if use_cum else _result_reason(conflict, missing, success, isinstance(window, int))
    details, inconsistent = normalize_prompt_cache_details(prompt, raw_cache)
    usage_obj = out.get("usage")
    raw_map = cast("Mapping[str, object]", usage_obj) if isinstance(usage_obj, Mapping) else {}
    raw_total = _count_or_none(raw_map.get("total_tokens"))
    reconciled = reconcile_turn_usage(
        raw_input=raw_in, raw_output=raw_out, raw_total=raw_total, raw_thinking=raw_th
    )
    fresh_comp = reconciled.completion_tokens
    completion = fresh_comp if all((not resume, not obs_steps)) else 0
    win_val = window if isinstance(window, int) else 0
    logs = (_cum_log(raw_meta, (win_val, divisor, prompt, turns, tools, obs_steps), inconsistent),) if use_cum else ()
    data: dict[str, object] = {
        "source": source, "reason": reason, "step_idx": None, "prompt": prompt,
        "completion": completion, "details": details, "inconsistent": inconsistent,
        "emit_wire_usage": not missing,
    }
    return data, logs


def resolve_turn_usage(
    out: Mapping[str, object],
    snap: StepUsageSnapshot | None,
    window: int | None,
    resume: bool,
) -> TurnUsageResolution:
    """Вычисляет нормализованный step-scoped usage (12 ключей + emit_wire_usage)."""
    raw_obj = out.get("usage")
    raw: Mapping[str, object] = cast("Mapping[str, object]", raw_obj) if isinstance(raw_obj, Mapping) else {}
    raw_in = _count_or_none(raw.get("input_tokens"))
    raw_out = _count_or_none(raw.get("output_tokens"))
    raw_th = _count_or_none(raw.get("thinking_tokens"))
    raw_cache, conflict = _raw_cache_tokens(raw)
    raw_total = _count_or_none(raw.get("total_tokens"))
    reconciled = reconcile_turn_usage(
        raw_input=raw_in, raw_output=raw_out, raw_total=raw_total, raw_thinking=raw_th
    )
    calc, logs = _resolve_from_result(out, snap, window, resume, (raw_in, raw_out, raw_th, raw_cache, conflict))
    if snap:
        if snap.last_step_usage:
            calc, logs = _resolve_from_last_step(snap.last_step_usage, snap, raw_out, raw_th)
    prompt = cast("int", calc["prompt"])
    completion = cast("int", calc["completion"])
    details = cast("dict[str, int] | None", calc["details"])
    reasoning_tokens: int | None = reconciled.reasoning_tokens
    reasoning_inconsistent = reconciled.reasoning_inconsistent
    if snap and snap.last_step_usage and raw_th is not None:
        if 0 < raw_th <= completion:
            reasoning_tokens, reasoning_inconsistent = raw_th, False
        elif raw_th > completion:
            reasoning_tokens, reasoning_inconsistent = None, True
    if reasoning_tokens is not None and reasoning_tokens > completion:
        reasoning_tokens, reasoning_inconsistent = None, True
    wire: dict[str, object] = {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
    }
    if isinstance(details, dict):
        wire["prompt_tokens_details"] = details
    if reasoning_tokens is not None:
        wire["completion_tokens_details"] = {"reasoning_tokens": reasoning_tokens}
    resolved: dict[str, object] = {
        "wire": wire, "source": calc["source"], "reason": calc["reason"],
        "step_idx": calc["step_idx"], "completeness": snap.completeness if snap else False,
        "inconsistent": calc["inconsistent"],
        "cached": details["cached_tokens"] if isinstance(details, dict) else None,
        "raw_in": raw_in, "raw_out": raw_out, "raw_thinking": raw_th,
        "raw_total": raw_total, "raw_cache": raw_cache,
        "emit_wire_usage": calc["emit_wire_usage"],
        "reasoning": reasoning_tokens, "reasoning_inconsistent": reasoning_inconsistent,
    }
    return TurnUsageResolution(resolved=resolved, log_messages=logs)


def should_emit_wire_usage(resolved: object) -> bool:
    """Возвращает False при строгом missing_usage (запрещает отдачу пустого/нулевого usage)."""
    result = True
    if isinstance(resolved, Mapping):
        flag = cast("Mapping[str, object]", resolved).get("emit_wire_usage")
        if isinstance(flag, bool):
            result = flag
    return result
