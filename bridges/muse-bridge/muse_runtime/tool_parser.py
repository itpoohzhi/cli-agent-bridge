"""Парсинг и санитизация блоков вызова инструментов <tool_call>."""

from __future__ import annotations

import json
import uuid
from typing import Callable

from core.tool_emulation import (
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
    "max_name_len": 64,
    "max_args_len": 32768,
    "max_calls": 32,
    "max_depth": 16,
}


def _split_tool_calls(
    chunks: list[str],
    tool_schemas: list[dict] | None = None,
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

    parser = ToolCallParser(pieces.append, add_call)
    for chunk in chunks:
        parser.feed(chunk)
    parser.finish()
    if sanitize_func is not None and tool_schemas is not None:
        calls = sanitize_func(calls, tool_schemas, **_SANITIZE_LIMITS)
    return "".join(pieces), calls
