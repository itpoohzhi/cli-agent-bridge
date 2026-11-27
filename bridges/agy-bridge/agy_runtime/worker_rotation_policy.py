"""Чистая политика ротации persistent-слотов agy-bridge (AD-001/AD-002, BND-001).

Доменный слой: без I/O, env и чтения часов. Все факты запроса приносит
адаптер в иммутабельном ReuseProbe, состояние слота — в SlotBinding.
Ротации (ROTATE_*) адаптер исполняет через desync-eviction (release
cancel=True, сброс привязки) и одноразовый cold/resume spawn.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

__all__ = [
    "ReuseProbe",
    "SlotBinding",
    "SlotReuseVerdict",
    "decide_slot_reuse",
]


class SlotReuseVerdict(StrEnum):
    """Вердикт повторного использования живого слота воркера."""

    FRESH = "fresh"
    REUSE = "reuse"
    ROTATE_COLD = "rotate_cold"
    ROTATE_MISMATCH = "rotate_mismatch"
    ROTATE_UNANCHORED = "rotate_unanchored"

    @property
    def evicts_slot(self) -> bool:
        """True, если вердикт требует eviction слота через desync-путь."""
        return self in (
            SlotReuseVerdict.ROTATE_COLD,
            SlotReuseVerdict.ROTATE_MISMATCH,
            SlotReuseVerdict.ROTATE_UNANCHORED,
        )


@dataclass(frozen=True, slots=True)
class SlotBinding:
    """Иммутабельная привязка слота: счётчик ходов и cid владельца."""

    turns: int = 0
    bound_cid: str = ""

    def __post_init__(self) -> None:
        if type(self.turns) is not int or self.turns < 0:
            raise ValueError("turns must be a non-negative integer")
        if type(self.bound_cid) is not str:
            raise ValueError("bound_cid must be str")

    def after_turn(self, cid: str) -> SlotBinding:
        """Чистый переход после хода: +1 ход и актуальный cid владельца."""
        return SlotBinding(turns=self.turns + 1, bound_cid=cid)


@dataclass(frozen=True, slots=True)
class ReuseProbe:
    """Снимок фактов запроса, собранный адаптером до решения о reuse.

    reused — дофиксовый признак живого слота (turns_before > 0 или
    generation > 0); resume_base_idx — якорь pre-spawn плана (> 0 только
    для доказанного transcript/DB resume, <= 0 — unanchored sentinel).
    """

    strict: bool = True
    reused: bool = False
    run_cid: str = ""
    resume_base_idx: int = 0

    def __post_init__(self) -> None:
        if type(self.strict) is not bool or type(self.reused) is not bool:
            raise ValueError("strict and reused must be bool")
        if type(self.run_cid) is not str:
            raise ValueError("run_cid must be str")
        if type(self.resume_base_idx) is not int:
            raise ValueError("resume_base_idx must be int")


def decide_slot_reuse(probe: ReuseProbe, binding: SlotBinding | None) -> SlotReuseVerdict:
    """REUSE только при strict && run_cid != '' && bound_cid == run_cid && base_idx > 0.

    Legacy (strict=False) воспроизводит дофиксовые вердикты: живой слот
    переиспользуется без проверки cid и якоря. Новый слот (reused=False)
    всегда FRESH; binding=None трактуется как пустая привязка (fail-closed).
    """
    if not probe.strict:
        return SlotReuseVerdict.REUSE if probe.reused else SlotReuseVerdict.FRESH
    if not probe.reused:
        return SlotReuseVerdict.FRESH
    if not probe.run_cid:
        return SlotReuseVerdict.ROTATE_COLD
    bound_cid = binding.bound_cid if binding is not None else ""
    if bound_cid != probe.run_cid:
        return SlotReuseVerdict.ROTATE_MISMATCH
    if probe.resume_base_idx <= 0:
        return SlotReuseVerdict.ROTATE_UNANCHORED
    return SlotReuseVerdict.REUSE
