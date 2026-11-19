"""Парсинг и санитизация блоков вызова инструментов <tool_call>."""

from __future__ import annotations

import inspect
import json
import uuid
from collections.abc import Mapping
from typing import Any, Callable

from core.runtime_env import synthesize_required_bash_desc_enabled
from core.tool_emulation import (
    DEFAULT_MAX_PARALLEL_CALLS,
    DEFAULT_MAX_PARALLEL_DEPTH,
    TOOL_CALL_CLOSE,
    TOOL_CALL_OPEN,
    ToolCallParser,
    _loads_tolerant,
    _parse_tool_call_block,
    _parse_tool_call_blocks,
    _recover_trailing_braces,
    _split_tool_call_inner,
    _strip_code_fence,
)

__all__ = [
    "TOOL_CALL_CLOSE",
    "TOOL_CALL_OPEN",
    "ToolCallParser",
    "_loads_tolerant",
    "_parse_tool_call_block",
    "_parse_tool_call_blocks",
    "_recover_trailing_braces",
    "_split_tool_call_inner",
    "_split_tool_calls",
    "_strip_code_fence",
]

_SANITIZE_LIMITS = {
    "max_parallel_calls": DEFAULT_MAX_PARALLEL_CALLS,
    "max_parallel_depth": DEFAULT_MAX_PARALLEL_DEPTH,
}


def _split_tool_calls(
    chunks: list[str],
    tool_schemas: Mapping[str, Any] | None = None,
    sanitize_func: Callable[..., list[dict]] | None = None,
) -> tuple[str, list[dict]]:
    """Собирает чанки, извлекает tool_calls и форматирует их в OpenAI-схему."""
    pieces: list[str] = []
    calls: list[dict] = []

    def add_call(call: dict) -> None:
        calls.append(
            {
                "index": len(calls),
                "id": "call_" + uuid.uuid4().hex[:24],
                "type": "function",
                "function": {
                    "name": call["name"],
                    "arguments": json.dumps(call["arguments"], ensure_ascii=False),
                },
            }
        )

    parser = ToolCallParser(pieces.append, add_call, tool_schemas=tool_schemas)
    for chunk in chunks:
        parser.feed(chunk)
    parser.finish()
    if sanitize_func is not None and tool_schemas is not None:
        kwargs: dict[str, Any] = dict(_SANITIZE_LIMITS)
        if "synthesize_required_description" in inspect.signature(sanitize_func).parameters:
            kwargs["synthesize_required_description"] = synthesize_required_bash_desc_enabled()
        calls = sanitize_func(calls, tool_schemas, **kwargs)
    return "".join(pieces), calls
