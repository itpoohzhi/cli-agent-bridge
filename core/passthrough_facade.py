"""Композиция HTTP и passthrough через живые порты server, без обратного импорта."""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Mapping
from copy import copy
from dataclasses import dataclass, fields, replace
from typing import Any

from core.backend_adapter import PreSendTransientError as AdapterPreSendError
from core.http_post_dispatch import _cleanup_post, _passthrough, dispatch_route
from core.http_post_dispatch_guard import read_post_request
from core.http_post_ingress import begin_post
from core.http_post_routing import prepare_post_body, resolve_post_route, selected_route_allowed
from core.passthrough_exchange import _validate_endpoint, internal_trace_scope
from core.passthrough_outcome import LeaseFenced
from core.route_attempts import AttemptPhase, RouteAttempt, RouteRefusal, decide_attempt
from core.route_eligibility import EligibilityFacts, request_snapshot, route_eligible
from core.route_health_policy import RetryBudgetConfig
from core.routing_contract import ROUTING_ALGORITHM, PreSendTransientError, parse_routes
from core.runtime_env import NumSpec, parse_number
from core.transport_credentials import credential_ready
from core.transport_routing import route_order
from core.transport_settings import ROUTING_FLAG, resolve_transport_seed

@dataclass(frozen=True)
class PassthroughCall:
    """Прежние аргументы HTTP-шва без изменения публичного метода handler."""

    adapter: Any
    raw: bytes
    request: dict[str, Any]
    model_id: str
    hub_auth_ok: bool = False
    is_probe: bool = False
    idempotency_key: str | None = None

def build_half_open_probe(call: PassthroughCall, lease: Any) -> PassthroughCall:
    """Строит HALF_OPEN-пробу: PONG in-process, tools пусты, клиентское тело не наследуется."""
    request: dict[str, Any] = {"model": call.model_id, "messages": [{"role": "user", "content": "PONG"}],
                               "tools": [], "stream": False, "is_probe": True,
                               "idempotency_key": f"ho:{lease.edge_key}:{lease.lease_epoch}:{lease.lease_token}"}
    return PassthroughCall(adapter=call.adapter, request=request, model_id=call.model_id, is_probe=True,
                           idempotency_key=request["idempotency_key"],
                           raw=json.dumps(request, ensure_ascii=False).encode("utf-8"))

def _headers(handler: Any, host: Any, call: PassthroughCall) -> dict[str, str]:
    """Заголовки egress: атрибуция хоста, снятие hub-ключа и запрет автоповтора."""
    headers = dict(handler.headers.items())
    if host.REQUEST_ATTRIBUTION_ENABLED:
        drop = {host.REQUEST_ID_HEADER.lower(), host.SUBAGENT_ID_HEADER.lower()}
        headers = {k: v for k, v in headers.items() if k.lower() not in drop}
        headers.update(host._trace_headers(handler._trace))
    if call.hub_auth_ok and not getattr(call.adapter, "_upstream_key", None):
        keep_out = {"authorization", "x-api-key", "x-turn-owner-token"}
        headers = {k: v for k, v in headers.items() if k.lower() not in keep_out}
    headers["X-Bridge-No-Retry"] = "1"
    return headers

def _canonical_model(host: Any, model_id: str) -> str:
    models = host.FLEET.get("models", {}) if isinstance(host.FLEET, dict) else {}
    return (host._resolve_model_alias(model_id, models) or (model_id,))[0]

