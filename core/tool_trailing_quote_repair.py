"""Strict Zero-I/O repair for one stray quote after a JSON object."""

from __future__ import annotations

import json
from typing import cast

_WS = " \t\r\n"


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for key, value in pairs:
        if key in parsed:
            raise ValueError(f"duplicate key: {key}")
        parsed[key] = value
    return parsed


def _reject_nonstandard_constant(token: str) -> object:
    raise ValueError(f"non-standard JSON constant: {token}")


def has_single_trailing_quote_suffix(prefix: str) -> bool:
    trimmed = prefix.rstrip(_WS)
    return (
        len(trimmed) >= 2
        and trimmed[-1] == '"'
        and trimmed[:-1].rstrip(_WS).endswith("}")
    )


def strip_single_trailing_quote(text: str) -> str | None:
    if not has_single_trailing_quote_suffix(text):
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
