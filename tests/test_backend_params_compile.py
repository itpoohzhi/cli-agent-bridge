"""REQ-004 / W1: `backends.<id>.params` — компиляция, строгая валидация, отказ на невалидном."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adapters import ADAPTER_KINDS  # noqa: E402
from core import compile_model_records as cmr  # noqa: E402
from core import fleet_compiler as fc  # noqa: E402
from core.backend_adapter import BACKEND_KEYS, FleetViolation, backend_entry_error, build_catalog  # noqa: E402
from core.backend_params import (  # noqa: E402
    BACKEND_PARAMS_INVALID,
    BACKEND_PARAMS_KEYS,
    extract_backend_params,
    validate_backend_params,
)
from core.provider_manifest import ParamsConfig, load_manifests  # noqa: E402

DIALECT_BACKENDS = ("neuralwatt", "opencode-go", "opencode-go-claude")


def _fleet() -> dict[str, Any]:
    return json.loads((ROOT / "fleet.json").read_text(encoding="utf-8"))


def _manifests() -> dict[str, Any]:
    return {m.provider_id: m for m in load_manifests(None, ADAPTER_KINDS).manifests}


def test_params_is_known_backend_key() -> None:
    assert "params" in BACKEND_KEYS
    assert BACKEND_PARAMS_KEYS == {"effort_field", "effort_map", "adaptive_whitelist", "strip_always"}


@pytest.mark.parametrize("backend_id", DIALECT_BACKENDS)
def test_fleet_json_carries_params_and_passes_strict_validation(backend_id: str) -> None:
    fleet = _fleet()
    params = fleet["backends"][backend_id]["params"]
    assert set(params) == BACKEND_PARAMS_KEYS
    assert validate_backend_params(params) == ""
    build_catalog(fleet, ADAPTER_KINDS, mode="strict")  # без FleetViolation


def test_fleet_json_dialects_match_manifests() -> None:
    fleet, manifests = _fleet(), _manifests()
    claude = fleet["backends"]["opencode-go-claude"]["params"]
    assert (claude["effort_field"], claude["adaptive_whitelist"], claude["strip_always"]) == (
        "reasoning_effort", ["reasoning_effort"], ["thinking"])
    assert fleet["backends"]["neuralwatt"]["params"]["effort_map"]["off"] == {"reasoning_effort": "none"}
    assert fleet["backends"]["opencode-go"]["params"]["effort_map"]["off"] == {"thinking": {"type": "disabled"}}
    for backend_id, backend in fleet["backends"].items():
        manifest = manifests.get(backend_id)
        if manifest is not None and "params" in backend:
            assert backend == {**backend, **extract_backend_params(manifest)}


def test_both_compilers_serialize_params_identically() -> None:
    for manifest in _manifests().values():
        if manifest.transport.bridge is None:
            continue
        via_records, via_facade = cmr.backend_entry(manifest), fc.backend_entry(manifest)
        assert via_records.get("params") == via_facade.get("params") == extract_backend_params(manifest).get("params")


def test_compile_from_disk_emits_params() -> None:
    compiled = fc.compile_from_disk(kinds=ADAPTER_KINDS)
    for backend_id in DIALECT_BACKENDS:
        assert compiled.fleet["backends"][backend_id]["params"] == _fleet()["backends"][backend_id]["params"]


def test_extract_skips_default_dialect_and_copies_mapping() -> None:
    assert extract_backend_params(SimpleNamespace(params=ParamsConfig())) == {}
    assert extract_backend_params(SimpleNamespace()) == {}
    source = {"off": {"thinking": {"type": "disabled"}}}
    out = extract_backend_params(SimpleNamespace(params=ParamsConfig("none", source, ("thinking",), ())))
    out["params"]["effort_map"]["off"]["thinking"]["type"] = "x"
    assert source["off"]["thinking"]["type"] == "disabled"


@pytest.mark.parametrize(
    "bad",
    [
        "x", [], {"unknown": 1}, {"effort_field": "bogus"}, {"effort_map": []}, {"effort_map": {"": "x"}},
        {"effort_map": {"off": 5}}, {"adaptive_whitelist": "thinking"}, {"adaptive_whitelist": ["nope"]},
        {"strip_always": [1]}, {"strip_always": ["thinking", ""]},
    ],
)
def test_validate_rejects_invalid_params(bad: Any) -> None:
    assert validate_backend_params(bad) == BACKEND_PARAMS_INVALID


@pytest.mark.parametrize(
    "good",
    [None, {}, {"effort_field": "none"}, {"effort_map": {"off": {"thinking": {"type": "disabled"}}, "low": "low"}},
     {"adaptive_whitelist": ["thinking"], "strip_always": ["thinking"]}],
)
def test_validate_accepts_valid_params(good: Any) -> None:
    assert validate_backend_params(good) == ""


def test_backend_entry_error_and_build_catalog_reject_invalid_params() -> None:
    entry = copy.deepcopy(_fleet()["backends"]["opencode-go-claude"])
    assert backend_entry_error("opencode-go-claude", entry, ADAPTER_KINDS) == ""
    entry["params"]["strip_always"] = "thinking"
    assert backend_entry_error("opencode-go-claude", entry, ADAPTER_KINDS) == BACKEND_PARAMS_INVALID
    broken = _fleet()
    broken["backends"]["opencode-go-claude"]["params"]["effort_field"] = "bogus"
    with pytest.raises(FleetViolation) as caught:
        build_catalog(broken, ADAPTER_KINDS, mode="strict")
    assert BACKEND_PARAMS_INVALID in str(caught.value)


def test_adapter_config_exposes_params_for_runtime_dispatch() -> None:
    import server

    config = server.BACKENDS.get("opencode-go-claude").config
    assert config["params"]["strip_always"] == ["thinking"]
