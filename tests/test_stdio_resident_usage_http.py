"""VER-004 & VER-005 tests: HTTP JSON/SSE/error/telemetry, proxy, and dynamic kill-switch."""

from __future__ import annotations

import io
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from adapters.stdio_resident_adapter import StdioResidentAdapter
from adapters.stdio_resident_delta import stream_assembled_deltas
from core.backend_adapter import TurnContext, TurnResult, Usage
from core.http_usage import SseUsageMeta, error_wire_usage, nonstream_wire_usage, sse_usage_chunk
from core.runtime_env import _SNAPSHOTS, FLAG_STDIO_USAGE_CONTRACT, stdio_usage_contract_enabled
from core.stdio_resident.protocol_driver import DecodedChunk
from core.stdio_resident.turn_error_sse import ResidentTurnError
from core.stdio_resident.zero_canon_router import (
    execute_routed_turn,
    execute_routed_turn_result,
    proxy_zero_canon_bridge_turn,
    proxy_zero_canon_bridge_turn_result,
)
from core.turn_dispatch import _format_turn_output
from core.turn_usage import TurnUsage, UsageUpdate
from core.turn_usage_result import make_turn_result
from core.usage_wire import build_wire_usage


def _legacy_wire(inp: object, out: object, cached: object) -> dict[str, Any]:
    wire, _ = build_wire_usage(inp, out, cached, input_includes_cache=True)
    return wire


def test_ver005_http_json_sse_and_error_usage_helpers() -> None:
    tu = TurnUsage(19474, 1565, 16244, None, 1474, "muse_msp_v1")
    out = _format_turn_output(make_turn_result("ok", "", tu), "stdio_resident")

    wire_json = nonstream_wire_usage(out, _legacy_wire)
    assert wire_json == {
        "prompt_tokens": 19474,
        "completion_tokens": 1565,
        "total_tokens": 21039,
        "prompt_tokens_details": {"cached_tokens": 16244},
        "completion_tokens_details": {"reasoning_tokens": 1474},
    }

    meta = SseUsageMeta("cmpl-1", 123, "muse-ember-1.0", "stop")
    sse = sse_usage_chunk(out, meta, _legacy_wire)
    assert sse is not None and sse.startswith("data: ")
    parsed = json.loads(sse.removeprefix("data: ").strip())
    assert parsed["usage"] == wire_json

    # Observed all-zero emits SSE usage chunk; absent usage emits None
    zero_out = _format_turn_output(make_turn_result("ok", "", TurnUsage(0, 0, source="z")), "stdio_resident")
    assert sse_usage_chunk(zero_out, meta, _legacy_wire) is not None
    absent_out = _format_turn_output(TurnResult(text="ok"), "stdio_resident")
    assert sse_usage_chunk(absent_out, meta, _legacy_wire) is None

    # Error path: positive preserved, observed all-zero suppressed
    assert error_wire_usage(out, legacy_wire_fn=_legacy_wire, counter_fn=lambda v: int(v or 0)) == wire_json
    assert error_wire_usage(zero_out, legacy_wire_fn=_legacy_wire, counter_fn=lambda v: int(v or 0)) is None
    assert error_wire_usage(absent_out, tu, legacy_wire_fn=_legacy_wire, counter_fn=lambda v: int(v or 0)) == wire_json


def test_ver005_midstream_resident_turn_error_preserves_usage_and_respects_kill_switch() -> None:
    def failing_stream(req: dict[str, Any]) -> Iterator[dict[str, Any]]:
        def gen() -> Iterator[DecodedChunk]:
            yield DecodedChunk(text="part1", usage=UsageUpdate(120, 30, cache_read_tokens=40, reasoning_tokens=10, source="muse_msp_v1"))
            raise RuntimeError("stream interrupted")

        yield from stream_assembled_deltas(
            gen(),
            usage_enabled=bool(req.get("_usage_enabled", True)),
            usage_sink=req.get("_turn_usage_sink"),
        )

    emitted: list[tuple[str, str]] = []
    with pytest.raises(ResidentTurnError) as exc_info:
        execute_routed_turn_result(
            failing_stream,
            "msp-v1",
            {"prompt": "hi", "model": "muse-ember-1.0", "_usage_enabled": True},
            lambda k, v: emitted.append((k, v)),
        )
    err = exc_info.value
    assert getattr(err, "turn_usage", None) == TurnUsage(120, 30, 40, None, 10, "muse_msp_v1")
    assert err.response.body.get("usage") == {
        "prompt_tokens": 120,
        "completion_tokens": 30,
        "total_tokens": 150,
        "prompt_tokens_details": {"cached_tokens": 40},
        "completion_tokens_details": {"reasoning_tokens": 10},
    }
    assert '"reasoning_tokens": 10' in err.response.sse

    # Kill-switch off: no turn_usage attached and no usage in SSE error envelope
    with pytest.raises(ResidentTurnError) as off_info:
        execute_routed_turn_result(
            failing_stream,
            "msp-v1",
            {"prompt": "hi", "model": "muse-ember-1.0", "_usage_enabled": False},
            lambda k, v: emitted.append((k, v)),
        )
    assert getattr(off_info.value, "turn_usage", None) is None
    assert "usage" not in off_info.value.response.body


