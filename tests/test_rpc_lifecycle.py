"""Жизненный цикл процессов чатов: idle-реап и restore, cap/вытеснение, таймауты, метаданные,
остановка, дрейф droid, окружение ребёнка, журнал, инвентарь baseline.

Часы моста подменяются (FakeClock), реальный droid и сеть не используются: процесс —
fake stream-jsonrpc subprocess (tests/fake_droid.py). Идентификаторы TM-NNN — в имени
метода и docstring.
"""

import json
import os
import signal
import socket
import stat
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from bridge_testlib import pid_alive, wait_until  # noqa: E402
from rpc_testlib import (  # noqa: E402
    DONE_LINE,
    EXEC_LINE,
    REJECT_LINE,
    USAGE_LINE,
    FakeClock,
    RpcCase,
)

SLOW = {"steps": [{"op": "sleep", "s": 1.0}, {"op": "text", "text": "slow"}]}


class TestIdleAndRestore(RpcCase):
    def setUp(self):
        super().setUp()
        self.clock = FakeClock(1000.0)
        server._clock = self.clock

    def _reap(self):
        return server.REGISTRY.reap_once()

    def test_tm008_idle_reap_boundary_and_restore_same_sid(self):
        """TM-008: t=2699 жив, t=2700 закрыт; release сбрасывает таймер; restore того же SID 3 цикла."""
        chat = self.conv("chat-idle")
        self.assertEqual(chat.ask("q0")[0], 200)
        self.assertEqual(chat.ask("q1")[0], 200)
        state = self.chat_of("chat-idle")
        sid, first_pid = state.sid, state.proc.pid
        self.assertEqual(state.last_used, 1000.0)  # release сбросил таймер
        self.clock.now = 1000.0 + 2699
        self.assertEqual(self._reap(), [])
        self.assertTrue(state.proc.alive())
        self.clock.now = 1000.0 + 2700
        self.assertEqual(self._reap(), [state.key_hash[:8]])
        self.assertTrue(self.wait_gone(first_pid))
        self.assertEqual(self.health()["active"], 0)
        self.assertEqual(state.state, "PERSISTED")
        self.assertEqual(state.sid, sid)  # SID и файлы остаются, процесс закрыт штатно
        # Закрытие штатное (close_session/EOF), а не убийство процесса.
        self.assertTrue(
            wait_until(
                lambda: any(e["reason"] == "close_session" for e in self.hub.exits())
            )
        )
        pids = [first_pid]
        for cycle in range(3):
            self.assertEqual(chat.ask(f"r{cycle}")[0], 200)
            self.assertEqual(state.sid, sid)
            pids.append(state.proc.pid)
            self.clock.advance(2700)
            self.assertEqual(self._reap(), [state.key_hash[:8]])
        self.assertEqual(len(set(pids)), 4)  # каждый restore — новый PID
        loads = self.hub.rpcs("droid.load_session")
        self.assertEqual([r["params"]["sessionId"] for r in loads], [sid] * 3)
        self.assertEqual(len(self.hub.inits()), 1)  # initialize ровно один раз
        self.assertEqual(state.restore_count, 3)
        # В restore в RPC уходит только суффикс (новый user), history не replay-ится.
        self.assertEqual(self.hub.sent_texts(), ["q0", "q1", "r0", "r1", "r2"])

    def test_tm008_busy_chat_is_never_reaped(self):
        """TM-008: busy/pending не вытесняется реапером; release сбрасывает таймер."""
        self.hub.script([SLOW])
        chat = self.conv("chat-busy")
        thread = threading.Thread(target=lambda: chat.ask("long"))
        thread.start()
        self.assertTrue(
            wait_until(
                lambda: (
                    server.REGISTRY.chats and self.chat_of("chat-busy").lock.locked()
                )
            )
        )
        time.sleep(0.3)
        self.clock.now = 10**6
        self.assertEqual(self._reap(), [])  # ход идёт: аренда занята
        thread.join(30)
        self.assertEqual(self.chat_of("chat-busy").last_used, 10**6)
        self.clock.now = 10**6 + 2699
        self.assertEqual(self._reap(), [])

    def test_tm008_corrupt_or_missing_state_falls_back_to_history(self):
        """TM-008: повреждённое/отсутствующее состояние -> history-fallback (новая generation)."""
        chat = self.conv("chat-corrupt")
        chat.ask("q0")
        state = self.chat_of("chat-corrupt")
        record = server._record_path(state.key_hash)
        self.assertTrue(record.exists())
        self.clock.advance(2700)
        self._reap()
        record.write_text("{not json", encoding="utf-8")
        server.REGISTRY = (
            server.ChatRegistry()
        )  # рестарт моста: реестр заново читает диск
        inits = len(self.hub.inits())
        with self.capture_logs() as lines:
            self.assertEqual(chat.ask("q1")[0], 200)
        self.assertEqual(len(self.hub.inits()), inits + 1)
        self.assertEqual(self.hub.rpcs("droid.load_session"), [])
        self.assertTrue(any("record=corrupt" in ln for ln in lines))
        self.assertTrue(
            all(
                skip
                for _, skip in self.texts_by_pid()[
                    self.chat_of("chat-corrupt").proc.pid
                ][:-1]
            )
        )
        # Отсутствующий файл — то же самое.
        record = server._record_path(self.chat_of("chat-corrupt").key_hash)
        self.clock.advance(2700)
        self._reap()
        record.unlink()
        server.REGISTRY = server.ChatRegistry()
        inits = len(self.hub.inits())
        self.assertEqual(chat.ask("q2")[0], 200)
        self.assertEqual(len(self.hub.inits()), inits + 1)

    def test_tm008_restore_cap_gives_fresh_generation(self):
        """TM-008: restore_count>5 -> шестой restore = свежая generation с replay."""
        chat = self.conv("chat-cap")
        chat.ask("q0")
        state = self.chat_of("chat-cap")
        state.restore_count = server.RESTORE_MAX
        old_sid, generation = state.sid, state.generation
        self.clock.advance(2700)
        self._reap()
        loads = len(self.hub.rpcs("droid.load_session"))
        inits = len(self.hub.inits())
        self.assertEqual(chat.ask("q1")[0], 200)
        self.assertEqual(len(self.hub.rpcs("droid.load_session")), loads)
        self.assertEqual(len(self.hub.inits()), inits + 1)
        self.assertNotEqual(state.sid, old_sid)
        self.assertEqual(state.generation, generation + 1)
        self.assertEqual(state.restore_count, 0)

    def test_tm008_scaffolding_duplicates_detected_on_first_repeat(self):
        """TM-008: каталог tools, добавляемый на каждом load, ловится на первом повторе (restore_integrity)."""
        self.hub.configure(load_scaffolding=True)
        chat = self.conv("chat-scaffold")
        chat.ask("q0")
        state = self.chat_of("chat-scaffold")
        sid = state.sid
        self.clock.advance(2700)
        self._reap()
        self.assertEqual(
            chat.ask("q1")[0], 200
        )  # первый restore: один каталог — допустимо
        self.assertEqual(state.sid, sid)
        self.clock.advance(2700)
        self._reap()
        with self.capture_logs() as lines:
            self.assertEqual(
                chat.ask("q2")[0], 200
            )  # повтор: каталог задвоен -> санитация
        self.assertTrue(any(ln.startswith("restore_integrity ") for ln in lines))
        self.assertNotEqual(state.sid, sid)
        replay = self.texts_by_pid()[state.proc.pid]
        self.assertEqual([t for t, _ in replay], ["q0", "PONG", "q1", "PONG", "q2"])
        self.assertTrue(all(skip for _, skip in replay[:-1]))

    def test_tm008_droid_ahead_of_bridge_gives_history_fallback(self):
        """TM-008: droid впереди запроса (лишнее сообщение) -> свежий авторитетный replay."""
        chat = self.conv("chat-ahead")
        chat.ask("q0")
        state = self.chat_of("chat-ahead")
        sid = state.sid
        self.clock.advance(2700)
        self._reap()
        self.hub.configure(load_advances=True)
        with self.capture_logs() as lines:
            self.assertEqual(chat.ask("q1")[0], 200)
        self.assertTrue(any("HISTORY_MISMATCH" in ln for ln in lines))
        self.assertNotEqual(state.sid, sid)


