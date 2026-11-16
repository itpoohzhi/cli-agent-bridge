"""Чистый agent-agnostic фасад транзиентного и доказанного каузального восстановления."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from typing import Final, cast
import core.turn_outcome_policy as causal
from core.route_health_policy import (
    TRANSIENT_STREAM_INTERRUPTION_RE as TRANSIENT_STREAM_INTERRUPTION_RE,
    RetryBudgetConfig, compute_attempt_decision,
    is_transient_stream_interruption as is_transient_stream_interruption,
    validate_retry_config,
)

CLI_ERROR_SOURCE: Final[str] = "cli_error"
ERROR_STATUS: Final[str] = "ERROR"
DONE_STATUS: Final[str] = "DONE"
DONE_STATE: Final[str] = "done"
ERROR_STATE: Final[str] = "agy_error"
SELF_HEALED_REASON: Final[str] = "self_healed_after_transient_interruption"
RETRY_BLOCKED_REASON: Final[str] = "retry_blocked"
TRANSIENT_RETRY_REASON: Final[str] = "transient_pre_delivery_retry"
DEFAULT_INTERRUPTION_NOTICE: Final[str] = "\n\n[⚠️ Поток прерван транзиентным сбоем транспорта; показан частичный ответ.]"
DEFAULT_RETRY_CONFIG: Final[RetryBudgetConfig] = RetryBudgetConfig(max_attempts=2)
MAX_ELAPSED_S: Final[float] = 1e308

class InterruptionTailState:
    """Факты о финальном planner-шаге и транзиентных обрывах."""
    final_planner: bool = False
    final_planner_content: str = ""
    last_planner_step_index: int = -1
    last_error_step_index: int = -1
    had_transient_error: bool = False
    had_safety_error: bool = False
    last_error_sha256: str = ""
    last_error_length: int = 0
    last_error_attempt: int = -1
    error_from_structured_record: bool = False
    last_completion_attempt: int = -1
    has_open_planner_after_completion: bool = False
    attempt: int = -1
    def note_error_record(self, rtype: str | int, rec: dict[str, object] | str = "", idx: int | None = None, **kw: object) -> None:
        """Без реального attempt или step_index каузальность не доказана."""
        if isinstance(rtype, int) or rtype == "ERROR_MESSAGE":
            text = kw.get("text", rec)
            struct_safety = False
            if isinstance(rec, dict):
                texts = (rec.get(key) for key in ("content", "message", "error"))
                text = next(filter(None, texts), "")
                struct_safety = any(
                    causal.is_fatal_safety_error(f"{k}: {v}")
                    for k, v in rec.items()
                    if str(k).lower() in ("block_reason", "blockreason", "finish_reason", "finishreason", "stop_reason", "stopreason", "reason", "error", "message") and v is not None
                ) or causal.is_fatal_safety_error(json.dumps(rec, default=str))
            text = str(text)
            seq = rtype if isinstance(rtype, int) else idx if idx is not None else -1
            self.final_planner, self.final_planner_content = False, ""
            self.has_open_planner_after_completion = self.last_planner_step_index >= 0
            self.had_transient_error |= is_transient_stream_interruption(text)
            self.had_safety_error |= struct_safety or causal.is_fatal_safety_error(text)
            if seq < 0 or seq >= self.last_error_step_index:
                self.last_error_step_index = seq
                self.last_error_sha256 = causal.error_identity_digest(text)
                self.last_error_length = len(causal.normalize_error_identity(text))
                attempt = kw.get("attempt", self.attempt)
                self.last_error_attempt = attempt if type(attempt) is int else -1
                self.error_from_structured_record = seq >= 0

    def note_planner_record(self, rec: dict[str, object], idx: int, *, attempt: int | None = None) -> None:
        """Непустой DONE без tools завершает шаг; любой новый открытый шаг отменяет финал."""
        content = rec.get("content")
        has_tools = bool(rec.get("tool_calls"))
        text = content if isinstance(content, str) else ""
        done = str(rec.get("status", DONE_STATUS)).upper() == DONE_STATUS
        self.final_planner = bool(text.strip()) and not has_tools and done
        self.has_open_planner_after_completion = not self.final_planner
        self.final_planner_content = text if self.final_planner else ""
        if self.final_planner:
            self.last_planner_step_index = max(self.last_planner_step_index, idx)
            self.last_completion_attempt = self.attempt if attempt is None else attempt

@dataclass(frozen=True)
class TailCausalFacts:
    """Замороженный снимок скалярного доказательства хвоста, без текста ошибки."""
    error: causal.CausalErrorIdentity
    error_from_structured_record: bool
    completion: causal.CausalCompletionFacts
    has_late_error_or_open_step: bool

def tail_causal_facts(tail: object) -> TailCausalFacts:
    """Экспортирует каузальные факты отдельно от совместимого legacy-словаря."""
    def get[T](name: str, default: T) -> T:
        return cast(T, getattr(tail, name, default))
    error = causal.CausalErrorIdentity(
        get("last_error_step_index", -1), get("last_error_attempt", -1),
        get("last_error_sha256", ""), get("last_error_length", 0),
    )
    completion = causal.CausalCompletionFacts(
        get("last_planner_step_index", -1), get("last_completion_attempt", -1),
        bool(get("final_planner", False)), bool(get("final_planner_content", "").strip()),
    )
    late = error.seq >= completion.last_completion_seq and error.seq >= 0
    return TailCausalFacts(error, bool(get("error_from_structured_record", False)),
                           completion, late or bool(get("has_open_planner_after_completion", False)))
def evaluate_done_causal_recovery(causal_input: causal.CausalOutcomeInput, error: str | None = None) -> causal.CausalOutcomeDecision:
    """Одно решение разрешает reconcile и снятие ошибки; эхо берётся целиком."""
    if error is not None:
        echo = replace(causal_input.error, result_error_sha256=causal.error_identity_digest(error))
        causal_input = replace(causal_input, error=echo, config=replace(causal_input.config, is_fatal_safety=causal_input.config.is_fatal_safety or causal.is_fatal_safety_error(error)))
    return causal.evaluate_causal_turn_recovery(causal_input)

def settle_error(error: str, cleared: str, status: str) -> str:
    """Вернуть ошибку хода на done."""
    return error or (cleared if status == ERROR_STATUS else "")

def trusted_final_text(final_text: str, error: str, tail: object, causal_input: causal.CausalOutcomeInput | None = None) -> str:
    """Текст для reconcile: при неснятой ошибке — только финальный planner хвоста."""
    if getattr(tail, "had_safety_error", False) or causal.is_fatal_safety_error(error):
        return ""
    if error and not is_transient_stream_interruption(error):
        snapshot = tail_causal_facts(tail)
        if causal_input is None:
            return ""
        consistent = (
            snapshot.error == causal_input.error.identity,
            snapshot.error_from_structured_record == causal_input.error.error_from_structured_record,
            snapshot.completion == causal_input.completion,
            not snapshot.has_late_error_or_open_step,
        )
        if not all(consistent) or not evaluate_done_causal_recovery(causal_input, error).allow_reconcile:
            return ""
    planner = str(getattr(tail, "final_planner_content", ""))
    healed = (final_text or planner) if getattr(tail, "final_planner", False) else ""
    return healed if error else final_text

def tail_turn_facts(tail: object, cleared_error: str = "") -> dict[str, object]:
    """Факты хода из транскрипт-хвоста для `resolve_done_turn_outcome` (без хвоста — нейтральны)."""
    facts: dict[str, object] = {
        "completion_done_without_tools": bool(getattr(tail, "final_planner", False)),
        "last_completion_seq": getattr(tail, "last_planner_step_index", -1),
        "last_error_seq": getattr(tail, "last_error_step_index", -1),
        "drain_complete": getattr(tail, "drain_outcome", "") != "timeout",
        "had_transient_error": bool(getattr(tail, "had_transient_error", False)) or bool(cleared_error),
    }
    if getattr(tail, "had_safety_error", False):
        facts["had_safety_error"] = True
    return facts
@dataclass(frozen=True)
class TurnOutcomeResolution:
    """Итог разбора done."""
    state: str
    rc: int
    error: str
    self_healed: bool
    reason: str
    final: bool

@dataclass(frozen=True)
class _TurnFacts:
    rc: int
    result_error: str
    result_status: str
    final_text: str
    emitted_text: str
    completion_done_without_tools: bool = False
    last_completion_seq: int = -1
    last_error_seq: int = -1
    drain_complete: bool = False
    had_transient_error: bool = False
    had_safety_error: bool = False
    has_unclosed_tool_call: bool = False
    self_heal_enabled: bool = True
    causal_input: causal.CausalOutcomeInput | None = None

_DONE_REASONS: Final[tuple[str, ...]] = ("clean_done", SELF_HEALED_REASON)
def _heal_blocker(f: _TurnFacts, transient_error: bool) -> str:
    """Первая причина, запрещающая самоисцеление (пусто — разрешено)."""
    checks = (("self_heal_disabled", not f.self_heal_enabled), ("non_transient_result_error", bool(f.result_error) and not transient_error),
              ("unclassified_nonzero_rc", not (f.had_transient_error or transient_error)),
              ("drain_incomplete", not f.drain_complete), ("unclosed_tool_call", f.has_unclosed_tool_call))
    return next((reason for reason, hit in checks if hit), "")

def _is_recovered(f: _TurnFacts) -> bool:
    """Финальный planner без tool_calls позже последней ошибки и с непустым телом."""
    has_body = bool(f.final_text.strip() or f.emitted_text.strip())
    later = f.last_completion_seq > max(f.last_error_seq, -1)
    return f.completion_done_without_tools and later and has_body
def resolve_done_turn_outcome(**kw: object) -> TurnOutcomeResolution:
    """Сохраняет legacy kwargs `_TurnFacts`; неизвестный аргумент даёт TypeError."""
    f = _TurnFacts(**kw)  # pyright: ignore[reportArgumentType]  # Legacy kwargs сохраняются без Any.
    if f.had_safety_error or causal.is_fatal_safety_error(f.result_error) or (f.causal_input is not None and f.causal_input.config.is_fatal_safety):
        error = f.result_error if causal.is_fatal_safety_error(f.result_error) else f"fatal_safety_error: {f.result_error}"
        return TurnOutcomeResolution(ERROR_STATE, 1, error, False, "fatal_safety_error", True)
    transient = is_transient_stream_interruption(f.result_error)
    if f.result_error and not transient and f.causal_input is not None:
        decision = evaluate_done_causal_recovery(f.causal_input, f.result_error)
        consistent = (f.self_heal_enabled and not f.has_unclosed_tool_call and bool(f.final_text.strip() or f.emitted_text.strip())
                      and f.rc == f.causal_input.terminal.process.returncode)
        healed = decision.clear_error and consistent
        reason = decision.reason if not decision.recovered or consistent else "inconsistent_causal_facts"
        return TurnOutcomeResolution(
            DONE_STATE if healed else ERROR_STATE, 0 if healed else f.rc or 1,
            "" if healed else f.result_error, healed, reason, True,
        )
    clean = not (f.rc or f.result_error or f.result_status == ERROR_STATUS)
    blocker = _heal_blocker(f, transient)
    reasons = (("clean_done", clean), (blocker, bool(blocker)), (SELF_HEALED_REASON, _is_recovered(f)), ("not_recovered", True))
    reason = next(name for name, hit in reasons if hit)
    error = f.result_error if f.result_error else f"rc={f.rc}"
    healed = reason == SELF_HEALED_REASON
    ok_out, fail_out = (DONE_STATE, 0, ""), (ERROR_STATE, f.rc if f.rc else 1, error)
    state, rc, err = ok_out if reason in _DONE_REASONS else fail_out
    return TurnOutcomeResolution(state, rc, err, healed, reason, healed or bool(f.result_error))
@dataclass(frozen=True)
class RetryDecision:
    """Решение о повторе запроса после обрыва стрима."""
    can_retry: bool
    keep_hot_session: bool
    reason: str
    attempt_budget_s: float = 0.0
RETRY_BLOCKED: Final[RetryDecision] = RetryDecision(False, False, RETRY_BLOCKED_REASON)
@dataclass(frozen=True)
class _RetryFacts:
    error_text: str
    delivered: bool
    had_tool_side_effects: bool = False
    attempt: int = 1
    max_attempts: int | None = None
    source: str = CLI_ERROR_SOURCE
    elapsed_s: float = 0.0
    budget_config: RetryBudgetConfig | None = None
def _valid_retry_facts(f: _RetryFacts) -> bool:
    """Проверить типы аргументов legacy-контракта; границы проверяет бюджетный контроллер."""
    typed = ((f.attempt, int), (f.elapsed_s, (int, float)), (f.delivered, bool), (f.had_tool_side_effects, bool),
             (f.max_attempts, int | None), (f.budget_config, RetryBudgetConfig | None), (f.error_text, str), (f.source, str))
    exact = all(isinstance(value, expected) for value, expected in typed)
    checks = (0.0 <= f.elapsed_s <= MAX_ELAPSED_S, 0 <= f.attempt, not isinstance(f.attempt, bool), not isinstance(f.elapsed_s, bool), not isinstance(f.max_attempts, bool))
    return exact and all(checks)
def _resolve_retry_cfg(f: _RetryFacts) -> RetryBudgetConfig | None:
    """Проверить конфигурацию повтора; явный legacy-лимит только сужает типизированный бюджет."""
    try:
        valid = validate_retry_config(f.budget_config or DEFAULT_RETRY_CONFIG)
        narrowed = valid if f.max_attempts is None else replace(valid, max_attempts=min(f.max_attempts, valid.max_attempts))
        return validate_retry_config(narrowed)
    except (ValueError, TypeError):
        return None
def _retry_with_budget(f: _RetryFacts) -> RetryDecision:
    """Повтор разрешён только в пределах бюджета, суженного legacy-лимитом."""
    cfg = _resolve_retry_cfg(f)
    result = replace(RETRY_BLOCKED, keep_hot_session=True)
    if cfg is not None:
        try:
            decision = compute_attempt_decision(cfg, f.attempt, float(f.elapsed_s))
        except (ValueError, TypeError, OverflowError):
            result = RETRY_BLOCKED
        else:
            result = RetryDecision(True, True, TRANSIENT_RETRY_REASON, decision.attempt_budget_s) if decision.allow_retry else result
    return result
def evaluate_stream_retry_eligibility(**kw: object) -> RetryDecision:
    """Оценить допустимость повтора стрима; горячая сессия живёт при тихом транзиентном обрыве."""
    try:
        f = _RetryFacts(**kw)  # pyright: ignore[reportArgumentType]  # Legacy kwargs без Any.
    except TypeError:
        return RETRY_BLOCKED
    quiet = _valid_retry_facts(f) and is_transient_stream_interruption(f.error_text, source=f.source) and not f.had_tool_side_effects
    result = replace(RETRY_BLOCKED, keep_hot_session=quiet)
    if quiet and not f.delivered:
        result = _retry_with_budget(f)
    return result

@dataclass(frozen=True)
class GracefulInterruptionDecision:
    """Решение о мягком закрытии стрима с частичным ответом."""
    should_gracefully_close: bool
    notice_text: str
    target_channel: str
    finish_reason: str
    reason: str

@dataclass(frozen=True)
class _GracefulFacts:
    error_text: str | None
    delivered_content: bool = False
    delivered_reasoning: bool = False
    delivered_tool_calls: bool = False
    has_unclosed_tool_call: bool = False
    graceful_enabled: bool = True
    source: str = CLI_ERROR_SOURCE
    notice_text: str = DEFAULT_INTERRUPTION_NOTICE

def evaluate_graceful_interruption(**kw: object) -> GracefulInterruptionDecision:
    """Мягко закрывает стрим с `finish_reason=stop`, если выдан частичный ответ без tool_calls."""
    f = _GracefulFacts(**kw)  # pyright: ignore[reportArgumentType]  # Legacy kwargs без Any.
    transient = is_transient_stream_interruption(f.error_text, source=f.source)
    partial = f.delivered_content or f.delivered_reasoning
    ok = f.graceful_enabled and partial and transient and not f.delivered_tool_calls and not f.has_unclosed_tool_call
    channel = "content" if f.delivered_content else "reasoning_content"
    return GracefulInterruptionDecision(ok, f.notice_text if ok else "", channel if ok else "none",
                                        "stop" if ok else "error", "graceful_partial_close" if ok else "graceful_blocked")
