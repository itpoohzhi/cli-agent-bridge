"""Чистые контракты маршрутов и канонический формат weighted-sha256-v1."""

from __future__ import annotations

import math
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import cast, override

ROUTING_ALGORITHM = "weighted-sha256-v1"
MAX_ROUTE_WEIGHT = 10_000


class FleetViolation(Exception):
    """Структурный отказ каталога; совместим с публичным конструктором загрузчика."""

    def __init__(self, reason: str, model: str = "-") -> None:
        super().__init__(reason)
        self.reason: str = reason
        self.model: str = model or "-"


class PreSendTransientError(ConnectionError):
    """Отказ транспорта, сам по себе не разрешающий повтор исполнения запроса."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_headers: tuple[tuple[str, str], ...] = (),
        response_body: bytes | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code: int | None = status_code
        self.response_headers: tuple[tuple[str, str], ...] = response_headers
        self.response_body: bytes | None = response_body


@dataclass(frozen=True, slots=True)
class FrozenMap(Mapping[str, object]):
    """Снимок JSON-объекта без изменяемых вложенных значений."""

    entries: tuple[tuple[str, object], ...] = ()

    def __post_init__(self) -> None:
        entries = tuple((key, freeze_value(value)) for key, value in self.entries)
        if any(not isinstance(cast(object, key), str) for key, _ in entries):
            raise ValueError("routing_params_key_invalid")
        if len({key for key, _ in entries}) != len(entries):
            raise ValueError("routing_params_duplicate_key")
        object.__setattr__(
            self, "entries", tuple(sorted(entries, key=lambda entry: entry[0]))
        )

    @override
    def __getitem__(self, key: str) -> object:
        for name, value in self.entries:
            if name == key:
                return value
        raise KeyError(key)

    @override
    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self.entries)

    @override
    def __len__(self) -> int:
        return len(self.entries)


def freeze_value(value: object) -> object:
    """Копирует JSON-контейнеры в рекурсивно неизменяемое представление."""
    if isinstance(value, FrozenMap):
        return value
    if isinstance(value, Mapping):
        return FrozenMap(tuple(cast(Mapping[str, object], value).items()))
    if isinstance(value, (list, tuple)):
        return tuple(freeze_value(item) for item in cast(Sequence[object], value))
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ValueError("routing_params_invalid")


def required_text(value: object) -> str:
    """Не преобразует ошибочные типы и не нормализует идентичность молча."""
    if not isinstance(value, str) or not value:
        raise ValueError("routing_text_invalid")
    return value


def validate_weight(value: object) -> int:
    """Проверяет протокольный диапазон весов, отдельно исключая bool."""
    if type(value) is not int or not 0 <= value <= MAX_ROUTE_WEIGHT:
        raise ValueError("routing_weight_invalid")
    return value


def _integer(value: object) -> int:
    if type(value) is not int:
        raise ValueError("routing_integer_invalid")
    return value


def _optional_limit(value: object) -> int | None:
    if value is None:
        return None
    result = _integer(value)
    if result <= 0:
        raise ValueError("routing_limit_invalid")
    return result


def _texts(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("routing_sequence_invalid")
    return tuple(required_text(item) for item in cast(Sequence[object], value))

__all__ = ('FleetViolation', 'PreSendTransientError', 'FrozenMap', 'freeze_value', 'required_text', 'validate_weight', '_integer', '_optional_limit', '_texts')
