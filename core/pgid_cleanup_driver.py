"""Injectable Darwin-safe PGID cleanup driver and cached flag/param I/O reader (W03)."""

from __future__ import annotations

import ctypes
import errno
import json
import os
import signal
import struct
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from core.p12_flag_and_params import CleanupParamSnapshot, FlagResolution, resolve_flag_with_params
from core.pgid_cleanup_policy import (
    CleanupAction,
    CleanupKey,
    CleanupRecord,
    GroupProbeStatus,
    ProbeObservation,
    TransitionResult,
    request_cancel,
    step_probe,
)

_PROC_PIDTBSDINFO: Final[int] = 3
_PROC_BSDINFO_SIZE: Final[int] = 136
_LIBPROC_LOCK = threading.Lock()
_LIBPROC_HANDLE: object | None = None
_LIBPROC_LOADED = False


@dataclass(frozen=True)
class ProcessIdentity:
    """Live process identity returned O(1) without fork on macOS Darwin."""

    pid: int
    pgid: int
    uid: int
    start_time_us: int


class ProcProbePort(Protocol):
    """Injectable OS probe abstraction for deterministic L1/L2 testing."""

    def probe_live(self, pid: int) -> ProcessIdentity | None: ...
    def probe_group(self, pgid: int) -> GroupProbeStatus: ...
    def signal_group(self, pgid: int, sig: int) -> None: ...
    def now_s(self) -> float: ...


def _load_libproc() -> object | None:
    global _LIBPROC_HANDLE, _LIBPROC_LOADED
    if _LIBPROC_LOADED:
        return _LIBPROC_HANDLE
    with _LIBPROC_LOCK:
        if _LIBPROC_LOADED:
            return _LIBPROC_HANDLE
        if sys.platform == "darwin":
            try:
                _LIBPROC_HANDLE = ctypes.CDLL("/usr/lib/libproc.dylib")
            except OSError:
                _LIBPROC_HANDLE = None
        _LIBPROC_LOADED = True
        return _LIBPROC_HANDLE


def darwin_probe_live_pid(pid: int) -> ProcessIdentity | None:
    """O(1) Darwin libproc.proc_pidinfo(PROC_PIDTBSDINFO) probe (returns None for exited/zombie)."""
    if pid <= 1:
        return None
    lib = _load_libproc()
    if lib is None:
        return None
    buf = ctypes.create_string_buffer(_PROC_BSDINFO_SIZE)
    ret = lib.proc_pidinfo(pid, _PROC_PIDTBSDINFO, 0, buf, _PROC_BSDINFO_SIZE)  # type: ignore[attr-defined]
    if ret < _PROC_BSDINFO_SIZE:
        return None
    _, _, pbi_pid, _, pbi_uid = struct.unpack_from("<IIIII", buf.raw, 4)
    pbi_pgid = struct.unpack_from("<I", buf.raw, 100)[0]
    tvsec, tvusec = struct.unpack_from("<QQ", buf.raw, 120)
    return ProcessIdentity(
        pid=int(pbi_pid),
        pgid=int(pbi_pgid),
        uid=int(pbi_uid),
        start_time_us=int(tvsec) * 1_000_000 + int(tvusec),
    )


def _is_unsafe_pgid(pgid: int) -> bool:
    try:
        return pgid <= 1 or pgid == os.getpgrp()
    except OSError:
        return True


class PosixProcProbe:
    """Production Darwin/POSIX process-group probe (never calls waitpid(-pgid))."""

    def probe_live(self, pid: int) -> ProcessIdentity | None:
        return darwin_probe_live_pid(pid)

    def probe_group(self, pgid: int) -> GroupProbeStatus:
        if _is_unsafe_pgid(pgid):
            return GroupProbeStatus.GONE_ESRCH
        try:
            os.killpg(pgid, 0)
            return GroupProbeStatus.ALIVE
        except ProcessLookupError:
            return GroupProbeStatus.GONE_ESRCH
        except PermissionError:
            return GroupProbeStatus.EPERM
        except OSError as exc:
            return GroupProbeStatus.EPERM if exc.errno == errno.EPERM else GroupProbeStatus.GONE_ESRCH

    def signal_group(self, pgid: int, sig: int) -> None:
        if _is_unsafe_pgid(pgid):
            return
        try:
            os.killpg(pgid, sig)
        except OSError:
            pass

    def now_s(self) -> float:
        return time.monotonic()


