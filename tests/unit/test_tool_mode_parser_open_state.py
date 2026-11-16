"""L1: ToolCallParser: открытый вызов, немедленная публикация и strict_live."""

from __future__ import annotations

from typing import Any

import pytest

import core.tool_emulation as emulation
from tests.unit._tool_mode_stream import OTHER_CALL, VALID_CALL


class _Probe:
    def __init__(self, *, strict_live: bool) -> None:
        self.content: list[str] = []
        self.calls: list[dict[str, Any]] = []
        self.parser = emulation.ToolCallParser(
            self.content.append,
            self.calls.append,
            strict_live=strict_live,
            repetition_guard_enabled=False,
        )

    def feed_chars(self, text: str) -> None:
        for char in text:
            self.parser.feed(char)


def test_fresh_parser_has_no_open_call() -> None:
    assert _Probe(strict_live=True).parser.has_open_tool_call() is False


def test_plain_text_leaves_no_open_call() -> None:
    probe = _Probe(strict_live=True)
    probe.parser.feed("no markup at all")
    assert probe.parser.has_open_tool_call() is False
    assert "".join(probe.content) == "no markup at all"


@pytest.mark.parametrize("tail", ("<", "<tool_c", "<tool_call"))
def test_partial_tag_prefix_counts_as_open(tail: str) -> None:
    probe = _Probe(strict_live=True)
    probe.feed_chars("x " + tail)
    assert probe.parser.has_open_tool_call() is True
    assert probe.calls == []


def test_body_in_progress_is_open_until_the_close_tag() -> None:
    probe = _Probe(strict_live=True)
    probe.feed_chars('<tool_call>{"name":"noop"')
    assert probe.parser.has_open_tool_call() is True
    probe.feed_chars(',"arguments":{}}</tool_call>')
    assert probe.parser.has_open_tool_call() is False
    assert [call["name"] for call in probe.calls] == ["noop"]


def test_call_is_published_on_the_closing_chunk_not_on_finish() -> None:
    probe = _Probe(strict_live=True)
    probe.parser.feed(VALID_CALL[:-1])
    assert probe.calls == []
    probe.parser.feed(VALID_CALL[-1])
    assert [call["name"] for call in probe.calls] == ["noop"]
    probe.parser.finish()
    assert len(probe.calls) == 1


def test_two_calls_in_one_feed_are_both_published_immediately() -> None:
    probe = _Probe(strict_live=True)
    probe.parser.feed(VALID_CALL + OTHER_CALL)
    assert [call["name"] for call in probe.calls] == ["noop", "other"]
    assert probe.calls[1]["arguments"] == {"k": 1}
    assert probe.content == []


def test_strict_live_unclosed_body_raises_on_finish() -> None:
    probe = _Probe(strict_live=True)
    probe.parser.feed('<tool_call>{"name":"f"')
    with pytest.raises(emulation.LiveParserError, match="unclosed tool_call block"):
        probe.parser.finish()
    assert probe.calls == [] and probe.content == []


def test_strict_live_failure_keeps_earlier_published_call() -> None:
    probe = _Probe(strict_live=True)
    probe.parser.feed(VALID_CALL + '<tool_call>{"name":"f"')
    with pytest.raises(emulation.LiveParserError):
        probe.parser.finish()
    assert [call["name"] for call in probe.calls] == ["noop"]


def test_legacy_unclosed_body_is_returned_as_content_without_error() -> None:
    probe = _Probe(strict_live=False)
    probe.parser.feed('<tool_call>{"name":"f"')
    probe.parser.finish()
    assert "".join(probe.content) == '<tool_call>{"name":"f"'
    assert probe.calls == []


def test_strict_live_empty_open_tag_at_finish_is_dropped_quietly() -> None:
    probe = _Probe(strict_live=True)
    probe.parser.feed("<tool_call>")
    probe.parser.finish()
    assert probe.calls == [] and probe.content == []
