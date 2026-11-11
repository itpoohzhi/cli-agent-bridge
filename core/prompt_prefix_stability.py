"""Сборка стабильного префикса промпта и учёт бюджета схем инструментов."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol, cast

from core.prompt_rendering import (
    _append_attachments,
    _render_message,
    _render_tools_section,
    _tool_choice_info,
    escape_role_delimiters,
)

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


class _Environment(Protocol):
    def get(self, key: str, default: str = "") -> str: ...


@dataclass(frozen=True, slots=True)
class PrefixStabilityConfig:
    """Параметры стабилизации префикса промпта и эпохального прунинга."""

    enabled: bool = True
    prune_marker: str = _DEFAULT_PRUNE_MARKER
    hysteresis_ratio: float = _DEFAULT_HYSTERESIS_RATIO

    @classmethod
    def from_env(cls, environ: _Environment | None = None) -> PrefixStabilityConfig:
        source = os.environ if environ is None else environ
        raw = str(source.get(_FLAG_NAME, "")).strip().lower()
        if raw in _TRUE_VALUES:
            return cls(enabled=True)
        if raw in _FALSE_VALUES:
            return cls(enabled=False)
        return cls()


def compute_tools_budget_overhead(
    tools_or_section: object = None,
    tool_choice: object = None,
    has_attachments: bool = False,
    **options: object,
) -> int:
    """Вычисляет вес секции инструментов в байтах UTF-8 с разделителем."""
    is_none, _, _ = _tool_choice_info(tool_choice)
    if is_none:
        return 0
    rendered = _budget_section(tools_or_section, tool_choice, has_attachments, options)
    if not rendered.strip():
        return 0
    raw_framing = options.get("framing_bytes", 2)
    framing_bytes = raw_framing if isinstance(raw_framing, int) else 2
    return len(rendered.encode("utf-8")) + max(0, framing_bytes)


def _budget_section(
    source: object,
    tool_choice: object,
    has_attachments: bool,
    options: dict[str, object],
) -> str:
    section = options.get("tools_section")
    if isinstance(section, str):
        return section
    if isinstance(source, str):
        return source
    if not isinstance(source, (list, tuple)):
        return ""
    images = options.get("images")
    sequence = cast("list[object] | tuple[object, ...]", source)
    return _render_tools_section(sequence, tool_choice, bool(has_attachments or images))


def assemble_prompt_blocks(
    messages: list[object] | tuple[object, ...] | None = None,
    tools: list[object] | tuple[object, ...] | None = None,
    tool_choice: object = None,
    images: list[dict[str, object]] | tuple[dict[str, object], ...] | None = None,
    **options: object,
) -> str:
    """Собирает стабильный префикс ``[System + Tools + History]`` за один проход."""
    config, stable = _assembly_config(options)
    tools_section = _assembly_tools(tools, tool_choice, images, options)
    text = _assemble_message_blocks(messages, tools_section, config, stable)
    return _append_attachments(text, images)


def _assembly_config(
    options: dict[str, object],
) -> tuple[PrefixStabilityConfig, bool]:
    raw_config = options.get("config")
    config = (
        raw_config
        if isinstance(raw_config, PrefixStabilityConfig)
        else PrefixStabilityConfig.from_env()
    )
    enabled = options.get("enabled")
    return config, config.enabled if enabled is None else bool(enabled)


def _assembly_tools(
    tools: list[object] | tuple[object, ...] | None,
    tool_choice: object,
    images: list[dict[str, object]] | tuple[dict[str, object], ...] | None,
    options: dict[str, object],
) -> str:
    is_none, _, _ = _tool_choice_info(tool_choice)
    if is_none:
        return ""
    section = options.get("tools_section")
    if isinstance(section, str):
        return section
    return _render_tools_section(tools or (), tool_choice, bool(images))


def _assemble_message_blocks(
    messages: list[object] | tuple[object, ...] | None,
    tools_section: str,
    config: PrefixStabilityConfig,
    stable: bool,
) -> str:
    counter, system_blocks, history_blocks = [0], list[str](), list[str]()
    in_system_prefix = stable
    for message in messages or ():
        is_system, block = _render_message(
            message,
            counter,
            escape_roles=stable,
            prune_marker=config.prune_marker,
        )
        if block:
            target = system_blocks if in_system_prefix and is_system else history_blocks
            target.append(block)
            in_system_prefix = in_system_prefix and is_system
    tool_blocks = [tools_section] if tools_section.strip() else []
    ordered = (
        (*system_blocks, *tool_blocks, *history_blocks)
        if stable
        else (*tool_blocks, *history_blocks)
    )
    return "\n\n".join(ordered).strip() or "Reply with exactly: PONG"
