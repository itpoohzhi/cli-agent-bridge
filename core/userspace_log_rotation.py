"""POSIX dir_fd/openat rotating log writer (100% Python 3.9.6+ compatible, stdlib only).

Single-writer-process invariant: thread-safe via per-writer Lock (L1); future multi-process
evolution can extend via fcntl.flock(dir_fd). Zero time.sleep and zero wall-clock clamps.
"""
from __future__ import annotations

import errno
import os
import select
import stat
import sys
import threading
from typing import Dict, Optional, Tuple

from core.log_rotation_policy import (
    RotationConfig, WriterState, format_transition_notice,
    plan_rollover_ops, should_reopen, should_rollover, validate_stat,
)

_OPEN_DIR_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
_OPEN_FILE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0)
_OPEN_SLOT_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0)


class _ArchiveUnsafeError(OSError):
    """Raised when an archive slot .1..N fails security/mode validation."""


def supports_secure_dir_fd() -> bool:
    """Verify platform supports the exact dir_fd callables used at runtime (Py 3.9.6+ safe)."""
    required_fns = (os.open, os.stat, os.rename, os.unlink, os.mkdir)
    required_flags = ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK", "O_CLOEXEC")
    return all(fn in os.supports_dir_fd for fn in required_fns) and all(hasattr(os, fl) for fl in required_flags)


def safe_stderr_write(msg: str) -> bool:
    """Emit <=200 B one-shot warning to dynamic sys.stderr without blocking or recursing."""
    stream = sys.stderr
    if stream is None:
        return False
    payload = msg[:200]
    try:
        fd = stream.fileno()
    except Exception:
        fd = None
    if isinstance(fd, int) and fd >= 0:
        try:
            _, writable, _ = select.select([], [fd], [], 0.0)
            if not writable:
                return False
        except Exception:
            pass
    try:
        stream.write(payload)
        stream.flush()
        return True
    except Exception:
        return False


def _step_dir_component(cur_fd: int, part: str, dir_mode: int) -> int:
    try:
        return os.open(part, _OPEN_DIR_FLAGS, dir_fd=cur_fd)
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            try:
                os.mkdir(part, dir_mode, dir_fd=cur_fd)
            except FileExistsError:
                pass
            return os.open(part, _OPEN_DIR_FLAGS, dir_fd=cur_fd)
        if exc.errno in (errno.ELOOP, errno.ENOTDIR):
            st = os.stat(part, dir_fd=cur_fd, follow_symlinks=False)
            if stat.S_ISLNK(st.st_mode) and st.st_uid == 0:
                return os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC, dir_fd=cur_fd)
            raise OSError(errno.ELOOP, f"user symlink rejected at {part}")
        raise


