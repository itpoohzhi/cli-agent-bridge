"""Регрессионные тесты cycle-3 rework (RW-001…RW-015): каждый красный на коде 28fe8db.

Все сценарии идут через настоящий HTTP-сервер моста и fake-subprocess (tests/fake_droid.py),
говорящий stream-jsonrpc в форме реального droid (turnId только у terminal и равен id user-сообщения,
parentId у ассистентских сообщений, factoryProtocolVersion в кадрах). Реальный droid, сеть и боевые
профили владельца не используются. Идентификаторы RW-NNN — в имени метода и docstring.
"""

import hashlib
import json
import os
import stat
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import server  # noqa: E402
from bridge_testlib import make_receipt, pid_alive, wait_until  # noqa: E402
from rpc_testlib import FakeClock, RpcCase  # noqa: E402
from test_images_strict import ImageCase  # noqa: E402
from test_rpc_rework import BODY, msg, no_leaks, post_safely  # noqa: E402

HEAD = "Instructions from: /x/AGENTS.md\n"


def _ask(case, key, *texts, **extra):
    return post_safely(case, dict(BODY, prompt_cache_key=key, messages=[msg(t) for t in texts], **extra))


# -- RW-001/002/003: гейт блока инструкций и автоматический контур b_guard ----------------------------------

