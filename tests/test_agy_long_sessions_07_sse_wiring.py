"""Unit-тесты проводки SSE-рантайма (W7): X-Agy-Conversation-Id loopback, settle_decision, register_post_turn, emit_wire_usage."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_AGY_DIR = str(_ROOT / "bridges/agy-bridge")
if _AGY_DIR not in sys.path:
    sys.path.append(_AGY_DIR)

from agy_runtime.sse_body_runner import _SseBodyRunner  # noqa: E402
from agy_runtime.sse_stream_helpers import SseStreamSession  # noqa: E402
from core.stream_resilience_runtime import StreamResilienceConfig  # noqa: E402
from core.tool_turn_settle_policy import SettleDecision  # noqa: E402


class _FakeHandler:
    def __init__(self, client_address: object = ("127.0.0.1", 5555)) -> None:
        self.client_address = client_address
        self.headers_sent: list[tuple[str, str]] = []
        self.emitted: list[str] = []
        self.close_connection = False
        self.wfile = None

    def send_response(self, status: int) -> None:
        self.status = status

    def send_header(self, k: str, v: str) -> None:
        self.headers_sent.append((k, v))

    def end_headers(self) -> None:
        pass

    def _emit(self, text: str) -> bool:
        self.emitted.append(text)
        return True

    def _error_body(self, out: dict, _resilience: bool) -> dict | None:
        return None if out.get("state") == "done" else {"message": "err"}

    def _usage_payload(self, _raw: dict, resolved: object) -> dict:
        if isinstance(resolved, dict) and not resolved.get("emit_wire_usage", True):
            return {}
        return {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110}


def _make_session(handler: _FakeHandler, ctx: dict) -> SseStreamSession:
    class _FakeToolTurn:
        def __init__(self, _tools, _t, _r, _c) -> None:
            self.calls = [{"id": "call_" + "a" * 24}]
            self.ok = True
            self.error = ""
            self.finished = False

        def feed(self, _x: str) -> bool:
            return True

        def feed_reasoning(self, _x: str) -> bool:
            return True

        def turn_complete(self) -> bool:
            return False

        def settle_decision(self, *, proc_exited: bool, result_received: bool) -> SettleDecision:
            return SettleDecision(
                "clean_complete" if result_received else "wait_done",
                result_received,
                False,
                result_received,
            )

        def finish(self) -> None:
            self.finished = True

    hooks = (lambda _k, d=False: d, lambda _m: None, lambda: "stop", _FakeToolTurn)
    base_ctx = {
        "model": "gemini-4-neon-high",
        "resilience_config": StreamResilienceConfig(),
        "emulate_tools": True,
        "cid_re": re.compile(r"^[0-9a-f-]{8,64}$"),
    }
    base_ctx.update(ctx)
    return SseStreamSession(handler, base_ctx, hooks)


def test_sse_start_emits_conv_header_only_for_loopback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AGY_BRIDGE_EXPOSE_CONV_HEADER", raising=False)
    h_local = _FakeHandler(("127.0.0.1", 5000))
    s_local = _make_session(h_local, {"conversation_id": "12345678-abcd"})
    s_local.start(200, [("Content-Type", "text/event-stream")])
    assert ("X-Agy-Conversation-Id", "12345678-abcd") in h_local.headers_sent
    assert s_local.ctx["emitted_call_ids"]() == ["call_" + "a" * 24]

    h_ext = _FakeHandler(("10.1.2.3", 5000))
    s_ext = _make_session(h_ext, {"conversation_id": "12345678-abcd"})
    s_ext.start(200, [("Content-Type", "text/event-stream")])
    assert all(k != "X-Agy-Conversation-Id" for k, _ in h_ext.headers_sent)


def test_sse_runner_settle_decision_post_turn_order_and_missing_usage() -> None:
    order: list[str] = []
    h = _FakeHandler()
    s = _make_session(h, {"conversation_id": "12345678-abcd"})
    orig_finish = s.tool_turn.finish  # type: ignore[union-attr]
    s.tool_turn.finish = lambda: (order.append("tool_turn.finish"), orig_finish())  # type: ignore[union-attr]
    s.ctx["register_post_turn"] = lambda _out: order.append("register_post_turn")

    runner = _SseBodyRunner(s)
    runner.stop = s.tool_turn.turn_complete  # type: ignore[union-attr]
    # До истечения дедлайна делегирует в tool_turn.settle_decision
    assert runner.settle_decision(proc_exited=False, result_received=True).action == "clean_complete"
    # После истечения дедлайна -> forced_stop немедленно
    runner.deadline = 0.0
    assert runner.settle_decision(proc_exited=False, result_received=True).action == "forced_stop"

    # finish() вызывает register_post_turn СТРОГО ПОСЛЕ tool_turn.finish()
    runner.deadline = float("inf")
    out = {
        "state": "done",
        "rc": 0,
        "conversation_id": "12345678-abcd",
        "usage": {},
        "usage_resolved": {"emit_wire_usage": False},
    }
    runner.finish(out)
    assert order == ["tool_turn.finish", "register_post_turn"]
    # При emit_wire_usage=False usage-чанк не отправляется
    assert all('"usage":' not in chunk for chunk in h.emitted)
    # При ошибке register_post_turn НЕ вызывается
    order.clear()
    runner.finish({"state": "agy_error", "rc": 1})
    assert "register_post_turn" not in order
    _ = SimpleNamespace()
