"""L1 unit tests for the trailing-semicolon Zero-I/O repair module."""

from __future__ import annotations

from core.tool_trailing_semicolon_repair import (
    has_single_trailing_semicolon_suffix,
    has_single_trailing_suffix,
    strip_single_trailing_semicolon,
    strip_single_trailing_suffix,
)

TOOL_CALL = '{"name":"read","arguments":{"limit":200,"offset":1}}'


def test_positive_basic_semicolon() -> None:
    assert has_single_trailing_semicolon_suffix(TOOL_CALL + ";")
    assert strip_single_trailing_semicolon(TOOL_CALL + ";") == TOOL_CALL


def test_positive_whitespace_between_brace_and_semicolon() -> None:
    for gap in (" ", "\t", "\r\n", " \n "):
        assert strip_single_trailing_semicolon(TOOL_CALL + gap + ";") == (
            TOOL_CALL + gap
        )


def test_positive_whitespace_after_semicolon() -> None:
    assert strip_single_trailing_semicolon(TOOL_CALL + "; \n\t") == TOOL_CALL


def test_positive_escaped_newline_inside_string() -> None:
    text = '{"name":"say","arguments":{"text":"line\\nbreak"}};'
    assert strip_single_trailing_semicolon(text) == (
        '{"name":"say","arguments":{"text":"line\\nbreak"}}'
    )


def test_dispatcher_quote_suffix() -> None:
    quoted = TOOL_CALL + '"'
    assert has_single_trailing_suffix(quoted)
    assert not has_single_trailing_semicolon_suffix(quoted)
    assert strip_single_trailing_suffix(quoted) == TOOL_CALL


def test_dispatcher_semicolon_suffix() -> None:
    suffixed = TOOL_CALL + ";"
    assert has_single_trailing_suffix(suffixed)
    assert strip_single_trailing_suffix(suffixed) == TOOL_CALL


def test_dispatcher_mutual_exclusion() -> None:
    from core.tool_trailing_semicolon_repair import (
        has_single_trailing_quote_suffix,
    )

    quote = TOOL_CALL + '"'
    semicolon = TOOL_CALL + ";"
    assert has_single_trailing_quote_suffix(quote)
    assert not has_single_trailing_semicolon_suffix(quote)
    assert not has_single_trailing_quote_suffix(semicolon)
    assert has_single_trailing_semicolon_suffix(semicolon)


def test_negative_empty_and_lone_semicolon() -> None:
    assert not has_single_trailing_semicolon_suffix("")
    assert strip_single_trailing_semicolon(";") is None
    assert strip_single_trailing_semicolon("") is None


def test_negative_no_suffix() -> None:
    assert not has_single_trailing_semicolon_suffix(TOOL_CALL)
    assert not has_single_trailing_suffix(TOOL_CALL)
    assert strip_single_trailing_suffix(TOOL_CALL) is None


def test_negative_double_semicolon_and_garbage() -> None:
    assert strip_single_trailing_semicolon('{"a":1};;') is None
    assert strip_single_trailing_semicolon('{"a":1}; garbage') is None


def test_negative_non_dict_top_level() -> None:
    assert strip_single_trailing_semicolon("[1,2];") is None


def test_negative_duplicate_keys() -> None:
    assert strip_single_trailing_semicolon('{"a":1,"a":2};') is None
    assert strip_single_trailing_semicolon('{"a":{"x":1,"x":2}};') is None


def test_negative_nonstandard_constants() -> None:
    assert strip_single_trailing_semicolon('{"a":NaN};') is None
    assert strip_single_trailing_semicolon('{"a":Infinity};') is None
    assert strip_single_trailing_semicolon('{"a":-Infinity};') is None


def test_negative_raw_newline_in_string() -> None:
    assert strip_single_trailing_semicolon('{"a":"line\nbreak"};') is None


def test_negative_invalid_escapes_and_trailing_comma() -> None:
    assert strip_single_trailing_semicolon('{"a":"\\q"};') is None
    assert strip_single_trailing_semicolon('{"a":1,};') is None


def test_negative_extra_braces() -> None:
    assert strip_single_trailing_semicolon('{"a":1}}};') is None


def test_negative_mixed_quote_and_semicolon_suffixes() -> None:
    assert strip_single_trailing_semicolon('{"a":1}";') is None
    assert strip_single_trailing_semicolon('{"a":1};"') is None
    assert not has_single_trailing_suffix('{"a":1}";')


def test_negative_non_rfc8259_whitespace() -> None:
    assert strip_single_trailing_semicolon('{"a":1}\xa0;') is None
    assert strip_single_trailing_semicolon('{"a":1};\xa0') is None
    assert not has_single_trailing_semicolon_suffix('{"a":1}\xa0;')
    assert not has_single_trailing_suffix('{"a":1}\xa0;')
