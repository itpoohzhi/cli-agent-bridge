"""Боевой каталог моста: ровно 8 free-моделей Zen (golden из api.json 2026-10-24) и их публикация по HTTP."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import server
from tests._fixtures import install_test_models, load_json
from tests._http import LiveServer

PRODUCTION_MODELS = install_test_models(server)

GOLDEN = {e["id"]: e for e in load_json("golden_catalog.json")}


class ProductionCatalogTest(unittest.TestCase):
    def test_exactly_eight_zen_models(self) -> None:
        self.assertEqual(set(PRODUCTION_MODELS), set(GOLDEN))

    def test_limits_match_golden(self) -> None:
        for model_id, entry in GOLDEN.items():
            meta = server.ALLOWED_MODELS[model_id]
            with self.subTest(model=model_id):
                self.assertEqual((meta["context_length"], meta["max_output"]),
                                 (entry["bridge"]["context_length"], entry["bridge"]["max_output"]))
                self.assertEqual(meta["supports_variant"], entry["bridge"]["supports_variant"])
                self.assertEqual(meta.get("variant_map"), entry["bridge"]["variant_map"])

    def test_variant_models(self) -> None:
        variants = {m for m in GOLDEN if server.ALLOWED_MODELS[m]["supports_variant"]}
        self.assertEqual(variants, {"deepseek-v4.1-flash-free", "glm-5.3-flash-free", "beam-free",
                                    "flint-40b-free", "nemotron-3.5-super-vl-free"})

    def test_default_model_is_in_catalog(self) -> None:
        self.assertIn(server.DEFAULT_MODEL, GOLDEN)
        self.assertEqual(server._effective_default_model(), server.DEFAULT_MODEL)

    def test_default_model_falls_back_when_missing(self) -> None:
        with patch.object(server, "DEFAULT_MODEL", "gone-free"):
            self.assertIn(server._effective_default_model(), GOLDEN)

    def test_model_names_are_not_masked_as_secrets(self) -> None:
        for model_id in GOLDEN:
            with self.subTest(model=model_id):
                self.assertEqual(server._mask_secrets(f"model={model_id}"), f"model={model_id}")
        for prefix in ("nemotron-", "minimax-", "beam-", "glm-", "qwen"):
            with self.subTest(prefix=prefix):
                long_id = f"{prefix}x-long-model-identifier-0123456789"
                self.assertEqual(server._mask_secrets(f"model={long_id}"), f"model={long_id}")

    def test_dynamic_long_model_ids_are_not_masked(self) -> None:
        long_id = "flint-x-long-model-identifier-0123456789"
        self.assertEqual(server._mask_secrets(f"model={long_id}"), "model=***")
        with patch.dict(server.ALLOWED_MODELS, {long_id: {"context_length": 1, "max_output": 1}}):
            self.assertEqual(server._mask_secrets(f"model={long_id}"), f"model={long_id}")
        with patch.dict(server.MODEL_ALIASES, {long_id: "big-pickle"}):
            self.assertEqual(server._mask_secrets(f"model={long_id}"), f"model={long_id}")


class ProductionCatalogHttpTest(unittest.TestCase):
    """Боевой каталог через настоящий HTTP: /v1/models, /health и отказ для чужих моделей."""

    EXCLUDED = ("jev-1.13", "jev-1.13-free", "nemotron-3-ultra-free", "test", "claude-opus-5-5-backup")
    GO_DIRECT = ("deepseek-v4.1-flash", "claude-haiku-5-5")

    live: LiveServer

    @classmethod
    def setUpClass(cls) -> None:
        production = {m: meta for m, meta in server.ALLOWED_MODELS.items() if m in PRODUCTION_MODELS}
        cls._patch = patch.object(server, "ALLOWED_MODELS", production)
        cls._patch.start()
        cls.live = LiveServer()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.live.stop()
        cls._patch.stop()

    def test_models_endpoint_lists_exactly_golden(self) -> None:
        status, payload = self.live.call("GET", "/v1/models")
        self.assertEqual(status, 200)
        self.assertEqual({item["id"] for item in payload["data"]}, set(GOLDEN))
        self.assertEqual(len(payload["data"]), 8)
        for item in payload["data"]:
            with self.subTest(model=item["id"]):
                cordis = GOLDEN[item["id"]]["cordis"]
                self.assertEqual(item["context_length"], cordis["contextWindow"])
                self.assertEqual(item["max_output"], cordis["maxTokens"])
                self.assertEqual(item["reasoning_efforts"], list(cordis["reasoningEfforts"]))

    def test_health_reports_catalog(self) -> None:
        status, payload = self.live.call("GET", "/health", key=None)
        self.assertEqual(status, 200)
        self.assertEqual(set(payload["models"]), set(GOLDEN))
        self.assertEqual(payload["catalog_mode"], "dynamic")

    def test_excluded_and_go_models_are_rejected_with_400(self) -> None:
        for model_id in (*self.EXCLUDED, *self.GO_DIRECT):
            with self.subTest(model=model_id):
                status, payload = self.live.call("POST", "/v1/chat/completions", {
                    "model": model_id, "messages": [{"role": "user", "content": "ping"}]})
                self.assertEqual(status, 400)
                self.assertEqual(payload["error"]["code"], "model_not_found")

    def test_wrong_key_is_unauthorized(self) -> None:
        status, _ = self.live.call("GET", "/v1/models", key="wrong-key")
        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()
