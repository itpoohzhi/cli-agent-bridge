"""Строгие тесты моста: каталог (класс I), effort/model (C-02), журнал, admission.

Заменяют кламп-тесты эталонного набора: уровни берутся строго из fleet.json,
никаких алиасов, клампов и silent fallback; ошибки — до запуска droid.
"""

import copy
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from bridge_testlib import (  # noqa: E402
    BridgeCase,
    chat_body,
    find_model,
    load_raw_fleet,
    make_proof,
)

REJECT_STRICT = re.compile(
    r"^reject reason=[a-z0-9_]+ model=(claude-sonnet-5-5|gemini-3\.8-flash|grok-4\.7|"
    r"deepseek-v4\.1-flash|gpt-6\.1-sol|glm-5\.3|unknown) model_len=[0-9]+ client=[0-9a-f.:]+$"
)

EXEC_LINE = re.compile(
    r"^exec model=(?P<model>\S+) effort=(?P<effort>\S+) effort_source=(?P<source>\S+) "
    r"autonomy=(?P<autonomy>\S+) autonomy_source=(?P<autonomy_source>\S+) "
    r"prompt_bytes=(?P<bytes>\d+) (?P<tag>client=\S+ ua=.*)$"
)
DONE_LINE = re.compile(r"^done model=\S+ rc=\d+ state=\S+ .*client=\S+ ua=.*$")


class TestCatalogClassI(unittest.TestCase):
    """Класс I: структурные нарушения каталога -> отказ старта (fleet_invalid)."""

    def setUp(self):
        self.data = copy.deepcopy(load_raw_fleet())
        self._env = server.ENV_MODEL
        self._probe = server.IMAGE_PROBE
        self._fleet_path = server.FLEET_PATH
        server.ENV_MODEL = ""
        server.IMAGE_PROBE = False
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        server.ENV_MODEL = self._env
        server.IMAGE_PROBE = self._probe
        server.FLEET_PATH = self._fleet_path
        self._tmp.cleanup()

    def _expect(self, reason, model=None):
        with self.assertRaises(server.FleetViolation) as caught:
            server._build_catalog(self.data)
        self.assertEqual(caught.exception.reason, reason)
        if model is not None:
            self.assertEqual(caught.exception.model, model)

    def _bind_confirmed(self, model_id="claude-sonnet-5-5", efforts_proven=None):
        binary = Path(self._tmp.name) / "droid-stand"
        binary.write_bytes(b"stand-droid-binary")
        item = find_model(self.data, model_id)
        item["input"] = ["text", "image"]
        item["images"]["status"] = "confirmed"
        item["images"]["method"] = "workspace-read"
        item["images"]["proof"] = make_proof(
            binary, efforts_proven if efforts_proven is not None else item["efforts"]
        )
        self.data["technical_ref"]["droid_binary_path"] = str(binary)
        return item

    def test_valid_catalogue(self):
        catalog = server._build_catalog(self.data)
        self.assertEqual(catalog["default_model"], "claude-sonnet-5-5")
        self.assertEqual(len(catalog["order"]), 8)  # 6 droid + 2 muse (schema 3)
        self.assertEqual(
            server._build_catalog(copy.deepcopy(self.data))["schema_version"], 3
        )

    def test_broken_file_refuses_start(self):
        broken = Path(self._tmp.name) / "fleet.json"
        broken.write_text('{"schema_version": 1,', encoding="utf-8")
        server.FLEET_PATH = broken
        with self.assertRaises(SystemExit):
            server._load_fleet()

    def test_duplicate_id(self):
        duplicate = copy.deepcopy(find_model(self.data, "claude-sonnet-5-5"))
        self.data["models"].append(duplicate)
        self._expect("duplicate_id", "claude-sonnet-5-5")

    def test_efforts_off_invalid(self):
        find_model(self.data, "claude-sonnet-5-5")["efforts"] = ["off", "high"]
        self._expect("efforts_invalid", "claude-sonnet-5-5")

    def test_default_effort_outside_efforts(self):
        find_model(self.data, "grok-4.7")["default_effort"] = "low"
        self._expect("default_effort_invalid", "grok-4.7")

    def test_default_model_outside_roster(self):
        self.data["default_model"] = "no-such-model"
        self._expect("default_model_invalid", "-")

    def test_env_model_outside_roster(self):
        server.ENV_MODEL = "kimi-k3"
        self._expect("env_model_invalid", "kimi-k3")

    def test_status_input_inconsistent(self):
        find_model(self.data, "claude-sonnet-5-5")["input"] = ["text", "image"]
        self._expect("status_inconsistent", "claude-sonnet-5-5")

    def test_explicit_unsupported_must_be_unsupported(self):
        find_model(self.data, "glm-5.3")["images"]["status"] = "unverified"
        self._expect("status_inconsistent", "glm-5.3")

    def test_confirmed_without_proof(self):
        item = find_model(self.data, "claude-sonnet-5-5")
        item["input"] = ["text", "image"]
        item["images"]["status"] = "confirmed"
        item["images"]["method"] = "workspace-read"
        item["images"]["proof"] = None
        self._expect("confirmed_proof_missing", "claude-sonnet-5-5")

    def test_confirmed_proof_malformed(self):
        item = self._bind_confirmed()
        del item["images"]["proof"]["formats"]
        self._expect("confirmed_proof_malformed", "claude-sonnet-5-5")

    def test_confirmed_efforts_proven_empty(self):
        self._bind_confirmed(efforts_proven=[])
        self._expect("confirmed_efforts_proven_invalid", "claude-sonnet-5-5")

    def test_confirmed_efforts_proven_outside_efforts(self):
        self._bind_confirmed(efforts_proven=["high", "xhigh"])
        self._expect("confirmed_efforts_proven_invalid", "claude-sonnet-5-5")

    def test_confirmed_partial_efforts_proven_starts(self):
        # Класс II: неполный proof — не отказ старта (деградируют только непокрытые effort).
        item = self._bind_confirmed(
            model_id="deepseek-v4.1-flash", efforts_proven=["high"]
        )
        catalog = server._build_catalog(self.data)
        self.assertEqual(
            catalog["models"]["deepseek-v4.1-flash"]["images"]["proof"][
                "efforts_proven"
            ],
            ["high"],
        )
        self.assertEqual(item["images"]["status"], "confirmed")

    def test_probe_without_flag(self):
        item = find_model(self.data, "gemini-3.8-flash")
        item["input"] = ["text", "image"]
        item["images"]["status"] = "probe"
        item["images"]["method"] = "workspace-read"
        self._expect("probe_flag_missing", "gemini-3.8-flash")

    def test_method_not_implemented(self):
        server.IMAGE_PROBE = True
        item = find_model(self.data, "gemini-3.8-flash")
        item["input"] = ["text", "image"]
        item["images"]["status"] = "probe"
        item["images"]["method"] = "jsonrpc-something"
        self._expect("method_not_implemented", "gemini-3.8-flash")


