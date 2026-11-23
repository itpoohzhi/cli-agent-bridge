"""L3 regression tests: thread/slot isolation in shared CodexAppServerV2Driver."""

from __future__ import annotations

import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.stdio_resident.codex_attestation_wire import (  # noqa: E402
    ZeroCanonSseHeaderGate,
    build_v2_admission_proof,
    build_v2_completion_proof,
)
from core.stdio_resident.codex_driver import CodexAppServerV2Driver  # noqa: E402
from core.stdio_resident.process_io import LINE, TaggedLine  # noqa: E402

DUMMY_SECRET = "sk-dummy-concurrent-secret-777"


class _ScriptedCodexHandle:
    """Thread-safe fake codex app-server handle synchronized at protocol phases."""

    def __init__(self, idx: int, barrier: threading.Barrier | None = None) -> None:
        self.idx = idx
        self.pid = 9100 + idx
        self.generation = 0
        self._pgid_dead = True
        self._barrier = barrier
        self._out: list[str] = []
        self.thread_id = f"srv-thr-{idx}"
        self.turn_id = f"srv-trn-{idx}"
        self.model = "gpt-6.1-terra"
        self.effort = "medium"

    def write(self, data: bytes) -> None:
        msg = json.loads(data.decode("utf-8").strip())
        method = msg.get("method")
        rid = msg.get("id")
        if method == "initialize":
            if self._barrier is not None:
                _ = self._barrier.wait(timeout=5.0)
            self._out.append(json.dumps({"jsonrpc": "2.0", "id": rid, "result": {"userAgent": "codex-test/2"}}))
        elif method == "thread/start":
            if self._barrier is not None:
                _ = self._barrier.wait(timeout=5.0)
            self._out.append(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": rid,
                        "result": {
                            "thread": {"id": self.thread_id},
                            "model": self.model,
                            "reasoningEffort": self.effort,
                        },
                    }
                )
            )
        elif method == "turn/start":
            if self._barrier is not None:
                _ = self._barrier.wait(timeout=5.0)
            self._out.extend(
                [
                    json.dumps({"jsonrpc": "2.0", "id": rid, "result": {"turn": {"id": self.turn_id, "status": "inProgress"}}}),
                    json.dumps({"jsonrpc": "2.0", "method": "turn/started", "params": {"threadId": self.thread_id, "turn": {"id": self.turn_id}}}),
                    json.dumps({"jsonrpc": "2.0", "method": "item/agentMessage/delta", "params": {"threadId": self.thread_id, "turnId": self.turn_id, "itemId": "i1", "delta": f"reply-{self.idx}"}}),
                    json.dumps({"jsonrpc": "2.0", "method": "turn/completed", "params": {"threadId": self.thread_id, "turn": {"id": self.turn_id, "status": "completed"}}}),
                ]
            )

    def read_stdout_line(self, timeout_s: float | None = None) -> TaggedLine | None:
        _ = timeout_s
        if not self._out:
            return None
        return TaggedLine(line=self._out.pop(0), generation=self.generation, pid=self.pid, is_stderr=False)

    def read_stdout_outcome(self, timeout_s: float | None = None) -> tuple[str, TaggedLine | None]:
        return (LINE, self.read_stdout_line(timeout_s))


