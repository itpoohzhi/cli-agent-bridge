"""Совместимость и независимые stage-швы, без требования позднего wiring.

W2-K: clean_transport_request(raw, req) -> (raw, req), без изменения входа.
W2-L: prepare_route_request(req, selected_model, canonical_id) -> dict.
При отсутствии extraction проверяется реальный прежний helper, не ImportError.
"""

from __future__ import annotations

import copy
import hashlib
import importlib
import importlib.util
import json
import secrets
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

import server
from adapters import passthrough_adapter
from core.backend_adapter import FleetViolation, PreSendTransientError, _normalize_model
from core.route_health_policy import (
    FailureCategory,
    advance_sliding_deadline,
    classify_provider_failure,
    normalize_model_route,
)
from tests.test_request_attribution import wire as wire
from tests.transport_test_support import semantic_equal


@pytest.fixture(autouse=True)
def notes_file(tmp_path: Path) -> None:
    (tmp_path / "notes.md").write_text(
        "## 1. Блокировки\n| Модель | Статус | Причина |\n|---|---|---|\n",
        encoding="utf-8",
    )


def _model() -> dict[str, Any]:
    return {
        "id": "public-model", "backend": "direct", "name": "Public",
        "efforts": ["low", "high"], "default_effort": "high",
        "context_window": 4096, "input": ["text"],
        "images": {"status": "unsupported", "cli_registry": "explicit_unsupported",
                   "method": None, "proof": None},
    }


