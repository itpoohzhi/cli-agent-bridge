"""Реконсиляция terminal-текста resident stdio-потока (волна W0-B, AD-004).

Чистый Zero-I/O модуль (M-MOD-I3): без `os`, `pathlib`, `subprocess`,
`socket`, `logging` и любого другого I/O. Единственный владелец состояния
накопления — экземпляр `TerminalTextReconciler` (M-MOD-I4).

Протоколы из allowlist (например `agy-stream-json`) шлют progressive-дельты
текста, а затем terminal-кадр с полным ответом. Реконсилятор убирает дубль:
если terminal повторяет накопленный текст — его `text` обнуляется; если
продолжает его — остаётся только хвост. Поля `reasoning`, `tool_calls`,
`usage`, `error`, `is_terminal` никогда не изменяются. При переполнении
бюджета накопления модуль переходит в fail-open passthrough.
"""

from __future__ import annotations

from dataclasses import replace

from core.stdio_resident.protocol_driver import DecodedChunk

# Протоколы, для которых разрешена реконсиляция terminal-текста.
RECONCILE_PROTOCOLS: frozenset[str] = frozenset({"agy-stream-json"})

# Бюджет накопления progressive-текста (байты UTF-8), по умолчанию 4 MiB.
DEFAULT_MAX_ACCUM_BYTES: int = 4 * 1024 * 1024


def should_reconcile_protocol(protocol: str | None) -> bool:
    """Входит ли протокол в allowlist реконсиляции terminal-текста."""
    return protocol in RECONCILE_PROTOCOLS


class TerminalTextReconciler:
    """Убирает дубль progressive-текста из terminal-кадра одного turn.

    Экземпляр — единственный владелец состояния накопления (M-MOD-I4):
    список фрагментов, счётчик байтов UTF-8 и флаг переполнения. Решение
    о включении и выбор бюджета принимает вызывающий слой через `__init__`.
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        max_accum_bytes: int = DEFAULT_MAX_ACCUM_BYTES,
    ) -> None:
        self._enabled: bool = enabled
        self._max_accum_bytes: int = max_accum_bytes
        self._parts: list[str] = []
        self._accum_bytes: int = 0
        self._overflowed: bool = False

    def apply(self, chunk: DecodedChunk) -> DecodedChunk:
        """Вернуть кадр с реконсилированным terminal-текстом (или как есть).

        Progressive-кадры накапливаются и возвращаются без изменений.
        Terminal-кадр с текстом, равным накопленному, теряет `text`;
        продолжающий накопленный — оставляет только хвост; расходящийся
        или пустой — возвращается без изменений. При выключенном режиме
        или переполнении бюджета любой кадр проходит нетронутым (fail-open).
        """
        if not self._enabled or self._overflowed:
            return chunk
        if not chunk.is_terminal:
            return self._accumulate(chunk)
        return self._reconcile_terminal(chunk)

    def _accumulate(self, chunk: DecodedChunk) -> DecodedChunk:
        """Накопить progressive-текст; при превышении бюджета — fail-open."""
        if chunk.text:
            size = len(chunk.text.encode("utf-8"))
            if self._accum_bytes + size > self._max_accum_bytes:
                self._overflowed = True
                self._parts.clear()
                self._accum_bytes = 0
            else:
                self._parts.append(chunk.text)
                self._accum_bytes += size
        return chunk

    def _reconcile_terminal(self, chunk: DecodedChunk) -> DecodedChunk:
        """Снять дубль/префикс с terminal-текста, не трогая прочие поля."""
        if not chunk.text or not self._parts:
            return chunk
        accum = "".join(self._parts)
        if chunk.text == accum:
            return replace(chunk, text="")
        if chunk.text.startswith(accum):
            return replace(chunk, text=chunk.text[len(accum) :])
        return chunk
