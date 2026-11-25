"""Strict Zero-I/O repair for one stray semicolon after a JSON object."""

from __future__ import annotations

import json
from typing import cast

from core.tool_trailing_quote_repair import (
    has_single_trailing_quote_suffix,
    strip_single_trailing_quote,
)

_WS = " \t\r\n"

__all__ = [
    "has_single_trailing_quote_suffix",
    "has_single_trailing_semicolon_suffix",
    "has_single_trailing_suffix",
    "strip_single_trailing_semicolon",
    "strip_single_trailing_suffix",
]


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for key, value in pairs:
        if key in parsed:
            raise ValueError(f"duplicate key: {key}")
        parsed[key] = value
    return parsed


def _reject_nonstandard_constant(token: str) -> object:
    raise ValueError(f"non-standard JSON constant: {token}")


def has_single_trailing_semicolon_suffix(prefix: str) -> bool:
    trimmed = prefix.rstrip(_WS)
    return (
        len(trimmed) >= 2
        and trimmed[-1] == ";"
        and trimmed[:-1].rstrip(_WS).endswith("}")
    )


def strip_single_trailing_semicolon(text: str) -> str | None:
    if not has_single_trailing_semicolon_suffix(text):
        return None
    candidate = text.rstrip(_WS)[:-1]
    try:
        parsed = cast(
            "object",
            json.loads(
                candidate,
                strict=True,
                object_pairs_hook=_reject_duplicate_keys,
                parse_constant=_reject_nonstandard_constant,
            ),
        )
    except (ValueError, RecursionError):
        return None
    return candidate if isinstance(parsed, dict) else None


def has_single_trailing_suffix(prefix: str) -> bool:
    return has_single_trailing_quote_suffix(prefix) or (
        has_single_trailing_semicolon_suffix(prefix)
    )


def strip_single_trailing_suffix(text: str) -> str | None:
    if has_single_trailing_quote_suffix(text):
        return strip_single_trailing_quote(text)
    if has_single_trailing_semicolon_suffix(text):
        return strip_single_trailing_semicolon(text)
    return None
