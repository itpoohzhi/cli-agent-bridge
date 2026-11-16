"""Фейки внешних границ Claude-моста: очередь событий, процесс и загрузка модуля.

Подменяются только процесс, транспорт и очередь; разбор HTTP, диспетчеризация,
нормализация и формирование ответа остаются продакшен-кодом моста.
"""

from __future__ import annotations

import functools
import importlib.machinery
import importlib.util
import queue
import sys
import uuid
from collections import deque
from collections.abc import Callable, Iterable
from pathlib import Path
from types import CodeType
from typing import Any

import pytest

BRIDGE_SERVER = (
    Path(__file__).resolve().parents[2] / "bridges" / "claude-p-bridge" / "server.py"
)
_CODE_NAME = "claude_p_bridge_inmem"
EMPTY = object()
Hook = Callable[[], None]


@functools.cache
def _bridge_code() -> CodeType:
    """Код-объект настоящего `server.py`, полученный штатным загрузчиком импорта.

    Код неизменяем и общий; изменяемое состояние (глобалы, классы, очереди) создаёт
    только `exec` в свежем пространстве имён. Ленивый вызов оставляет ошибку чтения
    или компиляции исходника ошибкой теста, а не сбором тестов.
    """
    loader = importlib.machinery.SourceFileLoader(_CODE_NAME, str(BRIDGE_SERVER))
    code = loader.get_code(_CODE_NAME)
    if code is None:
        raise ImportError(f"no code object for {BRIDGE_SERVER}")
    return code


def load_bridge(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Загружает мост под уникальным именем; sys.modules и sys.path откатываются.

    Тело модуля исполняется заново в каждом тесте (как `exec_module`), поэтому все
    глобалы, классы и блокировки моста свои у каждого теста.
    """
    name = f"claude_p_bridge_inmem_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(name, BRIDGE_SERVER)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setitem(sys.modules, name, module)
    exec(_bridge_code(), module.__dict__)
    return module


class ScriptedQueue:
    """Очередь событий хода: событие, `EMPTY` (пустой опрос) или хук без аргументов.

    Исчерпанный сценарий падает, а не возвращает `queue.Empty`: иначе цикл
    `execute` крутился бы бесконечно без реального ожидания.
    """

    def __init__(self, script: Iterable[Any]) -> None:
        self._items: deque[Any] = deque(script)
        self.timeouts: list[float | None] = []

    def get(self, timeout: float | None = None) -> Any:
        self.timeouts.append(timeout)
        while self._items:
            item = self._items.popleft()
            if item is EMPTY:
                raise queue.Empty
            if callable(item):
                item()
                continue
            return item
        raise AssertionError("script exhausted before the done event")

    @property
    def pending(self) -> int:
        return len(self._items)


class FakeProc:
    """Дочерний процесс: `wait` не ждёт, сигналов не получает."""

    def __init__(self, pid: int = 4242) -> None:
        self.pid = pid
        self.waits: list[float | None] = []

    def wait(self, timeout: float | None = None) -> int:
        self.waits.append(timeout)
        return 0

    def poll(self) -> int:
        return 0


class FakeRun:
    """Ход `claude -p` без процесса: только очередь событий и признак закрытия."""

    def __init__(self, script: Iterable[Any], proc: FakeProc | None = None) -> None:
        self.q = ScriptedQueue(script)
        self.err_box: list[str] = []
        self.proc = proc
        self.closed = False

    def close(self) -> None:
        self.closed = True


class RunFactory:
    """Подставляется вместо `bridge.Run`; хранит созданные ходы и промпты."""

    def __init__(self, script: Iterable[Any]) -> None:
        self.script = tuple(script)
        self.runs: list[FakeRun] = []
        self.prompts: list[str] = []

    def __call__(
        self, prompt: str, model: str, effort: str, tag: str, img_dir: Any = None
    ) -> FakeRun:
        self.prompts.append(prompt)
        run = FakeRun(self.script)
        self.runs.append(run)
        return run

    @property
    def prompt(self) -> str:
        return self.prompts[-1]

    @property
    def closed(self) -> list[bool]:
        return [run.closed for run in self.runs]


def done_script(*events: Any, rc: int = 0) -> list[Any]:
    usage = {"usage": {"input_tokens": 3, "output_tokens": 2}}
    return [*events, ("result", usage), ("done", rc)]


def text_script(text: str, chunk_size: int) -> list[Any]:
    return done_script(
        *(("text", text[i : i + chunk_size]) for i in range(0, len(text), chunk_size))
    )


def patch_bridge(module: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ключ авторизации, нулевой drain stderr и живой клиент: общий базис L1-тестов."""
    monkeypatch.setattr(module, "AUTH_KEY", "test-key")
    monkeypatch.setattr(module, "STDERR_DRAIN_S", 0.0)
    monkeypatch.setattr(module, "_client_gone", lambda _conn: False)


@pytest.fixture
def bridge(monkeypatch: pytest.MonkeyPatch) -> Any:
    module = load_bridge(monkeypatch)
    patch_bridge(module, monkeypatch)
    return module
