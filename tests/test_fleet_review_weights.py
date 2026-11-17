"""Веса маршрутов review-очереди в fleet.json: хеш каталога, резервы и выбор по RouteDraw."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from core.routing_contract import canonical_json, normalize_routes, parse_routes, routes_catalog_hash
from core.transport_routing import RouteDraw, route_order

ROOT = Path(__file__).resolve().parents[1]
# Актуальный `fleet.json`: routing остался только у haiku и deepseek; sol/sonnet — singleton.
EXPECTED_WEIGHTS: dict[str, dict[str, int]] = {
    "claude-haiku-5-5": {"claude-p": 0, "opencode-go-claude": 100},
    "deepseek-v4.1-flash": {"deepseek-direct": 100, "opencode-go": 0},
}
SINGLETON_BACKENDS: dict[str, str] = {
    "gpt-6.1-sol": "codex",
    "claude-sonnet-5-5": "claude-p",
}
SEEDS = tuple(f"review-seed-{index}" for index in range(64))


def _fleet() -> dict[str, Any]:
    return json.loads((ROOT / "fleet.json").read_bytes())


def _models() -> dict[str, dict[str, Any]]:
    return {record["id"]: record for record in _fleet()["models"]}


MODELS = _models()


def test_owner_policy_backends_in_fleet_json() -> None:
    backends = _fleet()["backends"]
    assert backends["droid"]["enabled"] is False
    assert backends["openai-key-2"]["enabled"] is False
    assert backends["openai-key-3"]["enabled"] is False
    assert backends["codex"]["kind"] == "stdio_resident"
    assert backends["codex"]["enabled"] is True


@pytest.mark.parametrize(("model_id", "backend"), sorted(SINGLETON_BACKENDS.items()))
def test_singleton_models_have_no_routing_and_synthesize_weight_100(
    model_id: str, backend: str
) -> None:
    from core.passthrough_facade import _model_routing

    model = MODELS[model_id]
    assert model["backend"] == backend
    assert "routing" not in model
    routing = _model_routing(model)
    assert routing["catalog_hash"] == f"singleton:{backend}"
    assert [(r["backend"], r["weight"]) for r in routing["routes"]] == [(backend, 100)]
    assert list(route_order(model_id, model, "seed-0", "review-queue")) == [backend]


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
def test_primary_route_is_live(model_id: str) -> None:
    routes = {route["route_id"]: route for route in MODELS[model_id]["routing"]["routes"]}
    primary = MODELS[model_id]["backend"]
    assert routes[primary]["weight"] == 100
    assert routes[primary]["backend"] == primary
    assert "droid" not in routes


def test_blocked_routes_stay_in_reserve() -> None:
    haiku = {route["route_id"]: route["weight"] for route in MODELS["claude-haiku-5-5"]["routing"]["routes"]}
    deepseek = {route["route_id"]: route["weight"] for route in MODELS["deepseek-v4.1-flash"]["routing"]["routes"]}
    assert haiku["claude-p"] == 0
    assert deepseek["opencode-go"] == 0


@pytest.mark.parametrize(
    ("model_id", "legacy", "disabled"),
    [
        ("claude-haiku-5-5", "opencode-go-claude", "claude-p"),
        ("deepseek-v4.1-flash", "deepseek-direct", "opencode-go"),
    ],
)
def test_legacy_backend_equals_model_backend(model_id: str, legacy: str, disabled: str) -> None:
    model = MODELS[model_id]
    routing = model["routing"]
    assert routing["legacy_backend"] == legacy
    assert routing["legacy_backend"] == model["backend"]
    assert routing["disabled_backend"] == disabled
    assert disabled in {route["backend"] for route in routing["routes"]}


def test_haiku_primary_is_only_positive_route() -> None:
    routing = MODELS["claude-haiku-5-5"]["routing"]
    assert [r["route_id"] for r in routing["routes"] if r["weight"] > 0] == ["opencode-go-claude"]
    assert next(route_order("claude-haiku-5-5", MODELS["claude-haiku-5-5"], "s", "review-queue")) == "opencode-go-claude"


def test_hash_ignores_reserves() -> None:
    routes = MODELS["claude-haiku-5-5"]["routing"]["routes"]
    live_only = [route for route in routes if route["weight"] > 0]
    assert routes_catalog_hash(routes) == routes_catalog_hash(live_only)
    assert routes_catalog_hash(live_only) == routes_catalog_hash(
        [{"route_id": "opencode-go-claude", "backend": "opencode-go-claude", "weight": 100, "priority": 99}]
    )
    assert canonical_json([{"backend": "codex", "route_id": "codex", "weight": 100}]) == (
        b'[{"backend":"codex","route_id":"codex","weight":100}]'
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
        first = next(route_order("claude-haiku-5-5", MODELS["claude-haiku-5-5"], seed, "review-queue"))
        assert first == "opencode-go-claude"


def test_weighted_draw_reaches_every_live_route_first() -> None:
    # В прод-флите моделей с несколькими живыми маршрутами больше нет: жеребьёвка на синтетике.
    routes = [
        {"route_id": backend, "backend": backend, "weight": 50, "priority": 10}
        for backend in ("codex", "claude-p", "agy")
    ]
    model = {
        "id": "synthetic-weighted",
        "backend": "codex",
        "routing": {
            "algorithm": "weighted-sha256-v1",
            "enabled": True,
            "catalog_hash": routes_catalog_hash(routes),
            "legacy_backend": "codex",
            "disabled_backend": "codex",
            "routes": routes,
        },
    }
    firsts = {
        next(route_order("synthetic-weighted", model, seed, "review-queue")) for seed in SEEDS
    }
    assert firsts == {"codex", "claude-p", "agy"}


@pytest.mark.parametrize("model_id", sorted(EXPECTED_WEIGHTS))
def test_real_resolvers_keep_routing(model_id: str, monkeypatch: pytest.MonkeyPatch) -> None:
    route = _resolve_real(model_id, MODELS[model_id], monkeypatch)
    assert route is not None
    assert route.model["routing"] == MODELS[model_id]["routing"]
    from core.passthrough_facade import _model_routing

    routing = _model_routing(route.model)
    assert routing["routes"] == MODELS[model_id]["routing"]["routes"]
    assert routing["catalog_hash"] == MODELS[model_id]["routing"]["catalog_hash"]
    if model_id == "claude-haiku-5-5":
        assert next(route_order(model_id, route.model, "seed-0", "review-queue")) == "opencode-go-claude"


@pytest.mark.parametrize(("model_id", "backend"), sorted(SINGLETON_BACKENDS.items()))
def test_real_resolver_keeps_singleton_backend(
    model_id: str, backend: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    route = _resolve_real(model_id, MODELS[model_id], monkeypatch)
    assert route is not None
    assert route.model["backend"] == backend
    assert "routing" not in route.model


def test_routing_rejected_when_backend_matches_neither_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.passthrough_facade import _model_routing

    model = dict(MODELS["claude-haiku-5-5"], backend="codex")
    assert model["routing"]["legacy_backend"] != "codex"
    assert model["routing"]["disabled_backend"] != "codex"
    # Резолвер fail-closed: owner tuple не сходится, маршрут отклоняется целиком.
    assert _resolve_real("claude-haiku-5-5", model, monkeypatch) is None
    assert _model_routing(model)["routes"][0]["backend"] == "codex"


def test_haiku_routing_kept_when_routing_flag_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    model = MODELS["claude-haiku-5-5"]
    assert model["backend"] == "opencode-go-claude"
    route = _resolve_real("claude-haiku-5-5", model, monkeypatch, routing_flag=False)
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
        _send=lambda *a, **k: None,
        _telemetry_meta=lambda **k: None,
    )
    backend_configs = _fleet()["backends"]
    backends = SimpleNamespace(
        get=lambda bid: (
            SimpleNamespace(config=dict(backend_configs[bid])) if bid in backend_configs else None
        )
    )
    host = SimpleNamespace(
        MODEL_ID=model_id,
        BACKENDS=backends,
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
