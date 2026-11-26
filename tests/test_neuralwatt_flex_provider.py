"""Targeted tests for neuralwatt-flex provider manifest and compiled fleet entry."""
from __future__ import annotations

import json
from pathlib import Path

from adapters import ADAPTER_KINDS
from core.fleet_compiler import compile_from_disk
from core.provider_manifest import load_manifests, providers_dir

ROOT = Path(__file__).resolve().parents[1]


def test_neuralwatt_flex_manifest_loaded_and_valid() -> None:
    loaded = load_manifests(providers_dir(), ADAPTER_KINDS)
    by_id = {m.provider_id: m for m in loaded.manifests}
    assert "neuralwatt-flex" in by_id
    m = by_id["neuralwatt-flex"]
    assert m.kind == "passthrough"
    assert m.enabled is True
    assert m.owned_by == "neuralwatt-flex"
    assert m.limits.max_concurrent == 8
    assert m.limits.timeout_s == 600


def test_neuralwatt_flex_compiled_into_fleet_json() -> None:
    fleet = json.loads((ROOT / "fleet.json").read_text(encoding="utf-8"))
    assert "neuralwatt-flex" in fleet["backends"]
    backend = fleet["backends"]["neuralwatt-flex"]
    assert backend["base_url"] == "http://127.0.0.1:10830/neuralwatt/v1"
    assert backend["api_key_env"] == "NEURALWATT_API_KEY"
    assert backend["max_concurrent"] == 8

    models_by_id = {m["id"]: m for m in fleet["models"]}
    assert "kimi-k3.1-pro-flex" in models_by_id
    assert models_by_id["kimi-k3.1-pro"]["backend"] == "dashscope-intl"
    kimi = models_by_id["kimi-k3.1-pro-flex"]
    assert kimi["backend"] == "neuralwatt-flex"
    assert kimi["name"] == "Kimi K3.1 Pro Flex (NeuralWatt)"
    assert kimi["efforts"] == ["high", "max"]
    assert kimi["default_effort"] == "high"
    assert kimi["context_window"] == 1000000
    assert kimi["max_tokens"] == 131072

    assert "deepseek-v4.1-flash-flex" in models_by_id
    ds = models_by_id["deepseek-v4.1-flash-flex"]
    assert ds["backend"] == "neuralwatt-flex"
    assert ds["name"] == "DeepSeek V4.1 Flash Flex (NeuralWatt)"
    assert ds["efforts"] == ["off", "low", "high", "xhigh", "max"]
    assert ds["default_effort"] == "high"
    assert ds["context_window"] == 1048560
    assert ds["max_tokens"] == 393216

    # Existing deepseek-v4.1-flash route stays untouched on opencode-go / deepseek-direct
    assert models_by_id["deepseek-v4.1-flash"]["backend"] != "neuralwatt-flex"

    assert fleet["aliases"]["kimi-k3.1-pro-flex-high"]["effort"] == "high"
    assert fleet["aliases"]["kimi-k3.1-pro-flex-max"]["effort"] == "max"
    for eff in ("off", "low", "high", "xhigh", "max"):
        alias = fleet["aliases"][f"deepseek-v4.1-flash-flex-{eff}"]
        assert alias["backend_id"] == "deepseek-v4.1-flash-flex"
        assert alias["backend"] == "neuralwatt-flex"
        assert alias["effort"] == eff


def test_compile_from_disk_accepts_neuralwatt_flex() -> None:
    res = compile_from_disk(kinds=ADAPTER_KINDS)
    assert "neuralwatt-flex" not in res.rejected_providers
    assert "neuralwatt-flex" in res.fleet["backends"]
    ds_entry = next(m for m in res.fleet["models"] if m["id"] == "deepseek-v4.1-flash-flex")
    assert ds_entry["backend"] == "neuralwatt-flex"
