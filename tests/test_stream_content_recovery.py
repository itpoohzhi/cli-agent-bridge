"""Regression-тесты сохранения контента при переполнении Run.q.

Управляемое заполнение делается очередью малого размера (maxsize=2)
вместо реального прогона на run_queue_maxsize из конфига.
"""

import queue
import threading

import pytest

from core.backpressure import publish_preserving, stream_content_recovery_enabled

FLAG = "BRIDGE_STREAM_CONTENT_RECOVERY_ENABLED"
LIMIT = "BRIDGE_STREAM_CONTENT_RECOVERY_MAX_MERGED_BYTES"


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


def test_repeated_delta_content_is_appended_not_deduped() -> None:
    """RW-001: повторяющиеся дельты не схлопываются префиксной эвристикой."""
    run_q: queue.Queue = queue.Queue(maxsize=1)
    run_q.put_nowait(("content", "ha"))
    assert publish_preserving(run_q, ("content", "ha")) is True
    assert _drain(run_q) == [("content", "haha")]


def test_prefix_delta_is_appended_not_treated_as_snapshot() -> None:
    """RW-001: дельта, начинающаяся с прежнего текста, дописывается целиком."""
    run_q: queue.Queue = queue.Queue(maxsize=1)
    run_q.put_nowait(("content", "ha"))
    assert publish_preserving(run_q, ("content", "haha")) is True
    assert _drain(run_q) == [("content", "hahaha")]


def test_unknown_kind_is_not_merged_on_overflow() -> None:
    """RW-001: неизвестный kind не входит в белый список content и не склеивается."""
    run_q: queue.Queue = queue.Queue(maxsize=1)
    run_q.put_nowait(("mystery", "a"))
    assert publish_preserving(run_q, ("mystery", "b")) is False
    assert _drain(run_q) == [("mystery", "a")]


def test_queue_join_and_unfinished_tasks_after_merge() -> None:
    """RW-002: публичный API сохраняет счётчик незавершённых задач и join."""
    run_q: queue.Queue = queue.Queue(maxsize=2)
    run_q.put_nowait(("content", "a"))
    run_q.put_nowait(("content", "b"))
    assert publish_preserving(run_q, ("content", "c")) is True
    assert run_q.unfinished_tasks == 2
    while not run_q.empty():
        run_q.get_nowait()
        run_q.task_done()
    joined = threading.Thread(target=run_q.join, daemon=True)
    joined.start()
    joined.join(timeout=2)
    assert not joined.is_alive()
    assert run_q.unfinished_tasks == 0


def test_iteration_freed_slot_is_used_for_terminal_item() -> None:
    """RW-002: освобождённый коалесценцией слот сразу занимает terminal item."""
    run_q: queue.Queue = queue.Queue(maxsize=4)
    for text in ("a", "b", "c", "d"):
        run_q.put_nowait(("content", text))
    assert publish_preserving(run_q, ("done", (0, "abcd"))) is True
    items = _drain(run_q)
    texts = [payload for kind, payload in items if kind == "content"]
    assert "".join(texts) == "abcd"
    assert items[-1] == ("done", (0, "abcd"))


def test_bound_merged_payload_fails_closed_without_content_loss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RW-002: превышение байтового предела — явный False без потери контента."""
    monkeypatch.setenv(LIMIT, "3")
    run_q: queue.Queue = queue.Queue(maxsize=2)
    run_q.put_nowait(("content", "ab"))
    run_q.put_nowait(("content", "cd"))
    assert publish_preserving(run_q, ("content", "ef")) is False
    assert _drain(run_q) == [("content", "ab"), ("content", "cd")]


def test_bound_merged_payload_via_dynamic_config_within_limit() -> None:
    """RW-002: предел из dynamic_config допускает слияние в своих границах."""
    run_q: queue.Queue = queue.Queue(maxsize=2)
    run_q.put_nowait(("content", "ab"))
    run_q.put_nowait(("content", "cd"))
    assert publish_preserving(run_q, ("content", "ef"), {LIMIT: 10}, {}) is True
    assert _drain(run_q) == [("content", "ab"), ("content", "cdef")]


def _make_run(maxsize: int = 2):
    """Минимальный Run без полного __init__: только поля, нужные _publish."""
    import server

    run = object.__new__(server.Run)
    run.sse_writer = object()
    run.q = queue.Queue(maxsize=maxsize)
    run.live_invalidated = False
    run._last_error = None
    run.active_turn = ""
    return run


def test_run_publish_integration_flag_true_preserves_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RW-003: переполнение Run.q при флаге true не инвалидирует live-стрим."""
    monkeypatch.setenv(FLAG, "true")
    run = _make_run()
    run.q.put_nowait(("content", "Hello "))
    run.q.put_nowait(("content", "world"))
    assert run.q.full()
    assert run._publish(("content", "!")) is True
    assert run._publish(("done", (0, "Hello world!"))) is True
    assert run.live_invalidated is False
    assert not run._last_error
    items = _drain(run.q)
    texts = [payload for kind, payload in items if kind == "content"]
    assert "".join(texts) == "Hello world!"
    assert items[-1] == ("done", (0, "Hello world!"))


def test_run_publish_integration_flag_false_keeps_old_fail_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RW-003: флаг false сохраняет прежний fail-close с live_invalidated."""
    monkeypatch.setenv(FLAG, "false")
    run = _make_run()
    run.q.put_nowait(("content", "Hello "))
    run.q.put_nowait(("content", "world"))
    assert run.q.full()
    assert run._publish(("content", "!")) is not True
    assert run.live_invalidated is True
    assert run._last_error
    assert _drain(run.q) == [("content", "Hello "), ("content", "world")]
