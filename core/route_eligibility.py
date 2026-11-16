"""Чистые предикаты рёбер и агрегата; совместимый фильтр перед draw."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol, cast

from core.catalog_routes import validate_weight
from core.gateway_execution_policy import denied_subagent
from core.route_health_policy import NormalizedModelRoute, evaluate_route_health
from core.route_penalty_state import Phase, State
from core.routing_contract import RouteSpec

_REQUIRED_FACTS = (
    "known_backend", "enabled", "model_member", "supports_effort",
    "egress_allowed", "credential_ready", "preflight_ok", "healthy",
)
_ROLE_KEYS = frozenset({"subagent_id", "trace_subagent_id", "x_subagent_id"})


@dataclass(frozen=True, slots=True)
class EdgeSnapshot:
    """Факты одного actual edge; None вместо penalty означает отказ чтения."""
    model_id: str
    backend: str
    enabled: bool
    weight: int
    is_blocked: bool
    notes_state: str
    penalty_state: State | None


@dataclass(frozen=True, slots=True)
class ModelAvailability:
    """Доменный результат без HTTP-кода, wire owner и полномочий на healing."""
    available: bool
    phase: Phase
    reason: str = ""


def _enabled(edge: EdgeSnapshot) -> bool:
    return bool(edge.model_id and edge.backend) and edge.enabled is True and validate_weight(edge.weight) > 0


def evaluate_edge_eligibility(edge: EdgeSnapshot) -> ModelAvailability:
    """Читает готовые факты, не вызывает filter/storage и не снимает штраф."""
    try:
        if not _enabled(edge):
            return ModelAvailability(False, Phase.OPEN, "route_disabled")
    except (TypeError, ValueError):
        return ModelAvailability(False, Phase.OPEN, "route_disabled")
    if edge.notes_state != "OK":
        return ModelAvailability(False, Phase.OPEN, "model_notes_failed_closed")
    if edge.is_blocked is not False:
        return ModelAvailability(False, Phase.OPEN, "model_notes_blocked")
    state = edge.penalty_state
    if state is None:
        return ModelAvailability(False, Phase.OPEN, "penalty_unavailable")
    if state.phase == Phase.CLOSED:
        return ModelAvailability(True, Phase.CLOSED)
    reason = "route_half_open" if state.phase == Phase.HALF_OPEN else "route_open"
    return ModelAvailability(False, Phase.OPEN, reason)


def _route_backend(route: object) -> str:
    backend = _mapping(route).get("backend")
    if not isinstance(backend, str) or not backend.strip():
        raise ValueError("no_enabled_routes")
    return backend


def _model_backends(model: Mapping[str, object], primary_provider_id: str) -> frozenset[str]:
    backend = model.get("backend")
    routing = model.get("routing")
    doc = _mapping(routing)
    owners = (backend, model.get("canonical_owner", backend),
              doc.get("legacy_backend", backend), primary_provider_id)
    if not isinstance(backend, str) or not backend or any(owner != backend for owner in owners):
        raise ValueError("owner_mismatch")
    if routing is None:
        return frozenset((backend,))
    if doc.get("legacy_backend") != backend:
        raise ValueError("owner_mismatch")
    routes = doc.get("routes")
    if not isinstance(routes, (list, tuple)):
        raise ValueError("no_enabled_routes")
    return frozenset(_route_backend(route) for route in routes)


def aggregate_model_availability(
    model: Mapping[str, object], edges: Iterable[EdgeSnapshot], primary_provider_id: str,
) -> ModelAvailability:
    """Сверяет owner tuple и агрегирует actual edges без выбора attempted_backend.

    owned_by — только wire-атрибут: в т.ч. singleton codex/openai-codex.
    Пустой routing не подменяется singleton; OPEN/HALF_OPEN не лечатся.
    """
    try:
        backends = _model_backends(model, primary_provider_id)
        enabled = tuple(edge for edge in edges if edge.model_id == model.get("id")
                        and edge.backend in backends and _enabled(edge))
    except (TypeError, ValueError) as error:
        reason = str(error) if str(error) == "owner_mismatch" else "no_enabled_routes"
        return ModelAvailability(False, Phase.OPEN, reason)
    if not enabled:
        return ModelAvailability(False, Phase.OPEN, "no_enabled_routes")
    if any(evaluate_edge_eligibility(edge).available for edge in enabled):
        return ModelAvailability(True, Phase.CLOSED)
    return ModelAvailability(False, Phase.OPEN, "all_routes_unavailable")


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
    return (request, _mapping(request.get("headers")), extra, _mapping(request.get("trace")),
            _mapping(extra.get("headers")), _mapping(extra.get("trace")))


def _role_ids(sources: tuple[Mapping[str, object], ...]) -> tuple[str, ...]:
    values = (value for source in sources for key, value in source.items()
              if key.lower().replace("-", "_") in _ROLE_KEYS if value is not None)
    return tuple(value.strip().lower() for value in _strings(tuple(values)) if value.strip())


def _exclusions(sources: tuple[Mapping[str, object], ...]) -> frozenset[str]:
    excluded: set[str] = set()
    for source in sources:
        for key, value in source.items():
            if key.lower().replace("-", "_") not in {"x_exclude_transports", "exclude_transports"}:
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
        if isinstance(content, (list, tuple)) and any(
            _mapping(part).get("type") in ("image", "image_url", "input_image") for part in content
        ):
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
        object.__setattr__(self, "role_ids", tuple(v.strip().lower() for v in _strings(self.role_ids)))
        object.__setattr__(self, "excluded", frozenset(v.strip().lower() for v in _strings(self.excluded)))


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
        _role_ids(sources), _exclusions(sources), _requires_images(request),
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
            blocked_models=_strings(facts.get("blocked_models", ())) + _strings(facts.get("global_blocked_models", ())),
            probe_age_s=cast(float | None, facts.get("probe_age_s")),
            max_stale_age_s=cast(float | None, facts.get("max_stale_age_s")),
            env_drift_keys=_strings(facts.get("env_drift_keys", ())),
            supports_images=facts.get("supports_images") is True,
            backend_kind=str(facts.get("backend_kind", "")).lower(),
        )


class EligibilityPort(Protocol):
    """Предоставляет локальные факты; сетевой probe на запросе не допускается."""
    def facts(self, route: RouteSpec, request: EligibilityRequest) -> EligibilityFacts: ...


def _field(route: RouteSpec | Mapping[str, object], name: str) -> object:
    return getattr(route, name, None) if isinstance(route, RouteSpec) else route.get(name)


def _policy_allows(
    route: RouteSpec | Mapping[str, object], facts: EligibilityFacts, request: EligibilityRequest,
) -> bool:
    backend = _field(route, "backend")
    if not isinstance(backend, str) or not backend:
        return False
    identities = frozenset((backend.lower(), facts.backend_kind))
    if identities & request.excluded:
        return False
    return not ("droid" in identities and (denied_subagent("DROID", *request.role_ids)
                or any(role.startswith("panel-") for role in request.role_ids)))


def _healthy(facts: EligibilityFacts, request: EligibilityRequest) -> bool:
    if facts.probe_age_s is None or facts.max_stale_age_s is None:
        return False
    return evaluate_route_health(
        NormalizedModelRoute(request.model_id, request.effort, False),
        facts.blocked_models, facts.probe_age_s, facts.max_stale_age_s, facts.env_drift_keys,
    ).available


def _capable(route: RouteSpec | Mapping[str, object], request: EligibilityRequest) -> bool:
    model_id = _field(route, "model_id")
    if model_id is not None and model_id != request.model_id:
        return False
    efforts = _field(route, "efforts")
    return request.effort in _strings(efforts) if request.effort is not None and efforts else True


def _eligible(
    route: RouteSpec | Mapping[str, object], facts: EligibilityFacts, request: EligibilityRequest,
) -> bool:
    if facts.ready is not True or facts.circuit_open is not False:
        return False
    enabled = _field(route, "enabled")
    if enabled is not None and enabled is not True:
        return False
    if request.requires_images and facts.supports_images is not True:
        return False
    if not _policy_allows(route, facts, request):
        return False
    return _capable(route, request) and _healthy(facts, request)


def route_eligible(
    route: RouteSpec | Mapping[str, object], facts: EligibilityFacts | Mapping[str, object],
    request: EligibilityRequest | Mapping[str, object],
) -> bool:
    """Проверяет hard gates и PR17 health, сохраняя прежний контракт."""
    try:
        policy = request if isinstance(request, EligibilityRequest) else request_snapshot(request)
        snapshot = facts if isinstance(facts, EligibilityFacts) else EligibilityFacts.from_mapping(facts)
        return _eligible(route, snapshot, policy)
    except (TypeError, ValueError, OverflowError):
        return False


def eligible_routes(
    routes: Iterable[RouteSpec], port: EligibilityPort, request: Mapping[str, object],
) -> tuple[RouteSpec, ...]:
    """Фиксирует eligible set перед draw; перед send порт вызывается повторно."""
    snapshot = request_snapshot(request)
    return tuple(route for route in routes if route_eligible(route, port.facts(route, snapshot), snapshot))
