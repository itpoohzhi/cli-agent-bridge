"""Существующие оракулы passthrough, выделенные для сохранения границ legacy."""

from __future__ import annotations

from adapters import ADAPTER_KINDS
from adapters.passthrough_adapter import PassthroughAdapter
from tests.bridge_testlib import load_raw_fleet
from core.backend_adapter import AdapterRegistry
from core.backend_adapter import FleetViolation
from core.backend_adapter import backend_entry_error
from core.backend_adapter import build_catalog
from core.backend_adapter import strip_bridge_secrets
from typing import Any
import copy
import os
import server
import tempfile
import unittest.mock


class TestFleetPassthroughKind(unittest.TestCase):
    def raw(self) -> Any:
        data = load_raw_fleet()
        return copy.deepcopy(data)

    def entry_error(self, **override: Any) -> Any:
        data = self.raw()
        data["backends"]["codex"].update(override)
        for key, value in list(data["backends"]["codex"].items()):
            if value is None:
                del data["backends"]["codex"][key]
        try:
            build_catalog(data, ADAPTER_KINDS)
        except FleetViolation as exc:
            return exc.reason
        return ""

    def test_live_fleet_declares_enabled_codex_passthrough_with_loopback_base_url(
        self,
    ) -> None:
        codex = self.raw()["backends"]["codex"]
        self.assertEqual(codex["kind"], "passthrough")
        self.assertEqual(codex["base_url"], "http://127.0.0.1:2455/v1")
        self.assertTrue(codex["enabled"])

    def test_live_fleet_declares_upstream_auth_environment_names(self) -> None:
        backends = self.raw()["backends"]
        for backend, env_name in (
            ("claude-p", "CLAUDE_P_BRIDGE_KEY"),
            ("agy", "AGY_BRIDGE_KEY"),
            ("opencode-zen", "OPENCODE_ZEN_BRIDGE_KEY"),
            ("codex", "CODEX_LB_API_KEY"),
        ):
            self.assertEqual(backends[backend]["api_key_env"], env_name)
            self.assertNotIn("api_key", backends[backend])

    def test_valid_entry_accepted(self) -> None:
        self.assertEqual(self.entry_error(), "")
        self.assertEqual(self.entry_error(enabled=True), "")

    def test_upstream_auth_config_validation(self) -> None:
        for config in (
            {"api_key_env": "TEST_UPSTREAM_KEY"},
            {"api_key": "config-key"},
            {"api_key_env": "TEST_UPSTREAM_KEY", "api_key": "config-key"},
        ):
            with self.subTest(config=config):
                self.assertEqual(self.entry_error(**config), "")
        for name in ("api_key_env", "api_key"):
            for invalid in (None, False, 123, [], {}):
                with self.subTest(name=name, invalid=invalid):
                    entry = {
                        "kind": "passthrough",
                        "base_url": "http://127.0.0.1:2455/v1",
                        name: invalid,
                    }
                    self.assertEqual(
                        backend_entry_error("test", entry, ADAPTER_KINDS),
                        f"backend_{name}_invalid",
                    )
            self.assertEqual(
                backend_entry_error(
                    "test", {"kind": "droid", name: "value"}, ADAPTER_KINDS
                ),
                "backend_key_unknown",
            )

    def test_base_url_validation_slugs(self) -> None:
        self.assertEqual(self.entry_error(base_url=None), "backend_base_url_missing")
        for bad in (
            "http://example.com/v1",
            "https://127.0.0.1:2455/v1",
            "http://127.0.0.1/v1",
            "http://127.0.0.1:2455/v2",
            "http://127.0.0.1:99999/v1",
            "http://localhost:2455/v1",
            5,
        ):
            with self.subTest(bad=bad):
                self.assertEqual(
                    self.entry_error(base_url=bad), "backend_base_url_invalid"
                )

    def test_base_url_rejected_for_other_kinds(self) -> None:
        data = self.raw()
        data["backends"]["droid"]["base_url"] = "http://127.0.0.1:2455/v1"
        with self.assertRaises(FleetViolation) as ctx:
            build_catalog(data, ADAPTER_KINDS)
        self.assertEqual(ctx.exception.reason, "backend_base_url_unexpected")

    def test_registry_builds_passthrough_adapter_without_spawn(self) -> None:
        data = self.raw()
        data["backends"]["codex"]["enabled"] = True
        catalog = build_catalog(data, ADAPTER_KINDS)
        registry = AdapterRegistry.from_fleet(catalog, ADAPTER_KINDS, lambda: catalog)
        adapter = registry.get("codex")
        self.assertIsInstance(adapter, PassthroughAdapter)
        self.assertEqual({m.id for m in adapter.get_models()}, {"gpt-6.1-terra", "gpt-6.1-sol"})
        self.assertTrue(adapter.is_healthy())
        self.assertIs(registry.adapter_for_model("gpt-6.1-terra"), adapter)


