"""C1-3: чистые предикаты рёбер, агрегата и канонической принадлежности."""
from __future__ import annotations

import ast
import itertools
import sys
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.route_eligibility import (
    EdgeSnapshot,
    aggregate_model_availability,
    evaluate_edge_eligibility,
)
from core.route_penalty_state import Phase, State


def edge(backend: str = "codex", **changes: Any) -> EdgeSnapshot:
    return replace(
        EdgeSnapshot("terra", backend, True, 100, False, "OK", State()), **changes
    )


def model(routing: bool = True) -> dict[str, Any]:
    routes = [{"backend": backend} for backend in ("codex", "droid")]
    return {
        "id": "terra", "backend": "codex", "owned_by": "openai-codex",
        "routing": {"legacy_backend": "codex", "routes": routes} if routing else None,
    }


@pytest.mark.parametrize("phase", tuple(Phase))
@pytest.mark.parametrize("enabled,blocked,notes", tuple(itertools.product(
    (False, True), (False, True), ("OK", "FAILED_CLOSED"),
)))
@pytest.mark.parametrize("weight", (0, 1, 10000))
def test_edge_predicate_truth_table(
    phase: Phase, enabled: bool, blocked: bool, notes: str, weight: int,
) -> None:
    snapshot = edge(
        enabled=enabled, weight=weight, is_blocked=blocked, notes_state=notes,
        penalty_state=State(phase, penalized_until=0, lease_until=0),
    )
    result = evaluate_edge_eligibility(snapshot)
    expected = all((enabled, weight > 0, not blocked, notes == "OK", phase == Phase.CLOSED))
    assert result.available is expected
    assert result.phase == (Phase.CLOSED if expected else Phase.OPEN)


@pytest.mark.parametrize("changes,reason", [
    ({"enabled": False}, "route_disabled"),
    ({"weight": 0}, "route_disabled"),
    ({"is_blocked": True}, "model_notes_blocked"),
    ({"notes_state": "FAILED_CLOSED"}, "model_notes_failed_closed"),
    ({"notes_state": "unknown"}, "model_notes_failed_closed"),
    ({"penalty_state": None}, "penalty_unavailable"),
    ({"penalty_state": State(Phase.OPEN)}, "route_open"),
    ({"penalty_state": State(Phase.HALF_OPEN)}, "route_half_open"),
])
def test_unavailable_reasons(changes: dict[str, Any], reason: str) -> None:
    result = evaluate_edge_eligibility(edge(**changes))
    assert (result.available, result.reason) == (False, reason)


@pytest.mark.parametrize("weight", (-1, 10001, True, 1.5, "100", None))
def test_invalid_weight_fails_closed(weight: Any) -> None:
    assert not evaluate_edge_eligibility(edge(weight=weight)).available


@pytest.mark.parametrize("first,second", tuple(itertools.product(tuple(Phase), repeat=2)))
@pytest.mark.parametrize("reverse", (False, True))
def test_aggregate_uses_actual_edges(first: Phase, second: Phase, reverse: bool) -> None:
    edges = (edge(penalty_state=State(first)), edge("droid", penalty_state=State(second)))
    result = aggregate_model_availability(model(), edges[:: -1 if reverse else 1], "codex")
    expected = Phase.CLOSED in (first, second)
    assert result.available is expected
    assert result.phase == (Phase.CLOSED if expected else Phase.OPEN)
    assert result.reason == ("" if expected else "all_routes_unavailable")


@pytest.mark.parametrize("weight,enabled", ((0, True), (100, False)))
def test_disabled_healthy_edge_does_not_hide_open_route(weight: int, enabled: bool) -> None:
    edges = (edge(penalty_state=State(Phase.OPEN)), edge("droid", weight=weight, enabled=enabled))
    assert not aggregate_model_availability(model(), edges, "codex").available


@pytest.mark.parametrize("changes", (
    {"is_blocked": True}, {"notes_state": "FAILED_CLOSED"}, {"penalty_state": None},
))
def test_unavailable_notes_or_storage_never_heal(changes: dict[str, Any]) -> None:
    edges = tuple(edge(backend, **changes) for backend in ("codex", "droid"))
    result = aggregate_model_availability(model(), edges, "codex")
    assert (result.phase, result.reason) == (Phase.OPEN, "all_routes_unavailable")


@pytest.mark.parametrize("changes", (
    {"is_blocked": True}, {"notes_state": "FAILED_CLOSED"}, {"penalty_state": None},
))
def test_unavailable_owner_does_not_poison_healthy_reserve(changes: dict[str, Any]) -> None:
    edges = (edge(**changes), edge("droid"))
    assert aggregate_model_availability(model(), iter(edges), "codex").available


@pytest.mark.parametrize("field,value", (
    ("enabled", None), ("enabled", 1), ("is_blocked", None), ("is_blocked", 0),
    ("model_id", ""), ("backend", ""),
))
def test_missing_or_untyped_edge_facts_deny(field: str, value: Any) -> None:
    assert not evaluate_edge_eligibility(edge(**{field: value})).available


