"""Контракты readiness, предвыбора и настоящего HTTP-входа транспорта."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import pytest

import server
from adapters import ADAPTER_KINDS
from core.backend_adapter import AdapterRegistry
from tests.transport_test_support import (
    RecordingUpstream,
    RunningHTTPServer,
    WireSettings,
    make_adapter,
    semantic_equal,
    wire_post,
)

HUB_KEY = "transport-fixture-hub-key"


def stage_entry(module: str, name: str, legacy: Callable[..., Any]) -> Callable[..., Any]:
    """До выноса вызываем реальный legacy-шов, а не имитируем ошибку импорта."""
    if importlib.util.find_spec(module) is None:
        return legacy
    return getattr(importlib.import_module(module), name)


@pytest.fixture(autouse=True)
def transport_options(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in {
        "BRIDGE_TRANSPORT_ROUTING_ENABLED": "true",
        "BRIDGE_TRANSPORT_TEST_SEED_ENABLED": "false",
        "BRIDGE_NONSTREAM_VIA_STREAM_ENABLED": "false",
        "BRIDGE_CONNECTION_POOLING_ENABLED": "false",
        "BRIDGE_PASSTHROUGH_PRESEND_MAX_RETRIES": "1",
        "BRIDGE_PASSTHROUGH_PRESEND_RETRY_DELAY_S": "0.001",
        "BRIDGE_PASSTHROUGH_PRESEND_RETRY_MAX_DELAY_S": "0.001",
        "BRIDGE_TELEMETRY_ENABLED": "false",
        "BRIDGE_RESILIENCE_ENABLED": "false",
    }.items():
        monkeypatch.setenv(key, value)


def _catalog(upstreams: Mapping[str, RecordingUpstream], configs: Mapping) -> dict[str, Any]:
    backends, routes = {}, []
    for index, (name, upstream) in enumerate(upstreams.items()):
        backends[name] = {
            "kind": "passthrough", "base_url": upstream.base_url,
            "enabled": True, "max_concurrent": 1, **configs.get(name, {}),
        }
        routes.append({
            "route_id": name, "backend": name, "weight": 100 if index == 0 else 0,
            "priority": index, "upstream_model": "m", "efforts": ["low", "high"],
            "default_effort": "high", "context_window": 8192, "max_tokens": 1024,
        })
    active = [{key: route[key] for key in ("route_id", "backend", "weight")}
              for route in routes if route["weight"] > 0]
    encoded = json.dumps(sorted(active, key=lambda r: (r["route_id"], r["backend"])),
                         sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    primary = next(iter(upstreams))
    model = {
        "id": "m", "backend": primary, "context_window": 8192, "max_tokens": 1024,
        "efforts": ["low", "high"], "default_effort": "high", "input": ["text"],
        "images": {"status": "unsupported", "method": None},
        "routing": {"legacy_backend": primary, "disabled_backend": primary,
                    "catalog_hash": hashlib.sha256(encoded).hexdigest(), "routes": routes},
    }
    return {"schema": 3, "models": {"m": model}, "order": ["m"], "backends": backends,
            "backend_order": list(backends),
            "image_limits": {"max_body_bytes": WireSettings().max_body_bytes}}


@contextmanager
def gateway(
    monkeypatch: pytest.MonkeyPatch,
    upstreams: Mapping[str, RecordingUpstream],
    configs: Mapping | None = None,
) -> Iterator[tuple[int, dict[str, Any]]]:
    """Не подменяет do_POST, dispatch, auth или passthrough, только зависимости."""
    catalog = _catalog(upstreams, configs or {})
    registry = AdapterRegistry.from_fleet(catalog, ADAPTER_KINDS, lambda: catalog, server)
    monkeypatch.setattr(server, "FLEET", catalog)
    monkeypatch.setattr(server, "BACKENDS", registry)
    monkeypatch.setattr(server, "AUTH_KEY", HUB_KEY)
    monkeypatch.setattr(server, "TOKEN_CACHE", server.TokenCache(
        path=server.ROOT / ".transport-fixture-absent.env", environ={"BRIDGE_KEY": HUB_KEY},
    ))
    monkeypatch.setattr(server, "_shutting_down", False)
    monkeypatch.setattr(server, "_is_drain_enabled", lambda: False)
    monkeypatch.setattr(server, "_log", lambda message: None)
    try:
        with RunningHTTPServer(server.Handler) as listener:
            yield listener.port, catalog
    finally:
        for adapter in registry.adapters():
            adapter.shutdown()


def request_body(stream: bool = False) -> dict[str, Any]:
    return {"model": "m", "stream": stream, "reasoning_effort": "high",
            "messages": [{"role": "user", "content": "wire-marker"}]}


def post(port: int, body: dict, headers: Mapping[str, str] | None = None) -> tuple[int, bytes]:
    return wire_post(port, body, {"Authorization": f"Bearer {HUB_KEY}", **(headers or {})})


def success(upstream: RecordingUpstream, stream: bool) -> None:
    if stream:
        upstream.respond = lambda handler, body: upstream.sse(
            handler, b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n',
        )
    else:
        upstream.respond = lambda handler, body: upstream.json(
            handler, {"choices": [{"message": {"role": "assistant", "content": "ok"}}]},
        )


@pytest.mark.semantic_red("live_env_credential_resolution")
def test_stage_w2_a_credential_rotation_and_revoke(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSPORT_FIXTURE_API_KEY", "fixture-first")
    with RecordingUpstream() as upstream:
        adapter = make_adapter(upstream, {"api_key_ref": "env:TRANSPORT_FIXTURE_API_KEY"})
        resolver = stage_entry(
            "core.transport_credentials", "resolve_credential",
            lambda config: adapter._read_key_ref(),
        )
        try:
            values = [resolver(adapter.config)]
            monkeypatch.setenv("TRANSPORT_FIXTURE_API_KEY", "fixture-rotated")
            values.append(resolver(adapter.config))
            monkeypatch.delenv("TRANSPORT_FIXTURE_API_KEY")
            values.append(resolver(adapter.config))
        finally:
            adapter.shutdown()
        assert (upstream.post_count, upstream.body_bytes) == (0, 0)
    semantic_equal(values, ["fixture-first", "fixture-rotated", ""],
                   "live_env_credential_resolution")


def _facts() -> dict[str, Any]:
    return {
        "known_backend": True, "enabled": True, "model_member": True,
        "supports_effort": True, "egress_allowed": True, "credential_ready": True,
        "preflight_ok": True, "healthy": True, "circuit_open": False,
        "blocked_models": (), "probe_age_s": 0.0, "max_stale_age_s": 30.0,
        "env_drift_keys": (),
    }


@pytest.mark.semantic_red("hard_eligibility_before_draw")
@pytest.mark.parametrize("field,value", [
    ("known_backend", False), ("enabled", False), ("model_member", False),
    ("supports_effort", False), ("egress_allowed", False), ("credential_ready", False),
    ("preflight_ok", False), ("healthy", False), ("circuit_open", True),
    ("blocked_models", ("m",)), ("probe_age_s", 31.0),
    ("env_drift_keys", ("TRANSPORT_FIXTURE_API_KEY",)),
])
def test_stage_w2_b_hard_eligibility_snapshot(field: str, value: Any) -> None:
    facts = {**_facts(), field: value}
    route = {"route_id": "first", "backend": "recording", "model_id": "m", "weight": 100}
    original = dict(facts)
    with RecordingUpstream() as upstream:
        adapter = make_adapter(upstream)
        eligible = stage_entry("core.route_eligibility", "route_eligible",
                               lambda route, facts, request: adapter.preflight().ok)
        try:
            actual = eligible(route, facts, request_body())
        finally:
            adapter.shutdown()
        assert facts == original
        assert (upstream.post_count, upstream.body_bytes) == (0, 0)
    semantic_equal(actual, False, "hard_eligibility_before_draw")


@pytest.mark.semantic_red("judge_sources_before_draw")
@pytest.mark.parametrize("source", ["header", "body", "extra_body", "trace"])
@pytest.mark.parametrize("role", ["panel-review-1", "judge-1", "seat-1"])
def test_stage_w2_b_judge_sources_exclude_droid(source: str, role: str) -> None:
    request = request_body()
    placements = {
        "header": {"headers": {"X-Subagent-Id": role}},
        "body": {"subagent_id": role},
        "extra_body": {"extra_body": {"subagent_id": role}},
        "trace": {"trace_subagent_id": role},
    }
    request.update(placements[source])
    route = {"route_id": "droid", "backend": "droid", "model_id": "m", "weight": 0}
    with RecordingUpstream() as upstream:
        adapter = make_adapter(upstream)
        eligible = stage_entry("core.route_eligibility", "route_eligible",
                               lambda route, facts, request: adapter.preflight().ok)
        try:
            actual = eligible(route, _facts(), request)
        finally:
            adapter.shutdown()
        assert upstream.post_count == 0
    semantic_equal(actual, False, "judge_sources_before_draw")


@pytest.mark.semantic_red("caller_exclusion_before_post")
@pytest.mark.parametrize("stream", [False, True])
def test_excluded_primary_has_zero_wire_bytes(
    monkeypatch: pytest.MonkeyPatch, stream: bool,
) -> None:
    with RecordingUpstream() as first, RecordingUpstream() as reserve:
        success(first, stream)
        success(reserve, stream)
        with gateway(monkeypatch, {"first": first, "reserve": reserve}) as (port, _):
            status, body = post(port, request_body(stream), {"X-Exclude-Transports": "FiRsT"})
        assert status == 200 and b"ok" in body
        actual = (first.post_count, first.body_bytes, reserve.post_count)
    semantic_equal(actual, (0, 0, 1), "caller_exclusion_before_post")


@pytest.mark.semantic_red("empty_eligible_pool_no_post")
@pytest.mark.parametrize("stream", [False, True])
def test_empty_eligible_pool_is_route_unavailable(
    monkeypatch: pytest.MonkeyPatch, stream: bool,
) -> None:
    with RecordingUpstream() as upstream:
        success(upstream, stream)
        with gateway(monkeypatch, {"first": upstream}) as (port, _):
            status, body = post(port, request_body(stream), {"X-Exclude-Transports": "FIRST"})
        error_type = json.loads(body).get("error", {}).get("type") if status == 503 else None
        actual = (status, error_type, upstream.post_count, upstream.body_bytes)
    semantic_equal(actual, (503, "route_unavailable", 0, 0), "empty_eligible_pool_no_post")


@pytest.mark.semantic_red("canonical_judge_uses_eligible_alternate")
@pytest.mark.parametrize("source", ["header", "body", "extra_body"])
@pytest.mark.parametrize("role", ["panel-review-1", "judge-1", "seat-1"])
def test_canonical_judge_avoids_droid_before_post(
    monkeypatch: pytest.MonkeyPatch, source: str, role: str,
) -> None:
    request, headers = request_body(), {}
    if source == "header":
        headers["X-Subagent-Id"] = role
    elif source == "body":
        request["subagent_id"] = role
    else:
        request["extra_body"] = {"subagent_id": role}
    with RecordingUpstream() as droid, RecordingUpstream() as reserve:
        success(droid, False)
        success(reserve, False)
        with gateway(monkeypatch, {"droid": droid, "reserve": reserve}) as (port, _):
            status, _ = post(port, request, headers)
        actual = (status, droid.post_count, droid.body_bytes, reserve.post_count)
    semantic_equal(actual, (200, 0, 0, 1), "canonical_judge_uses_eligible_alternate")


def test_dynamic_role_denials(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.route_eligibility import route_eligible

    for role in ("panel-review-1", "judge-1", "seat-1"):
        assert route_eligible({"backend": "reserve"}, {**_facts(), "backend_kind": "passthrough"},
                              {**request_body(), "subagent_id": role})
    assert route_eligible({"backend": "droid"}, _facts(), {**request_body(), "subagent_id": "coder-1"})
    monkeypatch.setenv("DROID_DENY_SUBAGENT_PREFIXES", "custom-audit-")
    for role in ("custom-audit-1", "panel-review-1"):
        for backend, kind in (("droid", "passthrough"), ("alias", "droid")):
            assert not route_eligible({"backend": backend}, {**_facts(), "backend_kind": kind},
                                      {**request_body(), "subagent_id": role})


@pytest.mark.parametrize("role", ["judge-trace-1", None, object()])
def test_handler_trace_role_policy(role: object) -> None:
    from core.passthrough_facade import _request_policy
    from core.route_eligibility import route_eligible

    handler = SimpleNamespace(headers={}, _trace=SimpleNamespace(subagent_id=role))
    route = SimpleNamespace(handler=handler, request=request_body(), model_id="m", alias_effort=None)
    policy = _request_policy(route)
    assert policy.role_ids == ((role,) if isinstance(role, str) else ())
    assert route_eligible({"backend": "droid"}, _facts(), policy) is (not isinstance(role, str))