class TestBridgeSecrets(unittest.TestCase):
    def test_strip_bridge_secrets_drops_upstream_keys(self) -> None:
        env = {
            "CODEX_LB_API_KEY": "codex-secret",
            "CLAUDE_P_BRIDGE_KEY": "claude-secret",
            "AGY_BRIDGE_KEY": "agy-secret",
            "OPENCODE_ZEN_BRIDGE_KEY": "zen-secret",
            "BRIDGE_KEY": "hub-secret",
            "CUSTOM_BRIDGE_AUTH_KEY": "bridge-secret",
            "FACTORY_API_KEY": "fk-secret",
            "PATH": "/usr/bin",
            "HOME": "/tmp/home",
            "PORT": "9882",
        }
        self.assertIs(strip_bridge_secrets(env), env)
        self.assertEqual(
            env,
            {
                "FACTORY_API_KEY": "fk-secret",
                "PATH": "/usr/bin",
                "HOME": "/tmp/home",
                "PORT": "9882",
            },
        )


class TestClientTokenValidation(unittest.TestCase):
    def test_only_own_nonempty_upstream_token_is_accepted(self) -> None:
        adapter = PassthroughAdapter(
            "test", {"base_url": "http://127.0.0.1:2455/v1", "api_key": "ключ"}, dict
        )
        self.assertTrue(adapter.validate_client_token("ключ"))
        for token in ("", "other-backend-key", "клюЧ"):
            with self.subTest(token=token):
                self.assertFalse(adapter.validate_client_token(token))

    def test_unconfigured_upstream_does_not_authenticate_client_token(self) -> None:
        adapter = PassthroughAdapter(
            "test", {"base_url": "http://127.0.0.1:2455/v1"}, dict
        )
        self.assertFalse(adapter.validate_client_token(""))
        self.assertFalse(adapter.validate_client_token("client-key"))


class TestDirectLoopbackValidation(unittest.TestCase):
    def test_invalid_url_rejected_before_any_network_call(self) -> None:
        for url in (
            "http://example.com:2455/v1",
            "https://127.0.0.1:2455/v1",
            "http://127.0.0.1/v1",
            "http://127.0.0.1:0/v1",
            "http://127.0.0.1:65536/v1",
            "http://127.0.0.1:abc/v1",
            "http://user@127.0.0.1:2455/v1",
            "http://127.0.0.1:2455/v1?x=1",
            "http://127.0.0.1:2455/v1#x",
            "http://127.1:2455/v1",
            "http://localhost.evil:2455/v1",
            "",
            None,
        ):
            with (
                self.subTest(url=url),
                unittest.mock.patch("http.client.HTTPConnection") as connection,
            ):
                with self.assertRaises(ValueError):
                    PassthroughAdapter("codex", {"base_url": url}, dict)
                connection.assert_not_called()

    def test_approved_loopback_urls_accepted(self) -> None:
        for host in ("127.0.0.1", "localhost"):
            adapter = PassthroughAdapter(
                "codex", {"base_url": f"http://{host}:2455/v1"}, dict
            )
            self.assertEqual((adapter._host, adapter._port), (host, 2455))


class TestNeutralTimeoutLabel(unittest.TestCase):
    """Подпись таймаута в `Handler._error_body`: прежняя по умолчанию, нейтральная под флагом."""

    def _message(self, flag: str | None) -> str:
        env = {
            "BRIDGE_DYNAMIC_CONFIG_PATH": os.path.join(
                tempfile.mkdtemp(), "missing.json"
            )
        }
        if flag is not None:
            env["BRIDGE_CLI_NEUTRAL_NAMES_ENABLED"] = flag
        with unittest.mock.patch.dict(os.environ, env):
            if flag is None:
                os.environ.pop("BRIDGE_CLI_NEUTRAL_NAMES_ENABLED", None)
            body = server.Handler._error_body({"state": "timeout", "timeout_s": 5})
        return body["message"]

    def test_default_keeps_vendor_label(self) -> None:
        self.assertIn("droid exec timed out", self._message(None))

    def test_neutral_flag_removes_vendor_name_but_keeps_shape(self) -> None:
        message = self._message("true")
        self.assertIn("cli exec timed out", message)
        self.assertNotIn("droid", message)
