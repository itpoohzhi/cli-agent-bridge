"""Чистый agent-agnostic фасад транзиентного и доказанного каузального восстановления."""
# pyright: reportPrivateUsage=false

from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Any, Final, cast

import core.turn_outcome_policy as causal
from core.route_health_policy import FailureCategory, RetryBudgetConfig, _normalize_diagnostic_text, classify_provider_failure, compute_attempt_decision, validate_retry_config  # fmt: skip  # noqa: E501,I001

_TRANSIENT_PHRASES: tuple[str, ...] = ("stream was interrupted", "please continue the task you were working on", "rst_stream", "http/2 stream", "connection reset", "eof occurred in violation of protocol", "broken pipe", "incomplete chunked read", "peer closed connection", "server disconnected", "currently unavailable")  # fmt: skip  # noqa: E501

TRANSIENT_STREAM_INTERRUPTION_RE = re.compile(
    "|".join(re.escape(p) for p in _TRANSIENT_PHRASES), re.IGNORECASE
)
_FATAL_STATUS_RE = re.compile(
    r"(?i)(?:\bhttp(?:[/\s]*\d(?:\.\d)?)?\s*(?!429\b)4\d\d\b|(?:\\*[\"'])?\bstatus(?:[_ -]?code)?\b(?:\\*[\"'])?\s*[:=]\s*(?!429\b)4\d\d\b|\b(?:bad\s+request|unauthorized|forbidden|not\s+found|method\s+not\s+allowed|conflict|unprocessable)\b)"  # noqa: E501
)

DEFAULT_INTERRUPTION_NOTICE = "\n\n[⚠️ Поток прерван транзиентным сбоем транспорта; показан частичный ответ.]"  # fmt: skip  # noqa: E501

def is_transient_stream_interruption(text: str | None, *, source: str = "cli_error") -> bool:
    """Распознать транзиентный транспортный обрыв."""
    if not isinstance(text, str) or source != "cli_error" or len(text) > 4096:
        return False
    haystack = _normalize_diagnostic_text(text, fail_closed=False)
    if re.search(r"(?:\\+|%)[uU][0-9a-fA-F]{4,8}|\\+(?:x[0-9a-fA-F]{2}|[0-7]{1,3})|%[0-9a-fA-F]{2}|&#[xX]?[0-9a-fA-F]+", haystack) or re.search(r"(?:%25)+[0-9a-fA-F]{2}", text, re.IGNORECASE): return False  # fmt: skip  # noqa: E501,E701
    if not TRANSIENT_STREAM_INTERRUPTION_RE.search(haystack):
        return False
    if _FATAL_STATUS_RE.search(haystack):
        return False
    category = classify_provider_failure(0, haystack).category
    blocked = (
        FailureCategory.AUTH_REFRESH_EXHAUSTED,
        FailureCategory.LIMIT_BLOCKED,
        FailureCategory.UPSTREAM_TLS_STALL,
    )
    return category not in blocked

