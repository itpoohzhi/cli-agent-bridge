"""Deterministic L1 unit tests for core/lossless_contracts.py and core/lossless_chunker.py."""

from __future__ import annotations

import ast
import hashlib
import json
import time
import tracemalloc
from pathlib import Path

import pytest

from core.lossless_chunker import (
    ENVELOPE_OVERHEAD_BYTES,
    ChunkLimitExceededError,
    encode_user_ndjson_frame,
    estimate_min_frames,
    iter_ndjson_frames,
    stream_chunk_summary,
)
from core.lossless_contracts import (
    DEFAULT_MAX_CHUNKS,
    DEFAULT_SAFE_FRAME_BYTES,
    HARD_FRAME_CLAMP_BYTES,
    MIN_FRAME_BYTES,
    RefuseStatusMode,
    build_loss_receipt,
    resolve_lossless_limits,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_IO_IMPORTS = frozenset({"asyncio", "subprocess", "socket", "urllib", "http", "pathlib"})


def test_bnd001_zero_io_imports_in_core_lossless_modules() -> None:
    for rel in ("core/lossless_contracts.py", "core/lossless_chunker.py"):
        tree = ast.parse((REPO_ROOT / rel).read_text(encoding="utf-8"))
        found: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module.split(".")[0])
        assert not (found & FORBIDDEN_IO_IMPORTS), f"Forbidden I/O import in {rel}: {found & FORBIDDEN_IO_IMPORTS}"


def test_resolve_lossless_limits_defaults_all_safe_off() -> None:
    limits = resolve_lossless_limits({})
    assert limits.lossless_enabled is False
    assert limits.muse_lossless_enabled is False
    assert limits.muse_refuse_status_mode is RefuseStatusMode.LEGACY_502
    assert limits.safe_frame_bytes == DEFAULT_SAFE_FRAME_BYTES
    assert limits.hard_frame_clamp_bytes == HARD_FRAME_CLAMP_BYTES
    assert limits.max_chunks == DEFAULT_MAX_CHUNKS
    assert limits.max_concurrency == 4
    assert limits.max_queue == 2
    assert limits.queue_wait_s == 10.0


def test_resolve_lossless_limits_priority_and_clamping() -> None:
    dyn = {
        "lossless_delivery_enabled": True,
        "safe_frame_bytes": 80000,
        "muse_lossless_enabled": True,
        "muse_refuse_status_mode": "413",
    }
    from_dyn = resolve_lossless_limits({}, dyn)
    assert from_dyn.lossless_enabled is True
    assert from_dyn.safe_frame_bytes == 80000
    assert from_dyn.muse_lossless_enabled is True
    assert from_dyn.muse_refuse_status_mode is RefuseStatusMode.FAIL_CLOSED_413

    env = {
        "AGY_BRIDGE_LOSSLESS_ENABLED": "false",
        "AGY_BRIDGE_SAFE_FRAME_BYTES": "9999999",
        "AGY_BRIDGE_LOSSLESS_MAX_CHUNKS": "0",
        "AGY_BRIDGE_LOSSLESS_QUEUE_WAIT_S": "nan",
        "MUSE_BRIDGE_REFUSE_STATUS_MODE": "legacy_502",
        "BRIDGE_LOSS_RECEIPT_DIGEST_MODE": "omitted",
    }
    over = resolve_lossless_limits(env, dyn)
    assert over.lossless_enabled is False
    assert over.safe_frame_bytes == HARD_FRAME_CLAMP_BYTES
    assert over.max_chunks == 1
    assert over.queue_wait_s == 10.0
    assert over.muse_refuse_status_mode is RefuseStatusMode.LEGACY_502
    assert over.digest_mode == "omitted"

    low = resolve_lossless_limits({"AGY_BRIDGE_SAFE_FRAME_BYTES": "100"})
    assert low.safe_frame_bytes == MIN_FRAME_BYTES


