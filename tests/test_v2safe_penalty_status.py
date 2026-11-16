"""C2-3a: HTTP-проекция actual edges не меняет штрафы и lease."""

from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import MappingProxyType

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import published_model_status as status
from core.route_eligibility import EdgeSnapshot, ModelAvailability
from core.route_penalty_state import Phase, State


def edge(backend: str = "codex", phase: Phase = Phase.CLOSED) -> EdgeSnapshot:
    return EdgeSnapshot("terra", backend, True, 100, False, "OK", State(phase))


def model() -> dict[str, object]:
    return {
        "id": "terra",
        "backend": "codex",
        "canonical_owner": "codex",
        "owned_by": "openai-codex",
        "routing": {
            "legacy_backend": "codex",
            "routes": [{"backend": "codex"}, {"backend": "droid"}],
        },
    }


def test_actual_edge_penalty_does_not_hide_healthy_reserve() -> None:
    edges = (edge(phase=Phase.OPEN), edge("droid"))
    result = status.project_model_status(model(), iter(edges), "codex")
    assert (result.status.available, result.status.http_status) == (True, 200)
    assert result.status.phase == Phase.CLOSED
    assert tuple(row.backend for row in result.edges) == ("codex", "droid")
    assert [row.status.http_status for row in result.edges] == [503, 200]
    assert result.edges[0].status.reason == "route_open"
    assert (result.owned_by, result.canonical_owner) == ("openai-codex", "codex")


@pytest.mark.parametrize("first", tuple(Phase))
@pytest.mark.parametrize("second", tuple(Phase))
def test_model_phase_is_closed_iff_an_actual_edge_is_available(
    first: Phase,
    second: Phase,
) -> None:
    result = status.project_model_status(
        model(),
        (edge(phase=first), edge("droid", second)),
        "codex",
    )
    available = Phase.CLOSED in (first, second)
    assert result.status.available is available
    assert result.status.http_status == (200 if available else 503)
    assert result.status.phase == (Phase.CLOSED if available else Phase.OPEN)
    assert result.status.reason == ("" if available else "all_routes_unavailable")


@pytest.mark.parametrize(
    "notes,blocked,penalty,reason",
    [
        ("FAILED_CLOSED", False, State(), "model_notes_failed_closed"),
        ("unknown", False, State(), "model_notes_failed_closed"),
        ("OK", True, State(), "model_notes_blocked"),
        ("OK", False, None, "penalty_unavailable"),
    ],
)
def test_failed_closed_notes_and_missing_penalty_are_unavailable(
    notes: str,
    blocked: bool,
    penalty: State | None,
    reason: str,
) -> None:
    snapshot = replace(
        edge(),
        notes_state=notes,
        is_blocked=blocked,
        penalty_state=penalty,
    )
    result = status.project_edge_status(snapshot)
    assert (result.model_id, result.backend) == ("terra", "codex")
    assert (result.status.available, result.status.http_status) == (False, 503)
    assert (result.status.phase, result.status.reason) == (Phase.OPEN, reason)
    aggregate = status.project_model_status(model(), (snapshot,), "codex")
    assert (aggregate.status.available, aggregate.status.http_status) == (False, 503)


@pytest.mark.parametrize("phase", (Phase.OPEN, Phase.HALF_OPEN))
def test_repeated_projection_has_zero_writes_and_zero_healing(
    phase: Phase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core import model_penalty, route_penalty_state

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("HTTP-проекция не должна читать storage, часы или менять lease")

    monkeypatch.setattr(model_penalty.ModelPenaltyTracker, "_run", forbidden)
    monkeypatch.setattr(route_penalty_state.RoutePenaltyState, "_run", forbidden)
    monkeypatch.setattr(route_penalty_state, "step", forbidden)
    snapshot = replace(edge(), penalty_state=State(phase, 1, 2, 3, "fencing"))
    record = model()
    before = repr((record, snapshot))
    with monkeypatch.context() as guarded:
        guarded.setattr(Path, "open", forbidden)
        guarded.setattr(route_penalty_state.time, "time", forbidden)
        for _ in range(3):
            projected = status.project_model_status(
                MappingProxyType(record),
                (snapshot,),
                "codex",
            )
            assert projected.status.http_status == 503
            assert status.project_edge_status(snapshot).status.http_status == 503
            with pytest.raises(FrozenInstanceError):
                setattr(projected.status, "available", True)
            with pytest.raises(FrozenInstanceError):
                setattr(projected.edges[0], "backend", "other")
    assert repr((record, snapshot)) == before
    assert snapshot.penalty_state == State(phase, 1, 2, 3, "fencing")


@pytest.mark.parametrize("routing", (False, True))
def test_wire_owner_is_not_canonical_backend(routing: bool) -> None:
    record = model()
    if not routing:
        record.pop("routing")
    result = status.project_model_status(record, (edge(),), "codex")
    assert result.id == "terra"
    assert (result.owned_by, result.canonical_owner) == ("openai-codex", "codex")
    assert result.status.http_status == 200
    assert (
        status.project_model_status(
            record, (edge(),), "openai-codex"
        ).status.http_status
        == 503
    )
    record["canonical_owner"] = "other"
    rejected = status.project_model_status(record, (edge("droid"),), "codex")
    assert (rejected.status.http_status, rejected.status.reason) == (
        503,
        "owner_mismatch",
    )


@pytest.mark.parametrize("case", ("empty", "disabled", "zero", "foreign", "undeclared"))
def test_no_eligible_edge_cannot_become_available(case: str) -> None:
    snapshots = {
        "empty": (),
        "disabled": (replace(edge(), enabled=False),),
        "zero": (replace(edge(), weight=0),),
        "foreign": (replace(edge(), model_id="other"),),
        "undeclared": (edge("other"),),
    }
    result = status.project_model_status(model(), snapshots[case], "codex")
    assert (result.status.available, result.status.http_status) == (False, 503)
    assert (result.status.phase, result.status.reason) == (
        Phase.OPEN,
        "no_enabled_routes",
    )


def test_projection_delegates_both_domain_decisions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core import route_eligibility

    calls: list[object] = []
    answer = ModelAvailability(False, Phase.OPEN, "domain_decision")

    def aggregate(
        record: object,
        snapshots: object,
        primary: object,
    ) -> ModelAvailability:
        calls.append((record, snapshots, primary))
        return answer

    def evaluate(snapshot: object) -> ModelAvailability:
        calls.append(snapshot)
        return answer

    monkeypatch.setattr(route_eligibility, "aggregate_model_availability", aggregate)
    monkeypatch.setattr(route_eligibility, "evaluate_edge_eligibility", evaluate)
    record, snapshots = model(), (edge(),)
    result = status.project_model_status(record, iter(snapshots), "codex")
    assert calls == [(record, snapshots, "codex"), snapshots[0]]
    assert (result.status.http_status, result.status.reason) == (503, "domain_decision")
    assert result.edges[0].status == result.status


@pytest.mark.parametrize(
    "filename,cap",
    [
        ("core/published_model_status.py", 120),
        ("tests/test_v2safe_penalty_status.py", 250),
    ],
)
def test_file_and_function_budgets(filename: str, cap: int) -> None:
    from tests.test_transport_modularity import exceeds, functions, metrics

    source = (Path(__file__).resolve().parents[1] / filename).read_bytes()
    assert len(source.splitlines()) <= cap
    failures = {
        name: metrics(node)
        for name, node in functions(source).items()
        if exceeds(metrics(node))
    }
    assert not failures, failures
