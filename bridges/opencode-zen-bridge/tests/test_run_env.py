"""Окружение и команда `opencode run` для Zen (--standalone, свежий каталог, без OPENCODE_API_KEY) и Go."""

from __future__ import annotations

import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server
import zen_catalog as zc
from tests._fake_cli import FakeCli
from tests._fixtures import install_test_models, load_json
from tests._http import LiveServer

install_test_models(server)

SERVER_SOURCE = (Path(__file__).resolve().parent.parent / "server.py").read_text("utf-8")
CONFIG_LITERAL = '{"permission":{"*":"ask"},"provider":{"opencode":{"options":{"baseURL":"http://127.0.0.1:10830/v1"}}}}'
GO_MODEL = "gemini-4-argon-contributor"


class ZenRunEnvTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.models_path = Path(tmp.name) / "models.json"
        self.models_path.write_text("{}", "utf-8")
        patcher = patch.object(server, "OPENCODE_MODELS_PATH", str(self.models_path))
        patcher.start()
        self.addCleanup(patcher.stop)

    def _env(self, model: str, **extra: str) -> dict[str, str]:
        base = {"OPENCODE_API_KEY": "expired-key", "OPENCODE_GO_API_KEY": "go-key", "HOME": "/tmp", **extra}
        with patch.dict(os.environ, base, clear=True):
            return server._run_env(model)

    def test_zen_env_uses_fresh_catalog_without_api_key(self) -> None:
        for model in ("flint-40b-free", "big-pickle", "deepseek-v4.1-flash-free"):
            with self.subTest(model=model):
                env = self._env(model)
                self.assertEqual(env["OPENCODE_MODELS_PATH"], str(self.models_path))
                self.assertEqual(env["OPENCODE_DISABLE_MODELS_FETCH"], "1")
                self.assertNotIn("OPENCODE_API_KEY", env)
                self.assertNotIn("OPENCODE_GO_API_KEY", env)  # allowlist THREAT-003: ключ Go в Zen не уходит
                self.assertEqual(env["OPENCODE_CONFIG_CONTENT"], CONFIG_LITERAL)
                self.assertNotIn("OPENCODE_CONFIG", env)

    def test_go_env_keeps_its_route_and_credentials(self) -> None:
        env = self._env(GO_MODEL)
        self.assertEqual(env["OPENCODE_API_KEY"], "expired-key")
        self.assertNotIn("OPENCODE_MODELS_PATH", env)
        self.assertNotIn("OPENCODE_DISABLE_MODELS_FETCH", env)
        self.assertTrue(env["OPENCODE_CONFIG"].endswith("opencode-go.json"))

    def test_missing_models_file_falls_back_to_builtin_snapshot(self) -> None:
        self.models_path.unlink()
        env = self._env("flint-40b-free")
        self.assertNotIn("OPENCODE_MODELS_PATH", env)
        self.assertNotIn("OPENCODE_DISABLE_MODELS_FETCH", env)
        self.assertNotIn("OPENCODE_API_KEY", env)

    def test_standalone_keeps_proxies_and_bypasses_loopback(self) -> None:
        # Без прокси приватный сервер получает RegionError на beam-free (проверено живьём 2026-10-24).
        env = self._env("beam-free", HTTPS_PROXY="http://p:1", http_proxy="http://p:1", ALL_PROXY="socks5://q:2",
                        NO_PROXY="example.com,127.0.0.1")
        self.assertEqual(env["HTTPS_PROXY"], "http://p:1")
        self.assertEqual(env["http_proxy"], "http://p:1")
        self.assertEqual(env["ALL_PROXY"], "socks5://q:2")
        self.assertEqual(env["NO_PROXY"], "example.com,127.0.0.1,localhost,::1")
        self.assertEqual(env["no_proxy"], env["NO_PROXY"])

    def test_standalone_without_proxies_still_sets_loopback_no_proxy(self) -> None:
        env = self._env("beam-free")
        self.assertEqual(env["NO_PROXY"], "127.0.0.1,localhost,::1")
        self.assertFalse({"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"} & env.keys())

    def test_go_route_and_service_route_strip_proxies(self) -> None:
        go = self._env(GO_MODEL, HTTPS_PROXY="http://p", http_proxy="http://p")
        self.assertNotIn("HTTPS_PROXY", go)
        self.assertNotIn("http_proxy", go)
        self.assertEqual(go["NO_PROXY"], "127.0.0.1,localhost")
        with patch.object(server, "CATALOG_MODE", "static"):
            svc = self._env("big-pickle", HTTPS_PROXY="http://p", ALL_PROXY="http://p")
        self.assertFalse({"HTTPS_PROXY", "ALL_PROXY"} & svc.keys())
        self.assertEqual(svc["NO_PROXY"], "127.0.0.1,localhost")

    def test_standalone_env_drops_foreign_secrets(self) -> None:
        # THREAT-003: посторонние секреты родительского процесса не попадают в дочерний opencode.
        env = self._env("deepseek-v4.1-flash-free", OPENCODE_ZEN_BRIDGE_KEY="bridge-secret",
                        ARBITRARY_SECRET_TOKEN="token-secret")
        for name in ("OPENCODE_ZEN_BRIDGE_KEY", "ARBITRARY_SECRET_TOKEN", "OPENCODE_API_KEY"):
            self.assertNotIn(name, env)

    def test_standalone_env_keys_are_within_allowlist(self) -> None:
        env = self._env("deepseek-v4.1-flash-free", OPENCODE_ZEN_BRIDGE_KEY="k", ARBITRARY_SECRET_TOKEN="t",
                        HTTPS_PROXY="http://p:1", TMPDIR="/tmp", LANG="C")
        allowed = set(server._STANDALONE_ENV_ALLOWLIST) | {
            "OPENCODE_CONFIG_CONTENT", "OPENCODE_MODELS_PATH", "OPENCODE_DISABLE_MODELS_FETCH"}
        self.assertLessEqual(set(env), allowed)
        self.assertTrue({"PATH", "HOME", "TMPDIR", "LANG", "HTTPS_PROXY", "OPENCODE_CONFIG_CONTENT"} <= set(env))

    def test_standalone_proxy_override_sets_rotating_proxy(self) -> None:
        proxy = "http://127.0.0.1:10816"
        env = self._env("deepseek-v4.1-flash-free", OPENCODE_ZEN_BRIDGE_STANDALONE_PROXY=proxy,
                        HTTP_PROXY="http://fixed:1", HTTPS_PROXY="http://fixed:1")
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            self.assertEqual(env[name], proxy)
        self.assertNotIn("OPENCODE_ZEN_BRIDGE_STANDALONE_PROXY", env)

    def test_standalone_proxy_pool_rotates_ports_round_robin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pool_file = Path(tmp) / "pool.txt"
            pool_file.write_text(
                "u1:p1@global.rotating.proxyrack.net:10001\n"
                "u2:p2@global.rotating.proxyrack.net:10002\n"
                "u3:p3@global.rotating.proxyrack.net:10003\n", "utf-8")
            extra = {
                "OPENCODE_ZEN_BRIDGE_STANDALONE_PROXY": "pool",
                "OPENCODE_ZEN_BRIDGE_PROXYRACK_FILE": str(pool_file),
                "OPENCODE_ZEN_BRIDGE_PROXYRACK_GATEWAY": "121.91.235.6",
                "OPENCODE_ZEN_BRIDGE_PROXYRACK_OFFSET": "0",
            }
            server._reset_proxy_pool_for_tests()
            try:
                seen = [self._env("deepseek-v4.1-flash-free", **extra) for _ in range(4)]
            finally:
                server._reset_proxy_pool_for_tests()
        expected = [f"http://u{n}:p{n}@121.91.235.6:1000{n}" for n in (1, 2, 3, 1)]
        for env, url in zip(seen, expected):
            for name in server._PROXY_VARS:
                self.assertEqual(env[name], url)
            self.assertNotIn("OPENCODE_ZEN_BRIDGE_STANDALONE_PROXY", env)

    def test_standalone_proxy_explicit_url_ignores_pool_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pool_file = Path(tmp) / "pool.txt"
            pool_file.write_text("u1:p1@global.rotating.proxyrack.net:10001\n", "utf-8")
            server._reset_proxy_pool_for_tests()
            try:
                env = self._env("deepseek-v4.1-flash-free",
                                OPENCODE_ZEN_BRIDGE_STANDALONE_PROXY="http://127.0.0.1:10816",
                                OPENCODE_ZEN_BRIDGE_PROXYRACK_FILE=str(pool_file))
            finally:
                server._reset_proxy_pool_for_tests()
        self.assertEqual(env["HTTP_PROXY"], "http://127.0.0.1:10816")
        self.assertEqual(env["https_proxy"], "http://127.0.0.1:10816")

    def test_standalone_proxy_pool_missing_file_keeps_parent_proxy(self) -> None:
        server._reset_proxy_pool_for_tests()
        env = self._env("deepseek-v4.1-flash-free", HTTPS_PROXY="http://parent:1",
                        OPENCODE_ZEN_BRIDGE_STANDALONE_PROXY="pool",
                        OPENCODE_ZEN_BRIDGE_PROXYRACK_FILE="/nonexistent/pool.txt")
        self.assertEqual(env["HTTPS_PROXY"], "http://parent:1")

    def test_go_and_static_routes_keep_full_environment(self) -> None:
        go = self._env(GO_MODEL, ARBITRARY_SECRET_TOKEN="t")
        self.assertEqual(go["ARBITRARY_SECRET_TOKEN"], "t")
        with patch.object(server, "CATALOG_MODE", "static"):
            svc = self._env("big-pickle", ARBITRARY_SECRET_TOKEN="t")
        self.assertEqual(svc["ARBITRARY_SECRET_TOKEN"], "t")

    def test_config_literal_has_no_static_models(self) -> None:
        self.assertIn(CONFIG_LITERAL, SERVER_SOURCE)
        self.assertNotIn("models", server.OPENCODE_CONFIG_CONTENT)


