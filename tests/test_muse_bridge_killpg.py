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
import http.client
import io
import itertools
import json
import os
import re
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

_REPO_BRIDGE_PY = (
    Path(__file__).resolve().parents[1] / "bridges" / "muse-bridge" / "server.py"
)
BRIDGE_PY = (
    _REPO_BRIDGE_PY
    if _REPO_BRIDGE_PY.exists()
    else Path(__file__).resolve().parents[1] / "server.py"
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

    def _health_json(self) -> dict[str, Any]:
        """Тело ответа GET /health."""
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
        return json.loads(body.decode("utf-8"))


class HealthQuarantinedTest(_BridgeScenario):
    """FU-004: /health показывает число слотов, изъятых в карантин."""

    def test_health_reports_quarantined_slots(self) -> None:
        self.assertEqual(self._health_json()["quarantined"], 0)
        self.mod._quarantined_slots.append([424242])
        self.assertEqual(self._health_json()["quarantined"], 1)


class DisconnectScenarioTest(_BridgeScenario):
    """R2/R3: обрыв клиента во время exec-хода освобождает слот и убивает группу."""

    def _run_pid(self) -> int | None:
        """PID лидера exec-группы; None — exec не стартовал (обрыв раньше fallback)."""
        if not wait_until(lambda: self.pidfile.exists(), 4.0):
            return None
        return int(self.pidfile.read_text(encoding="utf-8").strip())

    def _health_active(self) -> int:
        return int(self._health_json()["active"])

    def test_r2_disconnect_frees_slot_and_kills_group(self) -> None:
        sock = self._open_request()
        self.addCleanup(sock.close)
        # Обрываем только после появления pid лидера: без запущенного exec сценарий
        # не проверяет killpg и не вправе давать PASS.
        started = wait_until(
            lambda: (
                self.pidfile.exists()
                and self.pidfile.read_text(encoding="utf-8").strip() != ""
            ),
            SCENARIO_DEADLINE_S,
        )
        self.assertTrue(started, "exec не стартовал: сценарий не проверяет killpg")
        pid = int(self.pidfile.read_text(encoding="utf-8").strip())
        self.assertTrue(group_alive(pid), "exec-группа не жива до обрыва")
        time.sleep(DISCONNECT_AFTER_S)
        sock.close()
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
        self.assertEqual(len(mod._quarantined_slots), 1, "слот не учтён в карантине")

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
        self.assertEqual(len(mod._quarantined_slots), 0, "карантин не очищен")
        time.sleep(1.2)
        self.assertFalse(
            mod._slots.acquire(blocking=False), "слот освобождён больше одного раза"
        )

    def test_no_signals_after_ceiling(self) -> None:
        """RW-007: после потолка карантина killpg не шлётся, слот остаётся изъятым."""
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
        kills: list[int] = []
        mod._kill_group = lambda p: kills.append(p.pid)

        mod._quarantine_slot([SimpleNamespace(proc=proc)])
        critical = wait_until(
            lambda: any("CRITICAL" in line for line in logs), SCENARIO_DEADLINE_S
        )
        self.assertTrue(critical, "после потолка карантина нет аварийной эскалации")
        sent = len(kills)
        self.assertGreaterEqual(sent, 1, "до потолка группа не добивалась")
        time.sleep(2.2)
        self.assertEqual(len(kills), sent, "после потолка продолжается спам killpg")
        self.assertFalse(
            mod._slots.acquire(blocking=False), "слот возвращён при живой группе"
        )

    def test_reaped_leader_gets_no_signals(self) -> None:
        """RW-007: лидер реапнут — его PGID свободен для переиспользования, сигналов нет."""
        mod = load_bridge()
        mod._slots = threading.Semaphore(1)
        mod._slots.acquire()
        logs: list[str] = []
        mod._log = logs.append
        # Лидер выходит сразу, «внук» остаётся в группе.
        proc = subprocess.Popen(
            ["/bin/sh", "-c", "sleep 60 & exit 0"], start_new_session=True
        )
        proc.wait(timeout=5)
        self.addCleanup(CloseKillsGroupTest._reap_group, proc)
        self.assertTrue(group_alive(proc.pid), "стенд: группа должна быть жива")
        kills: list[int] = []
        mod._kill_group = lambda p: kills.append(p.pid)

        mod._quarantine_slot([SimpleNamespace(proc=proc)])
        time.sleep(2.2)
        self.assertEqual(kills, [], "killpg по PGID реапнутого лидера")

        os.killpg(proc.pid, signal.SIGKILL)
        released = wait_until(
            lambda: any("slot released" in line for line in logs), SCENARIO_DEADLINE_S
        )
        self.assertTrue(released, "слот не вернулся после смерти группы")


class ConcurrentCloseTest(unittest.TestCase):
    """RW-006: параллельный close() ждёт конца уборки, а не выходит по _closed."""

    def _assert_second_close_waits(self, cls_name: str) -> None:
        mod = load_bridge()
        with tempfile.TemporaryDirectory(prefix="muse-bridge-rw006-") as tmp:
            run = getattr(mod, cls_name)("muse-spark-1.3", "p", "max", Path(tmp))
            proc = CloseKillsGroupTest._spawn_group()
            self.addCleanup(CloseKillsGroupTest._reap_group, proc)
            run.proc = proc
            real_kill = mod._kill_group
            started = threading.Event()
            seen: list[bool] = []

            def slow_kill(p: subprocess.Popen) -> None:
                seen.append(run.dead_confirmed)
                started.set()
                time.sleep(0.6)
                real_kill(p)

            mod._kill_group = slow_kill
            first = threading.Thread(target=run.close)
            first.start()
            self.assertTrue(started.wait(5), "первая уборка не стартовала")
            run.close()
            self.assertFalse(
                group_alive(proc.pid),
                "второй close() вернулся до окончания уборки группы",
            )
            self.assertTrue(run.dead_confirmed)
            self.assertEqual(seen, [False], "во время уборки dead_confirmed не False")
            first.join(timeout=5)

    def test_run_second_close_waits_for_cleanup(self) -> None:
        self._assert_second_close_waits("Run")

    def test_serve_run_second_close_waits_for_cleanup(self) -> None:
        self._assert_second_close_waits("ServeRun")


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


def bridge_request(
    scenario: Any, payload: dict | None = None, path: str = "/v1/chat/completions"
) -> tuple[int, bytes]:
    """Прочитать полный ответ локального стенда, включая терминальный SSE-кадр."""
    conn = http.client.HTTPConnection(*scenario.server.server_address[:2], timeout=5)
    try:
        conn.request(
            "POST" if payload is not None else "GET",
            path,
            json.dumps(payload) if payload is not None else None,
            {"Content-Type": "application/json", "Connection": "close"},
        )
        response = conn.getresponse()
        return response.status, response.read()
    finally:
        conn.close()


def turn_request(stream: bool = False) -> dict:
    """Минимальный клиентский запрос без живого провайдера."""
    return {
        "model": "muse-spark-1.3",
        "messages": [{"role": "user", "content": "prompt-canary-private"}],
        "stream": stream,
    }


class ErrorLoggingTest(_BridgeScenario):
    """AD-001/F-001: все выходы журналируются и не раскрывают отражённые секреты."""

    def _error_response(
        self, state: str, err: Any, stream: bool = False, rc: int = 1
    ) -> tuple[dict, str]:
        out = {"rc": rc, "state": state, "text": "", "err": err}
        with mock.patch.object(self.mod.ServeRun, "execute", return_value=out):
            status, body = bridge_request(self, turn_request(stream))
        self.assertEqual(status, 200 if stream else 502)
        if stream:
            self.assertTrue(body.endswith(b"data: [DONE]\n\n"))
            frames = [
                json.loads(line[6:])
                for line in body.decode().splitlines()
                if line.startswith("data: {")
            ]
            error = next(frame["error"] for frame in frames if "error" in frame)
        else:
            error = json.loads(body)["error"]
        logs = self.mod.LOG_PATH.read_text()
        lines = [line for line in logs.splitlines() if " error model=" in line]
        self.assertTrue(lines, "нет итогового error-лога")
        return error, lines[-1]

    def test_all_error_branches_log_once_and_success_stays_done(self) -> None:
        for stream in (False, True):
            for state in ("launcher_missing", "spawn_failed", "terminal_failed", "ok"):
                with self.subTest(stream=stream, state=state):
                    self.mod.LOG_PATH.unlink(missing_ok=True)
                    error, line = self._error_response(
                        state, "line1\nline2", stream, 0 if state == "ok" else 1
                    )
                    self.assertIn(
                        "state=" + ("empty_output" if state == "ok" else state), line
                    )
                    self.assertIn("via=serve", line)
                    self.assertIn(f"stream={stream}", line)
                    self.assertIn("line1\\nline2", line)
                    self.assertEqual(error["detail"], "line1\nline2")
                    self.assertEqual(
                        sum(
                            " error model=" in x
                            for x in self.mod.LOG_PATH.read_text().splitlines()
                        ),
                        1,
                    )
        with mock.patch.object(
            self.mod.ServeRun,
            "execute",
            return_value={"rc": 0, "state": "ok", "text": "ok", "err": ""},
        ):
            self.mod.LOG_PATH.unlink()
            self.assertEqual(bridge_request(self, turn_request())[0], 200)
        self.assertEqual(
            sum(
                " done model=" in x for x in self.mod.LOG_PATH.read_text().splitlines()
            ),
            1,
        )
        self.assertNotIn(" error model=", self.mod.LOG_PATH.read_text())

    def test_secret_canaries_masked_in_log_json_and_sse(self) -> None:
        samples = [
            "Bearer secret-canary-token-123",
            "Authorization: super-private-value",
            "api_key=canary_secret_val",
            '{"token":"canary_secret_val"}',
            "{'password': 'canary_secret_val'}",
            'password="alpha beta gamma"',
            "TOKEN: canary_secret_val",
            "bridge-key=canary_secret_val",
            "secret=canary_secret_val",
            "sk-abcdefghijklmnop1234",
            "bare-bridge-canary",
        ]
        # Подмена только локальной конфигурации модуля, окружение не меняется.
        self.mod.AUTH_KEY = "bare-bridge-canary"
        for stream in (False, True):
            for sample in samples:
                for prefix in ("", "x" * 285 + " ", "x" * 485 + " "):
                    with self.subTest(stream=stream, sample=sample, prefix=len(prefix)):
                        # Аутентификация запроса не нужна: модульный mock не меняет тестируемую редакцию.
                        with mock.patch.object(self.mod, "_auth_ok", return_value=True):
                            error, line = self._error_response(
                                "terminal_failed", prefix + sample, stream
                            )
                        combined = json.dumps(error) + line
                        for secret in (
                            "secret-canary-token-123",
                            "super-private-value",
                            "canary_secret_val",
                            "alpha beta gamma",
                            "abcdefghijklmnop1234",
                            "bare-bridge-canary",
                        ):
                            self.assertNotIn(secret, combined)
                        if not prefix:
                            self.assertIn("[REDACTED]", error["detail"])
                            self.assertIn("[REDACTED]", line)
                        self.assertLessEqual(len(error["detail"]), 500)
                        self.assertNotIn("prompt-canary-private", combined)

    def test_none_diagnostic_is_empty(self) -> None:
        for state in ("spawn_failed", "terminal_failed", "ok"):
            error, _ = self._error_response(state, None, rc=0 if state == "ok" else 1)
            self.assertEqual(error["detail"], "")

    def test_serve_json_returns_sanitized_detail_on_error(self) -> None:
        secret = "sk-secret-token-1234567890abcdef"
        error, _ = self._error_response(
            "terminal_failed", f"auth_failed: not logged in {secret}"
        )
        self.assertIn(
            "muse turn failed (rc=1, state=terminal_failed)", error["message"]
        )
        self.assertIn("auth_failed", error["message"])
        self.assertIn("[REDACTED]", error["message"])
        self.assertNotIn(secret, error["message"])
        self.assertIn("auth_failed", error["detail"])
        self.assertIn("[REDACTED]", error["detail"])
        self.assertNotIn(secret, error["detail"])

        # SSE-ветка того же отказа: кадр ошибки несёт тот же санитизированный detail.
        sse_error, _ = self._error_response(
            "terminal_failed",
            "sse upstream failed api_key=canary_sse_secret_val",
            True,
        )
        self.assertTrue(
            sse_error["message"].startswith(
                "muse turn failed (rc=1, state=terminal_failed): "
            )
        )
        self.assertIn("sse upstream failed", sse_error["message"])
        self.assertIn("[REDACTED]", sse_error["message"])
        self.assertNotIn("canary_sse_secret_val", sse_error["message"])
        self.assertEqual(
            sse_error["message"],
            "muse turn failed (rc=1, state=terminal_failed): " + sse_error["detail"],
        )
        self.assertIn("[REDACTED]", sse_error["detail"])
        self.assertNotIn("canary_sse_secret_val", sse_error["detail"])

        # Ветка empty_output: успешный rc без текста — 502 с санитизированным detail.
        empty_error, _ = self._error_response(
            "ok",
            "empty upstream failed api_key=canary_empty_secret_val",
            rc=0,
        )
        self.assertTrue(
            empty_error["message"].startswith(
                "muse exec produced no text (rc=0, state=ok): "
            )
        )
        self.assertIn("empty upstream failed", empty_error["message"])
        self.assertIn("[REDACTED]", empty_error["message"])
        self.assertNotIn("canary_empty_secret_val", empty_error["message"])
        self.assertEqual(
            empty_error["message"],
            "muse exec produced no text (rc=0, state=ok): " + empty_error["detail"],
        )
        self.assertIn("[REDACTED]", empty_error["detail"])
        self.assertNotIn("canary_empty_secret_val", empty_error["detail"])

        # Длинная диагностика empty_output: detail в message и detail обрезан до 500.
        long_error, _ = self._error_response(
            "ok",
            "api_key=canary_long_secret_val " + "L" * 600,
            rc=0,
        )
        self.assertEqual(len(long_error["detail"]), 500)
        self.assertTrue(
            long_error["message"].startswith(
                "muse exec produced no text (rc=0, state=ok): "
            )
        )
        self.assertEqual(
            long_error["message"],
            "muse exec produced no text (rc=0, state=ok): " + long_error["detail"],
        )
        self.assertIn("[REDACTED]", long_error["message"])
        self.assertNotIn("canary_long_secret_val", long_error["message"])
        self.assertNotIn("canary_long_secret_val", long_error["detail"])

    def test_generic_diagnostic_not_duplicated_in_message(self) -> None:
        error, _ = self._error_response("terminal_failed", "state=terminal_failed rc=1")
        self.assertEqual(error["detail"], "state=terminal_failed rc=1")
        self.assertEqual(
            error["message"], "muse turn failed (rc=1, state=terminal_failed)"
        )

    def test_default_model_is_wonder_full(self) -> None:
        with mock.patch.dict(os.environ):
            os.environ.pop("MUSE_BRIDGE_MODEL", None)
            fresh = load_bridge()
        self.assertEqual(fresh.DEFAULT_MODEL, "muse-wonder-full-1.0")

    def test_r2_escaped_quotes_mask_entire_secret_in_all_sinks(self) -> None:
        samples = (
            (
                r'{"password": "alpha \" suffix-canary-27182"}',
                '{"password": [REDACTED]}',
            ),
            (r'{"token":"alpha\" beta gamma"}', '{"token":[REDACTED]}'),
        )
        for stream in (False, True):
            for sample, expected in samples:
                with self.subTest(stream=stream, sample=sample):
                    error, _ = self._error_response("terminal_failed", sample, stream)
                    self.assertEqual(error["detail"], expected)
                    logs = self.mod.LOG_PATH.read_text()
                    self.assertNotIn("suffix-canary-27182", logs)
                    self.assertNotIn("beta gamma", logs)

    def _protocol_error_detail(self, content: str, message: str, stream: bool) -> str:
        """Проверить все выходы ошибки реального протокольного стенда."""
        install_protocol_wrapper(
            self, {"terminal": "failed", "error": {"message": message}}
        )
        payload = turn_request(stream)
        payload["messages"][0]["content"] = content
        status, body = bridge_request(self, payload)
        self.assertEqual(status, 200 if stream else 502)
        if stream:
            self.assertTrue(body.endswith(b"data: [DONE]\n\n"))
            frames = [
                json.loads(line[6:])
                for line in body.decode().splitlines()
                if line.startswith("data: {")
            ]
            return next(
                frame["error"]["detail"] for frame in frames if "error" in frame
            )
        return json.loads(body)["error"]["detail"]

    def test_r2_long_reflected_message_redacted_before_clipping(self) -> None:
        content = "private-owner-content-" + "Q" * 220
        for stream in (False, True):
            with self.subTest(stream=stream):
                detail = self._protocol_error_detail(content, content, stream)
                self.assertEqual(detail, "[REDACTED]")
                combined = detail + self.mod.LOG_PATH.read_text()
                self.assertNotIn("private-owner-content-", combined)
                self.assertNotIn("Q" * 20, combined)

    def test_r2_short_messages_preserve_error_words(self) -> None:
        expected = "this turn failed upstream"
        for stream in (False, True):
            for content in ("hi", "e"):
                with self.subTest(stream=stream, content=content):
                    detail = self._protocol_error_detail(content, expected, stream)
                    self.assertEqual(detail, expected)
                    self.assertIn(expected, self.mod.LOG_PATH.read_text())

    def test_quota_secrets_do_not_reach_any_error_sink(self) -> None:
        samples = (
            "api_key=canary_secret_val",
            '{"token":"canary_secret_val"}',
            "{'password': 'canary_secret_val'}",
            'password="alpha beta gamma"',
        )
        for stream in (False, True):
            for sample in samples:
                with self.subTest(stream=stream, sample=sample):
                    params = {
                        "terminal": "failed",
                        "error": {
                            "kind": "quota",
                            "message": sample,
                            "quota": {
                                "token": "canary_secret_val",
                                "note": sample,
                            },
                        },
                        "stderr": sample,
                    }
                    install_protocol_wrapper(self, params)
                    status, body = bridge_request(self, turn_request(stream))
                    self.assertEqual(status, 200 if stream else 502)
                    logs = self.mod.LOG_PATH.read_text()
                    for secret in ("canary_secret_val", "alpha beta gamma"):
                        self.assertNotIn(secret, body.decode() + logs)
                    self.assertIn("[REDACTED]", body.decode())
                    self.assertIn("[REDACTED]", logs)
        for key in (
            "token",
            "secret",
            "password",
            "api_key",
            "bridge_key",
            "authorization",
        ):
            quota = {"outer": [{key: "alpha beta gamma"}]}
            install_protocol_wrapper(
                self, {"terminal": "failed", "error": {"quota": quota}}
            )
            _, body = bridge_request(self, turn_request())
            self.assertIn("[REDACTED]", body.decode())
            self.assertNotIn(
                "alpha beta gamma", body.decode() + self.mod.LOG_PATH.read_text()
            )


def install_protocol_wrapper(
    scenario: Any, params: dict, noise: bool = False, delay: float = 0
) -> None:
    """Фейковый MSP с реальными pipes; фиксирует argv и входящие RPC."""
    config = {
        "params": params,
        "noise": noise,
        "delay": delay,
        "root": str(scenario.tmp),
    }
    script = scenario.tmp / "protocol.py"
    script.write_text(
        """import json, sys, time
from pathlib import Path
config = json.loads(sys.argv[1])
root = Path(config["root"])
mode = sys.argv[2]
(root / (mode + "-argv.json")).write_text(json.dumps(sys.argv[2:]))
if mode == "exec":
    print(json.dumps({"schema_version": 1, "payload_type": "run.terminal.completed", "payload": {"text": "fallback-ok"}}), flush=True)
    sys.exit(0)
for line in sys.stdin:
    msg = json.loads(line)
    with (root / "rpc.jsonl").open("a") as fh:
        fh.write(json.dumps(msg) + "\\n")
    if "id" not in msg:
        continue
    method = msg["method"]
    result = {"session": {"sessionId": "sess-1"}} if method == "session/start" else {"status": "accepted", "turnId": "turn-1"} if method == "turn/start" else {}
    print(json.dumps({"id": msg["id"], "result": result}), flush=True)
    if method == "turn/start":
        time.sleep(config["delay"])
        if config["params"].get("approval"):
            print(json.dumps({"jsonrpc": "2.0", "id": 99, "method": "approval/request", "params": {}}), flush=True)
            break
        print(json.dumps({"method": "item/completed", "params": {"item": {"itemId": "a", "turnId": "turn-1", "kind": "agentMessage", "text": "hello"}}}), flush=True)
        print(json.dumps({"method": "turn/completed", "params": dict(config["params"], turnId="turn-1")}), flush=True)
        if config["params"].get("stderr"):
            print(config["params"]["stderr"], file=sys.stderr, flush=True)
        if config["noise"]:
            for i in range(12):
                print("noise-%02d-" % i + "z" * 100, file=sys.stderr, flush=True)
        break
""",
        encoding="utf-8",
    )
    import shlex

    wrapper = scenario.tmp / "muse-cli.sh"
    wrapper.write_text(
        f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(script))} {shlex.quote(json.dumps(config))} "$@"\n'
    )
    wrapper.chmod(0o755)
    scenario.mod.MUSE_WRAPPER = str(wrapper)


