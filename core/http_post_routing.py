"""Разрешение модели и ограничений POST без исполнения транспорта."""

from __future__ import annotations

import hmac
import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, cast

from core.http_post_context import PostRequestContext
from core.http_post_ingress import clean_transport_request
from core.passthrough_autonomy import PassthroughOptions, prepare_passthrough_request, resolve_target_model
from core.route_eligibility import EdgeSnapshot, aggregate_model_availability
from core.route_penalty_state import Phase, State


@dataclass(slots=True)
class PostRoute:
    """Данные одного разрешения; host остаётся живым портом фасада."""

    ingress: PostRequestContext
    request: dict[str, Any]
    model_id: str
    raw_model: object
    model_len: int
    model: dict[str, Any] = field(default_factory=dict)
    alias: Any = None
    alias_effort: str | None = None

    @property
    def host(self) -> Any:
        return self.ingress.host

    @property
    def handler(self) -> Any:
        return self.ingress.handler

    def reject(self, status: int, kind: str, message: str) -> bool:
        self.handler._reject(status, kind, message, self.model_id, self.model_len)
        return False


@dataclass(frozen=True, slots=True)
class PreparedPostBody:
    """Общая чистая основа попыток, без route defaults и управляющего seed."""

    raw: bytes
    request: Mapping[str, Any]


def prepare_post_body(route: PostRoute) -> PreparedPostBody:
    """Очищает тело один раз, до наложения параметров любой попытки."""
    raw = route.ingress.raw
    if route.request != route.ingress.request:
        raw = route.host.json.dumps(route.request, ensure_ascii=False).encode("utf-8")
    raw, clean = clean_transport_request(raw, route.request, route.host._strip_passthrough_env)
    return PreparedPostBody(raw, MappingProxyType(dict(clean)))

def prepare_route_request(
    request: dict[str, Any], selected_model: dict[str, Any], canonical_id: str,
    alias_effort: str | None = None, effort_on: bool = True,
) -> dict[str, Any]:
    """Накладывает выбранный маршрут на исходный запрос: клиент сильнее defaults."""
    params = selected_model.get("params")
    prepared = {**(params if isinstance(params, dict) else {}), **request}
    prepared.pop("transport_seed", None)
    prepared["model"] = resolve_target_model(selected_model, canonical_id)
    options = PassthroughOptions(alias_effort=alias_effort if request.get("reasoning_effort") is None else None, effort_on=effort_on)
    prepared, _ = prepare_passthrough_request(prepared, selected_model, canonical_id, options)
    return prepared

def _notes_allow(route: PostRoute, model_id: str) -> bool:
    """Bypass-заголовок не скрывает model-notes от actual-edge гейта."""
    if route.handler.headers.get("X-Bypass-Model-Filter") == "1":
        return True
    if not route.host._MODEL_NOTES_FILTER.is_blocked(model_id):
        return True
    route.handler._send(503, {"error": {"message": "Model temporarily blocked by operational limits", "type": "model_limit_blocked", "code": 503}})
    return False

def _internal_allowed(route: PostRoute, requested_id: str) -> bool:
    host, handler = route.host, route.handler
    if not any(value in host.INTERNAL_MODEL_IDS for value in (route.raw_model, requested_id, route.model_id)):
        return True
    key = getattr(host, "_INTERNAL_SERVICE_KEY", None) or os.environ.get("INTERNAL_SERVICE_KEY", "")
    supplied = handler.headers.get("X-Internal-Service-Key", "")
    if key and hmac.compare_digest(supplied.encode("utf-8"), key.encode("utf-8")):
        return True
    handler._reject(403, "internal_model_forbidden", "Model reserved for internal review", "unknown", route.model_len)
    return False

def _penalty_allowed(route: PostRoute, requested_id: str) -> bool:
    stat = route.host._PENALTY_TRACKER.get_model_status(route.model_id.strip().lower())
    if not stat["is_penalized"]:
        return True
    retry_after = max(1, math.ceil(stat["remaining_cooldown"]))
    message = f"Model '{requested_id}' is temporarily penalized due to start failures. Cooldown active for {retry_after}s."
    route.handler._send(503, {"error": {"message": message, "type": "model_penalized", "code": 503, "penalized_until": int(stat["penalized_until"])}}, extra_headers={"Retry-After": str(retry_after)})
    return False

def _provider_lookup(route: PostRoute, published: Any) -> str | None:
    if route.model_id in published:
        return route.model_id
    alias = route.host._resolve_model_alias(route.model_id, published)
    if alias is None:
        route.handler._reject(404, "model_not_found", "model is not in the catalogue", "unknown", route.model_len)
        return None
    route.model_id = alias[0] if isinstance(alias, (tuple, list)) else alias
    if route.alias is None:
        route.alias = alias
        route.alias_effort = alias[1] if isinstance(alias, (tuple, list)) and len(alias) > 1 else None
    return route.model_id

