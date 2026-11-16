"""W0-A: изоляция изменяемого состояния запросов и логических сессий."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import pytest

import server
from core.http_post_context import PostRequestContext
from core.turn_session_manager import TurnBuffer
from tests.test_bridge_stream_lifecycle import live_run_factory as live_run_factory


def test_run_mutable_state_is_not_shared_between_requests(
    live_run_factory: Callable[[], server.Run],
) -> None:
    first, second = live_run_factory(), live_run_factory()
    for name in (
        "plan",
        "q",
        "cancel",
        "err_box",
        "_msgs",
        "_order",
        "_counted",
        "_foreign_mids",
        "_own",
        "_held",
        "_live_mids",
    ):
        assert getattr(first, name) is not getattr(second, name), name
    first._msgs["message-a"] = {"text": "private-a"}
    first._order.append("message-a")
    first._held["message-a"] = [("text", "private-a", 9)]
    first.cancel.set()
    first.err_box.append("error-a")
    first._publish(("text_delta", ("message-a", "private-a")))
    assert second._msgs == second._held == {}
    assert second._order == second.err_box == []
    assert not second.cancel.is_set()
    assert second.q.empty()
    assert not second.live_invalidated


def test_overflow_of_one_request_does_not_invalidate_another(
    live_run_factory: Callable[[], server.Run],
) -> None:
    first, second = live_run_factory(), live_run_factory()
    for index in range(first.q.maxsize + 1):
        first._publish(("text_delta", ("message-a", str(index))))
    assert first.live_invalidated
    assert not second.live_invalidated
    assert second._last_error == ""
    assert second._publish(("done", (0, "answer-b")))
    assert second.q.get_nowait() == ("done", (0, "answer-b"))


def test_post_context_owns_request_and_transport_controls() -> None:
    first = PostRequestContext(SimpleNamespace(path="/v1/chat/completions"), server)
    second = PostRequestContext(SimpleNamespace(path="/v1/chat/completions"), server)
    caller = {"model": "model-a", "transport_seed": 17}
    first.prepare_route(b"request-a", caller)
    second.prepare_route(b"request-b", {"model": "model-b", "transport_seed": 23})
    first.consume_controls()
    second.consume_controls()
    first_snapshot = first.request
    first_snapshot["model"] = "mutated"
    controls = first.transport_controls
    controls["transport_seed"] = 999
    assert caller == {"model": "model-a", "transport_seed": 17}
    assert first.request == {"model": "model-a"}
    assert second.request == {"model": "model-b"}
    assert first.transport_controls == {"transport_seed": 17}
    assert second.transport_controls == {"transport_seed": 23}
    assert first.raw != second.raw
    fresh = PostRequestContext(SimpleNamespace(path="/v1/chat/completions"), server)
    assert fresh.request == fresh.transport_controls == {}
    assert fresh.raw == b""


def test_session_registry_isolates_locks_and_reference_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(server, "_load_record", lambda _chat: None)
    monkeypatch.setattr(server, "MAX_CHATS", 8)
    registry = server.ChatRegistry()
    first, second = registry.get("session-a"), registry.get("session-b")
    assert registry.get("session-a") is first
    try:
        assert first is not second
        assert first.lock is not second.lock
        first.sid, first.generation = "upstream-a", 7
        assert (second.sid, second.generation) == ("", 0)
        assert first.lock.acquire(blocking=False)
        try:
            assert not first.lock.acquire(blocking=False)
            assert second.lock.acquire(blocking=False)
            second.lock.release()
        finally:
            first.lock.release()
        registry.release(first)
        assert (first.refs, second.refs) == (1, 1)
        assert server.ChatRegistry().chats == {}
    finally:
        registry.release(first)
        registry.release(second)
    assert (first.refs, second.refs) == (0, 0)


def _fill_buffer(buffer: TurnBuffer, gate: Barrier, label: str) -> None:
    gate.wait(timeout=2.0)
    for index in range(8):
        buffer.append("content", f"{label}:{index};")
        buffer.append("reasoning", f"think-{label};")


def test_concurrent_session_buffers_keep_content_and_reasoning_separate() -> None:
    first, second = TurnBuffer(max_bytes=4096), TurnBuffer(max_bytes=4096)
    gate = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(_fill_buffer, buffer, gate, label)
            for buffer, label in ((first, "a"), (second, "b"))
        ]
        for future in futures:
            future.result(timeout=3.0)
    for buffer, label in ((first, "a"), (second, "b")):
        assert buffer.get_content_text() == "".join(f"{label}:{i};" for i in range(8))
        assert buffer.get_reasoning_text() == f"think-{label};" * 8
        assert buffer.last_seq == 16
        assert not buffer.sealed
    fresh = TurnBuffer(max_bytes=4096)
    assert fresh.get_content_text() == fresh.get_reasoning_text() == ""
    assert fresh.last_seq == 0
