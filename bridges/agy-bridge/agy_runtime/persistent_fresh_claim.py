"""Чистый Zero-I/O доменный модуль решения о свежести аренды persistent-слота."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = [
    "FRESH_CLAIM_TRANSITIONS",
    "ClaimInput",
    "FreshClaimDecision",
    "FreshClaimState",
    "FreshClaimVerdict",
    "LeaseFacts",
    "classify_fresh_lease",
    "decide_fresh_claim",
    "next_fresh_claim_state",
]


class FreshClaimState(Enum):
    """Состояние конечного автомата «свежей» аренды в рамках одного хода."""

    INITIAL = "initial"
    ROTATED_ONCE = "rotated_once"
    DONE_KEEP = "done_keep"
    DONE_COLD_FALLBACK = "done_cold_fallback"


class FreshClaimVerdict(Enum):
    """Вердикт классификации аренды: оставить слот или ротировать."""

    NO_LEASE = "no_lease"
    KEEP_RESUME = "keep_resume"
    KEEP_STANDBY = "keep_standby"
    KEEP_FRESH = "keep_fresh"
    ROTATE_HISTORY = "rotate_history"
    ROTATE_REUSED = "rotate_reused"
    ROTATE_INVALID = "rotate_invalid"


@dataclass(frozen=True, slots=True)
class LeaseFacts:
    """Наблюдаемые факты об аренде слота (без ссылок на живые ресурсы)."""

    turns_before: int
    reused: bool
    standby_claimed: bool
    generation: int


@dataclass(frozen=True, slots=True)
class ClaimInput:
    """Вход решения: признак cid, kill-switch, номер попытки и факты аренды."""

    has_cid: bool
    enabled: bool
    attempt: int
    lease: LeaseFacts | None


@dataclass(frozen=True, slots=True)
class FreshClaimDecision:
    """Решение: что делать с текущей арендой и каким будет следующее состояние."""

    verdict: FreshClaimVerdict
    discard_current: bool
    reacquire: bool
    cold_fallback: bool
    next_state: FreshClaimState
    shadow_would_rotate: bool


_Table = dict[tuple[FreshClaimState, FreshClaimVerdict], FreshClaimState]

_ROTATE_VERDICTS = frozenset(
    v for v in FreshClaimVerdict if v.name.startswith("ROTATE_")
)

_STATE_BY_ATTEMPT = (FreshClaimState.INITIAL, FreshClaimState.ROTATED_ONCE)
_ON_ROTATE = {
    FreshClaimState.INITIAL: FreshClaimState.ROTATED_ONCE,
    FreshClaimState.ROTATED_ONCE: FreshClaimState.DONE_COLD_FALLBACK,
}
FRESH_CLAIM_TRANSITIONS: _Table = {
    (s, v): r if v in _ROTATE_VERDICTS else FreshClaimState.DONE_KEEP
    for s, r in _ON_ROTATE.items()
    for v in FreshClaimVerdict
}


def next_fresh_claim_state(
    state: FreshClaimState, verdict: FreshClaimVerdict
) -> FreshClaimState:
    """Возвращает следующее состояние; для недопустимой пары бросает ValueError."""
    if (state, verdict) not in FRESH_CLAIM_TRANSITIONS:
        raise ValueError(f"invalid transition: {state.value} + {verdict.value}")
    return FRESH_CLAIM_TRANSITIONS[(state, verdict)]


def _classify_with_lease(lease: LeaseFacts) -> FreshClaimVerdict:
    """Классификация при отсутствии cid; порядок правил критичен."""
    if lease.turns_before < 0 or lease.generation < 0:
        return FreshClaimVerdict.ROTATE_INVALID
    # Standby на нулевом ходе проверяется СТРОГО до reused (у него reused=True).
    if lease.standby_claimed and lease.turns_before == 0:
        return FreshClaimVerdict.KEEP_STANDBY
    if lease.turns_before > 0:
        return FreshClaimVerdict.ROTATE_HISTORY
    if lease.reused:
        return FreshClaimVerdict.ROTATE_REUSED
    return FreshClaimVerdict.KEEP_FRESH


def classify_fresh_lease(has_cid: bool, lease: LeaseFacts | None) -> FreshClaimVerdict:
    """Классифицирует аренду по фактам: нет аренды, resume по cid либо по истории."""
    if lease is None:
        return FreshClaimVerdict.NO_LEASE
    if has_cid:
        return FreshClaimVerdict.KEEP_RESUME
    return _classify_with_lease(lease)


def decide_fresh_claim(inp: ClaimInput) -> FreshClaimDecision:
    """Принимает решение: keep, shadow (без ротации), ротация или cold fallback."""
    if inp.attempt not in (0, 1):
        raise ValueError("attempt must be 0 or 1")
    verdict = classify_fresh_lease(inp.has_cid, inp.lease)
    next_st = next_fresh_claim_state(_STATE_BY_ATTEMPT[inp.attempt], verdict)
    if verdict not in _ROTATE_VERDICTS:
        return FreshClaimDecision(verdict, False, False, False, next_st, False)
    if not inp.enabled:
        done = FreshClaimState.DONE_KEEP
        return FreshClaimDecision(verdict, False, False, False, done, True)
    first = inp.attempt == 0
    return FreshClaimDecision(verdict, True, first, not first, next_st, False)
