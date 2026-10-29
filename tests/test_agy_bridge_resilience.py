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
import base64
import contextlib
import dataclasses
import gc
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
import tracemalloc
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

    def test_read_only_fallback_retries_connect_and_query_only_errors(self) -> None:
        for stage in ("connect", "query_only"):
            with self.subTest(stage=stage), _Fixture() as fx:
                writer = fx.writer(wal=False)
                writer.think(3, 3, "шаг")
                writer.close()
                fx.writers.clear()
                failed_conn = mock.Mock(spec=sqlite3.Connection)
                error = sqlite3.OperationalError("unable to open database file")
                failed_conn.execute.side_effect = error
                first = error if stage == "connect" else failed_conn
                with mock.patch.object(
                    sqlite3,
                    "connect",
                    side_effect=[first, mock.DEFAULT],
                    wraps=sqlite3.connect,
                ) as connect:
                    conn = cast(
                        sqlite3.Connection, _bfn("_sqlite_open_ro")(fx.db_path())
                    )
                    try:
                        self.assertEqual(
                            conn.execute("PRAGMA query_only").fetchone()[0], 1
                        )
                        self.assertEqual(_bval("_sqlite_open_connections"), 1)
                    finally:
                        _ = _bfn("_sqlite_close")(conn)
                uri = _bfn("_sqlite_ro_uri")(fx.db_path())
                self.assertEqual(
                    [call.args[0] for call in connect.call_args_list],
                    [uri, uri + "&immutable=1"],
                )
                if stage == "query_only":
                    failed_conn.close.assert_called_once_with()
                self.assertEqual(_bval("_sqlite_open_connections"), 0)

    def test_read_only_fallback_is_blocked_by_either_sidecar(self) -> None:
        for suffix in ("-wal", "-shm"):
            with self.subTest(suffix=suffix), _Fixture() as fx:
                path = fx.db_path()
                path.with_name(path.name + suffix).touch()
                error = sqlite3.OperationalError("unable to open database file")
                with mock.patch.object(
                    sqlite3, "connect", side_effect=error
                ) as connect:
                    with self.assertRaises(sqlite3.OperationalError) as raised:
                        _ = _bfn("_sqlite_open_ro")(path)
                self.assertIs(raised.exception, error)
                self.assertEqual(connect.call_count, 1)
                self.assertEqual(_bval("_sqlite_open_connections"), 0)

    def test_closed_wal_without_sidecars_opens_and_anchors_resume(self) -> None:
        with _Fixture() as fx:
            fx.set_flag(True)
            writer = fx.writer()
            writer.think(3, 3, "закрытая WAL-база")
            self.assertEqual(
                writer.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0], 0
            )
            path = fx.db_path()
            for suffix in ("-wal", "-shm"):
                path.with_name(path.name + suffix).unlink()
            writer.close()
            fx.writers.clear()
            for suffix in ("-wal", "-shm"):
                self.assertFalse(path.with_name(path.name + suffix).exists())

            conn = cast(sqlite3.Connection, _bfn("_sqlite_open_ro")(path))
            try:
                self.assertEqual(
                    conn.execute("SELECT MAX(idx) FROM steps").fetchone()[0], 3
                )
                self.assertEqual(conn.execute("PRAGMA query_only").fetchone()[0], 1)
                with self.assertRaises(sqlite3.OperationalError):
                    _ = conn.execute("DELETE FROM steps")
            finally:
                _ = _bfn("_sqlite_close")(conn)
            plan = _bfn("_prespawn_plan")(_CID, True)
            self.assertIs(_oval(plan, "anchored"), True)
            self.assertEqual(_oval(plan, "base_idx"), 4)
            self.assertEqual(_oval(plan, "reason"), "")
            self.assertEqual(_bval("_sqlite_open_connections"), 0)

    def test_ao08_every_connect_is_read_only_uri(self) -> None:
        source = Path(_BRIDGE_PY).read_text(encoding="utf-8")
        self.assertNotIn("BEGIN", source)
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


# ======================================================================================
# agy-silent-agent-fix: арбитр planner-контента (AD-001), безопасный прогресс нативных
# инструментов (AD-002), раздельные idle/max таймауты (AD-003), graceful timeout
# (AD-004) и локальный GigaRC-совместимый снимок dynamic_config.json (AD-005).
# ======================================================================================

_FLAG_ENV = {
    "planner_content_streaming_enabled": "AGY_PLANNER_CONTENT_STREAMING_ENABLED",
    "emit_tool_trace": "AGY_BRIDGE_EMIT_TOOL_TRACE",
    "extended_timeout_enabled": "AGY_EXTENDED_TIMEOUT_ENABLED",
    "graceful_timeout_on_partial": "AGY_GRACEFUL_TIMEOUT_ON_PARTIAL",
    "step_scoped_usage_enabled": "AGY_STEP_SCOPED_USAGE_ENABLED",
}
_FLAG_NAMES = tuple(_FLAG_ENV)
_NOTICE_MARK = "Превышен лимит времени хода agy"


def _clean_flags(fx: _Fixture) -> None:
    """Все пять env-переключателей и таймаут-алиасы сняты: действует только файл/дефолт."""
    for env in _FLAG_ENV.values():
        fx.set_env(env, None)
    for env in ("AGY_IDLE_TIMEOUT_S", "AGY_TIMEOUT_S", "AGY_BRIDGE_IDLE_TIMEOUT"):
        fx.set_env(env, None)


def _clocked(fx: _Fixture) -> _FakeClock:
    clock = _FakeClock()
    fx.patch("time", _fake_time(clock))
    return clock


def _write_cfg(fx: _Fixture, data: object, mtime_ns: int | None = None) -> None:
    text = data if isinstance(data, str) else json.dumps(data)
    _ = fx.config.write_text(_str(text), encoding="utf-8")
    if mtime_ns is not None:
        os.utime(fx.config, ns=(mtime_ns, mtime_ns))


class RuntimeConfigSnapshotTests(unittest.TestCase):
    """AD-005: локальный GigaRC-совместимый снимок, env > JSON bool > False (VER-005)."""

    def test_runtime_config_snapshot_defaults_false_without_file_or_keys(self) -> None:
        with _Fixture() as fx:
            _clean_flags(fx)
            clock = _clocked(fx)
            new_flag = _bfn("_new_flag")
            for name in _FLAG_NAMES:
                self.assertIs(new_flag(name), False, name)
            _write_cfg(fx, {"unrelated": True}, 1_000_000_000)
            clock.advance(1.1)
            for name in _FLAG_NAMES:
                self.assertIs(new_flag(name), False, name)
            self.assertEqual(_bval("FLAG_TTL_S"), 1.0)

    def test_runtime_config_snapshot_json_true_enables_each_and_all_flags(self) -> None:
        with _Fixture() as fx:
            _clean_flags(fx)
            clock = _clocked(fx)
            new_flag = _bfn("_new_flag")
            stamp = 1_000_000_000
            for name in _FLAG_NAMES:
                with self.subTest(flag=name):
                    stamp += 1_000
                    _write_cfg(fx, {name: True}, stamp)
                    clock.advance(1.1)
                    for other in _FLAG_NAMES:
                        self.assertIs(new_flag(other), other == name, (name, other))
            stamp += 1_000
            _write_cfg(fx, dict.fromkeys(_FLAG_NAMES, True), stamp)
            clock.advance(1.1)
            for name in _FLAG_NAMES:
                self.assertIs(new_flag(name), True, name)

    def test_runtime_config_snapshot_env_override_beats_opposite_json(self) -> None:
        with _Fixture() as fx:
            _clean_flags(fx)
            clock = _clocked(fx)
            new_flag = _bfn("_new_flag")
            _write_cfg(fx, dict.fromkeys(_FLAG_NAMES, True), 1_000_000_000)
            clock.advance(1.1)
            for name, env in _FLAG_ENV.items():
                for raw in ("0", "false", "No", "OFF", " False "):
                    with self.subTest(flag=name, env=raw):
                        fx.set_env(env, raw)
                        self.assertIs(new_flag(name), False)
                fx.set_env(env, None)
            _write_cfg(fx, dict.fromkeys(_FLAG_NAMES, False), 2_000_000_000)
            clock.advance(1.1)
            for name, env in _FLAG_ENV.items():
                for raw in ("1", "true", "Yes", "ON", " True "):
                    with self.subTest(flag=name, env=raw):
                        fx.set_env(env, raw)
                        self.assertIs(new_flag(name), True)
                fx.set_env(
                    env, "garbage"
                )  # невалидный env игнорируется -> файл (False)
                self.assertIs(new_flag(name), False)
                fx.set_env(env, None)

    def test_runtime_config_snapshot_ttl_and_stat_key_reload(self) -> None:
        with _Fixture() as fx:
            _clean_flags(fx)
            clock = _clocked(fx)
            snap = _bfn("_runtime_snapshot")
            on = '{"emit_tool_trace":true }'
            off = '{"emit_tool_trace":false}'
            self.assertEqual(len(on), len(off))
            _write_cfg(fx, on, 1_000_000_000)
            self.assertIs(_oval(snap(), "emit_tool_trace"), True)
            _write_cfg(fx, off, 2_000_000_000)  # тот же размер, другой mtime_ns
            clock.advance(0.99)
            self.assertIs(_oval(snap(), "emit_tool_trace"), True)  # до TTL — без stat
            clock.advance(0.02)
            self.assertIs(_oval(snap(), "emit_tool_trace"), False)
            _write_cfg(fx, '{"emit_tool_trace":  true}', 2_000_000_000)  # другой размер
            clock.advance(1.01)
            self.assertIs(_oval(snap(), "emit_tool_trace"), True)

    def test_runtime_config_snapshot_unchanged_stat_means_zero_json_loads(self) -> None:
        with _Fixture() as fx:
            _clean_flags(fx)
            clock = _clocked(fx)
            snap = _bfn("_runtime_snapshot")
            _write_cfg(fx, {"graceful_timeout_on_partial": True}, 1_000_000_000)
            first = snap()
            with mock.patch.object(json, "loads", side_effect=json.loads) as spy:
                clock.advance(5.0)
                again = snap()
                clock.advance(5.0)
                third = snap()
            self.assertEqual(spy.call_count, 0)
            self.assertIs(again, first)
            self.assertIs(third, first)
            _write_cfg(fx, {"graceful_timeout_on_partial": False}, 3_000_000_000)
            clock.advance(5.0)
            with mock.patch.object(json, "loads", side_effect=json.loads) as spy:
                changed = snap()
            self.assertEqual(spy.call_count, 1)
            self.assertIsNot(changed, first)
            self.assertIs(_oval(changed, "graceful_timeout_on_partial"), False)

    def test_runtime_config_snapshot_bad_file_keeps_lastgood_or_false(self) -> None:
        bad_values = (
            '{"emit_tool_trace": "true"}',
            '{"emit_tool_trace": 1}',
            '{"emit_tool_trace": null}',
            '{"emit_tool_trace": []}',
            '{"emit_tool_trace": {}}',
            '{"emit_tool_trace": true, "extended_timeout_enabled": "yes"}',
            "{broken",
            "[]",
            "",
        )
        for bad in bad_values:
            with self.subTest(bad=bad):
                with _Fixture() as fx:  # холодный старт: целиком отвергается -> False
                    _clean_flags(fx)
                    _clocked(fx)
                    _write_cfg(fx, bad, 1_000_000_000)
                    for name in _FLAG_NAMES:
                        self.assertIs(_bfn("_new_flag")(name), False, name)
                with _Fixture() as fx:  # тёплый: last-known-good сохраняется
                    _clean_flags(fx)
                    clock = _clocked(fx)
                    good = {
                        "emit_tool_trace": True,
                        "graceful_timeout_on_partial": True,
                    }
                    _write_cfg(fx, good, 1_000_000_000)
                    self.assertIs(_bfn("_new_flag")("emit_tool_trace"), True)
                    _write_cfg(fx, bad, 2_000_000_000)
                    clock.advance(1.1)
                    self.assertIs(_bfn("_new_flag")("emit_tool_trace"), True)
                    self.assertIs(
                        _bfn("_new_flag")("graceful_timeout_on_partial"), True
                    )
                    self.assertIs(_bfn("_new_flag")("extended_timeout_enabled"), False)
                    _write_cfg(fx, {"emit_tool_trace": False}, 3_000_000_000)
                    clock.advance(1.1)  # исправленный файл снова принимается
                    self.assertIs(_bfn("_new_flag")("emit_tool_trace"), False)
                    self.assertIs(
                        _bfn("_new_flag")("graceful_timeout_on_partial"), False
                    )

    def test_runtime_config_snapshot_sqlite_flag_keeps_own_fail_closed(self) -> None:
        with _Fixture() as fx:
            _clean_flags(fx)
            clock = _clocked(fx)
            flag_on = _bfn("_runtime_flag_on")
            new_flag = _bfn("_new_flag")
            _write_cfg(
                fx, {"SQLITE_REASONING_ENABLED": True, "emit_tool_trace": True}, 1_000
            )
            self.assertIs(flag_on(), True)
            self.assertIs(new_flag("emit_tool_trace"), True)
            _write_cfg(fx, "{broken", 2_000)
            clock.advance(1.1)
            self.assertIs(flag_on(), False)  # SQLite — fail-closed без lastgood
            self.assertIs(new_flag("emit_tool_trace"), True)  # новые флаги — lastgood
            _write_cfg(
                fx, {"SQLITE_REASONING_ENABLED": "true", "emit_tool_trace": True}, 3_000
            )
            clock.advance(1.1)
            self.assertIs(flag_on(), False)  # не-bool -> False
            self.assertIs(new_flag("emit_tool_trace"), True)
            _write_cfg(fx, {"SQLITE_REASONING_ENABLED": True}, 4_000)
            clock.advance(1.1)
            self.assertIs(flag_on(), True)
            _write_cfg(fx, {"emit_tool_trace": True}, 5_000)
            clock.advance(1.1)
            self.assertIs(flag_on(), False)  # нет ключа -> False
            fx.config.unlink()
            clock.advance(1.1)
            self.assertIs(flag_on(), False)
            for name in _FLAG_NAMES:  # файл исчез -> новые флаги тоже False
                self.assertIs(new_flag(name), False, name)
            _write_cfg(fx, {"SQLITE_REASONING_ENABLED": True}, 6_000)
            clock.advance(1.1)
            fx.set_env("AGY_SQLITE_REASONING_ENABLED", "0")
            self.assertEqual(_bfn("_sqlite_disabled_reason")(), "env")
            fx.set_env("AGY_SQLITE_REASONING_ENABLED", None)
            self.assertEqual(_bfn("_sqlite_disabled_reason")(), "")


# ---- арбитр planner-контента (AD-001, VER-001) -----------------------------------------


def _arb(turn: str = "turn-1") -> object:
    return _bfn("_ContentArbiter")(turn)


def _offer(arb: object, source: str, idx: object, text: str, cid: str = _CID) -> str:
    return _str(_ofn(arb, "offer")(source, idx, text, cid))


def _pump_queue(
    lines: list[dict[str, object]], content: bool = False
) -> tuple[object, list[tuple[str, object]]]:
    """Прогнать Run._pump по готовому stdout без процесса: (run, события очереди)."""
    run = object.__new__(cast("type[object]", _bval("Run")))
    payload = b"".join(json.dumps(line).encode("utf-8") + b"\n" for line in lines)
    tail = SimpleNamespace(
        cid="",
        bind=lambda _cid: None,
        drain_deadline=0.0,
        thread=SimpleNamespace(join=lambda timeout=None: None, is_alive=lambda: False),
    )
    attrs: dict[str, object] = {
        "proc": SimpleNamespace(
            stdout=io.BytesIO(payload), wait=lambda timeout=None: 0
        ),
        "q": queue.Queue(),
        "_text_seen": {},
        "_tail": tail,
        "_proc_done": threading.Event(),
        "_stop_watch": threading.Event(),
        "_emit_lock": threading.Lock(),
        "drain_closed": False,
        "_done_put": False,
        "got_event": False,
        "content_streaming": content,
        "_arbiter": _arb("turn-pump"),
        "run_cid": "",
        "turn_id": "turn-pump",
        "_activity_lock": threading.Lock(),
        "last_producer_activity_ts": 0.0,
        "transcript_activity_ts": None,
        "started": 0.0,
        "err_box": [],
    }
    for key, value in attrs.items():
        setattr(run, key, value)
    _ = _ofn(run, "_pump")()
    items: list[tuple[str, object]] = []
    q = cast("queue.Queue[tuple[str, object]]", _oval(run, "q"))
    while not q.empty():
        items.append(q.get_nowait())
    return run, items


def _stdout_text(idx: object, text: str) -> dict[str, object]:
    return {
        "event": "step_update",
        "step_update": {
            "step_type": "agent_response",
            "step_index": idx,
            "text_delta": text,
        },
    }


def _stdout_tool(idx: object, name: object = "run_command") -> dict[str, object]:
    step: dict[str, object] = {
        "step_type": "tool",
        "state": "DONE",
        "tool_name": name,
        "duration_seconds": 1.5,
    }
    if idx is not _MISSING:
        step["step_index"] = idx
    return {"event": "step_update", "step_update": step}


_MISSING = object()


def _tail_with(
    emit_content: Callable[[int | None, str], bool] | None = None,
    on_activity: Callable[[], None] | None = None,
    base_idx: int = 0,
    offset: int = 0,
    resumed: bool = False,
    cid: str = _CID,
) -> tuple[object, list[tuple[int, str]]]:
    plan = _bfn("_TurnPlan")()
    setattr(plan, "mode", "OFF")
    setattr(plan, "base_idx", base_idx)
    setattr(plan, "offset", offset)
    emitted: list[tuple[int, str]] = []

    def emit(idx: int, delta: str, on_delivered: Callable[[], None] | None) -> bool:
        emitted.append((idx, delta))
        if on_delivered is not None:
            on_delivered()
        return True

    tail = _bfn("_TranscriptTail")(
        emit,
        threading.Event(),
        threading.Event(),
        resumed,
        plan,
        "turn-x",
        emit_content=emit_content,
        on_activity=on_activity,
    )
    _ = _ofn(tail, "bind")(cid)
    return tail, emitted


def _run_turn_text(
    ctx: dict[str, object] | None = None,
) -> tuple[dict[str, object], list[tuple[float, str]]]:
    texts: list[tuple[float, str]] = []

    def on_text(text: str) -> bool:
        texts.append((time.time(), text))
        return True

    with _Sock() as sock:
        handler = cast(object, _make_handler(sock))
        out = _dict(
            _ofn(handler, "_run_once")(
                ctx if ctx is not None else _ctx(),
                on_text,
                _tool_sink,
                _text_sink,
                None,
            )
        )
    return out, texts


def _planner_events(
    stdout: list[tuple[float, str]], transcript: tuple[float, str] | None, result: str
) -> list[dict[str, object]]:
    events: list[dict[str, object]] = [_init_ev(0.05)]
    for at, text in stdout:
        events.append(_text_ev(at, text, step=9))
    if transcript is not None:
        events.append(
            {
                "t": transcript[0],
                "op": "transcript",
                "record": {
                    "type": "PLANNER_RESPONSE",
                    "step_index": 9,
                    "content": transcript[1],
                    "tool_calls": [],
                },
            }
        )
    events.append(_result_ev(0.5, response=result))
    events.append(_exit_ev(0.55))
    return events


class SilentPlannerContentTests(unittest.TestCase):
    """AD-001: двухуровневый арбитр без потерь и дублей (VER-001)."""

    def test_silent_planner_content_same_idx_in_both_source_orders(self) -> None:
        for first, second in (("stdout", "transcript"), ("transcript", "stdout")):
            with self.subTest(first=first):
                arb = _arb()
                got = [
                    _offer(arb, first, 7, "Hel"),
                    _offer(arb, first, 7, "Hello"),
                    _offer(arb, second, 7, "Hello world"),
                    _offer(arb, first, 7, "Hello"),  # устаревший короткий снимок
                    _offer(arb, second, 7, "Hello world"),  # равный снимок
                ]
                self.assertEqual(got, ["Hel", "lo", " world", "", ""])

    def test_silent_planner_content_missing_or_invalid_idx_never_duplicates(
        self,
    ) -> None:
        bad_indices = (None, -1, -7, "7x", True, 1.5, [], "")
        for first, second in (("stdout", "transcript"), ("transcript", "stdout")):
            for bad in bad_indices:
                with self.subTest(first=first, bad=repr(bad)):
                    arb = _arb()
                    self.assertEqual(
                        _offer(arb, first, 3, "Hello world"), "Hello world"
                    )
                    self.assertEqual(_offer(arb, second, bad, "Hello world"), "")
                    self.assertEqual(_offer(arb, second, bad, "Hello"), "")  # префикс
                    self.assertEqual(_offer(arb, second, bad, "Hello world!!"), "!!")
                    self.assertEqual(_offer(arb, second, bad, "Hello world!!"), "")
                    self.assertEqual(_offer(arb, first, 3, "Hello world!!"), "")

    def test_silent_planner_content_mismatched_idx_aliases_one_watermark(self) -> None:
        for first, second in (("stdout", "transcript"), ("transcript", "stdout")):
            with self.subTest(first=first):
                arb = _arb()
                self.assertEqual(_offer(arb, first, 3, "ABC"), "ABC")
                self.assertEqual(_offer(arb, second, 12, "ABC"), "")  # alias
                self.assertEqual(_offer(arb, second, 12, "ABCD"), "D")
                self.assertEqual(
                    _offer(arb, first, 3, "ABCD"), ""
                )  # монотонный watermark
                self.assertEqual(_offer(arb, first, 3, "ABCDE"), "E")
                self.assertEqual(_offer(arb, second, 12, "ABCDE"), "")
                self.assertEqual(_offer(arb, second, 12, "AB"), "")

    def test_silent_planner_content_late_duplicate_of_an_old_step_is_dropped(
        self,
    ) -> None:
        arb = _arb()
        self.assertEqual(_offer(arb, "stdout", 3, "first"), "first")
        self.assertEqual(_offer(arb, "stdout", 5, "second"), "second")
        self.assertEqual(_offer(arb, "transcript", 3, "first"), "")  # тот же idx
        self.assertEqual(_offer(arb, "transcript", 40, "first"), "")  # чужой idx
        self.assertEqual(_offer(arb, "transcript", None, "firs"), "")  # префикс старого
        self.assertEqual(_offer(arb, "transcript", 41, "second"), "")
        self.assertEqual(_offer(arb, "transcript", 42, "third"), "third")  # новый шаг

    def test_silent_planner_content_non_prefix_divergence_freezes_the_step(
        self,
    ) -> None:
        arb = _arb()
        self.assertEqual(_offer(arb, "stdout", 3, "abc"), "abc")
        self.assertEqual(_offer(arb, "stdout", 3, "abX"), "")  # не склеивать мусор
        self.assertEqual(_offer(arb, "stdout", 3, "abXd"), "")
        self.assertEqual(_offer(arb, "transcript", 3, "abcdef"), "")  # заморожен
        self.assertEqual(_offer(arb, "stdout", 3, "abc"), "")  # без повтора префикса
        self.assertEqual(_oval(arb, "divergences"), 1)
        self.assertEqual(_offer(arb, "stdout", 4, "другой шаг"), "другой шаг")

    def test_silent_planner_content_same_source_equal_steps_are_both_kept(self) -> None:
        for source in ("stdout", "transcript"):
            with self.subTest(source=source):
                arb = _arb()
                self.assertEqual(_offer(arb, source, 3, "OK"), "OK")
                self.assertEqual(_offer(arb, source, 7, "OK"), "OK")  # независимый шаг
                self.assertEqual(_offer(arb, source, 3, "OK"), "")
        arb = _arb()  # без step_index подавление по тексту допустимо
        self.assertEqual(_offer(arb, "stdout", None, "OK"), "OK")
        self.assertEqual(_offer(arb, "stdout", None, "OK"), "")

    def test_silent_planner_content_result_response_merges_without_duplicate(
        self,
    ) -> None:
        arb = _arb()
        self.assertEqual(_offer(arb, "stdout", 3, "Part one."), "Part one.")
        self.assertEqual(_offer(arb, "stdout", 5, "Part two."), "Part two.")
        reconcile = _ofn(arb, "reconcile_result")
        self.assertEqual(reconcile("Part two."), "")  # равен последнему шагу
        self.assertEqual(reconcile("Part one.Part two."), "")  # равен конкатенации
        self.assertEqual(reconcile("Part one."), "")  # дубль старого шага
        self.assertEqual(
            reconcile("Part one.Part two. Tail"), " Tail"
        )  # только остаток
        self.assertEqual(reconcile("Part one.Part two. Tail"), "")
        self.assertEqual(reconcile(""), "")
        empty = _arb()
        self.assertEqual(
            _ofn(empty, "reconcile_result")("только result"), "только result"
        )
        broken = _arb()
        self.assertEqual(_offer(broken, "stdout", 1, "abc"), "abc")
        self.assertEqual(_ofn(broken, "reconcile_result")("xyz"), "")  # несовместим
        self.assertEqual(_oval(broken, "divergences"), 1)

    def test_silent_planner_content_lookup_work_does_not_scan_history(self) -> None:
        arb = _arb()
        for idx in range(100):
            _ = _offer(arb, "stdout", idx, "шаг-%03d текст" % idx)
        before = _int(_oval(arb, "probes"))
        self.assertEqual(_offer(arb, "stdout", 1000, "новый шаг"), "новый шаг")
        self.assertLessEqual(_int(_oval(arb, "probes")) - before, 3)
        before = _int(_oval(arb, "probes"))
        self.assertEqual(_offer(arb, "stdout", 5, "шаг-005 текст"), "")  # keyed hit
        self.assertLessEqual(_int(_oval(arb, "probes")) - before, 3)
        self.assertEqual(len(cast("dict[str, object]", _oval(arb, "eq_index"))), 101)

    def test_silent_planner_content_unicode_and_step_cap_overflow(self) -> None:
        arb = _arb()
        text = "Привет, 世界 🌍"
        parts = [_offer(arb, "stdout", 2, text[:k]) for k in range(1, len(text) + 1)]
        self.assertEqual("".join(parts), text)
        capped = _arb()
        for idx in range(_int(_bval("MAX_STEPS_TRACKED"))):
            _ = _offer(capped, "stdout", idx, "s%d" % idx)
        self.assertEqual(_offer(capped, "stdout", 9999, "лишний"), "")
        self.assertIs(_oval(capped, "overflow"), True)
        self.assertEqual(_offer(capped, "stdout", 0, "s0"), "")  # без replay

    def test_silent_planner_content_run_offer_queues_only_new_suffix(self) -> None:
        run = _bare_run()
        setattr(run, "_arbiter", _arb())
        setattr(run, "turn_id", "turn-1")
        setattr(run, "run_cid", _CID)
        offer = _ofn(run, "offer_content")
        for source, idx, text in (
            ("stdout", 4, "Hel"),
            ("stdout", 4, "Hello"),
            ("transcript", 4, "Hello"),
            ("transcript", 4, "Hello!"),
        ):
            _ = offer(source, idx, text)
        q = cast("queue.Queue[tuple[str, object]]", _oval(run, "q"))
        queued = [q.get_nowait() for _ in range(q.qsize())]
        self.assertEqual(queued, [("text", "Hel"), ("text", "lo"), ("text", "!")])
        setattr(run, "drain_closed", True)
        _ = offer("transcript", 4, "Hello!?")
        self.assertTrue(q.empty())  # после barrier ничего не ставится
        run_result = _ofn(run, "reconcile_result")
        self.assertEqual(run_result("Hello!"), "")

    def test_silent_planner_content_tail_emits_candidates_with_idx(self) -> None:
        with _Fixture() as fx:
            got: list[tuple[int | None, str]] = []
            tail, _emitted = _tail_with(
                emit_content=lambda idx, text: got.append((idx, text)) or True,
                base_idx=5,
                resumed=True,
                offset=0,
            )
            fx.append_record(
                {"type": "PLANNER_RESPONSE", "step_index": 2, "content": "история"}
            )
            fx.append_record(
                {
                    "type": "PLANNER_RESPONSE",
                    "step_index": 6,
                    "content": "с инструментом",
                    "tool_calls": [{"name": "run_command"}],
                }
            )
            fx.append_record(
                {"type": "PLANNER_RESPONSE", "step_index": 7, "content": ""}
            )
            fx.append_record(
                {"type": "PLANNER_RESPONSE", "step_index": 8, "content": "  "}
            )
            fx.append_record({"type": "PLANNER_RESPONSE", "content": "без индекса"})
            fx.append_record(
                {"type": "PLANNER_RESPONSE", "step_index": 9, "content": "финал"}
            )
            _ = _ofn(tail, "_read_transcript")()
            self.assertEqual(
                got, [(6, "с инструментом"), (None, "без индекса"), (9, "финал")]
            )

    def test_silent_planner_content_live_dedup_through_real_run(self) -> None:
        with _Fixture() as fx:
            fx.set_env(_FLAG_ENV["planner_content_streaming_enabled"], "1")
            fx.set_env(_FLAG_ENV["emit_tool_trace"], None)
            _ = fx.write_scenario(
                _planner_events(
                    [(0.1, "Hel"), (0.15, "Hello")], (0.2, "Hello world"), "Hello world"
                )
            )
            out, texts = _run_turn_text()
            self.assertEqual(out["state"], "done")
            self.assertEqual([t for _at, t in texts], ["Hel", "lo", " world"])
            self.assertEqual(out["text"], "Hello world")
            self.assertLess(texts[-1][0], _exit_time(fx))  # live до завершения процесса
            # transcript-only: result.response не дублирует уже выданный текст
            fx.transcript().unlink()  # новый разговор: чужой транскрипт не читается
            _ = fx.write_scenario(_planner_events([], (0.2, "Hello"), "Hello"))
            out, texts = _run_turn_text()
            self.assertEqual([t for _at, t in texts], ["Hello"])
            # текст есть только в result — досылается целиком
            fx.transcript().unlink()
            _ = fx.write_scenario(_planner_events([], None, "только result"))
            out, texts = _run_turn_text()
            self.assertEqual([t for _at, t in texts], ["только result"])

    def test_silent_planner_content_flag_off_keeps_legacy_stdout_only(self) -> None:
        with _Fixture() as fx:
            _clean_flags(fx)
            _ = fx.write_scenario(
                _planner_events(
                    [(0.1, "Hel"), (0.15, "Hello")], (0.2, "Hello world"), "Hello world"
                )
            )
            out, texts = _run_turn_text()
            self.assertEqual(out["state"], "done")
            self.assertEqual([t for _at, t in texts], ["Hel", "lo"])

    def test_silent_planner_content_pump_routes_stdout_through_arbiter(self) -> None:
        lines = [
            _stdout_text(4, "Hel"),
            _stdout_text(4, "Hello"),
            _stdout_text("4", "Hello"),  # тот же шаг в строковом виде
            _stdout_text(None, "Hello"),  # без idx: дубль по тексту
        ]
        _run, items = _pump_queue(lines, content=True)
        self.assertEqual(
            [p for k, p in items if k == "text"],
            ["Hel", "lo"],
        )
        _run, legacy = _pump_queue(lines, content=False)
        self.assertEqual([p for k, p in legacy if k == "text"][:2], ["Hel", "lo"])


