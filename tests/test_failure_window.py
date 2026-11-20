"""L1: окно недавних сбоев `FailureWindow` (AD-003 / BND-002, VER-005)."""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.failure_window import DEFAULT_MAXLEN, DEFAULT_WINDOW_S, FailureWindow  # noqa: E402


def test_defaults_match_architecture() -> None:
    assert (DEFAULT_WINDOW_S, DEFAULT_MAXLEN) == (60.0, 256)


def test_record_counts_events_inside_window() -> None:
    window = FailureWindow(window_s=60.0)
    assert [window.record(t) for t in (0.0, 10.0, 20.0)] == [1, 2, 3]
    assert window.recent_count(20.0) == 3


def test_events_expire_by_injected_clock_boundary_exclusive() -> None:
    """Событие на границе `now - window_s` уже вытеснено; чуть новее — остаётся."""
    window = FailureWindow(window_s=60.0)
    _ = window.record(0.0)
    _ = window.record(10.0)
    assert window.recent_count(59.9) == 2
    assert window.recent_count(60.0) == 1
    assert window.recent_count(70.0) == 0


def test_record_evicts_stale_events_first() -> None:
    window = FailureWindow(window_s=5.0)
    _ = window.record(0.0)
    assert window.record(100.0) == 1


def test_maxlen_bounds_memory_dropping_oldest() -> None:
    window = FailureWindow(window_s=1e9, maxlen=4)
    for t in range(10):
        _ = window.record(float(t))
    assert window.snapshot(10.0) == (6.0, 7.0, 8.0, 9.0)
    assert window.recent_count(10.0) == 4


def test_snapshot_is_immutable_copy_not_internal_state() -> None:
    window = FailureWindow()
    _ = window.record(1.0)
    snap = window.snapshot(1.0)
    assert isinstance(snap, tuple)
    _ = window.record(2.0)
    assert snap == (1.0,)
    assert window.snapshot(2.0) == (1.0, 2.0)


def test_clear_resets_window() -> None:
    window = FailureWindow()
    _ = window.record(1.0)
    window.clear()
    assert window.recent_count(1.0) == 0


@pytest.mark.parametrize("window_s", [0.0, -1.0, float("nan")])
def test_invalid_window_is_rejected(window_s: float) -> None:
    with pytest.raises(ValueError):
        FailureWindow(window_s=window_s)


@pytest.mark.parametrize("maxlen", [0, -3])
def test_invalid_maxlen_is_rejected(maxlen: int) -> None:
    with pytest.raises(ValueError):
        FailureWindow(maxlen=maxlen)


def test_concurrent_records_are_all_counted_under_lock() -> None:
    window = FailureWindow(window_s=1e9, maxlen=256)
    start = threading.Barrier(4)

    def worker(base: int) -> None:
        _ = start.wait(timeout=10)
        for i in range(50):
            _ = window.record(float(base * 1000 + i))

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert not any(t.is_alive() for t in threads)
    assert window.recent_count(1e8) == 200


def test_clock_going_backwards_does_not_crash_or_grow_unbounded() -> None:
    window = FailureWindow(window_s=10.0, maxlen=8)
    _ = window.record(100.0)
    _ = window.record(50.0)
    assert window.recent_count(100.0) <= 8


def test_two_windows_do_not_share_state() -> None:
    first, second = FailureWindow(), FailureWindow()
    _ = first.record(1.0)
    assert second.recent_count(1.0) == 0
