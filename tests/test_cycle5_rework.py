"""Регрессионные тесты cycle-5 rework (RW-005, RW-007…RW-014 замечаний Совета по Cycle 4).

Сценарии идут через настоящий HTTP-сервер моста и fake-subprocess (tests/fake_droid.py) либо напрямую через
Run._on_notif. Реальный droid, сеть, ~/.dsh и боевые каталоги владельца не используются.
Идентификаторы RW-NNN - в имени метода и docstring.
"""

import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import b_guard as bg  # noqa: E402
import droid_image  # noqa: E402
import server  # noqa: E402
from bridge_testlib import TOOLS, FakeDroidHub, wait_until  # noqa: E402
from rpc_testlib import RpcCase  # noqa: E402
from test_b_guard import PROFILE_YML  # noqa: E402
from test_rpc_cycle3 import GuardCase  # noqa: E402
from test_rpc_cycle4 import (  # noqa: E402
    HEAD,
    RunCase,
    _inject_start_failure,
    asst_create,
    note,
    terminal,
    user_create,
)
from test_rpc_rework import BODY, msg, no_leaks  # noqa: E402


# -- RW-005: droid_image закрывает stdout дочернего процесса --------------------------------------------------


class TestRw005ImageRpcClose(unittest.TestCase):
    """RW-005: _Rpc.close() закрывает pipe stdout и останавливает читателя (иначе ResourceWarning/утечка fd)."""

    def test_rw005_close_closes_stdout_and_stops_reader(self):
        """RW-005: после close() stdout закрыт, поток-читатель завершён, процесс остановлен."""
        with tempfile.TemporaryDirectory() as tmp:
            hub = FakeDroidHub(Path(tmp) / "fake")
            with mock.patch.dict(os.environ, {"FAKE_DROID_DIR": str(hub.base)}):
                rpc = droid_image._Rpc(hub.launcher, Path(tmp), Path(tmp) / "home")
                rpc.close()
            self.assertTrue(rpc.proc.stdout.closed)
            self.assertFalse(rpc._reader.is_alive())
            self.assertIsNotNone(rpc.proc.poll())


# -- RW-007: событие сообщения без messageId -------------------------------------------------------------------


class TestRw007EmptyMessageId(RunCase):
    """RW-007: delta/complete/retract без messageId в карантин: ни прогресса, ни слота, ни вывода."""

    EVENTS = (
        "assistant_text_delta",
        "assistant_text_complete",
        "thinking_text_delta",
        "thinking_text_complete",
        "assistant_message_retracted",
    )

    def test_rw007_events_without_message_id_are_quarantined(self):
        """RW-007: отсутствующий и пустой messageId не меняют прогресс, слоты и held; счётчик карантина растёт."""
        run = self.make_run()
        run._on_notif(user_create())
        progress = run.last_progress
        for ntype in self.EVENTS:
            for fields in ({}, {"messageId": ""}, {"messageId": None}):
                with self.subTest(ntype=ntype, fields=fields):
                    before = run._quarantined
                    event = note(ntype, textDelta="GHOST", text="GHOST", **fields)
                    self.assertFalse(run._on_notif(event))
                    self.assertEqual(run._quarantined, before + 1)
                    self.assertEqual(run.last_progress, progress)
                    self.assertEqual(run._msgs, {})
                    self.assertEqual(run._held, {})
                    self.assertEqual(run._held_bytes, 0)

    def test_rw007_answer_has_only_own_text(self):
        """RW-007: после потока безымянных событий ответ содержит только текст собственного сообщения."""
        run = self.make_run()
        run._on_notif(user_create())
        for ntype in self.EVENTS:
            run._on_notif(note(ntype, textDelta="GHOST", text="GHOST"))
        run._on_notif(asst_create("m1", "turn-1", "OWN"))
        self.assertTrue(run._on_notif(terminal()))
        self.assertEqual([v for k, v in self.drain(run) if k == "text"], ["OWN"])


# -- RW-008: возврат ресурсов при сбое запуска фонового потока --------------------------------------------------


