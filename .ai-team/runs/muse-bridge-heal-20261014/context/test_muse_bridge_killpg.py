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


class ServeTurnErrorExtractionTest(_BridgeScenario):
    """AD-002: приоритет, защитный разбор и точные лимиты терминальной причины."""

    def _execute(self, params: dict, noise: bool = False) -> dict:
        install_protocol_wrapper(self, params, noise)
        return self.mod.ServeRun(
            "muse-spark-1.3", "p", "max", self.tmp / "workspace"
        ).execute()

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
    """AD-004: реальные argv фейка и неизменный approval fallback."""

    def test_serve_argv_disables_write_shell(self) -> None:
        install_protocol_wrapper(self, {"terminal": "completed"})
        self.assertEqual(bridge_request(self, turn_request())[0], 200)
        argv = json.loads((self.tmp / "serve-argv.json").read_text())
        for flag in (
            "--disable-write",
            "--disable-shell",
            "--provider",
            "meta",
            "--model",
            "muse-spark-1.3",
            "--no-session-log",
            "--trust-workspace",
        ):
            self.assertIn(flag, argv)

    def test_approval_falls_back_to_exec_without_decide(self) -> None:
        install_protocol_wrapper(self, {"approval": True})
        status, body = bridge_request(self, turn_request())
        self.assertEqual(status, 200, body)
        self.assertIn("fallback-ok", body.decode())
        argv = json.loads((self.tmp / "exec-argv.json").read_text())
        for flag in (
            "--disable-write",
            "--disable-shell",
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
        self.assertNotIn("approval/decide", (self.tmp / "rpc.jsonl").read_text())
        self.assertIn(
            "serve unavailable (serve needs interaction (approval/request)), fallback exec",
            self.mod.LOG_PATH.read_text(),
        )


class AllowedModelsSyncTest(_BridgeScenario):
    """AD-005: модели доступны в конфигурации и обоих GET endpoints."""

    def test_models_and_health_include_wonder_models(self) -> None:
        models = ("muse-wonder-1.0", "muse-wonder-full-1.0")
        for model in models:
            self.assertEqual(
                self.mod.ALLOWED_MODELS.get(model),
                {"context_length": 1048576, "max_output": 131072},
            )
        for path in ("/health", "/v1/models"):
            status, body = bridge_request(self, path=path)
            self.assertEqual(status, 200)
            for model in models:
                self.assertIn(model, body.decode())


if __name__ == "__main__":
    unittest.main(verbosity=2)