def test_streaming_350kib_cyrillic_json_emoji_lossless_and_mem_budget() -> None:
    markers = [f"MK_{i:02d}" for i in range(1, 13)]
    block = 'Кириллица "quoted"\nline\\slash \x07 🚀🧪 — ' * 55
    payload = "\n".join(f"[{mk}] " + block * 11 for mk in markers)
    raw = payload.encode("utf-8")
    assert len(raw) >= 350 * 1024
    raw_sha = hashlib.sha256(raw).hexdigest()

    tracemalloc.start()
    t0 = time.perf_counter()
    frame_sizes: list[int] = []
    synthetics: list[bool] = []
    for frame in iter_ndjson_frames(payload, safe_frame_bytes=DEFAULT_SAFE_FRAME_BYTES):
        frame_sizes.append(len(frame.ndjson_bytes))
        synthetics.append(frame.is_synthetic)
    dt = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert dt <= 2.0
    assert (peak / len(raw)) <= 2.5
    assert max(frame_sizes) <= DEFAULT_SAFE_FRAME_BYTES
    assert len(frame_sizes) <= DEFAULT_MAX_CHUNKS
    assert synthetics[:-1] == [True] * (len(synthetics) - 1)
    assert synthetics[-1] is False

    parts = [
        json.loads(f.ndjson_bytes.decode("utf-8"))["message"]["content"][0]["text"]
        for f in iter_ndjson_frames(payload, safe_frame_bytes=DEFAULT_SAFE_FRAME_BYTES)
    ]
    reconstructed = "".join(parts)
    assert hashlib.sha256(reconstructed.encode("utf-8")).hexdigest() == raw_sha
    for mk in markers:
        assert mk in reconstructed

    summary = stream_chunk_summary(payload)
    assert summary.sha256_hex == raw_sha
    assert summary.total_frames == len(frame_sizes)
    assert summary.raw_utf8_bytes == len(raw)
    assert summary.max_frame_bytes <= DEFAULT_SAFE_FRAME_BYTES


@pytest.mark.parametrize(
    "text",
    [
        "",
        "a",
        "x" * (DEFAULT_SAFE_FRAME_BYTES - ENVELOPE_OVERHEAD_BYTES - 2),
        "x" * (DEFAULT_SAFE_FRAME_BYTES - ENVELOPE_OVERHEAD_BYTES - 1),
        ("а" * 44990) + "🚀" + ("я" * 45000),
        "\x00\x01\x08\x0c\n\r\t\"\\" * 5000,
    ],
)
def test_boundary_cases_byte_exact_and_valid_utf8_json(text: str) -> None:
    frames = list(iter_ndjson_frames(text, safe_frame_bytes=DEFAULT_SAFE_FRAME_BYTES))
    assert frames
    for idx, frame in enumerate(frames):
        assert frame.index == idx
        assert len(frame.ndjson_bytes) <= DEFAULT_SAFE_FRAME_BYTES
        assert frame.is_synthetic is (idx < len(frames) - 1)
    reconstructed = "".join(
        json.loads(f.ndjson_bytes.decode("utf-8"))["message"]["content"][0]["text"]
        for f in frames
    )
    assert reconstructed == text


def test_chunk_limit_exceeded_fail_closed_and_hard_clamp() -> None:
    big = "a" * (DEFAULT_SAFE_FRAME_BYTES * 3)
    assert estimate_min_frames(len(big), DEFAULT_SAFE_FRAME_BYTES) >= 3
    with pytest.raises(ChunkLimitExceededError) as exc_info:
        list(iter_ndjson_frames(big, safe_frame_bytes=DEFAULT_SAFE_FRAME_BYTES, max_chunks=2))
    assert exc_info.value.max_chunks == 2

    with pytest.raises(ValueError, match="hard clamp"):
        list(iter_ndjson_frames("abc", safe_frame_bytes=HARD_FRAME_CLAMP_BYTES + 1))

    # Escape expansion overflow during streaming (short char len, large escaped bytes)
    escaped = "\x00" * 30000
    with pytest.raises(ChunkLimitExceededError):
        list(iter_ndjson_frames(escaped, safe_frame_bytes=DEFAULT_SAFE_FRAME_BYTES, max_chunks=1))


def test_loss_receipt_threat001_redaction_and_digest_modes() -> None:
    secret_prompt = b"TOP_SECRET_TOKEN_XYZ_999 user confidential payload"
    rec_hmac = build_loss_receipt(
        reason="chunk_limit_exceeded",
        http_status=413,
        prompt_raw=secret_prompt,
        chunk_count=17,
        digest_mode="salted_hmac",
        salt=b"ephemeral-salt",
    )
    wire = rec_hmac.to_wire_dict()
    serialized = json.dumps(wire)
    assert "TOP_SECRET_TOKEN_XYZ_999" not in serialized
    assert "confidential" not in serialized
    assert wire["http_status"] == 413
    assert wire["prompt_bytes"] == len(secret_prompt)
    assert len(str(wire["prompt_digest"])) == 16

    rec_omit = build_loss_receipt(
        reason="chunk_limit_exceeded",
        http_status=413,
        prompt_raw=secret_prompt,
        digest_mode="omitted",
    )
    assert rec_omit.to_wire_dict()["prompt_digest"] == ""
    assert encode_user_ndjson_frame("hi").endswith(b"\n")
