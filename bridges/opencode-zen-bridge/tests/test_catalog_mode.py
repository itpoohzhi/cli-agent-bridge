"""Kill-switch CATALOG_MODE: dynamic (по умолчанию) и static/legacy (встроенный снимок, прежний маршрут)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server
import zen_catalog as zc
from tests._fixtures import install_test_models, load_json

install_test_models(server)

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_IDS = {e["id"] for e in load_json("golden_catalog.json")}


class ModeNormalizationTest(unittest.TestCase):
    def test_modes(self) -> None:
        self.assertEqual(server._normalize_catalog_mode("dynamic"), "dynamic")
        self.assertEqual(server._normalize_catalog_mode(""), "dynamic")
        self.assertEqual(server._normalize_catalog_mode("garbage"), "dynamic")
        for value in ("static", "STATIC", " legacy "):
            self.assertEqual(server._normalize_catalog_mode(value), "static")

    def test_default_in_tests_is_dynamic(self) -> None:
        self.assertEqual(server.CATALOG_MODE, "dynamic")


class StaticModeTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.state_path = Path(tmp.name) / "zen-catalog.json"
        # state-файл с одной моделью: в static он должен игнорироваться
        entry = json.loads(json.dumps(load_json("golden_catalog.json")[0]))
        self.state_path.write_text(json.dumps(zc.make_state(
            [entry], {}, [], degraded=False, generated_at="t", api_fetched=True, zen_fetched=True)), "utf-8")
        models_file = Path(tmp.name) / "models.json"
        models_file.write_text("{}", "utf-8")
        patchers = (
            patch.object(server, "CATALOG_MODE", "static"),
            patch.object(server, "CATALOG_STATE_PATH", self.state_path),
            patch.object(server, "OPENCODE_MODELS_PATH", str(models_file)),
            patch.object(server, "ALLOWED_MODELS", {}),
            patch.object(server, "MODEL_ALIASES", {}),
            patch.object(server, "_catalog_ids", set()),
            patch.object(server, "_log"),
        )
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_static_uses_embedded_snapshot_and_ignores_state_file(self) -> None:
        result = server.reload_catalog()
        self.assertEqual(result["source"], "static")
        self.assertEqual(set(server.ALLOWED_MODELS), GOLDEN_IDS)
        self.assertEqual(server.CATALOG_SOURCE, "static")

    def test_static_never_reloads_by_mtime(self) -> None:
        server.reload_catalog()
        with patch.object(server, "_stat_mtime") as stat:
            self.assertFalse(server._maybe_reload_catalog(now=1e9))
        stat.assert_not_called()

    def test_static_routes_through_background_service(self) -> None:
        server.reload_catalog()
        with patch.dict(os.environ, {"OPENCODE_API_KEY": "k", "HOME": "/tmp"}, clear=True):
            env = server._run_env("flint-40b-free")
        self.assertEqual(env["OPENCODE_API_KEY"], "k")
        self.assertNotIn("OPENCODE_MODELS_PATH", env)
        self.assertNotIn("OPENCODE_DISABLE_MODELS_FETCH", env)
        cmd, shown = server._build_cmd("x", "flint-40b-free", "high")
        self.assertNotIn("--standalone", cmd)
        self.assertNotIn("--standalone", shown)
        self.assertEqual(cmd[3:5], ["opencode/flint-40b-free#high", "--thinking"])

    def test_aliases_still_work_in_static(self) -> None:
        server.reload_catalog()
        self.assertEqual(server._resolve_alias("minimax-m3.1-flash-free"), "deepseek-v4.1-flash-free")


class ModeFromEnvironmentTest(unittest.TestCase):
    """Настоящий импорт `server` в чистом процессе с переменной окружения (как в plist моста)."""

    PROBE = (
        "import json, server; print(json.dumps({'mode': server.CATALOG_MODE, 'source': server.CATALOG_SOURCE, "
        "'models': sorted(server.ALLOWED_MODELS), 'standalone': server._uses_standalone('big-pickle')}))"
    )

    def _probe(self, mode: str | None) -> dict:
        env = {k: v for k, v in os.environ.items() if not k.startswith("OPENCODE_ZEN_BRIDGE_")}
        env["OPENCODE_ZEN_BRIDGE_CATALOG_STATE"] = str(Path(tempfile.gettempdir()) / "zen-no-such" / "c.json")
        if mode is not None:
            env["OPENCODE_ZEN_BRIDGE_CATALOG_MODE"] = mode
        out = subprocess.run([sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(ROOT)!r}); {self.PROBE}"],
                             env=env, capture_output=True, text=True, timeout=60, check=True)
        return json.loads(out.stdout)

    def test_env_static_and_legacy(self) -> None:
        for value in ("static", "legacy"):
            with self.subTest(mode=value):
                result = self._probe(value)
                self.assertEqual(result["mode"], "static")
                self.assertEqual(result["source"], "static")
                self.assertEqual(set(result["models"]), GOLDEN_IDS)
                self.assertFalse(result["standalone"])

    def test_env_default_is_dynamic(self) -> None:
        for value in (None, "dynamic"):
            with self.subTest(mode=value):
                result = self._probe(value)
                self.assertEqual(result["mode"], "dynamic")
                self.assertEqual(result["source"], "fallback")        # state-файла нет -> встроенный снимок
                self.assertTrue(result["standalone"])


if __name__ == "__main__":
    unittest.main()
