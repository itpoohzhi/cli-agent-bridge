"""Композиция HTTP и passthrough через живые порты server, без обратного импорта."""
from __future__ import annotations
import os
import threading
import time
from collections.abc import Mapping
from copy import copy
from dataclasses import dataclass, field, fields, replace
from typing import Any
from core.backend_adapter import PreSendTransientError as AdapterPreSendError
from core.model_modalities import supports_images
from core.effort_policy import pin_wire_effort
from core.http_post_dispatch import _cleanup_post, _passthrough, dispatch_route
from core.http_post_ingress import begin_post, read_post_request
from core.http_post_routing import prepare_post_body, resolve_post_route, selected_route_allowed
import core.passthrough_effort_map as _pem
from core.passthrough_exchange import _validate_endpoint, internal_trace_scope
from core.provider_route_scope import dispatch_scoped_single, filter_dispatch_routes
from core.quota_classifier import QuotaRules
from core.retry_control import MAX_RETRY_RATIO, MAX_TOTAL_ATTEMPTS_LIMIT, CircuitPolicy, RetryReservation, RetrySizing, RetryTokenBucket, RouteCandidate, validate_retry_sizing
from core.route_cb import RouteCB, RouteCBConfig, RouteCircuitBreaker, resolve_provider
from core.route_cb_guard import acquire_cb_guard, get_route_cb
from core.route_attempts import BRIDGE_OWNER, STATELESS_REPLAY_ENDPOINTS, AttemptPhase, AttemptState, RouteAttempt, RouteFailover, RouteRefusal, build_georouter_headers, evaluate_replay, failover_from_mapping, normalize_replay_endpoint
from core.route_failure_telemetry import emit_route_failure, finalize_passthrough_serve, finalize_routes_exit
from core.route_eligibility import EligibilityFacts, request_snapshot, route_eligible
from core.route_health_policy import RetryBudgetConfig, compute_attempt_decision
from core.routing_contract import ROUTING_ALGORITHM, PreSendTransientError, parse_routes
from core.routing_weights_runtime import base_model_routing as _model_routing  # noqa: F401
from core.routing_weights_runtime import effective_model_routing
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

def _headers(handler: Any, host: Any, call: PassthroughCall) -> dict[str, str]:
    headers = dict(handler.headers.items())
    if host.REQUEST_ATTRIBUTION_ENABLED:
        names = {host.REQUEST_ID_HEADER.lower(), host.SUBAGENT_ID_HEADER.lower()}
        headers = {key: value for key, value in headers.items() if key.lower() not in names} | dict(host._trace_headers(handler._trace))
    if call.hub_auth_ok and not getattr(call.adapter, "_upstream_key", None):
        headers = {key: value for key, value in headers.items() if key.lower() not in {"authorization", "x-api-key", "x-turn-owner-token"}}
    headers.update({"X-Bridge-No-Retry": "1", **build_georouter_headers({"retry_owner": BRIDGE_OWNER})})
    return headers

def _outcome(handler: Any, host: Any, sink: Any, model_id: str) -> None:
    lease = handler._current_lease()
    models = host.FLEET.get("models", {}) if isinstance(host.FLEET, dict) else {}
    model_id = (host._resolve_model_alias(model_id, models) or (model_id,))[0]
    error_type_fn = getattr(sink, "error_type", None)
    error_type = error_type_fn() if callable(error_type_fn) else ""
    discard = host._passthrough_discard_reason(sink.status, error_type)
    quota = sink.status in (429, 402, 408)
    # ADR-0020 §3.2: обрыв клиента, таймаут шага и оборванный стрим нейтральны.
    if sink._client_gone_flag or discard:
        lease.record_discard("client_disconnected" if sink._client_gone_flag else discard)
    elif 200 <= sink.status < 300 and not error_type:
        lease.record_success()
        host._PENALTY_TRACKER.record_start_success(model_id)
    elif quota or 400 <= sink.status < 500:
        # Квота/лимит/старт-таймаут и ошибки клиента относятся к модели, не к здоровью origin.
        lease.record_success()
        if quota:
            host._PENALTY_TRACKER.record_start_failure(model_id, f"http_{sink.status}")
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
    extra_headers = host._trace_headers(handler._trace)
    headers = [*extra_headers, ("X-Turn-Id", live_id)] if live_id else extra_headers
    sink = host._HandlerSink(handler, extra_headers=headers)
    attempt = getattr(handler, "_transport_attempt", None)
    sink.accepts_presend_errors, sink.presend_deadline = attempt is not None and not getattr(handler, "_headers_already_sent", False), attempt.deadline_s if attempt is not None else None
    try:
        if live_id:
            host.get_registry().register(live_id, host._owner_token_hash(handler), window)
        with internal_trace_scope(extra_headers):
            adapter.handle(path=handler.path, raw_body=raw, request=request, headers=_headers(handler, host, call), sink=sink, **({"window": window} if live_id else {}))
        _outcome(handler, host, sink, call.model_id)
    except RouteRefusal as error:
        attempt.advance_to(AttemptPhase.RESPONSE_HEADERS, error.status_code)
        sink.status = error.status_code
        _outcome(handler, host, sink, call.model_id)
        raise
    finally:
        host.get_registry().finish(live_id)
        finalize_passthrough_serve(handler, host, sink, started)

