"""L1: применение NormalizerModeSpec, prefix-hold и служебные теги нормализатора."""

from __future__ import annotations

import pytest

import core.tool_emulation as emulation
from core.tool_mode import ToolMode, ToollessTagPolicy
from tests.unit._tool_mode_stream import STRICT_MODES, VALID_CALL, make

OFF, FORBID, EMULATE = ToolMode.OFF, ToolMode.FORBID, ToolMode.EMULATE
TEXT, ERROR = ToollessTagPolicy.TEXT, ToollessTagPolicy.ERROR


def test_off_text_passes_tool_markup_through_as_content() -> None:
    capture = make(OFF, TEXT)
    capture.feed_chars(VALID_CALL + " </tool_call>")
    capture.normalizer.finish()
    assert capture.text == VALID_CALL + " </tool_call>"
    assert capture.calls == []


@pytest.mark.parametrize("mode,policy", STRICT_MODES)
def test_off_error_and_forbid_reject_tool_open_regardless_of_other_policy(
    mode: ToolMode, policy: ToollessTagPolicy
) -> None:
    capture = make(mode, policy)
    with pytest.raises(
        emulation.LiveParserError, match="unexpected service tag: tool_call"
    ):
        capture.feed_chars(VALID_CALL)
        capture.normalizer.finish()
    assert capture.text == "" and capture.calls == []


def test_emulate_accepts_tool_open_under_both_policies_and_parses_it() -> None:
    for policy in (TEXT, ERROR):
        capture = make(EMULATE, policy)
        capture.feed_chars(VALID_CALL)
        capture.normalizer.finish()
        assert [call["name"] for call in capture.calls] == ["noop"]
        assert capture.text == ""


@pytest.mark.parametrize("mode,policy", STRICT_MODES)
def test_strict_modes_reject_invoke_family_but_off_text_keeps_it(
    mode: ToolMode, policy: ToollessTagPolicy
) -> None:
    capture = make(mode, policy)
    with pytest.raises(emulation.LiveParserError):
        capture.feed_chars("<invoke>")
        capture.normalizer.finish()
    literal = make(OFF, TEXT)
    literal.feed_chars("<invoke>")
    literal.normalizer.finish()
    assert literal.text == "<invoke>"


@pytest.mark.parametrize("mode,policy", STRICT_MODES)
def test_non_strict_live_still_rejects_tool_blocks_fail_closed(
    mode: ToolMode, policy: ToollessTagPolicy
) -> None:
    capture = make(mode, policy, strict_live=False)
    with pytest.raises(
        emulation.LiveParserError, match="unexpected service tag: tool_call"
    ):
        capture.feed_chars(VALID_CALL)
    assert capture.normalizer._state == "text"
    assert capture.text == "" and capture.calls == []


@pytest.mark.parametrize("mode,policy", STRICT_MODES)
def test_non_strict_live_prefix_hold_at_eof_fails_closed(
    mode: ToolMode, policy: ToollessTagPolicy
) -> None:
    capture = make(mode, policy, strict_live=False)
    capture.feed_chars("answer <tool_c")
    assert capture.text == "answer "
    with pytest.raises(emulation.LiveParserError, match="unresolved tool/service tag"):
        capture.normalizer.finish()
    assert capture.normalizer._state == "text"
    assert capture.text == "answer "


@pytest.mark.parametrize(
    "mode,policy", ((EMULATE, TEXT), (EMULATE, ERROR), (OFF, TEXT))
)
def test_non_strict_live_keeps_literals_outside_strict_modes(
    mode: ToolMode, policy: ToollessTagPolicy
) -> None:
    capture = make(mode, policy, strict_live=False)
    capture.feed_chars("see </tool_call> and <tool_c")
    capture.normalizer.finish()
    assert capture.text == "see </tool_call> and <tool_c"
    assert capture.calls == []


@pytest.mark.parametrize("mode", (FORBID, OFF))
def test_prefix_hold_inside_open_code_fence_is_flushed_not_rejected(
    mode: ToolMode,
) -> None:
    capture = make(mode, ERROR)
    capture.feed_chars("```\n<tool_c")
    assert capture.normalizer.has_open_tool_call() is True
    capture.normalizer.finish()
    assert capture.text == "```\n<tool_c"


