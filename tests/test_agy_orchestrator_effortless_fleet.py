"""Tests for the effortless-fleet policy as applied to the AGY orchestrator model.

Covers ``bridges/agy-bridge/fleet.json`` discovery for
``gemini-pro-orchestrator`` and the behaviour of the effortless policy
helpers in ``core/effortless_policy.py``.
"""

import json
from pathlib import Path

import pytest

from core.effort_policy import EFFORT_LEVELS
from core.effortless_policy import (
    SOURCE_CLAMPED,
    SOURCE_DEFAULT,
    SOURCE_REQUEST,
    effort_cli_args,
    is_effortless,
    resolve_request_effort,
)

FLEET_PATH = (
    Path(__file__).resolve().parents[1] / "bridges" / "agy-bridge" / "fleet.json"
)
MODEL_ID = "gemini-pro-orchestrator"
NOT_ALLOWED_ERROR = "reasoning_effort is not allowed for this model"
NOT_A_STRING_ERROR = "reasoning_effort must be a string"


def _load_entry(model_id: str) -> dict:
    """Load the fleet entry for ``model_id``, failing if it is missing."""
    data = json.loads(FLEET_PATH.read_text(encoding="utf-8"))
    matches = [m for m in data["models"] if m.get("id") == model_id]
    assert len(matches) == 1, f"expected exactly one fleet entry for {model_id!r}"
    return matches[0]


@pytest.fixture(scope="module")
def entry() -> dict:
    """Fleet entry for the orchestrator model."""
    return _load_entry(MODEL_ID)


def test_fleet_file_exists() -> None:
    assert FLEET_PATH.is_file()


def test_orchestrator_entry_is_effortless(entry: dict) -> None:
    assert entry["efforts"] == ["off"]
    assert entry["default_effort"] == "off"
    assert is_effortless(entry["efforts"]) is True


def test_resolve_none_uses_default_effort(entry: dict) -> None:
    decision = resolve_request_effort(None, entry, EFFORT_LEVELS)
    assert decision.effort == "off"
    assert decision.source == SOURCE_DEFAULT
    assert decision.error is None


def test_resolve_explicit_off_is_honored(entry: dict) -> None:
    decision = resolve_request_effort("off", entry, EFFORT_LEVELS)
    assert decision.effort == "off"
    assert decision.source == SOURCE_REQUEST
    assert decision.error is None


@pytest.mark.parametrize("raw", ["low", "medium", "high", "xhigh"])
def test_resolve_efforts_clamped_by_default(
    raw: str, entry: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("BRIDGE_EFFORTLESS_CLAMP_ENABLED", raising=False)
    decision = resolve_request_effort(raw, entry, EFFORT_LEVELS)
    assert decision.effort == "off"
    assert decision.source == SOURCE_CLAMPED
    assert decision.error is None


def test_resolve_high_rejected_when_clamp_disabled(entry: dict) -> None:
    decision = resolve_request_effort(
        "high", entry, EFFORT_LEVELS, clamp_enabled=False
    )
    assert decision.effort is None
    assert decision.error == NOT_ALLOWED_ERROR


def test_resolve_unknown_effort_string_rejected(entry: dict) -> None:
    decision = resolve_request_effort("definitely-not-an-effort", entry, EFFORT_LEVELS)
    assert decision.effort is None
    assert decision.error == NOT_ALLOWED_ERROR


def test_resolve_non_string_rejected(entry: dict) -> None:
    decision = resolve_request_effort(7, entry, EFFORT_LEVELS)
    assert decision.effort is None
    assert decision.error == NOT_A_STRING_ERROR


def test_effort_cli_args_mapping() -> None:
    assert effort_cli_args("off") == []
    assert effort_cli_args("high") == ["--effort", "high"]
