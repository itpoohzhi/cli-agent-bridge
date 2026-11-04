from __future__ import annotations

import codecs
import json
import os
import selectors
import signal
import subprocess
from dataclasses import asdict, is_dataclass
from typing import Iterator

from zen_bridge.domain.models import (
    DeadlineBudget,
    ErrorClassification,
    RequestEnvelope,
    StreamChunk,
    ZenError,
)


def _deadline_error() -> ZenError:
    return ZenError(
        classification=ErrorClassification.TRANSIENT,
        status_code=504,
        message="Gateway Timeout: CLI fallback deadline budget exhausted",
    )


def _remaining(budget: DeadlineBudget) -> float:
    remaining = budget.remaining_s()
    if remaining <= 0:
        raise _deadline_error()
    return remaining


class ProcGroupManager:
    """Own the process group, including descendants surviving their parent."""

    def spawn_process(
        self,
        cmd: list[str],
        env: dict[str, str],
        cwd: str | None = None,
    ) -> subprocess.Popen:
        return subprocess.Popen(
            cmd,
            env=env,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setpgrp,
            bufsize=0,
        )

    @staticmethod
    def _signal_group(proc: subprocess.Popen, sig: int) -> None:
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            pass

    @staticmethod
    def _close_pipes(proc: subprocess.Popen) -> None:
        for pipe in (proc.stdin, proc.stdout, proc.stderr):
            if pipe is not None:
                try:
                    pipe.close()
                except OSError:
                    pass

    def killpg_drain(
        self, proc: subprocess.Popen, timeout_s: float = 2.0
    ) -> None:
        try:
            self._signal_group(proc, signal.SIGTERM)
            try:
                proc.wait(timeout=max(0.0, timeout_s))
            except subprocess.TimeoutExpired:
                pass
        finally:
            try:
                # Always kill the group: the parent may exit before its children.
                self._signal_group(proc, signal.SIGKILL)
            finally:
                try:
                    if proc.poll() is None:
                        proc.kill()
                    proc.wait()
                finally:
                    self._close_pipes(proc)


class ZenCliFallback:
    """Stream a CLI's UTF-8 stdout with one shared wall-clock deadline."""

    def __init__(
        self,
        cli_cmd: list[str],
        proc_manager: ProcGroupManager | None = None,
    ) -> None:
        self.cli_cmd = list(cli_cmd)
        self.proc_manager = (
            proc_manager if proc_manager is not None else ProcGroupManager()
        )

    @staticmethod
    def _serialize(envelope: RequestEnvelope) -> bytes:
        dump_json = getattr(envelope, "model_dump_json", None)
        if callable(dump_json):
            return (dump_json() + "\n").encode("utf-8")
        if is_dataclass(envelope):
            payload = asdict(envelope)
        else:
            payload = vars(envelope)
        return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")

    @staticmethod
    def _close_input(proc: subprocess.Popen) -> None:
        if proc.stdin is not None:
            proc.stdin.close()
            proc.stdin = None

    def _write_input(
        self,
        selector: selectors.BaseSelector,
        proc: subprocess.Popen,
        pending: memoryview,
    ) -> memoryview:
        try:
            written = os.write(proc.stdin.fileno(), pending)
        except BlockingIOError:
            return pending
        except BrokenPipeError:
            written = len(pending)
        pending = pending[written:]
        if not pending:
            selector.unregister(proc.stdin)
            self._close_input(proc)
        return pending

    @staticmethod
    def _read_output(proc: subprocess.Popen) -> bytes | None:
        try:
            return os.read(proc.stdout.fileno(), 65536)
        except BlockingIOError:
            return None

    @staticmethod
    def _register_pipes(
        selector: selectors.BaseSelector, proc: subprocess.Popen
    ) -> None:
        os.set_blocking(proc.stdin.fileno(), False)
        os.set_blocking(proc.stdout.fileno(), False)
        selector.register(proc.stdin, selectors.EVENT_WRITE, "stdin")
        selector.register(proc.stdout, selectors.EVENT_READ, "stdout")

    def _stream_process(
        self,
        proc: subprocess.Popen,
        payload: bytes,
        budget: DeadlineBudget,
    ) -> Iterator[StreamChunk]:
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        pending = memoryview(payload)
        with selectors.DefaultSelector() as selector:
            self._register_pipes(selector, proc)
            while True:
                events = selector.select(timeout=_remaining(budget))
                if not events:
                    _remaining(budget)
                    continue
                for key, _ in events:
                    _remaining(budget)
                    if key.data == "stdin":
                        pending = self._write_input(selector, proc, pending)
                        continue
                    data = self._read_output(proc)
                    if data is None:
                        continue
                    text = decoder.decode(data, final=not data)
                    if text:
                        yield StreamChunk(content=text)
                    if not data:
                        return

    def execute_stream(
        self, envelope: RequestEnvelope, budget: DeadlineBudget
    ) -> Iterator[StreamChunk]:
        if budget.remaining_s() <= 0:
            raise ZenError(
                classification=ErrorClassification.TRANSIENT,
                status_code=504,
                message=(
                    "Gateway Timeout: deadline budget exhausted "
                    "before CLI fallback"
                ),
            )
        proc = None
        try:
            payload = self._serialize(envelope)
            _remaining(budget)
            proc = self.proc_manager.spawn_process(
                self.cli_cmd, os.environ.copy()
            )
            yield from self._stream_process(proc, payload, budget)
            return_code = proc.wait(timeout=_remaining(budget))
            if return_code != 0:
                raise self._process_error(f"CLI exited with status {return_code}")
        except subprocess.TimeoutExpired as exc:
            raise _deadline_error() from exc
        except OSError as exc:
            raise self._process_error(f"CLI fallback failed: {exc}") from exc
        finally:
            if proc is not None:
                self.proc_manager.killpg_drain(proc)

    @staticmethod
    def _process_error(message: str) -> ZenError:
        return ZenError(
            classification=ErrorClassification.TRANSIENT,
            status_code=502,
            message=message,
        )
