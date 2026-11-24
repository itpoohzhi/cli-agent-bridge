"""Разрешение модели и ограничений POST без исполнения транспорта."""

from __future__ import annotations

import hmac
import math
import os
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from core import zero_canon_routing as _zcr
from core.http_post_context import PostRequestContext
from core.http_post_ingress import clean_transport_request
from core.muse_usage_client import MuseUsageClient
from core.passthrough_autonomy import PassthroughOptions, prepare_passthrough_request, resolve_target_model
from core.runtime_env import flag_enabled as _env_flag_enabled
from core.zero_canon_http import ZERO_CANON_HEADER_VALUE, ZeroCanonHttpError, filter_zero_canon_providers, parse_review_profile_headers

_MUSE_USAGE_FLAG = "MUSE_USAGE_ROUTER_ENABLED"


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


def prepare_route_request(request: dict[str, Any], selected_model: dict[str, Any], canonical_id: str, alias_effort: str | None = None, effort_on: bool = True) -> dict[str, Any]:
    """Накладывает выбранный маршрут на чистый исходный запрос (клиент сильнее defaults)."""
    params = selected_model.get("params")
    prepared = {**(params if isinstance(params, dict) else {}), **request}
    prepared.pop("transport_seed", None)
    prepared["model"] = resolve_target_model(selected_model, canonical_id)
    options = PassthroughOptions(alias_effort=alias_effort if request.get("reasoning_effort") is None else None, effort_on=effort_on)
    prepared, _ = prepare_passthrough_request(prepared, selected_model, canonical_id, options)
    return prepared


def _notes_allow(route: PostRoute, model_id: str) -> bool:
    if route.handler.headers.get("X-Bypass-Model-Filter") == "1" or not route.host._MODEL_NOTES_FILTER.is_blocked(model_id):
        return True
    route.handler._send(503, {"error": {"message": "Model temporarily blocked by operational limits", "type": "model_limit_blocked", "code": 503}})
    return False


def _internal_allowed(route: PostRoute, requested_id: str) -> bool:
    host, handler = route.host, route.handler
    if not any(v in host.INTERNAL_MODEL_IDS for v in (route.raw_model, requested_id, route.model_id)):
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
    msg = f"Model '{requested_id}' is temporarily penalized due to start failures. Cooldown active for {retry_after}s."
    route.handler._send(503, {"error": {"message": msg, "type": "model_penalized", "code": 503, "penalized_until": int(stat["penalized_until"])}}, extra_headers={"Retry-After": str(retry_after)})
    return False


def _provider_allowed(route: PostRoute) -> bool:
    provider_id = route.ingress.provider_id
    if provider_id is None:
        return True
    host = route.host
    published = host._get_published_models()
    lookup_id = route.model_id
    if lookup_id not in published:
        alias = host._resolve_model_alias(lookup_id, published)
        if alias is None:
            route.handler._reject(404, "model_not_found", "model is not in the catalogue", "unknown", route.model_len)
            return False
        lookup_id = alias[0] if isinstance(alias, (tuple, list)) else alias
    adapter, model = published[lookup_id]
    fallback = getattr(model, "owned_by", "") or (model.get("owned_by", "") if isinstance(model, dict) else "")
    owner = getattr(adapter, "owned_by", "") if adapter is not None else fallback
    allowed = host.PROVIDER_SCOPES[provider_id]
    if owner in ((allowed,) if isinstance(allowed, str) else allowed):
        return True
    route.handler._reply_error(400, f"Model '{route.raw_model}' is not available for provider '{provider_id}'", code="model_not_in_provider_scope")
    return False


def _auth_allowed(route: PostRoute) -> bool:
    if route.host._auth_ok(route.handler):
        return True
    route.handler._reject(401, "unauthorized", "invalid or missing credentials", "unknown", route.model_len)
    return False


def _effort_type_allowed(route: PostRoute) -> bool:
    return native_effort(route) is not None


def _identify(context: PostRequestContext) -> PostRoute | None:
    raw_model = context.request.get("model")
    if not raw_model or not isinstance(raw_model, str):
        context.handler._reject(400, "invalid_model", "model must be a non-empty string", "unknown", 0)
        return None
    return PostRoute(context, dict(context.request), raw_model.strip(), raw_model, len(raw_model))


def _resolve_alias(route: PostRoute, models: Mapping[str, Any]) -> None:
    host = route.host
    if route.model_id in models or host.flag_enabled("DISABLE_MODEL_ALIASES"):
        return
    resolved = host._resolve_model_alias(route.model_id, models)
    if resolved:
        route.alias = resolved
        route.model_id = resolved[0]
        route.alias_effort = resolved[1] if len(resolved) > 1 else None