class ZenCmdTest(unittest.TestCase):
    def setUp(self) -> None:
        models = zc.entries_to_bridge_models(load_json("golden_catalog.json"))
        models[GO_MODEL] = dict(server.ALLOWED_MODELS[GO_MODEL])
        for patcher in (patch.object(server, "ALLOWED_MODELS", models), patch.object(server, "_log")):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_zen_cmd_is_standalone_with_variant_suffix(self) -> None:
        cmd, shown = server._build_cmd("/x/opencode", "flint-40b-free", "high")
        self.assertEqual(cmd, ["/x/opencode", "run", "-m", "opencode/flint-40b-free#high",
                               "--thinking", "--format", "json", "--standalone"])
        self.assertEqual(shown, "-m opencode/flint-40b-free#high --standalone --thinking")

    def test_no_variant_flag_anywhere(self) -> None:
        for model in ("flint-40b-free", "big-pickle", GO_MODEL):
            for effort in ("", "high", "max"):
                cmd, _ = server._build_cmd("x", model, effort)
                self.assertNotIn("--variant", cmd)
        self.assertNotIn('"--variant"', SERVER_SOURCE)

    def test_model_without_variants_has_no_suffix_or_thinking(self) -> None:
        cmd, shown = server._build_cmd("x", "mimo-v2.6-flash-free", "high")
        self.assertEqual(cmd[3], "opencode/mimo-v2.6-flash-free")
        self.assertNotIn("--thinking", cmd)
        self.assertNotIn("#", shown)

    def test_off_level_drops_suffix(self) -> None:
        cmd, _ = server._build_cmd("x", "nemotron-3.5-super-vl-free", "")
        self.assertEqual(cmd[3], "opencode/nemotron-3.5-super-vl-free")
        self.assertNotIn("--thinking", cmd)

    def test_go_cmd_has_no_standalone(self) -> None:
        cmd, _ = server._build_cmd("x", GO_MODEL, "low")
        self.assertNotIn("--standalone", cmd)
        self.assertEqual(cmd[3:5], [f"opencode-go/{GO_MODEL}#low", "--thinking"])