def test_shared_codex_v2_driver_handles_4_concurrent_zero_canon_turns_without_race(tmp_path: Path) -> None:
    """Red->Green L3 regression: 4 concurrent threads on ONE CodexAppServerV2Driver never clobber _state."""
    home = tmp_path / "home"
    codex_dir = home / ".codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "auth.json").write_text('{"tokens": {}}', encoding="utf-8")
    (codex_dir / "config.toml").write_text('model = "gpt-6.1-terra"\n', encoding="utf-8")

    driver = CodexAppServerV2Driver()
    barrier = threading.Barrier(4)

    def _run_worker(idx: int) -> tuple[str, str, str, str]:
        zc_root = tmp_path / f"zc-{idx}"
        zc_root.mkdir()
        _ = driver.build_zero_canon_env({"HOME": str(home), "CODEX_HOME": str(codex_dir)}, str(zc_root))
        handle = _ScriptedCodexHandle(idx, barrier)
        assert driver.run_handshake(handle, timeout_s=5.0) is True
        ctx = {"model": "gpt-6.1-terra", "effort": "medium", "review_profile": "Zero-Canon", "cwd": str(zc_root)}
        assert driver.prepare_turn(handle, ctx, timeout_s=5.0) is True
        frame = driver.encode_turn(f"prompt-{idx}", ctx)
        handle.write(frame)
        parts: list[str] = []
        adm_tid = ""
        while True:
            line = handle.read_stdout_line(timeout_s=5.0)
            assert line is not None
            chunk = driver.decode_line(line.line)
            if chunk is not None and chunk.text:
                parts.append(chunk.text)
                adm = build_v2_admission_proof(driver, model="gpt-6.1-terra", effort="medium")
                assert adm is not None
                adm_tid = adm.thread_id
            if driver.is_terminal(line.line, chunk):
                assert driver.perform_turn_teardown(handle, ctx, timeout_s=2.0) is True
                break
        comp = build_v2_completion_proof(driver, model="gpt-6.1-terra", effort="medium")
        assert comp is not None
        return ("".join(parts), adm_tid, comp.admission.thread_id, comp.admission.turn_id)

    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(_run_worker, range(1, 5)))

    for idx, (text, adm_tid, comp_tid, comp_turn) in enumerate(results, start=1):
        assert text == f"reply-{idx}"
        assert adm_tid == f"srv-thr-{idx}"
        assert comp_tid == f"srv-thr-{idx}"
        assert comp_turn == f"srv-trn-{idx}"


def test_shared_codex_v2_driver_preserves_hot_resident_thread_across_threads() -> None:
    """Resident non-Zero-Canon handle reuses server thread_id when leased by a different thread."""
    driver = CodexAppServerV2Driver()
    handle = _ScriptedCodexHandle(99, barrier=None)
    ctx = {"model": "gpt-6.1-sol", "effort": "high", "review_profile": "standard"}

    def _turn_1() -> None:
        assert driver.run_handshake(handle, timeout_s=5.0) is True
        assert driver.prepare_turn(handle, ctx, timeout_s=5.0) is True
        handle.write(driver.encode_turn("first", ctx))
        while True:
            line = handle.read_stdout_line(timeout_s=5.0)
            assert line is not None
            chunk = driver.decode_line(line.line)
            if driver.is_terminal(line.line, chunk):
                assert driver.perform_turn_teardown(handle, ctx, timeout_s=2.0) is True
                break

    def _turn_2() -> str:
        # Different thread, NO run_handshake (generation > 0): must find bound thread_id via handle!
        handle.generation = 1
        assert driver.prepare_turn(handle, ctx, timeout_s=5.0) is True
        assert driver.protocol_state.thread_id == "srv-thr-99"
        frame = json.loads(driver.encode_turn("second", ctx).decode("utf-8"))
        return str(frame["params"]["threadId"])

    with ThreadPoolExecutor(max_workers=1) as ex1:
        ex1.submit(_turn_1).result(timeout=5.0)
    with ThreadPoolExecutor(max_workers=1) as ex2:
        reused_tid = ex2.submit(_turn_2).result(timeout=5.0)
    assert reused_tid == "srv-thr-99"


def test_pre_stream_error_logs_redacted_code_without_secret() -> None:
    logs: list[str] = []
    sent: list[tuple[int, Any]] = []
    lease = SimpleNamespace(failures=[], record_failure=lambda e: lease.failures.append(e))
    handler = SimpleNamespace(
        _review_profile="Zero-Canon",
        _headers_already_sent=False,
        _client_write_dead=False,
        _response_status=0,
        _send=lambda st, body: sent.append((st, body)),
    )
    gate = ZeroCanonSseHeaderGate.for_request(handler, {"backend": "codex"})
    handled = gate.handle_pre_stream_error(
        RuntimeError(f"protocol handshake failed Bearer {DUMMY_SECRET}"),
        lease,
        log_fn=logs.append,
    )
    assert handled is True
    assert sent and sent[0][0] == 502
    assert any("sse_pre_stream_error status=502 code=resident_protocol_failed" in line for line in logs)
    assert all(DUMMY_SECRET not in line for line in logs)


