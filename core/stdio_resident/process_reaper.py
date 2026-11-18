"""Process-group inspection, termination, and orphan sandbox reaping."""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import signal
import subprocess
import time
from contextlib import suppress
from typing import Any

_POLL_INTERVAL_S = 0.05
_SIGKILL_DEADLINE_S = 2.0


def get_process_start_time(pid: int) -> str:
    """Return the OS start-time string for pid, or '' if unavailable."""

    if pid <= 0:
        return ""
    try:
        proc = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def is_pgid_alive(pgid: int) -> bool:
    """Return whether at least one process exists in process group pgid."""

    if pgid <= 0:
        return False
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def get_pgid_rss_bytes(pgid: int) -> int | None:
    """Return total RSS in bytes for process group pgid, or None on error."""

    if pgid <= 0:
        return None
    try:
        proc = subprocess.run(
            ["ps", "-axo", "pgid=,rss="],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None

    total_kib = 0
    found = False
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            row_pgid = int(parts[0])
            row_rss_kib = int(parts[1])
        except ValueError:
            continue
        if row_pgid == pgid:
            total_kib += max(0, row_rss_kib)
            found = True
    return total_kib * 1024 if found else None


def _matches_start_time(pid: int, start_time: str) -> bool:
    """Guard against PID reuse by requiring a matching non-empty start_time."""

    if not start_time:
        return False
    actual = get_process_start_time(pid)
    return bool(actual and actual == start_time)


def terminate_process_group(
    proc: Any,
    pgid: int,
    start_time: str,
    cancel_grace_s: float = 5.0,
    already_dead: bool = False,
) -> bool:
    """Idempotently terminate a process group, escalating to SIGKILL."""

    if already_dead or pgid <= 0:
        return True

    grace = max(0.0, cancel_grace_s)
    leader_pid = getattr(proc, "pid", pgid) if proc is not None else pgid
    # An un-reaped leader (alive or zombie) reserves PID/PGID in the kernel without ps.
    leader_alive_at_entry = proc is not None and proc.poll() is None
    pgid_dead = False
    try:
        if leader_alive_at_entry or _matches_start_time(leader_pid, start_time):
            grace_deadline = time.monotonic() + grace
            with suppress(ProcessLookupError, PermissionError, OSError):
                os.killpg(pgid, signal.SIGTERM)
            if leader_alive_at_entry:
                with suppress(subprocess.TimeoutExpired):
                    proc.wait(timeout=grace)
            while is_pgid_alive(pgid) and time.monotonic() < grace_deadline:
                time.sleep(min(_POLL_INTERVAL_S, max(0.0, grace_deadline - time.monotonic())))
    finally:
        if proc is not None:
            with suppress(OSError, ValueError):
                proc.poll()
        group_owned = leader_alive_at_entry or _matches_start_time(leader_pid, start_time)
        if not group_owned:
            pgid_dead = True
        else:
            deadline = time.monotonic() + _SIGKILL_DEADLINE_S
            sigkill_sent = False
            pgid_dead = not is_pgid_alive(pgid)
            while not pgid_dead:
                if not sigkill_sent:
                    with suppress(ProcessLookupError, PermissionError, OSError):
                        os.killpg(pgid, signal.SIGKILL)
                    sigkill_sent = True
                if proc is not None:
                    with suppress(OSError, ValueError):
                        proc.poll()
                if not is_pgid_alive(pgid):
                    pgid_dead = True
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(_POLL_INTERVAL_S, remaining))
    return pgid_dead


def _kill_verified_group(pid: int, pgid: int, start_time: str) -> None:
    """Terminate an orphaned process group only when pid matches start_time."""

    if not _matches_start_time(pid, start_time) or not is_pgid_alive(pgid):
        return
    with suppress(ProcessLookupError, PermissionError, OSError):
        os.killpg(pgid, signal.SIGTERM)
    deadline = time.monotonic() + 0.5
    while is_pgid_alive(pgid) and time.monotonic() < deadline:
        time.sleep(min(_POLL_INTERVAL_S, max(0.0, deadline - time.monotonic())))
    if is_pgid_alive(pgid) and _matches_start_time(pid, start_time):
        with suppress(ProcessLookupError, PermissionError, OSError):
            os.killpg(pgid, signal.SIGKILL)


def sweep_orphan_sandboxes(base_dir: str, stale_age_s: float = 0.0) -> int:
    """Reap orphaned turn-* sandboxes whose flock is no longer held."""

    if not os.path.isdir(base_dir):
        return 0
    swept = 0
    for name in sorted(os.listdir(base_dir)):
        if not (name.startswith("turn-") and name.endswith(".lock")):
            continue
        lock_path = os.path.join(base_dir, name)
        if not os.path.isfile(lock_path):
            continue
        try:
            if stale_age_s > 0.0 and (time.time() - os.stat(lock_path).st_mtime) < stale_age_s:
                continue
            with open(lock_path, "r", encoding="utf-8") as lock_file:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    continue
                if stale_age_s > 0.0:
                    age = time.time() - os.fstat(lock_file.fileno()).st_mtime
                    if age < stale_age_s:
                        continue
                raw = lock_file.read().strip()
                payload: dict[str, Any] = {}
                if raw:
                    with suppress(ValueError):
                        parsed = json.loads(raw)
                        if isinstance(parsed, dict):
                            payload = parsed
                pid = payload.get("pid")
                pgid = payload.get("pgid", pid)
                start_time = payload.get("start_time")
                if (
                    isinstance(pid, int) and not isinstance(pid, bool) and pid > 0
                    and isinstance(pgid, int) and not isinstance(pgid, bool) and pgid > 0
                    and isinstance(start_time, str) and bool(start_time.strip())
                ):
                    _kill_verified_group(pid, pgid, start_time)
                turn_dir = os.path.join(base_dir, name[:-5])
                if os.path.isdir(turn_dir):
                    shutil.rmtree(turn_dir, ignore_errors=True)
                elif os.path.lexists(turn_dir):
                    with suppress(OSError):
                        os.unlink(turn_dir)
                with suppress(OSError):
                    os.unlink(lock_path)
                swept += 1
        except OSError:
            continue
    return swept
