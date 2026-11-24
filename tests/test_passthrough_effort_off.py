"""W2 / AD-002, REQ-002: сквозной passthrough логического effort `"off"` без ложного `"high"`."""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import core.passthrough_effort_map as pem
from core.passthrough_facade import _pin_effort
from core.route_eligibility import EligibilityFacts, request_snapshot, route_eligible
from core.routing_contract import ROUTING_ALGORITHM
from core.transport_routing import route_order


@dataclass(frozen=True)
class _Selected:
    request: dict
    model: dict


class _Adapter:
    def __init__(self, adapter_id):
        self.id = adapter_id
        self.config = {}


_NW = _Adapter("neuralwatt-1")
_GO = _Adapter("opencode-go-1")

_WIRE_NW = {"model": "glm", "reasoning_effort": "none"}
_WIRE_GO = {"model": "glm", "thinking": {"type": "disabled"}}


def test_is_thinking_disabled():
    assert pem.is_thinking_disabled({"thinking": {"type": "disabled"}})
    assert pem.is_thinking_disabled({"thinking": {"type": " Disabled "}})
    assert not pem.is_thinking_disabled({"thinking": {"type": "enabled"}})
    assert not pem.is_thinking_disabled({"thinking": "disabled"})
    assert not pem.is_thinking_disabled({})
    assert not pem.is_thinking_disabled(None)


def test_logical_effort_precedence():
    assert pem.logical_effort({"reasoning_effort": "high", "thinking": {"type": "disabled"}}, None, None) == "high"
    assert pem.logical_effort({"thinking": {"type": "disabled"}}, None, {"default_effort": "high"}) == "off"
    assert pem.logical_effort({}, "medium", None) == "medium"
    assert pem.logical_effort({}, None, {"default_effort": "low"}) == "low"
    assert pem.logical_effort({}, None, None) == ""


def test_pin_effort_does_not_inject_high_for_thinking_disabled():
    request = {"model": "m", "thinking": {"type": "disabled"}}
    route = SimpleNamespace(request=dict(request), alias_effort=None, model={"default_effort": "high"})
    assert _pin_effort(route) is route
    assert route.request == request
    assert "reasoning_effort" not in route.request


def test_pin_effort_keeps_explicit_off():
    request = {"model": "m", "reasoning_effort": "off"}
    route = SimpleNamespace(request=dict(request), alias_effort=None, model=None)
    assert _pin_effort(route) is route
    assert route.request == request
    assert route.request.get("reasoning_effort") != "high"


@pytest.mark.parametrize("dialect", ["reasoning_effort", "thinking"])
@pytest.mark.parametrize("backend,adapter,wire", [
    ("neuralwatt", _NW, _WIRE_NW),
    ("opencode-go", _GO, _WIRE_GO),
])
def test_apply_attempt_effort_map_wire_contract(dialect, backend, adapter, wire):
    request = (
        {"model": "glm", "thinking": {"type": "disabled"}}
        if dialect == "thinking"
        else {"model": "glm", "reasoning_effort": "off"}
    )
    frozen = dict(request)
    body = json.dumps(request).encode("utf-8")
    selected = _Selected(request=request, model={"backend": backend})
    patched, wire_body = pem.apply_attempt_effort_map(selected, adapter, body)
    assert selected.request == frozen  # вход не мутируется
    assert json.loads(wire_body) == wire
    assert patched.request == wire
    assert "high" not in wire_body.decode("utf-8")


def test_failover_neuralwatt_to_opencode_go():
    original = {"model": "glm", "reasoning_effort": "off"}
    route = _Selected(request=dict(original), model={"backend": "neuralwatt"})
    body = json.dumps(original).encode("utf-8")

    first, wire1 = pem.apply_attempt_effort_map(route, _NW, body)
    assert route.request == original  # исходный route.request/body не мутированы
    assert first is not route
    assert first.request == _WIRE_NW
    assert json.loads(wire1) == _WIRE_NW

    second, wire2 = pem.apply_attempt_effort_map(
        _Selected(request=route.request, model={"backend": "opencode-go"}), _GO, body
    )
    assert route.request == original
    assert second.request == _WIRE_GO
    assert json.loads(wire2) == _WIRE_GO
    assert b"high" not in wire1 and b"high" not in wire2


