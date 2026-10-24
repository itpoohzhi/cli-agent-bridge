"""Алиасы устаревших/выбывших id: вывод набора, резолв в мосте и прозрачная работа старых сессий."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import server
import zen_catalog as zc
from tests._fake_cli import FakeCli
from tests._fixtures import install_test_models, load_json
from tests._http import LiveServer

install_test_models(server)

API = load_json("api_fixture.json")
ZEN = load_json("zen_fixture.json")
ACTIVE = [e["id"] for e in load_json("golden_catalog.json")]
TARGET = "deepseek-v4.1-flash-free"
OWNER_IDS = ("minimax-m3.1-flash-free", "longcat-2.5-preview-free",
             "muse-spark-1.3-contributor-free", "qwen3.6-plus-free")


class AliasDerivationTest(unittest.TestCase):
    def test_static_aliases(self) -> None:
        self.assertEqual(set(zc.DEPRECATED_MODEL_ALIASES), {
            "minimax-m3.1-flash-free", "longcat-2.5-preview-free", "muse-spark-1.3-contributor-free",
            "qwen3.6-plus-free", "trinity-large-preview-free", "nemotron-3-super-free", "mimo-v2-pro-free",
            "mimo-v2-omni-free", "gpt-5-nano", "k2p5"})
        self.assertEqual(set(zc.DEPRECATED_MODEL_ALIASES.values()), {TARGET})
        self.assertIs(server.DEPRECATED_MODEL_ALIASES, zc.DEPRECATED_MODEL_ALIASES)

    def test_derived_from_api_and_retired(self) -> None:
        models = zc.api_models(API)
        aliases, retired = zc.derive_aliases(models, ACTIVE, ACTIVE + ["gone-free"], [])
        self.assertEqual(retired, ["gone-free"])
        self.assertEqual(aliases["gone-free"], TARGET)
        self.assertEqual(aliases["hy3-free"], TARGET)           # free deprecated из api.json
        self.assertEqual(aliases["minimax-m3.1-flash-free"], TARGET)
        self.assertTrue(set(aliases).isdisjoint(ACTIVE))
        self.assertNotIn("nemotron-3-ultra-free", aliases)       # активная free, не deprecated

    def test_returned_model_stops_being_retired(self) -> None:
        aliases, retired = zc.derive_aliases(zc.api_models(API), ACTIVE, ACTIVE, ["beam-free", "old-free"])
        self.assertEqual(retired, ["old-free"])
        self.assertNotIn("beam-free", aliases)

    def test_target_falls_back_when_default_is_inactive(self) -> None:
        active = [m for m in ACTIVE if m != TARGET]
        self.assertEqual(zc.pick_alias_target(active), "beam-free")
        self.assertEqual(zc.pick_alias_target(active, "glm-5.3-flash-free"), "glm-5.3-flash-free")
        aliases, _ = zc.derive_aliases(zc.api_models(API), active, ACTIVE, [])
        self.assertEqual(aliases["minimax-m3.1-flash-free"], "beam-free")
        self.assertEqual(aliases[TARGET], "beam-free")           # выбывшая сама стала алиасом

    def test_resolve_model(self) -> None:
        aliases = {"old-free": TARGET}
        self.assertEqual(zc.resolve_model("beam-free", ACTIVE, aliases), ("beam-free", False))
        self.assertEqual(zc.resolve_model("old-free", ACTIVE, aliases), (TARGET, True))
        self.assertEqual(zc.resolve_model("k2p5", ACTIVE, {}), (TARGET, True))
        self.assertEqual(zc.resolve_model("jev-1.13", ACTIVE, aliases), (None, False))
        # устаревший target в алиасе -> пересчёт на актуальную цель
        self.assertEqual(zc.resolve_model("old-free", ["beam-free"], {"old-free": "dead-free"}), ("beam-free", True))
        self.assertEqual(zc.resolve_model("old-free", [], aliases), (None, False))


class BridgeAliasTest(unittest.TestCase):
    def setUp(self) -> None:
        models = zc.entries_to_bridge_models(load_json("golden_catalog.json"))
        for patcher in (patch.object(server, "ALLOWED_MODELS", models),
                        patch.object(server, "MODEL_ALIASES", dict(zc.DEPRECATED_MODEL_ALIASES))):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_resolve_alias(self) -> None:
        for old in OWNER_IDS:
            with self.subTest(old=old):
                self.assertEqual(server._resolve_alias(old), TARGET)
        self.assertIsNone(server._resolve_alias(TARGET))
        self.assertIsNone(server._resolve_alias("jev-1.13"))


class AliasHttpTest(unittest.TestCase):
    """Старые id обслуживаются целевой моделью; в ответе остаётся запрошенный id."""

    def setUp(self) -> None:
        models = zc.entries_to_bridge_models(load_json("golden_catalog.json"))
        self.cli = FakeCli()
        self.addCleanup(self.cli.close)
        for patcher in (patch.object(server, "ALLOWED_MODELS", models),
                        patch.object(server, "MODEL_ALIASES", dict(zc.DEPRECATED_MODEL_ALIASES)),
                        patch.object(server, "_resolve_launcher", return_value=str(self.cli.path)),
                        patch.object(server, "_log") ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.log = server._log
        self.live = LiveServer()
        self.addCleanup(self.live.stop)

    def _chat(self, model: str, **extra: object) -> tuple[int, dict]:
        body = {"model": model, "messages": [{"role": "user", "content": "Reply with exact word OK"}], **extra}
        return self.live.call("POST", "/v1/chat/completions", body)

    def test_old_ids_are_served_by_target(self) -> None:
        for old in OWNER_IDS:
            with self.subTest(old=old):
                status, payload = self._chat(old, reasoning_effort="medium")
                self.assertEqual(status, 200)
                self.assertEqual(payload["model"], old)
                self.assertEqual(payload["choices"][0]["message"]["content"], "OK")
                argv = self.cli.argv()
                # уровень пересчитан по variant_map целевой модели: medium -> high
                self.assertEqual(argv[argv.index("-m") + 1], f"opencode/{TARGET}#high")
                self.assertIn("--thinking", argv)
                self.assertIn("--standalone", argv)
        logged = [c.args[0] for c in self.log.call_args_list]
        for old in OWNER_IDS:
            self.assertIn(f"alias {old} -> {TARGET}", logged)

    def test_unknown_and_denied_ids_still_400(self) -> None:
        for model in ("jev-1.13", "totally-unknown", "nemotron-3-ultra-free"):
            with self.subTest(model=model):
                status, payload = self._chat(model)
                self.assertEqual(status, 400)
                self.assertEqual(payload["error"]["code"], "model_not_found")

    def test_active_model_is_not_aliased(self) -> None:
        status, payload = self._chat("beam-free", reasoning_effort="high")
        self.assertEqual(status, 200)
        self.assertEqual(payload["model"], "beam-free")
        self.assertFalse(any("alias " in c.args[0] for c in self.log.call_args_list))

    def test_stream_keeps_requested_id(self) -> None:
        import urllib.request
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.live.port}/v1/chat/completions", method="POST",
            data=json.dumps({"model": "k2p5", "stream": True,
                             "messages": [{"role": "user", "content": "ping"}]}).encode(),
            headers={"Authorization": "Bearer test-key", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            events = [json.loads(line[6:]) for line in resp.read().decode().splitlines()
                      if line.startswith("data: ") and line != "data: [DONE]"]
        self.assertTrue(events)
        self.assertEqual({e["model"] for e in events}, {"k2p5"})


if __name__ == "__main__":
    unittest.main()