def open_dir_chain_no_toctou(dir_path: str, dir_mode: int = 0o700) -> int:
    """Component-by-component openat/dir_fd walk eliminating user-symlink TOCTOU."""
    abs_path = os.path.abspath(os.path.expanduser(dir_path))
    parts = [p for p in abs_path.split(os.sep) if p]
    cur_fd = os.open(os.sep, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in parts:
            nxt_fd = _step_dir_component(cur_fd, part, dir_mode)
            os.close(cur_fd)
            cur_fd = nxt_fd
        st = os.fstat(cur_fd)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid():
            raise OSError(errno.EPERM, "log directory not owned regular directory")
        if stat.S_IMODE(st.st_mode) != dir_mode:
            os.fchmod(cur_fd, dir_mode)
        return cur_fd
    except Exception:
        os.close(cur_fd)
        raise


def _open_active_file(dir_fd: int, base_name: str, file_mode: int) -> Tuple[int, os.stat_result, bool]:
    fd = os.open(base_name, _OPEN_FILE_FLAGS, file_mode, dir_fd=dir_fd)
    try:
        st = os.fstat(fd)
        reason = validate_stat(stat.S_ISREG(st.st_mode), st.st_uid, st.st_nlink, os.geteuid())
        if reason is not None:
            raise OSError(errno.ELOOP, f"unsafe active log file: {reason}")
        needs_adopt = bool(st.st_mode & 0o077)
        if needs_adopt or stat.S_IMODE(st.st_mode) != file_mode:
            os.fchmod(fd, file_mode)
        return fd, st, needs_adopt
    except Exception:
        os.close(fd)
        raise


def _validate_and_harden_slots(dir_fd: int, base_name: str, backup_count: int, file_mode: int) -> None:
    """Phase 1 of two-phase rollover: validate & fchmod 0600 ALL .1..N slots before any rename."""
    euid = os.geteuid()
    for idx in range(1, backup_count + 1):
        slot = f"{base_name}.{idx}"
        try:
            sfd = os.open(slot, _OPEN_SLOT_FLAGS, dir_fd=dir_fd)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise _ArchiveUnsafeError(exc.errno or errno.ELOOP, f"unsafe archive slot {slot}") from exc
        try:
            st = os.fstat(sfd)
            reason = validate_stat(stat.S_ISREG(st.st_mode), st.st_uid, st.st_nlink, euid)
            if reason is not None:
                raise _ArchiveUnsafeError(errno.ELOOP, f"unsafe archive slot {slot}: {reason}")
            if st.st_mode & 0o077:
                os.fchmod(sfd, file_mode)
        except _ArchiveUnsafeError:
            raise
        except OSError as exc:
            raise _ArchiveUnsafeError(exc.errno or errno.EACCES, f"archive fchmod failed {slot}") from exc
        finally:
            os.close(sfd)


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError(errno.EIO, "short log write")
        view = view[written:]


class PrivateWatchedRotatingWriter:
    """Thread-safe POSIX dir_fd rotating writer with close-before-open and commit-before-recover."""

    def __init__(self, service_id: str) -> None:
        self._service_id, self._lock = service_id, threading.Lock()
        self._state, self._degraded_reason, self._bound_path = WriterState.CLOSED, "", ""
        self._dir_fd = self._file_fd = -1
        self._open_id: Optional[Tuple[int, int]] = None
        self._pending_adopt_id: Optional[Tuple[int, int]] = None
        self._stats: Dict[str, object] = {
            "writes": 0, "rotations": 0, "reopens": 0, "dropped_lines": 0,
            "degraded_count": 0, "warn_skipped": 0, "last_errno": 0,
        }

    def is_active(self) -> bool:
        return self._state != WriterState.CLOSED

    def snapshot(self) -> Dict[str, object]:
        with self._lock:
            return {"service": self._service_id, "state": self._state.value, "degraded_reason": self._degraded_reason, **self._stats}

    def _close_file_locked(self) -> None:
        if self._file_fd >= 0:
            os.close(self._file_fd)
            self._file_fd = -1
        self._open_id = None

    def _close_all_locked(self) -> None:
        self._close_file_locked()
        if self._dir_fd >= 0:
            os.close(self._dir_fd)
            self._dir_fd = -1
        self._bound_path = ""

    def _emit_notice(self, prev_state: WriterState, next_state: WriterState, reason: str) -> None:
        msg = format_transition_notice(prev_state, next_state, self._service_id, reason)
        if msg and not safe_stderr_write(msg):
            self._stats["warn_skipped"] = int(self._stats["warn_skipped"]) + 1

    def _enter_degraded_locked(self, reason: str, err_no: int) -> None:
        prev = self._state
        self._close_all_locked()
        self._state, self._degraded_reason = WriterState.DEGRADED_FAIL_OPEN, reason
        self._stats["dropped_lines"], self._stats["last_errno"] = int(self._stats["dropped_lines"]) + 1, err_no
        if prev != WriterState.DEGRADED_FAIL_OPEN:
            self._stats["degraded_count"] = int(self._stats["degraded_count"]) + 1
            self._emit_notice(prev, self._state, reason)

    def _open_path_locked(self, cfg: RotationConfig, abs_log: str, base_name: str) -> bool:
        self._close_all_locked()
        self._dir_fd, self._bound_path = open_dir_chain_no_toctou(os.path.dirname(abs_log), cfg.dir_mode), abs_log
        fd, st, needs_adopt = _open_active_file(self._dir_fd, base_name, cfg.file_mode)
        self._file_fd, self._open_id = fd, (st.st_dev, st.st_ino)
        self._pending_adopt_id = self._open_id if needs_adopt else (self._pending_adopt_id if self._pending_adopt_id == self._open_id else None)
        self._stats["reopens"] = int(self._stats["reopens"]) + 1
        return needs_adopt

    def _do_rollover_locked(self, cfg: RotationConfig, base_name: str) -> None:
        self._close_file_locked()
        _validate_and_harden_slots(self._dir_fd, base_name, cfg.backup_count, cfg.file_mode)
        if cfg.backup_count == 0:
            try:
                os.unlink(base_name, dir_fd=self._dir_fd)
            except FileNotFoundError:
                pass
        else:
            for src, dst in plan_rollover_ops(base_name, cfg.backup_count):
                try:
                    os.rename(src, dst, src_dir_fd=self._dir_fd, dst_dir_fd=self._dir_fd)
                except FileNotFoundError:
                    continue
        fd, st, _ = _open_active_file(self._dir_fd, base_name, cfg.file_mode)
        self._file_fd, self._open_id, self._pending_adopt_id = fd, (st.st_dev, st.st_ino), None
        self._stats["rotations"] = int(self._stats["rotations"]) + 1

    def _ensure_current_locked(self, cfg: RotationConfig, abs_log: str, base_name: str) -> bool:
        if self._dir_fd < 0 or self._bound_path != abs_log:
            return self._open_path_locked(cfg, abs_log, base_name)
        try:
            pst = os.stat(base_name, dir_fd=self._dir_fd, follow_symlinks=False)
            path_id: Optional[Tuple[int, int]] = (pst.st_dev, pst.st_ino)
            path_reg = stat.S_ISREG(pst.st_mode)
        except FileNotFoundError:
            path_id, path_reg = None, False
        if not should_reopen(self._open_id, path_id, path_reg):
            return False
        self._close_file_locked()
        fd, st, needs_adopt = _open_active_file(self._dir_fd, base_name, cfg.file_mode)
        self._file_fd, self._open_id = fd, (st.st_dev, st.st_ino)
        self._pending_adopt_id = self._open_id if needs_adopt else (self._pending_adopt_id if self._pending_adopt_id == self._open_id else None)
        self._stats["reopens"] = int(self._stats["reopens"]) + 1
        return needs_adopt

    def _commit_payload_locked(self, cfg: RotationConfig, abs_log: str, payload: bytes, was_degraded: bool) -> None:
        base_name = os.path.basename(abs_log)
        if not base_name:
            raise OSError(errno.EINVAL, "empty log basename")
        if not supports_secure_dir_fd():
            raise OSError(errno.ENOTSUP, "dir_fd unsupported")
        needs_adopt = self._ensure_current_locked(cfg, abs_log, base_name)
        if was_degraded and self._degraded_reason == "ARCHIVE_UNSAFE":
            self._close_file_locked()
            _validate_and_harden_slots(self._dir_fd, base_name, cfg.backup_count, cfg.file_mode)
            needs_adopt = self._ensure_current_locked(cfg, abs_log, base_name) or needs_adopt
        must_roll = needs_adopt or (self._pending_adopt_id == self._open_id and self._open_id is not None)
        if must_roll or should_rollover(os.fstat(self._file_fd).st_size, len(payload), cfg.max_bytes):
            self._do_rollover_locked(cfg, base_name)
        _write_all(self._file_fd, payload)

    def write_bytes(self, cfg: RotationConfig, payload: bytes) -> bool:
        """Write UTF-8 bytes with inode-watch, two-phase rollover, and commit-before-recover."""
        with self._lock:
            was_degraded = self._state == WriterState.DEGRADED_FAIL_OPEN
            try:
                abs_log = os.path.abspath(os.path.expanduser(cfg.log_path))
                self._commit_payload_locked(cfg, abs_log, payload, was_degraded)
                self._state, self._degraded_reason = WriterState.OPEN, ""
                self._stats["writes"] = int(self._stats["writes"]) + 1
                if was_degraded:
                    self._emit_notice(WriterState.DEGRADED_FAIL_OPEN, WriterState.OPEN, f"dropped={self._stats['dropped_lines']}")
                return True
            except _ArchiveUnsafeError as exc:
                self._enter_degraded_locked("ARCHIVE_UNSAFE", exc.errno or errno.ELOOP)
                return False
            except (OSError, ValueError) as exc:
                err_no = getattr(exc, "errno", None) or errno.EINVAL
                reason = "UNSAFE_TARGET" if err_no in (errno.ELOOP, errno.ENXIO, errno.EPERM, errno.EINVAL) else "IO_ERROR"
                self._enter_degraded_locked(reason, err_no)
                return False

    def note_external_degrade(self, reason: str) -> None:
        """Fail-closed degrade on external pre-lock failure (e.g. redact_fn exception)."""
        with self._lock:
            self._enter_degraded_locked(reason, 0)

    def close(self) -> None:
        with self._lock:
            self._close_all_locked()
            self._state, self._degraded_reason, self._pending_adopt_id = WriterState.CLOSED, "", None

    def reset_after_fork(self) -> None:
        """Discard inherited parent FDs in child process without flushing parent state."""
        self._lock = threading.Lock()
        self._file_fd = self._dir_fd = -1
        self._open_id = self._pending_adopt_id = None
        self._bound_path, self._state, self._degraded_reason = "", WriterState.CLOSED, ""
