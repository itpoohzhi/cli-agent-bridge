"""Тесты учёта usage Codex app-server v2: thread/tokenUsage/updated (.last vs .total, W5)."""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.stdio_resident.codex_usage import (  # noqa: E402
    codex_v2_effects_to_chunk,
    extract_codex_v2_usage,
)
from core.turn_usage import UsageScope, normalize_usage_update  # noqa: E402


def _frame(last: dict[str, Any] | None, total: dict[str, Any] | None) -> dict[str, Any]:
    token_usage: dict[str, Any] = {"modelContextWindow": 272000}
    if last is not None:
        token_usage["last"] = last
    if total is not None:
        token_usage["total"] = total
    return {
        "jsonrpc": "2.0",
        "method": "thread/tokenUsage/updated",
        "params": {"threadId": "th_w5", "tokenUsage": token_usage},
    }


_LAST: dict[str, Any] = {
    "inputTokens": 15334,
    "outputTokens": 16310,
    "cachedInputTokens": 10240,
    "reasoningOutputTokens": 14976,
    "totalTokens": 31644,
}
_TOTAL: dict[str, Any] = {
    "inputTokens": 50000,
    "outputTokens": 20000,
    "cachedInputTokens": 30000,
    "reasoningOutputTokens": 18000,
    "totalTokens": 70000,
}


def test_turn_snapshot_taken_from_last_not_total() -> None:
    usage = extract_codex_v2_usage(_frame(_LAST, _TOTAL))
    assert usage is not None
    assert usage.scope is UsageScope.TURN_SNAPSHOT
    assert usage.input_tokens == 15334
    assert usage.output_tokens == 16310
    assert usage.cache_read_tokens == 10240
    assert usage.reasoning_tokens == 14976
    assert usage.reported_total_tokens == 31644
    result = normalize_usage_update(usage)
    assert result.usage is not None
    assert result.usage.prompt_tokens == 15334
    assert result.usage.completion_tokens == 16310
    assert result.reason is None and result.advisory is None


def test_total_only_frame_is_fail_closed_session_counter() -> None:
    # fail-closed: SESSION_COUNTER не приписывается ходу (normalize отклоняет)
    usage = extract_codex_v2_usage(_frame(None, _TOTAL))
    assert usage is not None
    assert usage.scope is UsageScope.SESSION_COUNTER
    assert usage.input_tokens == 50000
    assert normalize_usage_update(usage).reason == "session_counter_not_exportable"


def test_container_without_last_and_total_is_ignored() -> None:
    assert extract_codex_v2_usage(_frame(None, None)) is None


def test_last_snapshot_wins_within_single_turn() -> None:
    frames = [
        _frame({"inputTokens": 100, "outputTokens": 50, "totalTokens": 150}, _TOTAL),
        _frame({"inputTokens": 200, "outputTokens": 80, "totalTokens": 280}, _TOTAL),
        _frame({"inputTokens": 300, "outputTokens": 120, "totalTokens": 420}, _TOTAL),
    ]
    snapshots = [extract_codex_v2_usage(frame) for frame in frames]
    assert all(u is not None and u.scope is UsageScope.TURN_SNAPSHOT for u in snapshots)
    final = snapshots[-1]
    assert final is not None
    assert final.input_tokens == 300 and final.output_tokens == 120
    chunk = codex_v2_effects_to_chunk((), frames[-1])
    assert chunk is not None and chunk.usage is not None
    assert chunk.usage.input_tokens == 300 and chunk.usage.output_tokens == 120


def test_concurrent_turns_two_threads_no_cross_contamination() -> None:
    barrier = threading.Barrier(2)
    results: dict[str, list[int]] = {}

    def _session_worker(session_key: str, out_tokens: int) -> None:
        frames = [
            _frame(
                {"inputTokens": 10 * i, "outputTokens": out_tokens, "totalTokens": 10 * i + out_tokens},
                _TOTAL,
            )
            for i in (1, 2, 3)
        ]
        barrier.wait()
        outputs: list[int] = []
        for frame in frames:
            usage = extract_codex_v2_usage(frame)
            assert usage is not None and usage.output_tokens is not None
            outputs.append(usage.output_tokens)
        results[session_key] = outputs

    threads = [
        threading.Thread(target=_session_worker, args=("session_a", 111)),
        threading.Thread(target=_session_worker, args=("session_b", 222)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results["session_a"] == [111, 111, 111]
    assert results["session_b"] == [222, 222, 222]
