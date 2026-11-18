"""Контрактные red-repro тесты REQ-002 и REQ-003 (волна W0-A)."""

from __future__ import annotations

import importlib
import importlib.util
import io
import json
import os
import random
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from adapters.passthrough_adapter import (
    PassthroughAdapter,
    PassthroughLimits,
    relay_sse,
)
from core.http_post_ingress import clean_transport_request
from core.stream_resilience_policy import UncommittedTurnBuffer
from core.tool_emulation import StreamNormalizer
from core.tool_mode import (
    NormalizerModeSpec as ModeSpec,
    NormalizerSinks as Sinks,
    ToolMode,
    ToollessTagPolicy as TagPolicy,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BRIDGE_PY = _REPO_ROOT / "bridges" / "agy-bridge" / "server.py"


def _load_bridge() -> Any:
    """Загрузить bridges/agy-bridge/server.py без сокетов и подпроцессов."""
    mod_name = "agy_bridge_server_dsh_contract_test"
    cached = sys.modules.get(mod_name)
    if cached is not None:
        return cached
    os.environ.setdefault("AGY_BRIDGE_KEY", "test-key-dsh-contracts")
    spec = importlib.util.spec_from_file_location(mod_name, _BRIDGE_PY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


def _chunk_split(text: str, mode: str) -> list[str]:
    if mode == "whole":
        return [text]
    if mode == "1char":
        return list(text)
    if mode == "7char":
        return [text[i : i + 7] for i in range(0, len(text), 7)]
    rng = random.Random(42)
    chunks: list[str] = []
    pos = 0
    while pos < len(text):
        step = rng.randint(1, 9)
        chunks.append(text[pos : pos + step])
        pos += step
    return chunks


def _bash_call(call_id: str, idx: int = 0) -> dict[str, Any]:
    fn = {"name": "bash", "arguments": "{}"}
    return {"index": idx, "id": call_id, "type": "function", "function": fn}


def _seq46_raw_text() -> str:
    c1 = json.dumps({"name": "bash", "arguments": {"command": "ls"}})
    c2 = json.dumps({"name": "bash", "arguments": {"command": "pwd"}})
    return (
        f"Ищу файлы 🔍.\n\n<tool_call>{c1}</tool_call>\n\n"
        f"<tool_call>{c2}</tool_call>\n"
    )


def _sse_frame(delta: dict[str, Any], finish: str | None = None) -> bytes:
    payload = {"choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
    return b"data: " + json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n\n"


def _parse_sse_payloads(frames: list[bytes]) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for raw in frames:
        for line in raw.decode("utf-8").splitlines():
            if line.startswith("data: "):
                body = line[6:].strip()
                if body and body != "[DONE]":
                    parsed.append(json.loads(body))
    return parsed


def _make_runner() -> tuple[Any, dict[str, list[Any]]]:
    _load_bridge()
    runner_mod = importlib.import_module("agy_runtime.sse_body_runner")
    runner_cls: Any = getattr(runner_mod, "_SseBodyRunner")
    records: dict[str, list[Any]] = {"text": [], "reasoning": [], "calls": []}
    runner = object.__new__(runner_cls)
    session = SimpleNamespace(
        buffer=UncommittedTurnBuffer(),
        tool_turn=None,
        disconnected=False,
        commit=lambda: True,
        on_text=lambda val: records["text"].append(val) or True,
        on_reasoning=lambda val: records["reasoning"].append(val) or True,
        on_calls=lambda batch: records["calls"].append(batch) or True,
        ledger=SimpleNamespace(
            _active=-1,
            client_delivery_reconciled=True,
            mark_step_completed=lambda _idx: None,
        ),
    )
    vars(runner).update(s=session)
    return runner, records


def test_stream_normalizer_isolates_seq46_across_chunk_splits() -> None:
    """REQ-002/F-FSM-I2: 0 delta.content при tool_calls для whole/1char/7char/random."""
    raw_text = _seq46_raw_text()
    baseline: tuple[str, list[dict[str, Any]]] | None = None
    for mode in ("whole", "1char", "7char", "random"):
        content_ev: list[str] = []
        reason_ev: list[str] = []
        calls: list[dict[str, Any]] = []
        norm = StreamNormalizer(
            on_content=content_ev.append,
            on_reasoning=reason_ev.append,
            on_tool_call=calls.append,
            strict_live=True,
        )
        for piece in _chunk_split(raw_text, mode):
            norm.feed_text(piece)
        norm.finish()
        assert content_ev == []
        assert norm.content == ""
        assert len(calls) == 2
        assert "Ищу файлы 🔍." in "".join(reason_ev)
        current = ("".join(reason_ev).strip(), calls)
        baseline = current if baseline is None else baseline
        assert current == baseline


def test_sse_body_runner_drain_isolates_content_and_coalesces_calls() -> None:
    """REQ-002: _SseBodyRunner.drain() не пускает преамбулу/\\n в on_text при tools."""
    runner, records = _make_runner()
    assert runner.stage("Ищу файлы.\n\n")
    assert runner.stage_calls([_bash_call("call_1", 0)])
    assert runner.stage("\n\n")
    assert runner.stage_calls([_bash_call("call_2", 0)])
    assert runner.stage("\n")
    assert runner.drain() is True
    assert records["text"] == []
    assert len(records["calls"]) == 1
    assert [item["index"] for item in records["calls"][0]] == [0, 1]
    assert "Ищу файлы." in "".join(records["reasoning"])


def test_passthrough_relay_isolates_tool_step_whitespace() -> None:
    """REQ-002: relay_sse подавляет пробельный content при tool_calls."""
    assert PassthroughAdapter is not None
    raw_stream = b"".join([
        _sse_frame({"tool_calls": [_bash_call("c1", 0)]}),
        _sse_frame({"content": "\n\n"}),
        _sse_frame({"tool_calls": [_bash_call("c2", 1)]}),
        _sse_frame({"content": "\n"}),
        _sse_frame({}, finish="tool_calls"),
        b"data: [DONE]\n\n",
    ])
    out: list[bytes] = []
    relay_sse(
        io.BytesIO(raw_stream).readline,
        out.append,
        tool_schemas=None,
        limits=PassthroughLimits(),
    )
    content_deltas = [
        choice["delta"]["content"]
        for item in _parse_sse_payloads(out)
        for choice in item.get("choices", [])
        if "content" in (choice.get("delta") or {})
    ]
    assert content_deltas == []


def test_pure_text_without_tools_streams_first_delta_before_eof() -> None:
    """REQ-002 TTFT: чистый текст без tools/<tool_call> отдаёт первый чанк до EOF."""
    chunks: list[str] = []
    spec = ModeSpec(ToolMode.OFF, TagPolicy.TEXT)
    norm = StreamNormalizer.for_mode(spec, Sinks(on_content=chunks.append))
    norm.feed_text("Первый фрагмент ")
    assert chunks == ["Первый фрагмент "]
    norm.feed_text("второй.")
    norm.finish()
    assert "".join(chunks) == "Первый фрагмент второй."

    out: list[bytes] = []
    stream_lines = (
        _sse_frame({"content": "Первый"})
        + _sse_frame({}, finish="stop")
        + b"data: [DONE]\n\n"
    ).splitlines(keepends=True)
    idx, seen_before_second = 0, []

    def _readline(_n: int) -> bytes:
        nonlocal idx
        if idx == 2:
            seen_before_second.append(len(out))
        if idx >= len(stream_lines):
            return b""
        data = stream_lines[idx]
        idx += 1
        return data

    limits = PassthroughLimits()
    relay_sse(_readline, out.append, tool_schemas=None, limits=limits, mode_spec=spec)
    assert seen_before_second == [1]


def test_http_ingress_sanitizes_messages_5_2_and_orphan_calls() -> None:
    """REQ-003: ingress убирает пробелы messages.5.2 и закрывает сиротский call."""
    request: dict[str, Any] = {
        "model": "m",
        "messages": [
            {"role": "user", "content": "run"},
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "c1", "name": "bash", "input": {}},
                    {"type": "text", "text": "\n\n\n\n\n\n\n"},
                    {"type": "text", "text": "Plan"},
                ],
            },
            {"role": "user", "content": "next"},
            {
                "role": "assistant",
                "content": "\n\n\n\n\n\n\n",
                "tool_calls": [_bash_call("c2")],
            },
            {"role": "user", "content": "after"},
        ],
    }
    raw = json.dumps(request, ensure_ascii=False).encode("utf-8")
    clean_raw, clean_req = clean_transport_request(raw, request)
    msgs = clean_req["messages"]
    first_blocks = msgs[1]["content"]
    assert all(
        not (b.get("type") == "text" and not str(b.get("text", "")).strip())
        for b in first_blocks
    )
    assert [b["type"] for b in first_blocks] == ["text", "tool_use"]
    assert msgs[4]["content"] is None
    assert msgs[5]["role"] == "tool" and msgs[5]["tool_call_id"] == "c2"
    assert json.loads(clean_raw.decode("utf-8")) == clean_req
    same_raw, _ = clean_transport_request(clean_raw, clean_req)
    assert same_raw is clean_raw


def test_agy_messages_to_prompt_heals_orphan_and_dangling_tool_results() -> None:
    """REQ-003: _messages_to_prompt лечит сиротские call и висячие tool-ответы."""
    bridge = _load_bridge()
    messages = [
        {"role": "user", "content": "check"},
        {
            "role": "assistant",
            "content": "\n\n\n\n\n\n\n",
            "tool_calls": [_bash_call("c1", 0), _bash_call("c2", 1)],
        },
        {"role": "tool", "tool_call_id": "c1", "content": "ok"},
        {"role": "user", "content": "next"},
        {"role": "tool", "tool_call_id": "orphan_res", "content": "stale"},
    ]
    prompt = bridge._messages_to_prompt(messages)
    assert "[tool result c1]" in prompt
    assert "[tool result c2]" in prompt
    assert "[tool result orphan_res]" not in prompt
