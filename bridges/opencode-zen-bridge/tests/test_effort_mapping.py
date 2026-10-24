"""Уровни мышления: ceil_clamp, карточки DSH и #variant CLI для всех 8 моделей × всех уровней."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import server
import zen_catalog as zc
from tests._fixtures import install_test_models, load_json

install_test_models(server)

GOLDEN = {e["id"]: e for e in load_json("golden_catalog.json")}
LEVELS = ["off", "none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"]


class CeilClampTest(unittest.TestCase):
    def test_examples_from_owner(self) -> None:
        values = ["low", "high", "max"]
        self.assertEqual(zc.ceil_clamp("medium", values), "high")
        self.assertEqual(zc.ceil_clamp("xhigh", values), "max")
        self.assertEqual(zc.ceil_clamp("minimal", values), "low")
        self.assertEqual(zc.ceil_clamp("ultra", values), "max")
        nemotron = ["none", "minimal", "low", "medium", "high", "xhigh"]
        self.assertEqual(zc.ceil_clamp("max", nemotron), "xhigh")
        self.assertEqual(zc.ceil_clamp("minimal", nemotron), "minimal")

    def test_never_returns_none_level(self) -> None:
        for level in ("minimal", "low", "medium", "high", "xhigh", "max", "ultra"):
            self.assertNotEqual(zc.ceil_clamp(level, ["none", "low"]), "none")

    def test_empty_thinking_set_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            zc.ceil_clamp("high", ["none"])
        self.assertIsNone(zc.variant_map([]))
        self.assertIsNone(zc.variant_map(["none"]))


class CardsMatchGoldenTest(unittest.TestCase):
    def test_reasoning_efforts_from_effort_values(self) -> None:
        for model_id, entry in GOLDEN.items():
            with self.subTest(model=model_id):
                self.assertEqual(zc.reasoning_efforts(entry["effort_values"]), entry["cordis"]["reasoningEfforts"])
                self.assertEqual(zc.variant_map(entry["effort_values"]), entry["bridge"]["variant_map"])

    def test_card_values_are_valid_variants(self) -> None:
        for model_id, entry in GOLDEN.items():
            values = entry["effort_values"]
            if not entry["bridge"]["supports_variant"]:
                continue
            for level, sent in entry["cordis"]["reasoningEfforts"].items():
                with self.subTest(model=model_id, level=level):
                    self.assertTrue(level == "off" and sent == "off" or sent in values, (level, sent))

    def test_models_without_variants_keep_identity(self) -> None:
        for model_id in ("mimo-v2.6-flash-free", "nemotron-3.5-lightning-free", "big-pickle"):
            efforts = GOLDEN[model_id]["cordis"]["reasoningEfforts"]
            self.assertEqual(efforts, {"off": "off", "low": "low", "medium": "medium",
                                       "high": "high", "xhigh": "xhigh", "max": "max"})
            self.assertFalse(GOLDEN[model_id]["bridge"]["supports_variant"])

    def test_minimal_key_only_when_model_declares_it(self) -> None:
        for model_id, entry in GOLDEN.items():
            self.assertEqual("minimal" in entry["cordis"]["reasoningEfforts"], "minimal" in entry["effort_values"], model_id)


class BridgeVariantMatrixTest(unittest.TestCase):
    """56 комбинаций (8 моделей × 7 уровней): variant ∈ effort_values или пусто, без `--variant`."""

    def setUp(self) -> None:
        models = zc.entries_to_bridge_models(zc.build_catalog(
            zc.api_models(load_json("api_fixture.json")), zc.zen_ids(load_json("zen_fixture.json"))))
        for patcher in (patch.object(server, "ALLOWED_MODELS", models), patch.object(server, "_log")):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_every_model_and_level(self) -> None:
        for model_id, entry in GOLDEN.items():
            for level in LEVELS:
                with self.subTest(model=model_id, level=level):
                    effort = server._map_effort({"model": model_id, "reasoning_effort": level}, model_id)
                    cmd, shown = server._build_cmd("/bin/echo", model_id, effort)
                    self.assertNotIn("--variant", cmd)
                    spec = cmd[cmd.index("-m") + 1]
                    base = f"opencode/{model_id}"
                    if entry["bridge"]["supports_variant"] and level not in ("off", "none"):
                        expected = entry["bridge"]["variant_map"][level]
                        self.assertIn(expected, entry["effort_values"])
                        self.assertEqual(spec, f"{base}#{expected}")
                        self.assertIn("--thinking", cmd)
                    else:
                        self.assertEqual(spec, base)
                        self.assertNotIn("--thinking", cmd)
                    self.assertIn(spec, shown)

    def test_owner_examples(self) -> None:
        def spec(model_id: str, level: str) -> str:
            effort = server._map_effort({"reasoning_effort": level}, model_id)
            return server._build_cmd("x", model_id, effort)[0][3]

        self.assertEqual(spec("deepseek-v4.1-flash-free", "medium"), "opencode/deepseek-v4.1-flash-free#high")
        self.assertEqual(spec("deepseek-v4.1-flash-free", "xhigh"), "opencode/deepseek-v4.1-flash-free#max")
        self.assertEqual(spec("nemotron-3.5-super-vl-free", "max"), "opencode/nemotron-3.5-super-vl-free#xhigh")
        self.assertEqual(spec("flint-40b-free", "high"), "opencode/flint-40b-free#high")
        self.assertEqual(spec("mimo-v2.6-flash-free", "high"), "opencode/mimo-v2.6-flash-free")

    def test_default_effort_goes_through_variant_map(self) -> None:
        self.assertEqual(server._map_effort({}, "deepseek-v4.1-flash-free"), "high")
        self.assertEqual(server._map_effort({}, "nemotron-3.5-super-vl-free"), "high")
        self.assertEqual(server._map_effort({"reasoning_effort": "garbage"}, "deepseek-v4.1-flash-free"), "high")

    def test_invalid_variant_is_dropped_with_warning(self) -> None:
        with patch.object(server, "_log") as log:
            self.assertEqual(server._variant_for("deepseek-v4.1-flash-free", "medium"), "")
            self.assertEqual(server._variant_for("deepseek-v4.1-flash-free", "high"), "high")
            self.assertEqual(server._variant_for("big-pickle", "high"), "")
        self.assertTrue(any("WARN" in c.args[0] for c in log.call_args_list))


if __name__ == "__main__":
    unittest.main()
