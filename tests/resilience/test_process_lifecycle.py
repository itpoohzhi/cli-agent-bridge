"""Process lifecycle, process group management and reaper tests.

Guarantees:
1. Process groups are reliably terminated (SIGTERM -> SIGKILL escalation).
2. Leader processes are reaped to avoid zombies (no 'Z' state).
3. Deterministic execution with fast timeouts (< 5s per T-ISO-I3).
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest
from typing import Any
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BRIDGE_PY = _REPO_ROOT / "bridges" / "agy-bridge" / "server.py"
_POSIX = sys.platform != "win32"


def _load_agy_bridge() -> Any:
    """Load standalone agy-bridge server module for process isolation tests."""
    saved_path = list(sys.path)
    try:
        spec = importlib.util.spec_from_file_location(
            "agy_bridge_process_test_module", _BRIDGE_PY
        )
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path[:] = saved_path


srv = _load_agy_bridge()


def _spawn(argv: list[str], **kwargs: Any) -> subprocess.Popen:
    return subprocess.Popen(argv, start_new_session=True, **kwargs)


def _hard_kill(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass
    try:
        proc.wait(timeout=1.0)
    except (subprocess.TimeoutExpired, OSError):
        pass


def _ps_stat(pid: int) -> str:
    out = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)],
        capture_output=True,
        text=True,
        check=False,
    )
    return out.stdout.strip()


def _group_gone(pgid: int, within_s: float = 1.0) -> bool:
    deadline = time.monotonic() + within_s
    while time.monotonic() < deadline:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            pass
        time.sleep(0.02)
    return False


@unittest.skipUnless(_POSIX, "Requires POSIX process groups")
class ProcessLifecycleTests(unittest.TestCase):
    """Lifecycle test suite for child processes, group termination, and reaping."""

    def test_kill_group_reaps_when_group_already_gone(self) -> None:
        """When the process group has already exited, _kill_group reaps the leader."""
        proc = _spawn(["true"])
        try:
            deadline = time.monotonic() + 1.0
            while _ps_stat(proc.pid) != "Z" and time.monotonic() < deadline:
                time.sleep(0.02)
            with (
                mock.patch.object(srv.os, "killpg", side_effect=ProcessLookupError),
                mock.patch.object(proc, "wait", wraps=proc.wait) as wait,
            ):
                srv._kill_group(proc)
            wait.assert_called()
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(_ps_stat(proc.pid), "")
        finally:
            _hard_kill(proc)

    def test_kill_group_cleans_descendants_and_reaps_zombie(self) -> None:
        """_kill_group terminates process hierarchy and reaps zombie leader."""
        proc = _spawn(["sh", "-c", "sleep 10 & sleep 10 & wait"])
        try:
            deadline = time.monotonic() + 1.5
            while time.monotonic() < deadline:
                out = subprocess.run(
                    ["ps", "-o", "pid=", "-g", str(proc.pid)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if len(out.stdout.split()) >= 3:
                    break
                time.sleep(0.02)
            srv._kill_group(proc)
            self.assertIsNotNone(proc.returncode)
            self.assertTrue(_group_gone(proc.pid, within_s=1.0))
            self.assertEqual(_ps_stat(proc.pid), "")
        finally:
            _hard_kill(proc)

    def test_kill_group_escalates_to_sigkill(self) -> None:
        """Processes trapping SIGTERM are forcibly killed via SIGKILL after grace period."""
        proc = _spawn(
            ["sh", "-c", "trap '' TERM; echo ready; while :; do sleep 1; done"],
            stdout=subprocess.PIPE,
        )
        try:
            assert proc.stdout is not None
            self.assertEqual(proc.stdout.readline().strip(), b"ready")
            started = time.monotonic()
            with (
                mock.patch.object(srv, "KILL_TERM_GRACE_S", 0.15),
                mock.patch.object(srv, "KILL_WAIT_S", 1.0),
            ):
                srv._kill_group(proc, grace_s=0.15)
            elapsed = time.monotonic() - started
            self.assertEqual(proc.returncode, -signal.SIGKILL)
            self.assertGreaterEqual(elapsed, 0.1)
            self.assertLess(elapsed, 2.0)
            self.assertTrue(_group_gone(proc.pid, within_s=1.0))
        finally:
            _hard_kill(proc)
            if proc.stdout is not None:
                proc.stdout.close()