class InterruptionTailState:
    """Факты о финальном planner-шаге и транзиентных обрывах."""

    final_planner: bool = False; final_planner_content: str = ""  # fmt: skip  # noqa: E702
    last_planner_step_index: int = -1; last_error_step_index: int = -1  # fmt: skip  # noqa: E702
    had_transient_error: bool = False; last_error_sha256: str = ""  # fmt: skip  # noqa: E702
    last_error_length: int = 0; last_error_attempt: int = -1  # fmt: skip  # noqa: E702
    error_from_structured_record: bool = False; last_completion_attempt: int = -1  # fmt: skip  # noqa: E702
    has_open_planner_after_completion: bool = False

    def note_error_record(
        self, rtype: str | int, rec: dict[str, object] | str = "",
        idx: int | None = None, **kw: object,
    ) -> None:
        """Принимает legacy (rtype, rec, idx) либо (seq, text=..., attempt=0)."""
        if isinstance(rtype, int) or rtype == "ERROR_MESSAGE":
            text = kw.get("text", rec)
            if isinstance(rec, dict):
                texts = (rec.get(key) for key in ("content", "message", "error"))
                text = next(filter(None, texts), "")
            text = str(text)
            seq = rtype if isinstance(rtype, int) else idx or 0
            self.final_planner, self.final_planner_content = False, ""
            self.has_open_planner_after_completion = self.last_planner_step_index >= 0
            self.had_transient_error |= is_transient_stream_interruption(text)
            if seq >= self.last_error_step_index:
                self.last_error_step_index = seq
                self.last_error_sha256 = causal.error_identity_digest(text)
                self.last_error_length = len(causal.normalize_error_identity(text))
                attempt = kw.get("attempt", 0)
                self.last_error_attempt = attempt if type(attempt) is int else -1
                self.error_from_structured_record = True

    def note_planner_record(self, rec: dict[str, object], idx: int, *, attempt: int = 0) -> None:
        """Непустой DONE без tools завершает шаг; любой новый открытый шаг отменяет финал."""
        content = rec.get("content")
        has_tools = bool(rec.get("tool_calls"))
        text = content if isinstance(content, str) else ""
        done = str(rec.get("status", "DONE")).upper() == "DONE"
        self.final_planner = all((text.strip(), not has_tools, done))
        self.has_open_planner_after_completion = not self.final_planner
        self.final_planner_content = text if self.final_planner else ""
        if self.final_planner:
            self.last_planner_step_index = max(self.last_planner_step_index, idx)
            self.last_completion_attempt = attempt

@dataclass(frozen=True)
class TailCausalFacts:
    """Замороженный снимок скалярного доказательства хвоста, без текста ошибки."""

    error: causal.CausalErrorIdentity; error_from_structured_record: bool  # fmt: skip  # noqa: E702
    completion: causal.CausalCompletionFacts; has_late_error_or_open_step: bool  # fmt: skip  # noqa: E702

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
    return TailCausalFacts(
        error, bool(get("error_from_structured_record", False)),
        completion, late or bool(get("has_open_planner_after_completion", False)),
    )

def evaluate_done_causal_recovery(
    causal_input: causal.CausalOutcomeInput, error: str | None = None,
) -> causal.CausalOutcomeDecision:
    """Одно решение разрешает reconcile и снятие ошибки; эхо берётся целиком."""
    if error is not None:
        echo = replace(causal_input.error, result_error_sha256=causal.error_identity_digest(error))
        causal_input = replace(causal_input, error=echo)
    return causal.evaluate_causal_turn_recovery(causal_input)

def settle_error(error: str, cleared: str, status: str) -> str:
    """Вернуть ошибку хода на done."""
    return error or (cleared if status == "ERROR" else "")

def trusted_final_text(
    final_text: str, error: str, tail: object,
    causal_input: causal.CausalOutcomeInput | None = None,
) -> str:
    """Текст для reconcile: при неснятой ошибке — только финальный planner хвоста."""
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
    trusted = healed if error else final_text
    return trusted

def tail_turn_facts(tail: object, cleared_error: str = "") -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
    """Факты хода из транскрипт-хвоста для `resolve_done_turn_outcome` (без хвоста — нейтральны)."""
    seen = getattr(tail, "had_transient_error", False)
    return {
        "completion_done_without_tools": bool(getattr(tail, "final_planner", False)),
        "last_completion_seq": getattr(tail, "last_planner_step_index", -1),
        "last_error_seq": getattr(tail, "last_error_step_index", -1),
        "drain_complete": getattr(tail, "drain_outcome", "") != "timeout",
        "had_transient_error": any((seen, cleared_error)),
    }

@dataclass(frozen=True)
class TurnOutcomeResolution:
    """Итог разбора done."""

    state: str; rc: int; error: str  # fmt: skip  # noqa: E702
    self_healed: bool; reason: str; final: bool  # fmt: skip  # noqa: E702

