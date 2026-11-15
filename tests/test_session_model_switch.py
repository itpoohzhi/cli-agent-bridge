"""Смена модели в сессии: `gemini-4-carbon` без оси effort (`efforts == ["off"]`), кламп и отказы CLI.

L1: чистая политика (`core.effortless_policy`, `core.cli_rejection`, passthrough-подготовка).
L2 (хаб `:9882` и настоящий `agy-bridge`) — в `tests/test_session_model_switch_bridge.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from core.cli_rejection import ENV_DETERMINISTIC_RE, is_deterministic_cli_rejection  # noqa: E402
from core.effort_policy import EffortResolution, ModelEffortCardFields, ModelEffortSpec  # noqa: E402
from core.effortless_policy import (  # noqa: E402
    EffortDecision,
    card_effort_fields,
    effort_cli_args,
    effortless_specs,
    is_effortless,
    resolve_request_effort,
    strip_effortless_effort,
)
from core.passthrough_autonomy import prepare_passthrough_request  # noqa: E402

CARBON, ARGON = "gemini-4-carbon", "gemini-4-argon"
CLAMP_FLAG = "BRIDGE_EFFORTLESS_CLAMP_ENABLED"
LEVELS = ("off", "minimal", "low", "medium", "high", "xhigh", "max")
OFF_MODEL = {"efforts": ["off"], "default_effort": "off"}
LADDER_MODEL = {"efforts": ["low", "medium", "high"], "default_effort": "high"}
REJECT = 'invalid model selection (--model "gemini-4-carbon" --effort "high"): --effort is not supported for model "gemini-4-carbon"'


# ---- L1: политика effort и классификатор отказов CLI ------------------------------


def test_is_effortless_only_for_off_ladder() -> None:
    assert is_effortless(["off"]) and is_effortless(["OFF"])
    assert not any(map(is_effortless, (["low", "high"], [], None, ["off", "low"], "off")))


def test_specs_card_fields_and_cli_args() -> None:
    specs = {"a": ModelEffortSpec(("off",), "off"), "b": ModelEffortSpec(("low", "high"), "high")}
    assert set(effortless_specs(specs)) == {"a"}
    off_card = card_effort_fields(ModelEffortCardFields("off", ("off",)))
    assert off_card == {"supports_thinking": False, "supported_reasoning_efforts": ["off"], "default_reasoning_effort": "off"}
    assert card_effort_fields(ModelEffortCardFields("high", ("low", "high")))["supports_thinking"] is True
    assert effort_cli_args("off") == effort_cli_args(None) == effort_cli_args("") == []
    assert effort_cli_args("high") == ["--effort", "high"]


@pytest.mark.parametrize("effort_on", [False, True])
def test_passthrough_strips_reasoning_effort_for_effortless_model(effort_on: bool) -> None:
    req = {"model": CARBON, "reasoning_effort": "high", "messages": []}
    clean, resolution = prepare_passthrough_request(req, OFF_MODEL, CARBON, effort_on=effort_on)
    assert "reasoning_effort" not in clean and clean["messages"] == []
    assert (resolution.value, resolution.apply) == ("off", True)
    assert resolution.clamped_from == "high"
    assert req["reasoning_effort"] == "high"  # исходный запрос не мутируется
    clean_off, res_off = prepare_passthrough_request(
        {"model": CARBON, "reasoning_effort": "off"}, OFF_MODEL, CARBON, effort_on=effort_on
    )
    assert "reasoning_effort" not in clean_off
    assert res_off.value == "off" and res_off.clamped_from is None


def test_passthrough_keeps_request_of_ordinary_model() -> None:
    req = {"model": ARGON, "reasoning_effort": "high"}
    clean, resolution = prepare_passthrough_request(req, LADDER_MODEL, ARGON, effort_on=False)
    assert clean == req and resolution == EffortResolution()
    spec = ModelEffortSpec(("low", "medium", "high"), "high")
    assert strip_effortless_effort(req, spec, resolution) == (req, resolution)


@pytest.mark.parametrize("raw", ["high", "xhigh"])
def test_resolve_request_effort_clamps_known_level_to_off(raw: str) -> None:
    decision = resolve_request_effort(raw, OFF_MODEL, LEVELS, clamp_enabled=True)
    assert decision == EffortDecision("off", "clamped", None)
    assert resolve_request_effort(raw, OFF_MODEL, LEVELS) == EffortDecision("off", "clamped", None)
    assert resolve_request_effort(None, OFF_MODEL, LEVELS).effort == "off"
    assert resolve_request_effort("   ", OFF_MODEL, LEVELS) == EffortDecision("off", "default", None)
    assert resolve_request_effort("off", OFF_MODEL, LEVELS) == EffortDecision("off", "request", None)


def test_resolve_request_effort_rejects_when_clamp_disabled_or_junk(monkeypatch: pytest.MonkeyPatch) -> None:
    assert resolve_request_effort("high", OFF_MODEL, LEVELS, clamp_enabled=False).error
    monkeypatch.setenv(CLAMP_FLAG, "false")
    assert resolve_request_effort("high", OFF_MODEL, LEVELS).error
    assert resolve_request_effort("ultra_turbo", OFF_MODEL, LEVELS, clamp_enabled=True).error
    assert resolve_request_effort(7, OFF_MODEL, LEVELS).error == "reasoning_effort must be a string"
    assert resolve_request_effort("off", LADDER_MODEL, LEVELS, clamp_enabled=True).error


@pytest.mark.parametrize(
    "message", ["Invalid model selection: x", 'effort "high" is not supported for model "m"', "flag requires --effort"]
)
def test_default_deterministic_patterns(message: str) -> None:
    assert is_deterministic_cli_rejection(message, {})
    assert not is_deterministic_cli_rejection("connection reset by peer", {})
    assert not is_deterministic_cli_rejection(None, {}) and not is_deterministic_cli_rejection("", {})
    assert not is_deterministic_cli_rejection(123, {})


def test_deterministic_pattern_from_env_and_broken_regex_fallback() -> None:
    assert is_deterministic_cli_rejection("quota exceeded", {ENV_DETERMINISTIC_RE: "quota"})
    assert not is_deterministic_cli_rejection(REJECT, {ENV_DETERMINISTIC_RE: "quota"})
    assert is_deterministic_cli_rejection(REJECT, {ENV_DETERMINISTIC_RE: "[unclosed"})
    assert not is_deterministic_cli_rejection("boom", {ENV_DETERMINISTIC_RE: "[unclosed"})
