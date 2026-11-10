"""Чистая сборка стабильного префикса промпта, учёт бюджета схем и экранирование ролей."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Protocol, cast

__all__ = [
    "PrefixStabilityConfig",
    "assemble_prompt_blocks",
    "compute_tools_budget_overhead",
    "escape_role_delimiters",
]

_FLAG_NAME = "BRIDGE_STABLE_PROMPT_PREFIX_ENABLED"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})
_DEFAULT_PRUNE_MARKER = "[context pruned]"
_DEFAULT_HYSTERESIS_RATIO = 0.78
_TOOL_CALL_OPEN = "<tool_call>"
_TOOL_CALL_CLOSE = "</tool_call>"
_SPOOFED_ROLE_LINE_RE = re.compile(
    r"(?im)^([ \t]*)\[(system|user|assistant|developer|tool(?:\s+result[^\n\]]*)?|attachments)\]"
)
_TOOLS_PROTOCOL_LINES: tuple[str, ...] = (
    "[system]",
    "# Tool calling protocol",
    "You may call the external tools listed below.",
    "When you need a tool, output ONLY blocks exactly in this form:",
    f'{_TOOL_CALL_OPEN}{{"name": "<tool_name>", "arguments": {{<json>}}}}{_TOOL_CALL_CLOSE}',
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


class _Environment(Protocol):
    def get(self, key: str, default: str = "") -> str: ...


@dataclass(frozen=True)
class PrefixStabilityConfig:
    """Хранит параметры стабилизации префикса промпта и эпохального прунинга."""

    enabled: bool = True
    prune_marker: str = _DEFAULT_PRUNE_MARKER
    hysteresis_ratio: float = _DEFAULT_HYSTERESIS_RATIO

    @classmethod
    def from_env(cls, environ: _Environment | None = None) -> PrefixStabilityConfig:
        """Строит конфигурацию из переданного окружения или ``os.environ``."""
        source = os.environ if environ is None else environ
        raw = str(source.get(_FLAG_NAME, "")).strip().lower()
        if raw in _TRUE_VALUES:
            return cls(enabled=True)
        if raw in _FALSE_VALUES:
            return cls(enabled=False)
        return cls()


def _tool_choice_info(tool_choice: object) -> tuple[bool, str]:
    """Возвращает ``(is_none, forced_tool_name)`` для параметра ``tool_choice``."""
    if isinstance(tool_choice, str) and tool_choice.strip().lower() == "none":
        return True, ""
    if not isinstance(tool_choice, dict):
        return False, ""
    choice_map = cast(dict[str, object], tool_choice)
    raw_fn = choice_map.get("function")
    fn = cast(dict[str, object], raw_fn) if isinstance(raw_fn, dict) else {}
    name = fn.get("name") or choice_map.get("name") or ""
    return False, str(name) if name else ""


def _render_tools_section(
    tools: list[object] | tuple[object, ...],
    tool_choice: object = None,
    has_attachments: bool = False,
) -> str:
    """Формирует каноническую секцию протокола и схем инструментов."""
    is_none, forced = _tool_choice_info(tool_choice)
    if not tools or is_none:
        return ""
    lines = list(_TOOLS_PROTOCOL_LINES)
    if has_attachments:
        lines[-1] += ", except Read on the attachment files listed under [attachments]."
    if tool_choice == "required":
        lines.append("You MUST call at least one tool now.")
    elif forced:
        lines.append(f'You MUST call the tool "{forced}" now.')
    lines.extend(("", "Available tools:"))
    for item in tools:
        if not isinstance(item, dict):
            continue
        imap = cast(dict[str, object], item)
        rfn = imap.get("function")
        fn = cast(dict[str, object], rfn) if isinstance(rfn, dict) else imap
        rpar = fn.get("parameters")
        params = cast(dict[str, object], rpar) if isinstance(rpar, dict) else {}
        lines.append(f"- {fn.get('name') or ''}: {fn.get('description') or ''}")
        lines.append("  parameters: " + json.dumps(params, ensure_ascii=False))
    return "\n".join(lines)


def _render_content(content: object, counter: list[int]) -> str:
    """Рендерит тело сообщения со сквозной нумерацией маркеров ``[image N]``."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in cast(list[object], content):
            if isinstance(item, str) and item:
                parts.append(item)
            elif isinstance(item, dict):
                imap = cast(dict[str, object], item)
                if imap.get("type") == "image_url":
                    counter[0] += 1
                    parts.append(f"[image {counter[0]}]")
                elif imap.get("text") is not None and str(imap["text"]):
                    parts.append(str(imap["text"]))
        return "\n".join(parts)
    return str(content)


