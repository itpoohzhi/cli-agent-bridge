"""Тесты отказоустойчивости agy-bridge (ADR-0007, arch-spec r2 §6, RW-008).

Покрыто 15 сценариев: детекция неактивности группы, сброс таймера по CPU и по
протокольным событиям, fail-closed при деградации `ps`, троттлинг `check()` в
`_execute`, `child_exited` как штатное завершение, `absolute_cap` -> `timeout`,
kill-switch, контракт ошибки `idle_timeout` (HTTP 504 / SSE), зачистка группы
процессов и reap лидера, изоляция таймаута источника в `fetch_via_playwright.py`.

Мост `bridges/agy-bridge/server.py` лежит в каталоге с дефисом, поэтому грузится
через `importlib`. Таймауты малые (`idle_timeout_s=0.2`) либо мок-часы; процессы
создаются с `start_new_session=True` и убираются в `finally`.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import http.client
import importlib.util
import io
import json
import os
import queue
import re
import resource
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace
from typing import Any
from typing import Callable, cast
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.watchdog import (  # noqa: E402
    AdaptiveTimeoutController,
    ProcessWatchdog,
    WatchdogMetrics,
)

_BRIDGE_PY = _REPO_ROOT / "bridges" / "agy-bridge" / "server.py"
_FETCH_SCRIPT = Path(
    os.environ.get("AIBUNKER_FETCH_SCRIPT")
    or "~/Мой диск/Workshop/aibunker-workshop/scripts/fetch_via_playwright.py"
).expanduser()

_POSIX = sys.platform != "win32"
_DARWIN = sys.platform == "darwin"


def _load_bridge() -> Any:
    os.environ.setdefault("AGY_BRIDGE_KEY", "test-key-agy-resilience")
    os.environ.pop("AGY_BRIDGE_FLEET", None)
    spec = importlib.util.spec_from_file_location(
        "agy_bridge_server_under_test", _BRIDGE_PY
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


srv = _load_bridge()


class _FakeClock:
    """Ручные часы: время движется только через advance()."""

    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class _TickQueue:
    """Очередь, у которой пустое ожидание двигает мок-часы на `timeout` секунд."""

    def __init__(self, clock: _FakeClock, empty_ticks: int, events: list) -> None:
        self.clock = clock
        self.empty_ticks = empty_ticks
        self.events = list(events)

    def get(self, timeout: float = 0.0) -> Any:
        if self.empty_ticks > 0:
            self.empty_ticks -= 1
            self.clock.advance(float(timeout))
            raise queue.Empty
        if self.events:
            return self.events.pop(0)
        self.clock.advance(float(timeout))
        raise queue.Empty


class _SpyController:
    """Обёртка над реальным контроллером: считает check() и on_activity()."""

    def __init__(
        self, inner: AdaptiveTimeoutController, forced: tuple | None = None
    ) -> None:
        self.inner = inner
        self.forced = forced
        self.check_calls = 0
        self.activity: list[str] = []

    def on_activity(self, kind: str = "protocol") -> None:
        self.activity.append(kind)
        self.inner.on_activity(kind)

    def check(self, pgid: int | None = None) -> tuple:
        self.check_calls += 1
        if self.forced is not None:
            return self.forced
        return self.inner.check(pgid)


def _spawn(argv: list[str], **kwargs: Any) -> subprocess.Popen:
    return subprocess.Popen(argv, start_new_session=True, **kwargs)


def _hard_kill(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass
    try:
        proc.wait(timeout=5)
    except (subprocess.TimeoutExpired, OSError):
        pass


def _ps_stat(pid: int) -> str:
    out = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)],
        capture_output=True,
        text=True,
        check=False,
    )
    return out.stdout.strip()


def _group_gone(pgid: int, within_s: float = 2.0) -> bool:
    deadline = time.monotonic() + within_s
    while time.monotonic() < deadline:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            pass
        time.sleep(0.05)
    return False


class _Sock:
    """Пара сокетов для Handler.connection: пир открыт, данных нет -> клиент «на месте»."""

    a: socket.socket = cast(socket.socket, cast(object, None))
    b: socket.socket = cast(socket.socket, cast(object, None))

    def __enter__(self) -> socket.socket:
        self.a, self.b = socket.socketpair()
        return self.a

    def __exit__(self, *_exc: Any) -> None:
        self.a.close()
        self.b.close()


def _make_handler(connection: socket.socket) -> Any:
    handler = srv.Handler.__new__(srv.Handler)
    handler.connection = connection
    return handler


def _fake_run(
    clock: _FakeClock, controller: Any, events: list, empty_ticks: int
) -> SimpleNamespace:
    return SimpleNamespace(
        q=_TickQueue(clock, empty_ticks, events),
        controller=controller,
        proc=SimpleNamespace(pid=424242),
        got_event=True,
        started=clock(),
        err_box=[],
    )


def _fake_time(clock: _FakeClock) -> SimpleNamespace:
    return SimpleNamespace(
        monotonic=clock, sleep=lambda _s: None, strftime=time.strftime, time=time.time
    )


def _execute_with_clock(clock: _FakeClock, run: SimpleNamespace) -> dict:
    """Прогнать Handler._execute на мок-часах без реальных ожиданий."""
    with _Sock() as sock, mock.patch.object(srv, "time", _fake_time(clock)):
        handler = _make_handler(sock)
        return handler._execute(
            run, lambda _t: True, lambda _e: True, lambda _r: True, None
        )


class IdleDetectionTests(unittest.TestCase):
    @unittest.skipUnless(_DARWIN, "core.watchdog рассчитан на macOS ps")
    def test_idle_timeout_detected_for_sleeping_process(self) -> None:
        proc = _spawn(["sleep", "100"])
        try:
            ctrl = AdaptiveTimeoutController(
                idle_timeout_s=0.2, safety_cap_s=60.0, finish_reserve_s=0.0
            )
            ctrl.register_pgid(proc.pid)
            result: tuple = (False, "", None)
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                result = ctrl.check(proc.pid)
                if result[0]:
                    break
                time.sleep(0.05)
            self.assertTrue(result[0])
            self.assertEqual(result[1], "idle_timeout")
            ctrl.close()
        finally:
            _hard_kill(proc)

    @unittest.skipUnless(_DARWIN, "core.watchdog рассчитан на macOS ps")
    def test_cpu_delta_resets_idle_timer(self) -> None:
        proc = _spawn([sys.executable, "-I", "-c", "while True: pass"])
        try:
            ctrl = AdaptiveTimeoutController(
                idle_timeout_s=0.2, safety_cap_s=60.0, finish_reserve_s=0.0
            )
            ctrl.register_pgid(proc.pid)
            end = time.monotonic() + 0.9  # заметно больше idle_timeout_s
            while time.monotonic() < end:
                should_stop, reason, _m = ctrl.check(proc.pid)
                self.assertFalse(should_stop, f"ложный {reason}: CPU растёт")
                time.sleep(0.05)
            self.assertEqual(ctrl.last_activity_kind, "cpu_delta")
            ctrl.close()
        finally:
            _hard_kill(proc)

    def test_on_activity_resets_idle_timer(self) -> None:
        for kind in ("text", "reasoning", "tool_trace", "init"):
            with self.subTest(kind=kind):
                clock = _FakeClock()
                ctrl = AdaptiveTimeoutController(
                    idle_timeout_s=0.2,
                    safety_cap_s=60.0,
                    finish_reserve_s=0.0,
                    watchdog_enabled=False,
                    clock=clock,
                )
                for _ in range(5):
                    clock.advance(0.15)
                    ctrl.on_activity(kind)
                    self.assertEqual(ctrl.check(), (False, "", None))
                self.assertEqual(ctrl.last_activity_kind, kind)
                clock.advance(0.25)
                should_stop, reason, _m = ctrl.check()
                self.assertTrue(should_stop)
                self.assertEqual(reason, "idle_timeout")

    @unittest.skipUnless(_POSIX, "нужны процессные группы POSIX")
    def test_ps_degraded_fail_closed(self) -> None:
        class _DegradedPs(ProcessWatchdog):
            def _run_ps(self, pgid: int) -> Any:
                raise subprocess.TimeoutExpired(cmd="ps", timeout=2.0)

        logs: list[str] = []
        proc = _spawn(["sleep", "100"])
        try:
            clock = _FakeClock()
            ctrl = AdaptiveTimeoutController(
                idle_timeout_s=0.2,
                safety_cap_s=60.0,
                finish_reserve_s=0.0,
                watchdog=_DegradedPs(log_fn=logs.append),
                clock=clock,
                log_fn=logs.append,
            )
            ctrl.register_pgid(proc.pid)
            self.assertEqual(ctrl.check(proc.pid)[:2], (False, ""))
            marker = ctrl.last_activity_ts
            clock.advance(0.25)
            should_stop, reason, metrics = ctrl.check(proc.pid)
            self.assertTrue(should_stop)
            self.assertEqual(reason, "idle_timeout")
            self.assertTrue(metrics is not None and metrics.ps_degraded)
            self.assertEqual(
                ctrl.last_activity_ts, marker, "fail-closed: таймер не сбрасывается"
            )
            self.assertTrue(any("watchdog_ps_degraded" in line for line in logs), logs)
        finally:
            _hard_kill(proc)

    def test_ps_degraded_stub_metrics_never_count_as_progress(self) -> None:
        degraded = WatchdogMetrics(
            pgid=1,
            alive=True,
            descendant_pids=(),
            new_descendants=(),
            cpu_time_s=9.0,
            cpu_delta_s=5.0,
            ps_degraded=True,
        )
        self.assertFalse(degraded.has_progress)


class ExecuteLoopTests(unittest.TestCase):
    def _controller(
        self, clock: _FakeClock, **kwargs: Any
    ) -> AdaptiveTimeoutController:
        params: dict[str, Any] = dict(
            idle_timeout_s=1000.0,
            safety_cap_s=1800.0,
            finish_reserve_s=0.0,
            watchdog_enabled=False,
            clock=clock,
        )
        params.update(kwargs)
        return AdaptiveTimeoutController(**params)

    def test_check_throttled_in_execute(self) -> None:
        # (а) 100 событий за 1 с реального времени: check() не вызывается чаще 1 раза.
        clock = _FakeClock()
        spy = _SpyController(self._controller(clock))
        events = [("text", "x")] * 100 + [("done", (0, "", {}))]
        out = _execute_with_clock(clock, _fake_run(clock, spy, events, empty_ticks=0))
        self.assertEqual(out["state"], "done")
        self.assertLessEqual(spy.check_calls, 1)
        self.assertEqual(spy.activity, ["text"] * 100)

        # (б) пустая очередь 12 тиков по 1 с: проверка идёт раз в WATCHDOG_INTERVAL_S.
        clock = _FakeClock()
        spy = _SpyController(self._controller(clock))
        out = _execute_with_clock(
            clock, _fake_run(clock, spy, [("done", (0, "ok", {}))], empty_ticks=12)
        )
        self.assertEqual(out["state"], "done")
        self.assertGreaterEqual(spy.check_calls, 1)
        self.assertLess(spy.check_calls, 12)
        self.assertEqual(spy.check_calls, 2)  # на 5-й и 10-й секундах

    def test_all_activity_kinds_reach_controller(self) -> None:
        clock = _FakeClock()
        spy = _SpyController(self._controller(clock))
        events = [
            ("init", {"conversation_id": "c1", "tools": 0, "permission_mode": ""}),
            ("reasoning", "r"),
            ("text", "t"),
            ("tool_trace", {"name": "run_command"}),
            ("result", {"status": "OK", "usage": {}}),
            ("done", (0, "t", {})),
        ]
        out = _execute_with_clock(clock, _fake_run(clock, spy, events, empty_ticks=0))
        self.assertEqual(out["state"], "done")
        # result/done — терминальные события и активностью не считаются.
        self.assertEqual(spy.activity, ["init", "reasoning", "text", "tool_trace"])

    def test_idle_timeout_returns_state_in_execute(self) -> None:
        clock = _FakeClock()
        ctrl = self._controller(clock, idle_timeout_s=8.0)
        out = _execute_with_clock(clock, _fake_run(clock, ctrl, [], empty_ticks=30))
        self.assertEqual(out["state"], "idle_timeout")
        self.assertEqual(out["rc"], 124)
        self.assertIn("idle timeout", out["err"])

    def test_child_exited_is_not_error(self) -> None:
        clock = _FakeClock()
        spy = _SpyController(
            self._controller(clock), forced=(True, "child_exited", None)
        )
        events = [("text", "hi"), ("done", (0, "hi", {}))]
        out = _execute_with_clock(clock, _fake_run(clock, spy, events, empty_ticks=7))
        self.assertGreaterEqual(spy.check_calls, 1)
        self.assertEqual(out["state"], "done")
        self.assertEqual(out["rc"], 0)
        self.assertEqual(out["text"], "hi")

    def test_absolute_cap_maps_to_timeout(self) -> None:
        clock = _FakeClock()
        pure = AdaptiveTimeoutController(
            idle_timeout_s=1000.0,
            safety_cap_s=0.2,
            finish_reserve_s=0.0,
            watchdog_enabled=False,
            clock=clock,
        )
        clock.advance(0.25)
        self.assertEqual(pure.check()[:2], (True, "absolute_cap"))

        clock = _FakeClock()
        ctrl = self._controller(clock, safety_cap_s=7.0)
        out = _execute_with_clock(clock, _fake_run(clock, ctrl, [], empty_ticks=30))
        self.assertEqual(out["state"], "timeout")
        self.assertEqual(out["rc"], 124)
        self.assertEqual(srv.Handler._error_body(out)["type"], "timeout")


class KillSwitchTests(unittest.TestCase):
    def test_flag_values(self) -> None:
        for value in ("0", "false", "no", "off", "False", "OFF"):
            with (
                self.subTest(value=value),
                mock.patch.dict(os.environ, {"BRIDGE_ENABLE_ADAPTIVE_WATCHDOG": value}),
            ):
                self.assertFalse(srv._is_watchdog_enabled())
        for value in ("1", "true", "yes", "on"):
            with (
                self.subTest(value=value),
                mock.patch.dict(os.environ, {"BRIDGE_ENABLE_ADAPTIVE_WATCHDOG": value}),
            ):
                self.assertTrue(srv._is_watchdog_enabled())
        with mock.patch.dict(os.environ):
            os.environ.pop("BRIDGE_ENABLE_ADAPTIVE_WATCHDOG", None)
            self.assertTrue(srv._is_watchdog_enabled())

    def test_idle_timeout_env_validation(self) -> None:
        for raw in ("abc", "-5", "0", "nan", "inf"):
            with (
                self.subTest(raw=raw),
                mock.patch.dict(os.environ, {"AGY_BRIDGE_IDLE_TIMEOUT": raw}),
                mock.patch.object(srv, "_log") as log,
            ):
                self.assertEqual(srv._idle_timeout_from_env(), 300.0)
                log.assert_called_once()
        with mock.patch.dict(os.environ, {"AGY_BRIDGE_IDLE_TIMEOUT": "12.5"}):
            self.assertEqual(srv._idle_timeout_from_env(), 12.5)
        with mock.patch.dict(os.environ):
            os.environ.pop("AGY_BRIDGE_IDLE_TIMEOUT", None)
            self.assertEqual(srv._idle_timeout_from_env(), 300.0)

    @unittest.skipUnless(_POSIX, "нужны процессные группы POSIX")
    def test_killswitch_disables_watchdog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            launcher = Path(tmp) / "fake-launcher.sh"
            launcher.write_text("#!/bin/sh\nexec sleep 100\n", encoding="utf-8")
            launcher.chmod(0o755)
            runs: list[Any] = []

            def make_run() -> Any:
                run = srv.Run("ping", "m", "low", "default", "", "tag")
                runs.append(run)
                return run

            try:
                with (
                    mock.patch.object(srv, "_launcher", return_value=str(launcher)),
                    mock.patch.object(srv, "WORKSPACE", Path(tmp) / "ws"),
                    mock.patch.object(ProcessWatchdog, "_run_ps") as run_ps,
                ):
                    with mock.patch.dict(
                        os.environ, {"BRIDGE_ENABLE_ADAPTIVE_WATCHDOG": "0"}
                    ):
                        off = make_run()
                        self.assertEqual(
                            off.controller.idle_timeout_s, float(srv.TIMEOUT_S)
                        )
                        self.assertIs(off.controller.watchdog_enabled, False)
                        self.assertEqual(
                            off.controller.safety_cap_s, float(srv.TIMEOUT_S)
                        )
                        self.assertEqual(off.controller.finish_reserve_s, 0.0)
                        off.controller.check(off.proc.pid)
                        run_ps.assert_not_called()  # ни seed, ни check не зовут ps
                    with mock.patch.dict(
                        os.environ, {"BRIDGE_ENABLE_ADAPTIVE_WATCHDOG": "1"}
                    ):
                        on = make_run()
                        self.assertEqual(
                            on.controller.idle_timeout_s, srv.IDLE_TIMEOUT_S
                        )
                        self.assertIs(on.controller.watchdog_enabled, True)
                        self.assertEqual(
                            on.controller.safety_cap_s, float(srv.TIMEOUT_S)
                        )
            finally:
                for run in runs:
                    run.close()


class ErrorContractTests(unittest.TestCase):
    def test_error_body_idle_timeout_http_504(self) -> None:
        body = srv.Handler._error_body({"state": "idle_timeout", "rc": 124})
        self.assertEqual(body["code"], 504)
        self.assertEqual(body["type"], "idle_timeout")
        self.assertIn(f"idle timeout after {srv.IDLE_TIMEOUT_S:g}s", body["message"])
        self.assertIn("idle timeout after 300s", body["message"])

    def _out(self) -> dict:
        return {
            "state": "idle_timeout",
            "rc": 124,
            "text": "",
            "usage": {},
            "result": {},
            "err": "x",
            "tool_calls": [],
            "tool_events": 0,
            "conversation_id": "",
        }

    def test_sse_error_chunk_idle_timeout(self) -> None:
        frames: list[str] = []
        handler = srv.Handler.__new__(srv.Handler)
        handler.send_response = lambda *_a, **_k: None
        handler.send_header = lambda *_a, **_k: None
        handler.end_headers = lambda: None
        handler._emit = lambda data: frames.append(data) or True
        handler._run_once = lambda *_a, **_k: self._out()
        handler._serve_sse({"model": "m"})
        self.assertGreaterEqual(len(frames), 3)
        self.assertEqual(frames[-1], "data: [DONE]\n\n")
        error_frame = frames[-2]
        self.assertTrue(
            error_frame.startswith("data: ") and error_frame.endswith("\n\n")
        )
        payload = json.loads(error_frame[len("data: ") :])
        self.assertEqual(payload["error"]["type"], "idle_timeout")
        self.assertEqual(payload["error"]["code"], 504)
        # ни finish_reason=stop, ни usage-кадра после ошибки быть не должно
        self.assertFalse(any('"finish_reason": "stop"' in f for f in frames))

    def test_json_mode_idle_timeout_is_504(self) -> None:
        sent: list[tuple] = []
        handler = srv.Handler.__new__(srv.Handler)
        handler._send = lambda code, payload: sent.append((code, payload))
        handler._run_once = lambda *_a, **_k: self._out()
        handler._serve_json({"model": "m"})
        self.assertEqual(len(sent), 1)
        code, payload = sent[0]
        self.assertEqual(code, 504)
        self.assertEqual(payload["error"]["type"], "idle_timeout")


@unittest.skipUnless(_POSIX, "нужны процессные группы POSIX")
class KillGroupTests(unittest.TestCase):
    def test_kill_group_cleans_descendants_and_reaps_zombie(self) -> None:
        proc = _spawn(["sh", "-c", "sleep 100 & sleep 100 & wait"])
        try:
            out = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                out = subprocess.run(
                    ["ps", "-o", "pid=", "-g", str(proc.pid)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if len(out.stdout.split()) >= 3:  # лидер + два sleep
                    break
                time.sleep(0.05)
            self.assertGreaterEqual(len(out.stdout.split()), 3, "потомки не стартовали")
            srv._kill_group(proc)
            self.assertIsNotNone(proc.returncode)
            self.assertTrue(
                _group_gone(proc.pid), "потомки группы пережили _kill_group"
            )
            self.assertEqual(_ps_stat(proc.pid), "", "лидер остался зомби")
        finally:
            _hard_kill(proc)

    def test_kill_group_reaps_when_group_already_gone(self) -> None:
        proc = _spawn(["true"])
        try:
            deadline = time.monotonic() + 3.0
            while _ps_stat(proc.pid) != "Z" and time.monotonic() < deadline:
                time.sleep(0.05)  # лидер завершён и ещё не собран
            with (
                mock.patch.object(srv.os, "killpg", side_effect=ProcessLookupError),
                mock.patch.object(proc, "wait", wraps=proc.wait) as wait,
            ):
                srv._kill_group(proc)  # не должен падать
            wait.assert_called()
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(_ps_stat(proc.pid), "", "зомби не собран")
        finally:
            _hard_kill(proc)

    def test_kill_group_escalates_to_sigkill(self) -> None:
        self.assertEqual(srv.KILL_TERM_GRACE_S, 2.0)
        self.assertEqual(srv.KILL_WAIT_S, 5.0)
        proc = _spawn(
            ["sh", "-c", "trap '' TERM; echo ready; while :; do sleep 1; done"],
            stdout=subprocess.PIPE,
        )
        try:
            self.assertEqual(
                proc.stdout.readline().strip(), b"ready"
            )  # trap уже установлен
            started = time.monotonic()
            with mock.patch.object(srv, "KILL_TERM_GRACE_S", 0.4):
                srv._kill_group(proc)
            elapsed = time.monotonic() - started
            self.assertEqual(proc.returncode, -signal.SIGKILL)
            self.assertGreaterEqual(
                elapsed, 0.35, "SIGKILL раньше окончания grace-периода"
            )
            self.assertLess(elapsed, 2.0 + 5.0)
            self.assertTrue(_group_gone(proc.pid))
        finally:
            _hard_kill(proc)
            if proc.stdout is not None:
                proc.stdout.close()


def _load_fetch_script() -> Any:
    if not _FETCH_SCRIPT.is_file():
        raise unittest.SkipTest(f"нет {_FETCH_SCRIPT}")
    scripts_dir = str(_FETCH_SCRIPT.parent)
    spec = importlib.util.spec_from_file_location(
        "fetch_via_playwright_under_test", _FETCH_SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    added = scripts_dir not in sys.path
    if added:
        sys.path.insert(
            0, scripts_dir
        )  # `from _paths import ...` при пустом __package__
    try:
        spec.loader.exec_module(module)
    finally:
        if added and scripts_dir in sys.path:
            sys.path.remove(scripts_dir)
    return module


class FetchViaPlaywrightHotfixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fetch = _load_fetch_script()

    def setUp(self) -> None:
        with self.fetch._progress["lock"]:
            self.fetch._progress["pending"].clear()
            self.fetch._progress["completed"] = 0

    def test_fetch_one_timeout_isolated(self) -> None:
        fetch = self.fetch
        cancelled: list[str] = []

        async def fetch_one(src: dict, ctx: Any, ctx_r: Any, cutoff: Any) -> tuple:
            try:
                await asyncio.sleep(30)
            finally:
                cancelled.append(src["id"])
            return src["id"], ["never"], None

        async def fetch_one_no_rss(src: dict, ctx: Any, cutoff: Any) -> tuple:
            return src["id"], ["ok"], None

        async def scenario() -> list:
            return await asyncio.gather(
                fetch._track_fetch_one({"id": "hung"}, None, None, None, fetch_one),
                fetch._track_fetch_one(
                    {"id": "good"}, None, None, None, fetch_one_no_rss
                ),
            )

        self.assertEqual(fetch.FETCH_ONE_TIMEOUT_S, 60.0)
        started = time.monotonic()
        with mock.patch.object(fetch, "FETCH_ONE_TIMEOUT_S", 0.1):
            results = asyncio.run(scenario())
        self.assertLess(time.monotonic() - started, 2.0)
        self.assertEqual(results[0], ("hung", [], "timeout after 60s"))
        self.assertEqual(results[1], ("good", ["ok"], None))
        self.assertEqual(cancelled, ["hung"], "зависший источник должен быть отменён")
        self.assertEqual(fetch._progress["pending"], set())
        self.assertEqual(fetch._progress["completed"], 2)

    def test_page_close_bounded(self) -> None:
        fetch = self.fetch
        self.assertEqual(fetch.PAGE_CLOSE_TIMEOUT_S, 5.0)

        class _HungPage:
            async def close(self) -> None:
                await asyncio.sleep(30)

        class _BrokenPage:
            async def close(self) -> None:
                raise RuntimeError("Target closed")

        async def scenario() -> None:
            await fetch._safe_close_page(_HungPage())
            await fetch._safe_close_page(_BrokenPage())

        started = time.monotonic()
        with mock.patch.object(fetch, "PAGE_CLOSE_TIMEOUT_S", 0.1):
            asyncio.run(scenario())  # исключения подавлены
        self.assertLess(time.monotonic() - started, 2.0)

    def test_no_bare_page_close_left(self) -> None:
        text = _FETCH_SCRIPT.read_text(encoding="utf-8")
        bare = [
            n
            for n, line in enumerate(text.splitlines(), 1)
            if line.strip() == "await page.close()"
        ]
        self.assertEqual(bare, [], f"голые await page.close(): строки {bare}")


# ---- Реалтайм-мышление agy-bridge (agy-realtime-reasoning): SQLite-источник, drain,
# учёт выданного мышления, изоляция горячих сессий, breaker и kill-switch. ----------
# Тесты ниже обращаются к мосту через getattr: модуль грузится по пути с дефисом, а
# приватные имена моста не должны давать предупреждений типизации.

_BRIDGE_MODULE = "agy_bridge_server_under_test"
_CID = "82188e72-6eca-4f23-a0b3-2257ec43bd60"
_CID_B = "fa92a264-8039-40dc-a716-37f7f64ea9e3"
_CID_C = "57172100-e4cf-4553-a0b6-f0af14c28a80"
_STEPS_SCHEMA = "".join(
    [
        "CREATE TABLE IF NOT EXISTS steps (idx integer PRIMARY KEY, step_type integer, ",
        "status integer, has_subtrajectory, metadata blob, error_details blob, ",
        "permissions blob, task_details blob, render_info blob, step_payload blob, ",
        "step_format integer)",
    ]
)
_FAKE_AGY_SOURCE = """
import json, os, sqlite3, sys, time, uuid

def varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)

def ld(field, payload):
    return varint(field << 3 | 2) + varint(len(payload)) + payload

def blob(thinking):
    inner = ld(1, b"hdr") + ld(3, thinking.encode("utf-8")) + ld(8, b"tail")
    return varint(1 << 3) + varint(7) + ld(20, inner) + ld(21, b"x")

def note(path, text):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(text + "\\n")

def main():
    scen = json.load(open(os.environ["FAKE_SCENARIO"]))
    argv = sys.argv[1:]
    cid = argv[argv.index("--conversation") + 1] if "--conversation" in argv else str(uuid.uuid4())
    scen = json.loads(json.dumps(scen).replace("{cid}", cid))
    spawn = 0
    if scen.get("argv_log"):
        try:
            spawn = sum(1 for _ in open(scen["argv_log"], encoding="utf-8"))
        except OSError:
            spawn = 0
        note(scen["argv_log"], json.dumps({"argv": sys.argv[1:], "t": time.time()}))
    events = scen["spawns"][min(spawn, len(scen["spawns"]) - 1)] if "spawns" in scen else scen["events"]
    sys.stdin.read()
    t0 = time.monotonic()
    conn = None
    for ev in sorted(events, key=lambda e: e["t"]):
        delay = ev["t"] - (time.monotonic() - t0)
        if delay > 0:
            time.sleep(delay)
        op = ev["op"]
        if op == "stdout":
            sys.stdout.write(json.dumps(ev["line"]) + "\\n")
            sys.stdout.flush()
        elif op == "db":
            try:
                if conn is None:
                    conn = sqlite3.connect(scen["db"], timeout=5, isolation_level=None)
                    conn.execute("PRAGMA journal_mode=WAL")
                    conn.execute(scen["schema"])
                payload = blob(ev["thinking"]) if "thinking" in ev else b"x" * ev["blob_bytes"]
                conn.execute(
                    "INSERT OR REPLACE INTO steps (idx, step_type, status, step_payload) VALUES (?,?,?,?)",
                    (ev["idx"], ev.get("step_type", 15), ev["status"], payload))
                if scen.get("commit_log"):
                    note(scen["commit_log"], json.dumps({"cid": cid, "idx": ev["idx"], "status": ev["status"], "t": time.time()}))
            except sqlite3.Error as exc:
                note(scen.get("errors_log", os.devnull), repr(exc))
        elif op == "transcript":
            os.makedirs(os.path.dirname(scen["transcript"]), exist_ok=True)
            note(scen["transcript"], json.dumps(ev["record"], ensure_ascii=False))
        elif op == "late_transcript":
            if os.fork() == 0:
                try:
                    os.setsid()
                    os.close(1)
                    os.close(2)
                    time.sleep(ev["delay"])
                    if os.path.isdir(scen["tmp"]):
                        os.makedirs(os.path.dirname(scen["transcript"]), exist_ok=True)
                        note(scen["transcript"], json.dumps(ev["record"], ensure_ascii=False))
                finally:
                    os._exit(0)
        elif op == "stderr":
            sys.stderr.write(ev["text"] + "\\n")
            sys.stderr.flush()
        elif op == "exit":
            if conn is not None:
                conn.close()
            if scen.get("exit_ts"):
                note(scen["exit_ts"], repr(time.time()))
            if scen.get("exit_log"):
                note(scen["exit_log"], json.dumps({"cid": cid, "t": time.time()}))
            sys.exit(ev.get("code", 0))
    if conn is not None:
        conn.close()
    if scen.get("exit_ts"):
        note(scen["exit_ts"], repr(time.time()))

