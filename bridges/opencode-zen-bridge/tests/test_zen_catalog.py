"""Чистые функции каталога: golden 8 моделей, фильтры, лимиты, состояние, границы модуля."""

from __future__ import annotations

import ast
import copy
import json
import tempfile
import unittest
from pathlib import Path

import zen_catalog as zc
from tests._fixtures import load_json

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = load_json("golden_catalog.json")
API = load_json("api_fixture.json")
ZEN = load_json("zen_fixture.json")


class GoldenCatalogTest(unittest.TestCase):
    def test_fixture_catalog_equals_golden(self) -> None:
        catalog = zc.build_catalog(zc.api_models(API), zc.zen_ids(ZEN))
        self.assertEqual(catalog, GOLDEN)

    def test_embedded_fallback_equals_golden(self) -> None:
        self.assertEqual(zc.STATIC_FALLBACK_CATALOG, GOLDEN)

    def test_golden_has_eight_models_sorted(self) -> None:
        ids = [e["id"] for e in GOLDEN]
        self.assertEqual(len(ids), 8)
        self.assertEqual(ids, sorted(ids))

    def test_limits_follow_min_context_input(self) -> None:
        by_id = {e["id"]: e["cordis"] for e in GOLDEN}
        self.assertEqual((by_id["big-pickle"]["contextWindow"], by_id["big-pickle"]["maxTokens"]), (160000, 32000))
        self.assertEqual(by_id["nemotron-3.5-lightning-free"]["maxTokens"], 262144)
        self.assertEqual(by_id["flint-40b-free"]["contextWindow"], 262144)

    def test_context_window_formula(self) -> None:
        self.assertEqual(zc.context_window({"context": 200000, "input": 160000}), 160000)
        self.assertEqual(zc.context_window({"context": 190000, "input": 192000}), 190000)
        self.assertEqual(zc.context_window({"context": 200000}), 200000)
        self.assertIsNone(zc.context_window({"input": 1}))
        self.assertIsNone(zc.context_window({"context": True}))

    def test_input_is_limited_by_bridge_modalities(self) -> None:
        model = {"modalities": {"input": ["text", "image", "video"]}}
        self.assertEqual(zc.card_input(model), ["text"])
        self.assertEqual(zc.card_input(model, ("text", "image")), ["text", "image"])
        self.assertEqual(zc.card_input({"modalities": {"input": ["video"]}}, ("text", "image")), ["text"])
        self.assertEqual(zc.card_input({}), ["text"])

    def test_card_names(self) -> None:
        names = {e["id"]: zc.card_name(e) for e in GOLDEN}
        self.assertEqual(names["beam-free"], "Beam (Zen)")
        self.assertEqual(names["deepseek-v4.1-flash-free"], "DeepSeek V4.1 Flash (Zen)")
        self.assertEqual(names["big-pickle"], "Big Pickle (Zen)")


class SelectionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.models = copy.deepcopy(zc.api_models(API))
        self.zen = set(zc.zen_ids(ZEN))

    def test_fixture_contains_non_matching_models(self) -> None:
        # Страховка фикстуры: без «плохих» моделей фильтры нечем проверять.
        self.assertIn("nemotron-3-ultra-free", self.models)
        self.assertNotIn("nemotron-3-ultra-free", self.zen)
        self.assertIn("minimax-m3.1-flash-free", self.models)
        self.assertTrue(any(zc.zen_ids(ZEN) & {"jev-1.13", "test"}))

    def test_active_requires_free_active_tool_call(self) -> None:
        base = {"cost": {"input": 0}, "tool_call": True}
        self.assertTrue(zc.is_active_free(base))
        self.assertFalse(zc.is_active_free({**base, "cost": {"input": 0.1}}))
        self.assertFalse(zc.is_active_free({**base, "status": "deprecated"}))
        self.assertFalse(zc.is_active_free({**base, "tool_call": False}))
        self.assertFalse(zc.is_active_free({"cost": {"input": 0}}))
        self.assertFalse(zc.is_active_free({**base, "cost": {"input": False}}))
        self.assertFalse(zc.is_active_free("not a dict"))

    def test_zen_intersection_and_denylist(self) -> None:
        self.models["jev-1.13"] = {"cost": {"input": 0}, "tool_call": True, "limit": {"context": 1, "output": 1}}
        self.models["not-in-zen-free"] = copy.deepcopy(self.models["beam-free"])
        zen = self.zen | {"jev-1.13"}
        active = zc.select_active(self.models, zen)
        self.assertNotIn("jev-1.13", active)
        self.assertNotIn("not-in-zen-free", active)
        self.assertNotIn("nemotron-3-ultra-free", active)
        self.assertEqual(len(active), 8)
        self.assertEqual(zc.DENYLIST, {"jev-1.13", "jev-1.13-free", "test", "claude-opus-5-5-backup"})

    def test_new_free_model_appears_without_code_change(self) -> None:
        self.models["fresh-free"] = copy.deepcopy(self.models["beam-free"])
        self.models["fresh-free"]["name"] = "Fresh Free"
        catalog = zc.build_catalog(self.models, self.zen | {"fresh-free"})
        self.assertIn("fresh-free", [e["id"] for e in catalog])
        self.assertEqual(len(catalog), 9)

    def test_deprecated_model_leaves_catalog(self) -> None:
        self.models["beam-free"]["status"] = "deprecated"
        self.assertNotIn("beam-free", zc.select_active(self.models, self.zen))

    def test_invalid_ids_and_limits_are_skipped(self) -> None:
        self.assertFalse(zc.valid_model_id("Bad Id"))
        self.assertFalse(zc.valid_model_id("a\nb"))
        self.assertFalse(zc.valid_model_id("-x"))
        self.assertFalse(zc.valid_model_id("x" * 65))
        self.assertTrue(zc.valid_model_id("a.b-c9"))
        broken = copy.deepcopy(self.models["beam-free"])
        broken["limit"] = {"context": 0, "output": 10}
        self.assertIsNone(zc.build_entry("broken-free", broken))
        self.assertIsNone(zc.build_entry("Bad Id", copy.deepcopy(self.models["beam-free"])))

    def test_zen_ids_accepts_both_payload_shapes(self) -> None:
        self.assertEqual(zc.zen_ids({"data": [{"id": "a"}, {"id": "b"}, {"x": 1}]}), {"a", "b"})
        self.assertEqual(zc.zen_ids(["a", "b"]), {"a", "b"})
        self.assertEqual(zc.zen_ids("garbage"), set())

    def test_api_models_tolerates_garbage(self) -> None:
        self.assertEqual(zc.api_models(None), {})
        self.assertEqual(zc.api_models({"opencode": []}), {})


