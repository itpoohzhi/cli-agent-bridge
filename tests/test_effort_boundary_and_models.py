from __future__ import annotations

# Effort на границе роутинга: шкала с `off`, кламп passthrough, честный `/v1/models`, инварианты гейта.

import copy
import importlib
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from core import backend_adapter  # noqa: E402
from core import effort_policy  # noqa: E402
from core import quarantine_gate as qg  # noqa: E402
from core.effort_policy import (  # noqa: E402
    DEFAULT_LOG_EFFORT_MAX_CHARS,
    ModelEffortSpec,
    clamp_effort_downward,
    describe_clamp,
    resolve_passthrough_effort,
    sanitize_effort_for_log,
)

testlib = importlib.import_module("bridge_testlib")
find_model, load_raw_fleet = testlib.find_model, testlib.load_raw_fleet
route = importlib.import_module("test_passthrough_routing").route  # фикстура do_POST без сети
LMH = ["low", "medium", "high"]
SPEC = ModelEffortSpec(tuple(LMH), "high")


# ---- effort: шкала, кламп, passthrough -------------------------------------------------


def test_effort_levels_start_with_off_and_keep_minimal() -> None:
    levels = backend_adapter.EFFORT_LEVELS
    assert levels[0] == "off" and "minimal" in levels and levels[-1] == "max"
    assert levels is effort_policy.EFFORT_LEVELS


def test_clamp_off_maps_to_lowest_allowed() -> None:
    assert server.clamp_effort_downward is clamp_effort_downward
    assert clamp_effort_downward("off", LMH, "high") == ("low", True)
    assert clamp_effort_downward("max", LMH, "high") == ("high", True)
    assert clamp_effort_downward("off", ["high"], "high") == ("high", True)


def test_passthrough_stays_transparent_without_effort() -> None:
    decision = resolve_passthrough_effort(None, None, SPEC, enabled=True)
    assert (decision.apply, decision.value) == (False, None)


@pytest.mark.parametrize(
    "requested,allowed,value",
    [
        ("off", LMH, "low"),
        ("max", LMH, "high"),
        ("max", ["high"], "high"),
        ("xhigh", LMH, "high"),
    ],
)
def test_passthrough_clamps_unsupported_effort(
    requested: str, allowed: list[str], value: str
) -> None:
    spec = ModelEffortSpec(tuple(allowed), "high")
    decision = resolve_passthrough_effort(requested, None, spec, enabled=True)
    assert (decision.value, decision.apply, decision.clamped_from) == (
        value,
        True,
        requested,
    )


def test_passthrough_keeps_supported_effort_and_applies_alias() -> None:
    assert not resolve_passthrough_effort("medium", None, SPEC, enabled=True).apply
    alias = resolve_passthrough_effort(None, "high", SPEC, enabled=True)
    assert (alias.value, alias.apply, alias.clamped_from) == ("high", True, None)
    assert resolve_passthrough_effort(None, "max", SPEC, enabled=True).value == "high"


def test_passthrough_normalizes_padded_supported_effort() -> None:
    padded = resolve_passthrough_effort(" high ", None, SPEC, enabled=True)
    assert (padded.value, padded.apply, padded.clamped_from) == ("high", True, None)


def test_passthrough_legacy_when_flag_off_or_no_catalog_efforts() -> None:
    assert not resolve_passthrough_effort("off", None, SPEC, enabled=False).apply
    legacy_alias = resolve_passthrough_effort(None, "high", SPEC, enabled=False)
    assert (legacy_alias.value, legacy_alias.apply) == ("high", True)
    no_efforts = ModelEffortSpec()
    assert not resolve_passthrough_effort("off", None, no_efforts, enabled=True).apply


def _sent_request(handler: Any) -> dict[str, Any]:
    return dict(handler._serve_passthrough.call_args.args[2])


