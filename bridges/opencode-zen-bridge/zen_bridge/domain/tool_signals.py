"""Парсинг событий инструментов opencode и валидация тегов вызова."""

from __future__ import annotations

import json
from typing import Any


def _dict_or_empty(val: object) -> dict[str, Any]:
    return dict(val) if isinstance(val, dict) else {}


def _tools_section(
    tools: list[Any],
    tool_choice: Any,
    model_id: str = "",
    tool_tags_fn: Any = None,
    alt_tool_tag_fn: Any = None,
    tool_choice_name_fn: Any = None,
) -> str:
    """Английская секция протокола и схем инструментов для промпта."""
    if tool_tags_fn is not None:
        open_tag, close_tag = tool_tags_fn(model_id)
    else:
        open_tag, close_tag = "<tool_call>", "</tool_call>"
    uses_alt = alt_tool_tag_fn(model_id) if alt_tool_tag_fn is not None else False
    block_name = "tool_invoke" if uses_alt else "tool_call"
    lines = [
        "[system]",
        "# Tool calling protocol",
        "You may call the external tools listed below.",
        "When you need a tool, output ONLY blocks exactly in this form:",
        f'{open_tag}{{"name": "<tool_name>", "arguments": {{<json>}}}}{close_tag}',
        "You may output several such blocks in a row. Do not narrate around them.",
        "Tool results arrive later as lines like [tool result <id>] with the result text.",
        "If no tool is needed, reply normally in plain text.",
        "Never attempt to use built-in tools; the only tools available are the ones listed here.",
        f"Do not run shell commands or edit files yourself: emit a {block_name} block instead.",
        (
            f"If a tool is needed, you MUST emit the {block_name} block in this reply; prose claims "
            'like "I\'ll check..." without a block are forbidden and end the turn with no action.'
        ),
        "The block itself changes nothing: the caller executes the tool and sends back the result.",
    ]
    if tool_choice == "required":
        lines.append("You MUST call at least one tool now.")
    elif tool_choice_name_fn is not None:
        forced = tool_choice_name_fn(tool_choice)
        if forced:
            lines.append(f'You MUST call the tool "{forced}" now.')
    lines.append("")
    lines.append("Available tools:")
    for item in tools:
        fn = item.get("function") if isinstance(item.get("function"), dict) else item
        if not isinstance(fn, dict):
            continue
        name = str(fn.get("name") or "")
        desc = str(fn.get("description") or "")
        params = _dict_or_empty(fn.get("parameters"))
        lines.append(f"- {name}: {desc}")
        lines.append("  parameters: " + json.dumps(params, ensure_ascii=False))
    return "\n".join(lines)


def parse_opencode_event(event: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Разбор одного события `opencode run` для чанков OpenAI SSE / non-stream."""
    if not isinstance(event, dict):
        return "", {}
    etype = str(event.get("type") or "").strip()
    part = _dict_or_empty(event.get("part"))

    if etype == "reasoning":
        rtext = part.get("text")
        meta = _dict_or_empty(part.get("metadata"))
        openai_meta = _dict_or_empty(meta.get("openai"))
        enc_data = openai_meta.get("reasoningEncryptedContent")
        delta: dict[str, Any] = {}
        if isinstance(rtext, str) and rtext:
            delta["reasoning_content"] = rtext
        if isinstance(enc_data, str) and enc_data:
            delta["reasoning_details"] = [
                {"type": "reasoning.encrypted", "data": enc_data}
            ]
        return ("reasoning", delta)

    if etype == "text":
        ttext = part.get("text")
        if isinstance(ttext, str) and ttext:
            return ("text", {"content": ttext})
        return ("text", {})

    if etype == "step_finish":
        tokens = _dict_or_empty(part.get("tokens"))
        return ("step_finish", tokens)

    if etype == "error":
        err_obj = event.get("error")
        if not isinstance(err_obj, dict):
            err_obj = {"message": str(err_obj)}
        data = err_obj.get("data")
        if isinstance(data, dict):
            message = str(data.get("message") or err_obj.get("message") or err_obj)
            status = data.get("statusCode")
        else:
            message = str(err_obj.get("message") or err_obj)
            status = None
        if "provider.no-route" in message or "Variant unavailable" in message:
            status = 400
        return ("error", {"statusCode": status, "message": message})

    return (etype, {})