def test_ver004_legacy_router_and_proxy_9881_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps({
        "choices": [{"message": {"content": "hi", "reasoning_content": "r"}}],
        "usage": {
            "prompt_tokens": 250,
            "completion_tokens": 60,
            "total_tokens": 310,
            "prompt_tokens_details": {"cached_tokens": 200},
            "completion_tokens_details": {"reasoning_tokens": 25},
        },
    }).encode("utf-8")

    class _FakeResp(io.BytesIO):
        def __enter__(self) -> "_FakeResp":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    class _FakeOpener:
        def open(self, _req: object, timeout: float = 10.0) -> _FakeResp:
            _ = timeout
            return _FakeResp(payload)

    monkeypatch.setattr("urllib.request.build_opener", lambda *_a: _FakeOpener())

    res = proxy_zero_canon_bridge_turn_result("http://127.0.0.1:9881/v1", "claude-sonnet", "ping")
    assert res.text == "hi" and res.reasoning == "r"
    assert res.usage == TurnUsage(250, 60, 200, None, 25, "claude_zero_canon_bridge")

    # Legacy tuple API preserved
    assert proxy_zero_canon_bridge_turn("http://127.0.0.1:9881/v1", "claude-sonnet", "ping") == ("hi", "r")
    assert execute_routed_turn(
        lambda _req: iter([{"choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]}]),
        "msp-v1",
        {"prompt": "hi"},
        None,
    ) == ("ok", "")


def test_ver005_dynamic_kill_switch_true_false_true_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "dynamic_config.json"
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(cfg))
    monkeypatch.delenv(FLAG_STDIO_USAGE_CONTRACT, raising=False)

    adapter = StdioResidentAdapter(
        "muse",
        {"protocol": "msp-v1", "cli_argv": ["muse", "msp"]},
    )

    def fake_turn_stream(**_kwargs: Any) -> Iterator[DecodedChunk]:
        yield DecodedChunk(
            text="answer",
            usage=UsageUpdate(500, 100, cache_read_tokens=200, cache_creation_tokens=50, reasoning_tokens=30, source="muse_msp_v1"),
        )
        yield DecodedChunk(is_terminal=True)

    monkeypatch.setattr(adapter._session_manager, "execute_turn_stream", fake_turn_stream)
    ctx = TurnContext(model="muse-ember-1.0", effort="high", prompt="test", cwd=str(tmp_path))

    # 1. Default True (lossless cache_creation_tokens + source preserved!)
    _SNAPSHOTS.clear()
    assert stdio_usage_contract_enabled() is True
    r_on = adapter.execute_turn(ctx, None)
    assert r_on.usage == Usage(500, 100, 200, 50)
    assert getattr(r_on, "turn_usage", None) == TurnUsage(500, 100, 200, 50, 30, "muse_msp_v1")

    # 2. Flip to False via dynamic_config.json (no restart)
    cfg.write_text(json.dumps({FLAG_STDIO_USAGE_CONTRACT: False}), encoding="utf-8")
    _SNAPSHOTS.clear()
    assert stdio_usage_contract_enabled() is False
    r_off = adapter.execute_turn(ctx, None)
    assert r_off.usage == Usage(0, 0, None, None)
    assert getattr(r_off, "turn_usage", None) is None
    # Streaming deltas also omit usage when flag is False
    chunks_off = list(adapter.execute_chat({"prompt": "test", "cwd": str(tmp_path)}))
    assert all("usage" not in c for c in chunks_off)

    # 3. Flip back to True
    cfg.write_text(json.dumps({FLAG_STDIO_USAGE_CONTRACT: True}), encoding="utf-8")
    _SNAPSHOTS.clear()
    assert stdio_usage_contract_enabled() is True
    r_back = adapter.execute_turn(ctx, None)
    assert r_back.usage == Usage(500, 100, 200, 50)
    chunks_on = list(adapter.execute_chat({"prompt": "test", "cwd": str(tmp_path)}))
    assert sum(1 for c in chunks_on if "usage" in c) == 1
