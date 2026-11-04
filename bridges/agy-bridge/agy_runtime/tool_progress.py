"""Отслеживание прогресса инструментов и маркеров в потоке событий."""

from __future__ import annotations

import os
import re
from typing import cast, final

TOOL_NAME_ALLOWLIST = frozenset(
    {
        "run_command",
        "read_file",
        "write_file",
        "edit_file",
        "manage_task",
        "search_web",
        "search_marketplace",
        "ask_question",
        "schedule",
        "send_message",
        "invoke_subagent",
        "define_subagent",
        "manage_subagents",
        "list_resources",
        "read_resource",
        "grep_search",
        "find_by_name",
        "list_dir",
        "view_file_outline",
        "view_code_item",
        "replace_file_content",
        "multi_replace_file_content",
        "command_status",
        "send_command_input",
        "read_url_content",
        "view_content_chunk",
        "browser_subagent",
        "generate_image",
        "task_boundary",
        "notify_user",
        "bash",
        "glob",
        "grep",
        "read",
        "edit",
        "write",
    }
)
_SAFE_MCP_TOOL_RE = re.compile(r"mcp_[a-z0-9_-]{1,32}_[a-z0-9_]{1,32}\Z")
MAX_TOOL_MARKERS_PER_TURN = int(os.environ.get("AGY_BRIDGE_MAX_TOOL_MARKERS_PER_TURN", "128"))


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _safe_tool_name(raw: object) -> str:
    """Имя инструмента для маркера: только закрытый список, всё остальное -> `tool`."""
    if not isinstance(raw, str):
        return "tool"
    name = raw.strip()
    if (
        not name
        or len(name) > 128
        or name[0] in "/."
        or ".." in name
        or re.fullmatch(r"[A-Za-z0-9_:./-]+", name) is None
    ):
        return "tool"
    bare = re.split(r"[:./]", name)[-1]
    if bare in TOOL_NAME_ALLOWLIST or _SAFE_MCP_TOOL_RE.fullmatch(bare) is not None:
        return bare
    return "tool"


def _format_tool_marker(safe_name: str) -> str:
    return "\n[🔧 tool: %s — done]\n" % safe_name


@final
class _ToolProgress:
    """Дедупликация DONE нативных инструментов хода и безопасный маркер (AD-002)."""

    def __init__(
        self, turn_id: str, cid: str, max_markers: int = MAX_TOOL_MARKERS_PER_TURN
    ) -> None:
        self.turn_id = turn_id
        self.cid = cid
        self.max_markers = max_markers
        self._seen: set[tuple[object, ...]] = set()
        self._anon_seq = 0
        self._pending_key: tuple[object, ...] | None = None

    def _key_for(self, ev: dict[str, object]) -> tuple[object, ...]:
        step = _as_int(ev.get("step_index"))
        if step is not None and step >= 0:
            return (self.turn_id, self.cid, step)
        raw_id = ev.get("call_id") or ev.get("tool_call_id") or ev.get("id")
        if isinstance(raw_id, (str, int)) and str(raw_id).strip():
            return ("id", str(raw_id).strip())
        ordinal = _as_int(ev.get("fallback_ordinal"))
        if ordinal is not None:
            return ("ord", ordinal)
        self._anon_seq += 1
        return ("anon", self._anon_seq)

    def marker(self, event: object, *, commit: bool = True) -> str | None:
        """Строка маркера или None (дубль DONE того же шага / лимит маркеров)."""
        self._pending_key = None
        if not isinstance(event, dict):
            return None
        ev = cast("dict[str, object]", event)
        key = self._key_for(ev)
        if key in self._seen or len(self._seen) >= self.max_markers:
            return None
        if commit:
            self._seen.add(key)
        else:
            self._pending_key = key
        return _format_tool_marker(_safe_tool_name(ev.get("name")))

    def commit(self, event: object | None = None) -> None:
        """Засчитать маркер после успешной записи (ключ из последнего `commit=False`)."""
        key = self._pending_key
        self._pending_key = None
        if key is None and isinstance(event, dict):
            key = self._key_for(cast("dict[str, object]", event))
        if key is not None and len(self._seen) < self.max_markers:
            self._seen.add(key)
