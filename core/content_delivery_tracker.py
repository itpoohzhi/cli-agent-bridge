"""Трекер фактов доставки клиенту (AD-002, BND-002): владелец состояния `_facts`.

Различает keepalive/пустую role-дельту (не доставка) и реальный content/reasoning/tool_calls/
tool_events. Наружу — только frozen `DeliveryFacts`. Один писатель на ход (поток SSE-sink).
"""

from __future__ import annotations

from dataclasses import replace

from core.transport_failure_contracts import DeliveryFacts


def _size(text: str) -> int:
    """Размер текстовой дельты в байтах UTF-8; не-строка и пустая дельта — 0."""
    return len(text.encode("utf-8")) if isinstance(text, str) else 0


def _count(value: int) -> int:
    return value if type(value) is int and value > 0 else 0


class ContentDeliveryTracker:
    """Накопитель фактов доставки одного хода."""

    def __init__(self) -> None:
        self._facts = DeliveryFacts()

    def mark_keepalive(self) -> None:
        """Keepalive-комментарий либо пустая role-дельта: считается, но не доставка."""
        self._facts = replace(self._facts, keepalive_count=self._facts.keepalive_count + 1)

    def mark_content(self, text: str) -> None:
        """Непустая content-дельта доставлена."""
        size = _size(text)
        if size:
            self._facts = replace(self._facts, content_bytes=self._facts.content_bytes + size)

    def mark_reasoning(self, text: str) -> None:
        """Непустая reasoning-дельта доставлена."""
        size = _size(text)
        if size:
            self._facts = replace(self._facts, reasoning_bytes=self._facts.reasoning_bytes + size)

    def mark_tool_calls(self, count: int = 1) -> None:
        """Доставлены `count` структурированных tool_calls."""
        extra = _count(count)
        if extra:
            self._facts = replace(self._facts, tool_calls=self._facts.tool_calls + extra)

    def mark_tool_event(self, count: int = 1) -> None:
        """Зафиксированы `count` событий исполнения инструмента."""
        extra = _count(count)
        if extra:
            self._facts = replace(self._facts, tool_events=self._facts.tool_events + extra)

    def snapshot(self) -> DeliveryFacts:
        """Неизменяемый снимок фактов (frozen-копия, не внутреннее состояние)."""
        return replace(self._facts)
