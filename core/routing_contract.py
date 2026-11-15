"""Чистые контракты маршрутов и канонический формат weighted-sha256-v1."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
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


@dataclass(frozen=True, slots=True)
class RouteSpec:
    """Неизменяемый маршрут с собственными параметрами и ссылкой на credential."""

    route_id: str
    backend: str
    weight: int
    priority: int
    enabled: bool = True
    upstream_model: str | None = None
    efforts: tuple[str, ...] = ()
    default_effort: str | None = None
    context_window: int | None = None
    max_tokens: int | None = None
    input: tuple[str, ...] = ()
    params: Mapping[str, object] = field(default_factory=FrozenMap)
    credential_ref: str | None = None

    def __post_init__(self) -> None:
        _ = required_text(self.route_id)
        _ = required_text(self.backend)
        _ = validate_weight(self.weight)
        _ = _integer(self.priority)
        if type(self.enabled) is not bool:
            raise ValueError("routing_enabled_invalid")
        for value in (self.upstream_model, self.default_effort, self.credential_ref):
            if value is not None:
                _ = required_text(value)
        object.__setattr__(self, "efforts", _texts(self.efforts))
        object.__setattr__(self, "input", _texts(self.input))
        self._validate_overlay()

    def _validate_overlay(self) -> None:
        if self.default_effort is not None and self.default_effort not in self.efforts:
            raise ValueError("routing_default_effort_invalid")
        _ = _optional_limit(self.context_window)
        _ = _optional_limit(self.max_tokens)
        if not isinstance(cast(object, self.params), Mapping):
            raise ValueError("routing_params_invalid")
        object.__setattr__(self, "params", freeze_value(self.params))

    @classmethod
    def from_document(cls, value: Mapping[str, object]) -> RouteSpec:
        """Читает DTO без потери неизвестных полей и без приведения типов."""
        if not isinstance(cast(object, value), Mapping):
            raise ValueError("routing_route_invalid")
        fields = cls.__dataclass_fields__
        if set(value) - fields.keys():
            raise ValueError("routing_route_unknown_key")
        try:
            return cls(
                route_id=required_text(value["route_id"]),
                backend=required_text(value["backend"]),
                weight=validate_weight(value["weight"]),
                priority=_integer(value["priority"]),
                enabled=cast(bool, value.get("enabled", True)),
                upstream_model=cast(str | None, value.get("upstream_model")),
                efforts=_texts(value.get("efforts", ())),
                default_effort=cast(str | None, value.get("default_effort")),
                context_window=_optional_limit(value.get("context_window")),
                max_tokens=_optional_limit(value.get("max_tokens")),
                input=_texts(value.get("input", ())),
                params=cast(Mapping[str, object], value.get("params", FrozenMap())),
                credential_ref=cast(str | None, value.get("credential_ref")),
            )
        except (KeyError, TypeError) as error:
            raise ValueError("routing_route_invalid") from error


def normalize_routes(
    routes: Iterable[RouteSpec | Mapping[str, object]],
) -> tuple[RouteSpec, ...]:
    """Создаёт единый снимок; дубликат не превращается в скрытый повтор backend."""
    result = tuple(
        route if isinstance(route, RouteSpec) else RouteSpec.from_document(route)
        for route in routes
    )
    if len({route.route_id for route in result}) != len(result):
        raise ValueError("routing_duplicate_route")
    if len({route.backend for route in result}) != len(result):
        raise ValueError("routing_duplicate_backend")
    return tuple(sorted(result, key=lambda route: (route.route_id, route.backend)))


def parse_routes(model: Mapping[str, object]) -> tuple[RouteSpec, ...]:
    """Извлекает все объявленные маршруты; испорченный элемент не пропускается."""
    routing = model.get("routing")
    if routing is None:
        return ()
    if not isinstance(routing, Mapping):
        raise ValueError("routing_invalid")
    raw = cast(Mapping[str, object], routing).get("routes")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        raise ValueError("routing_routes_invalid")
    return normalize_routes(cast(Sequence[RouteSpec | Mapping[str, object]], raw))


def canonical_json(value: object) -> bytes:
    """Канон хеша: UTF-8 JSON, сортировка ключей, без пробелов и завершающего LF."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def routes_catalog_hash(routes: Iterable[RouteSpec | Mapping[str, object]]) -> str:
    """Хеширует только enabled positive routes, без приоритета и параметров."""
    active = [
        {"route_id": route.route_id, "backend": route.backend, "weight": route.weight}
        for route in normalize_routes(routes)
        if route.enabled and route.weight > 0
    ]
    return hashlib.sha256(canonical_json(active)).hexdigest()