@pytest.mark.parametrize("route", ({}, {"backend": None}, {"backend": 42}, {"backend": ""}))
def test_malformed_route_cannot_be_coerced_into_backend(route: dict[str, Any]) -> None:
    record = model()
    record["routing"]["routes"] = [route, {"backend": "codex"}]
    result = aggregate_model_availability(record, (edge("42"), edge()), "codex")
    assert not result.available


@pytest.mark.parametrize("routing", ({}, False, {"legacy_backend": "codex"}))
def test_malformed_routing_is_not_singleton(routing: Any) -> None:
    record = {**model(), "routing": routing}
    assert not aggregate_model_availability(record, (edge(),), "codex").available


@pytest.mark.parametrize("case", ("empty", "disabled", "zero", "declared_empty"))
def test_no_enabled_routes(case: str) -> None:
    record = model()
    inputs = {
        "empty": (), "disabled": (edge(enabled=False),),
        "zero": (edge(weight=0),), "declared_empty": (edge(),),
    }
    if case == "declared_empty":
        record["routing"]["routes"] = []
    result = aggregate_model_availability(record, inputs[case], "codex")
    assert (result.available, result.phase, result.reason) == (False, Phase.OPEN, "no_enabled_routes")


@pytest.mark.parametrize("field", ("backend", "legacy_backend", "canonical_owner", "primary"))
def test_owner_mismatch_rejected_even_with_healthy_alternate(field: str) -> None:
    record, primary = model(), "codex"
    if field == "legacy_backend":
        record["routing"][field] = "paid"
    elif field == "primary":
        primary = "paid"
    else:
        record[field] = "paid"
    result = aggregate_model_availability(record, (edge("droid"),), primary)
    assert (result.available, result.reason) == (False, "owner_mismatch")


def test_singleton_wire_owner_is_not_backend_identity() -> None:
    record = model(routing=False)
    record["canonical_owner"] = "codex"
    before = dict(record)
    result = aggregate_model_availability(MappingProxyType(record), (edge(),), "codex")
    assert result.available
    assert record == before
    assert record["owned_by"] == "openai-codex"
    assert not aggregate_model_availability(record, (edge("droid"),), "codex").available


@pytest.mark.parametrize("changes", ({"backend": "paid"}, {"model_id": "other"}))
def test_foreign_edge_cannot_authorize_model(changes: dict[str, Any]) -> None:
    assert not aggregate_model_availability(model(), (edge(**changes),), "codex").available


@pytest.mark.parametrize("phase", (Phase.OPEN, Phase.HALF_OPEN))
def test_repeated_read_only_snapshots_never_acquire_or_heal(
    phase: Phase, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import core.route_penalty_state as penalty

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Предикат не должен обращаться к storage, часам или leases")

    monkeypatch.setattr(penalty.RoutePenaltyState, "_run", forbidden)
    monkeypatch.setattr(penalty.time, "time", forbidden)
    snapshot = edge(penalty_state=State(phase, 1, 2, 3, "token"))
    before = replace(snapshot)
    for _ in range(3):
        assert not evaluate_edge_eligibility(snapshot).available
        assert not aggregate_model_availability(model(False), (snapshot,), "codex").available
    assert snapshot == before
    with pytest.raises(FrozenInstanceError):
        setattr(snapshot, "enabled", False)


def test_existing_route_eligible_api_remains_usable() -> None:
    from core.route_eligibility import route_eligible

    facts = dict.fromkeys((
        "known_backend", "enabled", "model_member", "supports_effort",
        "egress_allowed", "credential_ready", "preflight_ok", "healthy",
    ), True)
    facts.update(circuit_open=False, probe_age_s=0, max_stale_age_s=30)
    assert route_eligible({"backend": "codex"}, facts, {"model": "terra"})
    assert not route_eligible({"backend": "codex"}, {}, {"model": "terra"})


@pytest.mark.parametrize("filename", ("core/route_eligibility.py", "tests/test_route_eligibility_penalty.py"))
def test_file_and_function_budgets(filename: str) -> None:
    from tests.test_transport_modularity import functions, metrics

    source = (Path(__file__).resolve().parents[1] / filename).read_bytes()
    assert len(source.splitlines()) <= 300
    failures = {name: metrics(node) for name, node in functions(source).items()
                if any(a > b for a, b in zip(metrics(node), (40, 5, 10), strict=True))}
    assert not failures, failures


def test_new_predicates_have_no_effectful_dependencies() -> None:
    import inspect
    from core import route_eligibility

    for function in (evaluate_edge_eligibility, aggregate_model_availability):
        tree = ast.parse(inspect.getsource(function))
        calls = {getattr(node.func, "attr", getattr(node.func, "id", ""))
                 for node in ast.walk(tree) if isinstance(node, ast.Call)}
        assert not calls & {"open", "acquire", "finish", "step", "time", "is_blocked"}
    assert route_eligibility.__file__ == str(Path(__file__).resolve().parents[1] / "core/route_eligibility.py")