_FAKE_MSP_HEAD = """import json, os, sys, time
from pathlib import Path
cfg = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
root = Path(cfg["root"]); mode = sys.argv[2]
(root / (mode + "-argv.json")).write_text(json.dumps(sys.argv[2:]), encoding="utf-8")
with (root / (mode + "-argv.jsonl")).open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(sys.argv[2:]) + "\\n")
def bump(name):
    p = root / name
    n = int(p.read_text(encoding="utf-8")) if p.exists() else 0
    n += 1; p.write_text(str(n), encoding="utf-8"); return n
def effect(name):
    with (root / "effects.log").open("a", encoding="utf-8") as fh:
        fh.write(str(name) + "\\n")
idx = bump(mode + "-count.txt")
if mode == "exec":
    plans = cfg.get("exec_plans") or [{"text": "fallback-ok"}]
    plan = plans[min(idx - 1, len(plans) - 1)]
    if plan.get("effect"): effect(plan["effect"])
    if plan.get("delay"): time.sleep(float(plan["delay"]))
    if plan.get("stderr"): print(plan["stderr"], file=sys.stderr, flush=True)
    rc = int(plan.get("rc", 0))
    if rc == 0:
        print(json.dumps({"schema_version": 1, "payload_type": "run.terminal.completed", "payload": {"text": plan.get("text", "fallback-ok")}}), flush=True)
    sys.exit(rc)
plans = cfg.get("serve_plans") or [{}]
plan = plans[min(idx - 1, len(plans) - 1)]
with (root / "serve-pids.log").open("a", encoding="utf-8") as fh:
    fh.write(str(os.getpid()) + "\\n")
active_file = None
if cfg.get("track_concurrency"):
    active_file = root / ("active-%d" % os.getpid()); active_file.write_text("1")
    with (root / "concurrency.log").open("a", encoding="utf-8") as fh:
        fh.write(str(len(list(root.glob("active-*")))) + "\\n")
if plan.get("handshake_eof"):
    sys.exit(0)
if plan.get("handshake_hang"):
    time.sleep(30); sys.exit(0)
def send(obj):
    sys.stdout.write(json.dumps(obj) + "\\n"); sys.stdout.flush()
def read_msg():
    line = sys.stdin.readline()
    if not line: raise EOFError
    msg = json.loads(line)
    with (root / "rpc.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(msg) + "\\n")
    return msg
_decide_i = [0]
def decide_reply(rid):
    reps = plan.get("decide_replies") or [{"result": {"terminal": True}}]
    rep = reps[min(_decide_i[0], len(reps) - 1)]; _decide_i[0] += 1
    if "error" in rep: send({"jsonrpc": "2.0", "id": rid, "error": rep["error"]})
    else: send({"jsonrpc": "2.0", "id": rid, "result": rep.get("result", {})})
def cancel_reply(rid):
    rep = plan.get("cancel_reply") or {}
    if "error" in rep: send({"jsonrpc": "2.0", "id": rid, "error": rep["error"]})
    else: send({"jsonrpc": "2.0", "id": rid, "result": rep.get("result", {})})
def await_command():
    while True:
        msg = read_msg(); m = msg.get("method")
        if m == "approval/decide": decide_reply(msg["id"]); return msg
        if m in ("userInput/cancel", "turn/cancel"): cancel_reply(msg["id"]); return msg
def appr_payload(over=None, n=0):
    aid = "appr-%d" % n
    base = {"approvalId": aid, "availableChoices": [
        {"choiceId": "c-approve", "decision": "approved", "label": "Allow", "scope": "once"},
        {"choiceId": "c-abort", "decision": "abort", "label": "Abort", "scope": "once"}],
        "currentRequirementId": {"approvalId": aid, "sourceIndex": n}, "itemId": "item-1",
        "judgeEscalated": False, "protectedWrite": False, "rawArgs": "{}", "sessionId": "sess-1",
        "sourceRange": {}, "subject": {"kind": "tool", "toolName": "web_search"}, "taskId": "task-1",
        "toolCallId": "tc-1", "toolName": "web_search", "turnId": "turn-1", "viewCursor": "0"}
    if over: base.update(over)
    return base
def do_approval(over=None, req_mode="request", n=0):
    payload = appr_payload(over, n)
    if req_mode == "requested":
        send({"jsonrpc": "2.0", "method": "approval/requested", "params": payload})
    else:
        send({"jsonrpc": "2.0", "id": 9000 + n, "method": "approval/request", "params": payload})
    return await_command()
def ui_payload(over=None, n=0):
    base = {"userInputId": "ui-%d" % n, "sessionId": "sess-1", "toolName": "ask_user",
            "itemId": "item-1", "toolCallId": "tc-1", "turnId": "turn-1", "viewCursor": "0",
            "sourceRange": {}, "questions": [{"questionId": "q1", "text": "question"}]}
    if over: base.update(over)
    return base
def do_user_input(over=None, n=0):
    send({"jsonrpc": "2.0", "id": 9100 + n, "method": "userInput/request", "params": ui_payload(over, n)})
    return await_command()
"""

_FAKE_MSP_TAIL = """_started = set()
def ensure_item(kind):
    iid = "r1" if kind == "reasoning" else "a1" if kind == "agentMessage" else "t1"
    if iid not in _started:
        _started.add(iid)
        send({"jsonrpc": "2.0", "method": "item/started", "params": {"item": {"itemId": iid, "turnId": "turn-1", "kind": kind}}})
    return iid
def run_steps():
    for step in plan.get("steps") or []:
        if "delay" in step: time.sleep(float(step["delay"]))
        elif "effect" in step: effect(step["effect"])
        elif "approval" in step: do_approval(step["approval"] if isinstance(step["approval"], dict) else None, step.get("mode", "request"), int(step.get("n", 0)))
        elif "approval_repeat" in step:
            for i in range(int(step["approval_repeat"])): do_approval(None, "request", i)
        elif "approval_nowait" in step:
            over = step["approval_nowait"] if isinstance(step["approval_nowait"], dict) else None
            n = int(step.get("n", 7))
            send({"jsonrpc": "2.0", "id": 9200 + n, "method": "approval/request", "params": appr_payload(over, n)})
        elif "approval_then_exit" in step:
            over = step["approval_then_exit"] if isinstance(step["approval_then_exit"], dict) else None
            send({"jsonrpc": "2.0", "id": 9300, "method": "approval/request", "params": appr_payload(over, 0)})
            sys.stdout.flush(); os._exit(0)
        elif "user_input" in step: do_user_input(step["user_input"] if isinstance(step["user_input"], dict) else None, int(step.get("n", 0)))
        elif "user_input_repeat" in step:
            for i in range(int(step["user_input_repeat"])): do_user_input(None, i)
        elif "summary" in step:
            ensure_item("reasoning")
            sidx, text = step["summary"]
            send({"jsonrpc": "2.0", "method": "item/delta", "params": {"itemId": "r1", "field": "summary.%s" % sidx, "delta": text}})
        elif "reasoning_completed" in step:
            ensure_item("reasoning")
            send({"jsonrpc": "2.0", "method": "item/completed", "params": {"item": {"itemId": "r1", "turnId": "turn-1", "kind": "reasoning", "summary": list(step["reasoning_completed"])}}})
        elif "tool_item" in step:
            ti = step["tool_item"] if isinstance(step["tool_item"], dict) else {}
            item = {"itemId": "t1", "turnId": "turn-1", "kind": ti.get("kind", "toolCall"), "toolName": ti.get("toolName", "web_search"), "rawArgs": ti.get("rawArgs", "{}")}
            send({"jsonrpc": "2.0", "method": "item/started", "params": {"item": item}})
            send({"jsonrpc": "2.0", "method": "item/completed", "params": {"item": item}})
        elif "model_retry" in step:
            send({"jsonrpc": "2.0", "method": "turn/modelRetryScheduled", "params": dict(step["model_retry"])})
        elif "text_delta" in step:
            ensure_item("agentMessage")
            send({"jsonrpc": "2.0", "method": "item/delta", "params": {"itemId": "a1", "field": "text", "delta": step["text_delta"]}})
        elif "eof" in step:
            sys.stdout.flush(); os._exit(0)
        elif "hang" in step:
            while True:
                msg = read_msg(); m = msg.get("method")
                if m == "approval/decide": decide_reply(msg["id"])
                elif m in ("userInput/cancel", "turn/cancel"): cancel_reply(msg["id"])
        elif "no_read_hang" in step:
            while True: time.sleep(1)
        elif "terminal" in step:
            t = step["terminal"] if isinstance(step["terminal"], dict) else {}
            if t.get("text"):
                ensure_item("agentMessage")
                send({"jsonrpc": "2.0", "method": "item/completed", "params": {"item": {"itemId": "a1", "turnId": "turn-1", "kind": "agentMessage", "text": t["text"]}}})
            params = {"turnId": "turn-1", "sessionId": "sess-1", "terminal": t.get("terminal", "completed")}
            for key in ("error", "reason", "timeToFirstTokenMs", "usage", "durationMs"):
                if key in t: params[key] = t[key]
            send({"jsonrpc": "2.0", "method": "turn/completed", "params": params})
            return
def maybe_setup(when):
    sa = plan.get("setup_approval")
    if not sa or sa.get("when") != when: return False
    do_approval(sa.get("payload") if isinstance(sa.get("payload"), dict) else None, sa.get("mode", "request"), 0)
    if sa.get("effect"): effect(sa["effect"])
    return sa.get("after") == "break"
try:
    while True:
        msg = read_msg(); method = msg.get("method")
        if method == "initialize":
            if maybe_setup("initialize"):
                send({"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32603, "message": plan.get("setup_approval", {}).get("break_message", "[net-timeout] setup break")}}); break
            send({"jsonrpc": "2.0", "id": msg["id"], "result": {"serverInfo": {"version": "1.4.9-test"}, "schema": {"fingerprint": "fp-test-1234567890abcdef"}}})
        elif method == "session/start":
            if maybe_setup("session/start"):
                send({"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32603, "message": plan.get("setup_approval", {}).get("break_message", "[net-timeout] setup break")}}); break
            if plan.get("setup_delay"): time.sleep(float(plan["setup_delay"]))
            se = plan.get("session_error")
            if se:
                send({"jsonrpc": "2.0", "id": msg["id"], "error": se}); break
            if plan.get("no_session_id"):
                send({"jsonrpc": "2.0", "id": msg["id"], "result": {"session": {}}}); continue
            reqmode = (msg.get("params") or {}).get("approvalMode") or "allowAll"
            send({"jsonrpc": "2.0", "id": msg["id"], "result": {"session": {"sessionId": "sess-1", "approvalMode": {"mode": reqmode, "source": "startup", "lastCommandId": None}}}})
        elif method == "turn/start":
            if plan.get("turn_start_eof"): os._exit(0)
            if plan.get("turn_delay"): time.sleep(float(plan["turn_delay"]))
            send({"jsonrpc": "2.0", "id": msg["id"], "result": {"status": "accepted", "turnId": "turn-1"}})
            run_steps(); break
        elif method == "approval/decide": decide_reply(msg["id"])
        elif method in ("userInput/cancel", "turn/cancel"): cancel_reply(msg["id"])
except EOFError:
    pass
finally:
    if active_file is not None:
        try: active_file.unlink()
        except OSError: pass
"""

FAKE_MSP_SCRIPT = _FAKE_MSP_HEAD + _FAKE_MSP_TAIL

_OK_STEP = {"terminal": {"terminal": "completed", "text": "hello"}}


def ok_plan(*steps: dict) -> dict:
    """План serve, завершающийся успешным hello после шагов."""
    return {"steps": [*steps, _OK_STEP]}


def fail_terminal(marker: str, **extra: Any) -> dict:
    """Шаг транзиентного терминального провала serve."""
    term: dict[str, Any] = {
        "terminal": "failed",
        "error": {"kind": "network", "message": marker},
    }
    term.update(extra)
    return {"terminal": term}