def _plain_params(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain_params(item) for key, item in value.items()}
    return [_plain_params(item) for item in value] if isinstance(value, tuple) else value

def _selected(route: Any, spec: Any) -> tuple[Any, Any]:
    model = {**route.model, "backend": spec.backend, "params": _plain_params(spec.params)}
    model.update({name: value for name in ("upstream_model", "default_effort", "context_window", "max_tokens") if (value := getattr(spec, name)) is not None})
    model.update({name: list(value) for name in ("efforts", "input") if (value := getattr(spec, name))})
    adapter = route.host.BACKENDS.get(spec.backend)
    if adapter is not None and spec.credential_ref is not None:
        adapter = copy(adapter)
        adapter.config = {**adapter.config, "api_key_ref": spec.credential_ref}
    return replace(route, model=model), adapter

def _eligible(route: Any, spec: Any, policy: Any) -> bool:
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
        ready = all((adapter.config.get("enabled", True), preflight, healthy, member, not passthrough or credential_ready(adapter.config)))
        # preflight/is_healthy выше — свежие локальные проверки, не кэш probe.
        facts = EligibilityFacts(ready=ready, circuit_open=circuit["state"] == "OPEN", blocked_models=(), probe_age_s=0.0, max_stale_age_s=0.0, env_drift_keys=(), supports_images=supports_images(selected.model, getattr(route, "model_id", "")), backend_kind=adapter.kind)
        return route_eligible(spec, facts, policy)
    except (ValueError, OSError):
        return False

@dataclass
class _RuntimeState:
    """Process-wide retry bucket и circuit breaker: состояние переживает запросы."""
    lock: Any = field(default_factory=threading.Lock)
    bucket: RetryTokenBucket | None = None
    sizing: RetrySizing | None = None
    breaker: RouteCircuitBreaker | None = None
    route_cb: RouteCB | None = None
    route_cb_config: RouteCBConfig | None = None

_RUNTIME = _RuntimeState()

def _begin_retry_request(config: RetryBudgetConfig, eligible_routes: int) -> RetryReservation:
    """Старт logical request: sizing из окружения, admit_primary и upfront-резервация."""
    prefix, env = "BRIDGE_TRANSPORT_RETRY_BUCKET_", os.environ
    capacity = parse_number(env, NumSpec((prefix + "CAPACITY",), 100, 1, float("inf")))
    ratio = parse_number(env, NumSpec((prefix + "RATIO",), MAX_RETRY_RATIO, 0, float("inf")))
    with _RUNTIME.lock:
        sizing = validate_retry_sizing({"capacity": capacity, "retry_ratio": ratio, "max_total_attempts": min(config.max_attempts, MAX_TOTAL_ATTEMPTS_LIMIT)})
        if _RUNTIME.bucket is None or sizing != _RUNTIME.sizing:
            _RUNTIME.bucket, _RUNTIME.sizing = RetryTokenBucket(sizing), sizing
        _RUNTIME.bucket.admit_primary()
        return _RUNTIME.bucket.reserve(eligible_routes)

def _retry_token(reservation: RetryReservation | None) -> bool:
    """Только расход собственной резервации запроса; без неё — отказ."""
    return reservation.consume() if reservation is not None else False

def _breaker() -> RouteCircuitBreaker:
    """Legacy singleton сохраняет здоровье доменов при BRIDGE_ROUTE_CB_ENABLED=0."""
    return get_route_cb(_RUNTIME)[1] or RouteCircuitBreaker(CircuitPolicy())

def _route_request(route: Any) -> Mapping[str, Any]:
    """Payload маршрута; отсутствие `request` (деградированный маршрут) не падает."""
    request = getattr(route, "request", None)
    return request if isinstance(request, Mapping) else {}

def _effort(route: Any) -> str:
    return _pem.logical_effort(_route_request(route), getattr(route, "alias_effort", None), getattr(route, "model", None))

