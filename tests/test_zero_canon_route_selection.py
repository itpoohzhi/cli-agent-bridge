"""W2 / VER-001, VER-002, AD-001: лаконичные unit-тесты выбора Zero-Canon маршрута."""

import copy
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import core.http_post_routing as hpr
import core.zero_canon_routing as zcr
from core.http_post_routing import resolve_post_route


class _Adapter:
    def __init__(self, adapter_id=None, name=None, kind=None, config=None):
        self.id, self.name, self.kind = adapter_id, name, kind
        self.config = dict(config or {})


class _GatedRegistry:
    """Callable-реестр: `adapters()` возвращает живой список адаптеров."""

    def __init__(self, adapters):
        self._adapters = list(adapters)

    def adapters(self):
        return list(self._adapters)


def test_backend_configs_callable_registry_authoritative_kind():
    adapters = [
        _Adapter(adapter_id="nw-1", kind="neuralwatt", config={"kind": "spoofed", "base_url": "https://nw"}),
        _Adapter(adapter_id="go-1", kind="opencode-go"),
    ]
    configs = hpr._backend_configs(SimpleNamespace(BACKENDS=_GatedRegistry(adapters)))
    assert set(configs) == {"nw-1", "go-1"}
    assert configs["nw-1"]["kind"] == "neuralwatt"  # авторитетный kind адаптера перезаписывает spoofed config["kind"]
    assert configs["nw-1"]["base_url"] == "https://nw"
    assert configs["go-1"]["kind"] == "opencode-go"


def test_backend_configs_name_fallback_and_config_kind():
    named = _Adapter(name="named", config={"kind": "cfg-kind"})
    configs = hpr._backend_configs(SimpleNamespace(BACKENDS=_GatedRegistry([named])))
    assert configs == {"named": {"kind": "cfg-kind"}}


def test_backend_configs_legacy_mapping():
    legacy = _Adapter(adapter_id="ignored", kind="droid", config={"kind": "wrong"})
    configs = hpr._backend_configs(SimpleNamespace(BACKENDS=SimpleNamespace(adapters={"legacy": legacy})))
    assert configs == {"legacy": {"kind": "droid"}}


def test_select_route_positive_weight_then_min_priority():
    kept = [
        {"backend": "zeroed-best", "priority": 0, "weight": 0},
        {"backend": "go", "priority": 5, "weight": 1},
    ]
    assert zcr.select_zero_canon_route(kept) == "go"


def test_select_route_min_priority_and_fleet_order_tie_break():
    kept = [{"backend": "a", "priority": 3, "weight": 1}, {"backend": "b", "priority": 1, "weight": 2}]
    assert zcr.select_zero_canon_route(kept) == "b"
    tie = [{"backend": "first", "priority": 2, "weight": 1}, {"backend": "second", "priority": 2, "weight": 9}]
    assert zcr.select_zero_canon_route(tie) == "first"


def test_select_route_all_zero_weight_fallback():
    kept = [{"backend": "a", "priority": 2, "weight": 0}, {"backend": "b", "priority": 1, "weight": 0}]
    assert zcr.select_zero_canon_route(kept) == "b"


def test_select_route_non_numeric_priority_is_inf():
    kept = [{"backend": "a", "priority": "high", "weight": 1}, {"backend": "b", "priority": 7, "weight": 1}]
    assert zcr.select_zero_canon_route(kept) == "b"


def test_select_route_disabled_backend_only_without_routing():
    kept = [{"backend": "a", "priority": 1, "weight": 1}, {"backend": "disabled", "priority": 9, "weight": 1}]
    assert zcr.select_zero_canon_route(kept, disabled_backend="disabled", routing_enabled=False) == "disabled"
    assert zcr.select_zero_canon_route(kept, disabled_backend="disabled", routing_enabled=True) == "a"
    assert zcr.select_zero_canon_route(kept, disabled_backend="absent", routing_enabled=False) == "a"


def test_select_route_no_candidates():
    assert zcr.select_zero_canon_route([]) is None
    assert zcr.select_zero_canon_route([{"backend": ""}, {"priority": 1}]) is None


class _FlagHost:
    def __init__(self, fleet, routing_enabled):
        self.FLEET = fleet
        self._routing_enabled = routing_enabled

    def flag_enabled(self, name):
        assert name == "BRIDGE_TRANSPORT_ROUTING_ENABLED"
        return self._routing_enabled


