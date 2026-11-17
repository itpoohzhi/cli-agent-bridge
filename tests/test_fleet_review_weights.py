"""Веса маршрутов review-очереди в fleet.json: хеш каталога, резервы и выбор по RouteDraw."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from core.routing_contract import canonical_json, normalize_routes, parse_routes, routes_catalog_hash
from core.transport_routing import RouteDraw, route_order

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_WEIGHTS: dict[str, dict[str, int]] = {
    "gpt-6.1-sol": {"codex": 0, "droid": 50, "openai-key-2": 50, "openai-key-3": 50},
    "claude-sonnet-5-5": {"claude-p": 0, "droid": 50},
}
SEEDS = tuple(f"review-seed-{index}" for index in range(64))


def _models() -> dict[str, dict[str, Any]]:
    fleet = json.loads((ROOT / "fleet.json").read_bytes())
    return {record["id"]: record for record in fleet["models"]}


MODELS = _models()


@pytest.mark.parametrize("model_id", sorted(EXPECTED_WEIGHTS))
def test_routing_enabled_and_hash_matches_routes(model_id: str) -> None:
    routing = MODELS[model_id]["routing"]
    assert routing["enabled"] is True
    assert routing["catalog_hash"] == routes_catalog_hash(routing["routes"])


@pytest.mark.parametrize("model_id", sorted(EXPECTED_WEIGHTS))
def test_route_weights_are_exactly_expected(model_id: str) -> None:
    routes = {route["route_id"]: route["weight"] for route in MODELS[model_id]["routing"]["routes"]}
    assert routes == EXPECTED_WEIGHTS[model_id]


@pytest.mark.parametrize("model_id", sorted(EXPECTED_WEIGHTS))
def test_droid_route_is_live(model_id: str) -> None:
    routes = {route["route_id"]: route for route in MODELS[model_id]["routing"]["routes"]}
    assert routes["droid"]["weight"] > 0
    assert routes["droid"]["backend"] == "droid"


def test_blocked_routes_stay_in_reserve() -> None:
    sol = {route["route_id"]: route["weight"] for route in MODELS["gpt-6.1-sol"]["routing"]["routes"]}
    sonnet = {route["route_id"]: route["weight"] for route in MODELS["claude-sonnet-5-5"]["routing"]["routes"]}
    assert sol["codex"] == 0
    assert sonnet["claude-p"] == 0


@pytest.mark.parametrize(
    ("model_id", "legacy", "disabled"),
    [
        ("gpt-6.1-sol", "openai-key-2", "codex"),
        ("claude-sonnet-5-5", "droid", "claude-p"),
    ],
)
def test_legacy_backend_equals_model_backend(model_id: str, legacy: str, disabled: str) -> None:
    model = MODELS[model_id]
    routing = model["routing"]
    assert routing["legacy_backend"] == legacy
    assert routing["legacy_backend"] == model["backend"]
    assert routing["disabled_backend"] == disabled
    assert disabled in {route["backend"] for route in routing["routes"]}


def test_sonnet_droid_is_only_positive_route() -> None:
    routing = MODELS["claude-sonnet-5-5"]["routing"]
    assert [r["route_id"] for r in routing["routes"] if r["weight"] > 0] == ["droid"]
    assert next(route_order("claude-sonnet-5-5", MODELS["claude-sonnet-5-5"], "s", "review-queue")) == "droid"


def test_hash_ignores_reserves() -> None:
    routes = MODELS["claude-sonnet-5-5"]["routing"]["routes"]
    live_only = [route for route in routes if route["weight"] > 0]
    assert routes_catalog_hash(routes) == routes_catalog_hash(live_only)
    assert routes_catalog_hash(live_only) == routes_catalog_hash(
        [{"route_id": "droid", "backend": "droid", "weight": 50, "priority": 30}]
    )
    assert canonical_json([{"backend": "droid", "route_id": "droid", "weight": 100}]) == (
        b'[{"backend":"droid","route_id":"droid","weight":100}]'
    )


@pytest.mark.parametrize("model_id", sorted(EXPECTED_WEIGHTS))
def test_route_draw_picks_live_routes_before_reserves(model_id: str) -> None:
    routes = parse_routes(MODELS[model_id])
    live = {route.backend for route in routes if route.weight > 0}
    reserves = [route.backend for route in routes if route.weight == 0]
    domain = canonical_json([model_id, "review"])
    for seed in SEEDS:
        order = list(RouteDraw(routes, domain + seed.encode()))
        assert set(order[: len(live)]) == live
        assert order[len(live) :] == reserves
        assert sorted(order) == sorted(route.backend for route in normalize_routes(routes))


@pytest.mark.parametrize("model_id", sorted(EXPECTED_WEIGHTS))
def test_route_order_is_deterministic_on_fleet_json(model_id: str) -> None:
    live = {backend for backend, weight in EXPECTED_WEIGHTS[model_id].items() if weight > 0}
    for seed in SEEDS:
        first = list(route_order(model_id, MODELS[model_id], seed, "review-queue"))
        second = list(route_order(model_id, MODELS[model_id], seed, "review-queue"))
        assert first == second
        assert set(first[: len(live)]) == live
        assert set(first[len(live) :]) == {
            backend for backend, weight in EXPECTED_WEIGHTS[model_id].items() if weight == 0
        }


def test_single_live_route_is_always_first() -> None:
    for seed in SEEDS:
        first = next(route_order("claude-sonnet-5-5", MODELS["claude-sonnet-5-5"], seed, "review-queue"))
        assert first == "droid"


@pytest.mark.parametrize("model_id", ["gpt-6.1-sol"])
def test_weighted_draw_reaches_every_live_route_first(model_id: str) -> None:
    live = {backend for backend, weight in EXPECTED_WEIGHTS[model_id].items() if weight > 0}
    firsts = {
        next(route_order(model_id, MODELS[model_id], seed, "review-queue")) for seed in SEEDS
    }
    assert firsts == live


@pytest.mark.parametrize(
    "model_id",
    [
        "gpt-6.1-sol",
        "claude-sonnet-5-5",
    ],
)
def test_real_resolvers_keep_routing(model_id: str, monkeypatch: pytest.MonkeyPatch) -> None:
    route = _resolve_real(model_id, MODELS[model_id], monkeypatch)
    assert route is not None
    assert route.model["routing"] == MODELS[model_id]["routing"]
    from core.passthrough_facade import _model_routing

    routing = _model_routing(route.model)
    assert routing["routes"] == MODELS[model_id]["routing"]["routes"]
    assert routing["catalog_hash"] == MODELS[model_id]["routing"]["catalog_hash"]
    if model_id == "claude-sonnet-5-5":
        assert next(route_order(model_id, route.model, "seed-0", "review-queue")) == "droid"


def test_routing_dropped_when_backend_matches_neither_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.passthrough_facade import _model_routing

    model = dict(MODELS["claude-sonnet-5-5"], backend="codex")
    assert model["routing"]["legacy_backend"] != "codex"
    assert model["routing"]["disabled_backend"] != "codex"
    route = _resolve_real("claude-sonnet-5-5", model, monkeypatch)
    assert route is not None
    assert "routing" not in route.model
    assert _model_routing(model)["routes"][0]["backend"] == "codex"


def test_sonnet_routing_kept_when_routing_flag_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    model = MODELS["claude-sonnet-5-5"]
    assert model["backend"] == "droid"
    route = _resolve_real("claude-sonnet-5-5", model, monkeypatch, routing_flag=False)
    assert route is not None
    assert route.model["routing"] == model["routing"]
    assert route.model["backend"] == model["routing"]["disabled_backend"]


def _resolve_real(
    model_id: str, model: dict[str, Any], monkeypatch: pytest.MonkeyPatch, routing_flag: bool = True
) -> Any:
    from types import SimpleNamespace

    from core.http_post_context import PostRequestContext
    from core.http_post_routing import resolve_post_route
    monkeypatch.setenv("BRIDGE_TRANSPORT_ROUTING_ENABLED", "true" if routing_flag else "false")
    handler = SimpleNamespace(
        path="/v1/chat/completions", headers={}, _reject=lambda *a, **k: None,
        _telemetry_meta=lambda **k: None,
    )
    host = SimpleNamespace(
        MODEL_ID=model_id,
        FLEET={"models": {**{key: dict(value) for key, value in MODELS.items()}, model_id: dict(model)}},
        INTERNAL_MODEL_IDS=set(),
        _MODEL_NOTES_FILTER=SimpleNamespace(is_blocked=lambda _m: False),
        _PENALTY_TRACKER=SimpleNamespace(get_model_status=lambda _m: {"is_penalized": False}),
        _resolve_model_alias=lambda _m, _models: None,
        flag_enabled=lambda name: routing_flag and name == "BRIDGE_TRANSPORT_ROUTING_ENABLED",
    )
    context = PostRequestContext(handler, host)
    context._request = {"model": model_id}
    return resolve_post_route(context)
