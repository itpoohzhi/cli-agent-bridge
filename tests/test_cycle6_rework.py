"""Регрессионные тесты cycle-6 rework (замечания Совета Cycle 5: RW-002, RW-006…RW-012, FU-001/FU-002).

Сценарии идут через настоящий HTTP-сервер моста и fake-subprocess (tests/fake_droid.py) либо напрямую через
Run._on_notif / чистые функции. Реальный droid, сеть, ~/.dsh и боевые каталоги владельца не используются.
Идентификаторы RW-NNN - в имени метода и docstring.
"""

import gc
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
import warnings
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import b_guard as bg  # noqa: E402
import droid_image  # noqa: E402
import server  # noqa: E402
from bridge_testlib import FakeDroidHub, wait_until  # noqa: E402
from rpc_testlib import RpcCase  # noqa: E402
from test_rpc_cycle3 import GuardCase  # noqa: E402
from test_rpc_cycle4 import (  # noqa: E402
    HEAD,
    RunCase,
    _inject_start_failure,
    asst_create,
    note,
    stub_proc,
    terminal,
    user_create,
)
from test_rpc_rework import BODY, msg, no_leaks  # noqa: E402


# -- RW-002 / RW-010 / FU-002: droid_image закрывает stdin и stdout, ResourceWarning как ошибка -----------------

IMAGE_CLOSE_SCRIPT = (
    "import gc, sys\n"
    "from pathlib import Path\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "import droid_image\n"
    "rpc = droid_image._Rpc(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))\n"
    "rpc.close()\n"
    "del rpc\n"
    "gc.collect()\n"
)


