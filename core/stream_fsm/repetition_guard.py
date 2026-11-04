"""Кольцевой адаптер детекции зацикливания за O(1) памяти (ADR-0020, H-CPU-I6)."""

from __future__ import annotations

import unicodedata
from collections import deque
from typing import Any, Tuple

DEFAULT_MAX_REPEATS = 4
DEFAULT_MAX_TOKEN_LEN = 32
MAX_RING_CAPACITY = 1024


def _is_separator(token: str) -> bool:
    """Проверяет, является ли токен Markdown-разделителем или пунктуацией."""
    stripped = token.strip()
    if not stripped:
        return True
    if all(ch in "-*=_#|~`" for ch in stripped):
        return True
    return all(unicodedata.category(ch).startswith("P") for ch in stripped)


class StreamRepetitionGuard:
    """Детерминированный детектор циклов за O(1) аллокаций памяти на чанк."""

    def __init__(
        self,
        max_repeats: int = DEFAULT_MAX_REPEATS,
        max_token_len: int = DEFAULT_MAX_TOKEN_LEN,
        enabled: bool = True,
        capacity: int = MAX_RING_CAPACITY,
    ) -> None:
        self.max_repeats = max(2, int(max_repeats))
        self.max_token_len = max(1, int(max_token_len))
        self.enabled = bool(enabled)
        self.capacity = max(128, int(capacity))

        self._token_ring: deque[int] = deque(maxlen=self.capacity)
        self._tail_chars: list[str] = []
        self._detected = False
        self._in_code_fence = False

    @property
    def detected(self) -> bool:
        return self._detected

    @property
    def triggered(self) -> bool:
        return self._detected

    def reset(self) -> None:
        """Сброс состояния детектора."""
        self._token_ring.clear()
        self._tail_chars.clear()
        self._detected = False
        self._in_code_fence = False

    def _hash_token(self, token: str) -> int:
        return hash(token)

    def _check_cycle(self) -> bool:
        """Проверяет повторяющиеся периоды k в кольцевом буфере за O(1)."""
        ring_len = len(self._token_ring)
        if ring_len < self.max_repeats:
            return False

        max_period = min(32, ring_len // self.max_repeats)
        for period in range(1, max_period + 1):
            pattern_matched = True
            for rep in range(1, self.max_repeats):
                base_idx = -1
                cmp_idx = -1 - (rep * period)
                for offset in range(period):
                    if self._token_ring[base_idx - offset] != self._token_ring[cmp_idx - offset]:
                        pattern_matched = False
                        break
                if not pattern_matched:
                    break
            if pattern_matched:
                return True
        return False

    def _drain_tail(self) -> bool:
        """Сбрасывает накопленный токен в кольцевой буфер и проверяет зацикливание."""
        if not self._tail_chars:
            return False
        tok = "".join(self._tail_chars)
        self._tail_chars.clear()
        if 1 <= len(tok) <= self.max_token_len and not _is_separator(tok):
            self._token_ring.append(self._hash_token(tok))
            return self._check_cycle()
        return False

    def _check_trailing_tail(self) -> bool:
        """Проверяет, не замыкает ли текущий незавершенный токен цикл повторений."""
        if not self._tail_chars:
            return False
        tok = "".join(self._tail_chars)
        if 1 <= len(tok) <= self.max_token_len and not _is_separator(tok):
            self._token_ring.append(self._hash_token(tok))
            loop = self._check_cycle()
            self._token_ring.pop()
            return loop
        return False

    def _check_fence(self, chunk: str) -> bool:
        """Отслеживает состояние Markdown code fence (```)."""
        if "```" in chunk:
            self._in_code_fence = not self._in_code_fence
        return self._in_code_fence

    def _process_chars(self, chunk: str) -> bool:
        """Посимвольно токенизирует чанк и возвращает True при обнаружении зацикливания."""
        for ch in chunk:
            if ch.isspace() or (unicodedata.category(ch).startswith("P") and ch != "_"):
                if self._drain_tail():
                    return True
            elif len(self._tail_chars) < self.max_token_len + 8:
                self._tail_chars.append(ch)
        return self._check_trailing_tail()

    def feed(self, chunk: str) -> Tuple[str, bool]:
        """Принимает очередной чанк текста; возвращает (chunk, loop_detected)."""
        if not self.enabled or not chunk or self._detected:
            return chunk, self._detected

        if self._check_fence(chunk):
            return chunk, False

        if self._process_chars(chunk):
            self._detected = True
            return chunk, True

        return chunk, self._detected