def _render_tool_call(item: object) -> str:
    """Рендерит один исторический вызов инструмента в блок ``<tool_call>``."""
    imap = cast(dict[str, object], item) if isinstance(item, dict) else {}
    rfn = imap.get("function")
    fn = cast(dict[str, object], rfn) if isinstance(rfn, dict) else {}
    rargs = (
        imap.get("arguments") if fn.get("arguments") is None else fn.get("arguments")
    )
    aobj: dict[str, object] = {}
    if isinstance(rargs, dict):
        aobj = cast(dict[str, object], rargs)
    elif isinstance(rargs, str) and rargs.strip():
        try:
            parsed = cast(object, json.loads(rargs.strip()))
            aobj = cast(dict[str, object], parsed) if isinstance(parsed, dict) else {}
        except ValueError:
            aobj = {}
    payload = {
        "id": str(imap.get("id") or ""),
        "name": str(fn.get("name") or imap.get("name") or ""),
        "arguments": aobj,
    }
    return (
        f"{_TOOL_CALL_OPEN}{json.dumps(payload, ensure_ascii=False)}{_TOOL_CALL_CLOSE}"
    )


def escape_role_delimiters(text: str) -> str:
    """Экранирует поддельные ролевые заголовки в начале строк внутри тела сообщений."""
    if not text or "[" not in text:
        return text
    return _SPOOFED_ROLE_LINE_RE.sub(r"\1\\[\2]", text)


def _render_message(
    msg: object, counter: list[int], *, escape_roles: bool, prune_marker: str
) -> tuple[bool, str]:
    """Преобразует сообщение в ``(is_system_prefix_candidate, rendered_block)``."""
    if not isinstance(msg, dict):
        return False, ""
    mmap = cast(dict[str, object], msg)
    role = str(mmap.get("role") or "user")
    raw = _render_content(mmap.get("content"), counter)
    is_prune = raw.strip() == prune_marker
    text = escape_role_delimiters(raw) if (escape_roles and not is_prune) else raw
    if role == "tool":
        cid = str(mmap.get("tool_call_id") or mmap.get("id") or "")
        name = str(mmap.get("name") or "")
        hdr = f"[tool result {cid}]" + (f" ({name})" if name else "")
        return False, f"{hdr}\n{text}" if text.strip() else hdr
    if role == "assistant":
        parts = [text] if text.strip() else []
        calls = mmap.get("tool_calls")
        if isinstance(calls, list):
            parts.extend(_render_tool_call(tc) for tc in cast(list[object], calls))
        body = "\n".join(p for p in parts if p)
        return False, f"[assistant]\n{body}" if body.strip() else ""
    if not text.strip():
        return False, ""
    return role in ("system", "developer") and not is_prune, f"[{role}]\n{text}"


def compute_tools_budget_overhead(
    tools_or_section: object = None,
    tool_choice: object = None,
    has_attachments: bool = False,
    *,
    tools_section: str | None = None,
    images: list[object] | tuple[object, ...] | None = None,
    framing_bytes: int = 2,
) -> int:
    """Вычисляет вес секции инструментов в байтах UTF-8 с учётом разделителя блока."""
    if isinstance(tools_section, str):
        rendered = tools_section
    elif isinstance(tools_or_section, str):
        rendered = tools_or_section
    elif isinstance(tools_or_section, (list, tuple)):
        seq = cast("list[object] | tuple[object, ...]", tools_or_section)
        rendered = _render_tools_section(
            seq, tool_choice, bool(has_attachments or images)
        )
    else:
        return 0
    if not rendered.strip():
        return 0
    return len(rendered.encode("utf-8")) + max(0, int(framing_bytes))


def assemble_prompt_blocks(
    messages: list[object] | tuple[object, ...] | None = None,
    tools: list[object] | tuple[object, ...] | None = None,
    tool_choice: object = None,
    images: list[dict[str, object]] | tuple[dict[str, object], ...] | None = None,
    *,
    tools_section: str | None = None,
    config: PrefixStabilityConfig | None = None,
    enabled: bool | None = None,
) -> str:
    """Собирает промпт за один проход со стабильным префиксом ``[System + Tools + History]``."""
    cfg = config if config is not None else PrefixStabilityConfig.from_env()
    stable = cfg.enabled if enabled is None else bool(enabled)
    t_sec = (
        tools_section
        if tools_section is not None
        else _render_tools_section(tools or (), tool_choice, bool(images))
    )
    counter, sys_b, hist_b, in_sys = [0], list[str](), list[str](), stable
    for msg in messages or ():
        is_sys, blk = _render_message(
            msg, counter, escape_roles=stable, prune_marker=cfg.prune_marker
        )
        if blk:
            (sys_b if (in_sys and is_sys) else hist_b).append(blk)
            in_sys = in_sys and is_sys
    t_list = [t_sec] if t_sec.strip() else []
    ordered = (*sys_b, *t_list, *hist_b) if stable else (*t_list, *hist_b)
    text = "\n\n".join(ordered).strip() or "Reply with exactly: PONG"
    if not images:
        return text
    head = f"[attachments]\nThis request includes {len(images)} image(s) as local files in the working directory. The markers [image N] in the conversation refer to them in order."
    items = [
        f"- [image {i}] ./{im.get('name', '')} ({im.get('mime', '')}, {len(str(im.get('data', '')))} bytes)"
        for i, im in enumerate(images, 1)
    ]
    return "\n\n".join((text, "\n".join([head, *items, _ATTACHMENTS_FOOTER])))
