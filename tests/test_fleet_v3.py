"""fleet.json schema 3: парсинг backends, привязка моделей, совместимость со schema 2 (AC-001)."""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402

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
        self.assertTrue(muse["enabled"])
        self.assertEqual(muse["wrapper"], "~/.config/muse-launch/muse-cli.sh")
        self.assertEqual(muse["max_concurrent"], 2)

    def test_models_are_bound_to_backends(self):
        catalog = server._build_catalog(raw_v3())
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
        self.assertEqual(len(server.FLEET["order"]), 8)


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
        self.expect(lambda d: d.update(backends={}), "backends_invalid")
        self.expect(lambda d: d.pop("backends"), "backends_invalid")

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


if __name__ == "__main__":
    unittest.main()
