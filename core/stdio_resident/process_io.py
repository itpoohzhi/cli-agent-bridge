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
from typing import BinaryIO, Final

from .process_reaper import (
    get_pgid_rss_bytes,
    get_process_start_time,
    terminate_process_group,
)

DEFAULT_FRAME_MAX_BYTES: Final[int] = 4_194_304
DEFAULT_STDOUT_QUEUE_BYTES: Final[int] = 4_194_304
DEFAULT_STDERR_RING_BYTES: Final[int] = 65_536
_STDERR_RING_MAX_BYTES: Final[int] = DEFAULT_STDERR_RING_BYTES
_READ_CHUNK_BYTES: Final[int] = 8192
_LIMIT_SPECS: Final[tuple[tuple[str, tuple[str, ...], int], ...]] = (
    (
        "frame_max_bytes",
        ("BRIDGE_STDIO_FRAME_MAX_BYTES", "BRIDGE_STDIO_MAX_TURN_OUTPUT_BYTES"),
        DEFAULT_FRAME_MAX_BYTES,
    ),
    ("stdout_queue_bytes", ("BRIDGE_STDIO_STDOUT_QUEUE_BYTES",), DEFAULT_STDOUT_QUEUE_BYTES),
    ("stderr_ring_bytes", ("BRIDGE_STDIO_STDERR_RING_BYTES",), DEFAULT_STDERR_RING_BYTES),
)
_LIMIT_KEYS: Final[frozenset[str]] = frozenset(spec[0] for spec in _LIMIT_SPECS)
_OVERFLOW_ERRORS: Final[frozenset[str]] = frozenset(
    {"output_limit_exceeded", "stdout_queue_limit_exceeded"}
)
LINE, TIMEOUT, EOF = "line", "timeout", "eof"


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


LineOutcome = tuple[str, TaggedLine | None]


def _env_positive_int(keys: tuple[str, ...], default: int) -> int:
    for key in keys:
        raw = os.environ.get(key)
        if not raw or not raw.strip():
            continue
        try:
            value = int(raw.strip())
        except ValueError:
            continue
        if value > 0:
            return value
    return default


def _resolve_bounds(
    max_output_bytes: int | None, limits: Mapping[str, int]
) -> tuple[int, int, int]:
    extra = set(limits) - _LIMIT_KEYS
    if extra:
        raise TypeError(f"unexpected limit keyword(s): {sorted(extra)}")
    resolved: list[int] = []
    for name, env_keys, default in _LIMIT_SPECS:
        raw = limits.get(name)
        if raw is None and name == "frame_max_bytes":
            raw = max_output_bytes
        val = _env_positive_int(env_keys, default) if raw is None else raw
        if isinstance(val, bool) or val <= 0:
            raise ValueError(f"{name} must be > 0")
        resolved.append(val)
    return resolved[0], resolved[1], resolved[2]