def _request_allowed(route: PostRoute, requested_id: str) -> bool:
    return all(step() for step in (
        lambda: _auth_allowed(route),
        lambda: _internal_allowed(route, requested_id),
        lambda: _penalty_allowed(route, requested_id),
        lambda: _provider_allowed(route),
        lambda: requested_id == route.model_id or _notes_allow(route, route.model_id),
        lambda: _effort_type_allowed(route),
    ))


class _MuseUsageGate:
    """Единственный владелец ленивого клиента квоты Muse (lock + bounded hot wait)."""

    def __init__(self) -> None:
        self._client: MuseUsageClient | None = None
        self._lock = threading.Lock()

    def snapshot(self, host: Any) -> Any:
        client = getattr(host, "_MUSE_USAGE_CLIENT", None) or getattr(host, "muse_usage_client", None)
        if client is None:
            with self._lock:
                self._client = self._client or MuseUsageClient()
                client = self._client
        return client.get_snapshot(wait_timeout_s=0.25) if isinstance(client, MuseUsageClient) else client.get_snapshot()


_MUSE_USAGE_GATE = _MuseUsageGate()


def check_muse_usage_gate(route: PostRoute) -> bool:
    """Fail-Closed при `exhausted`, Fail-Open при `unknown`/ошибках; только Muse-слоты и включённый флаг."""
    if str(route.model.get("backend") or "").strip().lower() != "muse":
        return True
    try:
        reader = getattr(route.host, "flag_enabled", None)
        if not (reader(_MUSE_USAGE_FLAG) if callable(reader) else _env_flag_enabled(_MUSE_USAGE_FLAG)):
            return True
        snapshot = _MUSE_USAGE_GATE.snapshot(route.host)
    except Exception:
        return True
    field = snapshot.get if isinstance(snapshot, Mapping) else lambda k, d=None: getattr(snapshot, k, d)
    if field("status") != "exhausted":
        return True
    route.handler._send(503, {"error": {"message": "Muse quota exhausted", "type": "muse_usage_exhausted", "code": 503, "reset_at": field("reset_at")}})
    return False


def _lookup_backend(backends: Any, name: str | None) -> Any:
    return getattr(backends, "get", lambda _n: None)(name) if isinstance(name, str) and backends is not None else None


def _backend_configs(host: Any) -> dict[str, Mapping[str, Any]]:
    return _zcr.backend_configs(host)


def _apply_filtered_routes(route: PostRoute, routing: dict[str, Any], kept: list[Any]) -> str | None:
    host = getattr(route, "host", None)
    routing_enabled = bool(host.flag_enabled("BRIDGE_TRANSPORT_ROUTING_ENABLED")) if host is not None else True
    return _zcr.apply_filtered_routes(route, routing, kept, routing_enabled=routing_enabled)


def _selected_backend_in_provider_scope(route: PostRoute, kept: list[Any] | None = None) -> bool:
    if (pid := route.ingress.provider_id) is None:
        return True
    scopes = getattr(route.host, "PROVIDER_SCOPES", None)
    allowed = scopes.get(pid) if isinstance(scopes, Mapping) else None
    if allowed is not None:
        allowed_owners = (allowed,) if isinstance(allowed, str) else tuple(allowed)
        backends = getattr(route.host, "BACKENDS", None)
        for item in kept or (route.model,):
            adapter = _lookup_backend(backends, item.get("backend") if isinstance(item, dict) else None)
            if not (owner := getattr(adapter, "owned_by", "")) or owner not in allowed_owners:
                break
        else:
            return True
    route.handler._reply_error(400, f"Model '{route.raw_model}' is not available for provider '{pid}'", code="model_not_in_provider_scope")
    return False


def _zero_canon_route_allowed(route: PostRoute) -> bool:
    cached = getattr(route.handler, "_review_profile", None)
    try:
        profile = cached if cached is not None else parse_review_profile_headers(getattr(route.handler, "headers", None))
        if profile != ZERO_CANON_HEADER_VALUE:
            return True
        routing = route.model.get("routing")
        routes = routing.get("routes") if isinstance(routing, dict) else None
        kept = filter_zero_canon_providers(routes if isinstance(routes, list) else [route.model], profile, provider_configs=_backend_configs(route.host), model_id=route.model_id)
    except ZeroCanonHttpError as exc:
        return route.reject(exc.status_code, exc.code, str(exc))
    if not kept:
        return route.reject(503, "route_unavailable", "no Zero-Canon eligible provider is available")
    if isinstance(routing, dict) and isinstance(routes, list):
        if _apply_filtered_routes(route, routing, kept) is None:
            return route.reject(503, "route_unavailable", "no active Zero-Canon route with positive weight")
    return _selected_backend_in_provider_scope(route, kept)


