"""L1/L2: нечётные кавычки на EOF (`[F-18]`), литеральный `</tool_call>` и `F-FSM-I2`."""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.tool_emulation import LiveParserError, StreamNormalizer, ToolCallParser  # noqa: E402
from core.tool_json_repair import DEFAULT_MAX_ODD_CLOSE_CANDIDATES, resolve_odd_quote_tool_close  # noqa: E402
from core.tool_post_call_policy import PostCallPolicy  # noqa: E402

_REPRO_STREAM = (
    '<tool_call>{"name":"write","arguments":{"path":"a.py","content":"ok"}}</tool_call>'
    '<tool_call>{"name":"bash","arguments":{"description":"step73","command":"python3 - << \'PY\'\\n'
    'print(\\"hdr\\")\n{\n  "canary": "ok",\n  "nested": {"k": "v"}\n}\nPY"}}</tool_call>'
)
_REPRO_ODD = (
    '<tool_call>{"name": "bash", "arguments": {"description": "Odd quote", '
    '"command": "echo "hello\nPY"}}</tool_call>'
)
_REPRO_ODD_THEN_VALID = (
    _REPRO_ODD
    + '\n<tool_call>{"name": "bash", "arguments": {"description": "Second", "command": "echo ok"}}</tool_call>'
)
_REPRO_ESCAPE = (
    '<tool_call>{"name":"bash","arguments":{"command":"python3 -c \'print(\\"\\x27hi\\x27\\")\'"}}</tool_call>'
    '<tool_call>{"name":"bash","arguments":{"command":"rg \\"a\\s+b\\""}}</tool_call>'
)
_REPRO_LITERAL_CLOSE = (
    '<tool_call>{"name":"write","arguments":{"content":"s = \'{\\"a\\":1}</tool_call>\'"}}</tool_call>'
)


def _iter_chunks(text: str, mode: str) -> list[str]:
    if mode == "whole":
        return [text]
    if mode == "seeded":
        rng = random.Random(42)
        out: list[str] = []
        pos = 0
        while pos < len(text):
            step = rng.randint(1, 23)
            out.append(text[pos : pos + step])
            pos += step
        return out
    size = int(mode)
    return [text[i : i + size] for i in range(0, len(text), size)]


def _run_normalizer(raw: str, mode: str, *, repair: bool = True) -> tuple[list[dict[str, Any]], str, str]:
    norm = StreamNormalizer(strict_live=True)
    norm.configure_post_call_policy(PostCallPolicy(json_repair_enabled=repair))
    for chunk in _iter_chunks(raw, mode):
        norm.feed_text(chunk)
    norm.finish()
    return norm.tool_calls, norm.content, norm.reasoning_content


def _run_standalone_parser(raw: str, mode: str, *, repair: bool = True) -> tuple[list[dict[str, Any]], str]:
    calls: list[dict[str, Any]] = []
    content: list[str] = []
    parser = ToolCallParser(content.append, calls.append, strict_live=True)
    parser.configure_json_repair(repair)
    for chunk in _iter_chunks(raw, mode):
        parser.feed(chunk)
    parser.finish()
    return calls, "".join(content)


def test_repro_odd_single_and_odd_then_valid_in_normalizer_and_parser() -> None:
    calls, content, _ = _run_normalizer(_REPRO_ODD, "7")
    assert content == ""
    assert len(calls) == 1
    assert calls[0]["name"] == "bash"
    assert calls[0]["arguments"] == {"description": "Odd quote", "command": 'echo "hello\nPY'}

    p_calls, p_content = _run_standalone_parser(_REPRO_ODD, "7")
    assert p_content == "" and p_calls == calls

    pair_calls, _, _ = _run_normalizer(_REPRO_ODD_THEN_VALID, "7")
    assert len(pair_calls) == 2
    assert pair_calls[0]["arguments"]["command"] == 'echo "hello\nPY'
    assert pair_calls[1]["arguments"]["command"] == "echo ok"

    p_pair, _ = _run_standalone_parser(_REPRO_ODD_THEN_VALID, "7")
    assert p_pair == pair_calls


