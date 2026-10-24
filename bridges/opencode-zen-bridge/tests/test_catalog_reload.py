"""Горячее обновление каталога: перечитывание по mtime (не чаще 1 stat/5 с) и POST /v1/models/reload."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

import server
import zen_catalog as zc
from tests._fixtures import install_test_models, load_json
from tests._http import LiveServer

install_test_models(server)

GOLDEN = load_json("golden_catalog.json")


def _state(entries: list[dict[str, Any]], aliases: dict[str, str] | None = None) -> dict[str, Any]:
    return zc.make_state(entries, aliases or {}, [], degraded=False, generated_at="t",
                         api_fetched=True, zen_fetched=True)


class CatalogReloadTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "zen-catalog.json"
        models = zc.entries_to_bridge_models(GOLDEN)
        patchers = (
            patch.object(server, "CATALOG_STATE_PATH", self.path),
            patch.object(server, "ALLOWED_MODELS", models),
            patch.object(server, "MODEL_ALIASES", dict(zc.DEPRECATED_MODEL_ALIASES)),
            patch.object(server, "_catalog_ids", set(models)),
            patch.object(server, "_catalog_mtime", None),
            patch.object(server, "_catalog_checked_at", float("-inf")),
            patch.object(server, "_log"),
        )
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def _write(self, entries: list[dict[str, Any]], aliases: dict[str, str] | None = None) -> None:
        self.path.write_text(json.dumps(_state(entries, aliases)), "utf-8")

    def test_reload_applies_new_state_in_place(self) -> None:
        ref = server.ALLOWED_MODELS
        self._write([e for e in GOLDEN if e["id"] != "beam-free"], {"beam-free": "big-pickle"})
        result = server.reload_catalog()
        self.assertIs(server.ALLOWED_MODELS, ref)
        self.assertEqual(result["source"], "file")
        self.assertNotIn("beam-free", server.ALLOWED_MODELS)
        self.assertEqual(len(server.ALLOWED_MODELS), 7)
        self.assertEqual(server.MODEL_ALIASES["beam-free"], "big-pickle")
        self.assertEqual(server._resolve_alias("beam-free"), "big-pickle")

    def test_reload_keeps_non_catalog_models(self) -> None:
        server.ALLOWED_MODELS["go-extra"] = {"context_length": 1, "max_output": 1, "provider": "opencode-go",
                                             "base_url": "http://x"}
        self._write(GOLDEN[:2])
        server.reload_catalog()
        self.assertIn("go-extra", server.ALLOWED_MODELS)
        self.assertEqual(set(server.ALLOWED_MODELS) - {"go-extra"}, {e["id"] for e in GOLDEN[:2]})

    def test_bad_or_missing_file_falls_back_to_embedded_snapshot(self) -> None:
        result = server.reload_catalog()
        self.assertEqual(result["source"], "fallback")
        self.assertEqual(set(server.ALLOWED_MODELS), {e["id"] for e in GOLDEN})
        self.path.write_text("{oops", "utf-8")
        self.assertEqual(server.reload_catalog()["source"], "fallback")

    def test_mtime_driven_reload_is_throttled(self) -> None:
        self._write(GOLDEN)
        stats: list[int | None] = []
        mtimes = iter([100, 100, 100, 200, 200])

        def fake_stat(path: Path) -> int | None:
            value = next(mtimes)
            stats.append(value)
            return value

        with patch.object(server, "_stat_mtime", side_effect=fake_stat):
            self.assertTrue(server._maybe_reload_catalog(now=1000.0))     # mtime 100 (stat) + 100 (внутри reload)
            self.assertFalse(server._maybe_reload_catalog(now=1001.0))    # <5 с: stat не вызывается
            self.assertFalse(server._maybe_reload_catalog(now=1004.9))
            self.assertEqual(len(stats), 2)
            self.assertFalse(server._maybe_reload_catalog(now=1006.0))    # 5 с прошло, mtime тот же (100)
            self.assertEqual(len(stats), 3)
            self.assertTrue(server._maybe_reload_catalog(now=1012.0))     # mtime 200 -> reload
            self.assertEqual(stats[3:], [200, 200])

    def test_real_mtime_change_triggers_reload(self) -> None:
        self._write(GOLDEN)
        self.assertTrue(server._maybe_reload_catalog(now=100.0))
        self.assertEqual(len(server.ALLOWED_MODELS), 8)
        self._write(GOLDEN[:3])
        os.utime(self.path, ns=(1, 2_000_000_000))
        self.assertFalse(server._maybe_reload_catalog(now=101.0))         # слишком рано
        self.assertTrue(server._maybe_reload_catalog(now=110.0))
        self.assertEqual(len(server.ALLOWED_MODELS), 3)


class ReloadEndpointTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "zen-catalog.json"
        models = zc.entries_to_bridge_models(GOLDEN)
        patchers = (
            patch.object(server, "CATALOG_STATE_PATH", self.path),
            patch.object(server, "ALLOWED_MODELS", models),
            patch.object(server, "MODEL_ALIASES", dict(zc.DEPRECATED_MODEL_ALIASES)),
            patch.object(server, "_catalog_ids", set(models)),
            patch.object(server, "_catalog_mtime", None),
            patch.object(server, "_catalog_checked_at", float("inf")),   # автоперечитывание отключено
            patch.object(server, "_log"),
        )
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.live = LiveServer()
        self.addCleanup(self.live.stop)

    def test_reload_requires_auth(self) -> None:
        status, _ = self.live.call("POST", "/v1/models/reload", {}, key="wrong")
        self.assertEqual(status, 401)
        status, _ = self.live.call("POST", "/v1/models/reload", {}, key=None)
        self.assertEqual(status, 401)

    def test_reload_picks_up_new_models_without_restart(self) -> None:
        extra = json.loads(json.dumps(GOLDEN[0]))
        extra["id"] = "fresh-free"
        self.path.write_text(json.dumps(_state(GOLDEN + [extra])), "utf-8")
        self.assertNotIn("fresh-free", [m["id"] for m in self.live.call("GET", "/v1/models")[1]["data"]])
        status, payload = self.live.call("POST", "/v1/models/reload", {})
        self.assertEqual(status, 200)
        self.assertEqual(payload["source"], "file")
        self.assertIn("fresh-free", payload["models"])
        listed = [m["id"] for m in self.live.call("GET", "/v1/models")[1]["data"]]
        self.assertIn("fresh-free", listed)
        self.assertEqual(len(listed), 9)

    def test_reload_after_model_removed_returns_alias(self) -> None:
        self.path.write_text(json.dumps(_state(GOLDEN[1:], {GOLDEN[0]["id"]: GOLDEN[1]["id"]})), "utf-8")
        self.live.call("POST", "/v1/models/reload", {})
        self.assertEqual(server._resolve_alias(GOLDEN[0]["id"]), GOLDEN[1]["id"])


if __name__ == "__main__":
    unittest.main()
