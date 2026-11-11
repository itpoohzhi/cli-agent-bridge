"""fleet.json schema 3: парсинг backends, привязка моделей, совместимость со schema 2 (AC-001)."""
from __future__ import annotations
import copy
import contextlib
import importlib
import io
import json
import os
import sys
import tempfile
import time
import types
import unittest
from hashlib import sha256
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from adapters import ADAPTER_KINDS  # noqa: E402

FLEET_FILE = Path(server.ROOT) / "fleet.json"

# Неизменные поля оставшихся droid-моделей (значения schema 2, снимок до хаба).
DROID_MODELS = {
    "claude-sonnet-5-5": (1000000, ["high"]),
    "gemini-3.8-flash": (1048576, ["high"]),
    "deepseek-v4.1-flash": (1000000, ["high", "max"]),
    "glm-5.3": (1000000, ["max"]),
}
MUSE_MODELS = (
    "muse-spark-1.3",
    "muse-spark-1.3-contributor",
    "muse-wonder-1.0",
    "muse-wonder-full-1.0",
)


def raw_v3():
    return json.loads(FLEET_FILE.read_text(encoding="utf-8"))


def to_schema_2(data):
    data = copy.deepcopy(data)
    data["schema_version"] = 2
    data["default_model"] = "claude-sonnet-5-5"
    data.pop("backends", None)
    data["models"] = [
        {
            "id": mid,
            "name": f"{mid} (Droid legacy)",
            "efforts": list(efforts),
            "default_effort": efforts[0],
            "context_window": window,
            "max_tokens": 128000,
            "input": ["text"],
            "images": {
                "cli_registry": "implicit_supported",
                "status": "unverified",
                "method": None,
                "proof": None,
            },
        }
        for mid, (window, efforts) in DROID_MODELS.items()
    ]
    return data


