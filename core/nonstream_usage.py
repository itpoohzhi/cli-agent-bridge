"""Pure helpers for extracting usage from raw SSE chunks (W1).

No I/O, no core.* imports, no model-name branches.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


def extract_usage(chunk: Mapping[str, Any]) -> dict[str, Any] | None:
    """Extract usage dict from chunk.

    Priority: top-level ``usage`` dict over ``choices[].usage``.
    Returns None when no valid usage dict is found (fail-open).
    Does not mutate input.
    """
    top = chunk.get("usage")
    if isinstance(top, dict):
        return top
    choices = chunk.get("choices")
    if not isinstance(choices, list):
        return None
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        usage = choice.get("usage")
        if isinstance(usage, dict):
            return usage
    return None


def internal_usage_injected(request_body: bytes, internal_body: bytes | None) -> bool:
    """Return True when *internal_body* added ``stream_options.include_usage=True``
    that the client did not already send in *request_body*.

    Fail-safe: returns False on any parse error or missing data.
    """
    if internal_body is None:
        return False
    try:
        internal = json.loads(internal_body)
        request = json.loads(request_body)
    except (ValueError, TypeError):
        return False
    if not isinstance(internal, dict) or not isinstance(request, dict):
        return False
    int_opts = internal.get("stream_options")
    if not isinstance(int_opts, dict) or int_opts.get("include_usage") is not True:
        return False
    req_opts = request.get("stream_options")
    if isinstance(req_opts, dict) and req_opts.get("include_usage") is True:
        return False
    return True
