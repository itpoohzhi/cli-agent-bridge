"""Targeted tests for neuralwatt (Standard non-flex) provider manifest and 100% routing priority."""
from __future__ import annotations

import json
from pathlib import Path

from adapters import ADAPTER_KINDS
from core.fleet_compiler import compile_from_disk
from core.provider_manifest import load_manifests, providers_dir
from core.transport_routing import route_order

ROOT = Path(__file__).resolve().parents[1]


def test_neuralwatt_standard_manifest_loaded_and_valid() -> None:
    loaded = load_manifests(providers_dir(), ADAPTER_KINDS)
    by_id = {m.provider_id: m for m in loaded.manifests}
    assert "neuralwatt" in by_id
    assert "neuralwatt-flex" in by_id  # flex transport stays intact
    m = by_id["neuralwatt"]
    assert m.kind == "passthrough"
    assert m.enabled is True
    assert m.priority == 5
    assert m.routing.weight == 100
    assert m.owned_by == "neuralwatt"
    assert m.limits.max_concurrent == 2
    assert m.limits.quota_group == "neuralwatt"
    assert m.limits.timeout_s == 300
    # Единый активный OpenCode Go остаётся включённым failover-резервом (weight 0)
    assert by_id["opencode-go"].enabled is True
    assert by_id["opencode-go"].routing.weight == 0
    assert by_id["opencode-go-sub1"].enabled is False
    assert by_id["opencode-go-sub1"].routing.weight == 0
    assert by_id["opencode-go-sub2"].enabled is False
    assert by_id["opencode-go-sub2"].routing.weight == 0


def test_neuralwatt_standard_100_percent_routing_and_failover_order() -> None:
    fleet = json.loads((ROOT / "fleet.json").read_text(encoding="utf-8"))
    assert "neuralwatt" in fleet["backends"]
    assert "neuralwatt-flex" in fleet["backends"]
    backend = fleet["backends"]["neuralwatt"]
    assert backend["base_url"] == "http://127.0.0.1:10830/neuralwatt/v1"
    assert backend["api_key_env"] == "NEURALWATT_API_KEY"
    assert backend["max_concurrent"] == 2

    models_by_id = {m["id"]: m for m in fleet["models"]}
    ds = models_by_id["deepseek-v4.1-flash"]
    assert ds["backend"] == "neuralwatt"
    assert ds["name"] == "DeepSeek V4.1 Flash (NeuralWatt)"
    assert ds["efforts"] == ["off", "low", "high", "max"]
    assert ds["default_effort"] == "high"
    assert ds["context_window"] == 1048560
    assert ds["max_tokens"] == 393216

    routes = {r["backend"]: (r["weight"], r["priority"]) for r in ds["routing"]["routes"]}
    assert routes == {
        "neuralwatt": (100, 5),
        "opencode-go": (0, 10),
        "deepseek-direct": (0, 20),
    }
    for i in range(100):
        order = list(route_order("deepseek-v4.1-flash", ds, f"seed-{i}"))
        assert order == ["neuralwatt", "opencode-go", "deepseek-direct"]

    # Новые модели NeuralWatt Standard и Flex
    assert models_by_id["glm-5.3-flash"]["backend"] == "neuralwatt"
    assert models_by_id["kimi-k3.1-pro-flex"]["backend"] == "neuralwatt-flex"
    assert models_by_id["deepseek-v4.1-flash-flex"]["backend"] == "neuralwatt-flex"
    assert models_by_id["glm-5.3-flex"]["backend"] == "neuralwatt-flex"
    assert models_by_id["mimo-v2.6-pro-flex"]["backend"] == "neuralwatt-flex"


def test_compile_from_disk_accepts_neuralwatt_and_flex_together() -> None:
    res = compile_from_disk(kinds=ADAPTER_KINDS)
    assert "neuralwatt" not in res.rejected_providers
    assert "neuralwatt-flex" not in res.rejected_providers
    assert "neuralwatt" in res.fleet["backends"]
    assert "neuralwatt-flex" in res.fleet["backends"]
    ds_entry = next(m for m in res.fleet["models"] if m["id"] == "deepseek-v4.1-flash")
    assert ds_entry["backend"] == "neuralwatt"
