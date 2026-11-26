"""Default-off гейт маршрутов `droid` в корневом fleet.json (`BRIDGE_DROID_CATALOG_ENABLED`)."""

from __future__ import annotations

import copy
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

from core.catalog_flags import FLAG_COMPILED_FLEET, FLAG_DROID_CATALOG, GatedCatalog  # noqa: E402
from core.catalog_flags import apply_droid_catalog_gate, droid_catalog_enabled  # noqa: E402
from core.gated_registry import GatedRegistry, gated_catalog  # noqa: E402
from core.runtime_env import ConfigSnapshotError, DynamicFlagSource  # noqa: E402

FLEET_FILE = Path(__file__).resolve().parent.parent / "fleet.json"
_LMH = ("low", "medium", "high")
# Эталон — актуальный fleet.json: без хардкодов моделей/алиасов, только инварианты droid_off.
BASE_NAMES = {"gemini-3.8-flash": "Gemini 3.8 Flash (AGY bridge)"}
BASE_DROID_BACKEND = dict(kind="droid", enabled=False, owned_by="factory-droid", max_concurrent=64)
ALIAS_COUNT = 67  # число алиасов fleet.json; droid_off их не трогает
DROID_ONLY = frozenset({"claude-sonnet-5-5-droid", "gemini-3.8-flash-droid", "gpt-6.1-sol-droid"})


def srv() -> Any:
    """`server` при импорте строит каталог: в тестах он нужен лениво, чтобы сбой был красным тестом."""
    return importlib.import_module("server")


def raw_fleet() -> dict[str, Any]:
    return json.loads(FLEET_FILE.read_text(encoding="utf-8"))


def routes(data: dict[str, Any]) -> dict[str, str]:
    return {m["id"]: m["backend"] for m in data["models"]}


def droid_on_bytes() -> bytes:
    """fleet.json с включённым `droid`: то, что гейт переключает флагом."""
    raw = raw_fleet()
    raw["backends"]["droid"]["enabled"] = True
    return json.dumps(raw).encode()


def effective(models: Any) -> dict[str, tuple[str, tuple[str, ...], str]]:
    items = models.values() if isinstance(models, dict) else models
    return {m["id"]: (m["backend"], tuple(m["efforts"]), m["default_effort"]) for m in items}


def base_effective(raw: dict[str, Any]) -> dict[str, tuple[str, tuple[str, ...], str]]:
    """Ожидаемый каталог при выключенном флаге: fleet.json + backend-override droid_off."""
    patch = raw["technical_ref"]["droid_off"].get("models", {})
    return {mid: (patch.get(mid, {}).get("backend", b), e, d) for mid, (b, e, d) in effective(raw["models"]).items()}


class DroidCatalogFlagTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env = {"BRIDGE_DYNAMIC_CONFIG_PATH": str(Path(tmp.name) / "absent.json")}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in (FLAG_DROID_CATALOG, FLAG_COMPILED_FLEET, "DROID_DSH_BRIDGE_FLEET"):
            os.environ.pop(name, None)

    def test_flag_name_and_default_off(self) -> None:
        self.assertEqual(FLAG_DROID_CATALOG, "BRIDGE_DROID_CATALOG_ENABLED")
        self.assertFalse(DynamicFlagSource(FLAG_DROID_CATALOG).enabled())
        self.assertFalse(droid_catalog_enabled())

    def test_enabled_only_by_droid_flag(self) -> None:
        with mock.patch.dict(os.environ, {FLAG_DROID_CATALOG: "1"}):
            self.assertTrue(droid_catalog_enabled())
        with mock.patch.dict(os.environ, {FLAG_COMPILED_FLEET: "1"}):
            self.assertFalse(droid_catalog_enabled())
        with mock.patch.dict(os.environ, {FLAG_COMPILED_FLEET: "1", FLAG_DROID_CATALOG: "0"}):
            self.assertFalse(droid_catalog_enabled())

    def test_reader_failure_keeps_last_known_state(self) -> None:
        """F-014: транзиентный сбой чтения не флипает включённый флаг в выключенный."""

        def broken(_name: str) -> bool:
            raise RuntimeError("gigarc down")

        self.assertTrue(droid_catalog_enabled(broken, fallback=True))
        self.assertFalse(droid_catalog_enabled(broken))
        self.assertFalse(droid_catalog_enabled(lambda _name: False, fallback=True))

    def test_snapshot_error_keeps_state(self) -> None:
        """F-014: `ConfigSnapshotError` реального источника не флипает состояние."""
        broken = mock.patch("core.runtime_env.read_config_snapshot", side_effect=ConfigSnapshotError("x"))
        for flag in ("1", "0"):
            os.environ[FLAG_DROID_CATALOG] = flag
            catalog, want = GatedCatalog({"a": "on"}, {"a": "off"}), flag == "1"
            with broken:
                self.assertEqual(catalog["a"], "on" if want else "off")
                self.assertEqual(droid_catalog_enabled(fallback=want), want)
                self.assertFalse(droid_catalog_enabled())
                self.assertFalse(DynamicFlagSource(FLAG_DROID_CATALOG).enabled())

    def test_failed_flip_rolls_back_listeners(self) -> None:
        """F-001/F-011: сбой второго подписчика откатывает первого, возврат флага не рассинхронит."""
        seen: list[Any] = []
        catalog = GatedCatalog({"a": "on"}, {"a": "off"})
        catalog.add_listener(seen.append)
        catalog.add_listener(mock.Mock(side_effect=RuntimeError("boom")))
        os.environ[FLAG_DROID_CATALOG] = "1"
        with self.assertRaises(RuntimeError):
            catalog.sync()
        self.assertEqual(seen, [{"a": "on"}, {"a": "off"}])
        os.environ.pop(FLAG_DROID_CATALOG)
        self.assertEqual((catalog["a"], len(seen)), ("off", 2))

    def test_flip_replaces_foreign_keys(self) -> None:
        """F-016: смена флага заменяет каталог снимком целиком."""
        catalog = GatedCatalog({"a": "on"}, {"a": "off"})
        catalog["extra"] = "stale"
        os.environ[FLAG_DROID_CATALOG] = "1"
        self.assertEqual(dict(catalog), {"a": "on"})

    def test_gate_off_keeps_other_sections(self) -> None:
        raw = raw_fleet()
        before = copy.deepcopy(raw)
        gated: Any = apply_droid_catalog_gate(raw, enabled=False)
        self.assertEqual(raw, before)
        self.assertEqual(set(gated["backends"]), set(raw["backends"]))
        for name, backend in raw["backends"].items():
            if name != "droid":
                self.assertEqual(gated["backends"][name], backend)
        self.assertEqual(gated["backends"]["droid"]["kind"], raw["backends"]["droid"]["kind"])
        skip = ("backends", "models", "aliases")
        self.assertEqual({k: v for k, v in gated.items() if k not in skip}, {k: v for k, v in raw.items() if k not in skip})
        self.assertEqual(gated["aliases"], raw["aliases"])
        self.assertEqual(len(gated["aliases"]), ALIAS_COUNT)

    def test_gate_off_restores_base_efforts(self) -> None:
        """W1B-001: default-off сохраняет и маршрут, и efforts/default_effort базы."""
        raw = raw_fleet()
        gated = effective(apply_droid_catalog_gate(raw, enabled=False)["models"])
        self.assertEqual(gated, base_effective(raw))
        self.assertEqual(gated["claude-haiku-5-5"][1:], (_LMH, "low"))
        self.assertEqual(gated["claude-opus-5-5"], effective(raw["models"])["claude-opus-5-5"])

    def test_load_fleet_off_matches_base_effective_catalog(self) -> None:
        """W1B-001: каталог сервера при выключенных флагах совпадает с базой по active-моделям."""
        got = effective(srv()._load_fleet()["models"])
        want = {mid: v for mid, v in base_effective(raw_fleet()).items() if mid not in DROID_ONLY}
        self.assertEqual(got, want)

    def test_gate_on_keeps_droid_routes(self) -> None:
        raw = raw_fleet()
        gated: Any = apply_droid_catalog_gate(raw, enabled=True)
        self.assertEqual(gated, raw)
        self.assertEqual(gated["backends"]["droid"], raw["backends"]["droid"])
        self.assertEqual(list(routes(gated).values()).count("droid"), len(DROID_ONLY))
        self.assertEqual(len(gated["aliases"]), ALIAS_COUNT)

    def test_gate_off_tolerates_malformed_entries(self) -> None:
        raw: dict[str, Any] = {"schema_version": 3, "backends": {"droid": "broken"}, "models": ["broken", {"id": "x"}], "technical_ref": {"droid_off": {"models": {"x": {"backend": "agy"}}}}}
        gated: Any = apply_droid_catalog_gate(raw, enabled=False)
        self.assertEqual(gated["backends"]["droid"], "broken")
        self.assertEqual(gated["models"], ["broken", {"id": "x", "backend": "agy"}])
        odd: dict[str, Any] = {"schema_version": 3, "models": "broken"}
        self.assertEqual(apply_droid_catalog_gate(odd, enabled=False), odd)

    def test_gate_off_null_patch_drops_model(self) -> None:
        """F-001: `null` в droid_off.models убирает модель, остальные записи сохраняются."""
        raw: dict[str, Any] = {"schema_version": 3, "models": ["broken", {"id": "a"}, {"id": "b"}, {"id": "c"}], "technical_ref": {"droid_off": {"models": {"a": None, "b": {"name": "B"}}}}}
        gated: Any = apply_droid_catalog_gate(raw, enabled=False)
        self.assertEqual(gated["models"], ["broken", {"id": "b", "name": "B"}, {"id": "c"}])
        self.assertEqual(apply_droid_catalog_gate(raw, enabled=True)["models"], raw["models"])

    def test_gate_off_without_profile_only_disables_droid(self) -> None:
        """F-005.2: без профиля нет чужих alias/backend, выключается только `droid`."""
        raw: dict[str, Any] = {"schema_version": 3, "backends": {"droid": {"kind": "droid", "enabled": True}}, "aliases": {"keep": {"backend_id": "x"}}, "models": [{"id": "m", "backend": "droid"}]}
        before = copy.deepcopy(raw)
        gated: Any = apply_droid_catalog_gate(raw, enabled=False)
        self.assertEqual(raw, before)
        self.assertFalse(gated["backends"]["droid"]["enabled"])
        self.assertEqual(gated["aliases"], before["aliases"])
        self.assertEqual(gated["models"], before["models"])
        no_droid: dict[str, Any] = {"schema_version": 3, "backends": {"agy": {}}}
        self.assertEqual(apply_droid_catalog_gate(no_droid, enabled=False), no_droid)

    def test_gate_off_restores_base_catalog_in_full(self) -> None:
        """F-004/F-010: профиль droid_off сохраняет имена, aliases и компактный backend."""
        gated: Any = apply_droid_catalog_gate(raw_fleet(), enabled=False)
        by_id = {m["id"]: m for m in gated["models"]}
        for mid, name in BASE_NAMES.items():
            self.assertEqual(by_id[mid]["name"], name)
        self.assertEqual(gated["backends"]["droid"], BASE_DROID_BACKEND)
        self.assertEqual(gated["aliases"], raw_fleet()["aliases"])
        self.assertEqual({m["id"] for m in gated["models"]}, set(effective(raw_fleet()["models"])))

    def test_schema_gate(self) -> None:
        """F-006.1: схема 2 не трогается, схема 4 под гейтом (fail-closed)."""
        two: dict[str, Any] = {"schema_version": 2, "models": [{"id": "x", "backend": "droid"}]}
        self.assertEqual(apply_droid_catalog_gate(two, enabled=False), two)
        four: dict[str, Any] = {"schema_version": 4, "backends": {"droid": {"enabled": True}}}
        gated_four: Any = apply_droid_catalog_gate(four, enabled=False)
        self.assertFalse(gated_four["backends"]["droid"]["enabled"])

    def test_reconcile_passes_models_and_order_to_make(self) -> None:
        """F-002: новый бэкенд создаётся с полным каталогом и `backend_order`."""
        reg, made = GatedRegistry(), []
        reg._make = lambda sub: made.append(sub) or mock.Mock(_adapters={"droid": 1})
        reg.reconcile({"models": [{"id": "m"}], "backends": {"droid": {"enabled": True}}})
        self.assertEqual((made[0]["models"], made[0]["backend_order"]), ([{"id": "m"}], ["droid"]))
        self.assertEqual(reg._adapters, {"droid": 1})

    def test_gated_catalog_follows_droid_off_profile(self) -> None:
        built: Any = gated_catalog(droid_on_bytes(), srv()._build_catalog)
        self.assertIsInstance(built, GatedCatalog)
        self.assertFalse(built["backends"]["droid"]["enabled"])
        with mock.patch.dict(os.environ, {FLAG_DROID_CATALOG: "1"}):
            self.assertTrue(built["backends"]["droid"]["enabled"])
        plain = json.loads(droid_on_bytes())
        del plain["technical_ref"]["droid_off"]
        synthetic = gated_catalog(json.dumps(plain).encode(), lambda data: data)
        self.assertEqual(synthetic, plain)
        self.assertNotIsInstance(synthetic, GatedCatalog)
        self.assertEqual(gated_catalog(b"[1]", lambda data: data), [1])

    def test_load_fleet_explicit_path_is_gated(self) -> None:
        """F-005.1: путь каталога не отключает гейт, пока в каталоге есть профиль."""
        explicit = Path(tempfile.gettempdir()) / "x.json"
        with mock.patch.object(srv(), "FLEET_PATH", explicit), mock.patch.object(Path, "read_bytes", return_value=droid_on_bytes()):
            catalog = srv()._load_fleet()
        self.assertIsInstance(catalog, GatedCatalog)
        self.assertFalse(catalog["backends"]["droid"]["enabled"])
        self.assertNotIn("gpt-6.1-sol-droid", catalog["models"])

    def test_load_fleet_env_fleet_path_keeps_gate(self) -> None:
        """F-005.1: `DROID_DSH_BRIDGE_FLEET` на штатный `fleet.json` не открывает fail-open."""
        env = {"DROID_DSH_BRIDGE_FLEET": str(FLEET_FILE)}
        with mock.patch.dict(os.environ, env), mock.patch.object(srv(), "FLEET_PATH", FLEET_FILE), mock.patch.object(Path, "read_bytes", return_value=droid_on_bytes()):
            catalog = srv()._load_fleet()
            self.assertIsInstance(catalog, GatedCatalog)
            self.assertFalse(catalog["backends"]["droid"]["enabled"])
            os.environ[FLAG_DROID_CATALOG] = "1"
            self.assertTrue(catalog["backends"]["droid"]["enabled"])
            self.assertIn("gpt-6.1-sol-droid", catalog["models"])

    def test_load_fleet_synthetic_explicit_catalog_is_plain(self) -> None:
        plain = json.loads(droid_on_bytes())
        del plain["technical_ref"]["droid_off"]
        explicit = Path(tempfile.gettempdir()) / "x.json"
        with mock.patch.object(srv(), "FLEET_PATH", explicit), mock.patch.object(Path, "read_bytes", return_value=json.dumps(plain).encode()):
            catalog = srv()._load_fleet()
        self.assertNotIsInstance(catalog, GatedCatalog)
        self.assertTrue(catalog["backends"]["droid"]["enabled"])
        self.assertIn("gpt-6.1-sol-droid", catalog["models"])

    def test_gated_catalog_methods_follow_flag(self) -> None:
        """F-003.1: `len`, `==`, `copy`, `keys` и `items` тоже применяют флаг."""
        built: Any = gated_catalog(droid_on_bytes(), srv()._build_catalog)
        self.assertNotIn("gpt-6.1-sol-droid", built["models"])
        os.environ[FLAG_DROID_CATALOG] = "1"
        self.assertIn("gpt-6.1-sol-droid", built.copy()["models"])
        os.environ.pop(FLAG_DROID_CATALOG)
        self.assertNotIn("gpt-6.1-sol-droid", dict(built.items())["models"])
        os.environ[FLAG_DROID_CATALOG] = "1"
        self.assertIn("gpt-6.1-sol-droid", list(built.values())[list(built.keys()).index("models")])
        self.assertEqual(len(built), len(built.copy()))
        self.assertEqual(built, built.copy())

    def test_load_fleet_enabled(self) -> None:
        for extra in ({}, {FLAG_COMPILED_FLEET: "1"}):
            env = {FLAG_DROID_CATALOG: "1", **extra}
            with self.subTest(env=sorted(env)), mock.patch.dict(os.environ, env), mock.patch.object(Path, "read_bytes", return_value=droid_on_bytes()):
                catalog = srv()._load_fleet()
                self.assertTrue(catalog["backends"]["droid"]["enabled"])
                self.assertEqual((catalog["models"]["gpt-6.1-sol"]["backend"], catalog["models"]["gpt-6.1-sol-droid"]["backend"]), ("codex", "droid"))
                self.assertEqual(len(catalog["aliases"]), ALIAS_COUNT)


if __name__ == "__main__":
    unittest.main()