# ---- безопасный прогресс инструментов (AD-002, VER-002) --------------------------------


class SilentToolProgressTests(unittest.TestCase):
    def test_silent_tool_progress_pump_forwards_step_index_and_fallback_ordinal(
        self,
    ) -> None:
        lines = [
            _stdout_tool(4),
            _stdout_tool("5", "read_file"),
            _stdout_tool(None),
            _stdout_tool(_MISSING),
            _stdout_tool(-1),
        ]
        _run, items = _pump_queue(lines)
        events = [cast("dict[str, object]", p) for k, p in items if k == "tool_trace"]
        self.assertEqual([e["step_index"] for e in events], [4, 5, None, None, -1])
        self.assertNotIn("fallback_ordinal", events[0])
        self.assertNotIn("fallback_ordinal", events[1])
        self.assertEqual(events[2]["fallback_ordinal"], 1)
        self.assertEqual(events[3]["fallback_ordinal"], 2)
        self.assertNotIn("fallback_ordinal", events[4])
        self.assertEqual(events[0]["name"], "run_command")
        self.assertEqual(events[0]["duration_s"], 1.5)

    def test_silent_tool_progress_allowlist_and_sanitising(self) -> None:
        safe = _bfn("_safe_tool_name")
        for name in ("run_command", "read_file", "write_file", "manage_task"):
            self.assertEqual(safe(name), name)
        self.assertEqual(safe("default_api:run_command"), "run_command")
        self.assertEqual(safe("  read_file "), "read_file")
        for hostile in (
            "unknown_tool",
            "rm -rf / # SECRET-TOKEN-abcdef0123456789",
            "run_command\r\nX-Injected: 1",
            "\x1b[31mrun_command\x1b[0m",
            "read_file\x00",
            "/Users/me/.ssh/id_rsa",
            "AKIAIOSFODNN7EXAMPLE",
            "",
            None,
            123,
            ["run_command"],
        ):
            self.assertEqual(safe(hostile), "tool", repr(hostile))

    def test_silent_tool_progress_marker_format_and_no_payload_leak(self) -> None:
        self.assertEqual(
            _bfn("_format_tool_marker")("run_command"),
            "\n[🔧 tool: run_command — done]\n",
        )
        progress = _bfn("_ToolProgress")("turn-1", _CID)
        secret = "sk-SECRET-0123456789abcdef"
        event = {
            "name": "write_file",
            "duration_s": 3.2,
            "step_index": 9,
            "args": {"path": "/etc/passwd", "token": secret},
            "result": secret,
            "env": {"KEY": secret},
            "path": "/Users/me/secret",
        }
        marker = _ofn(progress, "marker")(event)
        self.assertEqual(marker, "\n[🔧 tool: write_file — done]\n")
        text = _str(marker)
        for forbidden in (secret, "/etc/passwd", "args", "result", "\r", "\x1b", "3.2"):
            self.assertNotIn(forbidden, text)
        hostile = _ofn(progress, "marker")({"name": secret + "\r\n", "step_index": 10})
        self.assertEqual(hostile, "\n[🔧 tool: tool — done]\n")

    def test_silent_tool_progress_done_dedup_by_turn_cid_step_not_name(self) -> None:
        progress = _bfn("_ToolProgress")("turn-1", _CID)
        marker = _ofn(progress, "marker")
        self.assertIsNotNone(marker({"name": "run_command", "step_index": 4}))
        self.assertIsNone(marker({"name": "run_command", "step_index": 4}))
        self.assertIsNone(marker({"name": "read_file", "step_index": 4}))  # имя не ключ
        self.assertIsNotNone(marker({"name": "run_command", "step_index": 5}))
        # один и тот же объект события (replay) с fallback ordinal — подавляется
        replay = {"name": "run_command", "step_index": None, "fallback_ordinal": 1}
        self.assertIsNotNone(marker(replay))
        self.assertIsNone(marker(replay))
        self.assertIsNotNone(
            marker({"name": "run_command", "step_index": None, "fallback_ordinal": 2})
        )
        self.assertIsNotNone(marker({"name": "run_command"}))  # без ordinal: не теряем
        other_turn = _bfn("_ToolProgress")("turn-2", _CID)
        self.assertIsNotNone(
            _ofn(other_turn, "marker")({"name": "run_command", "step_index": 4})
        )

    def _sse_tool_run(
        self,
        events: list[object],
        env: str | None,
        fail_on: int | None = None,
        file_flag: bool | None = None,
    ) -> list[object]:
        with _Fixture() as fx:
            _clean_flags(fx)
            fx.set_env(_FLAG_ENV["emit_tool_trace"], env)
            if file_flag is not None:
                _write_cfg(fx, {"emit_tool_trace": file_flag}, 1_000)

            def run_once(_ctx: object, _t: object, on_tool: Any, *_a: object) -> object:
                results.extend(on_tool(event) for event in events)
                return {
                    "state": "done",
                    "rc": 0,
                    "text": "ok",
                    "usage": {},
                    "conversation_id": "",
                }

            results: list[object] = []
            _h, _s, wfile, _c = _sse_with(run_once, fail_on=fail_on)
            return [results, wfile.writes]

    def test_silent_tool_progress_disabled_is_noop_before_formatting(self) -> None:
        event = {"name": "run_command", "step_index": 4}
        for env, file_flag in ((None, None), ("0", True), (None, False)):
            with self.subTest(env=env, file_flag=file_flag):
                with mock.patch.object(
                    _bridge(),
                    "_format_tool_marker",
                    side_effect=_bfn("_format_tool_marker"),
                ) as fmt:
                    results, writes = self._sse_tool_run([event], env, None, file_flag)
                self.assertEqual(results, [True])
                self.assertEqual(fmt.call_count, 0)
                self.assertFalse(
                    any("reasoning_content" in w for w in cast("list[str]", writes))
                )

    def test_silent_tool_progress_enabled_by_env_or_json_emits_once(self) -> None:
        events = [
            {"name": "run_command", "step_index": 4},
            {"name": "run_command", "step_index": 4},
            {"name": "weird\r\nname", "step_index": 5},
        ]
        for env, file_flag in (("1", None), ("true", False), (None, True)):
            with self.subTest(env=env, file_flag=file_flag):
                results, writes = self._sse_tool_run(events, env, None, file_flag)
                self.assertEqual(results, [True, True, True])
                frames = [
                    w for w in cast("list[str]", writes) if "reasoning_content" in w
                ]
                self.assertEqual(len(frames), 2)
                joined = "".join(frames)
                self.assertIn("tool: run_command", joined)
                self.assertIn("tool: tool", joined)
                self.assertNotIn("weird", joined)

    def test_silent_tool_progress_counter_moves_only_after_successful_emit(
        self,
    ) -> None:
        # Маркер не дошёл (запись упала) -> это не «отданный прогресс»: graceful не включается.
        with _Fixture() as fx:
            _clean_flags(fx)
            fx.set_env(_FLAG_ENV["emit_tool_trace"], "1")
            fx.set_env(_FLAG_ENV["graceful_timeout_on_partial"], "1")
            outcomes: list[object] = []

            def run_once(ctx: Any, _t: object, on_tool: Any, *_a: object) -> object:
                outcomes.append(on_tool({"name": "run_command", "step_index": 1}))
                out: dict[str, object] = {
                    "state": "timeout",
                    "rc": 124,
                    "text": "",
                    "usage": {},
                    "conversation_id": "",
                    "timeout_limit_s": 1800.0,
                }
                hook = ctx.get("finalize_timeout")
                if hook is not None:
                    hook(out)
                return out

            _h, _s, wfile, _c = _sse_with(run_once, fail_on=2)
            self.assertEqual(outcomes, [False])
            frames = _frames_json(wfile.writes)
            self.assertFalse(any(_is_length(f) for f in frames))
            self.assertTrue(any(isinstance(f, dict) and "error" in f for f in frames))

    def test_silent_tool_progress_json_mode_collects_markers(self) -> None:
        with _Fixture() as fx:
            _clean_flags(fx)
            fx.set_env(_FLAG_ENV["emit_tool_trace"], "1")
            sent: list[tuple[int, dict[str, object]]] = []

            def run_once(
                _ctx: object, _t: object, on_tool: Any, on_r: Any, _k: object
            ) -> object:
                _ = on_r("думаю. ")
                _ = on_tool({"name": "read_file", "step_index": 1})
                _ = on_tool({"name": "read_file", "step_index": 1})
                return {
                    "state": "done",
                    "rc": 0,
                    "text": "ответ",
                    "reasoning": "думаю. ",
                    "usage": {},
                    "conversation_id": "",
                }

            with _Sock() as sock:
                handler = cast(object, _make_handler(sock))
                setattr(handler, "_run_once", run_once)
                setattr(handler, "_send", lambda c, p: sent.append((c, p)))
                _ = _ofn(handler, "_serve_json")({"model": "m"})
            message = _dict(
                _dict(cast("list[object]", sent[0][1]["choices"])[0])["message"]
            )
            self.assertEqual(
                message["reasoning_content"],
                "думаю. \n[🔧 tool: read_file — done]\n",
            )


# ---- таймауты по активности producer (AD-003, VER-003) ---------------------------------


class _ScriptQueue:
    """Очередь на мок-часах: каждый get() двигает часы, сценарий играет producer."""

    def __init__(
        self,
        clock: _FakeClock,
        run: SimpleNamespace,
        script: Callable[[int, float, SimpleNamespace], object | None],
    ) -> None:
        self.clock = clock
        self.run = run
        self.script = script
        self.tick = 0

    def get(self, timeout: float = 1.0) -> Any:
        self.tick += 1
        self.clock.advance(float(timeout) if timeout else 1.0)
        item = self.script(self.tick, self.clock(), self.run)
        if item is None:
            raise queue.Empty
        return item


def _policy(
    clock: _FakeClock,
    idle: float = 1800.0,
    cap: float = 3594.5,
    max_s: float = 3600.0,
    can_start: bool = True,
) -> object:
    return _bfn("_TimeoutPolicy")(
        t_req_start=clock(),
        idle_timeout_s=idle,
        max_timeout_s=max_s,
        effective_max_timeout_s=cap,
        can_start=can_start,
    )


def _ext_run(
    clock: _FakeClock,
    script: Callable[[int, float, SimpleNamespace], object | None],
    got_event: bool = True,
    policy: object | None = None,
    controller: Any = None,
) -> SimpleNamespace:
    ctrl = controller or AdaptiveTimeoutController(
        idle_timeout_s=300.0,
        safety_cap_s=1800.0,
        finish_reserve_s=0.0,
        watchdog_enabled=False,
        clock=clock,
    )
    run = SimpleNamespace(
        controller=ctrl,
        proc=SimpleNamespace(pid=424242),
        got_event=got_event,
        started=clock(),
        err_box=[],
        policy=policy if policy is not None else _policy(clock),
        last_producer_activity_ts=clock(),
        transcript_activity_ts=None,
    )
    run.q = _ScriptQueue(clock, run, script)
    return run


def _stamp(run: SimpleNamespace, now: float, transcript: bool = False) -> None:
    run.last_producer_activity_ts = now
    if transcript:
        run.transcript_activity_ts = now


