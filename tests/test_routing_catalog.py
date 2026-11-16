"""C2-7: внутренний owner tuple, чистота и стабильность компиляции без P0."""

from __future__ import annotations

import ast
import copy
import hashlib
import itertools
import sys
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import catalog_routes
from core.catalog_routes import compile_model_routing
from core.fleet_compiler import canonical_json, compile_catalog, render_fleet_json
from core.route_eligibility import EdgeSnapshot, aggregate_model_availability
from core.route_penalty_state import Phase, State
from tests.test_transport_modularity import functions, metrics
from tests.test_transport_routing import MODEL, compiled, provider

ROOT = Path(__file__).resolve().parents[1]


def routing_model() -> dict[str, object]:
    inputs = (provider("alpha", 7, 2), provider("beta", 13, 9))
    return {
        "id": MODEL,
        "backend": "beta",
        "canonical_owner": "beta",
        "owned_by": "wire-label",
        "routing": compile_model_routing(inputs, "alpha"),
    }


def test_canonical_tuple_uses_internal_ids_not_wire_owner() -> None:
    record = routing_model()
    before = copy.deepcopy(record)
    actual = catalog_routes.compile_routing_tuple(MappingProxyType(record), "beta")
    assert actual == ("beta", "beta", "beta", "beta")
    assert record == before
    assert record["owned_by"] == "wire-label"


@pytest.mark.parametrize("wire_owner", ("openai-codex", "", "unrelated"))
def test_singleton_without_routing_keeps_backend_identity(wire_owner: str) -> None:
    record = {"id": MODEL, "backend": "codex", "owned_by": wire_owner}
    assert catalog_routes.compile_routing_tuple(record, "codex") == ("codex",) * 4
    assert "routing" not in record
    assert "canonical_owner" not in record


@pytest.mark.parametrize(
    "field", ("backend", "canonical_owner", "legacy_backend", "primary")
)
def test_tuple_rejects_each_owner_mismatch(field: str) -> None:
    record = routing_model()
    primary = "beta"
    if field == "legacy_backend":
        record["routing"] = {**dict_routing(record), field: "alpha"}
    elif field == "primary":
        primary = "alpha"
    else:
        record[field] = "alpha"
    with pytest.raises(ValueError, match="^owner_mismatch$"):
        catalog_routes.compile_routing_tuple(record, primary)


def dict_routing(record: dict[str, object]) -> dict[str, object]:
    routing = record["routing"]
    assert isinstance(routing, dict)
    return dict(routing)


@pytest.mark.parametrize("backend", (None, "", True, 3, " beta", "beta\n"))
def test_tuple_rejects_invalid_internal_id(backend: object) -> None:
    record = {"id": MODEL, "backend": backend}
    with pytest.raises(ValueError):
        catalog_routes.compile_routing_tuple(record, backend)


@pytest.mark.parametrize(
    "routing", ({}, False, {"legacy_backend": "beta", "routes": []})
)
def test_malformed_routing_is_not_a_singleton(routing: object) -> None:
    record = {**routing_model(), "routing": routing}
    with pytest.raises(ValueError):
        catalog_routes.compile_routing_tuple(record, "beta")


@pytest.mark.parametrize("phase", tuple(Phase))
def test_availability_does_not_rewrite_canonical_tuple(phase: Phase) -> None:
    record = routing_model()
    before = copy.deepcopy(record)
    snapshots = (EdgeSnapshot(MODEL, "alpha", True, 7, False, "OK", State(phase)),)
    identity = catalog_routes.compile_routing_tuple(record, "beta")
    result = aggregate_model_availability(record, snapshots, "beta")
    assert identity == ("beta",) * 4
    assert result.available is (phase == Phase.CLOSED)
    assert catalog_routes.compile_routing_tuple(record, "beta") == identity
    assert record == before


def test_stage_w1_b_pure_owner_hash_and_reserve_permutations() -> None:
    inputs = (
        provider("alpha", 7, 2),
        provider("beta", 13, 9),
        provider("reserve", 0, 1),
    )
    before = copy.deepcopy(inputs)
    active = (
        b'[{"backend":"alpha","route_id":"alpha","weight":7},'
        b'{"backend":"beta","route_id":"beta","weight":13}]'
    )
    outputs = [
        compile_model_routing(iter(items), "alpha")
        for items in itertools.permutations(inputs)
    ]
    assert all(output == outputs[0] for output in outputs)
    assert outputs[0]["catalog_hash"] == hashlib.sha256(active).hexdigest()
    assert outputs[0]["legacy_backend"] == "beta"
    assert outputs[0]["disabled_backend"] == "alpha"
    assert [row["backend"] for row in outputs[0]["routes"]] == [
        "alpha",
        "beta",
        "reserve",
    ]
    assert inputs == before


