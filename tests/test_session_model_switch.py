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

from core.cli_rejection import (  # noqa: E402
    DEFAULT_ERR_SCAN_LEN,
    ENV_DETERMINISTIC_ERR_MAX_LEN,
    ENV_DETERMINISTIC_RE,
    is_deterministic_cli_rejection,
)
from core.effort_policy import EffortResolution, ModelEffortCardFields, ModelEffortSpec  # noqa: E402
from core.effortless_policy import (  # noqa: E402
    SOURCE_CLAMPED,
    SOURCE_DEFAULT,
    SOURCE_REQUEST,
    EffortDecision,
    EffortValidationError,
    card_effort_fields,
    effort_cli_args,
    effortless_specs,
    is_effortless,
    resolve_request_effort,
    strip_effortless_effort,
)
from core.passthrough_autonomy import PassthroughOptions, prepare_passthrough_request  # noqa: E402

CARBON, ARGON = "gemini-4-carbon", "gemini-4-argon"
CLAMP_FLAG = "BRIDGE_EFFORTLESS_CLAMP_ENABLED"
LEVELS = ("off", "minimal", "low", "medium", "high", "xhigh", "max")
OFF_MODEL = {"efforts": ["off"], "default_effort": "off"}
LADDER_MODEL = {"efforts": ["low", "medium", "high"], "default_effort": "high"}
REJECT = 'invalid model selection (--model "gemini-4-carbon" --effort "high"): --effort is not supported for model "gemini-4-carbon"'


# ---- L1: политика effort и классификатор отказов CLI ------------------------------


def test_is_effortless_only_for_off_ladder() -> None:
    assert is_effortless(["off"]) and is_effortless(["OFF"]) and is_effortless((" off ",))
    assert is_effortless({"off"}) and is_effortless(frozenset({"OFF"}))
    assert not any(
        map(
            is_effortless,
            (["low", "high"], [], (), None, ["off", "low"], "off", b"off", True, False, 123, {"off": None}, [1]),
        )
    )


def test_specs_card_fields_and_cli_args() -> None:
    specs = {"a": ModelEffortSpec(("off",), "off"), "b": ModelEffortSpec(("low", "high"), "high")}
    assert set(effortless_specs(specs)) == {"a"}
    off_card = card_effort_fields(ModelEffortCardFields("off", ("off",)))
    assert off_card == {"supports_thinking": False, "supported_reasoning_efforts": ["off"], "default_reasoning_effort": "off"}
    assert "supports_thinking" not in card_effort_fields(ModelEffortCardFields("high", ("low", "high")))
    assert "supports_thinking" not in card_effort_fields(ModelEffortCardFields(None, ()))
    assert effort_cli_args("off") == effort_cli_args(None) == effort_cli_args("") == []
    assert effort_cli_args("high") == ["--effort", "high"]


@pytest.mark.parametrize("effort_on", [False, True])
def test_passthrough_strips_reasoning_effort_for_effortless_model(effort_on: bool) -> None:
    req: dict[str, object] = {"model": CARBON, "reasoning_effort": "high", "messages": []}
    clean, resolution = prepare_passthrough_request(
        req, OFF_MODEL, CARBON, PassthroughOptions(effort_on=effort_on)
    )
    assert "reasoning_effort" not in clean and clean["messages"] == []
    assert (resolution.value, resolution.apply) == ("off", True)
    assert resolution.clamped_from == "high"
    assert req["reasoning_effort"] == "high"  # исходный запрос не мутируется
    clean_off, res_off = prepare_passthrough_request(
        {"model": CARBON, "reasoning_effort": "OFF"},
        OFF_MODEL,
        CARBON,
        PassthroughOptions(effort_on=effort_on, clamp_enabled=False),
    )
    assert "reasoning_effort" not in clean_off
    assert res_off.value == "off" and res_off.apply is True and res_off.clamped_from is None