def install_fake_msp(
    scenario: Any,
    serve_plans: list[dict] | None = None,
    exec_plans: list[dict] | None = None,
    track_concurrency: bool = False,
) -> None:
    """Расширенный фейковый MSP (a4): планы по вызовам, rpc.jsonl, счётчики."""
    import shlex

    for name in (
        "rpc.jsonl",
        "effects.log",
        "serve-count.txt",
        "exec-count.txt",
        "serve-argv.jsonl",
        "exec-argv.jsonl",
        "serve-pids.log",
        "concurrency.log",
    ):
        try:
            (scenario.tmp / name).unlink()
        except OSError:
            pass
    cfg = {
        "root": str(scenario.tmp),
        "serve_plans": serve_plans or [ok_plan()],
        "exec_plans": exec_plans or [{"text": "fallback-ok"}],
        "track_concurrency": track_concurrency,
    }
    cfg_path = scenario.tmp / "fake-cfg.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    script = scenario.tmp / "fake_msp.py"
    script.write_text(FAKE_MSP_SCRIPT, encoding="utf-8")
    wrapper = scenario.tmp / "muse-cli.sh"
    wrapper.write_text(
        f"#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(script))} "
        f'{shlex.quote(str(cfg_path))} "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    scenario.mod.MUSE_WRAPPER = str(wrapper)


def rpc_msgs(scenario: Any) -> list[dict]:
    """Все входящие RPC фейка (мост -> serve), включая receipt-ответы."""
    path = scenario.tmp / "rpc.jsonl"
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def rpc_by_method(scenario: Any, method: str) -> list[dict]:
    return [m for m in rpc_msgs(scenario) if m.get("method") == method]


def proc_count(scenario: Any, mode: str) -> int:
    """Число запусков serve/exec по argv-журналу фейка."""
    path = scenario.tmp / f"{mode}-argv.jsonl"
    if not path.exists():
        return 0
    return len(
        [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    )


def effect_lines(scenario: Any) -> list[str]:
    path = scenario.tmp / "effects.log"
    if not path.exists():
        return []
    return [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def sse_frames(body: bytes) -> list[dict]:
    return [
        json.loads(line[6:])
        for line in body.decode("utf-8", "replace").splitlines()
        if line.startswith("data: {")
    ]


def sse_deltas(body: bytes, key: str) -> list[str]:
    out: list[str] = []
    for frame in sse_frames(body):
        for choice in frame.get("choices") or []:
            delta = choice.get("delta") or {}
            if isinstance(delta.get(key), str):
                out.append(delta[key])
    return out


class ServeTurnErrorExtractionTest(_BridgeScenario):
    """AD-002: приоритет, защитный разбор и точные лимиты терминальной причины."""

    def _execute(self, params: dict, noise: bool = False) -> dict:
        install_protocol_wrapper(self, params, noise)
        return self.mod.ServeRun(
            "muse-spark-1.3", "p", "max", self.tmp / "workspace"
        ).execute()

    def test_r2_prompt_parts_redacted_before_and_after_normalization(self) -> None:
        content = "private-owner-content-" + "Q" * 220
        prompt = "User: " + content + "\n\nAssistant: prior\tprivate\nSystem: hi"
        parts = self.mod._prompt_reflected_parts(prompt)
        self.assertEqual(parts, sorted(parts, key=len, reverse=True))
        self.assertIn(content, parts)
        self.assertIn("prior\tprivate", parts)
        self.assertNotIn("hi", parts)
        for reflected in (content, "prior\tprivate", "prior private"):
            with self.subTest(reflected=reflected):
                diagnostic = self.mod._turn_diagnostics(
                    {"error": {"message": reflected}}, prompt
                )
                self.assertEqual(diagnostic, ["[REDACTED]"])

    def test_typed_error_reason_and_stderr_priority(self) -> None:
        params = {
            "terminal": "failed",
            "error": {
                "kind": "quota_exceeded",
                "message": "daily limit",
                "retryable": False,
                "quota": {"remaining": 0},
            },
            "reason": "try tomorrow",
        }
        out = self._execute(params, True)
        expected = 'quota_exceeded: daily limit retryable=False quota={"remaining":0}\nreason: try tomorrow'
        self.assertTrue(out["err"].startswith(expected), out)
        self.assertEqual((out["rc"], out["state"]), (1, "terminal_failed"))
        self.assertLessEqual(len(out["err"]), 500)
        for stream in (False, True):
            with mock.patch.object(self.mod.ServeRun, "execute", return_value=out):
                _, body = bridge_request(self, turn_request(stream))
            self.assertIn("quota_exceeded", body.decode())
            self.assertIn("try tomorrow", body.decode())
        self.assertIn("try tomorrow", self.mod.LOG_PATH.read_text())

    def test_reason_only_duplicate_and_malformed(self) -> None:
        for error, reason, expected in [
            (None, "cancelled by caller", "reason: cancelled by caller"),
            ({"message": "same"}, "same", "same"),
            ("raw failure", None, "raw failure"),
            ({"kind": 123, "quota": [1, 2]}, None, "123"),
            (["odd"], 17, "17"),
        ]:
            with self.subTest(error=error):
                out = self._execute(
                    {"terminal": "failed", "error": error, "reason": reason}
                )
                self.assertEqual(out["state"], "terminal_failed")
                self.assertIn(expected, out["err"])
                if reason == "same":
                    self.assertEqual(out["err"].count("same"), 1)

    def test_no_diagnostics_preserves_stderr_tail_and_success(self) -> None:
        tail = "\n".join("noise-%02d-" % i + "z" * 100 for i in range(6, 12))
        for terminal in ("failed", "completed"):
            out = self._execute({"terminal": terminal}, True)
            self.assertEqual(out["err"], tail)
            self.assertEqual(
                out["state"], "ok" if terminal == "completed" else "terminal_failed"
            )

    def test_field_caps_budget_and_redaction_boundaries(self) -> None:
        for field, limit in (("kind", 64), ("message", 160), ("reason", 160)):
            params: dict = {"terminal": "failed", "error": {}}
            (params if field == "reason" else params["error"])[field] = "X" * (
                limit + 20
            )
            out = self._execute(params)
            self.assertIn("X" * limit, out["err"])
            self.assertNotIn("X" * (limit + 1), out["err"])
        out = self._execute(
            {
                "terminal": "failed",
                "error": {
                    "kind": "K" * 90,
                    "message": "M" * 200,
                    "retryable": True,
                    "quota": {"data": "Q" * 200},
                },
                "reason": "R" * 200,
            },
            True,
        )
        diagnostic = out["err"].split("\nnoise-", 1)[0]
        self.assertEqual(len(diagnostic), 300)
        self.assertIn("K" * 64, diagnostic)
        self.assertIn("R" * 16, diagnostic)
        self.assertNotIn("quota=", diagnostic)
        self.assertNotIn("\r", diagnostic)
        out = self._execute(
            {
                "terminal": "failed",
                "error": {"message": "m" * 155 + " api_key=canary_secret_val"},
            }
        )
        self.assertNotIn("canary", out["err"])
        self.assertNotIn("[REDAC", out["err"].replace("[REDACTED]", ""))


class SseDataKeepaliveTest(_BridgeScenario):
    """AD-003: S1/S2/S3 проверяют байты и события, без гонок очереди замка."""

    def _handler(self, writer: Any = None) -> Any:
        handler = self.mod.Handler.__new__(self.mod.Handler)
        handler._wlock = threading.Lock()
        handler.wfile = writer if writer is not None else io.BytesIO()
        handler._sse_open = True
        return handler

    def test_defaults_and_s3_seal_suppresses_late_tick_and_duplicate_done(self) -> None:
        handler = self._handler()
        other = self._handler()
        self.assertEqual(handler._sse_phase, "OPEN")
        self.assertIsNone(handler._keepalive_stop)
        self.assertFalse(handler._client_gone)
        handler._keepalive_stop = threading.Event()
        self.assertIsNone(other._keepalive_stop)
        handler._sse_stop_keepalive()
        before = handler.wfile.getvalue()
        self.assertFalse(
            handler._sse_emit(handler._sse_chunk({"content": ""}), keepalive=True)
        )
        self.assertEqual(handler.wfile.getvalue(), before)
        handler._send_sse("muse-spark-1.3", "hello", [], 1, 1, 0)
        final = handler.wfile.getvalue()
        self.assertTrue(final.endswith(b"data: [DONE]\n\n"))
        self.assertEqual(handler._sse_phase, "CLOSED")
        self.assertFalse(
            handler._sse_emit(handler._sse_chunk({"content": ""}), keepalive=True)
        )
        self.assertFalse(handler._sse_write("data: [DONE]\n\n"))
        self.assertFalse(handler._sse_emit({"late": True}))
        self.assertEqual(handler.wfile.getvalue(), final)

    def test_s1_data_ticks_before_done_preserve_content_and_tools(self) -> None:
        install_protocol_wrapper(self, {"terminal": "completed"}, delay=0.2)
        self.mod.KEEPALIVE_S = 0.05
        _, body = bridge_request(self, turn_request(True))
        self.assertNotIn(b": keepalive", body)
        self.assertTrue(body.endswith(b"data: [DONE]\n\n"))
        self.assertEqual(body.count(b"data: [DONE]"), 1)
        frames = [
            json.loads(line[6:])
            for line in body.decode().splitlines()
            if line.startswith("data: {")
        ]
        deltas = [frame["choices"][0]["delta"] for frame in frames]
        self.assertTrue(any(delta == {"content": ""} for delta in deltas))
        self.assertTrue(
            all(frame["object"] == "chat.completion.chunk" for frame in frames)
        )
        self.assertEqual("".join(d.get("content", "") for d in deltas), "hello")
        tool_text = '<tool_call>{"name":"read","arguments":{"path":"a"}}</tool_call>'
        content, tools = self.mod._split_tool_calls(["", tool_text, ""])
        self.assertEqual(content, "")
        self.assertEqual(tools[0]["function"]["name"], "read")
        self.assertEqual(json.loads(tools[0]["function"]["arguments"]), {"path": "a"})

    def test_s2_inflight_flush_precedes_finalization(self) -> None:
        entered, release = threading.Event(), threading.Event()

        class Writer(io.BytesIO):
            def flush(self) -> None:
                if not entered.is_set():
                    entered.set()
                    if not release.wait(5):
                        raise OSError("тест не отпустил flush")

        writer = Writer()
        handler = self._handler(writer)
        stop = threading.Event()
        handler._keepalive_stop = stop
        self.mod.KEEPALIVE_S = 0.01
        ticker = threading.Thread(
            target=handler._keepalive_loop, args=(stop,), daemon=True
        )
        handler._ka_thread = ticker
        ticker.start()
        self.addCleanup(release.set)
        self.assertTrue(entered.wait(3))
        finalizer = threading.Thread(
            target=handler._send_sse,
            args=("muse-spark-1.3", "hello", [], 1, 1, 0),
            daemon=True,
        )
        finalizer.start()
        try:
            self.assertTrue(
                stop.wait(3), "остановка не использует единый _keepalive_stop"
            )
            self.assertTrue(finalizer.is_alive())
            self.assertNotIn(b"[DONE]", writer.getvalue())
        finally:
            release.set()
            finalizer.join(5)
            ticker.join(5)
        self.assertFalse(finalizer.is_alive())
        self.assertFalse(ticker.is_alive())
        self.assertTrue(writer.getvalue().startswith(b"data: {"))
        self.assertTrue(writer.getvalue().endswith(b"data: [DONE]\n\n"))

    def test_done_write_failure_closes_phase(self) -> None:
        class BrokenWriter(io.BytesIO):
            def write(self, data: object) -> int:
                raise OSError("closed peer")

        handler = self._handler(BrokenWriter())
        self.assertFalse(handler._sse_write("data: [DONE]\n\n"))
        self.assertEqual(handler._sse_phase, "CLOSED")
        self.assertTrue(handler._client_gone)


class CliDisableFlagsAndApprovalFallbackTest(_BridgeScenario):
    """Реальные argv фейка; транспортный fallback до turn/start сохранён."""

    def test_serve_argv_allows_write_shell_by_default(self) -> None:
        install_protocol_wrapper(self, {"terminal": "completed"})
        for model in self.mod.ALLOWED_MODELS:
            with self.subTest(model=model):
                request = turn_request()
                request["model"] = model
                self.assertEqual(bridge_request(self, request)[0], 200)
                argv = json.loads((self.tmp / "serve-argv.json").read_text())
                self.assertNotIn("--disable-write", argv)
                self.assertNotIn("--disable-shell", argv)
        for flag in (
            "--provider",
            "meta",
            "--model",
            "--no-session-log",
            "--trust-workspace",
        ):
            self.assertIn(flag, argv)

    def test_transport_fallback_exec_flags(self) -> None:
        # oracle_change (REQ-MUSE-002): approval больше не уходит в exec;
        # проверки exec-флагов сохранены на транспортном ServeUnavailable
        # (EOF рукопожатия до turn/start), approval-контракт — класс Approval.
        install_fake_msp(self, serve_plans=[{"handshake_eof": True}])
        for model in self.mod.ALLOWED_MODELS:
            with self.subTest(model=model):
                request = turn_request()
                request["model"] = model
                status, body = bridge_request(self, request)
                self.assertEqual(status, 200, body)
                self.assertIn("fallback-ok", body.decode())
                argv = json.loads((self.tmp / "exec-argv.json").read_text())
                self.assertNotIn("--disable-write", argv)
                self.assertNotIn("--disable-shell", argv)
        for flag in (
            "--disable-web-tools",
            "--disable-reminders",
            "--yolo",
            "--provider",
            "meta",
            "--model",
            "--reasoning-effort",
            "--trust-workspace",
            "--workspace",
            "--json",
            "--no-session-log",
            "--prompt-file",
        ):
            self.assertIn(flag, argv)
        self.assertIn("fallback exec", self.mod.LOG_PATH.read_text())

    def test_write_shell_restrictions_are_independent_opt_ins(self) -> None:
        for mode in ("serve", "exec"):
            for disable_write, disable_shell in itertools.product(("0", "1"), repeat=2):
                with (
                    self.subTest(mode=mode, write=disable_write, shell=disable_shell),
                    mock.patch.dict(
                        os.environ,
                        {
                            "MUSE_BRIDGE_DISABLE_WRITE": disable_write,
                            "MUSE_BRIDGE_DISABLE_SHELL": disable_shell,
                        },
                    ),
                ):
                    install_fake_msp(
                        self,
                        serve_plans=[
                            ok_plan() if mode == "serve" else {"handshake_eof": True}
                        ],
                    )
                    status, body = bridge_request(self, turn_request())
                    self.assertEqual(status, 200, body)
                    argv = json.loads((self.tmp / f"{mode}-argv.json").read_text())
                    self.assertEqual("--disable-write" in argv, disable_write == "1")
                    self.assertEqual("--disable-shell" in argv, disable_shell == "1")


class AllowedModelsSyncTest(_BridgeScenario):
    """T-00 / AD-001: wonder-модели объявляют context_length=400000, spark без изменений."""

    def test_t00_models_and_health_include_wonder_models_400k(self) -> None:
        wonder_models = ("muse-wonder-1.0", "muse-wonder-full-1.0")
        for model in wonder_models:
            self.assertEqual(
                self.mod.ALLOWED_MODELS.get(model),
                {"context_length": 400_000, "max_output": 131072},
            )
        spark_models = ("muse-spark-1.3", "muse-spark-1.3-contributor")
        for model in spark_models:
            self.assertEqual(
                self.mod.ALLOWED_MODELS.get(model),
                {"context_length": 1048576, "max_output": 131072},
            )
        status, health_body = bridge_request(self, path="/health")
        self.assertEqual(status, 200)
        health_data = json.loads(health_body.decode("utf-8"))
        for model in wonder_models:
            self.assertIn(model, health_data["models"])

        status, models_body = bridge_request(self, path="/v1/models")
        self.assertEqual(status, 200)
        by_id = {
            item["id"]: item["context_length"]
            for item in json.loads(models_body.decode("utf-8"))["data"]
        }
        for model in wonder_models:
            self.assertEqual(by_id.get(model), 400_000)
        for model in spark_models:
            self.assertEqual(by_id.get(model), 1048576)

        for patch_rel in (
            ".dsh/profiles/desktop/cordis.patch.yml",
            ".dsh/profiles/web/cordis.patch.yml",
        ):
            patch_path = Path.home() / patch_rel
            if patch_path.exists():
                content = patch_path.read_text(encoding="utf-8")
                for model in wonder_models:
                    m = re.search(
                        rf"-\s+id:\s+{re.escape(model)}\b.*?contextWindow:\s+(\d+)",
                        content,
                        flags=re.DOTALL,
                    )
                    self.assertIsNotNone(m, f"{model} not found in {patch_path}")
                    assert m is not None
                    self.assertEqual(
                        int(m.group(1)),
                        400_000,
                        f"wrong contextWindow for {model} in {patch_path}",
                    )
                for model in spark_models:
                    m = re.search(
                        rf"-\s+id:\s+{re.escape(model)}\b.*?contextWindow:\s+(\d+)",
                        content,
                        flags=re.DOTALL,
                    )
                    self.assertIsNotNone(m, f"{model} not found in {patch_path}")
                    assert m is not None
                    self.assertEqual(
                        int(m.group(1)),
                        1048576,
                        f"wrong contextWindow for {model} in {patch_path}",
                    )


class ContextEstimateTest(unittest.TestCase):
    """T-01..T-02: оценка токенов и вывод лимитов из ALLOWED_MODELS."""

    def test_t01_estimate_tokens_latin_cyrillic_code_json_empty(self) -> None:
        mod = load_bridge()
        self.assertEqual(mod._estimate_tokens(""), 0)
        latin = "a" * 900
        self.assertEqual(mod._estimate_tokens(latin), 300)
        cyrillic = "я" * 1000
        self.assertEqual(mod._estimate_tokens(cyrillic), 666)
        code_sample = "def foo(x: int) -> int:\n    return x * 42\n" * 30
        json_sample = json.dumps(
            {"ключ": "значение", "nums": list(range(50))}, ensure_ascii=False
        )
        for sample in (latin, cyrillic, code_sample, json_sample, "🌟" * 90):
            expected = max(len(sample) // 3, len(sample.encode("utf-8")) // 3)
            self.assertEqual(mod._estimate_tokens(sample), expected)

    def test_t02_context_limit_and_derived_targets(self) -> None:
        mod = load_bridge()
        self.assertEqual(mod._context_limit("muse-wonder-1.0"), 400_000)
        self.assertEqual(mod._context_limit("muse-wonder-full-1.0"), 400_000)
        self.assertEqual(mod._context_limit("muse-spark-1.3"), 1048576)
        self.assertEqual(mod._context_limit("unknown-model-id"), 400_000)
        self.assertEqual(mod._context_target(400_000), 320_000)
        self.assertEqual(mod._context_retry_target(400_000), 200_000)
        with mock.patch.dict(
            mod.ALLOWED_MODELS,
            {"muse-wonder-1.0": {"context_length": 250_000, "max_output": 131072}},
        ):
            lim = mod._context_limit("muse-wonder-1.0")
            self.assertEqual(lim, 250_000)
            self.assertEqual(mod._context_target(lim), 200_000)
            self.assertEqual(mod._context_retry_target(lim), 125_000)


class ContextPruneTest(unittest.TestCase):
    """T-03..T-11, T-13..T-14: защитный прунинг истории диалога."""

    mod: Any = None

    def setUp(self) -> None:
        self.mod = load_bridge()

    def test_t03_boundary_limit_minus_one_limit_and_limit_plus_one(self) -> None:
        # "User: " — 6 байт. Для оценки ровно N токенов при 1 реплике и другой реплике:
        # соберём историю из 3 сообщений и подгоним байты под точный порог limit=1000.
        limit = 1000
        target = 800
        m1 = {"role": "user", "content": "first-user"}
        m3 = {"role": "user", "content": "last-user"}
        base_prompt = self.mod._assemble_prompt(
            [m1, {"role": "assistant", "content": ""}, m3]
        )[2]
        # Проверим на точной длине промпта:
        # "User: first-user\n\nAssistant: <X>\n\nUser: last-user"
        prefix_overhead = len(
            "User: first-user\n\nAssistant: \n\nUser: last-user".encode("utf-8")
        )
        for desired_est, should_prune in (
            (limit - 1, False),
            (limit, False),
            (limit + 1, True),
        ):
            needed_bytes = desired_est * 3 - prefix_overhead
            m2 = {"role": "assistant", "content": "x" * needed_bytes}
            msgs = [m1, m2, m3]
            res = self.mod._prune_messages(msgs, limit=limit, target=target)
            self.assertEqual(res.est_before, desired_est)
            if not should_prune:
                self.assertEqual(res.status, "pass_through")
                self.assertIs(res.messages, msgs)
                self.assertNotIn(self.mod.COMPACTION_MARKER, res.prompt)
            else:
                self.assertEqual(res.status, "pruned")
                self.assertLessEqual(res.est_after, target)
                self.assertIn(self.mod.COMPACTION_MARKER, res.prompt)
                self.assertEqual(res.msgs_dropped, 1)
        _ = base_prompt

    def test_t04_pruned_assembled_prompt_within_320k_with_tools_and_system(
        self,
    ) -> None:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": f"tool_{i}",
                    "description": "Описание инструмента " * 40,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "arg": {"type": "string", "description": "d" * 200}
                        },
                    },
                },
            }
            for i in range(25)
        ]
        msgs: list[dict[str, Any]] = [
            {"role": "system", "content": "System instructions " * 500},
            {"role": "user", "content": "Initial task description " * 200},
        ]
        # Добавим 30 реплик по ~45k байт (~15k токенов каждая) -> ~450k токенов (> 400k).
        for i in range(30):
            role = "assistant" if i % 2 == 0 else "user"
            msgs.append({"role": role, "content": f"turn-{i} " + ("payload " * 5600)})
        msgs.append({"role": "user", "content": "Final user question"})

        res = self.mod._prune_messages(
            msgs, limit=400_000, target=320_000, tools=tools, tool_choice="auto"
        )
        self.assertEqual(res.status, "pruned")
        self.assertGreater(res.est_before, 400_000)
        actual_est = self.mod._estimate_tokens(res.prompt)
        self.assertEqual(res.est_after, actual_est)
        self.assertLessEqual(actual_est, 320_000)
        self.assertIn(self.mod.COMPACTION_MARKER, res.prompt)
        self.assertIn("# Tool calling protocol", res.prompt)

    def test_t05_preserves_all_system_developer_first_and_last_user_without_dup(
        self,
    ) -> None:
        msgs = [
            {"role": "system", "content": "sys-early"},
            {"role": "user", "content": "user-first"},
            {"role": "assistant", "content": "A" * 3000},
            {"role": "developer", "content": "dev-mid-insertion"},
            {"role": "user", "content": "U" * 3000},
            {"role": "assistant", "content": "B" * 3000},
            {"role": "system", "content": "sys-late-insertion"},
            {"role": "user", "content": "user-last"},
        ]
        res = self.mod._prune_messages(msgs, limit=1500, target=1000)
        self.assertEqual(res.status, "pruned")
        for needle in (
            "sys-early",
            "dev-mid-insertion",
            "sys-late-insertion",
            "user-first",
            "user-last",
        ):
            self.assertIn(needle, res.prompt)
        # Если в истории только один user — он не дублируется.
        single_user_msgs = [
            {"role": "system", "content": "sys-1"},
            {"role": "user", "content": "only-one-user"},
            {"role": "assistant", "content": "X" * 6000},
        ]
        res_single = self.mod._prune_messages(single_user_msgs, limit=1000, target=500)
        self.assertEqual(res_single.status, "pruned")
        self.assertEqual(res_single.prompt.count("only-one-user"), 1)

    def test_t06_tool_calls_and_tool_results_atomicity_sweep(self) -> None:
        msgs: list[dict[str, Any]] = [
            {"role": "user", "content": "first-user"},
            {"role": "assistant", "content": "early-assistant-" + ("x" * 300)},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_a1",
                        "type": "function",
                        "function": {"name": "f1", "arguments": "{}"},
                    },
                    {
                        "id": "call_a2",
                        "type": "function",
                        "function": {"name": "f2", "arguments": "{}"},
                    },
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_a1",
                "name": "f1",
                "content": "res_a1_" + ("y" * 300),
            },
            {
                "role": "tool",
                "tool_call_id": "call_a2",
                "name": "f2",
                "content": "res_a2_" + ("z" * 300),
            },
            {
                "role": "assistant",
                "content": "thinking",
                "tool_calls": [
                    {
                        "id": "call_b1",
                        "type": "function",
                        "function": {"name": "f3", "arguments": "{}"},
                    },
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_b1",
                "name": "f3",
                "content": "res_b1_" + ("w" * 300),
            },
            {"role": "user", "content": "last-user"},
        ]
        full_est = self.mod._estimate_tokens(self.mod._assemble_prompt(msgs)[2])
        for target in range(80, full_est + 20, 15):
            res = self.mod._prune_messages(msgs, limit=full_est - 1, target=target)
            self.assertNotEqual(res.status, "refused")
            kept_call_ids: set[str] = set()
            expected_tool_ids: dict[str, set[str]] = {}
            actual_tool_ids: set[str] = set()
            for m in res.messages:
                if m.get("role") == "assistant" and m.get("tool_calls"):
                    cids = {tc["id"] for tc in m["tool_calls"]}
                    kept_call_ids |= cids
                    expected_tool_ids[m["tool_calls"][0]["id"]] = cids
                elif m.get("role") == "tool":
                    actual_tool_ids.add(m["tool_call_id"])
            # Инвариант I-1: нет tool без вызова и нет частичного сохранения многовызовного хода.
            self.assertEqual(
                actual_tool_ids,
                kept_call_ids,
                f"нарушена атомарность при target={target}",
            )
            for group_ids in expected_tool_ids.values():
                self.assertTrue(group_ids.issubset(actual_tool_ids))

    def test_t07_orphan_tool_dropped_on_prune_kept_on_passthrough(self) -> None:
        orphan = {
            "role": "tool",
            "tool_call_id": "orphan_id_999",
            "name": "ghost",
            "content": "orphan-body",
        }
        msgs = [
            {"role": "user", "content": "u1"},
            orphan,
            {"role": "assistant", "content": "A" * 3000},
            {"role": "user", "content": "u2"},
        ]
        passthru = self.mod._prune_messages(msgs, limit=5000, target=4000)
        self.assertEqual(passthru.status, "pass_through")
        self.assertIn(orphan, passthru.messages)
        self.assertIn("orphan-body", passthru.prompt)

        pruned = self.mod._prune_messages(msgs, limit=500, target=300)
        self.assertEqual(pruned.status, "pruned")
        self.assertNotIn(orphan, pruned.messages)
        self.assertNotIn("orphan-body", pruned.prompt)

    def test_t08_cyrillic_triggers_prune_when_bytes_exceed_limit(self) -> None:
        # 900 кириллических символов = 300 chars//3, но 1800 байт = 600 bytes//3.
        # При limit=450 chars//3 < limit < bytes//3 -> прунинг обязан сработать.
        msgs = [
            {"role": "user", "content": "первый"},
            {"role": "assistant", "content": "ж" * 900},
            {"role": "user", "content": "последний"},
        ]
        res = self.mod._prune_messages(msgs, limit=450, target=300)
        self.assertEqual(res.status, "pruned")
        self.assertLessEqual(res.est_after, 300)
        self.assertNotIn("ж" * 100, res.prompt)

    def test_t09_multipart_none_empty_non_dict_unknown_role(self) -> None:
        msgs: list[Any] = [
            "not-a-dict",
            123,
            {"role": "user", "content": None},
            {"role": "user", "content": "   "},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "real-first-user"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "http://example.com/a.png"},
                    },
                ],
            },
            {"role": "custom_unknown_role", "content": "middle-" + ("M" * 3000)},
            {"role": "user", "content": "real-last-user"},
            {"role": "user", "content": ""},
        ]
        res = self.mod._prune_messages(msgs, limit=500, target=300)
        self.assertEqual(res.status, "pruned")
        self.assertIn("real-first-user", res.prompt)
        self.assertIn("[image omitted]", res.prompt)
        self.assertIn("real-last-user", res.prompt)
        self.assertNotIn("middle-M", res.prompt)

    def test_t10_marker_placement_chronology_determinism_and_idempotency(self) -> None:
        # Сценарий с двумя разрывами:
        # U0(first_user), U1(dropped), U2(last_user), U3(dropped tool group), U4(kept trailing tool group)
        msgs: list[dict[str, Any]] = [
            {"role": "system", "content": "sys-top"},
            {"role": "user", "content": "first-u"},
            {"role": "assistant", "content": "drop-1-" + ("A" * 1500)},
            {"role": "user", "content": "last-u"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c_drop",
                        "type": "function",
                        "function": {"name": "f", "arguments": "{}"},
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "c_drop",
                "name": "f",
                "content": "drop-2-" + ("B" * 1500),
            },
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c_keep",
                        "type": "function",
                        "function": {"name": "f", "arguments": "{}"},
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "c_keep",
                "name": "f",
                "content": "keep-trail",
            },
        ]
        res1 = self.mod._prune_messages(msgs, limit=600, target=400)
        res2 = self.mod._prune_messages(msgs, limit=600, target=400)
        self.assertEqual(res1.status, "pruned")
        self.assertEqual(res1.prompt, res2.prompt)
        self.assertEqual(res1.messages, res2.messages)
        # Ровно два маркера в двух разрывах.
        self.assertEqual(res1.prompt.count(self.mod.COMPACTION_MARKER), 2)
        p_first = res1.prompt.index("User: first-u")
        p_m1 = res1.prompt.index(self.mod.COMPACTION_MARKER)
        p_last = res1.prompt.index("User: last-u")
        p_m2 = res1.prompt.rindex(self.mod.COMPACTION_MARKER)
        p_trail = res1.prompt.index("keep-trail")
        self.assertTrue(p_first < p_m1 < p_last < p_m2 < p_trail)

        # Идемпотентность: повторный вызов с теми же параметрами и с принудительным порогом.
        idem1 = self.mod._prune_messages(res1.messages, limit=600, target=400)
        self.assertEqual(idem1.prompt, res1.prompt)
        self.assertEqual(idem1.messages, res1.messages)
        idem2 = self.mod._prune_messages(
            res1.messages, limit=res1.est_after - 1, target=res1.est_after
        )
        self.assertEqual(idem2.prompt, res1.prompt)
        self.assertEqual(idem2.messages, res1.messages)

    def test_t11_input_not_mutated_and_wlock_not_held_during_prune(self) -> None:
        import copy

        msgs = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "A" * 3000},
            {"role": "user", "content": "u2"},
        ]
        snapshot = copy.deepcopy(msgs)
        res = self.mod._prune_messages(msgs, limit=500, target=300)
        self.assertEqual(res.status, "pruned")
        self.assertEqual(msgs, snapshot)
        for m in res.messages:
            if m.get("role") != self.mod._COMPACTION_MARKER_ROLE:
                self.assertTrue(any(m is orig for orig in msgs))

        # Проверка в Handler._serve_json: во время _prune_messages замок self._wlock не захвачен.
        handler = self.mod.Handler.__new__(self.mod.Handler)
        handler.connection = None
        handler._wlock = threading.Lock()
        handler._client_gone = False
        handler._current_run = None
        handler._sse_open = False
        handler._content_started = False
        lock_states: list[bool] = []
        orig_prune = self.mod._prune_messages

        def spy_prune(*args: Any, **kwargs: Any) -> Any:
            lock_states.append(handler._wlock.locked())
            return orig_prune(*args, **kwargs)

        with (
            mock.patch.object(self.mod, "_prune_messages", side_effect=spy_prune),
            mock.patch.object(
                self.mod.ServeRun,
                "execute",
                return_value={"rc": 0, "state": "ok", "text": "ok", "err": ""},
            ),
            mock.patch.object(handler, "_send"),
        ):
            handler._serve_json({"model": "muse-wonder-1.0", "messages": msgs})
        self.assertEqual(lock_states, [False])

    def test_t13_trailing_incomplete_tool_unit_kept_or_refused_if_exceeds_cap(
        self,
    ) -> None:
        msgs = [
            {"role": "user", "content": "first-u"},
            {"role": "assistant", "content": "mid-" + ("M" * 2000)},
            {"role": "user", "content": "last-u"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c_tail",
                        "type": "function",
                        "function": {"name": "bash", "arguments": "{}"},
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "c_tail",
                "name": "bash",
                "content": "tool-output-" + ("T" * 600),
            },
        ]
        # Обязательный набор (first-u + last-u + trailing tool unit + маркер) ~ 260 токенов.
        # Пусть limit=500, target=200: обязательный набор > target (200), но <= cap (500) -> сохраняется!
        res_ok = self.mod._prune_messages(msgs, limit=500, target=200)
        self.assertEqual(res_ok.status, "pruned")
        self.assertIn("tool-output-", res_ok.prompt)
        self.assertNotIn("mid-M", res_ok.prompt)
        self.assertLessEqual(res_ok.est_after, 500)

        # Если же обязательный набор с незавершённой единицей > cap (limit=200) -> отказ.
        res_refused = self.mod._prune_messages(msgs, limit=200, target=160)
        self.assertEqual(res_refused.status, "refused")

    def test_t14_hysteresis_prefix_stability_and_399999_passthrough(self) -> None:
        # 399_999 не прунится при limit=400_000.
        prefix_len = len("User: ".encode("utf-8"))
        exact_bytes = 399_999 * 3 - prefix_len
        msg_399k = [{"role": "user", "content": "a" * exact_bytes}]
        res_399k = self.mod._prune_messages(msg_399k, limit=400_000, target=320_000)
        self.assertEqual(res_399k.est_before, 399_999)
        self.assertEqual(res_399k.status, "pass_through")

        # Два хода подряд с ростом > 400k: префикс (system, tools, первый user, маркер) побайтно одинаков.
        tools = [
            {
                "type": "function",
                "function": {"name": "t1", "description": "d", "parameters": {}},
            }
        ]
        base_msgs: list[dict[str, Any]] = [
            {"role": "system", "content": "stable-system-prompt"},
            {"role": "user", "content": "stable-first-user"},
        ]
        for i in range(15):
            base_msgs.append(
                {
                    "role": "assistant" if i % 2 == 0 else "user",
                    "content": f"m{i}-" + ("X" * 90_000),
                }
            )
        turn1 = base_msgs + [{"role": "user", "content": "question-1"}]
        turn2 = turn1 + [
            {"role": "assistant", "content": "answer-1-" + ("Y" * 30_000)},
            {"role": "user", "content": "question-2"},
        ]
        r1 = self.mod._prune_messages(turn1, limit=400_000, target=320_000, tools=tools)
        r2 = self.mod._prune_messages(turn2, limit=400_000, target=320_000, tools=tools)
        self.assertEqual(r1.status, "pruned")
        self.assertEqual(r2.status, "pruned")
        marker_end_1 = r1.prompt.index(self.mod.COMPACTION_MARKER) + len(
            self.mod.COMPACTION_MARKER
        )
        marker_end_2 = r2.prompt.index(self.mod.COMPACTION_MARKER) + len(
            self.mod.COMPACTION_MARKER
        )
        self.assertEqual(
            r1.prompt[:marker_end_1].encode("utf-8"),
            r2.prompt[:marker_end_2].encode("utf-8"),
        )


