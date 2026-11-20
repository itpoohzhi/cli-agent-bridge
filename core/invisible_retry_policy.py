"""Политика невидимого повтора и бюджета (AD-003, BND-001): чистый домен без часов и потоков.

Время, число недавних сбоев и случайность (`jitter_unit` ∈ [0, 1]) приходят параметрами.
Бюджет: T_total_eff = min(retry_total_budget_s, client_timeout_s);
T_attempt_cap = (T_total_eff - (N-1) * T_pause_max) / N, N = max_retries + 1;
гейт: elapsed + pause + last_attempt <= T_total_eff.
"""

from __future__ import annotations

import math

from core.transport_failure_contracts import (
    DeliveryFacts,
    RetryAttemptState,
    RetryBudgetConfig,
    RetryBudgetDecision,
)


def _deny(reason: str) -> RetryBudgetDecision:
    return RetryBudgetDecision(False, reason)


def _finite_non_negative(value: float) -> float:
    return value if isinstance(value, (int, float)) and math.isfinite(value) and value > 0 else 0.0


def t_total_eff(cfg: RetryBudgetConfig) -> float:
    """Эффективный сквозной бюджет: меньшее из общего и клиентского таймаута (≥ 0)."""
    return min(_finite_non_negative(cfg.retry_total_budget_s), _finite_non_negative(cfg.client_timeout_s))


def t_attempt_cap(cfg: RetryBudgetConfig) -> float:
    """Потолок одной попытки с учётом пауз между N попытками (может быть ≤ 0)."""
    attempts = max(1, int(cfg.max_retries) + 1)
    pauses = (attempts - 1) * _finite_non_negative(cfg.pause_max_s)
    return (t_total_eff(cfg) - pauses) / attempts


def _unit(value: float) -> float:
    """Нормировать jitter в [0, 1]; нечисло → 1.0 (консервативно длинная пауза)."""
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        return 1.0
    return min(1.0, max(0.0, float(value)))


def compute_pause_s(cfg: RetryBudgetConfig, state: RetryAttemptState) -> float:
    """Пауза = full jitter [0, pause_max] + добавка коррелированного окна; ≤ pause_max."""
    pause_max = _finite_non_negative(cfg.pause_max_s)
    failures = max(0, int(state.recent_failures))
    correlated = (pause_max / 2.0) * (1.0 - 1.0 / (1.0 + failures))
    return min(pause_max, pause_max * _unit(state.jitter_unit) + correlated)


def _structural_denial(
    facts: DeliveryFacts, cfg: RetryBudgetConfig, state: RetryAttemptState
) -> str:
    """Причина запрета до расчёта времени; пустая строка — структурно повтор допустим."""
    if facts.delivered:
        return "content_delivered"
    if int(cfg.max_retries) <= 0:
        return "retries_disabled"
    if state.attempt < 1 or state.attempt > int(cfg.max_retries):
        return "max_retries_exhausted"
    if t_total_eff(cfg) <= 0.0 or t_attempt_cap(cfg) <= 0.0:
        return "budget_non_positive"
    return ""


def may_retry_invisibly(
    facts: DeliveryFacts, cfg: RetryBudgetConfig, state: RetryAttemptState
) -> RetryBudgetDecision:
    """Разрешить невидимый повтор iff клиенту ничего не доставлено и бюджет позволяет."""
    reason = _structural_denial(facts, cfg, state)
    if reason:
        return _deny(reason)
    pause = compute_pause_s(cfg, state)
    elapsed = _finite_non_negative(state.elapsed_s)
    last = _finite_non_negative(state.last_attempt_s)
    total = t_total_eff(cfg)
    remaining = total - elapsed - pause
    if remaining <= 0.0 or elapsed + pause + last > total:
        return _deny("budget_exhausted")
    return RetryBudgetDecision(True, "retry_allowed", pause, min(t_attempt_cap(cfg), remaining))
