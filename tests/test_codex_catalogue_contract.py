"""Каталог fleet публикует обе exact codex-модели только при включённом backend."""

import json

from adapters import ADAPTER_KINDS
from core.backend_adapter import AdapterRegistry, build_catalog
from pathlib import Path


def test_codex_models_are_passthrough_and_enabled():
    data = json.loads((Path(__file__).resolve().parents[1] / "fleet.json").read_text())
    codex = data["backends"]["codex"]
    assert codex["kind"] == "passthrough"
    assert codex["base_url"] == "http://127.0.0.1:2455/v1"
    assert codex["enabled"] is True
    ids = {"gpt-6.1-terra", "gpt-6.1-sol"}
    assert {m["id"] for m in data["models"] if m["backend"] == "codex"} == ids
    for enabled in (False, True):
        codex["enabled"] = enabled
        catalog = build_catalog(data, ADAPTER_KINDS)
        registry = AdapterRegistry.from_fleet(catalog, ADAPTER_KINDS, lambda: catalog)
        published = {model.id for _, model in registry.models()}
        assert published & ids == (ids if enabled else set())
