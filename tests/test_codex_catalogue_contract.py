"""Владелец каталога отделён от Codex-резерва и локального Go-шва."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from adapters import ADAPTER_KINDS
from core.backend_adapter import AdapterRegistry, build_catalog
from core.transport_routing import route_order
from core.transport_settings import ROUTING_FLAG, routing_enabled
from tests.test_passthrough_adapter import CollectSink
import test_passthrough_upstream_params as upstream_params

ROOT = Path(__file__).resolve().parents[1]
CODEX_IDS = {"gpt-6.1-sol", "gpt-6.1-terra"}
DEEPSEEK = "deepseek-v4.1-flash"


def root_fleet() -> dict[str, Any]:
    return json.loads((ROOT / "fleet.json").read_text(encoding="utf-8"))


def test_codex_models_are_passthrough_and_enabled() -> None:
    data = root_fleet()
    codex = data["backends"]["codex"]
    assert codex["kind"] == "passthrough"
    assert codex["base_url"] == "http://127.0.0.1:2455/v1"
    assert codex["enabled"] is True
    assert not {m["id"] for m in data["models"] if m["backend"] == "codex"}
    for model in data["models"]:
        if model["id"] in CODEX_IDS:
            routes = {route["backend"]: route for route in model["routing"]["routes"]}
            assert routes["codex"]["route_id"] == "codex"
            assert routes["codex"]["weight"] == 0
            assert model["routing"]["disabled_backend"] == "codex"


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


def test_deepseek_direct_is_canonical_owner_not_local_go_fixture() -> None:
    data = root_fleet()
    catalog = build_catalog(data, ADAPTER_KINDS)
    model = catalog["models"][DEEPSEEK]
    assert model["backend"] == "deepseek-direct"
    assert model["routing"]["legacy_backend"] == "deepseek-direct"
    assert model["routing"]["disabled_backend"] == "opencode-go"
    routes = {route["backend"]: route["weight"] for route in model["routing"]["routes"]}
    assert routes == {"deepseek-direct": 100, "opencode-go": 0}
    registry = AdapterRegistry.from_fleet(catalog, ADAPTER_KINDS, lambda: catalog)
    try:
        assert registry.adapter_for_model(DEEPSEEK).id == "deepseek-direct"
        assert DEEPSEEK in {model.id for model in registry.get("opencode-go").get_models()}
    finally:
        registry.shutdown()


def opencode_go_fleet_fixture(fleet: dict[str, Any]) -> dict[str, Any]:
    """Изолирует прежний Go-шов от выбора канонического владельца компилятором."""
    fixture = copy.deepcopy(fleet)
    model = next(model for model in fixture["models"] if model["id"] == DEEPSEEK)
    model["backend"] = "opencode-go"
    model.pop("routing", None)
    fixture["models"] = [model]
    fixture["backends"] = {"opencode-go": fixture["backends"]["opencode-go"]}
    fixture["default_model"] = DEEPSEEK
    fixture["aliases"] = {}
    return fixture


def assert_unreadable_key_ref_rejects_client_credentials(go: Any) -> None:
    """Отозванный файл ключа не разрешает отправку клиентского токена."""
    go.key_file.unlink()
    sink = CollectSink()
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
