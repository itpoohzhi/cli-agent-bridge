"""L2 real-process macOS Darwin tests for PGID cleanup driver and O(1) bounded reaper (W04, VER-001)."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from core.p12_flag_and_params import CleanupParamSnapshot, SourcedParam, validate_cleanup_params
from core.pgid_cleanup_driver import (
    CachedDynamicFlagReader,
    PosixProcProbe,
    ProcessIdentity,
    darwin_probe_live_pid,
)
from core.pgid_cleanup_policy import CleanupKey, CleanupState, GroupProbeStatus
from core.pgid_reaper import BoundedPgidReaper, ReaperCapacityError


def _test_params(term_grace_s: float = 0.15, poll_s: float = 0.03) -> CleanupParamSnapshot:
    return CleanupParamSnapshot(
        service="test-l2",
        term_grace_s=SourcedParam(term_grace_s, "test:l2_sync"),
        poll_interval_s=SourcedParam(poll_s, "test:l2_sync"),
        leader_wait_s=SourcedParam(1.0, "test:l2_sync"),
    )


def _spawn_term_ignoring_parent_and_grandchild(tmp_path: Path) -> tuple[subprocess.Popen[bytes], Path]:
    child_pid_file = tmp_path / "grandchild.pid"
    script = (
        "import os, signal, subprocess, sys, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "gc = subprocess.Popen([sys.executable, '-c', "
        "'import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)'])\n"
        f"open({str(child_pid_file)!r}, 'w').write(str(gc.pid))\n"
        "time.sleep(30)\n"
    )
    proc = subprocess.Popen([sys.executable, "-c", script], start_new_session=True)
    deadline = time.monotonic() + 3.0
    while not child_pid_file.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert child_pid_file.exists()
    return proc, child_pid_file


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def test_l2_real_term_ignoring_grandchild_escalates_and_releases_only_on_dead_confirmed(tmp_path: Path) -> None:
    proc, gc_file = _spawn_term_ignoring_parent_and_grandchild(tmp_path)
    gc_pid = int(gc_file.read_text(encoding="utf-8").strip())
    ident = darwin_probe_live_pid(proc.pid)
    if sys.platform == "darwin":
        assert ident is not None and ident.pid == proc.pid and ident.pgid == proc.pid and ident.start_time_us > 0
    start_us = ident.start_time_us if ident is not None else 0

    released_ev = threading.Event()
    release_count = [0]

    def _on_release() -> None:
        release_count[0] += 1
        released_ev.set()

    reaper = BoundedPgidReaper(validate_cleanup_params(_test_params(term_grace_s=0.15, poll_s=0.03)))
    try:
        key = CleanupKey("turn-gc", 1, proc.pid, proc.pid, start_us, os.getuid())
        reaper.register_and_cancel(key, _on_release, reap_leader=proc.poll)
        # Immediately after TERM, grandchild ignoring SIGTERM is STILL alive -> slot MUST NOT be released!
        time.sleep(0.06)
        assert release_count[0] == 0
        assert _pid_alive(gc_pid)

        # Wait for escalation to SIGKILL + confirmed dead
        assert released_ev.wait(timeout=3.0)
        assert release_count[0] == 1
        assert reaper.get_state("turn-gc", 1) is CleanupState.RELEASED
        assert not _pid_alive(gc_pid)
        # Popen.returncode was preserved by reap_leader=proc.poll (negative SIGKILL, NOT stolen to 0!)
        assert proc.returncode is not None and proc.returncode != 0
    finally:
        reaper.shutdown(timeout_s=1.0)
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        proc.wait(timeout=2.0)


def test_l2_darwin_zombie_leader_reaped_via_popen_poll_preserves_nonzero_returncode() -> None:
    # Leader exits quickly with rc=7, becomes zombie before cancel starts
    proc = subprocess.Popen([sys.executable, "-c", "import sys; sys.exit(7)"], start_new_session=True)
    time.sleep(0.25)
    # On Darwin proc_pidinfo returns None for zombie, while proc.poll() reaps cleanly with rc=7
    if sys.platform == "darwin":
        assert darwin_probe_live_pid(proc.pid) is None

    released = [0]
    reaper = BoundedPgidReaper(validate_cleanup_params(_test_params(term_grace_s=0.05, poll_s=0.02)))
    try:
        key = CleanupKey("turn-zombie", 1, proc.pid, proc.pid, 0, os.getuid())
        reaper.register_and_cancel(key, lambda: released.__setitem__(0, released[0] + 1), reap_leader=proc.poll, start_ticker=False)
        reaper.tick_once()
        assert released[0] == 1
        assert reaper.get_state("turn-zombie", 1) is CleanupState.RELEASED
        assert proc.returncode == 7  # Exact exit code preserved, never corrupted to 0!
    finally:
        reaper.shutdown(timeout_s=0.5)


class _StubProbe:
    def __init__(self, group_status: GroupProbeStatus, ident: ProcessIdentity | None = None) -> None:
        self.group_status = group_status
        self.ident = ident
        self.signals: list[tuple[int, int]] = []
        self.now = 100.0

    def probe_live(self, _pid: int) -> ProcessIdentity | None:
        return self.ident

    def probe_group(self, _pgid: int) -> GroupProbeStatus:
        return self.group_status

    def signal_group(self, pgid: int, sig: int) -> None:
        self.signals.append((pgid, sig))

    def now_s(self) -> float:
        return self.now


def test_l2_eperm_quarantine_rollback_and_shutdown_hold_slot_until_dead_confirmed() -> None:
    probe = _StubProbe(GroupProbeStatus.EPERM, ProcessIdentity(pid=9999, pgid=9999, uid=0, start_time_us=555))
    alerts: list[tuple[CleanupKey, str]] = []
    released = [0]
    reaper = BoundedPgidReaper(
        validate_cleanup_params(_test_params(term_grace_s=1.0, poll_s=0.05)),
        probe=probe,
        on_alert=lambda k, m: alerts.append((k, m)),
    )
    key = CleanupKey("turn-eperm", 1, 9999, 9999, 555, 501)
    reaper.register_and_cancel(key, lambda: released.__setitem__(0, released[0] + 1), reap_leader=lambda: 0, start_ticker=False)
    probe.now = 102.0
    reaper.tick_once()  # escalates to KILL_SENT
    probe.now = 103.0
    reaper.tick_once()  # EPERM -> QUARANTINED + alert
    assert reaper.get_state("turn-eperm", 1) is CleanupState.QUARANTINED
    assert len(alerts) == 1
    assert released[0] == 0

    # Rollback flag_off & graceful shutdown MUST NOT release quarantined slot!
    reaper.notify_flag_off()
    reaper.shutdown(timeout_s=0.2)
    assert reaper.get_state("turn-eperm", 1) is CleanupState.QUARANTINED
    assert released[0] == 0

    # Explicit exit when group finally transitions to GONE_ESRCH
    probe.group_status = GroupProbeStatus.GONE_ESRCH
    probe.now = 104.0
    reaper.tick_once()
    assert reaper.get_state("turn-eperm", 1) is CleanupState.RELEASED
    assert released[0] == 1


def test_l2_reaper_saturation_never_evicts_quarantined_and_o1_threads() -> None:
    probe = _StubProbe(GroupProbeStatus.EPERM)
    reaper = BoundedPgidReaper(validate_cleanup_params(_test_params(term_grace_s=0.0)), bound=128, probe=probe)
    before_threads = threading.active_count()
    for i in range(128):
        key = CleanupKey(f"t-{i}", 1, 10000 + i, 10000 + i, 100 + i, 501)
        reaper.register_and_cancel(key, lambda: None, reap_leader=lambda: 0, start_ticker=False)
    with pytest.raises(ReaperCapacityError):
        reaper.register_and_cancel(CleanupKey("overflow", 1, 20000, 20000, 999, 501), lambda: None, reap_leader=lambda: 0, start_ticker=False)
    assert reaper.snapshot_counts()["active"] == 128
    assert threading.active_count() == before_threads


def test_l2_cached_flag_reader_atomic_replace_and_json_over_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    f = tmp_path / "dyn.json"
    monkeypatch.setenv("AGY_BRIDGE_PGID_QUARANTINE_ENABLED", "1")
    reader = CachedDynamicFlagReader(json_path=f)
    params = _test_params()
    assert reader.resolve("AGY_BRIDGE_PGID_QUARANTINE_ENABLED", params).enabled is True

    f.write_text(json.dumps({"AGY_BRIDGE_PGID_QUARANTINE_ENABLED": False}), encoding="utf-8")
    assert reader.resolve("AGY_BRIDGE_PGID_QUARANTINE_ENABLED", params).enabled is False

    tmp2 = tmp_path / "dyn.json.tmp"
    tmp2.write_text(json.dumps({"AGY_BRIDGE_PGID_QUARANTINE_ENABLED": True, "v": 2}), encoding="utf-8")
    os.replace(tmp2, f)
    assert reader.resolve("AGY_BRIDGE_PGID_QUARANTINE_ENABLED", params).enabled is True
    assert PosixProcProbe().probe_group(1) is GroupProbeStatus.GONE_ESRCH
