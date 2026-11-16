"""L1: границы tool_choice и режимов в core/tool_mode.py."""

from __future__ import annotations

from typing import Any

import pytest

from core.tool_mode import (
    NormalizerModeSpec,
    ToolMode,
    ToollessTagPolicy,
    _tool_choice_none,
    check_unexpected_tool_calls,
    format_tool_mode_log,
    resolve_tool_mode,
)

TOOLS = [{"type": "function", "function": {"name": "noop"}}]
NATIVE_CALL = {"id": "c1", "type": "function", "function": {"name": "noop"}}


@pytest.mark.parametrize(
    "choice,expected",
    (
        ("none", True),
        ("NONE", True),
        ("  None  ", True),
        ("auto", False),
        ("required", False),
        ("", False),
        ({"type": "none"}, True),
        ({"type": "NONE"}, True),
        ({"type": "function"}, False),
        ({"type": "function", "function": {"name": "noop"}}, False),
        ({"type": None}, False),
        ({"type": ""}, False),
        ({}, False),
        (None, False),
        (0, False),
        (["none"], False),
    ),
)
def test_tool_choice_none_forms(choice: Any, expected: bool) -> None:
    assert _tool_choice_none(choice) is expected


def test_object_form_requires_type_key_not_string_whitespace() -> None:
    assert _tool_choice_none({"type": " none "}) is False
    assert _tool_choice_none({"name": "none"}) is False


@pytest.mark.parametrize("choice", ("none", {"type": "none"}, "auto", None))
@pytest.mark.parametrize("tools", (None, [], ()))
def test_absent_tools_resolve_off_regardless_of_choice(tools: Any, choice: Any) -> None:
    assert resolve_tool_mode(tools, choice) is ToolMode.OFF


@pytest.mark.parametrize(
    "choice,expected",
    (
        ("none", ToolMode.FORBID),
        ({"type": "none"}, ToolMode.FORBID),
        ({"type": "function"}, ToolMode.EMULATE),
        (None, ToolMode.EMULATE),
        ("auto", ToolMode.EMULATE),
    ),
)
def test_present_tools_resolve_by_choice(choice: Any, expected: ToolMode) -> None:
    assert resolve_tool_mode(TOOLS, choice) is expected


def test_choice_defaults_to_none_value_meaning_emulate() -> None:
    assert resolve_tool_mode(TOOLS) is ToolMode.EMULATE


@pytest.mark.parametrize("mode", (ToolMode.OFF, ToolMode.FORBID))
@pytest.mark.parametrize("calls", (None, [], (), ""))
def test_empty_native_calls_pass_outside_emulate(mode: ToolMode, calls: Any) -> None:
    check_unexpected_tool_calls(mode, calls)


@pytest.mark.parametrize("mode", (ToolMode.OFF, ToolMode.FORBID))
def test_nonempty_native_calls_are_rejected_with_mode_name(mode: ToolMode) -> None:
    with pytest.raises(ValueError, match=f"unexpected tool calls in mode={mode.value}"):
        check_unexpected_tool_calls(mode, [NATIVE_CALL])


@pytest.mark.parametrize("calls", (None, [], [NATIVE_CALL]))
def test_emulate_accepts_any_native_calls(calls: Any) -> None:
    check_unexpected_tool_calls(ToolMode.EMULATE, calls)


@pytest.mark.parametrize(
    "tools,choice,shown",
    (
        (None, None, "req_tools=0 tool_choice=None"),
        ([], "auto", "req_tools=0 tool_choice=auto"),
        (TOOLS, {"type": "none"}, "req_tools=1 tool_choice=none"),
        (
            TOOLS + TOOLS,
            {"type": "function", "function": {"name": "x"}},
            "req_tools=2 tool_choice=function",
        ),
        (TOOLS, "required", "req_tools=1 tool_choice=required"),
    ),
)
def test_log_line_has_counts_and_choice_type_only(
    tools: Any, choice: Any, shown: str
) -> None:
    spec = NormalizerModeSpec(ToolMode.EMULATE, ToollessTagPolicy.ERROR)
    line = format_tool_mode_log(tools, choice, spec)
    assert line == f"{shown} mode=emulate policy=error"
    assert "noop" not in line and '"x"' not in line