def _finalize_route_model(route: PostRoute) -> bool:
    routing = route.model.get("routing")
    if isinstance(routing, dict):
        backend, legacy, disabled = route.model.get("backend"), routing.get("legacy_backend"), routing.get("disabled_backend")
        if legacy not in (None, backend) and (disabled is None or backend != disabled):
            route.model.pop("routing", None)
            routing = None
    if isinstance(routing, dict) and not route.host.flag_enabled("BRIDGE_TRANSPORT_ROUTING_ENABLED") and routing.get("disabled_backend"):
        route.model["backend"] = routing["disabled_backend"]
    return _zero_canon_route_allowed(route)


def resolve_post_route(context: PostRequestContext) -> PostRoute | None:
    """Разрешает alias и каталог, не создавая попытку и не вызывая RNG."""
    route = _identify(context)
    if route is None or not _notes_allow(route, route.model_id):
        return None
    requested_id, host = route.model_id, route.host
    models = host.FLEET.get("models", {}) if isinstance(host.FLEET, dict) else {}
    _resolve_alias(route, models)
    if isinstance(models, Mapping) and route.model_id in models:
        route.model = dict(models[route.model_id])
    if not _request_allowed(route, requested_id):
        return None
    route.handler._telemetry_meta(model=route.model_id)
    if route.model_id not in models:
        route.handler._reject(404, "model_not_found", "model is not in the catalogue", "unknown", route.model_len)
        return None
    if not check_muse_usage_gate(route):
        return None
    return route if _finalize_route_model(route) else None


def log_route(route: PostRoute, mode: str) -> None:
    """Сохраняет прежнюю запись выбранного пути в существующем host logger."""
    alias = route.model_id + "-" + route.alias[1] if route.alias else "-"
    route.host._log(f"chat route={mode} model={route.model_id} alias={alias} {route.handler._trace_log_fields()}")


def native_effort(route: PostRoute) -> tuple[str, str] | None:
    """Сохраняет строгий тип effort и прежний downward clamp CLI.

    Каталог не обязан объявлять `default_effort`/`efforts` для каждого слота:
    отсутствующие поля дают fail-safe "high" вместо падения маршрута.
    """
    value = route.request.get("reasoning_effort")
    source = "alias" if value is None and route.alias_effort is not None else "request"
    value = route.alias_effort if source == "alias" else value
    declared = route.model.get("efforts")
    efforts = declared if isinstance(declared, (list, tuple)) and declared else ["high"]
    default_effort = route.model.get("default_effort") or efforts[0]
    if value is None or isinstance(value, str) and not value.strip():
        return default_effort, "default"
    if not isinstance(value, str):
        route.reject(400, "unsupported_reasoning_effort", "reasoning_effort must be a string")
        return None
    effort, clamped = route.host.clamp_effort_downward(value.strip(), efforts, default_effort)
    if clamped:
        route.host._log(route.host.describe_clamp("reasoning_effort", value.strip(), effort, route.model_id, route.host._LOG_EFFORT_MAX))
    return effort, source


def native_autonomy(route: PostRoute) -> tuple[Any, str] | None:
    """Применяет существующую политику autonomy выбранного CLI."""
    host = route.host
    try:
        if str(route.model.get("backend") or "").strip().lower() == "droid":
            sub = str(route.handler.headers.get("X-Subagent-Id") or "") or None
            decision = host.resolve_autonomy_decision(route.request.get("autonomy"), "DROID", subagent_id=sub, require_subagent=True)
            return decision.value, decision.source
        host.validate_autonomy_request(route.request.get("autonomy"))
    except host.AutonomyViolation as error:
        route.reject(400, error.reason, str(error))
        return None
    return route.request.get("autonomy"), "request"


def selected_route_allowed(route: PostRoute) -> bool:
    """Сохраняет post-selection deny и проверку отложенной авторизации."""
    handler, host = route.handler, route.host
    if str(route.model.get("backend") or "").strip().lower() == "droid":
        trace = getattr(handler, "_trace", None) or host._resolve_trace(
            dict(handler.headers.items()), route.request,
        )
        if host.denied_subagent(
            "DROID", str(handler.headers.get("X-Subagent-Id") or ""), trace.subagent_id,
        ):
            return route.reject(403, "droid_forbidden_for_role",
                                "droid route is forbidden for this subagent role")
    denial = host._quarantine_denial(route.model_id, handler.headers.get("X-Subagent-Id"))
    if denial is not None:
        handler._log_reject(denial.reason, route.model_id, route.model_len)
        handler.close_connection = True
        handler._send(denial.http, denial.body())
        return False
    if route.ingress.deferred_passthrough_auth:
        selected = host.BACKENDS.get(route.model["backend"])
        if not isinstance(selected, host.PassthroughAdapter) or not (
            selected.validate_client_token(host._extract_auth_token(handler))
        ):
            route.ingress.send_error(401, "auth_error", "unauthorized")
            return False
    return True


__all__ = (
    "PostRoute", "PreparedPostBody", "prepare_post_body", "prepare_route_request",
    "_notes_allow", "_internal_allowed", "_penalty_allowed", "_provider_allowed",
    "selected_route_allowed",
)
