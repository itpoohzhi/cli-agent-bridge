import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml

from core.agy_anthropic_gate import ALLOWED_AGY_CLAUDE_IDS
from core.catalog_routes import RoutingConfig, compile_model_routing, provider_route
from core.compile_routes_pipeline import _select
from core.routing_weights_domain import WeightsOverrideDoc, apply_weight_overrides

ROOT = Path(__file__).resolve().parents[1]
PROVIDER_PATH = ROOT / "providers.d" / "agy.yaml"
CLAUDE_P_PATH = ROOT / "providers.d" / "claude-p.yaml"
CATALOG_PATH = ROOT / "catalog.lock.json"
FLEET_PATH = ROOT / "fleet.json"
BRIDGE_FLEET_PATH = ROOT / "bridges" / "agy-bridge" / "fleet.json"

CLAUDE_MODELS = ("claude-sonnet-5-5", "claude-opus-5-5")
GEMINI_MODELS = ("gemini-3.8-flash", "gemini-4-hydrogen", "gemini-4-neon")
EXPECTED_PROVIDERS = {"claude-p", "agy"}
EXPECTED_WEIGHTS = {"claude-p": 100, "agy": 0}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_provider(path: Path = PROVIDER_PATH) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _static_model_ids(discovery: dict[str, Any]) -> list[str]:
    return [
        entry if isinstance(entry, str) else entry["id"]
        for entry in discovery["static"]
    ]


def _fleet_models() -> dict[str, dict[str, Any]]:
    models = _load_json(FLEET_PATH)["models"]
    assert isinstance(models, list)
    by_id = {model["id"]: model for model in models}
    assert len(by_id) == len(models)
    return by_id


def _route_weights(routing: dict[str, Any]) -> dict[str, Any]:
    return {route["backend"]: route["weight"] for route in routing["routes"]}


def _entry_providers(entry: dict[str, Any]) -> set[str]:
    providers: set[str] = {entry["provider"]}
    providers.update(alt["provider"] for alt in entry["alternates"])
    return providers


def _fake_provider(
    provider_id: str,
    priority: int,
    weight: int | None,
    bridge: str,
    overrides: tuple[Any, ...] = (),
) -> SimpleNamespace:
    return SimpleNamespace(
        provider_id=provider_id,
        enabled=True,
        priority=priority,
        routing=RoutingConfig(weight),
        transport=SimpleNamespace(bridge=bridge),
        models_overrides=overrides,
    )


def test_provider_manifest_identity_and_static_discovery() -> None:
    document = _load_provider()
    assert document.get("provider_id") == "agy"
    assert document["routing"]["weight"] == 100
    static_ids = _static_model_ids(document["discovery"])
    assert set(GEMINI_MODELS) <= set(static_ids)
    assert all(model_id.startswith("gemini-") for model_id in static_ids)
    assert not any("claude-" in model_id for model_id in static_ids)
    assert document["family_rule"]["prefix"]["map"]["claude-"] == "Anthropic"


def test_provider_manifest_claude_overrides_are_conservative_and_dormant() -> None:
    overrides = _load_provider()["models_overrides"]
    assert set(CLAUDE_MODELS + GEMINI_MODELS) <= overrides.keys()
    for override in overrides.values():
        assert "verified" not in override
        assert "unverified" not in override
    for model_id in CLAUDE_MODELS:
        entry = overrides[model_id]
        assert entry["context_window"] == 1000000
        assert entry["max_tokens"] == 128000
        assert entry["input"] == ["text"]
        assert entry["route_weight"] == 0
        assert entry["route_priority"] == 20
        assert entry["images"]["cli_registry"] == "explicit_unsupported"
        assert entry["images"]["status"] == "unsupported"


def test_claude_p_manifest_remains_at_baseline_off_by_default() -> None:
    claude_p = _load_provider(CLAUDE_P_PATH)
    assert claude_p["priority"] == 10
    routing = claude_p.get("routing") or {}
    assert routing.get("weight") != 100


def test_bridge_fleet_contains_all_10_conservative_5_5_cards() -> None:
    models = {m["id"]: m for m in _load_json(BRIDGE_FLEET_PATH)["models"]}
    for model_id in ALLOWED_AGY_CLAUDE_IDS:
        card = models[model_id]
        assert card["context_window"] == 1000000
        assert card["max_tokens"] == 128000
        assert card["input"] == ["text"]
        assert card["images"] == {
            "cli_registry": "explicit_unsupported",
            "status": "unsupported",
            "method": None,
            "proof": "not image-verified; text-only",
        }


def test_per_model_route_override_keeps_claude_p_owner_without_editing_claude_p() -> None:
    agy_doc = _load_provider(PROVIDER_PATH)
    rules = tuple(
        SimpleNamespace(pattern=mid, fields=fields)
        for mid, fields in agy_doc["models_overrides"].items()
    )
    agy = _fake_provider(
        "agy", agy_doc["priority"], agy_doc["routing"]["weight"], "agy-bridge", rules
    )
    claude_p = _fake_provider("claude-p", 10, None, "claude-p-bridge")
    for model_id in CLAUDE_MODELS:
        agy_route = provider_route(agy, model_id)
        assert agy_route["weight"] == 0 and agy_route["priority"] == 20
        owner, fleet_source, routing = _select([(agy, {}), (claude_p, {})], model_id)
        assert owner.provider_id == "claude-p"
        assert fleet_source is not None and fleet_source[0].provider_id == "claude-p"
        assert routing is not None
        assert routing["legacy_backend"] == "claude-p"
        assert routing["disabled_backend"] == "claude-p"
        compiled = compile_model_routing([agy, claude_p], "claude-p", model_id=model_id)
        assert compiled["legacy_backend"] == "claude-p"
        assert compiled["disabled_backend"] == "claude-p"
    gemini_route = provider_route(agy, "gemini-4-neon")
    assert gemini_route["weight"] == 100
    assert gemini_route["priority"] == agy_doc["priority"]


def test_catalog_lock_and_fleet_invariants() -> None:
    catalog = _load_json(CATALOG_PATH)
    catalog_providers = catalog["providers"]
    assert catalog_providers["droid"]["enabled"] is False
    models = catalog["models"]
    for entry in models.values():
        assert isinstance(entry.get("provider"), str)
        assert isinstance(entry.get("alternates"), list)
    for model_id in CLAUDE_MODELS:
        providers = _entry_providers(models[model_id])
        assert EXPECTED_PROVIDERS <= providers
        enabled = {p for p in providers if catalog_providers[p]["enabled"]}
        assert enabled == EXPECTED_PROVIDERS
    for model_id in GEMINI_MODELS:
        assert models[model_id]["provider"] == "agy"
    fleet_models = _fleet_models()
    for model_id in CLAUDE_MODELS:
        weights = _route_weights(fleet_models[model_id]["routing"])
        assert EXPECTED_PROVIDERS <= weights.keys()
        assert "droid" not in weights
    per_model = {mid: dict(EXPECTED_WEIGHTS) for mid in CLAUDE_MODELS}
    overrides = WeightsOverrideDoc(1, {}, per_model, None, None)
    for model_id in CLAUDE_MODELS:
        resolved = apply_weight_overrides(
            model_id, fleet_models[model_id]["routing"], overrides
        )
        assert resolved["legacy_backend"] == "claude-p"
        assert _route_weights(resolved) == EXPECTED_WEIGHTS
    for model_id in GEMINI_MODELS:
        model = fleet_models[model_id]
        assert model.get("backend") == "agy"
        routing = model.get("routing")
        if routing and routing.get("routes"):
            assert _route_weights(routing).get("agy") == 100