class TestRw008ResourceFinalization(RpcCase):
    """RW-008: слот P и реестры возвращаются, даже если фоновый поток закрытия не создан."""

    def test_rw008_close_returns_slot_when_background_stream_close_cannot_start(self):
        """RW-008: читатель pipe блокирован, Thread.start падает: слот P возвращён (finally), реестры очищены."""
        self.assertEqual(server.POOL.acquire(lambda: ""), "")
        proc = server.RpcProcess(str(server.WORKSPACE), server.POOL, True)
        real_reader = proc._reader
        streams = (proc.proc.stdout, proc.proc.stderr)

        def cleanup():
            real_reader.join(timeout=5)
            for stream in streams:
                stream.close()

        self.addCleanup(cleanup)
        proc._reader = types.SimpleNamespace(
            join=lambda timeout=None: None, is_alive=lambda: True
        )
        _inject_start_failure(self, {server.RpcProcess._close_stream})
        proc.close(
            mode="term"
        )  # RuntimeError фонового закрытия не выходит из close() (RW-007 Cycle 5)
        self.assertFalse(proc.holds_slot)
        self.assertEqual(server.POOL.used, 0)
        self.assertNotIn(proc.pid, server._rpc_procs)

    def test_rw008_shutdown_all_closes_synchronously_and_returns_slots(self):
        """RW-008: shutdown_all при сбое Thread.start: процессы убиты, слоты P возвращены, реестр пуст."""
        self.assertEqual(self.conv("chat-a").ask("q0")[0], 200)
        self.assertEqual(self.conv("chat-b").ask("q0")[0], 200)
        pids = [spawn["pid"] for spawn in self.hub.spawns()]
        self.assertEqual(len(pids), 2)
        self.assertEqual(server.POOL.used, 2)
        _inject_start_failure(self, {server._shutdown_one})
        self.assertEqual(server.shutdown_all(grace=1.0), 2)
        self.assertEqual(server.POOL.used, 0)
        self.assertEqual(server._rpc_procs, {})
        for pid in pids:
            self.assertTrue(self.wait_gone(pid, timeout=5))


# -- RW-009: бюджет карантина событий -------------------------------------------------------------------------