@pytest.mark.parametrize("model_id", ["glm-5.3-flash", "deepseek-v4.1-flash"])
def test_non_off_effort_passthrough(model_id):
    request = {"model": model_id, "reasoning_effort": "high"}
    selected = _Selected(request=request, model={"backend": "neuralwatt"})
    body = json.dumps(request).encode("utf-8")
    patched, wire_body = pem.apply_attempt_effort_map(selected, _NW, body)
    assert patched is selected
    assert wire_body is body
    assert pem.logical_effort(request, None, None) == "high"


def _spec(backend):
    return SimpleNamespace(
        backend=backend, params={}, credential_ref=None, upstream_model=None,
        default_effort=None, context_window=None, max_tokens=None,
        efforts=(), input=["text"], weight=1, priority=1,
    )


def _facts():
    return EligibilityFacts(
        ready=True, circuit_open=False, blocked_models=(), probe_age_s=0.0,
        max_stale_age_s=0.0, env_drift_keys=(), supports_images=True,
        backend_kind="neuralwatt",
    )


_ORDER_MODEL = {
    "backend": "neuralwatt",
    "efforts": ["off", "low", "high"],
    "routing": {
        "enabled": True,
        "algorithm": ROUTING_ALGORITHM,
        "catalog_hash": "test-catalog-hash-01",
        "routes": [
            {"backend": "neuralwatt", "weight": 2, "priority": 1},
            {"backend": "opencode-go", "weight": 1, "priority": 2},
        ],
    },
}


def test_request_snapshot_consistent_across_off_dialects():
    off = request_snapshot({"model": "m", "reasoning_effort": "off"})
    thinking = request_snapshot({"model": "m", "thinking": {"type": "disabled"}})
    assert off.role_ids == thinking.role_ids
    assert off.excluded == thinking.excluded


def test_route_eligible_empty_efforts_is_dialect_agnostic():
    spec = {
        "backend": "neuralwatt",
        "enabled": True,
        "efforts": (),
        "input": ["text"],
        "weight": 1,
        "priority": 1,
    }  # route.efforts == () → fail-open в capability-проверке
    facts = _facts()
    policies = [
        request_snapshot({"model": "m", "reasoning_effort": "off"}),
        request_snapshot({"model": "m", "thinking": {"type": "disabled"}}),
    ]
    verdicts = [route_eligible(spec, facts, policy) for policy in policies]
    baseline = route_eligible(spec, facts, request_snapshot({"model": "m"}))
    assert verdicts == [baseline, baseline]
    assert baseline


def test_route_order_independent_of_effort_and_thinking():
    specs = (
        {"route_id": "neuralwatt", "backend": "neuralwatt", "weight": 2, "priority": 1, "efforts": ()},
        {"route_id": "opencode-go", "backend": "opencode-go", "weight": 1, "priority": 2, "efforts": ()},
    )
    base = tuple(route_order("m", _ORDER_MODEL, "seed-1", None, specs))
    assert sorted(base) == ["neuralwatt", "opencode-go"]
    assert tuple(route_order("m", _ORDER_MODEL, "seed-1", None, specs)) == base
    for model in (
        {**_ORDER_MODEL, "reasoning_effort": "off"},
        {**_ORDER_MODEL, "thinking": {"type": "disabled"}},
        {**_ORDER_MODEL, "efforts": ["high"]},
    ):
        assert tuple(route_order("m", model, "seed-1", None, specs)) == base
    specs_with_efforts = (
        {**specs[0], "efforts": ("off",)},
        {**specs[1], "efforts": ("high",)},
    )
    assert tuple(route_order("m", _ORDER_MODEL, "seed-1", None, specs_with_efforts)) == base