def _routing(owner: str = "direct", native: str = "native") -> dict[str, Any]:
    routes = [
        {"route_id": owner, "backend": owner, "weight": 100, "priority": 20},
        {"route_id": native, "backend": native, "weight": 0, "priority": 10},
    ]
    active = [{"route_id": owner, "backend": owner, "weight": 100}]
    digest = hashlib.sha256(json.dumps(
        active, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode()).hexdigest()
    return {
        "algorithm": "weighted-sha256-v1", "enabled": True, "catalog_hash": digest,
        "legacy_backend": owner, "disabled_backend": native, "routes": routes,
    }


def _stage_function(module: str, symbol: str, legacy: Callable[..., Any]) -> Callable[..., Any]:
    if importlib.util.find_spec(module) is None:
        return legacy
    return getattr(importlib.import_module(module), symbol)


@pytest.mark.semantic_red("normalized_model_loses_route_contract")
def test_stage_w2_h_normalization_preserves_disabled_owner_and_routes() -> None:
    item = _model()
    item["routing"] = _routing()
    original = copy.deepcopy(item)
    backends = {"direct": {"enabled": True}, "native": {"enabled": True}}
    try:
        normalized = _normalize_model(item, "public-model", 3, backends, False)
        actual = normalized["routing"] if normalized is not None else None
    except FleetViolation as error:
        actual = str(error)
    assert item == original
    semantic_equal(actual, original["routing"], "normalized_model_loses_route_contract")


def test_legacy_normalization_and_alias_effort_contract() -> None:
    item = _model()
    normalized = _normalize_model(item, item["id"], 3, {"direct": {"enabled": True}}, False)
    assert normalized is not None
    assert normalized["backend"] == "direct"
    assert normalized["efforts"] == ["low", "high"]
    route = normalize_model_route("public-model-high", "low", known_models={"public-model"})
    assert (route.canonical_model, route.reasoning_effort, route.alias_applied) == (
        "public-model", "low", True,
    )
    exact = normalize_model_route("public-model-high", known_models={"public-model-high"})
    assert (exact.canonical_model, exact.alias_applied) == ("public-model-high", False)


@pytest.mark.semantic_red("ingress_transport_seed_not_consumed")
@pytest.mark.parametrize("stream", [False, True])
def test_stage_w2_k_ingress_cleans_controls_even_when_feature_off(
    monkeypatch: pytest.MonkeyPatch, stream: bool,
) -> None:
    monkeypatch.setenv("BRIDGE_TRANSPORT_ROUTING_ENABLED", "false")
    request = {"model": "public-model", "stream": stream, "transport_seed": "synthetic-seed"}
    original = copy.deepcopy(request)
    raw = json.dumps(request).encode()
    clean = _stage_function(
        "core.http_post_ingress", "clean_transport_request", server._strip_passthrough_env,
    )
    clean_raw, clean_request = clean(raw, request)
    assert request == original
    expected = {"model": "public-model", "stream": stream}
    semantic_equal(
        (json.loads(clean_raw), clean_request), (expected, expected),
        "ingress_transport_seed_not_consumed",
    )


def _legacy_route_request(
    request: dict[str, Any], selected_model: dict[str, Any], canonical_id: str,
) -> dict[str, Any]:
    prepared, _ = server.prepare_passthrough_request(
        request, selected_model, canonical_id, None, "", True,
    )
    return prepared


@pytest.mark.semantic_red("selected_route_model_params_not_applied")
def test_stage_w2_l_selected_route_overlay_replaces_owner_defaults() -> None:
    route = {
        **_model(), "upstream_model": "provider-specific-id",
        "efforts": ["low"], "default_effort": "low", "params": {"temperature": 0.25},
    }
    request = {"model": "public-model", "messages": [], "reasoning_effort": "high"}
    original = copy.deepcopy(request)
    prepare = _stage_function(
        "core.http_post_routing", "prepare_route_request", _legacy_route_request,
    )
    actual = prepare(request, route, "public-model")
    assert request == original
    expected = {
        "model": "provider-specific-id", "messages": [],
        "reasoning_effort": "low", "temperature": 0.25,
    }
    semantic_equal(actual, expected, "selected_route_model_params_not_applied")


@pytest.mark.semantic_red("http_facade_leaks_transport_seed")
@pytest.mark.parametrize("stream", [False, True])
def test_stage_w2_m_real_http_alias_preserves_tools_and_strips_seed(wire: Any, stream: bool) -> None:
    tools = [{"type": "function", "function": {
        "name": "lookup", "parameters": {"type": "object", "properties": {}},
    }}]
    status, _, response = wire.call({
        "model": "gpt-6.1-terra-high", "reasoning_effort": "low", "stream": stream,
        "messages": [{"role": "user", "content": "hi"}], "tools": tools,
        "transport_seed": "body-seed",
    }, {"X-Transport-Seed": "header-seed", "X-Request-Id": "compat-request"})
    assert status == 200
    assert response
    assert len(wire.records) == 1
    headers, raw = wire.records[0]
    sent = json.loads(raw)
    semantic_equal(
        (sent["model"], sent["reasoning_effort"], sent["tools"],
         "transport_seed" in sent, any(name.lower() == "x-transport-seed" for name in headers)),
        ("gpt-6.1-terra", "low", tools, False, False),
        "http_facade_leaks_transport_seed",
    )


@pytest.mark.semantic_red("default_off_ignores_preserved_native_backend")
@pytest.mark.parametrize("flag", [None, "false"])
def test_default_off_uses_disabled_owner_without_rng(
    wire: Any, monkeypatch: pytest.MonkeyPatch, flag: str | None,
) -> None:
    if flag is None:
        monkeypatch.delenv("BRIDGE_TRANSPORT_ROUTING_ENABLED", raising=False)
    else:
        monkeypatch.setenv("BRIDGE_TRANSPORT_ROUTING_ENABLED", flag)
    model = copy.deepcopy(server.FLEET["models"]["gpt-6.1-terra"])
    model.update(backend="agy", routing=_routing("agy", "codex"))
    monkeypatch.setitem(server.FLEET["models"], "gpt-6.1-terra", model)
    native = server.BACKENDS.get("codex")
    direct = server.BACKENDS.get("agy")
    native_handle, direct_handle = Mock(wraps=native.handle), Mock(wraps=direct.handle)
    monkeypatch.setattr(native, "handle", native_handle)
    monkeypatch.setattr(direct, "handle", direct_handle)
    rng = Mock(side_effect=AssertionError("feature-off must not draw entropy"))
    monkeypatch.setattr(secrets, "token_bytes", rng)
    status, _, _ = wire.call({"model": "gpt-6.1-terra"})
    assert status == 200
    rng.assert_not_called()
    semantic_equal(
        (native_handle.call_count, direct_handle.call_count), (1, 0),
        "default_off_ignores_preserved_native_backend",
    )


def test_existing_auth_rejection_never_sends_upstream(wire: Any) -> None:
    status, _, _ = wire.call(
        {"model": "gpt-6.1-terra"}, {"Authorization": "Bearer wrong-test-key"},
    )
    assert status == 401
    assert wire.records == []


def test_pr17_capacity_taxonomy_and_sliding_deadline_stay_compatible() -> None:
    for status in (429, 502, 503, 504):
        assert classify_provider_failure(status, "capacity").category == FailureCategory.CAPACITY_EXHAUSTED
    assert advance_sliding_deadline(12.0, 0.0, 5.0, 100.0) == 17.0
    assert advance_sliding_deadline(14.0, 0.0, 5.0, 100.0) == 19.0


def test_pr15_error_identity_and_keyword_call_shape() -> None:
    assert passthrough_adapter.PreSendTransientError is PreSendTransientError
    error = PreSendTransientError(
        "synthetic refusal", status_code=503,
        response_headers=(("Retry-After", "1"),), response_body=b'{"error":"busy"}',
    )
    assert isinstance(error, ConnectionError)
    assert (error.status_code, error.response_headers, error.response_body) == (
        503, (("Retry-After", "1"),), b'{"error":"busy"}',
    )


def test_hydrogen_xhigh_alias_keeps_native_family_and_effort(wire: Any) -> None:
    model = server.FLEET["models"]["gemini-4-hydrogen"]
    assert model["efforts"] == ["low", "medium", "high", "xhigh"]
    assert model["backend"] == "agy"
    status, _, _ = wire.call({"model": "gemini-4-hydrogen-xhigh"})
    assert status == 200
    assert len(wire.records) == 1
    sent = json.loads(wire.records[0][1])
    assert (sent["model"], sent["reasoning_effort"]) == ("gemini-4-hydrogen", "xhigh")


@pytest.mark.parametrize("source", ["header", "body", "extra_body"])
def test_explicit_droid_judge_denial_survives_late_host_catalog_patch(
    wire: Any, monkeypatch: pytest.MonkeyPatch, source: str,
) -> None:
    monkeypatch.setenv("DROID_DENY_SUBAGENT_PREFIXES", "panel-judge-,judge-,seat-")
    model_id = "gpt-6.1-terra-droid"
    model = {**server.FLEET["models"]["gpt-6.1-terra"], "id": model_id, "backend": "droid"}
    monkeypatch.setitem(server.FLEET["models"], model_id, model)
    request, headers = {"model": model_id}, {}
    if source == "header":
        headers["X-Subagent-Id"] = "panel-judge-1"
    elif source == "body":
        request["subagent_id"] = "panel-judge-1"
    else:
        request["extra_body"] = {"subagent_id": "panel-judge-1"}
    status, _, raw = wire.call(request, headers)
    assert status == 403
    assert json.loads(raw)["error"]["type"] == "droid_forbidden_for_role"
    assert wire.records == []
