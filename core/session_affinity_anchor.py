"""System-prefix якорь диалога для одноходовых запросов с общим system-промптом.

Флаг BRIDGE_SESSION_AFFINITY_SYSTEM_ANCHOR_ENABLED (default OFF) позволяет
одноходовым запросам с длинным общим system/developer-промптом получать один
и тот же детерминированный x-opencode-session (KV-cache routing), не включая
первое user-сообщение в якорь. Scope-изоляция (namespace/model/user/ключи)
остаётся в core.session_affinity._scope().
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from core.runtime_env import flag_enabled

FLAG_SYSTEM_ANCHOR = "BRIDGE_SESSION_AFFINITY_SYSTEM_ANCHOR_ENABLED"
MIN_SYSTEM_ANCHOR_CHARS = 1024
_SYS_ROLES = ("system", "developer")


def is_system_anchor_enabled() -> bool:
    """Состояние kill-switch системного якоря (по умолчанию False)."""
    return flag_enabled(FLAG_SYSTEM_ANCHOR)


def _anchor_chars(
    top_level: Sequence[dict[str, Any]],
    sys_messages: Sequence[Any],
    field_fn: Callable[[Any, str], Any],
    content_text_fn: Callable[[Any], str | None],
) -> int:
    total = sum(len(str(item.get("content") or "")) for item in top_level)
    for message in sys_messages:
        text = content_text_fn(field_fn(message, "content"))
        total += len(text) if text is not None else 0
    return total


def _use_system_anchor(
    top_level: Sequence[dict[str, Any]],
    sys_messages: Sequence[Any],
    non_sys_count: int,
    anchor: Sequence[dict[str, Any]],
    field_fn: Callable[[Any, str], Any],
    content_text_fn: Callable[[Any], str | None],
    min_chars: int,
) -> bool:
    if not (is_system_anchor_enabled() and non_sys_count == 1 and anchor):
        return False
    return _anchor_chars(top_level, sys_messages, field_fn, content_text_fn) >= min_chars


def _append_user_fallback(
    anchor: list[dict[str, Any]],
    messages: Sequence[Any],
    field_fn: Callable[[Any, str], Any],
    msg_identity_fn: Callable[[Any], dict[str, Any]],
) -> None:
    user_msg = next((m for m in messages if field_fn(m, "role") == "user"), None)
    if user_msg is not None:
        anchor.append(msg_identity_fn(user_msg))
    if not anchor:
        anchor.append(msg_identity_fn(messages[0]))


def messages_dialog_anchor(
    messages: Sequence[Any],
    top_level: Sequence[dict[str, Any]],
    input_identity: list[dict[str, Any]] | None,
    field_fn: Callable[[Any, str], Any],
    msg_identity_fn: Callable[[Any], dict[str, Any]],
    content_text_fn: Callable[[Any], str | None],
    *,
    min_chars: int = MIN_SYSTEM_ANCHOR_CHARS,
) -> list[dict[str, Any]]:
    """Диалоговый якорь по messages; legacy-поведение при выключенном флаге."""
    dialog_anchor = list(top_level)
    if input_identity is not None:
        dialog_anchor.extend(input_identity)
    sys_messages = [m for m in messages if field_fn(m, "role") in _SYS_ROLES]
    dialog_anchor.extend(msg_identity_fn(m) for m in sys_messages)
    non_sys = [m for m in messages if field_fn(m, "role") not in _SYS_ROLES]
    if _use_system_anchor(
        top_level, sys_messages, len(non_sys), dialog_anchor, field_fn, content_text_fn, min_chars
    ):
        return dialog_anchor
    _append_user_fallback(dialog_anchor, messages, field_fn, msg_identity_fn)
    return dialog_anchor