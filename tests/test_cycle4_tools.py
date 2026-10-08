"""Регрессионные тесты cycle-4 для tools/b_guard.py, tools/droid_image.py и tools/receipt_schema.py.

RW-010 (F-B05) - охранник проверяет настоящий user-global файл, а не его синтезированную копию;
RW-020 (F-B14) - разбор профиля DSH отвергает дубли и «чужой» maxBytes;
RW-011 (F-B06) - read-back update берётся и из нотификаций, уже вернувшихся из call();
RW-012 (F-B07) - receipt не подтверждает подменённый профиль, а непроверяемые поля помечает явно;
RW-013 (F-C05) - droid_image зависит только от receipt_schema и не импортирует мост (server.py).
Реальный droid, ~/.dsh и боевые каталоги владельца не используются.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import b_guard as bg  # noqa: E402
import droid_image  # noqa: E402
from rpc_testlib import RpcCase  # noqa: E402
from test_b_guard import PROFILE_YML, build_snapshot_fs  # noqa: E402

MODEL, EFFORT = droid_image.PROBE_MODEL_EFFORT
IDS = ["Execute", "Read"]
DROP = object()


# -- RW-010: user-global instruction source --------------------------------------------------------------

class TestRw010UserGlobal(unittest.TestCase):
    """RW-010: check_installed читает настоящий ~/.dsh/AGENTS.md (наличие, содержимое, цель симлинка)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.fs = build_snapshot_fs(self.root)
        self.canon = self.fs["canon"]
        self.ug = self.root / "dsh-home" / "AGENTS.md"
        self.ug.parent.mkdir()
        self.ug.symlink_to(self.canon)
        cwds = self.fs["cwds"]
        self.default = tuple((label, str(cwds[label])) for label in ("KB", "WA", "AB", "DW"))
        for patcher in (mock.patch.object(bg, "KB_CWD", str(cwds["KB"])),
                        mock.patch.object(bg, "DEFAULT_CWDS", self.default),
                        mock.patch.object(bg, "UG_PATH", str(self.ug))):
            patcher.start()
            self.addCleanup(patcher.stop)

    def check(self, cwds=None):
        return bg.check_installed(106496, cwds or bg.DEFAULT_CWDS, str(self.canon))

    def assert_canon_lost(self, result):
        """Сервер считает небезопасным `None` либо exit_code == 2; причина обязана назвать user-global."""
        if result is None:
            return
        self.assertEqual(result.exit_code, 2, result)
        joined = " ".join(result.reasons)
        self.assertIn("CANON_LOST", joined)
        self.assertIn("~/.dsh/AGENTS.md", joined)

    def test_rw010_symlink_to_canon_is_ok(self):
        """RW-010: контроль - user-global симлинк на канон даёт безопасный результат (exit 0)."""
        result = self.check()
        self.assertIsNotNone(result)
        self.assertEqual(result.exit_code, 0, result.reasons)

    def test_rw010_identical_regular_copy_is_ok(self):
        """RW-010: контроль - обычный файл с байт-в-байт тем же содержимым допустим."""
        self.ug.unlink()
        self.ug.write_bytes(self.canon.read_bytes())
        result = self.check()
        self.assertIsNotNone(result)
        self.assertEqual(result.exit_code, 0, result.reasons)

    def test_rw010_deleted_user_global_is_canon_lost(self):
        """RW-010: ~/.dsh/AGENTS.md удалён -> CANON_LOST, а не синтезированная копия канона."""
        self.ug.unlink()
        self.assert_canon_lost(self.check())

    def test_rw010_modified_content_is_canon_lost(self):
        """RW-010: содержимое user-global отличается от канона -> CANON_LOST."""
        self.ug.unlink()
        self.ug.write_text("чужое содержимое\n", encoding="utf-8")
        self.assert_canon_lost(self.check())

    def test_rw010_retargeted_symlink_is_canon_lost(self):
        """RW-010: симлинк перенацелен на другой файл с тем же содержимым -> CANON_LOST (цель симлинка важна)."""
        other = self.root / "other-canon.md"
        other.write_bytes(self.canon.read_bytes())
        self.ug.unlink()
        self.ug.symlink_to(other)
        self.assert_canon_lost(self.check())

    def test_rw010_cwd_without_project_canon_and_without_user_global_is_not_ok(self):
        """RW-010: cwd без проектной копии канона и без user-global не даёт guard=ok."""
        self.ug.unlink()
        result = self.check([("DW", str(self.fs["cwds"]["DW"]))])
        self.assert_canon_lost(result)
        self.assertTrue(result is None or result.exit_code != 0)

    def test_rw010_dangling_symlink_is_canon_lost(self):
        """RW-010: висячий симлинк user-global (цель удалена) -> CANON_LOST."""
        self.ug.unlink()
        self.ug.symlink_to(self.root / "no-such-file.md")
        self.assert_canon_lost(self.check())


