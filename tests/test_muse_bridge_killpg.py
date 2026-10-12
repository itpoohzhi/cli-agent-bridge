"""Regression-тесты утечки слотов muse-bridge: killpg группы и обрыв клиента.

2026-10-09: close() Run/ServeRun бил только прямого ребёнка (proc.kill),
sleep-«внук» в группе хода выживал; обрыв клиента во время exec/serve ход не
прерывал — слот держался всю длительность прогона (до TIMEOUT_S), /health
показывал active=1. Тесты гоняют зеркальную копию моста
bridges/muse-bridge/server.py без живого muse-bin: вместо CLI — фейк-обёртка
на sh (serve сразу rc=42 → безусловный fallback на exec, exec держит ход:
лидер + спящий «внук», как реальное дерево muse); для serve-хода — фейк на python,
который проходит handshake и держит turn/start без завершения.
"""

from __future__ import annotations

import importlib.util
import itertools
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable
from unittest import mock

BRIDGE_PY = (
    Path(__file__).resolve().parents[1] / "bridges" / "muse-bridge" / "server.py"
)

_LOAD_SEQ = itertools.count()
DISCONNECT_AFTER_S = 1.0
SCENARIO_DEADLINE_S = 5.0
GROUP_EXIT_WAIT_S = 5.0

# Фейк muse-cli.sh: транспорт serve «недоступен» (мост уходит в fallback exec),
# exec пишет pid лидера группы и держит ход 30 с.
FAKE_WRAPPER = """#!/bin/sh
case "$1" in
  serve)
    exit 42
    ;;
  exec)
    echo $$ > "{pidfile}"
    sleep 30 &
    wait
    ;;
esac
exit 0
"""

# Фейк muse-cli.sh для serve-хода: serve принимает turn/start и держит ход (без
# turn/completed), exec-fallback отмечается отдельным pid-файлом — его появление
# означает, что сценарий serve не удался.
SERVE_WRAPPER = """#!/bin/sh
case "$1" in
  serve)
    exec "{python}" "{script}" "{servepid}"
    ;;
  exec)
    echo $$ > "{pidfile}"
    sleep 30 &
    wait
    ;;
esac
exit 0
"""

# Python-скрипт serve: handshake по NDJSON JSON-RPC, после turn/start — «внук» sleep
# в той же группе и pid-файл лидера (сигнал «serve удерживает ход»), дальше тишина.
FAKE_SERVE_SCRIPT = """import json, os, subprocess, sys, time

pidfile = sys.argv[1]
RESULTS = {
    "session/start": {"session": {"sessionId": "sess-1"}},
    "turn/start": {"status": "accepted", "turnId": "turn-1"},
}
for line in sys.stdin:
    msg = json.loads(line)
    rid = msg.get("id")
    if rid is None:
        continue
    reply = {"jsonrpc": "2.0", "id": rid, "result": RESULTS.get(msg["method"], {})}
    sys.stdout.write(json.dumps(reply) + "\\n")
    sys.stdout.flush()
    if msg["method"] == "turn/start":
        subprocess.Popen(["sleep", "30"])
        with open(pidfile, "w") as fh:
            fh.write(str(os.getpid()))
        while True:
            time.sleep(1)
"""