class TestLiveFleetV3(unittest.TestCase):
    def test_live_catalogue_is_schema_3_with_eight_backends(self):
        catalog = server._build_catalog(raw_v3())
        self.assertEqual(catalog["schema_version"], 3)
        self.assertEqual(catalog["backend_order"], ["opencode-go-claude", "agy", "claude-p", "codex", "muse", "opencode-go", "droid", "opencode-zen"])
        self.assertEqual(catalog["backends"]["droid"]["kind"], "droid")
        self.assertTrue(catalog["backends"]["droid"]["enabled"])
        self.assertEqual(catalog["backends"]["droid"]["max_concurrent"], 64)
        self.assertFalse(catalog["backends"]["droid"]["required"])
        muse = catalog["backends"]["muse"]
        self.assertEqual(muse["kind"], "muse")
        self.assertTrue(muse["enabled"])
        self.assertEqual(muse["wrapper"], "~/.config/muse-launch/muse-cli.sh")
        self.assertEqual(muse["max_concurrent"], 64)
        codex = catalog["backends"]["codex"]
        self.assertEqual(codex["kind"], "passthrough")
        self.assertTrue(codex["enabled"])
        self.assertEqual(codex["base_url"], "http://127.0.0.1:2455/v1")

    def test_local_bridges_are_registered_as_passthrough(self):
        """ADR 0015: agy :9887, opencode-zen :9883, claude-p :9881 заведены passthrough-бэкендами
        (необязательными; выключены, пока не перечислены их модели)."""
        catalog = server._build_catalog(raw_v3())
        for name, port in (("agy", 9887), ("opencode-zen", 9883), ("claude-p", 9881)):
            backend = catalog["backends"][name]
            self.assertEqual(backend["kind"], "passthrough", name)
            self.assertEqual(backend["base_url"], "http://127.0.0.1:%d/v1" % port, name)
            self.assertFalse(backend["required"], name)
            self.assertTrue(
                backend["enabled"], name
            )  # ADR 0017: passthrough-бэкенды включены

    def test_default_model_is_muse_wonder_full(self):
        """ADR 0015: умолчание каталога - активная модель muse, а не выводимый Droid."""
        catalog = server._build_catalog(raw_v3())
        self.assertEqual(catalog["default_model"], "muse-wonder-full-1.0")
        self.assertEqual(catalog["models"]["muse-wonder-full-1.0"]["backend"], "muse")
        self.assertEqual(server.FLEET["default_model"], "muse-wonder-full-1.0")

    def test_models_are_bound_to_backends(self):
        data = raw_v3()
        catalog = server._build_catalog(data)
        self.assertEqual(len(catalog["order"]), len(data["models"]))
        self.assertEqual(len(catalog["order"]), 28)
        self.assertEqual(catalog["models"]["claude-sonnet-5-5"]["backend"], "claude-p")
        self.assertEqual(catalog["models"]["gemini-3.8-flash"]["backend"], "agy")
        self.assertEqual(catalog["models"]["gpt-6.1-sol"]["backend"], "codex")
        for model_id in ("claude-sonnet-5-5-droid", "gemini-3.8-flash-droid", "gpt-6.1-sol-droid"):
            self.assertEqual(catalog["models"][model_id]["backend"], "droid")
        self.assertEqual(catalog["models"]["deepseek-v4.1-flash"]["backend"], "opencode-go")
        self.assertNotIn("kimi-k3.1-pro", catalog["models"])
        for mid in MUSE_MODELS:
            model = catalog["models"][mid]
            self.assertEqual(model["backend"], "muse")
            if mid in ("muse-wonder-1.0", "muse-wonder-full-1.0"):
                self.assertEqual(
                    model["efforts"], ["minimal", "low", "medium", "high", "max"]
                )
                self.assertEqual(model["default_effort"], "high")
            else:
                self.assertEqual(model["efforts"], ["max"])
                self.assertEqual(model["default_effort"], "max")

    def test_subscription_droid_models_are_published(self):
        catalog = server._build_catalog(raw_v3())
        self.assertEqual(
            sum(m["backend"] == "droid" for m in catalog["models"].values()), 3
        )
        self.assertTrue(raw_v3()["backends"]["droid"]["enabled"])
        self.assertEqual(catalog["default_model"], "muse-wonder-full-1.0")
        self.assertNotIn("grok-4.7", catalog["models"])
        self.assertNotIn("glm-5.3", catalog["models"])

    def test_technical_ref_and_limits_preserved(self):
        catalog = server._build_catalog(raw_v3())
        self.assertTrue(catalog["technical_ref"]["droid_binary_path"])
        self.assertEqual(catalog["admission"]["max_http_connections"], 128)
        self.assertEqual(catalog["admission"]["max_inflight_body_bytes"], 536870912)

    def test_load_fleet_reads_schema_3_file(self):
        catalog = server._build_catalog(raw_v3())
        self.assertEqual(catalog["schema_version"], 3)
        self.assertEqual(len(catalog["order"]), len(raw_v3()["models"]))
        self.assertEqual(len(catalog["order"]), 28)


