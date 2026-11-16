"""L1: pipe-loop не создаёт сокеты, пробуждается и освобождает дескрипторы."""

from __future__ import annotations

import asyncio
import errno
import os
import selectors
import socket
import stat
import sys
import threading
from collections.abc import Iterator
from unittest.mock import patch

import pytest

from tests.unit.conftest import _PipeEventLoopPolicy, _PipeSelectorEventLoop


@pytest.fixture
def pipe_loop() -> Iterator[_PipeSelectorEventLoop]:
    loop = _PipeEventLoopPolicy().new_event_loop()
    try:
        yield loop
    finally:
        if not loop.is_closed():
            loop.run_until_complete(loop.shutdown_default_executor())
        loop.close()


def _observe_blocking_select(
    loop: _PipeSelectorEventLoop, monkeypatch: pytest.MonkeyPatch
) -> threading.Event:
    waiting = threading.Event()
    original_select = loop._selector.select

    def select(timeout: float | None = None) -> list[tuple[selectors.SelectorKey, int]]:
        if timeout is None:
            waiting.set()
        return original_select(timeout)

    monkeypatch.setattr(loop._selector, "select", select)
    return waiting


def test_policy_creates_no_sockets() -> None:
    with patch.object(socket.socket, "__new__") as create_socket:
        loop = _PipeEventLoopPolicy().new_event_loop()
        try:
            assert isinstance(loop, asyncio.SelectorEventLoop)
            assert not loop.is_closed()
            assert create_socket.call_count == 0
        finally:
            loop.close()


def test_event_loop_policy_fixture(
    event_loop_policy: asyncio.AbstractEventLoopPolicy,
) -> None:
    # pytest загружает conftest отдельно от импорта tests.unit.conftest.
    fixture_module = sys.modules[type(event_loop_policy).__module__]
    assert isinstance(event_loop_policy, fixture_module._PipeEventLoopPolicy)


def test_pipe_is_nonblocking_and_registered(pipe_loop: _PipeSelectorEventLoop) -> None:
    rfd, wfd = pipe_loop._ssock.fileno(), pipe_loop._csock.fileno()
    for fd in (rfd, wfd):
        assert stat.S_ISFIFO(os.fstat(fd).st_mode)
        assert not os.get_blocking(fd)
    key = pipe_loop._selector.get_key(rfd)
    assert key.events == selectors.EVENT_READ
    assert key.data[0]._callback == pipe_loop._read_from_self
    assert pipe_loop._internal_fds == 1


def test_call_soon_threadsafe_wakes_blocked_loop(
    pipe_loop: _PipeSelectorEventLoop, monkeypatch: pytest.MonkeyPatch
) -> None:
    waiting = _observe_blocking_select(pipe_loop, monkeypatch)
    delivered: list[str] = []

    def notify() -> None:
        waiting.wait()
        pipe_loop.call_soon_threadsafe(delivered.append, "wake")
        pipe_loop.call_soon_threadsafe(pipe_loop.stop)

    worker = threading.Thread(target=notify)
    worker.start()
    try:
        pipe_loop.run_forever()
    finally:
        worker.join()
    assert delivered == ["wake"]


def test_executor_completion_wakes_blocked_loop(
    pipe_loop: _PipeSelectorEventLoop, monkeypatch: pytest.MonkeyPatch
) -> None:
    waiting = _observe_blocking_select(pipe_loop, monkeypatch)

    def work() -> int:
        waiting.wait()
        return 42

    async def run_job() -> int:
        return await pipe_loop.run_in_executor(None, work)

    assert pipe_loop.run_until_complete(run_job()) == 42


def test_self_pipe_drains_and_dispatches_data(
    pipe_loop: _PipeSelectorEventLoop, monkeypatch: pytest.MonkeyPatch
) -> None:
    received: list[bytes] = []
    monkeypatch.setattr(pipe_loop, "_process_self_data", received.append)
    pipe_loop._write_to_self()
    pipe_loop._read_from_self()
    pipe_loop._read_from_self()
    assert received == [b"\0"]


def test_close_releases_both_fds_and_is_idempotent(
    pipe_loop: _PipeSelectorEventLoop,
) -> None:
    fds = (pipe_loop._ssock.fileno(), pipe_loop._csock.fileno())
    pipe_loop.close()
    pipe_loop.close()
    pipe_loop._close_self_pipe()
    pipe_loop._write_to_self()
    assert pipe_loop.is_closed()
    assert pipe_loop._ssock is pipe_loop._csock is None
    assert pipe_loop._internal_fds == 0
    for fd in fds:
        with pytest.raises(OSError) as error:
            os.fstat(fd)
        assert error.value.errno == errno.EBADF


@pytest.mark.parametrize("failure", (BlockingIOError, BrokenPipeError, ValueError))
def test_wakeup_tolerates_full_or_closed_pipe(
    pipe_loop: _PipeSelectorEventLoop,
    monkeypatch: pytest.MonkeyPatch,
    failure: type[Exception],
) -> None:
    def write(fd: int, data: bytes) -> int:
        raise failure

    monkeypatch.setattr(os, "write", write)
    pipe_loop._write_to_self()