def test_passthrough_effortless_absent_blank_and_validation_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    absent_req: dict[str, object] = {"model": CARBON, "messages": []}
    clean_absent, res_absent = prepare_passthrough_request(absent_req, OFF_MODEL, CARBON)
    assert clean_absent is absent_req and res_absent == EffortResolution()

    clean_blank, res_blank = prepare_passthrough_request(
        {"model": CARBON, "reasoning_effort": "   "}, OFF_MODEL, CARBON
    )
    assert "reasoning_effort" not in clean_blank
    assert res_blank == EffortResolution("off", True, None)

    for bad in ("ultra_turbo", "ultra"):
        with pytest.raises(EffortValidationError):
            prepare_passthrough_request({"model": CARBON, "reasoning_effort": bad}, OFF_MODEL, CARBON)

    for non_str in (123, True, None):
        with pytest.raises(EffortValidationError, match="must be a string"):
            prepare_passthrough_request({"model": CARBON, "reasoning_effort": non_str}, OFF_MODEL, CARBON)

    with pytest.raises(EffortValidationError):
        prepare_passthrough_request(
            {"model": CARBON, "reasoning_effort": "high"},
            OFF_MODEL,
            CARBON,
            PassthroughOptions(clamp_enabled=False),
        )
    monkeypatch.setenv(CLAMP_FLAG, "false")
    with pytest.raises(EffortValidationError):
        prepare_passthrough_request({"model": CARBON, "reasoning_effort": "high"}, OFF_MODEL, CARBON)

    # alias_effort на effortless-модели учитывается так же, как reasoning_effort
    clean_alias, res_alias = prepare_passthrough_request(
        {"model": f"{CARBON}-high"},
        OFF_MODEL,
        CARBON,
        PassthroughOptions(alias=(CARBON, "high"), alias_effort="high", clamp_enabled=True),
    )
    assert clean_alias["model"] == CARBON and "reasoning_effort" not in clean_alias
    assert res_alias == EffortResolution("off", True, "high")
    with pytest.raises(EffortValidationError):
        prepare_passthrough_request(
            {"model": f"{CARBON}-high"},
            OFF_MODEL,
            CARBON,
            PassthroughOptions(alias=(CARBON, "high"), alias_effort="high", clamp_enabled=False),
        )


def test_passthrough_keeps_request_of_ordinary_model() -> None:
    req: dict[str, object] = {"model": ARGON, "reasoning_effort": "high"}
    clean, resolution = prepare_passthrough_request(
        req, LADDER_MODEL, ARGON, PassthroughOptions(effort_on=False)
    )
    assert clean == req and resolution == EffortResolution()
    spec = ModelEffortSpec(("low", "medium", "high"), "high")
    assert strip_effortless_effort(req, spec, resolution) == (req, resolution)
    off_spec = ModelEffortSpec(("off",), "off")
    bare_req: dict[str, object] = {"model": CARBON}
    bare_clean, bare_res = strip_effortless_effort(bare_req, off_spec, EffortResolution("off", True))
    assert bare_clean is bare_req and bare_res.apply is False


@pytest.mark.parametrize("raw", ["high", "xhigh"])
def test_resolve_request_effort_clamps_known_level_to_off(raw: str) -> None:
    decision = resolve_request_effort(raw, OFF_MODEL, LEVELS, clamp_enabled=True)
    assert decision == EffortDecision("off", SOURCE_CLAMPED, None)
    assert resolve_request_effort(raw, OFF_MODEL, LEVELS) == EffortDecision("off", SOURCE_CLAMPED, None)
    assert resolve_request_effort(None, OFF_MODEL, LEVELS) == EffortDecision("off", SOURCE_DEFAULT, None)
    assert resolve_request_effort("   ", OFF_MODEL, LEVELS) == EffortDecision("off", SOURCE_DEFAULT, None)
    assert resolve_request_effort("off", OFF_MODEL, LEVELS) == EffortDecision("off", SOURCE_REQUEST, None)
    assert resolve_request_effort("OFF", OFF_MODEL, LEVELS, clamp_enabled=False) == EffortDecision(
        "off", SOURCE_REQUEST, None
    )
    assert resolve_request_effort("OFF", ModelEffortSpec(("off",), "off"), LEVELS, clamp_enabled=False) == EffortDecision(
        "off", SOURCE_REQUEST, None
    )
    assert resolve_request_effort("HIGH", LADDER_MODEL, LEVELS) == EffortDecision("high", SOURCE_REQUEST, None)


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


@pytest.mark.parametrize("token", ["", "   ", "0", "false", "FALSE", "off", "OFF", "no"])
def test_deterministic_pattern_disable_tokens_and_scan_limit(token: str) -> None:
    assert not is_deterministic_cli_rejection(REJECT, {ENV_DETERMINISTIC_RE: token})
    long_tail = "x" * DEFAULT_ERR_SCAN_LEN + " " + REJECT
    assert not is_deterministic_cli_rejection(long_tail, {})
    assert is_deterministic_cli_rejection(
        long_tail, {ENV_DETERMINISTIC_ERR_MAX_LEN: str(len(long_tail))}
    )
