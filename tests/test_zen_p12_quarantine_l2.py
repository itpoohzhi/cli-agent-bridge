"""L2 real-process tests for opencode-zen-bridge P1.2 PGID quarantine & fallback barrier (W08, VER-001)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

_ZEN_DIR = Path(__file__).resolve().parents[1] / "bridges" / "opencode-zen-bridge"
if str(_ZEN_DIR) not in sys.path:
    sys.path.append(str(_ZEN_DIR))

from core.p12_flag_and_params import FLAG_ZEN_PGID_QUARANTINE  # noqa: E402
from core.pgid_cleanup_driver import PosixProcProbe, ProcessIdentity  # noqa: E402
from core.pgid_cleanup_policy import GroupProbeStatus  # noqa: E402
from zen_bridge.p12_cleanup_seam import (  # noqa: E402
    ZenP12CleanupSeam,
    capture_proc_identity,
    sourced_zen_cleanup_params,
)

_GRANDCHILD_SCRIPT = (
    "import signal, subprocess, sys, time; "
    "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
    "gc = subprocess.Popen([sys.executable, '-c', "
    "'import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)']); "
    "print(gc.pid, flush=True); "
    "time.sleep(60)"
)


def test_zen_seam_quarantines_slot_until_grandchild_dead_and_fallback_barrier_passes(tmp_path: Path) -> None:
    cfg = tmp_path / "zen-flags.json"
    cfg.write_text(json.dumps({FLAG_ZEN_PGID_QUARANTINE: True}), encoding="utf-8")
    params = sourced_zen_cleanup_params(term_grace_s=0.12, poll_interval_s=0.02, leader_wait_s=0.8)
    seam = ZenP12CleanupSeam(config_path=cfg, params_snapshot=params)

    proc = subprocess.Popen(
        [sys.executable, "-c", _GRANDCHILD_SCRIPT],
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert proc.stdout is not None
    gc_pid = int(proc.stdout.readline().strip())
    assert capture_proc_identity(proc) > 0

    released = threading.Event()
    try:
        assert seam.release_slot_after_proc(released.set, proc, "zen-turn-1") is False
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


def test_zen_fallback_barrier_refuses_spawn_when_pgid_quarantined_eperm(tmp_path: Path) -> None:
    cfg = tmp_path / "zen-flags.json"
    cfg.write_text(json.dumps({FLAG_ZEN_PGID_QUARANTINE: True}), encoding="utf-8")

    class _StubbornProbe:
        def __init__(self) -> None:
            self._t = 0.0

        def probe_live(self, pid: int) -> ProcessIdentity | None:
            return ProcessIdentity(pid=pid, pgid=pid, uid=501, start_time_us=12345)

        def probe_group(self, pgid: int) -> GroupProbeStatus:
            return GroupProbeStatus.EPERM

        def signal_group(self, pgid: int, sig: int) -> None:
            pass

        def now_s(self) -> float:
            self._t += 0.2
            return self._t

    class _FakeProc:
        pid = 99999
        _p12_start_time_us = 12345

        def poll(self) -> int | None:
            return None

    params = sourced_zen_cleanup_params(term_grace_s=0.1, poll_interval_s=0.005, leader_wait_s=0.5)
    seam = ZenP12CleanupSeam(config_path=cfg, params_snapshot=params, probe=_StubbornProbe())
    assert seam.confirm_dead_before_fallback(_FakeProc(), "zen-fb-stuck") is False
    seam.shutdown()
