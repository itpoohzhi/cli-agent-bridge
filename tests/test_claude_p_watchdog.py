"""Скользящее окно активности claude-p-bridge (AD-001..AD-004).

Покрытие: whitelist-чтение ~/.dsh/.env без мутации os.environ, срабатывание
вотчдога (`idle_timeout`/`absolute_cap` -> kill + 504), отсутствие ложного
таймаута на `child_exited`, троттлинг `check()` по `watchdog_interval_s`,
сброс таймера простоя на полезных событиях и закрытие контроллера в finally.
"""

from __future__ import annotations

import importlib.util
import os
import queue
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO = Path(__file__).resolve().parent.parent
BRIDGE_SERVER = REPO / "bridges" / "claude-p-bridge" / "server.py"
_ENV_PREFIXES = ("CLAUDE_P_BRIDGE_", "BRIDGE_")


@pytest.fixture(scope="module")
def isolated_claude_bridge(tmp_path_factory: pytest.TempPathFactory):
    """Загружает мост с изолированным HOME и без внешних CLAUDE_P_BRIDGE_*/BRIDGE_* env."""
    home = tmp_path_factory.mktemp("claude-p-home")
    name = f"claude_p_bridge_watchdog_{uuid.uuid4().hex}"
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("HOME", str(home))
        for key in list(os.environ):
            if key.startswith(_ENV_PREFIXES):
                mp.delenv(key, raising=False)
        spec = importlib.util.spec_from_file_location(name, BRIDGE_SERVER)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        try:
            spec.loader.exec_module(mod)
            yield SimpleNamespace(mod=mod, home=home)
        finally:
            sys.modules.pop(name, None)


class FakeController:
    """Фейковый AdaptiveTimeoutController: скриптованный check() и журнал вызовов."""

    instances: list = []
    verdict: tuple = (False, "", None)

    def __init__(self, idle_timeout_s, safety_cap_s, io_wait_cap_s, watchdog_interval_s):
        self.idle_timeout_s = idle_timeout_s
        self.safety_cap_s = safety_cap_s
        self.io_wait_cap_s = io_wait_cap_s
        self.watchdog_interval_s = watchdog_interval_s
        self.registered: list = []
        self.checks: list = []
        self.activity: list = []
        self.closed = False
        type(self).instances.append(self)

    def register_pgid(self, pgid: int) -> None:
        self.registered.append(pgid)

    def check(self, pgid: int | None = None) -> tuple:
        self.checks.append(pgid)
        return type(self).verdict

    def record_activity(self, kind: str = "protocol") -> None:
        self.activity.append(kind)

    def close(self) -> None:
        self.closed = True


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def monotonic(self) -> float:
        return self.t

    def sleep(self, _s: float) -> None:
        return None


class ScriptedQueue:
    """Очередь хода: каждый get() сдвигает фейковые часы на `step` секунд."""

    def __init__(self, items: list, clock: FakeClock | None = None, step: float = 0.0,
                 error: Exception | None = None) -> None:
        self.items = list(items)
        self.clock = clock
        self.step = step
        self.error = error

    def get(self, timeout: float | None = None) -> Any:
        if self.clock is not None:
            self.clock.t += self.step
        if self.error is not None:
            raise self.error
        if not self.items:
            raise queue.Empty
        return self.items.pop(0)


def _make_run(items: list, **kw: Any) -> SimpleNamespace:
    return SimpleNamespace(
        q=ScriptedQueue(items, **kw), err_box=[], proc=SimpleNamespace(pid=424242)
    )


@pytest.fixture()
def bridge(isolated_claude_bridge, monkeypatch: pytest.MonkeyPatch):
    mod = isolated_claude_bridge.mod
    FakeController.instances = []
    FakeController.verdict = (False, "", None)
    killed: list = []
    monkeypatch.setattr(mod, "AdaptiveTimeoutController", FakeController)
    monkeypatch.setattr(mod, "_kill_group", lambda proc: killed.append(proc))
    monkeypatch.setattr(mod, "_client_gone", lambda _sock: False)
    monkeypatch.setattr(mod, "_is_watchdog_enabled", lambda: True)
    monkeypatch.setattr(mod, "POLL_INTERVAL_S", 0.0)
    monkeypatch.setattr(mod, "STDERR_DRAIN_S", 0.0)
    return SimpleNamespace(mod=mod, killed=killed)


def _execute(mod: Any, run: Any) -> dict:
    handler = mod.Handler.__new__(mod.Handler)
    handler.connection = None
    sink = lambda *_a: True  # noqa: E731
    return handler._execute(run, sink, sink, sink, None, False, None)