def test_route_clamps_effort_only_with_flag(
    route: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "absent.json"))
    monkeypatch.delenv("BRIDGE_EFFORT_CATALOG_ENABLED", raising=False)
    handler, _ = route({"model": "gpt-6.1-terra", "reasoning_effort": "off"})
    assert (
        _sent_request(handler)["reasoning_effort"] == "off"
    )  # прежнее поведение: дословно
    monkeypatch.setenv("BRIDGE_EFFORT_CATALOG_ENABLED", "1")
    handler, _ = route({"model": "gpt-6.1-terra", "reasoning_effort": "off"})
    assert (
        _sent_request(handler)["reasoning_effort"] == "low"
    )  # efforts [low, medium, high]: минимум
    handler, _ = route({"model": "gpt-6.1-terra"})
    assert "reasoning_effort" not in _sent_request(
        handler
    )  # без effort — полностью прозрачно


@pytest.fixture
def raw_fleet(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Сырой каталог без влияния ENV_MODEL/IMAGE_PROBE окружения."""
    monkeypatch.setattr(server, "ENV_MODEL", "")
    monkeypatch.setattr(server, "IMAGE_PROBE", False)
    return copy.deepcopy(load_raw_fleet())


def _violation(data: dict[str, Any]) -> Any:
    with pytest.raises(server.FleetViolation) as caught:
        server._build_catalog(data)
    return caught.value


def test_catalog_accepts_off_effort_level(raw_fleet: dict[str, Any]) -> None:
    find_model(raw_fleet, "claude-sonnet-5-5")["efforts"] = ["off", "high"]
    model = server._build_catalog(raw_fleet)["models"]["claude-sonnet-5-5"]
    assert model["efforts"] == ["off", "high"]


class TestCatalogEfforts(unittest.TestCase):
    """Инварианты baseline каталога после ввода `off` (имена переехали из test_bridge_strict)."""

    data: dict[str, Any] = {}

    def setUp(self) -> None:
        for name, value in (("ENV_MODEL", ""), ("IMAGE_PROBE", False)):
            patcher = mock.patch.object(server, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.data = copy.deepcopy(load_raw_fleet())

    def _expect(self, reason: str, model: str) -> None:
        with self.assertRaises(server.FleetViolation) as caught:
            server._build_catalog(self.data)
        self.assertEqual(
            (caught.exception.reason, caught.exception.model), (reason, model)
        )

    def test_unknown_effort_level_is_invalid(self) -> None:
        find_model(self.data, "claude-sonnet-5-5")["efforts"] = ["bogus", "high"]
        self._expect("efforts_invalid", "claude-sonnet-5-5")

    def test_default_effort_outside_efforts(self) -> None:
        # efforts модели - [low, medium, high]; "xhigh" валидный уровень шкалы, но вне efforts.
        find_model(self.data, "claude-sonnet-5-5")["default_effort"] = "xhigh"
        self._expect("default_effort_invalid", "claude-sonnet-5-5")


# ---- /v1/models ------------------------------------------------------------------------


def test_effort_spec_mirrors_catalog_entry() -> None:
    entry = {"efforts": LMH, "default_effort": "low"}
    assert ModelEffortSpec.from_catalog_entry(entry) == ModelEffortSpec(
        tuple(LMH), "low"
    )
    empty = ModelEffortSpec()
    assert (
        ModelEffortSpec.from_catalog_entry({"efforts": [], "default_effort": None})
        == empty
    )
    assert ModelEffortSpec.from_catalog_entry(None) == empty
    assert ModelEffortSpec.from_catalog_entry(["efforts"]) == empty


def test_effort_spec_pinned_to_alias_effort_clamps_to_catalog() -> None:
    assert SPEC.pinned_to("low") == ModelEffortSpec(("low",), "low")
    assert SPEC.pinned_to("max") == ModelEffortSpec(("high",), "high")
    assert ModelEffortSpec().pinned_to("low") == ModelEffortSpec(("low",), "low")


def test_models_list_reports_catalog_efforts(
    route: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "absent.json"))
    monkeypatch.setenv("BRIDGE_EFFORT_CATALOG_ENABLED", "1")
    cards = {card["id"]: card for card in server._build_models_list()}
    checked = 0
    for mid, entry in server.FLEET["models"].items():
        if mid in cards:
            checked += 1
            assert cards[mid]["supported_reasoning_efforts"] == list(entry["efforts"])
            assert cards[mid]["default_reasoning_effort"] == entry["default_effort"]
    assert checked and cards["muse-spark-1.3"]["supported_reasoning_efforts"] == ["max"]


# ---- карантинный гейт: инварианты ------------------------------------------------------


def test_default_open_roles_are_unchanged() -> None:
    assert qg.DEFAULT_OPEN_ROLES == frozenset({"worker", "explorer", "probe"})
    assert "smoke" not in qg.DEFAULT_OPEN_ROLES
    assert qg.RoleClasses().class_of("smoke") == qg.CLASS_GATED


@pytest.mark.parametrize(
    "subagent_id,role",
    [
        ("probe-abc12345", "probe"),
        ("coder-abc-def", "coder"),
        ("Worker-1-2-3", "worker"),
        ("-weird", "adhoc"),
        (None, "adhoc"),
    ],
)
def test_role_from_subagent_id_handles_dashed_ids(subagent_id: Any, role: str) -> None:
    assert qg.role_from_subagent_id(subagent_id) == role
    assert (
        qg.role_from_subagent_id("", strict_anonymous=True) == qg.ROLE_ANONYMOUS_GATED
    )


def test_alias_card_pins_alias_effort(
    route: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "absent.json"))
    monkeypatch.setenv("BRIDGE_EFFORT_CATALOG_ENABLED", "1")
    aliases = ("gpt-6.1-terra-low", "gpt-6.1-terra-max")
    monkeypatch.setattr(server, "ADVERTISED_EFFORT_ALIASES", aliases)
    cards = {card["id"]: card for card in server._build_models_list()}
    low, over = cards["gpt-6.1-terra-low"], cards["gpt-6.1-terra-max"]
    assert (low["supported_reasoning_efforts"], low["default_reasoning_effort"]) == (
        ["low"],
        "low",
    )
    # `max` вне каталога [low, medium, high]: алиас реально применит `high`, карточка не обещает лишнего.
    assert (over["supported_reasoning_efforts"], over["default_reasoning_effort"]) == (
        ["high"],
        "high",
    )


# ---- журнал клампа: значение effort приходит от клиента ---------------------------------


def test_sanitize_effort_for_log_strips_controls_and_truncates() -> None:
    dirty = "hi\r\nx\ty\x00" + "a" * 100
    clean = sanitize_effort_for_log(dirty)
    assert clean == "hixy" + "a" * 28 and clean.isprintable()
    assert sanitize_effort_for_log(dirty, 3) == "hix"
    assert "\n" not in sanitize_effort_for_log(["a\nb"])


def test_describe_clamp_has_no_line_breaks() -> None:
    line = describe_clamp("reasoning_effort", "off\n2099 FORGED", "high\r", "m")
    assert line == "clamp reasoning_effort 'off2099 FORGED' -> 'high' for model m"


def test_route_clamp_log_cannot_be_forged(
    route: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "absent.json"))
    monkeypatch.setenv("BRIDGE_EFFORT_CATALOG_ENABLED", "1")
    forged = "bogus\r\n2099-01-01T00:00:00Z FORGED " + "x" * 500
    route({"model": "gpt-6.1-terra", "reasoning_effort": forged})
    lines = capsys.readouterr().err.splitlines()
    clamp_lines = [line for line in lines if "clamp passthrough" in line]
    assert len(clamp_lines) == 1 and len(clamp_lines[0]) < 200
    assert not any(line.startswith("2099-01-01") for line in lines)


def test_log_effort_max_chars_is_bounded_env_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """N-01: журнальный лимит effort — дефолт 32 (константа модуля) и 42 из env; нечисло/<=0 -> дефолт."""
    monkeypatch.delenv("BRIDGE_LOG_EFFORT_MAX_CHARS", raising=False)
    assert server._LOG_EFFORT_MAX == DEFAULT_LOG_EFFORT_MAX_CHARS == 32
    monkeypatch.setenv("BRIDGE_LOG_EFFORT_MAX_CHARS", "42")
    assert server._env_limit("BRIDGE_LOG_EFFORT_MAX_CHARS", 32) == 42
    for bad in ("abc", "-5", "0"):
        monkeypatch.setenv("BRIDGE_LOG_EFFORT_MAX_CHARS", bad)
        assert server._env_limit("BRIDGE_LOG_EFFORT_MAX_CHARS", 32) == 32