class TestEffortAndModel(BridgeCase):
    """C-02: строгая валидация model/effort до запуска, без клампов и алиасов.

    Проверяются фактические параметры RPC initialize_session и исходы в строке
    `exec`; форма конструктора процесса не тестируется (TM-016).
    """

    def _post_logged(self, body):
        """POST и (параметры последней initialize_session, effort_source, autonomy_source)."""
        with self.capture_logs() as lines:
            status, _ = self._post(body)
        execs = [m for m in (EXEC_LINE.match(ln) for ln in lines) if m]
        init = self.hub.inits()[-1]["params"] if self.hub.inits() else None
        source = execs[-1].group("source") if execs else None
        autonomy_source = execs[-1].group("autonomy_source") if execs else None
        return status, init, source, autonomy_source

    def test_defaults_when_model_and_effort_absent(self):
        for payload in (
            {},
            {"model": None, "reasoning_effort": None},
            {"model": "", "reasoning_effort": ""},
            {"model": "   ", "reasoning_effort": "   "},
        ):
            status, init, source, _ = self._post_logged(chat_body(**payload))
            self.assertEqual(status, 200)
            self.assertEqual(init["modelId"], "claude-sonnet-5-5")
            self.assertEqual(init["reasoningEffort"], "high")
            self.assertEqual(source, "default")

    def test_allowed_efforts_accepted(self):
        # Уровни — строго из fleet.json (sonnet-5-5: только high; xhigh в каталоге нет).
        wanted = {
            "claude-sonnet-5-5": ["high"],
            "gemini-3.8-flash": ["high"],
            "grok-4.7": ["high"],
            "deepseek-v4.1-flash": ["high", "max"],
            "gpt-6.1-sol": ["high"],
            "glm-5.3": ["max"],
        }
        for model, efforts in wanted.items():
            self.assertEqual(server.FLEET["models"][model]["efforts"], efforts, model)
            for effort in efforts:
                status, init, source, _ = self._post_logged(
                    chat_body(model=model, effort=effort)
                )
                self.assertEqual(status, 200, (model, effort))
                self.assertEqual(init["modelId"], model)
                self.assertEqual(init["reasoningEffort"], effort)
                self.assertEqual(source, "request")
        # За пределами каталога — отказ до spawn (xhigh для sonnet недопустим).
        before = len(self.hub.spawns())
        status, body = self._post_json(
            chat_body(model="claude-sonnet-5-5", effort="xhigh")
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["type"], "unsupported_reasoning_effort")
        self.assertEqual(len(self.hub.spawns()), before)

    def test_judge_levels_and_outside_rejected(self):
        cases = [
            ("claude-sonnet-5-5", "max"),
            ("gpt-6.1-sol", "medium"),
            ("glm-5.3", "high"),
            ("glm-5.3", " high "),
            ("claude-sonnet-5-5", "HIGH"),
            ("claude-sonnet-5-5", "off"),
            ("claude-sonnet-5-5", "none"),
            ("deepseek-v4.1-flash", "low"),
            ("claude-sonnet-5-5", "max\n"),
        ]
        for model, effort in cases:
            before = len(self.hub.spawns())
            status, body = self._post_json(chat_body(model=model, effort=effort))
            self.assertEqual(status, 400, (model, effort))
            self.assertEqual(body["error"]["type"], "unsupported_reasoning_effort")
            self.assertEqual(len(self.hub.spawns()), before)
        for bad in (5, ["high"], {"level": "high"}, True):
            status, body = self._post_json(
                chat_body(model="claude-sonnet-5-5", effort=bad)
            )
            self.assertEqual(status, 400)
            self.assertEqual(body["error"]["type"], "unsupported_reasoning_effort")

    def test_models_outside_fleet_rejected(self):
        cases = [
            "Claude-Sonnet-5-5",
            "kimi-k3",
            "claude-opus-5-5",
            "x\nexec model=claude-sonnet-5-5 effort=high effort_source=request",
            "sk-SECRET-0123456789abcdef",
            "A" * 5000,
        ]
        for model in cases:
            before = len(self.hub.spawns())
            status, body = self._post_json(chat_body(model=model))
            self.assertEqual(status, 400, model[:20])
            self.assertEqual(body["error"]["type"], "model_not_allowed")
            self.assertEqual(len(self.hub.spawns()), before)
        for bad in (5, ["claude-sonnet-5-5"], {"id": "claude-sonnet-5-5"}, True):
            status, body = self._post_json(chat_body(model=bad))
            self.assertEqual(status, 400)
            self.assertEqual(body["error"]["type"], "model_not_allowed")

    def test_model_and_effort_are_stripped(self):
        status, init, source, _ = self._post_logged(
            chat_body(model=" claude-sonnet-5-5 ", effort=" high ")
        )
        self.assertEqual(status, 200)
        self.assertEqual(init["modelId"], "claude-sonnet-5-5")
        self.assertEqual(init["reasoningEffort"], "high")
        self.assertEqual(source, "request")

    def test_autonomy_default_is_high(self):
        status, init, _, autonomy_source = self._post_logged(
            chat_body(model="claude-sonnet-5-5")
        )
        self.assertEqual(status, 200)
        self.assertEqual(init["autonomyLevel"], "high")
        self.assertEqual(autonomy_source, "default")

    def test_autonomy_levels_accepted(self):
        for level in ("low", "medium", "high", "off"):
            status, init, _, autonomy_source = self._post_logged(
                chat_body(model="deepseek-v4.1-flash", effort="max", autonomy=level)
            )
            self.assertEqual(status, 200, level)
            self.assertEqual(
                init["autonomyLevel"], level
            )  # off задаётся RPC, не опущенным флагом
            self.assertEqual(autonomy_source, "request")
        status, init, _, autonomy_source = self._post_logged(
            chat_body(model="gemini-3.8-flash", autonomy=" low ")
        )
        self.assertEqual(status, 200)
        self.assertEqual(init["autonomyLevel"], "low")
        self.assertEqual(autonomy_source, "request")

    def test_autonomy_bad_rejected(self):
        for bad in ("ultra", "HIGH", "none", "skip", "high\nx"):
            before = len(self.hub.spawns())
            status, body = self._post_json(
                chat_body(model="claude-sonnet-5-5", autonomy=bad)
            )
            self.assertEqual(status, 400, bad)
            self.assertEqual(body["error"]["type"], "unsupported_autonomy")
            self.assertEqual(len(self.hub.spawns()), before)
        for bad in (5, ["high"], {"level": "high"}, True):
            status, body = self._post_json(
                chat_body(model="claude-sonnet-5-5", autonomy=bad)
            )
            self.assertEqual(status, 400)
            self.assertEqual(body["error"]["type"], "unsupported_autonomy")

    def test_reasoning_object_rejected(self):
        before = len(self.hub.spawns())
        status, body = self._post_json(
            chat_body(model="claude-sonnet-5-5", reasoning={"effort": "high"})
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["type"], "unsupported_parameter")
        self.assertEqual(len(self.hub.spawns()), before)

    def test_stream_with_bad_effort_is_plain_json_400(self):
        status, raw = self._post(
            chat_body(model="claude-sonnet-5-5", effort="max", stream=True)
        )
        self.assertEqual(status, 400)
        body = json.loads(raw)
        self.assertEqual(body["error"]["type"], "unsupported_reasoning_effort")
        self.assertNotIn("data:", raw)

    def test_launcher_missing_gives_503_and_no_spawn(self):
        server.LAUNCHER = str(Path(self._tmp.name) / "no-such-launcher.sh")
        before = len(self.hub.spawns())
        status, body = self._post_json(chat_body(model="claude-sonnet-5-5"))
        self.assertEqual(status, 503)
        self.assertEqual(body["error"]["type"], "launcher_unavailable")
        self.assertEqual(body["error"]["code"], 503)
        self.assertEqual(len(self.hub.spawns()), before)