def test_zero_canon_does_not_leak_into_subsequent_standard_turn_on_same_thread(tmp_path: Path) -> None:
    """F-001/F-008 regression: Zero-Canon -> teardown -> standard turn on same worker thread stays standard."""
    home = tmp_path / "home"
    codex_dir = home / ".codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "auth.json").write_text('{"tokens": {}}', encoding="utf-8")
    (codex_dir / "config.toml").write_text('model = "gpt-6.1-terra"\n', encoding="utf-8")

    driver = CodexAppServerV2Driver()
    # 1. Zero-Canon turn on this thread
    zc_root = tmp_path / "zc-seq"
    zc_root.mkdir()
    _ = driver.build_zero_canon_env({"HOME": str(home), "CODEX_HOME": str(codex_dir)}, str(zc_root))
    zc_handle = _ScriptedCodexHandle(11, barrier=None)
    zc_ctx = {"model": "gpt-6.1-terra", "effort": "medium", "review_profile": "Zero-Canon", "cwd": str(zc_root)}
    assert driver.run_handshake(zc_handle, timeout_s=5.0) is True
    assert driver.protocol_state.zero_canon is True
    assert driver.prepare_turn(zc_handle, zc_ctx, timeout_s=5.0) is True
    zc_handle.write(driver.encode_turn("zc-prompt", zc_ctx))
    while True:
        line = zc_handle.read_stdout_line(timeout_s=5.0)
        assert line is not None
        chunk = driver.decode_line(line.line)
        if driver.is_terminal(line.line, chunk):
            assert driver.perform_turn_teardown(zc_handle, zc_ctx, timeout_s=2.0) is True
            break

    # 2. Subsequent standard turn on the EXACT SAME thread must NOT inherit zero_canon=True
    std_handle = _ScriptedCodexHandle(12, barrier=None)
    std_ctx = {"model": "gpt-6.1-sol", "effort": "high", "review_profile": "standard"}
    assert driver.run_handshake(std_handle, timeout_s=5.0) is True
    assert driver.protocol_state.zero_canon is False
    assert driver.prepare_turn(std_handle, std_ctx, timeout_s=5.0) is True
    assert driver.protocol_state.zero_canon is False
    std_handle.write(driver.encode_turn("std-prompt", std_ctx))
    while True:
        line = std_handle.read_stdout_line(timeout_s=5.0)
        assert line is not None
        chunk = driver.decode_line(line.line)
        if driver.is_terminal(line.line, chunk):
            assert driver.perform_turn_teardown(std_handle, std_ctx, timeout_s=2.0) is True
            break
    # Standard resident handle state must still be retained on std_handle after teardown
    assert driver._lookup_handle_state(std_handle) is not None
    assert driver._lookup_handle_state(zc_handle) is None


def test_slots_only_handle_weakref_cleanup_prevents_leak_and_id_aliasing() -> None:
    """F-010 regression: __slots__ handle uses weakref cleanup, no stale id() leak after GC."""
    import gc

    class _SlottedHandle:
        __slots__ = ("__weakref__", "_out", "pid", "generation")

        def __init__(self) -> None:
            self.pid = 9500
            self.generation = 0
            self._out: list[str] = []

        def write(self, data: bytes) -> None:
            msg = json.loads(data.decode("utf-8").strip())
            if msg.get("method") == "initialize":
                self._out.append(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": {"userAgent": "codex/2"}}))

        def read_stdout_line(self, timeout_s: float | None = None) -> TaggedLine | None:
            _ = timeout_s
            return TaggedLine(line=self._out.pop(0), generation=0, pid=self.pid, is_stderr=False) if self._out else None

    driver = CodexAppServerV2Driver()
    h: _SlottedHandle | None = _SlottedHandle()
    assert driver.run_handshake(h, timeout_s=5.0) is True
    assert driver._lookup_handle_state(h) is not None
    assert len(driver._weak_slots) == 1
    h = None
    gc.collect()
    assert len(driver._weak_slots) == 0
