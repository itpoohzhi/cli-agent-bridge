"""Регрессионные тесты обрамления SSE, finish_reason, drain/QoS и фильтрации unknown_tool."""

from __future__ import annotations

import io
import os
import threading
import time
import unittest
from typing import Any
from unittest.mock import patch

from adapters.muse_msp import MspEvents
from adapters.passthrough_adapter import PassthroughLimits, StreamOutcome, relay_sse
from core.lifecycle import (
    DEFAULT_DRAIN_QOS_GRACE_S,
    HubLifecycleManager,
    QoSSlotManager,
    _drain_grace_from_env,
)
from core.tool_emulation import sanitize_tool_call
from core.turn_session_manager import BufferedTurnEvent, EmitToolCall, TurnBuffer


class StreamDrainFinishReasonTests(unittest.TestCase):
    """Проверка инвариантов REQ-001..REQ-005 для SSE-потоков и MSP."""

    def test_passthrough_upstream_error_chunk_emits_finish_reason_and_done(self) -> None:
        raw_stream = (
            b'data: {"id":"chatcmpl-1","object":"chat.completion.chunk","created":1700000000,"model":"gpt-5.4","choices":[{"index":0,"delta":{"role":"assistant","content":"Hi"},"finish_reason":null}]}\n\n'
            b'data: {"error":{"message":"Codex upstream stream failed via proxy endpoint f5011bef: ClientPayloadError","type":"proxy_error"}}\n\n'
        )
        reader = io.BytesIO(raw_stream)
        written: list[bytes] = []
        outcome = StreamOutcome()
        with patch.dict(os.environ, {"BRIDGE_GRACEFUL_ERROR_FRAMING_ENABLED": "true"}, clear=False):
            relay_sse(
                reader.readline,
                written.append,
                tool_schemas=None,
                limits=PassthroughLimits(),
                state=outcome,
            )
        joined = b"".join(written).decode("utf-8")
        self.assertTrue(outcome.incomplete)
        self.assertIn('"finish_reason": "stop"', joined)
        self.assertIn("ClientPayloadError", joined)
        self.assertTrue(joined.endswith("data: [DONE]\n\n"))

    def test_passthrough_done_without_finish_reason_when_untrusted_tools(self) -> None:
        raw_stream = (
            b'data: {"id":"chatcmpl-2","object":"chat.completion.chunk","created":1700000000,"model":"gpt-5.4","choices":[{"index":0,"delta":{"content":"Partial"},"finish_reason":null}]}\n\n'
            b"data: [DONE]\n\n"
        )
        reader = io.BytesIO(raw_stream)
        written: list[bytes] = []
        outcome = StreamOutcome()
        with patch.dict(os.environ, {"BRIDGE_GRACEFUL_ERROR_FRAMING_ENABLED": "true"}, clear=False):
            relay_sse(
                reader.readline,
                written.append,
                tool_schemas=None,
                limits=PassthroughLimits(),
                trusted_tools=False,
                state=outcome,
            )
        joined = b"".join(written).decode("utf-8")
        self.assertTrue(outcome.incomplete)
        self.assertIn('"finish_reason": "stop"', joined)
        self.assertTrue(joined.endswith("data: [DONE]\n\n"))

    def test_passthrough_eof_after_open_choice_emits_error_frame_and_done(self) -> None:
        raw_stream = (
            b'data: {"id":"chatcmpl-3","object":"chat.completion.chunk","created":1700000000,"model":"gpt-5.4","choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":null}]}\n\n'
            b": keepalive\n\n"
        )
        reader = io.BytesIO(raw_stream)
        written: list[bytes] = []
        outcome = StreamOutcome()
        with patch.dict(os.environ, {"BRIDGE_GRACEFUL_ERROR_FRAMING_ENABLED": "true"}, clear=False):
            relay_sse(
                reader.readline,
                written.append,
                tool_schemas=None,
                limits=PassthroughLimits(),
                state=outcome,
            )
        joined = b"".join(written).decode("utf-8")
        self.assertTrue(outcome.incomplete)
        self.assertIn('"finish_reason": "stop"', joined)
        self.assertTrue(joined.endswith("data: [DONE]\n\n"))

    def test_buffered_turn_error_event_emits_finish_reason_and_done(self) -> None:
        ev = BufferedTurnEvent(
            seq=3,
            ts=1700000000.0,
            kind="error",
            payload={"message": "Turn cancelled", "type": "cancelled", "code": "turn_cancelled"},
            byte_len=32,
        )
        with patch.dict(os.environ, {"BRIDGE_GRACEFUL_ERROR_FRAMING_ENABLED": "true"}, clear=False):
            frame = ev.to_sse_frame(
                completion_id="chatcmpl-turn-1",
                created=1700000000,
                model="muse-ember-1.0",
            )
        self.assertIn('"finish_reason": "stop"', frame)
        self.assertTrue(frame.endswith("data: [DONE]\n\n"))

    def test_qos_interactive_waiter_survives_drain_event_within_grace(self) -> None:
        drain_ev = threading.Event()
        mgr = QoSSlotManager(max_concurrent=1, reserved_interactive=0, queue_timeout_s=5.0, drain_event=drain_ev)
        ok1, _ = mgr.acquire_slot(is_interactive=True)
        self.assertTrue(ok1)
        result_holder: list[tuple[bool, str]] = []

        def waiter() -> None:
            with patch.dict(os.environ, {"BRIDGE_DRAIN_QOS_GRACE_S": "5.0"}, clear=False):
                res = mgr.acquire_slot(is_interactive=True, timeout=2.0)
                result_holder.append(res)

        t = threading.Thread(target=waiter, daemon=True)
        t.start()
        deadline = time.monotonic() + 1.0
        while mgr.waiting_interactive == 0 and time.monotonic() < deadline:
            time.sleep(0.01)
        drain_ev.set()
        time.sleep(0.05)
        mgr.release_slot(is_interactive=True)
        t.join(timeout=2.0)
        self.assertEqual(result_holder, [(True, "")])
        mgr.release_slot(is_interactive=True)

    def test_drain_qos_grace_env_parsing_honours_zero(self) -> None:
        """F-001: "0"/0.0 — валидная настройка grace, а не повод вернуть дефолт 15.0."""
        with patch.dict(os.environ, {"BRIDGE_DRAIN_QOS_GRACE_S": "0"}, clear=False):
            self.assertEqual(_drain_grace_from_env(), 0.0)
        with patch.dict(os.environ, {"BRIDGE_DRAIN_QOS_GRACE_S": "0.0"}, clear=False):
            self.assertEqual(_drain_grace_from_env(), 0.0)
        with patch.dict(os.environ, {"BRIDGE_DRAIN_QOS_GRACE_S": "2.5"}, clear=False):
            self.assertEqual(_drain_grace_from_env(), 2.5)
        with patch.dict(os.environ, {"BRIDGE_DRAIN_QOS_GRACE_S": "bogus"}, clear=False):
            self.assertEqual(_drain_grace_from_env(), DEFAULT_DRAIN_QOS_GRACE_S)
        with patch.dict(os.environ, {"BRIDGE_DRAIN_QOS_GRACE_S": "-1"}, clear=False):
            self.assertEqual(_drain_grace_from_env(), DEFAULT_DRAIN_QOS_GRACE_S)

    def test_drain_qos_grace_zero_rejects_interactive_waiter_immediately(self) -> None:
        """F-001: при BRIDGE_DRAIN_QOS_GRACE_S="0" ожидающий получает немедленный отказ."""
        drain_ev = threading.Event()
        mgr = QoSSlotManager(max_concurrent=1, reserved_interactive=0, queue_timeout_s=5.0, drain_event=drain_ev)
        self.assertTrue(mgr.acquire_slot(is_interactive=True)[0])
        result_holder: list[tuple[bool, str]] = []

        def waiter() -> None:
            with patch.dict(os.environ, {"BRIDGE_DRAIN_QOS_GRACE_S": "0"}, clear=False):
                result_holder.append(mgr.acquire_slot(is_interactive=True, timeout=2.0))

        t = threading.Thread(target=waiter, daemon=True)
        t.start()
        deadline = time.monotonic() + 1.0
        while mgr.waiting_interactive == 0 and time.monotonic() < deadline:
            time.sleep(0.01)
        drain_ev.set()
        mgr.release_slot(is_interactive=True)
        t.join(timeout=2.0)
        self.assertEqual(result_holder, [(False, "draining")])

    def test_lifecycle_wait_for_drain_hold_respects_timeout(self) -> None:
        lc = HubLifecycleManager(drain_timeout_s=1.0)
        lc.shutdown_requested.set()
        with patch.dict(os.environ, {"BRIDGE_DRAIN_HOLD_TIMEOUT_S": "0.05"}, clear=False):
            t0 = time.monotonic()
            ok = lc.wait_for_drain_hold(is_subagent=False)
            elapsed = time.monotonic() - t0
        self.assertFalse(ok)
        self.assertGreaterEqual(elapsed, 0.04)

    def test_muse_msp_suppresses_unknown_tool_and_extracts_alternate_keys(self) -> None:
        events = MspEvents(reasoning_cap=65536, answer_cap=65536)
        with patch.dict(os.environ, {"BRIDGE_MUSE_SUPPRESS_UNKNOWN_TOOL": "true"}, clear=False):
            delta1 = events.feed(
                "item/started",
                {"item": {"itemId": "it-1", "kind": "toolCall"}},
            )
            delta2 = events.feed(
                "item/completed",
                {"item": {"itemId": "it-1", "kind": "toolCall"}},
            )
            delta3 = events.feed(
                "item/started",
                {"item": {"itemId": "it-2", "kind": "toolCall", "name": "read_file"}},
            )
        self.assertEqual(delta1, "")
        self.assertEqual(delta2, "")
        self.assertEqual(delta3, "[Вызов инструмента: read_file]\n")
        self.assertNotIn("unknown_tool", events.reasoning)

    def test_sanitize_tool_call_rejects_empty_name_and_turn_buffer_omits_empty_name(self) -> None:
        self.assertEqual(
            sanitize_tool_call({"id": "call_1", "type": "function", "function": {"name": "", "arguments": "{}"}}),
            [],
        )
        buf = TurnBuffer()
        with patch.object(buf._fsm, "feed", return_value=[EmitToolCall(call_id="call_1", name="", arguments='{"a":1}', index=0)]):
            evs = buf.feed_fsm_chunk("chunk")
        self.assertEqual(len(evs), 1)
        self.assertNotIn("name", evs[0].payload["function"])

    def test_server_sse_body_skips_duplicate_headers_and_frames_errors_with_null_finish(self) -> None:
        import server as hub_server

        written: list[bytes] = []
        send_response_calls: list[int] = []

        class _DummyLease:
            def record_discard(self, _reason: str) -> None:
                pass

            def record_failure(self, _exc: Any = None) -> None:
                pass

            def record_success(self) -> None:
                pass

        class _DummyConn:
            def gettimeout(self) -> float:
                return 30.0

            def settimeout(self, _t: float | None) -> None:
                pass

        h = object.__new__(hub_server.Handler)
        h._headers_already_sent = True
        h._trace = None
        h._context_pruned = ""
        h._active_managed_turn = None
        h.connection = _DummyConn()
        h.send_response = lambda code: send_response_calls.append(code)  # type: ignore[assignment]
        h._current_lease = lambda: _DummyLease()  # type: ignore[assignment]
        h._emit = lambda frame: (written.append(frame.encode("utf-8")) or True)  # type: ignore[assignment]
        h._telemetry_note = lambda **_kw: None  # type: ignore[assignment]
        h._telemetry_error = lambda _err: None  # type: ignore[assignment]
        h._record_turn_outcome = lambda *_a, **_kw: None  # type: ignore[assignment]
        h._error_body = lambda _out: {"message": "backend failed", "type": "backend_error", "code": 502}  # type: ignore[assignment]
        h._dispatch = lambda _ctx, _ka, sw: (sw("reasoning", "thinking") and {"state": "backend_error", "rc": 1, "err": "backend failed", "backend_kind": "muse"})  # type: ignore[assignment]

        with patch.dict(os.environ, {"BRIDGE_GRACEFUL_ERROR_FRAMING_ENABLED": "true"}, clear=False):
            h._serve_sse_body({"model": "muse-ember-1.0"})

        self.assertEqual(send_response_calls, [])
        joined = b"".join(written).decode("utf-8")
        self.assertIn('"finish_reason": null', joined)
        self.assertIn("backend failed", joined)
        self.assertTrue(joined.endswith("data: [DONE]\n\n"))


if __name__ == "__main__":
    unittest.main()