def _published_owner(entry: Any) -> str:
    adapter, model = entry
    if adapter is not None:
        return getattr(adapter, "owned_by", "")
    return getattr(model, "owned_by", "") or (model.get("owned_by", "") if isinstance(model, dict) else "")

def _provider_allowed(route: PostRoute) -> bool:
    provider_id = route.ingress.provider_id
    if provider_id is None:
        return True
    published = route.host._get_published_models()
    lookup_id = _provider_lookup(route, published)
    if lookup_id is None:
        return False
    allowed = route.host.PROVIDER_SCOPES[provider_id]
    if _published_owner(published[lookup_id]) in ((allowed,) if isinstance(allowed, str) else allowed):
        return True
    route.handler._reply_error(400, f"Model '{route.raw_model}' is not available for provider '{provider_id}'", code="model_not_in_provider_scope")
    return False

def selected_route_allowed(route: PostRoute) -> bool:
    """Сохраняет post-selection deny и проверку отложенной авторизации."""
    handler, host = route.handler, route.host
    if str(route.model.get("backend") or "").strip().lower() == "droid":
        trace = getattr(handler, "_trace", None) or host._resolve_trace(dict(handler.headers.items()), route.request)
        if host.denied_subagent("DROID", str(handler.headers.get("X-Subagent-Id") or ""), trace.subagent_id):
            return route.reject(403, "droid_forbidden_for_role", "droid route is forbidden for this subagent role")
    denial = host._quarantine_denial(route.model_id, handler.headers.get("X-Subagent-Id"))
    if denial is not None:
        handler._log_reject(denial.reason, route.model_id, route.model_len)
        handler.close_connection = True
        handler._send(denial.http, denial.body())
        return False
    if route.ingress.deferred_passthrough_auth:
        selected = host.BACKENDS.get(route.model["backend"])
        if not isinstance(selected, host.PassthroughAdapter) or not selected.validate_client_token(host._extract_auth_token(handler)):
            route.ingress.send_error(401, "auth_error", "unauthorized")
            return False
    return True

def _edge_state(host: Any, model_id: str, backend: str, routed: bool) -> State:
    """OPEN circuit или активный штраф закрывают ребро; отказ чтения — не блок."""
    try:
        circuit = host.RESILIENCE.snapshot((backend,))["backends"][backend]["state"]
        if routed and circuit == "OPEN":
            return State(Phase.OPEN)
    except (AttributeError, KeyError, TypeError, IndexError):
        pass
    try:
        status = host._PENALTY_TRACKER.get_model_status(model_id.strip().lower())
        until = float(status["penalized_until"]) if status["is_penalized"] else 0.0
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
        return State()
    return State(Phase.OPEN, until) if until else State()

def _edge(route: PostRoute, record: Mapping[str, Any], routed: bool) -> EdgeSnapshot:
    """Собирает actual edge из объявленного маршрута без healing и RNG."""
    backend = record.get("backend")
    if not isinstance(backend, str) or not backend:
        raise ValueError("owner_mismatch")
    config = getattr(route.host.BACKENDS.get(backend), "config", {}) or {}
    notes = route.host._MODEL_NOTES_FILTER
    health = getattr(notes, "health_state", None)
    return EdgeSnapshot(
        route.model_id, backend, bool(config.get("enabled", True)), cast(int, record.get("weight", 100)),
        bool(notes.is_blocked(route.model_id)), str(health()) if callable(health) else "OK",
        _edge_state(route.host, route.model_id, backend, routed),
    )

def _model_edges(route: PostRoute) -> tuple[EdgeSnapshot, ...]:
    """Собирает edges объявленных маршрутов; singleton остаётся своим ребром."""
    routing = route.model.get("routing")
    if not isinstance(routing, Mapping):
        return (_edge(route, {"backend": route.model.get("backend"), "weight": 100}, False),)
    records = routing.get("routes")
    if not isinstance(records, (list, tuple)):
        return ()
    return tuple(_edge(route, record, True) for record in records if isinstance(record, Mapping))

def _disabled_backend(route: PostRoute) -> str:
    """Kill-switch backend обязан быть объявленным владельцем маршрута."""
    routing = route.model.get("routing")
    backend = str(route.model.get("backend") or "")
    if not isinstance(routing, Mapping):
        return backend
    disabled = routing.get("disabled_backend")
    records = routing.get("routes")
    owners = {item.get("backend") for item in records if isinstance(item, Mapping)} if isinstance(records, (list, tuple)) else set()
    if disabled is not None and disabled not in owners:
        raise ValueError("owner_mismatch")
    return str(disabled) if isinstance(disabled, str) else backend