@dataclass(frozen=True)
class _TurnFacts:
    rc: int; result_error: str; result_status: str  # fmt: skip  # noqa: E702
    final_text: str; emitted_text: str  # fmt: skip  # noqa: E702
    completion_done_without_tools: bool = False; last_completion_seq: int = -1; last_error_seq: int = -1  # fmt: skip  # noqa: E501,E702
    drain_complete: bool = False; had_transient_error: bool = False  # fmt: skip  # noqa: E702
    has_unclosed_tool_call: bool = False; self_heal_enabled: bool = True  # fmt: skip  # noqa: E702
    causal_input: causal.CausalOutcomeInput | None = None

_DONE_REASONS: Final[frozenset[str]] = frozenset(
    ("clean_done", "self_healed_after_transient_interruption")
)

def _heal_blocker(f: _TurnFacts, transient_error: bool) -> str:
    """Первая причина, запрещающая самоисцеление (пусто — разрешено)."""
    checks = (
        ("self_heal_disabled", not f.self_heal_enabled),
        ("non_transient_result_error", all((f.result_error, not transient_error))),
        ("unclassified_nonzero_rc", not any((f.had_transient_error, transient_error))),
        ("drain_incomplete", not f.drain_complete),
        ("unclosed_tool_call", f.has_unclosed_tool_call),
    )
    return next((reason for reason, hit in checks if hit), "")

def _is_recovered(f: _TurnFacts) -> bool:
    """Финальный planner без tool_calls позже последней ошибки и с непустым телом."""
    has_body = any((f.final_text.strip(), f.emitted_text.strip()))
    later = f.last_completion_seq > max(f.last_error_seq, -1)
    return all((f.completion_done_without_tools, later, has_body))

def resolve_done_turn_outcome(**kw: Any) -> TurnOutcomeResolution:  # pyright: ignore[reportAny, reportExplicitAny]
    """Сохраняет legacy kwargs `_TurnFacts`; неизвестный аргумент даёт TypeError."""
    f = _TurnFacts(**kw)  # pyright: ignore[reportAny]  # Legacy kwargs сохраняются без изменения типов.
    transient = is_transient_stream_interruption(f.result_error)
    if f.result_error and not transient and f.causal_input is not None:
        decision = evaluate_done_causal_recovery(f.causal_input, f.result_error)
        consistent = all((f.self_heal_enabled, not f.has_unclosed_tool_call,
                          f.rc == f.causal_input.terminal.process.returncode,
                          bool(f.final_text.strip() or f.emitted_text.strip())))
        healed = decision.clear_error and consistent
        reason = decision.reason if not decision.recovered or consistent else "inconsistent_causal_facts"
        return TurnOutcomeResolution(
            "done" if healed else "agy_error", 0 if healed else f.rc or 1,
            "" if healed else f.result_error, healed, reason, True,
        )
    clean = all((f.rc == 0, not f.result_error, f.result_status != "ERROR"))
    blocker = _heal_blocker(f, transient)
    reasons = (
        ("clean_done", clean),
        (blocker, bool(blocker)),
        ("self_healed_after_transient_interruption", _is_recovered(f)),
        ("not_recovered", True),
    )
    reason = next(name for name, hit in reasons if hit)
    error = f.result_error if f.result_error else f"rc={f.rc}"
    healed = reason == "self_healed_after_transient_interruption"
    ok_out, fail_out = ("done", 0, ""), ("agy_error", f.rc if f.rc else 1, error)
    state, rc, err = ok_out if reason in _DONE_REASONS else fail_out
    return TurnOutcomeResolution(state, rc, err, healed, reason, any((healed, f.result_error)))

@dataclass(frozen=True)
class RetryDecision:
    """Решение о повторе запроса после обрыва стрима."""

    can_retry: bool; keep_hot_session: bool; reason: str  # fmt: skip  # noqa: E702
    attempt_budget_s: float = 0.0

@dataclass(frozen=True)
class _RetryFacts:
    error_text: str; delivered: bool; had_tool_side_effects: bool = False  # fmt: skip  # noqa: E702
    attempt: int = 1; max_attempts: int = 2; source: str = "cli_error"  # fmt: skip  # noqa: E702
    elapsed_s: float = 0.0
    budget_config: RetryBudgetConfig | None = None

