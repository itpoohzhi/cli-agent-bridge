"""Версионированный контракт каталога Codex (`resident_v2` vs `passthrough`) и владельцев маршрутов."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _path in (str(ROOT), str(ROOT / "tests")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from adapters import ADAPTER_KINDS  # noqa: E402
from core import route_catalog_contract as rcc  # noqa: E402
from core.backend_adapter import AdapterRegistry, build_catalog  # noqa: E402
from core.transport_routing import route_order  # noqa: E402
from core.transport_settings import ROUTING_FLAG, routing_enabled  # noqa: E402
from scripts import sync_codex_catalog  # noqa: E402
import test_passthrough_adapter as passthrough_seam  # noqa: E402
import test_passthrough_upstream_params as upstream_params  # noqa: E402

CODEX_IDS = frozenset({rcc.SOL_MODEL_ID, rcc.TERRA_MODEL_ID})
DEEPSEEK = "deepseek-v4.1-flash"
EXPECTED_CONTEXT = {rcc.SOL_MODEL_ID: 272_000, rcc.TERRA_MODEL_ID: 500_000}
EXPECTED_EFFORTS = {
    rcc.SOL_MODEL_ID: list(rcc.SOL_EFFORTS),
    rcc.TERRA_MODEL_ID: list(rcc.TERRA_EFFORTS),
}


def root_fleet() -> dict[str, Any]:
    return json.loads((ROOT / "fleet.json").read_text(encoding="utf-8"))


def test_codex_backend_is_stdio_resident_with_v2_route_in_fleet() -> None:
    """ADR-001 Catalogue: codex backend is stdio_resident with codex-app-server-v2 routes."""
    data = root_fleet()
    codex = data["backends"]["codex"]
    assert codex["kind"] == rcc.BACKEND_KIND_STDIO_RESIDENT
    assert codex["wrapper"] == "codex app-server"
    assert codex["enabled"] is True
    assert "base_url" not in codex
    assert not {m["id"] for m in data["models"] if m["backend"] == "codex"}
    rcc.validate_no_forbidden_aliases(data["aliases"])
    models = {m["id"]: m for m in data["models"]}
    for model_id in sorted(CODEX_IDS):
        model = models[model_id]
        routes = {route["backend"]: route for route in model["routing"]["routes"]}
        assert routes["codex"]["route_id"] == rcc.CODEX_V2_ROUTE_ID
        assert routes["codex"]["weight"] == 0
        assert model["routing"]["disabled_backend"] == "codex"
        assert model["efforts"] == EXPECTED_EFFORTS[model_id]
        assert model["context_window"] == EXPECTED_CONTEXT[model_id]
        assert model["max_tokens"] == 128_000


def test_versioned_resident_v2_and_passthrough_routes_are_strictly_separated() -> None:
    """ADR-001 Catalogue: resident_v2 and passthrough HTTP contracts are strictly separated."""
    primary = rcc.build_codex_v2_primary_route(enabled=True)
    passthrough = rcc.build_codex_passthrough_route(enabled=False)
    contract = rcc.RouteCatalogContract((primary, passthrough))
    resident, http_routes = rcc.separate_routes_by_transport(contract.entries)

    assert primary.is_resident_v2 is True
    assert primary.upstream_contract == rcc.CODEX_APP_SERVER_V2_CONTRACT
    assert primary.zero_canon_attested is True
    sol_cap = primary.capability_for(rcc.SOL_MODEL_ID)
    terra_cap = primary.capability_for(rcc.TERRA_MODEL_ID)
    assert sol_cap is not None and sol_cap.safe_input_tokens == 200_000
    assert terra_cap is not None and terra_cap.safe_input_tokens == 340_000
    assert passthrough.is_passthrough is True
    assert passthrough.enabled is False
    assert passthrough.zero_canon_attested is False
    assert [r.route_id for r in resident] == [rcc.CODEX_V2_ROUTE_ID]
    assert [r.route_id for r in http_routes] == [rcc.CODEX_PASSTHROUGH_ROUTE_ID]
    assert rcc.verify_catalog_hash(contract.entries, contract.catalog_hash) is True
    assert rcc.find_forbidden_secret_keys(contract.canonical_dict()) == ()


def test_route_contract_separation_rejects_mixed_kinds_and_forbidden_aliases() -> None:
    """ADR-001 Catalogue: fail closed on kind/contract mismatch, passthrough attestation, 6.2 alias."""
    with pytest.raises(rcc.RouteCatalogContractError, match="contract_backend_kind_mismatch"):
        rcc.validate_route_contract_separation(
            rcc.CODEX_V2_ROUTE_ID,
            rcc.BACKEND_KIND_PASSTHROUGH,
            rcc.CODEX_APP_SERVER_V2_CONTRACT,
        )
    with pytest.raises(rcc.RouteCatalogContractError, match="passthrough_cannot_attest_zero_canon"):
        rcc.VersionedRouteEntry(
            rcc.CODEX_PASSTHROUGH_ROUTE_ID,
            rcc.CODEX_PASSTHROUGH_ROUTE_ID,
            rcc.BACKEND_KIND_PASSTHROUGH,
            "codex.passthrough.http.v1@unverified",
            enabled=False,
            zero_canon_attested=True,
        )
    with pytest.raises(rcc.RouteCatalogContractError, match="forbidden_model_alias"):
        rcc.validate_no_forbidden_aliases({"gpt-6.2-sol": {"backend_id": rcc.SOL_MODEL_ID}})


def test_sync_codex_catalog_matches_fleet_and_separates_transports() -> None:
    """ADR-001 Catalogue: sync_codex_catalog reproduces exact fleet.json bytes and separated contract."""
    result = sync_codex_catalog.generate_fleet()
    ok, detail = sync_codex_catalog.check_fleet_file(ROOT / "fleet.json", result)
    assert (ok, detail) == (True, "ok")
    assert result.updated_models == tuple(sorted(CODEX_IDS))
    assert [r.route_id for r in result.contract.resident_v2_routes] == [rcc.CODEX_V2_ROUTE_ID]
    http_ids = {r.route_id for r in result.contract.passthrough_routes}
    assert {rcc.CODEX_PASSTHROUGH_ROUTE_ID, "openai-key-3"} <= http_ids


@pytest.mark.parametrize("model_id", sorted(CODEX_IDS))
def test_root_openai_models_have_direct_canonical_owner(model_id: str) -> None:
    data = root_fleet()
    models = {model["id"]: model for model in data["models"]}
    catalog = build_catalog(data, ADAPTER_KINDS)
    assert models[model_id]["backend"] == "openai-key-3"
    assert models[model_id]["routing"]["legacy_backend"] == "openai-key-3"
    assert catalog["models"][model_id]["backend"] == "openai-key-3"


@pytest.mark.parametrize("enabled", [False, True])
def test_codex_explicit_route_membership_follows_backend_flag(enabled: bool) -> None:
    data = root_fleet()
    data["backends"]["codex"]["enabled"] = enabled
    catalog = build_catalog(data, ADAPTER_KINDS)
    registry = AdapterRegistry.from_fleet(catalog, ADAPTER_KINDS, lambda: catalog)
    try:
        members = {model.id for adapter, model in registry.models() if adapter.id == "codex"}
        assert members == (CODEX_IDS if enabled else set())
        published = {model.id for _, model in registry.models()}
        assert published & CODEX_IDS == CODEX_IDS
        for model_id in CODEX_IDS:
            assert registry.adapter_for_model(model_id).id == "openai-key-3"
    finally:
        registry.shutdown()


@pytest.mark.parametrize("model_id", sorted(CODEX_IDS))
def test_codex_is_only_drawn_after_positive_weight_routes(model_id: str) -> None:
    model = next(model for model in root_fleet()["models"] if model["id"] == model_id)
    before = copy.deepcopy(model)
    for seed in ("first", "second", "third"):
        order = list(route_order(model_id, model, seed))
        assert order[0] == "openai-key-3"
        assert order[1] == "codex"
        assert len(order) == len(set(order))
    assert model == before


@pytest.mark.parametrize("model_id", sorted(CODEX_IDS))
def test_flag_off_retains_native_codex_order(
    model_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ROUTING_FLAG, raising=False)
    assert routing_enabled() is False
    model = next(model for model in root_fleet()["models"] if model["id"] == model_id)
    model["routing"]["enabled"] = False
    assert list(route_order(model_id, model, "flag-off")) == ["codex"]
    assert model["backend"] == "openai-key-3"


@pytest.mark.parametrize("enabled", [False, True])
def test_native_codex_models_still_follow_backend_flag(enabled: bool) -> None:
    data = root_fleet()
    for model in data["models"]:
        if model["id"] in CODEX_IDS:
            model["backend"] = "codex"
            model.pop("routing")
    data["backends"]["codex"]["enabled"] = enabled
    catalog = build_catalog(data, ADAPTER_KINDS)
    registry = AdapterRegistry.from_fleet(catalog, ADAPTER_KINDS, lambda: catalog)
    try:
        published = {model.id for _, model in registry.models()}
        assert published & CODEX_IDS == (CODEX_IDS if enabled else set())
    finally:
        registry.shutdown()


def test_deepseek_canonical_owner_is_neuralwatt_not_local_go_fixture() -> None:
    """Fleet contract: deepseek-v4.1-flash canonical owner is neuralwatt with reserve routes."""
    data = root_fleet()
    catalog = build_catalog(data, ADAPTER_KINDS)
    model = catalog["models"][DEEPSEEK]
    assert model["backend"] == "neuralwatt"
    assert model["routing"]["legacy_backend"] == "neuralwatt"
    assert model["routing"]["disabled_backend"] == "neuralwatt"
    routes = {route["backend"]: route["weight"] for route in model["routing"]["routes"]}
    assert routes == {
        "neuralwatt": 100,
        "deepseek-direct": 0,
        "opencode-go-sub1": 0,
        "opencode-go-sub2": 0,
    }
    registry = AdapterRegistry.from_fleet(catalog, ADAPTER_KINDS, lambda: catalog)
    try:
        assert registry.adapter_for_model(DEEPSEEK).id == "neuralwatt"
        assert DEEPSEEK in {m.id for m in registry.get("opencode-go-sub1").get_models()}
    finally:
        registry.shutdown()


def opencode_go_fleet_fixture(fleet: dict[str, Any]) -> dict[str, Any]:
    """Изолирует прежний Go-шов от выбора канонического владельца компилятором."""
    fixture = copy.deepcopy(fleet)
    model = next(model for model in fixture["models"] if model["id"] == DEEPSEEK)
    model["backend"] = "opencode-go"
    model.pop("routing", None)
    fixture["models"] = [model]
    fixture["backends"] = {
        "opencode-go": {**fixture["backends"]["opencode-go"], "enabled": True}
    }
    fixture["default_model"] = DEEPSEEK
    fixture["aliases"] = {}
    return fixture


def assert_unreadable_key_ref_rejects_client_credentials(go: Any) -> None:
    """Отозванный файл ключа не разрешает отправку клиентского токена."""
    go.key_file.unlink()
    sink = passthrough_seam.CollectSink()
    go.adapter.handle(
        path="/v1/chat/completions",
        raw_body=b'{"model":"deepseek-v4.1-flash"}',
        request={"model": DEEPSEEK},
        headers={"Authorization": "Bearer client-own", "X-Api-Key": "client-x"},
        sink=sink,
    )
    assert sink.status == 503
    assert go.upstream.requests == []


def test_go_file_headers_are_reread_on_every_request(tmp_path: Path) -> None:
    stand = upstream_params.GoStand(tmp_path)
    try:
        assert stand.call({"model": DEEPSEEK})["headers"]["x-opencode-org-id"] == "org-42"
        config = json.loads(stand.opencode_json.read_text(encoding="utf-8"))
        config["provider"]["opencode-go"]["options"]["headers"]["x-opencode-org-id"] = "org-43"
        stand.opencode_json.write_text(json.dumps(config), encoding="utf-8")
        sent = stand.call({"model": DEEPSEEK})
        assert sent["headers"]["x-opencode-org-id"] == "org-43"
        assert sent["headers"]["authorization"] == "Bearer go-secret-key"
        assert "x-ignored" not in sent["headers"]
    finally:
        stand.close()
