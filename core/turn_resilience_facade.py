"""Тонкий фасад устойчивости хода (AD-001..AD-009): связка монолита моста с чистыми политиками.

В `bridges/agy-bridge/server.py` остаются лишь делегирующие вызовы; вся оркестрация здесь.
Каждая точка читает kill-switch флаги заново (`read_recovery_flags`), а при выключенном флаге
возвращает ровно базовое значение (побайтная эквивалентность). Агент-агностично: решения
опираются на факты хода (доставка клиенту, класс сбоя, шаги), не на имя CLI.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Any

from core.content_delivery_tracker import ContentDeliveryTracker
from core.failure_window import FailureWindow
from core.function_call_recovery import is_recoverable_function_call_error
from core.hot_session_retention_policy import NO_CONVERSATION, should_retain_hot_session
from core.invisible_retry_policy import compute_pause_s, may_retry_invisibly
from core.recovery_flags import read_recovery_flags, read_retry_budget_config, read_transport_failure_config
from core.stream_interruption_recovery import is_transient_stream_interruption
from core.strict_tool_call_parser import StrictToolCallParser, calls_to_markup
from core.tool_call_completion_tracker import ToolCallCompletionTracker
from core.tool_call_recovery_policy import evaluate_recovery
from core.transport_failure_classifier import classify_transport_failure
from core.transport_failure_contracts import DeliveryFacts, FailureKind, HotSessionFacts, RecoveryFlagSnapshot, RetryAttemptState
from core.turn_resolution_report import (
    build_turn_resolution_report,
    flags_snapshot_dict,
    format_turn_resolved,
    health_fields as _report_health_fields,
)
from core.vendor_phrase_sanitizer import mask_vendor_phrases

TRACKER_ATTR = "_resilience_step_tracker"
_ATTEMPT_KEY = "_resilience_attempts"
_RECOVERY_KEY = "_resilience_recovery_done"
_CLOCK_KEY = "resilience_clock"
_WINDOW = FailureWindow()
Log = Callable[[str], object]


def reset_failure_window() -> None:
    """Сбросить окно недавних сбоев процесса (тесты, рестарт политики)."""
    _WINDOW.clear()


def _flags() -> RecoveryFlagSnapshot:
    return read_recovery_flags()


def _now(ctx: Mapping[str, object]) -> float:
    clock = ctx.get(_CLOCK_KEY)
    return float(clock()) if callable(clock) else time.monotonic()


def _say(log: Log, reason: str, attempts: int = 0, kind: FailureKind = FailureKind.UNCLASSIFIED) -> None:
    """Одна строка `turn-resolved` в лог (только если включён хотя бы один флаг)."""
    flags = _flags()
    if any(vars(flags).values()):
        spoken = reason.replace("_", ".")  # токены <24 символов: LONG_TOKEN_RE логов их не маскирует
        log(format_turn_resolved(build_turn_resolution_report(spoken, flags, attempts, kind)))


def go_transient(text: object) -> bool:
    """AD-001: Go-форма сетевого сбоя (`: EOF`, TLS timeout…) транзиентна; FATAL — вето."""
    if not _flags().transport_failure_classifier:
        return False
    verdict = classify_transport_failure(text, read_transport_failure_config())
    return verdict.kind is FailureKind.NETWORK_TRANSIENT


def _facts(ctx: Mapping[str, object]) -> DeliveryFacts:
    tracker = ctx.get("delivery_tracker")
    return tracker.snapshot() if isinstance(tracker, ContentDeliveryTracker) else DeliveryFacts()


def _network_transient(out: Mapping[str, object]) -> bool:
    """Сбой транспорта (а не модели/разметки): Go-формы классификатора либо общее ядро replay."""
    text = out.get("err")
    kind = classify_transport_failure(text, read_transport_failure_config()).kind
    return kind is FailureKind.NETWORK_TRANSIENT or (isinstance(text, str) and is_transient_stream_interruption(text))


def delivered_after_commit(ctx: Mapping[str, object], out: Mapping[str, object], delivered: bool) -> bool:
    """AD-002: при сетевом сбое keepalive/role-дельта — не доставка. Иначе — прежний commit.

    Флаг выкл., сбой не сетевой (напр. ошибка functionCall) или recovery уже отвергнут → база:
    `stream_committed` запрещает невидимый повтор (INV-S7, поведение при REJECT равно базе).
    """
    activity = bool(ctx.get("tool_activity") or out.get("tool_events"))
    tracker = ctx.get("delivery_tracker")
    relaxed = _flags().keepalive_only_preretry and isinstance(tracker, ContentDeliveryTracker)
    if not relaxed or ctx.get(_RECOVERY_KEY) or not _network_transient(out):
        return delivered or bool(ctx.get("stream_committed") or activity)
    return delivered or _facts(ctx).delivered or activity


def _elapsed_s(ctx: Mapping[str, object], now: float) -> float:
    start = ctx.get("t_req_start")
    return max(0.0, now - float(start)) if isinstance(start, (int, float)) else 0.0


def _last_attempt_s(out: Mapping[str, object]) -> float:
    value = out.get("duration_s")
    return float(value) if isinstance(value, (int, float)) and value > 0 else 0.0


def take(ctx: dict[str, Any], out: Mapping[str, object], take_fn: Callable[[], bool], log: Log) -> bool:
    """AD-003: гейт повтора по бюджету и окну сбоев; флаг выкл. → прежний `take_fn()`."""
    if not _flags().retry_window_pause:
        return take_fn()
    now = _now(ctx)
    attempt = int(ctx.get(_ATTEMPT_KEY, 0)) + 1
    ctx[_ATTEMPT_KEY] = attempt
    state = RetryAttemptState(attempt, _elapsed_s(ctx, now), _last_attempt_s(out), _WINDOW.record(now))
    decision = may_retry_invisibly(_facts(ctx), read_retry_budget_config(), state)
    _say(log, f"retry_gate:{decision.reason}", attempt)
    return decision.allowed and take_fn()


def pause_s(attempt: int, base: float, cap: float) -> float:
    """AD-003: пауза = full jitter + добавка коррелированного окна; флаг выкл. → `base`."""
    if not _flags().retry_window_pause:
        return base
    jitter = base / cap if cap > 0 else 1.0
    state = RetryAttemptState(attempt, 0.0, 0.0, _WINDOW.recent_count(time.monotonic()), jitter)
    return compute_pause_s(read_retry_budget_config(), state)


def _retain(out: Mapping[str, object]) -> bool:
    kind = classify_transport_failure(out.get("err"), read_transport_failure_config()).kind
    turns = out.get("num_turns")
    conversation = str(out.get("conversation_id") or NO_CONVERSATION)
    facts = HotSessionFacts(kind, turns if type(turns) is int else 0, conversation)
    return should_retain_hot_session(facts).retain


def invalidate(ctx: Mapping[str, Any], out: Mapping[str, object], invalidate_fn: Callable[[Any, Any], object], log: Log) -> None:
    """AD-004: немутированную сессию при транзиентном сбое сохранить; иначе — как в базе."""
    if _flags().hot_session_retain_on_transient and _retain(out):
        _say(log, "hot_session_retained", 0, FailureKind.NETWORK_TRANSIENT)
        return
    invalidate_fn(ctx["sess_key"], ctx["conversation_id"])


def masked_error_body(inner: Callable[..., Any]) -> Callable[..., Any]:
    """AD-006: user-visible `message`/`detail` тела ошибки без `Retries remaining: N`.

    Оборачивает сборщик тела ошибки моста: вход парсера/классификатора не затрагивается, а при
    выключенном флаге возвращается исходный объект (побайтная эквивалентность базе).
    """

    def build(out: Any, resilience: Any = None) -> Any:
        body = inner(out, resilience)
        if not isinstance(body, dict) or not _flags().vendor_retry_phrase_mask:
            return body
        masked = ("message", "detail")
        return {k: mask_vendor_phrases(v) if k in masked and isinstance(v, str) else v for k, v in body.items()}

    return build


def _tracker_of(tail: object) -> ToolCallCompletionTracker:
    tracker = getattr(tail, TRACKER_ATTR, None)
    if not isinstance(tracker, ToolCallCompletionTracker):
        tracker = ToolCallCompletionTracker()
        setattr(tail, TRACKER_ATTR, tracker)
    return tracker


def observe_record(tail: object, rec: Mapping[str, object], idx: int | None) -> None:
    """AD-005: запомнить шаги транскрипта (ошибка/planner) для recovery; флаг выкл. → no-op."""
    kind = str(rec.get("type") or "")
    if idx is None or kind not in ("PLANNER_RESPONSE", "ERROR_MESSAGE") or not _flags().toolcall_error_recovery:
        return
    if kind == "PLANNER_RESPONSE":
        _tracker_of(tail).note_planner(idx, str(rec.get("content") or ""))
        return
    text = next(filter(None, (rec.get(key) for key in ("content", "message", "error"))), "")
    _tracker_of(tail).note_error(idx, str(text))


def _known_names(ctx: Mapping[str, Any]) -> frozenset[str]:
    names: set[str] = set()
    for item in ctx.get("tools") or ():
        spec = item.get("function", item) if isinstance(item, dict) else {}
        name = spec.get("name") if isinstance(spec, dict) else None
        if isinstance(name, str):
            names.add(name)
    return frozenset(names)


def _deliver(ctx: Mapping[str, Any], calls: tuple[Any, ...]) -> bool:
    """Подать проверенные вызовы в структурный эмулятор; True iff он их опубликовал."""
    feed, emitted = ctx.get("recovery_feed"), ctx.get("tool_calls_emitted")
    if not callable(feed) or not callable(emitted) or not {c.name for c in calls} <= _known_names(ctx):
        return False
    return bool(feed(calls_to_markup(calls)) is not False and emitted())


def _turn_facts(ctx: Mapping[str, Any], out: Mapping[str, object]) -> DeliveryFacts:
    """Факты клиента плюс то, что видно только в `out` (JSON-режим: текст, tool_events)."""
    facts = _facts(ctx)
    text_bytes = len(str(out.get("text") or "").encode("utf-8"))
    events = int(out.get("tool_events") or 0)
    return replace(facts, content_bytes=facts.content_bytes + text_bytes, tool_events=facts.tool_events + events)


def _recoverable(ctx: Mapping[str, Any], run: object, out: Mapping[str, object]) -> ToolCallCompletionTracker | None:
    tracker = getattr(getattr(run, "_tail", None), TRACKER_ATTR, None)
    if out.get("state") != "agy_error" or not isinstance(tracker, ToolCallCompletionTracker):
        return None
    return tracker if is_recoverable_function_call_error(str(out.get("err") or "")) else None


def recover(ctx: dict[str, Any], run: object, out: dict[str, Any], log: Log) -> None:
    """AD-005: «ошибка functionCall → валидный tool_call» → структурные tool_calls (INV-S1..S8)."""
    tracker = _recoverable(ctx, run, out) if _flags().toolcall_error_recovery else None
    if tracker is None or ctx.get(_RECOVERY_KEY):
        return
    ctx[_RECOVERY_KEY] = True
    decision = evaluate_recovery(tracker.snapshot(), StrictToolCallParser(), _turn_facts(ctx, out))
    if decision.recovered and _deliver(ctx, decision.calls):
        out.update(state="done", rc=0, err="", tool_turn_stop=True)
        _say(log, "toolcall_recovered", 1)
        return
    _say(log, f"toolcall_rejected:{'delivery_failed' if decision.recovered else decision.reason}", 1)


def health_fields() -> dict[str, object]:
    """Аддитивные поля `/health`: `flags_snapshot` и `resilience_flags` по именам env."""
    flags = _flags()
    fields = _report_health_fields(build_turn_resolution_report("health", flags))
    return {**fields, "flags_snapshot": flags_snapshot_dict(flags)}
