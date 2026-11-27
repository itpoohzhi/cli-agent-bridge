from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OverflowSpec:
    limit_bytes: int
    separator: str
    marker: str
    size_fn: Callable[[str], int]
    prune_fn: Callable[[str, int, str], str]


MIN_PROTECTED_FLOOR_BYTES = 256
SHRINK_ROLE_ORDER = ("tool", "assistant", "system", "digest", "user")
EVICT_ROLE_ORDER = ("tool", "digest", "assistant", "system")


def _join(parts: Sequence[tuple[str, str]], spec: OverflowSpec) -> str:
    return spec.separator.join(text for _, text in parts if text)


def _available(
    parts: Sequence[tuple[str, str]], index: int, spec: OverflowSpec
) -> int:
    other = [text for pos, (_, text) in enumerate(parts) if pos != index and text]
    other_bytes = spec.size_fn(spec.separator.join(other))
    if other:
        other_bytes += spec.size_fn(spec.separator)
    return spec.limit_bytes - other_bytes


def _role_indices(
    parts: Sequence[tuple[str, str]], role: str, spec: OverflowSpec
) -> list[int]:
    indices = (index for index, part in enumerate(parts) if part[0] == role and part[1])
    return sorted(
        indices, key=lambda index: spec.size_fn(parts[index][1]), reverse=True
    )


def _reduce_part(
    parts: list[tuple[str, str]], index: int, role: str, spec: OverflowSpec
) -> None:
    current_role, text = parts[index]
    available = _available(parts, index, spec)
    if role == "digest":
        replacement = (
            spec.prune_fn(text, available, spec.marker) if available >= 64 else ""
        )
        parts[index] = (current_role, replacement)
        return
    if available >= 0:
        parts[index] = (
            current_role,
            spec.prune_fn(text, available, spec.marker),
        )
        return
    if spec.size_fn(text) > MIN_PROTECTED_FLOOR_BYTES:
        parts[index] = (
            current_role,
            spec.prune_fn(text, MIN_PROTECTED_FLOOR_BYTES, spec.marker),
        )


def _shrink_role(
    parts: list[tuple[str, str]], role: str, spec: OverflowSpec
) -> str | None:
    for index in _role_indices(parts, role, spec):
        joined = _join(parts, spec)
        if spec.size_fn(joined) <= spec.limit_bytes:
            return joined
        _reduce_part(parts, index, role, spec)
    joined = _join(parts, spec)
    return joined if spec.size_fn(joined) <= spec.limit_bytes else None


def _evict_role(
    parts: list[tuple[str, str]], role: str, spec: OverflowSpec
) -> str | None:
    for index in _role_indices(parts, role, spec):
        joined = _join(parts, spec)
        if spec.size_fn(joined) <= spec.limit_bytes:
            return joined
        current_role, text = parts[index]
        available = _available(parts, index, spec)
        replacement = (
            spec.prune_fn(text, available, spec.marker) if available >= 0 else ""
        )
        parts[index] = (current_role, replacement)
    joined = _join(parts, spec)
    return joined if spec.size_fn(joined) <= spec.limit_bytes else None


def _shrink_tool_groups(
    parts: Sequence[tuple[str, str]], spec: OverflowSpec
) -> str | None:
    """Делегирует overflow атомарному домену при наличии assistant+tool группы."""
    if not any(
        role == "assistant" and "[tool call " in text for role, text in parts
    ):
        return None
    # Локальный импорт разрывает цикл инициализации: atomic_group_overflow
    # использует OverflowSpec и порядок ролей из этого модуля.
    from .atomic_group_overflow import OverflowItem, shrink_atomic

    grouped: list[OverflowItem] = []
    group = ""
    last_tool_pos = -1
    for pos, (role, text) in enumerate(parts):
        if role == "assistant" and "[tool call " in text:
            group = f"tool-{pos}"
            last_tool_pos = pos
        elif role != "tool" or not group:
            group = f"item-{pos}"
        grouped.append(OverflowItem(group=group, role=role, text=text))
    has_later_user = any(role == "user" for role, _ in parts[last_tool_pos + 1 :])
    active_group = grouped[last_tool_pos].group if not has_later_user else ""
    if active_group:
        grouped = [
            OverflowItem(item.group, item.role, item.text, item.group == active_group)
            for item in grouped
        ]
    return shrink_atomic(grouped, spec).prompt


def shrink_overflow_parts(
    items: Sequence[tuple[str, str]], spec: OverflowSpec
) -> str:
    parts = list(items)
    joined = _join(parts, spec)
    if spec.size_fn(joined) <= spec.limit_bytes:
        return joined
    if (fitted := _shrink_tool_groups(parts, spec)) is not None:
        return fitted
    if (fitted := _shrink_role(parts, "synthetic", spec)) is not None:
        return fitted
    if (fitted := _evict_role(parts, "synthetic", spec)) is not None:
        return fitted
    for role in SHRINK_ROLE_ORDER:
        if (fitted := _shrink_role(parts, role, spec)) is not None:
            return fitted
    for role in EVICT_ROLE_ORDER:
        if (fitted := _evict_role(parts, role, spec)) is not None:
            return fitted
    if (fitted := _shrink_role(parts, "user", spec)) is not None:
        return fitted
    joined = _join(parts, spec)
    pruned = spec.prune_fn(joined, max(spec.limit_bytes, 0), spec.marker)
    return pruned if spec.size_fn(pruned) <= max(spec.limit_bytes, 0) else ""
