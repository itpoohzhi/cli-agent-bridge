"""Чистый контракт режимов эмуляции инструментов и каналов нормализатора."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ToolMode(str, Enum):
    EMULATE = "emulate"
    FORBID = "forbid"
    OFF = "off"


class ToollessTagPolicy(str, Enum):
    TEXT = "text"
    ERROR = "error"


@dataclass(frozen=True)
class NormalizerSinks:
    on_content: Callable[[str], None] | None = None
    on_reasoning: Callable[[str], None] | None = None
    on_tool_call: Callable[[dict[str, Any]], None] | None = None


@dataclass(frozen=True)
class NormalizerModeSpec:
    mode: ToolMode
    policy: ToollessTagPolicy = ToollessTagPolicy.TEXT


DEFAULT_EMULATE_SPEC = NormalizerModeSpec(ToolMode.EMULATE)
TOOLLESS_PURE_TEXT_HINT = (
    "No tools are available. Reply with plain text, without tool calls or service tags."
)


def build_mode_spec(
    mode: ToolMode, policy: ToollessTagPolicy = ToollessTagPolicy.TEXT
) -> NormalizerModeSpec:
    """Создаёт неизменяемую спецификацию режима без чтения конфигурации."""
    return NormalizerModeSpec(mode, policy)


def _tool_choice_none(tool_choice: Any) -> bool:
    """Сохраняет историческую семантику строковой и объектной формы none."""
    if isinstance(tool_choice, str):
        return tool_choice.strip().lower() == "none"
    return (
        isinstance(tool_choice, dict)
        and str(tool_choice.get("type") or "").lower() == "none"
    )


def resolve_tool_mode(tools: Any, tool_choice: Any = None) -> ToolMode:
    """Отсутствие инструментов приоритетнее запрета на их вызов."""
    if not tools:
        return ToolMode.OFF
    return ToolMode.FORBID if _tool_choice_none(tool_choice) else ToolMode.EMULATE


def check_unexpected_tool_calls(mode: ToolMode, tool_calls: Any) -> None:
    """Отклоняет нативные вызовы, запрещённые контрактом запроса."""
    if tool_calls and mode is not ToolMode.EMULATE:
        raise ValueError(f"unexpected tool calls in mode={mode.value}")


def format_tool_mode_log(
    tools: Any, tool_choice: Any, mode_spec: NormalizerModeSpec
) -> str:
    """Возвращает операционные поля без схем и аргументов инструментов."""
    choice = tool_choice.get("type") if isinstance(tool_choice, dict) else tool_choice
    return (
        f"req_tools={len(tools) if tools else 0} tool_choice={choice} "
        f"mode={mode_spec.mode.value} policy={mode_spec.policy.value}"
    )
