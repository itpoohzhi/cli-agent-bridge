"""L1: трекер шагов хода `ToolCallCompletionTracker` (AD-005 / BND-002, VER-012)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.tool_call_completion_tracker import ToolCallCompletionTracker  # noqa: E402
from core.tool_call_recovery_policy import evaluate_recovery  # noqa: E402
from core.transport_failure_contracts import ParsedToolCall, StepRecord  # noqa: E402

_CALL = '<tool_call>{"name": "read", "arguments": {"file_path": "/a"}}</tool_call>'


class _Port:
    def parse_all(self, text: str) -> tuple[ParsedToolCall, ...] | None:
        if not (text.startswith("<tool_call>") and text.endswith("</tool_call>")):
            return None
        body = json.loads(text[len("<tool_call>") : -len("</tool_call>")])
        return (ParsedToolCall("", body["name"], json.dumps(body["arguments"])),)


def test_empty_tracker_has_empty_snapshot() -> None:
    snap = ToolCallCompletionTracker().snapshot()
    assert (snap.steps, snap.recovery_attempted) == ((), False)


def test_steps_are_ordered_by_index_regardless_of_arrival() -> None:
    tracker = ToolCallCompletionTracker()
    tracker.note_planner(6, "p6")
    tracker.note_error(5, "e5")
    tracker.note_planner(4, "p4")
    assert [(s.index, s.kind) for s in tracker.snapshot().steps] == [(4, "planner"), (5, "error"), (6, "planner")]


def test_same_index_and_kind_replaces_previous_record() -> None:
    tracker = ToolCallCompletionTracker()
    tracker.note_planner(6, "partial", complete=False)
    tracker.note_planner(6, "final", complete=True)
    steps = tracker.snapshot().steps
    assert steps == (StepRecord(6, "planner", "final", True),)


def test_error_and_planner_with_same_index_coexist() -> None:
    tracker = ToolCallCompletionTracker()
    tracker.note_error(5, "e")
    tracker.note_planner(5, "p")
    assert len(tracker.snapshot().steps) == 2


def test_snapshot_is_immutable_tuple_and_detached_from_later_notes() -> None:
    tracker = ToolCallCompletionTracker()
    tracker.note_error(1, "e")
    snap = tracker.snapshot()
    tracker.note_planner(2, "p")
    assert isinstance(snap.steps, tuple) and len(snap.steps) == 1
    assert len(tracker.snapshot().steps) == 2


def test_once_per_turn_flag() -> None:
    tracker = ToolCallCompletionTracker()
    assert tracker.try_begin_recovery() is True
    assert tracker.try_begin_recovery() is False
    assert tracker.snapshot().recovery_attempted is True


def test_max_steps_bounds_memory_dropping_oldest() -> None:
    tracker = ToolCallCompletionTracker(max_steps=4)
    for i in range(10):
        tracker.note_planner(i, f"p{i}")
    assert [s.index for s in tracker.snapshot().steps] == [6, 7, 8, 9]


@pytest.mark.parametrize("limit", [0, 1, -5])
def test_tiny_max_steps_is_raised_to_safe_minimum(limit: int) -> None:
    tracker = ToolCallCompletionTracker(max_steps=limit)
    tracker.note_error(1, "e")
    tracker.note_planner(2, "p")
    assert len(tracker.snapshot().steps) == 2


def test_two_trackers_do_not_share_state() -> None:
    one, two = ToolCallCompletionTracker(), ToolCallCompletionTracker()
    one.note_error(1, "e")
    assert two.snapshot().steps == ()


def test_integration_with_recovery_policy_recovers_after_error() -> None:
    tracker = ToolCallCompletionTracker()
    tracker.note_planner(4, _CALL)
    tracker.note_error(5, "Malformed function call")
    tracker.note_planner(6, _CALL)
    decision = evaluate_recovery(tracker.snapshot(), _Port())
    assert decision.recovered is True and len(decision.calls) == 1


def test_integration_once_per_turn_blocks_second_recovery() -> None:
    tracker = ToolCallCompletionTracker()
    tracker.note_error(5, "e")
    tracker.note_planner(6, _CALL)
    assert tracker.try_begin_recovery() is True
    decision = evaluate_recovery(tracker.snapshot(), _Port())
    assert (decision.recovered, decision.reason) == (False, "once_per_turn")


def test_state_is_private_to_the_tracker() -> None:
    public = sorted(n for n in dir(ToolCallCompletionTracker) if not n.startswith("_"))
    assert public == ["note_error", "note_planner", "snapshot", "try_begin_recovery"]
