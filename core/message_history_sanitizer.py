"""Чистый санитайзер истории chat-сообщений (REQ-003, Zero I/O).

Чинит дефекты, дающие ошибку ``messages.N.M`` для вызовов инструментов:
пробельный ``content``/``text`` у ``assistant`` с вызовами, ``tool_use`` не в
хвосте блоков, непарные ``tool_calls``/``tool_use`` <-> ``tool``/``tool_result``
(недостающие — синтетический ``is_error``, висячие — удаляются).
Входные сообщения не мутируются; чистая история возвращается как есть.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import TypeAlias, cast

JsonMap: TypeAlias = Mapping[str, object]
MutableJsonMap: TypeAlias = dict[str, object]
Pending: TypeAlias = dict[str, tuple[str, str]]  # id -> (формат, имя)

SYNTHETIC_TOOL_INTERRUPTED_TEXT = (
    "[tool call interrupted before completion; no result recorded]"
)
_RESULT_ROLES = ("tool", "function")
_ALL_FORMATS = ("openai", "anthropic")


def _as_map(value: object) -> JsonMap | None:
    return cast("JsonMap", value) if isinstance(value, Mapping) else None


def _as_list(value: object) -> list[object] | None:
    return cast("list[object]", value) if isinstance(value, list) else None


def _block_type(block: object) -> str | None:
    block_map = _as_map(block)
    kind = block_map.get("type") if block_map is not None else None
    return kind if isinstance(kind, str) else None


def _is_blank_text(block: object) -> bool:
    block_map = _as_map(block)
    if block_map is None or block_map.get("type") != "text":
        return False
    text = block_map.get("text")
    return isinstance(text, str) and not text.strip()


def _same_items(left: Sequence[object], right: Sequence[object]) -> bool:
    return len(left) == len(right) and all(
        a is b for a, b in zip(left, right, strict=True)
    )


def _clean_assistant(msg: JsonMap) -> JsonMap:
    """Дефекты 1 и 2: убирает пробельный контент и группирует ``tool_use`` в хвост."""
    content = msg.get("content")
    blocks = _as_list(content)
    has_openai = bool(_as_list(msg.get("tool_calls")))
    has_use = blocks is not None and any(_block_type(b) == "tool_use" for b in blocks)
    if not (has_openai or has_use):
        return msg
    if isinstance(content, str):
        return msg if content.strip() else {**msg, "content": None}
    if blocks is None:
        return msg
    kept = [b for b in blocks if not _is_blank_text(b)]
    if has_use:
        kept = [b for b in kept if _block_type(b) != "tool_use"] + [
            b for b in kept if _block_type(b) == "tool_use"
        ]
    return msg if _same_items(kept, blocks) else {**msg, "content": kept or None}


def _call_entry(call: object) -> tuple[str, tuple[str, str]] | None:
    """Достаёт ``(id, (формат, имя))`` из ``tool_call`` / ``tool_use``."""
    call_map = _as_map(call)
    if call_map is None:
        return None
    call_id = call_map.get("id")
    if not isinstance(call_id, str) or not call_id:
        return None
    is_use = call_map.get("type") == "tool_use"
    holder = call_map if is_use else _as_map(call_map.get("function"))
    name = holder.get("name") if holder is not None else None
    return call_id, (
        "anthropic" if is_use else "openai",
        name if isinstance(name, str) and name else "unknown",
    )


def _collect_pending(msg: JsonMap) -> Pending:
    calls = list(_as_list(msg.get("tool_calls")) or [])
    calls += [
        b for b in _as_list(msg.get("content")) or [] if _block_type(b) == "tool_use"
    ]
    entries = (_call_entry(call) for call in calls)
    return dict(e for e in entries if e is not None)


def _take(pending: Pending, fmt: str) -> Pending:
    taken = {key: value for key, value in pending.items() if value[0] == fmt}
    for key in taken:
        del pending[key]
    return taken


def _synthetic_block(call_id: str) -> MutableJsonMap:
    return {
        "type": "tool_result",
        "tool_use_id": call_id,
        "is_error": True,
        "content": SYNTHETIC_TOOL_INTERRUPTED_TEXT,
    }


def _flush(
    pending: Pending, out: list[object], formats: Sequence[str] = _ALL_FORMATS
) -> bool:
    """Закрывает висячие вызовы синтетикой; True, если добавлено."""
    openai = _take(pending, "openai") if "openai" in formats else {}
    anthropic = _take(pending, "anthropic") if "anthropic" in formats else {}
    out.extend(
        {
            "role": "tool",
            "tool_call_id": cid,
            "name": entry[1],
            "content": SYNTHETIC_TOOL_INTERRUPTED_TEXT,
        }
        for cid, entry in openai.items()
    )
    if anthropic:
        out.append(
            {"role": "user", "content": [_synthetic_block(cid) for cid in anthropic]}
        )
    return bool(openai or anthropic)


def _step_result(msg: JsonMap, pending: Pending, out: list[object]) -> bool:
    """``role=tool|function``: валидный результат остаётся, висячий удаляется."""
    call_id = msg.get("tool_call_id")
    if isinstance(call_id, str) and pending.get(call_id, ("", ""))[0] == "openai":
        del pending[call_id]
        out.append(msg)
        return False
    if msg.get("role") == "function" and not call_id:  # легаси function-result без id
        out.append(msg)
        return False
    return True


def _step_user_results(
    msg: JsonMap, blocks: list[object], pending: Pending, out: list[object]
) -> bool:
    """``user`` с ``tool_result``: валидные — оставить, недостающие — дополнить."""
    changed = _flush(pending, out, ("openai",))
    wanted = _take(pending, "anthropic")
    seen: set[str] = set()
    results: list[object] = []
    others: list[object] = []
    for block in blocks:
        block_map = _as_map(block)
        use_id = block_map.get("tool_use_id") if block_map is not None else None
        if _block_type(block) != "tool_result":
            others.append(block)
        elif isinstance(use_id, str) and use_id in wanted and use_id not in seen:
            seen.add(use_id)
            results.append(block)
    missing = [_synthetic_block(cid) for cid in wanted if cid not in seen]
    new_blocks = results + missing + others
    if not new_blocks:
        return True
    if missing or not _same_items(new_blocks, blocks):
        out.append({**msg, "content": new_blocks})
        return True
    out.append(msg)
    return changed


def _step(msg: object, pending: Pending, out: list[object]) -> bool:
    """Обрабатывает одно сообщение; True, если история изменилась."""
    msg_map = _as_map(msg)
    role = msg_map.get("role") if msg_map is not None else None
    if msg_map is not None and role in _RESULT_ROLES:
        return _step_result(msg_map, pending, out)
    blocks = (
        _as_list(msg_map.get("content"))
        if msg_map is not None and role == "user"
        else None
    )
    if (
        msg_map is not None
        and blocks is not None
        and any(_block_type(b) == "tool_result" for b in blocks)
    ):
        return _step_user_results(msg_map, blocks, pending, out)
    changed = _flush(pending, out)
    if msg_map is not None and role == "assistant":
        cleaned = _clean_assistant(msg_map)
        pending.update(_collect_pending(cleaned))
        out.append(cleaned)
        return changed or cleaned is not msg_map
    out.append(msg)
    return changed


def is_history_sanitization_enabled() -> bool:
    import os
    val = os.environ.get("BRIDGE_SANITIZE_MESSAGE_HISTORY_ENABLED", "1").strip().lower()
    return val not in ("0", "false", "off", "no")


def sanitize_chat_messages(
    messages: Sequence[object], *, enabled: bool | None = None
) -> tuple[list[object], bool]:
    """Возвращает ``(messages, changed)``; чистая история — тот же список."""
    original = _as_list(messages)
    if enabled is None:
        enabled = is_history_sanitization_enabled()
    if not enabled:
        return (original if original is not None else list(messages)), False
    out: list[object] = []
    pending: Pending = {}
    changed = False
    for msg in messages:
        changed = _step(msg, pending, out) or changed
    changed = _flush(pending, out) or changed
    if not changed:
        return (original if original is not None else list(messages)), False
    return out, True


def sanitize_request_payload(
    raw: bytes, request: MutableJsonMap, *, enabled: bool | None = None
) -> tuple[bytes, MutableJsonMap]:
    """Обёртка ингресса: при ``changed=False`` — ``(raw, request)`` без dumps."""
    if enabled is None:
        enabled = is_history_sanitization_enabled()
    if not enabled:
        return raw, request
    messages = _as_list(request.get("messages"))
    if messages is None:
        return raw, request
    cleaned, changed = sanitize_chat_messages(messages, enabled=enabled)
    if not changed:
        return raw, request
    updated: MutableJsonMap = dict(request)
    updated["messages"] = cleaned
    return json.dumps(updated, ensure_ascii=False).encode("utf-8"), updated
