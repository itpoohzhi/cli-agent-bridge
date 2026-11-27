"""L1/L2 tests for agy_runtime ProcessAdmissionGuard (QA-002) and ChunkDeliveryAdapter."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

AGY_DIR = Path(__file__).resolve().parents[2] / "bridges" / "agy-bridge"
if str(AGY_DIR) not in sys.path:
    sys.path.insert(0, str(AGY_DIR))

from agy_runtime.chunk_delivery_adapter import deliver_chunked_prompt  # noqa: E402
from agy_runtime.process_admission_guard import (  # noqa: E402
    AdmissionOverloadError,
    ProcessAdmissionGuard,
    is_pgid_alive,
)
from core.lossless_contracts import DEFAULT_SAFE_FRAME_BYTES, LosslessLimits  # noqa: E402
from core.lossless_fsm import SessionState  # noqa: E402

ECHO_STREAM_STUB = """
import hashlib, json, sys
buf = []
for raw in sys.stdin:
    raw = raw.strip()
    if not raw:
        continue
    obj = json.loads(raw)
    txt = obj["message"]["content"][0]["text"]
    buf.append(txt)
    sha = hashlib.sha256("".join(buf).encode("utf-8")).hexdigest()
    sys.stdout.write(json.dumps({"type": "result", "status": "SUCCESS", "chunks": len(buf), "sha256": sha}) + "\\n")
    sys.stdout.flush()
"""

STALE_EPOCH_STUB = """
import json, sys
for raw in sys.stdin:
    if raw.strip():
        sys.stdout.write(json.dumps({"type": "result", "status": "SUCCESS", "epoch": 999}) + "\\n")
        sys.stdout.flush()
        break
"""

SLEEP_WITH_GRANDCHILD_STUB = """
import json, subprocess, sys, time
subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
first = sys.stdin.readline()
if first.strip():
    sys.stdout.write(json.dumps({"type": "result", "status": "SUCCESS"}) + "\\n")
    sys.stdout.flush()
time.sleep(60)
"""


def test_qa002_admission_4_active_2_queued_and_7th_gets_fast_429() -> None:
    guard = ProcessAdmissionGuard(max_concurrency=4, max_queue=2, queue_wait_s=0.35)
    for _ in range(4):
        guard.acquire()
    assert guard.snapshot().active == 4

    queued_errors: list[Exception] = []
    entered_queue = threading.Barrier(3)

    def _waiter() -> None:
        try:
            entered_queue.wait(timeout=2.0)
            guard.acquire(wait_s=0.25)
        except Exception as exc:  # noqa: BLE001
            queued_errors.append(exc)

    t5 = threading.Thread(target=_waiter)
    t6 = threading.Thread(target=_waiter)
    t5.start()
    t6.start()
    entered_queue.wait(timeout=2.0)

    # Wait briefly until both 5th and 6th are queued
    deadline = time.monotonic() + 1.0
    while guard.snapshot().queued < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert guard.snapshot().queued == 2

    # 7th request must fail fast (<50ms) with HTTP 429 without spawning
    t0 = time.perf_counter()
    with pytest.raises(AdmissionOverloadError) as exc_info:
        guard.acquire(wait_s=5.0)
    dt_7th = time.perf_counter() - t0
    assert exc_info.value.http_status == 429
    assert dt_7th < 0.05

    t5.join(timeout=2.0)
    t6.join(timeout=2.0)
    assert len(queued_errors) == 2
    assert all(isinstance(e, AdmissionOverloadError) and e.http_status == 429 for e in queued_errors)

    for _ in range(4):
        guard.release()
    assert guard.snapshot().active == 0
    assert guard.snapshot().queued == 0


def test_chunked_delivery_350kib_cyrillic_emoji_byte_exact_without_pipe_deadlock() -> None:
    markers = [f"MK_{i:02d}" for i in range(1, 13)]
    block = 'Кириллица "quoted"\nline\\slash 🚀🧪 — ' * 55
    payload = "\n".join(f"[{mk}] " + block * 11 for mk in markers)
    expected_sha = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    guard = ProcessAdmissionGuard(max_concurrency=4, max_queue=2)
    limits = LosslessLimits(lossless_enabled=True, safe_frame_bytes=DEFAULT_SAFE_FRAME_BYTES, max_chunks=16)
    with guard.slot():
        proc = guard.spawn_isolated([sys.executable, "-c", ECHO_STREAM_STUB])
        try:
            res = deliver_chunked_prompt(proc, payload, limits, guard, epoch=1, frame_timeout_s=10.0)
        finally:
            guard.teardown_process(proc)

    assert res.ok is True
    assert res.state is SessionState.COMPLETED
    assert res.anchor_committed is True
    assert res.chunks_delivered >= 4
    last_ev = json.loads(res.stdout_lines[-1])
    assert last_ev["chunks"] == res.chunks_delivered
    assert last_ev["sha256"] == expected_sha
    assert guard.snapshot().active_pgids == ()


def test_mid_chunk_cancel_performs_shielded_pgid_teardown_zero_orphans() -> None:
    guard = ProcessAdmissionGuard(max_concurrency=4, max_queue=2, kill_grace_s=0.2)
    limits = LosslessLimits(lossless_enabled=True, safe_frame_bytes=DEFAULT_SAFE_FRAME_BYTES, max_chunks=16)
    payload = "а" * 120_000  # 2 chunks
    cancel_ev = threading.Event()

    def _cancel_after_first_ack(_line: str) -> None:
        cancel_ev.set()

    with guard.slot():
        proc = guard.spawn_isolated([sys.executable, "-c", SLEEP_WITH_GRANDCHILD_STUB])
        pgid = os.getpgid(proc.pid)
        res = deliver_chunked_prompt(
            proc,
            payload,
            limits,
            guard,
            epoch=2,
            frame_timeout_s=5.0,
            cancel_event=cancel_ev,
            on_line=_cancel_after_first_ack,
        )

    assert res.ok is False
    assert res.state is SessionState.CANCELLED
    assert res.anchor_committed is False
    assert res.receipt is not None
    assert not is_pgid_alive(pgid)
    assert guard.snapshot().active_pgids == ()


def test_stale_epoch_ack_terminates_session_and_cleans_pgid() -> None:
    guard = ProcessAdmissionGuard(max_concurrency=4, max_queue=2, kill_grace_s=0.2)
    limits = LosslessLimits(lossless_enabled=True, safe_frame_bytes=DEFAULT_SAFE_FRAME_BYTES, max_chunks=16)
    with guard.slot():
        proc = guard.spawn_isolated([sys.executable, "-c", STALE_EPOCH_STUB])
        pgid = os.getpgid(proc.pid)
        res = deliver_chunked_prompt(proc, "hello", limits, guard, epoch=1, frame_timeout_s=5.0)

    assert res.ok is False
    assert res.state is SessionState.EPOCH_MISMATCH
    assert res.http_status == 409
    assert not is_pgid_alive(pgid)
    assert guard.snapshot().active_pgids == ()
