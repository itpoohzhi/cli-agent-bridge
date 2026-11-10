from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .defaults import BRIDGE_EFFORT_LEVELS


@dataclass(frozen=True)
class ResolvedModel:
    requested_id: str
    public_id: str
    base_id: str
    backend_id: str
    adapter: str
    effort: str | None
    alias_of: str | None


class ModelNotFoundError(Exception):
    pass


class AliasCycleError(Exception):
    pass


def _has_field(value: Any, name: str) -> bool:
    if isinstance(value, Mapping):
        return name in value
    return hasattr(value, name)


def _get_field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _catalogue_model(public_id: str, entry: Any) -> ResolvedModel:
    base_id = str(_get_field(entry, "base_id", public_id))
    backend_id = str(_get_field(entry, "backend_id", base_id))
    adapter = str(_get_field(entry, "adapter", ""))

    if _has_field(entry, "effort"):
        effort = _get_field(entry, "effort")
    else:
        effort = _get_field(entry, "default_effort")

    return ResolvedModel(
        requested_id=public_id,
        public_id=str(_get_field(entry, "public_id", public_id)),
        base_id=base_id,
        backend_id=backend_id,
        adapter=adapter,
        effort=effort,
        alias_of=None,
    )


def _alias_target(entry: Any) -> str | None:
    if isinstance(entry, str):
        return entry

    for field in ("target", "model", "model_id", "public_id", "base_id", "backend_id", "upstream_model"):
        value = _get_field(entry, field)
        if value is not None:
            return str(value)
    return None


def _alias_effort(entry: Any, fallback: str | None) -> str | None:
    if isinstance(entry, str):
        return fallback
    if _has_field(entry, "effort"):
        return _get_field(entry, "effort")
    if _has_field(entry, "default_effort"):
        return _get_field(entry, "default_effort")
    return fallback


def _resolve_alias(
    requested: str,
    alias_id: str,
    fleet_catalogue: Mapping[str, Any],
    aliases: Mapping[str, Any],
    seen: frozenset[str],
    depth: int,
) -> ResolvedModel:
    if alias_id in seen or depth >= 3:
        raise AliasCycleError(f"Alias cycle or maximum depth exceeded for {requested}")

    entry = aliases[alias_id]
    target = _alias_target(entry)
    next_seen = seen | {alias_id}

    if target is not None:
        resolved = _resolve_candidate(
            requested=requested,
            candidate=target,
            fleet_catalogue=fleet_catalogue,
            aliases=aliases,
            seen=next_seen,
            depth=depth + 1,
        )
        canonical_alias_target = resolved.alias_of or resolved.public_id
        return ResolvedModel(
            requested_id=requested,
            public_id=alias_id,
            base_id=str(_get_field(entry, "base_id", resolved.base_id)),
            backend_id=str(_get_field(entry, "backend_id", resolved.backend_id)),
            adapter=str(_get_field(entry, "adapter", resolved.adapter)),
            effort=_alias_effort(entry, resolved.effort),
            alias_of=canonical_alias_target,
        )

    backend_id = _get_field(entry, "backend_id")
    adapter = _get_field(entry, "adapter")
    if backend_id is None or adapter is None:
        raise ModelNotFoundError(
            f"Model {requested} not found in fleet catalogue"
        )

    base_id = str(_get_field(entry, "base_id", alias_id))
    return ResolvedModel(
        requested_id=requested,
        public_id=alias_id,
        base_id=base_id,
        backend_id=str(backend_id),
        adapter=str(adapter),
        effort=_alias_effort(entry, None),
        alias_of=str(backend_id),
    )


def _resolve_candidate(
    requested: str,
    candidate: str,
    fleet_catalogue: Mapping[str, Any],
    aliases: Mapping[str, Any],
    seen: frozenset[str],
    depth: int,
) -> ResolvedModel:
    if candidate in aliases:
        return _resolve_alias(
            requested=requested,
            alias_id=candidate,
            fleet_catalogue=fleet_catalogue,
            aliases=aliases,
            seen=seen,
            depth=depth,
        )

    if candidate in fleet_catalogue:
        resolved = _catalogue_model(candidate, fleet_catalogue[candidate])
        return ResolvedModel(
            requested_id=requested,
            public_id=resolved.public_id,
            base_id=resolved.base_id,
            backend_id=resolved.backend_id,
            adapter=resolved.adapter,
            effort=resolved.effort,
            alias_of=resolved.alias_of,
        )

    for level in sorted(BRIDGE_EFFORT_LEVELS, key=len, reverse=True):
        suffix = f"-{level}"
        if not candidate.endswith(suffix):
            continue

        base = candidate[: -len(suffix)]
        if base not in fleet_catalogue:
            continue

        resolved = _catalogue_model(base, fleet_catalogue[base])
        return ResolvedModel(
            requested_id=requested,
            public_id=candidate,
            base_id=resolved.base_id,
            backend_id=resolved.backend_id,
            adapter=resolved.adapter,
            effort=level,
            alias_of=None,
        )

    raise ModelNotFoundError(f"Model {requested} not found in fleet catalogue")


def resolve_model(
    requested: str,
    fleet_catalogue: Mapping[str, Any],
    aliases: Mapping[str, Any] | None = None,
) -> ResolvedModel:
    """Resolve an exact alias, catalogue model, or supported effort suffix."""
    return _resolve_candidate(
        requested=requested,
        candidate=requested,
        fleet_catalogue=fleet_catalogue,
        aliases=aliases or {},
        seen=frozenset(),
        depth=0,
    )


__all__ = [
    "ResolvedModel",
    "ModelNotFoundError",
    "AliasCycleError",
    "resolve_model",
]
