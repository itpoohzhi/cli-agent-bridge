from __future__ import annotations

# `GET /v1/models`: каталожные efforts отдаются только при BRIDGE_EFFORT_CATALOG_ENABLED (SK-R-B17).

import importlib
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from core.effort_policy import (  # noqa: E402
    ModelEffortCardFields,
    ModelEffortSpec,
    catalog_effort_specs,
    resolve_model_effort_fields,
)

route = importlib.import_module("test_passthrough_routing").route
LEGACY = ["low", "medium", "high"]
ALIASES = ("gpt-6.1-terra-low", "gpt-6.1-terra-max")
FLAG = "BRIDGE_EFFORT_CATALOG_ENABLED"


def _cards() -> dict[str, dict[str, Any]]:
    return {card["id"]: card for card in server._build_models_list()}


def _sent_request(handler: Any) -> dict[str, Any]:
    return dict(handler._serve_passthrough.call_args.args[2])


@pytest.fixture
def flag_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> pytest.MonkeyPatch:
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "absent.json"))
    monkeypatch.setattr(server, "ADVERTISED_EFFORT_ALIASES", ALIASES)
    monkeypatch.setattr(server, "_EFFORT_SPECS_CACHE", (None, {}))
    return monkeypatch


def test_models_list_keeps_legacy_efforts_when_flag_off(
    route: Any, flag_env: pytest.MonkeyPatch
) -> None:
    flag_env.delenv(FLAG, raising=False)
    cards = _cards()
    assert "muse-spark-1.3" in cards and set(ALIASES) <= set(cards)
    for card in cards.values():
        assert card["supported_reasoning_efforts"] == LEGACY
        assert card["default_reasoning_effort"] == "high"


def test_models_list_reports_catalog_efforts_when_flag_on(
    route: Any, flag_env: pytest.MonkeyPatch
) -> None:
    flag_env.setenv(FLAG, "1")
    cards = _cards()
    assert cards["muse-spark-1.3"]["supported_reasoning_efforts"] == ["max"]
    assert cards["gpt-6.1-terra-low"]["supported_reasoning_efforts"] == ["low"]
    assert cards["gpt-6.1-terra-max"]["default_reasoning_effort"] == "high"


def test_model_without_catalog_efforts_keeps_legacy_advertisement(
    flag_env: pytest.MonkeyPatch,
) -> None:
    flag_env.setenv(FLAG, "1")
    specs = catalog_effort_specs({"empty": {}}, {})
    card: dict[str, Any] = {
        "supported_reasoning_efforts": list(LEGACY),
        "default_reasoning_effort": "high",
    }
    server._advertise_efforts(card, "empty", specs)
    assert resolve_model_effort_fields("empty", specs) is None
    assert card["supported_reasoning_efforts"] == LEGACY
    assert card["default_reasoning_effort"] == "high"


def test_resolve_model_effort_fields_returns_typed_dto_or_none() -> None:
    specs = {"a": ModelEffortSpec(("off", "max"), "off"), "empty": ModelEffortSpec()}
    assert resolve_model_effort_fields("a", specs) == ModelEffortCardFields("off", ("off", "max"))
    assert resolve_model_effort_fields("empty", specs) is None
    assert resolve_model_effort_fields("absent", specs) is None
    assert resolve_model_effort_fields("a", {}) is None


def test_catalog_effort_specs_pins_alias_and_tolerates_junk() -> None:
    models = {"m": {"efforts": ["low", "high"], "default_effort": "high"}}
    specs = catalog_effort_specs(models, {"m-max": ("m", "max"), "x-low": ("x", "low")})
    assert specs["m"] == ModelEffortSpec(("low", "high"), "high")
    assert specs["m-max"] == ModelEffortSpec(("high",), "high")
    assert specs["x-low"] == ModelEffortSpec(("low",), "low")
    assert catalog_effort_specs(None, {}) == {}


