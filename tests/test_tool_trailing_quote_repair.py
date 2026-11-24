"""Regression coverage for strict single trailing-quote tool-call recovery."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.tool_block_parsing import loads_tolerant_json  # noqa: E402
from core.tool_emulation import LiveParserError, StreamNormalizer, ToolCallParser  # noqa: E402
from core.tool_json_repair import (  # noqa: E402
    ActiveBlockScanner,
    DEFAULT_MAX_ODD_CLOSE_CANDIDATES,
    resolve_odd_quote_tool_close,
)
from core.tool_post_call_policy import PostCallPolicy  # noqa: E402
from core.tool_trailing_quote_repair import (  # noqa: E402
    has_single_trailing_quote_suffix,
    strip_single_trailing_quote,
)

_CLOSE = "</tool_call>"
_FIVE_BLOCKS = (
    '<tool_call>{"name":"read","arguments":{"path":"alpha.txt"}}</tool_call>'
    '<tool_call>{"name":"read","arguments":{"path":"beta.txt"}}</tool_call>'
    '<tool_call>{"name":"read","arguments":{"path":"gamma.txt"}}</tool_call>'
    '<tool_call>{"name":"job_list","arguments":{}}</tool_call>'
    '<tool_call>{"name":"bash","arguments":{"command":"printf ok"}}"</tool_call>'
)
_EXPECTED = [
    ("read", {"path": "alpha.txt"}),
    ("read", {"path": "beta.txt"}),
    ("read", {"path": "gamma.txt"}),
    ("job_list", {}),
    ("bash", {"command": "printf ok"}),
]


def _chunks(text: str, size: int | None) -> list[str]:
    if size is None:
        return [text]
    return [text[pos : pos + size] for pos in range(0, len(text), size)]


def _run_normalizer(raw: str, size: int | None, *, repair: bool = True) -> list[dict]:
    normalizer = StreamNormalizer(strict_live=True)
    normalizer.configure_post_call_policy(PostCallPolicy(json_repair_enabled=repair))
    for chunk in _chunks(raw, size):
        normalizer.feed_text(chunk)
    normalizer.finish()
    return normalizer.tool_calls


def _snapshot(calls: list[dict]) -> list[tuple[str, object]]:
    return [(str(call["name"]), call["arguments"]) for call in calls]


def test_leaf_suffix_and_valid_dict_repair() -> None:
    assert has_single_trailing_quote_suffix('{"a":1}"')
    assert strip_single_trailing_quote('{"a":1}"') == '{"a":1}'
    spaced = '{"a":"x\\n","b":"\\u0041"}   " \r\n'
    assert has_single_trailing_quote_suffix(spaced)
    assert strip_single_trailing_quote(spaced) == '{"a":"x\\n","b":"\\u0041"}   '


@pytest.mark.parametrize(
    "raw",
    [
        "",
        '{"a":',
        '{"a":1}""',
        '[1,2]"',
        '{"a":1,"a":2}"',
        '{"a":NaN}"',
        '{"a":Infinity}"',
        '{"a":-Infinity}"',
        '{"a":"line\nbreak"}"',
        '{"a":1}```"',
        '{"a":1}~~~"',
    ],
)
def test_leaf_rejects_non_single_or_non_strict_inputs(raw: str) -> None:
    assert strip_single_trailing_quote(raw) is None


def test_leaf_suffix_does_not_strip_fences_or_non_dicts() -> None:
    assert not has_single_trailing_quote_suffix('[1,2]"')
    assert not has_single_trailing_quote_suffix('{"a":1}```"')
    assert not has_single_trailing_quote_suffix('{"a":1}~~~"')


def test_ground_truth_five_blocks_recovered_once_in_order() -> None:
    assert _snapshot(_run_normalizer(_FIVE_BLOCKS, None)) == _EXPECTED


@pytest.mark.parametrize("size", [None, 1, 17, 64, 257])
def test_chunk_invariance_five_blocks(size: int | None) -> None:
    assert _snapshot(_run_normalizer(_FIVE_BLOCKS, size)) == _EXPECTED


def test_active_scanner_and_tool_call_parser_recover_at_eof() -> None:
    inner = '{"name":"bash","arguments":{"command":"printf ok"}}"'
    scanner = ActiveBlockScanner()
    assert scanner.feed(inner + _CLOSE + "tail") == (None, "")
    recovered = scanner.recover_odd_close(
        lambda raw: loads_tolerant_json(raw, json_repair_enabled=True)
    )
    assert recovered == (inner, "tail")

    calls: list[dict] = []
    parser = ToolCallParser(lambda _text: None, calls.append, strict_live=True)
    parser.configure_json_repair(True)
    parser.feed("<tool_call>" + inner + _CLOSE)
    parser.finish()
    assert _snapshot(calls) == [("bash", {"command": "printf ok"})]


def test_between_blocks_recovers_both_calls() -> None:
    raw = (
        '<tool_call>{"name":"read","arguments":{"path":"first"}}"</tool_call>'
        '<tool_call>{"name":"bash","arguments":{"command":"printf second"}}</tool_call>'
    )
    assert _snapshot(_run_normalizer(raw, 17)) == [
        ("read", {"path": "first"}),
        ("bash", {"command": "printf second"}),
    ]


@pytest.mark.parametrize(
    "raw",
    [
        r'{"name":"bash","arguments":{"command":"echo \q"}}"',
        '{"name":"bash","arguments":{"command":"echo "bad""}}"',
        '```json\n{"name":"bash","arguments":{"command":"echo ok"}}\n```"',
        '{"name":"bash","arguments":{"command":NaN}}"',
    ],
)
def test_negative_multi_corruption_fails_without_over_repair(raw: str) -> None:
    with pytest.raises(ValueError):
        loads_tolerant_json(raw, json_repair_enabled=True)
    with pytest.raises(LiveParserError):
        _run_normalizer("<tool_call>" + raw + _CLOSE, None)


def test_disabled_flag_parity_fails_closed() -> None:
    raw = '{"name":"bash","arguments":{"command":"printf ok"}}"'
    with pytest.raises(ValueError):
        loads_tolerant_json(raw, json_repair_enabled=False)
    with pytest.raises(LiveParserError, match="unclosed tool_call block"):
        _run_normalizer("<tool_call>" + raw + _CLOSE, None, repair=False)


def test_ambiguity_and_cap_still_fail_closed() -> None:
    parse = lambda _raw: {"ok": True}  # noqa: E731
    ambiguous = '{"a":1}"</tool_call>{"b":2}"</tool_call>'
    assert resolve_odd_quote_tool_close(ambiguous, 0, _CLOSE, parse) == -1
    many = "".join(
        '{"a":1}"</tool_call>' for _ in range(DEFAULT_MAX_ODD_CLOSE_CANDIDATES + 1)
    )
    assert resolve_odd_quote_tool_close(many, 0, _CLOSE, parse) == -1
