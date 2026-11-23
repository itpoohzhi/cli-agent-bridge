"""Cross-layer parity tests for strict Anthropic 5.5 AGY gating."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

import core.agy_anthropic_gate as gate

EXPECTED_ALLOWLIST: tuple[str, ...] = (
    "claude-sonnet-5-5", "claude-sonnet-5-5-low", "claude-sonnet-5-5-medium",
    "claude-sonnet-5-5-high", "claude-sonnet-5-5-thinking",
    "claude-opus-5-5", "claude-opus-5-5-low", "claude-opus-5-5-medium",
    "claude-opus-5-5-high", "claude-opus-5-5-thinking",
)
REJECTED_IDS: tuple[str, ...] = (
    "claude-sonnet-4-6", "claude-opus-4-6-thinking", "claude-haiku-4-5",
    "claude-haiku-5-5", "claude-sonnet-5-5-max", "claude-opus-5-5-xhigh",
)
TRUTHY_FLAGS: tuple[str, ...] = ("1", "true", "TRUE", "yes", "on", "ON")
FALSY_FLAGS: tuple[str, ...] = ("0", "false", "no", "off", "")
REAL_AGY_MODELS_FIXTURE = (
    "\r⠋ Fetching available models..."
    "\rgemini-4-neon-high          Gemini 4 Neon (High)\n"
    "gemini-4-hydrogen-high      Gemini 4 Hydrogen (High)\n"
    "claude-opus-5-5-high        Claude Opus 5.5 (High)\n"
    "claude-sonnet-5-5-high      Claude Sonnet 5.5 (High)\n"
    "claude-sonnet-4-6           Claude Sonnet 4.6\n"
)
_LAUNCH_GUARD_REL = "~/work/tmp/agy-5-5-config/agy-launch/agy_anthropic_launch_guard.py"
_PREFLIGHT_REL = (
    "~/work/tmp/agy-5-5-skils/ai-sdlc/universal/teamlead-gate/scripts/"
    "agy_anthropic_preflight.py"
)
LAYER_PATHS: tuple[tuple[str, Path], ...] = (
    ("launch_guard", Path(_LAUNCH_GUARD_REL).expanduser()),
    ("preflight", Path(_PREFLIGHT_REL).expanduser()),
)


def _load_layer(path: Path, mod_name: str) -> Any:
    if not path.is_file():
        pytest.skip(f"Sibling layer missing: {path}")
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        pytest.fail(f"Cannot load module spec: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


def _first_attr(module: Any, names: tuple[str, ...]) -> Any:
    for name in names:
        val = getattr(module, name, None)
        if val is not None:
            return val
    pytest.fail(f"Missing expected symbol {names} in {module.__name__}")


def test_gate_strict_allowlist_parser_and_flags() -> None:
    assert gate.ALLOWED_AGY_CLAUDE_IDS == EXPECTED_ALLOWLIST
    assert all(not gate.is_forbidden_claude_id(m) for m in EXPECTED_ALLOWLIST)
    assert all(gate.is_forbidden_claude_id(m) for m in REJECTED_IDS)
    assert all(not gate.validate_claude_effort(e)[0] for e in ("max", "xhigh"))
    assert gate.parse_agy_models_output(REAL_AGY_MODELS_FIXTURE) == (
        "gemini-4-neon-high", "gemini-4-hydrogen-high",
        "claude-opus-5-5-high", "claude-sonnet-5-5-high", "claude-sonnet-4-6",
    )
    assert all(gate.is_anthropic_flag_enabled(v) for v in TRUTHY_FLAGS)
    assert all(not gate.is_anthropic_flag_enabled(v) for v in FALSY_FLAGS)


@pytest.mark.parametrize(("layer_name", "layer_path"), LAYER_PATHS)
def test_sibling_layer_allowlist_parity(layer_name: str, layer_path: Path) -> None:
    mod = _load_layer(layer_path, f"_parity_{layer_name}")
    allowlist = _first_attr(
        mod,
        ("ALLOWED_AGY_CLAUDE_IDS", "EXACT_5_5_CLAUDE_IDS", "EXACT_5_5_ALLOW"),
    )
    assert frozenset(allowlist) == frozenset(EXPECTED_ALLOWLIST)
    assert len(allowlist) == len(EXPECTED_ALLOWLIST)
    for attr, fn in (
        ("is_forbidden_claude_id", gate.is_forbidden_claude_id),
        ("canonicalize_claude_model", gate.canonicalize_claude_model),
    ):
        peer = getattr(mod, attr, None)
        if peer is not None:
            assert all(peer(m) == fn(m) for m in EXPECTED_ALLOWLIST + REJECTED_IDS)
    effort_fn = vars(mod).get("validate_claude_effort")
    if effort_fn is not None:
        for effort in (None, "low", "medium", "high", "max", "xhigh"):
            assert effort_fn(effort)[0] == gate.validate_claude_effort(effort)[0]


@pytest.mark.parametrize(("layer_name", "layer_path"), LAYER_PATHS)
def test_sibling_layer_parser_and_flag_parity(layer_name: str, layer_path: Path) -> None:
    mod = _load_layer(layer_path, f"_parity_{layer_name}")
    assert tuple(mod.parse_agy_models_output(REAL_AGY_MODELS_FIXTURE)) == (
        gate.parse_agy_models_output(REAL_AGY_MODELS_FIXTURE)
    )
    enabled_set = _first_attr(mod, ("ENABLED_FLAG_VALUES", "_ENABLED_VALUES"))
    assert frozenset(enabled_set) == frozenset(gate.ENABLED_FLAG_VALUES)
    for v in TRUTHY_FLAGS + FALSY_FLAGS:
        expected = gate.is_anthropic_flag_enabled(v)
        if layer_name == "launch_guard":
            assert mod._is_enabled({"AGY_ANTHROPIC_ENABLED": v}) is expected
        else:
            assert mod.is_judge_agy_anthropic_enabled({"JUDGE_AGY_ANTHROPIC_ENABLED": v}) is expected