class TestRw010ImageRpcResources(unittest.TestCase):
    """RW-010: квалификация образа не оставляет открытых stdin/stdout (ResourceWarning трактуется как ошибка)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.hub = FakeDroidHub(self.tmp / "fake")
        patcher = mock.patch.dict(os.environ, {"FAKE_DROID_DIR": str(self.hub.base)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def new_rpc(self):
        return droid_image._Rpc(self.hub.launcher, self.tmp, self.tmp / "home")

    def test_rw010_close_closes_stdin_and_stdout_without_resource_warning(self):
        """RW-010: после close() stdin и stdout закрыты; сборка мусора не порождает ResourceWarning."""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            rpc = self.new_rpc()
            stdin, stdout = rpc.proc.stdin, rpc.proc.stdout
            rpc.close()
            self.assertTrue(stdin.closed)
            self.assertTrue(stdout.closed)
            del rpc, stdin, stdout
            gc.collect()
        self.assertEqual(
            [str(w.message) for w in caught if issubclass(w.category, ResourceWarning)],
            [],
        )

    def test_rw010_close_is_clean_under_python_w_error_resource_warning(self):
        """RW-010: тот же сценарий в отдельном интерпретаторе с `-W error::ResourceWarning`: stderr пуст, rc=0."""
        result = subprocess.run(
            [
                sys.executable,
                "-W",
                "error::ResourceWarning",
                "-c",
                IMAGE_CLOSE_SCRIPT,
                str(ROOT / "tools"),
                str(self.hub.launcher),
                str(self.tmp),
                str(self.tmp / "home"),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            env=dict(os.environ),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("ResourceWarning", result.stderr)
        self.assertEqual(result.stderr, "")

    def test_fu002_blocked_reader_stdout_is_closed_in_background(self):
        """FU-002: читатель не завершился за join - stdout закрывается фоновым потоком, а не остаётся до GC."""
        rpc = self.new_rpc()
        real_reader = rpc._reader
        stdout = rpc.proc.stdout
        rpc._reader = types.SimpleNamespace(
            join=lambda timeout=None: None, is_alive=lambda: True
        )
        rpc.close()
        self.assertTrue(wait_until(lambda: stdout.closed))
        real_reader.join(timeout=5)

    def test_rw002_call_without_stdin_is_probe_error(self):
        """RW-002: proc.stdin is None - ProbeError (сужение типа), а не AttributeError."""
        rpc = self.new_rpc()
        stdin = rpc.proc.stdin
        rpc.proc.stdin = None
        with self.assertRaises(droid_image.ProbeError):
            rpc.call("droid.list_tools", {}, timeout=1.0)
        rpc.proc.stdin = stdin
        rpc.close()


# -- RW-009: flow-form дубликат config в профиле DSH ---------------------------------------------------------------


class TestRw009FlowDuplicateConfig(unittest.TestCase):
    """RW-009: ключ config считается в любой форме значения; повтор и flow-форма - None (отказ)."""

    @staticmethod
    def parse(plugin_lines):
        text = (
            "- id: preset-standard\n  config:\n    id: standard\n    plugins:\n      - id: persona\n"
            "      - id: agent-instructions\n"
            + plugin_lines
            + "      - id: tool-bash\n"
        )
        return bg.parse_profile_maxbytes(text)

    def test_rw009_single_block_config_still_gives_value(self):
        """RW-009: контроль: одиночный блочный config читается."""
        self.assertEqual(
            self.parse("        config:\n          maxBytes: 106496\n"), 106496
        )

    def test_rw009_block_then_flow_duplicate_is_unreadable(self):
        """RW-009: block-config с 106496, затем flow-config с 262144 - None, а не «безопасное первое значение»."""
        self.assertIsNone(
            self.parse(
                "        config:\n          maxBytes: 106496\n"
                "        config: {maxBytes: 262144}\n"
            )
        )

    def test_rw009_flow_then_block_duplicate_is_unreadable(self):
        """RW-009: flow-config, затем block-config - None."""
        self.assertIsNone(
            self.parse(
                "        config: {maxBytes: 262144}\n"
                "        config:\n          maxBytes: 106496\n"
            )
        )

    def test_rw009_quoted_flow_duplicate_is_unreadable(self):
        """RW-009: quoted-ключ и quoted-значение: `\"config\": {...}` после block-config - None."""
        self.assertIsNone(
            self.parse(
                "        config:\n          maxBytes: 106496\n"
                '        "config": {"maxBytes": 262144}\n'
            )
        )
        self.assertIsNone(
            self.parse(
                "        'config': {'maxBytes': 5}\n        config:\n          maxBytes: 7\n"
            )
        )

    def test_rw009_single_flow_or_inline_config_is_unreadable(self):
        """RW-009: единственный config в flow/inline-форме не поддерживается разбором - None."""
        self.assertIsNone(self.parse("        config: {maxBytes: 106496}\n"))
        self.assertIsNone(self.parse('        config: "x"\n'))

    def test_rw009_other_keys_starting_with_config_are_not_counted(self):
        """RW-009: контроль: ключ `configuration:` не считается ключом config."""
        self.assertEqual(
            self.parse(
                "        configuration: x\n        config:\n          maxBytes: 4096\n"
            ),
            4096,
        )


# -- RW-006: структурный лимит до json.loads ----------------------------------------------------------------------


class TestRw006StructLimit(unittest.TestCase):
    """RW-006: дефолт 50 000; плоские потоки скаляров, `{}` и глубокая вложенность < 8 МиБ отсекаются до разбора."""

    def test_rw006_default_limit_is_50000(self):
        """RW-006: дефолт DROID_BRIDGE_MAX_JSON_STRUCT_TOKENS равен заявленным 50000 (код, README, ADR, CHANGELOG)."""
        self.assertEqual(server.MAX_JSON_STRUCT_TOKENS, 50_000)

    def test_rw006_scalar_array_under_line_limit_is_flood(self):
        """RW-006: `[1.1, 1.1, ...]` меньше MAX_RPC_LINE_BYTES (8 МиБ) - flood по умолчанию."""
        raw = b"[" + b",".join([b"1.1"] * 1_500_000) + b"]"
        self.assertLess(len(raw), server.MAX_RPC_LINE_BYTES)
        self.assertTrue(server._struct_flood(raw))

    def test_rw006_empty_objects_under_line_limit_is_flood(self):
        """RW-006: миллионы `{}` меньше 8 МиБ - flood."""
        raw = b"{}" * 3_000_000
        self.assertLess(len(raw), server.MAX_RPC_LINE_BYTES)
        self.assertTrue(server._struct_flood(raw))

    def test_rw006_deep_nesting_under_line_limit_is_flood(self):
        """RW-006: вложенность в миллионы уровней меньше 8 МиБ - flood до json.loads."""
        raw = b"[" * 4_000_000 + b"]" * 4_000_000
        self.assertLess(len(raw), server.MAX_RPC_LINE_BYTES)
        self.assertTrue(server._struct_flood(raw))

    def test_rw006_valid_large_frames_within_limit_pass(self):
        """RW-006: контроль: большая строка и массив в пределах лимита проходят."""
        big_text = json.dumps({"text": "x, y: [z] {w} " * 400_000}).encode()
        self.assertGreater(len(big_text), 5_000_000)
        self.assertFalse(server._struct_flood(big_text))
        numbers = json.dumps({"pad": [1.1] * 20_000}).encode()
        self.assertFalse(server._struct_flood(numbers))


class TestRw006StructLimitLive(RpcCase):
    """RW-006: кадр `[1.1, ...]` отклоняется до json.loads с 502 proxy_error, читатель и слоты живы."""

    def test_rw006_float_array_flood_rejected_before_parse(self):
        """RW-006: 1 000 000 значений 1.1 (≈ 4 МиБ) при дефолтном лимите: json.loads не вызван, ход 502, слоты возвращены."""
        self.hub.script(
            [
                {
                    "steps": [
                        {"op": "num_flood", "count": 1_000_000, "value": "1.1"},
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
        self.hub.script([{"steps": [{"op": "text", "text": "ok"}]}])
        status, body = self._post_json(dict(BODY, messages=[msg("again")]))
        self.assertEqual(
            status, 200, body
        )  # читатель и пул живы: следующий ход проходит


# -- RW-007: изоляция отказов потоков shutdown и возврат слота -----------------------------------------------------


class TestRw007ShutdownIsolation(RpcCase):
    """RW-007: сбой Thread.start (и в shutdown_all, и в close) не выходит наружу и не пропускает детей и force_kill."""

    def children(self):
        self.assertEqual(self.conv("chat-a").ask("q0")[0], 200)
        self.assertEqual(self.conv("chat-b").ask("q0")[0], 200)
        procs = list(server._rpc_procs.values())
        self.assertEqual(len(procs), 2)
        return procs

    def block_readers(self, procs):
        """Читатель stdout «не завершается»: close() обязан закрывать pipe в фоне (а поток создать не удаётся)."""
        for proc in procs:
            real_reader, streams = proc._reader, (proc.proc.stdout, proc.proc.stderr)
            self.addCleanup(
                lambda r=real_reader, s=streams: (
                    r.join(timeout=5),
                    [x.close() for x in s],
                )
            )
            proc._reader = types.SimpleNamespace(
                join=lambda timeout=None: None, is_alive=lambda: True
            )

    def test_rw007_thread_start_failures_in_shutdown_and_close_for_two_children(self):
        """RW-007: два ребёнка, RuntimeError на Thread.start и в shutdown_all, и в close(): исключения нет, слоты возвращены."""
        procs = self.children()
        self.block_readers(procs)
        killed = []
        real_kill = server.RpcProcess.force_kill
        _inject_start_failure(
            self, {server._shutdown_one, server.RpcProcess._close_stream}
        )
        with mock.patch.object(
            server.RpcProcess,
            "force_kill",
            lambda proc: (killed.append(proc.pid), real_kill(proc)),
        ):
            self.assertEqual(server.shutdown_all(grace=1.0), 2)
        self.assertEqual(sorted(killed), sorted(p.pid for p in procs))
        for proc in procs:
            self.assertFalse(proc.holds_slot)
            proc.close(
                mode="term"
            )  # повторный close() не бросает и слот не возвращает второй раз
        self.assertEqual(server.POOL.used, 0)
        self.assertEqual(server._rpc_procs, {})

    def test_rw007_failure_closing_one_child_does_not_skip_next_or_force_kill(self):
        """RW-007: исключение синхронного закрытия первого ребёнка не прерывает обход второго и финальный force_kill."""
        procs = self.children()
        real_one = server._shutdown_one
        seen = []

        def flaky(proc, close_kwargs):
            seen.append(proc.pid)
            if len(seen) == 1:
                raise RuntimeError("second failure")
            return real_one(proc, close_kwargs)

        killed = []
        real_kill = server.RpcProcess.force_kill
        with mock.patch.object(server, "_shutdown_one", flaky):
            _inject_start_failure(self, {flaky})
            with mock.patch.object(
                server.RpcProcess,
                "force_kill",
                lambda proc: (killed.append(proc.pid), real_kill(proc)),
            ):
                with self.capture_logs() as lines:
                    self.assertEqual(server.shutdown_all(grace=1.0), 2)
        self.assertEqual(len(seen), 2)
        self.assertEqual(sorted(killed), sorted(p.pid for p in procs))
        self.assertTrue(
            any(ln.startswith("shutdown_child_failed") for ln in lines), lines
        )
        for proc in procs:
            self.assertTrue(self.wait_gone(proc.pid, timeout=5))
        for proc in (
            procs
        ):  # ребёнок с отказом закрытия добирается обычным close(): слот P возвращается
            proc.close(mode="term")
        self.assertEqual(server.POOL.used, 0)


# -- RW-008: бюджет памяти доставки по фактической памяти CPython --------------------------------------------------


class TestRw008DeliveryMemory(RpcCase):
    """RW-008: резерв доставки >= фактическая память (ASCII + emoji = 4 Б на символ, две копии текста)."""

    def test_rw008_ascii_with_one_emoji_is_charged_four_bytes_per_char(self):
        """RW-008: два сообщения ~3 МиБ ASCII+emoji: резерв >= 4 Б/символ в обеих копиях (события и объединённый текст)."""
        chars = 3 << 20
        piece = "a" * chars + "\N{GRINNING FACE}"
        out = {
            "text": piece + piece,
            "events": [("content", piece), ("content", piece)],
        }
        self.assertGreaterEqual(server._delivery_size(out), 4 * (4 * chars))
        self.assertGreater(
            server._delivery_size(out), 3 * len((piece + piece).encode("utf-8"))
        )

    def test_rw008_cyrillic_and_ascii_widths(self):
        """RW-008: кириллица - не меньше 2 Б/символ, ASCII - не меньше 1 Б/символ (память, а не длина UTF-8 среза)."""
        self.assertGreaterEqual(
            server._delivery_size({"text": "ж" * 1000, "events": []}), 2000
        )
        self.assertGreaterEqual(
            server._delivery_size({"text": "a" * 1000, "events": []}), 1000
        )
        self.assertEqual(server._delivery_size({"text": "", "events": []}), 0)

    def test_rw008_budget_is_exhausted_by_mixed_unicode_answer(self):
        """RW-008: ответ ASCII+emoji не помещается в бюджет, достаточный по длине UTF-8: 502 proxy_error, резерв свободен."""
        text = "a" * 5000 + "\N{GRINNING FACE}"
        self.hub.script([{"steps": [{"op": "text", "text": text}]}])
        budget = server._ByteBudget(
            25_000
        )  # UTF-8 длина обеих копий ~ 10 КБ, память CPython ~ 40 КБ
        with mock.patch.object(server, "_DELIVERY_BUDGET", budget):
            status, body = self._post_json(dict(BODY, messages=[msg("hi")]))
            self.assertEqual(status, 502, body)
            self.assertEqual(body["error"]["type"], "proxy_error")
            self.assertTrue(wait_until(lambda: budget._used == 0))
        self.assertTrue(no_leaks(self))


# -- RW-011: сбой записи canon_seen.json - fail-closed -----------------------------------------------------------------


class TestRw011CanonSeenFailClosed(GuardCase):
    """RW-011: ход не принимается, пока история канонов не записана; после записи файл переживает рестарт."""

    def block_request(self, key):
        return dict(
            BODY,
            prompt_cache_key=key,
            messages=[msg("hello"), msg(HEAD + "canon body")],
        )

    def test_rw011_persist_failure_rejects_turn_then_recovers_and_survives_restart(
        self,
    ):
        """RW-011: ENOSPC на canon_seen.json - 503 launcher_unavailable до spawn; после починки ход проходит, файл на диске."""
        Path(server.GUARD_CANON).write_text("canon body\n", encoding="utf-8")
        server._canon_cache.update(key=None, digest="")
        server._canon_seen.clear()
        real_write = server._atomic_write

        def failing(path, data):
            if Path(path).name == "canon_seen.json":
                raise OSError(28, "No space left")
            return real_write(path, data)

        with mock.patch.object(server, "_atomic_write", failing):
            status, body = self._post_json(self.block_request("chat-canon"))
        self.assertEqual(status, 503, body)
        self.assertEqual(body["error"]["type"], "launcher_unavailable")
        self.assertEqual(self.hub.spawns(), [])
        self.assertEqual(dict(server._canon_seen), {})
        status, body = self._post_json(self.block_request("chat-canon"))
        self.assertEqual(status, 200, body)
        digest = server._canon_digest()
        server._canon_seen.clear()  # рестарт инстанса: история только на диске
        server._canon_seen_load()
        self.assertIn(digest, server._canon_seen)


# -- RW-012: учёт истории droid: служебные вставки приходят с пустым content ---------------------------------------


def service_create(mid="svc-1", parent="root"):
    """Живой create_message system-reminder реального droid: content=[] (текст виден только после load_session)."""
    return note(
        "create_message",
        messageId=mid,
        message={"id": mid, "role": "user", "content": [], "parentId": parent},
        requestId="r0",
    )


class TestRw012HistoryAccounting(RunCase):
    """RW-012: счёт droid_real по живым нотификациям совпадает с подсчётом после load_session (без HISTORY_MISMATCH)."""

    PATHS = ("cold", "hot", "restore")

    @staticmethod
    def proc_for(path):
        return stub_proc() if path == "hot" else None

    def test_rw012_blank_service_user_messages_are_not_counted(self):
        """RW-012: пустые user-вставки (system-reminder) не увеличивают droid_real; пользовательский ход и ответ - да."""
        for path in self.PATHS:
            with self.subTest(path):
                run = self.make_run(path, self.proc_for(path), droid_real=0)
                run._on_notif(service_create("svc-1"))
                run._on_notif(service_create("svc-2"))
                self.assertEqual(run.droid_real, 0)
                run._on_notif(user_create())
                self.assertEqual(run.droid_real, 1)
                run._on_notif(service_create("svc-3"))
                run._on_notif(asst_create("m1", "turn-1", "OWN"))
                self.assertEqual(run.droid_real, 2)
                self.assertTrue(run._on_notif(terminal()))

    def test_rw012_live_count_equals_load_count_for_stand_history(self):
        """RW-012: история стенда after-idle (8 сообщений, 3 служебных вставки): live-счёт равен load-счёту 5."""
        stored = [
            ("user", "Привет"),
            (
                "user",
                "<system-reminder>\nWorkspace instruction budget</system-reminder>",
            ),
            (
                "user",
                "Current runtime context. This snapshot supersedes earlier runtime-context snapshots.",
            ),
            ("user", "<system-reminder>Current date: 2026-10-08.</system-reminder>"),
            ("user", "<system-reminder>\nA skill is a reusable set</system-reminder>"),
            ("assistant", "Привет."),
            ("user", "Для справки: 42"),
            ("assistant", "Принято."),
        ]
        loaded = [
            {"role": role, "content": [{"type": "text", "text": text}]}
            for role, text in stored
        ]
        load_count = sum(1 for m in loaded if not server._is_service_message(m))
        run = self.make_run("hot", stub_proc(), droid_real=0)
        for index, (role, text) in enumerate(stored):
            if role == "user" and text.startswith("<system-reminder>"):
                run._on_notif(
                    service_create("s%d" % index)
                )  # живое событие: content пуст
            elif role == "user":
                content = [{"type": "text", "text": text}]
                run._on_notif(
                    note(
                        "create_message",
                        messageId="u%d" % index,
                        requestId="r0",
                        message={
                            "id": "u%d" % index,
                            "role": "user",
                            "content": content,
                        },
                    )
                )
            else:
                run._on_notif(asst_create("a%d" % index, "u%d" % index, text))
        self.assertEqual(load_count, 5)
        self.assertEqual(run.droid_real, load_count)


# -- RW-007 (прошлый бриф): пути hot/restore и ход без user ID -----------------------------------------------------


class TestRw007PathsWithoutUserId(RunCase):
    """RW-007: квазиконтроль карантина на hot и restore (а не только cold) и ход без id user-сообщения."""

    PATHS = ("cold", "hot", "restore")
    EVENTS = (
        "assistant_text_delta",
        "assistant_text_complete",
        "thinking_text_delta",
        "thinking_text_complete",
        "assistant_message_retracted",
    )

    @staticmethod
    def proc_for(path):
        return stub_proc() if path == "hot" else None

    def test_rw007_events_without_message_id_are_quarantined_on_every_path(self):
        """RW-007: на cold/hot/restore события без messageId не меняют прогресс и слоты, ответ - только собственный текст."""
        for path in self.PATHS:
            with self.subTest(path):
                run = self.make_run(path, self.proc_for(path))
                run._on_notif(user_create())
                progress = run.last_progress
                for ntype in self.EVENTS:
                    for fields in ({}, {"messageId": ""}):
                        before = run._quarantined
                        self.assertFalse(
                            run._on_notif(
                                note(ntype, textDelta="GHOST", text="GHOST", **fields)
                            )
                        )
                        self.assertEqual(run._quarantined, before + 1)
                self.assertEqual(run.last_progress, progress)
                self.assertEqual(run._msgs, {})
                run._on_notif(asst_create("m1", "turn-1", "OWN"))
                self.assertTrue(run._on_notif(terminal()))
                self.assertEqual(
                    [v for k, v in self.drain(run) if k == "text"], ["OWN"]
                )

    def test_rw007_turn_without_user_id_is_never_completed_on_every_path(self):
        """RW-007: user create без id: active_turn пуст, ответ ассистента и terminal не принимаются на cold/hot/restore."""
        for path in self.PATHS:
            with self.subTest(path):
                run = self.make_run(path, self.proc_for(path))
                run._on_notif(user_create(with_ids=False))
                self.assertEqual(run.active_turn, "")
                progress = run.last_progress
                run._on_notif(asst_create("m1", "turn-1", "NOT-CONFIRMED"))
                self.assertFalse(run._on_notif(terminal("turn-1")))
                self.assertEqual(run._msgs, {})
                self.assertEqual(run.last_progress, progress)
                self.assertEqual(self.drain(run), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