class ContextRetryTest(_BridgeScenario):
    """T-12, T-15..T-22: аварийный auto-retry при ошибке жёсткого порога Meta."""

    def _over_budget_messages(
        self, chunk_bytes: int = 110_000, count: int = 12
    ) -> list[dict[str, Any]]:
        msgs: list[dict[str, Any]] = [
            {"role": "system", "content": "sys-canary-head"},
            {"role": "user", "content": "first-user-canary"},
        ]
        for i in range(count):
            role = "assistant" if i % 2 == 0 else "user"
            msgs.append(
                {"role": role, "content": f"mid-canary-{i}-" + ("M" * chunk_bytes)}
            )
        msgs.append({"role": "user", "content": "last-user-canary"})
        return msgs

    def test_t12_mandatory_exceeds_limit_returns_502_before_run(self) -> None:
        huge_canary = "MANDATORY_SECRET_CANARY_" + ("Z" * 1_250_000)
        payload = {
            "model": "muse-wonder-1.0",
            "messages": [{"role": "user", "content": huge_canary}],
            "stream": False,
        }
        with (
            mock.patch.object(self.mod, "ServeRun") as serve_cls,
            mock.patch.object(self.mod, "Run") as run_cls,
        ):
            status, body = bridge_request(self, payload)
            self.assertEqual(status, 502)
            serve_cls.assert_not_called()
            run_cls.assert_not_called()
        self.assertTrue(self._slot_free())
        err = json.loads(body.decode("utf-8"))["error"]
        self.assertIn("mandatory context exceeds budget", err["message"])
        self.assertIn("limit=400000", err["message"])
        logs = self.mod.LOG_PATH.read_text(encoding="utf-8")
        self.assertIn("reason=refused_mandatory", logs)
        self.assertNotIn("MANDATORY_SECRET_CANARY_", body.decode("utf-8") + logs)

    def test_t15_hard_threshold_error_triggers_single_retry_and_succeeds(self) -> None:
        hard_err = (
            "modelError: context compaction replacement still exceeds the hard threshold "
            "(639915 >= 460800 tokens) retryable=True"
        )
        for stream in (False, True):
            with self.subTest(stream=stream):
                self.mod.LOG_PATH.unlink(missing_ok=True)
                prompts_seen: list[str] = []

                def fake_execute(run_self: Any) -> dict[str, Any]:
                    prompts_seen.append(run_self.prompt)
                    if len(prompts_seen) == 1:
                        return {
                            "rc": 1,
                            "state": "terminal_failed",
                            "text": "",
                            "err": hard_err,
                            "via": "serve",
                        }
                    return {
                        "rc": 0,
                        "state": "ok",
                        "text": "recovered-ok",
                        "chunks": ["recovered-ok"],
                        "err": "",
                        "summaries": [],
                        "usage": {"promptTokens": 150000, "outputTokens": 5},
                        "via": "serve",
                    }

                payload = {
                    "model": "muse-wonder-1.0",
                    "messages": self._over_budget_messages(),
                    "stream": stream,
                }
                with mock.patch.object(self.mod.ServeRun, "execute", fake_execute):
                    status, body = bridge_request(self, payload)
                self.assertEqual(status, 200)
                self.assertEqual(len(prompts_seen), 2)
                est1 = self.mod._estimate_tokens(prompts_seen[0])
                est2 = self.mod._estimate_tokens(prompts_seen[1])
                self.assertLessEqual(est1, 320_000)
                self.assertLessEqual(est2, 200_000)
                self.assertLess(est2, est1)
                text_body = body.decode("utf-8")
                self.assertIn("recovered-ok", text_body)
                if stream:
                    self.assertEqual(text_body.count("data: [DONE]"), 1)
                    frames = [
                        json.loads(line[6:])
                        for line in text_body.splitlines()
                        if line.startswith("data: {")
                    ]
                    self.assertFalse(any("error" in f for f in frames))

    def test_t16_hard_threshold_error_twice_returns_terminal_502(self) -> None:
        hard_err = (
            "modelError: context compaction replacement still exceeds the hard threshold "
            "(500000 >= 460800 tokens) prompt-canary-reflected"
        )
        for stream in (False, True):
            with self.subTest(stream=stream):
                self.mod.LOG_PATH.unlink(missing_ok=True)
                calls = 0

                def fake_execute(run_self: Any) -> dict[str, Any]:
                    nonlocal calls
                    calls += 1
                    return {
                        "rc": 1,
                        "state": "terminal_failed",
                        "text": "",
                        "err": hard_err + " " + run_self.prompt,
                        "via": "serve",
                    }

                payload = {
                    "model": "muse-wonder-full-1.0",
                    "messages": self._over_budget_messages(),
                    "stream": stream,
                }
                with mock.patch.object(self.mod.ServeRun, "execute", fake_execute):
                    status, body = bridge_request(self, payload)
                self.assertEqual(calls, 2)
                text_body = body.decode("utf-8")
                if stream:
                    self.assertEqual(status, 200)
                    self.assertEqual(text_body.count("data: [DONE]"), 1)
                    err_frames = [
                        json.loads(line[6:])["error"]
                        for line in text_body.splitlines()
                        if line.startswith("data: {")
                        and "error" in json.loads(line[6:])
                    ]
                    self.assertEqual(len(err_frames), 1)
                    err_obj = err_frames[0]
                else:
                    self.assertEqual(status, 502)
                    err_obj = json.loads(text_body)["error"]
                self.assertEqual(err_obj["type"], "proxy_error")
                self.assertEqual(err_obj["code"], 502)
                self.assertIn(
                    "context hard threshold exceeded after single compaction retry",
                    err_obj["message"],
                )
                self.assertIn("target=200000", err_obj["message"])
                logs = self.mod.LOG_PATH.read_text(encoding="utf-8")
                for canary in (
                    "sys-canary-head",
                    "first-user-canary",
                    "mid-canary-",
                    "last-user-canary",
                ):
                    self.assertNotIn(canary, text_body + logs)

    def test_t17_other_error_or_marker_in_normal_text_does_not_retry(self) -> None:
        self.assertEqual(
            self.mod.HARD_THRESHOLD_ERR_SUBSTR,
            "context compaction replacement still exceeds the hard threshold",
        )
        # 1) Другая ошибка в err -> 1 попытка.
        calls = 0

        def other_err(_self: Any) -> dict[str, Any]:
            nonlocal calls
            calls += 1
            return {
                "rc": 1,
                "state": "terminal_failed",
                "text": "",
                "err": "quota_exceeded",
            }

        payload = {
            "model": "muse-wonder-1.0",
            "messages": self._over_budget_messages(),
        }
        with mock.patch.object(self.mod.ServeRun, "execute", other_err):
            status, _ = bridge_request(self, payload)
        self.assertEqual(status, 502)
        self.assertEqual(calls, 1)

        # 2) Подстрока в обычном ответе модели (rc=0, state="ok") -> 1 попытка, 200 OK.
        calls = 0

        def marker_in_text(_self: Any) -> dict[str, Any]:
            nonlocal calls
            calls += 1
            return {
                "rc": 0,
                "state": "ok",
                "text": f"Here is the error string: {self.mod.HARD_THRESHOLD_ERR_SUBSTR}",
                "chunks": [
                    f"Here is the error string: {self.mod.HARD_THRESHOLD_ERR_SUBSTR}"
                ],
                "err": "",
            }

        with mock.patch.object(self.mod.ServeRun, "execute", marker_in_text):
            status, body = bridge_request(self, payload)
        self.assertEqual(status, 200)
        self.assertEqual(calls, 1)
        self.assertIn(self.mod.HARD_THRESHOLD_ERR_SUBSTR, body.decode("utf-8"))

    def test_t18_serve_fallback_and_network_retry_preserve_context_retry_budget(
        self,
    ) -> None:
        # oracle_change (AD-003): внутренний exec-reтрай по NETWORK_RETRY_MARKER
        # упразднён; транзиентный счётчик Handler не расходует контекстный.
        # Утверждение про контекстный бюджет сохранено дословно по смыслу:
        # транзиентный повтор идёт тем же промптом, контекстный — прунённым.
        self.mod.TRANSIENT_BACKOFF_S = (0.0, 0.0)
        self.mod.TRANSIENT_JITTER_S = 0.0
        serve_prompts: list[str] = []
        exec_calls: list[str] = []

        def fake_serve(run_self: Any) -> dict[str, Any]:
            serve_prompts.append(run_self.prompt)
            n = len(serve_prompts)
            if n == 1:
                # Пре-турновый транзиентный сбой serve: повтор новым serve.
                raise self.mod.ServeUnavailable("[net-timeout] setup boom")
            if n == 2:
                # Транзиентный повтор вернул hard threshold: контекстный retry.
                run_self.action_possible = True
                return {
                    "rc": 1,
                    "state": "terminal_failed",
                    "text": "",
                    "err": self.mod.HARD_THRESHOLD_ERR_SUBSTR,
                    "hard_threshold": True,
                }
            return {
                "rc": 0,
                "state": "ok",
                "text": "serve-recovered",
                "chunks": ["serve-recovered"],
                "err": "",
            }

        def fake_exec(run_self: Any) -> dict[str, Any]:
            exec_calls.append(run_self.prompt)
            return {
                "rc": 0,
                "state": "ok",
                "text": "exec-should-not-run",
                "chunks": ["exec-should-not-run"],
                "err": "",
            }

        payload = {
            "model": "muse-wonder-1.0",
            "messages": self._over_budget_messages(),
        }
        with (
            mock.patch.object(self.mod.ServeRun, "execute", fake_serve),
            mock.patch.object(self.mod.Run, "execute", fake_exec),
        ):
            status, body = bridge_request(self, payload)
        self.assertEqual(status, 200, body)
        self.assertEqual(len(serve_prompts), 3)
        self.assertEqual(serve_prompts[0], serve_prompts[1])
        self.assertLess(
            self.mod._estimate_tokens(serve_prompts[2]),
            self.mod._estimate_tokens(serve_prompts[0]),
        )
        self.assertEqual(exec_calls, [])
        self.assertIn("serve-recovered", body.decode("utf-8"))
        self.assertIn(
            "reason=hard_threshold_retry",
            self.mod.LOG_PATH.read_text(encoding="utf-8"),
        )

    def test_t19_client_disconnect_between_attempts_skips_second_run(self) -> None:
        calls = 0
        first_entered = threading.Event()
        release_first = threading.Event()

        def fake_execute(_self: Any) -> dict[str, Any]:
            nonlocal calls
            calls += 1
            first_entered.set()
            release_first.wait(5)
            return {
                "rc": 1,
                "state": "terminal_failed",
                "text": "",
                "err": self.mod.HARD_THRESHOLD_ERR_SUBSTR,
            }

        with mock.patch.object(self.mod.ServeRun, "execute", fake_execute):
            body = json.dumps(
                {
                    "model": "muse-wonder-1.0",
                    "messages": self._over_budget_messages(),
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
            self.assertTrue(first_entered.wait(5))
            sock.close()
            time.sleep(0.35)
            release_first.set()
            self.assertTrue(wait_until(self._slot_free, SCENARIO_DEADLINE_S))
        self.assertEqual(calls, 1)
        log_text = self.mod.LOG_PATH.read_text(encoding="utf-8")
        self.assertIn("reason=proactive_prune", log_text)
        self.assertNotIn("reason=hard_threshold_retry", log_text)

    def test_t20_mandatory_exceeds_200k_on_retry_skips_second_run(self) -> None:
        # Обязательный user ~ 250k токенов (750k байт): проходит в 400k, но не влезает в retry_target=200k.
        calls = 0

        def fake_execute(_self: Any) -> dict[str, Any]:
            nonlocal calls
            calls += 1
            return {
                "rc": 1,
                "state": "terminal_failed",
                "text": "",
                "err": self.mod.HARD_THRESHOLD_ERR_SUBSTR,
            }

        payload = {
            "model": "muse-wonder-1.0",
            "messages": [
                {"role": "user", "content": "first-mandatory-" + ("A" * 750_000)},
                {"role": "assistant", "content": "mid-optional-" + ("B" * 300_000)},
                {"role": "user", "content": "last-mandatory"},
            ],
        }
        with mock.patch.object(self.mod.ServeRun, "execute", fake_execute):
            status, body = bridge_request(self, payload)
        self.assertEqual(status, 502)
        self.assertEqual(calls, 1)
        err = json.loads(body.decode("utf-8"))["error"]
        self.assertIn("mandatory context exceeds budget", err["message"])
        self.assertIn("limit=200000", err["message"])
        self.assertIn(
            "reason=refused_retry", self.mod.LOG_PATH.read_text(encoding="utf-8")
        )

    def test_t21_retry_cut_does_not_reduce_prompt_skips_second_run(self) -> None:
        calls = 0

        def fake_execute(_self: Any) -> dict[str, Any]:
            nonlocal calls
            calls += 1
            return {
                "rc": 1,
                "state": "terminal_failed",
                "text": "",
                "err": self.mod.HARD_THRESHOLD_ERR_SUBSTR,
            }

        # Короткий запрос (<< 200k): повторный срез до 200k даёт ту же оценку -> второй запуск не нужен.
        payload = {
            "model": "muse-wonder-1.0",
            "messages": [{"role": "user", "content": "short prompt"}],
        }
        with mock.patch.object(self.mod.ServeRun, "execute", fake_execute):
            status, body = bridge_request(self, payload)
        self.assertEqual(status, 502)
        self.assertEqual(calls, 1)
        err = json.loads(body.decode("utf-8"))["error"]
        self.assertIn(
            "context hard threshold exceeded after single compaction retry",
            err["message"],
        )
        self.assertIn(
            "reason=refused_retry", self.mod.LOG_PATH.read_text(encoding="utf-8")
        )

    def test_t22_unconfirmed_death_on_attempt_one_skips_retry_and_quarantines_slot(
        self,
    ) -> None:
        calls = 0
        proc = CloseKillsGroupTest._spawn_group()
        self.addCleanup(CloseKillsGroupTest._reap_group, proc)

        def fake_execute(run_self: Any) -> dict[str, Any]:
            nonlocal calls
            calls += 1
            run_self.proc = proc
            return {
                "rc": 1,
                "state": "terminal_failed",
                "text": "",
                "err": self.mod.HARD_THRESHOLD_ERR_SUBSTR,
            }

        def fake_close(run_self: Any) -> None:
            run_self.dead_confirmed = False

        payload = {
            "model": "muse-wonder-1.0",
            "messages": self._over_budget_messages(),
        }
        with (
            mock.patch.object(self.mod.ServeRun, "execute", fake_execute),
            mock.patch.object(self.mod.ServeRun, "close", fake_close),
            mock.patch.object(self.mod, "_kill_group", lambda _p: None),
        ):
            status, _ = bridge_request(self, payload)
            self.assertEqual(status, 502)
            self.assertEqual(calls, 1)
            self.assertEqual(len(self.mod._quarantined_slots), 1)
            self.assertFalse(self._slot_free())

            # После реальной смерти группы карантин возвращает слот ровно один раз.
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5)
            self.assertTrue(wait_until(self._slot_free, SCENARIO_DEADLINE_S))
            self.assertEqual(len(self.mod._quarantined_slots), 0)
            time.sleep(0.2)
            self.assertTrue(self.mod._slots.acquire(blocking=False))
            self.mod._slots.release()
            self.assertFalse(
                self.mod._slots._value > 1, "семафор освобождён больше одного раза"
            )


class ContextObservabilityTest(_BridgeScenario):
    """T-23: формат context_prune, отсутствие секретов/тел в обоих проходах и отсутствие утечки буферов."""

    def test_t23_observability_log_fields_secret_redaction_and_no_retained_buffers(
        self,
    ) -> None:
        secret1 = "sk-attempt1secretcanary123456"
        secret2 = "Bearer attempt2-secret-token-98765"
        body_canary_1 = "ATTEMPT_ONE_ONLY_BODY_CANARY_" + ("P" * 750_000)
        body_canary_2 = "MANDATORY_USER_BODY_CANARY_" + ("Q" * 30)

        msgs: list[dict[str, Any]] = [
            {"role": "system", "content": f"sys {secret1}"},
            {"role": "user", "content": body_canary_2},
            {"role": "assistant", "content": "old-dropped-" + ("D" * 900_000)},
            {"role": "assistant", "content": body_canary_1},
            {"role": "user", "content": f"final question {secret2}"},
        ]

        attempts = 0

        def fake_execute(run_self: Any) -> dict[str, Any]:
            nonlocal attempts
            attempts += 1
            return {
                "rc": 1,
                "state": "terminal_failed",
                "text": "",
                "err": (
                    f"{self.mod.HARD_THRESHOLD_ERR_SUBSTR} "
                    f"reflected1={body_canary_1[:160]} reflected2={body_canary_2} "
                    f"sec1={secret1} sec2={secret2} prompt={run_self.prompt}"
                ),
            }

        for stream in (False, True):
            self.mod.LOG_PATH.unlink(missing_ok=True)
            attempts = 0
            with mock.patch.object(self.mod.ServeRun, "execute", fake_execute):
                status, resp_bytes = bridge_request(
                    self,
                    {"model": "muse-wonder-1.0", "messages": msgs, "stream": stream},
                )
            self.assertEqual(status, 200 if stream else 502)
            self.assertEqual(attempts, 2)
            log_text = self.mod.LOG_PATH.read_text(encoding="utf-8")
            resp_text = resp_bytes.decode("utf-8")

            prune_lines = [
                line for line in log_text.splitlines() if "context_prune " in line
            ]
            self.assertEqual(len(prune_lines), 2)
            self.assertIn("reason=proactive_prune", prune_lines[0])
            self.assertIn("attempt=1", prune_lines[0])
            self.assertIn("reason=hard_threshold_retry", prune_lines[1])
            self.assertIn("attempt=2", prune_lines[1])
            for line in prune_lines:
                for field in (
                    "rid=",
                    "model=muse-wonder-1.0",
                    "limit=400000",
                    "target=",
                    "est_before=",
                    "est_after=",
                    "msgs_total=",
                    "msgs_kept=",
                    "msgs_dropped=",
                    "mandatory_est=",
                    "overhead_est=",
                    "method=bytes_div_3",
                ):
                    self.assertIn(field, line)

            combined = log_text + resp_text
            for forbidden in (
                "attempt1secretcanary123456",
                "attempt2-secret-token-98765",
                "ATTEMPT_ONE_ONLY_BODY_CANARY_",
                "MANDATORY_USER_BODY_CANARY_",
                "old-dropped-",
            ):
                self.assertNotIn(forbidden, combined)

        # Серия запросов не растит удерживаемые буферы модуля.
        self.assertEqual(len(self.mod._active), 0)
        self.assertEqual(len(self.mod._quarantined_slots), 0)

    def test_t24_repeated_tool_call_id_across_episodes_preserves_trailing_mandatory_unit(
        self,
    ) -> None:
        """RW-001 / FU-001: повтор tool_call_id в разных эпизодах не теряет хвостовой вызов; Фаза C линейна."""
        msgs: list[dict[str, Any]] = [
            {"role": "user", "content": "first-user"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_0",
                        "type": "function",
                        "function": {"name": "cmd", "arguments": '{"step": 1}'},
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_0",
                "name": "cmd",
                "content": "ep1-tool-result-" + ("X" * 1200),
            },
            {"role": "assistant", "content": "ep1-summary-" + ("Y" * 300)},
            {"role": "user", "content": "last-user"},
            {
                "role": "assistant",
                "content": "tail-assistant-call",
                "tool_calls": [
                    {
                        "id": "call_0",
                        "type": "function",
                        "function": {"name": "cmd", "arguments": '{"step": 2}'},
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_0",
                "name": "cmd",
                "content": "tail-mandatory-tool-result",
            },
        ]
        res = self.mod._prune_messages(msgs, limit=500, target=400)
        self.assertEqual(res.status, "pruned")
        self.assertNotIn("ep1-tool-result-", res.prompt)
        self.assertIn("User: first-user", res.prompt)
        self.assertIn("User: last-user", res.prompt)
        self.assertIn("tail-assistant-call", res.prompt)
        self.assertIn("tail-mandatory-tool-result", res.prompt)

        # FU-001: 3000 сообщений прунятся за линейное время (< 0.5 с).
        many_msgs: list[dict[str, Any]] = [{"role": "user", "content": "start"}]
        for i in range(3000):
            many_msgs.append(
                {
                    "role": "assistant" if i % 2 == 0 else "user",
                    "content": f"m{i}-" + ("a" * 300),
                }
            )
        many_msgs.append({"role": "user", "content": "end"})
        t0 = time.monotonic()
        many_res = self.mod._prune_messages(many_msgs, limit=100_000, target=80_000)
        elapsed = time.monotonic() - t0
        self.assertEqual(many_res.status, "pruned")
        self.assertLessEqual(many_res.est_after, 80_000)
        self.assertLess(elapsed, 0.5, f"Фаза C слишком медленная: {elapsed:.2f}s")

    def test_t25_long_prefix_before_hard_threshold_marker_triggers_retry_via_msp(
        self,
    ) -> None:
        """RW-002: префикс >160/300 символов перед маркером в реальном MSP не блокирует retry."""
        long_err_msg = (
            ("P" * 360)
            + " "
            + self.mod.HARD_THRESHOLD_ERR_SUBSTR
            + " (639915 >= 460800 tokens)"
        )
        script = self.tmp / "msp_retry.py"
        state_file = self.tmp / "msp_attempt.txt"
        prompts_file = self.tmp / "msp_prompts.jsonl"

        def write_msp_wrapper(fail_both: bool) -> None:
            state_file.unlink(missing_ok=True)
            prompts_file.unlink(missing_ok=True)
            script.write_text(
                f"""import json, sys
from pathlib import Path
state_file = Path({str(state_file)!r})
prompts_file = Path({str(prompts_file)!r})
fail_both = {fail_both!r}
long_err_msg = {long_err_msg!r}
for line in sys.stdin:
    msg = json.loads(line)
    if "id" not in msg:
        continue
    method = msg["method"]
    result = {{"session": {{"sessionId": "sess-1"}}}} if method == "session/start" else {{"status": "accepted", "turnId": "turn-1"}} if method == "turn/start" else {{}}
    print(json.dumps({{"id": msg["id"], "result": result}}), flush=True)
    if method == "turn/start":
        prompt_text = msg["params"]["input"][0]["text"]
        with prompts_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(prompt_text) + "\\n")
        attempt = int(state_file.read_text()) + 1 if state_file.exists() else 1
        state_file.write_text(str(attempt))
        if attempt == 1 or fail_both:
            print(json.dumps({{"method": "turn/completed", "params": {{"turnId": "turn-1", "terminal": "failed", "error": {{"kind": "modelError", "message": long_err_msg, "retryable": True}}}}}}), flush=True)
        else:
            print(json.dumps({{"method": "item/completed", "params": {{"item": {{"itemId": "a", "turnId": "turn-1", "kind": "agentMessage", "text": "retry-after-long-prefix-ok"}}}}}}), flush=True)
            print(json.dumps({{"method": "turn/completed", "params": {{"turnId": "turn-1", "terminal": "completed"}}}}), flush=True)
        break
""",
                encoding="utf-8",
            )
            import shlex

            wrapper = self.tmp / "muse-cli.sh"
            wrapper.write_text(
                f"#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(script))}\n",
                encoding="utf-8",
            )
            wrapper.chmod(0o755)
            self.mod.MUSE_WRAPPER = str(wrapper)

        msgs: list[dict[str, Any]] = [
            {"role": "user", "content": "first-u"},
            {"role": "assistant", "content": "mid-" + ("M" * 750_000)},
            {"role": "user", "content": "last-u"},
        ]
        # 1) Первая попытка падает с длинным префиксом, вторая успешна.
        write_msp_wrapper(fail_both=False)
        status, body = bridge_request(
            self, {"model": "muse-wonder-1.0", "messages": msgs}
        )
        self.assertEqual(status, 200, body.decode("utf-8"))
        self.assertIn("retry-after-long-prefix-ok", body.decode("utf-8"))
        seen_prompts = [
            json.loads(line)
            for line in prompts_file.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(len(seen_prompts), 2)
        self.assertLessEqual(self.mod._estimate_tokens(seen_prompts[1]), 200_000)

        # 2) Обе попытки падают с длинным префиксом -> terminal_context_err.
        write_msp_wrapper(fail_both=True)
        status2, body2 = bridge_request(
            self, {"model": "muse-wonder-1.0", "messages": msgs}
        )
        self.assertEqual(status2, 502)
        err_obj = json.loads(body2.decode("utf-8"))["error"]
        self.assertIn(
            "context hard threshold exceeded after single compaction retry",
            err_obj["message"],
        )

    def test_t26_reflected_message_with_embedded_secret_leaves_neither_canary_nor_secret(
        self,
    ) -> None:
        """RW-003 / FU-002: сообщение с приватным текстом и секретом не утекает при отражении."""
        user_msg = "BODY_PRIVATE_CANARY api_key=synthetic-secret"
        install_protocol_wrapper(
            self,
            {
                "terminal": "failed",
                "error": {"message": f"upstream failed on: {user_msg}"},
            },
        )
        for stream in (False, True):
            self.mod.LOG_PATH.unlink(missing_ok=True)
            status, body = bridge_request(
                self,
                {
                    "model": "muse-wonder-1.0",
                    "messages": [{"role": "user", "content": user_msg}],
                    "stream": stream,
                },
            )
            self.assertEqual(status, 200 if stream else 502)
            combined = body.decode("utf-8") + self.mod.LOG_PATH.read_text(
                encoding="utf-8"
            )
            self.assertNotIn("synthetic-secret", combined)
            self.assertNotIn("BODY_PRIVATE_CANARY", combined)

        # FU-002: exec-ветка считает usage по словам, а не по байтам/3.
        cyrillic_reply = "привет " * 30
        with (
            mock.patch.object(
                self.mod.ServeRun,
                "execute",
                side_effect=self.mod.ServeUnavailable("down"),
            ),
            mock.patch.object(
                self.mod.Run,
                "execute",
                return_value={
                    "rc": 0,
                    "state": "ok",
                    "text": cyrillic_reply,
                    "chunks": [cyrillic_reply],
                    "err": "",
                },
            ),
        ):
            status_u, body_u = bridge_request(
                self,
                {
                    "model": "muse-wonder-1.0",
                    "messages": [{"role": "user", "content": "вопрос"}],
                },
            )
        self.assertEqual(status_u, 200)
        usage = json.loads(body_u.decode("utf-8"))["usage"]
        self.assertLess(
            usage["completion_tokens"],
            self.mod._estimate_tokens(cyrillic_reply) // 2,
        )

    def test_t27_serve_unavailable_with_reflected_prompt_does_not_leak_to_log(
        self,
    ) -> None:
        """RW-004: ServeUnavailable с отражённым телом промпта не пишет приватный текст в лог."""
        user_msg = "SERVE_FALLBACK_PRIVATE_CANARY api_key=fallback-secret-123"
        self.mod.LOG_PATH.unlink(missing_ok=True)

        def fail_serve(run_self: Any) -> dict[str, Any]:
            raise self.mod.ServeUnavailable(f"serve exited rc=1: {run_self.prompt}")

        def ok_exec(_run_self: Any) -> dict[str, Any]:
            return {
                "rc": 0,
                "state": "ok",
                "text": "exec-ok",
                "chunks": ["exec-ok"],
                "err": "",
            }

        with (
            mock.patch.object(self.mod.ServeRun, "execute", fail_serve),
            mock.patch.object(self.mod.Run, "execute", ok_exec),
        ):
            status, body = bridge_request(
                self,
                {
                    "model": "muse-wonder-1.0",
                    "messages": [{"role": "user", "content": user_msg}],
                },
            )
        self.assertEqual(status, 200)
        self.assertIn("exec-ok", body.decode("utf-8"))
        logs = self.mod.LOG_PATH.read_text(encoding="utf-8")
        self.assertIn("serve unavailable", logs)
        self.assertIn("fallback exec", logs)
        self.assertNotIn("SERVE_FALLBACK_PRIVATE_CANARY", logs)
        self.assertNotIn("fallback-secret-123", logs)


class ApprovalTest(_BridgeScenario):
    """REQ-MUSE-002 / AD-001, AD-002, AD-006, AD-007 (T-A01..T-A16)."""

    def _shrink_grace(self) -> None:
        self.mod.APPROVAL_CANCEL_GRACE_S = 0.4
        self.mod.CONTROL_WRITE_TIMEOUT_S = 0.5

    def test_t_a01_session_start_allowall_and_flags(self) -> None:
        install_fake_msp(self, serve_plans=[ok_plan()])
        status, body = bridge_request(self, turn_request())
        self.assertEqual(status, 200, body)
        starts = rpc_by_method(self, "session/start")
        self.assertEqual(len(starts), 1)
        self.assertEqual(starts[0]["params"]["approvalMode"], "allowAll")
        argv = json.loads((self.tmp / "serve-argv.json").read_text())
        self.assertNotIn("--disable-write", argv)
        self.assertNotIn("--disable-shell", argv)
        self.assertNotIn("--disable-sandbox", argv)
        logs = self.mod.LOG_PATH.read_text(encoding="utf-8")
        self.assertIn("approvalMode=allowAll", logs)
        self.assertIn("1.4.9-test", logs)

    def test_t_a02_approval_receipt_and_decide_without_exec(self) -> None:
        install_fake_msp(self, serve_plans=[ok_plan({"approval": {}})])
        status, body = bridge_request(self, turn_request())
        self.assertEqual(status, 200, body)
        self.assertIn("hello", body.decode())
        self.assertEqual(proc_count(self, "exec"), 0)
        self.assertEqual(len(rpc_by_method(self, "turn/start")), 1)
        receipts = [
            m for m in rpc_msgs(self) if "method" not in m and m.get("id") == 9000
        ]
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0].get("result"), {})
        decides = rpc_by_method(self, "approval/decide")
        self.assertEqual(len(decides), 1)
        params = decides[0]["params"]
        self.assertEqual(params["choiceId"], "c-approve")
        self.assertEqual(
            params["requirementId"], {"approvalId": "appr-0", "sourceIndex": 0}
        )
        self.assertIn("via=serve", self.mod.LOG_PATH.read_text(encoding="utf-8"))

    def test_t_a03_policy_preference_and_amendment_never_chosen(self) -> None:
        policy = self.mod.ApprovalPolicy("allowAll")
        snap = {
            "approvalId": "a1",
            "sessionId": "s1",
            "toolName": "web_search",
            "availableChoices": [
                {"choiceId": "c-sess", "decision": "approvedForSession"},
                {"choiceId": "c-once", "decision": "approved"},
            ],
        }
        got = policy.evaluate(snap)
        self.assertEqual(got["action"], "approve")
        self.assertEqual(got["choice_id"], "c-once")
        only_amend = dict(
            snap,
            availableChoices=[
                {"choiceId": "c-amend", "decision": "approvedPolicyAmendment"}
            ],
        )
        self.assertEqual(policy.evaluate(only_amend)["action"], "fail_turn")
        # Сценарно: выбор только amendment+abort ведёт в отказную деградацию.
        self._shrink_grace()
        choices = [
            {
                "choiceId": "c-amend",
                "decision": "approvedPolicyAmendment",
                "label": "Amend",
                "scope": "once",
            },
            {
                "choiceId": "c-abort",
                "decision": "abort",
                "label": "Abort",
                "scope": "once",
            },
        ]
        install_fake_msp(
            self,
            serve_plans=[
                {"steps": [{"approval": {"availableChoices": choices}}, {"hang": True}]}
            ],
        )
        status, _ = bridge_request(self, turn_request())
        self.assertEqual(status, 502)
        decides = rpc_by_method(self, "approval/decide")
        self.assertEqual([d["params"]["choiceId"] for d in decides], ["c-abort"])
        self.assertEqual(proc_count(self, "exec"), 0)

    def test_t_a04_terminal_false_then_updated_request(self) -> None:
        plan = ok_plan({"approval": {}, "n": 0}, {"approval": {}, "n": 1})
        plan["decide_replies"] = [
            {"result": {"terminal": False}},
            {"result": {"terminal": True}},
        ]
        install_fake_msp(self, serve_plans=[plan])
        status, body = bridge_request(self, turn_request())
        self.assertEqual(status, 200, body)
        self.assertEqual(len(rpc_by_method(self, "approval/decide")), 2)

    def test_t_a05_requested_dedup_single_decide(self) -> None:
        plan = ok_plan(
            {"approval": {}, "mode": "requested", "n": 0},
        )
        install_fake_msp(self, serve_plans=[plan])
        status, body = bridge_request(self, turn_request())
        self.assertEqual(status, 200, body)
        self.assertEqual(len(rpc_by_method(self, "approval/decide")), 1)
        receipts = [m for m in rpc_msgs(self) if "method" not in m]
        self.assertEqual(receipts, [])
        # Пара request+requested с той же парой — по-прежнему один decide.
        install_fake_msp(
            self,
            serve_plans=[
                ok_plan({"approval": {}, "n": 0}, {"approval_nowait": {}, "n": 0})
            ],
        )
        # approval_nowait шлёт request с другим серверным id, но той же
        # парой appr-0/req-0: второй decide запрещён дедупликацией.
        status, body = bridge_request(self, turn_request())
        self.assertEqual(status, 200, body)
        self.assertEqual(len(rpc_by_method(self, "approval/decide")), 1)

    def test_t_a06_user_input_receipt_and_cancel(self) -> None:
        canary = "CANARY_QUESTION_TEXT"
        plan = ok_plan(
            {"user_input": {"questions": [{"questionId": "q1", "text": canary}]}}
        )
        install_fake_msp(self, serve_plans=[plan])
        status, body = bridge_request(self, turn_request())
        self.assertEqual(status, 200, body)
        self.assertEqual(len(rpc_by_method(self, "userInput/cancel")), 1)
        receipts = [
            m for m in rpc_msgs(self) if "method" not in m and m.get("id") == 9100
        ]
        self.assertEqual(len(receipts), 1)
        self.assertNotIn(canary, self.mod.LOG_PATH.read_text(encoding="utf-8"))

    def test_t_a07_approval_after_setup_window_still_decides(self) -> None:
        self.mod.SERVE_SPAWN_TIMEOUT_S = 2.0
        plan = ok_plan({"delay": 2.6}, {"approval": {}})
        install_fake_msp(self, serve_plans=[plan])
        status, body = bridge_request(self, turn_request())
        self.assertEqual(status, 200, body)
        self.assertEqual(len(rpc_by_method(self, "approval/decide")), 1)
        self.assertEqual(proc_count(self, "exec"), 0)

    def test_t_a08_decide_error_codes_latch_and_32051_benign(self) -> None:
        self._shrink_grace()
        for code in (-32050, -32052, -32053, -32054, -32030):
            with self.subTest(code=code):
                plan = {
                    "steps": [{"approval": {}}, {"hang": True}],
                    "decide_replies": [
                        {"error": {"code": code, "message": "decide boom"}}
                    ],
                }
                install_fake_msp(self, serve_plans=[plan])
                status, _ = bridge_request(self, turn_request())
                self.assertEqual(status, 502)
                self.assertEqual(proc_count(self, "exec"), 0)
                self.assertTrue(self._slot_free())
        with self.subTest(code=-32051):
            plan = ok_plan({"approval": {}})
            plan["decide_replies"] = [
                {"error": {"code": -32051, "message": "already resolved"}}
            ]
            install_fake_msp(self, serve_plans=[plan])
            status, body = bridge_request(self, turn_request())
            self.assertEqual(status, 200, body)
        with self.subTest(case="empty_choices"):
            plan = {
                "steps": [
                    {"approval": {"availableChoices": []}},
                    {"hang": True},
                ]
            }
            install_fake_msp(self, serve_plans=[plan])
            status, _ = bridge_request(self, turn_request())
            self.assertEqual(status, 502)
            self.assertEqual(len(rpc_by_method(self, "approval/decide")), 0)
            self.assertEqual(len(rpc_by_method(self, "turn/cancel")), 1)
        with self.subTest(case="user_input_cancel_error"):
            plan = {
                "steps": [{"user_input": {}}, {"hang": True}],
                "cancel_reply": {"error": {"code": -32603, "message": "cancel boom"}},
            }
            install_fake_msp(self, serve_plans=[plan])
            status, _ = bridge_request(self, turn_request())
            self.assertEqual(status, 502)
            self.assertEqual(proc_count(self, "exec"), 0)

    def test_t_a09_decide_and_cancel_bounds(self) -> None:
        self._shrink_grace()
        plan = {"steps": [{"approval_repeat": 12}]}
        install_fake_msp(self, serve_plans=[plan])
        status, _ = bridge_request(self, turn_request())
        self.assertEqual(status, 502)
        self.assertEqual(len(rpc_by_method(self, "approval/decide")), 10)
        self.assertEqual(proc_count(self, "exec"), 0)
        self.assertTrue(self._slot_free())
        plan = {"steps": [{"user_input_repeat": 5}]}
        install_fake_msp(self, serve_plans=[plan])
        status, _ = bridge_request(self, turn_request())
        self.assertEqual(status, 502)
        self.assertEqual(len(rpc_by_method(self, "userInput/cancel")), 3)
        self.assertTrue(self._slot_free())

    def test_t_a09b_ignored_cancel_killed_within_grace(self) -> None:
        self._shrink_grace()
        plan = {"steps": [{"approval": {"availableChoices": []}}, {"hang": True}]}
        install_fake_msp(self, serve_plans=[plan])
        started = time.monotonic()
        status, body = bridge_request(self, turn_request(stream=True))
        elapsed = time.monotonic() - started
        self.assertEqual(status, 200)
        self.assertEqual(body.count(b"data: [DONE]"), 1)
        self.assertTrue(any("error" in f for f in sse_frames(body)))
        self.assertLess(elapsed, 0.4 + 3.0)
        self.assertTrue(
            wait_until(self._slot_free, SCENARIO_DEADLINE_S), "слот не освободился"
        )
        pids = (self.tmp / "serve-pids.log").read_text().split()
        self.assertTrue(pids)
        self.assertTrue(
            wait_until(lambda: not group_alive(int(pids[-1])), GROUP_EXIT_WAIT_S)
        )
        self.assertEqual(proc_count(self, "exec"), 0)

    def test_t_a09c_blocked_stdin_grace_from_latch(self) -> None:
        self._shrink_grace()
        plan = {
            "steps": [
                {"approval_nowait": {"availableChoices": []}, "n": 3},
                {"no_read_hang": True},
            ]
        }
        install_fake_msp(self, serve_plans=[plan])
        started = time.monotonic()
        status, body = bridge_request(self, turn_request(stream=True))
        elapsed = time.monotonic() - started
        self.assertEqual(status, 200)
        self.assertEqual(body.count(b"data: [DONE]"), 1)
        self.assertLess(elapsed, 0.4 + 3.5)
        self.assertTrue(wait_until(self._slot_free, SCENARIO_DEADLINE_S))
        self.assertEqual(proc_count(self, "exec"), 0)
        self.assertIn(
            "approval_degraded", self.mod.LOG_PATH.read_text(encoding="utf-8")
        )

    def test_t_a10_canaries_redacted_in_audit_log(self) -> None:
        bad_choice = "bad id CANARY_CHOICE"
        choices = [
            {
                "choiceId": bad_choice,
                "decision": "approved",
                "label": "Allow",
                "scope": "once",
            },
            {
                "choiceId": "c-abort",
                "decision": "abort",
                "label": "Abort",
                "scope": "once",
            },
        ]
        plan = ok_plan(
            {
                "approval": {
                    "availableChoices": choices,
                    "toolName": "bad tool CANARY_TOOL",
                    "rawArgs": "CANARY_RAWARGS",
                    "subject": {"kind": "tool", "toolName": "bad tool"},
                }
            }
        )
        install_fake_msp(self, serve_plans=[plan])
        status, body = bridge_request(self, turn_request())
        self.assertEqual(status, 200, body)
        decides = rpc_by_method(self, "approval/decide")
        self.assertEqual(decides[0]["params"]["choiceId"], bad_choice)
        logs = self.mod.LOG_PATH.read_text(encoding="utf-8")
        self.assertIn("approval_decide", logs)
        for canary in ("CANARY_CHOICE", "CANARY_TOOL", "CANARY_RAWARGS"):
            self.assertNotIn(canary, logs)
            self.assertNotIn(canary, body.decode())
        self.assertIn("redacted", logs)

    def test_t_a11_ceiling_32030_single_exec_fallback(self) -> None:
        plan = {"session_error": {"code": -32030, "message": "ceiling"}}
        install_fake_msp(self, serve_plans=[plan])
        status, body = bridge_request(self, turn_request())
        self.assertEqual(status, 200, body)
        self.assertIn("fallback-ok", body.decode())
        self.assertEqual(len(rpc_by_method(self, "session/start")), 1)
        self.assertEqual(len(rpc_by_method(self, "approval/decide")), 0)
        self.assertEqual(len(rpc_by_method(self, "turn/start")), 0)
        self.assertEqual(proc_count(self, "serve"), 1)
        self.assertEqual(proc_count(self, "exec"), 1)
        logs = self.mod.LOG_PATH.read_text(encoding="utf-8")
        self.assertIn("-32030", logs)
        self.assertIn("1.4.9-test", logs)

    def test_t_a11b_deny_unmatched_never_exec(self) -> None:
        self._shrink_grace()
        self.mod.APPROVAL_MODE = "denyUnmatched"
        cases: list[tuple[str, dict]] = [
            ("ceiling", {"session_error": {"code": -32030, "message": "x"}}),
            ("eof", {"handshake_eof": True}),
            ("hang", {"handshake_hang": True}),
            ("no_session", {"no_session_id": True, "steps": []}),
        ]
        for name, plan in cases:
            with self.subTest(case=name):
                if name == "hang":
                    self.mod.SERVE_SPAWN_TIMEOUT_S = 0.4
                install_fake_msp(self, serve_plans=[plan])
                status, body = bridge_request(self, turn_request(stream=True))
                self.assertEqual(status, 200)
                self.assertEqual(body.count(b"data: [DONE]"), 1)
                self.assertIn(b"exec_fallback_disabled", body)
                self.assertEqual(proc_count(self, "exec"), 0)
                self.assertLessEqual(proc_count(self, "serve"), 1)
                self.assertTrue(self._slot_free())
        with self.subTest(case="spawn_failed"):
            exec_calls: list[Any] = []

            def fail_spawn(_self: Any) -> dict:
                raise self.mod.ServeUnavailable("serve spawn failed: boom")

            def fake_exec(run_self: Any) -> dict:
                exec_calls.append(run_self)
                return {"rc": 0, "state": "ok", "text": "x", "chunks": ["x"]}

            with (
                mock.patch.object(self.mod.ServeRun, "execute", fail_spawn),
                mock.patch.object(self.mod.Run, "execute", fake_exec),
            ):
                status, body = bridge_request(self, turn_request(stream=True))
            self.assertEqual(status, 200)
            self.assertIn(b"exec_fallback_disabled", body)
            self.assertEqual(exec_calls, [])

    def test_t_a13_terminal_latch_discards_late_success(self) -> None:
        self._shrink_grace()
        choices = [
            {
                "choiceId": "c-abort",
                "decision": "abort",
                "label": "Abort",
                "scope": "once",
            }
        ]
        plan = {
            "steps": [
                {"approval": {"availableChoices": choices}},
                {"approval_nowait": {}, "n": 5},
                {"terminal": {"terminal": "completed", "text": "late-success"}},
            ],
            "decide_replies": [{"result": {"terminal": False}}],
        }
        install_fake_msp(self, serve_plans=[plan])
        status, body = bridge_request(self, turn_request())
        self.assertEqual(status, 502)
        self.assertNotIn("late-success", body.decode())
        self.assertLessEqual(len(rpc_by_method(self, "approval/decide")), 1)
        self.assertEqual(proc_count(self, "exec"), 0)
        # Молчание после denied: grace убивает группу, исход один.
        plan = {"steps": [{"approval": {"availableChoices": choices}}, {"hang": True}]}
        install_fake_msp(self, serve_plans=[plan])
        status, body = bridge_request(self, turn_request(stream=True))
        self.assertEqual(status, 200)
        self.assertEqual(body.count(b"data: [DONE]"), 1)
        self.assertTrue(wait_until(self._slot_free, SCENARIO_DEADLINE_S))

    def test_t_a14_env_mode_gates_session_and_approve(self) -> None:
        self._shrink_grace()
        self.mod.APPROVAL_MODE = "denyUnmatched"
        install_fake_msp(
            self, serve_plans=[{"steps": [{"approval": {}}, {"hang": True}]}]
        )
        status, _ = bridge_request(self, turn_request())
        self.assertEqual(status, 502)
        starts = rpc_by_method(self, "session/start")
        self.assertEqual(starts[0]["params"]["approvalMode"], "denyUnmatched")
        chosen = [
            d["params"]["choiceId"] for d in rpc_by_method(self, "approval/decide")
        ]
        self.assertNotIn("c-approve", chosen)
        self.assertEqual(proc_count(self, "exec"), 0)
        with mock.patch.dict(os.environ, {"MUSE_BRIDGE_APPROVAL_MODE": "bogus"}):
            with self.assertRaises(Exception):
                load_bridge()

    def test_t_a15_tool_item_journal_without_args(self) -> None:
        canary = "CANARY_TOOL_ARGS"
        plan = {
            "steps": [
                {
                    "tool_item": {
                        "kind": "toolCall",
                        "toolName": "web_search",
                        "rawArgs": canary,
                    }
                },
                fail_terminal(
                    "[net-timeout] boom",
                    timeToFirstTokenMs=123,
                    usage={"outputTokens": 3},
                ),
            ]
        }
        install_fake_msp(self, serve_plans=[plan])
        status, _ = bridge_request(self, turn_request())
        self.assertEqual(status, 502)
        logs = self.mod.LOG_PATH.read_text(encoding="utf-8")
        self.assertIn("tool_item", logs)
        self.assertIn("web_search", logs)
        self.assertIn("tool_items=1", logs)
        self.assertIn("ttft=1", logs)
        self.assertNotIn(canary, logs)

    def test_t_a16_setup_approval_blocks_any_new_process(self) -> None:
        for when in ("initialize", "session/start"):
            for req_mode in ("request", "requested"):
                with self.subTest(when=when, mode=req_mode):
                    plan = {
                        "setup_approval": {
                            "when": when,
                            "mode": req_mode,
                            "effect": "setup-effect",
                            "after": "break",
                        },
                        "steps": [_OK_STEP],
                    }
                    install_fake_msp(self, serve_plans=[plan, ok_plan()])
                    status, body = bridge_request(self, turn_request(stream=True))
                    self.assertEqual(status, 200)
                    self.assertEqual(body.count(b"data: [DONE]"), 1)
                    self.assertTrue(any("error" in f for f in sse_frames(body)))
                    self.assertEqual(proc_count(self, "serve"), 1)
                    self.assertEqual(proc_count(self, "exec"), 0)
                    self.assertEqual(effect_lines(self), ["setup-effect"])
                    self.assertEqual(len(rpc_by_method(self, "approval/decide")), 1)
        # Контроль: setup-транзиент без approval по-прежнему повторяется.
        self.mod.TRANSIENT_BACKOFF_S = (0.0, 0.0)
        self.mod.TRANSIENT_JITTER_S = 0.0
        install_fake_msp(
            self,
            serve_plans=[
                {"session_error": {"code": -32603, "message": "[net-timeout]"}},
                ok_plan(),
            ],
        )
        status, body = bridge_request(self, turn_request())
        self.assertEqual(status, 200, body)
        self.assertEqual(proc_count(self, "serve"), 2)

    def test_startup_constants_validation(self) -> None:
        with mock.patch.dict(os.environ, {"MUSE_BRIDGE_TIMEOUT_S": "100"}):
            with self.assertRaises(Exception):
                load_bridge()
        with mock.patch.dict(os.environ, {"MUSE_BRIDGE_TIMEOUT_S": "1800"}):
            self.assertIsNotNone(load_bridge())


class TransientRetryTest(_BridgeScenario):
    """REQ-MUSE-003 / AD-003 (T-R01..T-R12)."""

    def setUp(self) -> None:
        super().setUp()
        self.mod.TRANSIENT_BACKOFF_S = (0.01, 0.01)
        self.mod.TRANSIENT_JITTER_S = 0.0
        self.mod.APPROVAL_CANCEL_GRACE_S = 0.4

    def test_t_r01_pre_turn_markers_retry_new_serve(self) -> None:
        markers = [
            "[net-timeout]",
            "timed out waiting for response data",
            "network connection could not be opened",
            "transport_connect_unreachable",
        ]
        for marker in markers:
            with self.subTest(marker=marker):
                install_fake_msp(
                    self,
                    serve_plans=[
                        {"session_error": {"code": -32603, "message": marker}},
                        ok_plan(),
                    ],
                )
                status, body = bridge_request(self, turn_request(stream=True))
                self.assertEqual(status, 200, body)
                self.assertEqual(proc_count(self, "serve"), 2)
                self.assertEqual(proc_count(self, "exec"), 0)
                self.assertEqual(body.count(b"data: [DONE]"), 1)
                self.assertFalse(any("error" in f for f in sse_frames(body)))
        for marker in markers:
            with self.subTest(terminal=marker):
                install_fake_msp(
                    self,
                    serve_plans=[{"steps": [fail_terminal(marker)]}, ok_plan()],
                )
                status, _ = bridge_request(self, turn_request())
                self.assertEqual(status, 502)
                self.assertEqual(proc_count(self, "serve"), 1)

    def test_t_r02_three_transient_failures_terminal(self) -> None:
        plan = {"session_error": {"code": -32603, "message": "[net-timeout]"}}
        install_fake_msp(self, serve_plans=[plan, plan, plan, ok_plan()])
        status, _ = bridge_request(self, turn_request())
        self.assertEqual(status, 502)
        self.assertEqual(proc_count(self, "serve"), 3)
        self.assertEqual(proc_count(self, "exec"), 0)
        self.assertTrue(self._slot_free())

    def test_t_r03_no_retry_guards(self) -> None:
        with self.subTest(case="timeout_state"):
            calls: list[int] = []

            def fake_timeout(_self: Any) -> dict:
                calls.append(1)
                return {"rc": 1, "state": "timeout", "text": "", "err": "[net-timeout]"}

            with mock.patch.object(self.mod.ServeRun, "execute", fake_timeout):
                status, _ = bridge_request(self, turn_request())
            self.assertEqual(status, 502)
            self.assertEqual(len(calls), 1)
        with self.subTest(case="spawn_failed_state"):
            calls = []

            def fake_spawn(_self: Any) -> dict:
                calls.append(1)
                return {
                    "rc": 1,
                    "state": "spawn_failed",
                    "text": "",
                    "err": "[net-timeout]",
                }

            with mock.patch.object(self.mod.ServeRun, "execute", fake_spawn):
                status, _ = bridge_request(self, turn_request())
            self.assertEqual(status, 502)
            self.assertEqual(len(calls), 1)
        with self.subTest(case="marker_in_success_text"):
            install_fake_msp(
                self,
                serve_plans=[
                    {
                        "steps": [
                            {
                                "terminal": {
                                    "terminal": "completed",
                                    "text": "note [net-timeout] x",
                                }
                            }
                        ]
                    }
                ],
            )
            status, body = bridge_request(self, turn_request())
            self.assertEqual(status, 200, body)
            self.assertEqual(proc_count(self, "serve"), 1)
        with self.subTest(case="after_live_delta_observed_scope"):
            self.mod.TRANSIENT_RETRY_SCOPE = "observed-items"
            install_fake_msp(
                self,
                serve_plans=[
                    {
                        "steps": [
                            {"summary": [0, "thinking"]},
                            fail_terminal("[net-timeout]"),
                        ]
                    },
                    ok_plan(),
                ],
            )
            status, body = bridge_request(self, turn_request(stream=True))
            self.assertEqual(status, 200)
            self.assertEqual(proc_count(self, "serve"), 1)
            self.assertIn(
                "retry_blocked", self.mod.LOG_PATH.read_text(encoding="utf-8")
            )

    def test_t_r03b_unconfirmed_death_quarantine_then_release(self) -> None:
        proc = CloseKillsGroupTest._spawn_group()
        self.addCleanup(CloseKillsGroupTest._reap_group, proc)
        calls: list[int] = []

        def fake_transient(run_self: Any) -> dict:
            calls.append(1)
            run_self.proc = proc
            raise self.mod.ServeUnavailable("[net-timeout] setup")

        def fake_close(run_self: Any) -> None:
            run_self.dead_confirmed = False

        with (
            mock.patch.object(self.mod.ServeRun, "execute", fake_transient),
            mock.patch.object(self.mod.ServeRun, "close", fake_close),
            mock.patch.object(self.mod, "_kill_group", lambda _p: None),
        ):
            status, _ = bridge_request(self, turn_request())
            self.assertEqual(status, 502)
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(self.mod._quarantined_slots), 1)
            self.assertFalse(self._slot_free())
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5)
            self.assertTrue(wait_until(self._slot_free, SCENARIO_DEADLINE_S))
            self.assertEqual(len(self.mod._quarantined_slots), 0)

    def test_t_r05_retry_gets_only_remaining_budget(self) -> None:
        deadlines: list[float] = []
        started = time.monotonic()

        def fake_serve(run_self: Any) -> dict:
            deadlines.append(float(run_self.exec_deadline))
            if len(deadlines) == 1:
                raise self.mod.ServeUnavailable("[net-timeout] setup")
            return {
                "rc": 0,
                "state": "ok",
                "text": "ok-now",
                "chunks": ["ok-now"],
                "err": "",
            }

        with mock.patch.object(self.mod.ServeRun, "execute", fake_serve):
            status, body = bridge_request(self, turn_request())
        self.assertEqual(status, 200, body)
        self.assertEqual(len(deadlines), 2)
        self.assertAlmostEqual(deadlines[0], deadlines[1], places=6)
        self.assertLess(deadlines[1], started + self.mod.TIMEOUT_S - 30)

    def test_t_r06_admission_predicate_matrix(self) -> None:
        cases: list[tuple[str, dict, int]] = [
            ("turn_start_no_ack", {"turn_start_eof": True}, 502),
            ("summary_eof", {"steps": [{"summary": [0, "x"]}, {"eof": True}]}, 502),
            ("approval_exit", {"steps": [{"approval_then_exit": {}}]}, 502),
            ("cancel_eof", {"steps": [{"approval": {"availableChoices": []}}]}, 502),
        ]
        for name, plan, want in cases:
            with self.subTest(case=name):
                install_fake_msp(self, serve_plans=[plan])
                status, _ = bridge_request(self, turn_request())
                self.assertEqual(status, want)
                self.assertEqual(proc_count(self, "exec"), 0)
        with self.subTest(case="handshake_eof_allows_exec"):
            install_fake_msp(self, serve_plans=[{"handshake_eof": True}])
            status, body = bridge_request(self, turn_request())
            self.assertEqual(status, 200, body)
            self.assertEqual(proc_count(self, "exec"), 1)

    def test_t_r07_action_possible_single_effect(self) -> None:
        with self.subTest(path="serve"):
            install_fake_msp(
                self,
                serve_plans=[
                    {"steps": [{"effect": "fx"}, fail_terminal("[net-timeout] mid")]},
                    ok_plan(),
                ],
            )
            status, _ = bridge_request(self, turn_request())
            self.assertEqual(status, 502)
            self.assertEqual(proc_count(self, "serve"), 1)
            self.assertEqual(effect_lines(self), ["fx"])
        with self.subTest(path="exec"):
            install_fake_msp(
                self,
                serve_plans=[{"handshake_eof": True}],
                exec_plans=[
                    {"rc": 1, "stderr": "[net-timeout] exec", "effect": "exec-fx"}
                ],
            )
            status, _ = bridge_request(self, turn_request())
            self.assertEqual(status, 502)
            self.assertEqual(proc_count(self, "exec"), 1)
            self.assertEqual(effect_lines(self), ["exec-fx"])

    def test_t_r07b_observed_items_scope(self) -> None:
        self.mod.TRANSIENT_RETRY_SCOPE = "observed-items"
        with self.subTest(case="no_signals_retries"):
            install_fake_msp(
                self,
                serve_plans=[
                    {"steps": [{"effect": "fx"}, fail_terminal("[net-timeout] mid")]},
                    ok_plan(),
                ],
            )
            status, body = bridge_request(self, turn_request())
            self.assertEqual(status, 200, body)
            self.assertEqual(proc_count(self, "serve"), 2)
            self.assertIn("retry_scope", self.mod.LOG_PATH.read_text(encoding="utf-8"))
        with self.subTest(case="tool_item_blocks"):
            install_fake_msp(
                self,
                serve_plans=[
                    {"steps": [{"tool_item": {}}, fail_terminal("[net-timeout] mid")]},
                    ok_plan(),
                ],
            )
            status, _ = bridge_request(self, turn_request())
            self.assertEqual(status, 502)
            self.assertEqual(proc_count(self, "serve"), 1)
        with self.subTest(case="invalid_scope_stops_start"):
            with mock.patch.dict(
                os.environ, {"MUSE_BRIDGE_TRANSIENT_RETRY_SCOPE": "bogus"}
            ):
                with self.assertRaises(Exception):
                    load_bridge()

    def test_t_r03c_client_gone_during_retry_pause(self) -> None:
        self.mod.TRANSIENT_BACKOFF_S = (1.0, 1.0)
        install_fake_msp(
            self,
            serve_plans=[
                {"session_error": {"code": -32603, "message": "[net-timeout]"}},
                ok_plan(),
            ],
        )
        sock = self._open_request()
        self.addCleanup(sock.close)
        self.assertTrue(
            wait_until(lambda: proc_count(self, "serve") == 1, 3.0),
            "первый serve не стартовал",
        )
        time.sleep(0.3)
        sock.close()
        self.assertTrue(wait_until(self._slot_free, SCENARIO_DEADLINE_S))
        time.sleep(0.3)
        self.assertEqual(proc_count(self, "serve"), 1)

    def test_t_r08_deadline_from_receipt_queue(self) -> None:
        self.mod._slots = threading.Semaphore(2)
        self.mod.TIMEOUT_S = 2.0
        self.mod.FINISH_RESERVE_S = 0.3
        self.mod.CLOSE_RESERVE_S = 0.2
        self.mod.MIN_ATTEMPT_REMAINING_S = 0.8
        install_fake_msp(self, serve_plans=[ok_plan({"delay": 1.2})])
        results: list[tuple[int, bytes]] = []

        def call() -> None:
            results.append(bridge_request(self, turn_request()))

        threads = [threading.Thread(target=call) for _ in range(3)]
        started = time.monotonic()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=8)
        elapsed = time.monotonic() - started
        self.assertEqual(len(results), 3)
        self.assertLess(elapsed, 3.5)
        self.assertEqual(proc_count(self, "serve"), 2)
        statuses = sorted(s for s, _ in results)
        self.assertEqual(statuses, [200, 200, 503])

    def test_t_r09_parallel_series_max_two_processes(self) -> None:
        self.mod._slots = threading.Semaphore(2)
        plan = {
            "setup_delay": 0.25,
            "session_error": {"code": -32603, "message": "[net-timeout]"},
        }
        install_fake_msp(self, serve_plans=[plan], track_concurrency=True)
        results: list[tuple[int, bytes]] = []
        threads = [
            threading.Thread(
                target=lambda: results.append(bridge_request(self, turn_request()))
            )
            for _ in range(2)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=8)
        self.assertEqual(sorted(s for s, _ in results), [502, 502])
        counts = [int(x) for x in (self.tmp / "concurrency.log").read_text().split()]
        self.assertTrue(counts)
        self.assertLessEqual(max(counts), 2)

    def test_t_r10_model_hangs_to_e_outcome_by_d(self) -> None:
        self.mod.TIMEOUT_S = 2.6
        self.mod.FINISH_RESERVE_S = 0.7
        self.mod.CLOSE_RESERVE_S = 0.3
        self.mod.MIN_ATTEMPT_REMAINING_S = 0.2
        self.mod.LIVE_WRITE_TIMEOUT_S = 0.2
        install_fake_msp(self, serve_plans=[{"steps": [{"hang": True}]}])
        started = time.monotonic()
        status, _ = bridge_request(self, turn_request())
        elapsed = time.monotonic() - started
        self.assertEqual(status, 502)
        self.assertLess(elapsed, 2.6 + 1.5)
        self.assertTrue(wait_until(self._slot_free, SCENARIO_DEADLINE_S))
        self.assertEqual(proc_count(self, "exec"), 0)

    def test_t_r11_setup_approval_no_replay_either_scope(self) -> None:
        for scope in ("pre-action", "observed-items"):
            with self.subTest(scope=scope):
                self.mod.TRANSIENT_RETRY_SCOPE = scope
                plan = {
                    "setup_approval": {
                        "when": "session/start",
                        "mode": "requested",
                        "effect": "setup-fx",
                        "after": "break",
                    },
                    "steps": [_OK_STEP],
                }
                install_fake_msp(self, serve_plans=[plan, ok_plan()])
                status, _ = bridge_request(self, turn_request())
                self.assertEqual(status, 502)
                self.assertEqual(proc_count(self, "serve"), 1)
                self.assertEqual(proc_count(self, "exec"), 0)
                self.assertEqual(effect_lines(self), ["setup-fx"])

    def test_t_r12_slow_steady_delivery_cut_at_w(self) -> None:
        # Детерминированный транспорт: каждый кадр быстрее L, сумма — дольше W.
        self.mod.LIVE_WRITE_TIMEOUT_S = 0.2
        self.mod.SSE_CHUNK_SIZE = 10
        self.mod.SSE_CHUNK_DELAY_S = 0.0
        handler = self.mod.Handler.__new__(self.mod.Handler)
        starts: list[float] = []

        class SlowWriter(io.BytesIO):
            def write(self, data):  # type: ignore[override]
                starts.append(time.monotonic())
                time.sleep(0.05)
                return super().write(data)

        writer = SlowWriter()
        handler._wlock = threading.Lock()
        handler.wfile = writer
        handler._sse_open = True
        handler._live_sent_text = ""
        w = time.monotonic() + 0.32
        handler._write_deadline = w
        handler._send_sse("muse-spark-1.3", "x" * 200, [], 1, 1, 0)
        self.assertNotIn(b"data: [DONE]", writer.getvalue())
        self.assertTrue(all(s <= w + 0.06 for s in starts), starts)
        # Контроль: малый N успевает до W целиком с одним [DONE].
        writer2 = SlowWriter()
        handler.wfile = writer2
        handler._sse_phase = "OPEN"
        handler._client_gone = False
        handler._write_deadline = time.monotonic() + 5
        handler._send_sse("muse-spark-1.3", "hi", [], 1, 1, 0)
        self.assertEqual(writer2.getvalue().count(b"data: [DONE]"), 1)
        self.assertIn(b"hi", writer2.getvalue())


