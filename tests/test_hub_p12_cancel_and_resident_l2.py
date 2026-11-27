"""L2 tests for hub non-detached client cancel, detached protection, OPEN-16 resident wiring, and PGID gate (W12-W13, VER-002)."""

from __future__ import annotations

import email.message
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.p12_flag_and_params import (
    FLAG_HUB_NONDETACHED_CANCEL,
    FLAG_HUB_RESIDENT_WIRING,
    FLAG_HUB_TURN_MODE_PROPAGATION,
)
from core.p12_hub_cancel_seam import (
    HubP12CancelSeam,
    bind_resident_slot_pgid,
    reset_hub_p12_seam_for_tests,
    sourced_hub_cleanup_params,
    strip_http_message_turn_mode,
)
from core.pgid_cleanup_driver import PosixProcProbe
from core.pgid_cleanup_policy import GroupProbeStatus
from core.turn_mode_cancel_policy import (
    INTERNAL_TURN_MODE_HEADER,
    CancelDecision,
    SlotReleaseDecision,
    TurnMode,
)

_GRANDCHILD_SCRIPT = (
    "import signal, subprocess, sys, time; "
    "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
    "gc = subprocess.Popen([sys.executable, '-c', "
    "'import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)']); "
    "print(gc.pid, flush=True); "
    "time.sleep(60)"
)


class _StubTurnManager:
    def __init__(self) -> None:
        self.detached: list[str] = []
        self.cancelled: list[tuple[str, str]] = []

    def mark_detached(self, turn_id: str) -> None:
        self.detached.append(turn_id)

    def cancel_turn(self, turn_id: str, *, reason: str = "client_cancelled") -> None:
        self.cancelled.append((turn_id, reason))


def test_l2_nondetached_cancels_when_flag_on_and_detached_stays_protected(tmp_path: Path) -> None:
    flags_file = tmp_path / "hub-flags.json"
    flags_file.write_text(json.dumps({FLAG_HUB_NONDETACHED_CANCEL: True}), encoding="utf-8")
    seam = HubP12CancelSeam(config_path=flags_file)
    tm = _StubTurnManager()
    turn_nd = SimpleNamespace(turn_id="turn-nd-1")
    turn_det = SimpleNamespace(turn_id="turn-det-1")

    assert seam.on_client_disconnect(turn_nd, tm, TurnMode.NON_DETACHED) is CancelDecision.CANCEL_NONDETACHED
    assert tm.cancelled == [("turn-nd-1", "client_disconnected")]

    assert seam.on_client_disconnect(turn_det, tm, TurnMode.DETACHED) is CancelDecision.MARK_DETACHED
    assert tm.detached == ["turn-det-1"]
    assert tm.cancelled == [("turn-nd-1", "client_disconnected")]

    # UNKNOWN mode -> fail-closed NO_CANCEL
    assert seam.on_client_disconnect(turn_nd, tm, TurnMode.UNKNOWN) is CancelDecision.NO_CANCEL
    assert len(tm.cancelled) == 1

    # Flag off -> NO_CANCEL for NON_DETACHED, still MARK_DETACHED for DETACHED
    flags_file.write_text(json.dumps({FLAG_HUB_NONDETACHED_CANCEL: False}), encoding="utf-8")
    assert seam.on_client_disconnect(turn_nd, tm, TurnMode.NON_DETACHED) is CancelDecision.NO_CANCEL
    assert seam.on_client_disconnect(turn_det, tm, TurnMode.DETACHED) is CancelDecision.MARK_DETACHED
    seam.shutdown()


