# pyright: reportAny=false, reportExplicitAny=false
# ruff: noqa: I001
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from math import isfinite
from typing import Any, Final

from core.route_health_policy import FailureCategory, RetryBudgetConfig, classify_provider_failure, compute_attempt_decision, validate_retry_config  # fmt: skip  # noqa: E501,I001

_TRANSIENT_PHRASES: tuple[str, ...] = ("stream was interrupted", "please continue the task you were working on", "rst_stream", "http/2 stream", "connection reset", "eof occurred in violation of protocol", "broken pipe", "incomplete chunked read", "peer closed connection", "server disconnected", "currently unavailable")  # fmt: skip  # noqa: E501

TRANSIENT_STREAM_INTERRUPTION_RE = re.compile(
    "|".join(re.escape(p) for p in _TRANSIENT_PHRASES), re.IGNORECASE
)
_FATAL_STATUS_RE = re.compile(
    r"(?i)\b(?:http(?:[/\s]*\d(?:\.\d)?)?\s+(?!429\b)4\d\d|status(?:\s+code)?[\s:=]+(?!429\b)4\d\d|bad\s+request|unauthorized|forbidden|not\s+found|method\s+not\s+allowed|conflict|unprocessable)\b"
)

DEFAULT_INTERRUPTION_NOTICE = "\n\n[⚠️ Поток прерван транзиентным сбоем транспорта; показан частичный ответ.]"  # fmt: skip  # noqa: E501


def is_transient_stream_interruption(
    text: str | None, *, source: str = "cli_error"
) -> bool:
    """Распознать транзиентный транспортный обрыв."""
    if not isinstance(text, str) or source == "model_content" or len(text) > 4096:
        return False
    haystack = text.replace("\x00", " ")
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

    final_planner: bool = False
    final_planner_content: str = ""
    last_planner_step_index: int = -1
    last_error_step_index: int = -1
    had_transient_error: bool = False

    def note_error_record(
        self, rtype: str, rec: dict[str, object], idx: int | None
    ) -> None:
        """ERROR_MESSAGE сбрасывает финальный planner-шаг и фиксирует транзиентность."""
        if rtype == "ERROR_MESSAGE":
            texts = (rec.get(key) for key in ("content", "message", "error"))
            self.final_planner, self.final_planner_content = False, ""
            self.last_error_step_index = max(self.last_error_step_index, idx or 0)
            self.had_transient_error |= is_transient_stream_interruption(
                str(next(filter(None, texts), ""))
            )

    def note_planner_record(self, rec: dict[str, object], idx: int) -> None:
        """Зафиксировать финальный planner без tool calls."""
        content = rec.get("content")
        has_tools = bool(rec.get("tool_calls"))
        text = content if isinstance(content, str) else ""
        done = str(rec.get("status", "DONE")).upper() == "DONE"
        if all((text.strip(), not has_tools, done)):
            self.final_planner, self.final_planner_content = True, text
            self.last_planner_step_index = max(self.last_planner_step_index, idx)
        if has_tools:
            self.final_planner, self.final_planner_content = False, ""


def settle_error(error: str, cleared: str, status: str) -> str:
    """Вернуть ошибку хода на done."""
    return error or (cleared if status == "ERROR" else "")


def trusted_final_text(final_text: str, error: str, tail: object) -> str:
    """Текст для reconcile: при неснятой ошибке — только финальный planner хвоста."""
    planner = str(getattr(tail, "final_planner_content", ""))
    healed = (final_text or planner) if getattr(tail, "final_planner", False) else ""
    trusted = healed if error else final_text
    return trusted


def tail_turn_facts(tail: object, cleared_error: str = "") -> dict[str, Any]:
    """Собрать факты хода из транскрипт-хвоста."""
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


def resolve_done_turn_outcome(**kw: Any) -> TurnOutcomeResolution:
    """Итоговое состояние хода и самоисцеление после транзиентного обрыва.

    Keyword-аргументы `_TurnFacts` (обязательные: `rc`, `result_error`, `result_status`,
    `final_text`, `emitted_text`); неизвестный аргумент — `TypeError`.
    """
    f = _TurnFacts(**kw)
    transient = is_transient_stream_interruption(f.result_error)
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
    return TurnOutcomeResolution(
        state, rc, err, healed, reason, any((healed, f.result_error))
    )


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


def evaluate_stream_retry_eligibility(**kw: Any) -> RetryDecision:
    """Оценить допустимость повтора стрима."""
    try:
        f = _RetryFacts(**kw)
    except TypeError:
        return RetryDecision(False, False, "retry_blocked", 0.0)
    valid_types = all((isinstance(f.error_text, str), isinstance(f.source, str), type(f.delivered) is bool, type(f.had_tool_side_effects) is bool, type(f.attempt) is int, type(f.max_attempts) is int, type(f.elapsed_s) in (int, float), f.budget_config is None or isinstance(f.budget_config, RetryBudgetConfig)))  # pyright: ignore[reportUnnecessaryIsInstance]  # fmt: skip  # noqa: E501
    if not valid_types:
        return RetryDecision(False, False, "retry_blocked", 0.0)
    valid = all((isfinite(f.elapsed_s), f.elapsed_s >= 0.0, 0 <= f.attempt < f.max_attempts, f.max_attempts > 0))  # fmt: skip  # noqa: E501
    if not valid:
        return RetryDecision(False, False, "retry_blocked", 0.0)
    cfg = _resolve_retry_cfg(f)
    if cfg is None:
        return RetryDecision(False, False, "retry_blocked", 0.0)
    trans = is_transient_stream_interruption(f.error_text, source=f.source)
    quiet = all((trans, not f.had_tool_side_effects))
    cat = (classify_provider_failure(0, f.error_text).category, FailureCategory.CAPACITY_EXHAUSTED)[trans]  # fmt: skip  # noqa: E501
    adm = compute_attempt_decision(cfg, f.attempt, float(f.elapsed_s), cat)
    can = all((quiet, not f.delivered, f.attempt < cfg.max_attempts, adm.allow_retry))
    out = ((False, quiet, "retry_blocked", 0.0), (True, quiet, "transient_pre_delivery_retry", adm.attempt_budget_s))[can]  # fmt: skip  # noqa: E501
    return RetryDecision(*out)


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


def evaluate_graceful_interruption(**kw: Any) -> GracefulInterruptionDecision:
    """Оценить мягкое закрытие частичного стрима."""
    f = _GracefulFacts(**kw)
    transient = is_transient_stream_interruption(f.error_text, source=f.source)
    partial = any((f.delivered_content, f.delivered_reasoning))
    clear = not any((f.delivered_tool_calls, f.has_unclosed_tool_call))
    ok = all((f.graceful_enabled, partial, clear, transient))
    channel = "content" if f.delivered_content else "reasoning_content"
    closed = (ok, f.notice_text, channel, "stop", "graceful_partial_close")
    blocked = (ok, "", "none", "error", "graceful_blocked")
    return GracefulInterruptionDecision(*(closed if ok else blocked))
