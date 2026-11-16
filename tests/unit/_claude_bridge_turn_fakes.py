"""Фейки границ `_Execution` Claude-моста: часы, процессная группа, watchdog, колбэки."""

from __future__ import annotations

import os
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import pytest

from tests.unit._claude_bridge_tool_fakes import (
    FakeProc,
    FakeRun,
    bridge as bridge,  # noqa: F401
)


class FakeClock:
    """Подмена модуля `time` моста: часы идут только вручную, `sleep` не спит."""

    def __init__(self, now: float = 1000.0) -> None:
        self.now = now
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)

    def __getattr__(self, name: str) -> Any:
        return getattr(time, name)


class FakeOs:
    """Подмена `os` моста: `killpg` только записывается, остальное — настоящий `os`."""

    def __init__(self) -> None:
        self.killed: list[tuple[int, int]] = []

    def killpg(self, pgid: int, sig: int) -> None:
        self.killed.append((pgid, sig))

    def __getattr__(self, name: str) -> Any:
        return getattr(os, name)


class FakeController:
    """Контроллер watchdog: фиксированный вердикт `check`, учёт активности и закрытия."""

    def __init__(
        self, verdict: tuple[bool, str, Any] = (False, "", None), interval: float = 5.0
    ) -> None:
        self.watchdog_interval_s = interval
        self.verdict = verdict
        self.checked: list[int | None] = []
        self.activity: list[str] = []
        self.closed = False

    def check(self, pgid: int | None = None) -> tuple[bool, str, Any]:
        self.checked.append(pgid)
        return self.verdict

    def record_activity(self, kind: str = "protocol") -> None:
        self.activity.append(kind)

    def close(self) -> None:
        self.closed = True


class Sinks:
    """Колбэки приёмника: записывают вывод; `keepalive=None` убирает колбэк keepalive."""

    def __init__(self, keepalive: bool | None = True, accept_text: bool = True) -> None:
        self.text: list[str] = []
        self.reasoning: list[str] = []
        self.calls: list[dict] = []
        self.keepalives = 0
        self._keepalive = keepalive
        self._accept_text = accept_text

    def on_text(self, value: str) -> bool:
        self.text.append(value)
        return self._accept_text

    def on_reasoning(self, value: str) -> bool:
        self.reasoning.append(value)
        return True

    def on_tool_call(self, call: dict) -> bool:
        self.calls.append(call)
        return True

    def beat(self) -> bool:
        self.keepalives += 1
        return bool(self._keepalive)

    def callbacks(self, module: Any) -> Any:
        keepalive = None if self._keepalive is None else self.beat
        return module._Callbacks(
            self.on_text, self.on_reasoning, self.on_tool_call, keepalive
        )


@dataclass
class Pump:
    execution: Any
    run: FakeRun
    sinks: Sinks
    proc: FakeProc


def build_pump(
    module: Any, script: Iterable[Any] = (), sinks: Sinks | None = None
) -> Pump:
    """Реальный `_Execution` OFF/TEXT на фейковом ходе; часы и `os` уже подменены."""
    sinks = sinks or Sinks()
    proc = FakeProc()
    run = FakeRun(script, proc)
    spec = module.build_mode_spec(module.ToolMode.OFF)
    execution = module._Execution(run, sinks.callbacks(module), spec, None)
    return Pump(execution, run, sinks, proc)


@pytest.fixture
def clock(bridge: Any, monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    fake = FakeClock()
    monkeypatch.setattr(bridge, "time", fake)
    return fake


@pytest.fixture
def fake_os(bridge: Any, monkeypatch: pytest.MonkeyPatch) -> FakeOs:
    fake = FakeOs()
    monkeypatch.setattr(bridge, "os", fake)
    return fake
