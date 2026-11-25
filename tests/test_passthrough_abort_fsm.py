"""Unit tests for PassthroughAbortFSM (Wave 1)."""

from __future__ import annotations

import threading

from core.passthrough_abort_fsm import AbortState, PassthroughAbortFSM, fsm_enabled


def test_first_writer_wins_client_gone_blocks_deadline() -> None:
    aborts: list[str] = []
    fsm = PassthroughAbortFSM(lambda: aborts.append("abort"))

    assert fsm.state is AbortState.ACTIVE
    assert fsm.on_client_gone() is True
    assert fsm.on_deadline() is False
    assert fsm.on_upstream_error() is False
    assert fsm.on_completed() is False
    assert fsm.state is AbortState.CLIENT_GONE
    assert fsm.is_client_cancelled() is True
    assert fsm.is_timeout() is False
    assert aborts == ["abort"]


def test_first_writer_wins_deadline_preserved_over_late_client_gone() -> None:
    aborts: list[str] = []
    fsm = PassthroughAbortFSM(lambda: aborts.append("abort"))

    assert fsm.on_deadline() is True
    assert fsm.on_client_gone() is False
    assert fsm.state is AbortState.UPSTREAM_TIMEOUT
    assert fsm.is_timeout() is True
    assert fsm.is_client_cancelled() is False
    assert aborts == ["abort"]


def test_explicit_cancel_and_completed_transitions() -> None:
    fsm_cancel = PassthroughAbortFSM()
    assert fsm_cancel.on_explicit_cancel() is True
    assert fsm_cancel.is_client_cancelled() is True
    assert fsm_cancel.is_timeout() is False

    fsm_done = PassthroughAbortFSM()
    assert fsm_done.on_completed() is True
    assert fsm_done.on_deadline() is False
    assert fsm_done.is_aborted is False


def test_concurrent_race_latches_exactly_one_abort() -> None:
    aborts: list[int] = []
    lock = threading.Lock()
    fsm = PassthroughAbortFSM(lambda: _append(lock, aborts))
    barrier = threading.Barrier(4)
    results: list[bool] = []

    def racer(fn):
        barrier.wait()
        ok = fn()
        with lock:
            results.append(ok)

    threads = [
        threading.Thread(target=racer, args=(fsm.on_client_gone,)),
        threading.Thread(target=racer, args=(fsm.on_deadline,)),
        threading.Thread(target=racer, args=(fsm.on_explicit_cancel,)),
        threading.Thread(target=racer, args=(fsm.on_completed,)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=2)

    assert results.count(True) == 1
    assert len(aborts) <= 1


def _append(lock: threading.Lock, items: list[int]) -> None:
    with lock:
        items.append(1)


def test_env_rollback_flag(monkeypatch) -> None:
    monkeypatch.delenv("BRIDGE_PASSTHROUGH_ABORT_FSM", raising=False)
    assert fsm_enabled() is True
    monkeypatch.setenv("BRIDGE_PASSTHROUGH_ABORT_FSM", "0")
    assert fsm_enabled() is False
    monkeypatch.setenv("BRIDGE_PASSTHROUGH_ABORT_FSM", "1")
    assert fsm_enabled() is True


def test_clear_callback_breaks_reference_cycle() -> None:
    import gc
    import weakref

    class _Holder:
        def __init__(self) -> None:
            self.fsm = PassthroughAbortFSM(self._cb)

        def _cb(self) -> None:
            pass

    holder = _Holder()
    ref = weakref.ref(holder)
    fsm = holder.fsm
    fsm.clear_callback()
    del holder
    gc.collect()
    assert ref() is None
