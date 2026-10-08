"""Контракт `BackendAdapter` и `AdapterRegistry` (ADR 0002, AC-002).

Проверяется на фейковом адаптере и на реальных DroidAdapter/MuseAdapter: набор методов,
маппинг модель -> адаптер, отказ от загрузки кода из конфигурации, изоляция сбоя shutdown.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from adapters import ADAPTER_KINDS, DroidAdapter, MuseAdapter  # noqa: E402
from core.backend_adapter import (  # noqa: E402
    AdapterRegistry,
    BackendAdapter,
    BackendNotSupported,
)

CONTRACT_METHODS = (
    "get_models",
    "qualify",
    "is_healthy",
    "spawn_session",
    "execute_turn",
    "close_session",
    "shutdown",
)


def catalog():
    models = {
        "a-1": {"id": "a-1", "backend": "alpha", "context_window": 1},
        "a-2": {"id": "a-2", "backend": "alpha", "context_window": 2},
        "b-1": {"id": "b-1", "backend": "beta", "context_window": 3},
    }
    return {
        "order": ["a-1", "b-1", "a-2"],
        "models": models,
        "backend_order": ["alpha", "beta", "gamma"],
        "backends": {
            "alpha": {"kind": "fake", "enabled": True, "max_concurrent": 2},
            "beta": {"kind": "fake", "enabled": True, "owned_by": "bee"},
            "gamma": {"kind": "fake", "enabled": False},
        },
    }


class FakeAdapter(BackendAdapter):
    kind = "fake"
    stopped = []

    def get_models(self):
        return self._catalog_models()

    def qualify(self):
        return (True, "ok")

    def is_healthy(self):
        return True

    def spawn_session(self, ctx):
        raise BackendNotSupported("none")

    def execute_turn(self, ctx, sse_writer):
        return {"state": "done", "rc": 0, "text": self.id, "usage": {}, "err": ""}

    def close_session(self, sid):
        return None

    def shutdown(self):
        FakeAdapter.stopped.append(self.id)


class ExplodingAdapter(FakeAdapter):
    def shutdown(self):
        super().shutdown()
        raise RuntimeError("boom")


class TestInterface(unittest.TestCase):
    def test_interface_is_abstract(self):
        with self.assertRaises(TypeError):
            BackendAdapter("x", {}, dict)  # type: ignore[abstract]

    def test_missing_method_keeps_class_abstract(self):
        for name in CONTRACT_METHODS:
            namespace = {m: (lambda self, *a, **k: None) for m in CONTRACT_METHODS}
            namespace.pop(name)
            partial = type("Partial", (BackendAdapter,), namespace)
            with self.assertRaises(TypeError, msg=name):
                partial("x", {}, dict)

    def test_abstract_methods_are_exactly_the_contract(self):
        self.assertEqual(set(BackendAdapter.__abstractmethods__), set(CONTRACT_METHODS))

    def test_adapter_kinds_are_hard_coded_in_code(self):
        self.assertEqual(set(ADAPTER_KINDS), {"droid", "muse"})
        self.assertIs(ADAPTER_KINDS["droid"], DroidAdapter)
        self.assertIs(ADAPTER_KINDS["muse"], MuseAdapter)
        for cls in ADAPTER_KINDS.values():
            self.assertTrue(issubclass(cls, BackendAdapter))
            self.assertFalse(getattr(cls, "__abstractmethods__", None))


class TestRegistry(unittest.TestCase):
    def build(self, cat=None):
        cat = cat or catalog()
        return AdapterRegistry.from_fleet(cat, {"fake": FakeAdapter}, lambda: cat), cat

    def test_from_fleet_skips_disabled_and_keeps_order(self):
        registry, _ = self.build()
        self.assertEqual([a.id for a in registry.adapters()], ["alpha", "beta"])
        self.assertIsNone(registry.get("gamma"))

    def test_model_to_adapter_mapping(self):
        registry, _ = self.build()
        self.assertEqual(registry.adapter_for_model("a-2").id, "alpha")
        self.assertEqual(registry.adapter_for_model("b-1").id, "beta")
        self.assertIsNone(registry.adapter_for_model("nope"))

    def test_models_union_follows_catalog_order_per_adapter(self):
        registry, _ = self.build()
        union = [(a.id, m["id"]) for a, m in registry.models()]
        self.assertEqual(union, [("alpha", "a-1"), ("alpha", "a-2"), ("beta", "b-1")])

    def test_catalog_is_read_lazily(self):
        registry, cat = self.build()
        del cat["models"]["a-2"]
        cat["order"].remove("a-2")
        self.assertIsNone(registry.adapter_for_model("a-2"))

    def test_defaults_and_totals(self):
        registry, _ = self.build()
        alpha, beta = registry.adapters()
        self.assertEqual((alpha.owned_by, beta.owned_by), ("alpha", "bee"))
        self.assertEqual((alpha.max_concurrent, beta.max_concurrent), (2, 1))
        self.assertEqual(registry.max_concurrent_total(), 3)
        self.assertEqual(registry.active_total(), 0)
        self.assertTrue(alpha.preflight()[0])

    def test_duplicate_backend_id_rejected(self):
        registry, cat = self.build()
        with self.assertRaises(ValueError):
            registry.register(FakeAdapter("alpha", {}, lambda: cat))

    def test_unknown_kind_cannot_load_code(self):
        cat = catalog()
        cat["backends"]["alpha"]["kind"] = "os.system"
        with self.assertRaises(ValueError):
            AdapterRegistry.from_fleet(cat, {"fake": FakeAdapter}, lambda: cat)

    def test_shutdown_isolated_and_exclude(self):
        cat = catalog()
        FakeAdapter.stopped = []
        registry = AdapterRegistry()
        registry.register(ExplodingAdapter("alpha", {}, lambda: cat))
        registry.register(FakeAdapter("beta", {}, lambda: cat))
        registry.shutdown()
        self.assertEqual(FakeAdapter.stopped, ["alpha", "beta"])
        FakeAdapter.stopped = []
        registry.shutdown(exclude=("alpha",))
        self.assertEqual(FakeAdapter.stopped, ["beta"])


class TestRealAdapters(unittest.TestCase):
    """Droid и Muse подчиняются одному контракту; поведение droid-моделей не меняется."""

    def test_server_registry_has_both_backends_from_fleet(self):
        ids = {a.id: a for a in server.BACKENDS.adapters()}
        self.assertEqual(set(ids), {"droid", "muse"})
        self.assertIsInstance(ids["droid"], DroidAdapter)
        self.assertIsInstance(ids["muse"], MuseAdapter)
        self.assertTrue(ids["droid"].required)
        self.assertFalse(ids["muse"].required)

    def test_model_routing(self):
        reg = server.BACKENDS
        for mid in server.FLEET["order"]:
            expected = "muse" if mid.startswith("muse-") else "droid"
            self.assertEqual(reg.adapter_for_model(mid).id, expected, mid)
            self.assertEqual(server.FLEET["models"][mid]["backend"], expected)

    def test_each_adapter_exposes_contract_and_capabilities(self):
        for adapter in server.BACKENDS.adapters():
            for name in CONTRACT_METHODS:
                self.assertTrue(callable(getattr(adapter, name)), name)
            ok, reason = adapter.qualify()
            self.assertIsInstance(ok, bool)
            self.assertIsInstance(reason, str)
            self.assertIsInstance(adapter.is_healthy(), bool)
            self.assertTrue(adapter.get_models())
            for model in adapter.get_models():
                self.assertEqual(model["backend"], adapter.id)
            self.assertIn(adapter.capabilities["sessions"], ("resident", "none"))
            with self.assertRaises(BackendNotSupported):
                adapter.spawn_session({})
            adapter.close_session("no-such-sid")

    def test_droid_health_follows_receipt_state(self):
        droid = server.BACKENDS.get("droid")
        saved = server._receipt_state
        try:
            server._receipt_state = lambda: "invalid"
            self.assertFalse(droid.is_healthy())
            self.assertEqual(droid.qualify(), (False, "receipt_invalid"))
            server._receipt_state = lambda: "ok"
            self.assertTrue(droid.is_healthy())
            self.assertEqual(droid.qualify(), (True, "receipt_ok"))
        finally:
            server._receipt_state = saved

    def test_droid_capacity_is_host_pool_cap(self):
        droid = server.BACKENDS.get("droid")
        self.assertEqual(droid.max_concurrent, server.MAX_CONCURRENT)


if __name__ == "__main__":
    unittest.main()
