"""F-FSM-I2: Chunk-Boundary Invariance test suite.

Verifies that any standard SSE/NDJSON stream containing:
- reasoning_content
- tool_calls
- Cyrillic UTF-8 multibyte characters
- terminal done frame
produces bit-for-bit identical stream events whether fed as:
1 chunk, 1-byte chunks, 7-byte chunks, or 50 random split cuts.
"""

from __future__ import annotations

import codecs
import importlib
import random
import time
from typing import Any

import pytest

from core.stream_fsm.machine import StreamMachine
from core.stream_fsm.types import EmitChunk
from core.tool_emulation import LiveParserError, StreamNormalizer
from core.tool_mode import (
    NormalizerSinks,
    ToolMode,
    ToollessTagPolicy,
    build_mode_spec,
)

SAMPLE_SSE_STREAM = (
    'data: {"choices": [{"delta": {"reasoning_content": "Анализирую требования FSM на кириллице..."}}]}\n\n'
    'data: {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_weather", "function": {"name": "get_weather", "arguments": "{\\"location\\": \\"Москва\\"}"}}]}}]}\n\n'
    'data: {"choices": [{"delta": {"content": "Готово! Все данные собраны."}}]}\n\n'
    'data: [DONE]\n\n'
)


def _collect_events(chunks: list[bytes]) -> list:
    """Прогоняет поток чанков через StreamMachine и собирает результирующие эффекты."""
    machine = StreamMachine()
    events = []
    for chunk in chunks:
        effs = machine.feed(chunk)
        events.extend(effs)
    events.extend(machine.finish())
    return events


def _generate_random_slices(data: bytes, cuts_count: int, seed: int) -> list[bytes]:
    """Генерирует случайную нарезку байтового массива."""
    rng = random.Random(seed)
    n = len(data)
    cut_indices = sorted(rng.sample(range(1, n), min(cuts_count, n - 1)))
    chunks = []
    prev = 0
    for idx in cut_indices:
        chunks.append(data[prev:idx])
        prev = idx
    chunks.append(data[prev:])
    return chunks


def test_chunk_boundary_invariance_comprehensive():
    """Тест F-FSM-I2: побайтовая идентичность событий при любой фрагментации."""
    raw_bytes = SAMPLE_SSE_STREAM.encode("utf-8")
    t_start = time.perf_counter()

    # 1. Эталон: 1 цельный чанк
    baseline = _collect_events([raw_bytes])
    assert len(baseline) >= 4, "Должно быть как минимум 4 события"
    assert any(isinstance(e, EmitChunk) and e.is_reasoning is True for e in baseline), "Должен присутствовать chunk с is_reasoning=True"
    assert any(isinstance(e, EmitChunk) and e.is_reasoning is False for e in baseline), "Должен присутствовать chunk с is_reasoning=False"

    # 2. Нарезка по 1 байту
    byte_chunks = [bytes([b]) for b in raw_bytes]
    events_1byte = _collect_events(byte_chunks)
    assert events_1byte == baseline, "События при нарезке по 1 байту отличаются от эталона!"

    # 3. Нарезка по 7 байт
    seven_chunks = [raw_bytes[i : i + 7] for i in range(0, len(raw_bytes), 7)]
    events_7byte = _collect_events(seven_chunks)
    assert events_7byte == baseline, "События при нарезке по 7 байт отличаются от эталона!"

    # 4. 50 случайных сплитов
    for seed in range(50):
        cuts = 5 + (seed % 20)
        random_chunks = _generate_random_slices(raw_bytes, cuts, seed=seed)
        events_random = _collect_events(random_chunks)
        assert events_random == baseline, f"Случайная нарезка (seed={seed}) отличается от эталона!"

    elapsed = time.perf_counter() - t_start
    print(f"F-FSM-I2 elapsed time: {elapsed:.3f}s")
    assert elapsed <= 3.0, f"Время выполнения теста {elapsed:.3f}s превышает лимит 3.0s!"


def _run_normalizer_chunks(
    chunks: list[bytes], *, cutoff_enabled: bool = False
) -> tuple[list[dict[str, Any]], str, str, StreamNormalizer]:
    content: list[str] = []
    reasoning: list[str] = []
    calls: list[dict[str, Any]] = []
    sinks = NormalizerSinks(content.append, reasoning.append, calls.append)
    norm = StreamNormalizer.for_mode(
        build_mode_spec(ToolMode.EMULATE, ToollessTagPolicy.ERROR),
        sinks,
        strict_live=True,
    )
    if cutoff_enabled:
        configure = getattr(norm, "configure_post_call_policy", None)
        if configure is not None:
            policy_mod = importlib.import_module("core.tool_post_call_policy")
            configure(policy_mod.PostCallPolicy(cutoff_enabled=True))
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    for chunk in chunks:
        text = decoder.decode(chunk, final=False)
        if text:
            norm.feed_text(text)
    tail = decoder.decode(b"", final=True)
    if tail:
        norm.feed_text(tail)
    norm.finish()
    return calls, "".join(content), "".join(reasoning), norm


