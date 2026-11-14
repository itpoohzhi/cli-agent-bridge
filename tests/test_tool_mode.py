"""VER-001: L1-контракты режимов, каналов и EOF (красные до W1)."""

from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core  # noqa: E402 - pytest console entry point не добавляет корень.
import core.runtime_env as runtime_env  # noqa: E402
import core.tool_emulation as emulation  # noqa: E402
from core.backend_adapter import TurnEvent, TurnResult  # noqa: E402

MODE_CASES = (
    ("OFF", "TEXT"),
    ("OFF", "ERROR"),
    ("FORBID", "TEXT"),
    ("FORBID", "ERROR"),
    ("EMULATE", "TEXT"),
    ("EMULATE", "ERROR"),
)
POLICY_ENV = "BRIDGE_TOOLLESS_TOOL_TAG_POLICY"
VALID_CALL = '<tool_call>{"name":"noop","arguments":{}}</tool_call>'


def _api() -> ModuleType:
    # Импорт внутри теста: отсутствие W1 не мешает собрать независимые регрессии.
    return importlib.import_module("core.tool_mode")


def _tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "noop",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]


def _assert_default_mode_spec(api: ModuleType) -> None:
    assert api.build_mode_spec(api.ToolMode.EMULATE) == api.DEFAULT_EMULATE_SPEC
    assert api.build_mode_spec(api.ToolMode.OFF) == api.build_mode_spec(
        api.ToolMode.OFF,
        api.ToollessTagPolicy.TEXT,
    )
    assert isinstance(api.NormalizerSinks(), api.NormalizerSinks)
    assert isinstance(api.TOOLLESS_PURE_TEXT_HINT, str)
    assert api.TOOLLESS_PURE_TEXT_HINT.strip()


def test_leaf_domain_types_and_default_mode_spec() -> None:
    api = _api()
    assert {item.name for item in api.ToolMode} == {"EMULATE", "FORBID", "OFF"}
    assert {item.name for item in api.ToollessTagPolicy} == {"TEXT", "ERROR"}
    assert isinstance(api.DEFAULT_EMULATE_SPEC, api.NormalizerModeSpec)
    _assert_default_mode_spec(api)


@pytest.mark.parametrize("tools", (None, []))
@pytest.mark.parametrize("choice", (None, "auto", "none", {"type": "none"}))
def test_no_tools_always_resolves_off(tools: Any, choice: Any) -> None:
    api = _api()
    assert api.resolve_tool_mode(tools, choice) is api.ToolMode.OFF


@pytest.mark.parametrize("choice", ("none", {"type": "none"}))
def test_tools_with_none_resolves_forbid(choice: Any) -> None:
    api = _api()
    assert api.resolve_tool_mode(_tools(), choice) is api.ToolMode.FORBID


@pytest.mark.parametrize(
    "choice",
    (None, "auto", "required", {"type": "function", "function": {"name": "noop"}}),
)
def test_tools_with_allowed_choice_resolves_emulate(choice: Any) -> None:
    api = _api()
    assert api.resolve_tool_mode(_tools(), choice) is api.ToolMode.EMULATE


@pytest.mark.parametrize(
    "choice,expected",
    (
        (None, False),
        ("auto", False),
        ("required", False),
        ("none", True),
        ({"type": "none"}, True),
        ({"type": "function"}, False),
    ),
)
def test_tool_choice_none_reexports_and_semantics(choice: Any, expected: bool) -> None:
    api = _api()
    assert (
        api._tool_choice_none is emulation._tool_choice_none is core._tool_choice_none
    )
    assert api._tool_choice_none(choice) is expected