class SilentTimeoutPolicyTests(unittest.TestCase):
    def _exec(
        self, fx: _Fixture, clock: _FakeClock, run: SimpleNamespace
    ) -> dict[str, object]:
        return _dict(cast(object, _execute_with_clock(clock, run)))

    def test_silent_timeout_policy_producer_activity_extends_idle_until_max(
        self,
    ) -> None:
        with _Fixture() as fx:
            _clean_flags(fx)
            fx.set_env(_FLAG_ENV["extended_timeout_enabled"], "1")
            clock = _FakeClock()
            start = clock()

            def script(tick: int, now: float, run: SimpleNamespace) -> object | None:
                if tick % 600 == 0:  # stdout/transcript растёт, очередь пуста
                    _stamp(run, now, transcript=bool(tick % 1200))
                return None

            out = self._exec(fx, clock, _ext_run(clock, script))
            self.assertEqual(out["state"], "timeout")
            self.assertEqual(out["rc"], 124)
            self.assertEqual(out["timeout_limit_s"], 3594.5)
            self.assertLessEqual(clock() - start, 3596.0)
            self.assertGreater(clock() - start, 3594.0)  # idle 1800 не сработал

    def test_silent_timeout_policy_silent_producers_idle_at_configured_1800(
        self,
    ) -> None:
        with _Fixture() as fx:
            _clean_flags(fx)
            fx.set_env(_FLAG_ENV["extended_timeout_enabled"], "1")
            clock = _FakeClock()
            start = clock()
            spy = _SpyController(
                AdaptiveTimeoutController(
                    idle_timeout_s=300.0,
                    safety_cap_s=1800.0,
                    finish_reserve_s=0.0,
                    watchdog_enabled=False,
                    clock=clock,
                ),
                forced=(False, "", None),  # «CPU растёт» — контроллер не должен решать
            )
            run = _ext_run(clock, lambda *_a: None, controller=spy)
            out = self._exec(fx, clock, run)
            self.assertEqual(out["state"], "idle_timeout")
            self.assertEqual(out["rc"], 124)
            self.assertEqual(out["timeout_limit_s"], 1800.0)
            self.assertGreaterEqual(clock() - start, 1800.0)
            self.assertLess(clock() - start, 1802.0)
            self.assertEqual(spy.check_calls, 0)  # cpu_delta контроллера не участвует

    def test_silent_timeout_policy_activity_resets_idle_window(self) -> None:
        with _Fixture() as fx:
            _clean_flags(fx)
            fx.set_env(_FLAG_ENV["extended_timeout_enabled"], "1")
            clock = _FakeClock()
            start = clock()

            def script(tick: int, now: float, run: SimpleNamespace) -> object | None:
                if tick == 1700:  # последняя активность на 1700 с
                    _stamp(run, now)
                return None

            out = self._exec(fx, clock, _ext_run(clock, script))
            self.assertEqual(out["state"], "idle_timeout")
            self.assertGreaterEqual(clock() - start, 3500.0)  # 1700 + 1800

    def test_silent_timeout_policy_transcript_progress_blocks_first_token_timeout(
        self,
    ) -> None:
        for stamp_tick in (60, 120):  # в том числе ровно на границе окна 120 с
            with self.subTest(stamp_tick=stamp_tick):
                with _Fixture() as fx:
                    _clean_flags(fx)
                    fx.set_env(_FLAG_ENV["extended_timeout_enabled"], "1")
                    clock = _FakeClock()

                    def script(
                        tick: int,
                        now: float,
                        run: SimpleNamespace,
                        at: int = stamp_tick,
                    ) -> object | None:
                        if tick == at:
                            _stamp(run, now, transcript=True)
                        return None

                    run = _ext_run(clock, script, got_event=False)
                    out = self._exec(fx, clock, run)
                    self.assertNotEqual(out["state"], "first_token_timeout")
                    self.assertEqual(out["state"], "idle_timeout")

    def test_silent_timeout_policy_total_silence_is_first_token_timeout_504(
        self,
    ) -> None:
        with _Fixture() as fx:
            _clean_flags(fx)
            fx.set_env(_FLAG_ENV["extended_timeout_enabled"], "1")
            clock = _FakeClock()
            start = clock()
            out = self._exec(
                fx, clock, _ext_run(clock, lambda *_a: None, got_event=False)
            )
            self.assertEqual(out["state"], "first_token_timeout")
            self.assertGreater(clock() - start, _float(_bval("FIRST_TOKEN_TIMEOUT_S")))
            self.assertLess(clock() - start, 123.0)
            body = _dict(_ofn(_bval("Handler"), "_error_body")(out))
            self.assertEqual(body["code"], 504)
            self.assertEqual(body["type"], "first_token_timeout")

    def test_silent_timeout_policy_cap_is_checked_with_a_non_empty_queue(self) -> None:
        with _Fixture() as fx:
            _clean_flags(fx)
            fx.set_env(_FLAG_ENV["extended_timeout_enabled"], "1")
            clock = _FakeClock()
            start = clock()
            served = [0]

            def script(tick: int, now: float, run: SimpleNamespace) -> object | None:
                _stamp(run, now)
                served[0] += 1
                return ("text", "x")  # очередь никогда не пуста

            out = self._exec(fx, clock, _ext_run(clock, script))
            self.assertEqual(out["state"], "timeout")
            self.assertEqual(out["timeout_limit_s"], 3594.5)
            self.assertLessEqual(clock() - start, 3596.0)
            self.assertGreater(served[0], 3500)

    def test_silent_timeout_policy_live_kill_switch_returns_to_legacy_deadline(
        self,
    ) -> None:
        with _Fixture() as fx:
            _clean_flags(fx)
            fx.set_env(_FLAG_ENV["extended_timeout_enabled"], "1")
            clock = _FakeClock()
            start = clock()

            def script(tick: int, now: float, run: SimpleNamespace) -> object | None:
                _stamp(run, now)
                if tick == 500:
                    fx.set_env(_FLAG_ENV["extended_timeout_enabled"], "0")
                return None

            quiet = AdaptiveTimeoutController(
                idle_timeout_s=1e9,
                safety_cap_s=3594.5,
                finish_reserve_s=0.0,
                watchdog_enabled=False,
                clock=clock,
            )
            out = self._exec(fx, clock, _ext_run(clock, script, controller=quiet))
            self.assertEqual(out["state"], "timeout")
            self.assertEqual(out["timeout_limit_s"], float(_bval("TIMEOUT_S")))
            self.assertLessEqual(clock() - start, 1802.0)
            self.assertGreaterEqual(clock() - start, 1800.0)

    def test_silent_timeout_policy_disabled_keeps_legacy_300_and_1800(self) -> None:
        with _Fixture() as fx:
            _clean_flags(fx)
            clock = _FakeClock()
            start = clock()
            ctrl = AdaptiveTimeoutController(
                idle_timeout_s=_float(_bval("IDLE_TIMEOUT_S")),
                safety_cap_s=float(_bval("TIMEOUT_S")),
                finish_reserve_s=0.0,
                watchdog_enabled=False,
                clock=clock,
            )
            out = _dict(
                cast(
                    object, _execute_with_clock(clock, _fake_run(clock, ctrl, [], 2000))
                )
            )
            self.assertEqual(out["state"], "idle_timeout")
            self.assertLessEqual(clock() - start, 306.0)
            self.assertEqual(_bval("IDLE_TIMEOUT_S"), 300.0)
            self.assertEqual(_bval("TIMEOUT_S"), 1800)
            # даже при включённом env без policy у run действует прежний путь
            fx.set_env(_FLAG_ENV["extended_timeout_enabled"], "1")
            clock = _FakeClock()
            ctrl = AdaptiveTimeoutController(
                idle_timeout_s=1e9,
                safety_cap_s=1800.0,
                finish_reserve_s=0.0,
                watchdog_enabled=False,
                clock=clock,
            )
            run = _fake_run(clock, ctrl, [], 2000)
            out = _dict(cast(object, _execute_with_clock(clock, run)))
            self.assertEqual(out["state"], "timeout")
            self.assertLessEqual(clock() - 1000.0, 1802.0)

    def test_silent_timeout_policy_budget_math_and_env_overrides(self) -> None:
        with _Fixture() as fx:
            _clean_flags(fx)
            clock = _clocked(fx)
            build = _bfn("_build_timeout_policy")
            t_req = clock()
            self.assertIsNone(build(t_req))  # флаг выключен -> legacy
            fx.set_env(_FLAG_ENV["extended_timeout_enabled"], "1")
            policy = build(t_req)
            self.assertEqual(_oval(policy, "idle_timeout_s"), 1800.0)
            self.assertEqual(_oval(policy, "max_timeout_s"), 3600.0)
            self.assertEqual(_oval(policy, "effective_max_timeout_s"), 3594.5)
            self.assertIs(_oval(policy, "can_start"), True)
            clock.advance(900.0)  # admission ждал 900 с
            policy = build(t_req)
            self.assertEqual(_oval(policy, "effective_max_timeout_s"), 2694.5)
            self.assertEqual(900.0 + 2694.5 + 0.5 + 5.0, 3600.0)
            for remaining, can in (
                (5.5, False),
                (6.0, False),
                (6.25, False),
                (6.5, True),
            ):
                with self.subTest(remaining=remaining):
                    clock.now = t_req + 3600.0 - remaining
                    policy = build(t_req)
                    self.assertIs(_oval(policy, "can_start"), can)
                    if can:
                        self.assertEqual(_oval(policy, "effective_max_timeout_s"), 1.0)
            clock.now = t_req
            fx.set_env("AGY_BRIDGE_IDLE_TIMEOUT", "77")  # старый алиас
            self.assertEqual(_oval(build(t_req), "idle_timeout_s"), 77.0)
            fx.set_env("AGY_IDLE_TIMEOUT_S", "50")  # новый env приоритетнее
            fx.set_env("AGY_TIMEOUT_S", "100")
            policy = build(t_req)
            self.assertEqual(_oval(policy, "idle_timeout_s"), 50.0)
            self.assertEqual(_oval(policy, "max_timeout_s"), 100.0)
            self.assertEqual(_oval(policy, "effective_max_timeout_s"), 100.0)
            fx.set_env("AGY_IDLE_TIMEOUT_S", "nan")
            fx.set_env("AGY_TIMEOUT_S", "-4")
            policy = build(t_req)
            self.assertEqual(_oval(policy, "idle_timeout_s"), 77.0)
            self.assertEqual(_oval(policy, "max_timeout_s"), 3600.0)

    def _run_once_policy(
        self,
        fx: _Fixture,
        clock: _FakeClock,
        outs: list[dict[str, object]],
        spend: list[float],
        ctx_over: dict[str, object] | None = None,
        sem: object | None = None,
    ) -> tuple[dict[str, object], list[object]]:
        policies: list[object] = []

        class PolicyRun:
            created: list[object] = []

            def __init__(self, *_a: object, **kw: object) -> None:
                self.kw = kw
                PolicyRun.created.append(self)

            def close(self) -> None:
                return None

        calls = [0]

        def fake_execute(_self: object, run: Any, *_a: object) -> dict[str, object]:
            policies.append(run.kw.get("policy"))
            clock.advance(spend[calls[0]])
            out = dict(outs[calls[0]])
            calls[0] += 1
            return out

        ctx = _ctx(stream=False, t_req_start=clock())
        ctx.update(ctx_over or {})
        with contextlib.ExitStack() as stack:
            _ = stack.enter_context(
                mock.patch.object(_bval("Handler"), "_execute", fake_execute)
            )
            _ = stack.enter_context(mock.patch.object(_bridge(), "Run", PolicyRun))
            _ = stack.enter_context(
                mock.patch.object(_bridge(), "_launcher", _fake_launcher_path)
            )
            _ = stack.enter_context(mock.patch.object(_bridge(), "_rng", _zero))
            if sem is not None:
                _ = stack.enter_context(mock.patch.object(_bridge(), "_slots", sem))
            with _Sock() as sock:
                handler = cast(object, _make_handler(sock))
                out = _dict(
                    _ofn(handler, "_run_once")(
                        ctx, _text_sink, _tool_sink, _text_sink, None
                    )
                )
        return out, policies + [len(PolicyRun.created)]

    def test_silent_timeout_policy_retry_spends_the_same_request_budget(self) -> None:
        err = {
            "state": "agy_error",
            "rc": 1,
            "text": "",
            "err": "x",
            "usage": {},
            "conversation_id": "",
        }
        ok = {
            "state": "done",
            "rc": 0,
            "text": "ok",
            "err": "",
            "usage": {},
            "conversation_id": "",
        }
        with _Fixture() as fx:
            _clean_flags(fx)
            fx.set_env(_FLAG_ENV["extended_timeout_enabled"], "1")
            clock = _clocked(fx)
            out, seen = self._run_once_policy(fx, clock, [err, ok], [1000.0, 1.0])
            self.assertEqual(out["state"], "done")
            self.assertEqual(seen[-1], 2)
            first, second = seen[0], seen[1]
            self.assertEqual(_oval(first, "effective_max_timeout_s"), 3594.5)
            # вторая попытка: бюджет НЕ перезапущен, 1000 с уже потрачены
            self.assertEqual(_oval(second, "effective_max_timeout_s"), 2594.5)
            clock2 = _clocked(fx)
            out, seen = self._run_once_policy(fx, clock2, [err, ok], [3595.0, 1.0])
            self.assertEqual(seen[-1], 1)  # remaining = 5с <= 5.5 -> 0 новых attempts
            self.assertEqual(out["state"], "agy_error")
            clock3 = _clocked(fx)
            out, seen = self._run_once_policy(
                fx, clock3, [err, ok], [3593.0, 1.0]
            )  # остаток 7с: попытка допустима
            self.assertEqual(seen[-1], 2)
            clock4 = _clocked(fx)
            out, seen = self._run_once_policy(
                fx, clock4, [err, ok], [3594.0, 1.0]
            )  # остаток 6с: полезное окно < 1с -> новой попытки нет
            self.assertEqual(seen[-1], 1)

    def test_silent_timeout_policy_request_clock_starts_before_admission(self) -> None:
        class GateSem:
            def __init__(self, clock: _FakeClock, grant_at: float) -> None:
                self.clock = clock
                self.grant_at = grant_at

            def acquire(
                self, blocking: bool = True, timeout: float | None = None
            ) -> bool:
                if not blocking:
                    return self.clock() >= self.grant_at
                self.clock.advance(float(timeout or 0.0))
                return self.clock() >= self.grant_at

            def release(self) -> None:
                return None

        ok = {
            "state": "done",
            "rc": 0,
            "text": "ok",
            "err": "",
            "usage": {},
            "conversation_id": "",
        }
        for wait, expected in ((0.0, 3594.5), (900.0, 2694.5)):
            with self.subTest(wait=wait):
                with _Fixture() as fx:
                    _clean_flags(fx)
                    fx.set_env(_FLAG_ENV["extended_timeout_enabled"], "1")
                    clock = _clocked(fx)
                    sem = GateSem(clock, clock() + wait)
                    out, seen = self._run_once_policy(
                        fx,
                        clock,
                        [ok],
                        [0.0],
                        sem=sem,
                        ctx_over={"t_req_start": clock()},
                    )
                    self.assertEqual(out["state"], "done")
                    self.assertEqual(
                        _oval(seen[0], "effective_max_timeout_s"), expected
                    )

    def test_silent_timeout_policy_exhausted_budget_never_spawns_a_run(self) -> None:
        with _Fixture() as fx:
            _clean_flags(fx)
            fx.set_env(_FLAG_ENV["extended_timeout_enabled"], "1")
            clock = _clocked(fx)
            ok = {
                "state": "done",
                "rc": 0,
                "text": "ok",
                "err": "",
                "usage": {},
                "conversation_id": "",
            }
            out, seen = self._run_once_policy(
                fx, clock, [ok], [0.0], ctx_over={"t_req_start": clock() - 3595.0}
            )
            self.assertEqual(seen, [0])
            self.assertEqual(out["state"], "timeout")
            self.assertEqual(out["rc"], 124)
            body = _dict(_ofn(_bval("Handler"), "_error_body")(out))
            self.assertEqual(body["code"], 504)

    def test_silent_timeout_policy_tail_deadline_follows_effective_max(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            launcher = Path(tmp) / "fake-launcher.sh"
            _ = launcher.write_text("#!/bin/sh\nexec sleep 30\n", encoding="utf-8")
            launcher.chmod(0o755)
            runs: list[Any] = []
            try:
                with (
                    mock.patch.object(
                        _bridge(), "_launcher", return_value=str(launcher)
                    ),
                    mock.patch.object(_bridge(), "WORKSPACE", Path(tmp) / "ws"),
                ):
                    clock = _FakeClock(time.monotonic())
                    policy = _bfn("_TimeoutPolicy")(
                        t_req_start=clock(),
                        idle_timeout_s=1800.0,
                        max_timeout_s=3600.0,
                        effective_max_timeout_s=3594.5,
                        can_start=True,
                    )
                    ext = srv.Run("p", "m", "low", "default", "", "tag", policy=policy)
                    runs.append(ext)
                    legacy = srv.Run("p", "m", "low", "default", "", "tag")
                    runs.append(legacy)
                    self.assertEqual(ext._tail.deadline_s, 3594.5 + 60.0)
                    self.assertEqual(ext.controller.idle_timeout_s, 1800.0)
                    self.assertEqual(ext.controller.safety_cap_s, 3594.5)
                    self.assertEqual(legacy._tail.deadline_s, srv.TIMEOUT_S + 60.0)
                    self.assertIsNone(legacy.policy)
            finally:
                for run in runs:
                    run.close()

    def test_silent_timeout_policy_tail_loop_survives_past_1860_when_extended(
        self,
    ) -> None:
        class ClockEvent:
            def __init__(self, clock: _FakeClock) -> None:
                self.clock = clock

            def is_set(self) -> bool:
                return False

            def wait(self, timeout: float | None = None) -> bool:
                self.clock.advance(float(timeout or 0.0))
                return False

        for deadline_s, low, high in (
            (3594.5 + 60.0, 3654.5, 3665.0),
            (None, 1860.0, 1871.0),
        ):
            with self.subTest(deadline_s=deadline_s):
                with _Fixture() as fx:
                    clock = _clocked(fx)
                    fx.patch("TRANSCRIPT_POLL_S", 10.0)
                    tail, _e = _tail_with()
                    if deadline_s is not None:
                        setattr(tail, "deadline_s", deadline_s)
                    setattr(tail, "done_event", ClockEvent(clock))
                    ticks = [0]
                    setattr(tail, "tick", lambda: ticks.__setitem__(0, ticks[0] + 1))
                    start = clock()
                    _ = _ofn(tail, "_run_loop")()
                    self.assertGreaterEqual(clock() - start, low)
                    self.assertLessEqual(clock() - start, high)
                    self.assertGreater(ticks[0], 180)

    def test_silent_timeout_policy_tail_stamps_only_real_progress(self) -> None:
        with _Fixture() as fx:
            stamps: list[int] = []
            history = [
                {"type": "PLANNER_RESPONSE", "step_index": 0, "thinking": "h0"},
                {"type": "PLANNER_RESPONSE", "step_index": 1, "thinking": "h1"},
            ]
            for record in history:
                fx.append_record(record)
            size = fx.transcript().stat().st_size
            tail, _e = _tail_with(
                on_activity=lambda: stamps.append(1),
                base_idx=2,
                offset=size,
                resumed=True,
            )
            read = _ofn(tail, "_read_transcript")
            _ = read()
            _ = read()  # неизменный stat: пустой тик
            self.assertEqual(stamps, [], "старый бэклог/пустой тик не продлевают idle")
            fx.append_record({"type": "PLANNER_RESPONSE", "step_index": 2})
            _ = read()
            self.assertEqual(len(stamps), 1)
            _ = read()
            self.assertEqual(len(stamps), 1, "повторное чтение тех же байт")
            with open(fx.transcript(), "a", encoding="utf-8") as fh:
                _ = fh.write('{"type": "PLANNER_RESP')  # рост неполной строки
            _ = read()
            self.assertEqual(len(stamps), 2)
            _ = fx.transcript().write_text(
                "".join(json.dumps(r) + "\n" for r in history), encoding="utf-8"
            )  # файл переписан: снова только история (idx < base_idx)
            before = len(stamps)
            _ = read()
            self.assertEqual(len(stamps), before)

    def test_silent_timeout_policy_pump_stamps_valid_stdout_events_only(self) -> None:
        run, _items = _pump_queue([])
        self.assertEqual(_oval(run, "last_producer_activity_ts"), 0.0)
        run, _items = _pump_queue(
            [{"event": "init", "conversation_id": _CID, "init": {}}]
        )
        self.assertGreater(_float(_oval(run, "last_producer_activity_ts")), 0.0)
        self.assertIsNone(_oval(run, "transcript_activity_ts"))
        _ = _ofn(run, "note_producer_activity")("transcript")
        self.assertIsNotNone(_oval(run, "transcript_activity_ts"))
        self.assertGreaterEqual(
            _float(_oval(run, "last_producer_activity_ts")),
            _float(_oval(run, "transcript_activity_ts")),
        )


# ---- graceful timeout (AD-004, VER-004) -------------------------------------------------


class _FakeSocket:
    """Сокет-заглушка: фиксирует settimeout перед каждой записью."""

    def __init__(self) -> None:
        self.timeouts: list[float] = []

    def settimeout(self, value: float | None) -> None:
        if value is not None:
            self.timeouts.append(value)


class _FakeWfile:
    """wfile на мок-часах: каждая запись стоит `cost` секунд, N-я запись может упасть."""

    def __init__(self, clock: _FakeClock, cost: float, fail_on: int | None) -> None:
        self.clock = clock
        self.cost = cost
        self.fail_on = fail_on
        self.calls = 0
        self.writes: list[str] = []

    def write(self, data: bytes) -> None:
        self.calls += 1
        if self.fail_on is not None and self.calls == self.fail_on:
            raise BrokenPipeError("client gone")
        self.clock.advance(self.cost)
        self.writes.append(data.decode("utf-8"))

    def flush(self) -> None:
        return None


def _make_sse_handler(sock: _FakeSocket, wfile: _FakeWfile) -> Any:
    handler = _make_handler(cast(socket.socket, cast(object, sock)))
    handler.wfile = wfile

    def noop(*_a: object, **_k: object) -> None:
        return None

    handler.send_response = noop
    handler.send_header = noop
    handler.end_headers = noop
    return handler


def _sse_with(
    run_once: Callable[..., object],
    ctx: dict[str, object] | None = None,
    clock: _FakeClock | None = None,
    cost: float = 0.0,
    fail_on: int | None = None,
) -> tuple[Any, _FakeSocket, _FakeWfile, _FakeClock]:
    clock = clock or _FakeClock(5000.0)
    sock = _FakeSocket()
    wfile = _FakeWfile(clock, cost, fail_on)
    handler = _make_sse_handler(sock, wfile)
    handler._run_once = run_once
    with mock.patch.object(_bridge(), "time", _fake_time(clock)):
        handler._serve_sse(ctx if ctx is not None else {"model": "m"})
    return handler, sock, wfile, clock


def _frames_json(frames: list[str]) -> list[object]:
    parsed: list[object] = []
    for frame in frames:
        if frame.startswith("data: [DONE]"):
            parsed.append("[DONE]")
        elif frame.startswith("data: "):
            parsed.append(json.loads(frame[len("data: ") :]))
    return parsed


def _is_length(frame: object) -> bool:
    if not isinstance(frame, dict) or "choices" not in frame:
        return False
    return (
        _dict(cast("list[object]", frame["choices"])[0]).get("finish_reason")
        == "length"
    )


def _content_of(frame: object) -> str:
    if not isinstance(frame, dict) or "choices" not in frame:
        return ""
    delta = _dict(_dict(cast("list[object]", frame["choices"])[0]).get("delta") or {})
    return _str(delta.get("content") or "")


def _scenario(
    kind: str,
    on_text: Callable[[str], object],
    on_tool: Callable[[dict[str, object]], object],
    on_reasoning: Callable[[str], object],
    out: dict[str, object],
) -> None:
    if kind == "content":
        _ = on_text("часть ответа")
        out["text"] = "часть ответа"
    elif kind == "reasoning":
        _ = on_reasoning("мысль")
        out["reasoning"] = "мысль"
    elif kind == "tool":
        _ = on_tool({"name": "run_command", "duration_s": 1.0, "step_index": 4})
    elif kind == "retained":
        out["retained_events"] = [("text", "удержанный хвост")]
        out["retained_planner_text"] = "удержанный хвост"


def _timeout_out(state: str) -> dict[str, object]:
    limit = 1800.0 if state == "timeout" else 900.0
    return {
        "state": state,
        "rc": 124,
        "text": "",
        "reasoning": "",
        "usage": {},
        "result": {},
        "err": "x",
        "tool_calls": [],
        "tool_events": 0,
        "conversation_id": _CID,
        "timeout_limit_s": limit,
    }


class SilentGracefulTimeoutTests(unittest.TestCase):
    def _flags(self, fx: _Fixture, graceful: bool) -> None:
        _clean_flags(fx)
        fx.set_env(_FLAG_ENV["graceful_timeout_on_partial"], "1" if graceful else "0")
        fx.set_env(_FLAG_ENV["emit_tool_trace"], "1")

    def _sse_case(
        self, state: str, kind: str, graceful: bool
    ) -> tuple[list[object], dict[str, object]]:
        with _Fixture() as fx:
            self._flags(fx, graceful)
            holder: dict[str, object] = {}

            def run_once(
                ctx: Any, on_text: Any, on_tool: Any, on_r: Any, _k: object
            ) -> object:
                out = _timeout_out(state)
                _scenario(kind, on_text, on_tool, on_r, out)
                hook = ctx.get("finalize_timeout")
                if hook is not None and out["state"] in ("timeout", "idle_timeout"):
                    hook(out)
                holder["out"] = out
                return out

            _h, _s, wfile, _c = _sse_with(
                run_once, {"model": "m", "t_req_start": 5000.0}
            )
            return _frames_json(wfile.writes), _dict(holder["out"])

    def test_silent_graceful_timeout_sse_matrix(self) -> None:
        for state in ("timeout", "idle_timeout"):
            for kind in ("content", "reasoning", "tool", "retained", "silent"):
                for graceful in (True, False):
                    with self.subTest(state=state, kind=kind, graceful=graceful):
                        frames, _out = self._sse_case(state, kind, graceful)
                        self.assertEqual(frames[-1], "[DONE]")
                        self.assertEqual(frames.count("[DONE]"), 1)
                        errors = [
                            f for f in frames if isinstance(f, dict) and "error" in f
                        ]
                        lengths = [f for f in frames if _is_length(f)]
                        notices = [f for f in frames if _NOTICE_MARK in _content_of(f)]
                        if graceful and kind != "silent":
                            self.assertEqual(errors, [])
                            self.assertEqual(len(lengths), 1)
                            self.assertEqual(len(notices), 1)
                            notice = _content_of(notices[0])
                            self.assertIn(state, notice)
                            limit = "1800" if state == "timeout" else "900"
                            self.assertIn(limit + "s", notice)
                            self.assertEqual(
                                [f for f in frames if _content_of(f)][-1], notices[0]
                            )
                            if kind == "retained":
                                self.assertIn(
                                    "удержанный хвост",
                                    "".join(_content_of(f) for f in frames),
                                )
                            self.assertEqual(
                                sum(
                                    1
                                    for f in frames
                                    if _is_length(f) or "error" in _dict_or_empty(f)
                                ),
                                1,
                            )
                        else:
                            self.assertEqual(lengths, [])
                            self.assertEqual(notices, [])
                            self.assertEqual(len(errors), 1)
                            err = _dict(_dict(errors[0])["error"])
                            self.assertEqual(err["code"], 504)
                            self.assertEqual(err["type"], state)

    def test_silent_graceful_timeout_first_token_timeout_stays_504(self) -> None:
        with _Fixture() as fx:
            self._flags(fx, True)

            def run_once(ctx: Any, *_a: object) -> object:
                out = _timeout_out("first_token_timeout")
                hook = ctx.get("finalize_timeout")
                if hook is not None:
                    hook(out)
                return out

            _h, _s, wfile, _c = _sse_with(run_once, {"model": "m"})
            frames = _frames_json(wfile.writes)
            self.assertFalse(any(_is_length(f) for f in frames))
            errors = [f for f in frames if isinstance(f, dict) and "error" in f]
            self.assertEqual(
                _dict(_dict(errors[0])["error"])["type"], "first_token_timeout"
            )

    def test_silent_graceful_timeout_json_matrix(self) -> None:
        for state in ("timeout", "idle_timeout"):
            for kind in ("content", "reasoning", "tool", "retained", "silent"):
                for graceful in (True, False):
                    with self.subTest(state=state, kind=kind, graceful=graceful):
                        with _Fixture() as fx:
                            self._flags(fx, graceful)
                            sent: list[tuple[int, dict[str, object]]] = []

                            def run_once(
                                _ctx: object,
                                on_t: Any,
                                on_tool: Any,
                                on_r: Any,
                                _k: object,
                            ) -> object:
                                out = _timeout_out(state)
                                _scenario(kind, on_t, on_tool, on_r, out)
                                return out

                            with _Sock() as sock:
                                handler = cast(object, _make_handler(sock))
                                setattr(handler, "_run_once", run_once)
                                setattr(
                                    handler, "_send", lambda c, p: sent.append((c, p))
                                )
                                _ = _ofn(handler, "_serve_json")({"model": "m"})
                        self.assertEqual(len(sent), 1)
                        code, payload = sent[0]
                        if graceful and kind != "silent":
                            self.assertEqual(code, 200)
                            choice = _dict(cast("list[object]", payload["choices"])[0])
                            self.assertEqual(choice["finish_reason"], "length")
                            message = _dict(choice["message"])
                            content = _str(message["content"])
                            self.assertEqual(content.count(_NOTICE_MARK), 1)
                            self.assertIn(state, content)
                            if kind == "content":
                                self.assertIn("часть ответа", content)
                            if kind == "retained":
                                self.assertIn("удержанный хвост", content)
                            if kind == "reasoning":
                                self.assertEqual(message["reasoning_content"], "мысль")
                            if kind == "tool":
                                self.assertIn(
                                    "tool: run_command",
                                    _str(message["reasoning_content"]),
                                )
                        else:
                            self.assertEqual(code, 504)
                            self.assertEqual(_dict(payload["error"])["type"], state)

    def test_silent_graceful_timeout_final_flush_window_survives_expired_deadline(
        self,
    ) -> None:
        with _Fixture() as fx:
            self._flags(fx, True)
            clock = _FakeClock(9000.0)

            def run_once(
                ctx: Any, on_text: Any, on_tool: Any, on_r: Any, _k: object
            ) -> object:
                out = _timeout_out("timeout")
                _scenario("retained", on_text, on_tool, on_r, out)
                ctx["finalize_timeout"](out)
                return out

            # нативный дедлайн (1800 с) давно истёк, но запрос ещё внутри 3600 с
            ctx = {"model": "m", "t_req_start": 9000.0 - 3000.0}
            _h, sock, wfile, _c = _sse_with(run_once, ctx, clock=clock, cost=0.0)
            frames = _frames_json(wfile.writes)
            self.assertTrue(any(_is_length(f) for f in frames))
            self.assertEqual(frames[-1], "[DONE]")
            self.assertEqual(
                sock.timeouts, [5.0, 5.0, 5.0, 5.0]
            )  # суффикс+notice+length+DONE

    def test_silent_graceful_timeout_one_shared_window_for_all_final_writes(
        self,
    ) -> None:
        with _Fixture() as fx:
            self._flags(fx, True)

            def run_once(
                ctx: Any, on_text: Any, on_tool: Any, on_r: Any, _k: object
            ) -> object:
                out = _timeout_out("idle_timeout")
                _scenario("retained", on_text, on_tool, on_r, out)
                ctx["finalize_timeout"](out)
                return out

            ctx = {"model": "m", "t_req_start": 5000.0}
            _h, sock, wfile, clock = _sse_with(run_once, ctx, cost=2.0)
            # role-chunk (до окна) стоит 2 с; окно открывается после него.
            # Запись 1: remaining 5 -> 5.0; 2: 3.0; 3: 1.0; остаток исчерпан -> DONE не пишется
            self.assertEqual(sock.timeouts, [5.0, 3.0, 1.0])
            frames = _frames_json(wfile.writes)
            self.assertNotIn("[DONE]", frames)
            self.assertEqual(
                sum(1 for f in frames if _NOTICE_MARK in _content_of(f)), 1
            )
            self.assertEqual(
                sum(1 for f in frames if _is_length(f)), 1
            )  # третья запись
            self.assertEqual(wfile.calls, 4)  # role + суффикс + notice + length
            self.assertLessEqual(max(sock.timeouts), 5.0)

    def test_silent_graceful_timeout_window_never_crosses_request_ceiling(self) -> None:
        with _Fixture() as fx:
            self._flags(fx, True)

            def run_once(
                ctx: Any, on_text: Any, on_tool: Any, on_r: Any, _k: object
            ) -> object:
                out = _timeout_out("timeout")
                _scenario("content", on_text, on_tool, on_r, out)
                ctx["finalize_timeout"](out)
                return out

            # до потолка запроса (t_req_start + 3600) осталось 2 с
            ctx = {"model": "m", "t_req_start": 5000.0 - 3598.0}
            _h, sock, wfile, _c = _sse_with(run_once, ctx, cost=0.0)
            self.assertEqual(sock.timeouts[0], 2.0)
            self.assertTrue(all(t <= 2.0 for t in sock.timeouts))

    def test_silent_graceful_timeout_write_failure_stops_all_further_writes(
        self,
    ) -> None:
        with _Fixture() as fx:
            self._flags(fx, True)

            def run_once(
                ctx: Any, on_text: Any, on_tool: Any, on_r: Any, _k: object
            ) -> object:
                out = _timeout_out("timeout")
                _scenario("retained", on_text, on_tool, on_r, out)
                ctx["finalize_timeout"](out)
                holder.append(out)
                return out

            holder: list[dict[str, object]] = []
            # вызовы: 1 role, 2 суффикс, 3 notice (падает) -> length/DONE не пишутся
            _h, sock, wfile, _c = _sse_with(
                run_once, {"model": "m", "t_req_start": 5000.0}, fail_on=3
            )
            self.assertEqual(wfile.calls, 3)
            frames = _frames_json(wfile.writes)
            self.assertNotIn("[DONE]", frames)
            self.assertFalse(any(_is_length(f) for f in frames))
            self.assertFalse(any(isinstance(f, dict) and "error" in f for f in frames))
            self.assertIs(
                holder[0].get("graceful_done"), True
            )  # терминал ровно один раз

    def test_silent_graceful_timeout_post_hoc_path_when_run_once_skips_the_hook(
        self,
    ) -> None:
        with _Fixture() as fx:
            self._flags(fx, True)

            def run_once(
                _ctx: Any, on_text: Any, on_tool: Any, on_r: Any, _k: object
            ) -> object:
                out = _timeout_out("timeout")
                _scenario("content", on_text, on_tool, on_r, out)
                return out

            _h, _s, wfile, _c = _sse_with(run_once, {"model": "m"})
            frames = _frames_json(wfile.writes)
            self.assertEqual(sum(1 for f in frames if _is_length(f)), 1)
            self.assertEqual(frames[-1], "[DONE]")

    def test_silent_graceful_timeout_run_once_finalizes_before_close_and_never_retries(
        self,
    ) -> None:
        order: list[str] = []

        class Run:
            created: list[object] = []

            def __init__(self, *_a: object, **_k: object) -> None:
                Run.created.append(self)

            def close(self) -> None:
                order.append("close")

        partial = _timeout_out("idle_timeout")
        partial["text"] = "часть"

        def fake_execute(_self: object, _run: object, *_a: object) -> dict[str, object]:
            return dict(partial)

        def finalize(out: dict[str, object]) -> None:
            order.append("finalize:" + _str(out["state"]))

        with _Fixture() as fx:
            self._flags(fx, True)
            before_ok = list(cast("list[float]", _bval("_last_ok")))
            with (
                mock.patch.object(_bval("Handler"), "_execute", fake_execute),
                mock.patch.object(_bridge(), "Run", Run),
                mock.patch.object(_bridge(), "_launcher", _fake_launcher_path),
                mock.patch.object(_bridge(), "_session_commit") as commit,
            ):
                with _Sock() as sock:
                    handler = cast(object, _make_handler(sock))
                    ctx = _ctx(
                        stream=True, sess_key=("m", "", "low"), conversation_id=_CID
                    )
                    ctx["finalize_timeout"] = finalize
                    out = _dict(
                        _ofn(handler, "_run_once")(
                            ctx, _text_sink, _tool_sink, _text_sink, None
                        )
                    )
            self.assertEqual(order, ["finalize:idle_timeout", "close"])
            self.assertEqual(len(Run.created), 1)  # второй attempt не запускается
            self.assertEqual(out["state"], "idle_timeout")
            self.assertEqual(out["rc"], 124)
            commit.assert_not_called()
            self.assertEqual(list(cast("list[float]", _bval("_last_ok"))), [0.0])
            del before_ok

    def test_silent_graceful_timeout_execute_drains_retained_text_before_returning(
        self,
    ) -> None:
        for graceful in (True, False):
            with self.subTest(graceful=graceful):
                with _Fixture() as fx:
                    _clean_flags(fx)
                    fx.set_env(_FLAG_ENV["extended_timeout_enabled"], "1")
                    fx.set_env(
                        _FLAG_ENV["graceful_timeout_on_partial"],
                        "1" if graceful else "0",
                    )
                    clock = _FakeClock()
                    drains: list[float] = []

                    def script(
                        tick: int, now: float, run: SimpleNamespace
                    ) -> object | None:
                        _stamp(run, now)
                        return None

                    run = _ext_run(clock, script)
                    run.content_streaming = True

                    def terminal_drain(budget_s: float) -> list[tuple[str, object]]:
                        drains.append(budget_s)
                        return [("text", "хвост"), ("reasoning", "мысль")]

                    run.terminal_drain = terminal_drain
                    out = _dict(cast(object, _execute_with_clock(clock, run)))
                    self.assertEqual(out["state"], "timeout")
                    self.assertEqual(drains, [0.5])
                    if graceful:
                        self.assertEqual(
                            out["retained_events"],
                            [("text", "хвост"), ("reasoning", "мысль")],
                        )
                        self.assertEqual(out["retained_planner_text"], "хвост")
                        self.assertEqual(out["text"], "")
                    else:  # без graceful остаток уходит сразу (до legacy-ошибки)
                        self.assertNotIn("retained_events", out)
                        self.assertEqual(out["text"], "хвост")
                        self.assertEqual(out["reasoning"], "мысль")
        self.assertEqual(_bval("T_DRAIN_MAX_S"), 0.5)
        self.assertEqual(_bval("T_FINAL_FLUSH_S"), 5.0)
        self.assertEqual(_bval("T_REQ_BUDGET_S"), 3600.0)
        self.assertEqual(_bval("T_MIN_ATTEMPT_S"), 1.0)

    def _e2e_fixture(self, fx: _Fixture, env: dict[str, str]) -> None:
        _clean_flags(fx)
        for name in _FLAG_NAMES:
            fx.set_env(_FLAG_ENV[name], "1")
        for key, value in env.items():
            fx.set_env(key, value)
        events = [
            _init_ev(0.05),
            _text_ev(0.1, "Hello", step=9),
            {
                "t": 0.2,
                "op": "transcript",
                "record": {
                    "type": "PLANNER_RESPONSE",
                    "step_index": 9,
                    "content": "Hello world",
                    "tool_calls": [],
                },
            },
            _exit_ev(40.0),  # процесс «зависает»: его добьёт зачистка группы
        ]
        _ = fx.write_scenario(events)

    def test_silent_graceful_timeout_end_to_end_real_run_both_states_sse(self) -> None:
        cases = (
            ("timeout", {"AGY_TIMEOUT_S": "2", "AGY_IDLE_TIMEOUT_S": "50"}),
            ("idle_timeout", {"AGY_TIMEOUT_S": "60", "AGY_IDLE_TIMEOUT_S": "1.5"}),
        )
        for state, env in cases:
            with self.subTest(state=state), _Fixture() as fx:
                self._e2e_fixture(fx, env)
                started = time.monotonic()
                frames = _frames_json(_sse_frames(_ctx()))
                self.assertLess(time.monotonic() - started, 15.0)
                self.assertEqual(frames[-1], "[DONE]")
                self.assertEqual(frames.count("[DONE]"), 1)
                self.assertEqual(
                    [f for f in frames if isinstance(f, dict) and "error" in f], []
                )
                texts = [_content_of(f) for f in frames if _content_of(f)]
                self.assertEqual(texts[:2], ["Hello", " world"])  # без дублей
                self.assertEqual(len(texts), 3)
                self.assertIn(_NOTICE_MARK, texts[2])
                self.assertIn(state, texts[2])
                self.assertEqual(sum(1 for f in frames if _is_length(f)), 1)
                self.assertEqual(list(cast("list[float]", _bval("_last_ok"))), [0.0])
                self.assertEqual(len(cast("dict[int, object]", _bval("_active"))), 0)

    def test_silent_graceful_timeout_end_to_end_real_run_json_and_silent_504(
        self,
    ) -> None:
        with _Fixture() as fx:
            self._e2e_fixture(fx, {"AGY_TIMEOUT_S": "2", "AGY_IDLE_TIMEOUT_S": "50"})
            sent: list[tuple[int, dict[str, object]]] = []
            with _Sock() as sock:
                handler = cast(object, _make_handler(sock))
                setattr(handler, "_send", lambda c, p: sent.append((c, p)))
                _ = _ofn(handler, "_serve_json")(_ctx(stream=False))
            code, payload = sent[0]
            self.assertEqual(code, 200)
            choice = _dict(cast("list[object]", payload["choices"])[0])
            self.assertEqual(choice["finish_reason"], "length")
            content = _str(_dict(choice["message"])["content"])
            self.assertTrue(content.startswith("Hello world"))
            self.assertEqual(content.count(_NOTICE_MARK), 1)
        with _Fixture() as fx:  # полная тишина обоих источников -> прежний 504
            _clean_flags(fx)
            for name in ("extended_timeout_enabled", "graceful_timeout_on_partial"):
                fx.set_env(_FLAG_ENV[name], "1")
            fx.set_env("AGY_TIMEOUT_S", "2")
            _ = fx.write_scenario([_init_ev(0.05), _exit_ev(40.0)])
            sent = []
            with _Sock() as sock:
                handler = cast(object, _make_handler(sock))
                setattr(handler, "_send", lambda c, p: sent.append((c, p)))
                _ = _ofn(handler, "_serve_json")(_ctx(stream=False))
            self.assertEqual(sent[0][0], 504)
            self.assertEqual(_dict(sent[0][1]["error"])["type"], "timeout")


# ---- Цикл 2 Совета: RW-001/002/003, F-004/005/007 ----------------------------------------


class _TimeoutSocket(_FakeSocket):
    """Сокет с gettimeout(): таймаут восстанавливается после окна финальной записи."""

    def __init__(self, initial: float | None) -> None:
        super().__init__()
        self.current = initial
        self.history: list[float | None] = []

    def gettimeout(self) -> float | None:
        return self.current

    def settimeout(self, value: float | None) -> None:
        self.current = value
        self.history.append(value)


def _tool_trace_events(items: list[tuple[str, object]]) -> list[dict[str, object]]:
    return [cast("dict[str, object]", p) for k, p in items if k == "tool_trace"]


class SilentCouncilCycle2Tests(unittest.TestCase):
    def _flags(self, fx: _Fixture) -> None:
        _clean_flags(fx)
        fx.set_env(_FLAG_ENV["graceful_timeout_on_partial"], "1")
        fx.set_env(_FLAG_ENV["emit_tool_trace"], "1")

    # -- RW-001: окно финальной записи не отравляет keep-alive соединение -----------------

    def test_silent_rw001_sse_window_reset_restores_timeout_and_deadline(self) -> None:
        with _Fixture() as fx:
            self._flags(fx)
            clock = _FakeClock(5000.0)
            sock = _TimeoutSocket(7.0)
            handler = _make_sse_handler(sock, _FakeWfile(clock, 0.0, None))
            armed: list[object] = []

            def run_once(
                ctx: Any, on_text: Any, on_tool: Any, on_r: Any, _k: object
            ) -> object:
                out = _timeout_out("timeout")
                _scenario("content", on_text, on_tool, on_r, out)
                ctx["finalize_timeout"](out)
                armed.append(handler._flush_deadline)
                return out

            handler._run_once = run_once
            with mock.patch.object(_bridge(), "time", _fake_time(clock)):
                handler._serve_sse({"model": "m", "t_req_start": 5000.0})
            self.assertIsNotNone(armed[0])
            self.assertIsNone(handler._flush_deadline)
            self.assertEqual(sock.current, 7.0)
            self.assertTrue(any(t is not None and t <= 5.0 for t in sock.history))

    def test_silent_rw001_sse_exception_still_resets_and_next_request_is_clean(
        self,
    ) -> None:
        with _Fixture() as fx:
            self._flags(fx)
            clock = _FakeClock(5000.0)
            sock = _TimeoutSocket(7.0)
            wfile = _FakeWfile(clock, 0.0, None)
            handler = _make_sse_handler(sock, wfile)

            def boom(
                ctx: Any, on_text: Any, on_tool: Any, on_r: Any, _k: object
            ) -> object:
                out = _timeout_out("timeout")
                _scenario("content", on_text, on_tool, on_r, out)
                ctx["finalize_timeout"](out)
                raise RuntimeError("boom")

            handler._run_once = boom
            with mock.patch.object(_bridge(), "time", _fake_time(clock)):
                with self.assertRaises(RuntimeError):
                    handler._serve_sse({"model": "m", "t_req_start": 5000.0})
            self.assertIsNone(handler._flush_deadline)
            self.assertEqual(sock.current, 7.0)
            # Следующий запрос на том же Handler: окно закрыто, записи не отбрасываются.
            wfile.writes.clear()
            clock.advance(60.0)

            def ok_run(*_a: object) -> object:
                return {
                    "state": "done",
                    "rc": 0,
                    "text": "ok",
                    "usage": {},
                    "conversation_id": "",
                }

            handler._run_once = ok_run
            with mock.patch.object(_bridge(), "time", _fake_time(clock)):
                handler._serve_sse({"model": "m"})
            self.assertEqual(_frames_json(wfile.writes)[-1], "[DONE]")
            self.assertEqual(sock.current, 7.0)

    def test_silent_rw001_json_window_reset_restores_timeout_hook_and_post_hoc(
        self,
    ) -> None:
        for use_hook in (True, False):
            with self.subTest(use_hook=use_hook), _Fixture() as fx:
                self._flags(fx)
                sent: list[tuple[int, dict[str, object]]] = []

                def run_once(ctx: Any, *_a: object) -> object:
                    out = _timeout_out("timeout")
                    out["text"] = "часть"
                    if use_hook:
                        ctx["finalize_timeout"](out)
                    return out

                with _Sock() as sock:
                    sock.settimeout(9.0)
                    handler = _make_handler(sock)
                    handler._run_once = run_once
                    handler._send = lambda c, p: sent.append((c, p))
                    handler._serve_json({"model": "m"})
                    self.assertEqual(sock.gettimeout(), 9.0)
                self.assertIsNone(handler._flush_deadline)
                self.assertEqual(len(sent), 1)
                self.assertEqual(sent[0][0], 200)
                choice = _dict(cast("list[object]", sent[0][1]["choices"])[0])
                self.assertEqual(choice["finish_reason"], "length")

    def test_silent_rw001_json_finalizes_before_run_close(self) -> None:
        order: list[str] = []

        class FakeRun:
            def __init__(self, *_a: object, **_k: object) -> None:
                pass

            def close(self) -> None:
                order.append("close")

        partial = _timeout_out("timeout")
        partial["text"] = "часть"

        def fake_execute(_self: object, _run: object, *_a: object) -> dict[str, object]:
            return dict(partial)

        with _Fixture() as fx:
            self._flags(fx)
            with (
                mock.patch.object(_bval("Handler"), "_execute", fake_execute),
                mock.patch.object(_bridge(), "Run", FakeRun),
                mock.patch.object(_bridge(), "_launcher", _fake_launcher_path),
            ):
                with _Sock() as sock:
                    handler = _make_handler(sock)
                    handler._send = lambda c, _p: order.append("send:%d" % c)
                    handler._serve_json(_ctx(stream=False))
        self.assertEqual(order, ["send:200", "close"])

    # -- RW-002: потолок маркеров, двухфазный учёт, стабильный ordinal --------------------

    def test_silent_rw002_marker_cap_is_32_and_anonymous_events_are_capped(
        self,
    ) -> None:
        self.assertEqual(_bval("MAX_TOOL_MARKERS_PER_TURN"), 32)
        anon = _bfn("_ToolProgress")("turn-1", _CID)
        got = [_ofn(anon, "marker")({"name": "run_command"}) for _ in range(40)]
        self.assertEqual(sum(1 for m in got if m is not None), 32)
        indexed = _bfn("_ToolProgress")("turn-1", _CID)
        got = [
            _ofn(indexed, "marker")({"name": "run_command", "step_index": i})
            for i in range(40)
        ]
        self.assertEqual(sum(1 for m in got if m is not None), 32)

    def test_silent_rw002_two_phase_commit_spends_budget_only_after_commit(
        self,
    ) -> None:
        progress = _bfn("_ToolProgress")("turn-1", _CID, 2)
        marker = _ofn(progress, "marker")
        commit = _ofn(progress, "commit")
        event = {"name": "run_command", "step_index": 1}
        self.assertIsNotNone(marker(event, commit=False))
        self.assertIsNotNone(
            marker(event, commit=False)
        )  # не засчитан: можно повторить
        _ = commit()
        self.assertIsNone(marker(event, commit=False))
        self.assertIsNotNone(marker({"name": "read_file", "step_index": 2}))
        self.assertIsNone(marker({"name": "read_file", "step_index": 3}))  # лимит 2

    def test_silent_rw002_failed_sink_write_does_not_consume_marker(self) -> None:
        event = {"name": "run_command", "step_index": 4}
        with _Fixture() as fx:
            _clean_flags(fx)
            fx.set_env(_FLAG_ENV["emit_tool_trace"], "1")
            results: list[object] = []

            def run_once(_ctx: object, _t: object, on_tool: Any, *_a: object) -> object:
                results.append(on_tool(event))
                results.append(on_tool(event))
                return {
                    "state": "done",
                    "rc": 0,
                    "text": "ok",
                    "usage": {},
                    "conversation_id": "",
                }

            # запись 1 — role-chunk, запись 2 — первый маркер (падает), 3 — повтор
            _h, _s, wfile, _c = _sse_with(run_once, fail_on=2)
        self.assertEqual(results, [False, True])
        frames = [w for w in wfile.writes if "reasoning_content" in w]
        self.assertEqual(len(frames), 1)

    def test_silent_rw002_call_id_dedups_regardless_of_ordinal(self) -> None:
        progress = _bfn("_ToolProgress")("turn-1", _CID)
        marker = _ofn(progress, "marker")
        first = {"name": "run_command", "call_id": "c-1", "fallback_ordinal": 1}
        self.assertIsNotNone(marker(first))
        self.assertIsNone(marker({**first, "fallback_ordinal": 9}))
        self.assertIsNotNone(marker({**first, "call_id": "c-2"}))

    def test_silent_rw002_pump_ordinal_is_stable_for_replayed_call_id(self) -> None:
        def with_id(call_id: str | None) -> dict[str, object]:
            line = _stdout_tool(_MISSING)
            if call_id is not None:
                _dict(line["step_update"])["call_id"] = call_id
            return line

        _run, items = _pump_queue(
            [with_id("c-1"), with_id("c-1"), with_id("c-2"), with_id(None)]
        )
        events = _tool_trace_events(items)
        self.assertEqual([e["fallback_ordinal"] for e in events], [1, 1, 2, 3])
        self.assertEqual(
            [e.get("call_id") for e in events], ["c-1", "c-1", "c-2", None]
        )

    # -- RW-003: расширенный allowlist ----------------------------------------------------

    def test_silent_rw003_extended_allowlist_and_mcp_names(self) -> None:
        safe = _bfn("_safe_tool_name")
        for name in (
            "edit_file",
            "search_web",
            "invoke_subagent",
            "grep_search",
            "multi_replace_file_content",
            "bash",
        ):
            self.assertEqual(safe(name), name)
        self.assertEqual(safe("default_api:invoke_subagent"), "invoke_subagent")
        self.assertEqual(safe("mcp_github_create_issue"), "mcp_github_create_issue")
        for hostile in (
            "unknown_tool",
            "/bin/bash",
            "./bash",
            "a/../bash",
            "mcp_" + "x" * 40 + "_y",
            "mcp_SECRET_token",
            "mcp_github",
            "sk-SECRET-0123456789abcdef",
        ):
            self.assertEqual(safe(hostile), "tool", repr(hostile))

    # -- F-004: удержание расходящегося текста и отсутствие O(n^2) ------------------------

    def test_silent_f004_divergent_text_is_retained_and_capped(self) -> None:
        arb = _arb()
        self.assertEqual(_offer(arb, "stdout", 1, "hello"), "hello")
        self.assertEqual(_offer(arb, "stdout", 1, "other text"), "")
        self.assertEqual(_ofn(arb, "retained_divergent_text")(), "other text")
        limit = _int(_bval("MAX_RETAINED_DIVERGENT_BYTES"))
        self.assertEqual(limit, 65536)
        self.assertEqual(_offer(arb, "stdout", 2, "a"), "a")
        self.assertEqual(_offer(arb, "stdout", 2, "ы" * 100000), "")
        text = _str(_ofn(arb, "retained_divergent_text")())
        self.assertLessEqual(len(text.encode("utf-8")), limit)
        self.assertGreater(len(text.encode("utf-8")), limit - 4)

    def test_silent_f004_reconcile_result_divergence_is_retained(self) -> None:
        arb = _arb()
        self.assertEqual(_offer(arb, "stdout", 1, "alpha"), "alpha")
        self.assertEqual(_ofn(arb, "reconcile_result")("совсем другое"), "")
        self.assertEqual(_ofn(arb, "retained_divergent_text")(), "совсем другое")

    def test_silent_f004_same_source_equal_steps_do_not_scan_quadratically(
        self,
    ) -> None:
        arb = _arb()
        count = 100
        for idx in range(1, count + 1):
            self.assertEqual(_offer(arb, "stdout", idx, "x"), "x")
        self.assertLessEqual(_int(_oval(arb, "probes")), 3 * count)
        # другой источник по-прежнему находит свой канонический шаг без дубля текста
        self.assertEqual(_offer(arb, "transcript", 7, "x"), "")

    def test_silent_f004_execute_finish_exposes_retained_divergent_text(self) -> None:
        with _Fixture() as fx:
            _clean_flags(fx)
            fx.set_env(_FLAG_ENV["graceful_timeout_on_partial"], "1")
            fx.set_env(_FLAG_ENV["extended_timeout_enabled"], "1")
            clock = _FakeClock()
            run = _ext_run(clock, lambda _t, now, r: _stamp(r, now))
            run.content_streaming = True
            run.terminal_drain = lambda _b: []
            run.retained_divergent_text = lambda: "расхождение"
            out = _dict(cast(object, _execute_with_clock(clock, run)))
        self.assertEqual(out["state"], "timeout")
        self.assertEqual(out["retained_divergent_text"], "расхождение")
        self.assertEqual(out["retained_planner_text"], "расхождение")

    # -- F-005: terminal_drain на нормальном done -----------------------------------------

    def test_silent_f005_done_drains_tail_before_reconcile(self) -> None:
        with _Fixture() as fx:
            _clean_flags(fx)
            clock = _FakeClock()
            order: list[str] = []
            sent = [False]

            def script(_t: int, now: float, run: SimpleNamespace) -> object | None:
                _stamp(run, now)
                if sent[0]:
                    return None
                sent[0] = True
                return ("done", (0, "хвост итог", {}))

            run = _ext_run(clock, script)
            run.content_streaming = True

            def terminal_drain(budget_s: float) -> list[tuple[str, object]]:
                order.append("drain:%g" % budget_s)
                return [("text", "хвост")]

            def reconcile(text: str) -> str:
                order.append("reconcile")
                return text[len("хвост") :]

            run.terminal_drain = terminal_drain
            run.reconcile_result = reconcile
            out = _dict(cast(object, _execute_with_clock(clock, run)))
        self.assertEqual(order, ["drain:0.5", "reconcile"])
        self.assertEqual(out["state"], "done")
        self.assertEqual(out["text"], "хвост итог")

    # -- F-007: устаревший читатель не затирает более свежий снимок -----------------------

    def test_silent_f007_stale_reader_does_not_overwrite_newer_snapshot(self) -> None:
        with _Fixture() as fx:
            _clean_flags(fx)
            clock = _clocked(fx)
            module = _bridge()
            for name in (
                "_cfg_snapshot",
                "_cfg_key",
                "_cfg_checked_at",
                "_cfg_generation",
            ):
                fx.patch(name, getattr(module, name))
            module._cfg_key = None
            module._cfg_checked_at = None
            snap = _bfn("_runtime_snapshot")
            flags = _bfn("_RuntimeFlags")
            newer = flags(graceful_timeout_on_partial=True)
            real_parse = _bfn("_parse_runtime_flags")
            _write_cfg(fx, {"emit_tool_trace": True}, 7_000_000_000)
            gen_before = _int(module._cfg_generation)

            def parse_while_other_thread_wins(text: str) -> object:
                module._cfg_snapshot = newer
                module._cfg_key = (1, 1)
                module._cfg_generation += 1
                return real_parse(text)

            clock.advance(5.0)
            with mock.patch.object(
                module, "_parse_runtime_flags", parse_while_other_thread_wins
            ):
                result = snap()
            self.assertIs(result, newer)
            self.assertIs(module._cfg_snapshot, newer)
            self.assertEqual(module._cfg_key, (1, 1))
            self.assertEqual(module._cfg_generation, gen_before + 1)
            # обычное обновление без гонки двигает поколение ровно на 1
            _write_cfg(fx, {"emit_tool_trace": False}, 8_000_000_000)
            clock.advance(5.0)
            self.assertIs(_oval(snap(), "emit_tool_trace"), False)
            self.assertEqual(module._cfg_generation, gen_before + 2)


def _dict_or_empty(value: object) -> dict[str, object]:
    return _dict(value) if isinstance(value, dict) else {}


# ---- Image input (workspace-read): AD-001..AD-006, F-001..F-010 ---------------------

_IMG_TARGETS = ("gemini-4-argon", "gemini-3.8-flash")
_IMG_MIMES = ("image/png", "image/jpeg", "image/gif", "image/webp")
_IMG_MAGIC: dict[str, bytes] = {
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/jpeg": b"\xff\xd8\xff\xe0",
    "image/gif": b"GIF89a",
    "image/webp": b"RIFF\x00\x00\x00\x00WEBP",
}
_IMG_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
}
_IMG_CAP = 20971520
_FAKE_IMG_SOURCE = """
import hashlib, json, os, stat, sys, time, uuid

argv = sys.argv[1:]
scen = json.load(open(os.environ["FAKE_IMG_SCEN"]))
raw_in = sys.stdin.read()
try:
    prompt = json.loads(raw_in)["message"]["content"][0]["text"]
except Exception:
    prompt = ""
idx = 0
while True:
    try:
        os.mkdir(os.path.join(scen["marks"], str(idx)))
        break
    except FileExistsError:
        idx += 1
rec = {"idx": idx, "argv": argv, "cwd": os.getcwd(), "prompt": prompt,
       "t0": time.time(), "pid": os.getpid()}
if "--add-dir" in argv:
    d = argv[argv.index("--add-dir") + 1]
    rec["dir"] = d
    rec["dir_mode"] = stat.S_IMODE(os.stat(d).st_mode)
    files = {}
    for name in sorted(os.listdir(d)):
        p = os.path.join(d, name)
        with open(p, "rb") as fh:
            data = fh.read()
        files[name] = {"sha": hashlib.sha256(data).hexdigest(),
                       "mode": stat.S_IMODE(os.stat(p).st_mode), "size": len(data)}
    rec["files"] = files


def save():
    path = os.path.join(scen["recs"], "%d.json" % idx)
    with open(path + ".tmp", "w") as fh:
        json.dump(rec, fh)
    os.replace(path + ".tmp", path)


def emit(obj):
    sys.stdout.write(json.dumps(obj) + "\\n")
    sys.stdout.flush()


spawns = scen.get("spawns") or [{}]
beh = spawns[min(idx, len(spawns) - 1)]
cid = argv[argv.index("--conversation") + 1] if "--conversation" in argv else beh.get("cid") or str(uuid.uuid4())
save()
emit({"event": "init", "conversation_id": cid, "init": {"tools": [], "permission_mode": "x"}})
time.sleep(beh.get("sleep", 0))
mode = beh.get("mode", "ok")
if mode in ("ok", "text_then_error"):
    emit({"event": "step_update", "step_update": {"step_type": "agent_response", "step_index": 9, "text_delta": "ответ"}})
status = "ERROR" if mode in ("error", "text_then_error") else "OK"
emit({"event": "result", "result": {"response": "" if status == "ERROR" else "ответ", "status": status,
      "error": "boom" if status == "ERROR" else "", "conversation_id": cid,
      "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}})
rec["t1"] = time.time()
save()
sys.exit(1 if status == "ERROR" else 0)
"""


