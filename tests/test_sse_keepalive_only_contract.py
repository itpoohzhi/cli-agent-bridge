"""Контракт SSE keepalive-only (W3-B): инвариантность к нарезке (F-FSM-I2) и инварианты L2.

Факты доставки не зависят от того, как делится текст на дельты и как байты SSE режутся по сети;
кадры всегда заканчиваются `\\n\\n`, tool_calls не смешиваются с content (изоляция `<Think>`),
скользящее окно активности продлевается только полезным чанком (keepalive не продлевает).
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

import pytest
from live_isolated_harness import ALL_ON, running
from resilience_wiring_support import make_session

from core.passthrough_sliding_window import init_sliding_stream, remaining_sliding_s, step_sliding_stream

TEXT = "Привет, мир! Ёж съел 3 яблока.\nВторая строка с «кавычками» и 🙂."
SPLITS = ([TEXT], list(TEXT), [TEXT[:7], TEXT[7:13], TEXT[13:]], [TEXT[:1], TEXT[1:-1], TEXT[-1:]])


def _parse_sse(chunks: list[bytes]) -> list[str]:
    """Инкрементальный разбор SSE: кадры по пустой строке, независимо от границ чанков."""
    buffer, frames = b"", []
    for chunk in chunks:
        buffer += chunk
        while b"\n\n" in buffer:
            frame, buffer = buffer.split(b"\n\n", 1)
            frames.append(frame.decode("utf-8"))
    assert buffer == b"", "хвост без завершающего \\n\\n"
    return frames


def _canonical_stream() -> bytes:
    body = [": keepalive\n\n"] + [f"data: {json.dumps({'n': i, 't': TEXT[i]}, ensure_ascii=False)}\n\n" for i in range(12)]
    return "".join(body + ["data: [DONE]\n\n"]).encode("utf-8")


@pytest.mark.parametrize("seed", [1, 7, 42, 2026])
def test_sse_frames_invariant_under_arbitrary_byte_chunking(seed: int) -> None:
    raw = _canonical_stream()
    whole = _parse_sse([raw])
    rng = random.Random(seed)
    cuts = sorted(rng.sample(range(1, len(raw)), 25))
    pieces = [raw[a:b] for a, b in zip([0, *cuts], [*cuts, len(raw)], strict=True)]
    assert _parse_sse(pieces) == whole
    assert _parse_sse([raw[i : i + 1] for i in range(len(raw))]) == whole  # побайтово


@pytest.mark.parametrize("parts", SPLITS)
def test_delivery_facts_do_not_depend_on_delta_splitting(parts: list[str]) -> None:
    session, _wire, _ctx = make_session()
    _ = session.commit()
    _ = session.keepalive()
    for part in parts:
        _ = session.on_text(part)
    facts = session.delivery.snapshot()
    assert facts.content_bytes == len(TEXT.encode("utf-8")) and facts.delivered is True


def test_coordinator_output_invariant_to_fragmenting_of_frames() -> None:
    """Реальный коалесцер `emit_chunk`: произвольная нарезка байт даёт тот же поток кадров."""
    raw = _canonical_stream()
    outputs = []
    for size in (len(raw), 1, 5, 17):
        session, wire, _ctx = make_session()
        _ = session.coordinator.start_headers()
        wire.frames.clear()
        for i in range(0, len(raw), size):
            _ = session.coordinator.emit_chunk(raw[i : i + size])
        outputs.append("".join(wire.frames))
    assert len(set(outputs)) == 1 and outputs[0].encode("utf-8") == raw


def test_role_delta_and_keepalive_alone_never_flip_delivered() -> None:
    session, wire, ctx = make_session()
    _ = session.commit()
    for _ in range(5):
        _ = session.keepalive()
    assert ctx["stream_committed"] is True and session.delivery.snapshot().delivered is False
    assert any('"role": "assistant"' in frame for frame in wire.frames)


@pytest.mark.parametrize(("scenario", "tools"), [("eof_then_ok", False), ("malformed_valid", True)])
def test_live_stream_frames_are_well_formed_and_isolated(tmp_path: Path, scenario: str, tools: bool) -> None:
    """L2 на живом процессе: кадры закрыты `\\n\\n`, склеек слов нет, tool_calls не смешаны с content."""
    with running(tmp_path, scenario, ALL_ON) as bridge:
        result = bridge.chat(tools=tools)
    assert result.raw.endswith("\n\n") and result.done_count == 1
    frames = [f for f in result.raw.split("\n\n") if f]
    assert all(f.startswith("data: ") or f == ": keepalive" for f in frames)
    assert not re.search(r"[а-яёa-z]\.[А-ЯЁA-Z]", "".join(str(v) for v in result.delta_values("content")))
    for chunk in result.chunks:
        delta = chunk.get("choices", [{}])[0].get("delta", {})  # type: ignore[union-attr, index]
        assert not ("tool_calls" in delta and delta.get("content")), "tool_calls смешаны с content"
    assert bridge.leaks == {"orphan_pids": 0, "listeners": 0}


def test_sliding_activity_window_extends_only_on_useful_chunk() -> None:
    """Keepalive (не полезный чанк) окно не продлевает; полезный — сдвигает вперёд до предохранителя."""
    state = init_sliding_stream(0.0, 10.0, 10.0, 100.0, True)
    idle = step_sliding_stream(state, 8.0, False, True)
    assert idle.deadline_s == state.deadline_s and remaining_sliding_s(idle, 8.0) == 2.0
    useful = step_sliding_stream(state, 8.0, True, True)
    assert useful.deadline_s == 18.0 and remaining_sliding_s(useful, 8.0) == 10.0
    capped = step_sliding_stream(useful, 95.0, True, True)
    assert capped.deadline_s == capped.cap_deadline_s == 100.0
