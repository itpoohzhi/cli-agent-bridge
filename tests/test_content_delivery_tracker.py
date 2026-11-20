"""L1: трекер фактов доставки `ContentDeliveryTracker` (AD-002 / BND-002, VER-011)."""

from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.content_delivery_tracker import ContentDeliveryTracker  # noqa: E402
from core.transport_failure_contracts import DeliveryFacts  # noqa: E402


def test_fresh_tracker_reports_nothing_delivered() -> None:
    facts = ContentDeliveryTracker().snapshot()
    assert facts == DeliveryFacts()
    assert facts.delivered is False


def test_keepalive_only_is_not_delivery() -> None:
    tracker = ContentDeliveryTracker()
    for _ in range(5):
        tracker.mark_keepalive()
    facts = tracker.snapshot()
    assert facts.keepalive_count == 5
    assert facts.delivered is False


def test_content_reasoning_tool_calls_and_events_count_as_delivery() -> None:
    for mark in (
        lambda t: t.mark_content("текст"),
        lambda t: t.mark_reasoning("мысль"),
        lambda t: t.mark_tool_calls(2),
        lambda t: t.mark_tool_event(),
    ):
        tracker = ContentDeliveryTracker()
        tracker.mark_keepalive()
        mark(tracker)
        assert tracker.snapshot().delivered is True


def test_sizes_are_utf8_bytes_and_accumulate() -> None:
    tracker = ContentDeliveryTracker()
    tracker.mark_content("абв")
    tracker.mark_content("ab")
    tracker.mark_reasoning("é")
    facts = tracker.snapshot()
    assert (facts.content_bytes, facts.reasoning_bytes) == (8, 2)


@pytest.mark.parametrize("value", ["", None, 0, 5, b"x", []])
def test_empty_or_non_text_deltas_are_not_delivery(value: object) -> None:
    tracker = ContentDeliveryTracker()
    tracker.mark_content(value)  # type: ignore[arg-type]
    tracker.mark_reasoning(value)  # type: ignore[arg-type]
    assert tracker.snapshot().delivered is False


@pytest.mark.parametrize("count", [0, -1, -10, 1.5, "2", None, True])
def test_invalid_counts_are_ignored(count: object) -> None:
    tracker = ContentDeliveryTracker()
    tracker.mark_tool_calls(count)  # type: ignore[arg-type]
    tracker.mark_tool_event(count)  # type: ignore[arg-type]
    facts = tracker.snapshot()
    assert (facts.tool_calls, facts.tool_events) == (0, 0)


def test_snapshot_is_frozen_and_independent_of_later_marks() -> None:
    tracker = ContentDeliveryTracker()
    tracker.mark_content("a")
    first = tracker.snapshot()
    tracker.mark_content("bb")
    second = tracker.snapshot()
    assert first is not second
    assert (first.content_bytes, second.content_bytes) == (1, 3)
    with pytest.raises(FrozenInstanceError):
        first.content_bytes = 99  # type: ignore[misc]


def test_two_trackers_do_not_share_state() -> None:
    one, two = ContentDeliveryTracker(), ContentDeliveryTracker()
    one.mark_content("x")
    assert two.snapshot().delivered is False


def test_tool_events_and_calls_accumulate() -> None:
    tracker = ContentDeliveryTracker()
    tracker.mark_tool_calls(2)
    tracker.mark_tool_calls()
    tracker.mark_tool_event(4)
    facts = tracker.snapshot()
    assert (facts.tool_calls, facts.tool_events) == (3, 4)


def test_state_is_private_to_the_tracker() -> None:
    """Публичного доступа к `_facts` нет в API: наружу только `snapshot()`."""
    public = [n for n in dir(ContentDeliveryTracker) if not n.startswith("_")]
    assert sorted(public) == [
        "mark_content", "mark_keepalive", "mark_reasoning", "mark_tool_calls", "mark_tool_event", "snapshot",
    ]
