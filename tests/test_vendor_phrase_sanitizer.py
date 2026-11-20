"""L1: маскирование вендорной фразы `Retries remaining: N` (AD-006, VER-008)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.vendor_phrase_sanitizer import DEFAULT_PATTERNS, mask_vendor_phrases  # noqa: E402

_MALFORMED = (
    "Your previous response contained an improperly formatted function call: Malformed function "
    "call: Failed to parse function call: Function call is empty - no input to parse. "
    "Please retry with a properly formatted function call Retries remaining: 3"
)


def test_default_pattern_is_documented_regex() -> None:
    assert DEFAULT_PATTERNS == (r"Retries remaining:\s*\d+",)


def test_masks_phrase_and_keeps_diagnostics() -> None:
    out = mask_vendor_phrases(_MALFORMED)
    assert "Retries remaining" not in out
    assert "Malformed function call: Failed to parse function call" in out
    assert out.endswith("properly formatted function call")


@pytest.mark.parametrize(
    "text",
    ["Retries remaining: 3", "retries remaining:7", "RETRIES REMAINING:   12", "x Retries remaining:\t0 y"],
)
def test_phrase_variants_are_masked(text: str) -> None:
    assert "retries" not in mask_vendor_phrases(text).lower()


@pytest.mark.parametrize("text", [_MALFORMED, "Retries remaining: 3\nRetries remaining: 2", "a  Retries remaining: 1  b"])
def test_masking_is_idempotent(text: str) -> None:
    once = mask_vendor_phrases(text)
    assert mask_vendor_phrases(once) == once


def test_multiple_occurrences_are_all_masked() -> None:
    out = mask_vendor_phrases("A Retries remaining: 3 B Retries remaining: 2 C")
    assert "Retries" not in out
    assert out.startswith("A ") and out.endswith(" C")


@pytest.mark.parametrize("value", [None, "", 0, [], {}, b"Retries remaining: 3", 3.5])
def test_non_text_and_empty_inputs_yield_empty_string(value: object) -> None:
    assert mask_vendor_phrases(value) == ""


def test_text_without_phrase_is_returned_unchanged_including_whitespace() -> None:
    text = "plain error with trailing space  \n"
    assert mask_vendor_phrases(text) == text


def test_long_text_is_masked_without_truncation() -> None:
    text = ("lorem ipsum " * 20000) + "Retries remaining: 3"
    out = mask_vendor_phrases(text)
    assert "Retries remaining" not in out
    assert out.startswith("lorem ipsum") and len(out) >= len("lorem ipsum " * 20000) - 1


def test_custom_patterns_and_replacement_are_configurable() -> None:
    out = mask_vendor_phrases("vendor-id=ABC123 failed", (r"vendor-id=\w+",), "[masked]")
    assert out == "[masked] failed"


def test_invalid_pattern_is_skipped_and_valid_ones_still_apply() -> None:
    out = mask_vendor_phrases("x Retries remaining: 3", ("(unclosed", *DEFAULT_PATTERNS))
    assert "Retries" not in out


def test_empty_patterns_leave_text_untouched() -> None:
    assert mask_vendor_phrases(_MALFORMED, ()) == _MALFORMED


def test_input_text_is_not_mutated_for_parser_path() -> None:
    """Санитайзер возвращает новую строку; исходный текст (вход парсера) не меняется."""
    original = _MALFORMED
    _ = mask_vendor_phrases(original)
    assert "Retries remaining: 3" in original