class GuardCase(RpcCase):
    """Профили/канон/cwd во временном каталоге; реальные ~/.dsh и Google Drive не читаются."""

    def setUp(self):
        super().setUp()
        import b_guard
        from test_b_guard import build_snapshot_fs
        self.bg = b_guard
        self.root = Path(self._tmp.name) / "guard"
        self.root.mkdir()
        self.fs = build_snapshot_fs(self.root)
        cwds = self.fs["cwds"]
        default = tuple((label, str(cwds[label])) for label in ("KB", "WA", "AB", "DW"))
        user_global = self.root / "user-global-AGENTS.md"
        user_global.symlink_to(self.fs["canon"])  # как на стенде владельца: ~/.dsh/AGENTS.md -> канон
        for patcher in (mock.patch.object(b_guard, "KB_CWD", str(cwds["KB"])),
                        mock.patch.object(b_guard, "UG_PATH", str(user_global)),
                        mock.patch.object(b_guard, "DEFAULT_CWDS", default)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.profiles = self.root / "profiles"
        server.GUARD_PROFILES_DIR = str(self.profiles)
        server.GUARD_CANON = str(self.fs["canon"])
        server._canon_cache.update(key=None, digest="")

    def write_profile(self, maxbytes, name="web"):
        from test_b_guard import PROFILE_YML
        target = self.profiles / name
        target.mkdir(parents=True, exist_ok=True)
        (target / "cordis.patch.yml").write_text(PROFILE_YML % maxbytes, encoding="utf-8")

    def block_ask(self, key, body="инструкции"):
        return _ask(self, key, "hello", HEAD + body)


class TestGuardLoop(GuardCase):
    """RW-003: контур b_guard внутри моста видит CANON_LOST / DUPLICATE_RETURNED / дрейф maxBytes без CLI."""

    def test_rw003_safe_profile_is_ok(self):
        """RW-003: профиль maxBytes=106496 и канон на месте -> состояние ok."""
        self.write_profile(106496)
        self.assertEqual(server.GUARD.check_once(), "ok")

    def test_rw003_duplicate_returned_is_unsafe_with_alert(self):
        """RW-003: maxBytes=262144 возвращает канон дважды -> unsafe, alert DUPLICATE_RETURNED в журнале."""
        self.write_profile(262144)
        with self.capture_logs() as lines:
            self.assertEqual(server.GUARD.check_once(), "unsafe")
            server.GUARD.check_once()  # то же состояние: alert не повторяется
        alerts = [ln for ln in lines if ln.startswith("instr_guard_alert ")]
        self.assertEqual(len(alerts), 1, lines)
        self.assertIn("DUPLICATE_RETURNED", alerts[0])

    def test_rw003_canon_lost_is_unsafe(self):
        """RW-003: канон исчез -> CANON_LOST, unsafe."""
        self.write_profile(106496)
        self.fs["canon"].unlink()
        with self.capture_logs() as lines:
            self.assertEqual(server.GUARD.check_once(), "unsafe")
        self.assertTrue(any("CANON_LOST" in ln for ln in lines if ln.startswith("instr_guard_alert ")))

    def test_rw003_maxbytes_drift_detected_by_background_loop_without_cli(self):
        """RW-003: профиль изменён уже после старта -> фоновый поток находит дрейф и пишет alert сам."""
        self.write_profile(106496)
        server.GUARD_TICK_S = 0.1
        self.addCleanup(setattr, server, "GUARD_TICK_S", 30)
        with self.capture_logs() as lines:
            server.GUARD.check_once()
            self.assertEqual(server.GUARD.snapshot()[0], "ok")
            server.GUARD.start()
            self.write_profile(262144)
            self.assertTrue(wait_until(lambda: server.GUARD.snapshot()[0] == "unsafe", timeout=5))
        self.assertTrue(any(ln.startswith("instr_guard_alert ") for ln in lines))

    def test_rw003_unreadable_maxbytes_is_unsafe(self):
        """RW-003: профиль без читаемого maxBytes -> unsafe (fail-closed), а не молчаливый ok."""
        self.write_profile(106496)
        (self.profiles / "web" / "cordis.patch.yml").write_text("[]\n", encoding="utf-8")
        self.assertEqual(server.GUARD.check_once(), "unsafe")


class TestGuardGate(GuardCase):
    """RW-001: небезопасный профиль не даёт немого 400 живому трафику; новые чаты — управляемый отказ."""

    def test_rw001_unsafe_guard_refuses_new_chat_with_block_before_spawn(self):
        """RW-001: unsafe + новый чат с блоком -> 503 launcher_unavailable до spawn/add, в журнале gate-alert."""
        self.write_profile(262144)
        server.GUARD.check_once()
        with self.capture_logs() as lines:
            status, body = self.block_ask("chat-new")
        self.assertEqual(status, 503, body)
        self.assertEqual(body["error"]["type"], "launcher_unavailable")
        self.assertIn("guard", body["error"]["message"])
        self.assertEqual(self.hub.spawns(), [])
        self.assertEqual(self.hub.rpcs("droid.add_user_message"), [])
        self.assertTrue(any(ln.startswith("instr_gate_alert ") for ln in lines))

    def test_rw001_unsafe_guard_does_not_stop_live_chat_or_requests_without_block(self):
        """RW-001: живой чат и запросы без блока продолжают работать при unsafe (трафик владельца не встаёт)."""
        self.write_profile(106496)
        server.GUARD.check_once()
        self.assertEqual(self.block_ask("chat-live")[0], 200)
        self.write_profile(262144)
        server.GUARD.check_once()
        self.assertEqual(server.GUARD.snapshot()[0], "unsafe")
        status, _ = post_safely(self, dict(BODY, prompt_cache_key="chat-live", messages=[
            msg("hello"), msg(HEAD + "инструкции"), msg("PONG", "assistant"), msg("second")]))
        self.assertEqual(status, 200)
        self.assertEqual(_ask(self, "chat-plain", "no block")[0], 200)

    def test_rw001_safe_guard_passes_non_kb_blocks_larger_than_60000(self):
        """RW-001: при ok блок WA/AB (79 515/93 760 Б, не канон) < maxBytes−запас проходит, а не 400."""
        self.write_profile(106496)
        server.GUARD.check_once()
        for index, size in enumerate((79515, 93760)):
            status, body = self.block_ask(f"chat-wa-{index}", "a" * (size - len(HEAD)))
            self.assertEqual(status, 200, body)

    def test_rw001_canon_only_block_over_60000_is_refused(self):
        """RW-001: форма «только канон» (KB/DW) сверх 60 000 Б — 503 до spawn/add даже при ok-профиле."""
        self.write_profile(106496)
        server.GUARD.check_once()
        canon_text = self.fs["canon"].read_text(encoding="utf-8")
        status, body = _ask(self, "chat-kb", "hello", HEAD + canon_text + "\n" + HEAD + canon_text)
        self.assertEqual(status, 503, body)
        self.assertEqual(body["error"]["type"], "launcher_unavailable")
        self.assertEqual(self.hub.spawns(), [])


class TestInstructionScan(RpcCase):
    """RW-002: гейт проверяет все блоки во всём тексте сообщений."""

    def canon_block(self, size):
        body = "k" * (size - len(HEAD.encode()))
        Path(server.GUARD_CANON).write_text(body + "\n", encoding="utf-8")
        server._canon_cache.update(key=None, digest="")
        return HEAD + body

    def test_rw002_scan_returns_all_blocks_and_largest(self):
        """RW-002: два блока: _instr_blocks видит оба, _instr_scan возвращает крупнейший (не первый)."""
        small = HEAD + "a" * 100
        big = self.canon_block(60001)
        messages = [msg(small), msg("x"), msg(big)]
        self.assertEqual(len(server._instr_blocks(messages)), 2)
        self.assertEqual(server._instr_scan(messages)[2], 60001)

    def test_rw002_marker_after_4096_chars_is_detected(self):
        """RW-002: маркер дальше 4096 символов от начала сообщения находится."""
        text = "p" * 6000 + "\n" + HEAD + "body"
        self.assertEqual(len(server._instr_blocks([msg(text)])), 1)

    def test_rw002_oversized_second_block_refused_before_spawn(self):
        """RW-002: малый первый блок + второй 60 001 Б (канон) -> 503 до spawn/add."""
        big = self.canon_block(60001)
        status, body = _ask(self, "chat-two", "hello", HEAD + "tiny", big)
        self.assertEqual(status, 503, body)
        self.assertEqual(self.hub.spawns(), [])
        self.assertEqual(self.hub.rpcs("droid.add_user_message"), [])


# -- RW-004: ENOSPC на spool картинок -> 502 для JSON и SSE -------------------------------------------------

class TestSpoolEnospcBothModes(ImageCase):
    def _enospc(self, stream):
        from bridge_testlib import image_part, make_png, text_part
        server.IMAGE_PROBE = True
        self.probe_stand()
        real = Path.write_bytes

        def full_disk(self_path, data):
            if self_path.parent.name.startswith("img-"):
                raise OSError(28, "No space left on device")
            return real(self_path, data)

        body = {"model": "claude-sonnet-5-5", "prompt_cache_key": "chat-img", "stream": stream,
                "messages": [{"role": "user", "content": [text_part("look"), image_part(make_png(64))]}]}
        Path.write_bytes = full_disk
        try:
            if stream:
                return self._post(body)
            return post_safely(self, body)
        finally:
            Path.write_bytes = real

    def test_rw004_enospc_json_gives_502_proxy_error(self):
        """RW-004: ENOSPC (JSON) -> 502 proxy_error; каталог spool и слот свободны."""
        status, body = self._enospc(False)
        self.assertEqual(status, 502)
        self.assertEqual(body["error"]["type"], "proxy_error")
        self.assertEqual(list(server.WORKSPACE.glob("img-*")), [])
        self.assertTrue(server._slots.acquire(blocking=False))
        server._slots.release()

    def test_rw004_enospc_sse_gives_502_not_507(self):
        """RW-004: ENOSPC (SSE) -> кадр ошибки proxy_error/502 (как у прочих отказов потока), без 507/insufficient_storage."""
        status, text = self._enospc(True)
        self.assertEqual(status, 200)  # заголовки SSE уже отправлены: ошибка идёт кадром потока
        self.assertIn('"type": "proxy_error"', text)
        self.assertIn('"code": 502', text)
        self.assertNotIn("insufficient_storage", text)

    def test_rw004_no_507_anywhere_in_sources(self):
        """RW-004: в server.py и tests нет кода 507 и insufficient_storage (кроме этого теста)."""
        import re
        root = Path(__file__).resolve().parent.parent
        pattern = re.compile(r"\b507\b|insufficient_storage")
        hits = []
        for path in [root / "server.py"] + sorted((root / "tests").glob("*.py")):
            if path.name == "test_rpc_cycle3.py":
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if pattern.search(line):
                    hits.append(f"{path.name}:{number}")
        self.assertEqual(hits, [])


# -- RW-005: ошибки записи состояния чата -------------------------------------------------------------------

class TestPersistFailures(RpcCase):
    @staticmethod
    def _failing(match):
        real = server._atomic_write

        def failing(path, data):
            try:
                state = json.loads(data).get("state")
            except (ValueError, AttributeError):
                state = None
            if state == match:
                raise OSError(28, "No space left on device")
            return real(path, data)

        return real, failing

    def test_rw005_pending_write_failure_blocks_turn_before_add_user_message(self):
        """RW-005: ENOSPC на PENDING -> 502 proxy_error, add_user_message не вызван, чат DIRTY."""
        chat = self.conv("chat-pend")
        self.assertEqual(chat.ask("q0")[0], 200)
        adds = len(self.hub.rpcs("droid.add_user_message"))
        real, failing = self._failing("PENDING")
        server._atomic_write = failing
        try:
            status, body = chat.ask("q1")
        finally:
            server._atomic_write = real
        self.assertEqual(status, 502)
        self.assertEqual(body["error"]["type"], "proxy_error")
        self.assertEqual(len(self.hub.rpcs("droid.add_user_message")), adds)
        self.assertEqual(self.chat_of("chat-pend").state, "DIRTY")
        self.assertTrue(no_leaks(self))

    def test_rw005_commit_failure_is_not_success_and_next_turn_replays_new_sid(self):
        """RW-005: ENOSPC на commit READY -> нет 200, чат DIRTY; после рестарта и следующий ход — новая generation."""
        chat = self.conv("chat-commit")
        self.assertEqual(chat.ask("q0")[0], 200)
        old_sid = self.chat_of("chat-commit").sid
        real, failing = self._failing("READY")
        server._atomic_write = failing
        try:
            status, body = chat.ask("q1")
        finally:
            server._atomic_write = real
        self.assertEqual(status, 502)
        self.assertEqual(body["error"]["type"], "proxy_error")
        self.assertEqual(self.chat_of("chat-commit").state, "DIRTY")
        self.assertIsNone(self.chat_of("chat-commit").proc)
        self.assertTrue(no_leaks(self))
        # «Рестарт» моста: на диске PENDING — старый SID не продолжается.
        server._reset_rpc_state()
        chat.msgs.pop()
        inits = len(self.hub.inits())
        loads = len(self.hub.rpcs("droid.load_session"))
        self.assertEqual(chat.ask("q1")[0], 200)
        self.assertEqual(len(self.hub.inits()), inits + 1)
        self.assertEqual(len(self.hub.rpcs("droid.load_session")), loads)
        self.assertNotEqual(self.chat_of("chat-commit").sid, old_sid)

    def test_rw005_commit_failure_frees_all_slots(self):
        """RW-005: после сбоя commit свободны L (аренда чата), P (слот процесса) и T (вычисление)."""
        chat = self.conv("chat-slots")
        self.assertEqual(chat.ask("q0")[0], 200)
        real, failing = self._failing("READY")
        server._atomic_write = failing
        try:
            self.assertEqual(chat.ask("q1")[0], 502)
        finally:
            server._atomic_write = real
        state = self.chat_of("chat-slots")
        self.assertTrue(wait_until(lambda: not state.lock.locked()))
        self.assertTrue(no_leaks(self))
        self.assertTrue(server._slots.acquire(blocking=False))
        server._slots.release()


# -- RW-006: терминалы/сообщения чужих и неизвестных ходов -------------------------------------------------

class TestTurnIsolation(RpcCase):
    def _two_turns(self, second_steps, key="chat-iso"):
        self.hub.script([{"steps": [{"op": "text", "text": "A0"}]},
                         {"steps": second_steps, "usage": {"inputTokens": 21, "outputTokens": 2}}])
        chat = self.conv(key)
        self.assertEqual(chat.ask("q0")[0], 200)
        return chat.ask("q1")

    def test_rw006_unknown_turn_id_terminal_does_not_finish_turn(self):
        """RW-006: terminal с неизвестным turnId игнорируется: ответ и usage — собственные."""
        status, body = self._two_turns([{"op": "unknown_terminal"}, {"op": "sleep", "s": 0.3},
                                        {"op": "text", "text": "A1"}])
        self.assertEqual(status, 200)
        self.assertEqual(body["choices"][0]["message"]["content"], "A1")
        self.assertEqual(body["usage"]["prompt_tokens"], 21)

    def test_rw006_empty_turn_id_terminal_does_not_finish_turn(self):
        """RW-006: terminal без turnId (пустой) ход не завершает."""
        status, body = self._two_turns([{"op": "empty_terminal"}, {"op": "sleep", "s": 0.3},
                                        {"op": "text", "text": "A1"}])
        self.assertEqual(status, 200)
        self.assertEqual(body["choices"][0]["message"]["content"], "A1")
        self.assertEqual(body["usage"]["prompt_tokens"], 21)

    def test_rw006_stale_message_and_delta_of_previous_turn_are_dropped(self):
        """RW-006: сообщение и дельта прежнего хода (его mid/parentId) не попадают в ответ нового."""
        status, body = self._two_turns([{"op": "stale_message", "text": "STALE-MSG"},
                                        {"op": "stale_delta", "text": "STALE-DELTA"},
                                        {"op": "text", "text": "A1"}])
        self.assertEqual(status, 200)
        self.assertEqual(body["choices"][0]["message"]["content"], "A1")

    def test_rw006_foreign_events_do_not_reset_silence_watchdog(self):
        """RW-006: поток чужих событий не продлевает watchdog тишины: ход, не дающий своего прогресса, -> 504."""
        server.SILENCE_WATCHDOG_S = 0.8
        steps = []
        for _ in range(8):
            steps += [{"op": "sleep", "s": 0.25}, {"op": "stale_message", "text": "STALE"}]
        steps.append({"op": "hang"})
        started = time.monotonic()
        status, body = self._two_turns(steps)
        self.assertEqual(status, 504, body)
        self.assertEqual(body["error"]["type"], "timeout")
        self.assertLess(time.monotonic() - started, 6.0)

    def test_rw006_exhausted_finished_turn_set_replaces_process_at_turn_boundary(self):
        """RW-006: предел FINISHED_TURNS_KEEP исчерпан -> процесс заменяется (новый init), ответы корректны."""
        server.FINISHED_TURNS_KEEP = 1
        chat = self.conv("chat-evict")
        for index in range(4):
            status, body = chat.ask(f"q{index}")
            self.assertEqual(status, 200, body)
            self.assertEqual(body["choices"][0]["message"]["content"], "PONG")
        self.assertGreaterEqual(len(self.hub.inits()), 2)
        self.assertTrue(no_leaks(self))


# -- RW-007/008: байтовые бюджеты и доставка кусками --------------------------------------------------------

class TestBudgetsCycle3(RpcCase):
    def test_rw007_default_limits_are_8_4_10_mib(self):
        """RW-007: значения по умолчанию: строка RPC 8 МиБ, inbox 4 МиБ, текст хода 10 МиБ."""
        self.assertEqual(server.MAX_RPC_LINE_BYTES, 8 << 20)
        self.assertEqual(server.MAX_INBOX_BYTES, 4 << 20)
        self.assertEqual(server.MAX_TURN_TEXT_BYTES, 10 << 20)

    def test_rw007_tiny_notification_flood_is_bounded_by_entry_overhead(self):
        """RW-007: много крошечных нотификаций без потребителя не обходят бюджет inbox (учёт служебных байт)."""
        server.MAX_INBOX_BYTES = 100_000
        proc = server.RpcProcess(str(server.WORKSPACE), server.POOL, False)
        try:
            tiny = {"method": "droid.session_notification", "params": {"notification": {"type": "x"}}}
            for _ in range(20_000):
                proc._on_message(dict(tiny))
            kinds = []
            while True:
                event = proc.next_event(0.02)
                if event is None or event[0] == "eof":
                    break
                kinds.append(event[0])
            self.assertIn("overflow", kinds)
            self.assertLessEqual(len(kinds), 100_000 // 32 + 4)
        finally:
            proc.close(mode="term")

    def test_rw007_empty_message_flood_is_charged_against_turn_budget(self):
        """RW-007: поток пустых сообщений ассистента не копится бесплатно: бюджет хода -> 502 limit."""
        server.MAX_TURN_TEXT_BYTES = 20_000
        self.hub.script([{"steps": [{"op": "empty_msgs", "count": 3000}, {"op": "text", "text": "tail"}]}])
        status, body = post_safely(self, dict(BODY, messages=[msg("hi")]))
        self.assertEqual(status, 502, body)
        self.assertIn("limit", json.dumps(body))
        self.assertTrue(no_leaks(self))

    def test_rw008_delta_plus_complete_is_charged_once(self):
        """RW-008: delta + complete(text) одного блока стоит N байт, а не 2N: ход на 0,6 лимита проходит."""
        n = 100_000
        server.MAX_TURN_TEXT_BYTES = int(n * 1.5)
        self.hub.script([{"steps": [{"op": "text", "text": "x" * n, "complete_with_text": True}]}])
        status, body = post_safely(self, dict(BODY, messages=[msg("hi")]))
        self.assertEqual(status, 200, body)
        self.assertEqual(len(body["choices"][0]["message"]["content"]), n)

    def test_rw007_large_response_is_delivered_in_slices_json_and_sse(self):
        """RW-007: большой ответ уходит срезами (экранирование по кускам), содержимое и Content-Length целы."""
        server.DELIVERY_CHUNK_BYTES = 4096
        text = ("Привет \"мир\"\n" * 40_000)
        sizes = []
        real = getattr(server, "_escape_json_piece", None)

        def spy(piece):
            sizes.append(len(piece))
            return real(piece)

        server._escape_json_piece = spy
        self.addCleanup(lambda: setattr(server, "_escape_json_piece", real) if real else delattr(
            server, "_escape_json_piece"))
        self.hub.script([{"steps": [{"op": "text", "text": text}]}] * 2)
        status, body = post_safely(self, dict(BODY, messages=[msg("hi")]))
        self.assertEqual(status, 200)
        self.assertEqual(body["choices"][0]["message"]["content"], text)
        self.assertGreater(len(sizes), 50)
        self.assertLessEqual(max(sizes), 4096 // 4)
        status, stream = self._post(dict(BODY, stream=True, messages=[msg("hi")]))
        self.assertEqual(status, 200)
        pieces = [json.loads(line[6:]) for line in stream.splitlines()
                  if line.startswith("data: {")]
        joined = "".join(p["choices"][0]["delta"].get("content", "") for p in pieces if p.get("choices"))
        self.assertEqual(joined, text)
        self.assertGreater(len([p for p in pieces if p.get("choices")
                                and p["choices"][0]["delta"].get("content")]), 5)


# -- RW-009: receipt как набор компонентов ------------------------------------------------------------------

class TestReceiptComponents(RpcCase):
    def setUp(self):
        super().setUp()
        server.RECEIPT_REQUIRED = True

    def install(self, **override):
        content = b"qualified-image"
        digest = hashlib.sha256(content).hexdigest()
        image_dir = server.WORKSPACE / "runtime" / "droid-image" / digest
        image_dir.mkdir(parents=True, exist_ok=True)
        image = image_dir / "droid"
        if not image.exists():
            image.write_bytes(content)
            image.chmod(0o500)
        server._atomic_write(server._receipt_path(), json.dumps(
            make_receipt(image, digest, **override)).encode())

    def ask(self):
        return post_safely(self, dict(BODY, messages=[msg("hi")]))

    def test_rw009_valid_receipt_is_accepted(self):
        """RW-009: контрольный случай — полный receipt schema 2 принимается."""
        self.install()
        self.assertEqual(self.ask()[0], 200)

    def _refused_at_spawn(self, **override):
        self.install(**override)
        status, body = self.ask()
        self.assertEqual(status, 503, body)
        self.assertEqual(body["error"]["type"], "launcher_unavailable")
        self.assertEqual(self.hub.spawns(), [])

    def test_rw009_old_schema_is_refused(self):
        """RW-009: receipt без schema 2 (только image_path/sha) отвергается."""
        self._refused_at_spawn(schema=1)

    def test_rw009_each_missing_component_is_refused(self):
        """RW-009: нет protocol / tools_policy / settings_profile / probes -> spawn запрещён."""
        for name in ("protocol", "tools_policy", "settings_profile", "probes"):
            with self.subTest(name):
                self.hub.config.clear()
                self._refused_at_spawn(**{name: None})

    def test_rw009_tools_policy_digest_mismatch_is_refused(self):
        """RW-009: digest tools_policy не соответствует набору id -> spawn запрещён."""
        ids = ["Read"]
        self._refused_at_spawn(tools_policy={"policy": server.TOOLS_POLICY, "disabled_tool_ids": ids,
                                             "digest": "0" * 64})

    def test_rw009_settings_profile_drift_is_refused(self):
        """RW-009: профиль безопасных настроек в receipt отличается от кода моста -> spawn запрещён."""
        profile = dict(server.SETTINGS_PROFILE)
        profile["autonomyLevel"] = "off"
        self._refused_at_spawn(settings_profile={"profile": profile, "digest": server.settings_profile_digest()})

    def test_rw009_failed_probe_is_refused(self):
        """RW-009: любая проба не ok -> receipt не считается квалификацией."""
        probes = {name: "ok" for name in server.RECEIPT_PROBES}
        probes[server.RECEIPT_PROBES[0]] = "fail"
        self._refused_at_spawn(probes=probes)

    def test_rw009_live_protocol_version_mismatch_stops_before_add(self):
        """RW-009: живой droid говорит другой protocolVersion, чем в receipt -> 502, add_user_message нет."""
        import fake_droid
        self.install(protocol={"api_version": server.RPC_API_VERSION, "protocol_version": "9.9.9"})
        self.assertNotEqual(fake_droid.PROTOCOL, "9.9.9")
        status, body = self.ask()
        self.assertEqual(status, 502, body)
        self.assertEqual(self.hub.rpcs("droid.add_user_message"), [])
        self.assertTrue(no_leaks(self))

    def test_rw009_live_tools_catalogue_drift_stops_before_add(self):
        """RW-009: каталог tools живого droid шире квалифицированного -> 502, add_user_message нет."""
        self.install()
        self.hub.configure(tools=["Read", "Execute", "Edit", "web_search", "BrandNewTool"])
        status, body = self.ask()
        self.assertEqual(status, 502, body)
        self.assertEqual(self.hub.rpcs("droid.add_user_message"), [])
        self.assertTrue(no_leaks(self))


class TestDroidImageProbes(RpcCase):
    """RW-009: tools/droid_image.py пишет receipt только после реальных проб и не оставляет его при провале."""

    def setUp(self):
        super().setUp()
        import droid_image
        self.tool = droid_image
        self.source = Path(self._tmp.name) / "global-droid"
        self.source.write_bytes(self.hub.launcher.read_bytes())
        self.source.chmod(0o755)

    def test_rw009_receipt_schema2_contains_all_probed_components(self):
        """RW-009: receipt после проб содержит protocol/tools_policy/settings_profile/probes."""
        receipt = self.tool.install_image(self.source, server.WORKSPACE)
        self.assertEqual(receipt["schema"], server.RECEIPT_SCHEMA)
        self.assertTrue(receipt["protocol"]["protocol_version"])
        self.assertEqual(receipt["settings_profile"]["digest"], server.settings_profile_digest())
        self.assertEqual(sorted(receipt["tools_policy"]["disabled_tool_ids"]), sorted(
            __import__("fake_droid").DEFAULT_TOOLS))
        self.assertEqual(set(receipt["probes"]), set(server.RECEIPT_PROBES))
        self.assertTrue(all(v == "ok" for v in receipt["probes"].values()))

    def test_rw009_failed_probe_leaves_no_receipt(self):
        """RW-009: сломанные настройки при пробе -> ProbeError и receipt не записан."""
        self.hub.configure(no_readback=True)
        with self.assertRaises(self.tool.ProbeError):
            self.tool.install_image(self.source, server.WORKSPACE)
        self.assertFalse(server._receipt_path().exists())


# -- RW-010: группа процессов ------------------------------------------------------------------------------

class TestProcessGroup(RpcCase):
    def test_rw010_orphan_holding_pipes_is_killed_with_the_group(self):
        """RW-010: лидер вышел, потомок держит pipe -> закрытие убивает группу, слот возвращается."""
        self.hub.script([{"steps": [{"op": "orphan_child", "seconds": 300}]}] * 3)
        orphans = []
        try:
            status, _ = post_safely(self, dict(BODY, messages=[msg("hi")]), timeout=40)
            orphans = [r["child_pid"] for r in self.hub.records() if r.get("ev") == "orphan"]
            self.assertEqual(status, 502)
            self.assertTrue(orphans)
            for pid in orphans:
                self.assertTrue(self.wait_gone(pid, timeout=10), f"осиротевший потомок {pid} жив")
            self.assertTrue(no_leaks(self))
            self.assertTrue(wait_until(lambda: server.POOL.used == 0))
        finally:
            for pid in orphans:
                try:
                    os.kill(pid, 9)
                except OSError:
                    pass


# -- RW-011: реапер ----------------------------------------------------------------------------------------

class _HookLock:
    """Замок чата: перед захватом исполняет hook (имитация хода, проскочившего между снимком и claim)."""

    def __init__(self, inner, hook):
        self._inner, self._hook = inner, hook

    def acquire(self, *args, **kwargs):
        hook, self._hook = self._hook, lambda: None
        hook()
        return self._inner.acquire(*args, **kwargs)

    def release(self):
        return self._inner.release()

    def locked(self):
        return self._inner.locked()


class TestReaperRace(RpcCase):
    def setUp(self):
        super().setUp()
        self.clock = FakeClock(1000.0)
        server._clock = self.clock

    def _prepare(self, key):
        chat = self.conv(key)
        self.assertEqual(chat.ask("q0")[0], 200)
        state = self.chat_of(key)
        self.clock.advance(2700)
        return chat, state

    def test_rw011_activity_between_snapshot_and_claim_prevents_close(self):
        """RW-011: last_used обновлён после снимка кандидатов -> процесс не закрывается по устаревшему снимку."""
        _, state = self._prepare("chat-race-1")
        pid = state.proc.pid
        now = self.clock.now
        state.lock = _HookLock(state.lock, lambda: setattr(state, "last_used", now))
        self.assertEqual(server.REGISTRY.reap_once(), [])
        self.assertTrue(state.proc is not None and state.proc.alive())
        self.assertTrue(pid_alive(pid))

    def test_rw011_busy_between_snapshot_and_claim_prevents_close(self):
        """RW-011: процесс стал busy после снимка -> реапер его не закрывает."""
        _, state = self._prepare("chat-race-2")
        proc = state.proc
        state.lock = _HookLock(state.lock, lambda: setattr(proc, "busy", True))
        self.assertEqual(server.REGISTRY.reap_once(), [])
        self.assertTrue(proc.alive())

    def test_rw011_replaced_process_is_not_closed_by_stale_snapshot(self):
        """RW-011: за время снимка в чате новый процесс -> закрывается не он (идентичность проверяется заново)."""
        chat, state = self._prepare("chat-race-3")
        old = state.proc
        fresh = {}

        def swap():
            fresh["proc"] = server.RpcProcess(str(server.WORKSPACE), server.POOL, False)
            state.proc = fresh["proc"]
            state.last_used = self.clock.now

        state.lock = _HookLock(state.lock, swap)
        try:
            self.assertEqual(server.REGISTRY.reap_once(), [])
            self.assertTrue(fresh["proc"].alive())
        finally:
            fresh["proc"].close(mode="term")
            old.close(mode="term")


# -- RW-012/013: ресурсы при сбоях и эфемерные сессии -----------------------------------------------------

class TestSetupFailures(RpcCase):
    def test_rw012_popen_failure_returns_all_resources(self):
        """RW-012: Popen бросает OSError -> ответ без обрыва, слоты P/T свободны, процессов нет."""
        real = subprocess.Popen

        def failing(*args, **kwargs):
            raise OSError(24, "Too many open files")

        with mock.patch.object(server.subprocess, "Popen", failing):
            status, body = post_safely(self, dict(BODY, messages=[msg("hi")]))
        self.assertEqual(status, 502, body)
        self.assertTrue(no_leaks(self))
        self.assertEqual(server.POOL.used, 0)
        self.assertTrue(server._slots.acquire(blocking=False))
        server._slots.release()
        self.assertIs(subprocess.Popen, real)

    def test_rw012_worker_thread_start_failure_returns_all_resources(self):
        """RW-012: Thread.start воркера хода не удался -> ответ без обрыва, слоты и аренда возвращены."""
        real_start = threading.Thread.start

        def start(thread):
            if getattr(thread._target, "__name__", "") == "_work":
                raise RuntimeError("can't start new thread")
            return real_start(thread)

        with mock.patch.object(threading.Thread, "start", start):
            status, body = post_safely(self, dict(BODY, prompt_cache_key="chat-nothread", messages=[msg("hi")]))
        self.assertEqual(status, 502, body)
        self.assertTrue(no_leaks(self))
        state = server.REGISTRY.chats.get(server._key_hash("chat-nothread"))
        if state is not None:
            self.assertFalse(state.lock.locked())
        self.assertTrue(server._slots.acquire(blocking=False))
        server._slots.release()
        self.assertEqual(post_safely(self, dict(BODY, prompt_cache_key="chat-nothread",
                                                messages=[msg("again")]))[0], 200)

    def test_rw012_reader_thread_start_failure_kills_spawned_child_and_frees_slot(self):
        """RW-012: потоки чтения не стартовали после Popen -> ребёнок убит, реестры и слот P чисты, ответ 502."""
        real_start = threading.Thread.start

        def start(thread):
            if getattr(thread._target, "__name__", "") == "_read":
                raise RuntimeError("can't start new thread")
            return real_start(thread)

        real_popen = subprocess.Popen
        spawned = []

        def tracking(*args, **kwargs):
            proc = real_popen(*args, **kwargs)
            spawned.append(proc.pid)
            return proc

        with mock.patch.object(threading.Thread, "start", start), \
                mock.patch.object(server.subprocess, "Popen", tracking):
            status, body = post_safely(self, dict(BODY, messages=[msg("hi")]))
        self.assertEqual(status, 502, body)
        self.assertGreaterEqual(len(spawned), 1)  # мост может повторить попытку: каждый порождённый ребёнок убит
        for pid in spawned:
            self.assertTrue(self.wait_gone(pid, timeout=5), pid)
        self.assertTrue(no_leaks(self))
        self.assertEqual(server.POOL.used, 0)
        self.assertEqual(server._rpc_procs, {})

    def test_rw012_run_init_failure_returns_resources(self):
        """RW-012: сбой в Run.__init__ (после захвата слотов) не оставляет ни P, ни T, ни аренды."""
        real = server.Run.__init__

        def broken(self_run, plan, proc, holds_slot):
            raise OSError("init failed")

        with mock.patch.object(server.Run, "__init__", broken):
            status, body = post_safely(self, dict(BODY, prompt_cache_key="chat-initfail", messages=[msg("hi")]))
        self.assertEqual(status, 502, body)
        self.assertTrue(no_leaks(self))
        self.assertTrue(server._slots.acquire(blocking=False))
        server._slots.release()
        self.assertIs(server.Run.__init__, real)


class TestEphemeralClose(RpcCase):
    def test_rw013_ephemeral_session_releases_slot_without_graceful_wait(self):
        """RW-013: эфемерная сессия (без ключа) закрывается term, слот возвращается быстро, close_session не ждём."""
        self.hub.configure(close_delay=6.0)
        started = time.monotonic()
        status, _ = post_safely(self, dict(BODY, messages=[msg("hi")]))
        self.assertEqual(status, 200)
        self.assertTrue(wait_until(lambda: server.POOL.used == 0, timeout=3))
        self.assertLess(time.monotonic() - started, 4.0)
        self.assertEqual([e for e in self.hub.exits() if e["reason"] == "close_session"], [])


# -- RW-014: права каталогов -------------------------------------------------------------------------------

class TestPrivateDirs(RpcCase):
    def test_rw014_existing_loose_state_dirs_are_tightened_to_0700(self):
        """RW-014: заранее созданные state/runtime с 0755 внутри workspace ужесточаются, а не принимаются."""
        for rel in ("state", "runtime"):
            path = server.WORKSPACE / rel
            path.mkdir()
            path.chmod(0o755)
        self.assertEqual(self.conv("chat-perm").ask("hi")[0], 200)
        for rel in ("state", "runtime", "runtime/factory-home"):
            mode = stat.S_IMODE((server.WORKSPACE / rel).stat().st_mode)
            self.assertEqual(mode, 0o700, rel)

    def test_rw014_droid_image_tool_tightens_existing_chain(self):
        """RW-014: droid_image.py ужесточает заранее созданную цепочку runtime/droid-image до 0700."""
        import droid_image
        source = Path(self._tmp.name) / "global-droid"
        source.write_bytes(self.hub.launcher.read_bytes())
        source.chmod(0o755)
        for rel in ("runtime", "runtime/droid-image"):
            path = server.WORKSPACE / rel
            path.mkdir(exist_ok=True)
            path.chmod(0o755)
        receipt = droid_image.install_image(source, server.WORKSPACE)
        for rel in ("runtime", "runtime/droid-image"):
            self.assertEqual(stat.S_IMODE((server.WORKSPACE / rel).stat().st_mode), 0o700, rel)
        self.assertEqual(stat.S_IMODE(Path(receipt["image_path"]).parent.stat().st_mode), 0o700)


# -- RW-015: /health отражает допуск образа ----------------------------------------------------------------

class TestHealthReceipt(RpcCase):
    def test_rw015_health_keeps_seven_keys_and_reflects_receipt(self):
        """RW-015: /health сохраняет 7 ключей; при обязательном, но отсутствующем receipt ok=false."""
        self.assertTrue(self.health()["ok"])
        keys = set(self.health())
        server.RECEIPT_REQUIRED = True
        health = self.health()
        self.assertEqual(set(health), keys)
        self.assertEqual(len(health), 7)
        self.assertFalse(health["ok"])

    def test_rw015_receipt_state_values(self):
        """RW-015: _receipt_state: not_required / invalid / ok."""
        self.assertEqual(server._receipt_state(), "not_required")
        server.RECEIPT_REQUIRED = True
        self.assertEqual(server._receipt_state(), "invalid")
        content = b"qualified-image"
        digest = hashlib.sha256(content).hexdigest()
        image_dir = server.WORKSPACE / "runtime" / "droid-image" / digest
        image_dir.mkdir(parents=True)
        image = image_dir / "droid"
        image.write_bytes(content)
        image.chmod(0o500)
        server._atomic_write(server._receipt_path(), json.dumps(make_receipt(image, digest)).encode())
        self.assertEqual(server._receipt_state(), "ok")
        self.assertTrue(self.health()["ok"])


class TestStartup(GuardCase):
    """RW-003/RW-014/RW-015: старт моста — alert по профилю и receipt без трассировок."""

    class _NoServe:
        def __init__(self, *args, **kwargs):
            pass

        def serve_forever(self):
            return None

    def _run_main(self):
        with mock.patch.object(server, "Server", self._NoServe), \
                mock.patch.object(server.signal, "signal"), \
                mock.patch.object(server.GUARD, "start") as started:
            server.main()
        return started

    def test_rw003_start_checks_profiles_and_starts_guard_loop_with_alert(self):
        """RW-003: main() сам проверяет профили (alert в журнал до приёма трафика) и запускает контур."""
        self.write_profile(262144)
        with self.capture_logs() as lines:
            started = self._run_main()
        started.assert_called_once()
        self.assertTrue(any(ln.startswith("instr_guard_alert ") and "DUPLICATE_RETURNED" in ln for ln in lines))

    def test_rw015_start_logs_invalid_receipt_pointing_to_readme(self):
        """RW-015: RECEIPT_REQUIRED без receipt -> старт с понятным alert (ссылка на README), без трассировки."""
        server.RECEIPT_REQUIRED = True
        self.write_profile(106496)
        with self.capture_logs() as lines:
            self._run_main()
        invalid = [ln for ln in lines if ln.startswith("droid_receipt_invalid ")]
        self.assertEqual(len(invalid), 1, lines)
        self.assertIn("README", invalid[0])

    def test_rw014_unusable_workspace_refuses_start_with_message(self):
        """RW-014: WORKSPACE — не каталог (OSError) -> SystemExit(1) с сообщением, а не трассировка."""
        bad = Path(self._tmp.name) / "not-a-dir"
        bad.write_text("x", encoding="utf-8")
        server.WORKSPACE = bad
        with mock.patch.object(server.sys.stderr, "write") as err:
            with self.assertRaises(SystemExit) as caught:
                self._run_main()
        self.assertEqual(caught.exception.code, 1)
        self.assertTrue(any("state directory is not usable" in str(c.args[0]) for c in err.call_args_list))


if __name__ == "__main__":
    unittest.main(verbosity=2)
