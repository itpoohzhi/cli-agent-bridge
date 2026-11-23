# ruff: noqa: E501
"""Оркестрация SSE: публикация границ хода, безопасный replay и единый финал."""
# pyright: reportAny=false, reportExplicitAny=false, reportPrivateUsage=false
from __future__ import annotations
import json
import threading
from typing import Any, Callable, final
from agy_runtime import activity_runtime
from agy_runtime.midstream_resilience import AgyToolTraceCollector, _owner_time
from agy_runtime.sse_stream_helpers import SseStreamSession, retry_after_headers
from core.route_health_policy import redact_diagnostic_text
from core.agy_capacity_guard import CAPACITY_REASON
from core.usage_wire import positive_wire_usage
from core.tool_channel_fsm import normalize_staged_fragments
from core.tool_turn_settle_policy import SettleDecision, resolve_tool_turn_stop
from core.stream_activity_policy import SlidingActivityWindow, build_final_outcome
from core.turn_usage_fsm import should_emit_wire_usage
from core.stream_resilience_policy import can_safely_replay_turn, is_present, is_uncommitted_step
from core.stream_resilience_runtime import MidstreamReplayOrchestrator
_attempt_scope = threading.local()
def current_attempt_index() -> int:
    return getattr(_attempt_scope, "index", -1)
def invoke_at_attempt[T](index: int, invoke: Callable[[], T]) -> T:
    previous_index, _attempt_scope.index = current_attempt_index(), index if type(index) is int else -1
    try:
        return invoke()
    finally:
        _attempt_scope.index = previous_index