class ZenSpawnTest(unittest.TestCase):
    """Через настоящий HTTP и поддельный CLI: что реально получает дочерний процесс."""

    def test_child_process_receives_standalone_cmd_and_clean_env(self) -> None:
        cli = FakeCli()
        self.addCleanup(cli.close)
        models_file = Path(cli.dir) / "models.json"
        models_file.write_text("{}", "utf-8")
        models = zc.entries_to_bridge_models(load_json("golden_catalog.json"))
        patchers = (
            patch.object(server, "ALLOWED_MODELS", models),
            patch.object(server, "_resolve_launcher", return_value=str(cli.path)),
            patch.object(server, "OPENCODE_MODELS_PATH", str(models_file)),
            patch.object(server, "_log"),
            patch.dict(os.environ, {"OPENCODE_API_KEY": "expired-key"}),
        )
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        live = LiveServer()
        self.addCleanup(live.stop)
        status, payload = live.call("POST", "/v1/chat/completions", {
            "model": "flint-40b-free", "reasoning_effort": "high",
            "messages": [{"role": "user", "content": "Reply with exact word OK"}]})
        self.assertEqual(status, 200)
        self.assertEqual(payload["choices"][0]["message"]["content"], "OK")
        self.assertEqual(cli.argv(), ["run", "-m", "opencode/flint-40b-free#high", "--thinking",
                                      "--format", "json", "--standalone"])
        env = cli.env()
        self.assertNotIn("OPENCODE_API_KEY", env)
        self.assertEqual(env["OPENCODE_MODELS_PATH"], str(models_file))
        self.assertEqual(env["OPENCODE_DISABLE_MODELS_FETCH"], "1")
        self.assertIsNotNone(re.search(r'"baseURL":"http://127.0.0.1:10830/v1"', env["OPENCODE_CONFIG_CONTENT"]))


if __name__ == "__main__":
    unittest.main()