def test_fleet_routing_not_mutated_across_requests():
    fleet = {"models": {"m": {
        "backend": "a",
        "routing": {
            "enabled": True,
            "routes": [
                {"backend": "a", "priority": 1, "weight": 1},
                {"backend": "b", "priority": 2, "weight": 1},
            ],
            "disabled_backend": "a",
        },
    }}}
    snapshot = copy.deepcopy(fleet)

    # Запрос 1 (Zero-Canon): провайдер "a" отфильтрован, routing включён.
    host_on = _FlagHost(fleet, routing_enabled=True)
    zero = SimpleNamespace(model=dict(fleet["models"]["m"]), host=host_on)
    hpr._apply_filtered_routes(zero, fleet["models"]["m"]["routing"], [{"backend": "b", "priority": 2, "weight": 1}])
    assert fleet == snapshot
    assert zero.model["backend"] == "b"
    assert zero.model["routing"]["routes"] == [{"backend": "b", "priority": 2, "weight": 1}]
    assert zero.model["routing"]["zero_canon_backend"] == "b"
    assert zero.model["routing"] is not fleet["models"]["m"]["routing"]
    assert fleet["models"]["m"]["routing"]["routes"][0]["backend"] == "a"

    # Запрос 2 (обычный): полный kept, routing выключен → disabled_backend.
    host_off = _FlagHost(fleet, routing_enabled=False)
    normal = SimpleNamespace(model=dict(fleet["models"]["m"]), host=host_off)
    hpr._apply_filtered_routes(normal, fleet["models"]["m"]["routing"], fleet["models"]["m"]["routing"]["routes"])
    assert fleet == snapshot
    assert normal.model["backend"] == "a"
    assert normal.model["routing"]["zero_canon_backend"] == "a"


class _NotesFilter:
    def is_blocked(self, model_id):
        return False


class _PenaltyTracker:
    def get_model_status(self, model_id):
        return {"is_penalized": False, "remaining_cooldown": 0.0, "penalized_until": 0}


class _RecordingHandler:
    def __init__(self):
        self.headers = {}
        self.rejections = []

    def _reject(self, status, kind, message, model_id, model_len):
        self.rejections.append((status, kind, message))

    def _send(self, status, body, extra_headers=None):
        self.rejections.append((status, None, None))

    def _telemetry_meta(self, **meta):
        pass


class _RouteHost:
    _LOG_EFFORT_MAX = "high"

    def __init__(self, models):
        self.FLEET = {"models": models}
        self.INTERNAL_MODEL_IDS = set()
        self._MODEL_NOTES_FILTER = _NotesFilter()
        self._PENALTY_TRACKER = _PenaltyTracker()
        self.clamp_calls = []
        self.logs = []

    def _auth_ok(self, handler):
        return True

    def flag_enabled(self, name):
        return False

    def _resolve_model_alias(self, model_id, models):
        return None

    def _log(self, message):
        self.logs.append(message)

    def describe_clamp(self, field, value, effort, model_id, log_max):
        return f"clamp {field} {value}->{effort} model={model_id}"

    def clamp_effort_downward(self, effort, efforts, default):
        self.clamp_calls.append((effort, list(efforts), default))
        return (effort, False) if effort in efforts else (default, True)


class _PostContext:
    def __init__(self, request, host, handler):
        self.request = request
        self.host = host
        self.handler = handler
        self.provider_id = None


@pytest.mark.parametrize("effort", ["low", "off"])
def test_model_initialized_before_request_allowed_no_false_clamp(effort):
    efforts = ["off", "low", "high"]
    host = _RouteHost({"m": {"backend": "nw", "efforts": efforts, "default_effort": "low"}})
    handler = _RecordingHandler()
    route = resolve_post_route(_PostContext({"model": "m", "reasoning_effort": effort}, host, handler))
    assert route is not None
    assert handler.rejections == []
    assert host.clamp_calls == [(effort, efforts, "low")]
    assert host.logs == []


def test_clamp_still_detected_when_effort_undeclared():
    host = _RouteHost({"m": {"backend": "nw", "efforts": ["medium", "high"], "default_effort": "high"}})
    handler = _RecordingHandler()
    route = resolve_post_route(_PostContext({"model": "m", "reasoning_effort": "low"}, host, handler))
    assert route is not None
    assert host.clamp_calls == [("low", ["medium", "high"], "high")]
    assert host.logs and "clamp" in host.logs[0]