@final
class _SseBodyRunner:
    def __init__(self, session: SseStreamSession) -> None:
        self.s = session
        self.time = _owner_time(session.handler)
        self.replay = MidstreamReplayOrchestrator(session.config, clock=self.time.monotonic, sleeper=self.time.sleep)
        self.replay.buffer = session.buffer
        self.collector = AgyToolTraceCollector(session.ledger)
        self.buffering = False
        self.deadline = float("inf")
        self.cid = str(next(filter(None, (session.ctx.get("conversation_id"),)), ""))
        self._last_out: dict[str, Any] = {}
        self._activity_window: SlidingActivityWindow | None = None
        self._activity_runtime: activity_runtime.ActivityRuntime | None = None
        self._attempt_started_at = self._attempt_budget = 0.0
        self.stop: Any = None
    def _note_progress(self, kind: str, payload: object) -> None:
        runtime = getattr(self, "_activity_runtime", None)
        if is_present(runtime):
            _ = runtime.record_signal(kind, payload, self.time.monotonic())
            self.deadline = runtime.current_deadline()
    def stage(self, value: str, channel: str = "content") -> bool:
        try:
            payload = json.loads(value) if channel == "tool_calls" else value
        except (ValueError, TypeError):
            payload = value.strip()
        self._note_progress(channel, payload)
        ok = False
        if not self.cancelled():
            self.s.buffer.stage_fragment(value, channel)
            ok = self.s.commit()
        return ok
    def stage_reasoning(self, value: str) -> bool:
        return self.stage(value, "reasoning_content")
    def stage_calls(self, value: list[dict[str, Any]]) -> bool:
        return self.stage(json.dumps(value, ensure_ascii=False), "tool_calls")
    def cancelled(self) -> bool:
        return self.s.disconnected
    def keepalive(self) -> bool:
        return self._deliver(self.s.keepalive)
    def text(self, value: str) -> bool:
        self._note_progress("content", value)
        return self._deliver(self.s.stream_text, value)
    def reasoning(self, value: str) -> bool:
        self._note_progress("reasoning", value)
        return self._deliver(self.s.stream_reasoning, value)
    def _deliver(self, callback: Any, *args: Any) -> bool:
        ok = False
        if not self.expired():
            ok = callback(*args)
        return ok
    def expired(self) -> bool:
        return self.time.monotonic() >= self.deadline
    def trace(self, event: dict[str, Any]) -> bool:
        self._note_progress("tool_calls", event)
        forward = self.s.ledger.should_forward_step(event.get("step_index"))
        ok = True
        if all((self.buffering, forward)):
            record = dict(event, tool_name=event.get("tool_name", event.get("name")), type=event.get("type", "tool_result"))
            self.collector.on_record(record)
        if any((not self.buffering, forward)):
            ok = False
            if not self.expired():
                ok = self.s.on_tool_trace(event)
        return ok
    def prepare_buffer(self) -> None:
        s = self.s
        s.stream_text, s.stream_reasoning = self.stage, self.stage_reasoning
        if is_present(s.tool_turn):
            s.tool_turn = s.hooks[3](next(filter(None, (s.ctx.get("tools"),)), list[dict[str, Any]]()), self.stage, self.stage_reasoning, self.stage_calls)
            s.stream_text = s.tool_turn.feed
            s.stream_reasoning = s.tool_turn.feed_reasoning
            s.ctx["tool_stop"] = s.tool_turn.turn_complete
            s.ctx["tool_calls_emitted"] = lambda: bool(s.tool_turn.calls)
            s.ctx["emitted_call_ids"] = lambda: [str(c.get("id", "")) for c in s.tool_turn.calls]
    def tool_stop(self) -> bool:
        return self.expired() or bool(self.stop and self.stop())
    def settle_decision(self, *, proc_exited: bool = False, result_received: bool = False) -> SettleDecision:
        res = SettleDecision("forced_stop", True, True, False)
        if not self.expired():
            got = resolve_tool_turn_stop(self.stop, proc_exited=proc_exited, result_received=result_received)
            res = got if isinstance(got, SettleDecision) else SettleDecision("continue", False, False, False)
        return res
    def recovery_snapshot(self) -> str:
        owner = getattr(self.stop, "__self__", None)
        snapshot = getattr(owner, "recovery_snapshot", None)
        try:
            return str(snapshot()) if callable(snapshot) else ("closed" if self.stop is None else "unknown")
        except Exception:
            return "unknown"
    def attempt(self, index: int, budget: float) -> dict[str, Any]:
        s, ctx, prev_stop = self.s, self.s.ctx, self.stop
        ctx["attempt_index"] = index
        self._activity_window = self._activity_runtime = None
        self._attempt_started_at, self._attempt_budget = self.time.monotonic(), budget
        if self.buffering:
            s.buffer.rollback_uncommitted()
            self.prepare_buffer()
            ctx.update(conversation_id=self.cid, attempt_budget_s=budget, attempt_index=index)
            self.deadline = self._attempt_started_at + budget if s.config.flag_enabled("midstream_retry_enabled") else float("inf")
        if s.config.flag_enabled("sliding_activity_window_enabled"):
            self._activity_window = self.replay.arm_attempt(budget)
            self._activity_runtime = activity_runtime.ActivityRuntime(self._activity_window)
            self.deadline = self._activity_runtime.current_deadline()
        ctx["activity_runtime"] = self._activity_runtime
        self.stop = stop = ctx.get("tool_stop")
        if self.buffering:
            ctx["tool_stop"] = self.tool_stop
        try:
            out = invoke_at_attempt(index, self._invoke)
        finally:
            self.deadline = float("inf")
            _ = ctx.pop("activity_runtime", None)
            self.stop = prev_stop
            if not is_present(stop):
                _ = ctx.pop("tool_stop", None)
            else:
                ctx["tool_stop"] = stop
        self._last_out = out
        if self.buffering:
            self.reconcile_trace(out)
        return out
    def _invoke(self) -> dict[str, Any]:
        s, ready = self.s, threading.Event()
        watcher = threading.Thread(target=s.coordinator.await_headers_or_flush, args=(ready,), daemon=True, name="agy-precommit")
        watcher.start()
        done_log = activity_runtime.defer_done(s.handler)
        try:
            out = s.handler._run_once(s.ctx, self.text, self.trace, self.reasoning, self.keepalive)
        except BaseException as exc:
            activity_runtime.clear_handler(s.handler, done_log)
            self._log_final(self._outcome(dict(state="error", rc=1, err=redact_diagnostic_text(str(exc)))))
            raise
        finally:
            ready.set()
            watcher.join()
            activity_runtime.clear_handler(s.handler, done_log)
        out = self._outcome(out)
        self._log_final(out)
        return out
    def _outcome(self, out: dict[str, Any]) -> dict[str, Any]:
        runtime = getattr(self, "_activity_runtime", None)
        if is_present(runtime):
            success = {("done", 0, True): True}.get((out.get("state"), out.get("rc"), any((out.get("text"), out.get("reasoning")))), False)
            snapshot = runtime.mark_completed(self.time.monotonic(), succeeded=success)
            return dict(out, **build_final_outcome(out, snapshot, req_id=str(self.s.ctx.get("tag", "")), cid=self.cid))
        if all((self.expired(), not self.cancelled())):
            out.update(state="timeout", rc=124, err="retry_budget_exhausted", timeout_limit_s=self._attempt_budget)
        return out
    def _log_final(self, out: dict[str, Any]) -> None:
        log = getattr(self.s.handler, "_log_done", None)
        if callable(log):
            log(str(self.s.ctx.get("model", "")), out, self._attempt_started_at, str(self.s.ctx.get("tag", "")))
    def reconcile_trace(self, out: dict[str, Any]) -> None:
        ledger = self.s.ledger
        cid = str(next(filter(None, (out.get("conversation_id"),)), self.cid))
        snapshot = out.get("trace_snapshot")
        active = ledger._active
        terminal = dict(first_token_timeout=True, first_event_timeout=True).get(str(out.get("state")), False)
        valid = all( ( bool(cid.strip()), any((not self.cid, cid == self.cid)),
                is_uncommitted_step(active, ledger.last_committed_step_idx),
                not terminal, snapshot == ledger.snapshot(), ) )
        if valid:
            valid = can_safely_replay_turn(snapshot, ledger.last_committed_step_idx)
        if not valid:
            ledger.trace_complete = False
        self.cid = cid
    def drain(self) -> bool:
        s = self.s
        if is_present(s.tool_turn):
            s.tool_turn.finish()
            if s.tool_turn.error:
                s.buffer.rollback_uncommitted()
                return True
        callbacks = dict(content=s.on_text, reasoning_content=s.on_reasoning)
        pending = normalize_staged_fragments(s.buffer.commit_fragments())
        ok = True
        for channel, value in pending:
            callback = dict(callbacks, tool_calls=lambda v: s.on_calls(json.loads(v)))[channel]
            ok = callback(value)
            if not ok:
                s.ledger.client_delivery_reconciled = False
                break
        if all((ok, pending, s.ledger._active >= 0)):
            _ = s.ledger.mark_step_completed(s.ledger._active)
        return ok
    def run(self) -> None:
        s, ctx = self.s, self.s.ctx
        self.buffering = any((s.config.flag_enabled("midstream_retry_enabled"), s.config.flag_enabled("tool_rollback_enabled")))
        try:
            allowed = True
            if not any((s.resilience, ctx.get("step_job_id"))):
                allowed = s.commit()
            if allowed:
                self._run_body()
        finally:
            ctx["finalize_timeout"] = s.finalize_stream
            s.coordinator.close()
            s.relay.close()
    def _run_body(self) -> None:
        s, ctx = self.s, self.s.ctx
        proceed = True
        if self.buffering:
            ctx["finalize_timeout"] = lambda _out: None
            out = dict(self.replay.run_with_resilience(self.attempt, s.ledger, s.keepalive, self.cancelled))
            if all((dict(cancelled=True).get(str(out.get("state")), False), not self.cancelled())):
                out = (self._last_out if self._last_out else dict(state="pump_error", rc=1, err="retry cancelled"))
            success = out.get("state") == "done"
            if all((success, out.get("rc") == 0)):
                if not self.cancelled():
                    proceed = self.drain()
            else:
                s.buffer.rollback_uncommitted()
                _ = out.pop("retained_events", None)
        else:
            out = self.attempt(0, self.replay.attempt_budget_s(0) if s.config.flag_enabled("sliding_activity_window_enabled") else s.config.first_event_timeout_s)
        if proceed:
            if any((self.cancelled(), dict(client_gone=True).get(str(out.get("state")), False))):
                s.hooks[1]("client gone mid-stream, child killed")
            else:
                ctx["finalize_timeout"] = s.finalize_stream
                s.finalize_stream(out)
                if not out.get("graceful_done"):
                    self.finish(out)
    def finish(self, out: dict[str, Any]) -> None:
        s = self.s
        err = s.handler._error_body(out, s.resilience)
        reason, proceed = "stop", True
        if all(((not is_present(err)), (is_present(s.tool_turn)))):
            s.tool_turn.finish()
            proceed = not self.cancelled() and (s.tool_turn.ok or bool(s.tool_turn.error))
            if s.tool_turn.error:
                err = s.tool_turn.error_body()
            elif s.tool_turn.calls:
                reason = "tool_calls"
        reg = s.ctx.get("register_post_turn")
        if all((not is_present(err), proceed)):
            if callable(reg):
                reg(out)
        if proceed:
            self._finish_response(out, err, reason)
    def _finish_response(self, out: dict[str, Any], err: Any, reason: str) -> None:
        s = self.s
        presend = all(((is_present(err)), not s.ctx["stream_committed"], any((s.resilience, s.ctx.get("step_job_id")))))
        if presend:
            clean = {k: redact_diagnostic_text(v) if isinstance(v, str) else v for k, v in err.items()}
            code = int(err.get("code") or 502) if any((s.ctx.get("step_job_id"), err.get("type") in (CAPACITY_REASON, "overloaded"))) else 502
            extra = retry_after_headers(out, err)
            s.handler._send(code, {"error": clean}, extra) if extra else s.handler._send(code, {"error": clean})
            s.handler.close_connection = True
        elif s.commit():
            ok = (self.finish_success(out, reason) if (not is_present(err)) else s.emit(s.error_chunk(err, self.error_usage(out))))
            if any((ok, not s.resilience)):
                _ = s.emit("data: [DONE]\n\n")
    def error_usage(self, out: dict[str, Any]) -> dict[str, Any] | None:
        try:
            return positive_wire_usage(self.s.handler._usage_payload(out.get("usage") or {}, out.get("usage_resolved")))
        except (TypeError, ValueError, AttributeError):
            return None
    def finish_success(self, out: dict[str, Any], reason: str) -> bool:
        s = self.s
        cid = str(next(filter(None, (out.get("conversation_id"),)), ""))
        ok = s.emit(s.chunk({}, reason, conversation_id=cid))
        if any((ok, not s.resilience)):
            ok = True
            usage = s.handler._usage_payload(next(filter(None, (out.get("usage"),)), dict[str, Any]()), out.get("usage_resolved"))
            if all((should_emit_wire_usage(out.get("usage_resolved")), any((usage.get("prompt_tokens"), usage.get("completion_tokens"))))):
                ok = s.emit(s.chunk({}, reason, usage=usage, conversation_id=cid))
        return ok
def serve_sse_body(handler: Any, ctx: dict[str, Any], hooks: tuple[Any, Any, Any, Any]) -> None:
    _SseBodyRunner(SseStreamSession(handler, ctx, hooks)).run()
