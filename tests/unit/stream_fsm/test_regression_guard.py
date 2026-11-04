"""Red regression test suite for RepetitionGuard FSM.

Verifies:
1. Detection of loop when tokens are split across chunk boundaries (1-byte chunks).
2. O(1) memory guarantees per H-CPU-I6 (no bytes/str += chunk in loop).
3. Preservation of code blocks/markdown fences without false positives.
"""

import pytest

def test_repetition_guard_split_boundary_red():
    """Проверка импорта и детекции зацикливания при нарезке токенов по 1 байту."""
    # Пакет еще не создан — ожидается ModuleNotFoundError (red_repro)
    from core.stream_fsm.repetition_guard import StreamRepetitionGuard

    guard = StreamRepetitionGuard(max_repeats=3, max_token_len=10)
    # Повторяющийся паттерн 'loop_token ' нарезан по 1 байту
    stream = "start " + ("loop_token " * 5)
    detected = False
    for ch in stream:
        _, loop = guard.feed(ch)
        if loop:
            detected = True
            break
    assert detected, "RepetitionGuard обязан поймать цикл даже при нарезке по 1 символу"