class TestRw009QuarantineBudget(RunCase):
    """RW-009: удерживаемые до create_message события учитываются по реальному размеру и не копят чужие поля."""

    def test_rw009_overlong_message_id_is_turn_error(self):
        """RW-009: id длиннее MAX_HELD_MID_CHARS - ошибка хода; id ровно предельной длины удерживается."""
        run = self.make_run()
        run._on_notif(user_create())
        with mock.patch.object(server, "MAX_HELD_MID_CHARS", 64):
            run._on_notif(
                note("assistant_text_delta", messageId="m" * 64, textDelta="x")
            )
            self.assertIn("m" * 64, run._held)
            with self.assertRaises(server.RpcError):
                run._on_notif(
                    note("assistant_text_delta", messageId="m" * 65, textDelta="x")
                )
        self.assertNotIn("m" * 65, run._held)

    def test_rw009_held_entry_keeps_only_needed_fields_and_counts_id(self):
        """RW-009: в held лежат только textDelta/text; размер = накладные + id + дельта + текст."""
        run = self.make_run()
        run._on_notif(user_create())
        run._on_notif(
            note(
                "assistant_text_delta",
                messageId="mid-1",
                textDelta="abc",
                junk="J" * 10_000,
            )
        )
        ((ntype, kept, size),) = run._held["mid-1"]
        self.assertEqual(ntype, "assistant_text_delta")
        self.assertEqual(kept, {"textDelta": "abc", "text": None})
        self.assertEqual(size, server.ENTRY_OVERHEAD_BYTES + len("mid-1") + 3)
        self.assertEqual(run._held_bytes, size)
        run._on_notif(
            note(
                "assistant_text_complete",
                messageId="mid-1",
                text="abcdef",
                junk="J" * 10_000,
            )
        )
        self.assertEqual(
            run._held_bytes, server.ENTRY_OVERHEAD_BYTES + len("mid-1") + 6
        )

    def test_rw009_flood_of_long_unique_ids_hits_turn_budget_fast(self):
        """RW-009: поток событий с длинными уникальными id упирается в бюджет хода по их реальному размеру."""
        server.MAX_TURN_TEXT_BYTES = 20_000
        run = self.make_run()
        run._on_notif(user_create())
        sent = 0
        with self.assertRaises(server.RpcError):
            for index in range(2000):
                sent += 1
                run._on_notif(
                    note(
                        "assistant_text_delta",
                        messageId="%d-" % index + "i" * 500,
                        textDelta="",
                    )
                )
        self.assertLessEqual(sent, 20_000 // 500 + 2)

    def test_rw009_released_hold_returns_bytes(self):
        """RW-009: после create_message собственного сообщения удержание снято, текст применён один раз."""
        run = self.make_run()
        run._on_notif(user_create())
        run._on_notif(note("assistant_text_delta", messageId="m1", textDelta="OW"))
        run._on_notif(note("assistant_text_delta", messageId="m1", textDelta="N"))
        self.assertGreater(run._held_bytes, 0)
        run._on_notif(asst_create("m1", "turn-1", "OWN"))
        self.assertEqual(run._held_bytes, 0)
        self.assertEqual(run._held, {})
        self.assertTrue(run._on_notif(terminal()))
        self.assertEqual([v for k, v in self.drain(run) if k == "text"], ["OWN"])


# -- RW-010: структурные токены строки RPC ---------------------------------------------------------------------


class TestRw010StructTokens(unittest.TestCase):
    """RW-010: предел структурных токенов считает `{`, `[`, `,`, `:` вне строк, а не только скобки."""

    def test_rw010_number_array_is_flood(self):
        """RW-010: массив чисел (две скобки, много запятых) превышает предел."""
        raw = b"[" + b",".join([b"1"] * 1000) + b"]"
        with mock.patch.object(server, "MAX_JSON_STRUCT_TOKENS", 500):
            self.assertTrue(server._struct_flood(raw))
        with mock.patch.object(server, "MAX_JSON_STRUCT_TOKENS", 5000):
            self.assertFalse(server._struct_flood(raw))

    def test_rw010_flat_object_with_many_keys_is_flood(self):
        """RW-010: плоский объект с множеством ключей (двоеточия и запятые) превышает предел."""
        raw = json.dumps({"k%d" % i: i for i in range(600)}).encode()
        with mock.patch.object(server, "MAX_JSON_STRUCT_TOKENS", 500):
            self.assertTrue(server._struct_flood(raw))

    def test_rw010_punctuation_inside_strings_is_not_counted(self):
        """RW-010: запятые, двоеточия и скобки внутри строковых литералов не считаются."""
        raw = json.dumps({"text": ",:[{" * 5000, "esc": 'a\\"b,:' * 100}).encode()
        with mock.patch.object(server, "MAX_JSON_STRUCT_TOKENS", 500):
            self.assertFalse(server._struct_flood(raw))

    def test_rw010_boundary_is_strict(self):
        """RW-010: ровно предел - допустимо, предел + 1 - отказ."""
        with mock.patch.object(server, "MAX_JSON_STRUCT_TOKENS", 10):
            self.assertEqual(server._struct_tokens(b"[1,1,1,1,1]"), 5)
            self.assertFalse(
                server._struct_flood(b"[" + b",".join([b"1"] * 10) + b"]")
            )  # 1 + 9 = 10
            self.assertTrue(
                server._struct_flood(b"[" + b",".join([b"1"] * 11) + b"]")
            )  # 1 + 10 = 11


class TestRw010StructTokensLive(RpcCase):
    """RW-010: строка из миллионов чисел отклоняется до json.loads (живой fake-droid)."""

    def test_rw010_number_flood_rejected_before_parse(self):
        """RW-010: 400 000 чисел в одной строке: json.loads не вызван, ход -> 502 proxy_error."""
        server.MAX_JSON_STRUCT_TOKENS = 50_000
        self.hub.script(
            [
                {
                    "steps": [
                        {"op": "num_flood", "count": 400_000},
                        {"op": "text", "text": "late"},
                    ]
                }
            ]
        )
        real = json.loads
        big = []

        def spy(text, *args, **kwargs):
            if isinstance(text, str) and len(text) > 500_000:
                big.append(len(text))
            return real(text, *args, **kwargs)

        with mock.patch.object(server.json, "loads", spy):
            status, body = self._post_json(dict(BODY, messages=[msg("hi")]))
        self.assertEqual(status, 502, body)
        self.assertEqual(body["error"]["type"], "proxy_error")
        self.assertEqual(big, [])
        self.assertTrue(no_leaks(self))


# -- RW-011: бюджет памяти готовых ответов ---------------------------------------------------------------------


class TestRw011DeliveryBudget(RpcCase):
    """RW-011: готовый ответ резервирует память до конца выдачи; исчерпан бюджет - 502 proxy_error."""

    def setUp(self):
        super().setUp()
        self.big = "A" * 5000
        self.hub.script([{"steps": [{"op": "text", "text": self.big}]}])

    def use_budget(self, total):
        budget = server._ByteBudget(total)
        patcher = mock.patch.object(server, "_DELIVERY_BUDGET", budget)
        patcher.start()
        self.addCleanup(patcher.stop)
        return budget

    def test_rw011_delivery_size_counts_text_events_and_arguments(self):
        """RW-011/RW-008: размер = удерживаемая память CPython: текст + события content/reasoning + аргументы вызовов."""
        out = {
            "text": "ab",
            "events": [
                ("content", "héllo"),
                ("reasoning", "r"),
                ("tool_call", {"function": {"arguments": "{}"}}),
            ],
        }
        held = sys.getsizeof
        self.assertEqual(
            server._delivery_size(out),
            held("ab") + held("héllo") + held("r") + held("{}"),
        )
        self.assertEqual(server._delivery_size({"text": "", "events": []}), 0)

    def test_rw011_json_over_budget_gives_502_and_releases(self):
        """RW-011: JSON: ответ больше бюджета - 502 proxy_error без контента, резерв не залипает."""
        budget = self.use_budget(1000)
        status, body = self._post_json(dict(BODY, messages=[msg("hi")]))
        self.assertEqual(status, 502, body)
        self.assertEqual(body["error"]["type"], "proxy_error")
        self.assertIn("delivery", body["error"]["message"])
        self.assertNotIn("AAAA", json.dumps(body))
        self.assertTrue(wait_until(lambda: budget._used == 0))
        self.assertTrue(no_leaks(self))

    def test_rw011_sse_over_budget_gives_error_event(self):
        """RW-011: SSE: ответ больше бюджета - событие error proxy_error и [DONE], без контента."""
        budget = self.use_budget(1000)
        status, stream = self._post(dict(BODY, stream=True, messages=[msg("hi")]))
        self.assertEqual(status, 200)
        self.assertIn("proxy_error", stream)
        self.assertNotIn("AAAA", stream)
        self.assertTrue(stream.rstrip().endswith("data: [DONE]"))
        self.assertTrue(wait_until(lambda: budget._used == 0))

    def test_rw011_reservation_held_by_other_delivery_blocks_then_frees(self):
        """RW-011: бюджет занят чужой выдачей - 502; после освобождения тот же запрос проходит, резерв возвращён."""
        budget = self.use_budget(100_000)
        self.assertTrue(budget.reserve(100_000))
        status, body = self._post_json(dict(BODY, messages=[msg("hi")]))
        self.assertEqual(status, 502, body)
        budget.release(100_000)
        self.hub.script([{"steps": [{"op": "text", "text": self.big}]}])
        status, body = self._post_json(dict(BODY, messages=[msg("hi")]))
        self.assertEqual(status, 200, body)
        self.assertEqual(body["choices"][0]["message"]["content"], self.big)
        self.assertTrue(wait_until(lambda: budget._used == 0))


# -- RW-012: аргументы вызовов выдаются срезами -----------------------------------------------------------------


class TestRw012ToolArgumentsStreaming(RpcCase):
    """RW-012: большие arguments tool_call выдаются срезами (JSON - без второй копии, SSE - фрагментами)."""

    CITY = 'Ж"q\\\n' * 80

    def setUp(self):
        super().setUp()
        server.DELIVERY_CHUNK_BYTES = 64
        call = json.dumps(
            {"name": "get_weather", "arguments": {"city": self.CITY}},
            ensure_ascii=False,
        )
        self.hub.script(
            [
                {
                    "steps": [
                        {
                            "op": "text",
                            "text": "pre "
                            + server.TOOL_CALL_OPEN
                            + call
                            + server.TOOL_CALL_CLOSE,
                        }
                    ]
                }
            ]
            * 2
        )
        self.expected = json.dumps({"city": self.CITY}, ensure_ascii=False)
        self.assertGreater(len(self.expected.encode()), 64 * 4)

    def test_rw012_json_arguments_are_intact(self):
        """RW-012: JSON: Content-Length верен, arguments совпадает побайтно, finish_reason=tool_calls."""
        status, body = self._post_json(dict(BODY, tools=TOOLS, messages=[msg("w")]))
        self.assertEqual(status, 200, body)
        choice = body["choices"][0]
        self.assertEqual(choice["finish_reason"], "tool_calls")
        calls = choice["message"]["tool_calls"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["function"]["name"], "get_weather")
        self.assertEqual(calls[0]["function"]["arguments"], self.expected)
        self.assertEqual(choice["message"]["content"], "pre ")

    def test_rw012_sse_arguments_arrive_in_fragments_and_reassemble(self):
        """RW-012: SSE: первый кадр с id и именем, остальные - фрагменты arguments; склейка равна оригиналу."""
        status, stream = self._post(
            dict(BODY, stream=True, tools=TOOLS, messages=[msg("w")])
        )
        self.assertEqual(status, 200)
        frames = []
        for line in stream.splitlines():
            if line.startswith("data: {"):
                delta = json.loads(line[6:])["choices"][0]["delta"]
                if delta.get("tool_calls"):
                    frames.append(delta["tool_calls"][0])
        self.assertGreater(len(frames), 2)
        self.assertEqual(frames[0]["function"]["name"], "get_weather")
        self.assertTrue(frames[0]["id"].startswith("call_"))
        for frame in frames[1:]:
            self.assertNotIn("id", frame)
            self.assertEqual(frame["index"], frames[0]["index"])
        self.assertEqual(
            "".join(f["function"]["arguments"] for f in frames), self.expected
        )
        self.assertIn('"finish_reason": "tool_calls"', stream)


# -- RW-013: точный YAML-путь config.maxBytes -------------------------------------------------------------------


class TestRw013ProfilePath(unittest.TestCase):
    """RW-013: maxBytes принимается только по пути agent-instructions -> config -> maxBytes."""

    @staticmethod
    def preset(plugin_lines):
        return (
            "- id: preset-standard\n  config:\n    id: standard\n    plugins:\n      - id: persona\n"
            "      - id: agent-instructions\n"
            + plugin_lines
            + "      - id: tool-bash\n"
        )

    def parse(self, plugin_lines):
        return bg.parse_profile_maxbytes(self.preset(plugin_lines))

    def test_rw013_exact_path_is_accepted(self):
        """RW-013: контроль: прямой потомок config плагина (в том числе после соседних ключей) читается."""
        self.assertEqual(
            self.parse("        config:\n          maxBytes: 106496\n"), 106496
        )
        self.assertEqual(
            self.parse(
                "        config:\n          prefix: x\n          maxBytes: 4096\n"
            ),
            4096,
        )
        self.assertEqual(bg.parse_profile_maxbytes(PROFILE_YML % 106496), 106496)

    def test_rw013_quoted_keys_are_accepted(self):
        """RW-013: ключи и id в кавычках разбираются тем же путём."""
        text = (
            '- id: preset-standard\n  config:\n    plugins:\n      - id: "agent-instructions"\n'
            "        \"config\":\n          'maxBytes': 106496\n"
        )
        self.assertEqual(bg.parse_profile_maxbytes(text), 106496)

    def test_rw013_comments_and_blank_lines_do_not_break_block(self):
        """RW-013: комментарии и пустые строки внутри config не закрывают блок и не считаются потомками."""
        self.assertEqual(
            self.parse(
                "        config:\n# c\n\n          # note\n          maxBytes: 7\n"
            ),
            7,
        )

    def test_rw013_maxbytes_without_config_is_unreadable(self):
        """RW-013: maxBytes прямо под плагином (мимо config) - None."""
        self.assertIsNone(self.parse("        maxBytes: 5\n"))

    def test_rw013_nested_maxbytes_is_unreadable(self):
        """RW-013: config.extra.maxBytes и maxBytes глубже первого потомка - None."""
        self.assertIsNone(
            self.parse("        config:\n          extra:\n            maxBytes: 5\n")
        )
        self.assertIsNone(
            self.parse("        config:\n          mode: a\n            maxBytes: 5\n")
        )

    def test_rw013_maxbytes_after_config_closed_is_unreadable(self):
        """RW-013: maxBytes на уровне config после закрытия блока (соседний ключ плагина) - None."""
        self.assertIsNone(
            self.parse("        config:\n          prefix: x\n        maxBytes: 5\n")
        )

    def test_rw013_duplicate_config_is_unreadable(self):
        """RW-013: второй config у плагина - None, даже с одинаковым значением."""
        self.assertIsNone(
            self.parse(
                "        config:\n          maxBytes: 5\n        config:\n          x: 1\n"
            )
        )

    def test_rw013_duplicate_maxbytes_is_unreadable(self):
        """RW-013: два maxBytes в config (в том числе с разными кавычками) - None."""
        self.assertIsNone(
            self.parse(
                '        config:\n          maxBytes: 5\n          "maxBytes": 6\n'
            )
        )

    def test_rw013_non_numeric_value_is_unreadable(self):
        """RW-013: нечисловое и отрицательное значение - None."""
        for value in ("abc", "-1", "5 # c", "''", ""):
            with self.subTest(value=value):
                self.assertIsNone(
                    self.parse("        config:\n          maxBytes: %s\n" % value)
                )


# -- RW-014: история виденных канонов переживает рестарт ---------------------------------------------------------


class TestRw014CanonSeenPersistence(GuardCase):
    """RW-014: дайджесты виденных канонов хранятся в state/canon_seen.json: блок со старой копией остаётся KB-формой."""

    def set_canon(self, text):
        Path(server.GUARD_CANON).write_text(text + "\n", encoding="utf-8")
        server._canon_cache.update(key=None, digest="")
        return server._canon_digest()

    def test_rw014_old_canon_block_stays_kb_form_after_restart(self):
        """RW-014: канон изменён, процесс перезапущен (память пуста): блок со старой копией канона - canon_only."""
        old = self.set_canon("old canon body")
        new = self.set_canon("new canon body")
        server._canon_seen.clear()  # рестарт: история только на диске; main() грузит её до первого чтения канона
        server._canon_cache.update(key=None, digest="")
        server._canon_seen_load()
        self.assertEqual(list(server._canon_seen), [old, new])
        self.assertEqual(server._canon_digest(), new)
        self.assertTrue(server._block_is_canon_only(HEAD + "old canon body"))
        self.assertTrue(server._block_is_canon_only(HEAD + "new canon body"))
        self.assertFalse(server._block_is_canon_only(HEAD + "foreign body"))

    def test_rw014_file_is_private_json_list_of_digests(self):
        """RW-014: файл - JSON-список sha256 по порядку появления, права 0600, повтор дайджеста не дублирует."""
        first = self.set_canon("canon one")
        second = self.set_canon("canon two")
        self.set_canon("canon one")
        path = server._canon_seen_path()
        self.assertEqual(json.loads(path.read_text("utf-8")), [first, second])
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_rw014_corrupt_or_foreign_entries_are_ignored(self):
        """RW-014: нечитаемый файл - пустая история; не-sha256 записи отбрасываются."""
        path = server._canon_seen_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        for content in ("{not json", '{"a": 1}', "[]"):
            path.write_text(content, encoding="utf-8")
            server._canon_seen.clear()
            server._canon_seen_load()
            self.assertEqual(dict(server._canon_seen), {}, content)
        good = "a" * 64
        path.write_text(json.dumps([good, "xyz", 5, "A" * 64, None]), encoding="utf-8")
        server._canon_seen_load()
        self.assertEqual(list(server._canon_seen), [good])
        path.unlink()
        server._canon_seen.clear()
        server._canon_seen_load()  # файла нет - не ошибка
        self.assertEqual(dict(server._canon_seen), {})

    def test_rw014_history_is_capped_dropping_oldest(self):
        """RW-014: сверх CANON_SEEN_KEEP вытесняются самые старые; на диске тот же хвост."""
        with mock.patch.object(server, "CANON_SEEN_KEEP", 3):
            digests = [self.set_canon("canon %d" % i) for i in range(5)]
        self.assertEqual(list(server._canon_seen), digests[2:])
        self.assertEqual(
            json.loads(server._canon_seen_path().read_text("utf-8")), digests[2:]
        )

    def test_rw014_persist_failure_is_fail_closed(self):
        """RW-014/RW-011: сбой записи истории - CanonPersistError, запись в памяти откатана, журнал содержит причину."""
        with mock.patch.object(
            server, "_atomic_write", side_effect=OSError(28, "No space left")
        ):
            with self.capture_logs() as lines:
                with self.assertRaises(server.CanonPersistError):
                    self.set_canon("canon enospc")
        self.assertEqual(dict(server._canon_seen), {})
        self.assertTrue(
            any(ln.startswith("canon_seen_persist_failed") for ln in lines), lines
        )

    def test_rw014_gate_keeps_old_block_limited_after_restart(self):
        """RW-014: после рестарта старый KB-блок 61000 Б всё ещё отклоняется предельной проверкой 60000 Б."""
        size = 61000
        body = "k" * (size - len(HEAD.encode()))
        self.set_canon(body)
        self.set_canon("short new canon")
        server._canon_seen.clear()
        server._canon_cache.update(key=None, digest="")
        server._canon_seen_load()
        block = HEAD + body
        status, answer = self._post_json(
            dict(
                BODY,
                prompt_cache_key="chat-restart",
                messages=[msg("hello"), msg(block)],
            )
        )
        self.assertEqual(status, 503, answer)
        self.assertEqual(self.hub.spawns(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
