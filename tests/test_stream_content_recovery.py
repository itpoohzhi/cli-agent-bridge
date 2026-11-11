"""Regression-тесты сохранения контента при переполнении Run.q.

Управляемое заполнение делается очередью малого размера (maxsize=2)
вместо реального прогона на run_queue_maxsize из конфига.
"""

import queue

import pytest

from core.backpressure import publish_preserving, stream_content_recovery_enabled

FLAG = "BRIDGE_STREAM_CONTENT_RECOVERY_ENABLED"


def _drain(target: queue.Queue) -> list:
    items = []
    while not target.empty():
        items.append(target.get_nowait())
    return items


def test_overflow_preserves_monotonic_content_and_terminal_rc0() -> None:
    """AC-1: переполнение не даёт пустой успех при terminal rc=0."""
    run_q: queue.Queue = queue.Queue(maxsize=2)
    run_q.put_nowait(("content", "Hello "))
    run_q.put_nowait(("content", "world"))
    assert run_q.full()
    assert publish_preserving(run_q, ("content", "!")) is True
    assert publish_preserving(run_q, ("done", (0, "Hello world!"))) is True
    items = _drain(run_q)
    texts = [payload for kind, payload in items if kind == "content"]
    assert "".join(texts) == "Hello world!"
    assert items[-1] == ("done", (0, "Hello world!"))


def test_overflow_evicts_only_coalescible_notifications_not_terminal() -> None:
    run_q: queue.Queue = queue.Queue(maxsize=2)
    run_q.put_nowait(("done", (0, "kept")))
    run_q.put_nowait(("status", "noise"))
    assert publish_preserving(run_q, ("content", "kept-too")) is True
    assert _drain(run_q) == [("done", (0, "kept")), ("content", "kept-too")]


def test_overflow_without_room_returns_false_and_keeps_queue() -> None:
    """Явный отказ вместо тихого пустого успеха: очередь не искажена."""
    run_q: queue.Queue = queue.Queue(maxsize=2)
    run_q.put_nowait(("done", (0, "x")))
    run_q.put_nowait(("error", "boom"))
    assert publish_preserving(run_q, ("content", "lost")) is False
    assert _drain(run_q) == [("done", (0, "x")), ("error", "boom")]


def test_coalescible_notification_dropped_without_losing_content() -> None:
    run_q: queue.Queue = queue.Queue(maxsize=2)
    run_q.put_nowait(("content", "a"))
    run_q.put_nowait(("content", "b"))
    assert publish_preserving(run_q, ("status", "noise")) is True
    assert _drain(run_q) == [("content", "a"), ("content", "b")]


def test_flag_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(FLAG, raising=False)
    assert stream_content_recovery_enabled({}) is False
    monkeypatch.setenv(FLAG, "true")
    assert stream_content_recovery_enabled({}) is True
    monkeypatch.setenv(FLAG, "false")
    assert stream_content_recovery_enabled({FLAG: True}) is False


def test_config_from_dynamic_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(FLAG, raising=False)
    assert stream_content_recovery_enabled({FLAG: True}) is True
    assert stream_content_recovery_enabled({FLAG: "on"}) is True
    assert stream_content_recovery_enabled({FLAG: False}) is False
    assert stream_content_recovery_enabled({}) is False
