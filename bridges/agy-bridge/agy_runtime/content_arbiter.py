"""Двухуровневый арбитр planner-текста (stdout и transcript), AD-001."""

from __future__ import annotations

import bisect
import os
import sys
from typing import final
from .arbiter_types import _ArbStep, _scan_step

def _log(msg: str) -> None:
    if os.environ.get("AGY_BRIDGE_DEBUG"):
        sys.stderr.write(f"[arbiter] {msg}\n")

MAX_CONTENT_STEPS = int(
    os.environ.get("AGY_BRIDGE_MAX_STEPS_TRACKED", os.environ.get("AGY_BRIDGE_MAX_CONTENT_STEPS", "128"))
)
MAX_CONTENT_BYTES_PER_TURN = int(os.environ.get("AGY_BRIDGE_MAX_CONTENT_BYTES_PER_TURN", str(512 * 1024)))
MAX_RETAINED_DIVERGENT_BYTES = int(os.environ.get("AGY_BRIDGE_MAX_RETAINED_DIVERGENT_BYTES", str(64 * 1024)))

@final
class _ContentArbiter:
    """Двухуровневый арбитр planner-текста двух источников (stdout и transcript), AD-001."""

    def __init__(self, turn_id: str) -> None:
        self.turn_id = turn_id
        self.by_key: dict[tuple[str, str, int], _ArbStep] = {}
        self.step_count = 0
        self.eq_index: dict[str, list[_ArbStep]] = {}
        self.sorted_texts: list[str] = []
        # Те же индексы в разрезе источника-создателя: кандидат с валидным idx
        # сверяется только с шагами ДРУГИХ источников, без скана одноимённых.
        self._eq_by_source: dict[str, dict[str, list[_ArbStep]]] = {}
        self._sorted_by_source: dict[str, list[str]] = {}
        self.retained_divergent: list[str] = []
        self.retained_divergent_bytes = 0
        self.last_step: _ArbStep | None = None
        self.last_by_source: dict[str, _ArbStep] = {}
        self.chunks: list[str] = []
        self.bytes_total = 0
        self.overflow = False
        self.divergences = 0
        self.probes = 0
        self.last_result_diverged = False

    def _set_overflow(self, why: str) -> None:
        if not self.overflow:
            self.overflow = True
            _log(f"content-overflow turn={self.turn_id[:8] or '-'} why={why}")

    def _retain_divergent(self, text: str) -> None:
        """Удержать расходящийся текст (до MAX_RETAINED_DIVERGENT_BYTES суммарно)."""
        room = MAX_RETAINED_DIVERGENT_BYTES - self.retained_divergent_bytes
        if room <= 0 or not text:
            return
        data = text.encode("utf-8")
        if len(data) > room:
            text = data[:room].decode("utf-8", "ignore")
            data = text.encode("utf-8")
        if text:
            self.retained_divergent.append(text)
            self.retained_divergent_bytes += len(data)

    def retained_divergent_text(self) -> str:
        return "".join(self.retained_divergent)

    @staticmethod
    def _drop(
        eq: dict[str, list[_ArbStep]],
        texts: list[str],
        step: _ArbStep,
        old: str,
    ) -> None:
        bucket = eq.get(old)
        if bucket is None:
            return
        bucket.remove(step)
        if not bucket:
            del eq[old]
            pos = bisect.bisect_left(texts, old)
            if pos < len(texts) and texts[pos] == old:
                del texts[pos]

    @staticmethod
    def _put(
        eq: dict[str, list[_ArbStep]], texts: list[str], step: _ArbStep, text: str
    ) -> None:
        bucket = eq.setdefault(text, [])
        if not bucket:
            bisect.insort(texts, text)
        bucket.append(step)

    def _unindex(self, step: _ArbStep) -> None:
        old = step.emitted
        if not old:
            return
        self._drop(self.eq_index, self.sorted_texts, step, old)
        self._drop(
            self._eq_by_source.setdefault(step.origin, {}),
            self._sorted_by_source.setdefault(step.origin, []),
            step,
            old,
        )

    def _index(self, step: _ArbStep, text: str) -> None:
        self._put(self.eq_index, self.sorted_texts, step, text)
        self._put(
            self._eq_by_source.setdefault(step.origin, {}),
            self._sorted_by_source.setdefault(step.origin, []),
            step,
            text,
        )

    def _eligible(self, step: _ArbStep, source: str, idx: int | None) -> bool:
        self.probes += 1
        return idx is None or step.origin != source

    def _match(self, source: str, idx: int | None, text: str) -> _ArbStep | None:
        """Шаг, к которому относится кандидат без прямого ключа (уровень 2)."""
        if idx is None:
            found = self._scan(self.eq_index, self.sorted_texts, source, idx, text)
        else:
            # Валидный idx: подходят только шаги других источников; одноимённые
            # (N одинаковых шагов одного источника) не просматриваются вовсе.
            found = None
            for other, eq in self._eq_by_source.items():
                if other == source:
                    continue
                found = self._scan(eq, self._sorted_by_source[other], source, idx, text)
                if found is not None:
                    break
        if found is not None:
            return found
        refs: list[_ArbStep] = []
        if self.last_step is not None:
            refs.append(self.last_step)
        for other, step in self.last_by_source.items():
            if other != source and step not in refs:
                refs.append(step)
        for step in refs:
            if (
                step.emitted
                and text.startswith(step.emitted)
                and self._eligible(step, source, idx)
            ):
                return step
        return None

    def _scan(
        self,
        eq: dict[str, list[_ArbStep]],
        texts: list[str],
        source: str,
        idx: int | None,
        text: str,
    ) -> _ArbStep | None:
        return _scan_step(eq, texts, source, idx, text, self._eligible)

    def _advance(self, step: _ArbStep, source: str, text: str) -> str:
        if step.frozen:
            return ""
        prefix = step.emitted
        if text == prefix or (len(text) < len(prefix) and prefix.startswith(text)):
            return ""
        if not text.startswith(prefix):
            step.frozen = True
            self._retain_divergent(text)
            self.divergences += 1
            _log(f"content-divergence turn={self.turn_id[:8] or '-'} source={source}")
            return ""
        suffix = text[len(prefix) :]
        size = len(suffix.encode("utf-8"))
        if self.bytes_total + size > MAX_CONTENT_BYTES_PER_TURN:
            self._set_overflow("bytes")
            return ""
        self._unindex(step)
        step.emitted = text
        self._index(step, text)
        self.chunks.append(suffix)
        self.bytes_total += size
        self.last_step = step
        self.last_by_source[source] = step
        return suffix

    def offer(self, source: str, step_index: object, text: str, cid: str = "") -> str:
        """Кумулятивный снимок -> новый суффикс ('' — дубль, префикс или заморозка)."""
        if self.overflow or not text:
            return ""
        idx = (
            step_index
            if isinstance(step_index, int)
            and not isinstance(step_index, bool)
            and step_index >= 0
            else None
        )
        key = (self.turn_id, cid, idx) if idx is not None else None
        step = self.by_key.get(key) if key is not None else None
        if step is None:
            step = self._match(source, idx, text)
            if step is None:
                if self.step_count >= MAX_CONTENT_STEPS:
                    self._set_overflow("steps")
                    return ""
                step = _ArbStep(source)
                self.step_count += 1
            if key is not None:
                if len(self.by_key) >= 4 * MAX_CONTENT_STEPS:
                    self._set_overflow("aliases")
                    return ""
                self.by_key[key] = step
        return self._advance(step, source, text)

    def reconcile_result(self, text: str) -> str:
        """`result.response` как агрегат: досылается только то, чего ещё не было выдано."""
        self.last_result_diverged = False
        if self.overflow or not text:
            return ""
        emitted = "".join(self.chunks)
        if not emitted:
            if self.step_count >= MAX_CONTENT_STEPS:
                self._set_overflow("steps")
                return ""
            self.step_count += 1
            return self._advance(_ArbStep("result"), "result", text)
        if text == emitted or emitted.startswith(text):
            return ""
        if text.startswith(emitted):
            if self.step_count >= MAX_CONTENT_STEPS:
                self._set_overflow("steps")
                return ""
            self.step_count += 1
            return self._advance(_ArbStep("result"), "result", text[len(emitted) :])
        if text in self.eq_index:
            self.probes += 1
            return ""
        pos = bisect.bisect_left(self.sorted_texts, text)
        if pos < len(self.sorted_texts) and self.sorted_texts[pos].startswith(text):
            self.probes += 1
            return ""
        last = self.last_step
        if last is not None and last.emitted and text.startswith(last.emitted):
            return self._advance(last, "result", text)
        self._retain_divergent(text)
        self.divergences += 1
        self.last_result_diverged = True
        _log(f"content-divergence turn={self.turn_id[:8] or '-'} source=result")
        return ""
