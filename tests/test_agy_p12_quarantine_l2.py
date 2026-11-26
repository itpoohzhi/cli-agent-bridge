"""L2 real-process tests for AGY bridge P1.2 PGID quarantine & orphan coordinator (W07, VER-001)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

_AGY_DIR = Path(__file__).resolve().parents[1] / "bridges" / "agy-bridge"
if str(_AGY_DIR) not in sys.path:
    sys.path.append(str(_AGY_DIR))

from agy_runtime.orphan_coordinator import CoordinatorDecision  # noqa: E402
from agy_runtime.p12_cleanup_seam import (  # noqa: E402
    AgyP12CleanupSeam,
    DisconnectInput,
    capture_run_identity,
    sourced_agy_cleanup_params,
)
from agy_runtime.process_supervisor import ProcessSupervisorConfig  # noqa: E402
from core.p12_flag_and_params import FLAG_AGY_ORPHAN_COORDINATOR, FLAG_AGY_PGID_QUARANTINE  # noqa: E402
from core.pgid_cleanup_driver import PosixProcProbe  # noqa: E402
from core.pgid_cleanup_policy import CleanupState, GroupProbeStatus  # noqa: E402

_GRANDCHILD_SCRIPT = (
    "import os, signal, subprocess, sys, time; "
    "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
    "gc = subprocess.Popen([sys.executable, '-c', "
    "'import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)']); "
    "print(gc.pid, flush=True); "
    "time.sleep(60)"
)


def test_agy_seam_quarantines_slot_until_term_ignoring_grandchild_dead(tmp_path: Path) -> None:
    cfg_path = tmp_path / "dynamic_config.json"
    cfg_path.write_text(json.dumps({FLAG_AGY_PGID_QUARANTINE: True}), encoding="utf-8")
    params = sourced_agy_cleanup_params(ProcessSupervisorConfig(kill_term_grace_s=0.12, poll_interval_s=0.02, kill_wait_s=0.2))
    seam = AgyP12CleanupSeam(config_path=cfg_path, params_snapshot=params)

    proc = subprocess.Popen(
        [sys.executable, "-c", _GRANDCHILD_SCRIPT],
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert proc.stdout is not None
    gc_pid = int(proc.stdout.readline().strip())
    run = SimpleNamespace(proc=proc)
    start_us = capture_run_identity(run)
    assert start_us > 0

    released = threading.Event()
    try:
        immediate = seam.release_slot_after_run(released.set, run, "turn-agy-1", attempt_epoch=1)
        assert immediate is False
        assert not released.is_set()
        assert released.wait(timeout=3.0), "slot must release after SIGKILL confirms PGID dead"
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


def test_agy_seam_flag_false_releases_immediately_and_orphan_coordinator_authoritative(tmp_path: Path) -> None:
    cfg_path = tmp_path / "dynamic_config.json"
    cfg_path.write_text(json.dumps({FLAG_AGY_PGID_QUARANTINE: False, FLAG_AGY_ORPHAN_COORDINATOR: True}), encoding="utf-8")
    seam = AgyP12CleanupSeam(config_path=cfg_path)

    released = []
    assert seam.release_slot_after_run(lambda: released.append(1), SimpleNamespace(proc=None), "t0") is True
    assert released == [1]

    # Intentional AGY orphan (tools>0, post-TTFC, active_orphans < orphan_max) -> ORPHAN_KEEP
    keep = seam.decide_disconnect(DisconnectInput("t1", 1, tools_count=2, ttfc_received=True, readers=0, active_orphans=0, orphan_max=5, allow_orphan=True, fast_client_gone_enabled=True))
    assert keep is CoordinatorDecision.ORPHAN_KEEP

    # Toolless or pre-TTFC -> TEARDOWN_REQUEST
    tear = seam.decide_disconnect(DisconnectInput("t2", 1, tools_count=0, ttfc_received=True, readers=0, active_orphans=0, orphan_max=5, allow_orphan=True, fast_client_gone_enabled=True))
    assert tear is CoordinatorDecision.TEARDOWN_REQUEST

    # Active reader -> KEEP
    stay = seam.decide_disconnect(DisconnectInput("t3", 1, tools_count=0, ttfc_received=False, readers=1, active_orphans=0, orphan_max=5, allow_orphan=False, fast_client_gone_enabled=True))
    assert stay is CoordinatorDecision.KEEP

    # When flag #3 is off -> returns None so legacy path runs unchanged
    cfg_path.write_text(json.dumps({FLAG_AGY_ORPHAN_COORDINATOR: False}), encoding="utf-8")
    assert seam.decide_disconnect(DisconnectInput("t4", 1, 0, False, 0, 0, 5, False, True)) is None
    assert seam.cleanup_state_for("missing", 1) is CleanupState.LIVE
    seam.shutdown()
