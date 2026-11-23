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
        expected = {m for m in self.srv.FLEET["order"] if not m.startswith("claude-")} | {self.srv.MODEL_ID}
        self.assertEqual(set(ids), expected)
        self.assertEqual(ids[0], self.srv.MODEL_ID)
        self.assertEqual(len(self.logs), 1)
        self.assertIn("allowlist", self.logs[0])

    def test_empty_allowlist_keeps_full_catalog_and_warns_once(self) -> None:
        self._allowlist("# только комментарий\n\n")
        ids = [item["id"] for item in self._catalog()["data"]]
        expected = {m for m in self.srv.FLEET["order"] if not m.startswith("claude-")} | {self.srv.MODEL_ID}
        self.assertEqual(set(ids), expected)
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

    def test_matching_rule_is_literal(self) -> None:
        """Правило каталога — дословное совпадение с allowlist лончера.

        Базовая форма НЕ расширяет каталог: лончер сверяет id дословно, поэтому
        `gemini-4-argon-high` недопустим, если в файле есть только `gemini-4-argon`.
        """
        allowed = frozenset({"gemini-4-argon", "gemini-3.8-flash-low"})
        match = self.srv._model_in_allowlist
        self.assertTrue(match("gemini-4-argon", allowed))
        self.assertTrue(match("gemini-3.8-flash-low", allowed))
        self.assertFalse(match("gemini-4-argon-high", allowed))
        self.assertFalse(match("gemini-4-argon-medium", allowed))
        self.assertFalse(match("gemini-3.8-flash", allowed))
        self.assertFalse(match("gemini-3.7-flash", allowed))
        self.assertFalse(match("gemini-3.1-pro", allowed))
        self.assertFalse(match("gpt-oss-120b", allowed))
        self.assertFalse(match("gemini-4-argon-ultra", allowed))

    def test_anthropic_enabled_exposes_probed_claude_5_5_with_google_allowlist(
        self,
    ) -> None:
        """При включённом флаге /v1/models отдаёт живые Claude 5.5 поверх Google allowlist."""
        self._allowlist(_ALLOWLIST)
        os.environ["BRIDGE_AGY_ANTHROPIC_ENABLED"] = "true"
        available_ids = {"claude-sonnet-5-5-high", "claude-opus-5-5-high"}

        class _FakeProbe:
            def probe(self, model_id: str) -> Any:
                ok = model_id in available_ids
                return mock.Mock(
                    available=ok,
                    upstream_model=model_id if ok else None,
                    reason="ok" if ok else "not_advertised_by_agy",
                )

        with mock.patch.object(self.srv, "_ANTHROPIC_PROBE", _FakeProbe()):
            body = self._catalog()
        by_id = {item["id"]: item for item in body["data"]}
        self.assertEqual(set(by_id), _SERVED | available_ids)
        self.assertNotIn("claude-sonnet-5-5-low", by_id)
        self.assertNotIn("claude-opus-5-5-thinking", by_id)
        self.assertFalse(by_id["claude-sonnet-5-5-high"]["images"])
        self.assertFalse(by_id["claude-opus-5-5-high"]["images"])

    def test_anthropic_disabled_hides_claude_5_5_even_if_probe_available(self) -> None:
        """При выключенном флаге /v1/models не отдаёт ни одной claude-* модели."""
        self._allowlist(_ALLOWLIST)
        os.environ["BRIDGE_AGY_ANTHROPIC_ENABLED"] = "false"

        class _AlwaysOkProbe:
            def probe(self, model_id: str) -> Any:
                return mock.Mock(available=True, upstream_model=model_id, reason="ok")

        with mock.patch.object(self.srv, "_ANTHROPIC_PROBE", _AlwaysOkProbe()):
            ids = [item["id"] for item in self._catalog()["data"]]
        self.assertEqual(set(ids), _SERVED)

    def test_catalog_model_order_flag_gating_and_forbidden_claude_ids(self) -> None:
        """catalog_model_order() fail-closed при OFF и отсекает все запрещённые ID при ON."""
        self._allowlist(_ALLOWLIST)
        candidates = [
            "gemini-3.8-flash",
            "claude-sonnet-5-5-high",
            "claude-opus-5-5",
            "claude-sonnet-4-6",
            "claude-opus-4-6-thinking",
            "claude-haiku-5-5",
            "claude-sonnet-5-5-xhigh",
            "claude-opus-5-5-max",
            "claude-unknown-9-9",
        ]
        order_off = self.srv._ant_rt.catalog_model_order(
            "gemini-3.8-flash",
            candidates,
            self.srv._allowed_models_file(),
            self.logs.append,
            env={"BRIDGE_AGY_ANTHROPIC_ENABLED": "false"},
        )
        self.assertEqual(order_off, ["gemini-3.8-flash"])
        order_on = self.srv._ant_rt.catalog_model_order(
            "gemini-3.8-flash",
            candidates,
            self.srv._allowed_models_file(),
            self.logs.append,
            env={"BRIDGE_AGY_ANTHROPIC_ENABLED": "true"},
        )
        self.assertEqual(
            order_on,
            ["gemini-3.8-flash", "claude-sonnet-5-5-high", "claude-opus-5-5"],
        )

    def test_catalog_model_order_missing_and_polluted_allowlist_fail_closed(
        self,
    ) -> None:
        """Отсутствующий/пустой или загрязнённый claude-* allowlist не обходит флаг."""
        candidates = [
            "gemini-3.8-flash",
            "claude-sonnet-5-5-high",
            "claude-sonnet-4-6",
            "claude-haiku-5-5",
        ]
        # 1) Отсутствующий allowlist: OFF скрывает все claude-*, ON пускает только 5.5.
        self._allowlist(None)
        missing_off = self.srv._ant_rt.catalog_model_order(
            "gemini-3.8-flash",
            candidates,
            self.srv._allowed_models_file(),
            self.logs.append,
            env={"BRIDGE_AGY_ANTHROPIC_ENABLED": "false"},
        )
        self.assertEqual(missing_off, ["gemini-3.8-flash"])
        missing_on = self.srv._ant_rt.catalog_model_order(
            "gemini-3.8-flash",
            candidates,
            self.srv._allowed_models_file(),
            self.logs.append,
            env={"BRIDGE_AGY_ANTHROPIC_ENABLED": "true"},
        )
        self.assertEqual(missing_on, ["gemini-3.8-flash", "claude-sonnet-5-5-high"])

        # 2) Загрязнённый allowlist с claude-sonnet-5-5-high и claude-sonnet-4-6.
        self._allowlist(
            _ALLOWLIST + "claude-sonnet-5-5-high\nclaude-sonnet-4-6\nclaude-haiku-5-5\n"
        )
        polluted_off = self.srv._ant_rt.catalog_model_order(
            "gemini-3.8-flash",
            candidates,
            self.srv._allowed_models_file(),
            self.logs.append,
            env={"BRIDGE_AGY_ANTHROPIC_ENABLED": "false"},
        )
        self.assertEqual(polluted_off, ["gemini-3.8-flash"])
        polluted_on = self.srv._ant_rt.catalog_model_order(
            "gemini-3.8-flash",
            candidates,
            self.srv._allowed_models_file(),
            self.logs.append,
            env={"BRIDGE_AGY_ANTHROPIC_ENABLED": "true"},
        )
        self.assertEqual(polluted_on, ["gemini-3.8-flash", "claude-sonnet-5-5-high"])


if __name__ == "__main__":
    _ = unittest.main()