def _pin_effort(route: Any) -> Any:
    """Закрепляет replay-effort в payload до наложения параметров маршрута."""
    request = getattr(route, "request", None)
    if not isinstance(request, Mapping):
        return route
    if not (effort := _effort(route)) or request.get("reasoning_effort") == effort or (effort == "off" and _pem.is_thinking_disabled(request)):
        return route
    route.request = pin_wire_effort(dict(request), effort)
    return route

def _attempt(route: Any, spec: Any, body: Any, attempt: RouteAttempt) -> None:
    selected, adapter = _selected(route, spec)
    selected, body = _pem.apply_attempt_effort_map(selected, adapter, body)
    route.handler._transport_attempt = attempt
    try:
        if isinstance(adapter, route.host.PassthroughAdapter) and spec.credential_ref is not None:
            # Только credential overlay требует локального adapter; реестр не меняется.
            if selected_route_allowed(selected):
                _passthrough(selected, adapter, body)
        else:
            dispatch_route(selected, body)
    finally:
        route.handler._transport_attempt = None

def _replay_gate(
    route: Any, state: AttemptState | None, config: RetryBudgetConfig,
    declared: RouteFailover | None = None,
) -> bool:
    """Fail-closed: без известного effort и без реальных фактов попытки replay запрещён."""
    if state is None:
        return True
    if (
        not _effort(route)
        and declared is not None
        and declared.opt_in
        and (state.status_code in declared.statuses or state.status_code in (401, 429, 503))
        and not state.committed
    ):
        # Маршрут явно объявил этот статус отказом слота: переход к следующему
        # слоту того же объявления — не replay исполненного запроса, а failover.
        return True
    path = getattr(route.handler, "path", None)
    effort = _effort(route)
    endpoint = normalize_replay_endpoint(path) if isinstance(path, str) else ""
    if not effort:
        return False
    facts: dict[str, object] = {"status_code": state.status_code, "timed_out": state.timed_out, "truncated": state.truncated, "wire_send_started": state.body_sent, "endpoint": endpoint, "tool_side_effects": state.tool_side_effects or endpoint not in STATELESS_REPLAY_ENDPOINTS, "downstream_committed": state.committed, "retry_owner": BRIDGE_OWNER, "max_total_attempts": config.max_attempts, "canonical_model_id": route.model_id, "effort": effort}
    return evaluate_replay(facts)["replay_allowed"] is True

def _route_failover(route: Any, backend: str) -> RouteFailover:
    """Per-route opt-in: контракт только этого бэкенда, без объединения по модели."""
    registries = getattr(route.host, "BACKENDS", None)
    adapter = registries.get(backend) if isinstance(registries, Mapping) else None
    return failover_from_mapping(
        getattr(adapter, "config", None) if adapter is not None else None
    )


def _credential_scope(route: Any, spec: Any) -> str:
    """Уникальный scope учётных данных слота (чтобы 429 одного слота не блокировал соседний)."""
    ref = getattr(spec, "credential_ref", None)
    if isinstance(ref, str) and ref:
        return ref
    registries = getattr(route.host, "BACKENDS", None)
    adapter = registries.get(spec.backend) if isinstance(registries, Mapping) else None
    cfg = getattr(adapter, "config", None) if adapter is not None else None
    if isinstance(cfg, Mapping):
        for key in ("api_key_ref", "quota_group", "api_key_env"):
            val = cfg.get(key)
            if isinstance(val, str) and val:
                return val
    return f"backend:{spec.backend}"


_emit_route_failure = emit_route_failure