main()
"""


def _bridge() -> ModuleType:
    return sys.modules[_BRIDGE_MODULE]


def _bfn(name: str) -> Callable[..., object]:
    return cast(Callable[..., object], getattr(_bridge(), name))


def _bval(name: str) -> object:
    return cast(object, getattr(_bridge(), name))


def _ofn(obj: object, name: str) -> Callable[..., object]:
    return cast(Callable[..., object], getattr(obj, name))


def _oval(obj: object, name: str) -> object:
    return cast(object, getattr(obj, name))


def _dict(value: object) -> dict[str, object]:
    return cast("dict[str, object]", value)


def _str(value: object) -> str:
    return cast(str, value)


def _int(value: object) -> int:
    return cast(int, value)


def _float(value: object) -> float:
    return cast(float, value)


def _varint(number: int) -> bytes:
    out = bytearray()
    while True:
        low = number & 0x7F
        number >>= 7
        if number:
            out.append(low | 0x80)
        else:
            out.append(low)
            return bytes(out)


def _ld(field: int, payload: bytes) -> bytes:
    return _varint(field << 3 | 2) + _varint(len(payload)) + payload


def _step_blob(thinking: str, junk_before: bytes = b"") -> bytes:
    """step_payload: корневое поле 20 с подполями 1, 3 (мышление), 6, 8 и чужие поля."""
    inner = (
        _ld(1, b"hdr")
        + _ld(3, thinking.encode("utf-8"))
        + _ld(6, b"tool")
        + _ld(8, b"t")
    )
    return junk_before + _ld(20, inner) + _ld(21, b"x")


def _extract(raw: bytes | None, final: bool = True) -> str:
    return _str(_bfn("_extract_thinking_from_step_blob")(raw, final))


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class _DbWriter:
    """Внешний писатель БД разговора agy (WAL): держит своё соединение открытым."""

    conn: sqlite3.Connection

    def __init__(self, path: Path, wal: bool = True) -> None:
        self.conn = sqlite3.connect(str(path), timeout=5, isolation_level=None)
        if wal:
            _ = self.conn.execute("PRAGMA journal_mode=WAL")
        _ = self.conn.execute(_STEPS_SCHEMA)

    def put(self, idx: int, status: int, raw: bytes, step_type: int = 15) -> None:
        sql = "INSERT OR REPLACE INTO steps (idx, step_type, status, step_payload) VALUES (?, ?, ?, ?)"
        _ = self.conn.execute(sql, (idx, step_type, status, raw))

    def think(self, idx: int, status: int, thinking: str) -> None:
        self.put(idx, status, _step_blob(thinking))

    def close(self) -> None:
        self.conn.close()


class _Fixture:
    """Временные BRAIN/CONV/agy-бинарь/dynamic_config рядом с патчами констант моста."""

    tmp: Path
    brain: Path
    conv: Path
    agy_bin: Path
    config: Path
    launcher: Path
    scenario: Path
    stack: contextlib.ExitStack
    env_saved: dict[str, str | None]
    writers: list[_DbWriter]

    def __init__(self) -> None:
        self.stack = contextlib.ExitStack()
        self.env_saved = {}
        self.writers = []
        self.tmp = Path(tempfile.mkdtemp(prefix="agy-rt-"))
        self.brain = self.tmp / "brain"
        self.conv = self.tmp / "conv"
        self.agy_bin = self.tmp / "agy.real"
        self.config = self.tmp / "dynamic_config.json"
        self.launcher = self.tmp / "fake-agy.py"
        self.scenario = self.tmp / "scenario.json"

    def __enter__(self) -> _Fixture:
        self.brain.mkdir()
        self.conv.mkdir()
        _ = self.agy_bin.write_text("agy-fixture-binary", encoding="utf-8")
        _ = self.launcher.write_text(
            "#!" + sys.executable + "\n" + _FAKE_AGY_SOURCE, encoding="utf-8"
        )
        self.launcher.chmod(0o755)
        self.patch("BRAIN_DIR", self.brain)
        self.patch("CONV_DIR", self.conv)
        self.patch("AGY_BIN", str(self.agy_bin))
        self.patch("DYNAMIC_CONFIG_PATH", self.config)
        self.patch("LAUNCHER", str(self.launcher))
        self.patch("WORKSPACE", self.tmp / "ws")
        self.set_env("FAKE_SCENARIO", str(self.scenario))
        self.set_env("AGY_SQLITE_REASONING_ENABLED", None)
        self.reset_state()
        return self

    def __exit__(self, *_exc: object) -> None:
        for writer in self.writers:
            with contextlib.suppress(sqlite3.Error):
                writer.close()
        self.stack.close()
        for key, old in self.env_saved.items():
            if old is None:
                _ = os.environ.pop(key, None)
            else:
                os.environ[key] = old
        self.reset_state()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def reset_state(self) -> None:
        """Процессные глобалы моста: guardrails, стор горячих сессий и занятые cid."""
        _ = _bfn("_reset_sqlite_guards_for_tests")()
        cast("dict[object, object]", _bval("_session_store")).clear()
        cast("set[str]", _bval("_in_flight_cids")).clear()

    def patch(self, name: str, value: object) -> None:
        _ = self.stack.enter_context(mock.patch.object(_bridge(), name, value))

    def set_env(self, key: str, value: str | None) -> None:
        if key not in self.env_saved:
            self.env_saved[key] = os.environ.get(key)
        if value is None:
            _ = os.environ.pop(key, None)
        else:
            os.environ[key] = value

    def set_flag(self, value: bool | None) -> None:
        """Рантайм-флаг SQLITE_REASONING_ENABLED: True/False или None (удалить файл)."""
        if value is None:
            self.config.unlink(missing_ok=True)
            return
        text = json.dumps({"SQLITE_REASONING_ENABLED": value}) + " " * (
            time.monotonic_ns() % 7
        )
        _ = self.config.write_text(text, encoding="utf-8")

    def prime_canary(self) -> None:
        """Прогревочный ход уже подтвердил совместимость agy: compat = LIVE."""
        identity = _bfn("_agy_binary_identity")()
        _ = _bfn("_compat_turn_state")(identity)
        _ = _bfn("_compat_promote")(identity)

    def db_path(self, cid: str = _CID) -> Path:
        return self.conv / (cid + ".db")

    def writer(self, cid: str = _CID, wal: bool = True) -> _DbWriter:
        writer = _DbWriter(self.db_path(cid), wal=wal)
        self.writers.append(writer)
        return writer

    def transcript(self, cid: str = _CID) -> Path:
        return self.brain / cid / ".system_generated" / "logs" / "transcript_full.jsonl"

    def append_record(self, record: dict[str, object], cid: str = _CID) -> None:
        path = self.transcript(cid)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            _ = fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def write_scenario(
        self, events: list[dict[str, object]], cid: str = _CID, **extra: object
    ) -> dict[str, str]:
        paths = {
            "argv_log": str(self.tmp / "argv.log"),
            "commit_log": str(self.tmp / "commits.log"),
            "errors_log": str(self.tmp / "errors.log"),
            "exit_ts": str(self.tmp / "exit.ts"),
            "exit_log": str(self.tmp / "exit.log"),
        }
        body: dict[str, object] = {
            "tmp": str(self.tmp),
            "db": str(self.db_path(cid)),
            "transcript": str(self.transcript(cid)),
            "schema": _STEPS_SCHEMA,
            "events": events,
        }
        body.update(paths)
        body.update(extra)
        _ = self.scenario.write_text(json.dumps(body), encoding="utf-8")
        return paths

    def spawns(self) -> list[list[str]]:
        log = self.tmp / "argv.log"
        if not log.exists():
            return []
        rows: list[list[str]] = []
        for line in log.read_text(encoding="utf-8").splitlines():
            record = _dict(cast(object, json.loads(line)))
            rows.append(cast("list[str]", record["argv"]))
        return rows


def _init_ev(t: float, cid: str = _CID, tools: int = 0) -> dict[str, object]:
    return {
        "t": t,
        "op": "stdout",
        "line": {
            "event": "init",
            "conversation_id": cid,
            "init": {"tools": [{"name": "t"}] * tools, "permission_mode": "x"},
        },
    }


def _result_ev(
    t: float,
    cid: str = _CID,
    status: str = "OK",
    error: str = "",
    response: str = "ответ",
) -> dict[str, object]:
    result: dict[str, object] = {
        "response": response,
        "status": status,
        "conversation_id": cid,
        "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    }
    if error:
        result["error"] = error
    return {"t": t, "op": "stdout", "line": {"event": "result", "result": result}}


def _text_ev(t: float, text: str = "ответ", step: int = 9) -> dict[str, object]:
    return {
        "t": t,
        "op": "stdout",
        "line": {
            "event": "step_update",
            "step_update": {
                "step_type": "agent_response",
                "step_index": step,
                "text_delta": text,
            },
        },
    }


def _db_ev(t: float, idx: int, status: int, thinking: str) -> dict[str, object]:
    return {"t": t, "op": "db", "idx": idx, "status": status, "thinking": thinking}


def _tr_ev(t: float, idx: int, thinking: str, final: bool = False) -> dict[str, object]:
    record: dict[str, object] = {"type": "PLANNER_RESPONSE", "step_index": idx}
    if thinking:
        record["thinking"] = thinking
    if final:
        record["content"] = "ответ"
    else:
        record["tool_calls"] = [{"name": "run_command"}]
    return {"t": t, "op": "transcript", "record": record}


def _exit_ev(t: float, code: int = 0) -> dict[str, object]:
    return {"t": t, "op": "exit", "code": code}


def _ctx(**over: object) -> dict[str, object]:
    ctx: dict[str, object] = {
        "model": "m",
        "model_len": 1,
        "effort": "low",
        "effort_source": "default",
        "prompt": "hi",
        "full_prompt": "hi",
        "cwd": "",
        "tools_count": 0,
        "conversation_id": "",
        "hot_resumed": False,
        "sess_key": None,
        "stream": True,
        "tag": "tag",
    }
    ctx.update(over)
    return ctx


class _Turn:
    """Результат одного _run_once: итог, чанки мышления с метками времени и сколько ждали."""

    out: dict[str, object]
    chunks: list[tuple[float, str]]
    wall: float
    ended: float

    def __init__(
        self,
        out: dict[str, object],
        chunks: list[tuple[float, str]],
        wall: float,
        ended: float,
    ) -> None:
        self.out = out
        self.chunks = chunks
        self.wall = wall
        self.ended = ended

    def reasoning(self) -> str:
        return "".join(text for _t, text in self.chunks)


def _run_turn(ctx: dict[str, object] | None = None) -> _Turn:
    """Один ход через Handler._run_once с настоящим подпроцессом фейкового agy."""
    chunks: list[tuple[float, str]] = []
    started = time.time()

    def on_text(_text: str) -> bool:
        return True

    def on_tool(_event: dict[str, object]) -> bool:
        return True

    def on_reasoning(text: str) -> bool:
        chunks.append((time.time(), text))
        return True

    with _Sock() as sock:
        handler = cast(object, _make_handler(sock))
        out = _dict(
            _ofn(handler, "_run_once")(
                ctx if ctx is not None else _ctx(), on_text, on_tool, on_reasoning, None
            )
        )
    ended = time.time()
    return _Turn(out, chunks, ended - started, ended)


def _make_tail(
    mode: str = "LIVE",
    cid: str | None = _CID,
    base_idx: int = 0,
    offset: int = 0,
    resumed: bool = False,
    probe_gen: int | None = None,
    identity: tuple[int, int] | None = None,
    plan: object | None = None,
) -> tuple[object, list[tuple[int, str]], threading.Event, threading.Event]:
    """Источник мышления без процесса: эмиты копятся в списке, bind при заданном cid."""
    if plan is None:
        plan = _bfn("_TurnPlan")()
        setattr(plan, "mode", mode)
        setattr(plan, "base_idx", base_idx)
        setattr(plan, "offset", offset)
        setattr(plan, "probe_gen", probe_gen)
        setattr(plan, "identity", identity)
    emitted: list[tuple[int, str]] = []

    def emit(idx: int, delta: str, on_delivered: Callable[[], None] | None) -> bool:
        emitted.append((idx, delta))
        if on_delivered is not None:
            on_delivered()
        return True

    stop = threading.Event()
    done = threading.Event()
    tail = _bfn("_TranscriptTail")(
        emit, stop, done, resumed, plan, "turn-" + (cid or "x")[:8]
    )
    if cid is not None:
        _ = _ofn(tail, "bind")(cid)
    return tail, emitted, stop, done


def _poll(tail: object) -> object:
    """Один опрос SQLite с гарантированным токеном bucket."""
    setattr(_oval(tail, "bucket"), "tenths", 30)
    setattr(tail, "_next_poll_at", 0.0)
    return _ofn(tail, "_poll_sqlite")()


def _text_of(emitted: list[tuple[int, str]], idx: int | None = None) -> str:
    return "".join(text for i, text in emitted if idx is None or i == idx)


class WireParserTests(unittest.TestCase):
    """REQ-002: разбор step_payload на stdlib (TC-01..TC-12), без исключений наружу."""

    def test_tc01_parser_positive_field_20_subfield_3(self) -> None:
        self.assertEqual(_extract(_step_blob("abc")), "abc")
        self.assertEqual(_extract(_step_blob("abc"), final=False), "abc")

    def test_tc02_multibyte_varint_length(self) -> None:
        self.assertEqual(_varint(300), b"\xac\x02")
        self.assertEqual(len(_varint(70000)), 3)
        for size in (300, 70000):
            with self.subTest(size=size):
                text = "x" * size
                self.assertEqual(_extract(_step_blob(text)), text)

    def test_tc03_multibyte_tag_and_far_field_skipped(self) -> None:
        blob = _step_blob("abc")
        self.assertTrue(blob.startswith(b"\xa2\x01"))  # тег поля 20 занимает 2 байта
        self.assertEqual(_extract(_ld(20000, b"zz") + blob), "abc")

    def test_tc04_cyrillic_and_cut_character(self) -> None:
        text = "Размышляю о задаче"
        self.assertEqual(_extract(_step_blob(text)), text)
        raw = text.encode("utf-8")
        for cut in range(len(raw) + 1):
            part = _extract(_ld(20, _ld(3, raw[:cut])), final=False)
            self.assertTrue(text.startswith(part), (cut, part))
            self.assertNotIn("\ufffd", part)
        cut_blob = _ld(20, _ld(3, raw[:-1]))
        self.assertEqual(_extract(cut_blob, final=False), text[:-1])
        self.assertIn("\ufffd", _extract(cut_blob, final=True))

    def test_tc05_invalid_utf8_replaced_without_exception(self) -> None:
        blob = _ld(20, _ld(3, b"a\xff\xfeb"))
        self.assertEqual(_extract(blob), "a\ufffd\ufffdb")
        self.assertEqual(_extract(blob, final=False), "a\ufffd\ufffdb")

    def test_tc06_varint_fields_before_field_20_skipped(self) -> None:
        junk = _varint(1 << 3) + _varint(5) + _varint(2 << 3) + _varint(300)
        self.assertEqual(_extract(_step_blob("abc", junk_before=junk)), "abc")

    def test_tc07_fixed64_field_skipped(self) -> None:
        junk = _varint(3 << 3 | 1) + b"\x01" * 8
        self.assertEqual(_extract(_step_blob("abc", junk_before=junk)), "abc")

    def test_tc08_fixed32_field_skipped(self) -> None:
        junk = _varint(4 << 3 | 5) + b"\x02" * 4
        self.assertEqual(_extract(_step_blob("abc", junk_before=junk)), "abc")

    def test_tc09_foreign_length_delimited_fields_ignored(self) -> None:
        inner = _ld(6, b"call-a") + _ld(6, b"call-b") + _ld(3, b"abc") + _ld(8, b"zzz")
        blob = (
            _ld(4, b"other")
            + _ld(20, inner)
            + _ld(21, b"tail")
            + _ld(20, _ld(1, b"no3"))
        )
        self.assertEqual(_extract(blob), "abc")
        last = _ld(20, _ld(3, b"old") + _ld(3, b"new"))
        self.assertEqual(_extract(last), "new")

    def test_tc10_unsupported_wire_types_yield_nothing(self) -> None:
        for wire in (3, 4, 6, 7):
            with self.subTest(wire=wire):
                junk = _varint(1 << 3 | wire)
                self.assertEqual(_extract(junk + _step_blob("abc")), "")
                nested = _ld(20, junk + _ld(3, b"abc"))
                self.assertEqual(_extract(nested), "")

    def test_tc11_truncation_at_every_position_never_raises(self) -> None:
        text = "x" * 300
        blob = _step_blob(text)
        for cut in range(len(blob)):
            part = _extract(blob[:cut])
            self.assertTrue(part == "" or text.startswith(part), cut)

    def test_tc12_no_field_empty_and_none(self) -> None:
        self.assertEqual(_extract(None), "")
        self.assertEqual(_extract(b""), "")
        self.assertEqual(_extract(_ld(1, b"x")), "")
        self.assertEqual(_extract(_ld(20, _ld(1, b"x"))), "")
        self.assertEqual(_extract(b"\xff\xff\xff"), "")


def _snapshots(
    sizes: tuple[int, ...], alphabet: str = "abcdefghijklmnopqrstuvwxyz"
) -> list[str]:
    base = "".join(alphabet[i % len(alphabet)] for i in range(max(sizes)))
    return [base[:size] for size in sizes]


class SqliteLiveSourceTests(unittest.TestCase):
    """REQ-001: дельты мышления из SQLite во время status=8 (TC-20, TC-21, TC-23, TC-24)."""

    def test_tc20_chunks_arrive_before_status_3(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            writer = fx.writer()
            tail, emitted, _stop, _done = _make_tail()
            snaps = _snapshots((523, 810, 1088, 1419, 2156))
            for snap in snaps:
                writer.think(3, 8, snap)
                _ = _poll(tail)
            before_final = len(emitted)
            self.assertGreaterEqual(before_final, 2)
            self.assertEqual(before_final, len(snaps))
            writer.think(3, 3, snaps[-1])
            _ = _poll(tail)
            self.assertEqual(_text_of(emitted), snaps[-1])

    def test_tc21_step_without_thinking_emits_nothing(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            writer = fx.writer()
            tail, emitted, _stop, _done = _make_tail()
            writer.put(2, 3, _step_blob("секрет"), step_type=90)
            writer.put(3, 3, _ld(1, b"no-thinking"))
            writer.put(4, 8, _ld(20, _ld(1, b"only-header")))
            _ = _poll(tail)
            self.assertEqual(emitted, [])

    def test_tc23_faster_writer_than_poll_keeps_final_text(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            writer = fx.writer()
            tail, emitted, _stop, _done = _make_tail()
            snaps = _snapshots((100, 400, 800, 1500))
            for snap in snaps[:-1]:
                writer.think(3, 8, snap)  # писатель обновляет чаще опроса
            _ = _poll(tail)
            self.assertEqual(_text_of(emitted), snaps[2])
            writer.think(3, 3, snaps[-1])
            _ = _poll(tail)
            self.assertEqual(_text_of(emitted), snaps[-1])
            self.assertEqual(len(emitted), 2)

    def test_tc24_multistep_order_follows_step_order(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            writer = fx.writer()
            tail, emitted, _stop, _done = _make_tail()
            writer.think(3, 3, "первый шаг")
            writer.think(7, 8, "второй шаг")
            _ = _poll(tail)
            writer.think(7, 3, "второй шаг, продолжение")
            _ = _poll(tail)
            self.assertEqual([idx for idx, _t in emitted], [3, 7, 7])
            self.assertEqual(_text_of(emitted, 3), "первый шаг")
            self.assertEqual(_text_of(emitted, 7), "второй шаг, продолжение")


class DedupTests(unittest.TestCase):
    """REQ-003: ровно одна выдача шага при двух источниках (TC-30..TC-33)."""

    def test_tc30_both_sources_same_final_text_emitted_once(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            writer = fx.writer()
            tail, emitted, _stop, _done = _make_tail()
            final = (
                "Ответ: думаю про задачу, then English words, и снова русский текст."
            )
            writer.think(3, 8, final[:20])
            _ = _poll(tail)
            writer.think(3, 3, final)
            _ = _poll(tail)
            fx.append_record(
                {"type": "PLANNER_RESPONSE", "step_index": 3, "thinking": final}
            )
            _ = _ofn(tail, "_read_transcript")()
            self.assertEqual(_text_of(emitted), final)
            self.assertEqual(_text_of(emitted).encode("utf-8"), final.encode("utf-8"))

    def test_tc31_transcript_before_database_gives_no_duplicates(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            writer = fx.writer()
            tail, emitted, _stop, _done = _make_tail()
            final = "финальный текст шага"
            fx.append_record(
                {"type": "PLANNER_RESPONSE", "step_index": 3, "thinking": final}
            )
            _ = _ofn(tail, "_read_transcript")()
            self.assertEqual(_text_of(emitted), final)
            writer.think(3, 8, final[:5])
            writer.think(3, 3, final)
            _ = _poll(tail)
            self.assertEqual(_text_of(emitted), final)
            self.assertEqual(len(emitted), 1)

    def test_tc32_non_prefix_snapshot_never_repeats_delivered_prefix(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            writer = fx.writer()
            tail, emitted, _stop, _done = _make_tail()
            writer.think(3, 8, "abc")
            _ = _poll(tail)
            writer.think(3, 8, "abXde")
            _ = _poll(tail)
            self.assertEqual(emitted, [(3, "abc")])
            state = cast("dict[int, object]", _oval(tail, "seen"))[3]
            self.assertIs(_oval(state, "diverged"), True)
            self.assertEqual(_bval("_sqlite_divergence_count"), 1)
            fx.append_record(
                {"type": "PLANNER_RESPONSE", "step_index": 3, "thinking": "abXde"}
            )
            _ = _ofn(tail, "_read_transcript")()
            self.assertEqual(emitted, [(3, "abc")])

    def test_tc33_cyrillic_and_ascii_steps_equal_final_text(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            writer = fx.writer()
            tail, emitted, _stop, _done = _make_tail()
            cyr = "".join(chr(0x410 + i % 32) for i in range(1080))
            asc = "".join(chr(97 + i % 26) for i in range(5561))
            for idx, text in ((3, cyr), (5, asc)):
                writer.think(idx, 8, text[: len(text) // 2])
                _ = _poll(tail)
                writer.think(idx, 3, text)
                _ = _poll(tail)
                fx.append_record(
                    {"type": "PLANNER_RESPONSE", "step_index": idx, "thinking": text}
                )
                _ = _ofn(tail, "_read_transcript")()
            self.assertEqual(_text_of(emitted, 3).encode("utf-8"), cyr.encode("utf-8"))
            self.assertEqual(_text_of(emitted, 5).encode("utf-8"), asc.encode("utf-8"))


def _damaged_db(fx: _Fixture, kind: str) -> None:
    path = fx.db_path()
    if kind == "garbage":
        _ = path.write_bytes(b"this is not a database " * 400)
    elif kind == "no_steps":
        conn = sqlite3.connect(str(path))
        _ = conn.execute("CREATE TABLE other (x integer)")
        conn.commit()
        conn.close()
    elif kind == "no_column":
        conn = sqlite3.connect(str(path))
        _ = conn.execute(
            "CREATE TABLE steps (idx integer PRIMARY KEY, step_type integer, status integer)"
        )
        _ = conn.execute("INSERT INTO steps VALUES (3, 15, 8)")
        conn.commit()
        conn.close()


def _thinking_turn_events() -> list[dict[str, object]]:
    return [
        _init_ev(0.05),
        _tr_ev(0.25, 3, "мышление из транскрипта"),
        _text_ev(0.5),
        _result_ev(0.55),
        _exit_ev(0.6),
    ]


class FailOpenTests(unittest.TestCase):
    """REQ-004: SQLite вспомогателен, ход идёт на транскрипте (TC-40..TC-44)."""

    def test_tc40_missing_database_turn_uses_transcript(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            fx.prime_canary()
            tail, emitted, _stop, _done = _make_tail()
            self.assertIsNone(_poll(tail))
            self.assertIs(_oval(tail, "failed"), False)
            self.assertEqual(emitted, [])
            _ = fx.write_scenario(_thinking_turn_events())
            turn = _run_turn()
            self.assertEqual(turn.out["state"], "done")
            self.assertEqual(turn.out["text"], "ответ")
            self.assertEqual(turn.reasoning(), "мышление из транскрипта")

    def test_tc41_closed_wal_database_is_not_a_failure(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            fx.prime_canary()
            writer = fx.writer()
            writer.think(3, 8, "закрытая база")
            writer.close()
            fx.writers.clear()
            tail, _emitted, _stop, _done = _make_tail()
            _ = _poll(
                tail
            )  # на 3.9.6 mode=ro не открывает закрытую WAL-БД: «изменений нет»
            self.assertIs(_oval(tail, "failed"), False)
            _ = fx.write_scenario(_thinking_turn_events())
            turn = _run_turn()
            self.assertEqual(turn.out["state"], "done")
            self.assertIn("мышление из транскрипта", turn.reasoning())

    def test_tc42_exclusive_lock_skips_poll_without_hanging(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            writer = fx.writer(wal=False)
            writer.think(3, 8, "под блокировкой")
            _ = writer.conn.execute("BEGIN EXCLUSIVE")
            tail, emitted, _stop, _done = _make_tail()
            started = time.monotonic()
            _ = _poll(tail)
            elapsed = time.monotonic() - started
            _ = writer.conn.execute("ROLLBACK")
            self.assertLess(elapsed, 0.5)
            self.assertEqual(emitted, [])
            self.assertIs(_oval(tail, "failed"), False)

    def test_tc43_unknown_schema_means_no_thinking_and_done_turn(self) -> None:
        for kind in ("no_steps", "no_column"):
            with self.subTest(kind=kind), _Fixture() as fx:
                fx.set_flag(True)
                fx.prime_canary()
                _damaged_db(fx, kind)
                tail, emitted, _stop, _done = _make_tail()
                buffer = io.StringIO()
                with mock.patch.object(sys, "stderr", buffer):
                    _ = _poll(tail)
                self.assertEqual(emitted, [])
                self.assertIs(_oval(tail, "failed"), True)
                self.assertIs(_oval(tail, "sqlite_active"), False)
                self.assertIn("sqlite-schema-mismatch", buffer.getvalue())
                _ = fx.write_scenario(_thinking_turn_events())
                turn = _run_turn()
                self.assertEqual(turn.out["state"], "done")
                self.assertEqual(turn.reasoning(), "мышление из транскрипта")

    def test_tc44_garbage_file_is_handled_like_unknown_schema(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            fx.prime_canary()
            _damaged_db(fx, "garbage")
            tail, emitted, _stop, _done = _make_tail()
            _ = _poll(tail)
            self.assertEqual(emitted, [])
            self.assertIs(_oval(tail, "failed"), True)
            self.assertIs(_oval(tail, "sqlite_active"), False)
            _ = fx.write_scenario(_thinking_turn_events())
            turn = _run_turn()
            self.assertEqual(turn.out["state"], "done")
            self.assertEqual(turn.reasoning(), "мышление из транскрипта")


class ResumeTests(unittest.TestCase):
    """REQ-005: продолжение треда не переотдаёт историю (TC-50, TC-51)."""

    def test_tc50_resumed_turn_emits_only_new_steps(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            writer = fx.writer()
            for idx in range(4):
                writer.think(idx, 3, "прошлый ход %d" % idx)
            plan = _bfn("_prespawn_plan")(_CID, True)
            self.assertIs(_oval(plan, "anchored"), True)
            self.assertEqual(_oval(plan, "base_idx"), 4)
            tail, emitted, _stop, _done = _make_tail(
                base_idx=_int(_oval(plan, "base_idx")), resumed=True
            )
            _ = _poll(tail)
            self.assertEqual(emitted, [])
            writer.think(4, 8, "новый шаг")
            _ = _poll(tail)
            self.assertEqual(emitted, [(4, "новый шаг")])

    def test_tc51_new_transcript_record_after_init_is_not_lost(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            for idx in range(3):
                fx.append_record(
                    {
                        "type": "PLANNER_RESPONSE",
                        "step_index": idx,
                        "thinking": "старый %d" % idx,
                    }
                )
            plan = _bfn("_prespawn_plan")(_CID, True)
            self.assertEqual(_oval(plan, "base_idx"), 3)
            self.assertEqual(_oval(plan, "offset"), fx.transcript().stat().st_size)
            time.sleep(0.05)
            fx.append_record(
                {"type": "PLANNER_RESPONSE", "step_index": 3, "thinking": "новый"}
            )
            tail, emitted, _stop, _done = _make_tail(
                mode="OFF",
                base_idx=_int(_oval(plan, "base_idx")),
                offset=_int(_oval(plan, "offset")),
                resumed=True,
            )
            _ = _ofn(tail, "_read_transcript")()
            self.assertEqual(emitted, [(3, "новый")])
            setattr(
                tail, "_offset", 0
            )  # файл переписан с нуля: история всё равно отсекается
            _ = _ofn(tail, "_read_transcript")()
            self.assertEqual(emitted, [(3, "новый")])


def _late_ev(t: float, delay: float, idx: int, thinking: str) -> dict[str, object]:
    """Запись шага в транскрипт ПОСЛЕ выхода процесса (F-29: +90 мс после result)."""
    record: dict[str, object] = {
        "type": "PLANNER_RESPONSE",
        "step_index": idx,
        "thinking": thinking,
        "tool_calls": [{"name": "run_command"}],
    }
    return {"t": t, "op": "late_transcript", "delay": delay, "record": record}


def _run_many(count: int, workers: int = 4, stream: bool = True) -> list[_Turn]:
    """count ходов подряд в workers потоках (слотов моста по умолчанию 4)."""
    results: list[_Turn] = []
    lock = threading.Lock()
    remaining = [count]

    def work() -> None:
        while True:
            with lock:
                if remaining[0] <= 0:
                    return
                remaining[0] -= 1
            turn = _run_turn(_ctx(stream=stream))
            with lock:
                results.append(turn)

    threads = [threading.Thread(target=work) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(120)
    return results


def _exit_time(fx: _Fixture) -> float:
    lines = (fx.tmp / "exit.ts").read_text(encoding="utf-8").split()
    return float(lines[-1])


def _sse_frames(ctx: dict[str, object]) -> list[str]:
    frames: list[str] = []

    def emit(data: str) -> bool:
        frames.append(data)
        return True

    def noop(*_args: object, **_kwargs: object) -> None:
        return None

    with _Sock() as sock:
        handler = cast(object, _make_handler(sock))
        setattr(handler, "send_response", noop)
        setattr(handler, "send_header", noop)
        setattr(handler, "end_headers", noop)
        setattr(handler, "_emit", emit)
        _ = _ofn(handler, "_serve_sse")(ctx)
    return frames


class FinalDrainTests(unittest.TestCase):
    """REQ-006/REQ-007: мышление последнего шага не теряется, drain ограничен (TC-60..TC-63)."""

    def test_tc60_late_record_reaches_client_before_stop(self) -> None:
        with _Fixture() as fx:
            thinking = "мышление последнего шага"
            events = [
                _init_ev(0.05),
                _text_ev(0.1),
                _result_ev(0.15),
                _late_ev(0.16, 0.09, 3, thinking),
                _exit_ev(0.17),
            ]
            _ = fx.write_scenario(events)
            turns = _run_many(20)
            self.assertEqual(len(turns), 20)
            hits = sum(1 for turn in turns if turn.reasoning() == thinking)
            self.assertEqual(hits, 20)
            frames = _sse_frames(_ctx())
            reasoning_at = [i for i, f in enumerate(frames) if "reasoning_content" in f]
            stop_at = [
                i for i, f in enumerate(frames) if '"finish_reason": "stop"' in f
            ]
            self.assertTrue(reasoning_at and stop_at)
            self.assertLess(reasoning_at[0], stop_at[0])

    def test_tc61_json_mode_contains_reasoning_content(self) -> None:
        with _Fixture() as fx:
            thinking = "мышление нестримингового хода"
            events = [
                _init_ev(0.05),
                _text_ev(0.1),
                _result_ev(0.15),
                _late_ev(0.16, 0.09, 3, thinking),
                _exit_ev(0.17),
            ]
            _ = fx.write_scenario(events)
            seen: list[str] = []
            lock = threading.Lock()

            def one_run() -> None:
                sent: list[tuple[int, object]] = []

                def send(code: int, payload: object) -> None:
                    sent.append((code, payload))

                with _Sock() as sock:
                    handler = cast(object, _make_handler(sock))
                    setattr(handler, "_send", send)
                    _ = _ofn(handler, "_serve_json")(_ctx(stream=False))
                _code, payload = sent[0]
                message = _dict(
                    _dict(cast("list[object]", _dict(payload)["choices"])[0])["message"]
                )
                with lock:
                    seen.append(_str(message.get("reasoning_content")))

            for _round in range(5):
                threads = [threading.Thread(target=one_run) for _ in range(4)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(60)
            self.assertEqual(seen, [thinking] * 20)

    def test_tc62_silent_sources_stop_within_one_second_of_eof(self) -> None:
        with _Fixture() as fx:
            _ = fx.write_scenario(
                [_init_ev(0.05), _text_ev(0.1), _result_ev(0.15), _exit_ev(0.16)]
            )
            turn = _run_turn()
            self.assertEqual(turn.out["state"], "done")
            self.assertEqual(turn.reasoning(), "")
            self.assertLessEqual(turn.ended - _exit_time(fx), 1.0)
            with (
                mock.patch.object(_bridge(), "DRAIN_WINDOW_S", 0.5),
                mock.patch.object(_bridge(), "DRAIN_MIN_S", 0.25),
                mock.patch.object(_bridge(), "JOIN_TIMEOUT_S", 0.2),
            ):
                turn = _run_turn()
            self.assertEqual(turn.out["state"], "done")
            self.assertLessEqual(turn.ended - _exit_time(fx), 1.0)

    def test_tc63_record_after_the_window_is_dropped_without_hanging(self) -> None:
        with _Fixture() as fx:
            events = [
                _init_ev(0.05),
                _text_ev(0.1),
                _result_ev(0.15),
                _late_ev(0.16, 1.5, 3, "слишком поздняя запись"),
                _exit_ev(0.17),
            ]
            _ = fx.write_scenario(events)
            turn = _run_turn()
            self.assertEqual(turn.out["state"], "done")
            self.assertEqual(turn.reasoning(), "")
            self.assertLessEqual(turn.ended - _exit_time(fx), 1.0)


class DeliveredReasoningTests(unittest.TestCase):
    """REQ-008: отданное мышление — выдача, повтор поверх него запрещён (TC-70..TC-72)."""

    def _quota_events(self) -> list[dict[str, object]]:
        return [
            _init_ev(0.05),
            _tr_ev(0.2, 3, "мышление до сбоя квоты"),
            _result_ev(
                0.8, status="ERROR", error="Individual quota reached", response=""
            ),
            _exit_ev(0.85, code=1),
        ]

    def test_tc70_quota_error_after_reasoning_runs_process_once(self) -> None:
        with _Fixture() as fx:
            _ = fx.write_scenario(self._quota_events())
            turn = _run_turn()
            self.assertEqual(len(fx.spawns()), 1)
            self.assertEqual(turn.out["state"], "agy_error")
            self.assertEqual(turn.reasoning(), "мышление до сбоя квоты")
            self.assertEqual(len(turn.chunks), 1)

    def test_tc71_hot_session_failure_after_reasoning_has_no_cold_retry(self) -> None:
        with _Fixture() as fx:
            _ = fx.write_scenario(self._quota_events())
            ctx = _ctx(
                hot_resumed=True,
                sess_key=("m", "", "low"),
                conversation_id=_CID,
                tools_count=1,
                full_prompt="полная история",
                prompt="новое сообщение",
            )
            turn = _run_turn(ctx)
            spawns = fx.spawns()
            self.assertEqual(len(spawns), 1)
            self.assertIn("--conversation", spawns[0])
            self.assertEqual(turn.out["state"], "agy_error")
            self.assertEqual(turn.reasoning(), "мышление до сбоя квоты")

    def test_tc72_failure_before_any_delivery_is_still_retried(self) -> None:
        with _Fixture() as fx:
            failing = [
                _init_ev(0.05),
                _result_ev(0.2, status="ERROR", error="boom", response=""),
                _exit_ev(0.25, code=1),
            ]
            fine = [_init_ev(0.05), _text_ev(0.1), _result_ev(0.15), _exit_ev(0.2)]
            _ = fx.write_scenario([], spawns=[failing, fine])

            def no_pause() -> float:
                return 0.0

            fx.patch("_rng", no_pause)
            turn = _run_turn()
            self.assertEqual(len(fx.spawns()), 2)
            self.assertEqual(turn.out["state"], "done")
            self.assertEqual(turn.out["text"], "ответ")


class _HttpBridge:
    """Настоящий HTTP-сервер моста на свободном порту с фейковым agy."""

    server: object
    port: int
    thread: threading.Thread

    def __init__(self) -> None:
        self.server = _bfn("Server")(("127.0.0.1", 0), _bval("Handler"))
        address = cast("tuple[str, int]", _oval(self.server, "server_address"))
        self.port = address[1]
        self.thread = threading.Thread(
            target=_ofn(self.server, "serve_forever"), daemon=True
        )
        self.thread.start()

    def close(self) -> None:
        _ = _ofn(self.server, "shutdown")()
        _ = _ofn(self.server, "server_close")()
        self.thread.join(10)

    def post(self, body: dict[str, object]) -> tuple[int, dict[str, object]]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + _str(_bval("AUTH_KEY")),
        }
        conn.request(
            "POST", "/v1/chat/completions", body=json.dumps(body), headers=headers
        )
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        return response.status, _dict(cast(object, json.loads(raw.decode("utf-8"))))

    def get(self, path: str) -> tuple[int, dict[str, object]]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", path)
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        return response.status, _dict(cast(object, json.loads(raw.decode("utf-8"))))


def _agentic_body(text: str, history: bool = False) -> dict[str, object]:
    messages: list[dict[str, object]] = [{"role": "user", "content": "начало диалога"}]
    if history:
        messages.append({"role": "assistant", "content": "ответ"})
    messages.append({"role": "user", "content": text})
    tool: dict[str, object] = {
        "type": "function",
        "function": {"name": "x", "parameters": {}},
    }
    return {"messages": messages, "tools": [tool], "stream": False}


def _plain_body(text: str, history: bool = False) -> dict[str, object]:
    body = _agentic_body(text, history)
    del body["tools"]
    return body


def _quick(cid: str, text: str = "ответ") -> list[dict[str, object]]:
    return [
        _init_ev(0.05, cid),
        _text_ev(0.1, text),
        _result_ev(0.15, cid),
        _exit_ev(0.2),
    ]


def _slow(cid: str, until: float) -> list[dict[str, object]]:
    return [
        _init_ev(0.05, cid),
        _text_ev(0.1),
        _result_ev(until, cid),
        _exit_ev(until + 0.05),
    ]


class SessionIsolationTests(unittest.TestCase):
    """REQ-009: фоновые запросы без tools не трогают горячую сессию (TC-80..TC-82)."""

    def test_tc80_background_request_does_not_steal_agentic_session(self) -> None:
        with _Fixture() as fx:
            _ = fx.write_scenario(
                [], spawns=[_quick(_CID), _quick(_CID_B), _quick(_CID)]
            )
            http_bridge = _HttpBridge()
            try:
                code1, body1 = http_bridge.post(_agentic_body("первый агентный ход"))
                code2, body2 = http_bridge.post(_plain_body("придумай заголовок"))
                code3, body3 = http_bridge.post(
                    _agentic_body("второй агентный ход", True)
                )
            finally:
                http_bridge.close()
            self.assertEqual((code1, code2, code3), (200, 200, 200))
            spawns = fx.spawns()
            self.assertEqual(len(spawns), 3)
            self.assertNotIn("--conversation", spawns[1])
            self.assertEqual(spawns[2][spawns[2].index("--conversation") + 1], _CID)
            self.assertEqual(body1["conversation_id"], _CID)
            self.assertEqual(body2["conversation_id"], _CID_B)
            self.assertEqual(body3["conversation_id"], _CID)

    def test_tc81_background_request_during_agentic_turn_keeps_entry(self) -> None:
        with _Fixture() as fx:
            _ = fx.write_scenario(
                [], spawns=[_quick(_CID), _slow(_CID, 1.4), _quick(_CID_B)]
            )
            http_bridge = _HttpBridge()
            results: list[tuple[int, dict[str, object]]] = []
            try:
                _ = http_bridge.post(_agentic_body("первый агентный ход"))

                def slow_request() -> None:
                    results.append(http_bridge.post(_agentic_body("долгий ход", True)))

                worker = threading.Thread(target=slow_request)
                worker.start()
                deadline = time.monotonic() + 10
                while len(fx.spawns()) < 2 and time.monotonic() < deadline:
                    time.sleep(0.02)
                code_bg, body_bg = http_bridge.post(_plain_body("фоновый заголовок"))
                worker.join(30)
            finally:
                http_bridge.close()
            self.assertEqual(code_bg, 200)
            self.assertEqual(body_bg["conversation_id"], _CID_B)
            spawns = fx.spawns()
            self.assertEqual(len(spawns), 3)
            self.assertIn("--conversation", spawns[1])
            self.assertNotIn("--conversation", spawns[2])
            store = cast("dict[object, dict[str, object]]", _bval("_session_store"))
            self.assertEqual([entry["cid"] for entry in store.values()], [_CID])
            self.assertEqual(len(cast("set[str]", _bval("_in_flight_cids"))), 0)
            self.assertEqual(len(results), 1)

    def test_tc82_plain_dialogs_never_share_or_claim_sessions(self) -> None:
        with _Fixture() as fx:
            cids = [_CID, _CID_B, _CID_C, _CID_B]
            _ = fx.write_scenario([], spawns=[_quick(cid) for cid in cids])
            claims: list[object] = []
            real_claim = _bfn("_session_claim")

            def spy(*args: object) -> object:
                claims.append(args)
                return real_claim(*args)

            fx.patch("_session_claim", spy)
            http_bridge = _HttpBridge()
            try:
                codes = [
                    http_bridge.post(_plain_body("диалог А, ход 1"))[0],
                    http_bridge.post(_plain_body("диалог Б, ход 1"))[0],
                    http_bridge.post(_plain_body("диалог А, ход 2", True))[0],
                    http_bridge.post(_plain_body("диалог Б, ход 2", True))[0],
                ]
            finally:
                http_bridge.close()
            self.assertEqual(codes, [200, 200, 200, 200])
            self.assertEqual(claims, [])
            self.assertTrue(all("--conversation" not in argv for argv in fx.spawns()))
            self.assertEqual(
                len(cast("dict[object, object]", _bval("_session_store"))), 0
            )


class SwitchAndObservabilityTests(unittest.TestCase):
    """REQ-011/REQ-012: флаг выключен — БД не открывается; логи без текста мышления."""

    def test_tc91_disabled_flag_never_opens_a_database(self) -> None:
        real_connect = cast(Callable[..., sqlite3.Connection], sqlite3.connect)
        calls: list[str] = []

        def counting_connect(database: str, **kwargs: object) -> sqlite3.Connection:
            calls.append(database)
            return real_connect(database, **kwargs)

        with _Fixture() as fx:
            fx.writer().think(3, 3, "есть база")
            fx.writers.clear()
            events = [
                _init_ev(0.05),
                _tr_ev(0.25, 3, "мышление из транскрипта"),
                _text_ev(0.5),
                _result_ev(0.55),
                _exit_ev(0.6),
            ]
            _ = fx.write_scenario(events)
            with mock.patch.object(sqlite3, "connect", counting_connect):
                off = _run_turn()  # файла dynamic_config.json нет: fail-closed
                fx.set_flag(True)
                fx.set_env("AGY_SQLITE_REASONING_ENABLED", "0")
                env_off = _run_turn(_ctx(conversation_id=_CID, tools_count=1))
            self.assertEqual(calls, [])
            self.assertEqual(off.reasoning(), "мышление из транскрипта")
            self.assertEqual(env_off.out["state"], "done")
            self.assertFalse(_bfn("_is_sqlite_reasoning_enabled")())

    def test_tc92_diagnostic_lines_carry_ids_but_never_thinking_text(self) -> None:
        secret = "СЕКРЕТНОЕ-МЫШЛЕНИЕ-ФИКСТУРЫ"
        with _Fixture() as fx:
            fx.set_flag(True)
            fx.prime_canary()
            events = [
                _init_ev(0.05),
                _db_ev(0.3, 3, 8, secret[:10]),
                _db_ev(1.0, 3, 8, secret),
                _db_ev(1.3, 3, 3, secret),
                _text_ev(1.4),
                _result_ev(1.45),
                _exit_ev(1.5),
            ]
            _ = fx.write_scenario(events)
            buffer = io.StringIO()
            with mock.patch.object(sys, "stderr", buffer):
                turn = _run_turn()
            log = buffer.getvalue()
            self.assertEqual(turn.reasoning(), secret)
            self.assertRegex(log, r"sqlite-emit cid=82188e72 step=3 len=\d+")
            self.assertRegex(log, r"reasoning-emit cid=82188e72 n=\d+ len=\d+ ok=1")
            self.assertRegex(log, r"drain cid=82188e72 ms=\d+ emitted=\d+ outcome=\w+")
            self.assertNotIn(secret, log)
            self.assertNotIn(secret[:10], log)


def _stepping_time(clock: _FakeClock) -> SimpleNamespace:
    """Мок-время моста: sleep двигает те же часы, что и monotonic."""
    return SimpleNamespace(
        monotonic=clock, sleep=clock.advance, strftime=time.strftime, time=time.time
    )


def _spy_open(
    fx: _Fixture, stamps: list[float], clock: _FakeClock | None = None
) -> None:
    """Считает открытия БД источником (время по мок-часам или монотонное)."""
    real = _bfn("_sqlite_open_ro")

    def spy(path: object) -> object:
        stamps.append(clock() if clock is not None else time.monotonic())
        return real(path)

    fx.patch("_sqlite_open_ro", spy)


def _spy_parser(
    fx: _Fixture, calls: list[int], after_first: threading.Event | None = None
) -> None:
    real = _bfn("_extract_thinking_from_step_blob")

    def spy(raw: object, final: bool, stop: object = None) -> object:
        calls.append(1)
        if after_first is not None:
            after_first.set()
        return real(raw, final, stop)

    fx.patch("_extract_thinking_from_step_blob", spy)


class _StubTail:
    """Подмена источника мыслей для Run: поток жив, пока interrupt его не отпустит."""

    cid: str
    thread: threading.Thread
    release: threading.Event
    events: list[str]

    def __init__(self) -> None:
        self.cid = ""
        self.release = threading.Event()
        self.events = []
        self.thread = threading.Thread(target=self._block, daemon=True)
        self.thread.start()

    def _block(self) -> None:
        _ = self.release.wait(10)

    def interrupt_active_query(self) -> None:
        self.events.append("interrupt")
        self.release.set()


def _bare_run() -> object:
    """Run без процесса: только то, что нужно для _emit_reasoning/_close_and_put_done."""
    run = object.__new__(cast("type[object]", _bval("Run")))
    setattr(run, "_emit_lock", threading.Lock())
    setattr(run, "q", queue.Queue())
    setattr(run, "drain_closed", False)
    setattr(run, "_done_put", False)
    setattr(run, "_reasoning_bytes", 0)
    setattr(run, "_cap_logged", False)
    setattr(run, "_tail", SimpleNamespace(cid=""))
    return run


def _queue_kinds(run: object) -> list[str]:
    q = cast("queue.Queue[tuple[str, object]]", _oval(run, "q"))
    kinds: list[str] = []
    while not q.empty():
        kinds.append(q.get_nowait()[0])
    return kinds


class BreakerAndBudgetTests(unittest.TestCase):
    """AD-005: circuit breaker с probe_gen, целочисленные бюджеты (AO-01, AO-02)."""

    def test_ao01_breaker_fsm_atomic_probe_and_stale_probe(self) -> None:
        clock = _FakeClock()
        with _Fixture(), mock.patch.object(_bridge(), "time", _fake_time(clock)):
            report = _bfn("_breaker_report")
            acquire = _bfn("_breaker_acquire")
            # единичная divergence и холодные ходы не открывают breaker
            _ = report(None, 1, True)
            self.assertEqual(_bval("_breaker_state"), "CLOSED")
            _ = report(None, 1, False)
            self.assertEqual(_bval("_breaker_failures"), 0)
            for _turn in range(3):
                _ = report(None, 0, False)
            self.assertEqual(_bval("_breaker_state"), "CLOSED")
            # классификация ошибок источника
            for message, failed in (
                (sqlite3.OperationalError("unable to open database file"), False),
                (sqlite3.OperationalError("no such table: steps"), True),
                (sqlite3.OperationalError("no such column: step_payload"), True),
                (sqlite3.DatabaseError("file is not a database"), True),
            ):
                tail, _emitted, _stop, _done = _make_tail()
                _ = _ofn(tail, "_on_sqlite_error")(message)
                self.assertEqual(_oval(tail, "failed"), failed, str(message))
            tail, _emitted, stop, _done = _make_tail()
            stop.set()
            _ = _ofn(tail, "_on_sqlite_error")(sqlite3.OperationalError("interrupted"))
            self.assertIs(_oval(tail, "failed"), False)
            # три сбойных хода -> OPEN: connect не вызывается
            for _turn in range(3):
                _ = report(None, 1, True)
            self.assertEqual(_bval("_breaker_state"), "OPEN")
            self.assertEqual(acquire(), (False, None))
            self.assertFalse(_bfn("_breaker_permits")(None))
            # cooldown 30 с: 10 одновременных ходов -> ровно одна проба с probe_gen
            clock.advance(30.1)
            barrier = threading.Barrier(10)
            answers: list[object] = []
            lock = threading.Lock()

            def competitor() -> None:
                _ = barrier.wait(10)
                got = acquire()
                with lock:
                    answers.append(got)

            threads = [threading.Thread(target=competitor) for _ in range(10)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(10)
            winners = [a for a in answers if cast("tuple[bool, int | None]", a)[0]]
            self.assertEqual(len(answers), 10)
            self.assertEqual(len(winners), 1)
            gen = cast("tuple[bool, int | None]", winners[0])[1]
            self.assertIsNotNone(gen)
            self.assertEqual(_bval("_breaker_state"), "HALF_OPEN")
            # исходы пробы: SELECT без ошибок -> CLOSED
            _ = report(gen, 1, False)
            self.assertEqual(_bval("_breaker_state"), "CLOSED")
            self.assertEqual(_bval("_breaker_failures"), 0)
            # ошибка пробы -> OPEN
            for _turn in range(3):
                _ = report(None, 1, True)
            clock.advance(30.1)
            ok, gen2 = cast("tuple[bool, int | None]", acquire())
            self.assertTrue(ok)
            _ = report(gen2, 0, True)
            self.assertEqual(_bval("_breaker_state"), "OPEN")
            # проба без SELECT снимается, остаётся HALF_OPEN
            clock.advance(30.1)
            ok, gen3 = cast("tuple[bool, int | None]", acquire())
            self.assertTrue(ok)
            _ = report(gen3, 0, False)
            self.assertEqual(_bval("_breaker_state"), "HALF_OPEN")
            self.assertIsNone(_bval("_breaker_active_probe_gen"))
            # аренда 60 с: устаревшая проба не меняет FSM
            ok, gen4 = cast("tuple[bool, int | None]", acquire())
            self.assertTrue(ok)
            clock.advance(60.1)
            ok, gen5 = cast("tuple[bool, int | None]", acquire())
            self.assertTrue(ok)
            self.assertEqual(gen5, _int(gen4) + 1)
            self.assertFalse(_bfn("_breaker_permits")(gen4))
            self.assertTrue(_bfn("_breaker_permits")(gen5))
            _ = report(gen4, 1, True)
            self.assertEqual(_bval("_breaker_state"), "HALF_OPEN")
            self.assertEqual(_bval("_breaker_active_probe_gen"), gen5)
            _ = report(gen5, 1, False)
            self.assertEqual(_bval("_breaker_state"), "CLOSED")
            _ = _bfn("_reset_sqlite_guards_for_tests")()
            self.assertEqual(_bval("_breaker_probe_gen"), 0)

    def test_ao02_retry_budget_integer_tenths_and_full_jitter(self) -> None:
        with _Fixture() as fx:
            retries = 0
            for _request in range(100):
                _ = _bfn("_retry_credit")()
                if _bfn("_retry_take")():
                    retries += 1
            self.assertLessEqual(retries, 23)
            setattr(_bridge(), "_retry_tenths", 0)
            for _credit in range(5):
                _ = _bfn("_retry_credit")()
            self.assertEqual(
                _bval("_retry_tenths"), 10
            )  # без float-дрейфа ровно один повтор
            self.assertTrue(_bfn("_retry_take")())
            self.assertFalse(_bfn("_retry_take")())
            for _credit in range(40):
                _ = _bfn("_retry_credit")()
            self.assertEqual(_bval("_retry_tenths"), 30)
            pauses: list[float] = []
            for u in (0.0, 0.5, 1.0):

                def rng(value: float = u) -> float:
                    return value

                pauses.append(_float(_bfn("_retry_pause_s")(1, rng)))
            self.assertEqual(pauses, [0.0, 1.0, 2.0])
            # hot -> cold fallback тоже стоит 10 десятых; пустой бюджет повтор не даёт
            failing = [
                _init_ev(0.05),
                _result_ev(0.2, status="ERROR", error="boom", response=""),
                _exit_ev(0.25, code=1),
            ]
            fine = [_init_ev(0.05), _text_ev(0.1), _result_ev(0.15), _exit_ev(0.2)]
            _ = fx.write_scenario([], spawns=[failing, fine])
            ctx = _ctx(
                hot_resumed=True,
                sess_key=("m", "", "low"),
                conversation_id=_CID,
                tools_count=1,
                full_prompt="полная история",
                prompt="новое",
            )
            turn = _run_turn(ctx)
            self.assertEqual(turn.out["state"], "done")
            self.assertEqual(len(fx.spawns()), 2)
            self.assertEqual(ctx["conversation_id"], "")
            self.assertEqual(_bval("_retry_tenths"), 20)
            setattr(_bridge(), "_retry_tenths", 0)
            fx.tmp.joinpath("argv.log").unlink()
            ctx2 = _ctx(
                hot_resumed=True,
                sess_key=("m", "", "low"),
                conversation_id=_CID,
                tools_count=1,
                full_prompt="полная история",
                prompt="новое",
            )
            turn2 = _run_turn(ctx2)
            self.assertEqual(turn2.out["state"], "agy_error")
            self.assertEqual(len(fx.spawns()), 1)


class DrainAndJoinTests(unittest.TestCase):
    """AD-002: окно drain, ранний выход только по маркеру, закрытие очереди (AO-03)."""

    def _drain(
        self,
        fx: _Fixture,
        records: list[dict[str, object]],
        mode: str = "OFF",
        window: float = 0.35,
    ) -> tuple[float, str]:
        clock = _FakeClock(500.0)
        buffer = io.StringIO()
        with (
            mock.patch.object(_bridge(), "time", _stepping_time(clock)),
            mock.patch.object(sys, "stderr", buffer),
        ):
            tail, _emitted, _stop, done = _make_tail(mode=mode)
            for record in records:
                fx.append_record(record)
            done.set()
            setattr(tail, "drain_deadline", clock() + window)
            started = clock()
            _ = _ofn(tail, "_drain_post_eof")()
            elapsed = clock() - started
        return elapsed, buffer.getvalue()

    def test_ao03_no_early_exit_without_authoritative_marker(self) -> None:
        final: dict[str, object] = {
            "type": "PLANNER_RESPONSE",
            "step_index": 3,
            "content": "ответ",
        }
        thinking: dict[str, object] = {
            "type": "PLANNER_RESPONSE",
            "step_index": 2,
            "thinking": "т",
            "tool_calls": [1],
        }
        with _Fixture() as fx:
            elapsed, log = self._drain(fx, [thinking, final])
            self.assertGreaterEqual(elapsed, 0.34)
            self.assertLessEqual(elapsed, 0.40)
            self.assertIn("outcome=complete pending_steps=0 exit=window", log)
        with _Fixture() as fx:
            end_turn: dict[str, object] = {"type": "END_TURN", "step_index": 4}
            elapsed, log = self._drain(fx, [end_turn])
            self.assertGreaterEqual(elapsed, 0.15)
            self.assertLess(elapsed, 0.30)
            self.assertIn("exit=end_turn", log)
        with _Fixture() as fx:
            elapsed, log = self._drain(fx, [], window=10.0)
            self.assertLessEqual(elapsed, 0.55)  # DRAIN_MAX_S — жёсткая граница окна
            self.assertIn("outcome=window_complete", log)

    def test_ao03_planner_final_with_two_quiet_selects_holds_full_window(self) -> None:
        final: dict[str, object] = {
            "type": "PLANNER_RESPONSE",
            "step_index": 4,
            "content": "ответ",
        }
        step: dict[str, object] = {
            "type": "PLANNER_RESPONSE",
            "step_index": 3,
            "thinking": "шаг",
            "tool_calls": [1],
        }
        with _Fixture() as fx:
            fx.set_flag(True)
            writer = fx.writer()
            writer.think(3, 3, "шаг")
            elapsed, log = self._drain(fx, [step, final], mode="LIVE")
            # PLANNER_RESPONSE без END_TURN: раннего planner_final нет, полное окно.
            self.assertGreaterEqual(elapsed, 0.34)
            self.assertLessEqual(elapsed, 0.40)
            self.assertIn("outcome=complete pending_steps=0 exit=window", log)
            self.assertNotIn("exit=planner_final", log)

    def test_ao03_pending_step_gives_window_complete_and_counts_deadline(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            writer = fx.writer()
            writer.think(3, 3, "шаг завершён, записи в транскрипте ещё нет")
            elapsed, log = self._drain(fx, [], mode="LIVE")
            self.assertGreaterEqual(elapsed, 0.34)
            self.assertIn("outcome=window_complete pending_steps=1", log)
            self.assertEqual(_bval("_sqlite_drain_deadline_count"), 1)

    def test_ao03_time_budget_and_closed_queue_never_hold_late_reasoning(self) -> None:
        default_budget = (
            _float(_bval("PROC_EXIT_WAIT_S"))
            + 0.05
            + _float(_bval("DRAIN_WINDOW_S"))
            + _float(_bval("JOIN_TIMEOUT_S"))
        )
        self.assertLessEqual(default_budget, 0.60 + 1e-9)
        self.assertEqual(_bval("DRAIN_WINDOW_S"), 0.35)
        maxima = 0.05 + 0.05 + _float(_bval("DRAIN_MAX_S")) + 0.20
        self.assertLessEqual(maxima, 0.80 + 1e-9)
        for _attempt in range(1000):
            run = _bare_run()

            def emitter(target: object = run) -> None:
                for step in range(100):
                    if not _ofn(target, "_emit_reasoning")(step, "x", None):
                        break

            thread = threading.Thread(target=emitter)
            thread.start()
            _ = _ofn(run, "_close_and_put_done")("done", (0, "", {}))
            thread.join(5)
            kinds = _queue_kinds(run)
            self.assertEqual(kinds.count("done"), 1)
            self.assertNotIn("reasoning", kinds[kinds.index("done") :])
        late = _bare_run()
        _ = _ofn(late, "_close_and_put_done")("done", (0, "", {}))
        buffer = io.StringIO()
        with mock.patch.object(sys, "stderr", buffer):
            accepted = _ofn(late, "_emit_reasoning")(5, "поздно", None)
        self.assertIs(accepted, False)
        self.assertRegex(buffer.getvalue(), r"reasoning-late-drop cid=- step=5 len=6")

    def test_ao03_hung_select_is_interrupted_before_the_final_join(self) -> None:
        run = _bare_run()
        stub = _StubTail()
        setattr(run, "_tail", stub)
        with mock.patch.object(_bridge(), "DRAIN_WINDOW_S", 0.05):
            _ = _ofn(run, "_join_source")(time.monotonic())
        self.assertEqual(stub.events, ["interrupt"])
        self.assertFalse(stub.thread.is_alive())
        with _Fixture() as fx:
            fx.set_flag(True)
            writer = fx.writer()
            writer.think(3, 8, "нужна строка")
            heavy = "".join(
                [
                    "WITH RECURSIVE c(x) AS (SELECT ?1 UNION ALL SELECT x+1 FROM c ",
                    "WHERE x < 2000000000) SELECT count(*), 8, 0, NULL FROM c",
                ]
            )
            fx.patch("_STEPS_SQL", heavy)
            tail, _emitted, _stop, _done = _make_tail()
            worker = threading.Thread(target=_poll, args=(tail,))
            started = time.monotonic()
            worker.start()
            time.sleep(0.3)
            self.assertTrue(worker.is_alive())
            _ = _ofn(tail, "interrupt_active_query")()
            worker.join(5)
            self.assertFalse(worker.is_alive())
            self.assertLess(time.monotonic() - started, 4.0)
            self.assertEqual(_bval("_sqlite_open_connections"), 0)
            self.assertIs(_oval(tail, "failed"), False)


class ConnectionLifecycleTests(unittest.TestCase):
    """T-LIFE/C-MULT: ≤1 соединения на ход, парный close, остановка источника (AO-04)."""

    def test_ao04_connections_are_paired_and_single_per_turn(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            writer = fx.writer()
            writer.think(3, 8, "абв")
            opened: list[float] = []
            _spy_open(fx, opened)
            for turn in range(20):
                tail, _emitted, _stop, _done = _make_tail(cid=_CID)
                for _poll_no in range(3):
                    _ = _poll(tail)
                _ = _ofn(tail, "_finish")()
                self.assertEqual(_bval("_sqlite_open_connections"), 0, turn)
            self.assertEqual(_bval("_sqlite_max_open_connections"), 1)
            self.assertEqual(len(opened), 60)

    def test_ao04_flag_off_and_stop_close_the_connection(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            writer = fx.writer()
            writer.think(3, 8, "абв")
            tail, emitted, stop, _done = _make_tail()
            _ = _poll(tail)
            self.assertEqual(emitted, [(3, "абв")])
            fx.set_flag(False)
            setattr(_bridge(), "_flag_checked_at", None)
            _ = _ofn(tail, "tick")()
            self.assertIs(_oval(tail, "sqlite_active"), False)
            self.assertEqual(_bval("_sqlite_open_connections"), 0)
            stop.set()
            self.assertIsNone(_ofn(tail, "_poll_sqlite")())
            self.assertEqual(_bval("_sqlite_open_connections"), 0)


class PollEnvelopeTests(unittest.TestCase):
    """H-CPU/S-HERD: огибающая SELECT, пропуск неизменных снимков, потолок памяти (AO-05)."""

    def test_ao05_select_envelope_never_exceeds_three_plus_two_per_second(self) -> None:
        clock = _FakeClock(100.0)
        with (
            _Fixture() as fx,
            mock.patch.object(_bridge(), "time", _stepping_time(clock)),
        ):
            fx.set_flag(True)
            writer = fx.writer()
            writer.think(3, 8, "абв")
            stamps: list[float] = []
            _spy_open(fx, stamps, clock)
            tail, _emitted, _stop, _done = _make_tail()
            for _step in range(400):  # 20 с мок-времени, опрос на каждом тике drain
                _ = _ofn(tail, "_poll_sqlite")()
                clock.advance(0.05)
            self.assertGreater(len(stamps), 10)
            worst = 0.0
            for i in range(len(stamps)):
                for j in range(i, len(stamps)):
                    allowed = 3 + 2 * (stamps[j] - stamps[i])
                    worst = max(worst, (j - i + 1) - allowed)
            self.assertLessEqual(worst, 1e-6)

    def test_ao05_unchanged_snapshot_skips_parser_same_size_does_not(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            writer = fx.writer()
            calls: list[int] = []
            _spy_parser(fx, calls)
            tail, emitted, _stop, _done = _make_tail()
            writer.think(3, 8, "aaaa")
            for _round in range(3):
                _ = _poll(tail)
            self.assertEqual(len(calls), 1)
            writer.think(3, 8, "aaab")  # тот же размер, другое содержимое
            _ = _poll(tail)
            self.assertEqual(len(calls), 2)
            self.assertEqual(emitted, [(3, "aaaa")])  # непрефиксный снимок заморожен

    def test_ao05_stop_inside_sixteen_rows_stops_the_parser(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            writer = fx.writer()
            for idx in range(16):
                writer.think(idx, 8, "шаг %02d" % idx)
            calls: list[int] = []
            tail, _emitted, stop, _done = _make_tail()
            _spy_parser(fx, calls, after_first=stop)
            _ = _poll(tail)
            self.assertEqual(len(calls), 1)
            many = b"".join(_varint(i + 100 << 3) + _varint(1) for i in range(200))
            flag = threading.Event()
            flag.set()
            self.assertEqual(
                _bfn("_extract_thinking_from_step_blob")(
                    many + _step_blob("x"), True, flag
                ),
                "",
            )
            self.assertEqual(_extract(many + _step_blob("x")), "x")

    def test_ao05_row_limit_blob_limit_and_oversize_log(self) -> None:
        sql = _str(_bval("_STEPS_SQL"))
        self.assertIn("LIMIT 16", sql)
        self.assertIn("262144", sql)
        self.assertEqual(_bval("MAX_STEP_BLOB_BYTES"), 262144)
        with _Fixture() as fx:
            fx.set_flag(True)
            writer = fx.writer()
            writer.put(3, 8, b"x" * 300_000)
            writer.think(4, 8, "z" * 250_000)
            tail, emitted, _stop, _done = _make_tail()
            buffer = io.StringIO()
            with mock.patch.object(sys, "stderr", buffer):
                _ = _poll(tail)
            self.assertEqual(emitted, [(4, "z" * 250_000)])
            self.assertIn(
                "sqlite-oversize cid=82188e72 step=3 blob_len=300000", buffer.getvalue()
            )

    def test_ao05_flag_file_parsed_once_within_ttl_and_cap_two_mib(self) -> None:
        clock = _FakeClock(10.0)
        real_loads = json.loads
        loads: list[int] = []

        def counting_loads(text: str) -> object:
            loads.append(1)
            return cast(object, real_loads(text))

        with _Fixture() as fx, mock.patch.object(json, "loads", counting_loads):
            with mock.patch.object(_bridge(), "time", _fake_time(clock)):
                fx.set_flag(True)
                for _look in range(4):
                    self.assertTrue(_bfn("_is_sqlite_reasoning_enabled")())
                    clock.advance(0.3)
                self.assertEqual(len(loads), 1)
                clock.advance(1.0)
                self.assertTrue(_bfn("_is_sqlite_reasoning_enabled")())
                self.assertEqual(
                    len(loads), 1
                )  # stat не менялся: JSON не разбирается заново
                fx.set_flag(False)
                clock.advance(1.5)
                self.assertFalse(_bfn("_is_sqlite_reasoning_enabled")())
                self.assertEqual(len(loads), 2)
        run = _bare_run()
        chunk = "я" * 524_288  # 1 MiB в UTF-8
        buffer = io.StringIO()
        with mock.patch.object(sys, "stderr", buffer):
            results = [_ofn(run, "_emit_reasoning")(0, chunk, None) for _n in range(4)]
        self.assertEqual(results, [True, True, False, False])
        self.assertEqual(_queue_kinds(run), ["reasoning", "reasoning"])
        self.assertEqual(buffer.getvalue().count("reasoning-cap"), 1)
        self.assertEqual(_bval("MAX_REASONING_BYTES_PER_TURN"), 2 * 1024 * 1024)


class _StubRun:
    """Подмена Run: процесс не стартует, close ничего не делает."""

    count: list[int] = []

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        _StubRun.count.append(1)

    def close(self) -> None:
        return None


def _done_lines(call: Callable[[], object]) -> list[str]:
    buffer = io.StringIO()
    with mock.patch.object(sys, "stderr", buffer):
        _ = call()
    return [line for line in buffer.getvalue().splitlines() if " done model=" in line]


class ExitLogAndHealthTests(unittest.TestCase):
    """O-EXIT: одна строка done на каждом выходе _run_once; /health аддитивен (AO-06)."""

    def _run_once_with(
        self,
        execute_out: dict[str, object] | None,
        ctx: dict[str, object] | None = None,
        slot: str = "",
    ) -> list[str]:

        def fake_execute(_self: object, _run: object, *_a: object) -> dict[str, object]:
            return dict(execute_out or {})

        def fake_slot(_self: object, _keepalive: object) -> str:
            return slot

        handler_cls = _bval("Handler")
        with contextlib.ExitStack() as stack:
            _ = stack.enter_context(
                mock.patch.object(handler_cls, "_execute", fake_execute)
            )
            if slot:
                _ = stack.enter_context(
                    mock.patch.object(handler_cls, "_acquire_slot", fake_slot)
                )
            _ = stack.enter_context(mock.patch.object(_bridge(), "Run", _StubRun))
            _ = stack.enter_context(
                mock.patch.object(_bridge(), "_launcher", _fake_launcher_path)
            )
            with _Sock() as sock:
                handler = cast(object, _make_handler(sock))
                setattr(handler, "client_address", ("127.0.0.1", 1))

                def call() -> object:
                    return _ofn(handler, "_run_once")(
                        ctx if ctx is not None else _ctx(),
                        _text_sink,
                        _tool_sink,
                        _text_sink,
                        None,
                    )

                return _done_lines(call)

    def test_ao06_single_done_line_on_every_exit_branch(self) -> None:
        base: dict[str, object] = {
            "rc": 1,
            "text": "",
            "usage": {},
            "result": {},
            "err": "e",
            "tool_calls": [],
            "tool_events": 0,
            "conversation_id": "",
            "num_turns": None,
            "duration_s": None,
        }
        branches = {
            "done": {**base, "state": "done", "rc": 0, "text": "ok"},
            "agy_error": {**base, "state": "agy_error", "reasoning": "r"},
            "pump_error": {**base, "state": "pump_error"},
            "client_gone": {**base, "state": "client_gone"},
            "timeout": {**base, "state": "timeout", "rc": 124},
        }
        for name, out in branches.items():
            with self.subTest(branch=name), _Fixture():
                _StubRun.count.clear()
                setattr(_bridge(), "_rng", _zero)
                lines = self._run_once_with(out, _ctx(stream=False))
                self.assertEqual(len(lines), 1, lines)
                self.assertIn("state=" + name, lines[0])
                for field in (
                    "rc=",
                    "conversation=",
                    "turns=",
                    "tool_events=",
                    "out_bytes=",
                    "wall_s=",
                ):
                    self.assertIn(field, lines[0])
        with self.subTest(branch="no_slot"), _Fixture():
            lines = self._run_once_with(None, slot="queue_timeout")
            self.assertEqual(len(lines), 1, lines)
            self.assertIn("state=queue_timeout", lines[0])
        with self.subTest(branch="launcher_unavailable"), _Fixture() as fx:
            fx.patch("LAUNCHER", str(fx.tmp / "missing-launcher"))
            with _Sock() as sock:
                handler = cast(object, _make_handler(sock))
                setattr(handler, "client_address", ("127.0.0.1", 1))

                def call() -> object:
                    return _ofn(handler, "_run_once")(
                        _ctx(), _text_sink, _tool_sink, _text_sink, None
                    )

                lines = _done_lines(call)
            self.assertEqual(len(lines), 1, lines)
            self.assertIn("state=launcher_unavailable", lines[0])

    def test_ao06_health_has_four_additive_fields_and_keeps_existing_ones(self) -> None:
        with _Fixture() as fx:
            sent: list[tuple[int, dict[str, object]]] = []

            def send(code: int, payload: dict[str, object]) -> None:
                sent.append((code, payload))

            def fetch() -> dict[str, object]:
                with _Sock() as sock:
                    handler = cast(object, _make_handler(sock))
                    setattr(handler, "path", "/health")
                    setattr(handler, "_send", send)
                    _ = _ofn(handler, "do_GET")()
                return sent[-1][1]

            body = fetch()
            for key in (
                "ok",
                "transport",
                "model",
                "active",
                "max_concurrent",
                "hot_sessions",
                "tool_emulation",
                "tool_translation",
                "native_tools",
                "images",
                "uptime_s",
            ):
                self.assertIn(key, body)
            self.assertEqual(
                body["sqlite_reasoning_mode"], "off"
            )  # флага нет: fail-closed
            self.assertEqual(body["sqlite_breaker_state"], "closed")
            self.assertEqual(body["sqlite_divergence_count"], 0)
            self.assertEqual(body["sqlite_drain_deadline_count"], 0)
            fx.set_flag(True)
            setattr(_bridge(), "_flag_checked_at", None)
            self.assertEqual(fetch()["sqlite_reasoning_mode"], "shadow")
            fx.prime_canary()
            self.assertEqual(fetch()["sqlite_reasoning_mode"], "live")
            _ = _bfn("_count_divergence")()
            _ = _bfn("_count_drain_deadline")()
            for _turn in range(3):
                _ = _bfn("_breaker_report")(None, 1, True)
            opened = fetch()
            self.assertEqual(opened["sqlite_reasoning_mode"], "breaker_open")
            self.assertEqual(opened["sqlite_breaker_state"], "open")
            self.assertEqual(opened["sqlite_divergence_count"], 1)
            self.assertEqual(opened["sqlite_drain_deadline_count"], 1)
            fx.set_env("AGY_SQLITE_REASONING_ENABLED", "false")
            self.assertEqual(fetch()["sqlite_reasoning_mode"], "off")


def _zero() -> float:
    return 0.0


def _text_sink(_value: object) -> bool:
    return True


def _tool_sink(_event: object) -> bool:
    return True


class DatabasePathTests(unittest.TestCase):
    """THREAT-003: путь к БД строится только из валидного cid внутри CONV_DIR (AO-07)."""

    def test_ao07_invalid_cid_never_reaches_connect(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            outside = fx.tmp / "outside.db"
            _ = outside.write_bytes(b"")
            (fx.conv / (_CID_B + ".db")).symlink_to(outside)
            bad = [
                "",
                "../x",
                "a/b",
                "..",
                "zz-not-hex-zz",
                "abc",
                _CID + "/../x",
                "g" * 36,
                "-" * 8 + "/",
                "a" * 65,
            ]
            for cid in bad:
                with self.subTest(cid=cid):
                    self.assertIsNone(_bfn("_db_path_for")(cid))
            self.assertIsNone(_bfn("_db_path_for")(_CID_B))  # симлинк вне CONV_DIR
            good = _bfn("_db_path_for")(_CID)
            self.assertEqual(good, fx.conv / (_CID + ".db"))
            real_connect = cast(Callable[..., sqlite3.Connection], sqlite3.connect)
            calls: list[str] = []

            def counting_connect(database: str, **kwargs: object) -> sqlite3.Connection:
                calls.append(database)
                return real_connect(database, **kwargs)

            with mock.patch.object(sqlite3, "connect", counting_connect):
                for cid in ("../x", "a/b", "zz-not-hex-zz"):
                    tail, emitted, _stop, _done = _make_tail(cid=cid)
                    self.assertIsNone(_poll(tail))
                    self.assertEqual(emitted, [])
                    self.assertIs(_oval(tail, "sqlite_active"), False)
            self.assertEqual(calls, [])


class ReadOnlyAndAnchorTests(unittest.TestCase):
    """THREAT-003/RISK: только чтение, владение cid, якорь resume (AO-08)."""

    def test_ao08_every_connect_is_read_only_uri(self) -> None:
        source = Path(_BRIDGE_PY).read_text(encoding="utf-8")
        self.assertNotIn("BEGIN", source)
        self.assertNotIn("immutable", source)
        self.assertNotIn("mode=rw", source)
        with _Fixture() as fx:
            fx.set_flag(True)
            writer = fx.writer()
            writer.think(3, 8, "абв")
            real_connect = cast(Callable[..., sqlite3.Connection], sqlite3.connect)
            seen: list[tuple[str, object]] = []

            def recording_connect(
                database: str, **kwargs: object
            ) -> sqlite3.Connection:
                seen.append((database, kwargs.get("uri")))
                return real_connect(database, **kwargs)

            with mock.patch.object(sqlite3, "connect", recording_connect):
                tail, emitted, _stop, _done = _make_tail()
                _ = _poll(tail)
                _ = _bfn("_prespawn_plan")(_CID, True)
                conn = cast(sqlite3.Connection, _bfn("_sqlite_open_ro")(fx.db_path()))
                try:
                    self.assertEqual(conn.execute("PRAGMA query_only").fetchone()[0], 1)
                    self.assertEqual(
                        conn.execute("PRAGMA busy_timeout").fetchone()[0], 50
                    )
                    with self.assertRaises(sqlite3.OperationalError):
                        _ = conn.execute("DELETE FROM steps")
                finally:
                    conn.close()
            self.assertEqual(emitted, [(3, "абв")])
            self.assertGreaterEqual(len(seen), 3)
            for database, uri in seen:
                self.assertTrue(
                    database.startswith("file:") and database.endswith("?mode=ro"),
                    database,
                )
                self.assertIs(uri, True)
            self.assertEqual(
                writer.conn.execute("SELECT count(*) FROM steps").fetchone()[0], 1
            )

    def test_ao08_second_request_with_busy_cid_gets_fresh_conversation(self) -> None:
        self.assertTrue(_bfn("_cid_acquire")(_CID, "turn-a"))
        self.assertTrue(_bfn("_cid_acquire")(_CID, "turn-a"))
        self.assertFalse(_bfn("_cid_acquire")(_CID, "turn-b"))
        _ = _bfn("_cid_release")(_CID, "turn-b")  # чужой release владение не снимает
        self.assertFalse(_bfn("_cid_acquire")(_CID, "turn-b"))
        _ = _bfn("_cid_release")(_CID, "turn-a")
        self.assertTrue(_bfn("_cid_acquire")(_CID, "turn-b"))
        _ = _bfn("_cid_release")(_CID, "turn-b")
        with _Fixture() as fx:
            key = ("m", "", "low")
            _ = _bfn("_session_commit")(key, _CID)
            self.assertTrue(_bfn("_cid_acquire")(_CID, "other"))
            self.assertEqual(_bfn("_session_claim")(key, "t2"), "")
            _ = _bfn("_cid_release")(_CID, "other")
            self.assertEqual(_bfn("_session_claim")(key, "t2"), _CID)
            self.assertEqual(
                cast("dict[str, str]", _bval("_active_cid_owners"))[_CID], "t2"
            )
            _ = _bfn("_cid_release")(_CID, "t2")
            cast("set[str]", _bval("_in_flight_cids")).discard(_CID)
            _ = fx.write_scenario([], spawns=[_slow(_CID, 1.2), _quick(_CID_B)])
            http_bridge = _HttpBridge()
            holders: list[tuple[int, dict[str, object]]] = []
            explicit: dict[str, object] = {"extra_body": {"conversation_id": _CID_C}}
            try:

                def first() -> None:
                    body = _plain_body("долгий")
                    body.update(explicit)
                    holders.append(http_bridge.post(body))

                worker = threading.Thread(target=first)
                worker.start()
                deadline = time.monotonic() + 10
                while len(fx.spawns()) < 1 and time.monotonic() < deadline:
                    time.sleep(0.02)
                body2 = _plain_body("одновременный")
                body2.update(explicit)
                code2, _payload2 = http_bridge.post(body2)
                worker.join(30)
            finally:
                http_bridge.close()
            spawns = fx.spawns()
            self.assertEqual(code2, 200)
            self.assertEqual(len(spawns), 2)
            self.assertEqual(spawns[0][spawns[0].index("--conversation") + 1], _CID_C)
            self.assertNotIn("--conversation", spawns[1])
            self.assertEqual(cast("dict[str, str]", _bval("_active_cid_owners")), {})

    def test_ao08_unanchored_resume_turns_sqlite_off_for_the_whole_turn(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            fx.prime_canary()
            for idx in range(2):
                fx.append_record(
                    {
                        "type": "PLANNER_RESPONSE",
                        "step_index": idx,
                        "thinking": "старый",
                    }
                )
            plan = _bfn("_prespawn_plan")(_CID, True)  # базы нет: якоря SQLite нет
            _ = _bfn("_decide_turn_mode")(plan)
            self.assertIs(_oval(plan, "anchored"), False)
            self.assertEqual(_oval(plan, "mode"), "OFF")
            self.assertEqual(_oval(plan, "reason"), "resume_unanchored")
            self.assertEqual(_oval(plan, "base_idx"), 2)
            opened: list[float] = []
            _spy_open(fx, opened)
            buffer = io.StringIO()
            with mock.patch.object(sys, "stderr", buffer):
                tail, emitted, _stop, _done = _make_tail(plan=plan, resumed=True)
            fx.writer().think(2, 8, "новый шаг")
            self.assertIsNone(_poll(tail))
            self.assertEqual(opened, [])
            fx.append_record(
                {"type": "PLANNER_RESPONSE", "step_index": 2, "thinking": "новый шаг"}
            )
            _ = _ofn(tail, "_read_transcript")()
            self.assertEqual(emitted, [(2, "новый шаг")])
            self.assertIn(
                "sqlite-off cid=82188e72 reason=resume_unanchored", buffer.getvalue()
            )

    def test_ao08_stale_generating_row_of_a_failed_turn_is_never_redelivered(
        self,
    ) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            fx.prime_canary()
            writer = fx.writer()
            writer.think(0, 3, "прошлый ход 0")
            writer.think(1, 3, "прошлый ход 1")
            writer.think(2, 8, "зависшая строка упавшего хода")
            plan = _bfn("_prespawn_plan")(_CID, True)
            _ = _bfn("_decide_turn_mode")(plan)
            self.assertIs(_oval(plan, "anchored"), True)
            self.assertEqual(_oval(plan, "base_idx"), 3)
            self.assertEqual(_oval(plan, "mode"), "LIVE")
            tail, emitted, _stop, _done = _make_tail(plan=plan, resumed=True)
            _ = _poll(tail)
            self.assertEqual(emitted, [])
            writer.think(3, 8, "шаг нового хода")
            _ = _poll(tail)
            writer.think(3, 3, "шаг нового хода, финал")
            _ = _poll(tail)
            self.assertEqual(_text_of(emitted), "шаг нового хода, финал")
            self.assertEqual({idx for idx, _t in emitted}, {3})


class KillSwitchTests2(unittest.TestCase):
    """AD-006: выключение флага посреди хода гасит SELECT за ≤1.30 с (AO-09)."""

    def _flip_and_wait(
        self, fx: _Fixture, flip: Callable[[], None], poll_s: float
    ) -> float:
        clock = _FakeClock(1000.0)
        with (
            mock.patch.object(_bridge(), "time", _stepping_time(clock)),
            mock.patch.object(_bridge(), "SQLITE_POLL_S", poll_s),
        ):
            fx.set_flag(True)
            writer = fx.writer()
            writer.think(3, 8, "абв")
            stamps: list[float] = []
            _spy_open(fx, stamps, clock)
            tail, _emitted, _stop, _done = _make_tail()
            for _tick in range(60):
                _ = _ofn(tail, "tick")()
                clock.advance(0.05)
            self.assertGreaterEqual(len(stamps), 2)
            flipped_at = clock()
            flip()
            while _oval(tail, "sqlite_active") is True and clock() - flipped_at < 5.0:
                _ = _ofn(tail, "tick")()
                clock.advance(0.05)
            off_after = clock() - flipped_at
            polls_before = len(stamps)
            for _tick in range(60):
                _ = _ofn(tail, "tick")()
                clock.advance(0.05)
            self.assertEqual(len(stamps), polls_before)
            self.assertEqual(_bval("_sqlite_open_connections"), 0)
            return off_after

    def test_ao09_flag_off_mid_turn_stops_selects_within_1_30_seconds(self) -> None:
        for poll_s in (0.5, 2.0):
            for kind in ("false", "delete", "broken"):
                with self.subTest(poll_s=poll_s, kind=kind), _Fixture() as fx:

                    def flip(how: str = kind, fixture: _Fixture = fx) -> None:
                        if how == "false":
                            fixture.set_flag(False)
                        elif how == "delete":
                            fixture.set_flag(None)
                        else:
                            _ = fixture.config.write_text(
                                "{not json" + " " * 5, encoding="utf-8"
                            )

                    off_after = self._flip_and_wait(fx, flip, poll_s)
                    self.assertLessEqual(off_after, 1.30)

    def test_ao09_env_switch_never_opens_a_connection(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            fx.set_env("AGY_SQLITE_REASONING_ENABLED", "0")
            fx.writer().think(3, 8, "абв")
            real_connect = cast(Callable[..., sqlite3.Connection], sqlite3.connect)
            calls: list[str] = []

            def counting_connect(database: str, **kwargs: object) -> sqlite3.Connection:
                calls.append(database)
                return real_connect(database, **kwargs)

            with mock.patch.object(sqlite3, "connect", counting_connect):
                plan = _bfn("_prespawn_plan")(_CID, True)
                _ = _bfn("_decide_turn_mode")(plan)
                tail, emitted, _stop, _done = _make_tail(plan=plan)
                _ = _poll(tail)
            self.assertEqual(_oval(plan, "mode"), "OFF")
            self.assertEqual(_oval(plan, "reason"), "env")
            self.assertEqual(emitted, [])
            self.assertEqual(calls, [])


def _plan_for(cid: str = "") -> object:
    plan = _bfn("_prespawn_plan")(cid, False)
    _ = _bfn("_decide_turn_mode")(plan)
    return plan


class CompatCanaryTests(unittest.TestCase):
    """F-005: семантический canary и фиксированный режим хода (AO-10)."""

    def _canary_turn(
        self, fx: _Fixture, cid: str, text: str
    ) -> tuple[object, list[tuple[int, str]]]:
        plan = _plan_for()
        writer = fx.writer(cid)
        tail, emitted, _stop, _done = _make_tail(cid=cid, plan=plan)
        writer.think(3, 8, text[:3])
        _ = _poll(tail)
        writer.think(3, 3, text)
        _ = _poll(tail)
        fx.append_record(
            {"type": "PLANNER_RESPONSE", "step_index": 3, "thinking": text}, cid
        )
        _ = _ofn(tail, "_read_transcript")()
        return tail, emitted

    def test_ao10_unknown_binary_is_shadow_and_final_goes_out_whole(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            final = "полное мышление шага для проверки canary"
            tail, emitted = self._canary_turn(fx, _CID, final)
            self.assertEqual(_oval(tail, "mode"), "SHADOW")
            self.assertEqual(
                emitted, [(3, final)]
            )  # 100 % final_thinking, 0 SQLite-эмитов
            state = cast("dict[int, object]", _oval(tail, "seen"))[3]
            self.assertEqual(_oval(state, "delivered_len"), len(final))
            self.assertEqual(_oval(state, "observed_sha"), _sha(final))
            self.assertEqual(
                _bval("_compat_state"), "LIVE"
            )  # canary подтверждён для будущих ходов

    def test_ao10_turn_mode_is_fixed_at_start_despite_concurrent_promotion(
        self,
    ) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            writer_a = fx.writer(_CID)
            plan_a = _plan_for()
            tail_a, emitted_a, _s, _d = _make_tail(cid=_CID, plan=plan_a)
            self.assertEqual(_oval(tail_a, "mode"), "SHADOW")
            writer_a.think(3, 8, "первый ход, начало")
            _ = _poll(tail_a)
            _tail_b, _emitted_b = self._canary_turn(
                fx, _CID_B, "ход B подтверждает canary"
            )
            self.assertEqual(_bval("_compat_state"), "LIVE")
            writer_a.think(3, 8, "первый ход, начало и продолжение")
            _ = _poll(tail_a)
            self.assertEqual(emitted_a, [])  # A остаётся SHADOW после промоута ходом B
            plan_c = _plan_for()
            tail_c, emitted_c, _s2, _d2 = _make_tail(cid=_CID_C, plan=plan_c)
            self.assertEqual(_oval(tail_c, "mode"), "LIVE")
            fx.writer(_CID_C).think(3, 8, "ход C идёт вживую")
            _ = _poll(tail_c)
            self.assertEqual(emitted_c, [(3, "ход C идёт вживую")])

    def test_ao10_mismatch_in_shadow_and_divergence_in_live_demote_compat(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            plan = _plan_for()
            writer = fx.writer()
            tail, emitted, _s, _d = _make_tail(plan=plan)
            writer.think(3, 3, "снимок SQLite")
            _ = _poll(tail)
            fx.append_record(
                {
                    "type": "PLANNER_RESPONSE",
                    "step_index": 3,
                    "thinking": "иное мышление",
                }
            )
            _ = _ofn(tail, "_read_transcript")()
            self.assertEqual(emitted, [(3, "иное мышление")])  # клиенту ушёл транскрипт
            self.assertEqual(_bval("_compat_state"), "SHADOW")
            self.assertEqual(_bval("_sqlite_divergence_count"), 1)
            self.assertIs(_oval(tail, "failed"), True)
        with _Fixture() as fx:
            fx.set_flag(True)
            fx.prime_canary()
            self.assertEqual(_bval("_compat_state"), "LIVE")
            writer = fx.writer()
            tail, emitted, _s, _d = _make_tail(plan=_plan_for())
            self.assertEqual(_oval(tail, "mode"), "LIVE")
            writer.think(3, 8, "abc")
            _ = _poll(tail)
            writer.think(3, 8, "abX")
            _ = _poll(tail)
            self.assertEqual(emitted, [(3, "abc")])
            self.assertEqual(_bval("_compat_state"), "SHADOW")
            self.assertIs(_oval(tail, "failed"), True)

    def test_ao10_new_binary_identity_and_live_loss_return_to_shadow(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            fx.prime_canary()
            self.assertEqual(
                _bfn("_compat_turn_state")(_bfn("_agy_binary_identity")()), "LIVE"
            )
            _ = fx.agy_bin.write_text(
                "agy-fixture-binary-after-autoupdate", encoding="utf-8"
            )
            self.assertEqual(
                _bfn("_compat_turn_state")(_bfn("_agy_binary_identity")()), "SHADOW"
            )
            fx.prime_canary()
            writer = fx.writer()
            tail, emitted, _s, _d = _make_tail(plan=_plan_for())
            writer.put(3, 3, _ld(20, _ld(1, "заголовок без мышления".encode("utf-8"))))
            _ = _poll(tail)
            buffer = io.StringIO()
            with mock.patch.object(sys, "stderr", buffer):
                fx.append_record(
                    {
                        "type": "PLANNER_RESPONSE",
                        "step_index": 3,
                        "thinking": "есть в транскрипте",
                    }
                )
                _ = _ofn(tail, "_read_transcript")()
            self.assertIn("sqlite-live-loss cid=82188e72 step=3", buffer.getvalue())
            self.assertEqual(_bval("_compat_state"), "SHADOW")
            self.assertEqual(emitted, [(3, "есть в транскрипте")])

    def test_ao10_watermark_moves_past_sixteen_finished_steps(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            fx.prime_canary()
            writer = fx.writer()
            for idx in range(20):
                writer.think(idx, 3, "шаг %02d" % idx)
            tail, emitted, _s, _d = _make_tail(plan=_plan_for())
            _ = _poll(tail)
            self.assertEqual(_oval(tail, "poll_watermark"), 16)
            _ = _poll(tail)
            self.assertEqual(_oval(tail, "poll_watermark"), 20)
            self.assertEqual([idx for idx, _t in emitted], list(range(20)))


class ExecuteDrainRetryTests(unittest.TestCase):
    """AD-002/AD-003: result ERROR не обрывает дренирование очереди (AO-11)."""

    def _events(self) -> list[object]:
        return [
            ("init", {"conversation_id": "c1", "tools": 0, "permission_mode": ""}),
            (
                "result",
                {"status": "ERROR", "error": "Individual quota reached", "usage": {}},
            ),
            ("reasoning", "мысль-1 "),
            ("reasoning", "мысль-2"),
            ("done", (1, "", {})),
        ]

    def test_ao11_reasoning_after_result_error_reaches_out_before_retry_decision(
        self,
    ) -> None:
        clock = _FakeClock()
        controller = AdaptiveTimeoutController(
            idle_timeout_s=1000.0,
            safety_cap_s=1800.0,
            finish_reserve_s=0.0,
            watchdog_enabled=False,
            clock=clock,
        )
        run = _fake_run(clock, controller, self._events(), empty_ticks=0)
        out = _dict(cast(object, _execute_with_clock(clock, run)))
        self.assertEqual(out["state"], "agy_error")
        self.assertEqual(out["reasoning"], "мысль-1 мысль-2")
        self.assertEqual(out["err"], "Individual quota reached")
        with _Fixture():
            for stream, expected_runs in ((True, 1), (False, 2)):
                with self.subTest(stream=stream):
                    _StubRun.count.clear()
                    reasoning_out: dict[str, object] = dict(out)
                    reasoning_out["rc"] = 1

                    def fake_execute(
                        _self: object, _run: object, *_a: object
                    ) -> dict[str, object]:
                        return dict(reasoning_out)

                    with (
                        mock.patch.object(_bval("Handler"), "_execute", fake_execute),
                        mock.patch.object(_bridge(), "Run", _StubRun),
                        mock.patch.object(_bridge(), "_launcher", _fake_launcher_path),
                        mock.patch.object(_bridge(), "_rng", _zero),
                    ):
                        with _Sock() as sock:
                            handler = cast(object, _make_handler(sock))
                            result = _dict(
                                _ofn(handler, "_run_once")(
                                    _ctx(stream=stream),
                                    _text_sink,
                                    _tool_sink,
                                    _text_sink,
                                    None,
                                )
                            )
                    self.assertEqual(len(_StubRun.count), expected_runs)
                    self.assertEqual(result["state"], "agy_error")
                    err = _dict(_ofn(_bval("Handler"), "_error_body")(result))
                    self.assertEqual(err["type"], "agy_error")


def _fake_launcher_path() -> str:
    return "/bin/true"


def _transcript_final(fx: _Fixture, idx: int, text: str) -> None:
    fx.append_record({"type": "PLANNER_RESPONSE", "step_index": idx, "thinking": text})


class DedupInvariantTests(unittest.TestCase):
    """AD-001: префикс по sha256, замороженные шаги, память seen (AO-12)."""

    def test_ao12_snapshot_divergence_freezes_step_and_closes_polling(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            writer = fx.writer()
            tail, emitted, _s, _d = _make_tail()
            writer.think(3, 8, "abc")
            _ = _poll(tail)
            buffer = io.StringIO()
            with mock.patch.object(sys, "stderr", buffer):
                writer.think(3, 8, "abXde")
                _ = _poll(tail)
                _transcript_final(fx, 3, "abXde")
                _ = _ofn(tail, "_read_transcript")()
                _transcript_final(fx, 4, "шаг после divergence")
                _ = _ofn(tail, "_read_transcript")()
            self.assertEqual(
                _text_of(emitted, 3), "abc"
            )  # ни повторов, ни склейки 'abcde'
            self.assertEqual(_text_of(emitted, 4), "шаг после divergence")
            self.assertIs(_oval(tail, "sqlite_active"), False)
            self.assertIn(
                "sqlite_snapshot_divergence cid=82188e72 step=3", buffer.getvalue()
            )
            self.assertEqual(_bval("_sqlite_divergence_count"), 1)
            self.assertIs(_oval(tail, "failed"), True)
            _ = _bfn("_breaker_report")(None, 1, True)
            self.assertEqual(_bval("_breaker_failures"), 1)

    def test_ao12_transcript_divergence_never_glues_the_tail(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            writer = fx.writer()
            tail, emitted, _s, _d = _make_tail()
            writer.think(3, 8, "abc")
            _ = _poll(tail)
            buffer = io.StringIO()
            with mock.patch.object(sys, "stderr", buffer):
                _transcript_final(fx, 3, "abXde")
                _ = _ofn(tail, "_read_transcript")()
            self.assertEqual(_text_of(emitted), "abc")
            self.assertIn(
                "sqlite_transcript_divergence cid=82188e72 step=3", buffer.getvalue()
            )
            self.assertEqual(_bval("_sqlite_divergence_count"), 1)

    def test_ao12_same_size_change_is_divergence_shorter_snapshot_is_ignored(
        self,
    ) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            writer = fx.writer()
            tail, emitted, _s, _d = _make_tail()
            writer.think(3, 8, "abcdef")
            _ = _poll(tail)
            writer.think(5, 8, "xyz")
            _ = _poll(tail)
            writer.think(5, 8, "xy")  # укороченный снимок с тем же префиксом
            _ = _poll(tail)
            self.assertEqual(_text_of(emitted, 5), "xyz")
            writer.think(3, 8, "abcdeX")  # тот же размер, другой текст
            _ = _poll(tail)
            self.assertEqual(_text_of(emitted, 3), "abcdef")
            self.assertEqual(_bval("_sqlite_divergence_count"), 1)

    def test_ao12_matching_prefix_final_adds_only_the_tail(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            writer = fx.writer()
            tail, emitted, _s, _d = _make_tail()
            writer.think(3, 8, "начало мышления")
            _ = _poll(tail)
            _transcript_final(fx, 3, "начало мышления и его финал")
            _ = _ofn(tail, "_read_transcript")()
            self.assertEqual(emitted, [(3, "начало мышления"), (3, " и его финал")])
            self.assertEqual(_text_of(emitted), "начало мышления и его финал")

    def test_seen_cap_evicts_oldest_when_no_finalized_below_watermark(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            tail, _emitted, _s, _d = _make_tail()
            seen = cast("dict[int, object]", _oval(tail, "seen"))
            buffer = io.StringIO()
            with mock.patch.object(sys, "stderr", buffer):
                for idx in range(200):  # ни одного финализированного ниже watermark
                    _ = _ofn(tail, "_state")(idx)
                    self.assertLessEqual(len(seen), 128)
            self.assertEqual(len(seen), 128)
            self.assertEqual(min(seen), 72)  # вытеснены самые старые ключи
            self.assertEqual(max(seen), 199)
            self.assertIs(_oval(tail, "sqlite_active"), False)
            self.assertEqual(buffer.getvalue().count("reason=seen_cap"), 1)

    def test_ao12_seen_is_bounded_and_split_utf8_is_emitted_whole(self) -> None:
        with _Fixture() as fx:
            tail, _emitted, _s, _d = _make_tail(mode="OFF")
            for idx in range(300):
                _transcript_final(fx, idx, "шаг %d" % idx)
            _ = _ofn(tail, "_read_transcript")()
            self.assertLessEqual(
                len(cast("dict[int, object]", _oval(tail, "seen"))), 128
            )
        with _Fixture() as fx:
            fx.set_flag(True)
            writer = fx.writer()
            tail, emitted, _s, _d = _make_tail()
            text = "Размышляю о задаче"
            raw = text.encode("utf-8")
            writer.put(3, 8, _ld(20, _ld(3, raw[:-1])))  # снимок разрезал символ
            _ = _poll(tail)
            self.assertEqual(emitted, [(3, text[:-1])])
            writer.put(3, 8, _ld(20, _ld(3, raw)))
            _ = _poll(tail)
            self.assertEqual(_text_of(emitted), text)
            self.assertNotIn("\ufffd", _text_of(emitted))


_L2_MARKER = "СЕКРЕТ-L2-МЫШЛЕНИЕ"
_L2_SIZES = (523, 810, 1088, 1419, 2156)  # ряд размеров снимков из замера F-30


def _json_lines(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(_dict(cast(object, json.loads(line))))
    return rows


def _rss_bytes() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024


def _stream_text(size: int) -> str:
    body = "".join(chr(0x410 + (i % 32)) if i % 5 else " " for i in range(size))
    return (_L2_MARKER + body)[:size]


def _l2_events(times: tuple[float, ...], tail: float = 0.4) -> list[dict[str, object]]:
    """Один ход с растущим мышлением шага 3 (status=8 -> 3) и финалом в транскрипте."""
    events: list[dict[str, object]] = [_init_ev(0.05, "{cid}")]
    texts = [_stream_text(size) for size in _L2_SIZES]
    for at, text in zip(times, texts):
        events.append(_db_ev(at, 3, 8, text))
    end = times[-1] + tail
    events.append(_db_ev(end, 3, 3, texts[-1]))
    events.append(_text_ev(end + 0.05))
    events.append(_result_ev(end + 0.1, "{cid}"))
    events.append(_tr_ev(end + 0.15, 3, texts[-1]))
    events.append(_exit_ev(end + 0.17))
    return events


class L2HarnessTests(unittest.TestCase):
    """L2-харнесс VER-010: фейковый agy-писатель, 8 параллельных ходов, ресурсы и сроки."""

    def _warmup(self, fx: _Fixture) -> None:
        """Прогревочный ход: canary подтверждает совместимость agy (SHADOW -> LIVE)."""
        text = _stream_text(300)
        events = [
            _init_ev(0.05, "{cid}"),
            _db_ev(0.2, 3, 8, text[:100]),
            _db_ev(0.4, 3, 3, text),
            _tr_ev(0.5, 3, text),
            _text_ev(0.55),
            _result_ev(0.6, "{cid}"),
            _exit_ev(0.62),
        ]
        _ = fx.write_scenario(events, cid="{cid}")
        turn = _run_turn()
        self.assertEqual(turn.out["state"], "done")
        self.assertEqual(turn.reasoning(), text)  # SHADOW: финал транскрипта целиком
        self.assertEqual(_bval("_compat_state"), "LIVE")

    def _phase_parallel(self, fx: _Fixture) -> None:
        times = (0.4, 1.3, 2.1, 3.2, 4.0)
        _ = fx.write_scenario(_l2_events(times), cid="{cid}")
        cpu0, wall0 = time.process_time(), time.monotonic()
        turns = _run_many(8, workers=8)
        cpu = time.process_time() - cpu0
        wall = time.monotonic() - wall0
        self.assertEqual(len(turns), 8)
        # CPU: ≤ 0.01 ядра на ход на минимальном SQLITE_POLL_S=0.5 при 8 параллельных ходах
        self.assertLessEqual(cpu / (wall * 8), 0.01, "cpu=%.3f wall=%.3f" % (cpu, wall))
        commits = _json_lines(fx.tmp / "commits.log")
        for turn in turns:
            cid = _str(turn.out["conversation_id"])
            self.assertEqual(turn.out["state"], "done", cid)
            self.assertEqual(
                turn.reasoning(), _stream_text(_L2_SIZES[-1]), cid
            )  # AC-004
            growing = sorted(
                (
                    _float(c["t"])
                    for c in commits
                    if c["cid"] == cid and c["status"] == 8
                )
            )
            final_commit = min(
                _float(c["t"]) for c in commits if c["cid"] == cid and c["status"] == 3
            )
            self.assertEqual(len(growing), len(_L2_SIZES))
            self.assertGreaterEqual(
                len([t for t, _x in turn.chunks if t < final_commit]), 2
            )  # TC-20
            for commit_at, (chunk_at, _text) in zip(growing, turn.chunks):  # TC-22
                self.assertGreaterEqual(chunk_at, commit_at - 0.01)
                self.assertLessEqual(
                    chunk_at - commit_at, _float(_bval("SQLITE_POLL_S")) + 0.5
                )

    def _phase_late_records(self, fx: _Fixture) -> None:
        thinking = "мышление последнего шага, записанное после выхода"
        late = [
            _init_ev(0.05, "{cid}"),
            _text_ev(0.1),
            _result_ev(0.15, "{cid}"),
            _late_ev(0.16, 0.09, 3, thinking),
            _exit_ev(0.17),
        ]
        _ = fx.write_scenario(late, cid="{cid}")
        stream_hits = sum(
            1 for t in _run_many(100, workers=8) if t.reasoning() == thinking
        )
        self.assertEqual(stream_hits, 100)  # TC-60: 100/100
        json_hits = 0
        for turn in _run_many(100, workers=8, stream=False):
            if turn.out.get("reasoning") == thinking:
                json_hits += 1
        self.assertEqual(json_hits, 100)  # TC-61: 100/100

    def _phase_eof_to_stop(self, fx: _Fixture) -> None:
        _ = fx.write_scenario(
            [
                _init_ev(0.05, "{cid}"),
                _text_ev(0.1),
                _result_ev(0.15, "{cid}"),
                _exit_ev(0.16),
            ],
            cid="{cid}",
        )
        configs: list[tuple[float, dict[str, float]]] = [
            (0.65, {}),
            (0.85, {"DRAIN_WINDOW_S": 0.5, "DRAIN_MIN_S": 0.25, "JOIN_TIMEOUT_S": 0.2}),
        ]
        for limit, patches in configs:
            with contextlib.ExitStack() as stack:
                for name, value in patches.items():
                    _ = stack.enter_context(mock.patch.object(_bridge(), name, value))
                gaps: list[float] = []
                for _round in range(3):
                    turn = _run_turn()
                    gaps.append(turn.ended - _exit_time(fx))
            self.assertLessEqual(min(gaps), limit, gaps)
            self.assertLessEqual(max(gaps), 1.0, gaps)

    def _phase_kill_switch(self, fx: _Fixture, poll_s: float) -> None:
        times = (0.4, 1.0, 1.6, 2.2, 2.8)
        _ = fx.write_scenario(_l2_events(times, tail=1.6), cid="{cid}")
        fx.set_flag(True)
        stamps: list[float] = []
        _spy_open(fx, stamps)
        flipped: list[float] = []

        def flip() -> None:
            flipped.append(time.monotonic())
            fx.set_flag(False)

        timer = threading.Timer(1.3, flip)
        with mock.patch.object(_bridge(), "SQLITE_POLL_S", poll_s):
            timer.start()
            turn = _run_turn()
            timer.join()
        self.assertEqual(turn.out["state"], "done")
        self.assertEqual(len(flipped), 1)
        late = [at for at in stamps if at > flipped[0] + 2.0]
        self.assertEqual(late, [], "SELECT после kill-switch: poll_s=%s" % poll_s)
        self.assertEqual(_bval("_sqlite_open_connections"), 0)
        self.assertEqual(turn.reasoning(), _stream_text(_L2_SIZES[-1]))
        fx.set_flag(True)
        setattr(_bridge(), "_flag_checked_at", None)

    def _phase_resumed(self, fx: _Fixture) -> None:
        cid = _CID
        writer = fx.writer(cid)
        for idx in range(4):
            writer.think(idx, 3, "прошлый ход %d %s" % (idx, _L2_MARKER))
            fx.append_record(
                {
                    "type": "PLANNER_RESPONSE",
                    "step_index": idx,
                    "thinking": "прошлый ход %d %s" % (idx, _L2_MARKER),
                },
                cid,
            )
        events: list[dict[str, object]] = [_init_ev(0.05, cid)]
        texts = [_stream_text(size) for size in _L2_SIZES[:3]]
        for k, text in enumerate(texts):
            events.append(_db_ev(0.4 + k * 0.8, 4, 8, text))
        events.append(_db_ev(2.4, 4, 3, texts[-1]))
        events.append(_text_ev(2.5))
        events.append(_result_ev(2.55, cid))
        events.append(_tr_ev(2.6, 4, texts[-1]))
        events.append(_exit_ev(2.62))
        paths = fx.write_scenario(events, cid=cid)
        buffer = io.StringIO()
        with mock.patch.object(sys, "stderr", buffer):
            turn = _run_turn(
                _ctx(
                    conversation_id=cid,
                    tools_count=1,
                    hot_resumed=True,
                    sess_key=("m", "", "low"),
                )
            )
        self.assertEqual(turn.out["state"], "done")
        self.assertEqual(
            turn.reasoning(), texts[-1]
        )  # 0 переотданных шагов прошлых ходов
        self.assertNotIn("прошлый ход", turn.reasoning())
        self.assertFalse(
            Path(paths["errors_log"]).exists()
        )  # 0 SQLITE_BUSY/CORRUPT у писателя
        self.assertNotIn("divergence", buffer.getvalue())

    def _phase_stress(self, fx: _Fixture) -> None:
        """Стресс-профиль: 16 шагов по ~256 KiB в одной выборке (LIMIT 16, BLOB <= 256 KiB)."""
        writer = fx.writer(_CID_C)
        big = "".join(chr(0x61 + (i % 26)) for i in range(250_000))
        for idx in range(16):
            writer.think(idx, 3, "%02d" % idx + big[2:])
        tail, emitted, _s, _d = _make_tail(cid=_CID_C, plan=_plan_for())
        cpu0 = time.process_time()
        parsed = _poll(tail)
        cpu = time.process_time() - cpu0
        self.assertEqual(parsed, (16, 0))
        self.assertEqual(len(emitted), 16)
        self.assertEqual(sum(len(text) for _i, text in emitted), 16 * 250_000)
        self.assertLess(cpu, 2.0)
        _ = _ofn(tail, "_finish")()

    def test_tc93_l2_harness_parallel_turns_resources_and_deadlines(self) -> None:
        with _Fixture() as fx:
            fx.patch("_slots", threading.BoundedSemaphore(8))
            fx.patch("SQLITE_POLL_S", 0.5)
            fx.set_flag(True)
            log = io.StringIO()
            with mock.patch.object(sys, "stderr", log):
                self._warmup(fx)
                self._phase_stress(fx)
                self._phase_parallel(fx)
                self._phase_late_records(fx)
                self._phase_eof_to_stop(fx)
                self._phase_resumed(fx)
                for poll_s in (0.5, 2.0):
                    self._phase_kill_switch(fx, poll_s)
            text = log.getvalue()
            self.assertEqual(text.count("sqlite_snapshot_divergence"), 0)
            self.assertEqual(text.count("sqlite_transcript_divergence"), 0)
            self.assertNotIn(_L2_MARKER, text)
            drains = cast(
                "list[str]",
                re.findall(r"drain cid=\S+ ms=\d+ emitted=\d+ outcome=(\w+)", text),
            )
            self.assertTrue(drains)
            self.assertTrue(all(o in ("complete", "window_complete") for o in drains))
            self.assertLessEqual(_rss_bytes(), 112 * 1024 * 1024)
            health: list[dict[str, object]] = []

            def send(_code: int, payload: dict[str, object]) -> None:
                health.append(payload)

            with _Sock() as sock:
                handler = cast(object, _make_handler(sock))
                setattr(handler, "path", "/health")
                setattr(handler, "_send", send)
                _ = _ofn(handler, "do_GET")()
            for key in (
                "sqlite_reasoning_mode",
                "sqlite_breaker_state",
                "sqlite_divergence_count",
                "sqlite_drain_deadline_count",
            ):
                self.assertIn(key, health[0])
            self.assertEqual(health[0]["sqlite_divergence_count"], 0)


if __name__ == "__main__":
    unittest.main()
