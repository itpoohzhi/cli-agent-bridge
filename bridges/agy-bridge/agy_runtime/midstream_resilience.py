# fmt: off
"""Снимок дедлайна и однопроходный сбор фактов CLI до публикации дельт."""
# Legacy-фасад передаёт Any; приватные API переиспользуются по контракту извлечения.
# pyright: reportAny=false, reportExplicitAny=false, reportPrivateUsage=false
from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Mapping
from typing import Any, cast, final

from agy_runtime.process_supervisor import ProcessSupervisor
from core.stream_resilience_policy import (
    MidstreamStepLedger,
    TraceSafetyReport,
    is_present,
    raise_error,
)
from core.stream_resilience_runtime import _number, _snapshot


def _owner_time(owner: Any) -> Any:
    return next( filter( None, ( getattr(m, "__globals__", {}).get("time")
                for c in type(owner).__mro__ for m in vars(c).values() ), ), time, )
def current_first_event_timeout_s(run: Any, legacy_resolved_default: float) -> float:
    cached = getattr(run, "_first_event_timeout_s", None)
    if not is_present(cached):
        cached = _first_event_limit(legacy_resolved_default)
        run._first_event_timeout_s = cached
    return float(cached)
def _first_event_limit(legacy_resolved_default: float) -> float:
    snapshot, broken = _snapshot(os.environ)
    key = "BRIDGE_STREAM_FIRST_EVENT_TIMEOUT_S"
    raw = snapshot.get("first_event_timeout_s", snapshot.get(key, os.environ.get(key)))
    flags = ( "midstream_retry", "precommit_flush", "passthrough_early_flush",
        "tool_rollback", )
    enabled = all((not broken, any(_flag(snapshot, f) for f in flags)))
    if not is_present(raw):
        raw = os.environ.get( "AGY_BRIDGE_FIRST_TOKEN_TIMEOUT_S",
            os.environ.get("AGY_BRIDGE_FIRST_TOKEN_TIMEOUT"), )
    fallback = 120.0 if any((enabled, is_present(raw))) else legacy_resolved_default
    limit = _number(key, "first_event_timeout_s", fallback, raw)
    return limit
def _flag(snapshot: Mapping[str, object], name: str) -> bool:
    key = f"BRIDGE_STREAM_{name.upper()}_ENABLED"
    raw = snapshot.get(f"{name}_enabled", snapshot.get(key, os.environ.get(key, "")))
    accepted: dict[str, bool] = dict.fromkeys(("true", "1", "yes", "on"), True)
    return accepted.get(str(raw).lower(), False)
def first_event_timeout_for_result( out: Mapping[str, Any], resilience: Any,
    legacy_resolved_default: float, ) -> float:
    values = [ out[k] for k in ("timeout_limit_s", "first_event_timeout_s")
        if not out.keys().isdisjoint((k,)) ]
    snapshot = out.get("timeout_snapshot")
    if is_present(snapshot):
        values.append( cast(Mapping[str, Any], snapshot).get("first_event_timeout_s")
            if isinstance(snapshot, Mapping)
            else getattr(snapshot, "first_event_timeout_s", None) )
    detail, prefix = str(out.get("err", "")), "no agy event within "
    if detail.count(prefix):
        values.append(detail.split(prefix, 1)[1].removesuffix("s"))
    limit = legacy_resolved_default
    if any((values, resilience)):
        limit = _validated_limit(values)
    return limit
def _validated_limit(values: list[Any]) -> float:
    try:
        limits = [float(v) for v in values]
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("invalid first-event timeout outcome") from exc
    if any( ( not limits, any(isinstance(v, bool) for v in values),
            any(not 0 < v < float("inf") for v in limits), len(set(limits)) != 1, ) ):
        raise_error(ValueError("missing or inconsistent first-event timeout outcome"))
    return limits[0]
def run_transcript_tail_loop( tail: Any,
    deps: tuple[float, float, Callable[[str], None]], ) -> None:
    legacy, poll, log = deps
    run = getattr(tail, "run_ref", None)
    limit = current_first_event_timeout_s(run, legacy) if (is_present(run)) else legacy
    if _await_tail_binding(tail, (limit, poll, log)):
        mono = _owner_time(tail).monotonic
        started = mono()
        while mono() - started < tail.deadline_s:
            if tail.stop_event.is_set():
                break
            if tail.done_event.is_set():
                tail._drain_post_eof()
                break
            tail.tick()
            tail.done_event.wait(poll)