class SafetyAndStateTest(unittest.TestCase):
    def test_shrink_violation(self) -> None:
        ids = [f"m{i}" for i in range(8)]
        self.assertIsNotNone(zc.shrink_violation([], ids))
        self.assertIsNotNone(zc.shrink_violation(ids[:3], ids))
        self.assertIsNone(zc.shrink_violation(ids[:4], ids))
        self.assertIsNone(zc.shrink_violation(ids, []))

    def test_state_roundtrip_and_validation(self) -> None:
        aliases, retired = zc.derive_aliases(zc.api_models(API), [e["id"] for e in GOLDEN], [], [])
        state = zc.make_state(GOLDEN, aliases, retired, degraded=False, generated_at="t", api_fetched=True, zen_fetched=True)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "zen-catalog.json"
            path.write_text(json.dumps(state), "utf-8")
            loaded = zc.load_state_file(path)
            assert loaded is not None
            self.assertEqual(loaded["active"], state["active"])
            self.assertEqual(loaded["aliases"], state["aliases"])
            path.write_text("{broken", "utf-8")
            self.assertIsNone(zc.load_state_file(path))
            path.write_text(json.dumps({**state, "models": []}), "utf-8")
            self.assertIsNone(zc.load_state_file(path))
            path.write_text(json.dumps({**state, "schema_version": 99}), "utf-8")
            self.assertIsNone(zc.load_state_file(path))
        self.assertIsNone(zc.load_state_file(Path(tmp) / "missing.json"))

    def test_parse_state_rejects_variant_model_without_map(self) -> None:
        state = zc.fallback_state()
        broken = copy.deepcopy(state)
        broken["models"][0]["bridge"]["variant_map"] = None
        self.assertEqual(broken["models"][0]["bridge"]["supports_variant"], True)
        self.assertIsNone(zc.parse_state(broken))

    def test_bridge_models_shape(self) -> None:
        models = zc.entries_to_bridge_models(GOLDEN)
        self.assertEqual(models["big-pickle"]["supports_variant"], False)
        self.assertNotIn("variant_map", models["big-pickle"])
        self.assertEqual(models["deepseek-v4.1-flash-free"]["variant_map"]["medium"], "high")
        self.assertEqual(models["deepseek-v4.1-flash-free"]["effort_values"], ["low", "high", "max"])
        self.assertEqual(models["nemotron-3.5-super-vl-free"]["reasoning_efforts"][:2], ["off", "minimal"])


class ModuleBoundaryTest(unittest.TestCase):
    """BND-001/BND-002 и NFR-01: границы импортов и синтаксис Python 3.9."""

    def _imports(self, name: str) -> set[str]:
        tree = ast.parse((ROOT / name).read_text("utf-8"))
        found: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module.split(".")[0])
        return found

    def test_zen_catalog_is_pure(self) -> None:
        imports = self._imports("zen_catalog.py")
        self.assertTrue(imports <= {"__future__", "json", "re", "typing"}, imports)

    def test_sync_has_no_yaml_dependency(self) -> None:
        imports = self._imports("sync_dsh_models.py")
        self.assertNotIn("yaml", imports)
        self.assertNotIn("ruamel", imports)

    def test_sources_parse_as_python_39(self) -> None:
        for name in ("zen_catalog.py", "sync_dsh_models.py", "server.py", "tests/live_matrix.py"):
            with self.subTest(file=name):
                ast.parse((ROOT / name).read_text("utf-8"), filename=name, feature_version=(3, 9))


if __name__ == "__main__":
    unittest.main()
