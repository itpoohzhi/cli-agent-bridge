"""Вендор-агностичная политика бюджета промпта и ленивая материализация (D1, W6)."""

from __future__ import annotations

from collections.abc import Callable, MutableMapping
from typing import final


def compute_prompt_budget(
    *,
    max_cap_bytes: int,
    env_cap_bytes: int | None,
    floor_bytes: int,
    reserve_bytes: int,
) -> int:
    """Вычисляет итоговый бюджет промпта с учётом потолка, нижней границы и резерва."""
    floor = max(1, int(floor_bytes))
    cap = max(floor, int(max_cap_bytes))
    requested = int(env_cap_bytes) if isinstance(env_cap_bytes, int) else cap
    clamped = max(floor, min(cap, requested))
    return max(floor, clamped - max(0, int(reserve_bytes)))


@final
class LazyPromptMaterializer:
    """Однократная ленивая материализация промпта с кэшированием (0 аллокаций на горячем resume=1)."""

    def __init__(self, builder: Callable[[], str]) -> None:
        self._builder = builder
        self._cached: str | None = None

    @property
    def materialized(self) -> bool:
        """Флаг: был ли промпт фактически построен."""
        return isinstance(self._cached, str)

    def get(self) -> str:
        """Возвращает промпт, строя его не более одного раза."""
        if not isinstance(self._cached, str):
            self._cached = self._builder()
        return self._cached


def resolve_ctx_prompt(ctx: MutableMapping[str, object], key: str) -> str:
    """Извлекает str из ctx[key]; при LazyPromptMaterializer материализует и кэширует."""
    raw = ctx.get(key)
    result = ""
    if isinstance(raw, LazyPromptMaterializer):
        result = raw.get()
        ctx[key] = result
    elif isinstance(raw, str):
        result = raw
    return result
