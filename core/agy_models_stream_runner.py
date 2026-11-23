"""Bounded streaming process runner for ``agy models``."""

from __future__ import annotations

import os
import selectors
import signal
import stat
import subprocess
import time
from contextlib import suppress

_READ_CHUNK_BYTES = 8192
_FORBIDDEN_BIN_CHARS = ("\x00", "\n", "\r", "$", "`", ";", "|", "&", "<", ">")


class _OutputTooLarge(RuntimeError):
    """Raised when the models command exceeds its output limit."""


def _validate_binary(raw_bin: str | None) -> str:
    """Resolve and validate the ``agy`` executable path."""
    binary = (
        raw_bin
        if raw_bin is not None and raw_bin != ""
        else os.path.expanduser("~/.local/bin/agy.real")
    )
    if any(ch in binary for ch in _FORBIDDEN_BIN_CHARS):
        raise ValueError("invalid_agy_bin")
    if not os.path.isabs(binary):
        raise ValueError("invalid_agy_bin")
    try:
        st = os.stat(binary)
    except OSError as exc:
        raise ValueError("invalid_agy_bin") from exc
    if not stat.S_ISREG(st.st_mode) or not os.access(binary, os.X_OK):
        raise ValueError("invalid_agy_bin")
    return binary


def _kill_pg(proc: subprocess.Popen[bytes], grace_s: float = 0.2) -> None:
    """Terminate and force-kill the process group for ``proc``."""
    pgid: int | None = None
    with suppress(OSError):
        pgid = os.getpgid(proc.pid)
    with suppress(OSError):
        if pgid is not None:
            os.killpg(pgid, signal.SIGTERM)
        else:
            proc.terminate()
    with suppress(subprocess.TimeoutExpired, OSError):
        proc.wait(timeout=grace_s)
    with suppress(OSError):
        if pgid is not None:
            os.killpg(pgid, signal.SIGKILL)
        elif proc.poll() is None:
            proc.kill()
    with suppress(subprocess.TimeoutExpired, OSError):
        proc.wait(timeout=1.0)


def _stream_bounded_output(
    proc: subprocess.Popen[bytes], deadline: float, max_output_bytes: int
) -> bytes:
    """Read stdout up to ``max_output_bytes`` before ``deadline``."""
    if proc.stdout is None:
        raise RuntimeError("stdout_pipe_missing")
    fd = proc.stdout.fileno()
    os.set_blocking(fd, False)
    sel = selectors.DefaultSelector()
    chunks: list[bytes] = []
    total = 0
    try:
        sel.register(fd, selectors.EVENT_READ)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not sel.select(timeout=remaining):
                _kill_pg(proc)
                raise TimeoutError("agy models timed out")
            try:
                chunk = os.read(fd, _READ_CHUNK_BYTES)
            except BlockingIOError:
                continue
            if not chunk:
                return b"".join(chunks)
            total += len(chunk)
            if total > max_output_bytes:
                _kill_pg(proc)
                raise _OutputTooLarge("output_too_large")
            chunks.append(chunk)
    finally:
        with suppress(OSError):
            sel.close()


def default_agy_models_runner(
    timeout_s: float, max_output_bytes: int
) -> tuple[int, str]:
    """Run ``agy models`` with streaming output cap and process-group kill."""
    binary = _validate_binary(os.environ.get("AGY_BIN"))
    if timeout_s <= 0 or max_output_bytes <= 0:
        raise ValueError("invalid_probe_limits")
    proc = subprocess.Popen(
        [binary, "models"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=False,
        start_new_session=True,
    )
    deadline = time.monotonic() + timeout_s
    try:
        raw_bytes = _stream_bounded_output(proc, deadline, max_output_bytes)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _kill_pg(proc)
            raise TimeoutError("agy models timed out")
        try:
            proc.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            _kill_pg(proc)
            raise TimeoutError("agy models timed out") from None
        rc = int(proc.returncode) if proc.returncode is not None else 1
        return rc, raw_bytes.decode("utf-8", errors="replace")
    finally:
        if proc.stdout is not None:
            with suppress(OSError):
                proc.stdout.close()
        if proc.poll() is None:
            _kill_pg(proc)