@pytest.mark.parametrize("mode", (FORBID, OFF))
def test_prefix_hold_outside_code_raises_with_no_leak(mode: ToolMode) -> None:
    capture = make(mode, ERROR)
    capture.feed_chars("answer <tool_c")
    assert capture.text == "answer "
    with pytest.raises(emulation.LiveParserError, match="unresolved tool/service tag"):
        capture.normalizer.finish()
    assert capture.text == "answer "


@pytest.mark.parametrize("policy", (TEXT, ERROR))
@pytest.mark.parametrize("tail", ("<t", "<tool_c", "</t"))
def test_emulate_prefix_hold_is_flushed_not_rejected_at_finish(
    tail: str, policy: ToollessTagPolicy
) -> None:
    capture = make(EMULATE, policy)
    capture.feed_chars("see " + tail)
    assert capture.normalizer.has_open_tool_call() is True
    assert capture.text == "see "
    capture.normalizer.finish()
    assert capture.text == "see " + tail
    assert capture.calls == []


def test_prefix_hold_that_is_not_a_tag_prefix_is_flushed_in_forbid() -> None:
    capture = make(FORBID)
    capture.feed_chars("<tool_cat")
    assert capture.normalizer.has_open_tool_call() is False
    capture.normalizer.finish()
    assert capture.text == "<tool_cat"


def test_prefix_hold_in_non_strict_forbid_raises_fail_closed() -> None:
    capture = make(FORBID, strict_live=False)
    capture.feed_chars("<tool_c")
    with pytest.raises(emulation.LiveParserError, match="unresolved tool/service tag"):
        capture.normalizer.finish()
    assert capture.text == ""


@pytest.mark.parametrize("mode", (FORBID, OFF))
def test_inline_code_span_keeps_tool_open_literal(mode: ToolMode) -> None:
    capture = make(mode, ERROR)
    capture.feed_chars("use `<tool_call>` here")
    capture.normalizer.finish()
    assert capture.text == "use `<tool_call>` here"
    assert capture.calls == []


@pytest.mark.parametrize("mode", (FORBID, OFF))
def test_unclosed_backtick_does_not_shield_tool_open(mode: ToolMode) -> None:
    capture = make(mode, ERROR)
    with pytest.raises(emulation.LiveParserError, match="unexpected service tag"):
        capture.feed_chars("a `b <tool_call>")
        capture.normalizer.finish()
    assert capture.calls == []


def test_orphan_tool_close_in_emulate_strict_raises() -> None:
    capture = make(EMULATE)
    with pytest.raises(
        emulation.LiveParserError, match="unexpected service tag: tool_call"
    ):
        capture.feed_chars("</tool_call>")
        capture.normalizer.finish()
    assert capture.text == ""


def test_orphan_tool_close_in_emulate_non_strict_is_content() -> None:
    capture = make(EMULATE, strict_live=False)
    capture.feed_chars("</tool_call>")
    capture.normalizer.finish()
    assert capture.text == "</tool_call>"


@pytest.mark.parametrize("mode,policy", ((OFF, TEXT), (EMULATE, TEXT), (FORBID, TEXT)))
def test_orphan_reasoning_close_raises_in_every_strict_mode(
    mode: ToolMode, policy: ToollessTagPolicy
) -> None:
    capture = make(mode, policy)
    with pytest.raises(
        emulation.LiveParserError, match="unexpected service tag: think"
    ):
        capture.feed_chars("</think>")
        capture.normalizer.finish()


def test_orphan_reasoning_close_non_strict_is_content() -> None:
    capture = make(OFF, TEXT, strict_live=False)
    capture.feed_chars("</think>")
    capture.normalizer.finish()
    assert capture.text == "</think>"


def test_reasoning_open_is_never_rejected_by_reject_tools() -> None:
    capture = make(FORBID, TEXT)
    capture.feed_chars("<think>why</think>done")
    capture.normalizer.finish()
    assert "".join(capture.reasoning) == "why"
    assert capture.text == "done"
