"""L1: открытое состояние, немедленная публикация вызовов и strict_live нормализатора."""

from __future__ import annotations

import pytest

import core.tool_emulation as emulation
from core.tool_mode import ToolMode, ToollessTagPolicy
from tests.unit._tool_mode_stream import OTHER_CALL, VALID_CALL, make

OFF_FORBID = (
    (ToolMode.OFF, ToollessTagPolicy.TEXT),
    (ToolMode.OFF, ToollessTagPolicy.ERROR),
    (ToolMode.FORBID, ToollessTagPolicy.TEXT),
    (ToolMode.FORBID, ToollessTagPolicy.ERROR),
)


@pytest.mark.parametrize("mode,policy", OFF_FORBID)
def test_off_and_forbid_have_no_parser_and_no_open_block_after_plain_text(
    mode: ToolMode, policy: ToollessTagPolicy
) -> None:
    capture = make(mode, policy)
    assert capture.normalizer._parser is None
    assert capture.normalizer.has_open_tool_call() is False
    capture.feed_chars("plain answer")
    assert capture.normalizer.has_open_tool_call() is False
    capture.normalizer.finish()
    assert capture.normalizer.has_open_tool_call() is False
    assert capture.text == "plain answer"


def test_emulate_owns_a_parser_and_is_closed_before_any_input() -> None:
    capture = make(ToolMode.EMULATE)
    assert capture.normalizer._parser is not None
    assert capture.normalizer.has_open_tool_call() is False


@pytest.mark.parametrize("tail", ("<", "<t", "<tool_c", "<tool_call"))
def test_emulate_partial_tag_prefix_is_open(tail: str) -> None:
    capture = make(ToolMode.EMULATE)
    capture.feed_chars("ok " + tail)
    assert capture.normalizer.has_open_tool_call() is True
    assert capture.text == "ok "


@pytest.mark.parametrize("tail", ("<thin", "<thinking"))
def test_off_text_partial_reasoning_prefix_is_open(tail: str) -> None:
    capture = make(ToolMode.OFF)
    capture.feed_chars(tail)
    assert capture.normalizer.has_open_tool_call() is True


@pytest.mark.parametrize("tag", emulation.REASONING_TAGS)
def test_open_thinking_block_is_open_until_closed(tag: str) -> None:
    capture = make(ToolMode.EMULATE)
    capture.feed_chars(f"<{tag}>step")
    assert capture.normalizer.has_open_tool_call() is True
    capture.feed_chars(f"</{tag}>")
    assert capture.normalizer.has_open_tool_call() is False
    assert "".join(capture.reasoning) == "step"


def test_open_tool_call_block_is_open_until_close_tag() -> None:
    capture = make(ToolMode.EMULATE)
    capture.feed_chars('<tool_call>{"name":"noop"')
    assert capture.normalizer.has_open_tool_call() is True
    assert capture.calls == []
    capture.feed_chars(',"arguments":{}}')
    assert capture.normalizer.has_open_tool_call() is True
    capture.feed_chars("</tool_call>")
    assert capture.normalizer.has_open_tool_call() is False


def test_complete_call_is_visible_before_finish() -> None:
    capture = make(ToolMode.EMULATE)
    capture.feed_chars(VALID_CALL[:-1])
    assert len(capture.calls) == 0
    capture.feed_chars(VALID_CALL[-1])
    assert len(capture.calls) == 1
    assert capture.calls[0]["name"] == "noop"
    assert capture.calls[0]["arguments"] == {}
    assert len(capture.normalizer.tool_calls) == 1
    capture.normalizer.finish()
    assert len(capture.calls) == 1


def test_complete_call_is_visible_before_finish_with_text_around_it() -> None:
    capture = make(ToolMode.EMULATE)
    capture.feed_chars("before ")
    capture.feed_chars(VALID_CALL)
    assert [call["name"] for call in capture.calls] == ["noop"]
    assert capture.text == "before "
    capture.feed_chars(" after")
    capture.normalizer.finish()
    assert capture.text == "before  after"


def test_two_back_to_back_calls_in_one_feed_are_both_published_before_finish() -> None:
    capture = make(ToolMode.EMULATE)
    capture.normalizer.feed_text(VALID_CALL + OTHER_CALL)
    assert [call["name"] for call in capture.calls] == ["noop", "other"]
    assert capture.calls[1]["arguments"] == {"k": 1}
    assert capture.text == ""
    assert capture.normalizer.has_open_tool_call() is False
    capture.normalizer.finish()
    assert [call["name"] for call in capture.normalizer.tool_calls] == ["noop", "other"]


def test_second_call_in_progress_leaves_first_call_published_and_gate_open() -> None:
    capture = make(ToolMode.EMULATE)
    capture.normalizer.feed_text(VALID_CALL + '<tool_call>{"name":"other"')
    assert [call["name"] for call in capture.calls] == ["noop"]
    assert capture.normalizer.has_open_tool_call() is True


def test_strict_live_unclosed_call_raises_on_finish_without_publishing() -> None:
    capture = make(ToolMode.EMULATE, strict_live=True)
    capture.normalizer.feed_text('<tool_call>{"name":"f"')
    assert capture.normalizer.has_open_tool_call() is True
    with pytest.raises(emulation.LiveParserError, match="unclosed tool_call block"):
        capture.normalizer.finish()
    assert capture.calls == []
    assert capture.text == ""


def test_strict_live_keeps_calls_published_before_the_failure() -> None:
    capture = make(ToolMode.EMULATE, strict_live=True)
    capture.normalizer.feed_text(VALID_CALL + '<tool_call>{"name":"f"')
    with pytest.raises(emulation.LiveParserError):
        capture.normalizer.finish()
    assert [call["name"] for call in capture.calls] == ["noop"]


def test_non_strict_unclosed_call_is_flushed_as_literal_content() -> None:
    capture = make(ToolMode.EMULATE, strict_live=False)
    capture.normalizer.feed_text('<tool_call>{"name":"f"')
    capture.normalizer.finish()
    assert capture.text == '<tool_call>{"name":"f"'
    assert capture.calls == []


def test_strict_live_bare_json_without_tag_is_plain_content() -> None:
    capture = make(ToolMode.EMULATE, strict_live=True)
    capture.normalizer.feed_text('{"name":"f"')
    capture.normalizer.finish()
    assert capture.text == '{"name":"f"'
    assert capture.calls == []


@pytest.mark.parametrize("tag", ("think", "analysis"))
def test_strict_live_unclosed_reasoning_raises_on_finish(tag: str) -> None:
    capture = make(ToolMode.EMULATE, strict_live=True)
    capture.normalizer.feed_text(f"<{tag}>never closed")
    assert "".join(capture.reasoning) == "never closed"
    with pytest.raises(emulation.LiveParserError, match="unclosed reasoning tag"):
        capture.normalizer.finish()
