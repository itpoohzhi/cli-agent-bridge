"""Общий fail-closed фильтр маршрутов до draw, без транспортного I/O."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol, cast

from core.routing_contract import RouteSpec

_REQUIRED_FACTS = (
    "known_backend", "enabled", "model_member", "supports_effort",
    "egress_allowed", "credential_ready", "preflight_ok", "healthy",
)
_ROLE_KEYS = frozenset({"subagent_id", "trace_subagent_id", "x_subagent_id"})


def _mapping(value: object) -> Mapping[str, object]:
    return cast(Mapping[str, object], value) if isinstance(value, Mapping) else {}


def _strings(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, (tuple, list, frozenset)):
        raise ValueError("eligibility_texts_invalid")
    if not all(isinstance(item, str) for item in value):
        raise ValueError("eligibility_texts_invalid")
    return tuple(cast(Iterable[str], value))


def _sources(request: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    extra = _mapping(request.get("extra_body"))
    return (
        request, _mapping(request.get("headers")), extra,
        _mapping(request.get("trace")), _mapping(extra.get("headers")),
        _mapping(extra.get("trace")),
    )


def _role_ids(sources: tuple[Mapping[str, object], ...]) -> tuple[str, ...]:
    values = (
        value
        for source in sources
        for key, value in source.items()
        if key.lower().replace("-", "_") in _ROLE_KEYS
        if value is not None
    )
    return tuple(value.strip().lower() for value in _strings(tuple(values)) if value.strip())


def _exclusions(sources: tuple[Mapping[str, object], ...]) -> frozenset[str]:
    excluded: set[str] = set()
    for source in sources:
        for key, value in source.items():
            if key.lower().replace("-", "_") not in {
                "x_exclude_transports", "exclude_transports",
            }:
                continue
            for group in _strings(value):
                excluded.update(item.strip().lower() for item in group.split(",") if item.strip())
    return frozenset(excluded)


def _requires_images(request: Mapping[str, object]) -> bool:
    messages = request.get("messages", ())
    if not isinstance(messages, (list, tuple)):
        raise ValueError("eligibility_messages_invalid")
    for message in messages:
        content = _mapping(message).get("content")
        if not isinstance(content, (list, tuple)):
            continue
        if any(_mapping(part).get("type") in ("image", "image_url", "input_image")
               for part in content):
            return True
    return False


@dataclass(frozen=True, slots=True)
class EligibilityRequest:
    """Неизменяемые controls одного запроса; ни токенов, ни исходного тела."""

    model_id: str
    effort: str | None
    role_ids: tuple[str, ...]
    excluded: frozenset[str]
    requires_images: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "role_ids", tuple(
            value.strip().lower() for value in _strings(self.role_ids)
        ))
        object.__setattr__(self, "excluded", frozenset(
            value.strip().lower() for value in _strings(self.excluded)
        ))


def request_snapshot(request: Mapping[str, object]) -> EligibilityRequest:
    """Собирает все источники роли, не позволяя одному скрыть другой."""
    model_id = request.get("canonical_model_id", request.get("model"))
    effort = request.get("reasoning_effort")
    if not isinstance(model_id, str) or not model_id.strip():
        raise ValueError("eligibility_model_invalid")
    if effort is not None and not isinstance(effort, str):
        raise ValueError("eligibility_effort_invalid")
    sources = _sources(request)
    return EligibilityRequest(
        model_id.strip(), effort.strip().lower() if effort is not None else None,
        _role_ids(sources), _exclusions(sources),
        _requires_images(request),
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class EligibilityFacts:
    """Снимок фактов из порта; отсутствие обязательного факта закрывает маршрут."""

    ready: bool
    circuit_open: bool
    blocked_models: tuple[str, ...]
    probe_age_s: float | None
    max_stale_age_s: float | None
    env_drift_keys: tuple[str, ...]
    supports_images: bool = False
    backend_kind: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "blocked_models", _strings(self.blocked_models))
        object.__setattr__(self, "env_drift_keys", _strings(self.env_drift_keys))

    @classmethod
    def from_mapping(cls, facts: Mapping[str, object]) -> EligibilityFacts:
        return cls(
            ready=all(facts.get(name) is True for name in _REQUIRED_FACTS),
            circuit_open=facts.get("circuit_open") is not False,
            blocked_models=(
                _strings(facts.get("blocked_models", ()))
                + _strings(facts.get("global_blocked_models", ()))
            ),
            probe_age_s=cast(float | None, facts.get("probe_age_s")),
            max_stale_age_s=cast(float | None, facts.get("max_stale_age_s")),
            env_drift_keys=_strings(facts.get("env_drift_keys", ())),
            supports_images=facts.get("supports_images") is True,
            backend_kind=str(facts.get("backend_kind", "")).lower(),
        )


class EligibilityPort(Protocol):
    """Предоставляет локальные факты; сетевой probe на запросе не допускается."""

    def facts(self, route: RouteSpec, request: EligibilityRequest) -> EligibilityFacts: ...

__all__ = ('_mapping', '_strings', '_sources', '_role_ids', '_exclusions', '_requires_images', 'EligibilityRequest', 'request_snapshot', 'EligibilityFacts', 'EligibilityPort')