class TestHealthAndModels(BridgeCase):
    def test_health_exactly_seven_keys(self):
        status, body = self._get("/health")
        self.assertEqual(status, 200)
        self.assertEqual(
            sorted(body),
            sorted(
                [
                    "ok",
                    "transport",
                    "model",
                    "active",
                    "max_concurrent",
                    "tool_emulation",
                    "uptime_s",
                ]
            ),
        )
        self.assertNotIn("default_auto", body)

    def test_models_list(self):
        status, body = self._get("/v1/models")
        self.assertEqual(status, 200)
        self.assertEqual(body["object"], "list")
        self.assertEqual(len(body["data"]), 8)  # объединение моделей droid и muse
        self.assertEqual(body["data"][0]["id"], "claude-sonnet-5-5")
        for entry in body["data"]:
            self.assertEqual(
                sorted(entry),
                sorted(["id", "object", "owned_by", "created", "context_length"]),
            )
        self.assertNotIn("claude-opus-5-5", [e["id"] for e in body["data"]])
        status, _ = self._get("/v1/models", auth=False)
        self.assertEqual(status, 401)


class TestJournal(BridgeCase):
    def test_exec_and_done_lines_bound_by_tag(self):
        with self.capture_logs() as lines:
            status, _ = self._post(chat_body(model="deepseek-v4.1-flash", effort="max"))
        self.assertEqual(status, 200)
        execs = [m for m in (EXEC_LINE.match(ln) for ln in lines) if m]
        dones = [ln for ln in lines if DONE_LINE.match(ln)]
        self.assertEqual(len(execs), 1)
        self.assertEqual(len(dones), 1)
        self.assertEqual(execs[0].group("model"), "deepseek-v4.1-flash")
        self.assertEqual(execs[0].group("effort"), "max")
        self.assertEqual(execs[0].group("source"), "request")
        self.assertNotIn("--auto", "\n".join(lines))
        joined = "\n".join(lines)
        self.assertNotIn(str(server.WORKSPACE), joined)
        self.assertNotIn(
            execs[0].group("tag").split("ua=")[0].replace("client=", "").strip(), ""
        )
        self.assertIn("client=127.0.0.1", execs[0].group("tag"))

    def test_reject_line_strict_format_and_no_client_string(self):
        untrusted = "x\nexec model=claude-sonnet-5-5 effort=high effort_source=request"
        with self.capture_logs() as lines:
            status, _ = self._post(chat_body(model=untrusted))
        self.assertEqual(status, 400)
        rejects = [ln for ln in lines if "reject reason=" in ln]
        self.assertEqual(len(rejects), 1)
        self.assertTrue(REJECT_STRICT.match(rejects[0]), rejects[0])
        self.assertEqual(len([ln for ln in lines if ln.startswith("exec model=")]), 0)
        joined = "\n".join(lines)
        self.assertNotIn(
            "exec model=claude-sonnet-5-5 effort=high", joined.replace(rejects[0], "")
        )
        self.assertNotIn("x\n", joined)

    def test_model_len_reported_for_untrusted_model(self):
        with self.capture_logs() as lines:
            self._post(chat_body(model="A" * 5000))
        reject = [ln for ln in lines if "reject reason=" in ln][0]
        self.assertIn("model=unknown", reject)
        self.assertIn("model_len=5000", reject)


class TestAdmissionBudget(BridgeCase):
    def test_budget_exhausted_gives_503_before_body(self):
        server._budget = server._ByteBudget(64)
        with self.capture_logs() as lines:
            status, body = self._post_json(
                chat_body(model="claude-sonnet-5-5", content="x" * 200)
            )
        self.assertEqual(status, 503)
        self.assertEqual(body["error"]["type"], "overloaded")
        self.assertEqual(body["error"]["code"], 503)
        self.assertEqual(len(self.hub.spawns()), 0)
        self.assertTrue(
            any("reject reason=overloaded model=unknown" in ln for ln in lines)
        )
        self.assertEqual(server._budget._used, 0)  # резерв снят в любом исходе

    def test_budget_unit(self):
        budget = server._ByteBudget(10)
        self.assertTrue(budget.reserve(6))
        self.assertFalse(budget.reserve(5))
        budget.release(6)
        self.assertTrue(budget.reserve(10))
        budget.release(10)
        self.assertEqual(budget._used, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