def test_claude_p_env_loader_security(isolated_claude_bridge) -> None:
    mod = isolated_claude_bridge.mod
    env_dir = isolated_claude_bridge.home / ".dsh"
    env_dir.mkdir(exist_ok=True)
    env_file = env_dir / ".env"
    env_file.write_text(
        "\n".join([
            "# comment",
            "",
            "CLAUDE_P_BRIDGE_IDLE_TIMEOUT_S=111",
            "CLAUDE_P_BRIDGE_IDLE_TIMEOUT_S=222",
            "export BRIDGE_SAFETY_CAP_S='1800'",
            'CLAUDE_P_BRIDGE_WATCHDOG_ENABLED="0"',
            "CLAUDE_P_BRIDGE_KEY=super-secret",
            "OPENAI_API_KEY=sk-should-not-leak",
            "NOT_A_PAIR",
        ]) + "\n",
        encoding="utf-8",
    )
    before = dict(os.environ)
    try:
        got = mod._read_dsh_env_file()
    finally:
        env_file.unlink()
    assert dict(os.environ) == before  # os.environ не мутирован
    assert got == {
        "CLAUDE_P_BRIDGE_IDLE_TIMEOUT_S": "222",  # дубликат — последнее значение
        "BRIDGE_SAFETY_CAP_S": "1800",
        "CLAUDE_P_BRIDGE_WATCHDOG_ENABLED": "0",
    }
    assert not any(k.endswith("_KEY") for k in got)
    assert "super-secret" not in got.values()
    # Без файла — пустой словарь.
    assert mod._read_dsh_env_file() == {}


@pytest.mark.parametrize("reason", ["idle_timeout", "absolute_cap"])
def test_watchdog_timeout_trigger(bridge, monkeypatch: pytest.MonkeyPatch, reason: str) -> None:
    mod = bridge.mod
    monkeypatch.setattr(mod, "CLAUDE_P_BRIDGE_WATCHDOG_INTERVAL_S", 0.0)
    FakeController.verdict = (True, reason, None)
    run = _make_run([("text", "partial"), ("done", 0)])
    out = _execute(mod, run)
    assert bridge.killed == [run.proc]
    assert out["state"] == "timeout"
    assert out["rc"] == 1
    assert reason in out["err"]
    err = mod.Handler._error_body(out)
    assert err["code"] == 504
    assert err["type"] == "upstream_timeout"
    assert reason in err["message"]
    (ctl,) = FakeController.instances
    assert ctl.registered == [run.proc.pid]
    assert ctl.closed


def test_child_exited_no_false_timeout(bridge, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = bridge.mod
    monkeypatch.setattr(mod, "CLAUDE_P_BRIDGE_WATCHDOG_INTERVAL_S", 0.0)
    FakeController.verdict = (True, "child_exited", None)
    run = _make_run([
        ("text", "hello"),
        ("result", {"usage": {"output_tokens": 1}}),
        ("done", 0),
    ])
    out = _execute(mod, run)
    assert bridge.killed == []
    assert out["state"] == "done"
    assert out["rc"] == 0
    assert out["text"] == "hello"
    (ctl,) = FakeController.instances
    assert len(ctl.checks) >= 1  # вердикт child_exited получен, но ход не прерван


def test_watchdog_throttle(bridge, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = bridge.mod
    clock = FakeClock()
    monkeypatch.setattr(mod, "time", clock)
    interval = 3.0
    monkeypatch.setattr(mod, "CLAUDE_P_BRIDGE_WATCHDOG_INTERVAL_S", interval)
    check_ts: list = []
    orig_check = FakeController.check

    def timed_check(self, pgid=None):
        check_ts.append(clock.t)
        return orig_check(self, pgid)

    monkeypatch.setattr(FakeController, "check", timed_check)
    items = [("text", f"t{i} ") for i in range(10)] + [("done", 0)]
    run = _make_run(items, clock=clock, step=1.0)
    out = _execute(mod, run)
    assert out["state"] == "done"
    # 11 итераций по 1 с: проверки только на t=3, 6, 9.
    assert check_ts == [3.0, 6.0, 9.0]
    assert all(b - a >= interval for a, b in zip(check_ts, check_ts[1:]))
    assert len(check_ts) <= clock.t / interval


def test_record_activity_calls(bridge, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = bridge.mod
    monkeypatch.setattr(mod, "CLAUDE_P_BRIDGE_WATCHDOG_INTERVAL_S", 1e9)
    run = _make_run([
        ("text", "a"),
        ("thinking", "b"),
        ("result", {"usage": {}}),
        ("done", 0),
    ])
    out = _execute(mod, run)
    assert out["state"] == "done"
    (ctl,) = FakeController.instances
    assert ctl.activity == ["text", "thinking", "result"]
    assert ctl.checks == []


def test_controller_closed_in_finally(bridge, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = bridge.mod
    monkeypatch.setattr(mod, "CLAUDE_P_BRIDGE_WATCHDOG_INTERVAL_S", 1e9)

    # Штатный выход.
    out = _execute(mod, _make_run([("text", "ok"), ("done", 0)]))
    assert out["state"] == "done"
    # Аварийный выход по pump_error.
    out = _execute(mod, _make_run([("pump_error", "boom")]))
    assert out["state"] == "pump_error"
    # Исключение внутри цикла.
    with pytest.raises(RuntimeError, match="queue broken"):
        _execute(mod, _make_run([], error=RuntimeError("queue broken")))

    assert len(FakeController.instances) == 3
    assert all(ctl.closed for ctl in FakeController.instances)