def _all_split_variants(raw_bytes: bytes) -> list[tuple[str, list[bytes]]]:
    variants: list[tuple[str, list[bytes]]] = [
        ("whole", [raw_bytes]),
        ("1B", [bytes([b]) for b in raw_bytes]),
        ("7B", [raw_bytes[i : i + 7] for i in range(0, len(raw_bytes), 7)]),
    ]
    for seed in range(50):
        variants.append(
            (f"rand_{seed}", _generate_random_slices(raw_bytes, 5 + (seed % 20), seed=seed))
        )
    return variants


def test_l514369_single_quote_escape_chunk_invariance() -> None:
    """L514369: одиночный \\' в JSON-строке чинится, а валидный \\\\' сохраняется."""
    payload = (
        r'''<tool_call>{"name":"bash","arguments":{"command":"echo \'привет\' && printf \\'ok\\'"}}</tool_call>'''
    ).encode("utf-8")
    baseline_calls: list[dict[str, Any]] | None = None
    for label, chunks in _all_split_variants(payload):
        err: LiveParserError | None = None
        calls: list[dict[str, Any]] = []
        try:
            calls, text, _reasoning, _norm = _run_normalizer_chunks(chunks)
        except LiveParserError as exc:
            err = exc
            text = ""
        assert err is None, f"L514369 defect on {label}: {err}"
        assert text == ""
        assert len(calls) == 1
        assert calls[0]["name"] == "bash"
        assert calls[0]["arguments"]["command"] == r"echo 'привет' && printf \'ok\'"
        if baseline_calls is None:
            baseline_calls = calls
        else:
            assert calls == baseline_calls


def _assert_4f43dcea_variant(label: str, chunks: list[bytes]) -> list[dict[str, Any]]:
    err: LiveParserError | None = None
    calls: list[dict[str, Any]] = []
    norm: StreamNormalizer | None = None
    try:
        calls, text, _reasoning, norm = _run_normalizer_chunks(chunks, cutoff_enabled=True)
    except LiveParserError as exc:
        err, text = exc, ""
    assert err is None, f"4f43dcea defect on {label}: {err}"
    assert text == "" and len(calls) == 7
    if norm is not None and hasattr(norm, "post_call_suppressed"):
        assert getattr(norm, "post_call_suppressed") is True
    return calls


def test_4f43dcea_orphan_tool_close_after_seven_calls_chunk_invariance() -> None:
    """4f43dcea: 7 валидных вызовов + orphan </tool_call> + '<' + повтор отсекаются чисто."""
    seven_calls = "".join(
        f'<tool_call>{{"name":"bash","arguments":{{"command":"echo шаг_{i}"}}}}</tool_call>\n'
        for i in range(7)
    )
    orphan_marker = "</tool_call><tool_c"
    tail = f'{orphan_marker}all>{{"name":"bash","arguments":{{"command":"echo repeat"}}}}</tool_call><'
    payload_str = seven_calls + tail
    raw_bytes = payload_str.encode("utf-8")
    variants = _all_split_variants(raw_bytes)
    marker_pos = payload_str.index(orphan_marker)
    for offset in range(len(orphan_marker) + 1):
        cut = len(payload_str[: marker_pos + offset].encode("utf-8"))
        variants.append((f"marker_{offset}", [raw_bytes[:cut], raw_bytes[cut:]]))

    baseline_calls: list[dict[str, Any]] | None = None
    for label, chunks in variants:
        calls = _assert_4f43dcea_variant(label, chunks)
        if baseline_calls is None:
            baseline_calls = calls
        else:
            assert calls == baseline_calls


def test_orphan_tool_close_with_zero_calls_fails_closed() -> None:
    """Orphan </tool_call> при calls == 0 обязан падать fail-closed даже с cutoff_enabled=True."""
    raw_bytes = "текст перед закрытием </tool_call> хвост".encode("utf-8")
    with pytest.raises(LiveParserError, match="unexpected service tag: tool_call"):
        _ = _run_normalizer_chunks([raw_bytes], cutoff_enabled=True)