def _img_raw(mime: str, tag: str = "x", size: int = 0) -> bytes:
    body = _IMG_MAGIC[mime] + tag.encode("ascii")
    return body.ljust(size, b"\x00") if size else body


def _img_url(mime: str, raw: bytes) -> str:
    return "data:%s;base64,%s" % (mime, base64.b64encode(raw).decode("ascii"))


def _img_part(mime: str, raw: bytes) -> dict[str, object]:
    return {"type": "image_url", "image_url": {"url": _img_url(mime, raw)}}


def _img_msg(
    *parts: dict[str, object], text: str = "", role: str = "user"
) -> dict[str, object]:
    content: list[dict[str, object]] = []
    if text:
        content.append({"type": "text", "text": text})
    content.extend(parts)
    return {"role": role, "content": content}


def _txt_msg(role: str, text: str) -> dict[str, object]:
    return {"role": role, "content": text}


def _png_part(tag: str) -> dict[str, object]:
    return _img_part("image/png", _img_raw("image/png", tag))


def _collect(
    messages: list[dict[str, object]],
    model: str = "gemini-4-argon",
    effort: str = "low",
) -> list[dict[str, object]]:
    return cast(
        "list[dict[str, object]]",
        _bfn("_collect_images")(messages, model, effort),
    )


def _reject_of(call: Callable[[], object]) -> tuple[str, str]:
    """(reason, code) исключения ImageReject; иначе тест падает."""
    reject_cls = cast("type[Exception]", _bval("ImageReject"))
    try:
        _ = call()
    except reject_cls as exc:
        return _str(_oval(exc, "reason")), _str(_oval(exc, "code"))
    raise AssertionError("ImageReject expected")


def _proof_of(model_id: str) -> dict[str, object]:
    models = _dict(_bval("FLEET_MODELS"))
    images = _dict(_dict(models[model_id])["images"])
    return _dict(images["proof"])


def _err(body: dict[str, object]) -> dict[str, object]:
    return _dict(body["error"])


def _img_body(
    messages: list[dict[str, object]],
    tools: bool = False,
    cwd: str = "",
    conv: str = "",
    model: str = "gemini-4-argon",
    stream: bool = False,
) -> dict[str, object]:
    body: dict[str, object] = {"model": model, "messages": messages, "stream": stream}
    if tools:
        body["tools"] = [
            {"type": "function", "function": {"name": "x", "parameters": {}}}
        ]
    extra: dict[str, object] = {}
    if cwd:
        extra["cwd"] = cwd
    if conv:
        extra["conversation_id"] = conv
    if extra:
        body["extra_body"] = extra
    return body


def _small_limits(**limits: int) -> contextlib.AbstractContextManager[object]:
    """Временно уменьшить image_limits (границы те же, память теста — нет)."""
    return cast(
        "contextlib.AbstractContextManager[object]",
        mock.patch.dict(
            _dict(_bval("IMAGE_LIMITS")), cast("dict[str, object]", limits)
        ),
    )


def _restore_key(target: dict[str, object], key: str, value: object) -> None:
    target[key] = value


class _ImgEnv:
    """Фикстура image-входа: флаг включён, proof подогнан под фиксчер-бинарь, фейковый agy."""

    fx: _Fixture
    fake: Path
    marks: Path
    recs: Path
    scen: Path

    def __init__(self) -> None:
        self.fx = _Fixture()
        self.fake = self.fx.tmp / "fake-img-agy.py"
        self.marks = self.fx.tmp / "marks"
        self.recs = self.fx.tmp / "recs"
        self.scen = self.fx.tmp / "img-scenario.json"

    def __enter__(self) -> _ImgEnv:
        _ = self.fx.__enter__()
        fx = self.fx
        _ = self.fake.write_text(
            "#!" + sys.executable + "\n" + _FAKE_IMG_SOURCE, encoding="utf-8"
        )
        self.fake.chmod(0o755)
        self.marks.mkdir()
        self.recs.mkdir()
        fx.patch("LAUNCHER", str(self.fake))
        fx.patch("_slots", threading.BoundedSemaphore(4))
        fx.patch("_rng", _zero)
        fx.set_env("FAKE_IMG_SCEN", str(self.scen))
        fx.set_env("AGY_IMAGE_INPUT_ENABLED", None)
        sha = hashlib.sha256(fx.agy_bin.read_bytes()).hexdigest()
        for model_id in _IMG_TARGETS:
            proof = _proof_of(model_id)
            original = proof["agy_binary_sha256"]
            proof["agy_binary_sha256"] = sha
            _ = fx.stack.callback(_restore_key, proof, "agy_binary_sha256", original)
        self.write_scen([{}])
        self.flag(True)
        return self

    def __exit__(self, *_exc: object) -> None:
        self.fx.__exit__()

    def write_scen(self, spawns: list[dict[str, object]]) -> None:
        body = {"marks": str(self.marks), "recs": str(self.recs), "spawns": spawns}
        _ = self.scen.write_text(json.dumps(body), encoding="utf-8")

    def flag(self, value: bool | None) -> None:
        """IMAGE_INPUT_ENABLED в dynamic_config.json (None — файла нет) + сброс кэша."""
        if value is None:
            self.fx.config.unlink(missing_ok=True)
        else:
            _ = self.fx.config.write_text(
                json.dumps({"IMAGE_INPUT_ENABLED": value}), encoding="utf-8"
            )
        setattr(_bridge(), "_image_flag_cache", (0.0, False))

    def records(self) -> list[dict[str, object]]:
        rows = [
            _dict(cast(object, json.loads(p.read_text(encoding="utf-8"))))
            for p in self.recs.glob("*.json")
        ]
        return sorted(rows, key=lambda r: _int(r["idx"]))

    def img_dirs(self) -> list[Path]:
        ws = Path(_str(str(_bval("WORKSPACE"))))
        return sorted(ws.glob("img-*")) if ws.exists() else []

    def free_slots(self) -> int:
        slots = cast(threading.BoundedSemaphore, _bval("_slots"))
        taken = 0
        while slots.acquire(blocking=False):
            taken += 1
        for _i in range(taken):
            _ = slots.release()
        return taken

    def active_dirs(self) -> set[str]:
        return set(cast("set[str]", _bval("_active_img_dirs")))


def _file_map(rec: dict[str, object]) -> dict[str, dict[str, object]]:
    files = _dict(rec.get("files") or {})
    return {name: _dict(info) for name, info in files.items()}


def _argv_of(rec: dict[str, object]) -> list[str]:
    return cast("list[str]", rec["argv"])


def _add_dir_of(rec: dict[str, object]) -> str:
    argv = _argv_of(rec)
    return argv[argv.index("--add-dir") + 1]


def _sha_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class _SnapRun:
    """Подмена Run: снимок каталога изображений в момент каждой попытки, процесс не стартует."""

    attempts: list[dict[str, object]] = []
    add_dir: object

    def __init__(self, *_args: object, **kwargs: object) -> None:
        add_dir = kwargs.get("add_dir")
        self.add_dir = add_dir
        snap: dict[str, object] = {"add_dir": None if add_dir is None else str(add_dir)}
        if add_dir is not None and os.path.isdir(str(add_dir)):
            root = str(add_dir)
            snap["dir_mode"] = os.stat(root).st_mode & 0o777
            files: dict[str, dict[str, object]] = {}
            for name in sorted(os.listdir(root)):
                path = os.path.join(root, name)
                with open(path, "rb") as handle:
                    data = handle.read()
                files[name] = {
                    "sha": _sha_hex(data),
                    "mode": os.stat(path).st_mode & 0o777,
                }
            snap["files"] = files
        _SnapRun.attempts.append(snap)

    def close(self) -> None:
        return None


def _scripted_out(state: str, **over: object) -> dict[str, object]:
    out: dict[str, object] = {
        "rc": 0 if state == "done" else 1,
        "text": "ok" if state == "done" else "",
        "usage": {},
        "result": {},
        "err": "e",
        "tool_calls": [],
        "tool_events": 0,
        "conversation_id": "",
        "num_turns": None,
        "duration_s": None,
        "state": state,
    }
    out.update(over)
    return out


def _img_ctx(
    messages: list[dict[str, object]],
    model: str = "gemini-4-argon",
    effort: str = "low",
    over: dict[str, object] | None = None,
) -> dict[str, object]:
    images = _collect(messages, model, effort)
    img_dir = cast(Path, images[0]["path"]).parent if images else None
    prompt = _str(_bfn("_messages_to_prompt")(messages, images))
    ctx = _ctx(
        model=model,
        model_len=len(model),
        effort=effort,
        prompt=prompt,
        full_prompt=prompt,
        images=images,
        img_dir=img_dir,
        stream=False,
    )
    ctx.update(over or {})
    return ctx


def _run_once_direct(
    ctx: dict[str, object], execute: Callable[..., dict[str, object]] | None = None
) -> dict[str, object]:
    """Handler._run_once с подменой Run (_SnapRun) и, при желании, _execute."""
    handler_cls = _bval("Handler")
    with contextlib.ExitStack() as stack:
        _ = stack.enter_context(mock.patch.object(_bridge(), "Run", _SnapRun))
        _ = stack.enter_context(
            mock.patch.object(_bridge(), "_launcher", _fake_launcher_path)
        )
        if execute is not None:
            _ = stack.enter_context(mock.patch.object(handler_cls, "_execute", execute))
        with _Sock() as sock:
            handler = cast(object, _make_handler(sock))
            setattr(handler, "client_address", ("127.0.0.1", 1))
            return _dict(
                _ofn(handler, "_run_once")(
                    ctx, _text_sink, _tool_sink, _text_sink, None
                )
            )


def _sequence_execute(
    outs: list[dict[str, object]],
) -> Callable[..., dict[str, object]]:
    queue_outs = list(outs)

    def execute(_self: object, _run: object, *_a: object) -> dict[str, object]:
        return dict(queue_outs.pop(0) if len(queue_outs) > 1 else queue_outs[0])

    return execute


def _post_raw_headers(port: int, content_length: int) -> int:
    """Только заголовки с заявленным Content-Length (без тела): HTTP-статус ответа."""
    key = _str(_bval("AUTH_KEY"))
    head = "\r\n".join(
        [
            "POST /v1/chat/completions HTTP/1.1",
            "Host: x",
            "Authorization: Bearer " + key,
            "Content-Type: application/json",
            "Content-Length: %d" % content_length,
            "",
            "",
        ]
    )
    with socket.create_connection(("127.0.0.1", port), timeout=10) as sock:
        sock.sendall(head.encode("ascii"))
        data = sock.recv(4096).decode("ascii", "replace")
    return int(data.split(" ", 2)[1])


def _sse_post(port: int, body: dict[str, object]) -> str:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + _str(_bval("AUTH_KEY")),
    }
    conn.request("POST", "/v1/chat/completions", body=json.dumps(body), headers=headers)
    text = conn.getresponse().read().decode("utf-8")
    conn.close()
    return text


def _get_auth(port: int, path: str) -> dict[str, object]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"Authorization": "Bearer " + _str(_bval("AUTH_KEY"))}
    conn.request("GET", path, headers=headers)
    raw = conn.getresponse().read()
    conn.close()
    return _dict(cast(object, json.loads(raw.decode("utf-8"))))


def _open_fds() -> int:
    return len(os.listdir("/dev/fd"))


def _expect_files(
    test: unittest.TestCase,
    rec: dict[str, object],
    expected: dict[int, tuple[str, bytes]],
) -> None:
    """Файлы каталога изображений в момент spawn: имена, байты (sha) и права 0600."""
    files = _file_map(rec)
    names = {"img-%d.%s" % (n, _IMG_EXT[m]) for n, (m, _r) in expected.items()}
    test.assertEqual(set(files), names)
    for number, (mime, raw) in expected.items():
        info = files["img-%d.%s" % (number, _IMG_EXT[mime])]
        test.assertEqual(info["sha"], _sha_hex(raw))
        test.assertEqual(info["mode"], 0o600)
    test.assertEqual(rec["dir_mode"], 0o700)