def test_l2_unconditional_http_header_strip_and_propagation_flag(tmp_path: Path) -> None:
    msg = email.message.Message()
    msg["Authorization"] = "Bearer abc"
    msg[INTERNAL_TURN_MODE_HEADER] = "detached"
    msg["x-bridge-internal-turn-mode"] = "non_detached"
    assert strip_http_message_turn_mode(msg) is True
    assert msg.get(INTERNAL_TURN_MODE_HEADER) is None
    assert msg.get("Authorization") == "Bearer abc"

    flags_file = tmp_path / "hub-flags.json"
    flags_file.write_text(json.dumps({FLAG_HUB_TURN_MODE_PROPAGATION: False}), encoding="utf-8")
    seam = HubP12CancelSeam(config_path=flags_file)
    assert seam.propagation_header(TurnMode.NON_DETACHED) is None
    flags_file.write_text(json.dumps({FLAG_HUB_TURN_MODE_PROPAGATION: True}), encoding="utf-8")
    assert seam.propagation_header(TurnMode.NON_DETACHED) == (INTERNAL_TURN_MODE_HEADER, "non_detached")
    seam.shutdown()


def test_l2_open16_resident_wiring_registers_pgid_only_when_flag_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reset_hub_p12_seam_for_tests()
    flags_file = tmp_path / "hub-flags.json"
    flags_file.write_text(json.dumps({FLAG_HUB_RESIDENT_WIRING: False}), encoding="utf-8")
    monkeypatch.setenv("BRIDGE_DYNAMIC_FLAGS_PATH", str(flags_file))

    registered: list[int] = []
    handle = SimpleNamespace(pid=42424)
    ctx = {"_register_pgid": registered.append}
    assert bind_resident_slot_pgid(handle, ctx) == 0
    assert registered == []

    flags_file.write_text(json.dumps({FLAG_HUB_RESIDENT_WIRING: True}), encoding="utf-8")
    assert bind_resident_slot_pgid(handle, ctx) == 42424
    assert registered == [42424]
    reset_hub_p12_seam_for_tests()


