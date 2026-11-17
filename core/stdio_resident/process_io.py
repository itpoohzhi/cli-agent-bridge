"""Process lifecycle and stream I/O for resident stdio slots."""

from __future__ import annotations

import queue
import subprocess
import threading
import time
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from typing import BinaryIO


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

    proc: subprocess.Popen[bytes]
    pid: int
    generation: int
    created_at_mono: float
    last_activity_mono: float
    _reader_threads: list[threading.Thread]
    _queue: queue.Queue[TaggedLine | None]
    _closed: bool
    _state_lock: threading.Lock
    _eof_readers: int

    def __init__(self, proc: subprocess.Popen[bytes]) -> None:
        self.proc = proc
        self.pid = proc.pid
        self.generation = 0
        self.created_at_mono = time.monotonic()
        self.last_activity_mono = self.created_at_mono
        self._reader_threads = []
        self._queue = queue.Queue()
        self._closed = False
        self._state_lock = threading.Lock()
        self._eof_readers = 0

    @classmethod
    def spawn(
        cls,
        argv: list[str],
        cwd: str,
        env: Mapping[str, str] | None = None,
    ) -> ResidentProcessHandle:
        """Start a subprocess and daemon readers for both output streams."""

        proc: subprocess.Popen[bytes] = subprocess.Popen(
            argv,
            cwd=cwd,
            env=dict(env) if env is not None else None,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        handle = cls(proc)
        stdout = proc.stdout
        stderr = proc.stderr
        if stdout is None or stderr is None:
            with suppress(OSError):
                proc.kill()
            raise StdioIoError("process output pipes were not created")

        for stream, is_stderr in ((stdout, False), (stderr, True)):
            thread = threading.Thread(
                target=handle._read_stream,
                args=(stream, is_stderr),
                daemon=True,
                name=f"stdio-reader-{proc.pid}-{'err' if is_stderr else 'out'}",
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
        deadline = None
        if timeout_s is not None:
            deadline = time.monotonic() + max(0.0, timeout_s)

        while True:
            timeout = None
            if deadline is not None:
                timeout = max(0.0, deadline - time.monotonic())
            try:
                tagged = self._queue.get(timeout=timeout)
            except queue.Empty:
                return None
            if tagged is None:
                return None
            with self._state_lock:
                active_generation = self.generation
            if tagged.generation == active_generation:
                return tagged

    def is_alive(self) -> bool:
        """Return whether the subprocess is still running."""

        return self.proc.poll() is None

    def terminate_gracefully(self, grace_s: float, timeout_s: float = 2.0) -> int:
        """Terminate, escalate to kill after grace, and release all pipes."""

        try:
            if self.is_alive():
                with suppress(OSError):
                    self.proc.terminate()
                try:
                    _ = self.proc.wait(timeout=max(0.0, grace_s))
                except subprocess.TimeoutExpired:
                    with suppress(OSError):
                        self.proc.kill()
                    try:
                        _ = self.proc.wait(timeout=max(0.0, timeout_s))
                    except subprocess.TimeoutExpired as exc:
                        raise StdioProcessTerminated(
                            "process did not exit after forced termination"
                        ) from exc
        finally:
            self._closed = True
            for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
                if stream is not None:
                    with suppress(OSError, ValueError):
                        stream.close()
            for thread in self._reader_threads:
                thread.join(timeout=max(0.0, timeout_s))

        returncode = self.proc.returncode
        if returncode is None:
            raise StdioProcessTerminated("process termination has no return code")
        return returncode

    def _read_stream(self, stream: BinaryIO, is_stderr: bool) -> None:
        try:
            while True:
                with self._state_lock:
                    generation = self.generation
                raw_line = stream.readline()
                if not raw_line:
                    break
                tagged = TaggedLine(
                    line=raw_line.decode("utf-8", errors="replace").rstrip("\r\n"),
                    generation=generation,
                    pid=self.pid,
                    is_stderr=is_stderr,
                )
                if not is_stderr:
                    with self._state_lock:
                        self.last_activity_mono = tagged.timestamp_mono
                self._queue.put(tagged)
        finally:
            with self._state_lock:
                self._eof_readers += 1
                all_readers_finished = self._eof_readers == 2
            if all_readers_finished:
                self._queue.put(None)
