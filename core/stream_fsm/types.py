"""Типы состояний, событий и эффектов потокового автомата (ADR-0020)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Union


class StreamState(Enum):
    """Иммутабельные состояния потокового разбора."""

    IDLE = auto()
    STREAMING = auto()
    REASONING = auto()
    TEXT = auto()
    TOOL_CALL_ASSEMBLING = auto()
    TOOL_CALL_READY = auto()
    COMPLETED = auto()
    CLOSED = auto()


@dataclass(frozen=True)
class StreamEvent:
    """Базовый класс событий входящего потока."""

    epoch: int = 0


@dataclass(frozen=True)
class ChunkReceived(StreamEvent):
    """Событие поступления очередного фрагмента данных от модели."""

    chunk: Union[str, bytes] = ""


@dataclass(frozen=True)
class KeepAliveTick(StreamEvent):
    """Периодический тик поддержания активности соединения."""

    pass


@dataclass(frozen=True)
class CancelRequested(StreamEvent):
    """Запрос отмены потока со стороны клиента."""

    reason: str = ""
    pgid: int = 0


@dataclass(frozen=True)
class UpstreamEOF(StreamEvent):
    """Сигнал штатного завершения входного потока (EOF / [DONE])."""

    pass


@dataclass(frozen=True)
class ProtocolError(StreamEvent):
    """Ошибка разбора протокола или превышение лимитов."""

    message: str = ""
    code: str = "PROTOCOL_ERROR"


@dataclass(frozen=True)
class StreamEffect:
    """Базовый класс сайд-эффектов, возвращаемых автоматом."""

    pass


@dataclass(frozen=True)
class EmitSSE(StreamEffect):
    """Эффект отправки готового SSE-фрейма клиенту."""

    event: str
    data: str


@dataclass(frozen=True)
class EmitChunk(StreamEffect):
    """Эффект передачи полезного текстового чанка."""

    text: str
    is_reasoning: bool = False


@dataclass(frozen=True)
class EmitToolCall(StreamEffect):
    """Эффект передачи собранного вызова инструмента."""

    index: int
    call_id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class TriggerKillpg(StreamEffect):
    """Эффект прерывания зависшего процесса или отмененной сессии."""

    pgid: int
    epoch: int


@dataclass(frozen=True)
class RecordMetric(StreamEffect):
    """Эффект записи метрики производительности или счетчика."""

    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