def test_catalog_effort_specs_skips_alias_of_model_without_efforts() -> None:
    models = {"empty": {}}
    assert catalog_effort_specs(models, {"empty-low": ("empty", "low")}) == {}


def test_route_alias_call_clamps_explicit_effort_to_alias(
    route: Any, flag_env: pytest.MonkeyPatch
) -> None:
    flag_env.setenv(FLAG, "1")
    handler, _ = route({"model": "gpt-6.1-terra-low", "reasoning_effort": "high"})
    assert _sent_request(handler)["reasoning_effort"] == "low"
    flag_env.delenv(FLAG, raising=False)
    handler, _ = route({"model": "gpt-6.1-terra-low", "reasoning_effort": "high"})
    assert _sent_request(handler)["reasoning_effort"] == "high"


def test_effort_specs_are_cached_until_catalog_or_aliases_change(flag_env: pytest.MonkeyPatch) -> None:
    first = server._effort_specs()
    assert server._effort_specs() is first
    flag_env.setitem(server.FLEET, "sha256", "changed-catalog")
    second = server._effort_specs()
    assert second is not first and server._effort_specs() is second
    flag_env.setattr(server, "ADVERTISED_EFFORT_ALIASES", ())
    third = server._effort_specs()
    assert third is not second
    flag_env.setattr(server, "EFFORT_ALIAS_ENABLED", not server.EFFORT_ALIAS_ENABLED)
    fourth = server._effort_specs()
    assert fourth is not third
    flag_env.setattr(server, "EFFORT_SUFFIXES", ("low",))
    assert server._effort_specs() is not fourth


DROID_FLAG = "BRIDGE_DROID_CATALOG_ENABLED"
HAIKU = "claude-haiku-5-5"
# Эталон из каталога: droid ON даёт haiku [low, medium, high]/low, droid OFF — claude-p [high]/high.
HAIKU_BY_DROID = {True: (["low", "medium", "high"], "low"), False: (["high"], "high")}


def _haiku_card() -> tuple[list[str], str]:
    card = _cards()[HAIKU]
    return card["supported_reasoning_efforts"], card["default_reasoning_effort"]


@pytest.mark.parametrize("start_on", [True, False])
def test_models_list_efforts_follow_droid_flag_without_cache_reset(
    flag_env: pytest.MonkeyPatch, start_on: bool
) -> None:
    """F-001: kill-switch droid меняет модели при том же sha256 файла; кэш effort не залипает."""
    flag_env.setenv(FLAG, "1")
    states = [start_on, not start_on, start_on]
    for droid_on in states:
        flag_env.setenv(DROID_FLAG, "1" if droid_on else "0")
        assert _haiku_card() == HAIKU_BY_DROID[droid_on]
        assert server.FLEET["models"][HAIKU]["efforts"] == HAIKU_BY_DROID[droid_on][0]


def test_effort_specs_cache_resets_when_catalog_listener_fires(flag_env: pytest.MonkeyPatch) -> None:
    first = server._effort_specs()
    server._invalidate_effort_specs_cache({})
    assert server._EFFORT_SPECS_CACHE == (None, {})
    assert server._effort_specs() is not first


def test_route_does_not_build_effort_spec_when_flag_off(
    route: Any, flag_env: pytest.MonkeyPatch
) -> None:
    flag_env.delenv(FLAG, raising=False)
    flag_env.setattr(ModelEffortSpec, "from_catalog_entry", _fail_spec)
    handler, _ = route({"model": "gpt-6.1-terra-low", "reasoning_effort": "high"})
    assert _sent_request(handler)["reasoning_effort"] == "high"


def _fail_spec(entry: object) -> ModelEffortSpec:
    raise AssertionError("спека effort строится при выключенном флаге")


def test_server_keeps_unrelated_reexports() -> None:
    assert server.QoSSlotManager and server.QOS_DEFAULT_QUEUE_TIMEOUT_S > 0
    assert callable(server._is_watchdog_enabled)
