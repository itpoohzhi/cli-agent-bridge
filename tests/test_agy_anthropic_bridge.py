import ast
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from core.agy_anthropic_gate import ALLOWED_AGY_CLAUDE_IDS
from core.agy_anthropic_probe import AgyAnthropicProbe

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = ROOT / "bridges" / "agy-bridge" / "anthropic_runtime.py"
BRIDGE_FLEET_PATH = ROOT / "bridges" / "agy-bridge" / "fleet.json"
SERVER_PATH = ROOT / "bridges" / "agy-bridge" / "server.py"
ENABLED = {"BRIDGE_AGY_ANTHROPIC_ENABLED": "1"}

REAL_FORMAT_55_LIVE = (
    "\rFetching available models...\r"
    "Available models:\n"
    "  gemini-4-neon             Gemini 4 Neon\n"
    "  claude-sonnet-5-5-low     Claude Sonnet 5.5 (Low)\n"
    "  claude-sonnet-5-5-high    Claude Sonnet 5.5 (High)\n"
    "  claude-opus-5-5-thinking  Claude Opus 5.5 Thinking\n"
)


def load_runtime():
    spec = importlib.util.spec_from_file_location("agy_anthropic_runtime", RUNTIME_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {RUNTIME_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def snapshot(model_id, available=True, reason=""):
    return SimpleNamespace(
        available=available,
        upstream_model=model_id if available else None,
        reason=reason,
    )


class FakeProbe:
    def __init__(self, snapshots=None):
        self.snapshots = snapshots or {}
        self.calls = []

    def probe(self, model_id):
        self.calls.append(model_id)
        return self.snapshots.get(model_id, snapshot(model_id, False, "not_available"))


class AnthropicRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = load_runtime()

    def resolve_without_spawn(self, model_id, effort, probe, env):
        with (
            mock.patch.object(self.runtime, "spawn_registered", create=True) as spawn,
            mock.patch.object(self.runtime, "Run", create=True) as runner,
            mock.patch("subprocess.run") as subprocess_run,
            mock.patch("subprocess.Popen") as subprocess_popen,
        ):
            resolution = self.runtime.resolve_anthropic_turn(
                model_id, effort, probe, env=env
            )
        spawn.assert_not_called()
        runner.assert_not_called()
        subprocess_run.assert_not_called()
        subprocess_popen.assert_not_called()
        return resolution

    def test_feature_flag_off_by_default_and_truthy_parity(self):
        probe = FakeProbe({"claude-sonnet-5-5": snapshot("claude-sonnet-5-5")})
        resolution = self.resolve_without_spawn("claude-sonnet-5-5", "off", probe, {})
        self.assertFalse(self.runtime.is_bridge_anthropic_enabled({}))
        for val in ("1", "true", "TRUE", "yes", "on", "ON"):
            self.assertTrue(
                self.runtime.is_bridge_anthropic_enabled(
                    {"BRIDGE_AGY_ANTHROPIC_ENABLED": val}
                )
            )
        for val in ("", "0", "false", "off", "no"):
            self.assertFalse(
                self.runtime.is_bridge_anthropic_enabled(
                    {"BRIDGE_AGY_ANTHROPIC_ENABLED": val}
                )
            )
        self.assertFalse(resolution.available)
        self.assertEqual(503, resolution.http_status)
        self.assertEqual("feature_flag_disabled", resolution.reason)
        self.assertEqual([], probe.calls)

    def test_account_with_only_46_returns_unavailable_without_spawn(self):
        real_probe = AgyAnthropicProbe(
            runner=lambda t, m: (0, "claude-sonnet-4-6\ngemini-4-neon\n")
        )
        resolution = self.resolve_without_spawn(
            "claude-sonnet-5-5", "off", real_probe, ENABLED
        )
        self.assertFalse(resolution.available)
        self.assertEqual(503, resolution.http_status)
        self.assertEqual("model_unavailable", resolution.error_type)
        self.assertEqual("missing_5_5_on_account", resolution.reason)

    def test_l2_happy_path_real_probe_resolves_effort_and_thinking_in_fleet(self):
        fleet_models = {
            m["id"]: m
            for m in json.loads(BRIDGE_FLEET_PATH.read_text(encoding="utf-8"))["models"]
        }
        real_probe = AgyAnthropicProbe(runner=lambda t, m: (0, REAL_FORMAT_55_LIVE))
        res_high = self.resolve_without_spawn(
            "claude-sonnet-5-5", "high", real_probe, ENABLED
        )
        res_low = self.resolve_without_spawn(
            "claude-sonnet-5-5", "low", real_probe, ENABLED
        )
        res_thinking = self.resolve_without_spawn(
            "claude-opus-5-5", None, real_probe, ENABLED
        )
        self.assertTrue(res_high.available)
        self.assertEqual(res_high.upstream_model, "claude-sonnet-5-5-high")
        self.assertEqual(res_low.upstream_model, "claude-sonnet-5-5-low")
        self.assertEqual(res_thinking.upstream_model, "claude-opus-5-5-thinking")
        self.assertEqual(res_high.effective_effort, "off")
        self.assertEqual(res_high.extra_env, {"AGY_ANTHROPIC_ENABLED": "1"})
        self.assertEqual([], self.runtime.effort_cli_args("off"))
        for res in (res_high, res_low, res_thinking):
            self.assertIn(res.upstream_model, fleet_models)

    def test_xhigh_and_max_reasoning_effort_are_rejected(self):
        for effort in ("xhigh", "max"):
            with self.subTest(effort=effort):
                probe = FakeProbe()
                resolution = self.resolve_without_spawn(
                    "claude-opus-5-5", effort, probe, ENABLED
                )
                self.assertFalse(resolution.available)
                self.assertEqual(400, resolution.http_status)
                self.assertEqual("unsupported_reasoning_effort", resolution.error_type)
                self.assertEqual([], probe.calls)

    def test_forbidden_and_unknown_claude_models_are_rejected(self):
        for model_id in ("claude-sonnet-4-6", "claude-haiku-5-5", "claude-unknown-9"):
            with self.subTest(model_id=model_id):
                probe = FakeProbe()
                resolution = self.resolve_without_spawn(
                    model_id, "off", probe, ENABLED
                )
                self.assertEqual(400, resolution.http_status)
                self.assertEqual("model_not_allowed", resolution.error_type)
                self.assertEqual("forbidden_or_unknown_model", resolution.reason)
                self.assertEqual([], probe.calls)

    def test_non_claude_bypasses_probe_and_bridge_environment(self):
        probe = FakeProbe()
        resolution = self.resolve_without_spawn("gemini-4-neon", "high", probe, ENABLED)
        self.assertTrue(resolution.bypass)
        self.assertTrue(resolution.available)
        self.assertEqual({}, resolution.extra_env)
        self.assertEqual([], probe.calls)

    def test_catalog_filter_disabled_and_enabled(self):
        probe = FakeProbe(
            {
                "claude-sonnet-5-5": snapshot("claude-sonnet-5-5"),
                "claude-opus-5-5": snapshot("claude-opus-5-5", False, "disabled"),
            }
        )
        order = ["gemini-4-neon", "claude-sonnet-5-5", "claude-opus-5-5"]
        self.assertEqual(
            ["gemini-4-neon"],
            self.runtime.filter_anthropic_catalog_order(order, probe, env={}),
        )
        self.assertEqual([], probe.calls)
        self.assertEqual(
            ["gemini-4-neon", "claude-sonnet-5-5"],
            self.runtime.filter_anthropic_catalog_order(order, probe, env=ENABLED),
        )
        self.assertEqual(["claude-sonnet-5-5", "claude-opus-5-5"], probe.calls)

    def test_server_uses_safe_fleet_lookup_and_bridge_fleet_has_all_10_ids(self):
        fleet_data = json.loads(BRIDGE_FLEET_PATH.read_text(encoding="utf-8"))
        by_id = {m["id"]: m for m in fleet_data["models"]}
        for model_id in ALLOWED_AGY_CLAUDE_IDS:
            with self.subTest(model_id=model_id):
                self.assertIn(model_id, by_id)
                card = by_id[model_id]
                self.assertEqual(card["context_window"], 1000000)
                self.assertEqual(card["max_tokens"], 128000)
                self.assertEqual(card["input"], ["text"])
                self.assertEqual(card["images"]["cli_registry"], "explicit_unsupported")
                self.assertEqual(card["images"]["status"], "unsupported")
        server_src = SERVER_PATH.read_text(encoding="utf-8")
        ast.parse(server_src)
        self.assertNotIn('FLEET["models"][ar.upstream_model]', server_src)
        self.assertIn('FLEET["models"].get(ar.upstream_model)', server_src)
        self.assertIn("resolved upstream model missing from fleet catalogue", server_src)


if __name__ == "__main__":
    unittest.main()
