"""VER-001: потоковые каналы, EOF и инвариантность разбиения tool-mode."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

import core.tool_emulation as emulation
from tests.unit.test_tool_mode import MODE_CASES, VALID_CALL, _api


def _normalizer(mode: str, policy: str = "TEXT") -> tuple[Any, list, list, list]:
    api = _api()
    content: list[str] = []
    reasoning: list[str] = []
    calls: list[dict[str, Any]] = []
    sinks = api.NormalizerSinks(
        on_content=content.append,
        on_reasoning=reasoning.append,
        on_tool_call=calls.append,
    )
    spec = api.build_mode_spec(
        getattr(api.ToolMode, mode), getattr(api.ToollessTagPolicy, policy)
    )
    normalizer = emulation.StreamNormalizer.for_mode(spec, sinks, strict_live=True)
    return normalizer, content, reasoning, calls


def _feed_chars(normalizer: Any, text: str) -> None:
    for char in text:
        normalizer.feed_text(char)


def test_off_text_never_constructs_tool_parser_and_emits_before_close() -> None:
    with patch.object(
        emulation,
        "ToolCallParser",
        side_effect=AssertionError("OFF must not parse tools"),
    ) as spy:
        norm, content, reasoning, calls = _normalizer("OFF")
        assert norm._parser is None
        _feed_chars(norm, 'P1 <tool_call>{"name":"noop"}')
        assert "".join(content).startswith("P1 ")
        _feed_chars(norm, "</tool_call> P2")
        norm.finish()
    spy.assert_not_called()
    assert "".join(content) == 'P1 <tool_call>{"name":"noop"}</tool_call> P2'
    assert norm.content == "".join(content)
    assert not calls and not reasoning


@pytest.mark.parametrize(
    "text",
    (
        VALID_CALL,
        "<invoke>",
        "<execute>",
        "</tool_call>",
        "<tool_call>{",
        "<t",
        "<tool_c",
        "<th",
    ),
)
@pytest.mark.parametrize("width", (1, 7, 1000))
def test_off_text_is_lossless_for_literals_and_eof_prefixes(
    text: str, width: int
) -> None:
    norm, content, _, calls = _normalizer("OFF")
    for index in range(0, len(text), width):
        norm.feed_text(text[index : index + width])
    norm.finish()
    assert "".join(content) == text
    assert norm.content == text
    assert not calls and not norm.tool_calls


@pytest.mark.parametrize("mode", ("FORBID", "OFF"))
@pytest.mark.parametrize("tail", ("<t", "<tool_c", "</t", "<i", "<e"))
def test_strict_modes_reject_one_char_split_tool_prefix_at_eof(
    mode: str, tail: str
) -> None:
    norm, content, _, calls = _normalizer(mode, "ERROR" if mode == "OFF" else "TEXT")
    _feed_chars(norm, tail)
    assert norm._state == "text", "S_PREFIX_HOLD must be distinguished from S_TOOL_GATE"
    assert not content and not calls
    with pytest.raises(emulation.LiveParserError):
        norm.finish()
    assert not content and not calls


@pytest.mark.parametrize("mode", ("FORBID", "OFF"))
@pytest.mark.parametrize(
    "text", ('<tool_call>{"name":', VALID_CALL, "<invoke>", "<execute>", "</tool_call>")
)
def test_strict_modes_reject_tool_blocks_without_leaking(mode: str, text: str) -> None:
    norm, content, _, calls = _normalizer(mode, "ERROR" if mode == "OFF" else "TEXT")
    with pytest.raises(emulation.LiveParserError):
        _feed_chars(norm, text)
        norm.finish()
    assert not content and not calls


@pytest.mark.parametrize("mode,policy", MODE_CASES)
def test_non_tool_prefix_th_is_flushed_safely(mode: str, policy: str) -> None:
    norm, content, _, calls = _normalizer(mode, policy)
    _feed_chars(norm, "<th")
    assert norm._state == "text"
    norm.finish()
    assert "".join(content) == "<th"
    assert not calls


@pytest.mark.parametrize(
    "use_factory", (False, True), ids=("legacy-default", "for-mode")
)
@pytest.mark.parametrize("tail", ("<th", "<tool_c", "<t"))
def test_emulate_flushes_unentered_prefix_hold(use_factory: bool, tail: str) -> None:
    content: list[str] = []
    norm = (
        _normalizer("EMULATE")[0]
        if use_factory
        else emulation.StreamNormalizer(on_content=content.append)
    )
    _feed_chars(norm, tail)
    assert norm._state == "text"
    norm.finish()
    assert norm.content == tail
    if not use_factory:
        assert "".join(content) == tail


@pytest.mark.parametrize(
    "use_factory", (False, True), ids=("legacy-default", "for-mode")
)
def test_emulate_rejects_open_tool_gate(use_factory: bool) -> None:
    norm = _normalizer("EMULATE")[0] if use_factory else emulation.StreamNormalizer()
    _feed_chars(norm, '<tool_call>{"name":')
    assert norm._state == "tool"
    with pytest.raises(emulation.LiveParserError):
        norm.finish()
    assert norm.content == "" and not norm.tool_calls


@pytest.mark.parametrize("mode,policy", MODE_CASES)
@pytest.mark.parametrize("tag", emulation.REASONING_TAGS)
def test_reasoning_is_incremental_and_isolates_tool_literals(
    mode: str, policy: str, tag: str
) -> None:
    norm, content, reasoning, calls = _normalizer(mode, policy)
    norm.feed_text(f"<{tag}>thinking")
    assert "".join(reasoning) == "thinking"
    _feed_chars(norm, f" {VALID_CALL}</{tag}>answer")
    norm.finish()
    assert "".join(reasoning) == f"thinking {VALID_CALL}"
    assert norm.reasoning_content == "".join(reasoning)
    assert "".join(content) == "answer"
    assert not calls


@pytest.mark.parametrize("mode,policy", MODE_CASES)
def test_native_thinking_never_enters_tool_or_text_parser(
    mode: str, policy: str
) -> None:
    norm, content, reasoning, calls = _normalizer(mode, policy)
    text = f"native {VALID_CALL} <invoke> <t"
    _feed_chars(norm, "answer")
    norm.feed_thinking(text)
    norm.finish()
    assert "".join(content) == "answer"
    assert "".join(reasoning) == text
    assert not calls


@pytest.mark.parametrize("mode,policy", MODE_CASES)
def test_markdown_fences_preserve_literal_markup(mode: str, policy: str) -> None:
    norm, content, reasoning, calls = _normalizer(mode, policy)
    text = f"```xml\n{VALID_CALL}\n```\n"
    _feed_chars(norm, text)
    norm.finish()
    assert "".join(content) == text
    assert not reasoning and not calls


@pytest.mark.parametrize("policy", ("TEXT", "ERROR"))
def test_emulate_still_extracts_valid_tool_call(policy: str) -> None:
    norm, content, _, calls = _normalizer("EMULATE", policy)
    _feed_chars(norm, VALID_CALL)
    norm.finish()
    assert not content
    assert len(calls) == 1
    assert calls[0]["name"] == "noop" and calls[0]["arguments"] == {}
    assert norm.tool_calls == calls