def _await_tail_binding( tail: Any, deps: tuple[float, float, Callable[[str], None]],
) -> bool:
    limit, poll, log = deps
    waited, bound = 0.0, False
    while True:
        delay = min(poll, max(0.0, limit - waited))
        if tail._ready.wait(timeout=delay):
            bound = True
            break
        waited += delay
        if any((tail.stop_event.is_set(), tail.done_event.is_set())):
            break
        if waited >= limit:
            log(f"tail-timeout cid={tail._cid8()}: no bind within {limit:g}s")
            break
    return bound
@final
class AgyToolTraceCollector:
    """Переводит транспортные записи в консервативный журнал ядра."""
    def __init__(self, ledger: MidstreamStepLedger | None = None) -> None:
        self.ledger = ledger if (is_present(ledger)) else MidstreamStepLedger()
    def record_cli_event(self, record: Any, source: str = "stdout") -> None:
        if isinstance(record, (str, bytes, bytearray)):
            try:
                record = json.loads(record)
            except (ValueError, UnicodeError):
                self.ledger.trace_complete = False
                record = None
        if not isinstance(record, Mapping):
            self.ledger.trace_complete = False
        else:
            self._record_mapping(cast(Mapping[str, Any], record), source)
    def _record_mapping(self, record: Mapping[str, Any], source: str) -> None:
        kind = record.get("type")
        if dict.fromkeys(("tool_use", "tool_result", "gap"), True).get(kind, False):
            self.ledger.record_tool_event(record, source=source)
        elif {"tool": True}.get(record.get("step_type"), False):
            kind = ( "tool_result"
                if dict(DONE=True).get(str(record.get("state")), False) else "tool_use"
            )
            event = dict(record, type=kind)
            self.ledger.record_tool_event(event, source=source)
        elif not record.keys().isdisjoint(("tool_calls",)):
            self._record_calls(record, source)
    def _record_calls(self, record: Mapping[str, Any], source: str) -> None:
        calls = record.get("tool_calls")
        if not isinstance(calls, (list, tuple)):
            self.ledger.trace_complete = False
            calls = ()
        for raw in cast(list[object], calls):
            call: Mapping[str, Any] = (
                cast(Mapping[str, Any], raw) if isinstance(raw, Mapping) else {} )
            function = call.get("function")
            if not isinstance(function, Mapping):
                self.ledger.trace_complete = False
                continue
            event = dict( call,
                step_index=record.get("step_index", record.get("step_idx")),
                type="tool_use",
                tool_name=cast(Mapping[str, Any], function).get("name", ""), )
            self.ledger.record_tool_event(event, source=source)
            if {"completed": True}.get(call.get("status"), False):
                event["type"] = "tool_result"
                self.ledger.record_tool_event(event, source=source)
    on_record = record_cli_event
    def snapshot(self) -> TraceSafetyReport: return self.ledger.snapshot()
def _collector(owner: Any) -> AgyToolTraceCollector:
    run = getattr(owner, "run_ref", None)
    target = run if (is_present(run)) else owner
    collector = getattr(target, "tool_trace_collector", None)
    if not is_present(collector):
        collector = AgyToolTraceCollector(getattr(target, "step_ledger", None))
        target.tool_trace_collector = collector
    return collector
def tick_transcript_with_tool_capture(tail: Any, sqlite_poll_s: float) -> None:
    collector, original = _collector(tail), tail._emit_record
    row_handler = getattr(tail, "_handle_row", None)
    def on_record(raw: Any) -> Any:
        collector.record_cli_event(raw, source="transcript")
        return original(raw)
    def on_row(idx: int, status: int, size: Any, payload: Any) -> Any:
        collector.record_cli_event(payload, source="sqlite")
        assert is_present(row_handler)
        return row_handler(idx, status, size, payload)
    tail._emit_record = on_record
    if is_present(row_handler):
        tail._handle_row = on_row
    try:
        tail._read_transcript()
        if not tail.dead:
            permitted = tail._sqlite_permitted()
            now = _owner_time(tail).monotonic()
            if all((permitted, tail.sqlite_active, now >= tail._next_poll_at)):
                tail._next_poll_at = now + sqlite_poll_s
                tail._poll_sqlite()
    finally:
        tail._emit_record = original
        if is_present(row_handler):
            tail._handle_row = row_handler
