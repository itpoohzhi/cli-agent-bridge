"""Трекер шагов хода для recovery (AD-005, BND-002): владелец состояния `_steps`.

Накапливает служебные ошибки и шаги планировщика, отдаёт неизменяемую проекцию
`TurnStepsSnapshot` для `evaluate_recovery`. Хранит признак once-per-turn (INV-S6).
"""

from __future__ import annotations

from core.transport_failure_contracts import StepRecord, TurnStepsSnapshot

ERROR_KIND = "error"
PLANNER_KIND = "planner"
DEFAULT_MAX_STEPS = 64


class ToolCallCompletionTracker:
    """Шаги одного хода: error/planner, ограниченное число, once-per-turn."""

    def __init__(self, max_steps: int = DEFAULT_MAX_STEPS) -> None:
        self._max_steps = max(2, int(max_steps))
        self._steps: list[StepRecord] = []
        self._attempted = False

    def _put(self, record: StepRecord) -> None:
        """Заменить шаг с тем же (index, kind) либо добавить; вытеснять самые старые."""
        self._steps = [s for s in self._steps if (s.index, s.kind) != (record.index, record.kind)]
        self._steps.append(record)
        if len(self._steps) > self._max_steps:
            self._steps = self._steps[-self._max_steps :]

    def note_error(self, index: int, text: str) -> None:
        """Зафиксировать служебную ошибку шага `index`."""
        self._put(StepRecord(int(index), ERROR_KIND, str(text)))

    def note_planner(self, index: int, content: str, complete: bool = True) -> None:
        """Зафиксировать шаг планировщика `index` с текстом и признаком завершённости."""
        self._put(StepRecord(int(index), PLANNER_KIND, str(content), bool(complete)))

    def try_begin_recovery(self) -> bool:
        """Once-per-turn: `True` только при первом вызове за ход."""
        if self._attempted:
            return False
        self._attempted = True
        return True

    def snapshot(self) -> TurnStepsSnapshot:
        """Неизменяемая проекция шагов, упорядоченная по индексу."""
        ordered = tuple(sorted(self._steps, key=lambda s: (s.index, s.kind)))
        return TurnStepsSnapshot(ordered, self._attempted)
