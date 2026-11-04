"""Unit tests for the pure reasoning FSM and its chunk-boundary invariant."""

import random

import pytest

from zen_bridge.domain.reasoning_parser import (
    ParserState,
    ReasoningFSM,
    TransitionResult,
)


TEXT = "Начало. <think>рассуждения и проверка</think>ответ."


def collect(chunks, parser=None):
    parser = parser if parser is not None else ReasoningFSM()
    results = []
    for chunk in chunks:
        results.extend(parser.feed(chunk))
    results.extend(parser.flush())
    return TransitionResult(
        content="".join(result.content for result in results),
        reasoning="".join(result.reasoning for result in results),
    )


def split_randomly(text, rng):
    chunks = []
    offset = 0
    while offset < len(text):
        size = rng.randint(1, 11)
        chunks.append(text[offset : offset + size])
        offset += size
    return chunks


def test_reasoning_fsm_basic_separation():
    result = collect(["<think>рассуждения</think>ответ"])
    assert result == TransitionResult(
        content="ответ", reasoning="рассуждения"
    )


def test_reasoning_fsm_chunk_boundary_invariance_1_byte():
    assert collect(list(TEXT)) == collect([TEXT])
    assert collect(list(TEXT)) == TransitionResult(
        content="Начало. ответ.", reasoning="рассуждения и проверка"
    )


def test_reasoning_fsm_chunk_boundary_invariance_7_bytes():
    chunks = [TEXT[index : index + 7] for index in range(0, len(TEXT), 7)]
    assert collect(chunks) == collect([TEXT])


def test_reasoning_fsm_random_chunk_splits():
    text = TEXT + "<think>ещё <think>глубже</think> мысль</think>конец<thi"
    expected = collect([text])
    rng = random.Random(2026)
    for _ in range(10):
        assert collect(split_randomly(text, rng)) == expected


def test_reasoning_fsm_no_thinking_tags():
    text = "Обычный ответ с Unicode: привет, мир!"
    assert collect(list(text)) == TransitionResult(content=text)


def test_reasoning_fsm_thinking_only_unclosed():
    parser = ReasoningFSM()
    assert parser.feed("<think>мысль</thi") == [
        TransitionResult(reasoning="мысль")
    ]
    assert parser.is_in_thinking
    assert parser.state is ParserState.IN_CLOSE_TAG
    assert parser.flush() == [TransitionResult(reasoning="</thi")]
    assert parser.state is ParserState.FINISHED
    assert not parser.is_in_thinking
    assert parser.flush() == []
    assert collect(["<think>мысль"]) == TransitionResult(reasoning="мысль")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "a<think>one</think>b<think>two</think>c",
            TransitionResult(content="abc", reasoning="onetwo"),
        ),
        (
            "a<think>one<think>two</think>three</think>b",
            TransitionResult(content="ab", reasoning="onetwothree"),
        ),
    ],
)
def test_reasoning_fsm_interleaved_or_multiple_blocks(text, expected):
    assert collect([text]) == expected
    assert collect(list(text)) == expected


def test_reasoning_fsm_reset():
    parser = ReasoningFSM()
    parser.feed("<think>старое</thi")
    parser.reset()
    assert parser.state is ParserState.OUTSIDE
    assert not parser.is_in_thinking
    assert collect(["новый ответ"], parser) == TransitionResult(
        content="новый ответ"
    )
    parser.reset()
    assert collect(["<think>новое</think>ответ"], parser) == TransitionResult(
        content="ответ", reasoning="новое"
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", TransitionResult()),
        ("abc<thi", TransitionResult(content="abc<thi")),
        ("</think>ответ", TransitionResult(content="</think>ответ")),
        ("<<think>x</think>", TransitionResult(content="<", reasoning="x")),
        (
            "<think>a</thX>b</think>c",
            TransitionResult(content="c", reasoning="a</thX>b"),
        ),
        (
            "<think>x<th",
            TransitionResult(reasoning="x<th"),
        ),
    ],
)
def test_partial_and_malformed_delimiters(text, expected):
    assert collect([text]) == expected
    assert collect(list(text)) == expected
    for boundary in range(len(text) + 1):
        assert collect([text[:boundary], "", text[boundary:]]) == expected


def test_custom_delimiters():
    text = "a[[one[[two]]three]]b["
    expected = TransitionResult(content="ab[", reasoning="onetwothree")
    assert collect([text], ReasoningFSM("[[", "]]")) == expected
    assert collect(list(text), ReasoningFSM("[[", "]]")) == expected


def test_overlapping_delimiters():
    text = "xababax"
    expected = collect([text], ReasoningFSM("ab", "aba"))
    assert collect(list(text), ReasoningFSM("ab", "aba")) == expected
    for boundary in range(len(text) + 1):
        parser = ReasoningFSM("ab", "aba")
        assert collect([text[:boundary], text[boundary:]], parser) == expected


def test_state_transitions():
    parser = ReasoningFSM()
    parser.feed("<thi")
    assert parser.state is ParserState.IN_OPEN_TAG
    assert not parser.is_in_thinking
    parser.feed("nk>")
    assert parser.state is ParserState.IN_THINKING
    assert parser.is_in_thinking
    parser.feed("</thi")
    assert parser.state is ParserState.IN_CLOSE_TAG
    assert parser.is_in_thinking
    parser.feed("nk>")
    assert parser.state is ParserState.OUTSIDE
    assert not parser.is_in_thinking


def test_feed_after_flush_requires_reset():
    parser = ReasoningFSM()
    parser.flush()
    with pytest.raises(ValueError):
        parser.feed("text")
    parser.reset()
    assert collect(["text"], parser) == TransitionResult(content="text")


@pytest.mark.parametrize(
    ("prefix", "suffix"),
    [("", "</think>"), ("<think>", ""), ("same", "same")],
)
def test_invalid_delimiters(prefix, suffix):
    with pytest.raises(ValueError):
        ReasoningFSM(prefix, suffix)
