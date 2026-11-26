"""Targeted tests for Alibaba DashScope International (SG proxy /sg-qwen) manifests and 4-key failover."""
from __future__ import annotations

import json
from pathlib import Path

from adapters import ADAPTER_KINDS
from core.fleet_compiler import compile_from_disk
from core.provider_manifest import load_manifests, providers_dir
from core.transport_routing import route_order

ROOT = Path(__file__).resolve().parents[1]
DASHSCOPE_PROVIDERS = (
    "dashscope-intl",
    "dashscope-intl-k2",
    "dashscope-intl-k3",
    "dashscope-intl-k4",
)


def test_dashscope_intl_manifests_loaded_and_valid() -> None:
    loaded = load_manifests(providers_dir(), ADAPTER_KINDS)
    assert dict(loaded.rejected_providers) == {}
    by_id = {m.provider_id: m for m in loaded.manifests}
    for idx, pid in enumerate(DASHSCOPE_PROVIDERS):
        assert pid in by_id
        m = by_id[pid]
        assert m.kind == "passthrough"
        assert m.enabled is True
        assert m.owned_by == "dashscope-intl"
        assert m.priority == 10 + idx
        assert m.routing.weight == (100 if idx == 0 else 0)
        assert m.limits.max_concurrent == 4
        assert m.limits.quota_group == pid
        assert m.limits.timeout_s == 300
        assert m.transport.bridge is not None
        assert m.transport.bridge.base_url == "http://127.0.0.1:10830/sg-qwen"
        assert m.failover.pool == "dashscope-intl"


def test_dashscope_intl_compiled_fleet_and_4key_failover_order() -> None:
    fleet = json.loads((ROOT / "fleet.json").read_text(encoding="utf-8"))
    for idx, pid in enumerate(DASHSCOPE_PROVIDERS):
        assert pid in fleet["backends"]
        backend = fleet["backends"][pid]
        assert backend["base_url"] == "http://127.0.0.1:10830/sg-qwen"
        suffix = "" if idx == 0 else f"-k{idx + 1}"
        assert backend["api_key_ref"] == f"file:~/.config/opencode/dashscope-intl{suffix}.key"
        assert backend["max_concurrent"] == 4
        assert backend["failover_pool"] == "dashscope-intl"
        assert 429 in backend["failover_statuses"]

    models_by_id = {m["id"]: m for m in fleet["models"]}
    qwen = models_by_id["qwen4-max"]
    assert qwen["backend"] == "dashscope-intl"
    assert qwen["efforts"] == ["off", "low", "high", "xhigh"]
    assert qwen["default_effort"] == "high"
    assert qwen["context_window"] == 984000
    assert qwen["max_tokens"] == 65536

    kimi = models_by_id["kimi-k3.1-pro"]
    assert kimi["backend"] == "dashscope-intl"
    assert kimi["efforts"] == ["off", "low", "medium", "high", "xhigh"]
    assert kimi["default_effort"] == "high"
    assert kimi["context_window"] == 1000000
    assert kimi["max_tokens"] == 65536

    expected_order = list(DASHSCOPE_PROVIDERS)
    for model_id, entry in (("qwen4-max", qwen), ("kimi-k3.1-pro", kimi)):
        routes = {r["backend"]: (r["weight"], r["priority"]) for r in entry["routing"]["routes"]}
        assert routes == {
            "dashscope-intl": (100, 10),
            "dashscope-intl-k2": (0, 11),
            "dashscope-intl-k3": (0, 12),
            "dashscope-intl-k4": (0, 13),
        }
        for i in range(25):
            assert list(route_order(model_id, entry, f"seed-{i}")) == expected_order

    for eff in ("off", "low", "high", "xhigh"):
        alias = fleet["aliases"][f"qwen4-max-{eff}"]
        assert alias == {"backend_id": "qwen4-max", "backend": "dashscope-intl", "effort": eff}
    for eff in ("off", "low", "medium", "high", "xhigh"):
        alias = fleet["aliases"][f"kimi-k3.1-pro-{eff}"]
        assert alias == {"backend_id": "kimi-k3.1-pro", "backend": "dashscope-intl", "effort": eff}


def test_compile_from_disk_accepts_dashscope_intl() -> None:
    res = compile_from_disk(kinds=ADAPTER_KINDS)
    for pid in DASHSCOPE_PROVIDERS:
        assert pid not in res.rejected_providers
        assert pid in res.fleet["backends"]
    assert next(m for m in res.fleet["models"] if m["id"] == "qwen4-max")["backend"] == "dashscope-intl"
    assert next(m for m in res.fleet["models"] if m["id"] == "kimi-k3.1-pro")["backend"] == "dashscope-intl"
