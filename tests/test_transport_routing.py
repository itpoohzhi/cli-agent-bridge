"""Независимый контракт weighted-sha256-v1 и источников seed.

W0-probe наблюдает настоящий статический compile_catalog, если нового шва ещё нет.
Отсутствующий импорт сам по себе никогда не считается семантическим red.
"""

from __future__ import annotations

import ast
import hashlib
import importlib
import importlib.util
import itertools
import json
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from adapters import ADAPTER_KINDS
from core.backend_adapter import AllowEntry
from core.fleet_compiler import compile_catalog
from core.provider_manifest import (
    BridgeTransport, ModelRule, ProviderManifest, TransportConfig,
)
from tests.transport_test_support import semantic_equal

ROOT = Path(__file__).resolve().parents[1]
MODEL, ROLE = "unit-model", "panel-judge"
ALGORITHM = "weighted-sha256-v1"
CATALOG_HASH = "abf90fc8dd121da8d0fb575a0da79bf60d63fec59576ff5247f78e061d55f280"
ROUTES = (
    {"route_id": "alpha", "backend": "alpha", "weight": 1, "priority": 90},
    {"route_id": "beta", "backend": "beta", "weight": 3, "priority": 10},
    {"route_id": "reserve", "backend": "reserve", "weight": 0, "priority": 0},
)
pytestmark = pytest.mark.semantic_red("weighted_routing_unimplemented")


@dataclass(frozen=True)
class Weight:
    """Тестовый DTO позволяет baseline-компилятору получить новый вход без патчей."""

    weight: int | None = None

    @property
    def effective_weight(self) -> int:
        return 100 if self.weight is None else self.weight


@dataclass(frozen=True)
class WeightedManifest(ProviderManifest):
    """Неизменяемый вход; baseline действительно игнорирует незнакомый ему вес."""

    routing: Weight = field(default_factory=Weight)


def provider(pid: str, weight: int | None = 100, priority: int = 100) -> WeightedManifest:
    """Создаёт полностью локальный манифест без чтения ключей или discovery."""
    return WeightedManifest(
        provider_id=pid, kind="passthrough", owned_by="test", priority=priority,
        transport=TransportConfig(bridge=BridgeTransport("http://127.0.0.1:9100/v1")),
        allow_base_url=(AllowEntry("http", "127.0.0.1", 9100, "/v1"),),
        models_overrides=(ModelRule(MODEL),), routing=Weight(weight),
    )


def compiled(providers: Any = None, compiler: Any = compile_catalog) -> Any:
    """Использует реальный entry point; чужой runtime и временные файлы не нужны."""
    current = json.loads((ROOT / "fleet.json").read_bytes())
    header = {key: current[key] for key in ("schema_version", "image_limits", "admission")}
    header.update(default_model=MODEL, aliases={})
    inputs = (provider("alpha", 1, 0), provider("beta", 3, 90))
    return compiler(header, inputs if providers is None else providers,
                    kinds=ADAPTER_KINDS, now="2026-11-14T00:00:00Z", env={})


def feature_api(name: str, defect: str = "weighted_routing_unimplemented") -> ModuleType:
    """Baseline-only red: отсутствует active hash в реально скомпилированной модели."""
    if importlib.util.find_spec(name) is None:
        actual = compiled().fleet["models"][0].get("routing", {}).get("catalog_hash")
        semantic_equal(actual, CATALOG_HASH, defect)
    return importlib.import_module(name)


