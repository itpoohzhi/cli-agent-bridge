"""Anthropic `cache_control` breakpoints для OpenAI-формата (opencode-go-claude).

OpenCode Go сам ставит единственный breakpoint в конец последнего сообщения: 0% cache hits
и 1.25x штраф записи кэша на каждом ходу. Модуль ставит до двух `{"type": "ephemeral"}`:
на system/developer-префикс и на префикс multi-turn истории. Чистая функция: входной payload
не мутируется; клиентский `cache_control` уважается (идемпотентность).
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any, Final

from core.runtime_env import DynamicFlagSource

FLAG_ANTHROPIC_CACHE_CONTROL: Final[str] = "BRIDGE_ANTHROPIC_CACHE_CONTROL_ENABLED"
_FLAG: Final[DynamicFlagSource] = DynamicFlagSource(FLAG_ANTHROPIC_CACHE_CONTROL, default=False)
DEFAULT_MIN_CACHE_CHARS = 2048
STRATEGY_ANTHROPIC_EPHEMERAL = "anthropic_ephemeral"
_SYSTEM_ROLES = ("system", "developer")


def is_anthropic_cache_control_enabled() -> bool:
    """Состояние флага (дефолт `false`: payload побайтно совпадает с прежним поведением)."""
    return _FLAG.enabled(fallback=False)


def _ephemeral() -> dict[str, str]:
    return {"type": "ephemeral"}


def _has_cache_control(node: Any) -> bool:
    """Рекурсивный поиск клиентского `cache_control` в messages/tools/system."""
    if isinstance(node, Mapping):
        return "cache_control" in node or any(_has_cache_control(v) for v in node.values())
    if isinstance(node, list):
        return any(_has_cache_control(item) for item in node)
    return False


def _is_text_block(block: Any) -> bool:
    return (
        isinstance(block, dict)
        and block.get("type") == "text"
        and isinstance(block.get("text"), str)
        and bool(block.get("text"))
    )


def _text_len(content: Any) -> int:
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(len(b["text"]) for b in content if _is_text_block(b))
    return 0


def _content(message: Any) -> Any:
    return message.get("content") if isinstance(message, dict) else None


def _mark(message: dict[str, Any]) -> bool:
    """Breakpoint на последний непустой текст сообщения; `False` — текста нет (tool-call/image-only)."""
    content = message.get("content")
    if isinstance(content, str) and content:
        message["content"] = [{"type": "text", "text": content, "cache_control": _ephemeral()}]
        return True
    if isinstance(content, list):
        for block in reversed(content):
            if _is_text_block(block):
                block["cache_control"] = _ephemeral()
                return True
    return False


def _role_indices(messages: list[Any], *, system: bool) -> list[int]:
    return [
        i
        for i, m in enumerate(messages)
        if isinstance(m, dict) and (m.get("role") in _SYSTEM_ROLES) == system
    ]


def _mark_system(messages: list[Any], min_chars: int) -> None:
    """Breakpoint 1: последнее непустое system/developer сообщение, если суммарный текст >= порога."""
    idxs = _role_indices(messages, system=True)
    if sum(_text_len(_content(messages[i])) for i in idxs) < min_chars:
        return
    for i in reversed(idxs):
        if _mark(messages[i]):
            return


def _mark_history(messages: list[Any], min_chars: int) -> None:
    """Breakpoint 2: префикс multi-turn истории (>= 3 не-system сообщений) до `non_sys[-2]` включительно."""
    idxs = _role_indices(messages, system=False)
    if len(idxs) < 3:
        return
    stop = idxs[-2]
    if sum(_text_len(_content(messages[i])) for i in range(stop + 1)) < min_chars:
        return
    for i in reversed(idxs[:-1]):
        if _mark(messages[i]):
            return


def inject_anthropic_cache_control(
    payload: Mapping[str, Any], *, min_chars: int = DEFAULT_MIN_CACHE_CHARS
) -> dict[str, Any]:
    """До двух `ephemeral` breakpoints; клиентский `cache_control` где-либо — payload без изменений."""
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        return dict(payload)
    if any(_has_cache_control(payload.get(key)) for key in ("messages", "tools", "system")):
        return dict(payload)
    out = copy.deepcopy(dict(payload))
    _mark_system(out["messages"], min_chars)
    _mark_history(out["messages"], min_chars)
    return out
