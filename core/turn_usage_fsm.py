"""Чистая FSM-политика расчёта step-scoped usage и строгого missing_usage (D4, W3)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, cast

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
    result: int | None = None
    if isinstance(value, int) and not isinstance(value, bool):
        result = value if value >= 0 else None
    return result


def _num_text(value: object) -> str:
    count = _count_or_none(value)
    result = str(count) if isinstance(count, int) else "missing"
    return result


def _raw_cache_tokens(raw: Mapping[str, object]) -> tuple[int | None, bool]:
    snake = raw.get("cache_read_tokens")
    camel = raw.get("cacheReadTokens")
    both = all((not isinstance(snake, type(None)), not isinstance(camel, type(None))))
    conflict = both and snake != camel
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
                snap.observed_planner_steps,
                int(snap.observed_planner_steps_saturated),
                snap.invalid_records_count,
                _num_text(raw_out),
                _num_text(raw_th),
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
    if isinstance(window, int) and isinstance(raw_in, int):
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
    turns = _count_or_none(out.get("num_turns")) or 0
    tools = _count_or_none(out.get("tool_events")) or 0
    divisor = max(2, turns + tools, obs_steps)
    missing = all((not isinstance(raw_in, int), not isinstance(raw_cache, int), not conflict))
    if use_cum and isinstance(raw_in, int) and isinstance(window, int):
        source, prompt, reason = "cumulative_estimate", min(raw_in // divisor, window - 1), "over_window"
    else:
        source = "result"
        prompt = (raw_in if isinstance(raw_in, int) else 0) + cache_sum
        reason = _result_reason(conflict, missing, success, isinstance(window, int))
    details, inconsistent = normalize_prompt_cache_details(prompt, raw_cache)
    fresh_comp = (raw_out if isinstance(raw_out, int) else 0) + (raw_th if isinstance(raw_th, int) else 0)
    completion = fresh_comp if all((not resume, not obs_steps)) else 0
    logs: tuple[str, ...] = ()
    if use_cum and isinstance(window, int):
        fmt = (
            "usage-cumulative-fallback raw_in=%s raw_cache=%s window=%d n=%d "
            + "prompt=%d turns=%d tools=%d observed_steps=%d inconsistent=%d "
            + "raw_output=%s raw_thinking=%s"
        )
        logs = (
            fmt
            % (
                _num_text(raw_in), _num_text(raw_cache), window, divisor, prompt,
                turns, tools, obs_steps, int(inconsistent), _num_text(raw_out), _num_text(raw_th),
            ),
        )
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
    last = snap.last_step_usage if snap else None
    if last and snap:
        calc, logs = _resolve_from_last_step(last, snap, raw_out, raw_th)
    else:
        calc, logs = _resolve_from_result(out, snap, window, resume, (raw_in, raw_out, raw_th, raw_cache, conflict))
    prompt = cast("int", calc["prompt"])
    completion = cast("int", calc["completion"])
    details = cast("dict[str, int] | None", calc["details"])
    wire: dict[str, object] = {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
    }
    if isinstance(details, dict):
        wire["prompt_tokens_details"] = details
    resolved: dict[str, object] = {
        "wire": wire,
        "source": calc["source"],
        "reason": calc["reason"],
        "step_idx": calc["step_idx"],
        "completeness": snap.completeness if snap else False,
        "inconsistent": calc["inconsistent"],
        "cached": details["cached_tokens"] if isinstance(details, dict) else None,
        "raw_in": raw_in,
        "raw_out": raw_out,
        "raw_thinking": raw_th,
        "raw_total": _count_or_none(raw.get("total_tokens")),
        "raw_cache": raw_cache,
        "emit_wire_usage": calc["emit_wire_usage"],
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