class TestCapAndQueue(RpcCase):
    def setUp(self):
        super().setUp()
        self.saved_cap = server.MAX_CONCURRENT
        self.saved_queue = server.QUEUE_TIMEOUT_S
        self.saved_ka = server.KEEPALIVE_S
        self.clock = FakeClock(1000.0)
        server._clock = self.clock

    def tearDown(self):
        server.MAX_CONCURRENT = self.saved_cap
        server.QUEUE_TIMEOUT_S = self.saved_queue
        server.KEEPALIVE_S = self.saved_ka
        super().tearDown()

    def test_tm009_cap_lru_eviction_keeps_state_and_never_exceeds_cap(self):
        """TM-009/TM-021: cap включает все процессы; вытеснение LRU idle, данные чата сохраняются."""
        server.MAX_CONCURRENT = 2
        peak = []
        stop = threading.Event()

        def sample():
            while not stop.is_set():
                peak.append(len(server._active))
                time.sleep(0.01)

        sampler = threading.Thread(target=sample, daemon=True)
        sampler.start()
        try:
            convs = {name: self.conv("chat-" + name) for name in "abc"}
            for name in "abc":
                self.clock.advance(1)
                self.assertEqual(convs[name].ask("hi " + name)[0], 200)
            # c вытеснил LRU idle (a): процесс закрыт, SID и запись остались.
            a = self.chat_of("chat-a")
            self.assertIsNone(a.proc)
            self.assertEqual(a.state, "PERSISTED")
            self.assertTrue(a.sid)
            self.assertTrue(server._record_path(a.key_hash).exists())
            self.assertEqual(self.health()["active"], 2)
            # Вернувшийся a восстанавливается тем же SID, вытесняя уже b.
            sid = a.sid
            self.clock.advance(1)
            self.assertEqual(convs["a"].ask("again")[0], 200)
            self.assertEqual(a.sid, sid)
            self.assertIsNone(self.chat_of("chat-b").proc)
            self.assertEqual(len(self.hub.rpcs("droid.load_session")), 1)
        finally:
            stop.set()
            sampler.join(2)
        self.assertLessEqual(max(peak), 2)
        self.assertTrue(
            wait_until(lambda: server.POOL.used == len(server._rpc_procs) == 2)
        )

    def test_tm009_pending_chat_not_evicted_and_queue_waits_for_slot(self):
        """TM-009: busy-чат не вытесняется; при полном cap — FIFO-очередь с keepalive до освобождения."""
        server.MAX_CONCURRENT = 1
        server.KEEPALIVE_S = 0.2
        self.hub.script([SLOW])
        busy = self.conv("chat-busy")
        out = {}
        first = threading.Thread(
            target=lambda: out.__setitem__("busy", busy.ask("long"))
        )
        first.start()
        self.assertTrue(
            wait_until(
                lambda: (
                    server.REGISTRY.chats and self.chat_of("chat-busy").lock.locked()
                )
            )
        )
        time.sleep(0.4)
        started = time.monotonic()
        status, stream = self._post(
            {
                "model": "claude-sonnet-5-5",
                "stream": True,
                "prompt_cache_key": "chat-wait",
                "messages": [{"role": "user", "content": "hello"}],
            }
        )
        first.join(30)
        self.assertEqual(out["busy"][0], 200)
        self.assertEqual(status, 200)
        self.assertIn(": keepalive", stream)  # keepalive в очереди
        self.assertGreater(
            time.monotonic() - started, 0.3
        )  # ждал занятый слот, но не 900 с
        self.assertIn('"content": "PONG"', stream)
        self.assertIsNone(
            self.chat_of("chat-busy").proc
        )  # после завершения был вытеснен (LRU idle)

    def test_tm009_queue_timeout_and_client_abort_return_reservations(self):
        """TM-009: таймаут очереди -> 503 overloaded; отмена клиента возвращает билет; счётчики как раньше."""
        server.MAX_CONCURRENT = 1
        self.hub.script(
            [{"steps": [{"op": "sleep", "s": 2.0}, {"op": "text", "text": "slow"}]}]
        )
        busy = self.conv("chat-busy2")
        first = threading.Thread(target=lambda: busy.ask("long"))
        first.start()
        self.assertTrue(
            wait_until(
                lambda: (
                    server.REGISTRY.chats and self.chat_of("chat-busy2").lock.locked()
                )
            )
        )
        time.sleep(0.3)
        server.QUEUE_TIMEOUT_S = 1
        status, body = self._post_json(
            {
                "model": "claude-sonnet-5-5",
                "prompt_cache_key": "chat-q",
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        self.assertEqual(status, 503)
        self.assertEqual(body["error"]["type"], "overloaded")
        # Клиент уходит из очереди: билет и резервации возвращены, spawn не было.
        server.QUEUE_TIMEOUT_S = 900
        payload = json.dumps(
            {
                "model": "claude-sonnet-5-5",
                "prompt_cache_key": "chat-gone",
                "messages": [{"role": "user", "content": "hi"}],
            }
        ).encode()
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        sock.sendall(self._raw_request(payload))
        time.sleep(0.6)
        sock.close()
        first.join(30)
        self.assertTrue(wait_until(lambda: not server.POOL.queue))
        self.assertEqual(len(self.hub.spawns()), 1)
        self.assertEqual(server.POOL.used, len(server._rpc_procs))

    def test_tm009_concurrent_claims_and_reaper_race_without_deadlock(self):
        """TM-009: гонка claim/reaper при тесном cap без дедлока и двойной аренды."""
        server.MAX_CONCURRENT = 2
        results = []
        stop = threading.Event()

        def reaper():
            while not stop.is_set():
                self.clock.advance(5000)
                server.REGISTRY.reap_once()
                time.sleep(0.02)

        def worker(index):
            chat = self.conv(f"chat-race-{index % 4}")
            for turn in range(2):
                results.append(chat.ask(f"w{index}-{turn}")[0])

        racer = threading.Thread(target=reaper, daemon=True)
        racer.start()
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(120)
        stop.set()
        racer.join(5)
        self.assertEqual(len(results), 12)
        self.assertEqual(set(results), {200})
        # Двойной аренды нет: на каждый чат в каждый момент один владелец (все замки свободны).
        for chat_state in server.REGISTRY.chats.values():
            self.assertFalse(chat_state.lock.locked())
        self.assertTrue(wait_until(lambda: server.POOL.used == len(server._rpc_procs)))
        self.assertLessEqual(server.POOL.used, 2)


class TestTimeoutsAndCancel(RpcCase):
    def setUp(self):
        super().setUp()
        self.saved_ka = server.KEEPALIVE_S

    def tearDown(self):
        server.KEEPALIVE_S = self.saved_ka
        super().tearDown()

    def test_tm010_silence_watchdog_interrupts_and_invalidates_chat(self):
        """TM-010: watchdog без прогресса -> interrupt, 504 timeout; чат DIRTY, следующий ход — replay."""
        server.SILENCE_WATCHDOG_S = 0.6
        self.hub.script(
            [{"steps": [{"op": "text", "text": "partial"}, {"op": "hang"}]}]
        )
        chat = self.conv("chat-wd")
        status, body = chat.ask("q0")
        self.assertEqual(status, 504)
        self.assertEqual(body["error"]["type"], "timeout")
        self.assertTrue(wait_until(lambda: self.hub.rpcs("droid.interrupt_session")))
        state = self.chat_of("chat-wd")
        self.assertEqual(state.state, "DIRTY")
        self.assertIsNone(state.proc)
        # Следующий запрос того же ключа строится заново из истории запроса.
        chat.msgs.pop()  # клиент повторяет тот же запрос
        inits = len(self.hub.inits())
        status, body = chat.ask("q0 retry")
        self.assertEqual(status, 200)
        self.assertEqual(len(self.hub.inits()), inits + 1)
        self.assertTrue(wait_until(lambda: server.POOL.used == len(server._rpc_procs)))

    def test_tm010_first_token_total_keepalive_and_client_gone(self):
        """TM-010: first-token, общий таймаут, keepalive при буферизации, client_gone -> interrupt и аренда свободна."""
        # first-token: initialize не отвечает дольше порога.
        server.FIRST_TOKEN_TIMEOUT_S = 0.5
        self.hub.configure(init_delay=3.0)
        status, body = self._post_json(
            {
                "model": "claude-sonnet-5-5",
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        self.assertEqual(status, 504)
        self.assertEqual(body["error"]["type"], "first_token_timeout")
        server.FIRST_TOKEN_TIMEOUT_S = self._saved["FIRST_TOKEN_TIMEOUT_S"]
        self.hub.configure(init_delay=0)
        # keepalive во время буферизации (ход молчит в SSE до terminal).
        server.KEEPALIVE_S = 0.2
        self.hub.script(
            [{"steps": [{"op": "sleep", "s": 2.5}, {"op": "text", "text": "buffered"}]}]
        )
        status, stream = self._post(
            {
                "model": "claude-sonnet-5-5",
                "stream": True,
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        self.assertEqual(status, 200)
        self.assertGreaterEqual(stream.count(": keepalive"), 2)
        self.assertIn('"content": "buffered"', stream)
        # общий абсолютный таймаут хода.
        server.TIMEOUT_S = 1
        self.hub.script([{"steps": [{"op": "hang"}]}])
        status, body = self._post_json(
            {
                "model": "claude-sonnet-5-5",
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        self.assertEqual(status, 504)
        self.assertEqual(body["error"]["type"], "timeout")
        server.TIMEOUT_S = self._saved["TIMEOUT_S"]
        # client_gone -> interrupt, аренда чата и слоты свободны, следующий запрос проходит.
        self.hub.script(
            [{"steps": [{"op": "sleep", "s": 6.0}, {"op": "text", "text": "never"}]}]
        )
        interrupts_before = len(self.hub.rpcs("droid.interrupt_session"))
        calls = []
        real_gone = server._client_gone
        server._client_gone = lambda sock: calls.append(1) or len(calls) > 3
        try:
            payload = json.dumps(
                {
                    "model": "claude-sonnet-5-5",
                    "prompt_cache_key": "chat-gone",
                    "messages": [{"role": "user", "content": "long"}],
                }
            ).encode()
            sock = socket.create_connection(("127.0.0.1", self.port), timeout=5)
            sock.sendall(self._raw_request(payload))
            self.assertTrue(
                wait_until(
                    lambda: (
                        len(self.hub.rpcs("droid.interrupt_session"))
                        > interrupts_before
                    ),
                    timeout=20,
                )
            )
            sock.close()
        finally:
            server._client_gone = real_gone
        state = self.chat_of("chat-gone")
        self.assertTrue(wait_until(lambda: not state.lock.locked()))
        self.assertTrue(server._slots.acquire(timeout=5))
        server._slots.release()
        chat = self.conv("chat-gone")
        self.assertEqual(chat.ask("again")[0], 200)

    def test_tm010_late_events_are_not_counted_for_next_request(self):
        """TM-010: запоздавшее событие прежнего хода не засчитывается следующему запросу."""
        self.hub.script(
            [
                {"steps": [{"op": "text", "text": "A0"}], "late": 0.3},
                {
                    "steps": [{"op": "text", "text": "A1"}],
                    "usage": {"inputTokens": 21, "outputTokens": 2},
                },
            ]
        )
        chat = self.conv("chat-late")
        self.assertEqual(chat.ask("q0")[0], 200)
        time.sleep(
            0.8
        )  # запоздавшие LATE/terminal уже лежат в inbox простаивающего процесса
        status, body = chat.ask("q1")
        self.assertEqual(status, 200)
        self.assertEqual(body["choices"][0]["message"]["content"], "A1")
        self.assertEqual(body["usage"]["prompt_tokens"], 21)


class TestPersistenceAndShutdown(RpcCase):
    def test_tm012_metadata_atomic_private_and_crash_recovery(self):
        """TM-012: метаданные атомарны (0600/0700, только хеши); смерть посреди хода -> replay без двойного user."""
        server.AUTH_KEY = "test-key"
        chat = self.conv(
            "secret-chat-key-ABC",
        )
        self.assertEqual(chat.ask("CANARY-PROMPT-TEXT")[0], 200)
        state = self.chat_of("secret-chat-key-ABC")
        record = server._record_path(state.key_hash)
        self.assertEqual(stat.S_IMODE(record.stat().st_mode), 0o600)
        for directory in (
            record.parent,
            record.parent.parent,
            record.parent.parent.parent,
        ):
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
        raw = record.read_text(encoding="utf-8")
        data = json.loads(raw)
        self.assertEqual(data["state"], "READY")
        self.assertEqual(
            data["rec_rev"], 2
        )  # RW-019: PENDING пишется до первого add_user_message, затем READY
        self.assertEqual(chat.ask("second")[0], 200)
        self.assertEqual(
            json.loads(record.read_text(encoding="utf-8"))["rec_rev"], 4
        )  # ещё PENDING + READY
        self.assertNotIn("CANARY-PROMPT-TEXT", raw)
        self.assertNotIn("secret-chat-key-ABC", raw)
        self.assertNotIn("test-key", raw)
        self.assertEqual(
            sorted(p.name for p in record.parent.iterdir()), [record.name]
        )  # tmp не остался
        # Смерть процесса посреди хода: чат DIRTY на диске, следующий запрос — replay, user ровно один раз.
        self.hub.script([{"steps": [{"op": "exit", "rc": 1, "stderr": "crash"}]}] * 3)
        status, _ = chat.ask("q-crash")
        self.assertEqual(status, 502)
        self.assertEqual(
            json.loads(record.read_text(encoding="utf-8"))["state"], "DIRTY"
        )
        chat.msgs.pop()
        self.hub.script([{"steps": [{"op": "text", "text": "recovered"}]}])
        status, body = chat.ask("q-crash")
        self.assertEqual(status, 200)
        replay = self.texts_by_pid()[self.chat_of("secret-chat-key-ABC").proc.pid]
        self.assertEqual(
            [t for t, _ in replay],
            ["CANARY-PROMPT-TEXT", "PONG", "second", "PONG", "q-crash"],
        )
        self.assertEqual([t for t, _ in replay].count("q-crash"), 1)

    def test_tm012_pending_marker_after_bridge_death_forces_replay(self):
        """TM-012: отпечаток PENDING после падения моста -> reconcile свежим replay; load не используется."""
        chat = self.conv("chat-pending")
        chat.ask("q0")
        state = self.chat_of("chat-pending")
        server._write_record(state, "PENDING")  # мост умер между отпечатком и commit
        server._reset_rpc_state()  # «рестарт»: процессы закрыты, реестр читает диск
        inits = len(self.hub.inits())
        self.assertEqual(chat.ask("q1")[0], 200)
        self.assertEqual(len(self.hub.inits()), inits + 1)
        self.assertEqual(self.hub.rpcs("droid.load_session"), [])
        # Штатный рестарт (READY на диске) — restore того же SID.
        sid = self.chat_of("chat-pending").sid
        server._reset_rpc_state()
        self.assertEqual(chat.ask("q2")[0], 200)
        self.assertEqual(self.chat_of("chat-pending").sid, sid)
        self.assertEqual(len(self.hub.rpcs("droid.load_session")), 1)

    def test_tm012_write_failure_and_rec_rev_conflict_mark_chat_dirty(self):
        """TM-012/RW-005: сбой записи PENDING/расхождение rec_rev -> 502 до add_user_message, чат DIRTY, replay."""
        chat = self.conv("chat-write")
        chat.ask("q0")
        real = server._atomic_write

        def failing(path, data):
            raise OSError(28, "No space left on device")

        server._atomic_write = failing
        adds = len(self.hub.rpcs("droid.add_user_message"))
        try:
            status, body = chat.ask("q1")
        finally:
            server._atomic_write = real
        self.assertEqual(status, 502)  # без записи PENDING ход не начинается
        self.assertEqual(body["error"]["type"], "proxy_error")
        self.assertEqual(len(self.hub.rpcs("droid.add_user_message")), adds)
        self.assertEqual(self.chat_of("chat-write").state, "DIRTY")
        chat.msgs.pop()  # клиент повторяет запрос
        inits = len(self.hub.inits())
        self.assertEqual(chat.ask("q2")[0], 200)  # DIRTY -> rebase из истории запроса
        self.assertEqual(len(self.hub.inits()), inits + 1)
        # Расхождение rec_rev (второй писатель): запись отклонена, слияния нет, ход не начат.
        state = self.chat_of("chat-write")
        record = server._record_path(state.key_hash)
        data = json.loads(record.read_text(encoding="utf-8"))
        data["rec_rev"] += 10
        record.write_text(json.dumps(data), encoding="utf-8")
        adds = len(self.hub.rpcs("droid.add_user_message"))
        status, body = chat.ask("q3")
        self.assertEqual(status, 502)
        self.assertEqual(body["error"]["type"], "proxy_error")
        self.assertEqual(len(self.hub.rpcs("droid.add_user_message")), adds)
        self.assertEqual(state.state, "DIRTY")

    def test_tm012_writer_lock_rejects_second_bridge_instance(self):
        """TM-012: flock на .writer.lock отклоняет второй экземпляр моста; после освобождения — свободен."""
        first = server.acquire_writer_lock()
        self.assertIsNotNone(first)
        try:
            self.assertEqual(
                stat.S_IMODE(
                    (server.WORKSPACE / "state" / ".writer.lock").stat().st_mode
                ),
                0o600,
            )
            self.assertIsNone(server.acquire_writer_lock())
        finally:
            first.close()
        third = server.acquire_writer_lock()
        self.assertIsNotNone(third)
        third.close()

    def test_tm013_shutdown_closes_four_children_within_budget(self):
        """TM-013: SIGTERM-путь при 4 детях < 5 с, чужие PID не трогаются; новые запросы отклоняются."""
        for index in range(4):
            self.assertEqual(self.conv(f"chat-s{index}").ask("hi")[0], 200)
        pids = [r["pid"] for r in self.hub.spawns()]
        self.assertEqual(len(pids), 4)
        bystander = subprocess.Popen(["sleep", "30"], start_new_session=True)
        try:
            procs = list(server._rpc_procs.values())
            started = time.monotonic()
            closed = server.shutdown_all()
            elapsed = time.monotonic() - started
            self.assertEqual(closed, 4)
            self.assertLess(elapsed, 5.0)
            self.assertTrue(all(not pid_alive(pid) for pid in pids))
            self.assertEqual(server._rpc_procs, {})
            self.assertTrue(
                all(not p._reader.is_alive() for p in procs)
            )  # reader-потоки закрыты
            self.assertIsNone(bystander.poll())  # чужой процесс жив
            status, body = self._post_json(
                {
                    "model": "claude-sonnet-5-5",
                    "messages": [{"role": "user", "content": "late"}],
                }
            )
            self.assertEqual(status, 503)
            self.assertEqual(body["error"]["type"], "overloaded")
        finally:
            bystander.kill()
            bystander.wait()

    def test_tm013_reconcile_kills_only_own_orphans_by_start_signature(self):
        """TM-013: на старте проверка PID/PGID/start-signature; чужой PID не убивается; EOF у детей при смерти родителя."""
        own = subprocess.Popen(["sleep", "60"], start_new_session=True)
        foreign = subprocess.Popen(["sleep", "60"], start_new_session=True)
        reused = subprocess.Popen(["sleep", "60"], start_new_session=True)
        try:
            entries = [
                {
                    "pid": own.pid,
                    "start": server._proc_start_sig(own.pid),
                    "bridge_pid": 1,
                },
                {
                    "pid": reused.pid,
                    "start": "Mon Jan  1 00:00:00 1990",
                    "bridge_pid": 1,
                },  # подпись не совпала
                {"pid": foreign.pid, "start": "", "bridge_pid": 1},  # без подписи
            ]
            server._atomic_write(server._children_path(), json.dumps(entries).encode())
            self.assertEqual(server.reconcile_children(), 1)
            self.assertTrue(wait_until(lambda: own.poll() is not None))
            self.assertIsNone(foreign.poll())
            self.assertIsNone(reused.poll())
            self.assertEqual(json.loads(server._children_path().read_text()), [])
        finally:
            for proc in (own, foreign, reused):
                if proc.poll() is None:
                    proc.kill()
                proc.wait()
        # SIGKILL родителя -> EOF stdin у детей -> самозавершение (без участия моста).
        parent_code = (
            "import subprocess,sys,os,time\n"
            "env=dict(os.environ)\n"
            "p=subprocess.Popen([%r,%r,'exec'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,"
            "start_new_session=True,env=env)\n"
            "print(p.pid,flush=True)\n"
            "time.sleep(60)\n" % (str(self.hub.launcher), "x")
        )
        parent = subprocess.Popen(
            [sys.executable, "-c", parent_code], stdout=subprocess.PIPE, text=True
        )
        try:
            child_pid = int(parent.stdout.readline())
            self.assertTrue(pid_alive(child_pid))
            parent.send_signal(signal.SIGKILL)
            parent.wait()
            self.assertTrue(self.wait_gone(child_pid, timeout=8))
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.wait()
            parent.stdout.close()

    def test_tm014_tool_catalogue_drift_and_unknown_responses_fail_closed(self):
        """TM-014: новый tool id отключается, сбой list_tools/невалидный init — fail-closed без LLM-хода."""
        chat = self.conv("chat-drift")
        chat.ask("q0")
        first = [
            r["params"]["disabledToolIds"]
            for r in self.hub.rpcs("droid.update_session_settings")
            if "disabledToolIds" in r["params"]
        ]
        self.assertEqual(first, [["Read", "Execute", "Edit", "web_search"]])
        # Дрейф версии droid: на новой generation каталог шире — отключаются ВСЕ актуальные id.
        self.hub.configure(
            tools=["Read", "Execute", "Edit", "web_search", "BrandNewTool"]
        )
        chat.msgs[0] = {"role": "user", "content": "edited prefix"}
        self.assertEqual(chat.ask("q1")[0], 200)
        second = [
            r["params"]["disabledToolIds"]
            for r in self.hub.rpcs("droid.update_session_settings")
            if "disabledToolIds" in r["params"]
        ]
        self.assertIn("BrandNewTool", second[-1])
        # Ошибка list_tools: каталог неизвестен — ход не начинается (fail-closed).
        admissions = len(self.hub.admissions())
        self.hub.configure(list_tools_error=True)
        status, body = self._post_json(
            {
                "model": "claude-sonnet-5-5",
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        self.assertEqual(status, 502)
        self.assertEqual(body["error"]["type"], "proxy_error")
        self.assertEqual(len(self.hub.admissions()), admissions)
        # Неизвестный обязательный ответ: initialize без sessionId -> 502, без add_user_message.
        self.hub.configure(list_tools_error=False, bad_init=True)
        status, body = self._post_json(
            {
                "model": "claude-sonnet-5-5",
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        self.assertEqual(status, 502)
        self.assertEqual(body["error"]["type"], "proxy_error")
        self.assertEqual(len(self.hub.admissions()), admissions)
        # Молчаливая подмена модели невозможна (read-back).
        self.hub.configure(bad_init=False, substitute_model="gpt-default")
        status, body = self._post_json(
            {
                "model": "claude-sonnet-5-5",
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        self.assertEqual(status, 502)
        self.assertEqual(body["error"]["type"], "droid_error")
        self.assertEqual(len(self.hub.admissions()), admissions)

    def test_tm015_child_env_private_dirs_and_no_secrets_in_log_or_state(self):
        """TM-015: ключ моста вырезан, FACTORY_API_KEY унаследован и не в лог/state; права 0700/0600; sweep не трогает state."""
        saved = {
            k: os.environ.get(k)
            for k in (
                "FACTORY_API_KEY",
                "DROID_DSH_BRIDGE_KEY",
                "FAKE_DROID_EXPECT_KEY",
            )
        }
        os.environ["FACTORY_API_KEY"] = "TESTFACTORYKEY-NOT-REAL-0123456789"
        os.environ["FAKE_DROID_EXPECT_KEY"] = "TESTFACTORYKEY-NOT-REAL-0123456789"
        os.environ["DROID_DSH_BRIDGE_KEY"] = "bridge-secret-value-xyz"
        try:
            with self.capture_logs() as lines:
                chat = self.conv("chat-env")
                self.assertEqual(chat.ask("hi")[0], 200)
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        spawn = self.hub.spawns()[0]
        self.assertTrue(spawn["factory_api_key_present"])
        self.assertTrue(
            spawn["factory_api_key_expected"]
        )  # значение сверено в fake, в журнал не пишется
        self.assertNotIn("TESTFACTORYKEY-NOT-REAL", json.dumps(spawn))
        self.assertFalse(spawn["bridge_key_in_env"])
        joined = "\n".join(lines)
        self.assertNotIn("TESTFACTORYKEY-NOT-REAL", joined)
        self.assertNotIn("bridge-secret-value-xyz", joined)
        state_dir = server.WORKSPACE / "state"
        for path in state_dir.rglob("*"):
            if path.is_file():
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("TESTFACTORYKEY-NOT-REAL", text)
                self.assertNotIn("bridge-secret-value-xyz", text)
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            else:
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
        home = server.WORKSPACE / "runtime" / "factory-home"
        self.assertEqual(stat.S_IMODE(home.stat().st_mode), 0o700)
        # sweep трогает только prompt-*/img-*: собственное хранилище остаётся.
        old = time.time() - 7200
        for path in list(state_dir.rglob("*")):
            os.utime(path, (old, old))
        before = sorted(str(p) for p in state_dir.rglob("*"))
        server._sweep_workspace()
        self.assertEqual(before, sorted(str(p) for p in state_dir.rglob("*")))


class TestJournalGolden(RpcCase):
    STRICT = (EXEC_LINE, USAGE_LINE, DONE_LINE, REJECT_LINE)

    def test_tm019_new_lines_outside_strict_regexes_and_order_stable(self):
        """TM-019: session_rpc/instr_guard не совпадают со строгими регулярками; strict-строки и их порядок неизменны."""
        instr = (
            "<system-reminder>\nWorkspace instruction budget 106496 bytes: omitted ~/.dsh/AGENTS.md\n"
            "Instructions from: /x/AGENTS.md\nbody\n</system-reminder>"
        )
        chat = self.conv("chat-golden")
        chat.add(
            {"role": "user", "content": "hello"}, {"role": "user", "content": instr}
        )
        with self.capture_logs() as lines:
            self.assertEqual(chat.send()[0], 200)
            self.assertEqual(chat.ask("again")[0], 200)
        strict = [
            ln for ln in lines if ln.startswith(("exec ", "usage ", "done ", "reject "))
        ]
        for line in strict:
            self.assertTrue(any(rx.match(line) for rx in self.STRICT), line)
        new = [ln for ln in lines if ln.startswith(("session_rpc ", "instr_guard "))]
        self.assertTrue(new)
        for line in new:
            self.assertFalse(any(rx.match(line) for rx in self.STRICT), line)
        kinds = [
            ln.split(" ", 1)[0]
            for ln in lines
            if ln.split(" ", 1)[0]
            in ("exec", "instr_guard", "session_rpc", "usage", "done")
        ]
        self.assertEqual(
            kinds,
            [
                "exec",
                "instr_guard",
                "session_rpc",
                "usage",
                "done",
                "exec",
                "session_rpc",
                "usage",
                "done",
            ],
        )
        guard = [ln for ln in lines if ln.startswith("instr_guard ")][0]
        self.assertRegex(
            guard, r"^instr_guard sections=1 omitted=~/\.dsh/AGENTS\.md bytes=\d+$"
        )
        session = [ln for ln in lines if ln.startswith("session_rpc ")][0]
        self.assertRegex(
            session, r"^session_rpc chat=[0-9a-f]{8} key=1 path=cold gen=0 sid=-$"
        )
        # Golden неудачного хода: usage без сессии, формат строки не менялся.
        broken = Path(self._tmp.name) / "broken-launcher"
        broken.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        broken.chmod(0o755)
        server.LAUNCHER = str(broken)
        with self.capture_logs() as lines:
            status, _ = self._post_json(
                {
                    "model": "claude-sonnet-5-5",
                    "messages": [{"role": "user", "content": "hi"}],
                }
            )
        self.assertEqual(status, 502)
        usage = [ln for ln in lines if ln.startswith("usage ")]
        self.assertEqual(usage, ["usage sess=- raw=0/0 rep=0/0 resumed=0 turns=0"])
        self.assertEqual(len([ln for ln in lines if ln.startswith("exec ")]), 3)


class TestBaselineInventory(unittest.TestCase):
    def test_tm016_baseline_inventory_mapped_to_current_tests(self):
        """TM-016: все 92 baseline-теста сохранены либо сопоставлены (oracle_change) с новыми кейсами."""
        data = json.loads(
            (Path(__file__).resolve().parent / "baseline_inventory.json").read_text(
                encoding="utf-8"
            )
        )
        loader = unittest.defaultTestLoader
        suite = loader.discover(
            str(Path(__file__).resolve().parent), pattern="test_*.py"
        )
        present = set()

        def walk(item):
            if isinstance(item, unittest.TestSuite):
                for sub in item:
                    walk(sub)
            else:
                module = type(item).__module__.split(".")[-1]
                present.add(f"{module}.{type(item).__name__}.{item._testMethodName}")

        walk(suite)
        self.assertEqual(len(data["baseline_to_current"]), 92)
        missing = [
            (old, new)
            for old, targets in data["baseline_to_current"].items()
            for new in targets
            if new not in present
        ]
        self.assertEqual(missing, [])
        renamed = {
            old: t for old, t in data["baseline_to_current"].items() if t != [old]
        }
        self.assertEqual(len(renamed), 4)  # ровно 4 перепривязанных oracle_change


if __name__ == "__main__":
    unittest.main(verbosity=2)