def _run_routes(route: Any, routes: Any, seed: str, policy: Any) -> None:
    defaults = RetryBudgetConfig()
    config = RetryBudgetConfig(**{field.name: type(getattr(defaults, field.name))(os.environ.get("BRIDGE_TRANSPORT_" + field.name.upper(), getattr(defaults, field.name))) for field in fields(defaults)})
    config, started, last_error, state = replace(config, max_attempts=min(config.max_attempts, MAX_TOTAL_ATTEMPTS_LIMIT)), time.monotonic(), None, None
    by_backend, model = {spec.backend: spec for spec in routes}, {**route.model, "routing": {"enabled": True, "algorithm": ROUTING_ALGORITHM, **route.model["routing"]}}
    order = tuple(route_order(route.model_id, model, seed, getattr(route.handler._trace, "subagent_id", None), routes))
    route = _pin_effort(route)
    body, count, breakers, reservation = prepare_post_body(route), 0, get_route_cb(_RUNTIME), _begin_retry_request(config, len(order))
    refusals, quota_skipped, cb_blocked, declared, quota_rules = [], [], [], None, QuotaRules.from_config()
    try:
        for backend in order:
            if route.host._client_gone(route.handler.connection):
                return
            spec, now = by_backend[backend], time.monotonic()
            decision = compute_attempt_decision(config, count, now - started)
            if not decision.allow_retry or not _replay_gate(route, state, config, declared):
                break
            if not _eligible(route, spec, policy):
                continue
            candidate = RouteCandidate(route_id=spec.backend, origin=route.model_id, node=spec.backend, credential_scope=_credential_scope(route, spec), identity=f"{route.model_id}:{_effort(route)}")
            failover = _route_failover(route, backend)
            guard = acquire_cb_guard(breakers, candidate, (resolve_provider(route, spec), route.model_id, spec.backend), now, len(parse_routes(route.model) if "routes" in (route.model.get("routing") or {}) else ()))
            if guard.blocked:
                if guard.quota_refusal is not None:
                    quota_skipped.append((backend, guard.quota_refusal, failover))
                if guard.blocked_key is not None:
                    cb_blocked.append(guard.blocked_key)
                continue
            try:
                if count and not _retry_token(reservation):
                    break
                count += 1
                attempt = RouteAttempt(decision.attempt_budget_s, now + decision.attempt_budget_s, time.monotonic)
                attempt.advance(AttemptPhase.CONNECTING)
                _attempt(route, spec, body, attempt)
                attempt.advance_to(AttemptPhase.COMMITTED)
                guard.succeed(time.monotonic())
                return
            except (RouteRefusal, PreSendTransientError, AdapterPreSendError) as error:
                recorded_refusal = guard.record_error(error, route.host, failover, quota_rules)
                if isinstance(error, RouteRefusal) and recorded_refusal is not None:
                    attempt.advance_to(AttemptPhase.RESPONSE_HEADERS, error.status_code)
                    if failover.opt_in or error.status_code == 429:
                        refusals.append((backend, recorded_refusal, failover))
                        if failover.opt_in:
                            declared = failover
                # timed_out — наблюдённый факт дедлайна попытки; commit/side-effects уже в state.
                state = replace(attempt.state, timed_out=not isinstance(error, RouteRefusal) and attempt.remaining_s() <= 0)
                last_error = recorded_refusal if recorded_refusal is not None else error
            except BaseException as exc:
                guard.record_exception(exc)
                raise
            finally:
                guard.release()
        retry_after = breakers[0].retry_after_s(cb_blocked, time.monotonic()) if breakers[0] is not None and cb_blocked and count == 0 else None
        emit_route_failure(route, last_error, refusals, quota_skipped, retry_after)
    finally:
        finalize_routes_exit(route, reservation)

def _request_policy(route: Any) -> Any:
    """Объединяет все источники ролей: header не может скрыть роль в body."""
    request = {**route.request, "canonical_model_id": route.model_id}
    if request.get("reasoning_effort") is None and route.alias_effort is not None:
        request["reasoning_effort"] = route.alias_effort
    policy, trace_role = request_snapshot(request), getattr(getattr(route.handler, "_trace", None), "subagent_id", None)
    header_policy = request_snapshot({"model": route.model_id, "headers": dict(route.handler.headers.items()), "trace_subagent_id": trace_role if isinstance(trace_role, str) else None})
    return replace(policy, role_ids=policy.role_ids + header_policy.role_ids, excluded=policy.excluded | header_policy.excluded)

def _dispatch(route: Any) -> None:
    routing = effective_model_routing(route.model_id, route.model)
    if not (route.host.flag_enabled(ROUTING_FLAG) and routing and routing.get("enabled", True)):
        dispatch_scoped_single(route, routing, _pem.apply_attempt_effort_map, prepare_post_body, dispatch_route)
        return
    route = replace(route, model={**route.model, "routing": routing})
    if route.model_id.endswith("-" + route.model["backend"]) and not selected_route_allowed(route):
        return
    policy = _request_policy(route)
    routes = tuple(spec for spec in parse_routes(route.model) if _eligible(route, spec, policy))
    if (routes := filter_dispatch_routes(route, routes)) is None:
        return
    seed = resolve_transport_seed(dict(route.handler.headers.items()), {**route.request, **route.ingress.transport_controls})
    _run_routes(route, routes, seed, policy)

def handle_post(handler: Any, host: Any) -> None:
    """Общие auth/admission/alias и routing для всех API/CLI-входов."""
    context = begin_post(handler, host)
    if context is None:
        return
    try:
        if (route := resolve_post_route(context) if read_post_request(context) else None) is not None:
            _dispatch(route)
    except ValueError:
        handler._reject(400, "invalid_request", "invalid transport controls")
    finally:
        _cleanup_post(context)