def load_bridge() -> Any:
    """Свежий экземпляр модуля моста: изолированные _slots/_active на каждый тест."""
    spec = importlib.util.spec_from_file_location(
        f"muse_bridge_server_{next(_LOAD_SEQ)}", BRIDGE_PY
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def group_alive(pgid: int) -> bool:
    """Жива ли группа pgid (сигнал 0 ничего не убивает)."""
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def wait_until(predicate: Callable[[], bool], timeout: float) -> bool:
    """Опрос predicate каждые 50 мс до timeout (замер и на последней границе)."""
    deadline = time.monotonic() + timeout
    while True:
        if predicate():
            return True
        if time.monotonic() >= deadline:
            return predicate()
        time.sleep(0.05)


class CloseKillsGroupTest(unittest.TestCase):
    """R1: close() убивает всю группу хода, а не только прямого ребёнка."""

    @staticmethod
    def _spawn_group() -> subprocess.Popen:
        """Лидер-шелл + sleep-«внук» в собственной группе (start_new_session)."""
        return subprocess.Popen(
            ["/bin/sh", "-c", "sleep 60 & wait"],
            start_new_session=True,
        )

    @staticmethod
    def _reap_group(proc: subprocess.Popen) -> None:
        """Добить и реапнуть свою мок-группу (только свой PGID, чужие не трогаем)."""
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass

    def _assert_close_kills_group(self, run: Any) -> None:
        proc = self._spawn_group()
        self.addCleanup(self._reap_group, proc)
        run.proc = proc
        run.close()
        gone = wait_until(lambda: not group_alive(proc.pid), GROUP_EXIT_WAIT_S)
        self.assertTrue(
            gone,
            f"sleep-внук в группе {proc.pid} пережил close() — утечка процессов",
        )

    def test_r1_run_close_kills_group(self) -> None:
        with tempfile.TemporaryDirectory(prefix="muse-bridge-r1-") as tmp:
            run = load_bridge().Run("muse-spark-1.3", "p", "max", Path(tmp))
            self._assert_close_kills_group(run)

    def test_r1_serve_run_close_kills_group(self) -> None:
        with tempfile.TemporaryDirectory(prefix="muse-bridge-r1-") as tmp:
            run = load_bridge().ServeRun("muse-spark-1.3", "p", "max", Path(tmp))
            self._assert_close_kills_group(run)


class _BridgeScenario(unittest.TestCase):
    """Общий стенд: мост на временном порту с фейк-обёрткой вместо muse-cli."""

    # Значения инициализируются в setUp() каждого теста.
    tmp: Path = Path()
    mod: Any = None
    pidfile: Path = Path()
    servepid: Path = Path()
    server: Any = None

    def wrapper_text(self) -> str:
        """Текст фейк-обёртки; наследники подменяют транспорт."""
        return FAKE_WRAPPER.format(pidfile=self.pidfile)

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="muse-bridge-killpg-"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.mod = load_bridge()
        # Работаем только во временном каталоге: workspace и лог моста — не в репо.
        self.mod.WORKSPACE = self.tmp / "workspace"
        self.mod.LOG_PATH = self.tmp / "bridge.log"
        # Один слот: при двух утечка одного не видна неблокирующей пробой семафора.
        self.mod._slots = threading.Semaphore(1)
        self.pidfile = self.tmp / "run.pid"
        self.servepid = self.tmp / "serve.pid"
        wrapper = self.tmp / "muse-cli.sh"
        wrapper.write_text(self.wrapper_text(), encoding="utf-8")
        wrapper.chmod(0o755)
        self.mod.MUSE_WRAPPER = str(wrapper)
        self.server = self.mod.Server(("127.0.0.1", 0), self.mod.Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self._teardown_scenario)

    def _teardown_scenario(self) -> None:
        """Стоп сервера + добивание своих мок-групп (только свои PGID)."""
        self.server.shutdown()
        self.server.server_close()
        for pidfile in (self.pidfile, self.servepid):
            if pidfile.exists():
                try:
                    os.killpg(
                        int(pidfile.read_text(encoding="utf-8").strip()),
                        signal.SIGKILL,
                    )
                except (ProcessLookupError, OSError, ValueError):
                    pass

    def _open_request(self) -> socket.socket:
        """POST /v1/chat/completions; соединение остаётся открытым (закрывает вызывающий)."""
        body = json.dumps(
            {
                "model": "muse-spark-1.3",
                "messages": [{"role": "user", "content": "hi"}],
            }
        ).encode("utf-8")
        head = (
            "POST /v1/chat/completions HTTP/1.1\r\n"
            "Host: 127.0.0.1\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
        ).encode("utf-8")
        sock = socket.create_connection(self.server.server_address[:2], timeout=5)
        sock.sendall(head + body)
        return sock

    def _post_request_disconnect(self) -> None:
        """POST /v1/chat/completions и обрыв соединения через DISCONNECT_AFTER_S."""
        sock = self._open_request()
        try:
            time.sleep(DISCONNECT_AFTER_S)
        finally:
            sock.close()

    def _slot_free(self) -> bool:
        """Неблокирующая проба семафора слотов (сразу возвращаем взятую ячейку)."""
        sem = self.mod._slots
        if sem.acquire(blocking=False):
            sem.release()
            return True
        return False


class DisconnectScenarioTest(_BridgeScenario):
    """R2/R3: обрыв клиента во время exec-хода освобождает слот и убивает группу."""

    def _run_pid(self) -> int | None:
        """PID лидера exec-группы; None — exec не стартовал (обрыв раньше fallback)."""
        if not wait_until(lambda: self.pidfile.exists(), 4.0):
            return None
        return int(self.pidfile.read_text(encoding="utf-8").strip())

    def _health_active(self) -> int:
        head = (
            "GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n"
        ).encode("utf-8")
        with socket.create_connection(
            self.server.server_address[:2], timeout=5
        ) as sock:
            sock.sendall(head)
            chunks = []
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
        body = b"".join(chunks).split(b"\r\n\r\n", 1)[1]
        return int(json.loads(body.decode("utf-8"))["active"])

    def test_r2_disconnect_frees_slot_and_kills_group(self) -> None:
        self._post_request_disconnect()
        pid = self._run_pid()
        if pid is None:
            # Обрыв успел раньше fallback: exec не запущен, слот обязан быть свободен.
            ok = wait_until(self._slot_free, SCENARIO_DEADLINE_S)
            self.assertTrue(ok, "exec не стартовал после обрыва, но слот занят")
            return
        ok = wait_until(
            lambda: self._slot_free() and not group_alive(pid),
            SCENARIO_DEADLINE_S,
        )
        self.assertTrue(
            ok,
            f"через {DISCONNECT_AFTER_S}s после обрыва слот занят и группа "
            f"{pid} жива: утечка слота сохраняется",
        )

    def test_r3_health_active_zero_after_disconnect(self) -> None:
        self._post_request_disconnect()
        pid = self._run_pid()
        ok = wait_until(lambda: self._health_active() == 0, SCENARIO_DEADLINE_S)
        self.assertTrue(
            ok,
            f"/health active={self._health_active()} после обрыва клиента "
            f"(pid={pid}): disconnect-ход не снялся с учёта",
        )


class ServeDisconnectScenarioTest(_BridgeScenario):
    """R4: обрыв клиента во время живого serve-хода (не exec-fallback)."""

    def wrapper_text(self) -> str:
        script = self.tmp / "fake_serve.py"
        script.write_text(FAKE_SERVE_SCRIPT, encoding="utf-8")
        return SERVE_WRAPPER.format(
            python=sys.executable,
            script=script,
            servepid=self.servepid,
            pidfile=self.pidfile,
        )

    def test_r4_disconnect_during_serve_turn_kills_group_and_frees_slot(self) -> None:
        sock = self._open_request()
        self.addCleanup(sock.close)
        # Ход подтверждён: serve принял turn/start и держит его (pid-файл пишется после ack).
        started = wait_until(lambda: self.servepid.exists(), SCENARIO_DEADLINE_S)
        self.assertTrue(started, "serve-ход не стартовал: сценарий не проверяет serve")
        pid = int(self.servepid.read_text(encoding="utf-8").strip())
        self.assertTrue(group_alive(pid), "serve-группа не жива до обрыва")
        self.assertFalse(self._slot_free(), "слот свободен во время serve-хода")
        self.assertFalse(self.pidfile.exists(), "произошёл exec-fallback вместо serve")

        sock.close()
        ok = wait_until(
            lambda: self._slot_free() and not group_alive(pid), SCENARIO_DEADLINE_S
        )
        self.assertTrue(
            ok,
            f"после обрыва serve-хода слот занят или группа {pid} жива "
            "(ServeRun не входит в /health.active — смотрим группу и семафор)",
        )
        self.assertFalse(self.pidfile.exists(), "после обрыва запущен exec-fallback")


class SpyConn:
    """Обёртка сокета: фиксирует смену режима и флаги recv, остальное — настоящий сокет."""

    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock
        self.settimeout_calls: list[Any] = []
        self.recv_flags: list[int] = []

    def fileno(self) -> int:
        return self._sock.fileno()

    def gettimeout(self) -> float | None:
        return self._sock.gettimeout()

    def settimeout(self, value: Any) -> None:
        self.settimeout_calls.append(value)
        self._sock.settimeout(value)

    def recv(self, size: int, flags: int = 0) -> bytes:
        self.recv_flags.append(flags)
        return self._sock.recv(size, flags)


class ClientGoneProbeTest(unittest.TestCase):
    """R5: проба обрыва клиента не меняет режим общего сокета и не ломает запись."""

    def _probe_pair(self) -> tuple[Any, SpyConn, socket.socket]:
        handler_cls = load_bridge().Handler
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        left.settimeout(5.0)
        spy = SpyConn(left)
        handler = handler_cls.__new__(handler_cls)
        handler.connection = spy  # type: ignore[assignment]
        return handler, spy, right

    def test_probe_uses_msg_dontwait_without_mode_change(self) -> None:
        handler, spy, peer = self._probe_pair()
        peer.sendall(b"x")
        self.assertFalse(handler._client_gone_probe())
        self.assertEqual(spy.settimeout_calls, [], "проба сменила timeout сокета")
        self.assertEqual(spy.gettimeout(), 5.0)
        dontwait = getattr(socket, "MSG_DONTWAIT", 0)
        self.assertTrue(spy.recv_flags, "peek не выполнялся")
        for flags in spy.recv_flags:
            self.assertTrue(flags & socket.MSG_PEEK)
            self.assertTrue(flags & dontwait)

    def test_probe_no_data_is_not_disconnect(self) -> None:
        handler, spy, _peer = self._probe_pair()
        self.assertFalse(handler._client_gone_probe())
        self.assertEqual(spy.settimeout_calls, [])

    def test_probe_leaves_pending_data_unread(self) -> None:
        handler, spy, peer = self._probe_pair()
        peer.sendall(b"x")
        self.assertFalse(handler._client_gone_probe())
        self.assertEqual(spy._sock.recv(1), b"x")

    def test_probe_detects_fin_and_reset(self) -> None:
        handler, _spy, peer = self._probe_pair()
        peer.close()
        self.assertTrue(handler._client_gone_probe())

    def test_probe_does_not_break_concurrent_write(self) -> None:
        """Проба параллельно с большой записью: запись не падает, обрыва не видно."""
        handler, spy, peer = self._probe_pair()
        peer.sendall(b"x")  # select готов -> проба доходит до peek
        stop = threading.Event()
        probes: list[bool] = []

        def prober() -> None:
            while not stop.is_set():
                probes.append(handler._client_gone_probe())

        def drain() -> None:
            while peer.recv(65536):
                pass

        drainer = threading.Thread(target=drain, daemon=True)
        drainer.start()
        thread = threading.Thread(target=prober, daemon=True)
        thread.start()
        try:
            spy._sock.sendall(b"y" * (8 * 1024 * 1024))
        finally:
            stop.set()
            thread.join(timeout=5)
        self.assertTrue(probes)
        self.assertFalse(any(probes), "проба приняла живого клиента за оборвавшегося")
        self.assertEqual(spy.settimeout_calls, [])
        spy._sock.shutdown(socket.SHUT_WR)
        drainer.join(timeout=5)


class QuarantineSlotTest(unittest.TestCase):
    """R6: слот в карантине не возвращается, пока группа жива, даже после потолка."""

    def test_slot_stays_withdrawn_until_group_dies(self) -> None:
        mod = load_bridge()
        mod._slots = threading.Semaphore(1)
        mod._slots.acquire()
        mod.QUARANTINE_MAX_S = 0.3
        logs: list[str] = []
        mod._log = logs.append
        proc = subprocess.Popen(
            ["/bin/sh", "-c", "sleep 60 & wait"], start_new_session=True
        )
        self.addCleanup(CloseKillsGroupTest._reap_group, proc)
        # Живая группа: _kill_group заглушён, поэтому смерть наступает только по нашему killpg.
        kills: list[int] = []
        mod._kill_group = lambda p: kills.append(p.pid)

        mod._quarantine_slot([SimpleNamespace(proc=proc)])

        critical = wait_until(
            lambda: any("CRITICAL" in line for line in logs), SCENARIO_DEADLINE_S
        )
        self.assertTrue(critical, "после потолка карантина нет аварийной эскалации")
        self.assertTrue(
            any(str(proc.pid) in line for line in logs if "CRITICAL" in line),
            "в эскалации нет pgid живой группы",
        )
        self.assertFalse(
            mod._slots.acquire(blocking=False), "слот возвращён при живой группе"
        )
        self.assertFalse(any("slot released" in line for line in logs))

        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=5)
        released = wait_until(
            lambda: any("slot released" in line for line in logs), SCENARIO_DEADLINE_S
        )
        self.assertTrue(released, "слот не вернулся после смерти группы")
        self.assertTrue(mod._slots.acquire(blocking=False), "слот не освобождён")
        time.sleep(1.2)
        self.assertFalse(
            mod._slots.acquire(blocking=False), "слот освобождён больше одного раза"
        )


class WaitGroupExitTest(unittest.TestCase):
    """FU-001: после реапа лидера killpg по старому PGID шлётся не больше одного раза."""

    @staticmethod
    def _count_sigkills(leader_reaped: bool) -> tuple[bool, int]:
        mod = load_bridge()
        sigkills: list[int] = []

        def fake_killpg(pgid: int, sig: int) -> None:
            if sig == signal.SIGKILL:
                sigkills.append(pgid)

        with mock.patch.object(mod.os, "killpg", fake_killpg):
            dead = mod._wait_group_exit(424242, 0.4, leader_reaped=leader_reaped)
        return dead, len(sigkills)

    def test_reaped_leader_gets_single_control_kill(self) -> None:
        dead, count = self._count_sigkills(leader_reaped=True)
        self.assertFalse(dead)
        self.assertEqual(count, 1)

    def test_live_leader_keeps_killing(self) -> None:
        _dead, count = self._count_sigkills(leader_reaped=False)
        self.assertGreater(count, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