def test_l2_hub_slot_release_gate_holds_slot_until_pgid_dead_confirmed(tmp_path: Path) -> None:
    flags_file = tmp_path / "hub-flags.json"
    flags_file.write_text(json.dumps({FLAG_HUB_NONDETACHED_CANCEL: True}), encoding="utf-8")
    params = sourced_hub_cleanup_params(term_grace_s=0.12, poll_interval_s=0.02, leader_wait_s=0.4)
    seam = HubP12CancelSeam(config_path=flags_file, params_snapshot=params)

    proc = subprocess.Popen(
        [sys.executable, "-c", _GRANDCHILD_SCRIPT],
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert proc.stdout is not None
    gc_pid = int(proc.stdout.readline().strip())
    released = threading.Event()
    try:
        dec = seam.gate_slot_release("hub-turn-1", proc.pid, released.set, reap_leader=proc.poll)
        assert dec is SlotReleaseDecision.WAIT_PGID_CONFIRMED_DEAD
        assert not released.is_set()
        assert released.wait(timeout=3.0)
        assert proc.poll() is not None
        assert PosixProcProbe().probe_group(proc.pid) is GroupProbeStatus.GONE_ESRCH
        with pytest.raises(ProcessLookupError):
            os.kill(gc_pid, 0)
    finally:
        seam.shutdown()
        try:
            proc.kill()
            proc.wait(timeout=1.0)
        except OSError:
            pass


def test_f002_cancel_turn_runs_callbacks_before_release_and_protects_slot_on_unreg_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from core.turn_session_manager import TurnSessionManager

    reset_hub_p12_seam_for_tests()
    mgr = TurnSessionManager(state_root=tmp_path, persist_children_file=False)
    order: list[str] = []
    turn, _ = mgr.create_or_attach_turn(
        model="m1", backend="b1", cwd=str(tmp_path), messages=[{"role": "user", "content": "hi"}],
        owner_token_hash="h1", rid="r1", slot_release_fn=lambda: order.append("release"),
    )
    turn.add_cancel_callback(lambda: order.append("cb"))
    turn.pgid = None
    monkeypatch.setattr(mgr, "unregister_child_pgid", lambda _p: (_ for _ in ()).throw(RuntimeError("boom")))
    mgr.cancel_turn(turn.turn_id, reason="client_disconnected")
    # Default flag=False releases slot BEFORE callbacks (RW-001/F-005), and try/finally protects slot
    assert order == ["release", "cb"]
    reset_hub_p12_seam_for_tests()


def test_f006_cancel_turn_flag_on_live_pgid_reaps_without_reap_leader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from core.turn_session_manager import TurnSessionManager

    reset_hub_p12_seam_for_tests()
    flags_file = tmp_path / "hub-flags.json"
    flags_file.write_text(json.dumps({FLAG_HUB_NONDETACHED_CANCEL: True}), encoding="utf-8")
    monkeypatch.setenv("BRIDGE_DYNAMIC_FLAGS_PATH", str(flags_file))

    mgr = TurnSessionManager(state_root=tmp_path, persist_children_file=False)
    released = threading.Event()
    turn, _ = mgr.create_or_attach_turn(
        model="m1", backend="b1", cwd=str(tmp_path), messages=[{"role": "user", "content": "hi"}],
        owner_token_hash="h1", rid="r-f006", slot_release_fn=released.set,
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        turn.pgid = proc.pid
        mgr.cancel_turn(turn.turn_id, reason="client_disconnected")
        assert released.wait(timeout=4.0), "slot must release after TERM->ESRCH+reap even with reap_leader=None"
        assert PosixProcProbe().probe_group(proc.pid) is GroupProbeStatus.GONE_ESRCH
    finally:
        reset_hub_p12_seam_for_tests()
        try:
            proc.kill()
            proc.wait(timeout=1.0)
        except OSError:
            pass


def test_f015_cancel_turn_flag_off_keeps_pgid_registered_until_terminate_pgid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from core.turn_session_manager import TurnSessionManager

    reset_hub_p12_seam_for_tests()
    mgr = TurnSessionManager(state_root=tmp_path, persist_children_file=False)
    events: list[str] = []
    turn, _ = mgr.create_or_attach_turn(
        model="m1", backend="b1", cwd=str(tmp_path), messages=[{"role": "user", "content": "hi"}],
        owner_token_hash="h1", rid="r-f015", slot_release_fn=lambda: events.append("slot"),
    )
    turn.pgid = 55555
    turn.add_cancel_callback(lambda: events.append("cb"))
    monkeypatch.setattr(mgr, "unregister_child_pgid", lambda p: events.append(f"unreg:{p}"))
    monkeypatch.setattr(mgr, "_terminate_pgid", lambda p, g: (events.append(f"term:{p}"), mgr.unregister_child_pgid(p)))
    mgr.cancel_turn(turn.turn_id, reason="client_disconnected")
    assert events == ["slot", "cb", "term:55555", "unreg:55555"]
    reset_hub_p12_seam_for_tests()


def test_f014_check_leader_reaped_returns_false_on_reap_leader_oserror() -> None:
    from core.pgid_cleanup_driver import _check_leader_reaped
    from core.pgid_cleanup_policy import CleanupKey

    key = CleanupKey(turn_id="t", attempt_epoch=1, pgid=99999, leader_pid=99999, leader_start_time_us=0)
    def _boom() -> int | None:
        raise OSError("transient")
    reaped, gone, reused = _check_leader_reaped(key, _boom, PosixProcProbe())
    assert (reaped, gone, reused) == (False, True, False)


def test_f013_nonstream_detached_turn_sets_turn_mode_before_reply_json() -> None:
    import server as hub_server

    src = Path(hub_server.__file__).read_text(encoding="utf-8")
    assert "self._turn_mode = get_hub_p12_seam().resolve_mode_for_ctx(ctx)" in src
    assert "if detach_on_disconnect:" not in src
    h = object.__new__(hub_server.Handler)
    h._trace = None
    h._response_status = 0
    h._turn_mode = TurnMode.DETACHED
    h._telemetry_error_response = lambda *a: None
    h.send_response = lambda _c: None
    h.send_header = lambda _k, _v: None
    h.end_headers = lambda: None
    h.wfile = SimpleNamespace(write=lambda _b: (_ for _ in ()).throw(BrokenPipeError("gone")))
    h._send(200, {"ok": True})  # DETACHED swallows BrokenPipeError
    h._turn_mode = TurnMode.NON_DETACHED
    with pytest.raises(BrokenPipeError):
        h._send(200, {"ok": True})