def canonical(value: object) -> bytes:
    """Канон задан спецификацией, не заимствован у проверяемого компилятора."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def reference_hash(routes: Any) -> str:
    active = [
        {key: route[key] for key in ("route_id", "backend", "weight")}
        for route in routes if route["weight"] > 0 and route.get("enabled", True)
    ]
    active.sort(key=lambda route: (route["route_id"], route["backend"]))
    return hashlib.sha256(canonical(active)).hexdigest()


def model(routes: Any = ROUTES) -> dict[str, Any]:
    return {
        "id": MODEL, "backend": "alpha",
        "routing": {
            "algorithm": ALGORITHM, "enabled": True, "catalog_hash": reference_hash(routes),
            "legacy_backend": "beta", "disabled_backend": "alpha", "routes": list(routes),
        },
    }


def reference_order(routes: Any, seed: str, context: Any = (MODEL, ROLE)) -> tuple[str, ...]:
    """Прямой математический оракул: JSON-домен, uint64 и rejection без modulo bias."""
    remaining = sorted((dict(r) for r in routes if r["weight"] > 0),
                       key=lambda r: (r["route_id"], r["backend"]))
    reserves = sorted((r for r in routes if r["weight"] == 0),
                      key=lambda r: (r["priority"], r["route_id"], r["backend"]))
    domain = canonical([ALGORITHM, *context, reference_hash(routes), seed])
    result: list[str] = []
    round_no = 0
    while remaining:
        total = sum(route["weight"] for route in remaining)
        ticket = reference_ticket(domain, round_no, total)
        for index, route in enumerate(remaining):
            ticket -= route["weight"]
            if ticket < 0:
                result.append(remaining.pop(index)["backend"])
                break
        round_no += 1
    return tuple(result + [route["backend"] for route in reserves])


def reference_ticket(domain: bytes, round_no: int, total: int) -> int:
    limit = (1 << 256) - (1 << 256) % total
    counter = 0
    while True:
        material = domain + round_no.to_bytes(8, "big") + counter.to_bytes(8, "big")
        value = int.from_bytes(hashlib.sha256(material).digest(), "big")
        if value < limit:
            return value % total
        counter += 1


def test_independent_sha_vectors() -> None:
    assert reference_hash(ROUTES) == CATALOG_HASH
    domain = canonical([ALGORITHM, MODEL, ROLE, CATALOG_HASH, "fixed"])
    assert hashlib.sha256(domain + bytes(16)).hexdigest() == (
        "2683f7cf42bb16d0954422e8463e22ea21178560de55e88990595338596c2c8c"
    )
    assert reference_order(ROUTES, "fixed") == ("alpha", "beta", "reserve")
    assert reference_order(ROUTES, "0") == ("beta", "alpha", "reserve")


@pytest.mark.parametrize("seed", ["fixed", "0", "1", "café"])
def test_stage_w1_a_frozen_draw_all_permutations(seed: str) -> None:
    api = feature_api("core.transport_routing")
    expected = reference_order(ROUTES, seed)
    for routes in itertools.permutations(ROUTES):
        actual = tuple(api.route_order(MODEL, model(routes), seed, ROLE))
        semantic_equal(actual, expected, "weighted_routing_unimplemented")


def test_stage_w1_a_six_routes_exhaustive_permutations() -> None:
    api = feature_api("core.transport_routing")
    routes = (*ROUTES, *(
        {"route_id": name, "backend": name, "weight": weight, "priority": 50}
        for name, weight in (("gamma", 7), ("delta", 2), ("epsilon", 0))
    ))
    expected = reference_order(routes, "six")
    for permutation in itertools.permutations(routes):
        assert tuple(api.route_order(MODEL, model(permutation), "six", ROLE)) == expected


def test_stage_w1_a_active_hash_and_immutable_route() -> None:
    api = feature_api("core.routing_contract")
    for routes in itertools.permutations(ROUTES):
        assert api.routes_catalog_hash(routes) == CATALOG_HASH
    changed = [dict(route, priority=999) for route in ROUTES]
    changed[-1]["route_id"] = "different-reserve"
    assert api.routes_catalog_hash(changed) == CATALOG_HASH
    assert api.routes_catalog_hash(()) == hashlib.sha256(b"[]").hexdigest()
    route = api.RouteSpec(**ROUTES[0])
    with pytest.raises((AttributeError, TypeError)):
        route.weight = 2


def test_stage_w1_a_zero_reserves_only_and_no_routes() -> None:
    api = feature_api("core.transport_routing")
    reserves = [dict(r, weight=0) for r in ROUTES]
    assert tuple(api.route_order(MODEL, model(reserves), "fixed", ROLE)) == (
        "reserve", "beta", "alpha",
    )
    assert tuple(api.route_order(MODEL, model([]), "fixed", ROLE)) == ()


@dataclass
class Digest:
    value: int

    def digest(self) -> bytes:
        return self.value.to_bytes(32, "big")


class HashSequence:
    """Редкий rejection принудителен; ожидаемые счётчики заданы буквально."""

    def __init__(self) -> None:
        self.values = iter(((1 << 256) - 1, 1, 0))
        self.materials: list[bytes] = []

    def sha256(self, material: bytes) -> Digest:
        self.materials.append(material)
        return Digest(next(self.values))


def test_stage_w1_a_rejection_and_lazy_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    api = feature_api("core.transport_routing")
    routes = [dict(ROUTES[0]), dict(ROUTES[1], weight=2)]
    record = model(routes)
    hashes = HashSequence()
    monkeypatch.setattr(api, "hashlib", hashes)
    ordered = iter(api.route_order(MODEL, record, "reject", ROLE))
    assert next(ordered) == "beta"
    assert len(hashes.materials) == 2
    assert hashes.materials[0][-16:] == bytes(16)
    assert hashes.materials[1][-16:] == bytes(15) + b"\x01"
    assert next(ordered) == "alpha"
    assert hashes.materials[2][-16:] == bytes(7) + b"\x01" + bytes(8)
    assert tuple(ordered) == ()


@pytest.mark.parametrize("headers,body,env,expected", [
    ({"x-TrAnSpOrT-sEeD": "header"}, {"transport_seed": "body"}, {}, "header"),
    ({}, {"transport_seed": "body"}, {"BRIDGE_TRANSPORT_SEED": "test"}, "body"),
    ({}, {}, {"BRIDGE_TRANSPORT_SEED": "test",
              "BRIDGE_TRANSPORT_TEST_SEED_ENABLED": "true"}, "test"),
])
def test_explicit_and_test_only_seed_precedence(
    headers: Any, body: Any, env: Any, expected: str,
) -> None:
    api = feature_api("core.transport_settings")
    assert api.resolve_transport_seed(headers, body, env) == expected


def test_unseeded_requests_use_fresh_os_rng(monkeypatch: pytest.MonkeyPatch) -> None:
    import secrets

    api = feature_api("core.transport_settings")
    calls: list[int] = []

    def token_bytes(size: int) -> bytes:
        calls.append(size)
        return bytes([len(calls)]) * size

    monkeypatch.setattr(secrets, "token_bytes", token_bytes)
    env = {"BRIDGE_TRANSPORT_SEED": "must-not-pin-production"}
    headers = {"X-Request-Id": "same-request"}
    first = api.resolve_transport_seed(headers, {}, env)
    second = api.resolve_transport_seed(headers, {}, env)
    assert len(calls) == 2 and all(size > 0 for size in calls)
    assert first != second and first != "must-not-pin-production"


@pytest.mark.parametrize("bad", ["", 7, True, None, "a\nb", "a\x00b", "x" * 100000])
def test_seed_rejects_invalid_body_even_with_valid_header(bad: Any) -> None:
    api = feature_api("core.transport_settings")
    with pytest.raises(ValueError):
        api.resolve_transport_seed({"X-Transport-Seed": "valid"}, {"transport_seed": bad}, {})


def branch_cost(node: ast.AST) -> int:
    if isinstance(node, ast.BoolOp):
        return len(node.values) - 1
    if isinstance(node, ast.comprehension):
        return 1 + len(node.ifs)
    return int(isinstance(node, (
        ast.If, ast.IfExp, ast.For, ast.While, ast.ExceptHandler, ast.Assert, ast.With,
    )))


def check_file_contract(source: str) -> None:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        first = min([node.lineno] + [item.lineno for item in node.decorator_list])
        arguments = (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
        assert node.end_lineno is not None and node.end_lineno - first + 1 <= 40, node.name
        assert sum(arg.arg not in {"self", "cls"} for arg in arguments) <= 5, node.name
        assert 1 + sum(branch_cost(child) for child in ast.walk(node)) <= 10, node.name


def test_contract_file_envelopes() -> None:
    for name in ("test_transport_routing.py", "test_routing_catalog.py"):
        source = (ROOT / "tests" / name).read_text(encoding="utf-8")
        assert len(source.splitlines()) <= 300
        check_file_contract(source)
