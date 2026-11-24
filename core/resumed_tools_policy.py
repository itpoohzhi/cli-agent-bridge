"""Pure policy helpers for compact tool prompts on resumed conversations."""

from __future__ import annotations

import hashlib
import json
from typing import cast

from core.prompt_rendering import escape_role_delimiters

_TOOL_CALL_EXAMPLE = (
    '<tool_call>{"name":"<tool_name>","arguments":{<json>}}</tool_call>'
)


def compute_tools_fingerprint(
    tools: list[dict[str, object]] | None,
    tool_choice: object = None,
    *,
    has_attachments: bool = False,
    attachment_tool: str | None = None,
) -> str:
    """Return a stable digest of every input that affects the tools prompt."""
    payload = {
        "attachment_tool": attachment_tool,
        "has_attachments": has_attachments,
        "tool_choice": tool_choice,
        "tools": tools or [],
    }
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def should_use_compact_tools(
    is_resumed: bool,
    stored_fp: str,
    current_fp: str,
    compact_enabled: bool,
) -> bool:
    """Select compact mode only for an unchanged, known resumed contract."""
    return (
        is_resumed
        and compact_enabled
        and bool(stored_fp)
        and stored_fp == current_fp
    )


def _tool_choice_constraint(tool_choice: object) -> tuple[str, str]:
    if isinstance(tool_choice, str):
        mode = tool_choice.strip().lower()
        return (mode, "") if mode in {"none", "required"} else ("auto", "")
    if not isinstance(tool_choice, dict):
        return "auto", ""
    choice = cast(dict[str, object], tool_choice)
    choice_type = str(choice.get("type") or "").strip().lower()
    if choice_type == "none":
        return "none", ""
    raw_function = choice.get("function")
    function = (
        cast(dict[str, object], raw_function) if isinstance(raw_function, dict) else {}
    )
    function_name = (
        function.get("name")
    )
    name = function_name or choice.get("name")
    if name:
        return "function", str(name)
    return (choice_type, "") if choice_type == "required" else ("auto", "")


def _choice_instruction(tool_choice: object) -> str:
    mode, name = _tool_choice_constraint(tool_choice)
    if mode == "none":
        return "Tool choice is `none`: do not emit a tool call; reply in plain text."
    if mode == "required":
        return "Tool choice is `required`: you MUST call at least one available tool now."
    if mode == "function":
        safe_name = json.dumps(escape_role_delimiters(name), ensure_ascii=False)
        return f"Tool choice requires exactly this tool now: {safe_name}."
    return "If no tool is needed, reply normally in plain text."


def build_compact_tools_reminder(
    tool_names: list[str], tool_choice: object = None
) -> str:
    """Render protocol instructions without repeating full JSON schemas."""
    safe_names = json.dumps(
        [escape_role_delimiters(name) for name in tool_names],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    lines = (
        "[system]",
        "# Resumed tool calling protocol",
        "Full tool schemas are already present in the conversation context.",
        f"Available tool names: {safe_names}",
        "When calling a tool, output ONLY one or more blocks exactly in this form:",
        _TOOL_CALL_EXAMPLE,
        "Do not narrate around tool-call blocks or use tools outside the list.",
        "Tool results arrive later as [tool result <id>] followed by result text.",
        _choice_instruction(tool_choice),
    )
    return "\n".join(lines)


def wrap_resumed_tools_prompt(
    prompt: str, tool_names: list[str], tool_choice: object = None
) -> str:
    """Prepend the compact protocol to an already-rendered resumed delta."""
    reminder = build_compact_tools_reminder(tool_names, tool_choice)
    return f"{reminder}\n\n{prompt}" if prompt else reminder
