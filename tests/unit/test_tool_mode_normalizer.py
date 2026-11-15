"""VER-001: потоковые каналы, EOF и инвариантность разбиения tool-mode."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

import core.tool_emulation as emulation
from tests.unit.test_tool_mode import MODE_CASES, VALID_CALL, _api


def _normalizer(
    mode: str, policy: str = "TEXT", *, strict_live: bool = True
) -> tuple[Any, list, list, list]:
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
    normalizer = emulation.StreamNormalizer.for_mode(spec, sinks, strict_live=strict_live)
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


@pytest.mark.parametrize("use_factory", (False, True))
def test_strict_live_rejects_unclosed_named_call_before_parser_recovery(
    use_factory: bool,
) -> None:
    norm = (
        _normalizer("EMULATE")[0]
        if use_factory
        else emulation.StreamNormalizer(strict_live=True)
    )
    norm.feed_text('<tool_call>{"name":"noop"')
    with patch.object(norm._parser, "feed", wraps=norm._parser.feed) as feed:
        with pytest.raises(emulation.LiveParserError, match="unclosed tool_call block"):
            norm.finish()
    feed.assert_not_called()
    assert norm._state == "tool"
    assert norm.content == ""
    assert norm.tool_calls == []


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


@pytest.mark.parametrize("mode", ("FORBID", "OFF"))
def test_html_and_gfm_tags_pass_strict_modes(mode: str) -> None:
    """RW-004: дочерние payload-теги и GFM-HTML — обычный текст, не вызов инструмента."""
    text = "git <command> <parameter>\n\n<details><summary>Overview</summary></details>"
    norm, content, _, calls = _normalizer(mode, "ERROR" if mode == "OFF" else "TEXT")
    _feed_chars(norm, text)
    norm.finish()
    assert "".join(content) == text
    assert not calls


@pytest.mark.parametrize("mode", ("FORBID", "OFF"))
def test_single_trailing_lt_is_content_at_eof(mode: str) -> None:
    """RW-004: одиночный `<` в конце потока — текст, а не оборванный префикс тега."""
    norm, content, _, calls = _normalizer(mode, "ERROR" if mode == "OFF" else "TEXT")
    _feed_chars(norm, "1 <")
    norm.finish()
    assert "".join(content) == "1 <"
    assert not calls


@pytest.mark.parametrize("mode", ("FORBID", "OFF"))
@pytest.mark.parametrize(
    "text",
    ('<invoke name="bash">{"cmd":"ls"}</invoke>', "<execute>ls -la</execute>"),
)
@pytest.mark.parametrize("strict_live", (True, False))
def test_tool_envelopes_rejected_in_strict_modes(
    mode: str, text: str, strict_live: bool
) -> None:
    """RW-003/RW-004: внешние tool-конверты отклоняются fail-closed при любой нарезке."""
    norm, content, _, calls = _normalizer(
        mode, "ERROR" if mode == "OFF" else "TEXT", strict_live=strict_live
    )
    with pytest.raises(emulation.LiveParserError):
        _feed_chars(norm, text)
    assert norm._state == "text"
    assert not content and not calls


ENVELOPES = (
    '<invoke\nname="bash">secret</invoke>',
    '<invoke\tname="bash">secret</invoke>',
    "<invoke/>",
    '<INVOKE name="x">secret</INVOKE>',
    '<antml:invoke name="x">secret</antml:invoke>',
    "<execute\n>cmd</execute>",
)
STRICT_REJECT_MODES = (
    ("FORBID", "TEXT"),
    ("FORBID", "ERROR"),
    ("OFF", "ERROR"),
)
FENCED_ENVELOPE = '```xml\n<invoke\nname="x"/>\n```\n'


@pytest.mark.parametrize("mode,policy", STRICT_REJECT_MODES)
@pytest.mark.parametrize("text", ENVELOPES)
@pytest.mark.parametrize("width", (1, 7, 1000))
def test_rejected_envelopes_fail_closed_with_zero_leak(
    mode: str, policy: str, text: str, width: int
) -> None:
    """F-001.1/F-001.3: перенос, таб, `/>`, регистр и antml-форма — один и тот же отказ."""
    norm, content, _, calls = _normalizer(mode, policy)
    with pytest.raises(emulation.LiveParserError):
        for index in range(0, len(text), width):
            norm.feed_text(text[index : index + width])
        norm.finish()
    assert norm._state == "text"
    assert not content and norm.content == "" and not calls


@pytest.mark.parametrize("mode,policy", STRICT_REJECT_MODES)
@pytest.mark.parametrize("width", (1, 1000))
def test_tag_names_outside_envelope_boundary_stay_text(
    mode: str, policy: str, width: int
) -> None:
    """`<invoker>`: после стема идёт `r`, а не разделитель — обычный текст."""
    text = "<invoker>ok</invoker>"
    norm, content, _, calls = _normalizer(mode, policy)
    for index in range(0, len(text), width):
        norm.feed_text(text[index : index + width])
    norm.finish()
    assert "".join(content) == text
    assert not calls


@pytest.mark.parametrize("mode,policy", MODE_CASES)
@pytest.mark.parametrize("width", (1, 1000))
def test_fenced_envelope_literal_is_lossless_in_every_mode(
    mode: str, policy: str, width: int
) -> None:
    """Markdown-код литерален: конверт в блоке ```xml не отклоняется и не теряется."""
    norm, content, _, calls = _normalizer(mode, policy)
    for index in range(0, len(FENCED_ENVELOPE), width):
        norm.feed_text(FENCED_ENVELOPE[index : index + width])
    norm.finish()
    assert "".join(content) == FENCED_ENVELOPE
    assert norm.content == FENCED_ENVELOPE
    assert not calls


@pytest.mark.parametrize("text", ('<invoke name="x">secret</invoke>', "<antml:invoke/>"))
def test_emulate_strict_rejects_bare_envelope_outside_tool_call(text: str) -> None:
    norm, content, _, calls = _normalizer("EMULATE", strict_live=True)
    with pytest.raises(emulation.LiveParserError):
        _feed_chars(norm, text)
        norm.finish()
    assert norm.content == "" and not content and not calls


def test_emulate_strict_still_extracts_call_inside_tool_call_block() -> None:
    norm, content, _, calls = _normalizer("EMULATE", strict_live=True)
    _feed_chars(norm, VALID_CALL)
    norm.finish()
    assert norm.content == "" and not content
    assert [call["name"] for call in calls] == ["noop"]


def test_off_text_keeps_envelope_literal_without_strict_live() -> None:
    text = '<invoke name="x">secret</invoke>'
    norm, content, _, calls = _normalizer("OFF", "TEXT", strict_live=False)
    _feed_chars(norm, text)
    norm.finish()
    assert "".join(content) == text
    assert not calls


@pytest.mark.parametrize("mode,policy", (("FORBID", "TEXT"), ("OFF", "ERROR")))
def test_truncated_html_close_flushes_as_content_at_eof(mode: str, policy: str) -> None:
    """Обрезанный `</` (например, по max_tokens) — текст, а не оборванный тег."""
    norm, content, _, calls = _normalizer(mode, policy)
    _feed_chars(norm, "<div>hi</")
    norm.finish()
    assert "".join(content) == "<div>hi</"
    assert norm.content == "<div>hi</" and not calls


@pytest.mark.parametrize("mode,policy", (("FORBID", "TEXT"), ("OFF", "ERROR")))
@pytest.mark.parametrize("tail", ("<t", "<i", "<e", "</t", "<IN", "</antml:in", "<invoke"))
def test_held_tag_prefixes_still_raise_at_eof(mode: str, policy: str, tail: str) -> None:
    norm, content, _, calls = _normalizer(mode, policy)
    _feed_chars(norm, tail)
    assert norm._state == "text" and not content
    with pytest.raises(emulation.LiveParserError):
        norm.finish()
    assert not content and not calls