class ImageValidationTests(unittest.TestCase):
    """AD-002: упорядоченная fail-closed проверка image-частей (IMG-01..IMG-10)."""

    def test_img01_four_mimes_one_three_sixteen_accepted_and_staged(self) -> None:
        with _ImgEnv() as env:
            for mime in _IMG_MIMES:
                for count in (1, 3, 16):
                    with self.subTest(mime=mime, count=count):
                        raws = [_img_raw(mime, "n%d" % i) for i in range(count)]
                        msgs = [_img_msg(*[_img_part(mime, r) for r in raws])]
                        images = _collect(msgs)
                        numbers = [_int(i["index"]) for i in images]
                        self.assertEqual(numbers, list(range(1, count + 1)))
                        self.assertTrue(all(i["mime"] == mime for i in images))
                        self.assertTrue(all(i["data"] == b"" for i in images))
                        names = [Path(str(i["path"])).name for i in images]
                        self.assertEqual(
                            names,
                            ["img-%d.%s" % (n, _IMG_EXT[mime]) for n in numbers],
                        )
                        parents = {Path(str(i["path"])).parent for i in images}
                        self.assertEqual(len(parents), 1)
                        self.assertTrue(Path(str(images[0]["path"])).is_absolute())
            self.assertEqual(env.img_dirs(), [])  # проверка ничего не пишет на диск
            raws = {m: _img_raw(m, "stage-" + m[-3:]) for m in _IMG_MIMES}
            msgs = [_img_msg(*[_img_part(m, r) for m, r in raws.items()])]
            images = _collect(msgs)
            img_dir = Path(str(images[0]["path"])).parent
            _ = _bfn("_stage_images")(img_dir, images)
            try:
                for number, mime in enumerate(_IMG_MIMES, start=1):
                    path = img_dir / ("img-%d.%s" % (number, _IMG_EXT[mime]))
                    self.assertEqual(path.read_bytes(), raws[mime])
                    self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
                self.assertEqual(os.stat(img_dir).st_mode & 0o777, 0o700)
                self.assertTrue(all(i["data"] == b"" for i in images))
                self.assertTrue(all("b64" not in i for i in images))
            finally:
                shutil.rmtree(img_dir, ignore_errors=True)

    def test_img02_sixteen_mixed_mimes_keep_global_order(self) -> None:
        with _ImgEnv():
            seq = [
                (_IMG_MIMES[i % 4], _img_raw(_IMG_MIMES[i % 4], "m%d" % i))
                for i in range(16)
            ]
            parts = [_img_part(m, r) for m, r in seq]
            msgs = [
                _img_msg(*parts[:5], text="a"),
                _txt_msg("assistant", "ok"),
                _img_msg(*parts[5:11]),
                _img_msg(*parts[11:], text="z"),
            ]
            images = _collect(msgs)
            self.assertEqual([_int(i["index"]) for i in images], list(range(1, 17)))
            self.assertEqual(
                [_int(i["msg_index"]) for i in images], [0] * 5 + [2] * 6 + [3] * 5
            )
            self.assertEqual([i["mime"] for i in images], [m for m, _r in seq])
            self.assertEqual([i["ext"] for i in images], [_IMG_EXT[m] for m, _r in seq])

    def test_img03_seventeen_images_rejected_before_any_decode(self) -> None:
        with _ImgEnv() as env:
            msgs = [_img_msg(*[_png_part("c%d" % i) for i in range(17)])]
            calls: list[int] = []
            real = base64.b64decode

            def spy(data: str, altchars: None = None, validate: bool = False) -> bytes:
                calls.append(1)
                return real(data, altchars, validate)

            with mock.patch.object(base64, "b64decode", spy):
                reason, code = _reject_of(lambda: _collect(msgs))
            self.assertEqual((reason, code), ("too_many_images", "too_many_images"))
            self.assertEqual(calls, [])
            self.assertEqual(env.img_dirs(), [])

    def test_img04_single_image_boundary_for_every_base64_padding(self) -> None:
        # Лимиты уменьшены патчем: граница та же, но тест не раздувает RSS процесса.
        with _ImgEnv(), _small_limits(max_image_bytes=1000, max_total_image_bytes=1000):
            for size in range(997, 1004):  # все остатки по модулю 3 (паддинг 0/1/2)
                with self.subTest(size=size):
                    msgs = [
                        _img_msg(
                            _img_part("image/png", _img_raw("image/png", "b", size))
                        )
                    ]
                    if size <= 1000:
                        self.assertEqual(_int(_collect(msgs)[0]["size"]), size)
                    else:
                        self.assertEqual(
                            _reject_of(lambda: _collect(msgs)),
                            ("image_too_large", "image_too_large"),
                        )

    def test_img05_single_image_one_byte_over_limit_rejected_before_total(self) -> None:
        with _ImgEnv(), _small_limits(max_image_bytes=1000, max_total_image_bytes=500):
            raw = _img_raw("image/png", "big", size=1001)
            msgs = [_img_msg(_img_part("image/png", raw))]
            self.assertEqual(
                _reject_of(lambda: _collect(msgs)),
                ("image_too_large", "image_too_large"),
            )

    def test_img06_total_limit_boundary(self) -> None:
        with _ImgEnv(), _small_limits(max_image_bytes=1000, max_total_image_bytes=1000):
            first = _img_part("image/png", _img_raw("image/png", "a", size=500))
            ok = _img_part("image/jpeg", _img_raw("image/jpeg", "b", size=500))
            over = _img_part("image/jpeg", _img_raw("image/jpeg", "b", size=501))
            self.assertEqual(len(_collect([_img_msg(first, ok)])), 2)
            self.assertEqual(
                _reject_of(lambda: _collect([_img_msg(first, over)])),
                ("images_too_large", "images_too_large"),
            )

    def test_img07_http_body_limit_boundary(self) -> None:
        with _ImgEnv() as env, _small_limits(max_body_bytes=8192):
            bridge = _HttpBridge()
            try:
                head = b'{"messages":[{"role":"user","content":"'
                tail = b'"}]}'
                data = head + b"x" * (8192 - len(head) - len(tail)) + tail
                self.assertEqual(len(data), 8192)
                conn = http.client.HTTPConnection("127.0.0.1", bridge.port, timeout=60)
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + _str(_bval("AUTH_KEY")),
                }
                conn.request("POST", "/v1/chat/completions", body=data, headers=headers)
                self.assertEqual(conn.getresponse().status, 200)
                conn.close()
                self.assertEqual(_post_raw_headers(bridge.port, 8193), 413)
            finally:
                bridge.close()
            self.assertEqual(
                len(env.records()), 1
            )  # 413 не дошёл ни до decode, ни до spawn
        with _ImgEnv():
            bridge = _HttpBridge()
            try:
                limit = _int(_dict(_bval("IMAGE_LIMITS"))["max_body_bytes"])
                self.assertEqual(limit, 33554432)
                self.assertEqual(_post_raw_headers(bridge.port, limit + 1), 413)
            finally:
                bridge.close()

    def test_img08_image_only_user_message_keeps_marker_and_attachment(self) -> None:
        with _ImgEnv():
            msgs = [_img_msg(_png_part("only"))]
            images = _collect(msgs)
            prompt = _str(_bfn("_messages_to_prompt")(msgs, images))
            self.assertNotIn("PONG", prompt)
            self.assertIn("[image 1]", prompt)
            self.assertIn("[attachments]", prompt)
            self.assertIn(str(images[0]["path"]), prompt)
            self.assertIn("(image/png, %d bytes)" % _int(images[0]["size"]), prompt)

    def test_img09_text_only_history_has_zero_image_overhead(self) -> None:
        with _ImgEnv() as env:
            calls: list[str] = []

            def spy_for(name: str) -> Callable[..., object]:
                def spy(*_a: object, **_k: object) -> bool:
                    calls.append(name)
                    return False

                return spy

            msgs: list[dict[str, object]] = [
                _txt_msg("user", "hi"),
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "a"},
                        {"type": "mystery", "x": 1},
                        cast(object, "plain"),
                    ],
                },
            ]
            with contextlib.ExitStack() as stack:
                for name in (
                    "_is_image_input_enabled",
                    "_file_sha256",
                    "_new_img_dir",
                    "_image_proof_reason",
                ):
                    _ = stack.enter_context(
                        mock.patch.object(_bridge(), name, spy_for(name))
                    )
                self.assertEqual(_collect(msgs), [])
            self.assertEqual(calls, [])
            prompt = _str(_bfn("_messages_to_prompt")(msgs))
            self.assertEqual(prompt, "### 1. user\nhi\n\n### 2. user\na\nplain")
            self.assertEqual(env.img_dirs(), [])

    def test_img10_signature_check_is_not_pixel_decoding(self) -> None:
        with _ImgEnv():
            truncated = _IMG_MAGIC["image/png"] + b"\x00truncated-body"
            msgs = [_img_msg(_img_part("image/png", truncated))]
            images = _collect(
                msgs
            )  # сигнатура ок: файл принят, пиксели не декодируются
            self.assertEqual(len(images), 1)
            prompt = _str(_bfn("_messages_to_prompt")(msgs, images))
            self.assertIn("view_file", prompt)
            self.assertIn("Read every attached image file", prompt)

    def test_f003_count_and_base64_length_checked_before_b64decode(self) -> None:
        with _ImgEnv(), _small_limits(max_image_bytes=1000, max_total_image_bytes=1000):
            calls: list[int] = []
            real = base64.b64decode

            def spy(data: str, altchars: None = None, validate: bool = False) -> bytes:
                calls.append(1)
                return real(data, altchars, validate)

            huge = "data:image/png;base64," + "A" * 1336  # оценка 1002 B > лимита 1000
            msgs = [_img_msg({"type": "image_url", "image_url": {"url": huge}})]
            with mock.patch.object(base64, "b64decode", spy):
                self.assertEqual(
                    _reject_of(lambda: _collect(msgs)),
                    ("image_too_large", "image_too_large"),
                )
                many = [_img_msg(*[_png_part("k%d" % i) for i in range(17)])]
                self.assertEqual(
                    _reject_of(lambda: _collect(many))[1], "too_many_images"
                )
            self.assertEqual(calls, [])

    def test_f006_data_url_is_case_insensitive_and_log_values_are_sanitized(
        self,
    ) -> None:
        with _ImgEnv() as env:
            raw = _img_raw("image/png", "case")
            url = "DATA:IMAGE/PNG;BASE64," + base64.b64encode(raw).decode("ascii")
            msgs = [_img_msg({"type": "image_url", "image_url": {"url": url}})]
            images = _collect(msgs)
            self.assertEqual(images[0]["mime"], "image/png")
            self.assertEqual(
                _str(_bfn("_safe_log_value")("a\nb\tc\rd\x00e")), "a_b_c_d_e"
            )
            buffer = io.StringIO()
            with _Sock() as sock, mock.patch.object(sys, "stderr", buffer):
                handler = cast(object, _make_handler(sock))
                setattr(handler, "client_address", ("127.0.0.1", 1))
                _ = _ofn(handler, "_log_reject")(
                    "image_too_large", "gem\nini\tfake\r", 3
                )
            lines = buffer.getvalue().splitlines()
            self.assertEqual(len(lines), 1)
            self.assertIn("model=gem_ini_fake_ ", lines[0])
            self.assertIsNot(_bval("_image_flag_lock"), _bval("_sqlite_guard_lock"))
            self.assertEqual(env.img_dirs(), [])

    def test_f006_sha_cache_keyed_by_identity_and_hash_runs_outside_cache_lock(
        self,
    ) -> None:
        with _ImgEnv() as env:
            target = env.fx.tmp / "sha-subject.bin"
            _ = target.write_bytes(b"first-content")
            self.assertEqual(_bfn("_file_sha256")(target), _sha_hex(b"first-content"))
            held: list[bool] = []

            class _ProbeHash:
                chunks: list[bytes]

                def __init__(self) -> None:
                    self.chunks = []

                def update(self, data: bytes) -> None:
                    held.append(bool(_ofn(_bval("_sha_cache_lock"), "locked")()))
                    self.chunks.append(data)

                def hexdigest(self) -> str:
                    return hashlib.sha256(b"".join(self.chunks)).hexdigest()

            replacement = env.fx.tmp / "sha-subject.new"
            _ = replacement.write_bytes(b"second-content")
            os.replace(replacement, target)  # другой inode/mtime при том же пути
            probe_module = SimpleNamespace(sha256=_ProbeHash)
            with mock.patch.object(_bridge(), "hashlib", probe_module):
                digest = _bfn("_file_sha256")(target)
            self.assertEqual(digest, _sha_hex(b"second-content"))
            self.assertTrue(held)
            self.assertFalse(any(held))
            self.assertEqual(_bfn("_file_sha256")(env.fx.tmp / "absent.bin"), "")


_IMG_RAW_A = _img_raw("image/png", "alpha")
_IMG_RAW_B = _img_raw("image/jpeg", "bravo")
_IMG_RAW_C = _img_raw("image/gif", "charlie")


def _post_many(
    bridge: _HttpBridge, bodies: list[dict[str, object]]
) -> list[tuple[int, dict[str, object]]]:
    return [bridge.post(body) for body in bodies]


class ImageHistoryTests(unittest.TestCase):
    """AD-003/AD-004: сквозная нумерация истории, cold/hot/explicit/fallback (HIST-01..10)."""

    def test_hist01_cold_images_then_text_resends_full_history(self) -> None:
        with _ImgEnv() as env:
            turn1 = [
                _img_msg(
                    _img_part("image/png", _IMG_RAW_A),
                    _img_part("image/jpeg", _IMG_RAW_B),
                    text="смотри",
                )
            ]
            turn2 = turn1 + [
                _txt_msg("assistant", "вижу"),
                _txt_msg("user", "а теперь текст"),
            ]
            bridge = _HttpBridge()
            try:
                results = _post_many(bridge, [_img_body(turn1), _img_body(turn2)])
            finally:
                bridge.close()
            self.assertEqual([code for code, _b in results], [200, 200])
            recs = env.records()
            self.assertEqual(len(recs), 2)
            for rec in recs:
                _expect_files(
                    self,
                    rec,
                    {1: ("image/png", _IMG_RAW_A), 2: ("image/jpeg", _IMG_RAW_B)},
                )
                prompt = _str(rec["prompt"])
                for needle in (
                    "[image 1]",
                    "[image 2]",
                    "[attachments]",
                    "img-1.png",
                    "img-2.jpg",
                ):
                    self.assertIn(needle, prompt)
                self.assertNotIn("--conversation", _argv_of(rec))
            self.assertEqual(env.img_dirs(), [])

    def test_hist02_rejected_history_without_assistant_keeps_all_images(self) -> None:
        with _ImgEnv() as env:
            msgs = [
                _img_msg(
                    _img_part("image/png", _IMG_RAW_A),
                    _img_part("image/jpeg", _IMG_RAW_B),
                    text="скриншоты",
                ),
                _txt_msg("user", "следующий текстовый ход"),
            ]
            bridge = _HttpBridge()
            try:
                code, _body = bridge.post(_img_body(msgs))
            finally:
                bridge.close()
            self.assertEqual(code, 200)
            rec = env.records()[0]
            _expect_files(
                self, rec, {1: ("image/png", _IMG_RAW_A), 2: ("image/jpeg", _IMG_RAW_B)}
            )
            prompt = _str(rec["prompt"])
            self.assertIn("[image 1]", prompt)
            self.assertIn("[image 2]", prompt)
            self.assertIn("следующий текстовый ход", prompt)

    def test_hist03_hot_text_turn_after_images_has_no_new_attachments(self) -> None:
        with _ImgEnv() as env:
            cwd = env.fx.tmp / "proj"
            cwd.mkdir()
            turn1 = [
                _img_msg(
                    _img_part("image/png", _IMG_RAW_A),
                    _img_part("image/jpeg", _IMG_RAW_B),
                )
            ]
            turn2 = turn1 + [
                _txt_msg("assistant", "ок"),
                _txt_msg("user", "только текст"),
            ]
            bridge = _HttpBridge()
            try:
                code1, body1 = bridge.post(_img_body(turn1, tools=True, cwd=str(cwd)))
                code2, _body2 = bridge.post(_img_body(turn2, tools=True, cwd=str(cwd)))
            finally:
                bridge.close()
            self.assertEqual((code1, code2), (200, 200))
            first, second = env.records()
            argv = _argv_of(second)
            self.assertEqual(
                argv[argv.index("--conversation") + 1], body1["conversation_id"]
            )
            prompt = _str(second["prompt"])
            self.assertIn("только текст", prompt)
            self.assertNotIn("[attachments]", prompt)
            self.assertNotIn("[image", prompt)
            _expect_files(
                self,
                second,
                {1: ("image/png", _IMG_RAW_A), 2: ("image/jpeg", _IMG_RAW_B)},
            )
            self.assertEqual(
                os.path.realpath(_str(second["cwd"])), os.path.realpath(cwd)
            )
            store = cast("dict[tuple[str, str, str], object]", _bval("_session_store"))
            self.assertEqual(list(store), [("gemini-4-argon", str(cwd), "high")])
            self.assertNotEqual(_add_dir_of(first), _add_dir_of(second))

    def test_hist04_hot_new_image_keeps_global_index_and_correct_bytes(self) -> None:
        with _ImgEnv() as env:
            turn1 = [_img_msg(_img_part("image/png", _IMG_RAW_A))]
            turn2 = turn1 + [
                _txt_msg("assistant", "ок"),
                _img_msg(_img_part("image/jpeg", _IMG_RAW_B), text="новая картинка"),
            ]
            bridge = _HttpBridge()
            try:
                _ = bridge.post(_img_body(turn1, tools=True))
                code, _body = bridge.post(_img_body(turn2, tools=True))
            finally:
                bridge.close()
            self.assertEqual(code, 200)
            second = env.records()[1]
            self.assertIn("--conversation", _argv_of(second))
            prompt = _str(second["prompt"])
            self.assertIn("[image 2]", prompt)
            self.assertNotIn("[image 1]", prompt)
            self.assertIn("- [image 2] ", prompt)
            self.assertIn("(image/jpeg, %d bytes)" % len(_IMG_RAW_B), prompt)
            self.assertNotIn("img-1.png (", prompt)
            _expect_files(
                self,
                second,
                {1: ("image/png", _IMG_RAW_A), 2: ("image/jpeg", _IMG_RAW_B)},
            )

    def test_hist05_hot_failure_falls_back_to_cold_with_all_files(self) -> None:
        with _ImgEnv() as env:
            env.write_scen([{"cid": _CID}, {"mode": "error"}, {"mode": "ok"}])
            turn1 = [_img_msg(_img_part("image/png", _IMG_RAW_A))]
            turn2 = turn1 + [
                _txt_msg("assistant", "ок"),
                _img_msg(_img_part("image/jpeg", _IMG_RAW_B)),
            ]
            bridge = _HttpBridge()
            try:
                _ = bridge.post(_img_body(turn1, tools=True))
                code, _body = bridge.post(_img_body(turn2, tools=True))
            finally:
                bridge.close()
            self.assertEqual(code, 200)
            recs = env.records()
            self.assertEqual(len(recs), 3)  # ход 1 + hot-попытка + cold fallback
            hot, cold = recs[1], recs[2]
            self.assertIn("--conversation", _argv_of(hot))
            self.assertNotIn("--conversation", _argv_of(cold))
            expected = {1: ("image/png", _IMG_RAW_A), 2: ("image/jpeg", _IMG_RAW_B)}
            _expect_files(self, hot, expected)
            _expect_files(self, cold, expected)
            self.assertEqual(_add_dir_of(hot), _add_dir_of(cold))
            for needle in ("[image 1]", "[image 2]", "img-1.png", "img-2.jpg"):
                self.assertIn(needle, _str(cold["prompt"]))
            self.assertEqual(env.img_dirs(), [])

    def test_hist06_no_second_spawn_after_content_was_delivered(self) -> None:
        with _ImgEnv() as env:
            env.write_scen([{"cid": _CID}, {"mode": "text_then_error"}])
            turn1 = [_img_msg(_img_part("image/png", _IMG_RAW_A))]
            turn2 = turn1 + [_txt_msg("assistant", "ок"), _txt_msg("user", "ещё")]
            bridge = _HttpBridge()
            try:
                _ = bridge.post(_img_body(turn1, tools=True))
                code, body = bridge.post(_img_body(turn2, tools=True))
            finally:
                bridge.close()
            self.assertEqual(code, 502)
            self.assertEqual(_err(body)["type"], "agy_error")
            self.assertEqual(len(env.records()), 2)
            self.assertEqual(env.img_dirs(), [])

    def test_hist07_explicit_conversation_id_and_automatic_hot_prompt_differ(
        self,
    ) -> None:
        with _ImgEnv() as env:
            history = [
                _img_msg(_img_part("image/png", _IMG_RAW_A)),
                _txt_msg("assistant", "ок"),
                _img_msg(_img_part("image/jpeg", _IMG_RAW_B)),
            ]
            explicit_cid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
            bridge = _HttpBridge()
            try:
                code, _b = bridge.post(_img_body(history, conv=explicit_cid))
                self.assertEqual(code, 200)
                _ = bridge.post(_img_body(history[:1], tools=True))
                code2, _b2 = bridge.post(_img_body(history, tools=True))
                self.assertEqual(code2, 200)
            finally:
                bridge.close()
            explicit, _first, hot = env.records()
            argv = _argv_of(explicit)
            self.assertEqual(argv[argv.index("--conversation") + 1], explicit_cid)
            expected = {1: ("image/png", _IMG_RAW_A), 2: ("image/jpeg", _IMG_RAW_B)}
            _expect_files(self, explicit, expected)
            for needle in ("[image 1]", "[image 2]", "img-1.png", "img-2.jpg"):
                self.assertIn(needle, _str(explicit["prompt"]))
            self.assertNotIn("[image 1]", _str(hot["prompt"]))
            self.assertIn("[image 2]", _str(hot["prompt"]))
            _expect_files(self, hot, expected)

    def test_hist08_plain_and_background_requests_do_not_touch_agentic_session(
        self,
    ) -> None:
        with _ImgEnv() as env:
            env.write_scen([{"cid": _CID}, {"cid": _CID_B}, {}])
            first = [_img_msg(_img_part("image/png", _IMG_RAW_A))]
            bridge = _HttpBridge()
            try:
                _ = bridge.post(_img_body(first, tools=True))
                _ = bridge.post(
                    _img_body([_img_msg(_img_part("image/jpeg", _IMG_RAW_B))])
                )
                follow = first + [
                    _txt_msg("assistant", "ок"),
                    _txt_msg("user", "дальше"),
                ]
                code, _b = bridge.post(_img_body(follow, tools=True))
            finally:
                bridge.close()
            self.assertEqual(code, 200)
            agentic1, plain, agentic2 = env.records()
            self.assertNotIn("--conversation", _argv_of(plain))
            argv = _argv_of(agentic2)
            self.assertEqual(argv[argv.index("--conversation") + 1], _CID)
            self.assertEqual(
                len({_add_dir_of(r) for r in (agentic1, plain, agentic2)}), 3
            )
            store = cast("dict[object, dict[str, object]]", _bval("_session_store"))
            self.assertEqual([entry["cid"] for entry in store.values()], [_CID])

    def test_hist09_parallel_requests_with_other_cwd_and_model_stay_separate(
        self,
    ) -> None:
        with _ImgEnv() as env:
            env.write_scen([{"sleep": 0.8, "cid": _CID}, {"sleep": 0.8, "cid": _CID_B}])
            dir_a = env.fx.tmp / "proj-a"
            dir_b = env.fx.tmp / "proj-b"
            dir_a.mkdir()
            dir_b.mkdir()
            bridge = _HttpBridge()
            results: list[int] = []

            def worker(cwd: Path, model: str, raw: bytes) -> None:
                body = _img_body(
                    [_img_msg(_img_part("image/png", raw))],
                    tools=True,
                    cwd=str(cwd),
                    model=model,
                )
                results.append(bridge.post(body)[0])

            threads = [
                threading.Thread(
                    target=worker, args=(dir_a, "gemini-4-argon", _IMG_RAW_A)
                ),
                threading.Thread(
                    target=worker,
                    args=(dir_b, "gemini-3.8-flash", _img_raw("image/png", "other")),
                ),
            ]
            try:
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(60)
            finally:
                bridge.close()
            self.assertEqual(sorted(results), [200, 200])
            recs = env.records()
            self.assertEqual(len(recs), 2)
            self.assertTrue(all("--conversation" not in _argv_of(r) for r in recs))
            self.assertEqual(
                {os.path.realpath(_str(r["cwd"])) for r in recs},
                {os.path.realpath(dir_a), os.path.realpath(dir_b)},
            )
            self.assertEqual(len({_add_dir_of(r) for r in recs}), 2)
            self.assertLess(
                max(_float(r["t0"]) for r in recs), min(_float(r["t1"]) for r in recs)
            )
            store = cast("dict[tuple[str, str, str], object]", _bval("_session_store"))
            self.assertEqual(len(store), 2)

    def test_hist10_cwd_with_spaces_and_unicode_is_not_replaced_by_image_dir(
        self,
    ) -> None:
        with _ImgEnv() as env:
            proj = env.fx.tmp / "проект с пробелом"
            proj.mkdir()
            _ = (proj / "rel.txt").write_text("project-file", encoding="utf-8")
            msgs = [_img_msg(_img_part("image/png", _IMG_RAW_A), text="файл")]
            bridge = _HttpBridge()
            try:
                code, _b = bridge.post(_img_body(msgs, cwd=str(proj)))
                code_missing, _b2 = bridge.post(
                    _img_body(msgs, cwd="/nonexistent-agy-cwd/проект")
                )
            finally:
                bridge.close()
            self.assertEqual((code, code_missing), (200, 200))
            rec, missing = env.records()
            self.assertEqual(os.path.realpath(_str(rec["cwd"])), os.path.realpath(proj))
            self.assertTrue((Path(_str(rec["cwd"])) / "rel.txt").is_file())
            argv = _argv_of(rec)
            self.assertEqual(argv.count("--add-dir"), 1)
            add_dir = _add_dir_of(rec)
            self.assertTrue(os.path.isabs(add_dir))
            ws = os.path.realpath(_str(str(_bval("WORKSPACE"))))
            self.assertTrue(os.path.realpath(add_dir).startswith(ws + os.sep))
            self.assertNotEqual(os.path.realpath(add_dir), os.path.realpath(proj))
            match = re.search(
                r"- \[image 1\] (/[^\n]+?) \(image/png, \d+ bytes\)",
                _str(rec["prompt"]),
            )
            self.assertIsNotNone(match)
            attached = Path(cast("re.Match[str]", match).group(1))
            self.assertEqual(attached.parent, Path(add_dir))
            self.assertIn(attached.name, _file_map(rec))
            self.assertEqual(os.path.realpath(_str(missing["cwd"])), ws)


class ImageLifecycleTests(unittest.TestCase):
    """AD-005: каталог изображений живёт ход, удаляется в finally, sweep (LIFE-01..05)."""

    def _assert_clean(self, env: _ImgEnv, ctx: dict[str, object]) -> None:
        self.assertFalse(os.path.exists(_str(str(ctx["img_dir"]))))
        self.assertEqual(env.active_dirs(), set())
        self.assertEqual(env.free_slots(), 4)

    def test_life01_dir_removed_on_every_terminal_path(self) -> None:
        with _ImgEnv() as env:
            msgs = [_img_msg(_img_part("image/png", _IMG_RAW_A))]
            scripted = {
                "done": [_scripted_out("done")],
                "agy_error": [_scripted_out("agy_error")],
                "client_gone": [_scripted_out("client_gone")],
            }
            for name, outs in scripted.items():
                with self.subTest(path=name):
                    _SnapRun.attempts.clear()
                    ctx = _img_ctx(msgs)
                    out = _run_once_direct(ctx, _sequence_execute(outs))
                    self.assertEqual(out["state"], name)
                    self.assertGreaterEqual(len(_SnapRun.attempts), 1)
                    for attempt in _SnapRun.attempts:
                        self.assertEqual(
                            _dict(attempt["files"])["img-1.png"],
                            {"sha": _sha_hex(_IMG_RAW_A), "mode": 0o600},
                        )
                    self._assert_clean(env, ctx)
            with self.subTest(path="exception"):
                _SnapRun.attempts.clear()
                ctx = _img_ctx(msgs)

                def boom(_self: object, _run: object, *_a: object) -> dict[str, object]:
                    raise RuntimeError("boom")

                with self.assertRaises(RuntimeError):
                    _ = _run_once_direct(ctx, boom)
                self.assertEqual(len(_SnapRun.attempts), 1)
                self._assert_clean(env, ctx)
            with self.subTest(path="launcher_unavailable"):
                _SnapRun.attempts.clear()
                ctx = _img_ctx(msgs)
                unavailable = cast("type[Exception]", _bval("LauncherUnavailable"))

                def missing() -> str:
                    raise unavailable("x")

                with (
                    mock.patch.object(_bridge(), "_launcher", missing),
                    mock.patch.object(_bridge(), "Run", _SnapRun),
                    _Sock() as sock,
                ):
                    handler = cast(object, _make_handler(sock))
                    setattr(handler, "client_address", ("127.0.0.1", 1))
                    out = _dict(
                        _ofn(handler, "_run_once")(
                            ctx, _text_sink, _tool_sink, _text_sink, None
                        )
                    )
                self.assertEqual(out["state"], "launcher_unavailable")
                self.assertEqual(_SnapRun.attempts, [])
                self._assert_clean(env, ctx)

    def test_life02_retry_and_hot_cold_fallback_reuse_one_directory(self) -> None:
        with _ImgEnv() as env:
            msgs = [
                _img_msg(_img_part("image/png", _IMG_RAW_A)),
                _txt_msg("assistant", "ок"),
                _img_msg(_img_part("image/jpeg", _IMG_RAW_B)),
            ]
            variants: dict[str, dict[str, object]] = {
                "transient_retry": {},
                "hot_to_cold": {
                    "hot_resumed": True,
                    "conversation_id": _CID,
                    "sess_key": ("gemini-4-argon", "", "low"),
                    "turn_id": "turn-life02",
                },
            }
            for name, over in variants.items():
                with self.subTest(variant=name):
                    _SnapRun.attempts.clear()
                    ctx = _img_ctx(msgs, over=over)
                    out = _run_once_direct(
                        ctx,
                        _sequence_execute(
                            [_scripted_out("agy_error"), _scripted_out("done")]
                        ),
                    )
                    self.assertEqual(out["state"], "done")
                    self.assertEqual(len(_SnapRun.attempts), 2)
                    first, second = _SnapRun.attempts
                    self.assertEqual(first["add_dir"], second["add_dir"])
                    self.assertEqual(first["files"], second["files"])
                    self.assertEqual(
                        set(_dict(second["files"])), {"img-1.png", "img-2.jpg"}
                    )
                    self._assert_clean(env, ctx)

    def test_life03_spool_failure_returns_500_and_leaves_no_directory(self) -> None:
        with _ImgEnv() as env:
            real_open = os.open
            created: list[str] = []

            def failing_open(
                path: str, flags: int, mode: int = 0o777, **kw: int
            ) -> int:
                if str(path).endswith("img-2.png"):
                    raise OSError(28, "No space left on device")
                if str(path).endswith(".png"):
                    created.append(str(path))
                return real_open(path, flags, mode, **kw)

            msgs = [_img_msg(_png_part("one"), _png_part("two"), text="две")]
            bridge = _HttpBridge()
            buffer = io.StringIO()
            try:
                with (
                    mock.patch.object(os, "open", failing_open),
                    mock.patch.object(sys, "stderr", buffer),
                ):
                    code, body = bridge.post(_img_body(msgs))
            finally:
                bridge.close()
            self.assertEqual(code, 500)
            self.assertEqual(
                _err(body),
                {
                    "message": "image spool failed",
                    "type": "image_spool_error",
                    "code": 500,
                },
            )
            self.assertEqual(len(created), 1)  # img-1.png успел записаться, затем откат
            self.assertEqual(env.records(), [])  # spawn не было
            self.assertEqual(env.img_dirs(), [])
            self.assertEqual(env.active_dirs(), set())
            self.assertEqual(env.free_slots(), 4)
            log = buffer.getvalue()
            self.assertIn("image_spool_error model=gemini-4-argon err=OSError", log)
            self.assertNotIn(
                base64.b64encode(_img_raw("image/png", "one")).decode("ascii"), log
            )

    def test_life04_parallel_turns_never_touch_each_others_directory(self) -> None:
        with _ImgEnv() as env:
            ctx_a = _img_ctx([_img_msg(_png_part("turn-a"))])
            ctx_b = _img_ctx([_img_msg(_png_part("turn-b"))])
            dir_a = _str(str(ctx_a["img_dir"]))
            dir_b = _str(str(ctx_b["img_dir"]))
            self.assertNotEqual(dir_a, dir_b)
            entered = threading.Event()
            gate = threading.Event()

            def execute(_self: object, run: object, *_a: object) -> dict[str, object]:
                if _str(str(_oval(run, "add_dir"))) == dir_a:
                    entered.set()
                    _ = gate.wait(20)
                return _scripted_out("done")

            outs: dict[str, dict[str, object]] = {}
            with contextlib.ExitStack() as stack:
                _ = stack.enter_context(mock.patch.object(_bridge(), "Run", _SnapRun))
                _ = stack.enter_context(
                    mock.patch.object(_bridge(), "_launcher", _fake_launcher_path)
                )
                _ = stack.enter_context(
                    mock.patch.object(_bval("Handler"), "_execute", execute)
                )

                def run_a() -> None:
                    with _Sock() as sock:
                        handler = cast(object, _make_handler(sock))
                        setattr(handler, "client_address", ("127.0.0.1", 1))
                        outs["a"] = _dict(
                            _ofn(handler, "_run_once")(
                                ctx_a, _text_sink, _tool_sink, _text_sink, None
                            )
                        )

                thread = threading.Thread(target=run_a)
                thread.start()
                self.assertTrue(entered.wait(20))
                with _Sock() as sock:
                    handler = cast(object, _make_handler(sock))
                    setattr(handler, "client_address", ("127.0.0.1", 2))
                    outs["b"] = _dict(
                        _ofn(handler, "_run_once")(
                            ctx_b, _text_sink, _tool_sink, _text_sink, None
                        )
                    )
                self.assertFalse(os.path.exists(dir_b))
                self.assertEqual(env.active_dirs(), {dir_a})
                self.assertEqual(
                    Path(dir_a, "img-1.png").read_bytes(),
                    _img_raw("image/png", "turn-a"),
                )
                gate.set()
                thread.join(20)
            self.assertEqual((outs["a"]["state"], outs["b"]["state"]), ("done", "done"))
            self.assertFalse(os.path.exists(dir_a))
            self.assertEqual(env.active_dirs(), set())

    def test_life05_sweep_removes_only_stale_orphans(self) -> None:
        with _ImgEnv() as env:
            ws = Path(_str(str(_bval("WORKSPACE"))))
            ws.mkdir(parents=True, exist_ok=True)
            now = 1_700_000_000.0

            def make(name: str, age: float) -> Path:
                path = ws / name
                path.mkdir()
                _ = (path / "f.bin").write_bytes(b"x")
                os.utime(path, (now - age, now - age))
                return path

            stale = make("img-stale", 3601)
            exact = make("img-exact", 3600)
            fresh = make("img-fresh", 10)
            active = make("img-active", 7200)
            old_run = make("run-old", 7200)
            other = make("keep-me", 7200)
            outside = env.fx.tmp / "outside-target"
            outside.mkdir()
            _ = (outside / "secret.txt").write_text("keep", encoding="utf-8")
            os.utime(outside, (now - 9999, now - 9999))
            link = ws / "img-link"
            link.symlink_to(outside, target_is_directory=True)
            registry = cast("set[str]", _bval("_active_img_dirs"))
            registry.add(str(active))
            try:
                with mock.patch.object(time, "time", lambda: now):
                    removed = _bfn("_sweep_workspace")()
            finally:
                registry.discard(str(active))
            self.assertEqual(removed, 1)
            self.assertFalse(stale.exists())
            self.assertFalse(old_run.exists())
            for survivor in (exact, fresh, active, other):
                self.assertTrue(survivor.exists(), survivor.name)
            self.assertTrue(link.is_symlink())
            self.assertTrue((outside / "secret.txt").is_file())


