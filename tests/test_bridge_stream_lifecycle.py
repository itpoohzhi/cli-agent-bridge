"""W0-A: воспроизведения дефектов SSE без внешних CLI и настенных ожиданий."""

from __future__ import annotations

import os
import socket
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Barrier
from typing import Any

import pytest

import server
from adapters import passthrough_adapter as passthrough
from core import liveness_signals
from core.passthrough_sliding_window import SlidingDeadline


def _check_contract(defect: bool, evidence: object) -> None:
    """В red-режиме требует доказанного дефекта, иначе проверяет контракт."""
    if os.environ.get("BRIDGE_EXPECT_RED") == "1":
        assert defect, f"Дефект baseline больше не воспроизводится: {evidence!r}"
    else:
        assert not defect, evidence


baseline_defect = pytest.mark.xfail(
    os.environ.get("BRIDGE_EXPECT_RED") != "1",
    reason="baseline defect",
    raises=AssertionError,
    strict=True,
)


@pytest.mark.red_repro
@baseline_defect
def test_red_repro_sse_accepted_socket_tcp_nodelay() -> None:
    """EVD-002: проверяет реальный сокет после Server.accept и Handler.setup."""
    with server.Server(("127.0.0.1", 0), server.Handler) as httpd:
        httpd.socket.settimeout(2.0)
        with socket.create_connection(httpd.server_address, timeout=2.0):
            accepted, address = httpd.get_request()
            with accepted:
                handler = server.Handler.__new__(server.Handler)
                handler.request = accepted
                handler.client_address = address
                handler.server = httpd
                handler.setup()
                try:
                    actual = accepted.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY)
                finally:
                    handler.finish()
    assert actual in (0, 1)
    _check_contract(actual == 0, {"TCP_NODELAY": actual})


@dataclass
class _Clock:
    """Часы двигает только чтение очередной строки upstream."""

    now: float = 100.0

    def monotonic(self) -> float:
        return self.now


def _scripted_source(
    clock: _Clock, script: list[tuple[float, bytes]]
) -> Callable[[int], bytes]:
    rows = iter(script)

    def readline(_limit: int) -> bytes:
        delay, line = next(rows, (0.0, b""))
        clock.now += delay
        return line

    return readline


def _content(text: str) -> bytes:
    return (
        'data: {"choices":[{"index":0,"delta":{"content":"'
        + text
        + '"},"finish_reason":null}]}\n'
    ).encode()


@contextmanager
def _reader(
    monkeypatch: pytest.MonkeyPatch, script: list[tuple[float, bytes]]
) -> Iterator[tuple[passthrough._TimedSseReader, _Clock]]:
    clock = _Clock()
    # Не подменяем общий time.monotonic: блокировки потоков используют часы ОС.
    monkeypatch.setattr(passthrough, "time", clock)
    monkeypatch.setattr(liveness_signals, "time", clock)
    limits = passthrough.PassthroughLimits(
        total_timeout_s=1.0,
        idle_timeout_s=1.0,
        stream_safety_cap_s=20.0,
        heartbeat_interval_s=10.0,
        poll_interval_s=0.01,
        reader_join_timeout_s=2.0,
    )
    cell = SlidingDeadline(clock.now + limits.total_timeout_s)
    cell.arm_for(clock.now, limits)
    reader = passthrough._TimedSseReader(
        _scripted_source(clock, script), lambda _frame: None, limits, cell
    )
    try:
        yield reader, clock
    finally:
        reader.close()
        assert not reader.thread.is_alive(), "Утечка reader-потока"