@final
class PumpToolState:
    """Идентичность и порядковые номера инструментов одного хода."""
    def __init__(self, _as_int_fn: Callable[[Any], int | None]) -> None:
        self._as_int = _as_int_fn
        self.tool_ordinal = 0
        self.tool_ordinal_by_id: dict[str, int] = {}
        self.collector: AgyToolTraceCollector | None = None
    def trace(self, step: Mapping[str, Any]) -> dict[str, Any]:
        idx = self._as_int(step.get("step_index"))
        trace = dict( name=str(next(filter(None, (step.get("tool_name"),)), "tool")),
            step_index=idx, duration_s=step.get("duration_seconds"), )
        raw_id = next( filter(None, (step.get("call_id"), step.get("tool_call_id"))),
            step.get("id"), )
        call_id = str(raw_id).strip() if isinstance(raw_id, (str, int)) else ""
        if call_id:
            trace["call_id"] = call_id
        if not is_present(idx):
            ordinal = self.tool_ordinal_by_id.get(call_id) if call_id else None
            if not is_present(ordinal):
                self.tool_ordinal += 1
                ordinal = self.tool_ordinal
                if call_id:
                    self.tool_ordinal_by_id[call_id] = ordinal
            trace["fallback_ordinal"] = ordinal
        return trace
def capture_pump_tool_step( run: Any, step: Mapping[str, Any],
    tool_state: PumpToolState, ) -> None:
    if dict(tool=True).get(str(step.get("step_type")), False):
        tool_state.collector = _collector(run)
        idx = tool_state._as_int(step.get("step_index"))
        if is_present(idx):
            indices: set[int] = getattr(run, "_tool_step_indices", set())
            indices.add(idx)
            run._tool_step_indices = indices
        if not dict(DONE=True).get(str(step.get("state")), False):
            tool_state.collector.on_record(step, source="stdout")
def emit_done_tool_trace_if_any( run: Any, step: Mapping[str, Any], kind: object,
    tool_state: PumpToolState, ) -> None:
    if all( ( dict(tool=True).get(str(kind), False),
            dict(DONE=True).get(str(step.get("state")), False), ) ):
        collector = (tool_state.collector if tool_state.collector
                     else _collector(run))
        collector.on_record(step, source="stdout")
        run.q.put(("tool_trace", tool_state.trace(step)))
@final
class AgyContinuation:
    """Ограничивает продолжение исходным cid и владением группой процесса."""
    def __init__(self, supervisor: ProcessSupervisor | None = None) -> None:
        self.supervisor = supervisor if supervisor else ProcessSupervisor()
        self._owned: dict[int, Any] = {}
    def spawn(self, command: list[str], cid: str, options: Any = None) -> Any:
        if any((not cid.strip(), command.count("--conversation"))):
            raise_error(
                ValueError("continuation requires one nonempty conversation id") )
        process = self.supervisor.spawn( [*command, "--conversation", cid],
            **cast(dict[str, Any], options if options else {}), )
        self._owned[id(process)] = process
        return process
    def cleanup(self, process: Any) -> None:
        self.supervisor.kill_group(self._owned.pop(id(process)))


def finish_transcript_tail(
    tail: Any,
    close_fn: Callable[[Any], None],
    pool_fn: Callable[[], Any],
    breaker_fn: Callable[..., None],
    release_cid_fn: Callable[[str, str], None],
) -> None:
    if tail._finished:
        return
    tail._finished = True
    try:
        with tail._conn_lock:
            conn = tail._active_conn
            tail._active_conn = None
            if conn is not None:
                close_fn(conn)
        if (pool := pool_fn()) is not None:
            pool.release_thread()
        if tail.plan.mode in ("LIVE", "SHADOW"):
            breaker_fn(tail.probe_gen, tail.selects_ok, tail.failed)
    finally:
        if tail._owned_cid:
            release_cid_fn(tail._owned_cid, tail.turn_id)
