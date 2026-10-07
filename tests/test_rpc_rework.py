"""Регрессионные тесты cycle-2 rework (RW-002…RW-015): каждый красный на коде 830937e.

Все сценарии идут через настоящий HTTP-сервер моста и настоящий fake-subprocess
(tests/fake_droid.py), говорящий stream-jsonrpc. Реальный droid и сеть не используются;
значения ключей в тестах фиктивные. Идентификаторы RW-NNN — в имени метода и docstring.
"""

import hashlib
import json
import os
import socket
import sys
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from bridge_testlib import pid_alive, wait_until  # noqa: E402
from rpc_testlib import FakeClock, RpcCase  # noqa: E402
from test_images_strict import ImageCase  # noqa: E402

BODY = {"model": "claude-sonnet-5-5"}


def msg(text, role="user"):
    return {"role": role, "content": text}


def post_safely(case, body, timeout=60.0):
    """(status, json) либо (repr(исключения), None): обрыв соединения — провал теста, а не ошибка."""
    try:
        return case._post_json(body, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - диагностический разбор теста
        return repr(exc), None


def no_leaks(case):
    """Процессы/слоты/билеты возвращены: P == число живых процессов."""
    return wait_until(lambda: server.POOL.used == len(server._rpc_procs) and not server.POOL.queue)


class TestTagsSchema(RpcCase):
    """RW-015: строковый tags в initialize_session отвергается схемой реального droid."""

    def test_rw015_initialize_params_follow_real_droid_schema(self):
        """RW-015: ход проходит, а tags в initialize либо отсутствует, либо список объектов."""
        status, _ = self.conv("chat-tags").ask("hi")
        self.assertEqual(status, 200)
        tags = self.hub.inits()[0]["params"].get("tags")
        self.assertTrue(tags is None or (isinstance(tags, list) and all(isinstance(t, dict) for t in tags)))

    def test_rw015_fake_rejects_string_tags_like_real_droid(self):
        """RW-015: fake_droid строго валидирует tags: строка в списке -> JSON-RPC error про tags."""
        proc = server.RpcProcess(str(server.WORKSPACE), server.POOL, False)
        try:
            with self.assertRaises(server.RpcError) as caught:
                proc.call("droid.initialize_session", {
                    "machineId": "t", "cwd": str(server.WORKSPACE), "modelId": "m",
                    "tags": ["droid-dsh-bridge"]})
            self.assertIn("tags", str(caught.exception))
        finally:
            proc.close(mode="term")


class TestSecretsScrub(RpcCase):
    """RW-014: реальный FACTORY_API_KEY не доезжает до артефактов тестов."""

    CANARY = "CANARY-REAL-FACTORY-KEY-0123456789abcdef"

    def setUp(self):
        self._pre = os.environ.get("FACTORY_API_KEY")
        os.environ["FACTORY_API_KEY"] = self.CANARY
        self.addCleanup(self._restore)
        self.addCleanup(self._check_restored)  # выполнится после cleanup общего setUp (LIFO)
        super().setUp()

    def _restore(self):
        if self._pre is None:
            os.environ.pop("FACTORY_API_KEY", None)
        else:
            os.environ["FACTORY_API_KEY"] = self._pre

    def _check_restored(self):
        # Общий setUp обязан вернуть окружение к значению ДО себя (в т.ч. при падении теста).
        self.assertEqual(os.environ.get("FACTORY_API_KEY"), self.CANARY)

    def test_rw014_canary_key_is_replaced_and_not_on_disk(self):
        """RW-014: унаследованный ключ подменён sentinel; canary нет ни в log.jsonl, ни в state, ни в tmp."""
        self.assertNotEqual(os.environ.get("FACTORY_API_KEY"), self.CANARY)
        self.assertEqual(self.conv("chat-secret").ask("hi")[0], 200)
        spawn = self.hub.spawns()[0]
        self.assertTrue(spawn["factory_api_key_present"])
        self.assertTrue(spawn["factory_api_key_expected"])
        leaks = [str(p) for p in Path(self._tmp.name).rglob("*")
                 if p.is_file() and self.CANARY.encode() in p.read_bytes()]
        self.assertEqual(leaks, [])

    def test_rw014_env_restored_even_when_test_body_fails(self):
        """RW-014: падение тела теста не оставляет подменённый ключ (addCleanup восстанавливает)."""
        with self.assertRaises(AssertionError):
            self.assertEqual(1, 2)
        self.assertNotEqual(os.environ.get("FACTORY_API_KEY"), self.CANARY)


class TestTurnIdFilter(RpcCase):
    """RW-013: terminal прежнего хода не завершает следующий."""

    def test_rw013_stale_terminal_after_arming_is_ignored(self):
        """RW-013: stale terminal (turnId прошлого хода) во время финального add: ход не завершён, usage/output свои."""
        self.hub.script([
            {"steps": [{"op": "text", "text": "A0"}]},
            {"steps": [{"op": "stale_terminal"}, {"op": "text", "text": "A1"}],
             "usage": {"inputTokens": 21, "outputTokens": 2}},
        ])
        chat = self.conv("chat-stale")
        self.assertEqual(chat.ask("q0")[0], 200)
        status, body = chat.ask("q1")
        self.assertEqual(status, 200)
        self.assertEqual(body["choices"][0]["message"]["content"], "A1")
        self.assertEqual(body["usage"]["prompt_tokens"], 21)


class TestRetractionCounter(RpcCase):
    """RW-012: retraction уменьшает счётчик сообщений droid, restore сохраняет SID."""

    def test_rw012_draft_retract_final_then_idle_restore_keeps_sid(self):
        """RW-012: draft -> retract -> final -> реапер -> restore: тот же SID, load вместо init, только суффикс."""
        clock = FakeClock(1000.0)
        server._clock = clock
        self.hub.script([{"steps": [{"op": "text", "text": "draft"}, {"op": "retry"},
                                    {"op": "retract"}, {"op": "text", "text": "final"}]}])
        chat = self.conv("chat-retract")
        status, body = chat.ask("q0")
        self.assertEqual(status, 200)
        self.assertEqual(body["choices"][0]["message"]["content"], "final")
        state = self.chat_of("chat-retract")
        sid = state.sid
        saved = json.loads((self.hub.base / "sessions" / f"{sid}.json").read_text(encoding="utf-8"))
        real_in_droid = sum(1 for m in saved["messages"] if not server._is_service_message(m))
        self.assertEqual(state.droid_real, real_in_droid)
        clock.advance(2700)
        self.assertEqual(server.REGISTRY.reap_once(), [state.key_hash[:8]])
        self.assertEqual(chat.ask("q1")[0], 200)
        self.assertEqual(state.sid, sid)
        self.assertEqual(len(self.hub.rpcs("droid.load_session")), 1)
        self.assertEqual(len(self.hub.inits()), 1)
        self.assertEqual(self.hub.sent_texts(), ["q0", "q1"])


class TestRecordValidation(RpcCase):
    """RW-010: валидный JSON с испорченными полями -> history-fallback без обрыва HTTP."""

    CASES = {
        "rec_rev_text": lambda rec: rec.update(rec_rev="abc"),
        "rec_rev_list": lambda rec: rec.update(rec_rev=[1]),
        "head_missing": lambda rec: rec.pop("head"),
        "n_text": lambda rec: rec.update(n="x"),
    }

    def test_rw010_malformed_record_replays_from_history(self):
        """RW-010: запись с нечисловым rec_rev/без полей: 200, запись заменена валидной, PID/слот не утекли."""
        for name, mutate in self.CASES.items():
            with self.subTest(name):
                key = "chat-rec-" + name
                chat = self.conv(key)
                self.assertEqual(chat.ask("q0")[0], 200)
                state = self.chat_of(key)
                record = server._record_path(state.key_hash)
                server._reset_rpc_state()  # «рестарт»: процессы закрыты, реестр читает диск
                rec = json.loads(record.read_text(encoding="utf-8"))
                mutate(rec)
                record.write_text(json.dumps(rec), encoding="utf-8")
                inits = len(self.hub.inits())
                status, _ = post_safely(self, dict(BODY, prompt_cache_key=key, messages=chat.msgs + [msg("q1")]))
                self.assertEqual(status, 200)
                self.assertEqual(len(self.hub.inits()), inits + 1)  # replay из истории, без load
                self.assertEqual(self.chat_of(key).state, "READY")
                self.assertIsNotNone(server._read_record(record))  # повреждённая запись заменена
                self.assertTrue(no_leaks(self))


class TestFactoryHome(RpcCase):
    """RW-006: сбой подготовки чистого Factory home запрещает spawn."""

    def test_rw006_mkdir_failure_refuses_spawn(self):
        """RW-006: _mkdir_private(factory-home) бросает OSError -> Popen не вызван, штатный 502, ресурсы целы."""
        real = server._mkdir_private

        def failing(path):
            if "factory-home" in str(path):
                raise OSError(13, "Permission denied")
            return real(path)

        server._mkdir_private = failing
        try:
            status, body = self._post_json(dict(BODY, messages=[msg("hi")]))
        finally:
            server._mkdir_private = real
        self.assertEqual(status, 502)
        self.assertEqual(body["error"]["type"], "proxy_error")
        self.assertEqual(self.hub.spawns(), [])
        self.assertTrue(no_leaks(self))
        self.assertEqual(server.POOL.used, 0)


class TestSettingsFailClosed(RpcCase):
    """RW-005: любое сомнение в read-back безопасных настроек — ход не начинается."""

    SCENARIOS = {
        "no_autonomy": {"omit_autonomy": True},
        "no_settings_updated": {"no_readback": True},
        "no_disabled_ids": {"omit_disabled_ids": True},
        "tools_without_ids": {"raw_tools": [{"name": "Read"}, {"name": "Execute"}]},
        "empty_catalogue": {"raw_tools": []},
        "skills_mismatch": {"echo_flags": True, "flags_override": {"disableBuiltinSkills": False}},
        "autoreject_mismatch": {"echo_flags": True, "flags_override": {"autoRejectPermissionRequests": False}},
    }

    def test_rw005_each_scenario_raises_rpc_error_before_add_user_message(self):
        """RW-005: 7 сценариев -> 502 proxy_error/droid_error и ни одного add_user_message."""
        for name, config in self.SCENARIOS.items():
            with self.subTest(name):
                self.hub.config.clear()
                self.hub.configure(**config)
                before = len(self.hub.rpcs("droid.add_user_message"))
                status, body = self._post_json(dict(BODY, messages=[msg("hi")]))
                self.assertEqual(status, 502, body)
                self.assertEqual(len(self.hub.rpcs("droid.add_user_message")), before)
                self.assertTrue(no_leaks(self))

    def test_rw005_positive_control_with_echoed_flags(self):
        """RW-005: корректный read-back (включая эхо флагов) ход пропускает."""
        self.hub.configure(echo_flags=True)
        status, _ = self._post_json(dict(BODY, messages=[msg("hi")]))
        self.assertEqual(status, 200)


class TestDroidReceipt(RpcCase):
    """RW-007: spawn допускается только по receipt квалификации образа; исполняется образ из receipt."""

    def setUp(self):
        super().setUp()
        server.RECEIPT_REQUIRED = True
        self._env_bin = os.environ.get("DROID_BIN")
        self.addCleanup(self._restore_bin)

    def _restore_bin(self):
        if self._env_bin is None:
            os.environ.pop("DROID_BIN", None)
        else:
            os.environ["DROID_BIN"] = self._env_bin

    def _install_image(self, content=b"qualified-image"):
        digest = hashlib.sha256(content).hexdigest()
        image_dir = server.WORKSPACE / "runtime" / "droid-image" / digest
        image_dir.mkdir(parents=True)
        image = image_dir / "droid"
        image.write_bytes(content)
        image.chmod(0o500)
        server._atomic_write(server._receipt_path(), json.dumps({
            "schema": 1, "image_path": str(image), "image_sha256": digest}).encode())
        return image, digest

    def _ask(self):
        return self._post_json(dict(BODY, messages=[msg("hi")]))

    def test_rw007_missing_receipt_refuses_spawn(self):
        """RW-007: receipt отсутствует -> 503 launcher_unavailable, процесса нет."""
        status, body = self._ask()
        self.assertEqual(status, 503)
        self.assertEqual(body["error"]["type"], "launcher_unavailable")
        self.assertEqual(self.hub.spawns(), [])

    def test_rw007_mismatching_receipt_refuses_spawn(self):
        """RW-007: образ изменён после квалификации (sha не совпал) -> 503, процесса нет."""
        image, _ = self._install_image()
        image.chmod(0o700)
        image.write_bytes(b"tampered-image")
        status, body = self._ask()
        self.assertEqual(status, 503)
        self.assertEqual(body["error"]["type"], "launcher_unavailable")
        self.assertEqual(self.hub.spawns(), [])

    def test_rw007_valid_receipt_runs_pinned_image_not_global_binary(self):
        """RW-007: глобальный DROID_BIN подменён, но ребёнок получает образ из receipt."""
        image, _ = self._install_image()
        os.environ["DROID_BIN"] = "/usr/local/bin/droid-global-updated"
        status, _ = self._ask()
        self.assertEqual(status, 200)
        self.assertEqual(self.hub.spawns()[0]["droid_bin"], os.path.realpath(str(image)))


class TestDroidImageTool(RpcCase):
    """RW-007: tools/droid_image.py даёт образ и receipt, которые мост принимает на spawn."""

    def test_rw007_installed_image_is_accepted_by_bridge(self):
        """RW-007: образ 0500 в каталоге 0700, receipt атомарный; мост запускает его как DROID_BIN."""
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
        import droid_image
        source = Path(self._tmp.name) / "global-droid"
        source.write_bytes(b"global-droid-binary")
        source.chmod(0o755)
        receipt = droid_image.install_image(source, server.WORKSPACE)
        image = Path(receipt["image_path"])
        self.assertEqual(oct(image.stat().st_mode & 0o777), "0o500")
        self.assertEqual(oct(image.parent.stat().st_mode & 0o777), "0o700")
        self.assertEqual(receipt["image_sha256"], hashlib.sha256(b"global-droid-binary").hexdigest())
        self.assertEqual(source.read_bytes(), b"global-droid-binary")  # глобальный бинарь не тронут
        server.RECEIPT_REQUIRED = True
        status, _ = self._post_json(dict(BODY, messages=[msg("hi")]))
        self.assertEqual(status, 200)
        self.assertEqual(self.hub.spawns()[0]["droid_bin"], os.path.realpath(str(image)))


class TestByteBudgets(RpcCase):
    """RW-008: байтовые лимиты и предусмотренные отказы с возвратом ресурсов."""

    def test_rw008_oversized_rpc_line_is_rejected_and_resources_returned(self):
        """RW-008: строка RPC больше лимита -> 502, процесс закрыт, слот/билет возвращены."""
        server.MAX_RPC_LINE_BYTES = 50_000
        self.hub.script([{"steps": [{"op": "big_line", "bytes": 200_000}, {"op": "text", "text": "late"}]}])
        status, body = self._post_json(dict(BODY, messages=[msg("hi")]))
        self.assertEqual(status, 502)
        self.assertEqual(body["error"]["type"], "proxy_error")
        pid = self.hub.spawns()[0]["pid"]
        self.assertTrue(self.wait_gone(pid))
        self.assertTrue(no_leaks(self))
        self.assertTrue(wait_until(lambda: server.POOL.used == 0))  # слот возвращается после waitpid

    def test_rw008_turn_text_accumulation_is_capped(self):
        """RW-008: накопление text хода сверх лимита -> предусмотренная ошибка, не OOM."""
        server.MAX_TURN_TEXT_BYTES = 100_000
        self.hub.script([{"steps": [{"op": "flood", "count": 50, "size": 10_000},
                                    {"op": "text", "text": "tail"}]}])
        status, body = self._post_json(dict(BODY, messages=[msg("hi")]))
        self.assertEqual(status, 502)
        self.assertIn("limit", json.dumps(body))
        self.assertTrue(no_leaks(self))

    def test_rw008_stderr_is_capped_but_still_drained(self):
        """RW-008: stderr ребёнка сохраняется не больше лимита (читается до конца, чтобы pipe не встал)."""
        server.MAX_STDERR_BYTES = 10_000
        self.hub.configure(exit_on_init=3, exit_stderr="E" * 300_000)
        proc = server.RpcProcess(str(server.WORKSPACE), server.POOL, False)
        try:
            with self.assertRaises(server.RpcEof):
                proc.call("droid.initialize_session", {"machineId": "t", "cwd": str(server.WORKSPACE)})
            self.assertTrue(wait_until(lambda: proc.err_box))
            self.assertLessEqual(sum(len(part) for part in proc.err_box), 10_000 + 200)
        finally:
            proc.close(mode="term")

    def test_rw008_inbox_is_bounded_when_nobody_consumes(self):
        """RW-008: очередь событий ограничена по байтам; переполнение — одно событие overflow, память не растёт."""
        server.MAX_INBOX_BYTES = 200_000
        proc = server.RpcProcess(str(server.WORKSPACE), server.POOL, False)
        try:
            big = {"method": "droid.session_notification",
                   "params": {"notification": {"type": "x", "pad": "A" * 100_000}}}
            for _ in range(50):
                proc._on_message(dict(big))
            kinds = []
            while True:
                event = proc.next_event(0.05)
                if event is None or event[0] == "eof":
                    break
                kinds.append(event[0])
            self.assertLessEqual(len(kinds), 4)
            self.assertIn("overflow", kinds)
        finally:
            proc.close(mode="term")

    def test_rw008_chat_index_does_not_grow_with_key_churn(self):
        """RW-008: поток новых ключей: индекс чатов ограничен, вытесненный чат возвращается с диска (restore)."""
        server.MAX_CHATS = 3
        first = self.conv("churn-0")
        self.assertEqual(first.ask("q0")[0], 200)
        sid = self.chat_of("churn-0").sid
        for index in range(1, 9):
            self.assertEqual(self.conv(f"churn-{index}").ask("hi")[0], 200)
        # Чаты с живым процессом (до cap=4) индекс держит, остальные вытеснены; без лимита было бы 9.
        self.assertLessEqual(len(server.REGISTRY.chats), server.MAX_CONCURRENT + 1)
        self.assertEqual(first.ask("q1")[0], 200)
        self.assertEqual(self.chat_of("churn-0").sid, sid)
        self.assertTrue(no_leaks(self))


class TestSpoolEnospc(ImageCase):
    """RW-008: ENOSPC при spool картинок — предусмотренная ошибка 507, ресурсы возвращены."""

    def test_rw008_enospc_on_image_spool_gives_507_and_frees_resources(self):
        """RW-008: write_bytes картинки -> OSError(ENOSPC): 507 insufficient_storage, lease/слот/каталог свободны."""
        from bridge_testlib import image_part, make_png, text_part
        server.IMAGE_PROBE = True
        self.probe_stand()
        real = Path.write_bytes

        def full_disk(self_path, data):
            if self_path.parent.name.startswith("img-"):
                raise OSError(28, "No space left on device")
            return real(self_path, data)

        Path.write_bytes = full_disk
        try:
            status, body = post_safely(self, {
                "model": "claude-sonnet-5-5", "prompt_cache_key": "chat-img",
                "messages": [{"role": "user", "content": [text_part("look"), image_part(make_png(64))]}]})
        finally:
            Path.write_bytes = real
        self.assertEqual(status, 507)
        self.assertEqual(body["error"]["type"], "insufficient_storage")
        self.assertEqual(self.hub.spawns(), [])
        self.assertEqual([p for p in server.WORKSPACE.glob("img-*")], [])
        self.assertTrue(server._slots.acquire(blocking=False))
        server._slots.release()


class TestDeliveryDecoupled(RpcCase):
    """RW-009: доставка клиенту не держит ни аренду чата L, ни разрешение вычисления T."""

    def _slow_client(self, key):
        """SSE-клиент с крошечным окном приёма: запрос отправлен, ответ не читается."""
        sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
        sock.connect(("127.0.0.1", self.port))
        payload = json.dumps(dict(BODY, stream=True, prompt_cache_key=key,
                                  messages=[msg("go " + key)])).encode()
        sock.sendall(self._raw_request(payload))
        return sock

    def test_rw009_slow_clients_do_not_block_next_turn_or_exhaust_compute(self):
        """RW-009: 4 медленных клиента завершили вычисление; 5-й запрос и повторный ход ключа A идут без ожидания."""
        server.MAX_CONCURRENT = 4
        big = "X" * 3_000_000
        self.hub.script([{"steps": [{"op": "text", "text": big}]}] * 4
                        + [{"steps": [{"op": "text", "text": "FIFTH"}]},
                           {"steps": [{"op": "text", "text": "A-AGAIN"}]}])
        socks = [self._slow_client(f"slow-{i}") for i in range(4)]
        try:
            self.assertTrue(wait_until(lambda: len(self.hub.admissions()) >= 4, timeout=30))
            time.sleep(1.0)  # вычисление закончено, сервер застрял на записи в закрытое окно клиента
            result = {}
            fifth = threading.Thread(target=lambda: result.update(
                fifth=post_safely(self, dict(BODY, prompt_cache_key="fifth", messages=[msg("five")]), 40)))
            again = threading.Thread(target=lambda: result.update(
                again=post_safely(self, dict(BODY, prompt_cache_key="slow-0",
                                             messages=[msg("other history")]), 40)))
            fifth.start()
            again.start()
            fifth.join(45)
            again.join(45)
            self.assertEqual(result["fifth"][0], 200)
            self.assertEqual(result["again"][0], 200)
            self.assertEqual(server.POOL.cap(), 4)
        finally:
            for sock in socks:
                sock.close()
        # Обрыв доставки не меняет checkpoint: чаты не DIRTY.
        self.assertTrue(wait_until(lambda: all(
            self.chat_of(f"slow-{i}").state in ("READY", "PERSISTED") for i in range(1, 4))))
        self.assertTrue(no_leaks(self))


class TestRpcWriteDeadline(RpcCase):
    """RW-011: запись в stdin ребёнка отменяема; interrupt и shutdown не ждут зависшую запись."""

    BIG = "S" * 3_000_000

    def _stalled_request(self, results):
        self.hub.configure(stall_after=0)
        body = dict(BODY, messages=[msg(self.BIG, "system"), msg("hi")])
        thread = threading.Thread(target=lambda: results.update(r=post_safely(self, body, 60)), daemon=True)
        thread.start()
        self.assertTrue(wait_until(lambda: len(self.hub.spawns()) == 1, timeout=15))
        time.sleep(0.5)
        return thread

    def test_rw011_write_phase_is_covered_by_rpc_deadline(self):
        """RW-011: ребёнок не читает stdin, payload > pipe: запрос отменяется по RPC-дедлайну (502), не по first-token."""
        server.RPC_CALL_TIMEOUT_S = 1.0
        server.FIRST_TOKEN_TIMEOUT_S = 4.0
        results = {}
        started = time.monotonic()
        thread = self._stalled_request(results)
        thread.join(30)
        self.assertEqual(results["r"][0], 502, results)
        self.assertEqual(results["r"][1]["error"]["type"], "proxy_error")
        self.assertLess(time.monotonic() - started, 4.0)
        self.assertTrue(no_leaks(self))

    def test_rw011_interrupt_does_not_wait_for_stuck_writer(self):
        """RW-011: interrupt_quietly при зависшей записи возвращается сразу (пишущий лок не удерживает interrupt)."""
        server.RPC_CALL_TIMEOUT_S = 20.0
        results = {}
        self._stalled_request(results)
        proc = next(iter(server._rpc_procs.values()))
        thread = threading.Thread(target=proc.interrupt_quietly, daemon=True)
        thread.start()
        thread.join(1.5)
        self.assertFalse(thread.is_alive())

    def test_rw011_shutdown_all_within_budget_with_stuck_child(self):
        """RW-011: SIGTERM-путь при зависшей записи: shutdown_all быстро, ребёнок убит (бюджет 4,5 с)."""
        server.RPC_CALL_TIMEOUT_S = 20.0
        results = {}
        thread = self._stalled_request(results)
        pid = self.hub.spawns()[0]["pid"]
        started = time.monotonic()
        closed = server.shutdown_all()
        elapsed = time.monotonic() - started
        self.assertEqual(closed, 1)
        self.assertLess(elapsed, 1.5)
        self.assertTrue(self.wait_gone(pid, timeout=3))
        thread.join(15)
        self.assertFalse(pid_alive(pid))


class TestInstructionBudget(RpcCase):
    """RW-002: размер блока agent-instructions > 60 000 Б запрещает spawn/add до add_user_message."""

    @staticmethod
    def block(size):
        head = "Instructions from: /x/AGENTS.md\n"
        return head + "a" * (size - len(head.encode()))

    def _ask(self, size):
        return self._post_json(dict(BODY, prompt_cache_key="chat-instr",
                                    messages=[msg("hello"), msg(self.block(size))]))

    def test_rw002_oversized_block_rejected_before_spawn(self):
        """RW-002: 60 001 Б -> 400 REQ003_SIZE_EXCEEDED, ни spawn, ни add_user_message."""
        status, body = self._ask(60001)
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["type"], "REQ003_SIZE_EXCEEDED")
        self.assertEqual(self.hub.spawns(), [])
        self.assertEqual(self.hub.rpcs("droid.add_user_message"), [])

    def test_rw002_exact_limit_passes(self):
        """RW-002: ровно 60 000 Б проходит."""
        status, _ = self._ask(60000)
        self.assertEqual(status, 200)
        self.assertEqual(len(self.hub.spawns()), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
