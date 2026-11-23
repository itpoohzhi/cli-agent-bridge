# fmt: off
"""Агент-агностическая политика допуска повторов и журнал незакоммиченного хода."""
from __future__ import annotations

import math
from collections.abc import Collection, Mapping
from dataclasses import dataclass, replace
from decimal import ROUND_FLOOR, Decimal
from typing import NoReturn, Protocol, TypeGuard, cast, final

import core.route_health_policy as routes
import core.stream_activity_policy as activity
from core.stream_interruption_recovery import is_transient_stream_interruption

AttemptDecision = routes.AttemptDecision
FailureCategory = routes.FailureCategory
RetryBudgetConfig = routes.RetryBudgetConfig
RetryReason = routes.RetryReason
classify_provider_failure = routes.classify_provider_failure
compute_attempt_decision = routes.compute_attempt_decision
redact_diagnostic_text = routes.redact_diagnostic_text
Record = Mapping[str, object]
Identity = tuple[int, str, str]
def is_present[T](value: T | None) -> TypeGuard[T]: return value is not None
def raise_error(error: BaseException) -> NoReturn: raise error from None
DEFAULT_MUTATING_TOOLS = frozenset((
    "write_file edit_file replace_file_content multi_replace_file_content run_command "
    "bash send_command_input write edit invoke_subagent define_subagent "
    "manage_subagents manage_task schedule send_message generate_image browser_subagent"
).split())
def normalize_stream_interruption(status_code: int, detail: str) -> FailureCategory:
    category = classify_provider_failure(status_code, detail).category
    if all((category == FailureCategory.FATAL_REQUEST_ERROR,
            is_transient_stream_interruption(redact_diagnostic_text(detail)))):
        category = FailureCategory.CAPACITY_EXHAUSTED
    if detail.lower().count("first_event_timeout_exceeded"):
        category = FailureCategory.FATAL_REQUEST_ERROR
    return category
def compute_effective_attempt_budget(config: RetryBudgetConfig,
    attempt_index: int, elapsed_s: float, required_floor_s: float, backoff_cap_s: float,
) -> AttemptDecision:
    if not all(all((math.isfinite(v), v >= 0))
               for v in (required_floor_s, backoff_cap_s)):
        raise_error(ValueError("invalid attempt floor or backoff cap"))
    decision = compute_attempt_decision(config, attempt_index, elapsed_s)
    if decision.allow_retry:
        total, reserve, elapsed, floor, backoff = map(Decimal, map(str, (
            config.total_budget_s, config.reserve_s, elapsed_s,
            required_floor_s, backoff_cap_s)))
        horizon = total - reserve - elapsed
        horizon -= (config.max_attempts - 1 - attempt_index) * (floor + backoff)
        cap = float(horizon.quantize(Decimal("0.001"), rounding=ROUND_FLOOR))
        effective = min(decision.attempt_budget_s, cap)
        if effective < max(required_floor_s, config.min_attempt_budget_s):
            decision = replace( decision, allow_retry=False, attempt_budget_s=0.0,
                reason=RetryReason.BUDGET_EXHAUSTED)
        else:
            decision = replace(decision, attempt_budget_s=effective)
    return decision
def effective_attempt_budget_s(config: RetryBudgetConfig, attempt_index: int,
    elapsed_s: float, required_floor_s: float, backoff_cap_s: float, ) -> float:
    decision = compute_effective_attempt_budget(
        config, attempt_index, elapsed_s, required_floor_s, backoff_cap_s )
    return decision.attempt_budget_s
SlidingBudgetInput = activity.SlidingBudgetInput
def effective_activity_attempt_budget_s(value: SlidingBudgetInput) -> float:
    return activity.compute_sliding_attempt_budget_s(value)
class CrossHopConfig(Protocol):
    first_event_timeout_s: float
    cross_hop_margin_s: float
    retry_total_budget_s: float
    retry_reserve_s: float
    retry_min_attempt_s: float
    backoff_cap_s: float
    idle_timeout_s: float
    passthrough_read_timeout_s: float
    midstream_retry_enabled: bool
    max_retries: int
    sliding_activity_window_enabled: bool
    sliding_idle_timeout_s: float