@pytest.mark.red_repro
@baseline_defect
@pytest.mark.parametrize("comment", [b": heartbeat\n", b": keepalive\n"])
def test_red_repro_incoming_heartbeat_does_not_slide_deadline(
    monkeypatch: pytest.MonkeyPatch, comment: bytes
) -> None:
    """Входящие комментарии продолжаются, но исходный срок обрывает чтение."""
    script = [(0.0, _content("start")), (0.0, b"\n")]
    script += [
        (delay, line)
        for _ in range(5)
        for delay, line in ((0.4, comment), (0.0, b"\n"))
    ]
    script += [(0.0, b"data: [DONE]\n"), (0.0, b"\n")]
    comments = 0
    timed_out = False
    with _reader(monkeypatch, script) as (reader, clock):
        initial = reader.cell.deadline_s
        try:
            for raw, data in passthrough.iter_sse_events(reader.readline, 4096):
                reader.progress.note(data)
                comments += int(comment in raw)
                if data == "[DONE]":
                    break
        except TimeoutError as exc:
            assert str(exc) == "upstream stream deadline exceeded"
            timed_out = True
        assert comments >= 2, "Сценарий не доставил heartbeat до исходного срока"
        assert clock.now - 100.0 > 1.0
        defect = timed_out and reader.cell.deadline_s == initial
    _check_contract(defect, {"comments": comments, "timed_out": timed_out})


def test_useful_sse_chunks_slide_beyond_initial_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Контроль: полезные данные продлевают окно в том же реальном reader."""
    script = [
        (delay, line)
        for _ in range(5)
        for delay, line in ((0.4, _content("useful")), (0.0, b"\n"))
    ]
    script += [(0.0, b"data: [DONE]\n"), (0.0, b"\n")]
    with _reader(monkeypatch, script) as (reader, clock):
        frames = []
        for _raw, data in passthrough.iter_sse_events(reader.readline, 4096):
            reader.progress.note(data)
            frames.append(data)
        assert frames[-1] == "[DONE]"
        assert len(frames) == 6
        assert clock.now == pytest.approx(102.0)
        assert reader.cell.deadline_s == pytest.approx(103.0)


@pytest.fixture
def live_run_factory(monkeypatch: pytest.MonkeyPatch) -> Callable[[], server.Run]:
    """Создаёт настоящие Run, отключая только внешний CLI-воркер."""
    monkeypatch.setattr(server.Run, "_work", lambda _self: None)
    monkeypatch.setattr(server, "_log", lambda _message: None)
    monkeypatch.setattr(server, "RUN_QUEUE_MAXSIZE", 2)

    def create() -> server.Run:
        run = server.Run({"path": "ephemeral"}, None, False, lambda _k, _t: True)
        run.thread.join(timeout=2.0)
        assert not run.thread.is_alive()
        return run

    return create


def _publish_burst(run: server.Run, gate: Barrier, request_id: str) -> tuple[bool, ...]:
    gate.wait(timeout=2.0)
    events: tuple[tuple[str, Any], ...] = (
        ("text_delta", (request_id, "first")),
        ("text_delta", (request_id, "second")),
        ("text_delta", (request_id, "third")),
        ("done", (0, "")),
    )
    return tuple(run._publish(event) for event in events)


@pytest.mark.red_repro
@baseline_defect
def test_red_repro_concurrent_sse_queue_overflow_loses_terminal(
    live_run_factory: Callable[[], server.Run],
) -> None:
    """Четыре одновременных SSE-хода теряют хвост и terminal при bounded burst."""
    runs = [live_run_factory() for _ in range(4)]
    assert len({id(run.q) for run in runs}) == len(runs)
    gate = Barrier(len(runs))
    with ThreadPoolExecutor(max_workers=len(runs)) as pool:
        futures = [
            pool.submit(_publish_burst, run, gate, f"request-{index}")
            for index, run in enumerate(runs)
        ]
        published = [future.result(timeout=3.0) for future in futures]
    retained = [[run.q.get_nowait() for _ in range(run.q.qsize())] for run in runs]
    for index, events in enumerate(retained):
        assert events, "Пустая очередь не доказывает конкурентное переполнение"
        assert all(
            event[1][0] == f"request-{index}"
            for event in events
            if event[0] == "text_delta"
        )
    defect = all(
        flags == (True, True, False, False)
        and run.live_invalidated
        and run._last_error == "Run.q overflow"
        and all(kind != "done" for kind, _payload in events)
        for run, flags, events in zip(runs, published, retained, strict=True)
    )
    _check_contract(defect, published)
