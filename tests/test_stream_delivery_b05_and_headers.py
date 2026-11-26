"""W2 (Stage 3): регрессионные L1/L2-тесты [B-05], сброса tool_turn и X-Bridge-Tool-Sanitized."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
_AGY_DIR = str(_ROOT / "bridges" / "agy-bridge")
if _AGY_DIR not in sys.path:
    sys.path.append(_AGY_DIR)

from agy_runtime.sse_stream_helpers import SseStreamSession  # noqa: E402
from core.stream_resilience_runtime import StreamResilienceConfig  # noqa: E402
from resilience_wiring_support import load_server  # noqa: E402


class _FakeSseHandler:
    def __init__(self) -> None:
        self.client_address = ("127.0.0.1", 5555)
        self.wfile = SimpleNamespace(write=lambda data: len(data), flush=lambda: None)
        self.close_connection = False
        self.status = 0
        self.headers_sent: list[tuple[str, str]] = []
        self.emitted: list[str] = []

    def send_response(self, code: int) -> None:
        self.status = code

    def send_header(self, key: str, value: str) -> None:
        self.headers_sent.append((key, value))

    def end_headers(self) -> None:
        pass

    def _emit(self, data: str) -> bool:
        self.emitted.append(data)
        return True

    def _arm_flush_window(self, _ctx: dict[str, Any]) -> None:
        pass

    def _graceful_notice(self, reason: str, limit_s: object) -> str:
        return f"\n[graceful:{reason}:{limit_s}]"


def _make_session(
    *,
    emulate_tools: bool = False,
    tool_turn_cls: Any = None,
    emit_tool_trace: bool = True,
) -> tuple[SseStreamSession, _FakeSseHandler, dict[str, Any]]:
    handler = _FakeSseHandler()
    tools = [
        {
            "type": "function",
            "function": {
                "name": "read",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                },
            },
        }
    ]
    ctx: dict[str, Any] = {
        "model": "test-model",
        "turn_id": "turn-b05",
        "conversation_id": "12345678-abcd",
        "resilience_config": StreamResilienceConfig(),
        "emulate_tools": emulate_tools,
        "tools": tools if emulate_tools else [],
    }
    flags = {
        "AGY_BRIDGE_STREAM_RESILIENCE_ENABLED": True,
        "graceful_timeout_on_partial": True,
        "graceful_interruption_on_partial": True,
        "emit_tool_trace": emit_tool_trace,
    }
    hooks = (
        lambda name, default=False: flags.get(name, default),
        lambda _msg: None,
        lambda: "stop",
        tool_turn_cls,
    )
    return SseStreamSession(handler, ctx, hooks), handler, ctx


def _parse_deltas(frames: list[str]) -> list[dict[str, Any]]:
    deltas: list[dict[str, Any]] = []
    for raw in frames:
        for line in raw.splitlines():
            if not line.startswith("data: "):
                continue
            payload = line[len("data: ") :]
            if payload == "[DONE]":
                continue
            obj = json.loads(payload)
            choices = obj.get("choices") or []
            if choices:
                deltas.append(choices[0].get("delta") or {})
    return deltas


def test_b05_partial_timeout_no_duplicate_on_unbuffered_stream() -> None:
    session, handler, _ctx = _make_session(emulate_tools=False)
    partial = "Частичный ответ модели"
    assert session.stream_text(partial) is True
    out: dict[str, Any] = {
        "state": "idle_timeout",
        "timeout_limit_s": 30,
        "conversation_id": "12345678-abcd",
        "retained_events": [("text", partial)],
    }
    session.finalize_timeout(out)
    assert out.get("graceful_done") is True
    assert handler.emitted[-1] == "data: [DONE]\n\n"
    content = "".join(d.get("content", "") for d in _parse_deltas(handler.emitted))
    assert content.count(partial) == 1
    assert "[graceful:idle_timeout:30]" in content
    assert content == partial + "\n[graceful:idle_timeout:30]"
    assert session.b05_skipped_chars == len(partial)
    assert session.b05_flushed_tail_chars == 0


def test_b05_partial_timeout_rechunked_partial_overlap_emits_only_suffix() -> None:
    session, handler, _ctx = _make_session(emulate_tools=False)
    assert session.stream_text("Частичный ") is True
    assert session.stream_text("прог") is True
    out: dict[str, Any] = {
        "state": "idle_timeout",
        "timeout_limit_s": 15,
        "conversation_id": "12345678-abcd",
        "retained_events": [("text", "Частичный прогресс до таймаута")],
    }
    session.finalize_timeout(out)
    content = "".join(d.get("content", "") for d in _parse_deltas(handler.emitted))
    before_notice = content.split("\n[graceful:", 1)[0]
    assert before_notice == "Частичный прогресс до таймаута"
    assert session.b05_skipped_chars == len("Частичный прог")
    assert session.b05_flushed_tail_chars == len("ресс до таймаута")


def test_b05_partial_timeout_with_held_partial_tool_call_flushes_without_loss_or_dup() -> (
    None
):
    srv = load_server()
    session, handler, _ctx = _make_session(
        emulate_tools=True, tool_turn_cls=srv._ToolTurn
    )
    prefix = "Префикс. "
    part_call = '<tool_call>{"name":"read",'
    rest_call = '"arguments":{"path":"a.py"}}</tool_call>'
    assert session.stream_text(prefix) is True
    assert session.stream_text(part_call) is True
    out: dict[str, Any] = {
        "state": "idle_timeout",
        "timeout_limit_s": 20,
        "conversation_id": "12345678-abcd",
        "retained_events": [("text", prefix + part_call + rest_call)],
    }
    session.finalize_timeout(out)
    assert out.get("graceful_done") is True
    deltas = _parse_deltas(handler.emitted)
    content = "".join(d.get("content", "") for d in deltas)
    reasoning = "".join(d.get("reasoning_content", "") for d in deltas)
    tool_calls = [tc for d in deltas for tc in (d.get("tool_calls") or [])]
    assert "<tool_call>" not in content
    assert "</tool_call>" not in content
    assert (content + reasoning).count("Префикс.") == 1
    assert len(tool_calls) == 1
    assert tool_calls[0]["function"]["name"] == "read"
    assert json.loads(tool_calls[0]["function"]["arguments"]) == {"path": "a.py"}
    assert session.b05_skipped_chars == len(prefix + part_call)
    assert session.b05_flushed_tail_chars == len(rest_call)


def test_reset_precommit_emitted_reinstantiates_clean_tool_turn_and_keeps_invariant() -> (
    None
):
    srv = load_server()
    session, _handler, ctx = _make_session(
        emulate_tools=True, tool_turn_cls=srv._ToolTurn
    )
    old_turn = session.tool_turn
    assert old_turn is not None
    assert ctx["stream_committed"] is False
    assert session.stream_text('Префикс <tool_call>{"name":"read",') is True
    assert session.stream_reasoning("думаю") is True
    assert session.on_tool_trace({"step_index": 1, "tool_name": "read_file"}) is True
    assert old_turn._normalizer.has_open_tool_call() is True
    assert session.emitted_stream_text
    assert session.emitted_reasoning_text
    assert len(session.emitted_tool_trace_keys) == 1

    session.reset_precommit_emitted()

    assert session.emitted_stream_text == ""
    assert session.emitted_reasoning_text == ""
    assert session.emitted_tool_trace_keys == []
    assert session.tool_turn is not None
    assert session.tool_turn is not old_turn
    assert session.tool_turn._normalizer.has_open_tool_call() is False
    assert ctx["tool_stop"] == session.tool_turn.turn_complete
    assert session.stream_text("Чистый текст") is True
    assert session.emitted_stream_text == "Чистый текст"


def test_b05_partial_timeout_no_duplicate_reasoning_and_tool_trace() -> None:
    session, handler, _ctx = _make_session(emulate_tools=False, emit_tool_trace=True)
    assert session.stream_reasoning("Шаг 1. ") is True
    assert session.on_tool_trace({"step_index": 7, "tool_name": "read_file"}) is True
    emitted_reasoning = session.emitted_reasoning_text
    assert emitted_reasoning.startswith("Шаг 1. ")
    assert "tool" in emitted_reasoning
    out: dict[str, Any] = {
        "state": "idle_timeout",
        "timeout_limit_s": 10,
        "conversation_id": "12345678-abcd",
        "retained_events": [
            ("reasoning", "Шаг 1. "),
            ("reasoning", emitted_reasoning[len("Шаг 1. ") :] + "Шаг 2."),
            ("tool_trace", {"tool_name": "read_file", "step_index": 7}),
            ("tool_trace", {"step_index": 8, "tool_name": "grep"}),
        ],
    }
    session.finalize_timeout(out)
    assert out.get("graceful_done") is True
    reasoning = "".join(
        d.get("reasoning_content", "") for d in _parse_deltas(handler.emitted)
    )
    assert reasoning.count("Шаг 1.") == 1
    assert "Шаг 2." in reasoning
    assert reasoning.count("tool — done") == 2  # ровно один marker на trace
    assert session.b05_skipped_chars > len("Шаг 1. ")
    assert session.b05_flushed_tail_chars > 0


def test_start_emits_tool_sanitized_header_iff_tool_turn_is_not_none() -> None:
    class _FalsyToolTurn:
        def __init__(self, *_a: Any) -> None:
            self.calls: list[dict[str, Any]] = []

        def __bool__(self) -> bool:
            return False

        def feed(self, _text: str) -> bool:
            return True

        def feed_reasoning(self, _text: str) -> bool:
            return True

        def turn_complete(self) -> bool:
            return False

        def finish(self) -> None:
            pass

    srv = load_server()
    s_active, h_active, _ = _make_session(
        emulate_tools=True, tool_turn_cls=srv._ToolTurn
    )
    s_active.start(200, [("Content-Type", "text/event-stream")])
    assert ("X-Bridge-Tool-Sanitized", "1") in h_active.headers_sent

    s_falsy, h_falsy, _ = _make_session(
        emulate_tools=True, tool_turn_cls=_FalsyToolTurn
    )
    assert s_falsy.tool_turn is not None and bool(s_falsy.tool_turn) is False
    s_falsy.start(200, [("Content-Type", "text/event-stream")])
    assert ("X-Bridge-Tool-Sanitized", "1") in h_falsy.headers_sent

    s_none, h_none, _ = _make_session(emulate_tools=False)
    assert s_none.tool_turn is None
    s_none.start(200, [("Content-Type", "text/event-stream")])
    assert all(k.lower() != "x-bridge-tool-sanitized" for k, _ in h_none.headers_sent)
