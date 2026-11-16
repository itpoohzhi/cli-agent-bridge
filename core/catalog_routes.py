"""Чистая детерминированная компиляция маршрутов по входным DTO."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, TypedDict, cast

ROUTING_ALGORITHM = "weighted-sha256-v1"
DEFAULT_ROUTE_WEIGHT = 100
MAX_ROUTE_WEIGHT = 10_000


class RouteRecord(TypedDict):
    """Публичная запись маршрута без значений учётных данных."""

    route_id: str
    backend: str
    weight: int
    priority: int


class RoutingDocument(TypedDict):
    """Закрытая routing metadata одной канонической модели."""

    algorithm: str
    enabled: bool
    catalog_hash: str
    legacy_backend: str
    disabled_backend: str
    routes: list[RouteRecord]


@dataclass(frozen=True, slots=True)
class RoutingConfig:
    """Отсутствующий вес сохраняет семантику старого манифеста."""

    weight: int | None = None

    def __post_init__(self) -> None:
        if self.weight is not None:
            _ = validate_weight(self.weight)

    @property
    def effective_weight(self) -> int:
        """Возвращает протокольный fallback, сохраняя явный ноль."""
        return DEFAULT_ROUTE_WEIGHT if self.weight is None else self.weight


def validate_weight(value: object) -> int:
    """Принимает только целое 0..10000, не bool, float или строку."""
    if type(value) is not int or not 0 <= value <= MAX_ROUTE_WEIGHT:
        raise ValueError("routing_weight_invalid")
    return value


def _identifier(value: object) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError("routing_identifier_invalid")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("routing_identifier_invalid")
    return value


def _priority(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("routing_priority_invalid")
    return value


def parse_route(raw: object) -> RouteRecord:
    """Проверяет полную запись маршрута без неявного приведения типов."""
    if not isinstance(raw, Mapping) or set(cast(Mapping[object, object], raw)) != set(
        RouteRecord.__annotations__
    ):
        raise ValueError("routing_route_invalid")
    return RouteRecord(
        route_id=_identifier(raw["route_id"]),
        backend=_identifier(raw["backend"]),
        weight=validate_weight(raw["weight"]),
        priority=_priority(raw["priority"]),
    )


def parse_routes(raw: object) -> list[RouteRecord]:
    """Отклоняет весь набор при дубликате route_id либо backend."""
    if not isinstance(raw, (list, tuple)):
        raise ValueError("routing_routes_invalid")
    routes: list[RouteRecord] = []
    route_ids: set[str] = set()
    backends: set[str] = set()
    for item in cast(Sequence[object], raw):
        route = parse_route(item)
        if route["route_id"] in route_ids or route["backend"] in backends:
            raise ValueError("routing_route_duplicate")
        route_ids.add(route["route_id"])
        backends.add(route["backend"])
        routes.append(route)
    return sorted(routes, key=route_order_key)


def route_order_key(route: RouteRecord) -> tuple[str, str]:
    """Задаёт канонический порядок независимо от YAML/input order."""
    return route["route_id"], route["backend"]


def route_owner_key(route: RouteRecord) -> tuple[int, int, str]:
    """При равных весах выбирает меньшие priority и provider_id."""
    return -route["weight"], route["priority"], route["backend"]


def canonical_routes_bytes(routes: Sequence[RouteRecord]) -> bytes:
    """Канон hash-домена: UTF-8 JSON, без priority, резервов и LF."""
    active = [
        {
            "route_id": route["route_id"],
            "backend": route["backend"],
            "weight": route["weight"],
        }
        for route in sorted(routes, key=route_order_key)
        if route["weight"] > 0
    ]
    return json.dumps(
        active,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def routes_catalog_hash(routes: Sequence[RouteRecord]) -> str:
    """Вычисляет frozen hash объявленных положительных маршрутов."""
    return hashlib.sha256(canonical_routes_bytes(routes)).hexdigest()


class RoutingWeight(Protocol):
    """Минимальный вход веса без зависимости от manifest loader."""

    @property
    def weight(self) -> int | None: ...


class ProviderTransport(Protocol):
    """Компилятору достаточно признака исполняемого bridge-транспорта."""

    @property
    def bridge(self) -> object | None: ...


class RouteProvider(Protocol):
    """Read-only проекция провайдера, без импорта provider_manifest."""

    @property
    def provider_id(self) -> str: ...

    @property
    def enabled(self) -> bool: ...

    @property
    def priority(self) -> int: ...

    @property
    def transport(self) -> ProviderTransport: ...

    @property
    def routing(self) -> RoutingWeight: ...


def provider_routing(provider: RouteProvider) -> RoutingConfig:
    """Поддерживает старый DTO без routing, но не маскирует плохой вес."""
    declared: RoutingWeight = getattr(provider, "routing", RoutingConfig())
    return RoutingConfig(declared.weight)


def provider_route(provider: RouteProvider) -> RouteRecord:
    """Сохраняет backend как идентификатор credential/transport слота.

    Разные слоты одной модели остаются разными backend; секретные значения
    и api_key_env в route metadata и hash не попадают.
    """
    return parse_route(
        {
            "route_id": provider.provider_id,
            "backend": provider.provider_id,
            "weight": provider_routing(provider).effective_weight,
            "priority": provider.priority,
        }
    )


def compile_model_routing(
    providers: Iterable[RouteProvider], legacy_backend: str
) -> RoutingDocument:
    """Компилирует owner и route-set, сохраняя старый owner для kill-switch.

    На входе только провайдеры одной модели. Direct-only и disabled записи
    не исполнимы; дубликаты в исполняемом наборе считаются ошибкой входа.
    """
    eligible = tuple(
        provider
        for provider in providers
        if provider.enabled and provider.transport.bridge is not None
    )
    routes = parse_routes([provider_route(provider) for provider in eligible])
    if not routes:
        raise ValueError("routing_routes_empty")
    owner = min(routes, key=route_owner_key)["backend"]
    backends = {route["backend"] for route in routes}
    disabled_backend = legacy_backend if legacy_backend in backends else owner
    return RoutingDocument(
        algorithm=ROUTING_ALGORITHM,
        enabled=any(
            provider_routing(provider).weight is not None for provider in eligible
        ),
        catalog_hash=routes_catalog_hash(routes),
        legacy_backend=owner,
        disabled_backend=disabled_backend,
        routes=routes,
    )
