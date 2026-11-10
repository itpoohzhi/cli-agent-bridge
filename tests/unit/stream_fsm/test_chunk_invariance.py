"""F-FSM-I2: Chunk-Boundary Invariance test suite.

Verifies that any standard SSE/NDJSON stream containing:
- reasoning_content
- tool_calls
- Cyrillic UTF-8 multibyte characters
- terminal done frame
produces bit-for-bit identical stream events whether fed as:
1 chunk, 1-byte chunks, 7-byte chunks, or 50 random split cuts.
"""

import random
import time

from core.stream_fsm.machine import StreamMachine
from core.stream_fsm.types import EmitChunk

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