def validate_cross_hop_timeouts(config: CrossHopConfig, *, hop: str) -> None:
    c = config
    floor = c.first_event_timeout_s + c.cross_hop_margin_s
    idle_floor = ( c.retry_total_budget_s + c.cross_hop_margin_s
        if c.midstream_retry_enabled else floor )
    sliding = getattr(c, "sliding_activity_window_enabled", False)
    sliding_idle = getattr(c, "sliding_idle_timeout_s", 0.0)
    sliding_ok = not sliding or all((sliding_idle > 0,
        c.first_event_timeout_s <= sliding_idle < c.passthrough_read_timeout_s))
    checks = { "passthrough": lambda: all(
            (c.idle_timeout_s >= idle_floor, c.passthrough_read_timeout_s >= floor,
             sliding_ok) ),
        "backend": lambda: bool(effective_attempt_budget_s(RetryBudgetConfig(
            c.retry_total_budget_s, c.retry_reserve_s, c.retry_min_attempt_s,
            c.max_retries + 1), 0, 0, c.first_event_timeout_s, c.backoff_cap_s)
            if c.midstream_retry_enabled else True) and sliding_ok}
    check = checks.get(hop, lambda: raise_error(ValueError("unknown hop")))
    if not check():
        raise_error(ValueError("cross-hop timeout horizon is too short"))
@dataclass(frozen=True)
class ToolExecutionTraceRecord:
    step_idx: int
    call_id: str
    tool_name: str
    started: bool = True
    completed: bool = False
    source: str = ""
    @property
    def identity(self) -> Identity: return self.step_idx, self.call_id, self.tool_name
@dataclass(frozen=True)
class TraceSafetyReport:
    records: tuple[ToolExecutionTraceRecord, ...] = ()
    trace_complete: bool = False
    trace_trusted: bool = False
    client_delivery_reconciled: bool = False
    readonly_tools: frozenset[str] = frozenset()
    mutating_tools: frozenset[str] = DEFAULT_MUTATING_TOOLS
def can_safely_replay_turn( trace_snapshot: TraceSafetyReport,
    last_committed_step_idx: int, readonly_tools: Collection[str] | None = None,
    mutating_tools: Collection[str] | None = None, ) -> bool:
    s = trace_snapshot
    readonly = frozenset(
        s.readonly_tools if not is_present(readonly_tools) else readonly_tools )
    denied = s.mutating_tools.union(
        DEFAULT_MUTATING_TOOLS, ("shell",), next(filter(None, (mutating_tools,)), ()) )
    safe = all( all( ( r.completed, r.started, not readonly.isdisjoint((r.tool_name,)),
                denied.isdisjoint((r.tool_name,)), ) ) for r in s.records
        if is_uncommitted_step(r.step_idx, last_committed_step_idx) )
    return all((s.trace_complete, s.trace_trusted, s.client_delivery_reconciled, safe))
def is_uncommitted_step(idx: int, committed: int) -> bool: return idx > committed
def _valid_step(idx: object) -> bool:
    return type(idx) is int and idx >= 0
