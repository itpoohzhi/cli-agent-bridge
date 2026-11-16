"""Canonical catalog ownership and read-only model publication helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from core.published_model_status import PublishedModelStatus, project_model_status
from core.route_eligibility import EdgeSnapshot
from core.route_penalty_state import Phase, State


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _models(catalog: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    raw = catalog.get("models", {})
    if isinstance(raw, Mapping):
        return {
            str(key): value
            for key, value in raw.items()
            if isinstance(value, Mapping)
        }
    if isinstance(raw, list):
        return {
            model_id: row
            for row in raw
            if isinstance(row, Mapping) and (model_id := _text(row.get("id")))
        }
    return {}


def canonical_owner(record: Mapping[str, object]) -> str:
    """Returns the single internal owner or rejects a split identity."""
    backend = _text(record.get("backend"))
    routing = record.get("routing")
    legacy = routing.get("legacy_backend", backend) if isinstance(routing, Mapping) else backend
    identities = {backend, _text(record.get("canonical_owner", backend)), _text(legacy)}
    if "" in identities or len(identities) != 1:
        raise ValueError("owner_mismatch")
    return backend


def canonical_published_models(
    catalog: Mapping[str, object], members: Iterable[object]
) -> dict[str, tuple[Any, Any]]:
    """Indexes registry members by the catalog owner, never iteration order."""
    indexed: dict[tuple[str, str], tuple[Any, Any]] = {}
    for item in members:
        adapter, model = item if isinstance(item, tuple) and len(item) == 2 else (getattr(item, "adapter", None), item)
        model_id = getattr(model, "id", None)
        backend = getattr(adapter, "id", None)
        if isinstance(model_id, str) and isinstance(backend, str):
            indexed[(model_id, backend)] = (adapter, model)
    published: dict[str, tuple[Any, Any]] = {}
    for model_id, record in _models(catalog).items():
        member = indexed.get((model_id, canonical_owner(record)))
        if member is not None:
            published[model_id] = member
    return published


def wire_owner(adapter: object, model: object, record: Mapping[str, object]) -> str:
    """Keeps the HTTP owner attribute separate from internal routing identity."""
    for value in (
        getattr(adapter, "owned_by", None),
        getattr(model, "owned_by", None),
        record.get("owned_by"),
    ):
        if isinstance(value, str) and value:
            return value
    return ""


def _routes(record: Mapping[str, object], routing_enabled: bool) -> tuple[Mapping[str, object], ...]:
    routing = record.get("routing")
    raw = routing.get("routes") if routing_enabled and isinstance(routing, Mapping) else None
    if isinstance(raw, list):
        return tuple(route for route in raw if isinstance(route, Mapping))
    return ({"backend": canonical_owner(record), "weight": 100},)


def _state(backends: Mapping[str, object], backend: str) -> State | None:
    raw = backends.get(backend)
    phase = raw.get("state") if isinstance(raw, Mapping) else None
    try:
        return State(Phase(phase))
    except (TypeError, ValueError):
        return None


def _weight(route: Mapping[str, object]) -> int:
    value = route.get("weight", 0)
    return int(value) if isinstance(value, (int, str)) else 0


def publication_status(
    record: Mapping[str, object],
    resilience: Mapping[str, object],
    notes_state: str,
    blocked: bool,
    routing_enabled: bool,
) -> PublishedModelStatus:
    """Projects actual edges without leases, healing, clocks, or writes."""
    model_id = _text(record.get("id"))
    backends = resilience.get("backends", {})
    backend_rows = backends if isinstance(backends, Mapping) else {}
    edges = tuple(
        EdgeSnapshot(
            model_id,
            _text(route.get("backend")),
            True,
            _weight(route),
            blocked,
            notes_state,
            _state(backend_rows, _text(route.get("backend"))),
        )
        for route in _routes(record, routing_enabled)
    )
    return project_model_status(record, edges, canonical_owner(record))
