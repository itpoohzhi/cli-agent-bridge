"""Чистый домен атомарного overflow групп истории (AD-012, CD-009, BND-001).

Группа assistant+tool_calls+tool_results сжимается пропорционально или
вытесняется только целиком; активная (carrier) не вытесняется — middle-prune
до floor 256 B на участника, иначе UNFIT. Без I/O, env и часов.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final, Protocol, final

from .history_user_classifier import is_synthetic_user_block

# Зеркало history_overflow_policy (сверяется тестом): разрыв цикла импортов.
MIN_PROTECTED_FLOOR_BYTES: Final = 256
SHRINK_ROLE_ORDER: Final = ("tool", "assistant", "system", "digest", "user")
EVICT_ROLE_ORDER: Final = ("tool", "digest", "assistant", "system")

__all__ = [
    "AtomicOverflowResult",
    "OverflowItem",
    "build_overflow_items",
    "shrink_atomic",
]


class OverflowSpec(Protocol):
    """Структурный контракт history_overflow_policy.OverflowSpec.

    Локальный Protocol (не импорт) разрывает цикл: history_overflow_policy
    делегирует сюда; реальный OverflowSpec удовлетворяет ему структурно.
    """

    @property
    def limit_bytes(self) -> int: ...
    @property
    def separator(self) -> str: ...
    @property
    def marker(self) -> str: ...
    @property
    def size_fn(self) -> Callable[[str], int]: ...
    @property
    def prune_fn(self) -> Callable[[str, int, str], str]: ...


class _OverflowBlock(Protocol):
    """Структурный контракт блока (удовлетворяется PromptBlock)."""

    @property
    def role(self) -> str: ...
    @property
    def rendered(self) -> str: ...


@dataclass(frozen=True, slots=True)
class OverflowItem:
    """Один overflow-блок с id группы и признаком активной группы."""

    group: str
    role: str
    text: str
    active: bool = False


@dataclass(frozen=True, slots=True)
class AtomicOverflowResult:
    """Итог: промпт в лимите либо явный UNFIT (активная группа не влезла)."""

    prompt: str
    unfit: bool = False


def _group_items(
    gid: str,
    group: Sequence[_OverflowBlock],
    carrier: Sequence[_OverflowBlock] | None,
) -> list[OverflowItem]:
    active = carrier is not None and tuple(group) == tuple(carrier)

    def role(block: _OverflowBlock) -> str:
        synthetic = block.role == "user" and block not in (carrier or ())
        return (
            "synthetic"
            if synthetic and is_synthetic_user_block(block.rendered)
            else block.role
        )

    return [OverflowItem(gid, role(b), b.rendered, active) for b in group]


def build_overflow_items(
    anchor_groups: Sequence[Sequence[_OverflowBlock]],
    digest: str,
    tail_groups: Sequence[Sequence[_OverflowBlock]],
    carrier: Sequence[_OverflowBlock] | None,
) -> tuple[OverflowItem, ...]:
    """Порядок промпта: якорь, digest, хвост; id "a<i>"/"t<i>"/"digest".

    Группа, равная carrier, active=True; пустой digest не добавляется.
    """
    items = [
        item
        for pos, group in enumerate(anchor_groups)
        for item in _group_items(f"a{pos}", group, carrier)
    ]
    if digest:
        items.append(OverflowItem(group="digest", role="digest", text=digest))
    items.extend(
        item
        for pos, group in enumerate(tail_groups)
        for item in _group_items(f"t{pos}", group, carrier)
    )
    return tuple(items)


def _prune_proportional(
    texts: Sequence[str], budget: int, spec: OverflowSpec, floor: int = 0
) -> list[str] | None:
    """Пропорциональный prune под бюджет; None, если участник исчез бы."""
    sizes = [spec.size_fn(text) for text in texts]
    total = sum(sizes)
    if total == 0 or total <= budget:
        return list(texts)
    shares = [max(budget * size // total, floor) for size in sizes]
    pruned = [
        spec.prune_fn(text, share, spec.marker)
        for text, share in zip(texts, shares, strict=True)
    ]
    if any(not out and text for out, text in zip(pruned, texts, strict=True)):
        return None
    return pruned


@final
class _Work:
    """Рабочая копия элементов; метрика байтов повторяет legacy overflow."""

    def __init__(self, items: Sequence[OverflowItem], spec: OverflowSpec) -> None:
        self.items = tuple(items)
        self.spec = spec
        self.texts = [item.text for item in self.items]
        self.groups: dict[str, tuple[int, ...]] = {}
        for pos, item in enumerate(self.items):
            self.groups[item.group] = (*self.groups.get(item.group, ()), pos)
        self.active = frozenset(
            gid
            for gid, indices in self.groups.items()
            if any(self.items[pos].active for pos in indices)
        )

    def joined(self) -> str:
        return self.spec.separator.join(text for text in self.texts if text)

    def fits(self) -> bool:
        return self.spec.size_fn(self.joined()) <= self.spec.limit_bytes

    def available(self, indices: tuple[int, ...]) -> int:
        skip = set(indices)
        other = [t for pos, t in enumerate(self.texts) if pos not in skip and t]
        other_bytes = self.spec.size_fn(self.spec.separator.join(other))
        if other:
            other_bytes += self.spec.size_fn(self.spec.separator)
        return self.spec.limit_bytes - other_bytes

    def role_groups(self, role: str) -> list[str]:
        scored: list[tuple[int, int, str]] = []
        for order, (gid, indices) in enumerate(self.groups.items()):
            if gid in self.active:
                continue
            if not any(
                self.items[pos].role == role and self.texts[pos] for pos in indices
            ):
                continue
            size = sum(self.spec.size_fn(self.texts[pos]) for pos in indices)
            scored.append((-size, order, gid))
        return [gid for _, _, gid in sorted(scored)]

    def shrink_group(self, gid: str, floor: int = 0) -> None:
        indices = self.groups[gid]
        sep_bytes = self.spec.size_fn(self.spec.separator)
        budget = self.available(indices) - (len(indices) - 1) * sep_bytes
        members = [self.texts[pos] for pos in indices]
        pruned = _prune_proportional(members, max(budget, 0), self.spec, floor)
        if pruned is not None:
            for pos, text in zip(indices, pruned, strict=True):
                self.texts[pos] = text

    def floor_user(self, gid: str) -> None:
        for pos in self.groups[gid]:
            text = self.texts[pos]
            if self.spec.size_fn(text) > MIN_PROTECTED_FLOOR_BYTES:
                self.texts[pos] = self.spec.prune_fn(
                    text, MIN_PROTECTED_FLOOR_BYTES, self.spec.marker
                )

    def shrink_role(self, role: str) -> bool:
        for gid in self.role_groups(role):
            if self.fits():
                return True
            available = self.available(self.groups[gid])
            if available < 0 and role != "user":
                continue
            if available < 0:
                self.floor_user(gid)
            else:
                self.shrink_group(gid)
        return self.fits()

    def evict_role(self, role: str) -> bool:
        for gid in self.role_groups(role):
            if self.fits():
                return True
            for pos in self.groups[gid]:
                self.texts[pos] = ""
        return self.fits()

    def shrink_active_fits(self) -> bool:
        for gid in sorted(self.active):
            self.shrink_group(gid, floor=MIN_PROTECTED_FLOOR_BYTES)
        return self.fits()


def shrink_atomic(
    items: Sequence[OverflowItem], spec: OverflowSpec
) -> AtomicOverflowResult:
    """Атомарно сжать/вытеснить группы под spec.limit_bytes.

    Порядок повторяет legacy overflow (synthetic первым, затем
    SHRINK_ROLE_ORDER/EVICT_ROLE_ORDER), но группа трогается только
    целиком: пропорциональный prune всех участников либо eviction всех.
    Активная группа сжимается последней до floor 256 B на участника;
    если и это не влезает — явный UNFIT (prompt пуст).
    """
    work = _Work(items, spec)
    steps = (
        work.fits,
        lambda: work.shrink_role("synthetic"),
        lambda: work.evict_role("synthetic"),
        *(lambda r=r: work.shrink_role(r) for r in SHRINK_ROLE_ORDER),
        *(lambda r=r: work.evict_role(r) for r in EVICT_ROLE_ORDER),
        work.shrink_active_fits,
    )
    if any(step() for step in steps):
        return AtomicOverflowResult(work.joined())
    return AtomicOverflowResult("", unfit=True)