def _route_gate(route: PostRoute) -> str | None:
    """Проверяет owner tuple и actual edges; отказ — явный 503, не drop."""
    reason = "route_mismatch"
    try:
        model = route.model
        result = aggregate_model_availability(model, _model_edges(route), str(model.get("backend") or ""))
        if result.available:
            return _disabled_backend(route)
        reason = result.reason or "route_unavailable"
    except (TypeError, ValueError) as error:
        if str(error) == "owner_mismatch":
            reason = "owner_mismatch"
    route.reject(503, reason, "no usable transport route")
    return None

def _identify(context: PostRequestContext) -> PostRoute | None:
    host: Any = context.host
    handler: Any = context.handler
    request = context.request
    raw_model = request.get("model")
    model_len = len(raw_model) if isinstance(raw_model, str) else 0
    if raw_model is not None and not isinstance(raw_model, str):
        handler._reject(400, "model_not_allowed", "model must be a string from the catalogue", "unknown", model_len)
        return None
    model_id = (raw_model or "").strip() or host.MODEL_ID
    key = (handler.headers.get("X-Idempotency-Key") or "").strip()
    if key:
        request["step_job_id"] = key
    return PostRoute(context, request, model_id, raw_model, model_len)

def _resolve_alias(route: PostRoute, models: dict[str, Any]) -> None:
    alias = route.host._resolve_model_alias(route.model_id, models)
    route.alias = alias
    if alias is None:
        return
    route.model_id = alias[0] if isinstance(alias, (tuple, list)) else alias
    route.alias_effort = alias[1] if isinstance(alias, (tuple, list)) and len(alias) > 1 else None

def _effort_type_allowed(route: PostRoute) -> bool:
    value = route.request.get("reasoning_effort")
    if value is None or isinstance(value, str):
        return True
    return route.reject(400, "unsupported_reasoning_effort", "reasoning_effort must be a string")

def _request_allowed(route: PostRoute, requested_id: str) -> bool:
    return all(check() for check in (
        lambda: _internal_allowed(route, requested_id),
        lambda: _penalty_allowed(route, requested_id),
        lambda: _provider_allowed(route),
        lambda: requested_id == route.model_id or _notes_allow(route, route.model_id),
        lambda: _effort_type_allowed(route),
    ))

def resolve_post_route(context: PostRequestContext) -> PostRoute | None:
    """Разрешает alias, каталог и actual edges, не создавая попытку и RNG."""
    route = _identify(context)
    if route is None or not _notes_allow(route, route.model_id):
        return None
    requested_id, host = route.model_id, route.host
    models = host.FLEET.get("models", {}) if isinstance(host.FLEET, dict) else {}
    _resolve_alias(route, models)
    if not _request_allowed(route, requested_id):
        return None
    route.handler._telemetry_meta(model=route.model_id)
    if route.model_id not in models:
        route.handler._reject(404, "model_not_found", "model is not in the catalogue", "unknown", route.model_len)
        return None
    route.model = dict(models[route.model_id])
    backend = _route_gate(route)
    if backend is None:
        return None
    if not host.flag_enabled("BRIDGE_TRANSPORT_ROUTING_ENABLED"):
        route.model["backend"] = backend
    return route

def log_route(route: PostRoute, mode: str) -> None:
    """Сохраняет прежнюю запись выбранного пути в существующем host logger."""
    name = route.model_id + "-" + route.alias[1] if route.alias else "-"
    route.host._log(f"chat route={mode} model={route.model_id} alias={name} {route.handler._trace_log_fields()}")

def native_effort(route: PostRoute) -> tuple[str, str] | None:
    """Сохраняет строгий тип effort и прежний downward clamp CLI."""
    value = route.request.get("reasoning_effort")
    source = "alias" if value is None and route.alias_effort is not None else "request"
    value = route.alias_effort if source == "alias" else value
    if value is None or isinstance(value, str) and not value.strip():
        return route.model["default_effort"], "default"
    if not isinstance(value, str):
        route.reject(400, "unsupported_reasoning_effort", "reasoning_effort must be a string")
        return None
    effort, clamped = route.host.clamp_effort_downward(value.strip(), route.model["efforts"], route.model["default_effort"])
    if clamped:
        route.host._log(route.host.describe_clamp("reasoning_effort", value.strip(), effort, route.model_id, route.host._LOG_EFFORT_MAX))
    return effort, source

def native_autonomy(route: PostRoute) -> tuple[Any, str] | None:
    """Применяет существующую политику autonomy выбранного CLI."""
    host = route.host
    try:
        if str(route.model.get("backend") or "").strip().lower() == "droid":
            role = str(route.handler.headers.get("X-Subagent-Id") or "") or None
            decision = host.resolve_autonomy_decision(route.request.get("autonomy"), "DROID", subagent_id=role, require_subagent=True)
            return decision.value, decision.source
        host.validate_autonomy_request(route.request.get("autonomy"))
    except host.AutonomyViolation as error:
        route.reject(400, error.reason, str(error))
        return None
    return route.request.get("autonomy"), "request"