def test_odd_quote_kill_switch_off_keeps_legacy_unclosed_error() -> None:
    with pytest.raises(LiveParserError, match="unclosed tool_call block"):
        _ = _run_normalizer(_REPRO_ODD, "whole", repair=False)
    with pytest.raises(LiveParserError, match="unclosed tool_call block"):
        _ = _run_standalone_parser(_REPRO_ODD, "whole", repair=False)


def test_literal_close_tag_inside_valid_string_does_not_close_prematurely() -> None:
    calls, content, _ = _run_normalizer(_REPRO_LITERAL_CLOSE, "1")
    assert content == ""
    assert len(calls) == 1
    assert calls[0]["arguments"] == {"content": 's = \'{"a":1}</tool_call>\''}


def test_resolve_odd_quote_tool_close_strict_uniqueness_and_cap() -> None:
    ambiguous = (
        '<tool_call>{"name":"write","arguments":{"content":"x = "a"}}</tool_call>'
        '"more"}}</tool_call>'
    )
    with pytest.raises(LiveParserError, match="unclosed tool_call block"):
        _ = _run_normalizer(ambiguous, "whole", repair=True)

    two_valid = '{"a":1}</tool_call>{"b":2}</tool_call>'
    assert resolve_odd_quote_tool_close(two_valid, 0, "</tool_call>", lambda _s: {"ok": True}) == -1

    many = " ".join('{"a":1}</tool_call>' for _ in range(DEFAULT_MAX_ODD_CLOSE_CANDIDATES + 1))
    assert resolve_odd_quote_tool_close(many, 0, "</tool_call>", lambda _s: {"ok": True}) == -1


@pytest.mark.parametrize(
    ("name", "raw", "expected_count"),
    [
        ("hybrid_even", _REPRO_STREAM, 2),
        ("odd_single", _REPRO_ODD, 1),
        ("odd_plus_valid", _REPRO_ODD_THEN_VALID, 2),
        ("invalid_escapes", _REPRO_ESCAPE, 2),
        ("literal_close", _REPRO_LITERAL_CLOSE, 1),
    ],
)
def test_chunk_boundary_invariance(name: str, raw: str, expected_count: int) -> None:
    baseline = _run_normalizer(raw, "whole")
    assert len(baseline[0]) == expected_count, name
    parser_base = _run_standalone_parser(raw, "whole")
    assert parser_base[0] == baseline[0], name
    for mode in ("1", "7", "17", "seeded"):
        assert _run_normalizer(raw, mode) == baseline, f"{name} normalizer mode={mode}"
        assert _run_standalone_parser(raw, mode) == parser_base, f"{name} parser mode={mode}"


def test_truly_unclosed_block_fails_closed() -> None:
    broken = '<tool_call>{"name":"bash","arguments":{"command":"echo hi'
    with pytest.raises(LiveParserError, match="unclosed tool_call block"):
        _ = _run_normalizer(broken, "7", repair=True)
    with pytest.raises(LiveParserError, match="unclosed tool_call block"):
        _ = _run_standalone_parser(broken, "7", repair=True)


def test_odd_quote_followed_by_truncated_or_second_odd_block() -> None:
    odd_then_trunc = _REPRO_ODD + '\n<tool_call>{"name":"bash","arguments":{"command":"cut'
    with pytest.raises(LiveParserError, match="unclosed tool_call block"):
        _ = _run_standalone_parser(odd_then_trunc, "7", repair=True)
    calls_ns: list[dict[str, Any]] = []
    text_ns: list[str] = []
    p = ToolCallParser(text_ns.append, calls_ns.append, strict_live=False)
    p.configure_json_repair(True)
    p.feed(odd_then_trunc)
    p.finish()
    assert len(calls_ns) == 1 and p.has_open_tool_call() is False
    assert "<tool_call>" in "".join(text_ns)

    two_odd = _REPRO_ODD + "\n" + _REPRO_ODD
    calls2, content2 = _run_standalone_parser(two_odd, "7", repair=True)
    assert len(calls2) == 2 and content2.strip() == ""
