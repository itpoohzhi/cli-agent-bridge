"""VER-001, VER-002, VER-003 tests for universal per-turn usage contract."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, replace

import pytest

from adapters.stdio_drivers.agy_driver import AgyStreamJsonDriver
from adapters.stdio_drivers.muse_codec import decode_msp_line
from adapters.stdio_drivers.opencode_driver import OpenCodeAcpDriver
from core.backend_adapter import TurnResult, Usage
from core.stdio_resident.claude_driver import ClaudeStreamJsonDriver
from core.stdio_resident.codex_driver import CodexAppServerDriver, CodexAppServerV2Driver
from core.stdio_resident.protocol_driver import DecodedChunk, StreamJsonDriver
from core.stdio_resident.rpc_drivers import AcpDriver, StreamJsonRpcDriver
from core.stdio_resident.turn_stream import TurnStreamAssembler
from core.turn_dispatch import _format_turn_output
from core.turn_usage import (
    INT64_MAX,
    NormalizeResult,
    TurnUsage,
    UsageScope,
    UsageUpdate,
    normalize_usage_update,
)
from core.turn_usage_accumulator import MAX_REJECTION_LOGS_PER_TURN, UsageAccumulator
from core.turn_usage_result import TurnResultWithUsage, make_turn_result, turn_usage_of
from core.usage_wire import build_turn_wire_usage, turn_usage_from_wire


def test_ver001_muse_live_probe_and_wire_format() -> None:
    upd = UsageUpdate(
        input_tokens=19474,
        output_tokens=1565,
        cache_read_tokens=16244,
        reasoning_tokens=1474,
        reported_total_tokens=21039,
        input_includes_cache=True,
        output_includes_reasoning=True,
        source="muse_msp_v1",
    )
    res = normalize_usage_update(upd)
    assert res.reason is None and res.advisory is None
    assert res.usage == TurnUsage(19474, 1565, 16244, None, 1474, "muse_msp_v1")
    assert res.usage.total_tokens == 21039
    wire = build_turn_wire_usage(res.usage)
    assert wire == {
        "prompt_tokens": 19474,
        "completion_tokens": 1565,
        "total_tokens": 21039,
        "prompt_tokens_details": {"cached_tokens": 16244},
        "completion_tokens_details": {"reasoning_tokens": 1474},
    }
    assert turn_usage_from_wire(wire, "roundtrip") == TurnUsage(
        19474, 1565, 16244, None, 1474, "roundtrip"
    )


def test_ver001_claude_and_agy_exclusive_accounting_and_zero_vs_absent() -> None:
    claude = normalize_usage_update(
        UsageUpdate(
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=400,
            cache_creation_tokens=200,
            input_includes_cache=False,
            output_includes_reasoning=True,
            source="claude_stream_json",
        )
    )
    assert claude.usage == TurnUsage(700, 50, 400, 200, None, "claude_stream_json")
    assert build_turn_wire_usage(claude.usage)["prompt_tokens_details"] == {"cached_tokens": 400}
    assert "completion_tokens_details" not in build_turn_wire_usage(claude.usage)

    agy = normalize_usage_update(
        UsageUpdate(
            input_tokens=120,
            output_tokens=30,
            cache_read_tokens=80,
            reasoning_tokens=70,
            input_includes_cache=False,
            output_includes_reasoning=False,
            source="agy_stream_json",
        )
    )
    assert agy.usage == TurnUsage(200, 100, 80, None, 70, "agy_stream_json")

    zero = normalize_usage_update(
        UsageUpdate(0, 0, cache_read_tokens=0, reasoning_tokens=0, source="zero")
    )
    assert zero.usage is not None
    assert build_turn_wire_usage(zero.usage) == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "prompt_tokens_details": {"cached_tokens": 0},
        "completion_tokens_details": {"reasoning_tokens": 0},
    }


@pytest.mark.parametrize(
    ("update", "expected_reason"),
    [
        (UsageUpdate(None, None), "missing_required_counters"),
        (UsageUpdate(10, None), "missing_required_counters"),
        (UsageUpdate(None, 10), "missing_required_counters"),
        (UsageUpdate(None, None, reported_total_tokens=99), "missing_required_counters"),
        (UsageUpdate(True, 10), "invalid_counter_type"),  # type: ignore[arg-type]
        (UsageUpdate(10, "5"), "invalid_counter_type"),  # type: ignore[arg-type]
        (UsageUpdate(10.0, 5), "invalid_counter_type"),  # type: ignore[arg-type]
        (UsageUpdate(-1, 5), "negative_counter"),
        (UsageUpdate(10, -5), "negative_counter"),
        (UsageUpdate(10, 5, reasoning_tokens=-1), "negative_counter"),
        (UsageUpdate(INT64_MAX + 1, 1), "counter_overflow"),
        (UsageUpdate(INT64_MAX, 1), "total_overflow"),
        (UsageUpdate(100, 50, cache_read_tokens=101, input_includes_cache=True), "cache_exceeds_prompt"),
        (UsageUpdate(100, 50, reasoning_tokens=51, output_includes_reasoning=True), "reasoning_exceeds_completion"),
        (UsageUpdate(100, 50, scope=UsageScope.SESSION_COUNTER), "session_counter_not_exportable"),
    ],
)
def test_ver001_strict_rejections_no_coercion_no_clamp(
    update: UsageUpdate, expected_reason: str
) -> None:
    res = normalize_usage_update(update)
    assert res.usage is None
    assert res.reason == expected_reason


def test_ver001_normalize_result_invariant_and_total_mismatch_advisory() -> None:
    with pytest.raises(ValueError):
        NormalizeResult(None, None)
    with pytest.raises(ValueError):
        NormalizeResult(TurnUsage(1, 2), "err")

    res = normalize_usage_update(UsageUpdate(10, 20, reported_total_tokens=999, source="test"))
    assert res.usage is not None and res.usage.total_tokens == 30
    assert res.advisory == "usage_total_mismatch"


def test_ver002_accumulator_take_last_bounds_and_log_cap() -> None:
    logs: list[str] = []
    acc = UsageAccumulator(log_fn=logs.append)
    first = UsageUpdate(1000, 200, cache_read_tokens=800, reasoning_tokens=100, source="m")
    assert acc.observe(first) == TurnUsage(1000, 200, 800, None, 100, "m")
    # Downward correction replaces whole snapshot (no stale cache_read=800 inherited!)
    down = UsageUpdate(500, 100, cache_read_tokens=None, reasoning_tokens=0, source="m")
    assert acc.observe(down) == TurnUsage(500, 100, None, None, 0, "m")
    # Invalid and SESSION_COUNTER frames preserve prior valid snapshot
    for _ in range(10):
        assert acc.observe(UsageUpdate(999, 999, scope=UsageScope.SESSION_COUNTER, source="c")) == TurnUsage(
            500, 100, None, None, 0, "m"
        )
    assert len(logs) == MAX_REJECTION_LOGS_PER_TURN
    assert all("usage_update_rejected" in line for line in logs)


def test_ver002_assembler_terminal_only_and_concurrent_isolation() -> None:
    def run_turn(prompt_n: int) -> TurnUsage | None:
        asm = TurnStreamAssembler()
        d1 = asm.process_chunk(DecodedChunk(text="hi", usage=UsageUpdate(prompt_n, 10, source="s")))
        assert d1.usage is None  # non-terminal delta never emits usage
        d2 = asm.process_chunk(DecodedChunk(text="!", is_terminal=True))
        return d2.usage

    results: dict[int, TurnUsage | None] = {}
    threads = [
        threading.Thread(target=lambda n=n: results.__setitem__(n, run_turn(n)))
        for n in (100, 200, 300, 400)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for n in (100, 200, 300, 400):
        assert results[n] == TurnUsage(n, 10, None, None, None, "s")


def test_ver003_all_six_vendor_drivers_and_generic_extractors() -> None:
    # 1. Muse MSP v1: real nested params.usage (with cacheWriteTokens & cumulative ignored) + flat fallback
    muse_nested = decode_msp_line(
        json.dumps({
            "jsonrpc": "2.0",
            "method": "session/tokenUsage",
            "params": {
                "usage": {
                    "inputTokens": 21752,
                    "outputTokens": 46,
                    "cachedTokens": 16000,
                    "cacheWriteTokens": 120,
                    "cacheReadTokens": 16000,
                    "reasoningTokens": 36,
                },
                "promptTokens": 21752,
                "totalTokens": 21798,
                "cumulative": {"promptTokens": 99999, "outputTokens": 500, "totalTokens": 100499},
            },
        })
    )
    assert muse_nested.usage is not None
    assert normalize_usage_update(muse_nested.usage).usage == TurnUsage(
        21752, 46, 16000, 120, 36, "muse_msp_v1"
    )

    muse_u = decode_msp_line(
        json.dumps({
            "jsonrpc": "2.0",
            "method": "session/tokenUsage",
            "params": {
                "inputTokens": 19474,
                "outputTokens": 1565,
                "cachedTokens": 16244,
                "reasoningTokens": 1474,
                "totalTokens": 21039,
            },
        })
    )
    assert muse_u.usage is not None
    assert normalize_usage_update(muse_u.usage).usage == TurnUsage(19474, 1565, 16244, None, 1474, "muse_msp_v1")

    # 2. Claude stream-json (preserves cache_creation_tokens)
    claude_chunk = ClaudeStreamJsonDriver().decode_line(
        json.dumps({
            "type": "result",
            "result": "ok",
            "usage": {
                "input_tokens": 50,
                "output_tokens": 25,
                "cache_read_input_tokens": 300,
                "cache_creation_input_tokens": 150,
            },
        })
    )
    assert claude_chunk is not None and claude_chunk.usage is not None
    claude_tu = normalize_usage_update(claude_chunk.usage).usage
    assert claude_tu == TurnUsage(500, 25, 300, 150, None, "claude_stream_json")

    # 3. Codex v2: last_token_usage wins over total_token_usage; total-only is SESSION_COUNTER (fail-closed)
    codex_v2 = CodexAppServerV2Driver()
    c_both = codex_v2.decode_line(
        json.dumps({
            "jsonrpc": "2.0",
            "method": "thread/tokenUsage/updated",
            "params": {
                "info": {
                    "last_token_usage": {
                        "input_tokens": 500,
                        "output_tokens": 120,
                        "cached_input_tokens": 300,
                        "reasoning_output_tokens": 40,
                    },
                    "total_token_usage": {"input_tokens": 9000, "output_tokens": 2000},
                }
            },
        })
    )
    assert c_both is not None and c_both.usage is not None
    assert normalize_usage_update(c_both.usage).usage == TurnUsage(500, 120, 300, None, 40, "codex_app_server_v2")

    c_total_only = codex_v2.decode_line(
        json.dumps({
            "jsonrpc": "2.0",
            "method": "thread/tokenUsage/updated",
            "params": {"info": {"total_token_usage": {"input_tokens": 9000, "output_tokens": 2000}}},
        })
    )
    assert c_total_only is not None and c_total_only.usage is not None
    assert c_total_only.usage.scope is UsageScope.SESSION_COUNTER
    assert normalize_usage_update(c_total_only.usage).reason == "session_counter_not_exportable"

    # 3b. Codex legacy
    c_leg = CodexAppServerDriver().decode_line(
        json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"output": "ok", "usage": {"input_tokens": 80, "output_tokens": 20}}})
    )
    assert c_leg is not None and c_leg.usage is not None
    assert normalize_usage_update(c_leg.usage).usage == TurnUsage(80, 20, None, None, None, "codex_app_server")

    # 4. Agy stream-json
    agy_c = AgyStreamJsonDriver().decode_line(
        json.dumps({
            "event": "result",
            "result": {"response": "done"},
            "usage": {"input_tokens": 100, "output_tokens": 40, "cache_read_tokens": 60, "thinking_tokens": 20},
        })
    )
    assert agy_c is not None and agy_c.usage is not None
    assert normalize_usage_update(agy_c.usage).usage == TurnUsage(160, 60, 60, None, 20, "agy_stream_json")

    # 5. OpenCode ACP: OpenAI wire & cacheless pass; ambiguous input+cache fails closed
    oc = OpenCodeAcpDriver()
    oc_oai = oc.decode_line(
        json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"usage": {"prompt_tokens": 300, "completion_tokens": 50, "prompt_tokens_details": {"cached_tokens": 100}}},
        })
    )
    assert oc_oai is not None and oc_oai.usage is not None
    assert normalize_usage_update(oc_oai.usage).usage == TurnUsage(300, 50, 100, None, None, "opencode_acp")

    oc_ambig = oc.decode_line(
        json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "result": {"usage": {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 500}},
        })
    )
    assert oc_ambig is not None and oc_ambig.usage is not None
    assert normalize_usage_update(oc_ambig.usage).reason == "ambiguous_accounting_semantics"

    # 6. Generic StreamJson / StreamJsonRpc / Acp
    sj = StreamJsonDriver().decode_line(json.dumps({"type": "done", "usage": {"input_tokens": 10, "output_tokens": 5}}))
    assert sj is not None and sj.usage is not None and normalize_usage_update(sj.usage).usage == TurnUsage(10, 5, None, None, None, "stream_json")

    rpc = StreamJsonRpcDriver().decode_line(
        json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"usage": {"prompt_tokens": 12, "completion_tokens": 8}}})
    )
    assert rpc is not None and rpc.usage is not None and normalize_usage_update(rpc.usage).usage == TurnUsage(12, 8, None, None, None, "stream_jsonrpc")

    acp = AcpDriver().decode_line(
        json.dumps({"event": "turn_complete", "payload": {"usage": {"prompt_tokens": 22, "completion_tokens": 11}}})
    )
    assert acp is not None and acp.usage is not None and normalize_usage_update(acp.usage).usage == TurnUsage(22, 11, None, None, None, "acp")


def test_ver003_lossless_turn_result_and_dispatch_format() -> None:
    tu = TurnUsage(700, 50, 400, 200, 15, "claude_stream_json")
    res = make_turn_result("hello", "think", tu)
    assert isinstance(res, TurnResult) and isinstance(res, TurnResultWithUsage)
    assert asdict(res.usage) == asdict(Usage(700, 50, 400, 200))
    replaced = replace(res, text="hello2")
    assert turn_usage_of(replaced) == tu
    out = _format_turn_output(replaced, "stdio_resident")
    assert out["turn_usage"] == tu
    assert out["usage"] == {"input_tokens": 700, "output_tokens": 50, "cache_read_tokens": 400, "cache_creation_tokens": 200}
