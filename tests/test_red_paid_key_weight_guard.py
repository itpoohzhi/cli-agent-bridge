"""C2-11 / F-009: GREEN-контракт P0, платные ключи и droid отключены.

Решение владельца: openai-key-2/3 отключены с нулевым весом, droid отключён
(weight 20 в манифесте), codex (stdio_resident, weight 100) — единственный
активный бэкенд gpt-6.1-sol, поэтому у модели нет маршрутов (routing: null).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.fleet_compiler import CompileResult, compile_from_disk
from core.provider_manifest import read_yaml_file

ROOT = Path(__file__).resolve().parents[1]
PAID_KEYS = ("openai-key-2", "openai-key-3")
MODEL = "gpt-6.1-sol"


def _manifest(provider: str) -> dict[str, Any]:
    return read_yaml_file(ROOT / "providers.d" / f"{provider}.yaml")


def _json_file(name: str) -> dict[str, Any]:
    return json.loads((ROOT / name).read_bytes())


@pytest.fixture(scope="module")
def compiled() -> CompileResult:
    """Реальная локальная компиляция, без HTTP discovery и чтения ключей."""
    result = compile_from_disk(ROOT / "providers.d", now="2026-11-16T00:00:00Z", env={})
    assert result.rejected_providers == {}
    assert MODEL not in result.rejected
    return result


@pytest.fixture(params=("fleet.json", "compiled"))
def fleet(request: pytest.FixtureRequest, compiled: CompileResult) -> dict[str, Any]:
    if request.param == "compiled":
        return compiled.fleet
    return _json_file("fleet.json")


@pytest.fixture(params=("catalog.lock.json", "compiled"))
def sidecar(request: pytest.FixtureRequest, compiled: CompileResult) -> dict[str, Any]:
    if request.param == "compiled":
        return compiled.sidecar
    return _json_file("catalog.lock.json")


def _sol_model(fleet: dict[str, Any]) -> dict[str, Any]:
    models = [record for record in fleet["models"] if record["id"] == MODEL]
    assert len(models) == 1
    # Один живой бэкенд (codex): взвешенных маршрутов нет.
    assert models[0].get("routing") is None
    return models[0]


@pytest.mark.parametrize("provider", PAID_KEYS)
def test_paid_key_manifest_disabled(provider: str) -> None:
    assert _manifest(provider)["enabled"] is False, f"P0: {provider} enabled"


@pytest.mark.parametrize("provider", PAID_KEYS)
def test_paid_key_manifest_has_zero_weight(provider: str) -> None:
    weight = _manifest(provider)["routing"]["weight"]
    assert type(weight) is int
    assert weight == 0, f"P0: {provider} weight must be zero"


@pytest.mark.parametrize("slot", (2, 3))
def test_paid_key_transport_and_limits_preserved(slot: int) -> None:
    doc = _manifest(f"openai-key-{slot}")
    assert doc["transport"]["bridge"] == {
        "base_url": "http://127.0.0.1:10830/sg-openai",
        "api_key_env": f"OPENAI_API_KEY_{slot}",
    }
    assert doc["allow_base_url"] == [
        {
            "scheme": "http",
            "host": "127.0.0.1",
            "port": 10830,
            "path_prefix": "/sg-openai",
        }
    ]
    assert doc["limits"] == {
        "max_concurrent": 1,
        "quota_group": f"openai-key-{slot}",
        "timeout_s": 180,
    }


def _expected_override(slot: int, model: str) -> dict[str, Any]:
    sol = model == MODEL
    return {
        "name": f"GPT-6.1 {'Sol' if sol else 'Terra'} (OpenAI key {slot})",
        "efforts": ["low", "medium", "high", "max"]
        if sol
        else ["low", "medium", "high"],
        "default_effort": "high",
        "context_window": 272000 if sol else 500000,
        "max_tokens": 128000,
        "input": ["text"],
        "images": {
            "cli_registry": "implicit_supported",
            "status": "unverified",
            "method": None,
            "proof": None,
        },
    }


@pytest.mark.parametrize("slot", (2, 3))
def test_paid_key_model_overrides_preserved(slot: int) -> None:
    assert _manifest(f"openai-key-{slot}")["models_overrides"] == {
        model: _expected_override(slot, model) for model in (MODEL, "gpt-6.1-terra")
    }


@pytest.mark.parametrize(
    ("provider", "enabled", "expected"),
    (("codex", True, 100), ("droid", False, 20)),
)
def test_native_manifest_weight(provider: str, enabled: bool, expected: int) -> None:
    doc = _manifest(provider)
    assert doc["enabled"] is enabled
    weight = doc["routing"]["weight"]
    assert type(weight) is int
    assert weight == expected, f"P0: {provider} must have weight {expected}"


def test_manifest_codex_weight_exceeds_droid() -> None:
    assert (
        _manifest("codex")["routing"]["weight"]
        > _manifest("droid")["routing"]["weight"]
    )


def test_sol_single_active_backend_is_codex(fleet: dict[str, Any]) -> None:
    model = _sol_model(fleet)
    assert model["backend"] == "codex"
    assert fleet["backends"]["codex"]["enabled"] is True
    assert fleet["backends"]["codex"]["kind"] == "stdio_resident"
    assert fleet["backends"]["droid"]["enabled"] is False
    for provider in PAID_KEYS:
        assert fleet["backends"][provider]["enabled"] is False


def test_sol_no_droid_or_paid_routes(fleet: dict[str, Any]) -> None:
    model = _sol_model(fleet)
    routes = (model.get("routing") or {}).get("routes", [])
    assert [r["backend"] for r in routes if r["backend"] in (*PAID_KEYS, "droid")] == []
    assert model["backend"] not in (*PAID_KEYS, "droid")


@pytest.mark.parametrize("provider", PAID_KEYS)
def test_paid_key_fleet_backend_disabled(fleet: dict[str, Any], provider: str) -> None:
    assert fleet["backends"][provider]["enabled"] is False, f"P0: {provider} enabled"


@pytest.mark.parametrize("provider", PAID_KEYS)
def test_paid_key_has_no_weighted_routes(fleet: dict[str, Any], provider: str) -> None:
    """Даже отключённый backend не должен сохранять ненулевой вес маршрута."""
    _sol_model(fleet)
    routes = [
        (model["id"], route["weight"])
        for model in fleet["models"]
        for route in (model.get("routing") or {}).get("routes", [])
        if route["backend"] == provider
    ]
    assert all(type(weight) is int and weight == 0 for _, weight in routes), (
        f"P0: weighted paid routes remain: {routes}"
    )


@pytest.mark.parametrize("provider", PAID_KEYS)
def test_paid_key_sidecar_disabled(sidecar: dict[str, Any], provider: str) -> None:
    assert sidecar["providers"][provider]["enabled"] is False, f"P0: {provider} enabled"


def test_droid_fleet_and_sidecar_disabled(
    fleet: dict[str, Any], sidecar: dict[str, Any]
) -> None:
    assert fleet["backends"]["droid"]["enabled"] is False
    assert sidecar["providers"]["droid"]["enabled"] is False


def test_sol_only_codex_active_among_candidates(sidecar: dict[str, Any]) -> None:
    sol = sidecar["models"][MODEL]
    candidates = {sol["provider"], *(a["provider"] for a in sol["alternates"])}
    assert candidates == {"codex", *PAID_KEYS, "droid"}
    active = {p for p in candidates if sidecar["providers"][p]["enabled"] is True}
    assert active == {"codex"}


def test_checked_in_catalog_digest_matches_fleet() -> None:
    assert (
        _json_file("catalog.lock.json")["fleet_sha256"]
        == hashlib.sha256((ROOT / "fleet.json").read_bytes()).hexdigest()
    )