def test_stage_w1_b_owner_ignores_disabled_and_direct_only_routes() -> None:
    live = (provider("alpha", 7, 2), provider("beta", 7, 1), provider("gamma", 7, 1))
    disabled = replace(provider("disabled", 9999, 1), enabled=False)
    direct = replace(
        provider("direct", 9999, 1), transport=replace(live[0].transport, bridge=None)
    )
    routing = compile_model_routing((*live, disabled, direct), "alpha")
    assert routing["legacy_backend"] == "beta"
    assert [row["backend"] for row in routing["routes"]] == ["alpha", "beta", "gamma"]


@pytest.mark.parametrize("legacy", ("missing", "alpha", "beta"))
def test_disabled_backend_remains_separate_from_canonical_owner(legacy: str) -> None:
    routing = compile_model_routing(
        (provider("alpha", 7), provider("beta", 13)), legacy
    )
    record = {"id": MODEL, "backend": "beta", "routing": routing}
    assert catalog_routes.compile_routing_tuple(record, "beta") == ("beta",) * 4
    assert routing["disabled_backend"] == (legacy if legacy != "missing" else "beta")


def test_stage_w2_j_compiler_owner_and_input_byte_canonicalization() -> None:
    inputs = (
        provider("alpha", 7, 2),
        provider("beta", 13, 9),
        provider("reserve", 0, 1),
    )
    outputs: list[tuple[bytes, bytes]] = []
    for items in itertools.permutations(inputs):
        result = compiled(items, compiler=compile_catalog)
        model = result.fleet["models"][0]
        primary = result.sidecar["models"][MODEL]["provider"]
        assert catalog_routes.compile_routing_tuple(model, primary) == ("beta",) * 4
        assert result.rejected == {}
        outputs.append(
            (render_fleet_json(result.fleet), canonical_json(result.sidecar))
        )
    assert all(output == outputs[0] for output in outputs)


def test_compiler_singleton_preserves_wire_boundary() -> None:
    singleton = replace(provider("codex", 7), owned_by="openai-codex")
    result = compiled((singleton,))
    model = result.fleet["models"][0]
    primary = result.sidecar["models"][MODEL]["provider"]
    assert catalog_routes.compile_routing_tuple(model, primary) == ("codex",) * 4
    assert result.fleet["backends"]["codex"]["owned_by"] == "openai-codex"
    assert "owned_by" not in model


def test_catalog_compilation_calls_no_agent_policy_or_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core import route_eligibility, route_penalty_state

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("Компиляция не должна вызывать agent policy, storage или leases")

    monkeypatch.setattr(route_eligibility, "route_eligible", forbidden)
    monkeypatch.setattr(route_eligibility, "denied_subagent", forbidden)
    monkeypatch.setattr(route_penalty_state.RoutePenaltyState, "_run", forbidden)
    record = routing_model()
    assert catalog_routes.compile_routing_tuple(record, "beta") == ("beta",) * 4


def test_tuple_delegates_owner_validation_to_pure_predicate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core import route_eligibility

    seen: list[object] = []
    original = route_eligibility.aggregate_model_availability

    def observe(model: dict[str, object], edges: object, primary: str) -> object:
        seen.append(model)
        return original(model, (), primary)

    monkeypatch.setattr(route_eligibility, "aggregate_model_availability", observe)
    record = routing_model()
    catalog_routes.compile_routing_tuple(record, "beta")
    assert any(item is record for item in seen)


@pytest.mark.parametrize(
    "path", ("core/catalog_routes.py", "tests/test_routing_catalog.py")
)
def test_file_and_function_budgets(path: str) -> None:
    source = (ROOT / path).read_bytes()
    assert len(source.splitlines()) <= 300
    failures = {
        name: metrics(node)
        for name, node in functions(source).items()
        if any(
            actual > cap for actual, cap in zip(metrics(node), (40, 5, 10), strict=True)
        )
    }
    assert not failures, failures


def test_catalog_has_no_wire_owner_or_effectful_imports() -> None:
    tree = ast.parse((ROOT / "core/catalog_routes.py").read_bytes())
    imports = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert not imports & {
        "os",
        "time",
        "socket",
        "subprocess",
        "core.gateway_execution_policy",
    }


def test_catalog_does_not_synthesize_wire_owner() -> None:
    tree = ast.parse((ROOT / "core/catalog_routes.py").read_bytes())
    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert "owned_by" not in literals