def _outcome(handler: Any, host: Any, sink: Any, model_id: str) -> None:
    """Единственная фиксация исхода: обрыв/таймаут шага нейтральны (ADR-0020 §3.2), квота — сбой модели."""
    lease = handler._current_lease()
    model_id = _canonical_model(host, model_id)
    error_type_fn = getattr(sink, "error_type", None)
    error_type = error_type_fn() if callable(error_type_fn) else ""
    discard = host._passthrough_discard_reason(sink.status, error_type)
    if sink._client_gone_flag or discard:
        lease.record_discard("client_disconnected" if sink._client_gone_flag else discard)
    elif sink.status in (429, 402, 408):
        lease.record_success()
        host._PENALTY_TRACKER.record_start_failure(model_id, f"http_{sink.status}")
    elif 200 <= sink.status < 300 and not error_type:
        lease.record_success()
        host._PENALTY_TRACKER.record_start_success(model_id)
    elif 400 <= sink.status < 500:
        lease.record_success()
    else:
        lease.record_failure()
        host._PENALTY_TRACKER.record_start_failure(model_id, error_type or f"http_{sink.status}")

def serve_passthrough(handler: Any, host: Any, call: PassthroughCall) -> None:
    """Сохраняет headers, liveness, telemetry и единственную фиксацию исхода."""
    adapter, started = call.adapter, time.monotonic()
    handler._telemetry_meta(route_mode="passthrough", backend_id=adapter.id, model=call.model_id)
    host._log(f"passthrough route model={call.model_id} backend={adapter.id} {handler._trace_log_fields()}")
    raw, request = host._strip_passthrough_env(call.raw, call.request)
    live_id = host.new_passthrough_turn_id() if host.flag_enabled(host.FLAG_TELEMETRY) else ""
    window = host.passthrough_window(adapter.limits, handler.path, request) if live_id else None
    extra, attempt = host._trace_headers(handler._trace), getattr(handler, "_transport_attempt", None)
    sink = host._HandlerSink(handler, extra_headers=[*extra, ("X-Turn-Id", live_id)] if live_id else extra)
    sink.accepts_presend_errors = attempt is not None and not getattr(handler, "_headers_already_sent", False)
    sink.presend_deadline = attempt.deadline_s if attempt is not None else None
    try:
        if live_id:
            host.get_registry().register(live_id, host._owner_token_hash(handler), window)
        with internal_trace_scope(extra):
            adapter.handle(path=handler.path, raw_body=raw, request=request,
                           headers=_headers(handler, host, call), sink=sink,
                           **({"window": window} if live_id else {}))
        _outcome(handler, host, sink, call.model_id)
    except RouteRefusal as error:
        attempt.advance(AttemptPhase.SENDING)
        attempt.advance(AttemptPhase.RESPONSE_HEADERS, error.status_code)
        sink.status = error.status_code
        _outcome(handler, host, sink, call.model_id)
        raise
    finally:
        host.get_registry().finish(live_id)
        handler._telemetry_passthrough_done(sink.status)
        host._log(f"done route=passthrough status={sink.status} {handler._trace_log_fields()} elapsed_ms={int((time.monotonic() - started) * 1000)}")

def _plain_params(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain_params(item) for key, item in value.items()}
    return [_plain_params(item) for item in value] if isinstance(value, tuple) else value

def _selected(route: Any, spec: Any) -> tuple[Any, Any]:
    model = {**route.model, "backend": spec.backend, "params": _plain_params(spec.params)}
    model.update({n: getattr(spec, n) for n in ("upstream_model", "default_effort", "context_window", "max_tokens") if getattr(spec, n) is not None})
    model.update({name: list(value) for name in ("efforts", "input") if (value := getattr(spec, name))})
    adapter = route.host.BACKENDS.get(spec.backend)
    if adapter is not None and spec.credential_ref is not None:
        adapter = copy(adapter)
        adapter.config = {**adapter.config, "api_key_ref": spec.credential_ref}
    return replace(route, model=model), adapter