_LOG_REASONS = (
    "image_input_not_supported",
    "unsupported_reasoning_effort",
    "invalid_reasoning_effort",
    "unsupported_image_type",
    "invalid_image_content",
    "invalid_image_base64",
    "image_url_not_allowed",
    "image_type_mismatch",
    "image_proof_invalid",
    "images_too_large",
    "image_too_large",
    "too_many_images",
    "image_spool_error",
    "image_cleanup_error",
    "image_sweep_removed",
)


class ImageLogTests(unittest.TestCase):
    """AD-006: reason видны дословно, секреты и payload в журнал не попадают (LOG-01/02)."""

    def test_log01_every_reason_is_verbatim_and_masking_stays_strict(self) -> None:
        with _ImgEnv():
            with _Sock() as sock:
                handler = cast(object, _make_handler(sock))
                setattr(handler, "client_address", ("127.0.0.1", 1))
                for token in _LOG_REASONS:
                    with self.subTest(reason=token):
                        buffer = io.StringIO()
                        with mock.patch.object(sys, "stderr", buffer):
                            _ = _ofn(handler, "_log_reject")(
                                token, "gemini-4-argon", 14
                            )
                        pattern = (
                            r"^\[agy-bridge\] \d\d:\d\d:\d\d reject reason=%s " % token
                            + r"model=gemini-4-argon model_len=14 client=127.0.0.1:1$"
                        )
                        self.assertRegex(buffer.getvalue().strip(), pattern)
                buffer = io.StringIO()
                with mock.patch.object(sys, "stderr", buffer):
                    _ = _ofn(handler, "_log_reject")(
                        "image_input_not_supportedXY", "m", 1
                    )
                    _ = _ofn(handler, "_log_reject")(
                        "abcdefghijklmnopqrstuvwxyz012345", "m", 1
                    )
                text = buffer.getvalue()
                self.assertNotIn("not_supportedXY", text)
                self.assertNotIn("abcdefghijklmnopqrstuvwxyz012345", text)
                self.assertEqual(text.count("reason=***"), 2)

    def test_log01_http_proof_and_effort_rejects_are_visible(self) -> None:
        with _ImgEnv() as env:
            msgs = [_img_msg(_png_part("log"))]
            bridge = _HttpBridge()
            buffer = io.StringIO()
            try:
                with mock.patch.object(sys, "stderr", buffer):
                    with mock.patch.dict(
                        _proof_of("gemini-4-argon"), {"agy_binary_sha256": "0" * 64}
                    ):
                        code1, body1 = bridge.post(_img_body(msgs))
                    with mock.patch.dict(
                        _proof_of("gemini-4-argon"), {"efforts_proven": ["low"]}
                    ):
                        body = _img_body(msgs)
                        body["reasoning_effort"] = "high"
                        code2, body2 = bridge.post(body)
            finally:
                bridge.close()
            self.assertEqual((code1, code2), (400, 400))
            self.assertEqual(_err(body1)["type"], "image_input_not_supported")
            self.assertEqual(_err(body2)["type"], "unsupported_reasoning_effort")
            log = buffer.getvalue()
            self.assertIn(
                "image_proof_invalid model=gemini-4-argon reason=binary_sha_mismatch",
                log,
            )
            self.assertRegex(
                log,
                r"reject reason=image_input_not_supported model=gemini-4-argon model_len=14 client=",
            )
            self.assertRegex(
                log,
                r"reject reason=unsupported_reasoning_effort model=gemini-4-argon model_len=14 client=",
            )
            self.assertEqual(env.records(), [])

    def test_log02_auth_key_and_image_payload_never_reach_the_log(self) -> None:
        with _ImgEnv() as env:
            marker_raw = _IMG_MAGIC["image/jpeg"] + b"SECRET-PAYLOAD-MARKER-" * 8
            marker_b64 = base64.b64encode(marker_raw).decode("ascii")
            bad = _img_msg(
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64," + marker_b64},
                }
            )
            good = _img_msg(
                _img_part("image/png", _img_raw("image/png", "SECRET-OK-MARKER-" * 8))
            )
            bridge = _HttpBridge()
            buffer = io.StringIO()
            try:
                with mock.patch.object(sys, "stderr", buffer):
                    code_bad, _b = bridge.post(_img_body([bad]))
                    code_ok, _b2 = bridge.post(_img_body([good]))
            finally:
                bridge.close()
            self.assertEqual((code_bad, code_ok), (400, 200))
            log = buffer.getvalue()
            self.assertIn("reject reason=image_type_mismatch", log)
            self.assertNotIn(_str(_bval("AUTH_KEY")), log)
            self.assertNotIn(marker_b64, log)
            self.assertNotIn(marker_b64[:40], log)
            self.assertNotIn("SECRET-PAYLOAD-MARKER", log)
            self.assertNotIn(
                base64.b64encode(b"SECRET-OK-MARKER-").decode("ascii")[:16], log
            )
            self.assertEqual(len(env.records()), 1)


class ImageResourceTests(unittest.TestCase):
    """REQ-009/F-002/F-005: слоты, FD, повторная проверка после очереди, отказ без деградации."""

    def test_res01_concurrent_turns_bounded_by_slots_without_fd_or_dir_leaks(
        self,
    ) -> None:
        with _ImgEnv() as env:
            env.fx.patch("_slots", threading.BoundedSemaphore(2))
            env.write_scen([{"sleep": 0.5}])
            bridge = _HttpBridge()
            codes: list[int] = []
            sampled: list[int] = []
            stop = threading.Event()

            def sampler() -> None:
                while not stop.is_set():
                    sampled.append(len(env.img_dirs()))
                    time.sleep(0.02)

            def worker(n: int) -> None:
                parts = [_png_part("r%da" % n), _png_part("r%db" % n)]
                codes.append(
                    bridge.post(_img_body([_img_msg(*parts, text="req-%d" % n)]))[0]
                )

            watcher = threading.Thread(target=sampler)
            threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
            fd_before = _open_fds()
            try:
                watcher.start()
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(120)
            finally:
                stop.set()
                watcher.join(10)
                bridge.close()
            self.assertEqual(codes, [200] * 8)
            self.assertLessEqual(
                max(sampled), 2
            )  # каталоги только у ходов, занявших слот
            recs = env.records()
            self.assertEqual(len(recs), 8)
            events = sorted(
                [(_float(r["t0"]), 1) for r in recs]
                + [(_float(r["t1"]), -1) for r in recs]
            )
            running = peak = 0
            for _t, delta in events:
                running += delta
                peak = max(peak, running)
            self.assertLessEqual(peak, 2)
            for rec in recs:
                found = re.search(r"req-(\d+)", _str(rec["prompt"]))
                self.assertIsNotNone(found)
                number = int(cast("re.Match[str]", found).group(1))
                expected = {
                    1: ("image/png", _img_raw("image/png", "r%da" % number)),
                    2: ("image/png", _img_raw("image/png", "r%db" % number)),
                }
                _expect_files(self, rec, expected)
            self.assertEqual(len({_add_dir_of(r) for r in recs}), 8)
            self.assertEqual(env.img_dirs(), [])
            self.assertEqual(env.active_dirs(), set())
            self.assertEqual(env.free_slots(), 2)
            deadline = time.monotonic() + 5
            while _open_fds() > fd_before and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertLessEqual(_open_fds(), fd_before)

    def test_res02_disabled_or_unproven_image_path_leaves_text_untouched(self) -> None:
        with _ImgEnv() as env:
            bridge = _HttpBridge()
            try:
                env.flag(False)
                code, body = bridge.post(_img_body([_img_msg(_png_part("a"))]))
                self.assertEqual(
                    (code, _err(body)["type"]), (400, "image_input_not_supported")
                )
                self.assertEqual((env.records(), env.img_dirs()), ([], []))
                health = bridge.get("/health")[1]
                self.assertEqual(
                    (health["images"], health["image_input_mode"]), (False, "disabled")
                )
                text_code, _b = bridge.post(
                    _img_body([_txt_msg("user", "просто текст")])
                )
                self.assertEqual(text_code, 200)
                sse = _sse_post(
                    bridge.port, _img_body([_txt_msg("user", "поток")], stream=True)
                )
                self.assertIn("ответ", sse)
                self.assertIn("data: [DONE]", sse)
                env.flag(True)
                health = bridge.get("/health")[1]
                self.assertEqual(
                    (health["images"], health["image_input_mode"]), (True, "enabled")
                )
                before = len(env.records())
                with (
                    mock.patch.dict(
                        _proof_of("gemini-4-argon"), {"agy_binary_sha256": "f" * 64}
                    ),
                    mock.patch.dict(
                        _proof_of("gemini-3.8-flash"), {"agy_binary_sha256": "f" * 64}
                    ),
                ):
                    health = bridge.get("/health")[1]
                    self.assertEqual(health["images"], False)
                    code2, body2 = bridge.post(_img_body([_img_msg(_png_part("b"))]))
                    self.assertEqual(
                        (code2, _err(body2)["type"]), (400, "image_input_not_supported")
                    )
                    text2, _b2 = bridge.post(
                        _img_body([_txt_msg("user", "текст при чужом бинаре")])
                    )
                    self.assertEqual(text2, 200)
                self.assertEqual(len(env.records()), before + 1)
                self.assertEqual(env.img_dirs(), [])
            finally:
                bridge.close()

    def test_res03_at_most_two_attempts_and_retry_budget_is_respected(self) -> None:
        with _ImgEnv() as env:
            msgs = [_img_msg(_png_part("retry"))]
            for budget, expected in ((30, 2), (0, 1)):
                with self.subTest(budget_tenths=budget):
                    _SnapRun.attempts.clear()
                    setattr(_bridge(), "_retry_tenths", budget)
                    ctx = _img_ctx(msgs)
                    out = _run_once_direct(
                        ctx, _sequence_execute([_scripted_out("agy_error")])
                    )
                    self.assertEqual(out["state"], "agy_error")
                    self.assertEqual(len(_SnapRun.attempts), expected)
                    self.assertFalse(os.path.exists(_str(str(ctx["img_dir"]))))
            self.assertEqual(env.free_slots(), 4)

    def test_f002_flag_and_proof_are_rechecked_after_waiting_for_a_slot(self) -> None:
        with _ImgEnv() as env:
            handler_cls = _bval("Handler")
            real_acquire = cast(
                Callable[..., str], getattr(handler_cls, "_acquire_slot")
            )
            real_mkdir = os.mkdir
            mkdirs: list[str] = []
            flips: list[Callable[[], None]] = []

            def acquire_then_flip(self: object, keepalive: object) -> str:
                result = real_acquire(self, keepalive)
                flips.pop(0)()
                return result

            def spy_mkdir(path: str, mode: int = 0o777, **kw: int) -> None:
                if "img-" in str(path):
                    mkdirs.append(str(path))
                real_mkdir(path, mode, **kw)

            def disable_flag() -> None:
                env.fx.set_env("AGY_IMAGE_INPUT_ENABLED", "0")

            def break_proof() -> None:
                env.fx.set_env("AGY_IMAGE_INPUT_ENABLED", None)
                _proof_of("gemini-4-argon")["agy_binary_sha256"] = "e" * 64

            bridge = _HttpBridge()
            buffer = io.StringIO()
            try:
                with (
                    mock.patch.object(handler_cls, "_acquire_slot", acquire_then_flip),
                    mock.patch.object(os, "mkdir", spy_mkdir),
                    mock.patch.object(sys, "stderr", buffer),
                ):
                    for flip in (disable_flag, break_proof):
                        env.fx.set_env("AGY_IMAGE_INPUT_ENABLED", None)
                        flips.append(flip)
                        code, body = bridge.post(
                            _img_body([_img_msg(_png_part("late"))])
                        )
                        self.assertEqual(
                            (code, _err(body)["type"]),
                            (400, "image_input_not_supported"),
                        )
            finally:
                bridge.close()
            self.assertEqual(mkdirs, [])
            self.assertEqual(env.records(), [])
            self.assertEqual(env.img_dirs(), [])
            self.assertEqual(env.free_slots(), 4)
            self.assertIn(
                "image_proof_invalid model=gemini-4-argon reason=binary_sha_mismatch",
                buffer.getvalue(),
            )

    def test_f001_flag_defaults_false_and_follows_env_then_strict_config(self) -> None:
        with _ImgEnv() as env:
            is_enabled = _bfn("_is_image_input_enabled")
            env.flag(None)
            self.assertIs(is_enabled(), False)  # код по умолчанию fail-closed
            for raw, expected in (
                ("0", False),
                ("off", False),
                ("1", True),
                ("yes", True),
                ("maybe", False),
            ):
                with self.subTest(env=raw):
                    env.fx.set_env("AGY_IMAGE_INPUT_ENABLED", raw)
                    self.assertIs(is_enabled(), expected)
            env.fx.set_env("AGY_IMAGE_INPUT_ENABLED", None)
            payloads = {
                "true": ('{"IMAGE_INPUT_ENABLED": true}', True),
                "string": ('{"IMAGE_INPUT_ENABLED": "true"}', False),
                "int": ('{"IMAGE_INPUT_ENABLED": 1}', False),
                "other_key": ('{"SQLITE_REASONING_ENABLED": true}', False),
                "list": ("[true]", False),
                "corrupt": ("{not json", False),
                "huge": (
                    '{"IMAGE_INPUT_ENABLED": true, "pad": "' + "x" * 70000 + '"}',
                    False,
                ),
            }
            for name, (text, expected) in payloads.items():
                with self.subTest(config=name):
                    _ = env.fx.config.write_text(text, encoding="utf-8")
                    setattr(_bridge(), "_image_flag_cache", (0.0, False))
                    self.assertIs(is_enabled(), expected)
            _ = env.fx.config.write_text(
                '{"IMAGE_INPUT_ENABLED": true}', encoding="utf-8"
            )
            setattr(_bridge(), "_image_flag_cache", (0.0, False))
            self.assertIs(is_enabled(), True)
            _ = env.fx.config.write_text(
                '{"IMAGE_INPUT_ENABLED": false}', encoding="utf-8"
            )
            self.assertIs(is_enabled(), True)  # кэш TTL 1.0 с ещё действует
            setattr(_bridge(), "_image_flag_cache", (0.0, False))
            self.assertIs(is_enabled(), False)
            _ = env.fx.config.write_text(
                json.dumps(
                    {"SQLITE_REASONING_ENABLED": True, "IMAGE_INPUT_ENABLED": False}
                ),
                encoding="utf-8",
            )
            setattr(_bridge(), "_image_flag_cache", (0.0, False))
            self.assertIs(is_enabled(), False)  # SQLite-флаг image-вход не включает


_UNSUPPORTED_MODELS = (
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.1-pro",
    "gpt-oss-120b",
)


def _bad_url_msg(url: object) -> list[dict[str, object]]:
    return [_img_msg({"type": "image_url", "image_url": {"url": url}})]


