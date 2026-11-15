"""Композиция HTTP и passthrough через живые порты server, без обратного импорта."""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Mapping
from copy import copy
from dataclasses import dataclass, field, fields, replace
from typing import Any

from core.passthrough_exchange import _validate_endpoint, internal_trace_scope
from core.route_attempts import AttemptPhase, RouteRefusal
from core.route_eligibility import EligibilityFacts, route_eligible
from core.route_health_policy import RetryBudgetConfig
from core.transport_credentials import credential_ready


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
        headers = {key: value for key, value in headers.items() if key.lower() not in names}
        headers.update(host._trace_headers(handler._trace))
    if call.hub_auth_ok and not getattr(call.adapter, "_upstream_key", None):
        headers = {key: value for key, value in headers.items()
                   if key.lower() not in {"authorization", "x-api-key", "x-turn-owner-token"}}
    headers["X-Bridge-No-Retry"] = "1"
    return headers


def _canonical_model(host: Any, model_id: str) -> str:
    models = host.FLEET.get("models", {}) if isinstance(host.FLEET, dict) else {}
    return (host._resolve_model_alias(model_id, models) or (model_id,))[0]


def _outcome(handler: Any, host: Any, sink: Any, model_id: str) -> None:
    lease = handler._current_lease()
    model_id = _canonical_model(host, model_id)
    error_type_fn = getattr(sink, "error_type", None)
    error_type = error_type_fn() if callable(error_type_fn) else ""
    discard = host._passthrough_discard_reason(sink.status, error_type)
    # ADR-0020 §3.2: обрыв клиента, таймаут шага и оборванный стрим нейтральны.
    if sink._client_gone_flag or discard:
        lease.record_discard("client_disconnected" if sink._client_gone_flag else discard)
    elif sink.status in (429, 402, 408):
        # Квота/лимит/таймаут старта относятся к модели, а не к здоровью origin.
        lease.record_success()
        host._PENALTY_TRACKER.record_start_failure(model_id, f"http_{sink.status}")
    elif 200 <= sink.status < 300 and not error_type:
        lease.record_success()
        host._PENALTY_TRACKER.record_start_success(model_id)
    elif 400 <= sink.status < 500:
        # Ошибка клиента не открывает circuit breaker.
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
    extra_headers = host._trace_headers(handler._trace)
    headers = [*extra_headers, ("X-Turn-Id", live_id)] if live_id else extra_headers
    sink = host._HandlerSink(handler, extra_headers=headers)
    attempt = getattr(handler, "_transport_attempt", None)
    sink.accepts_presend_errors = attempt is not None and not getattr(handler, "_headers_already_sent", False)
    sink.presend_deadline = attempt.deadline_s if attempt is not None else None
    try:
        if live_id:
            host.get_registry().register(live_id, host._owner_token_hash(handler), window)
        with internal_trace_scope(extra_headers):
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
    if isinstance(value, tuple):
        return [_plain_params(item) for item in value]
    return value


def _selected(route: Any, spec: Any) -> tuple[Any, Any]:
    model = {**route.model, "backend": spec.backend, "params": _plain_params(spec.params)}
    model.update({name: value for name in ("upstream_model", "default_effort", "context_window", "max_tokens")
                  if (value := getattr(spec, name)) is not None})
    for name in ("efforts", "input"):
        if value := getattr(spec, name):
            model[name] = list(value)
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
        ready = all((adapter.config.get("enabled", True), preflight, healthy, member,
                     not passthrough or credential_ready(adapter.config)))
        # preflight/is_healthy выше — свежие локальные проверки, не кэш probe.
        facts = EligibilityFacts(
            ready=ready, circuit_open=circuit["state"] == "OPEN", blocked_models=(),
            probe_age_s=0.0, max_stale_age_s=0.0, env_drift_keys=(),
            supports_images="image" in selected.model.get("input", ()),
            backend_kind=adapter.kind,
        )
        return route_eligible(spec, facts, policy)
    except (ValueError, OSError):
        return False


def _budget() -> RetryBudgetConfig:
    defaults = RetryBudgetConfig()
    return RetryBudgetConfig(**{
        field.name: type(getattr(defaults, field.name))(
            os.environ.get("BRIDGE_TRANSPORT_" + field.name.upper(), getattr(defaults, field.name))
        ) for field in fields(defaults)
    })


@dataclass(slots=True)
class _RetryBucket:
    tokens: float = 0.0
    updated_at: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)


_RETRY_BUCKET = _RetryBucket()

__all__ = ('PassthroughCall', '_headers', '_canonical_model', '_outcome', 'serve_passthrough', '_plain_params', '_selected', '_eligible', '_budget', '_RetryBucket')
