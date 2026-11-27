# fmt: off
"""Сеанс SSE: единый commit, доставка, журнал и мягкое завершение."""
# Legacy-фасад передаёт Any; приватные API переиспользуются по контракту извлечения.
# pyright: reportAny=false, reportExplicitAny=false, reportPrivateUsage=false
from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any, cast, final

from agy_runtime.content_arbiter import _ContentArbiter
from agy_runtime.long_session_config import build_conv_headers, is_loopback_peer
from agy_runtime.midstream_resilience import _owner_time
from agy_runtime.stream_delivery_fsm import (
    canonical_trace_key,
    filter_unemitted_retained,
    sanitizer_headers,
)
from agy_runtime.stream_relay import StreamRelay
from agy_runtime.tool_progress import _ToolProgress
from core.content_delivery_tracker import ContentDeliveryTracker
from core.route_health_policy import redact_diagnostic_text
from core.stream_interruption_recovery import evaluate_graceful_interruption
from core.stream_resilience_policy import (
    MidstreamStepLedger,
    UncommittedTurnBuffer,
    is_present,
    raise_error,
)
from core.stream_resilience_runtime import (
    EarlyCommitSinkCoordinator,
    StreamResilienceConfig,
)


@final
class SseStreamSession:
    """Хранит исключительно состояние текущего HTTP-запроса."""
    def __init__( self, handler: Any, ctx: dict[str, Any], hooks: tuple[Any, ...],
    ) -> None:
        self.handler, self.ctx, self.hooks = handler, ctx, hooks
        self.config = ctx.get("resilience_config")
        if not self.config:
            self.config = StreamResilienceConfig.from_env()
        self.resilience = hooks[0]("AGY_BRIDGE_STREAM_RESILIENCE_ENABLED", True)
        ctx.update(stream_resilience_enabled=self.resilience, stream_committed=False,
            keepalive_cb=self.keepalive)
        self.delivery = ctx["delivery_tracker"] = ContentDeliveryTracker()
        ctx["recovery_feed"] = lambda text: self.stream_text(text)
        self.completion_id = f"chatcmpl-agy-{uuid.uuid4().hex[:12]}"
        self.created, self.disconnected = int(_owner_time(handler).time()), False
        self.relay = StreamRelay(getattr(handler, "wfile", None))
        handler._stream_relay = self.relay
        self.ledger = ctx.get("step_ledger")
        if not self.ledger:
            self.ledger = MidstreamStepLedger( self.config.ledger_max_entities,
                self.config.readonly_tools, self.config.mutating_tools, )
        ctx["step_ledger"] = self.ledger
        self.arbiter = _ContentArbiter(str(ctx.get("turn_id", "")))
        self.buffer = UncommittedTurnBuffer()
        self.progress = _ToolProgress(
            str(next(filter(None, (ctx.get("turn_id"),)), "")),
            str(next(filter(None, (ctx.get("conversation_id"),)), "")), )
        self.emitted_content = self.emitted_reasoning_or_tool = 0
        self.emitted_tool_calls = 0
        self.coordinator = EarlyCommitSinkCoordinator(
            self, self.config, clock=_owner_time(handler).monotonic )
        self._emulate_tools = bool(ctx.get("emulate_tools"))
        self.emitted_stream_text = self.emitted_reasoning_text = self.fed_raw_text = ""
        self.emitted_tool_trace_keys: list[str] = []
        self.b05_skipped_chars = self.b05_flushed_tail_chars = 0
        self._tool_targets: tuple[Any, Any, Any] = (self.on_text, self.on_reasoning, self.on_calls)
        self._bind_stream_targets()
        ctx["finalize_timeout"] = self.finalize_stream
    def _bind_stream_targets(self, on_text: Any = None, on_reasoning: Any = None, on_calls: Any = None) -> None:
        if all((on_text, on_reasoning, on_calls)):
            self._tool_targets = (on_text, on_reasoning, on_calls)
        on_t, on_r, on_c = self._tool_targets
        self.tool_turn = None
        if self._emulate_tools and len(self.hooks) > 3:
            self.tool_turn = self.hooks[3](
                next(filter(None, (self.ctx.get("tools"),)), list[dict[str, Any]]()),
                on_t, on_r, on_c, )
            self.ctx.update(tool_stop=self.tool_turn.turn_complete, tool_calls_emitted=lambda: bool(self.tool_turn.calls),
                emitted_call_ids=lambda: [str(c.get("id", "")) for c in self.tool_turn.calls])
        self.stream_text = self._feed_tool_text if self.tool_turn is not None else on_t
        self.stream_reasoning = (
            self.tool_turn.feed_reasoning if self.tool_turn is not None else on_r )
    def _feed_tool_text(self, value: str) -> bool:
        if self.tool_turn is None:
            return self._tool_targets[0](value)
        ok = self.tool_turn.feed(value)
        if ok:
            self.fed_raw_text += value
        return ok
    def reset_precommit_emitted(self) -> None:
        self.emitted_stream_text = self.emitted_reasoning_text = self.fed_raw_text = ""
        self.emitted_tool_trace_keys.clear()
        if self._emulate_tools and len(self.hooks) > 3:
            self._bind_stream_targets()
    @property
    def client_gone(self) -> bool:
        return self.disconnected
    def start(self, status: int, headers: list[tuple[str, str]]) -> None:
        h = self.handler
        cid_pat = self.ctx.get("cid_re")
        pat = cid_pat if isinstance(cid_pat, re.Pattern) else re.compile(r"^[0-9a-f-]{8,64}$")
        conv_hdrs = build_conv_headers(
            next(filter(None, (self.ctx.get("conversation_id"), getattr(h, "_observed_cid", ""))), ""),
            pat,
            peer_is_loopback=is_loopback_peer(h), config_path=self.ctx.get("dynamic_config_path"),
        )
        seen = {k.lower() for k, _ in headers}
        extra = [(k, v) for k, v in conv_hdrs.items() if not seen.__contains__(k.lower())]
        seen.update(k.lower() for k, _ in extra)
        extra.extend( (k, v) for k, v in sanitizer_headers(self.tool_turn is not None)
            if not seen.__contains__(k.lower()) )
        try:
            h.send_response(status)
            for key, value in ( *headers, *extra, ("Cache-Control", "no-cache"),
                ("X-Accel-Buffering", "no"), ):
                h.send_header(key, value)
            h.end_headers()
            self.ctx["stream_committed"] = h.close_connection = True
            if not h._emit(self.chunk({"role": "assistant", "content": ""})):
                raise_error(BrokenPipeError())
            self.delivery.mark_keepalive()
        except OSError as exc:
            self.disconnected = True
            raise BrokenPipeError from exc
    def write(self, data: bytes) -> bool:
        ok = self.handler._emit(data.decode("utf-8"))
        if all((self.resilience, not ok)):
            self.disconnected = True
            raise_error(BrokenPipeError())
        return ok
    def chunk(self, delta: dict[str, Any], finish: Any = None, **extras: Any) -> str:
        body = dict( id=self.completion_id, object="chat.completion.chunk",
            created=self.created, model=self.ctx["model"],
            choices=[dict(index=0, delta=delta, finish_reason=finish)], )
        body.update( { k: v for k, v in extras.items() if is_present(v)
                if (bool(v) if isinstance(v, str) else True) } )
        return "data: " + json.dumps(body, ensure_ascii=False) + "\n\n"
    def emit(self, data: str) -> bool:
        ok = self.coordinator.emit_chunk(data.encode("utf-8"))
        if self.resilience:
            self.disconnected |= not ok
        return ok
    def commit(self) -> bool:
        ok = self.coordinator.start_headers()
        self.disconnected |= not ok
        return ok
    def _delta(self, value: Any, channel: str) -> bool:
        ok = not self.disconnected
        if not all((self.resilience, not value)):
            ok = self.emit(self.chunk({channel: value}))
            if ok:
                self._track(value, channel)
                if channel == "content" and isinstance(value, str):
                    self.emitted_stream_text += value
                if channel == "reasoning_content" and isinstance(value, str):
                    self.emitted_reasoning_text += value
            useful = bool(value.strip()) if isinstance(value, str) else True
            if all((ok, useful)):
                self._count_delta(value, channel)
        return ok
    def _track(self, value: Any, channel: str) -> None:
        if channel == "tool_calls":
            self.delivery.mark_tool_calls(len(value))
        else:
            dict(content=self.delivery.mark_content).get(channel, self.delivery.mark_reasoning)(value)
    def _count_delta(self, value: Any, channel: str) -> None:
        if dict(content=True).get(channel, False):
            self.emitted_content += len(value.strip())
        else:
            self.emitted_reasoning_or_tool += 1
            self.emitted_tool_calls += int(dict(tool_calls=True).get(channel, False))
    def on_text(self, value: str) -> bool:
        return self._delta(value, "content")
    def on_reasoning(self, value: str) -> bool:
        return self._delta(value, "reasoning_content")
    def on_calls(self, calls: list[dict[str, Any]]) -> bool:
        return self._delta(calls, "tool_calls")
    def on_tool_trace(self, event: dict[str, Any]) -> bool:
        if self.tool_turn:
            self.tool_turn.notify_activity()
        self.delivery.mark_tool_event()
        if self.resilience:
            self.ctx["tool_activity"] = True
        ok = True
        if self.hooks[0]("emit_tool_trace"):
            marker = self.progress.marker(event, commit=False)
            if is_present(marker):
                channel = (
                    getattr(self, "tool_trace_channel", None)
                    or (self.config.get("tool_trace_channel") if isinstance(self.config, dict) else getattr(self.config, "tool_trace_channel", None))
                    or os.environ.get("AGY_BRIDGE_TOOL_TRACE_CHANNEL", "reasoning")
                )
                if str(channel).strip().lower() == "content":
                    clean_marker = f"\n\n{marker.strip()}\n\n"
                    ok = self.on_text(clean_marker)
                else:
                    ok = self.on_reasoning(marker)
                if ok:
                    self.progress.commit()
                    self.emitted_tool_trace_keys.append(canonical_trace_key(event))
        return ok
    def keepalive(self) -> bool:
        ok = not self.disconnected
        if any((self.ctx["stream_committed"], self.ctx.get("step_job_id"))):
            ok = self.coordinator.write_keepalive()
            if ok:
                self.delivery.mark_keepalive()
        if self.resilience:
            self.disconnected |= not ok
        return ok
    def handle_step_event(self, kind: str, event: dict[str, Any]) -> bool:
        idx = event.get("step_index", event.get("step_idx"))
        ok = True
        if self.ledger.should_forward_step(idx):
            ok = self._forward_step(kind, event, idx)
        return ok
    def _forward_step(self, kind: str, event: dict[str, Any], idx: Any) -> bool:
        _ = self.ledger.pin_active_step(event)
        ok = True
        if dict.fromkeys(("tool_use", "tool_result"), True).get(kind, False):
            _ = self.ledger.record_tool_event(dict(event, type=kind))
        else:
            text = cast( object, self.arbiter.offer( str(event.get("source", "stdout")),
                    idx, str(event.get("text", event.get("content", ""))), ), )
            callback = dict(reasoning=self.stream_reasoning).get(kind, self.stream_text)
            if isinstance(text, str):
                ok = callback(text)
        return ok
    def close_interrupted(self, out: dict[str, Any]) -> None:
        opened = bool(
            self.tool_turn._normalizer.has_open_tool_call() if self.tool_turn else False
        )
        decision = evaluate_graceful_interruption( error_text=out.get("err"),
            delivered_content=bool(self.emitted_content), delivered_reasoning=bool(
                self.emitted_reasoning_or_tool - self.emitted_tool_calls ),
            delivered_tool_calls=any((self.emitted_tool_calls, out.get("tool_calls"))),
            has_unclosed_tool_call=opened,
            graceful_enabled=self.hooks[0]("graceful_interruption_on_partial", True), )
        if decision.should_gracefully_close:
            self._close_partial(out, decision)
    def _close_partial(self, out: dict[str, Any], decision: Any) -> None:
        self.handler._arm_flush_window(self.ctx)
        if self.tool_turn:
            self.tool_turn.finish()
        callback = dict(content=self.on_text).get(
            str(decision.target_channel), self.on_reasoning )
        _ = callback(decision.notice_text)
        out.update(state="done", rc=0, err="", graceful_interruption_closed=True)
        self.hooks[1](f"stream-graceful-interruption target={decision.target_channel}")
    def finalize_timeout(self, out: dict[str, Any]) -> None:
        eligible = all( ( not out.get("graceful_done"),
                dict(timeout=True, idle_timeout=True).get(str(out.get("state")), False),
                self.hooks[0]("graceful_timeout_on_partial"), ) )
        if eligible:
            self._finalize_partial_timeout(out)
    def _finalize_partial_timeout(self, out: dict[str, Any]) -> None:
        retained: list[tuple[str, Any]] = list(
            next(filter(None, (out.get("retained_events"),)), ()) )
        text = "".join(str(p) for k, p in retained if dict(text=True).get(k, False))
        if any((self.emitted_content, self.emitted_reasoning_or_tool, text.strip())):
            self._flush_partial_timeout(out, retained)
    def _flush_partial_timeout(self, out: dict[str, Any], retained: Any) -> None:
        self.handler._arm_flush_window(self.ctx)
        open_fn = getattr(getattr(self.tool_turn, "_normalizer", None), "has_open_tool_call", None)
        has_open = bool(open_fn()) if callable(open_fn) else False
        emitted_text = (self.fed_raw_text if (self.tool_turn is not None and self.fed_raw_text
            and any((self.emitted_stream_text, self.emitted_tool_calls, has_open))) else self.emitted_stream_text)
        retained, skipped = filter_unemitted_retained( retained,
            emitted_content=emitted_text,
            emitted_reasoning=self.emitted_reasoning_text,
            emitted_tool_traces=self.emitted_tool_trace_keys, )
        rem_text = "".join(str(p) for k, p in retained if k == "text")
        if has_open and "<tool_call>" in rem_text.split("</tool_call>", 1)[0]:
            self._bind_stream_targets()
        self.b05_skipped_chars += skipped
        self.b05_flushed_tail_chars += sum( len(str(p)) for k, p in retained
            if k in ("text", "reasoning") )
        ok = True
        callbacks = dict( text=self._feed_tool_text if self.tool_turn is not None else self.on_text,
            reasoning=self.tool_turn.feed_reasoning if self.tool_turn is not None else self.on_reasoning,
            tool_trace=self.on_tool_trace, )
        for kind, payload in retained:
            callback = callbacks.get(kind)
            if callback:
                value = payload
                if not dict(tool_trace=True).get(kind, False):
                    value = str(payload)
                ok = callback(value)
            if not ok:
                break
        if all((ok, self.tool_turn)):
            self.tool_turn.finish()
            ok = self.tool_turn.ok
        reason = str(out.get("state"))
        if ok:
            ok = self.commit()
            if ok:
                ok = self.emit( self.chunk( { "content": self.handler._graceful_notice(
                                reason, out.get("timeout_limit_s") ) } ) )
        if ok:
            cid = str(next(filter(None, (out.get("conversation_id"),)), ""))
            ok = self.emit(self.chunk({}, self.hooks[2](), conversation_id=cid))
        if ok:
            _ = self.emit("data: [DONE]\n\n")
        out["graceful_done"] = True
        self.hooks[1](f"graceful-timeout state={reason} mode=sse ok={int(bool(ok))}")
    def finalize_stream(self, out: dict[str, Any]) -> None:
        if dict(agy_error=True, pump_error=True).get(str(out.get("state")), False):
            self.close_interrupted(out)
        else:
            self.finalize_timeout(out)
    def error_chunk(self, error: dict[str, Any], usage: dict[str, Any] | None = None) -> str:
        clean = { k: redact_diagnostic_text(v) if isinstance(v, str) else v
            for k, v in error.items() }
        data = "data: " + json.dumps({"error": clean}, ensure_ascii=False) + "\n\n"
        if self.resilience:
            data = self.chunk({}, "stop", error=clean, usage=usage)
        return data


def keepalive(ctx: dict[str, Any]) -> bool:
    return bool(ctx["keepalive_cb"]())


def retry_after_headers(out: dict[str, Any], err: Any) -> dict[str, str] | None:
    if not isinstance(err, dict) or err.get("type") != "overloaded":
        return None
    raw = out.get("retry_after_s")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not (0 < raw < float("inf")):
        return None
    return {"Retry-After": str(max(1, -int(-min(float(raw), 86400.0) // 1)))}