@pytest.mark.parametrize("mode", ("OFF", "FORBID", "EMULATE"))
@pytest.mark.parametrize("nonempty", (False, True))
def test_unexpected_native_tool_calls_are_protocol_errors(
    mode: str, nonempty: bool
) -> None:
    api = _api()
    calls = (
        [
            {
                "id": "c",
                "type": "function",
                "function": {"name": "noop", "arguments": "{}"},
            }
        ]
        if nonempty
        else []
    )
    if nonempty and mode != "EMULATE":
        with pytest.raises(
            (ValueError, RuntimeError), match="(?i)tool|forbid|unexpected"
        ):
            api.check_unexpected_tool_calls(getattr(api.ToolMode, mode), calls)
    else:
        api.check_unexpected_tool_calls(getattr(api.ToolMode, mode), calls)


@pytest.mark.parametrize("mode,policy", MODE_CASES)
def test_mode_log_has_operational_fields(mode: str, policy: str) -> None:
    api = _api()
    tools = [] if mode == "OFF" else _tools()
    choice = "none" if mode == "FORBID" else "auto"
    spec = api.build_mode_spec(
        getattr(api.ToolMode, mode), getattr(api.ToollessTagPolicy, policy)
    )
    line = api.format_tool_mode_log(tools, choice, spec).lower()
    assert f"req_tools={len(tools)}" in line
    assert f"tool_choice={choice}" in line
    assert f"mode={mode.lower()}" in line
    assert f"policy={policy.lower()}" in line


@pytest.mark.parametrize(
    "raw,expected",
    (
        (None, "TEXT"),
        ("", "TEXT"),
        ("text", "TEXT"),
        ("TEXT", "TEXT"),
        ("error", "ERROR"),
    ),
)
def test_policy_resolution_uses_explicit_mapping(
    raw: str | None, expected: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = _api()
    monkeypatch.setenv(POLICY_ENV, "error" if expected == "TEXT" else "text")
    environ = {} if raw is None else {POLICY_ENV: raw}
    before = dict(environ)
    assert runtime_env.resolve_toolless_tag_policy(environ) is getattr(
        api.ToollessTagPolicy, expected
    )
    assert environ == before


def test_policy_resolution_explicit_default() -> None:
    api = _api()
    assert (
        runtime_env.resolve_toolless_tag_policy({}, default=api.ToollessTagPolicy.ERROR)
        is api.ToollessTagPolicy.ERROR
    )


def test_unknown_nonempty_policy_fails_closed_with_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    api = _api()
    with caplog.at_level(logging.WARNING):
        result = runtime_env.resolve_toolless_tag_policy({POLICY_ENV: "bogus"})
    assert result is api.ToollessTagPolicy.ERROR
    assert any(record.levelno >= logging.WARNING for record in caplog.records)
    assert POLICY_ENV.lower() in caplog.text.lower() or "policy" in caplog.text.lower()


def test_new_entry_points_are_present_independently_of_leaf_import() -> None:
    assert callable(getattr(runtime_env, "resolve_toolless_tag_policy", None))
    assert callable(getattr(emulation.StreamNormalizer, "for_mode", None))


@pytest.mark.parametrize("mode", ("OFF", "FORBID"))
def test_batch_finalize_turn_nonemulation_keeps_legacy_literals(mode: str) -> None:
    # AC-18: batch API остаётся boolean; OFF/FORBID передают False, не новый spec.
    text = VALID_CALL + " <invoke> </tool_call> <tool_c"
    raw = TurnResult(state="done", rc=0, text=text, reasoning="thought")
    tools = None if mode == "OFF" else _tools()
    tool_choice = None if mode == "OFF" else "none"
    emulate_tools = bool(tools) and not emulation._tool_choice_none(tool_choice)
    assert emulate_tools is False
    result = emulation.finalize_turn(raw, emulate_tools)
    assert result.text == text
    assert result.reasoning == "thought"
    assert not result.tool_calls
    assert result.events == (
        TurnEvent("reasoning", "thought"),
        TurnEvent("content", text),
    )


def test_batch_finalize_turn_preserves_prebuilt_events_by_identity() -> None:
    raw = TurnResult(
        state="done", rc=0, text=VALID_CALL, events=(TurnEvent("content", VALID_CALL),)
    )
    assert emulation.finalize_turn(raw, False) is raw