def _eligible(route: Any, spec: Any, policy: Any) -> bool:
    """Свежие локальные проверки preflight/is_healthy, не кэш probe-результата."""
    selected, adapter = _selected(route, spec)
    if adapter is None:
        return False
    passthrough = isinstance(adapter, route.host.PassthroughAdapter)
    try:
        if passthrough:
            _validate_endpoint(adapter)
        preflight, healthy = adapter.preflight()[0], adapter.is_healthy()
        member = any(model.id == route.model_id for model in adapter.get_models())
        circuit = route.host.RESILIENCE.snapshot((spec.backend,))["backends"][spec.backend]
        ready = all((adapter.config.get("enabled", True), preflight, healthy, member,
                     not passthrough or credential_ready(adapter.config)))
        facts = EligibilityFacts(ready=ready, circuit_open=circuit["state"] == "OPEN", blocked_models=(),
                                 probe_age_s=0.0, max_stale_age_s=0.0, env_drift_keys=(), backend_kind=adapter.kind,
                                 supports_images="image" in selected.model.get("input", ()))
        return route_eligible(spec, facts, policy)
    except (ValueError, OSError):
        return False

def _budget() -> RetryBudgetConfig:
    """Конфиг retry-бюджета из окружения поверх дефолтов класса."""
    defaults = RetryBudgetConfig()
    return RetryBudgetConfig(**{n: type(v)(os.environ.get("BRIDGE_TRANSPORT_" + n.upper(), v))
                                for n, v in ((i.name, getattr(defaults, i.name)) for i in fields(defaults))})

_RETRY_LOCK, _RETRY_STATE = threading.Lock(), [0.0, 0.0]

def _retry_token(config: RetryBudgetConfig) -> bool:
    """Общий неблокирующий bucket с настраиваемыми burst и скоростью refill."""
    prefix, env = "BRIDGE_TRANSPORT_RETRY_BUCKET_", os.environ
    capacity = parse_number(env, NumSpec((prefix + "CAPACITY",), 100, 1, float("inf")))
    rate = parse_number(env, NumSpec((prefix + "RATE_S",), config.max_attempts, 0, float("inf")))
    with _RETRY_LOCK:
        now = time.monotonic()
        tokens, previous = _RETRY_STATE
        tokens = capacity if not previous else min(capacity, tokens + (now - previous) * rate)
        allowed = tokens >= 1
        _RETRY_STATE[:] = tokens - int(allowed), now
        return allowed

def _attempt(route: Any, spec: Any, body: Any, attempt: RouteAttempt) -> None:
    selected, adapter = _selected(route, spec)
    route.handler._transport_attempt = attempt
    try:
        if isinstance(adapter, route.host.PassthroughAdapter) and spec.credential_ref is not None:
            if not selected_route_allowed(selected):
                return
            _passthrough(selected, adapter, body)
        else:
            dispatch_route(selected, body)
    finally:
        route.handler._transport_attempt = None

def _run_routes(route: Any, routes: Any, seed: str, policy: Any) -> None:
    """Один проход по порядку рёбер; неизвестный исход клиентского POST не повторяется."""
    config, started, last_error, state = _budget(), time.monotonic(), None, None
    routing = {"enabled": True, "algorithm": ROUTING_ALGORITHM, **route.model["routing"]}
    by_backend = {spec.backend: spec for spec in routes}
    order = route_order(route.model_id, {**route.model, "routing": routing}, seed, getattr(route.handler._trace, "subagent_id", None), routes)
    body, count = prepare_post_body(route), 0
    for backend in order:
        if route.host._client_gone(route.handler.connection):
            return
        decision = decide_attempt(config, count, time.monotonic() - started, state)
        if not decision.allow_retry:
            break
        spec = by_backend[backend]
        if not _eligible(route, spec, policy):
            continue
        if count and not _retry_token(config):
            break
        count += 1
        attempt = RouteAttempt(decision.attempt_budget_s, time.monotonic() + decision.attempt_budget_s, time.monotonic)
        attempt.advance(AttemptPhase.CONNECTING)
        try:
            _attempt(route, spec, body, attempt)
            return
        except (RouteRefusal, PreSendTransientError, AdapterPreSendError) as error:
            last_error, state = error, attempt.state
    if isinstance(last_error, RouteRefusal):
        sink = route.host._HandlerSink(route.handler, extra_headers=route.host._trace_headers(route.handler._trace))
        sink.start(last_error.status_code, list(last_error.response_headers))
        sink.write(last_error.response_body)
    else:
        route.reject(503, "route_unavailable", "no eligible transport is available")

