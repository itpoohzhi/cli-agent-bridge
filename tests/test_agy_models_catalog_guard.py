"""Регресс: каталог `GET /v1/models` agy-bridge фильтруется по allowlist лончера.

Баг: каталог отдавал все модели fleet.json, хотя generation guard лончера
(`AGY_ALLOWED_MODELS_FILE`) отклоняет всё вне allowlist (HTTP 502). Мост лежит в
каталоге с дефисом, поэтому грузится через `importlib`; реальный allowlist и HOME
не читаются: путь подменяется временным файлом через окружение.
"""

from __future__ import annotations

import http.client
import importlib.util
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

_BRIDGE_PY = (
    Path(__file__).resolve().parents[1] / "bridges" / "agy-bridge" / "server.py"
)
_ENV = "AGY_ALLOWED_MODELS_FILE"
_ALLOWLIST = """\
# канонический allowlist (комментарий и пустые строки игнорируются)
gemini-4-argon-high
gemini-4-argon

gemini-3.8-flash-low
gemini-3.8-flash
"""
_SERVED = {"gemini-4-argon", "gemini-3.8-flash"}


def _load_bridge() -> Any:
    os.environ.setdefault("AGY_BRIDGE_KEY", "test-key-agy-catalog-guard")
    spec = importlib.util.spec_from_file_location(
        "agy_bridge_server_catalog_guard_under_test", _BRIDGE_PY
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CatalogGuardTests(unittest.TestCase):
    srv: Any = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.srv = _load_bridge()

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.logs: list[str] = []
        for patcher in (
            mock.patch.object(self.srv, "_log", self.logs.append),
            mock.patch.dict(os.environ),
        ):
            _ = patcher.start()
            self.addCleanup(patcher.stop)
        self.httpd = self.srv.Server(("127.0.0.1", 0), self.srv.Handler)
        self.port = self.httpd.server_address[1]
        thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 10)
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def _allowlist(self, text: str | None) -> None:
        path = self.tmp / "allowed-models.txt"
        if text is not None:
            _ = path.write_bytes(text.encode("utf-8"))
        os.environ[_ENV] = str(path)

    def _catalog(self) -> dict[str, Any]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            conn.request(
                "GET",
                "/v1/models",
                headers={"Authorization": "Bearer " + str(self.srv.AUTH_KEY)},
            )
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            return json.loads(response.read().decode("utf-8"))
        finally:
            conn.close()

    def test_only_allowlisted_models_are_listed(self) -> None:
        self._allowlist(_ALLOWLIST)
        ids = [item["id"] for item in self._catalog()["data"]]
        self.assertEqual(set(ids), _SERVED)
        self.assertEqual(self.logs, [])

    def test_model_id_is_first(self) -> None:
        self._allowlist(_ALLOWLIST)
        # Модель по умолчанию не первая в fleet.order: порядок задаёт именно MODEL_ID.
        with mock.patch.object(self.srv, "MODEL_ID", "gemini-3.8-flash"):
            ids = [item["id"] for item in self._catalog()["data"]]
        self.assertEqual(ids[0], "gemini-3.8-flash")
        self.assertEqual(ids, ["gemini-3.8-flash", "gemini-4-argon"])

    def test_response_shape_is_unchanged(self) -> None:
        self._allowlist(_ALLOWLIST)
        body = self._catalog()
        self.assertEqual(
            set(body), {"object", "data", "images", "image_fallback"}
        )
        self.assertEqual(body["object"], "list")
        for item in body["data"]:
            self.assertEqual(
                set(item),
                {"id", "object", "owned_by", "created", "context_length", "images"},
            )

    def test_missing_allowlist_keeps_full_catalog_and_warns_once(self) -> None:
        self._allowlist(None)
        ids = [item["id"] for item in self._catalog()["data"]]
        self.assertEqual(set(ids), set(self.srv.FLEET["order"]) | {self.srv.MODEL_ID})
        self.assertEqual(ids[0], self.srv.MODEL_ID)
        self.assertEqual(len(self.logs), 1)
        self.assertIn("allowlist", self.logs[0])

    def test_empty_allowlist_keeps_full_catalog_and_warns_once(self) -> None:
        self._allowlist("# только комментарий\n\n")
        ids = [item["id"] for item in self._catalog()["data"]]
        self.assertEqual(set(ids), set(self.srv.FLEET["order"]) | {self.srv.MODEL_ID})
        self.assertEqual(len(self.logs), 1)

    def test_default_path_is_real_home_when_env_unset(self) -> None:
        _ = os.environ.pop(_ENV, None)
        home = self.tmp / "home"
        with mock.patch.object(self.srv, "HOME", home):
            self.assertEqual(
                self.srv._allowed_models_file(),
                str(home / ".config" / "agy-launch" / "allowed-models.txt"),
            )

    def test_launch_env_shares_path_with_catalog(self) -> None:
        self._allowlist(_ALLOWLIST)
        with mock.patch.object(self.srv, "_prepare_agy_home", lambda: self.tmp):
            with mock.patch.object(self.srv, "_verify_clean_home_root", lambda _p: None):
                with mock.patch.object(self.srv, "_clean_canon_files", lambda _p: None):
                    env = self.srv._launch_env()
        self.assertEqual(env[_ENV], self.srv._allowed_models_file())

    def test_matching_rule_exact_or_base_form(self) -> None:
        allowed = frozenset({"gemini-4-argon", "gemini-3.8-flash-low"})
        match = self.srv._model_in_allowlist
        self.assertTrue(match("gemini-4-argon", allowed))
        self.assertTrue(match("gemini-4-argon-high", allowed))
        self.assertTrue(match("gemini-4-argon-medium", allowed))
        self.assertTrue(match("gemini-3.8-flash-low", allowed))
        self.assertFalse(match("gemini-3.8-flash", allowed))
        self.assertFalse(match("gemini-3.7-flash", allowed))
        self.assertFalse(match("gemini-3.1-pro", allowed))
        self.assertFalse(match("gpt-oss-120b", allowed))
        self.assertFalse(match("gemini-4-argon-ultra", allowed))


if __name__ == "__main__":
    _ = unittest.main()
