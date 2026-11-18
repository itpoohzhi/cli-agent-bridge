"""Process lifecycle and stream I/O for resident stdio slots."""

from __future__ import annotations

import collections
import os
import queue
import subprocess
import threading
import time
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from typing import BinaryIO

from .process_reaper import (
    get_pgid_rss_bytes, get_process_start_time, terminate_process_group,
)

_STDERR_RING_MAX_BYTES = 65536


class StdioIoError(Exception):
    """Base error raised by resident-process I/O operations."""


class StdioWriteError(StdioIoError):
    """Raised when data cannot be written to process stdin."""


class StdioProcessTerminated(StdioIoError):
    """Raised when a process cannot complete termination."""


@dataclass(frozen=True)
class TaggedLine:
    """One process output line bound to a process generation."""

    line: str
    generation: int
    pid: int
    is_stderr: bool = False
    timestamp_mono: float = field(default_factory=time.monotonic)


class ResidentProcessHandle:
    """Own a resident subprocess and its generation-aware output readers."""

    def __init__(self, proc: subprocess.Popen[bytes], max_output_bytes: int = 4194304) -> None:
        self.proc: subprocess.Popen[bytes] = proc
        self.pid: int = proc.pid
        self.generation: int = 0
        self.created_at_mono: float = time.monotonic()
        self.last_activity_mono: float = self.created_at_mono
        self._pgid: int = proc.pid
        self._start_time: str = get_process_start_time(proc.pid)
        self._pgid_dead: bool = False
        self._max_output_bytes: int = max_output_bytes
        self._stderr_ring: collections.deque[bytes] = collections.deque()
        self._stderr_ring_bytes: int = 0
        self._reader_threads: list[threading.Thread] = []
        self._queue: queue.Queue[TaggedLine | BaseException | None] = queue.Queue()
        self._closed: bool = False
        self._state_lock: threading.Lock = threading.Lock()
        self._eof_readers: int = 0
        self._reader_error: BaseException | None = None

    @property
    def _proc(self) -> subprocess.Popen[bytes]:
        return self.proc

    @classmethod
    def spawn(
        cls, argv: list[str], cwd: str,
        env: Mapping[str, str] | None = None, max_output_bytes: int = 4194304,
    ) -> ResidentProcessHandle:
        """Start a subprocess and daemon readers for both output streams."""
        proc = subprocess.Popen(
            argv, cwd=cwd, env=dict(env) if env is not None else None,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            bufsize=0, start_new_session=True,
        )
        stdout, stderr = proc.stdout, proc.stderr
        if stdout is None or stderr is None:
            with suppress(OSError):
                proc.kill()
            raise StdioIoError("process output pipes were not created")
        handle = cls(proc, max_output_bytes=max_output_bytes)
        for stream, is_stderr in ((stdout, False), (stderr, True)):
            thread = threading.Thread(
                target=handle._read_stream, args=(stream, is_stderr),
                daemon=True, name=f"stdio-reader-{proc.pid}-{'err' if is_stderr else 'out'}",
            )
            handle._reader_threads.append(thread)
            thread.start()
        return handle

    def advance_generation(self) -> int:
        """Advance the active generation and return its new value."""
        with self._state_lock:
            self.generation += 1
            return self.generation

    def write(self, data: bytes) -> None:
        """Write and flush data, normalizing pipe failures."""
        stdin = self.proc.stdin
        if stdin is None:
            raise StdioWriteError("process stdin is unavailable")
        try:
            _ = stdin.write(data)
            stdin.flush()
        except (BrokenPipeError, OSError, ValueError) as exc:
            raise StdioWriteError("failed to write to process stdin") from exc

    def read_line(self, timeout_s: float | None = None) -> TaggedLine | None:
        """Return the next active-generation line, dropping late output."""
        if self._closed:
            return None
        deadline = None if timeout_s is None else time.monotonic() + max(0.0, timeout_s)
        while True:
            timeout = None if deadline is None else max(0.0, deadline - time.monotonic())
            try:
                item = self._queue.get(timeout=timeout)
            except queue.Empty:
                return None
            if item is None:
                with self._state_lock:
                    if self._reader_error is not None:
                        raise self._reader_error
                return None
            if isinstance(item, BaseException):
                raise item
            with self._state_lock:
                active_generation = self.generation
            if item.generation == active_generation:
                return item

    def is_alive(self) -> bool:
        """Return whether the subprocess is still running."""
        return self.proc.poll() is None

    def stderr_tail(self) -> str:
        """Return buffered stderr tail (up to 64 KiB) decoded as UTF-8."""
        with self._state_lock:
            data = b"".join(self._stderr_ring)
        return data.decode("utf-8", errors="replace")

    def get_rss_bytes(self) -> int | None:
        """Return total RSS in bytes for the process group, or None."""
        return get_pgid_rss_bytes(self._pgid)

    def terminate_gracefully(self, grace_s: float, timeout_s: float = 2.0) -> int:
        """Terminate process group, reap leader, and release all pipes."""
        try:
            self._pgid_dead = terminate_process_group(
                self._proc, self._pgid, self._start_time,
                cancel_grace_s=grace_s, already_dead=self._pgid_dead,
            )
            if self.proc.returncode is None:
                try:
                    _ = self.proc.wait(timeout=max(0.0, timeout_s))
                except subprocess.TimeoutExpired as exc:
                    raise StdioProcessTerminated(
                        "process did not exit after forced termination"
                    ) from exc
        finally:
            self._closed = True
            self._queue.put(None)
            for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
                if stream is not None:
                    with suppress(OSError, ValueError):
                        stream.close()
            for thread in self._reader_threads:
                thread.join(timeout=max(0.0, timeout_s))
        if self.proc.returncode is None:
            raise StdioProcessTerminated("process termination has no return code")
        return self.proc.returncode

    def _record_stderr(self, data: bytes) -> None:
        if not data:
            return
        if len(data) > _STDERR_RING_MAX_BYTES:
            data = data[-_STDERR_RING_MAX_BYTES:]
        with self._state_lock:
            self._stderr_ring.append(data)
            self._stderr_ring_bytes += len(data)
            while self._stderr_ring_bytes > _STDERR_RING_MAX_BYTES and self._stderr_ring:
                self._stderr_ring_bytes -= len(self._stderr_ring.popleft())

    def _emit_line(self, raw_line: bytes, is_stderr: bool, generation: int) -> None:
        tagged = TaggedLine(
            line=raw_line.decode("utf-8", errors="replace").rstrip("\r\n"),
            generation=generation, pid=self.pid, is_stderr=is_stderr,
        )
        if not is_stderr:
            with self._state_lock:
                self.last_activity_mono = tagged.timestamp_mono
        self._queue.put(tagged)

    def _drain_buffer(self, buf: bytearray, is_stderr: bool, generation: int) -> None:
        while True:
            nl = buf.find(b"\n")
            if nl < 0:
                if not is_stderr and len(buf) > self._max_output_bytes:
                    raise RuntimeError("output_limit_exceeded")
                if is_stderr and len(buf) > _STDERR_RING_MAX_BYTES:
                    overflow = len(buf) - _STDERR_RING_MAX_BYTES
                    self._record_stderr(bytes(buf[:overflow]))
                    del buf[:overflow]
                return
            if not is_stderr and nl > self._max_output_bytes:
                raise RuntimeError("output_limit_exceeded")
            if is_stderr:
                self._record_stderr(bytes(buf[: nl + 1]))
            raw_line = bytes(buf[:nl])
            del buf[: nl + 1]
            self._emit_line(raw_line, is_stderr, generation)

    def _read_stream(self, stream: BinaryIO, is_stderr: bool) -> None:
        buf = bytearray()
        fd: int | None = None
        with suppress(AttributeError, OSError, ValueError):
            fd = stream.fileno()
        try:
            while True:
                try:
                    chunk = os.read(fd, 8192) if fd is not None else stream.read(8192)
                except (OSError, ValueError):
                    break
                if not chunk:
                    break
                buf.extend(chunk)
                with self._state_lock:
                    generation = self.generation
                self._drain_buffer(buf, is_stderr, generation)
            if buf:
                if is_stderr:
                    self._record_stderr(bytes(buf))
                with self._state_lock:
                    generation = self.generation
                self._emit_line(bytes(buf), is_stderr, generation)
        except RuntimeError as exc:
            if str(exc) == "output_limit_exceeded":
                with self._state_lock:
                    self._reader_error = exc
                self._queue.put(exc)
            raise
        finally:
            with self._state_lock:
                self._eof_readers += 1
                if self._eof_readers == 2:
                    self._queue.put(None)