def _request_policy(route: Any) -> Any:
    """Объединяет все источники ролей: header не может скрыть роль в body."""
    request = {**route.request, "canonical_model_id": route.model_id}
    if request.get("reasoning_effort") is None and route.alias_effort is not None:
        request["reasoning_effort"] = route.alias_effort
    policy = request_snapshot(request)
    trace_role = getattr(getattr(route.handler, "_trace", None), "subagent_id", None)
    header_policy = request_snapshot({"model": route.model_id, "headers": dict(route.handler.headers.items()),
                                      "trace_subagent_id": trace_role if isinstance(trace_role, str) else None})
    return replace(policy, role_ids=policy.role_ids + header_policy.role_ids,
                   excluded=policy.excluded | header_policy.excluded)

def _model_routing(model: dict[str, Any]) -> dict[str, Any]:
    routing = model.get("routing")
    backend = model.get("backend")
    if isinstance(routing, dict) and routing.get("legacy_backend") in (None, backend):
        return routing
    if not backend:
        return {}
    spec = dict(route_id=backend, backend=backend, weight=100, priority=0)
    spec["params"] = model.get("params", {})
    return {"catalog_hash": "singleton:" + backend, "routes": [spec]}

def _dispatch(route: Any) -> None:
    routing = _model_routing(route.model)
    if not (route.host.flag_enabled(ROUTING_FLAG) and routing and routing.get("enabled", True)):
        route.model["backend"] = routing.get("disabled_backend") or route.model.get("backend")
        dispatch_route(route)
        return
    route = replace(route, model={**route.model, "routing": routing})
    if route.model_id.endswith("-" + route.model["backend"]) and not selected_route_allowed(route):
        return
    policy = _request_policy(route)
    routes = tuple(spec for spec in parse_routes(route.model) if _eligible(route, spec, policy))
    if not routes:
        route.reject(503, "route_unavailable", "no eligible transport is available")
        return
    seed = resolve_transport_seed(dict(route.handler.headers.items()), {**route.request, **route.ingress.transport_controls})
    _run_routes(route, routes, seed, policy)

def _ingress_ok(handler: Any, request: Mapping[str, Any]) -> bool:
    """Probe клиента — 400 до маршрута и alias; тело не читается, замечания решает guard."""
    probe_headers = {"x-probe", "x-bridge-probe"}
    if "is_probe" in request or any(str(key).lower() in probe_headers for key in handler.headers):
        handler._reject(400, "invalid_request_error", "probe controls are reserved")
        return False
    return True

def _fence(handler: Any) -> None:
    """LeaseFenced терминален: 503 до заголовков, protocol error и close после них."""
    if not getattr(handler, "_headers_already_sent", False):
        handler._reject(503, "lease_fenced", "passthrough lease is not current")
        return
    payload = json.dumps({"error": {"message": "lease_fenced", "type": "lease_fenced", "code": 503}})
    try:
        handler.wfile.write(b"event: error\r\ndata: " + payload.encode("utf-8") + b"\r\n\r\n")
        handler.wfile.flush()
    except (AttributeError, OSError, ValueError):
        pass
    handler.close_connection = True

def handle_post(handler: Any, host: Any) -> None:
    """Допуск, отказ пробе, routing и терминальный fencing для всех API/CLI-входов."""
    context = begin_post(handler, host)
    if context is None:
        return
    try:
        if not _ingress_ok(handler, context.request):
            return
        if read_post_request(context):
            route = resolve_post_route(context)
            if route is not None:
                _dispatch(route)
    except LeaseFenced:
        _fence(handler)
    except ValueError:
        handler._reject(400, "invalid_request", "invalid transport controls")
    finally:
        _cleanup_post(context)
