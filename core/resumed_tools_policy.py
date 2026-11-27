"""Pure policy helpers for compact tool prompts on resumed conversations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from core.prompt_rendering import TOOL_CALL_FORMAT_LINE, escape_role_delimiters


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


class CompactToolsMode(StrEnum):
    """Compact-tools contract mode (AD-013): proven / legacy / off."""

    PROVEN = "proven"
    LEGACY = "legacy"
    OFF = "off"

    @classmethod
    def parse(cls, value: object) -> CompactToolsMode:
        """Map a config value to a mode; unknown input fails closed to PROVEN."""
        if isinstance(value, str):
            token = value.strip().lower()
            if token == "legacy":
                return cls.LEGACY
            if token == "off":
                return cls.OFF
        return cls.PROVEN


@dataclass(frozen=True, slots=True)
class CompactToolsQuery:
    """Immutable decision facts gathered by the adapter (BND-001).

    stored_fp/stored_cid mirror the session store entry {cid, tools_fp};
    explicit_path marks the explicit-session path with no fp ledger.
    """

    mode: CompactToolsMode = CompactToolsMode.PROVEN
    is_resumed: bool = False
    explicit_path: bool = False
    emulate_tools: bool = True
    compact_enabled: bool = True
    stored_fp: str = ""
    stored_cid: str = ""
    run_cid: str = ""
    tools: list[dict[str, object]] | None = None
    tool_choice: object = None
    has_attachments: bool = False
    attachment_tool: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.mode, CompactToolsMode):
            raise ValueError("mode must be a CompactToolsMode")
        if type(self.stored_fp) is not str or type(self.stored_cid) is not str:
            raise ValueError("stored_fp and stored_cid must be str")
        if type(self.run_cid) is not str:
            raise ValueError("run_cid must be str")
        if type(self.is_resumed) is not bool or type(self.explicit_path) is not bool:
            raise ValueError("resume flags must be bool")
        bools = (self.emulate_tools, self.compact_enabled, self.has_attachments)
        if any(type(flag) is not bool for flag in bools):
            raise ValueError("tool flags must be bool")


def decide_compact_tools(query: CompactToolsQuery) -> bool:
    """Compact only with a cid-bound fingerprint proof (AD-013, CD-006).

    PROVEN: resumed + stored_fp == current_fp + stored cid == run cid;
    explicit path and cold turns get full schemas. LEGACY reproduces the
    pre-fix decision; OFF never compacts.
    """
    if query.mode is CompactToolsMode.OFF or not query.emulate_tools:
        return False
    current_fp = compute_tools_fingerprint(
        query.tools,
        query.tool_choice,
        has_attachments=query.has_attachments,
        attachment_tool=query.attachment_tool,
    )
    if query.mode is CompactToolsMode.LEGACY:
        if query.explicit_path:
            return query.compact_enabled
        return should_use_compact_tools(
            query.is_resumed, query.stored_fp, current_fp, query.compact_enabled
        )
    if query.explicit_path or not query.is_resumed or not query.run_cid:
        return False
    if query.stored_cid != query.run_cid:
        return False
    return should_use_compact_tools(
        query.is_resumed, query.stored_fp, current_fp, query.compact_enabled
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
        TOOL_CALL_FORMAT_LINE,
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
