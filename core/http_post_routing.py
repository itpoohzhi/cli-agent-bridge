"""Разрешение модели и ограничений POST без исполнения транспорта."""

from __future__ import annotations

import hmac
import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from core.effort_policy import ModelEffortSpec, resolve_passthrough_effort
from core.http_post_context import PostRequestContext
from core.http_post_ingress import clean_transport_request
from core.passthrough_autonomy import resolve_target_model


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
    """Накладывает только выбранный маршрут на чистый исходный запрос.

    Явные параметры клиента сильнее route defaults. Повторный маршрут должен
    получить тот же исходный request, а не результат предыдущей подготовки.
    """
    params = selected_model.get("params")
    prepared = {**(params if isinstance(params, dict) else {}), **request}
    prepared.pop("transport_seed", None)
    prepared["model"] = resolve_target_model(selected_model, canonical_id)
    effort = resolve_passthrough_effort(
        request.get("reasoning_effort"),
        alias_effort if request.get("reasoning_effort") is None else None,
        ModelEffortSpec.from_catalog_entry(selected_model), enabled=effort_on,
    )
    if effort.apply:
        prepared["reasoning_effort"] = effort.value
    return prepared


def _notes_allow(route: PostRoute, model_id: str) -> bool:
    if route.handler.headers.get("X-Bypass-Model-Filter") == "1":
        return True
    if not route.host._MODEL_NOTES_FILTER.is_blocked(model_id):
        return True
    route.handler._send(503, {"error": {
        "message": "Model temporarily blocked by operational limits",
        "type": "model_limit_blocked", "code": 503,
    }})
    return False


def _internal_allowed(route: PostRoute, requested_id: str) -> bool:
    host, handler = route.host, route.handler
    key = getattr(host, "_INTERNAL_SERVICE_KEY", None) or os.environ.get(
        "INTERNAL_SERVICE_KEY", "",
    )
    if not key or not any(
        value in host.INTERNAL_MODEL_IDS
        for value in (route.raw_model, requested_id, route.model_id)
    ):
        return True
    supplied = handler.headers.get("X-Internal-Service-Key", "")
    if hmac.compare_digest(supplied.encode("utf-8"), key.encode("utf-8")):
        return True
    handler._reject(403, "internal_model_forbidden",
                    "Model reserved for internal review", "unknown", route.model_len)
    return False


def _penalty_allowed(route: PostRoute, requested_id: str) -> bool:
    stat = route.host._PENALTY_TRACKER.get_model_status(route.model_id.strip().lower())
    if not stat["is_penalized"]:
        return True
    retry_after = max(1, math.ceil(stat["remaining_cooldown"]))
    route.handler._send(503, {"error": {
        "message": (
            f"Model '{requested_id}' is temporarily "
            f"penalized due to start failures. Cooldown active for {retry_after}s."
        ),
        "type": "model_penalized", "code": 503,
        "penalized_until": int(stat["penalized_until"]),
    }}, extra_headers={"Retry-After": str(retry_after)})
    return False


def _provider_allowed(route: PostRoute) -> bool:
    provider_id = route.ingress.provider_id
    if provider_id is None:
        return True
    host = route.host
    published = host._get_published_models()
    if route.model_id not in published:
        route.handler._reject(404, "model_not_found",
                              "model is not in the catalogue", "unknown", route.model_len)
        return False
    adapter, model = published[route.model_id]
    owner = getattr(adapter, "owned_by", "") if adapter is not None else (
        getattr(model, "owned_by", "")
        or (model.get("owned_by", "") if isinstance(model, dict) else "")
    )
    allowed = host.PROVIDER_SCOPES[provider_id]
    if owner in ((allowed,) if isinstance(allowed, str) else allowed):
        return True
    route.handler._reply_error(
        400, f"Model '{route.raw_model}' is not available for provider '{provider_id}'",
        code="model_not_in_provider_scope",
    )
    return False


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

__all__ = ('PostRoute', 'PreparedPostBody', 'prepare_post_body', 'prepare_route_request', '_notes_allow', '_internal_allowed', '_penalty_allowed', '_provider_allowed', 'selected_route_allowed')