class TestSchema2Compat(unittest.TestCase):
    def test_schema_2_is_single_implicit_droid_backend(self):
        catalog = server._build_catalog(to_schema_2(raw_v3()))
        self.assertEqual(catalog["schema_version"], 2)
        self.assertEqual(catalog["backend_order"], ["droid"])
        self.assertTrue(catalog["backends"]["droid"]["enabled"])
        self.assertTrue(catalog["backends"]["droid"]["required"])
        self.assertEqual(len(catalog["order"]), len(DROID_MODELS))
        for model in catalog["models"].values():
            self.assertEqual(model["backend"], "droid")

    def test_schema_2_file_loads_through_load_fleet(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fleet.json"
            path.write_text(json.dumps(to_schema_2(raw_v3())), encoding="utf-8")
            saved = server.FLEET_PATH
            server.FLEET_PATH = path
            try:
                catalog = server._load_fleet()
            finally:
                server.FLEET_PATH = saved
        self.assertEqual(catalog["schema_version"], 2)
        self.assertEqual(catalog["order"], list(DROID_MODELS))

    def test_schema_2_with_backends_section_is_refused(self):
        data = to_schema_2(raw_v3())
        data["backends"] = raw_v3()["backends"]
        self.expect(data, "backends_in_schema_2")

    def test_unknown_schema_refused(self):
        for value in (1, 4, "3", True, None):
            data = raw_v3()
            data["schema_version"] = value
            self.expect(data, "schema_version_invalid")

    def expect(self, data, reason, model=None):
        with self.assertRaises(server.FleetViolation) as caught:
            server._build_catalog(data)
        self.assertEqual(caught.exception.reason, reason)
        if model is not None:
            self.assertEqual(caught.exception.model, model)


class TestSchema3Violations(unittest.TestCase):
    def expect(self, mutate, reason, model=None):
        data = raw_v3()
        mutate(data)
        with self.assertRaises(server.FleetViolation) as caught:
            server._build_catalog(data)
        self.assertEqual(caught.exception.reason, reason)
        if model is not None:
            self.assertEqual(caught.exception.model, model)

    def find(self, data, mid):
        return next(m for m in data["models"] if m["id"] == mid)

    def test_unknown_backend_kind_cannot_be_configured(self):
        self.expect(
            lambda d: d["backends"]["muse"].update(kind="exec-template"),
            "backend_kind_unknown",
            "muse",
        )

    def test_model_without_or_with_unknown_backend(self):
        self.expect(
            lambda d: self.find(d, "claude-sonnet-5-5").pop("backend"),
            "model_backend_unknown",
            "claude-sonnet-5-5",
        )
        self.expect(
            lambda d: self.find(d, "claude-sonnet-5-5").update(backend="ghost"),
            "model_backend_unknown",
            "claude-sonnet-5-5",
        )

    def test_unknown_keys_are_refused_not_dropped(self):
        self.expect(lambda d: d.update(surprise=1), "fleet_key_unknown")
        self.expect(
            lambda d: d["backends"]["muse"].update(command="rm -rf /"),
            "backend_key_unknown",
            "muse",
        )
        self.expect(
            lambda d: self.find(d, "claude-sonnet-5-5").update(extra=1),
            "model_key_unknown",
            "claude-sonnet-5-5",
        )

    def test_backend_field_validation(self):
        self.expect(
            lambda d: d["backends"]["muse"].update(max_concurrent=0),
            "backend_max_concurrent_invalid",
        )
        self.expect(
            lambda d: d["backends"]["muse"].update(max_concurrent=True),
            "backend_max_concurrent_invalid",
        )
        self.expect(
            lambda d: d["backends"]["muse"].update(enabled="yes"), "backend_invalid"
        )
        self.expect(
            lambda d: d["backends"]["muse"].update(required="no"), "backend_invalid"
        )
        self.expect(lambda d: d.update(backends={}), "backends_invalid")
        self.expect(lambda d: d.pop("backends"), "backends_invalid")

    def test_backend_nested_types_refused_before_registration(self):
        """RW-005: вложенные типы (technical_ref, wrapper, proxy_port) — отказ до регистрации.

        Раньше `technical_ref: ["bad"]` доезжал до `qualify()` и падал AttributeError на .get();
        теперь запись проверяется общим с сервером и fleet_check валидатором.
        """
        self.expect(
            lambda d: d["backends"]["muse"].update(technical_ref=["bad"]),
            "backend_technical_ref_invalid",
            "muse",
        )
        self.expect(
            lambda d: d["backends"]["muse"].update(technical_ref={}),
            "backend_technical_ref_incomplete",
            "muse",
        )
        self.expect(
            lambda d: d["backends"]["muse"].update(
                technical_ref={"binary_path": "~/.local/bin/muse"}
            ),
            "backend_technical_ref_incomplete",
            "muse",
        )
        self.expect(
            lambda d: d["backends"]["muse"].update(
                technical_ref={"binary_sha256": "0" * 64}
            ),
            "backend_technical_ref_incomplete",
            "muse",
        )
        self.expect(
            lambda d: d["backends"]["muse"].update(
                technical_ref={
                    "binary_path": "~/.local/bin/muse",
                    "binary_sha256": "zz",
                }
            ),
            "backend_technical_ref_incomplete",
            "muse",
        )
        self.expect(
            lambda d: d["backends"]["muse"].update(
                technical_ref={
                    "binary_path": "~/.local/bin/muse",
                    "binary_sha256": "0" * 64,
                    "surprise": 1,
                }
            ),
            "backend_technical_ref_invalid",
            "muse",
        )
        self.expect(
            lambda d: d["backends"]["muse"].pop("technical_ref"),
            "backend_technical_ref_missing",
            "muse",
        )
        self.expect(
            lambda d: d["backends"]["muse"].update(proxy_port=0),
            "backend_proxy_port_invalid",
            "muse",
        )
        self.expect(
            lambda d: d["backends"]["muse"].update(proxy_port=65536),
            "backend_proxy_port_invalid",
            "muse",
        )
        self.expect(
            lambda d: d["backends"]["muse"].update(proxy_port="10816"),
            "backend_proxy_port_invalid",
            "muse",
        )
        self.expect(
            lambda d: d["backends"]["muse"].update(proxy_port=True),
            "backend_proxy_port_invalid",
            "muse",
        )
        self.expect(
            lambda d: d["backends"]["muse"].update(wrapper=""),
            "backend_wrapper_invalid",
        )
        self.expect(
            lambda d: d["backends"]["muse"].update(wrapper=7), "backend_wrapper_invalid"
        )
        # Явный null/не-dict в technical_ref отвергается и у droid: поле присутствует, но неверного типа.
        self.expect(
            lambda d: d["backends"]["droid"].update(technical_ref=None),
            "backend_technical_ref_invalid",
            "droid",
        )
        # Droid-запись без ключа technical_ref допустима: pin обязателен только для muse.
        data = raw_v3()
        data["backends"]["droid"].pop("technical_ref", None)
        server._build_catalog(data)

    def test_complete_pin_and_proxy_port_accepted(self):
        data = raw_v3()
        data["backends"]["muse"]["proxy_port"] = 10816
        catalog = server._build_catalog(data)
        ref = catalog["backends"]["muse"]["technical_ref"]
        self.assertTrue(ref["binary_path"])
        self.assertEqual(len(ref["binary_sha256"]), 64)

    def test_duplicate_model_id_across_backends(self):
        def dup(d):
            clone = copy.deepcopy(self.find(d, "claude-sonnet-5-5"))
            clone["backend"] = "muse"
            d["models"].append(clone)

        self.expect(dup, "duplicate_id", "claude-sonnet-5-5")

    def test_disabled_backend_models_are_not_published(self):
        data = raw_v3()
        data["backends"]["muse"]["enabled"] = False
        data["backends"]["codex"]["enabled"] = False
        data["default_model"] = "claude-sonnet-5-5"
        catalog = server._build_catalog(data)
        published_backends = {catalog["models"][m]["backend"] for m in catalog["order"]}
        self.assertNotIn("muse", published_backends)
        self.assertNotIn("codex", published_backends)
        self.assertFalse(catalog["backends"]["muse"]["enabled"])

    def test_default_model_on_disabled_backend_is_refused(self):
        def mutate(d):
            d["backends"]["muse"]["enabled"] = False
            d["default_model"] = "muse-spark-1.3"

        self.expect(mutate, "default_model_invalid")

    def test_no_enabled_backend(self):
        def mutate(d):
            for entry in d["backends"].values():
                entry["enabled"] = False

        self.expect(mutate, "backends_none_enabled")

    def test_muse_model_effort_is_validated_like_any_other(self):
        self.expect(
            lambda d: self.find(d, "muse-spark-1.3").update(efforts=["ultra"]),
            "efforts_invalid",
            "muse-spark-1.3",
        )
        self.expect(
            lambda d: self.find(d, "muse-spark-1.3").update(default_effort="high"),
            "default_effort_invalid",
            "muse-spark-1.3",
        )

    def test_efforts_off_valid_and_unknown_level_invalid(self) -> None:
        data = raw_v3()
        self.find(data, "muse-spark-1.3").update(efforts=["off"], default_effort="off")
        self.assertEqual(
            server._build_catalog(data)["models"]["muse-spark-1.3"]["efforts"], ["off"]
        )
        self.expect(
            lambda d: self.find(d, "muse-spark-1.3").update(efforts=["bogus"]),
            "efforts_invalid",
            "muse-spark-1.3",
        )


def _import_fleet_check():
    """Импорт fleet_check; PyYAML в .venv отсутствует — для проверки каталога хватает заглушки."""
    root = str(Path(server.ROOT))
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        import yaml  # noqa: F401
    except ModuleNotFoundError:
        shim = types.ModuleType("yaml")

        class _Loader:
            @classmethod
            def add_multi_constructor(cls, prefix, fn):
                return None

        vars(shim).update(SafeLoader=_Loader, YAMLError=ValueError, load=lambda *a, **k: None)
        sys.modules["yaml"] = shim
    import fleet_check  # noqa: E402

    return fleet_check


class TestFleetCheckParity(unittest.TestCase):
    """RW-005: fleet_check и сервер принимают/отвергают одно множество backend-записей."""

    @classmethod
    def setUpClass(cls):
        cls.fleet_check = _import_fleet_check()

    def catalogue_errors(self, data):
        report = self.fleet_check.Report()
        self.fleet_check.check_catalogue(data, report)
        for check in report.checks:
            if check["name"] == "catalogue":
                return check["errors"]
        return []

    def test_kind_registry_is_shared_with_server(self):
        self.assertIs(self.fleet_check.ADAPTER_KINDS, ADAPTER_KINDS)

    def test_live_catalogue_has_no_catalogue_errors(self):
        self.assertEqual(self.catalogue_errors(raw_v3()), [])

    def test_same_backend_mutations_are_refused(self):
        cases = [
            (
                "technical_ref_list",
                lambda d: d["backends"]["muse"].update(technical_ref=["bad"]),
                "backend_technical_ref_invalid",
            ),
            (
                "pin_incomplete",
                lambda d: d["backends"]["muse"].update(
                    technical_ref={"binary_path": "~/.local/bin/muse"}
                ),
                "backend_technical_ref_incomplete",
            ),
            (
                "pin_missing",
                lambda d: d["backends"]["muse"].pop("technical_ref"),
                "backend_technical_ref_missing",
            ),
            (
                "proxy_port_range",
                lambda d: d["backends"]["muse"].update(proxy_port=70000),
                "backend_proxy_port_invalid",
            ),
            (
                "enabled_string",
                lambda d: d["backends"]["muse"].update(enabled="yes"),
                "backend_invalid",
            ),
            (
                "max_concurrent_zero",
                lambda d: d["backends"]["muse"].update(max_concurrent=0),
                "backend_max_concurrent_invalid",
            ),
            (
                "unknown_key",
                lambda d: d["backends"]["muse"].update(command="rm -rf /"),
                "backend_key_unknown",
            ),
            (
                "unknown_kind",
                lambda d: d["backends"]["muse"].update(kind="codex"),
                "backend_kind_unknown",
            ),
        ]
        for name, mutate, reason in cases:
            with self.subTest(name=name):
                data = raw_v3()
                mutate(data)
                errors = self.catalogue_errors(data)
                self.assertTrue(
                    any(reason in error for error in errors), (name, errors)
                )
                with self.assertRaises(server.FleetViolation) as caught:
                    server._build_catalog(data)
                self.assertEqual(caught.exception.reason, reason, name)

    def test_full_catalogue_fail_closed_parity(self):
        cases = (
            (lambda d: d.update(surprise=1), "fleet_key_unknown"),
            (lambda d: d["models"][0].update(surprise=1), "model_key_unknown"),
            (lambda d: d["models"][0].update(backend=[]), "model_backend_unknown"),
            (
                lambda d: d["backends"]["muse"].update(enabled=False),
                "default_model_invalid",
            ),
            (
                lambda d: [b.update(enabled=False) for b in d["backends"].values()],
                "backends_none_enabled",
            ),
            (
                lambda d: d["backends"]["muse"].update(
                    tool_policy={"disable_shell": True}
                ),
                "backend_key_unknown",
            ),
            (
                lambda d: d["backends"]["muse"].update(transport=[]),
                "backend_key_unknown",
            ),
            (
                lambda d: d["backends"]["muse"].update(max_concurrent=0),
                "backend_max_concurrent_invalid",
            ),
        )
        for mutate, reason in cases:
            with self.subTest(reason=reason):
                data = raw_v3()
                mutate(data)
                errors = self.catalogue_errors(data)
                self.assertTrue(any(reason in e for e in errors), errors)
                with self.assertRaises(server.FleetViolation) as caught:
                    server._build_catalog(data)
                self.assertEqual(caught.exception.reason, reason)
        data = to_schema_2(raw_v3())
        data["backends"] = None
        self.assertTrue(
            any("backends_in_schema_2" in e for e in self.catalogue_errors(data))
        )
        with self.assertRaises(server.FleetViolation):
            server._build_catalog(data)

    def test_mainline_muse_is_default_and_published(self):
        data = raw_v3()
        self.assertTrue(data["backends"]["muse"]["enabled"])
        catalog = server._build_catalog(data)
        self.assertEqual(len(catalog["order"]), len(data["models"]))
        self.assertEqual(len(catalog["order"]), 28)
        self.assertEqual(catalog["default_model"], "muse-wonder-full-1.0")

    def test_checker_main_returns_structured_error_for_invalid_model(self):
        data = raw_v3()
        data["models"][0] = []
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = self.fleet_check.main(["--catalogue", str(path)])
        self.assertEqual(code, 1)
        result = json.loads(output.getvalue())
        self.assertFalse(result["ok"])
        self.assertIn("model_invalid", result["checks"][0]["errors"][0])


class _CredentialsReportRecorder:
    def __init__(self):
        self.calls = []

    def add(self, name, errs, details=None):
        self.calls.append((name, list(errs), details))


class TestProviderCredentialsCheck(unittest.TestCase):
    SECRET_A = "sk-test-SECRET-aaaaaaaaaaaaaaaa"
    SECRET_B = "sk-test-SECRET-bbbbbbbbbbbbbbbb"
    SECRET_SHELL = "sk-test-SECRET-shell-cccccccccc"
    KEY = "DSH_TEST_FLEET_KEY_A"
    NOT_PI = "DSH_TEST_FLEET_NOT_PI"
    tmp = Path()

    @classmethod
    def setUpClass(cls):
        root = str(Path(__file__).resolve().parents[1])
        if root not in sys.path:
            sys.path.insert(0, root)
        cls.fc = importlib.import_module("fleet_check")

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    @staticmethod
    def lines(*parts):
        return "\n".join(parts) + "\n"

    @staticmethod
    def full_digest(value):
        return sha256(value.encode("utf-8")).hexdigest()

    def digest8(self, value):
        return self.full_digest(value)[:8]

    def write(self, name, text):
        path = self.tmp / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def profiles(self, *names):
        providers = [{"id": n, "type": "llm-pi-ai", "apiKeyEnv": n} for n in names]
        providers.append({"id": "other", "type": "openai", "apiKeyEnv": self.NOT_PI})
        return {"desktop": {"providers": providers}, "web": {}}

    def check(self, env_lines, refs_values, environ=None, profiles=None):
        env_path = self.write(".env", self.lines(*env_lines))
        refs_lines = ["  %s: %s" % kv for kv in refs_values]
        creds_path = self.write("credentials.yaml", self.lines("refs:", *refs_lines))
        report = _CredentialsReportRecorder()
        self.fc.check_provider_credentials(
            profiles or self.profiles(self.KEY),
            env_path,
            creds_path,
            report,
            environ={} if environ is None else environ,
        )
        self.assertEqual(len(report.calls), 1)
        name, errs, details = report.calls[0]
        self.assertEqual(name, "provider_credentials")
        return errs, {v["name"]: v for v in details["variables"]}

    def run_main(self, argv, names=None, env_vars=None):
        catalogue = self.write("catalogue.json", "{}")
        profile = self.profiles(*(names or (self.KEY,)))["desktop"]
        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch.multiple(
                self.fc,
                check_catalogue=mock.DEFAULT,
                droid_scope=mock.MagicMock(side_effect=lambda cat: cat),
                check_policy=mock.DEFAULT,
                check_efforts=mock.DEFAULT,
                check_profile=mock.MagicMock(return_value=profile),
                check_default_compat=mock.DEFAULT,
                check_opus=mock.DEFAULT,
            ),
            mock.patch.dict(os.environ, env_vars or {}),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            code = self.fc.main(["--catalogue", catalogue] + argv)
        return code, out.getvalue(), err.getvalue()

    def cli_files(self, env_value, refs_value):
        env_path = self.write(
            ".env", self.lines("export %s='%s'" % (self.KEY, env_value))
        )
        creds_path = self.write(
            "credentials.yaml",
            self.lines("refs:", "  %s: %s" % (self.KEY, refs_value)),
        )
        return env_path, creds_path

    def assert_no_secrets(self, *texts):
        for text in texts:
            for secret in (self.SECRET_A, self.SECRET_B, self.SECRET_SHELL):
                self.assertNotIn(secret, text)
                self.assertNotIn(self.full_digest(secret), text)

    def test_status_ok(self):
        errs, found = self.check(
            ["%s=%s" % (self.KEY, self.SECRET_A)], [(self.KEY, self.SECRET_A)]
        )
        self.assertEqual(errs, [])
        item = found[self.KEY]
        self.assertEqual(item["status"], "ok")
        self.assertEqual(item["env_sha256_8"], self.digest8(self.SECRET_A))
        self.assertEqual(item["refs_sha256_8"], self.digest8(self.SECRET_A))
        self.assertNotIn(self.NOT_PI, found)

    def test_status_missing_in_env(self):
        for env_lines in (["OTHER_VAR=1"], ["%s=" % self.KEY]):
            with self.subTest(env_lines=env_lines):
                errs, found = self.check(env_lines, [(self.KEY, self.SECRET_A)])
                self.assertEqual(found[self.KEY]["status"], "missing_in_env")
                self.assertIn("%s: missing_in_env" % self.KEY, errs)

    def test_status_missing_in_refs(self):
        env_lines = ["%s=%s" % (self.KEY, self.SECRET_A)]
        for refs in ([], [("OTHER_VAR", "x")], [(self.KEY, '""')]):
            with self.subTest(refs=refs):
                errs, found = self.check(env_lines, refs)
                self.assertEqual(found[self.KEY]["status"], "missing_in_refs")
                self.assertIn("%s: missing_in_refs" % self.KEY, errs)

    def test_status_digest_mismatch(self):
        errs, found = self.check(
            ["%s=%s" % (self.KEY, self.SECRET_A)], [(self.KEY, self.SECRET_B)]
        )
        item = found[self.KEY]
        self.assertEqual(item["status"], "digest_mismatch")
        self.assertNotEqual(item["env_sha256_8"], item["refs_sha256_8"])
        self.assertIn("%s: digest_mismatch" % self.KEY, errs)

    def test_status_shadowed_by_environ(self):
        env_lines = ["%s=%s" % (self.KEY, self.SECRET_A)]
        refs = [(self.KEY, self.SECRET_A)]
        errs, found = self.check(env_lines, refs, environ={self.KEY: self.SECRET_SHELL})
        item = found[self.KEY]
        self.assertEqual(item["status"], "shadowed_by_environ")
        self.assertEqual(item["environ_sha256_8"], self.digest8(self.SECRET_SHELL))
        self.assertIn("%s: shadowed_by_environ" % self.KEY, errs)
        for same in ({self.KEY: self.SECRET_A}, {self.KEY: ""}):
            with self.subTest(environ=sorted(same)):
                errs, found = self.check(env_lines, refs, environ=same)
                self.assertEqual(errs, [])
                self.assertEqual(found[self.KEY]["status"], "ok")

    def test_collects_pi_providers_from_both_profiles(self):
        key_d, key_w = "DSH_TEST_FLEET_KEY_D", "DSH_TEST_FLEET_KEY_W"
        profiles = {
            "desktop": {"providers": [{"type": "llm-pi-ai", "apiKeyEnv": key_d}]},
            "web": {
                "llm-pi-ai": {"apiKeyEnv": key_w},
                "other": {"type": "openai", "apiKeyEnv": self.NOT_PI},
            },
        }
        errs, found = self.check(
            ["%s=%s" % (k, self.SECRET_A) for k in (key_d, key_w)],
            [(k, self.SECRET_A) for k in (key_d, key_w)],
            profiles=profiles,
        )
        self.assertEqual(errs, [])
        self.assertEqual(set(found), {key_d, key_w})

    def test_unreadable_files_are_reported_without_paths_or_content(self):
        report = _CredentialsReportRecorder()
        self.fc.check_provider_credentials(
            self.profiles(self.KEY),
            str(self.tmp / "absent.env"),
            str(self.tmp / "absent.yaml"),
            report,
            environ={},
        )
        _, errs, details = report.calls[0]
        self.assertIn("env_unreadable: FileNotFoundError", errs)
        self.assertIn("credentials_unreadable: FileNotFoundError", errs)
        self.assertEqual(details["variables"][0]["status"], "missing_in_env")

    def test_dotenv_parser_handles_quotes_export_and_comments(self):
        path = self.write(
            ".env",
            self.lines(
                "# comment",
                "",
                'export DSH_TEST_A="value a"',
                "DSH_TEST_B='value b'",
                "DSH_TEST_C=value-c # tail",
                "  DSH_TEST_D = spaced ",
                "no-equals-line",
                "DSH_TEST_E=",
            ),
        )
        self.assertEqual(
            self.fc._parse_dotenv(path),
            {
                "DSH_TEST_A": "value a",
                "DSH_TEST_B": "value b",
                "DSH_TEST_C": "value-c",
                "DSH_TEST_D": "spaced",
                "DSH_TEST_E": "",
            },
        )

    def test_credentials_parser_reads_only_refs_section(self):
        path = self.write(
            "credentials.yaml",
            self.lines(
                "version: 1",
                "refs:  # secrets",
                '  DSH_TEST_A: "value a"',
                "  'DSH_TEST_B': value-b",
                "    nested: ignored",
                "other:",
                "  DSH_TEST_C: nope",
            ),
        )
        self.assertEqual(
            self.fc._parse_credentials_refs(path),
            {"DSH_TEST_A": "value a", "DSH_TEST_B": "value-b"},
        )

    def test_report_contains_no_secret_values(self):
        errs, found = self.check(
            ["%s=%s" % (self.KEY, self.SECRET_A)],
            [(self.KEY, self.SECRET_B)],
            environ={self.KEY: self.SECRET_SHELL},
        )
        dump = json.dumps([errs, found])
        self.assert_no_secrets(dump)
        for item in found.values():
            for field in ("env_sha256_8", "refs_sha256_8", "environ_sha256_8"):
                self.assertTrue(item[field] is None or len(item[field]) == 8)

    def test_main_runs_check_with_env_and_credentials_flags(self):
        env_path, creds_path = self.cli_files(self.SECRET_A, self.SECRET_A)
        code, out, err = self.run_main(["--env", env_path, "--credentials", creds_path])
        self.assertEqual(code, 0, out)
        result = json.loads(out)
        self.assertTrue(result["ok"])
        self.assertIn("provider_credentials", out)
        self.assert_no_secrets(out, err)

    def test_main_reports_mismatch_without_leaking_secrets(self):
        env_path, creds_path = self.cli_files(self.SECRET_A, self.SECRET_B)
        code, out, err = self.run_main(["--env", env_path, "--credentials", creds_path])
        self.assertEqual(code, 1)
        result = json.loads(out)
        self.assertFalse(result["ok"])
        self.assertIn("digest_mismatch", out)
        self.assertIn(self.KEY, out)
        self.assert_no_secrets(out, err)

    def test_main_single_flag_takes_other_path_from_environment(self):
        env_path, creds_path = self.cli_files(self.SECRET_A, self.SECRET_A)
        code, out, err = self.run_main(
            ["--env", env_path], env_vars={"DSH_CREDENTIALS_PATH": creds_path}
        )
        self.assertEqual(code, 0, out)
        self.assertIn("provider_credentials", out)
        self.assert_no_secrets(out, err)

    def test_main_check_credentials_flag_uses_environment_defaults(self):
        env_path, creds_path = self.cli_files(self.SECRET_A, self.SECRET_B)
        code, out, err = self.run_main(
            ["--check-credentials"],
            env_vars={"DSH_ENV_PATH": env_path, "DSH_CREDENTIALS_PATH": creds_path},
        )
        self.assertEqual(code, 1)
        self.assertIn("digest_mismatch", out)
        self.assert_no_secrets(out, err)

    def test_main_without_flags_skips_credentials_check(self):
        code, out, err = self.run_main([])
        self.assertEqual(code, 0, out)
        self.assertNotIn("provider_credentials", out)

    def test_check_completes_within_200ms(self):
        names = ["DSH_TEST_FLEET_KEY_%02d" % i for i in range(20)]
        env_lines = ["%s=%s-%d" % (n, self.SECRET_A, i) for i, n in enumerate(names)]
        refs = [(n, "%s-%d" % (self.SECRET_A, i)) for i, n in enumerate(names)]
        start = time.perf_counter()
        errs, found = self.check(env_lines, refs, profiles=self.profiles(*names))
        elapsed = time.perf_counter() - start
        self.assertEqual(errs, [])
        self.assertEqual(len(found), 20)
        self.assertLessEqual(elapsed, 0.2)


if __name__ == "__main__":
    unittest.main()