class ResidentProcessHandle:
    """Own a resident subprocess and its generation-aware output readers."""

    def __init__(
        self, proc: subprocess.Popen[bytes], max_output_bytes: int | None = None, **limits: int
    ) -> None:
        frame_max, queue_max, stderr_max = _resolve_bounds(max_output_bytes, limits)
        self.proc: subprocess.Popen[bytes] = proc
        self.pid: int = proc.pid
        self.generation: int = 0
        self.created_at_mono: float = time.monotonic()
        self.last_activity_mono: float = self.created_at_mono
        self._pgid: int = proc.pid
        self._start_time: str = get_process_start_time(proc.pid)
        self._pgid_dead: bool = False
        self._frame_max_bytes: int = frame_max
        self._max_output_bytes: int = frame_max
        self._stdout_queue_max_bytes: int = queue_max
        self._stdout_queue_bytes: int = 0
        self._stderr_ring_max_bytes: int = stderr_max
        self._stderr_ring: collections.deque[bytes] = collections.deque()
        self._stderr_ring_bytes: int = 0
        self._reader_threads: list[threading.Thread] = []
        self._queue: queue.Queue[TaggedLine | BaseException | None] = queue.Queue()
        self._closed: bool = False
        self._state_lock: threading.Lock = threading.Lock()
        self._reader_error: BaseException | None = None

    @property
    def _proc(self) -> subprocess.Popen[bytes]:
        return self.proc

    @property
    def frame_max_bytes(self) -> int:
        return self._frame_max_bytes

    @property
    def stdout_queue_max_bytes(self) -> int:
        return self._stdout_queue_max_bytes

    @property
    def stderr_ring_max_bytes(self) -> int:
        return self._stderr_ring_max_bytes

    @classmethod
    def spawn(
        cls,
        argv: list[str],
        cwd: str,
        env: Mapping[str, str] | None = None,
        max_output_bytes: int | None = None,
        **limits: int,
    ) -> ResidentProcessHandle:
        """Start a subprocess and daemon readers for stdout queue and stderr ring."""
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
        handle = cls(proc, max_output_bytes=max_output_bytes, **limits)
        for target, stream, suffix in (
            (handle._read_stdout, stdout, "out"),
            (handle._read_stderr, stderr, "err"),
        ):
            thread = threading.Thread(
                target=target, args=(stream,), daemon=True,
                name=f"stdio-reader-{proc.pid}-{suffix}",
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
        """Return the next active-generation line; None on timeout or EOF (legacy)."""
        kind, tagged = self.read_line_outcome(timeout_s)
        return tagged if kind == LINE else None

    def read_line_outcome(self, timeout_s: float | None = None) -> LineOutcome:
        """Strictly separate ``("line", t)`` / ``("timeout", None)`` / ``("eof", None)``."""
        return self._read_outcome(timeout_s, stdout_only=False)

    def read_stdout_line(self, timeout_s: float | None = None) -> TaggedLine | None:
        """Return the next active-generation stdout line, ignoring stderr frames."""
        kind, tagged = self.read_stdout_line_outcome(timeout_s)
        return tagged if kind == LINE else None

    def read_stdout_line_outcome(self, timeout_s: float | None = None) -> LineOutcome:
        """Read next active-generation stdout line outcome, skipping any stderr lines."""
        return self._read_outcome(timeout_s, stdout_only=True)

    def _raise_if_reader_error(self) -> None:
        with self._state_lock:
            err = self._reader_error
        if err is not None:
            raise err

    def _accept_line(self, item: TaggedLine, *, stdout_only: bool) -> TaggedLine | None:
        line_bytes = 0 if item.is_stderr else len(item.line.encode("utf-8"))
        with self._state_lock:
            self._stdout_queue_bytes = max(0, self._stdout_queue_bytes - line_bytes)
            active_generation = self.generation
            err = self._reader_error
        if err is not None:
            raise err
        if (stdout_only and item.is_stderr) or item.generation != active_generation:
            return None
        return item

    def _read_outcome(self, timeout_s: float | None, *, stdout_only: bool) -> LineOutcome:
        if self._closed:
            return (EOF, None)
        self._raise_if_reader_error()
        deadline = None if timeout_s is None else time.monotonic() + max(0.0, timeout_s)
        while True:
            timeout = None if deadline is None else max(0.0, deadline - time.monotonic())
            try:
                item = self._queue.get(timeout=timeout)
            except queue.Empty:
                self._raise_if_reader_error()
                return (TIMEOUT, None)
            if item is None:
                self._raise_if_reader_error()
                return (EOF, None)
            if isinstance(item, BaseException):
                raise item
            accepted = self._accept_line(item, stdout_only=stdout_only)
            if accepted is not None:
                return (LINE, accepted)

    def is_alive(self) -> bool:
        """Return whether the subprocess is still running."""
        return self.proc.poll() is None

    def stderr_tail(self) -> str:
        """Return buffered stderr tail (bounded by stderr_ring_max_bytes) as UTF-8."""
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
                    raise StdioProcessTerminated("process did not exit after forced termination") from exc
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
        limit = self._stderr_ring_max_bytes
        if len(data) > limit:
            data = data[-limit:]
        with self._state_lock:
            self._stderr_ring.append(data)
            self._stderr_ring_bytes += len(data)
            while self._stderr_ring_bytes > limit and self._stderr_ring:
                self._stderr_ring_bytes -= len(self._stderr_ring.popleft())

    def _emit_stdout_line(self, raw_line: bytes, generation: int) -> None:
        text = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
        line_bytes = len(text.encode("utf-8"))
        tagged = TaggedLine(line=text, generation=generation, pid=self.pid, is_stderr=False)
        with self._state_lock:
            if self._stdout_queue_bytes + line_bytes > self._stdout_queue_max_bytes:
                raise RuntimeError("stdout_queue_limit_exceeded")
            self._stdout_queue_bytes += line_bytes
            self.last_activity_mono = tagged.timestamp_mono
        self._queue.put(tagged)

    def _consume_stdout_chunk(self, buf: bytearray, chunk: bytes, generation: int) -> None:
        start, limit = 0, self._frame_max_bytes
        while start < len(chunk):
            nl = chunk.find(b"\n", start)
            if nl < 0:
                if len(buf) + (len(chunk) - start) > limit:
                    buf.clear()
                    raise RuntimeError("output_limit_exceeded")
                buf.extend(chunk[start:])
                return
            if len(buf) + (nl - start) > limit:
                buf.clear()
                raise RuntimeError("output_limit_exceeded")
            raw_line = bytes(buf) + chunk[start:nl] if buf else chunk[start:nl]
            buf.clear()
            self._emit_stdout_line(raw_line, generation)
            start = nl + 1

    def _handle_overflow(self, exc: RuntimeError) -> None:
        if str(exc) not in _OVERFLOW_ERRORS:
            return
        with self._state_lock:
            self._reader_error = exc
        self._queue.put(exc)
        if str(exc) == "stdout_queue_limit_exceeded" and not self._pgid_dead:
            if self._pgid > 1 and self._pgid != os.getpgrp():
                self._pgid_dead = terminate_process_group(
                    self._proc, self._pgid, self._start_time, cancel_grace_s=0.05, already_dead=False
                )

    @staticmethod
    def _read_chunk(stream: BinaryIO, fd: int | None) -> bytes:
        try:
            return os.read(fd, _READ_CHUNK_BYTES) if fd is not None else stream.read(_READ_CHUNK_BYTES)
        except (OSError, ValueError):
            return b""

    def _read_stderr(self, stream: BinaryIO) -> None:
        fd: int | None = None
        with suppress(AttributeError, OSError, ValueError):
            fd = stream.fileno()
        while chunk := self._read_chunk(stream, fd):
            self._record_stderr(chunk)

    def _read_stdout(self, stream: BinaryIO) -> None:
        buf, fd = bytearray(), None
        with suppress(AttributeError, OSError, ValueError):
            fd = stream.fileno()
        try:
            while chunk := self._read_chunk(stream, fd):
                with self._state_lock:
                    gen = self.generation
                self._consume_stdout_chunk(buf, chunk, gen)
            if buf:
                if len(buf) > self._frame_max_bytes:
                    raise RuntimeError("output_limit_exceeded")
                with self._state_lock:
                    gen = self.generation
                self._emit_stdout_line(bytes(buf), gen)
        except RuntimeError as exc:
            self._handle_overflow(exc)
            raise
        finally:
            self._queue.put(None)