def _taxonomy_cases(
    cap: int,
) -> list[tuple[str, str, Callable[[], list[dict[str, object]]]]]:
    png = _img_raw("image/png", "ok")
    ok_b64 = base64.b64encode(png).decode("ascii")

    def data(mime: str, raw: bytes) -> list[dict[str, object]]:
        return [_img_msg(_img_part(mime, raw))]

    def assistant_image() -> list[dict[str, object]]:
        return [_img_msg(_png_part("role"), role="assistant")]

    def string_image_url() -> list[dict[str, object]]:
        return [
            _img_msg({"type": "image_url", "image_url": _img_url("image/png", png)})
        ]

    return [
        (
            "remote_http",
            "image_url_not_allowed",
            lambda: _bad_url_msg("http://example.test/a.png"),
        ),
        (
            "remote_https",
            "image_url_not_allowed",
            lambda: _bad_url_msg("https://example.test/a.png"),
        ),
        (
            "file_url",
            "image_url_not_allowed",
            lambda: _bad_url_msg("file:///etc/passwd"),
        ),
        ("relative_path", "image_url_not_allowed", lambda: _bad_url_msg("img/a.png")),
        (
            "bmp_mime",
            "unsupported_image_type",
            lambda: _bad_url_msg("data:image/bmp;base64," + ok_b64),
        ),
        (
            "unknown_magic",
            "unsupported_image_type",
            lambda: data("image/png", b"not-an-image-at-all"),
        ),
        (
            "bad_alphabet",
            "invalid_image_base64",
            lambda: _bad_url_msg("data:image/png;base64,@@@@"),
        ),
        (
            "empty_payload",
            "invalid_image_base64",
            lambda: _bad_url_msg("data:image/png;base64,"),
        ),
        (
            "bad_padding",
            "invalid_image_base64",
            lambda: _bad_url_msg("data:image/png;base64,abc"),
        ),
        (
            "png_as_jpeg",
            "image_type_mismatch",
            lambda: data("image/png", _img_raw("image/jpeg")),
        ),
        (
            "gif_as_webp",
            "image_type_mismatch",
            lambda: data("image/webp", _img_raw("image/gif")),
        ),
        ("string_image_url", "invalid_image_content", string_image_url),
        (
            "url_missing",
            "invalid_image_content",
            lambda: [_img_msg({"type": "image_url", "image_url": {}})],
        ),
        ("url_not_string", "invalid_image_content", lambda: _bad_url_msg(42)),
        (
            "no_comma",
            "invalid_image_content",
            lambda: _bad_url_msg("data:image/png;base64"),
        ),
        (
            "no_base64_param",
            "invalid_image_content",
            lambda: _bad_url_msg("data:image/png," + ok_b64),
        ),
        ("assistant_role", "invalid_image_content", assistant_image),
        (
            "too_many",
            "too_many_images",
            lambda: [_img_msg(*[_png_part("t%d" % i) for i in range(17)])],
        ),
        (
            "one_byte_over",
            "image_too_large",
            lambda: data("image/png", _img_raw("image/png", "b", size=cap + 1)),
        ),
        (
            "sum_over",
            "images_too_large",
            lambda: [
                _img_msg(
                    _img_part("image/png", _img_raw("image/png", "a", size=cap // 2)),
                    _img_part(
                        "image/jpeg", _img_raw("image/jpeg", "b", size=cap // 2 + 1)
                    ),
                )
            ],
        ),
    ]


class AcceptanceOracleTests(unittest.TestCase):
    """AC-001..AC-010: приёмочные оракулы image-входа на уровне HTTP-обработчика (L1/L2)."""

    def test_ao01_target_models_accept_images_unsupported_and_flag_off_reject(
        self,
    ) -> None:
        with _ImgEnv() as env:
            bridge = _HttpBridge()
            try:
                for model in _IMG_TARGETS:
                    with self.subTest(model=model):
                        before = len(env.records())
                        code, _b = bridge.post(
                            _img_body([_img_msg(_png_part(model))], model=model)
                        )
                        self.assertEqual(code, 200)
                        rec = env.records()[before]
                        self.assertIn("--add-dir", _argv_of(rec))
                        self.assertEqual(set(_file_map(rec)), {"img-1.png"})
                listing = _get_auth(bridge.port, "/v1/models")
                flags = {
                    _str(_dict(m)["id"]): _dict(m)["images"]
                    for m in cast("list[object]", listing["data"])
                }
                self.assertEqual(
                    {mid for mid, on in flags.items() if on}, set(_IMG_TARGETS)
                )
                self.assertIs(listing["images"], True)
                self.assertIs(bridge.get("/health")[1]["images"], True)
                spawned = len(env.records())
                for model in _UNSUPPORTED_MODELS:
                    with self.subTest(unsupported=model):
                        code, body = bridge.post(
                            _img_body([_img_msg(_png_part("u"))], model=model)
                        )
                        self.assertEqual(code, 400)
                        self.assertEqual(
                            _err(body),
                            {
                                "message": "image rejected: image_input_not_supported",
                                "type": "image_input_not_supported",
                                "code": 400,
                            },
                        )
                self.assertEqual(len(env.records()), spawned)
                env.fx.set_env("AGY_IMAGE_INPUT_ENABLED", "0")
                code_off, body_off = bridge.post(
                    _img_body([_img_msg(_png_part("off"))])
                )
                self.assertEqual(
                    (code_off, _err(body_off)["type"]),
                    (400, "image_input_not_supported"),
                )
                code_text, _bt = bridge.post(
                    _img_body([_txt_msg("user", "текст при выключенном флаге")])
                )
                self.assertEqual(code_text, 200)
                self.assertEqual(len(env.records()), spawned + 1)
                env.fx.set_env("AGY_IMAGE_INPUT_ENABLED", None)
                env.flag(False)
                code_cfg, _bc = bridge.post(_img_body([_img_msg(_png_part("cfg"))]))
                self.assertEqual(code_cfg, 400)
            finally:
                bridge.close()

    def test_ao02_mixed_formats_sixteen_accepted_and_seventeen_rejected_over_http(
        self,
    ) -> None:
        with _ImgEnv() as env:
            seq = [
                (_IMG_MIMES[i % 4], _img_raw(_IMG_MIMES[i % 4], "h%d" % i))
                for i in range(16)
            ]
            bridge = _HttpBridge()
            try:
                code, _b = bridge.post(
                    _img_body([_img_msg(*[_img_part(m, r) for m, r in seq])])
                )
                self.assertEqual(code, 200)
                code17, body17 = bridge.post(
                    _img_body([_img_msg(*[_png_part("x%d" % i) for i in range(17)])])
                )
            finally:
                bridge.close()
            self.assertEqual((code17, _err(body17)["type"]), (400, "too_many_images"))
            rec = env.records()[0]
            _expect_files(self, rec, {n: seq[n - 1] for n in range(1, 17)})
            self.assertEqual(len(env.records()), 1)

    def test_ao03_every_reject_reason_is_400_before_spool_and_spawn(self) -> None:
        with (
            _ImgEnv() as env,
            _small_limits(max_image_bytes=1000, max_total_image_bytes=1000),
        ):
            bridge = _HttpBridge()
            try:
                for name, reason, build in _taxonomy_cases(1000):
                    with self.subTest(case=name):
                        code, body = bridge.post(_img_body(build()))
                        self.assertEqual(code, 400)
                        self.assertEqual(
                            _err(body),
                            {
                                "message": "image rejected: " + reason,
                                "type": reason,
                                "code": 400,
                            },
                        )
                code, body = bridge.post(
                    _img_body([_img_msg(_png_part("g"))], model="gpt-oss-120b")
                )
                self.assertEqual(_err(body)["type"], "image_input_not_supported")
                self.assertEqual((env.records(), env.img_dirs()), ([], []))
                with mock.patch.dict(_proof_of("gemini-4-argon"), {"impl_version": 99}):
                    code_p, body_p = bridge.post(_img_body([_img_msg(_png_part("p"))]))
                    code_t, _bt = bridge.post(_img_body([_txt_msg("user", "текст")]))
                self.assertEqual(
                    (code_p, _err(body_p)["type"], code_t),
                    (400, "image_input_not_supported", 200),
                )
            finally:
                bridge.close()
            self.assertEqual(
                len(env.records()), 1
            )  # только текстовый ход дошёл до spawn

    def test_ao04_global_numbering_for_cold_hot_and_fallback_prompts(self) -> None:
        with _ImgEnv():
            msgs = [
                _img_msg(
                    _img_part("image/png", _IMG_RAW_A),
                    _img_part("image/jpeg", _IMG_RAW_B),
                ),
                _txt_msg("assistant", "ок"),
                _img_msg(_img_part("image/gif", _IMG_RAW_C), text="новая"),
            ]
            images = _collect(msgs)
            full = _str(_bfn("_messages_to_prompt")(msgs, images))
            resumed = _str(_bfn("_get_resumed_turn_prompt")(msgs, images))
            for n in (1, 2, 3):
                self.assertIn("[image %d]" % n, full)
            self.assertEqual(full.count("- [image "), 3)
            self.assertIn("[image 3]", resumed)
            self.assertNotIn("[image 1]", resumed)
            self.assertNotIn("[image 2]", resumed)
            self.assertEqual(resumed.count("- [image "), 1)
            self.assertIn("img-3.gif (image/gif, %d bytes)" % len(_IMG_RAW_C), resumed)
            followup = msgs + [
                _txt_msg("assistant", "ещё"),
                _txt_msg("user", "просто текст"),
            ]
            images2 = _collect(followup)
            self.assertEqual([_int(i["index"]) for i in images2], [1, 2, 3])
            hot = _str(_bfn("_get_resumed_turn_prompt")(followup, images2))
            self.assertNotIn("[attachments]", hot)
            self.assertNotIn("[image", hot)
            self.assertIn("просто текст", hot)
            self.assertEqual(
                _str(_bfn("_get_resumed_turn_prompt")(msgs[:1], images[:2])),
                _str(_bfn("_messages_to_prompt")(msgs[:1], images[:2])),
            )

    def test_ao05_cwd_session_key_and_add_dir_argv(self) -> None:
        with _ImgEnv() as env:
            cwd = env.fx.tmp / "каталог с пробелом"
            cwd.mkdir()
            bridge = _HttpBridge()
            try:
                code, _b = bridge.post(
                    _img_body([_img_msg(_png_part("cwd"))], tools=True, cwd=str(cwd))
                )
            finally:
                bridge.close()
            self.assertEqual(code, 200)
            rec = env.records()[0]
            argv = _argv_of(rec)
            self.assertEqual(os.path.realpath(_str(rec["cwd"])), os.path.realpath(cwd))
            self.assertEqual(argv.count("--add-dir"), 1)
            self.assertNotEqual(
                os.path.realpath(_add_dir_of(rec)), os.path.realpath(cwd)
            )
            for flag in ("--dangerously-skip-permissions", "--model", "--effort"):
                self.assertIn(flag, argv)
            store = cast("dict[tuple[str, str, str], object]", _bval("_session_store"))
            self.assertEqual(list(store), [("gemini-4-argon", str(cwd), "high")])

    def test_ao06_modes_during_turn_and_cleanup_after_success_and_error(self) -> None:
        with _ImgEnv() as env:
            env.write_scen([{}, {"mode": "error"}])
            bridge = _HttpBridge()
            try:
                code_ok, _b = bridge.post(_img_body([_img_msg(_png_part("ok"))]))
                code_err, body_err = bridge.post(
                    _img_body([_img_msg(_png_part("fail"))])
                )
            finally:
                bridge.close()
            self.assertEqual((code_ok, code_err), (200, 502))
            self.assertEqual(_err(body_err)["type"], "agy_error")
            recs = env.records()
            self.assertGreaterEqual(len(recs), 2)
            for rec in recs:
                self.assertEqual(rec["dir_mode"], 0o700)
                self.assertTrue(
                    all(info["mode"] == 0o600 for info in _file_map(rec).values())
                )
            self.assertEqual(env.img_dirs(), [])
            self.assertEqual(env.active_dirs(), set())

    def test_ao07_reject_lines_follow_the_strict_template(self) -> None:
        with _ImgEnv():
            bridge = _HttpBridge()
            buffer = io.StringIO()
            try:
                with mock.patch.object(sys, "stderr", buffer):
                    for _name, _reason, build in _taxonomy_cases(1000)[:12]:
                        _ = bridge.post(_img_body(build()))
            finally:
                bridge.close()
            lines = [
                ln for ln in buffer.getvalue().splitlines() if " reject reason=" in ln
            ]
            self.assertGreaterEqual(len(lines), 12)
            for line in lines:
                self.assertRegex(
                    line,
                    r"^\[agy-bridge\] \d\d:\d\d:\d\d reject reason=[a-z0-9_]+ model=gemini-4-argon model_len=14 client=127\.0\.0\.1:\d+$",
                )
                self.assertNotIn("reason=***", line)

    def test_ao08_directory_is_registered_before_mkdir_and_survives_sweep(self) -> None:
        with _ImgEnv() as env:
            env.write_scen([{"sleep": 1.0}])
            real_mkdir = os.mkdir
            observed: list[bool] = []

            def spy_mkdir(path: str, mode: int = 0o777, **kw: int) -> None:
                if os.path.basename(str(path)).startswith("img-"):
                    observed.append(
                        str(path) in cast("set[str]", _bval("_active_img_dirs"))
                    )
                real_mkdir(path, mode, **kw)

            bridge = _HttpBridge()
            results: list[int] = []
            with mock.patch.object(os, "mkdir", spy_mkdir):
                thread = threading.Thread(
                    target=lambda: results.append(
                        bridge.post(_img_body([_img_msg(_png_part("sw"))]))[0]
                    )
                )
                try:
                    thread.start()
                    deadline = time.monotonic() + 30
                    while not env.records() and time.monotonic() < deadline:
                        time.sleep(0.02)
                    dirs = env.img_dirs()
                    self.assertEqual(len(dirs), 1)
                    removed = _bfn("_sweep_workspace")(
                        -1.0
                    )  # всё «старше» отсечки, кроме активного
                    self.assertEqual(removed, 0)
                    self.assertTrue(dirs[0].is_dir())
                    thread.join(60)
                finally:
                    bridge.close()
            self.assertEqual(results, [200])
            self.assertEqual(observed, [True])
            self.assertEqual(env.img_dirs(), [])

    def test_ao09_delivered_reasoning_is_never_retried_with_images(self) -> None:
        with _ImgEnv() as env:
            msgs = [_img_msg(_png_part("rs"))]
            for hot in (False, True):
                with self.subTest(hot=hot):
                    _SnapRun.attempts.clear()
                    over: dict[str, object] = {"stream": True}
                    if hot:
                        over.update(
                            hot_resumed=True,
                            conversation_id=_CID,
                            sess_key=("gemini-4-argon", "", "low"),
                            turn_id="turn-ao09",
                        )
                    ctx = _img_ctx(msgs, over=over)
                    out = _run_once_direct(
                        ctx,
                        _sequence_execute(
                            [_scripted_out("agy_error", reasoning="мышление")]
                        ),
                    )
                    self.assertEqual(out["state"], "agy_error")
                    self.assertEqual(len(_SnapRun.attempts), 1)
                    self.assertFalse(os.path.exists(_str(str(ctx["img_dir"]))))
            bridge = _HttpBridge()
            try:
                health = bridge.get("/health")[1]
            finally:
                bridge.close()
            for key in (
                "ok",
                "transport",
                "native_tools",
                "hot_sessions",
                "max_concurrent",
                "images",
                "sqlite_reasoning_mode",
            ):
                self.assertIn(key, health)
            self.assertEqual(env.free_slots(), 4)

    def test_ao10_repo_fleet_and_server_form_one_consistent_pair(self) -> None:
        # L3 (живой :9887 + DSH Desktop) этим тестом НЕ проверяется: нужен деплой пары.
        with _Fixture() as fx:
            fx.set_flag(None)
            fx.set_env("AGY_IMAGE_INPUT_ENABLED", None)
            self.assertEqual(_bval("IMPLEMENTED_METHODS"), {"workspace-read": 1})
            self.assertEqual(_bval("METHOD_IMPL_VERSION"), 1)
            catalog = _dict(_bval("FLEET"))
            ref = _dict(catalog["technical_ref"])
            self.assertEqual(ref["agy_version"], "1.4.9")
            sha = _str(ref["agy_binary_sha256"])
            limits = _dict(catalog["image_limits"])
            self.assertEqual(
                (
                    limits["max_images"],
                    limits["max_image_bytes"],
                    limits["max_total_image_bytes"],
                    limits["max_body_bytes"],
                ),
                (16, _IMG_CAP, _IMG_CAP, 33554432),
            )
            self.assertEqual(limits["types"], list(_IMG_MIMES))
            models = _dict(catalog["models"])
            for model_id, model in models.items():
                info = _dict(model)
                images = _dict(info["images"])
                if model_id in _IMG_TARGETS:
                    proof = _dict(images["proof"])
                    self.assertEqual(
                        (images["status"], images["method"], info["input"]),
                        ("confirmed", "workspace-read", ["text", "image"]),
                    )
                    self.assertEqual(proof["agy_binary_sha256"], sha)
                    self.assertEqual(proof["impl_version"], 1)
                    self.assertEqual(proof["formats"], list(_IMG_MIMES))
                    self.assertTrue(
                        set(cast("list[str]", proof["efforts_proven"]))
                        <= set(cast("list[str]", info["efforts"]))
                    )
                else:
                    self.assertEqual(
                        (images["status"], images["method"], info["input"]),
                        ("unsupported", None, ["text"]),
                    )
            self.assertIs(_bfn("_is_image_input_enabled")(), False)
            self.assertIs(_bfn("_model_supports_images")("gemini-4-argon"), False)
            build = _bfn("_build_catalog")
            violation = cast("type[Exception]", _bval("FleetViolation"))
            raw = cast(
                "dict[str, object]",
                json.loads(
                    Path(_str(_dict(catalog)["path"])).read_text(encoding="utf-8")
                ),
            )

            def drop_method(model: dict[str, object]) -> None:
                _dict(model["images"])["method"] = None

            def drop_proof(model: dict[str, object]) -> None:
                _dict(model["images"])["proof"] = None

            def text_only_input(model: dict[str, object]) -> None:
                model["input"] = ["text"]

            mutations: list[tuple[str, Callable[[dict[str, object]], None], str]] = [
                ("method_none", drop_method, "method_not_implemented"),
                ("proof_missing", drop_proof, "proof_invalid"),
                ("input_text_only", text_only_input, "status_inconsistent"),
            ]
            for label, mutate, reason in mutations:
                with self.subTest(violation=label):
                    broken = cast("dict[str, object]", json.loads(json.dumps(raw)))
                    mutate(_dict(cast("list[object]", broken["models"])[0]))
                    with self.assertRaises(violation) as caught:
                        _ = build(broken)
                    self.assertEqual(_oval(caught.exception, "reason"), reason)
            self.assertEqual(_dict(build(raw))["default_model"], "gemini-3.8-flash")


# ======================================================================================
# agy-usage-overflow-fix: usage по окну последнего шага (step_scoped_usage_enabled).
# AD-001 ledger шагов хода из транскрипта, AD-002/AD-003 нормализованный wire-usage и
# ограниченный fallback, AD-004 пятый runtime-флаг. Оракулы USG-01..USG-18.
# ======================================================================================

_USAGE_MODEL = "gemini-4-argon"  # окно 1048576 в fleet.json
_USAGE_WINDOW = 1048576
_OMIT: object = object()
_RAW_CUMULATIVE: dict[str, object] = {
    "input_tokens": 1552662,
    "output_tokens": 191762,
    "thinking_tokens": 500,
    "total_tokens": 1745000,
    "cache_read_tokens": 982479,
}


def _usage_rec(
    idx: object,
    inp: object = 100,
    cache: object = _OMIT,
    out: object = 10,
    **extra: object,
) -> dict[str, object]:
    """PLANNER_RESPONSE с верхнеуровневыми счётчиками; `_OMIT` убирает ключ."""
    rec: dict[str, object] = {
        "type": "PLANNER_RESPONSE",
        "step_index": idx,
        "input_tokens": inp,
        "cache_read_tokens": cache,
        "output_tokens": out,
    }
    rec.update(extra)
    return {key: value for key, value in rec.items() if value is not _OMIT}


def _usage_tail(
    base_idx: int = 0,
    offset: int = 0,
    resumed: bool = False,
    enabled: bool = True,
    plan: object | None = None,
) -> object:
    """Tail без процесса, SQLite OFF: только счётчики шагов из транскрипта."""
    if plan is None:
        plan = _bfn("_TurnPlan")()
        setattr(plan, "mode", "OFF")
        setattr(plan, "base_idx", base_idx)
        setattr(plan, "offset", offset)

    def emit(_idx: int, _delta: str, on_delivered: Callable[[], None] | None) -> bool:
        if on_delivered is not None:
            on_delivered()
        return True

    tail = _bfn("_TranscriptTail")(
        emit,
        threading.Event(),
        threading.Event(),
        resumed,
        plan,
        "turn-usage",
        usage_enabled=enabled,
    )
    _ = _ofn(tail, "bind")(_CID)
    return tail


def _usage_write(path: Path, recs: list[dict[str, object]], mode: str = "a") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not recs and mode == "a":
        return  # пустая дозапись не создаёт файл
    with open(path, mode, encoding="utf-8") as fh:
        for rec in recs:
            _ = fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _usage_feed(
    fx: _Fixture,
    tail: object,
    recs: list[dict[str, object]],
    name: str = "transcript_full.jsonl",
) -> object:
    """Дописать записи в транскрипт, прочитать один проход, вернуть снимок usage."""
    _usage_write(fx.transcript().parent / name, recs)
    _ = _ofn(tail, "_read_transcript")()
    return _ofn(tail, "usage_snapshot")()


def _screenshot_records() -> list[dict[str, object]]:
    """Шаги 186..602 хода со скриншота: сумма output 54601, последний 602 = (2437, 56849, 2867)."""
    outs = [125] * 150 + [124] * 266  # 416 шагов 186..601, сумма 51734
    recs = [_usage_rec(186 + i, 1000 + i, 50000 + i, out) for i, out in enumerate(outs)]
    recs.append(
        {
            "type": "PLANNER_RESPONSE",
            "step_index": 602,
            "input_tokens": 2437,
            "cache_read_tokens": 56849,
            "output_tokens": 2867,
        }
    )
    return recs


def _usage_out(**over: object) -> dict[str, object]:
    out: dict[str, object] = {
        "rc": 0,
        "state": "done",
        "text": "ok",
        "usage": {},
        "result": {"status": "OK"},
        "num_turns": None,
        "tool_events": 0,
    }
    out.update(over)
    return out


def _snap(**fields: object) -> object:
    return _bfn("_UsageSnapshot")(**fields)


def _resolve(
    out: dict[str, object],
    snap: object | None = None,
    window: int | None = _USAGE_WINDOW,
    resume: bool = False,
) -> tuple[dict[str, object], str]:
    """(итог `_resolve_step_usage`, stderr моста за вызов)."""
    buffer = io.StringIO()
    with mock.patch.object(sys, "stderr", buffer):
        resolved = _dict(
            _bfn("_resolve_step_usage")(
                out, snap if snap is not None else _snap(), window, resume
            )
        )
    return resolved, buffer.getvalue()


def _wire(resolved: dict[str, object]) -> dict[str, object]:
    return _dict(resolved["wire"])


def _usage_result_ev(
    t: float,
    usage: dict[str, object],
    num_turns: int | None = None,
    status: str = "OK",
    error: str = "",
) -> dict[str, object]:
    ev = _result_ev(t, status=status, error=error)
    result = _dict(_dict(ev["line"])["result"])
    result["usage"] = usage
    if num_turns is not None:
        result["num_turns"] = num_turns
    return ev


def _planner_counts_ev(
    t: float, rec: dict[str, object], late_delay: float | None = None
) -> dict[str, object]:
    if late_delay is None:
        return {"t": t, "op": "transcript", "record": rec}
    return {"t": t, "op": "late_transcript", "delay": late_delay, "record": rec}


def _usage_turn_events(late: bool = True) -> list[dict[str, object]]:
    """Ход со скриншота: кумулятивный result.usage и запись последнего шага после EOF."""
    last = _usage_rec(3, 2437, 56849, 2867, content="ответ")
    return [
        _init_ev(0.05),
        _text_ev(0.1),
        _planner_counts_ev(0.11, _usage_rec(0, 900, 0, 100, tool_calls=[{"n": "x"}])),
        _planner_counts_ev(
            0.12, _usage_rec(1, 1500, 800, 200, tool_calls=[{"n": "x"}])
        ),
        _planner_counts_ev(
            0.13, _usage_rec(2, 2000, 5000, 300, tool_calls=[{"n": "x"}])
        ),
        _usage_result_ev(0.15, dict(_RAW_CUMULATIVE), num_turns=3),
        _planner_counts_ev(0.16, last, 0.09 if late else None),
        _exit_ev(0.17),
    ]


_USAGE_TURN_SUM = 100 + 200 + 300 + 2867


def _usage_flags(fx: _Fixture, on: bool = True, **extra_env: str) -> None:
    _clean_flags(fx)
    fx.set_env("AGY_STEP_SCOPED_USAGE_ENABLED", "1" if on else "0")
    for key, value in extra_env.items():
        fx.set_env(key, value)


def _json_usage(ctx: dict[str, object]) -> tuple[int, dict[str, object]]:
    sent: list[tuple[int, object]] = []

    def send(code: int, payload: object) -> None:
        sent.append((code, payload))

    with _Sock() as sock:
        handler = cast(object, _make_handler(sock))
        setattr(handler, "_send", send)
        _ = _ofn(handler, "_serve_json")(ctx)
    code, payload = sent[0]
    return code, _dict(payload)


def _sse_usage(ctx: dict[str, object]) -> tuple[list[object], list[dict[str, object]]]:
    frames = _frames_json(_sse_frames(ctx))
    usages = [
        _dict(_dict(frame)["usage"])
        for frame in frames
        if isinstance(frame, dict) and "usage" in frame
    ]
    return frames, usages


def _stderr_of(call: Callable[[], object]) -> tuple[object, str]:
    buffer = io.StringIO()
    with mock.patch.object(sys, "stderr", buffer):
        result = call()
    return result, buffer.getvalue()


class StepScopedUsageLedgerTests(unittest.TestCase):
    """VER-001/VER-006 (USG-01..USG-05, USG-16): счётчики шагов хода из транскрипта."""

    def test_step_scoped_usage_l2_screenshot_fixture_186_602(self) -> None:
        with _Fixture() as fx:
            history = [_usage_rec(i, 7, 7, 9999) for i in range(186)]
            _usage_write(fx.transcript(), history)
            tail = _usage_tail(base_idx=186, resumed=True)
            snap = _usage_feed(fx, tail, _screenshot_records())
            self.assertEqual(_oval(snap, "last_step_usage"), (602, 2437, 56849, 2867))
            self.assertEqual(_oval(snap, "turn_output_tokens_sum"), 54601)
            self.assertEqual(_oval(snap, "observed_planner_steps"), 417)
            self.assertIs(_oval(snap, "completeness"), True)
            self.assertIs(_oval(snap, "observed_planner_steps_saturated"), False)
            out = _usage_out(usage=dict(_RAW_CUMULATIVE))
            resolved, _log_text = _resolve(out, snap)
            self.assertEqual(
                _wire(resolved),
                {
                    "prompt_tokens": 59286,
                    "completion_tokens": 54601,
                    "total_tokens": 113887,
                    "prompt_tokens_details": {"cached_tokens": 56849},
                },
            )
            self.assertEqual(resolved["source"], "last_step")
            # pi-ai: input = max(0, prompt - cacheRead); input + cacheRead = prompt.
            prompt = _int(_wire(resolved)["prompt_tokens"])
            cache = _int(
                _dict(_wire(resolved)["prompt_tokens_details"])["cached_tokens"]
            )
            self.assertEqual(max(0, prompt - cache) + cache, 59286)
            self.assertLessEqual(prompt, _USAGE_WINDOW)

    def test_step_scoped_usage_l2_cache_missing_and_zero(self) -> None:
        with _Fixture() as fx:
            tail = _usage_tail()
            snap = _usage_feed(fx, tail, [_usage_rec(0, 2437, _OMIT, 40)])
            self.assertEqual(_oval(snap, "last_step_usage"), (0, 2437, None, 40))
            resolved, _t = _resolve(_usage_out(usage=dict(_RAW_CUMULATIVE)), snap)
            self.assertEqual(
                _wire(resolved),
                {"prompt_tokens": 2437, "completion_tokens": 40, "total_tokens": 2477},
            )
        with _Fixture() as fx:
            tail = _usage_tail()
            snap = _usage_feed(
                fx, tail, [_usage_rec(0, 2437, 0, 40), _usage_rec(1, 5, None, 1)]
            )
            self.assertEqual(_oval(snap, "last_step_usage"), (1, 5, None, 1))
            self.assertIs(
                _oval(snap, "completeness"), True
            )  # null cache == отсутствует
            snap0 = _snap(
                last_step_usage=(0, 2437, 0, 40),
                completeness=True,
                turn_output_tokens_sum=40,
                observed_planner_steps=1,
            )
            resolved, _t = _resolve(_usage_out(), snap0)
            self.assertEqual(
                _wire(resolved)["prompt_tokens_details"], {"cached_tokens": 0}
            )

    def test_step_scoped_usage_l2_duplicates_and_corrections_not_double_counted(
        self,
    ) -> None:
        with _Fixture() as fx:
            tail = _usage_tail()
            snap = _usage_feed(
                fx, tail, [_usage_rec(5, 10, 1, 100), _usage_rec(5, 10, 1, 100)]
            )
            self.assertEqual(_oval(snap, "turn_output_tokens_sum"), 100)
            self.assertEqual(_oval(snap, "observed_planner_steps"), 1)
            # Исправленная запись того же шага заменяет вклад: 100 -> 130.
            snap = _usage_feed(fx, tail, [_usage_rec(5, 20, 2, 130)])
            self.assertEqual(_oval(snap, "turn_output_tokens_sum"), 130)
            self.assertEqual(_oval(snap, "last_step_usage"), (5, 20, 2, 130))
            # Меньший индекс позже: сумма растёт, latest не откатывается.
            snap = _usage_feed(fx, tail, [_usage_rec(3, 1, 1, 7)])
            self.assertEqual(_oval(snap, "turn_output_tokens_sum"), 137)
            self.assertEqual(_oval(snap, "last_step_usage"), (5, 20, 2, 130))
            self.assertEqual(_oval(snap, "observed_planner_steps"), 2)

    def test_step_scoped_usage_l2_rewrite_keeps_ledger_without_double_sum(self) -> None:
        with _Fixture() as fx:
            tail = _usage_tail()
            recs = [_usage_rec(i, 50 + i, 10, 100) for i in range(4)]
            snap = _usage_feed(fx, tail, recs)
            self.assertEqual(_oval(snap, "turn_output_tokens_sum"), 400)
            # Файл переписан с нуля (короче прежнего): записи снова видны tail'у.
            _usage_write(fx.transcript(), recs[:2] + [_usage_rec(0, 1, 1, 100)], "w")
            snap = _usage_feed(fx, tail, [])
            self.assertEqual(_oval(snap, "turn_output_tokens_sum"), 400)
            self.assertEqual(_oval(snap, "observed_planner_steps"), 4)

    def test_step_scoped_usage_l2_history_before_base_idx_is_ignored(self) -> None:
        with _Fixture() as fx:
            tail = _usage_tail(base_idx=10, resumed=True)
            snap = _usage_feed(
                fx,
                tail,
                [
                    _usage_rec(8, 1, 1, 500),
                    _usage_rec(9, 2, 2, 600),
                    _usage_rec(10, 3, 3, 7),
                ],
            )
            self.assertEqual(_oval(snap, "turn_output_tokens_sum"), 7)
            self.assertEqual(_oval(snap, "observed_planner_steps"), 1)
            self.assertEqual(_oval(snap, "last_step_usage"), (10, 3, 3, 7))

    def test_step_scoped_usage_l2_invalid_counts_mark_incomplete_keep_last_valid(
        self,
    ) -> None:
        bad_variants: list[dict[str, object]] = [
            _usage_rec(1, True, 1, 5),
            _usage_rec(1, 1, True, 5),
            _usage_rec(1, 1, 1, False),
            _usage_rec(1, -1, 1, 5),
            _usage_rec(1, 1, -2, 5),
            _usage_rec(1, 1, 1, -5),
            _usage_rec(1, "10", 1, 5),
            _usage_rec(1, 1.5, 1, 5),
            _usage_rec(1, 1, "3", 5),
            _usage_rec(1, 1, 1, "5"),
            _usage_rec(1, _OMIT, 1, 5),
            _usage_rec(1, 1, 1, _OMIT),
        ]
        for bad in bad_variants:
            with self.subTest(bad=bad), _Fixture() as fx:
                tail = _usage_tail()
                snap = _usage_feed(fx, tail, [_usage_rec(0, 10, 2, 50), bad])
                self.assertIs(_oval(snap, "completeness"), False)
                self.assertEqual(_oval(snap, "invalid_records_count"), 1)
                self.assertEqual(_oval(snap, "last_step_usage"), (0, 10, 2, 50))
                self.assertEqual(_oval(snap, "turn_output_tokens_sum"), 50)
                self.assertEqual(_oval(snap, "observed_planner_steps"), 2)
                # Невалидная запись не затирает уже сохранённый валидный кортеж.
                snap = _usage_feed(fx, tail, [dict(bad, step_index=0)])
                self.assertEqual(_oval(snap, "last_step_usage"), (0, 10, 2, 50))
                self.assertEqual(_oval(snap, "turn_output_tokens_sum"), 50)
        for bad_idx in (True, "7", -1, 1.0, None, _OMIT):
            with self.subTest(step_index=bad_idx), _Fixture() as fx:
                tail = _usage_tail()
                snap = _usage_feed(fx, tail, [_usage_rec(bad_idx, 1, 1, 1)])
                self.assertIs(_oval(snap, "completeness"), False)
                self.assertIsNone(_oval(snap, "last_step_usage"))
                self.assertEqual(_oval(snap, "observed_planner_steps"), 0)

    def test_step_scoped_usage_l2_incomplete_ledger_wire_completion_zero_and_diag(
        self,
    ) -> None:
        snap = _snap(
            last_step_usage=(602, 2437, 56849, 2867),
            turn_output_tokens_sum=54601,
            observed_planner_steps=417,
            completeness=False,
            invalid_records_count=2,
        )
        resolved, text = _resolve(_usage_out(usage=dict(_RAW_CUMULATIVE)), snap)
        self.assertEqual(_wire(resolved)["prompt_tokens"], 59286)
        self.assertEqual(_wire(resolved)["completion_tokens"], 0)
        self.assertEqual(_wire(resolved)["total_tokens"], 59286)
        self.assertIn("usage-step-ledger-incomplete observed_steps=417", text)
        self.assertIn("invalid_records=2", text)
        self.assertNotIn("***", text)
        self.assertNotIn("usage-cumulative-fallback", text)

    def test_step_scoped_usage_l2_transcript_full_priority_and_fallback_pinning(
        self,
    ) -> None:
        with _Fixture() as fx:
            base = fx.transcript().parent
            # Свежий разговор: ни одного файла — ничего не пинится, проверка повторяется.
            tail = _usage_tail()
            snap = _usage_feed(fx, tail, [])
            self.assertEqual(_oval(snap, "observed_planner_steps"), 0)
            self.assertIsNone(_oval(tail, "_path"))
            # Появился только transcript.jsonl: он и закрепляется на попытку.
            snap = _usage_feed(
                fx, tail, [_usage_rec(0, 5, 1, 11)], name="transcript.jsonl"
            )
            self.assertEqual(_oval(tail, "_path"), base / "transcript.jsonl")
            self.assertEqual(_oval(snap, "turn_output_tokens_sum"), 11)
            # Позже появился full: не подменяет файл и смещение выбранного.
            snap = _usage_feed(fx, tail, [_usage_rec(1, 6, 1, 4000)])
            self.assertEqual(_oval(tail, "_path"), base / "transcript.jsonl")
            self.assertEqual(_oval(snap, "turn_output_tokens_sum"), 11)
            snap = _usage_feed(
                fx, tail, [_usage_rec(2, 7, 1, 13)], name="transcript.jsonl"
            )
            self.assertEqual(_oval(snap, "turn_output_tokens_sum"), 24)
        with _Fixture() as fx:
            base = fx.transcript().parent
            _usage_write(base / "transcript.jsonl", [_usage_rec(0, 1, 1, 999)])
            tail = _usage_tail()
            snap = _usage_feed(fx, tail, [_usage_rec(0, 5, 1, 11)])
            self.assertEqual(_oval(tail, "_path"), base / "transcript_full.jsonl")
            self.assertEqual(_oval(snap, "turn_output_tokens_sum"), 11)

    def test_step_scoped_usage_l2_resume_prespawn_boundary_sqlite_off(self) -> None:
        with _Fixture() as fx:
            base = fx.transcript().parent
            history = [_usage_rec(i, 7, 7, 9999) for i in range(10)]
            _usage_write(base / "transcript.jsonl", history)
            plan = _bfn("_prespawn_plan")(_CID, True, True)
            self.assertIs(_oval(plan, "anchored"), False)  # SQLite OFF: нет БД-якоря
            self.assertEqual(_oval(plan, "transcript_path"), base / "transcript.jsonl")
            self.assertEqual(_oval(plan, "base_idx"), 10)
            self.assertEqual(
                _oval(plan, "offset"), (base / "transcript.jsonl").stat().st_size
            )
            tail = _usage_tail(resumed=True, plan=plan)
            snap = _usage_feed(
                fx,
                tail,
                [_usage_rec(10, 1, 1, 5), _usage_rec(11, 2, 2, 6)],
                name="transcript.jsonl",
            )
            self.assertEqual(_oval(snap, "turn_output_tokens_sum"), 11)
            self.assertEqual(_oval(snap, "observed_planner_steps"), 2)
            legacy = _bfn("_prespawn_plan")(_CID, True)
            self.assertIsNone(_oval(legacy, "transcript_path"))
            self.assertEqual(_oval(legacy, "base_idx"), 0)  # full-файла нет: legacy

    def test_step_scoped_usage_l2_distinct_cids_and_retries_are_isolated(self) -> None:
        with _Fixture() as fx:
            first = _usage_tail()
            snap_a = _usage_feed(fx, first, [_usage_rec(0, 1, 1, 10)])
            other = _bfn("_TranscriptTail")(
                lambda *_a: True,
                threading.Event(),
                threading.Event(),
                False,
                _bfn("_TurnPlan")(),
                "turn-b",
                usage_enabled=True,
            )
            _ = _ofn(other, "bind")(_CID_B)
            _usage_write(fx.transcript(_CID_B), [_usage_rec(0, 9, 9, 77)])
            _ = _ofn(other, "_read_transcript")()
            snap_b = _ofn(other, "usage_snapshot")()
            self.assertEqual(_oval(snap_a, "turn_output_tokens_sum"), 10)
            self.assertEqual(_oval(snap_b, "turn_output_tokens_sum"), 77)
            retry = _usage_tail(
                base_idx=1, resumed=True
            )  # новая попытка — новый ledger
            self.assertEqual(
                _oval(_ofn(retry, "usage_snapshot")(), "observed_planner_steps"), 0
            )

    def test_step_scoped_usage_l2_disabled_collector_is_legacy_and_allocates_nothing(
        self,
    ) -> None:
        with _Fixture() as fx:
            _usage_write(
                fx.transcript().parent / "transcript.jsonl", [_usage_rec(0, 1, 1, 5)]
            )
            tail = _usage_tail(enabled=False)
            self.assertIsNone(_oval(tail, "step_records_by_index"))
            with (
                mock.patch.object(tail, "_record_usage") as record,
                mock.patch.object(tail, "_publish_usage") as publish,
            ):
                snap = _usage_feed(fx, tail, [_usage_rec(0, 2, 2, 9)])
            self.assertEqual(record.call_count, 0)
            self.assertEqual(publish.call_count, 0)
            self.assertIs(snap, _bval("_EMPTY_USAGE_SNAPSHOT"))
            self.assertEqual(
                _oval(tail, "_transcript_file")(), _bfn("_transcript_path")(_CID)
            )

    def test_step_scoped_usage_l2_snapshot_is_immutable_and_published_without_io(
        self,
    ) -> None:
        with _Fixture() as fx:
            tail = _usage_tail()
            snap = _usage_feed(fx, tail, [_usage_rec(0, 1, 1, 5)])
            with self.assertRaises(dataclasses.FrozenInstanceError):
                setattr(snap, "completeness", False)

            class _SpyLock:
                held = False

                def __enter__(self) -> None:
                    _SpyLock.held = True

                def __exit__(self, *_exc: object) -> None:
                    _SpyLock.held = False

            violations: list[str] = []

            def forbid(name: str) -> Callable[..., object]:
                def guard(*_a: object, **_k: object) -> object:
                    if _SpyLock.held:
                        violations.append(name)
                    return None

                return guard

            setattr(tail, "_usage_lock", _SpyLock())
            setattr(tail, "_usage_dirty", True)
            with (
                mock.patch.object(_bridge(), "_log", forbid("log")),
                mock.patch.object(Path, "stat", forbid("stat")),
                mock.patch("builtins.open", forbid("open")),
            ):
                _ = _ofn(tail, "_publish_usage")()
            self.assertEqual(violations, [])
            self.assertIs(_SpyLock.held, False)

    def test_step_scoped_usage_l2_saturation_16385_distinct_invalid_then_corrections(
        self,
    ) -> None:
        cap = _int(_bval("USAGE_STEP_CAP"))
        self.assertEqual(cap, 16384)
        with _Fixture() as fx:
            tail = _usage_tail()
            records = cast("dict[int, object]", _oval(tail, "step_records_by_index"))
            bad = [_usage_rec(i, "bad", 1, 1) for i in range(1, cap + 2)]
            snap = None
            for start in range(0, len(bad), 512):
                snap = _usage_feed(fx, tail, bad[start : start + 512])
            self.assertEqual(len(records), cap)
            self.assertTrue(all(value is None for value in records.values()))
            self.assertNotIn(cap + 1, records)
            self.assertIs(_oval(snap, "observed_planner_steps_saturated"), True)
            # Повтор невалидного неотслеженного idx не меняет ledger.
            snap = _usage_feed(fx, tail, [_usage_rec(cap + 1, "bad", 1, 1)])
            self.assertEqual(len(records), cap)
            # Валидная коррекция отслеженного idx=100: значение на месте, len прежний.
            snap = _usage_feed(fx, tail, [_usage_rec(100, 40, 4, 8)])
            self.assertEqual(records[100], (40, 4, 8))
            self.assertEqual(len(records), cap)
            # Валидная запись неотслеженного idx: ключ не вставлен, last обновлён за O(1).
            snap = _usage_feed(fx, tail, [_usage_rec(cap + 1, 77, 7, 9)])
            self.assertNotIn(cap + 1, records)
            self.assertEqual(len(records), cap)
            self.assertEqual(_oval(tail, "last_valid_step_index"), cap + 1)
            self.assertEqual(_oval(snap, "last_step_usage"), (cap + 1, 77, 7, 9))
            self.assertEqual(_oval(snap, "observed_planner_steps"), cap)
            self.assertIs(_oval(snap, "observed_planner_steps_saturated"), True)
            self.assertIs(_oval(snap, "completeness"), False)
            resolved, text = _resolve(_usage_out(usage=dict(_RAW_CUMULATIVE)), snap)
            self.assertEqual(_wire(resolved)["prompt_tokens"], 84)
            self.assertEqual(
                _wire(resolved)["completion_tokens"], 0
            )  # unknown, не сумма
            self.assertIn("saturated=1", text)

    def test_step_scoped_usage_l2_ledger_memory_gate_4_mib_per_turn(self) -> None:
        cap = _int(_bval("USAGE_STEP_CAP"))
        with _Fixture() as fx:
            tail = _usage_tail()
            path = fx.transcript().parent / "transcript_full.jsonl"
            recs = [
                _usage_rec(i, 1_000_000 + i, 2_000_000 + i, 3_000 + i)
                for i in range(cap)
            ]
            _usage_write(path, recs)
            del recs
            gc.collect()
            tracemalloc.start()
            try:
                before = tracemalloc.get_traced_memory()[0]
                _ = _ofn(tail, "_read_transcript")()
                gc.collect()
                retained = tracemalloc.get_traced_memory()[0] - before
            finally:
                tracemalloc.stop()
            snap = _ofn(tail, "usage_snapshot")()
            self.assertEqual(_oval(snap, "observed_planner_steps"), cap)
            self.assertIs(_oval(snap, "completeness"), True)
            self.assertLessEqual(retained, 4 * 1024 * 1024)

    def test_step_scoped_usage_l2_single_monotonic_terminal_drain_deadline(
        self,
    ) -> None:
        window = _float(_bval("DRAIN_WINDOW_S"))
        for enabled in (True, False):
            with self.subTest(usage_enabled=enabled):
                run = _bare_run()
                setattr(run, "usage_enabled", enabled)
                setattr(run, "_proc_done", threading.Event())
                joins: list[float] = []
                tail = SimpleNamespace(
                    cid="",
                    drain_deadline=0.0,
                    thread=SimpleNamespace(
                        join=lambda timeout=None: joins.append(_float(timeout)),
                        is_alive=lambda: False,
                    ),
                )
                setattr(run, "_tail", tail)
                clock = _FakeClock(100.0)
                setattr(run, "_drain_t0", 100.0)  # EOF/exit: старт единого окна попытки
                with mock.patch.object(_bridge(), "time", _fake_time(clock)):
                    clock.advance(0.2)
                    _ = _ofn(run, "terminal_drain")(0.5)
                    clock.advance(0.2)
                    _ = _ofn(run, "terminal_drain")(0.5)
                    clock.advance(0.5)
                    _ = _ofn(run, "terminal_drain")(0.5)
                if enabled:
                    # Общий бюджет <= 0.5 с от EOF: второй drain получает остаток, не новое окно.
                    self.assertAlmostEqual(joins[0], 0.3)
                    self.assertAlmostEqual(joins[1], 0.1)
                    self.assertAlmostEqual(joins[2], 0.0)
                    self.assertAlmostEqual(_float(tail.drain_deadline), 100.0 + window)
                else:
                    self.assertEqual(
                        joins, [0.5, 0.5, 0.5]
                    )  # legacy: окно на каждый вызов

    def test_step_scoped_usage_l2_terminal_drain_wall_time_measured_gate(self) -> None:
        run = _bare_run()
        setattr(run, "usage_enabled", True)
        setattr(run, "_proc_done", threading.Event())
        release = threading.Event()
        blocker = threading.Thread(target=lambda: release.wait(5), daemon=True)
        blocker.start()
        setattr(
            run, "_tail", SimpleNamespace(cid="", drain_deadline=0.0, thread=blocker)
        )
        started = time.monotonic()
        try:
            _ = _ofn(run, "terminal_drain")(_float(_bval("T_DRAIN_MAX_S")))
            elapsed = time.monotonic() - started
        finally:
            release.set()
            blocker.join(5)
        self.assertLessEqual(elapsed, 0.5 + 0.4)  # <= 0.5 с + допуск планировщика


class StepScopedUsageFallbackTests(unittest.TestCase):
    """VER-003 (USG-09..USG-12): ограниченный fallback и result-only ветка."""

    def test_usage_fallback_cumulative_estimate_oracle_table(self) -> None:
        cases: list[tuple[str, dict[str, object], dict[str, object], bool, int]] = [
            ("turns2_tools202", {"num_turns": 2, "tool_events": 202}, {}, False, 7611),
            (
                "retry_resume",
                {"num_turns": 3, "tool_events": 10},
                {"input_tokens": 1596656},
                True,
                122819,
            ),
            ("single_turn_n2", {"num_turns": 1, "tool_events": 0}, {}, False, 776331),
            (
                "no_turn_info_n2",
                {"num_turns": None, "tool_events": 0},
                {},
                False,
                776331,
            ),
            (
                "raw_eq_window",
                {"num_turns": 1},
                {"input_tokens": _USAGE_WINDOW},
                False,
                524288,
            ),
        ]
        for label, over, usage_over, resume, prompt in cases:
            with self.subTest(case=label):
                usage = dict(_RAW_CUMULATIVE, cache_read_tokens=0)
                usage.update(usage_over)
                resolved, text = _resolve(
                    _usage_out(usage=usage, **over), resume=resume
                )
                wire = _wire(resolved)
                self.assertEqual(resolved["source"], "cumulative_estimate")
                self.assertEqual(wire["prompt_tokens"], prompt)
                self.assertLess(_int(wire["prompt_tokens"]), _USAGE_WINDOW)
                self.assertEqual(
                    wire["total_tokens"], prompt + _int(wire["completion_tokens"])
                )
                self.assertIn("usage-cumulative-fallback raw_in=", text)
                self.assertNotIn("***", text)
                if resume:  # область cumulative output неизвестна: 0 = unknown
                    self.assertEqual(wire["completion_tokens"], 0)
                else:
                    self.assertEqual(wire["completion_tokens"], 191762 + 500)
                self.assertEqual(
                    usage["input_tokens"], usage_over.get("input_tokens", 1552662)
                )

    def test_usage_fallback_divisor_includes_observed_steps_and_saturated_bound(
        self,
    ) -> None:
        out = _usage_out(usage={"input_tokens": 1552662}, num_turns=1, tool_events=0)
        resolved, _t = _resolve(
            out, _snap(observed_planner_steps=5000, invalid_records_count=1)
        )
        self.assertEqual(_wire(resolved)["prompt_tokens"], 1552662 // 5000)
        saturated = _snap(
            observed_planner_steps=16384,
            observed_planner_steps_saturated=True,
            invalid_records_count=3,
        )
        resolved, _t = _resolve(out, saturated)
        self.assertEqual(_wire(resolved)["prompt_tokens"], 1552662 // 16384)
        self.assertLessEqual(_int(_wire(resolved)["prompt_tokens"]), _USAGE_WINDOW - 1)
        # Свежий разговор, но транскрипт частично виден: область output неизвестна.
        self.assertEqual(_wire(resolved)["completion_tokens"], 0)

    def test_usage_fallback_window_boundary_and_not_over_window(self) -> None:
        at = _usage_out(usage={"input_tokens": _USAGE_WINDOW}, num_turns=1)
        resolved, text = _resolve(at)
        self.assertEqual(resolved["source"], "cumulative_estimate")
        self.assertIn("usage-cumulative-fallback", text)
        below = _usage_out(usage={"input_tokens": _USAGE_WINDOW - 1}, num_turns=1)
        resolved, text = _resolve(below)
        self.assertEqual(resolved["source"], "result")
        self.assertEqual(_wire(resolved)["prompt_tokens"], _USAGE_WINDOW - 1)
        self.assertNotIn("usage-cumulative-fallback", text)

    def test_usage_fallback_cache_cases_follow_normalizer_policy(self) -> None:
        # cache == prompt: details сохраняются.
        usage = {"input_tokens": _USAGE_WINDOW, "cache_read_tokens": 524288}
        resolved, _t = _resolve(_usage_out(usage=usage, num_turns=1))
        self.assertEqual(_wire(resolved)["prompt_tokens"], 524288)
        self.assertEqual(
            _wire(resolved)["prompt_tokens_details"], {"cached_tokens": 524288}
        )
        self.assertIs(resolved["inconsistent"], False)
        # valid_cache > estimated_prompt: details опущены, cache не clamp, inconsistent.
        usage = {"input_tokens": 1552662, "cache_read_tokens": 982479}
        resolved, text = _resolve(_usage_out(usage=usage, num_turns=2, tool_events=202))
        self.assertEqual(_wire(resolved)["prompt_tokens"], 7611)
        self.assertNotIn("prompt_tokens_details", _wire(resolved))
        self.assertIs(resolved["inconsistent"], True)
        self.assertIn("inconsistent=1", text)
        self.assertEqual(usage["cache_read_tokens"], 982479)
        # Малый input + большой cache: input + cache > window включает estimate.
        usage = {"input_tokens": 10, "cache_read_tokens": _USAGE_WINDOW}
        resolved, _t = _resolve(_usage_out(usage=usage, num_turns=1))
        self.assertEqual(resolved["source"], "cumulative_estimate")
        self.assertEqual(_wire(resolved)["prompt_tokens"], 5)
        self.assertNotIn("prompt_tokens_details", _wire(resolved))
        # Вне over_window input и cache раздельны: input10/cache40 -> prompt50/cache40.
        usage = {"input_tokens": 10, "cache_read_tokens": 40}
        resolved, text = _resolve(_usage_out(usage=usage))
        self.assertEqual(resolved["source"], "result")
        self.assertEqual(_wire(resolved)["prompt_tokens"], 50)
        self.assertEqual(
            _wire(resolved)["prompt_tokens_details"], {"cached_tokens": 40}
        )
        self.assertNotIn("usage-cumulative-fallback", text)
        # Явный 0 сохраняется, отсутствие cache не синтезирует 0.
        resolved, _t = _resolve(
            _usage_out(usage={"input_tokens": 10, "cache_read_tokens": 0})
        )
        self.assertEqual(_wire(resolved)["prompt_tokens_details"], {"cached_tokens": 0})
        resolved, _t = _resolve(_usage_out(usage={"input_tokens": 10}))
        self.assertNotIn("prompt_tokens_details", _wire(resolved))
        # camel-алиас, null, невалидный cache и конфликт алиасов.
        resolved, _t = _resolve(
            _usage_out(usage={"input_tokens": 10, "cacheReadTokens": 40})
        )
        self.assertEqual(_wire(resolved)["prompt_tokens"], 50)
        resolved, _t = _resolve(
            _usage_out(
                usage={
                    "input_tokens": 10,
                    "cache_read_tokens": None,
                    "cacheReadTokens": 40,
                }
            )
        )
        self.assertEqual(_wire(resolved)["prompt_tokens"], 50)
        for bad in (True, -1, "40", 1.5):
            with self.subTest(cache=bad):
                resolved, _t = _resolve(
                    _usage_out(usage={"input_tokens": 10, "cache_read_tokens": bad})
                )
                self.assertEqual(_wire(resolved)["prompt_tokens"], 10)
                self.assertNotIn("prompt_tokens_details", _wire(resolved))
        resolved, _t = _resolve(
            _usage_out(
                usage={
                    "input_tokens": 10,
                    "cache_read_tokens": 40,
                    "cacheReadTokens": 41,
                }
            )
        )
        self.assertEqual(resolved["reason"], "alias_conflict")
        self.assertEqual(_wire(resolved)["prompt_tokens"], 10)
        self.assertNotIn("prompt_tokens_details", _wire(resolved))

    def test_usage_fallback_never_clamps_errors_timeouts_or_measured_last_step(
        self,
    ) -> None:
        big = {"input_tokens": 1552662, "output_tokens": 5, "cache_read_tokens": 1}
        error_cases: list[tuple[str, dict[str, object]]] = [
            ("rc_nonzero", {"rc": 1}),
            ("state_agy_error", {"state": "agy_error"}),
            ("state_timeout", {"state": "timeout", "rc": 124}),
            ("result_error", {"result": {"status": "ERROR", "error": "boom"}}),
        ]
        for label, over in error_cases:
            with self.subTest(case=label):
                resolved, text = _resolve(
                    _usage_out(usage=dict(big), num_turns=2, **over)
                )
                self.assertEqual(resolved["source"], "result")
                self.assertEqual(_wire(resolved)["prompt_tokens"], 1552663)
                self.assertNotIn("usage-cumulative-fallback", text)
        # Валидный last_step с измеренным overflow не ограничивается окном.
        measured = _snap(
            last_step_usage=(7, 2_000_000, 100, 9),
            observed_planner_steps=1,
            turn_output_tokens_sum=9,
            completeness=True,
        )
        resolved, text = _resolve(_usage_out(usage=dict(big), num_turns=2), measured)
        self.assertEqual(resolved["source"], "last_step")
        self.assertEqual(_wire(resolved)["prompt_tokens"], 2_000_100)
        self.assertNotIn("usage-cumulative-fallback", text)
        # Невалидное окно: fallback выключен, clamp нет.
        for window in (None,):
            resolved, text = _resolve(
                _usage_out(usage=dict(big), num_turns=2), window=window
            )
            self.assertEqual(_wire(resolved)["prompt_tokens"], 1552663)
            self.assertEqual(resolved["reason"], "no_window")
            self.assertNotIn("usage-cumulative-fallback", text)

    def test_usage_fallback_model_context_window_validity(self) -> None:
        with _Fixture() as fx:
            fx.patch(
                "FLEET_MODELS",
                {
                    "ok": {"context_window": 2048},
                    "zero": {"context_window": 0},
                    "neg": {"context_window": -5},
                    "flag": {"context_window": True},
                    "text": {"context_window": "2048"},
                    "none": {},
                },
            )
            window = _bfn("_model_context_window")
            self.assertEqual(window("ok"), 2048)
            for model in ("zero", "neg", "flag", "text", "none", "absent", None, 5):
                with self.subTest(model=model):
                    self.assertIsNone(window(model))

    def test_usage_fallback_raw_usage_is_not_mutated_and_bad_types_do_not_raise(
        self,
    ) -> None:
        usage: dict[str, object] = {
            "input_tokens": "x",
            "output_tokens": [1],
            "thinking_tokens": None,
            "total_tokens": {},
            "cache_read_tokens": object.__name__,
        }
        before = json.dumps(usage, sort_keys=True)
        out = _usage_out(usage=usage, num_turns="2", tool_events=None)
        resolved, _t = _resolve(out)
        self.assertEqual(json.dumps(usage, sort_keys=True), before)
        self.assertIs(out["usage"], usage)
        self.assertEqual(
            _wire(resolved),
            {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )
        resolved, _t = _resolve(_usage_out(usage=None))  # type: ignore[arg-type]
        self.assertEqual(_wire(resolved)["total_tokens"], 0)

    def test_usage_fallback_run_once_attaches_one_resolution_and_logs_numbers(
        self,
    ) -> None:
        with _Fixture() as fx:
            _usage_flags(fx)
            out = _scripted_out(
                "done",
                usage=dict(_RAW_CUMULATIVE),
                num_turns=2,
                tool_events=202,
                conversation_id=_CID,
            )

            def execute(_self: object, _run: object, *_a: object) -> dict[str, object]:
                return dict(out)

            ctx = _ctx(model=_USAGE_MODEL, model_len=len(_USAGE_MODEL), stream=False)
            result, text = _stderr_of(lambda: _run_once_direct(ctx, execute))
            resolved = _dict(_dict(result)["usage_resolved"])
            self.assertEqual(_wire(resolved)["prompt_tokens"], 1552662 // 204)
            self.assertEqual(_dict(result)["usage"], dict(_RAW_CUMULATIVE))
            done_lines = [ln for ln in text.splitlines() if " done model=" in ln]
            self.assertEqual(len(done_lines), 1)
            self.assertIn("usage_source=cumulative_estimate", done_lines[0])
            self.assertIn("prompt=7611", done_lines[0])
            self.assertIn("raw_in=1552662", done_lines[0])
            self.assertIn("raw_out=191762", done_lines[0])
            self.assertIn("raw_cache=982479", done_lines[0])
            self.assertEqual(text.count("usage-cumulative-fallback"), 1)
        with _Fixture() as fx:
            _usage_flags(fx, on=False)
            result, text = _stderr_of(
                lambda: _run_once_direct(
                    _ctx(model=_USAGE_MODEL, model_len=len(_USAGE_MODEL), stream=False),
                    execute,
                )
            )
            self.assertNotIn("usage_resolved", _dict(result))
            self.assertNotIn("usage_source", text)
            self.assertNotIn("usage-cumulative-fallback", text)

    def test_usage_fallback_legacy_payload_unchanged_when_flag_off(self) -> None:
        payload = _bval("Handler")._usage_payload  # type: ignore[attr-defined]
        usage = {
            "input_tokens": 7,
            "output_tokens": 3,
            "thinking_tokens": 2,
            "total_tokens": 12,
        }
        self.assertEqual(
            payload(usage),
            {"prompt_tokens": 7, "completion_tokens": 5, "total_tokens": 12},
        )
        self.assertEqual(
            payload(usage, None),
            {"prompt_tokens": 7, "completion_tokens": 5, "total_tokens": 12},
        )


class StepScopedUsageHttpTests(unittest.TestCase):
    """VER-002 (USG-06..USG-08): JSON и SSE с fake agy, один итоговый usage."""

    def _ctx(self, stream: bool) -> dict[str, object]:
        return _ctx(model=_USAGE_MODEL, model_len=len(_USAGE_MODEL), stream=stream)

    def test_usage_http_json_and_sse_parity_with_late_transcript_content_streaming_off(
        self,
    ) -> None:
        with _Fixture() as fx:
            _usage_flags(fx)
            _ = fx.write_scenario(_usage_turn_events())
            expected = {
                "prompt_tokens": 59286,
                "completion_tokens": _USAGE_TURN_SUM,
                "total_tokens": 59286 + _USAGE_TURN_SUM,
                "prompt_tokens_details": {"cached_tokens": 56849},
            }
            (code, body), json_log = cast(
                "tuple[tuple[int, dict[str, object]], str]",
                _stderr_of(lambda: _json_usage(self._ctx(False))),
            )
            self.assertEqual(code, 200)
            self.assertEqual(_dict(body["usage"]), expected)
            choice = _dict(cast("list[object]", body["choices"])[0])
            self.assertEqual(choice["finish_reason"], "stop")
            self.assertEqual(_dict(choice["message"])["content"], "ответ")
            (frames, usages), sse_log = cast(
                "tuple[tuple[list[object], list[dict[str, object]]], str]",
                _stderr_of(lambda: _sse_usage(self._ctx(True))),
            )
            self.assertEqual(usages, [expected])  # ровно один usage-chunk
            self.assertEqual(frames[-1], "[DONE]")
            self.assertTrue(any(_content_of(frame) == "ответ" for frame in frames))
            finishes = [
                _dict(cast("list[object]", _dict(f)["choices"])[0]).get("finish_reason")
                for f in frames
                if isinstance(f, dict) and "choices" in f
            ]
            self.assertIn("stop", finishes)
            # pi-ai: max(0, prompt - cacheRead) + cacheRead == prompt <= окна.
            self.assertEqual(max(0, 59286 - 56849) + 56849, 59286)
            self.assertLessEqual(59286, _USAGE_WINDOW)
            for text in (json_log, sse_log):  # лог done == wire usage
                done = [ln for ln in text.splitlines() if " done model=" in ln]
                self.assertEqual(len(done), 1)
                self.assertIn("usage_source=last_step", done[0])
                self.assertIn("step_idx=3", done[0])
                self.assertIn("prompt=59286", done[0])
                self.assertIn("cached=56849", done[0])
                self.assertIn(f"completion={_USAGE_TURN_SUM}", done[0])
                self.assertIn("completeness=1", done[0])
                self.assertIn("raw_in=1552662", done[0])
                self.assertIn("raw_out=191762", done[0])

    def test_usage_http_flag_off_is_legacy_cumulative(self) -> None:
        with _Fixture() as fx:
            _usage_flags(fx, on=False)
            _ = fx.write_scenario(_usage_turn_events())
            (code, body), text = cast(
                "tuple[tuple[int, dict[str, object]], str]",
                _stderr_of(lambda: _json_usage(self._ctx(False))),
            )
            self.assertEqual(code, 200)
            self.assertEqual(
                _dict(body["usage"]),
                {
                    "prompt_tokens": 1552662,
                    "completion_tokens": 191762 + 500,
                    "total_tokens": 1745000,
                },
            )
            self.assertNotIn("usage_source", text)
            _frames, usages = _sse_usage(self._ctx(True))
            self.assertEqual(
                usages,
                [
                    {
                        "prompt_tokens": 1552662,
                        "completion_tokens": 191762 + 500,
                        "total_tokens": 1745000,
                    }
                ],
            )

    def test_usage_http_late_record_after_window_is_dropped_without_hanging(
        self,
    ) -> None:
        with _Fixture() as fx:
            _usage_flags(fx)
            events = _usage_turn_events()
            late = [e for e in events if e["op"] == "late_transcript"][0]
            late["delay"] = 1.5  # за пределом drain: в frozen usage не попадает
            _ = fx.write_scenario(events)
            started = time.time()
            code, body = _json_usage(self._ctx(False))
            self.assertEqual(code, 200)
            usage = _dict(body["usage"])
            self.assertEqual(
                usage["prompt_tokens"], 2000 + 5000
            )  # последний видимый шаг
            self.assertEqual(usage["completion_tokens"], 600)
            self.assertLessEqual(time.time() - started, 3.0)

    def test_usage_http_both_flags_share_one_drain_and_keep_text(self) -> None:
        with _Fixture() as fx:
            _usage_flags(fx, AGY_PLANNER_CONTENT_STREAMING_ENABLED="1")
            _ = fx.write_scenario(_usage_turn_events())
            calls: list[int] = []
            tail_cls = _bval("_TranscriptTail")
            real = getattr(tail_cls, "_drain_post_eof")

            def spy(self: object) -> None:
                calls.append(1)
                real(self)

            with mock.patch.object(tail_cls, "_drain_post_eof", spy):
                (code, body), text = cast(
                    "tuple[tuple[int, dict[str, object]], str]",
                    _stderr_of(lambda: _json_usage(self._ctx(False))),
                )
            self.assertEqual(code, 200)
            self.assertEqual(calls, [1])
            self.assertEqual(text.count(" drain cid="), 1)
            usage = _dict(body["usage"])
            self.assertEqual(usage["prompt_tokens"], 59286)
            self.assertEqual(usage["completion_tokens"], _USAGE_TURN_SUM)
            choice = _dict(cast("list[object]", body["choices"])[0])
            self.assertEqual(_dict(choice["message"])["content"], "ответ")

    def test_usage_http_agy_error_stays_error_without_clamped_usage(self) -> None:
        with _Fixture() as fx:
            _usage_flags(fx)
            events = [
                _init_ev(0.05),
                _text_ev(0.1, "частичный ответ"),
                _usage_result_ev(0.2, dict(_RAW_CUMULATIVE), 2, "ERROR", "boom"),
                _exit_ev(0.25, code=1),
            ]
            _ = fx.write_scenario(events)
            (code, body), text = cast(
                "tuple[tuple[int, dict[str, object]], str]",
                _stderr_of(lambda: _json_usage(self._ctx(False))),
            )
            self.assertEqual(code, 502)
            self.assertNotIn("usage", body)
            self.assertEqual(_dict(body["error"])["type"], "agy_error")
            done = [ln for ln in text.splitlines() if " done model=" in ln]
            self.assertIn("state=agy_error", done[0])
            self.assertIn("usage_source=result", done[0])
            self.assertIn("reason=not_success", done[0])
            self.assertNotIn("usage-cumulative-fallback", text)

    def test_usage_http_without_transcript_uses_bounded_estimate(self) -> None:
        with _Fixture() as fx:
            _usage_flags(fx)
            events = [
                _init_ev(0.05),
                _text_ev(0.1),
                _usage_result_ev(0.15, dict(_RAW_CUMULATIVE), 2),
                _exit_ev(0.17),
            ]
            _ = fx.write_scenario(events)
            (code, body), text = cast(
                "tuple[tuple[int, dict[str, object]], str]",
                _stderr_of(lambda: _json_usage(self._ctx(False))),
            )
            self.assertEqual(code, 200)
            usage = _dict(body["usage"])
            self.assertEqual(
                usage["prompt_tokens"], 1552662 // 2
            )  # turns=2, tools=0 -> N=2
            self.assertNotIn("prompt_tokens_details", usage)  # cache 982479 > оценки
            self.assertIn("usage-cumulative-fallback", text)


class StepScopedUsageRuntimeFlagTests(unittest.TestCase):
    """VER-004 (USG-13/USG-14): пятый флаг step_scoped_usage_enabled."""

    _NAME = "step_scoped_usage_enabled"
    _ENV = "AGY_STEP_SCOPED_USAGE_ENABLED"

    def test_runtime_config_snapshot_step_scoped_usage_code_default_and_registry(
        self,
    ) -> None:
        self.assertIs(getattr(_bfn("_RuntimeFlags")(), self._NAME), False)
        self.assertEqual(_dict(_bval("_NEW_FLAG_ENV"))[self._NAME], self._ENV)
        self.assertIn(self._NAME, _FLAG_NAMES)
        with _Fixture() as fx:
            _clean_flags(fx)
            _ = _clocked(fx)
            self.assertIs(_bfn("_new_flag")(self._NAME), False)  # нет файла

    def test_runtime_config_snapshot_step_scoped_usage_json_bool_and_neighbors_unchanged(
        self,
    ) -> None:
        with _Fixture() as fx:
            _clean_flags(fx)
            clock = _clocked(fx)
            new_flag = _bfn("_new_flag")
            _write_cfg(fx, {self._NAME: True}, 1_000_000_000)
            clock.advance(1.1)
            self.assertIs(new_flag(self._NAME), True)
            for other in _FLAG_NAMES:
                if other != self._NAME:
                    self.assertIs(new_flag(other), False, other)
            _write_cfg(fx, {"emit_tool_trace": True}, 2_000_000_000)
            clock.advance(1.1)
            self.assertIs(new_flag(self._NAME), False)  # нет ключа -> False
            self.assertIs(new_flag("emit_tool_trace"), True)

    def test_runtime_config_snapshot_step_scoped_usage_env_spellings_beat_json(
        self,
    ) -> None:
        with _Fixture() as fx:
            _clean_flags(fx)
            clock = _clocked(fx)
            new_flag = _bfn("_new_flag")
            _write_cfg(fx, {self._NAME: True}, 1_000_000_000)
            clock.advance(1.1)
            for raw in ("0", "false", "No", "OFF", " False "):
                with self.subTest(off=raw):
                    fx.set_env(self._ENV, raw)
                    self.assertIs(new_flag(self._NAME), False)
            _write_cfg(fx, {self._NAME: False}, 2_000_000_000)
            clock.advance(1.1)
            for raw in ("1", "true", "Yes", "ON", " True "):
                with self.subTest(on=raw):
                    fx.set_env(self._ENV, raw)
                    self.assertIs(new_flag(self._NAME), True)
            fx.set_env(self._ENV, "garbage")
            self.assertIs(new_flag(self._NAME), False)

    def test_runtime_config_snapshot_step_scoped_usage_ttl_stat_key_and_lastgood(
        self,
    ) -> None:
        with _Fixture() as fx:
            _clean_flags(fx)
            clock = _clocked(fx)
            snap = _bfn("_runtime_snapshot")
            on = '{"step_scoped_usage_enabled":true }'
            off = '{"step_scoped_usage_enabled":false}'
            self.assertEqual(len(on), len(off))
            _write_cfg(fx, on, 1_000_000_000)
            first = snap()
            self.assertIs(_oval(first, self._NAME), True)
            _write_cfg(fx, off, 2_000_000_000)
            clock.advance(0.99)
            self.assertIs(snap(), first)  # до TTL 1.0 с — без stat
            clock.advance(0.02)
            self.assertIs(_oval(snap(), self._NAME), False)
            with mock.patch.object(json, "loads", side_effect=json.loads) as spy:
                clock.advance(5.0)
                _ = snap()
            self.assertEqual(spy.call_count, 0)  # stat не менялся: JSON не разбирается
            _write_cfg(fx, on, 3_000_000_000)
            clock.advance(1.1)
            self.assertIs(_oval(snap(), self._NAME), True)
            for bad in ('{"step_scoped_usage_enabled": "true"}', "{broken", "[]", ""):
                with self.subTest(bad=bad):
                    _write_cfg(fx, bad, 4_000_000_000 + len(bad))
                    clock.advance(1.1)
                    self.assertIs(_oval(snap(), self._NAME), True)  # last-known-good
        for bad in ('{"step_scoped_usage_enabled": 1}', "{broken"):
            with self.subTest(cold=bad), _Fixture() as fx:
                _clean_flags(fx)
                _ = _clocked(fx)
                _write_cfg(fx, bad, 1_000_000_000)
                self.assertIs(_bfn("_new_flag")(self._NAME), False)

    def test_runtime_config_snapshot_step_scoped_usage_live_toggle_at_finalization(
        self,
    ) -> None:
        with _Fixture() as fx:
            _clean_flags(fx)
            clock = _clocked(fx)
            attach = _bval("Handler")._attach_resolved_usage  # type: ignore[attr-defined]
            run = SimpleNamespace(usage_snapshot=lambda: _snap(), run_cid="")
            usage = {"input_tokens": 5, "output_tokens": 2}

            def final_out() -> dict[str, object]:
                out = _usage_out(usage=dict(usage))
                with mock.patch.object(sys, "stderr", io.StringIO()):
                    attach(run, out, _USAGE_MODEL)
                return out

            _write_cfg(fx, {self._NAME: True}, 1_000_000_000)
            self.assertIn("usage_resolved", final_out())
            _write_cfg(fx, {self._NAME: False}, 2_000_000_000)
            clock.advance(1.1)  # без рестарта: следующий финал снова legacy
            self.assertNotIn("usage_resolved", final_out())
            fx.set_env(self._ENV, "1")
            self.assertIn("usage_resolved", final_out())  # env выше файла, сразу
            fx.set_env(self._ENV, "0")
            self.assertNotIn("usage_resolved", final_out())

    def test_runtime_config_snapshot_step_scoped_usage_log_event_names_are_not_masked(
        self,
    ) -> None:
        for name in ("usage-cumulative-fallback", "usage-step-ledger-incomplete"):
            with self.subTest(event=name):
                self.assertGreaterEqual(len(name), 24)
                self.assertIn(name, _bval("_LOG_EVENT_NAMES"))
                self.assertEqual(_bfn("_mask_secrets")(f"{name} a=1"), f"{name} a=1")
        self.assertEqual(_bfn("_mask_secrets")("x" * 30), "***")


if __name__ == "__main__":
    unittest.main()
