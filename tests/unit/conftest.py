"""L1: пробуждение asyncio через pipe без создания реальных сокетов."""

from __future__ import annotations

import asyncio
import io
import os

import pytest


class _PipeSelectorEventLoop(asyncio.SelectorEventLoop):
    """Сохраняет контракт selector-loop, заменяя socketpair обычным pipe."""

    def _make_self_pipe(self) -> None:
        rfd, wfd = os.pipe()
        self._ssock = io.FileIO(rfd, "rb")
        self._csock = io.FileIO(wfd, "wb")
        os.set_blocking(rfd, False)
        os.set_blocking(wfd, False)
        self._internal_fds += 1
        self._add_reader(rfd, self._read_from_self)

    def _close_self_pipe(self) -> None:
        if self._ssock is not None:
            super()._close_self_pipe()

    def _read_from_self(self) -> None:
        while True:
            try:
                data = os.read(self._ssock.fileno(), 4096)
                if not data:
                    break
                self._process_self_data(data)
            except InterruptedError:
                continue
            except BlockingIOError:
                break

    def _write_to_self(self) -> None:
        csock = self._csock
        if csock is None:
            return
        try:
            os.write(csock.fileno(), b"\0")
        except (OSError, ValueError):
            # Executor может завершиться одновременно с закрытием loop.
            pass


class _PipeEventLoopPolicy(asyncio.DefaultEventLoopPolicy):
    """Создаёт только бессокетные циклы для L1-набора."""

    def new_event_loop(self) -> _PipeSelectorEventLoop:
        return _PipeSelectorEventLoop()


@pytest.fixture(scope="session")
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    return _PipeEventLoopPolicy()
