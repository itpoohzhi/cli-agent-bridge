"""Существующие оракулы passthrough, выделенные для сохранения границ legacy."""

from __future__ import annotations

from adapters.passthrough_adapter import PassthroughLimits
from adapters.passthrough_adapter import relay_sse
from typing import Any
import io
import json


STR = {"type": "string"}

SCHEMAS = {
    "subagent": {
        "type": "function",
        "function": {
            "name": "subagent",
            "parameters": {
                "type": "object",
                "properties": {"prompt": STR, "provider": STR, "note": STR},
                "required": ["prompt"],
            },
        },
    }
}

TOOLS = list(SCHEMAS.values())

DONE = b"data: [DONE]\n\n"


def frame(payload: Any) -> bytes:
    return b"data: " + json.dumps(payload).encode("utf-8") + b"\n\n"


def chunk(choices: Any, **extra: Any) -> dict:
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "m",
        "choices": choices,
        **extra,
    }


def content(text: str, index: int = 0) -> bytes:
    return frame(
        chunk([{"index": index, "delta": {"content": text}, "finish_reason": None}])
    )


def tool_delta(
    index: int,
    tc_index: int,
    *,
    call_id: Any = None,
    name: Any = None,
    args: Any = None,
) -> bytes:
    delta: dict = {"index": tc_index}
    if call_id is not None:
        delta["id"] = call_id
        delta["type"] = "function"
    function: dict = {}
    if name is not None:
        function["name"] = name
    if args is not None:
        function["arguments"] = args
    if function:
        delta["function"] = function
    return frame(
        chunk(
            [{"index": index, "delta": {"tool_calls": [delta]}, "finish_reason": None}]
        )
    )


def finish(index: int, reason: str = "tool_calls", **extra: Any) -> bytes:
    return frame(
        chunk([{"index": index, "delta": {}, "finish_reason": reason}], **extra)
    )


def run_stream(
    events: bytes, limits: Any = None, schemas: Any = None, **kwargs: Any
) -> Any:
    out: list = []
    outcome = relay_sse(
        io.BytesIO(events).readline,
        out.append,
        tool_schemas=schemas if schemas is not None else SCHEMAS,
        limits=limits or PassthroughLimits(),
        **kwargs,
    )
    return (outcome, out)


def payloads(frames: Any) -> list:
    """Разобранные data-кадры (без [DONE])."""
    parsed = []
    for raw in b"".join(frames).split(b"\n\n"):
        text = raw.decode("utf-8").strip()
        if text.startswith("data:") and text[5:].strip() != "[DONE]":
            parsed.append(json.loads(text[5:]))
    return parsed


def published_calls(frames: Any, choice: int = 0) -> list:
    calls = []
    for item in payloads(frames):
        for ch in item.get("choices") or ():
            if ch.get("index") == choice:
                calls.extend((ch.get("delta") or {}).get("tool_calls") or ())
    return calls


def args_of(call: Any) -> dict:
    return json.loads(call["function"]["arguments"])
