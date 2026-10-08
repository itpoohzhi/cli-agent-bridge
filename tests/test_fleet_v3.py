"""fleet.json schema 3: парсинг backends, привязка моделей, совместимость со schema 2 (AC-001)."""

import copy
import contextlib
import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from adapters import ADAPTER_KINDS  # noqa: E402

FLEET_FILE = Path(server.ROOT) / "fleet.json"

# Неизменные поля шести droid-моделей (значения schema 2, снимок до хаба).
DROID_MODELS = {
    "claude-sonnet-5-5": (1000000, ["high"]),
    "gemini-3.8-flash": (1048576, ["high"]),
    "grok-4.7": (256000, ["high"]),
    "deepseek-v4.1-flash": (1000000, ["high", "max"]),
    "gpt-6.1-sol": (272000, ["high"]),
    "glm-5.3": (1000000, ["max"]),
}
MUSE_MODELS = ("muse-spark-1.3", "muse-spark-1.3-contributor")


def raw_v3():
    return json.loads(FLEET_FILE.read_text(encoding="utf-8"))


def to_schema_2(data):
    data = copy.deepcopy(data)
    data["schema_version"] = 2
    data.pop("backends")
    data["models"] = [m for m in data["models"] if m["backend"] == "droid"]
    for model in data["models"]:
        model.pop("backend")
    return data


class TestLiveFleetV3(unittest.TestCase):
    def test_live_catalogue_is_schema_3_with_two_backends(self):
        catalog = server._build_catalog(raw_v3())
        self.assertEqual(catalog["schema_version"], 3)
        self.assertEqual(catalog["backend_order"], ["droid", "muse"])
        self.assertEqual(catalog["backends"]["droid"]["kind"], "droid")
        self.assertTrue(catalog["backends"]["droid"]["enabled"])
        muse = catalog["backends"]["muse"]
        self.assertEqual(muse["kind"], "muse")
        self.assertFalse(muse["enabled"])
        self.assertEqual(muse["wrapper"], "~/.config/muse-launch/muse-cli.sh")
        self.assertEqual(muse["max_concurrent"], 1)  # RW-001: ходы muse сериализованы

    def test_models_are_bound_to_backends(self):
        data = raw_v3()
        data["backends"]["muse"]["enabled"] = True
        catalog = server._build_catalog(data)
        self.assertEqual(len(catalog["order"]), 8)
        for mid in DROID_MODELS:
            self.assertEqual(catalog["models"][mid]["backend"], "droid")
        for mid in MUSE_MODELS:
            model = catalog["models"][mid]
            self.assertEqual(model["backend"], "muse")
            self.assertEqual(model["efforts"], ["max"])
            self.assertEqual(model["default_effort"], "max")

    def test_droid_models_unchanged(self):
        catalog = server._build_catalog(raw_v3())
        for mid, (window, efforts) in DROID_MODELS.items():
            self.assertEqual(catalog["models"][mid]["context_window"], window, mid)
            self.assertEqual(catalog["models"][mid]["efforts"], efforts, mid)
        self.assertEqual(catalog["order"][:6], list(DROID_MODELS))
        self.assertEqual(catalog["default_model"], "claude-sonnet-5-5")

    def test_technical_ref_and_limits_preserved(self):
        catalog = server._build_catalog(raw_v3())
        self.assertTrue(catalog["technical_ref"]["droid_binary_path"])
        self.assertEqual(catalog["admission"]["max_http_connections"], 32)

    def test_load_fleet_reads_schema_3_file(self):
        self.assertEqual(server.FLEET["schema_version"], 3)
        self.assertEqual(len(server.FLEET["order"]), 6)


class TestSchema2Compat(unittest.TestCase):
    def test_schema_2_is_single_implicit_droid_backend(self):
        catalog = server._build_catalog(to_schema_2(raw_v3()))
        self.assertEqual(catalog["schema_version"], 2)
        self.assertEqual(catalog["backend_order"], ["droid"])
        self.assertTrue(catalog["backends"]["droid"]["enabled"])
        self.assertTrue(catalog["backends"]["droid"]["required"])
        self.assertEqual(len(catalog["order"]), 6)
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
            lambda d: self.find(d, "grok-4.7").pop("backend"),
            "model_backend_unknown",
            "grok-4.7",
        )
        self.expect(
            lambda d: self.find(d, "grok-4.7").update(backend="ghost"),
            "model_backend_unknown",
            "grok-4.7",
        )

    def test_unknown_keys_are_refused_not_dropped(self):
        self.expect(lambda d: d.update(surprise=1), "fleet_key_unknown")
        self.expect(
            lambda d: d["backends"]["muse"].update(command="rm -rf /"),
            "backend_key_unknown",
            "muse",
        )
        self.expect(
            lambda d: self.find(d, "grok-4.7").update(extra=1),
            "model_key_unknown",
            "grok-4.7",
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
            clone = copy.deepcopy(self.find(d, "grok-4.7"))
            clone["backend"] = "muse"
            d["models"].append(clone)

        self.expect(dup, "duplicate_id", "grok-4.7")

    def test_disabled_backend_models_are_not_published(self):
        data = raw_v3()
        data["backends"]["muse"]["enabled"] = False
        catalog = server._build_catalog(data)
        self.assertEqual(catalog["order"], list(DROID_MODELS))
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

        shim.SafeLoader = _Loader
        shim.YAMLError = ValueError
        shim.load = lambda *args, **kwargs: None
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
                lambda d: (
                    d["backends"]["muse"].update(enabled=True),
                    d["backends"]["droid"].update(enabled=False),
                ),
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
                lambda d: d["backends"]["muse"].update(max_concurrent=2),
                "backend_muse_max_concurrent_invalid",
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

    def test_mainline_muse_is_dark(self):
        data = raw_v3()
        self.assertFalse(data["backends"]["muse"]["enabled"])
        self.assertEqual(server._build_catalog(data)["order"], list(DROID_MODELS))

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


if __name__ == "__main__":
    unittest.main()
