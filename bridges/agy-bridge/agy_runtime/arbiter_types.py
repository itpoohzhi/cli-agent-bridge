"""Типы и состояния шагов арбитража контента agy-bridge."""

from __future__ import annotations

import hashlib
from typing import Any, final


@final
class _StepState:
    """Состояние одного шага планировщика (общее для SQLite и транскрипта).

    Текст мышления не хранится: только длины и sha256. observed_* — последний
    SQLite-снимок (любой режим), delivered_* — реально отданное клиенту.
    """

    def __init__(self) -> None:
        self.blob_len: int = -1
        self.blob_sha: str = ""
        self.observed_len: int = 0
        self.observed_sha: str = ""
        self.observed_final: bool = False
        self.delivered_len: int = 0
        self.delivered_sha = hashlib.sha256()
        self.final_len: int = 0
        self.final_sha: str = ""
        self.diverged: bool = False
        self.finalized: bool = False
        self.sql_seen: bool = False
        self.sql_done: bool = False
        self.canary_done: bool = False


@final
class _ArbStep:
    """Канонический шаг арбитра: источник-создатель, выданный префикс, заморозка."""

    __slots__ = ("origin", "emitted", "frozen")

    def __init__(self, origin: str) -> None:
        self.origin = origin
        self.emitted = ""
        self.frozen = False


def _scan_step(
    eq: dict[str, list[_ArbStep]],
    texts: list[str],
    source: str,
    idx: int | None,
    text: str,
    eligible_fn: Any,
) -> _ArbStep | None:
    import bisect

    for step in eq.get(text, ()):
        if eligible_fn(step, source, idx):
            return step
    if idx is None:
        candidates = [t for t in texts if len(text) >= len(t) and text.startswith(t)]
        if candidates:
            candidates.sort(key=len, reverse=True)
            for cand in candidates:
                for step in eq[cand]:
                    if eligible_fn(step, source, idx):
                        return step
        pos = bisect.bisect_left(texts, text)
        while pos < len(texts) and texts[pos].startswith(text):
            for step in eq[texts[pos]]:
                if step.origin != source and eligible_fn(step, source, idx):
                    return step
            pos += 1
    return None
