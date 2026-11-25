"""Чистые рендереры сообщений, схем инструментов и вложений промпта."""

from __future__ import annotations

import json
import re
from typing import cast

__all__ = (
    "_append_attachments", "_render_assistant", "_render_message", "_render_tool_call",
    "_render_tool_schema", "_render_tools_section", "TOOL_CALL_FORMAT_LINE", "escape_role_delimiters", "render_tool_call", "render_tools_section",
)

_TOOL_CALL_OPEN = "<tool_call>"
_TOOL_CALL_CLOSE = "</tool_call>"
TOOL_CALL_FORMAT_LINE = (
    "Wrap each call in a tool_call XML element (angle-bracket opening tag tool_call, "
    "closing tag /tool_call) whose entire body is one JSON object with a string \"name\" "
    "and an object \"arguments\"; nothing may follow the object inside the element."
)
_SPOOFED_ROLE_LINE_RE = re.compile(
    r"(?im)^([ \t]*)\[(system|user|assistant|developer|tool(?:\s+result[^\n\]]*)?|attachments)\]"
)
_TOOL_CALL_MARKER_RE = re.compile(r"</?tool_call\s*>", re.I)
_HEADER_TOKEN_RE = re.compile(r"[\r\n\[\]<>]+")
_TOOLS_PROTOCOL_LINES: tuple[str, ...] = (
    "[system]",
    "# Tool calling protocol",
    "You may call the external tools listed below.",
    "When you need a tool, output ONLY blocks exactly in this form:",
    TOOL_CALL_FORMAT_LINE,
    "You may output several such blocks in a row. Do not narrate around them.",
    "Tool results arrive later as lines like [tool result <id>] with the result text.",
    "If no tool is needed, reply normally in plain text.",
    "Never attempt to use built-in tools; the only tools available are the ones listed here.",
)
_ATTACHMENTS_FOOTER = (
    "Open each image with the Read tool on exactly these paths before answering about it "
    "(Read is the only built-in tool you may use, and only on these files). Do not claim to "
    "see an image you have not opened. If an image cannot be opened, say so explicitly "
    "instead of guessing."
)


def _tool_choice_info(tool_choice: object) -> tuple[bool, bool, str]:
    if isinstance(tool_choice, str):
        normalized = tool_choice.strip().lower()
        return normalized == "none", normalized == "required", ""
    if not isinstance(tool_choice, dict):
        return False, False, ""
    choice = cast(dict[str, object], tool_choice)
    choice_type = str(choice.get("type") or "").strip().lower()
    if choice_type == "none":
        return True, False, ""
    raw_function = choice.get("function")
    function = (
        cast(dict[str, object], raw_function) if isinstance(raw_function, dict) else {}
    )
    name = function.get("name") or choice.get("name") or ""
    return False, choice_type == "required" and not name, str(name) if name else ""


def _tool_function_and_params(item: object) -> tuple[dict[str, object], dict[str, object]] | None:
    if not isinstance(item, dict):
        return None
    item_map = cast(dict[str, object], item)
    raw_fn = item_map.get("function")
    fn = cast(dict[str, object], raw_fn) if isinstance(raw_fn, dict) else item_map
    raw_params = fn.get("parameters")
    params = cast(dict[str, object], raw_params) if isinstance(raw_params, dict) else {}
    return fn, params


def _tool_sort_key(item: object) -> tuple[str, str]:
    parsed = _tool_function_and_params(item)
    if parsed is None:
        return "", ""
    fn, params = parsed
    return str(fn.get("name") or ""), json.dumps(params, ensure_ascii=False, sort_keys=True)


def _render_tools_section(
    tools: list[object] | tuple[object, ...],
    tool_choice: object = None,
    has_attachments: bool = False,
    attachment_tool: str = "Read",
    *,
    sort_keys: bool = False,
) -> str:
    is_none, is_required, forced = _tool_choice_info(tool_choice)
    if not tools or is_none:
        return ""
    lines = list(_TOOLS_PROTOCOL_LINES)
    if has_attachments:
        lines[-1] = lines[-1].rstrip(".") + f", except {attachment_tool} on the attachment files listed under [attachments]."
    if is_required:
        lines.append("You MUST call at least one tool now.")
    elif forced:
        lines.append(f'You MUST call the tool "{_sanitize_header_token(forced)}" now.')
    lines.extend(("", "Available tools:"))
    ordered_tools = sorted(tools, key=_tool_sort_key) if sort_keys else tools
    for item in ordered_tools:
        lines.extend(_render_tool_schema(item, sort_keys=sort_keys))
    return "\n".join(lines)


def render_tools_section(
    tools: list[object] | tuple[object, ...],
    tool_choice: object = None,
    has_attachments: bool = False,
    attachment_tool: str = "Read",
    *,
    sort_keys: bool = False,
) -> str:
    """Рендерит секцию протокола и схем инструментов."""
    return _render_tools_section(tools, tool_choice, has_attachments, attachment_tool, sort_keys=sort_keys)