class LiveReasoningTest(_BridgeScenario):
    """REQ-MUSE-004 / AD-004 (T-L01..T-L09)."""

    def test_t_l01_live_deltas_concat_equals_buffered(self) -> None:
        plan = ok_plan(
            {"summary": [0, "think-"]},
            {"summary": [0, "more"]},
            {"summary": [1, "second"]},
        )
        install_fake_msp(self, serve_plans=[plan])
        status, body = bridge_request(self, turn_request(stream=True))
        self.assertEqual(status, 200, body)
        deltas = sse_deltas(body, "reasoning_content")
        self.assertGreaterEqual(len(deltas), 3)
        self.assertEqual("".join(deltas), "think-more\n\nsecond")
        self.assertEqual("".join(sse_deltas(body, "content")), "hello")
        self.assertEqual(body.count(b"data: [DONE]"), 1)

    def test_t_l02_completed_only_summaries_not_lost(self) -> None:
        plan = ok_plan({"reasoning_completed": ["alpha", "beta"]})
        install_fake_msp(self, serve_plans=[plan])
        status, body = bridge_request(self, turn_request(stream=True))
        self.assertEqual(status, 200, body)
        self.assertEqual(
            "".join(sse_deltas(body, "reasoning_content")), "alpha\n\nbeta"
        )
        install_fake_msp(self, serve_plans=[plan])
        status, body = bridge_request(self, turn_request())
        self.assertEqual(status, 200, body)
        self.assertEqual(json.loads(body)["reasoning_summaries"], ["alpha", "beta"])

    def test_t_l03_keepalive_data_chunks_preserved(self) -> None:
        self.mod.KEEPALIVE_S = 0.05
        install_fake_msp(self, serve_plans=[ok_plan({"delay": 0.25})])
        status, body = bridge_request(self, turn_request(stream=True))
        self.assertEqual(status, 200, body)
        self.assertNotIn(b": keepalive", body)
        self.assertEqual(body.count(b"data: [DONE]"), 1)
        self.assertTrue(any(d == "" for d in sse_deltas(body, "content")[:-1]))

    def test_t_l04_live_write_failure_is_terminal_not_exception(self) -> None:
        handler = self.mod.Handler.__new__(self.mod.Handler)

        class BrokenWriter(io.BytesIO):
            def write(self, data):  # type: ignore[override]
                raise OSError("closed peer")

        handler._wlock = threading.Lock()
        handler.wfile = BrokenWriter()
        handler._sse_open = True
        handler._live_sent_text = ""
        self.assertFalse(handler._live_reasoning_sink("thinking"))
        self.assertTrue(handler._client_gone)

    def test_t_l05_model_retry_scheduled_log_only(self) -> None:
        plan = ok_plan(
            {
                "model_retry": {
                    "attempt": 1,
                    "maxAttempts": 4,
                    "retryDelayMs": 500,
                    "errorKind": "network",
                    "turnId": "turn-1",
                }
            }
        )
        install_fake_msp(self, serve_plans=[plan])
        status, body = bridge_request(self, turn_request(stream=True))
        self.assertEqual(status, 200, body)
        self.assertEqual(sse_deltas(body, "reasoning_content"), [])
        logs = self.mod.LOG_PATH.read_text(encoding="utf-8")
        self.assertIn("modelRetryScheduled", logs)
        self.assertIn("attempt=1", logs)

    def test_t_l06_out_of_order_summaries_prefix_monotone(self) -> None:
        plan = ok_plan(
            {"summary": [0, "a"]},
            {"summary": [1, "b"]},
            {"summary": [0, "c"]},
        )
        install_fake_msp(self, serve_plans=[plan])
        status, body = bridge_request(self, turn_request(stream=True))
        self.assertEqual(status, 200, body)
        self.assertEqual("".join(sse_deltas(body, "reasoning_content")), "ac\n\nb")
        plan = ok_plan({"summary": [1, "b"]}, {"summary": [0, "a"]})
        install_fake_msp(self, serve_plans=[plan])
        status, body = bridge_request(self, turn_request(stream=True))
        self.assertEqual(status, 200, body)
        self.assertEqual("".join(sse_deltas(body, "reasoning_content")), "a\n\nb")

    def test_t_l07_diverged_snapshot_sends_authoritative_full(self) -> None:
        handler = self.mod.Handler.__new__(self.mod.Handler)
        handler._wlock = threading.Lock()
        handler.wfile = io.BytesIO()
        handler._sse_open = True
        handler._live_sent_text = "a"
        handler._send_sse("muse-spark-1.3", "hi", [], 1, 1, 0, ["b", "c"])
        deltas = sse_deltas(handler.wfile.getvalue(), "reasoning_content")
        self.assertEqual(deltas, ["\n\nb\n\nc"])
        logs = self.mod.LOG_PATH.read_text(encoding="utf-8")
        self.assertIn("reasoning_diverged", logs)
        handler2 = self.mod.Handler.__new__(self.mod.Handler)
        handler2._wlock = threading.Lock()
        handler2.wfile = io.BytesIO()
        handler2._sse_open = True
        handler2._live_sent_text = "a"
        handler2._send_sse("muse-spark-1.3", "hi", [], 1, 1, 0, ["ab"])
        self.assertEqual(
            sse_deltas(handler2.wfile.getvalue(), "reasoning_content"), ["b"]
        )

    def _timing_handler(self) -> Any:
        handler = self.mod.Handler.__new__(self.mod.Handler)
        handler._wlock = threading.Lock()
        handler._sse_open = True
        handler._live_sent_text = ""
        handler._write_deadline = time.monotonic() + 30
        conn = SimpleNamespace(_timeout=None)

        def gettimeout() -> Any:
            return conn._timeout

        def settimeout(value: Any) -> None:
            conn._timeout = value

        conn.gettimeout = gettimeout  # type: ignore[attr-defined]
        conn.settimeout = settimeout  # type: ignore[attr-defined]
        handler.connection = conn
        return handler

    def test_t_l08a_live_write_bounded_by_single_budget(self) -> None:
        self.mod.LIVE_WRITE_TIMEOUT_S = 0.2
        handler = self._timing_handler()

        class TimeoutWriter(io.BytesIO):
            def write(self, data):  # type: ignore[override]
                limit = handler.connection.gettimeout() or 5.0
                time.sleep(min(float(limit), 5.0))
                raise TimeoutError("socket timeout")

        handler.wfile = TimeoutWriter()
        started = time.monotonic()
        self.assertFalse(handler._live_reasoning_sink("thinking"))
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertTrue(handler._client_gone)

    def test_t_l08b_keepalive_blocking_first_bounds_sink(self) -> None:
        self.mod.LIVE_WRITE_TIMEOUT_S = 0.25
        handler = self._timing_handler()
        release = threading.Event()
        self.addCleanup(release.set)

        class BlockWriter(io.BytesIO):
            def write(self, data):  # type: ignore[override]
                limit = handler.connection.gettimeout() or 5.0
                if not release.wait(timeout=float(limit)):
                    raise TimeoutError("socket timeout")
                return super().write(data)

        handler.wfile = BlockWriter()
        results: dict[str, Any] = {}
        ka = threading.Thread(
            target=lambda: results.__setitem__(
                "ka", handler._sse_write("data: ka\n\n", keepalive=True)
            ),
            daemon=True,
        )
        ka.start()
        time.sleep(0.05)
        started = time.monotonic()
        self.assertFalse(handler._live_reasoning_sink("summary"))
        self.assertLess(time.monotonic() - started, 1.0)
        ka.join(timeout=2)
        self.assertFalse(ka.is_alive())

    def test_t_l08c_terminal_delivery_and_stop_bounded(self) -> None:
        self.mod.LIVE_WRITE_TIMEOUT_S = 0.2
        handler = self._timing_handler()

        class TimeoutWriter(io.BytesIO):
            def write(self, data):  # type: ignore[override]
                limit = handler.connection.gettimeout() or 5.0
                time.sleep(min(float(limit), 5.0))
                raise TimeoutError("socket timeout")

        handler.wfile = TimeoutWriter()
        started = time.monotonic()
        handler._send_sse("muse-spark-1.3", "hello", [], 1, 1, 0)
        self.assertLess(time.monotonic() - started, 1.5)
        self.assertTrue(handler._client_gone)

    def test_t_l09_slow_steady_frames_stop_at_w(self) -> None:
        self.mod.LIVE_WRITE_TIMEOUT_S = 0.2
        self.mod.SSE_CHUNK_SIZE = 10
        self.mod.SSE_CHUNK_DELAY_S = 0.0
        handler = self.mod.Handler.__new__(self.mod.Handler)
        starts: list[float] = []

        class SlowWriter(io.BytesIO):
            def write(self, data):  # type: ignore[override]
                starts.append(time.monotonic())
                time.sleep(0.05)
                return super().write(data)

        writer = SlowWriter()
        handler._wlock = threading.Lock()
        handler.wfile = writer
        handler._sse_open = True
        handler._live_sent_text = ""
        w = time.monotonic() + 0.32
        handler._write_deadline = w
        handler._send_sse("muse-spark-1.3", "y" * 200, [], 1, 1, 0)
        self.assertNotIn(b"data: [DONE]", writer.getvalue())
        self.assertTrue(all(s <= w + 0.06 for s in starts), starts)
        self.assertNotIn(b'"finish_reason": "stop"', writer.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
