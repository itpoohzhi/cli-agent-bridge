"""L2 subprocess PGID teardown & orphan-fencing integration test."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from core.stdio_resident.config import StdioPoolConfig
from core.stdio_resident.process_pool import ResidentProcessPool
from core.stdio_resident.types import SlotAffinityKey

ROOT = Path(__file__).resolve().parents[1]


def _spawn_grandchild_script() -> list[str]:
    code = (
        "import os, subprocess, sys, time; "
        "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
        "print(f'CHILD:{c.pid}', flush=True); "
        "time.sleep(30)"
    )
    return [sys.executable, "-c", code]


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def test_l2_subprocess_pgid_fenced_teardown_within_3s() -> None:
    cfg = StdioPoolConfig(max_slots=2, cancel_grace_s=0.1, shutdown_timeout_s=1.0, enabled=True)
    pool = ResidentProcessPool(cfg)
    child_pid = 0
    try:
        key = SlotAffinityKey("o1", "c1", "b1", "m1", "low", str(ROOT), env_digest="d1")
        slot = pool.acquire(key, _spawn_grandchild_script, str(ROOT))
        pgid = getattr(slot.handle, "_pgid", slot.handle.pid)
        kind, tagged = slot.handle.read_stdout_line_outcome(timeout_s=2.0)
        assert kind == "line" and tagged is not None and "CHILD:" in tagged.line
        child_pid = int(tagged.line.strip().split(":", 1)[1])
        assert _alive(slot.handle.pid) and _alive(child_pid)

        t0 = time.monotonic()
        pool.release(slot.slot_id, success=True, lease_id=slot.lease_id)
        closed = pool.close_if_idle(slot.slot_id, slot.handle.generation)
        elapsed = time.monotonic() - t0
        assert closed is True
        assert elapsed <= 3.0
        assert pgid > 0
    finally:
        pool.shutdown(timeout_s=1.0)

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and (_alive(child_pid)):
        time.sleep(0.05)
    assert not _alive(child_pid)
