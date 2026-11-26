"""AD-006: уровень ниже floor модели не повышается молча (три точки вызова clamp)."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import http_post_dispatch as dispatch  # noqa: E402
from core.effort_errors import EffortBelowFloorError, EffortValidationError  # noqa: E402
from core.effort_policy import (  # noqa: E402
    ModelEffortSpec,
    catalog_effort_specs,
    clamp_effort_downward,
    describe_clamp,
    resolve_passthrough_effort,
)
from core.effortless_policy import EffortValidationError as ReExported  # noqa: E402
from core.http_post_routing import PreparedPostBody  # noqa: E402
from core.native_effort import native_effort  # noqa: E402
from core.passthrough_autonomy import PassthroughOptions, prepare_passthrough_request  # noqa: E402

FLOOR_HIGH = ModelEffortSpec(("high",), "high")
LH = {"efforts": ["low", "high"], "default_effort": "low", "backend": "nw"}


def _fleet() -> dict[str, Any]:
    return json.loads((ROOT / "fleet.json").read_text(encoding="utf-8"))


def test_exceptions_hierarchy_and_reexport() -> None:
    assert issubclass(EffortBelowFloorError, EffortValidationError)
    assert issubclass(EffortValidationError, ValueError)
    assert ReExported is EffortValidationError
    import server

    assert server.EffortValidationError is EffortValidationError


@pytest.mark.parametrize(
    "candidate,allowed,expected",
    [("medium", ["low", "high"], ("low", True)), ("xhigh", ["low", "high"], ("high", True)),
     ("bogus", ["low", "high"], ("dflt", True)), ("", ["low", "high"], ("dflt", True)),
     ("high", ["low", "high"], ("high", False))],
)
def test_clamp_downward_and_fallback_preserved(candidate: str, allowed: list[str], expected: tuple[str, bool]) -> None:
    assert clamp_effort_downward(candidate, allowed, "dflt") == expected


@pytest.mark.parametrize("candidate,allowed", [("low", ["high"]), ("off", ["low", "high"])])
def test_clamp_below_floor_raises(candidate: str, allowed: list[str]) -> None:
    with pytest.raises(EffortBelowFloorError):
        clamp_effort_downward(candidate, allowed, "high")


def test_point1_pinned_to_rejects_below_floor_alias_with_warning(caplog: pytest.LogCaptureFixture) -> None:
    with pytest.raises(EffortBelowFloorError):
        FLOOR_HIGH.pinned_to("low")
    models = {"m": {"efforts": ["high"], "default_effort": "high"}}
    aliases = {"m-low": ("m", "low"), "m-high": ("m", "high")}
    with caplog.at_level(logging.WARNING, logger="core.effort_policy"):
        specs = catalog_effort_specs(models, aliases)
    assert "m-low" not in specs  # fail-closed: алиас не регистрируется, не повышается до high
    assert specs["m-high"] == ModelEffortSpec(("high",), "high")
    assert any("m-low" in r.getMessage() and r.levelno == logging.WARNING for r in caplog.records)


def test_point2_resolution_raises_validation_error() -> None:
    with pytest.raises(EffortValidationError):
        resolve_passthrough_effort("off", None, ModelEffortSpec(("low", "high"), "low"), enabled=True)
    with pytest.raises(EffortBelowFloorError):
        resolve_passthrough_effort("low", None, FLOOR_HIGH, enabled=True)


def _passthrough_route(effort: str) -> tuple[Any, list[tuple[int, str, str]]]:
    rejected: list[tuple[int, str, str]] = []
    host = SimpleNamespace(
        passthrough_autonomy_validation_enabled=lambda default: False,
        flag_enabled=lambda name: False,
        FLAG_EFFORT_CATALOG="BRIDGE_EFFORT_CATALOG_ENABLED",
        EffortValidationError=EffortValidationError,
        PassthroughOptions=lambda **kw: PassthroughOptions(**{**kw, "effort_on": True}),
        prepare_passthrough_request=prepare_passthrough_request,
        describe_clamp=describe_clamp,
        _log=lambda message: None,
        _LOG_EFFORT_MAX=32,
    )
    route = SimpleNamespace(
        host=host, handler=SimpleNamespace(), raw_model="m", model_id="m", alias=None, alias_effort=None,
        request={"reasoning_effort": effort}, model=dict(LH),
        reject=lambda status, kind, message: rejected.append((status, kind, message)) or False,
    )
    return route, rejected


def test_point2_passthrough_returns_http_400() -> None:
    route, rejected = _passthrough_route("off")
    body = PreparedPostBody(raw=b"{}", request={"reasoning_effort": "off", "model": "m"})
    dispatch._passthrough(route, SimpleNamespace(), body)
    assert [(s, k) for s, k, _ in rejected] == [(400, "unsupported_reasoning_effort")]
    assert "below" in rejected[0][2]


def _native_route(effort: Any, model: dict[str, Any] | None = None) -> tuple[Any, list[tuple[int, str, str]]]:
    rejected: list[tuple[int, str, str]] = []
    host = SimpleNamespace(
        clamp_effort_downward=clamp_effort_downward, describe_clamp=describe_clamp, _log=lambda m: None, _LOG_EFFORT_MAX=32
    )
    route = SimpleNamespace(
        host=host, request={"reasoning_effort": effort}, alias_effort=None, model_id="m", model=model or dict(LH),
        reject=lambda status, kind, message: rejected.append((status, kind, message)) or False,
    )
    return route, rejected


def test_point3_native_effort_returns_http_400() -> None:
    route, rejected = _native_route("off")
    assert native_effort(route) is None
    assert [(s, k) for s, k, _ in rejected] == [(400, "unsupported_reasoning_effort")]


@pytest.mark.parametrize(
    "effort,expected", [("medium", ("low", "request")), ("high", ("high", "request")), (None, ("low", "default"))]
)
def test_point3_native_effort_valid_levels(effort: Any, expected: tuple[str, str]) -> None:
    route, rejected = _native_route(effort)
    assert native_effort(route) == expected
    assert rejected == []


def test_native_effort_is_reexported_by_routing_monolith() -> None:
    from core import http_post_routing

    assert http_post_routing.native_effort is native_effort


def test_fleet_aliases_all_register_without_floor_violation(caplog: pytest.LogCaptureFixture) -> None:
    fleet = _fleet()
    models = {m["id"]: m for m in fleet["models"]}
    aliases = {a: (v["backend_id"], v["effort"]) for a, v in fleet["aliases"].items()}
    with caplog.at_level(logging.WARNING, logger="core.effort_policy"):
        specs = catalog_effort_specs(models, aliases)
    pinned = {a for a, (base, _) in aliases.items() if models.get(base, {}).get("efforts")}
    assert len(aliases) == 67 and pinned <= specs.keys()
    assert not [r for r in caplog.records if "alias skipped" in r.getMessage()]
    assert {a: specs[a].efforts for a in pinned} == {a: (aliases[a][1],) for a in pinned}


def test_fleet_haiku_keeps_declared_efforts() -> None:
    haiku = next(m for m in _fleet()["models"] if m["id"] == "claude-haiku-5-5")
    assert (haiku["efforts"], haiku["default_effort"]) == (["low", "medium", "high"], "low")
