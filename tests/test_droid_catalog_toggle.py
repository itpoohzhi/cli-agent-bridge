"""Kill-switch `BRIDGE_DROID_CATALOG_ENABLED` в рантайме: ON <-> OFF без рестарта и `_load_fleet()`."""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adapters import ADAPTER_KINDS  # noqa: E402
from core.catalog_flags import (  # noqa: E402
    FLAG_COMPILED_FLEET,
    FLAG_DROID_CATALOG,
    GatedCatalog,
    resolve_fleet_path,
)
from core.gated_registry import GatedRegistry  # noqa: E402


def srv() -> Any:
    """`server` при импорте строит каталог: лениво, чтобы сбой гейта был красным тестом."""
    return importlib.import_module("server")


def set_flag(enabled: bool) -> None:
    if enabled:
        os.environ[FLAG_DROID_CATALOG] = "1"
    else:
        os.environ.pop(FLAG_DROID_CATALOG, None)


def efforts(catalog: Any, model: str) -> tuple[list[str], str]:
    card = catalog["models"][model]
    return card["efforts"], card["default_effort"]


class DroidCatalogRuntimeToggleTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env = {"BRIDGE_DYNAMIC_CONFIG_PATH": str(Path(tmp.name) / "absent.json")}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in (FLAG_DROID_CATALOG, FLAG_COMPILED_FLEET):
            os.environ.pop(name, None)

    def build(self, enabled: bool) -> tuple[Any, GatedRegistry]:
        set_flag(enabled)
        catalog = srv()._load_fleet()
        registry = GatedRegistry.from_fleet(catalog, ADAPTER_KINDS, lambda: catalog, srv())
        return catalog, registry

    def assert_state(self, catalog: Any, registry: GatedRegistry, on: bool) -> None:
        adapter = registry.adapter_for_model("claude-sonnet-5-5")
        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.id if adapter else "", "claude-p")
        droid_adapter = registry.adapter_for_model("claude-sonnet-5-5-droid")
        self.assertEqual(droid_adapter is not None, on)
        if droid_adapter is not None:
            self.assertEqual(droid_adapter.id, "droid")
        self.assertEqual(registry.get("droid") is not None, on)
        published = {model.id for _adapter, model in registry.models()}
        # Профиль OFF скрывает базовый gpt-6.1-sol; при ON он маршрутизируется в codex.
        self.assertEqual("gpt-6.1-sol" in published, on)
        self.assertEqual(("droid" in [a.id for a in registry.adapters()]), on)
        self.assertEqual(len(catalog["aliases"]), 31 if on else 0)
        backend = catalog["models"]["claude-sonnet-5-5"]["backend"]
        self.assertEqual(backend, "claude-p")
        self.assertEqual("gpt-6.1-sol" in catalog["models"], on)

    def test_toggle_without_reload(self) -> None:
        for start in (False, True):
            with self.subTest(start=start):
                catalog, registry = self.build(start)
                self.assert_state(catalog, registry, start)
                for state in (not start, start, not start, start):
                    set_flag(state)
                    self.assert_state(catalog, registry, state)

    def test_toggle_with_compiled_flag_enabled(self) -> None:
        """`BRIDGE_DROID_CATALOG_ENABLED` выключает каталог независимо от compiled-флага."""
        os.environ[FLAG_COMPILED_FLEET] = "1"
        for start in (False, True):
            with self.subTest(start=start):
                catalog, registry = self.build(start)
                self.assert_state(catalog, registry, start)
                for state in (not start, start, not start, start):
                    set_flag(state)
                    self.assert_state(catalog, registry, state)

    def test_startup_selected_compiled_fleet_honors_runtime_kill_switch(self) -> None:
        """Compiled-каталог, выбранный `resolve_fleet_path`, тоже под гейтом и kill-switch."""
        with tempfile.TemporaryDirectory() as state:
            compiled = Path(state) / "fleet.compiled.json"
            compiled.write_bytes((srv().ROOT / "fleet.json").read_bytes())
            env = {"BRIDGE_STATE_DIR": state, FLAG_COMPILED_FLEET: "true", FLAG_DROID_CATALOG: "false"}
            with mock.patch.dict(os.environ, env):
                os.environ.pop("DROID_DSH_BRIDGE_FLEET", None)
                chosen = resolve_fleet_path(srv().ROOT / "fleet.json", ADAPTER_KINDS)
                self.assertEqual(chosen, compiled)
                with mock.patch.object(srv(), "FLEET_PATH", chosen):
                    catalog = srv()._load_fleet()
                self.assertIsInstance(catalog, GatedCatalog)
                registry = GatedRegistry.from_fleet(catalog, ADAPTER_KINDS, lambda: catalog, srv())
                for state_on in (False, True, False, True, False):
                    os.environ[FLAG_DROID_CATALOG] = "true" if state_on else "false"
                    self.assert_state(catalog, registry, state_on)

    def test_first_call_of_each_method_after_flip_is_fresh(self) -> None:
        calls = {
            "get": lambda r: r.get("droid") is not None,
            "adapters": lambda r: "droid" in [a.id for a in r.adapters()],
            "adapter_for_model": lambda r: r.adapter_for_model("gpt-6.1-sol") is not None,
            "models": lambda r: "gpt-6.1-sol" in {m.id for _a, m in r.models()},
        }
        for name, probe in calls.items():
            for on in (True, False):
                with self.subTest(method=name, on=on):
                    _catalog, registry = self.build(not on)
                    set_flag(on)
                    self.assertEqual(probe(registry), on)

    def test_flip_hook_fires_once_per_change(self) -> None:
        catalog, registry = self.build(False)
        seen: list[bool] = []
        catalog.add_listener(lambda cat: seen.append(True))
        registry.adapters()
        registry.adapters()
        self.assertEqual(seen, [])
        set_flag(True)
        registry.adapters()
        registry.adapters()
        self.assertEqual(len(seen), 1)
        set_flag(False)
        registry.adapters()
        self.assertEqual(len(seen), 2)

    def test_unchanged_adapters_survive_flip(self) -> None:
        _catalog, registry = self.build(False)
        codex = registry.get("codex")
        set_flag(True)
        self.assertIs(registry.get("codex"), codex)
        droid = registry.get("droid")
        set_flag(False)
        self.assertIs(registry.get("codex"), codex)
        set_flag(True)
        self.assertIs(registry.get("droid"), droid)

    def test_droid_adapter_instance_survives_on_off_on_cycle(self) -> None:
        """F-002: повторное включение возвращает тот же адаптер (семафор и слоты)."""
        for start in (True, False):
            with self.subTest(start=start):
                _catalog, registry = self.build(start)
                set_flag(True)
                first = registry.get("droid")
                self.assertIsNotNone(first)
                set_flag(False)
                self.assertIsNone(registry.get("droid"))
                set_flag(True)
                self.assertIs(registry.get("droid"), first)
                self.assertEqual([a.id for a in registry.adapters()].count("droid"), 1)

    def test_failed_reconcile_is_retried(self) -> None:
        """F-001/F-011/F-015: сбой подписчика не фиксирует состояние, следующий вызов повторяет."""
        catalog, registry = self.build(False)
        calls: list[object] = []

        def flaky(snap: Any) -> None:
            calls.append(snap)
            if len(calls) == 1:
                raise RuntimeError("boom")

        catalog.add_listener(flaky)
        set_flag(True)
        with self.assertRaises(RuntimeError):
            registry.adapters()
        backends = dict.__getitem__(catalog, "backends")
        self.assertFalse(backends["droid"]["enabled"])
        self.assert_state(catalog, registry, True)
        self.assertEqual(len(calls), 2)

    def test_failed_flip_reverts_registry_with_flag(self) -> None:
        """F-001/F-011: реестр не остаётся включённым, если флип упал, а флаг вернули."""
        catalog, registry = self.build(False)
        catalog.add_listener(mock.Mock(side_effect=RuntimeError("boom")))
        set_flag(True)
        with self.assertRaises(RuntimeError):
            registry.adapters()
        set_flag(False)
        self.assert_state(catalog, registry, False)

    def test_live_works_with_empty_adapter_set(self) -> None:
        """F-003.2: `_live()` не зависит от непустого набора адаптеров."""
        _catalog, registry = self.build(False)
        registry._adapters = {}
        set_flag(True)
        self.assertIsNotNone(registry.get("droid"))

    def test_listener_receives_plain_snapshot_without_reentry(self) -> None:
        """F-001.2: подписчик читает каталог во время флипа без рекурсии и получает `dict`."""
        catalog, _registry = self.build(False)
        seen: list[tuple[type, bool]] = []

        def listener(snap: Any) -> None:
            seen.append((type(snap), catalog["backends"]["droid"]["enabled"]))

        catalog.add_listener(listener)
        set_flag(True)
        self.assertTrue(catalog["backends"]["droid"]["enabled"])
        self.assertEqual(seen, [(dict, False)])

    def test_env_fleet_path_keeps_toggle(self) -> None:
        """F-005.1: заданный `DROID_DSH_BRIDGE_FLEET` не отключает рантайм-переключатель."""
        path = srv().ROOT / "fleet.json"
        env = {"DROID_DSH_BRIDGE_FLEET": str(path)}
        with mock.patch.dict(os.environ, env), mock.patch.object(srv(), "FLEET_PATH", path):
            catalog = srv()._load_fleet()
            self.assertIsInstance(catalog, GatedCatalog)
            registry = GatedRegistry.from_fleet(catalog, ADAPTER_KINDS, lambda: catalog, srv())
            for state in (False, True, False):
                set_flag(state)
                self.assert_state(catalog, registry, state)

    def test_off_catalog_restores_base_model_names(self) -> None:
        """F-004/F-010: имена возвращаются при выключенном флаге (`deepseek-v4.1-flash` — в другом тесте)."""
        catalog, _registry = self.build(False)
        names = {
            "claude-sonnet-5-5": "Claude Sonnet 5.5 (Claude-p bridge)",
            "gemini-3.8-flash": "Gemini 3.8 Flash (AGY bridge)",
        }
        for model, name in names.items():
            self.assertEqual(catalog["models"][model]["name"], name)
        self.assertNotIn("gpt-6.1-sol", catalog["models"])
        set_flag(True)
        sol = catalog["models"]["gpt-6.1-sol"]["name"]
        self.assertEqual(sol, "GPT-6.1 Sol (Codex passthrough)")
        set_flag(False)
        for model, name in names.items():
            self.assertEqual(catalog["models"][model]["name"], name)

    def test_efforts_follow_flag(self) -> None:
        catalog, _registry = self.build(False)
        for model in ("claude-haiku-5-5", "claude-opus-5-5", "claude-sonnet-5-5"):
            self.assertEqual(efforts(catalog, model), (["high"], "high"))
        set_flag(True)
        self.assertEqual(efforts(catalog, "claude-haiku-5-5"), (["low", "medium", "high"], "low"))
        set_flag(False)
        self.assertEqual(efforts(catalog, "claude-haiku-5-5"), (["high"], "high"))

    def test_catalog_keeps_meta_and_writes_across_flips(self) -> None:
        catalog, _registry = self.build(False)
        self.assertIsInstance(catalog, GatedCatalog)
        catalog["probe"] = "x"
        set_flag(True)
        self.assertNotIn("probe", catalog)
        self.assertEqual(catalog["path"], str(srv().FLEET_PATH))
        self.assertEqual(len(catalog["sha256"]), 64)
        self.assertIn("gpt-6.1-sol", catalog["models"])
        self.assertIn("gpt-6.1-sol", list(catalog["models"]))
        set_flag(False)
        self.assertNotIn("gpt-6.1-sol", catalog["models"])

    def test_reconcile_treats_missing_enabled_as_on(self) -> None:
        catalog, registry = self.build(False)
        codex = registry.get("codex")
        only = {"backends": {"codex": {"kind": "passthrough"}}}
        registry.reconcile(only)
        self.assertEqual([a.id for a in registry.adapters()], ["codex"])
        self.assertIs(registry.get("codex"), codex)

    def test_plain_catalog_registry_has_no_hook(self) -> None:
        plain = srv()._build_catalog(json.loads((srv().ROOT / "fleet.json").read_text("utf-8")))
        registry = GatedRegistry.from_fleet(plain, ADAPTER_KINDS, lambda: plain, srv())
        self.assertIsNotNone(registry.get("droid"))
        set_flag(True)
        self.assertIsNotNone(registry.get("droid"))
        self.assertIsNotNone(registry.get("codex"))


if __name__ == "__main__":
    unittest.main()
