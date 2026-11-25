"""Unit tests for core/route_cb_config.py (PR B4a)."""
from __future__ import annotations

from types import SimpleNamespace

from core.route_cb_config import (
    FailureOutcome,
    RouteCBConfig,
    RouteProbeLease,
    _ProviderState,
    _TupleState,
    _parse_float,
    _parse_int,
    is_route_cb_enabled,
    load_route_cb_config,
    resolve_provider,
)


def test_b4a_enabled_and_parsers() -> None:
    for falsy in ("0", "false", "OFF", "no"):
        assert is_route_cb_enabled({"BRIDGE_ROUTE_CB_ENABLED": falsy}) is False
    assert (is_route_cb_enabled({"BRIDGE_ROUTE_CB_ENABLED": " "}), is_route_cb_enabled({})) == (True, True)
    assert (_parse_int({"k": "5"}, "k", 3, 1), _parse_int({"k": "0"}, "k", 3, 1), _parse_int({"k": "bad"}, "k", 3, 1), _parse_int({}, "k", 3, 1)) == (5, 3, 3, 3)
    assert (_parse_float({"k": "65.5"}, "k", 90.0, (60.0, 120.0)), _parse_float({"k": "59"}, "k", 90.0, (60.0, 120.0)), _parse_float({"k": "121"}, "k", 90.0, (60.0, 120.0)), _parse_float({"k": "nan"}, "k", 90.0, (0.0, None)), _parse_float({}, "k", 90.0, (0.0, None))) == (65.5, 90.0, 90.0, 90.0, 90.0)


def test_b4a_load_config_bounds_and_provider() -> None:
    dflt = load_route_cb_config({})
    c60 = load_route_cb_config({"BRIDGE_ROUTE_CB_COOLDOWN_S": "60"})
    c120 = load_route_cb_config({"BRIDGE_ROUTE_CB_COOLDOWN_S": "120", "BRIDGE_ROUTE_CB_FAILURE_THRESHOLD": "5", "BRIDGE_ROUTE_CB_WINDOW_S": "150"})
    bad = load_route_cb_config({"BRIDGE_ROUTE_CB_FAILURE_THRESHOLD": "0", "BRIDGE_ROUTE_CB_COOLDOWN_S": "59", "BRIDGE_ROUTE_CB_WINDOW_S": "0", "BRIDGE_TRANSPORT_CIRCUIT_COOLDOWN_S": "15"})
    leg = load_route_cb_config({"BRIDGE_ROUTE_CB_ENABLED": "0", "BRIDGE_TRANSPORT_CIRCUIT_COOLDOWN_S": "15"})
    assert (dflt, c60.cooldown_s, c120.cooldown_s, c120.failure_threshold, c120.window_s) == (RouteCBConfig(), 60.0, 120.0, 5, 150.0)
    assert (bad.failure_threshold, bad.cooldown_s, bad.window_s, leg.enabled, leg.cooldown_s) == (3, 90.0, 300.0, False, 15.0)
    rt_host = SimpleNamespace(BACKENDS={"b1": SimpleNamespace(config={"provider": "cfg-p"}), "b2": SimpleNamespace(config={"provider": "", "provider_id": "id-p"}), "b3": SimpleNamespace(config={"provider": 123, "provider_id": ""})})
    assert (
        resolve_provider(SimpleNamespace(host=rt_host), SimpleNamespace(provider="spec-p", backend="b1")),
        resolve_provider(SimpleNamespace(host=rt_host), SimpleNamespace(provider="", backend="b1")),
        resolve_provider(SimpleNamespace(host=rt_host), SimpleNamespace(provider=123, backend="b2")),
        resolve_provider(SimpleNamespace(host=rt_host), SimpleNamespace(backend="b3")),
        resolve_provider(SimpleNamespace(host=None), SimpleNamespace(backend="")),
    ) == ("spec-p", "cfg-p", "id-p", "b3", "unknown")
    lease, tup, prov = RouteProbeLease(("p", "m", "b")), _TupleState(), _ProviderState()
    assert (FailureOutcome().reason, FailureOutcome().status, RouteCBConfig().enabled, lease.done, lease.provider_lease, lease.tuple_lease) == ("", None, True, False, False, False)
    assert (tup.failures, tup.probe_in_flight, prov.probe_in_flight) == (0, False, False)