# -- RW-020: профиль DSH ---------------------------------------------------------------------------------

class TestRw020Profile(unittest.TestCase):
    """RW-020: профиль с неоднозначным maxBytes нечитаем (maxbytes None), валидный разбирается."""

    def yml(self, old=None, new=None):
        text = PROFILE_YML % 106496
        if old is not None:
            self.assertIn(old, text)
            text = text.replace(old, new, 1)
        return text

    def test_rw020_valid_profile_still_parses(self):
        """RW-020: эталонный профиль даёт 106496."""
        self.assertEqual(bg.parse_profile_maxbytes(self.yml()), 106496)

    def test_rw020_duplicate_maxbytes_is_unreadable(self):
        """RW-020: два maxBytes у agent-instructions -> None."""
        text = self.yml("          maxBytes: 106496\n", "          maxBytes: 106496\n          maxBytes: 4096\n")
        self.assertIsNone(bg.parse_profile_maxbytes(text))

    def test_rw020_duplicate_agent_instructions_key_is_unreadable(self):
        """RW-020: второй плагин agent-instructions в preset-standard -> None."""
        text = self.yml("      - id: tool-bash\n",
                        "      - id: agent-instructions\n        config:\n          maxBytes: 4096\n"
                        "      - id: tool-bash\n")
        self.assertIsNone(bg.parse_profile_maxbytes(text))

    def test_rw020_stray_maxbytes_in_other_plugin_is_unreadable(self):
        """RW-020: maxBytes в чужом плагине внутри preset-standard -> None."""
        text = self.yml("          prefix: x\n", "          prefix: x\n          maxBytes: 5\n")
        self.assertIsNone(bg.parse_profile_maxbytes(text))

    def test_rw020_stray_maxbytes_at_preset_level_is_unreadable(self):
        """RW-020: maxBytes на уровне config пресета (вне пути плагина) -> None."""
        text = self.yml("    id: standard\n", "    id: standard\n    maxBytes: 5\n")
        self.assertIsNone(bg.parse_profile_maxbytes(text))

    def test_rw020_nested_maxbytes_under_agent_instructions_is_unreadable(self):
        """RW-020: вложенный дополнительный maxBytes под agent-instructions -> None."""
        text = self.yml("          maxBytes: 106496\n",
                        "          maxBytes: 106496\n          extra:\n            maxBytes: 4096\n")
        self.assertIsNone(bg.parse_profile_maxbytes(text))

    def test_rw020_duplicate_preset_standard_is_unreadable(self):
        """RW-020: второй пресет preset-standard с другим значением -> None."""
        text = self.yml() + ("- id: preset-standard\n  config:\n    plugins:\n      - id: agent-instructions\n"
                             "        config:\n          maxBytes: 262144\n")
        self.assertIsNone(bg.parse_profile_maxbytes(text))

    def test_rw020_find_profiles_reports_none_for_ambiguous_profile(self):
        """RW-020: find_profiles возвращает maxBytes None (сервер считает профиль небезопасным)."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "web"
            target.mkdir()
            text = self.yml("          maxBytes: 106496\n", "          maxBytes: 106496\n          maxBytes: 4096\n")
            (target / bg.PROFILE_FILE).write_text(text, encoding="utf-8")
            self.assertEqual(bg.find_profiles(tmp), [("web", str(target / bg.PROFILE_FILE), None)])


# -- RW-011/RW-012: пробы droid_image на сценарном RPC ----------------------------------------------------

def settings(**over):
    """Read-back настроек сессии; DROP убирает поле."""
    base = {"modelId": MODEL, "reasoningEffort": EFFORT, "autonomyLevel": "high"}
    base.update(over)
    return {k: v for k, v in base.items() if v is not DROP}


def note(payload):
    return {"notification": {"type": "settings_updated", "settings": payload}}


class ScriptedRpc:
    """Подмена droid_image._Rpc: ответы call() и очередь wait_settings задаются сценарием, процесса нет."""

    def __init__(self, replies, queued=None):
        self.replies = replies
        self.queued = queued
        self.protocol = "1.2.3"
        self.waited = 0

    def call(self, method, params, timeout=0.0):
        result, notes = self.replies[method]
        return dict(result), list(notes)

    def wait_settings(self, timeout=5.0):
        self.waited += 1
        if self.queued is None:
            raise droid_image.ProbeError("update_session_settings: read-back settings_updated не получен")
        return self.queued

    def close(self):
        pass


def scripted(init=None, update=None, load=None, in_notes=False, no_readback=False):
    """Сценарий проб: update-read-back приходит через очередь (по умолчанию) или уже в notes call()."""
    upd = settings(disabledToolIds=IDS) if update is None else update
    notes = [note(upd)] if in_notes else []
    replies = {
        "droid.initialize_session": ({"sessionId": "sid-1", "settings": settings() if init is None else init}, []),
        "droid.list_tools": ({"tools": [{"id": i} for i in IDS]}, []),
        "droid.update_session_settings": ({}, [] if no_readback else notes),
        "droid.load_session": ({"session": {"messages": []},
                                "settings": settings() if load is None else load}, []),
    }
    return ScriptedRpc(replies, None if (in_notes or no_readback) else upd)


class ProbeCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.workspace = self.tmp / "workspace"

    def probes(self, rpc):
        with mock.patch.object(droid_image, "_Rpc", lambda image, cwd, home: rpc):
            return droid_image.run_probes(self.tmp / "droid", self.workspace)

    def install(self, rpc):
        source = self.tmp / "source-droid"
        source.write_bytes(b"scripted-image")
        source.chmod(0o755)
        with mock.patch.object(droid_image, "_Rpc", lambda image, cwd, home: rpc):
            return droid_image.install_image(source, self.workspace)

    def receipt_path(self):
        return self.workspace / "state" / "droid-binary-receipt.json"


class TestRw011ReadbackFromNotes(ProbeCase):
    """RW-011: settings_updated, уже вернувшийся в notes из call(), не теряется."""

    def test_rw011_settings_updated_before_result_is_accepted(self):
        """RW-011: порядок settings_updated -> result (нотификация осталась в notes) квалифицируется."""
        rpc = scripted(in_notes=True)
        facts = self.probes(rpc)
        self.assertEqual(facts["disabled_tool_ids"], IDS)
        self.assertEqual(rpc.waited, 0)

    def test_rw011_settings_updated_after_result_is_accepted(self):
        """RW-011: порядок result -> settings_updated (нотификация в очереди) квалифицируется."""
        rpc = scripted()
        self.assertEqual(self.probes(rpc)["disabled_tool_ids"], IDS)
        self.assertEqual(rpc.waited, 1)

    def test_rw011_missing_readback_raises_and_writes_no_receipt(self):
        """RW-011: read-back нет ни в notes, ни в очереди -> ProbeError, receipt не записан."""
        with self.assertRaises(droid_image.ProbeError):
            self.install(scripted(no_readback=True))
        self.assertFalse(self.receipt_path().exists())

    def test_rw011_wrong_readback_in_notes_raises_and_writes_no_receipt(self):
        """RW-011: read-back в notes не подтверждает отключение tools -> ProbeError, receipt не записан."""
        with self.assertRaises(droid_image.ProbeError):
            self.install(scripted(update=settings(disabledToolIds=["Read"]), in_notes=True))
        self.assertFalse(self.receipt_path().exists())

    def test_rw011_wrong_readback_in_queue_raises_and_writes_no_receipt(self):
        """RW-011: read-back из очереди не подтверждает отключение tools -> ProbeError, receipt не записан."""
        with self.assertRaises(droid_image.ProbeError):
            self.install(scripted(update=settings(disabledToolIds=[])))
        self.assertFalse(self.receipt_path().exists())


class TestRw012VerifiedProfile(ProbeCase):
    """RW-012: receipt подтверждает фактический read-back, а не желаемый профиль."""

    SUBSTITUTIONS = (
        ("reasoningEffort", "low"),
        ("autonomyLevel", "off"),
        ("interactionMode", "spec"),
        ("disableBuiltinSkills", False),
        ("autoRejectPermissionRequests", False),
    )

    def test_rw012_initialize_substitution_raises(self):
        """RW-012: подмена любого сообщённого параметра при initialize -> ProbeError."""
        for key, value in self.SUBSTITUTIONS:
            with self.subTest(key=key, value=value):
                with self.assertRaises(droid_image.ProbeError):
                    self.probes(scripted(init=settings(**{key: value})))

    def test_rw012_initialize_without_effort_or_autonomy_raises(self):
        """RW-012: initialize без reasoningEffort/autonomyLevel в read-back не подтверждает профиль."""
        for key in ("reasoningEffort", "autonomyLevel"):
            with self.subTest(key=key):
                with self.assertRaises(droid_image.ProbeError):
                    self.probes(scripted(init=settings(**{key: DROP})))

    def test_rw012_update_readback_substitution_raises(self):
        """RW-012: подмена в read-back update_session_settings -> ProbeError."""
        for key, value in self.SUBSTITUTIONS:
            for in_notes in (False, True):
                with self.subTest(key=key, value=value, in_notes=in_notes):
                    with self.assertRaises(droid_image.ProbeError):
                        self.probes(scripted(update=settings(disabledToolIds=IDS, **{key: value}),
                                             in_notes=in_notes))

    def test_rw012_load_substitution_raises(self):
        """RW-012: подмена в settings load_session -> ProbeError."""
        for key, value in self.SUBSTITUTIONS:
            with self.subTest(key=key, value=value):
                with self.assertRaises(droid_image.ProbeError):
                    self.probes(scripted(load=settings(**{key: value})))

    def test_rw012_non_boolean_flag_is_rejected(self):
        """RW-012: флаг безопасности 1 вместо true не считается подтверждением."""
        with self.assertRaises(droid_image.ProbeError):
            self.probes(scripted(init=settings(disableBuiltinSkills=1)))

    def test_rw012_substitution_leaves_no_receipt(self):
        """RW-012: при подмене receipt не записывается."""
        with self.assertRaises(droid_image.ProbeError):
            self.install(scripted(init=settings(reasoningEffort="low")))
        self.assertFalse(self.receipt_path().exists())

    def test_rw012_receipt_marks_fields_without_readback(self):
        """RW-012: поля, которых droid не сообщает, записаны как not_confirmed_readback; ключи профиля прежние."""
        import server
        receipt = self.install(scripted())
        readback = receipt["settings_profile"]["readback"]
        self.assertEqual(readback["confirmed"], ["autonomyLevel", "modelId", "reasoningEffort"])
        self.assertEqual(readback["not_confirmed_readback"],
                         ["autoRejectPermissionRequests", "disableBuiltinSkills", "interactionMode"])
        self.assertEqual(receipt["settings_profile"]["profile"], server.SETTINGS_PROFILE)
        self.assertEqual(receipt["settings_profile"]["digest"], server.settings_profile_digest())
        self.assertEqual(receipt["schema"], 2)
        server._check_receipt_quad(receipt)

    def test_rw012_receipt_confirms_reported_flags(self):
        """RW-012: сообщённые и верные флаги/interactionMode попадают в confirmed."""
        full = settings(interactionMode="auto", disableBuiltinSkills=True, autoRejectPermissionRequests=True)
        receipt = self.install(scripted(init=full))
        readback = receipt["settings_profile"]["readback"]
        self.assertEqual(readback["not_confirmed_readback"], [])
        self.assertEqual(readback["confirmed"], sorted(
            ["modelId", "reasoningEffort", "autonomyLevel", "interactionMode",
             "disableBuiltinSkills", "autoRejectPermissionRequests"]))
        self.assertTrue(self.receipt_path().exists())
        stored = json.loads(self.receipt_path().read_text(encoding="utf-8"))
        self.assertEqual(stored["settings_profile"]["readback"], readback)


class TestRw012FakeImage(RpcCase):
    """RW-012: те же проверки на настоящем subprocess (tests/fake_droid.py)."""

    def setUp(self):
        super().setUp()
        import server
        self.server = server
        self.source = Path(self._tmp.name) / "global-droid"
        self.source.write_bytes(self.hub.launcher.read_bytes())
        self.source.chmod(0o755)

    def test_rw012_fake_image_records_unreported_fields(self):
        """RW-012: fake droid не сообщает флаги/interactionMode -> они в not_confirmed_readback."""
        receipt = droid_image.install_image(self.source, self.server.WORKSPACE)
        readback = receipt["settings_profile"]["readback"]
        self.assertEqual(readback["confirmed"], ["autonomyLevel", "modelId", "reasoningEffort"])
        self.assertIn("disableBuiltinSkills", readback["not_confirmed_readback"])
        self.assertIn("autoRejectPermissionRequests", readback["not_confirmed_readback"])

    def test_rw012_fake_image_echoing_true_flags_confirms_them(self):
        """RW-012: droid сообщает флаги true -> они подтверждены."""
        self.hub.configure(echo_flags=True)
        receipt = droid_image.install_image(self.source, self.server.WORKSPACE)
        confirmed = receipt["settings_profile"]["readback"]["confirmed"]
        self.assertIn("disableBuiltinSkills", confirmed)
        self.assertIn("autoRejectPermissionRequests", confirmed)

    def test_rw012_fake_image_reporting_false_flag_is_rejected(self):
        """RW-012: droid сообщает autoRejectPermissionRequests=false -> ProbeError, receipt не записан."""
        self.hub.configure(echo_flags=True, flags_override={"autoRejectPermissionRequests": False})
        with self.assertRaises(droid_image.ProbeError):
            droid_image.install_image(self.source, self.server.WORKSPACE)
        self.assertFalse(self.server._receipt_path().exists())


# -- RW-013: receipt_schema без моста ---------------------------------------------------------------------

class TestRw013ReceiptSchema(unittest.TestCase):
    """RW-013: общие константы и отпечатки живут в tools/receipt_schema.py и не требуют server.py/fleet.json."""

    def run_py(self, code, cwd, env=None):
        return subprocess.run([sys.executable, "-c", code], cwd=str(cwd), stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=120,
                              env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", **(env or {})))

    def test_rw013_schema_values_and_digests_equal_server(self):
        """RW-013: константы и отпечатки receipt_schema те же объекты, что видит server.py."""
        import receipt_schema as schema
        import server
        self.assertEqual(schema.RPC_API_VERSION, server.RPC_API_VERSION)
        self.assertEqual(schema.RECEIPT_SCHEMA, 2)
        self.assertEqual(schema.RECEIPT_SCHEMA, server.RECEIPT_SCHEMA)
        self.assertEqual(schema.TOOLS_POLICY, server.TOOLS_POLICY)
        self.assertEqual(schema.SETTINGS_PROFILE, server.SETTINGS_PROFILE)
        self.assertEqual(schema.RECEIPT_PROBES, server.RECEIPT_PROBES)
        self.assertIs(server.tools_policy_digest, schema.tools_policy_digest)  # мост берёт отпечатки из общего модуля
        self.assertIs(server.settings_profile_digest, schema.settings_profile_digest)
        self.assertEqual(schema.tools_policy_digest(["Read", "Execute"]), server.tools_policy_digest(["Execute", "Read"]))
        self.assertEqual(schema.settings_profile_digest(), server.settings_profile_digest())

    def test_rw013_exported_names(self):
        """RW-013: модуль экспортирует согласованный набор имён."""
        import receipt_schema as schema
        for name in ("RPC_API_VERSION", "RECEIPT_SCHEMA", "TOOLS_POLICY", "SETTINGS_PROFILE", "RECEIPT_PROBES",
                     "json_digest", "tools_policy_digest", "settings_profile_digest"):
            self.assertTrue(hasattr(schema, name), name)

    def test_rw013_droid_image_import_does_not_load_server(self):
        """RW-013: после import droid_image в чистом процессе модуль server не загружен."""
        code = ("import sys; sys.path.insert(0, %r); import droid_image; "
                "sys.stdout.write('server' if 'server' in sys.modules else 'clean')" % str(ROOT / "tools"))
        with tempfile.TemporaryDirectory() as tmp:
            proc = self.run_py(code, tmp)
        self.assertEqual(proc.stdout.decode("utf-8", "replace").strip(), "clean")

    def test_rw013_qualification_runs_without_fleet_json_or_server(self):
        """RW-013: пробы и receipt работают в раскладке без server.py; fleet.json отсутствует либо повреждён."""
        from bridge_testlib import FakeDroidHub
        for fleet in (None, "{broken json"):
            with self.subTest(fleet=fleet), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                tools = base / "tools"
                tools.mkdir()
                for name in ("droid_image.py", "receipt_schema.py"):
                    shutil.copy(ROOT / "tools" / name, tools / name)
                if fleet is not None:
                    (base / "fleet.json").write_text(fleet, encoding="utf-8")
                hub = FakeDroidHub(base / "fake")
                workspace = base / "workspace"
                proc = subprocess.run(
                    [sys.executable, str(tools / "droid_image.py"), "--source", str(hub.launcher),
                     "--workspace", str(workspace)],
                    cwd=str(base), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120,
                    env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", FAKE_DROID_DIR=str(hub.base)))
                text = proc.stdout.decode("utf-8", "replace")
                self.assertEqual(proc.returncode, 0, text)
                receipt = json.loads((workspace / "state" / "droid-binary-receipt.json").read_text(encoding="utf-8"))
                self.assertEqual(receipt["schema"], 2)
                self.assertIn("readback", receipt["settings_profile"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
