"""Чистый agent-agnostic фасад транзиентного и доказанного каузального восстановления."""

from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Any, cast

import core.turn_outcome_policy as causal

_TRANSIENT_PHRASES: tuple[str, ...] = (
    "stream was interrupted",
    "please continue the task you were working on",
    "rst_stream",
    "http/2 stream",
    "connection reset",
    "eof occurred in violation of protocol",
    "broken pipe",
    "incomplete chunked read",
    "peer closed connection",
    "server disconnected",
    "currently unavailable",
)

TRANSIENT_STREAM_INTERRUPTION_RE = re.compile(
    "|".join(re.escape(p) for p in _TRANSIENT_PHRASES), re.IGNORECASE
)

DEFAULT_INTERRUPTION_NOTICE = (
    "\n\n[⚠️ Поток прерван транзиентным сбоем транспорта; показан частичный ответ.]"
)

def is_transient_stream_interruption(text: str | None, *, source: str = "cli_error") -> bool:
    """Транзиентный ли обрыв; текст модели (`model_content`) никогда не классифицируется."""
    haystack = "" if source == "model_content" else text or ""
    return bool(TRANSIENT_STREAM_INTERRUPTION_RE.search(haystack))

class InterruptionTailState:
    """Миксин транскрипт-хвоста: факты о финальном planner-шаге и транзиентных обрывах."""

    final_planner: bool = False
    final_planner_content: str = ""
    last_planner_step_index: int = -1
    last_error_step_index: int = -1
    had_transient_error: bool = False
    last_error_sha256: str = ""
    last_error_length: int = 0
    last_error_attempt: int = -1
    error_from_structured_record: bool = False
    last_completion_attempt: int = -1
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
    """Ошибка хода на done: погашенный активностью сбой возвращается при `status=ERROR`."""
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
    """Итог разбора done: `state` — `done` | `agy_error`; `final` — решение окончательно."""

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
    has_unclosed_tool_call: bool = False
    self_heal_enabled: bool = True
    causal_input: causal.CausalOutcomeInput | None = None

_DONE_REASONS = {"clean_done": False, "self_healed_after_transient_interruption": True}

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
    healed = _DONE_REASONS.get(reason, False)
    ok_out, fail_out = ("done", 0, ""), ("agy_error", f.rc if f.rc else 1, error)
    state, rc, err = ok_out if reason in _DONE_REASONS else fail_out
    return TurnOutcomeResolution(state, rc, err, healed, reason, any((healed, f.result_error)))

@dataclass(frozen=True)
class RetryDecision:
    """Решение о повторе запроса после обрыва стрима."""

    can_retry: bool
    keep_hot_session: bool
    reason: str

@dataclass(frozen=True)
class _RetryFacts:
    error_text: str
    delivered: bool
    had_tool_side_effects: bool = False
    attempt: int = 1
    max_attempts: int = 2
    source: str = "cli_error"

def evaluate_stream_retry_eligibility(**kw: Any) -> RetryDecision:  # pyright: ignore[reportAny, reportExplicitAny]
    """Повтор допустим только для транзиентного обрыва до выдачи данных и без побочных эффектов."""
    f = _RetryFacts(**kw)  # pyright: ignore[reportAny]  # Неизменяемый legacy-контракт kwargs.
    trans = is_transient_stream_interruption(f.error_text, source=f.source)
    quiet = trans and not f.had_tool_side_effects
    can = all((quiet, not f.delivered, f.attempt < f.max_attempts))
    return RetryDecision(can, quiet, "transient_pre_delivery_retry" if can else "retry_blocked")

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
