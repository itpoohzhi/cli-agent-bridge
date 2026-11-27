"""Bounded process admission (Semaphore + queue + fast 429) and shielded PGID teardown for agy-bridge."""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass

from core.lossless_contracts import (
    DEFAULT_KILL_GRACE_S,
    DEFAULT_MAX_CONCURRENCY,
    DEFAULT_MAX_QUEUE,
    DEFAULT_QUEUE_WAIT_S,
    LosslessLimits,
)


class AdmissionOverloadError(RuntimeError):
    """Raised fail-closed (HTTP 429) when concurrency + queue capacity or wait budget is exceeded."""

    def __init__(self, reason: str, *, retry_after_s: float = 2.0) -> None:
        super().__init__(reason)
        self.http_status = 429
        self.reason = reason
        self.retry_after_s = max(1, int(retry_after_s))


@dataclass(frozen=True)
class AdmissionSnapshot:
    """Observable counters for admission diagnostics and tests."""

    active: int
    queued: int
    max_concurrency: int
    max_queue: int
    active_pgids: tuple[int, ...]


class ProcessAdmissionGuard:
    """Caps concurrent agy.real spawns, bounds wait queue, and enforces orphan-free PGID teardown."""

    def __init__(
        self,
        *,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        max_queue: int = DEFAULT_MAX_QUEUE,
        queue_wait_s: float = DEFAULT_QUEUE_WAIT_S,
        kill_grace_s: float = DEFAULT_KILL_GRACE_S,
    ) -> None:
        self._max_concurrency = max(1, max_concurrency)
        self._max_queue = max(0, max_queue)
        self._queue_wait_s = max(0.05, queue_wait_s)
        self._kill_grace_s = max(0.05, kill_grace_s)
        self._cond = threading.Condition()
        self._active = 0
        self._queued = 0
        self._pgids: set[int] = set()

    @classmethod
    def from_limits(cls, limits: LosslessLimits) -> ProcessAdmissionGuard:
        """Build guard directly from SSOT LosslessLimits."""
        return cls(
            max_concurrency=limits.max_concurrency,
            max_queue=limits.max_queue,
            queue_wait_s=limits.queue_wait_s,
            kill_grace_s=limits.kill_grace_s,
        )

    def snapshot(self) -> AdmissionSnapshot:
        """Return thread-safe admission and PGID registry counts."""
        with self._cond:
            return AdmissionSnapshot(
                active=self._active,
                queued=self._queued,
                max_concurrency=self._max_concurrency,
                max_queue=self._max_queue,
                active_pgids=tuple(sorted(self._pgids)),
            )

    def acquire(self, *, wait_s: float | None = None) -> None:
        """Acquire an execution slot or raise AdmissionOverloadError (HTTP 429) without spawning."""
        budget = self._queue_wait_s if wait_s is None else max(0.0, wait_s)
        with self._cond:
            if self._active < self._max_concurrency:
                self._active += 1
                return
            if self._queued >= self._max_queue:
                raise AdmissionOverloadError(
                    f"admission_queue_full (active={self._active}, queued={self._queued})",
                    retry_after_s=max(1.0, min(5.0, budget)),
                )
            self._queued += 1
            deadline = time.monotonic() + budget
            try:
                while self._active >= self._max_concurrency:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise AdmissionOverloadError(
                            f"admission_queue_timeout (wait_s={budget:.2f})",
                            retry_after_s=2.0,
                        )
                    self._cond.wait(timeout=remaining)
                self._active += 1
            finally:
                self._queued -= 1

    def release(self) -> None:
        """Release an acquired execution slot and wake one queued waiter."""
        with self._cond:
            if self._active > 0:
                self._active -= 1
            self._cond.notify(1)

    @contextmanager
    def slot(self, *, wait_s: float | None = None) -> Iterator[None]:
        """Context manager guaranteeing slot release even on cancellation or exception."""
        self.acquire(wait_s=wait_s)
        try:
            yield
        finally:
            self.release()

    def register_pgid(self, pgid: int) -> None:
        with self._cond:
            self._pgids.add(pgid)

    def unregister_pgid(self, pgid: int) -> None:
        with self._cond:
            self._pgids.discard(pgid)

    def spawn_isolated(
        self,
        cmd: Sequence[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> subprocess.Popen[bytes]:
        """Spawn child in its own POSIX process group (start_new_session=True) and register PGID."""
        proc = subprocess.Popen(
            list(cmd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=dict(env) if env is not None else None,
            start_new_session=True,
        )
        try:
            pgid = os.getpgid(proc.pid)
        except ProcessLookupError:
            pgid = proc.pid
        self.register_pgid(pgid)
        return proc

    def teardown_process(
        self,
        proc: subprocess.Popen[bytes],
        *,
        grace_s: float | None = None,
    ) -> bool:
        """Escalating PGID teardown (SIGTERM -> grace -> SIGKILL + wait) closing all stdio pipes."""
        wait_grace = self._kill_grace_s if grace_s is None else max(0.05, grace_s)
        pgid = proc.pid
        try:
            pgid = os.getpgid(proc.pid)
        except ProcessLookupError:
            pgid = proc.pid
        try:
            _signal_group(pgid, signal.SIGTERM)
            if not _wait_proc(proc, wait_grace):
                _signal_group(pgid, signal.SIGKILL)
                _wait_proc(proc, max(0.5, wait_grace))
            _signal_group(pgid, signal.SIGKILL)
        finally:
            _close_pipes(proc)
            self.unregister_pgid(pgid)
        return not is_pgid_alive(pgid)


def _signal_group(pgid: int, sig: int) -> None:
    try:
        os.killpg(pgid, sig)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def _wait_proc(proc: subprocess.Popen[bytes], timeout_s: float) -> bool:
    try:
        proc.wait(timeout=timeout_s)
        return True
    except subprocess.TimeoutExpired:
        return False


def _close_pipes(proc: subprocess.Popen[bytes]) -> None:
    for stream in (proc.stdin, proc.stdout, proc.stderr):
        if stream is not None:
            try:
                stream.close()
            except OSError:
                pass


def is_pgid_alive(pgid: int) -> bool:
    """Return True iff any process remains alive in the given POSIX process group."""
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