@final
class MidstreamStepLedger:
    """Хранит ограниченный журнал; потеря идентичности навсегда запрещает replay."""
    def __init__( self, max_entities: int = 512, readonly_tools: Collection[str] = (),
        mutating_tools: Collection[str] = DEFAULT_MUTATING_TOOLS, ) -> None:
        if not all((_valid_step(max_entities), max_entities)):
            raise_error(ValueError("max_entities must be positive"))
        self.max_entities, self.last_committed_step_idx = max_entities, -1
        self.readonly_tools = frozenset(readonly_tools)
        self.mutating_tools = frozenset(mutating_tools)
        self._active, self._ordinal = -1, 0
        self._steps: set[int] = set()
        self._records: dict[Identity, ToolExecutionTraceRecord] = {}
        self._pending: dict[Identity, str] = {}
        self.trace_complete = self.trace_trusted = True
        self.client_delivery_reconciled = True
    def should_forward_step(self, step_idx: int | None) -> bool:
        return (is_uncommitted_step(step_idx, self.last_committed_step_idx)
                if isinstance(step_idx, int) else True)
    def pin_active_step(self, record: Record | int) -> None:
        idx = _step_idx(record)
        if not _valid_step(idx):
            self.trace_complete = False
        else:
            number = cast(int, idx)
            self._active = max(self._active, number)
            if all((self._steps.isdisjoint((number,)),
                    not self._room(self._steps))):
                self.trace_complete = False
            else:
                self._steps.add(number)
    def mark_step_completed(self, record: Record | int) -> None:
        self.pin_active_step(record)
        idx = _step_idx(record)
        if _valid_step(idx):
            if isinstance(record, Mapping):
                calls = record.get("tool_calls", ())
                if not isinstance(calls, (list, tuple)):
                    self.trace_complete = False
                    calls = ()
                for raw in cast(Collection[object], calls):
                    call = _map(raw)
                    completed = dict(completed=True).get(str(call.get("status")), False)
                    for kind in ("tool_use",) + ("tool_result",) * completed:
                        name = _map(call.get("function")).get("name", "")
                        event = dict(call, step_index=idx, type=kind, tool_name=name)
                        self.record_tool_event(event, source="transcript")
            self.last_committed_step_idx = max(
                self.last_committed_step_idx, cast(int, idx) )
    def _identity(self, event: Record, source: str) -> Identity:
        idx, name = _step_idx(event), str(event.get("tool_name", ""))
        call_id = str(next(filter(None, map(event.get,
                      ("call_id", "tool_call_id", "id"))), ""))
        matches = [r for r in self._records.values() if call_id == r.call_id]
        if not is_present(idx):
            self.trace_complete &= len(matches) <= 1
            pending = [k[0] for k in self._pending if k[1:] == (source, name)]
            idx = ( matches[0].step_idx if len(matches) == 1 else ( pending[0]
                    if all((not call_id, len(pending) == 1)) else self._active + 1 ) )
        if not _valid_step(idx):
            self.trace_complete = False
            idx = self._active + 1
        idx = cast(int, idx)
        if any((not name, any(all((r.step_idx == idx, r.tool_name != name))
                             for r in matches))):
            self.trace_complete = False
        self.pin_active_step(idx)
        if not call_id:
            call_id = self._anonymous_id((idx, source, name), event.get("type"))
        return idx, call_id, name
    def _anonymous_id(self, key: Identity, kind: object) -> str:
        starting = dict(tool_use=True).get(str(kind), False)
        call_id = ""
        if starting:
            if any((bool(self._pending.get(key)),
                    not self._room(self._pending))):
                self.trace_complete = False
            else:
                self._ordinal += 1
                call_id = self._pending[key] = f"ordinal-{self._ordinal}"
        else:
            call_id = self._pending.pop(key, "")
        self.trace_complete &= bool(call_id)
        return call_id
    def record_tool_event(self, event: Record, *, source: str = "stdout") -> None:
        kind = str(event.get("type"))
        if not dict(tool_use=True, tool_result=True).get(kind, False):
            self.trace_complete = False
        else:
            self.trace_trusted &= dict(stdout=True, transcript=True, sqlite=True).get(
                source, False )
            identity = self._identity(event, source)
            old = self._records.get(identity)
            if all((not is_present(old), not self._room(self._records))):
                self.trace_complete = False
            else:
                completed = dict(tool_result=True).get(kind, False)
                self.trace_complete &= any((not completed, bool(old)))
                self._records[identity] = ToolExecutionTraceRecord( *identity,
                    started=any((not completed, getattr(old, "started", False))),
                    completed=any((completed, getattr(old, "completed", False))),
                    source=source, )
    def snapshot(self) -> TraceSafetyReport:
        return TraceSafetyReport( tuple(self._records.values()), self.trace_complete,
            self.trace_trusted, self.client_delivery_reconciled, self.readonly_tools,
            self.mutating_tools, )
    def _room(self, v: Collection[object]) -> bool: return len(v) < self.max_entities
@final
class UncommittedTurnBuffer:
    """Публикация только на границе; rollback удаляет также частичный tool_call."""
    def __init__(self) -> None: self._fragments: list[tuple[str, str]] = []
    def stage_fragment(self, fragment: str, channel: str = "content") -> None:
        self._fragments.append((channel, fragment))
    def commit_fragments(self) -> tuple[tuple[str, str], ...]:
        pending, self._fragments = self._fragments, []
        return tuple(pending)
    def commit_boundary(self) -> str:
        return "".join(fragment for _, fragment in self.commit_fragments())
    def rollback_uncommitted(self) -> None: self._fragments = []
def parse_tool_names(value: object, default: frozenset[str]) -> frozenset[str]:
    return frozenset( default if not is_present(value)
        else (item.strip() for item in str(value).split(",") if item.strip()) )
def _map(v: object) -> Record: return cast(Record, v if isinstance(v, Mapping) else {})
def _step_idx(record: Record | int) -> object:
    return cast(object, record if isinstance(record, int) else
                record.get("step_idx", record.get("step_index")))
def should_flush_precommit_headers( elapsed_s: float, threshold_s: float,
    headers_committed: bool, ) -> bool:
    return all((not headers_committed, 0 <= threshold_s <= elapsed_s < math.inf))
