"""Закрытые декларации routing и чистая проверка каталожных маршрутов."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from typing import cast

# Приватные имена реэкспортируются под прежними именами ради совместимости.
from core.catalog_routes import (
    DEFAULT_ROUTE_WEIGHT as DEFAULT_ROUTE_WEIGHT,
    MAX_ROUTE_WEIGHT as MAX_ROUTE_WEIGHT,
    ROUTING_ALGORITHM as ROUTING_ALGORITHM,
    RouteRecord as RouteRecord,
    RoutingConfig as RoutingConfig,
    RoutingDocument as RoutingDocument,
    _identifier as _identifier,  # pyright: ignore[reportPrivateUsage]
    _priority as _priority,  # pyright: ignore[reportPrivateUsage]
    canonical_routes_bytes as canonical_routes_bytes,
    parse_route as parse_route,
    parse_routes as parse_routes,
    route_order_key as route_order_key,
    route_owner_key as route_owner_key,
    routes_catalog_hash as routes_catalog_hash,
    validate_weight as validate_weight,
)


def parse_routing(raw: object) -> RoutingConfig:
    """Отличает отсутствие routing от некорректной явной декларации."""
    if raw is None:
        return RoutingConfig()
    if not isinstance(raw, Mapping) or set(cast(Mapping[object, object], raw)) != {
        "weight"
    }:
        raise ValueError("routing_invalid")
    return RoutingConfig(validate_weight(raw["weight"]))


def _routing_header(raw: object) -> Mapping[str, object]:
    if not isinstance(raw, Mapping) or set(cast(Mapping[object, object], raw)) != set(
        RoutingDocument.__annotations__
    ):
        raise ValueError("routing_invalid")
    if raw["algorithm"] != ROUTING_ALGORITHM or type(raw["enabled"]) is not bool:
        raise ValueError("routing_algorithm_or_enabled_invalid")
    return cast(Mapping[str, object], raw)


def _validate_owners(raw: Mapping[str, object], routes: Sequence[RouteRecord]) -> None:
    backends = {route["backend"] for route in routes}
    for field in ("legacy_backend", "disabled_backend"):
        if _identifier(raw[field]) not in backends:
            raise ValueError("routing_owner_unknown")
    if raw["legacy_backend"] != min(routes, key=route_owner_key)["backend"]:
        raise ValueError("routing_owner_invalid")


def validate_model_routing(raw: object, backends: Collection[str]) -> RoutingDocument:
    """Проверяет все маршруты до health-фильтров; плохие записи не отбрасывает.

    Вызывающий слой переводит ValueError в FleetViolation для всей модели.
    Состояние backend не меняет frozen catalog_hash и legacy_backend.
    """
    doc = _routing_header(raw)
    routes = parse_routes(doc["routes"])
    if not routes:
        raise ValueError("routing_routes_empty")
    if any(route["backend"] not in backends for route in routes):
        raise ValueError("routing_backend_unknown")
    _validate_owners(doc, routes)
    digest = routes_catalog_hash(routes)
    if doc["catalog_hash"] != digest:
        raise ValueError("routing_catalog_hash_invalid")
    return RoutingDocument(
        algorithm=ROUTING_ALGORITHM,
        enabled=doc["enabled"] is True,
        catalog_hash=digest,
        legacy_backend=_identifier(doc["legacy_backend"]),
        disabled_backend=_identifier(doc["disabled_backend"]),
        routes=routes,
    )