class CachedDynamicFlagReader:
    """(path, mtime_ns, size, st_ino)-cached JSON > env > False reader for bridge services."""

    def __init__(self, json_path: Path | None = None, env_path_var: str = "BRIDGE_DYNAMIC_FLAGS_PATH") -> None:
        self._explicit = json_path
        self._env_var = env_path_var
        self._lock = threading.Lock()
        self._key: tuple[str, int, int, int] | None = None
        self._snap: dict[str, object] | None = None
        self._invalid = False

    def _target_path(self) -> Path | None:
        if self._explicit is not None:
            return self._explicit
        raw = os.environ.get(self._env_var, "").strip()
        return Path(raw).expanduser() if raw else None

    def _read_json(self) -> tuple[dict[str, object] | None, bool]:
        path = self._target_path()
        if path is None:
            return None, False
        try:
            st = path.stat()
        except OSError:
            with self._lock:
                self._key, self._snap, self._invalid = None, None, False
            return None, False
        key = (str(path), st.st_mtime_ns, st.st_size, st.st_ino)
        with self._lock:
            if self._key == key:
                return self._snap, self._invalid
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            snap = data if isinstance(data, dict) else None
            invalid = snap is None
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            snap, invalid = None, True
        with self._lock:
            self._key, self._snap, self._invalid = key, snap, invalid
        return snap, invalid

    def resolve(self, name: str, params: CleanupParamSnapshot | None = None) -> FlagResolution:
        snap, invalid = self._read_json()
        return resolve_flag_with_params(name, snap, os.environ, params, json_invalid=invalid)


ReapLeaderFn = Callable[[], int | None]


def _check_leader_reaped(
    key: CleanupKey,
    reap_leader: ReapLeaderFn | None,
    probe: ProcProbePort,
) -> tuple[bool, bool, bool]:
    """Popen-safe leader liveness & zombie reap without ever stealing Popen.returncode."""
    if reap_leader is not None:
        try:
            if reap_leader() is not None:
                return True, False, False
        except OSError:
            return True, True, False
    ident = probe.probe_live(key.leader_pid)
    if ident is not None:
        if key.leader_start_time_us > 0 and ident.start_time_us != key.leader_start_time_us:
            return False, False, True
        return False, False, False
    if reap_leader is None:
        return _reap_raw_unowned_leader(key.leader_pid)
    return False, True, False


def _reap_raw_unowned_leader(leader_pid: int) -> tuple[bool, bool, bool]:
    """Raw waitpid(leader_pid, WNOHANG) permitted ONLY when reap_leader is None."""
    try:
        wpid, _ = os.waitpid(leader_pid, os.WNOHANG)
        return (wpid == leader_pid), False, False
    except ChildProcessError:
        return False, True, False
    except OSError:
        return False, False, False


def build_probe_observation(
    rec: CleanupRecord,
    reap_leader: ReapLeaderFn | None,
    term_grace_s: float,
    probe: ProcProbePort | None = None,
) -> ProbeObservation:
    """3-step EPERM-safe observation: (1) Popen-safe reap_leader, (2) killpg(0), (3) start_time fence."""
    pr = probe or PosixProcProbe()
    reaped, leader_esrch, mismatch = _check_leader_reaped(rec.key, reap_leader, pr)
    group_status = pr.probe_group(rec.key.pgid)
    if group_status is GroupProbeStatus.EPERM and not reaped and reap_leader is not None:
        try:
            if reap_leader() is not None:
                reaped = True
                group_status = pr.probe_group(rec.key.pgid)
        except OSError:
            pass
    return ProbeObservation(
        attempt_epoch=rec.key.attempt_epoch,
        now_s=pr.now_s(),
        leader_reaped=reaped,
        leader_esrch=leader_esrch,
        start_time_mismatch=mismatch,
        group_status=group_status,
        term_grace_s=term_grace_s,
    )


def execute_cleanup_step(
    rec: CleanupRecord,
    reap_leader: ReapLeaderFn | None,
    term_grace_s: float,
    probe: ProcProbePort | None = None,
) -> TransitionResult:
    """Execute one cancel/probe step against the OS using pure FSM policy."""
    pr = probe or PosixProcProbe()
    if rec.state.value == "live":
        res = request_cancel(rec, rec.key.attempt_epoch, pr.now_s())
        if res.action is CleanupAction.SEND_TERM:
            pr.signal_group(rec.key.pgid, signal.SIGTERM)
        return res
    obs = build_probe_observation(rec, reap_leader, term_grace_s, pr)
    res = step_probe(rec, obs)
    if res.action is CleanupAction.SEND_KILL:
        pr.signal_group(rec.key.pgid, signal.SIGKILL)
    return res