def _render_tool_schema(item: object, *, sort_keys: bool = False) -> tuple[str, ...]:
    parsed = _tool_function_and_params(item)
    if parsed is None:
        return ()
    fn, params = parsed
    label = f"- {fn.get('name') or ''}: {fn.get('description') or ''}"
    encoded = json.dumps(params, ensure_ascii=False, sort_keys=sort_keys)
    return escape_role_delimiters(label), "  parameters: " + encoded


def _render_content(content: object, counter: list[int]) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = (_render_content_item(item, counter) for item in cast(list[object], content))
        return "\n".join(part for part in parts if part)
    return str(content)


def _render_content_item(item: object, counter: list[int]) -> str:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return ""
    item_map = cast(dict[str, object], item)
    if item_map.get("type") == "image_url":
        counter[0] += 1
        return f"[image {counter[0]}]"
    text = item_map.get("text")
    return "" if text is None else str(text)


def _tool_arguments(
    item: dict[str, object], function: dict[str, object]
) -> dict[str, object]:
    raw = function.get("arguments")
    raw = item.get("arguments") if raw is None else raw
    if isinstance(raw, dict):
        return cast(dict[str, object], raw)
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = cast(object, json.loads(raw.strip()))
    except ValueError:
        return {}
    return cast(dict[str, object], parsed) if isinstance(parsed, dict) else {}


def _render_tool_call(item: object, *, sort_keys: bool = False) -> str:
    item_map = cast(dict[str, object], item) if isinstance(item, dict) else {}
    raw_function = item_map.get("function")
    function = (
        cast(dict[str, object], raw_function) if isinstance(raw_function, dict) else {}
    )
    payload = {
        "id": str(item_map.get("id") or ""),
        "name": str(function.get("name") or item_map.get("name") or ""),
        "arguments": _tool_arguments(item_map, function),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=sort_keys)
    return f"{_TOOL_CALL_OPEN}{encoded}{_TOOL_CALL_CLOSE}"


def render_tool_call(item: object, *, sort_keys: bool = False) -> str:
    """Рендерит блок вызова инструмента <tool_call>."""
    return _render_tool_call(item, sort_keys=sort_keys)


def _sanitize_header_token(value: str) -> str:
    return " ".join(_HEADER_TOKEN_RE.sub(" ", value).split())


def escape_role_delimiters(text: str) -> str:
    if not text:
        return text
    escaped = _SPOOFED_ROLE_LINE_RE.sub(r"\1\\[\2]", text) if "[" in text else text
    return _TOOL_CALL_MARKER_RE.sub(lambda m: "\\" + m.group(0), escaped)


def _render_tool_result(message: dict[str, object], text: str) -> str:
    call_id = _sanitize_header_token(
        str(message.get("tool_call_id") or message.get("id") or "")
    )
    name = _sanitize_header_token(str(message.get("name") or ""))
    header = f"[tool result {call_id}]" + (f" ({name})" if name else "")
    return f"{header}\n{text}" if text.strip() else header


def _render_assistant(message: dict[str, object], text: str, *, sort_keys: bool = False) -> str:
    parts = [text] if text.strip() else []
    calls = message.get("tool_calls")
    if isinstance(calls, list):
        parts.extend(_render_tool_call(call, sort_keys=sort_keys) for call in cast(list[object], calls))
    body = "\n".join(part for part in parts if part)
    return f"[assistant]\n{body}" if body.strip() else ""


def _render_message(
    message: object, counter: list[int], *, escape_roles: bool, prune_marker: str, sort_keys: bool = False
) -> tuple[bool, str]:
    if not isinstance(message, dict):
        return False, ""
    message_map = cast(dict[str, object], message)
    role = str(message_map.get("role") or "user").strip().lower() or "user"
    if role not in ("system", "developer", "user", "assistant", "tool"):
        role = "user"
    raw = _render_content(message_map.get("content"), counter)
    is_prune = bool(prune_marker) and raw.strip() == prune_marker.strip()
    text = escape_role_delimiters(raw) if escape_roles and not is_prune else raw
    if role == "tool":
        return False, _render_tool_result(message_map, text)
    if role == "assistant":
        return False, _render_assistant(message_map, text, sort_keys=sort_keys)
    if not text.strip():
        return False, ""
    is_prefix = _is_prefix_role(role, is_prune)
    return is_prefix, f"[{role}]\n{text}"


def _is_prefix_role(role: str, is_prune: bool) -> bool:
    return role in ("system", "developer") and not is_prune


def _append_attachments(
    text: str, images: list[dict[str, object]] | tuple[dict[str, object], ...] | None
) -> str:
    if not images:
        return text
    head = f"[attachments]\nThis request includes {len(images)} image(s) as local files in the working directory. The markers [image N] in the conversation refer to them in order."
    items = [
        f"- [image {index}] ./{_sanitize_header_token(str(image.get('name', '')))}"
        + f" ({_sanitize_header_token(str(image.get('mime', '')))}, {len(str(image.get('data', '')))} bytes)"
        for index, image in enumerate(images, 1)
    ]
    return "\n\n".join((text, "\n".join([head, *items, _ATTACHMENTS_FOOTER])))