def _resolve_retry_cfg(f: _RetryFacts) -> RetryBudgetConfig | None:
    """Проверить и ограничить конфигурацию повтора без исключений наружу."""
    base = f.budget_config or RetryBudgetConfig(max_attempts=f.max_attempts)
    try:
        valid = validate_retry_config(base)
    except ValueError:
        return None
    return replace(valid, max_attempts=min(f.max_attempts, valid.max_attempts))

def evaluate_stream_retry_eligibility(**kw: Any) -> RetryDecision:  # pyright: ignore[reportAny, reportExplicitAny]
    """Оценить допустимость повтора стрима."""
    try:
        f = _RetryFacts(**kw)  # pyright: ignore[reportAny]  # Неизменяемый legacy-контракт kwargs.
    except TypeError:
        return RetryDecision(False, False, "retry_blocked", 0.0)
    valid_types = all((isinstance(f.error_text, str), isinstance(f.source, str), type(f.delivered) is bool, type(f.had_tool_side_effects) is bool, type(f.attempt) is int, type(f.max_attempts) is int, type(f.elapsed_s) in (int, float), f.budget_config is None or isinstance(f.budget_config, RetryBudgetConfig)))  # pyright: ignore[reportUnnecessaryIsInstance]  # fmt: skip  # noqa: E501
    if not valid_types:
        return RetryDecision(False, False, "retry_blocked", 0.0)
    valid = all((0.0 <= f.elapsed_s <= 1e308, 0 <= f.attempt, f.max_attempts > 0))  # fmt: skip  # noqa: E501
    if not valid:
        return RetryDecision(False, False, "retry_blocked", 0.0)
    cfg = _resolve_retry_cfg(f)
    if cfg is None:
        return RetryDecision(False, False, "retry_blocked", 0.0)
    trans = is_transient_stream_interruption(f.error_text, source=f.source)
    quiet = all((trans, not f.had_tool_side_effects))
    if not quiet or f.delivered:
        return RetryDecision(False, quiet, "retry_blocked", 0.0)
    adm = compute_attempt_decision(cfg, f.attempt, float(f.elapsed_s))
    if not all((f.attempt < cfg.max_attempts, adm.allow_retry)):
        return RetryDecision(False, quiet, "retry_blocked", 0.0)
    return RetryDecision(True, quiet, "transient_pre_delivery_retry", adm.attempt_budget_s)  # fmt: skip  # noqa: E501

@dataclass(frozen=True)
class GracefulInterruptionDecision:
    """Решение о мягком закрытии стрима с частичным ответом."""

    should_gracefully_close: bool; notice_text: str; target_channel: str  # fmt: skip  # noqa: E702
    finish_reason: str; reason: str  # fmt: skip  # noqa: E702

@dataclass(frozen=True)
class _GracefulFacts:
    error_text: str | None; delivered_content: bool = False  # fmt: skip  # noqa: E702
    delivered_reasoning: bool = False; delivered_tool_calls: bool = False  # fmt: skip  # noqa: E702
    has_unclosed_tool_call: bool = False; graceful_enabled: bool = True  # fmt: skip  # noqa: E702
    source: str = "cli_error"
    notice_text: str = DEFAULT_INTERRUPTION_NOTICE

def evaluate_graceful_interruption(**kw: Any) -> GracefulInterruptionDecision:  # pyright: ignore[reportAny, reportExplicitAny]
    """Мягко закрывает стрим с `finish_reason=stop`, если выдан частичный ответ без tool_calls."""
    f = _GracefulFacts(**kw)  # pyright: ignore[reportAny]  # Неизменяемый legacy-контракт kwargs.
    transient = is_transient_stream_interruption(f.error_text, source=f.source)
    partial = any((f.delivered_content, f.delivered_reasoning))
    clear = not any((f.delivered_tool_calls, f.has_unclosed_tool_call))
    ok = all((f.graceful_enabled, partial, clear, transient))
    channel = "content" if f.delivered_content else "reasoning_content"
    closed = (ok, f.notice_text, channel, "stop", "graceful_partial_close")
    blocked = (ok, "", "none", "error", "graceful_blocked")
    return GracefulInterruptionDecision(*(closed if ok else blocked))
