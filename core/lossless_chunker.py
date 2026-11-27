"""Pure streaming O(L) UTF-8/JSON NDJSON frame chunker (BND-001: zero I/O)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from typing import Final

from core.lossless_contracts import (
    DEFAULT_MAX_CHUNKS,
    DEFAULT_SAFE_FRAME_BYTES,
    HARD_FRAME_CLAMP_BYTES,
    ChunkFrame,
    ChunkSummary,
)

ENVELOPE_PREFIX: Final[str] = (
    '{"event":"user","message":{"role":"user","content":[{"type":"text","text":'
)
ENVELOPE_SUFFIX: Final[str] = "}]}}\n"
ENVELOPE_OVERHEAD_BYTES: Final[int] = len((ENVELOPE_PREFIX + ENVELOPE_SUFFIX).encode("utf-8"))
JSON_QUOTES_OVERHEAD_BYTES: Final[int] = 2

_TWO_BYTE_ESCAPES: Final[frozenset[str]] = frozenset(('"', "\\", "\b", "\f", "\n", "\r", "\t"))


class ChunkLimitExceededError(ValueError):
    """Raised fail-closed when a prompt requires more than max_chunks NDJSON frames."""

    def __init__(self, message: str, *, estimated_chunks: int, max_chunks: int) -> None:
        super().__init__(message)
        self.estimated_chunks = estimated_chunks
        self.max_chunks = max_chunks


def encode_user_ndjson_frame(text: str) -> bytes:
    """Encode a single stream-json user frame with ensure_ascii=False."""
    payload = ENVELOPE_PREFIX + json.dumps(text, ensure_ascii=False) + ENVELOPE_SUFFIX
    return payload.encode("utf-8")


def _json_char_utf8_bytes(ch: str) -> int:
    """Exact UTF-8 byte cost of one character inside json.dumps(..., ensure_ascii=False)."""
    if ch in _TWO_BYTE_ESCAPES:
        return 2
    cp = ord(ch)
    if cp < 0x20:
        return 6
    if cp < 0x80:
        return 1
    if cp < 0x800:
        return 2
    if cp < 0x10000:
        return 3
    return 4


def _effective_text_budget(safe_frame_bytes: int) -> int:
    if safe_frame_bytes > HARD_FRAME_CLAMP_BYTES:
        raise ValueError(
            f"safe_frame_bytes ({safe_frame_bytes}) exceeds hard clamp ({HARD_FRAME_CLAMP_BYTES})"
        )
    budget = safe_frame_bytes - ENVELOPE_OVERHEAD_BYTES - JSON_QUOTES_OVERHEAD_BYTES
    if budget < 6:
        raise ValueError(f"safe_frame_bytes ({safe_frame_bytes}) leaves insufficient text budget")
    return budget


def estimate_min_frames(
    prompt_bytes: int,
    safe_frame_bytes: int = DEFAULT_SAFE_FRAME_BYTES,
) -> int:
    """O(1) lower bound on required NDJSON frames for early fail-closed 413 rejection."""
    budget = _effective_text_budget(safe_frame_bytes)
    if prompt_bytes <= 0:
        return 1
    return (prompt_bytes + budget - 1) // budget


def _next_slice_end(text: str, start: int, budget: int) -> int:
    """Advance character cursor in O(slice_len) without exceeding JSON+UTF-8 byte budget."""
    length = len(text)
    acc = 0
    end = start
    while end < length:
        need = _json_char_utf8_bytes(text[end])
        if acc + need > budget:
            break
        acc += need
        end += 1
    if end == start:
        raise ValueError("Single Unicode code point exceeds frame text budget")
    return end


def iter_ndjson_frames(
    text: str,
    *,
    safe_frame_bytes: int = DEFAULT_SAFE_FRAME_BYTES,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
    epoch: int = 1,
) -> Iterator[ChunkFrame]:
    """Single-pass O(L) generator holding at most one encoded NDJSON frame in memory."""
    if max_chunks < 1:
        raise ValueError("max_chunks must be >= 1")
    budget = _effective_text_budget(safe_frame_bytes)
    if not text:
        frame = encode_user_ndjson_frame("")
        yield ChunkFrame(0, 1, frame, 0, False, epoch)
        return

    raw_len_est = len(text)
    min_needed = estimate_min_frames(raw_len_est, safe_frame_bytes)
    if min_needed > max_chunks:
        raise ChunkLimitExceededError(
            f"Prompt requires at least {min_needed} frames (> max_chunks={max_chunks})",
            estimated_chunks=min_needed,
            max_chunks=max_chunks,
        )

    pos = 0
    total_chars = len(text)
    index = 0
    while pos < total_chars:
        if index >= max_chunks:
            raise ChunkLimitExceededError(
                f"Prompt exceeded max_chunks={max_chunks} during streaming split",
                estimated_chunks=index + 1,
                max_chunks=max_chunks,
            )
        end = _next_slice_end(text, pos, budget)
        slice_text = text[pos:end]
        frame = encode_user_ndjson_frame(slice_text)
        if len(frame) > safe_frame_bytes:
            raise AssertionError(f"Frame size {len(frame)} exceeded {safe_frame_bytes}")
        is_last = end >= total_chars
        yield ChunkFrame(
            index=index,
            total_hint=max(min_needed, index + 1),
            ndjson_bytes=frame,
            text_bytes=len(slice_text.encode("utf-8")),
            is_synthetic=not is_last,
            epoch=epoch,
        )
        pos = end
        index += 1


def stream_chunk_summary(
    text: str,
    *,
    safe_frame_bytes: int = DEFAULT_SAFE_FRAME_BYTES,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
) -> ChunkSummary:
    """Compute streaming chunk metrics and incremental SHA-256 without storing frames."""
    hasher = hashlib.sha256()
    total_frames = 0
    raw_utf8 = 0
    total_ndjson = 0
    max_frame = 0
    for chunk in iter_ndjson_frames(
        text, safe_frame_bytes=safe_frame_bytes, max_chunks=max_chunks
    ):
        total_frames += 1
        raw_utf8 += chunk.text_bytes
        flen = len(chunk.ndjson_bytes)
        total_ndjson += flen
        if flen > max_frame:
            max_frame = flen
        decoded = json.loads(chunk.ndjson_bytes.decode("utf-8"))
        part_text = decoded["message"]["content"][0]["text"]
        hasher.update(part_text.encode("utf-8"))
    return ChunkSummary(
        total_frames=total_frames,
        raw_utf8_bytes=raw_utf8,
        total_ndjson_bytes=total_ndjson,
        max_frame_bytes=max_frame,
        sha256_hex=hasher.hexdigest(),
    )
