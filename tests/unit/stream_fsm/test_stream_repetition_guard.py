"""Unit-тесты для StreamRepetitionGuard (Wave 1)."""

import math
import tracemalloc
import pytest
from core.stream_fsm.repetition_guard import StreamRepetitionGuard


def test_repetition_guard_split_boundary():
    """Проверка детекции зацикливания при нарезке токенов по 1 байту."""
    guard = StreamRepetitionGuard(max_repeats=3, max_token_len=16)
    pattern = "loop_token " * 5
    detected = False
    for ch in pattern:
        _, loop = guard.feed(ch)
        if loop:
            detected = True
            break
    assert detected, "RepetitionGuard обязан поймать цикл даже при нарезке по 1 символу"


def test_repetition_guard_multi_token_cycle():
    """Проверка детекции периодических циклов из нескольких токенов (например 'ping pong ')."""
    guard = StreamRepetitionGuard(max_repeats=3, max_token_len=16)
    stream = "alpha beta " + ("ping pong " * 4)
    detected = False
    for word in stream.split(" "):
        if word:
            _, loop = guard.feed(word + " ")
            if loop:
                detected = True
                break
    assert detected, "Цикл из двух токенов должен быть обнаружен"


def test_repetition_guard_code_fence_immunity():
    """Проверка иммунитета к повторам внутри Markdown code fences."""
    guard = StreamRepetitionGuard(max_repeats=3, max_token_len=16)
    code_block = "```python\nfor i in range(10):\n    print('test')\n    print('test')\n    print('test')\n    print('test')\n```\n"
    for line in code_block.splitlines(keepends=True):
        _, loop = guard.feed(line)
        assert not loop, "Повторы внутри code fences не должны триггерить Guard"
    assert not guard.detected


def test_repetition_guard_separator_immunity():
    """Проверка иммунитета к Markdown-разделителям (---, ***, ===, , )."""
    guard = StreamRepetitionGuard(max_repeats=3, max_token_len=16)
    separators = "--- --- --- --- --- --- , , , , , , | | | | | "
    for ch in separators:
        _, loop = guard.feed(ch)
        assert not loop, "Разделители не должны вызывать ложных срабатываний"
    assert not guard.detected


def test_repetition_guard_identifier_with_underscore():
    """Тест сохранения символа _ внутри токенов-идентификаторов."""
    guard = StreamRepetitionGuard(max_repeats=4)
    _, loop = guard.feed(" _placeholder" * 4)
    assert loop is True, "Идентификаторы с подчеркиванием должны корректно распознаваться"
    assert guard.detected is True


def test_h_cpu_i6_memory_bound():
    """H-CPU-I6: Оракул приемника на K = 1024 чанках по 1024 Б (B = 1 048 576 Б)."""
    guard = StreamRepetitionGuard(max_repeats=5, max_token_len=32, capacity=1024)
    chunk_1k = "x" * 1000 + " \n"
    K = 1024

    tracemalloc.start()
    base_current, _ = tracemalloc.get_traced_memory()

    for _ in range(K):
        guard.feed(chunk_1k)

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    delta_mem = peak - base_current
    # Потребление памяти кольцевого буфера должно быть O(1) и не превышать 256 КиБ
    assert delta_mem < 262144, f"Память не O(1): скачок {delta_mem} байт"
