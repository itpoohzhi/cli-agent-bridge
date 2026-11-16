"""Чистая ленивая перестановка маршрутов; seed и eligibility задаёт вызывающий."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Iterator, Mapping
from typing import cast, override

import core.routing_contract as _contract

_HASH_SPACE = 1 << 256
_UINT64_SPACE = 1 << 64
_COUNTER_BYTES = 8


def _uint64(value: int) -> bytes:
    """Отказывает до переполнения протокольного счётчика."""
    if not 0 <= value < _UINT64_SPACE:
        raise ValueError("routing_counter_overflow")
    return value.to_bytes(_COUNTER_BYTES, "big")


def _ticket(domain: bytes, round_no: int, total: int) -> int:
    """Выбирает unbiased ticket через SHA-256 rejection sampling."""
    if not 0 < total <= _HASH_SPACE:
        raise ValueError("routing_total_invalid")
    limit = _HASH_SPACE - _HASH_SPACE % total
    material = domain + _uint64(round_no)
    counter = 0
    while True:
        digest = hashlib.sha256(material + _uint64(counter)).digest()
        value = int.from_bytes(digest, "big")
        if value < limit:
            return value % total
        counter += 1


def _draw_index(routes: list[_contract.RouteSpec], domain: bytes, round_no: int) -> int:
    ticket = _ticket(domain, round_no, sum(route.weight for route in routes))
    for index, route in enumerate(routes):
        ticket -= route.weight
        if ticket < 0:
            return index
    raise ValueError("routing_ticket_out_of_range")


class RouteDraw(Iterator[str]):
    """Владеет остатком одной жеребьёвки; следующий SHA считается лишь по next."""

    def __init__(self, routes: Iterable[_contract.RouteSpec], domain: bytes) -> None:
        snapshot = _contract.normalize_routes(routes)
        self._remaining: list[_contract.RouteSpec] = [
            route for route in snapshot if route.enabled and route.weight > 0
        ]
        reserves = sorted(
            (route for route in snapshot if route.enabled and route.weight == 0),
            key=lambda route: (route.priority, route.route_id, route.backend),
        )
        self._reserves: Iterator[str] = iter(tuple(route.backend for route in reserves))
        self._domain: bytes = domain
        self._round_no: int = 0

    @override
    def __iter__(self) -> RouteDraw:
        return self

    @override
    def __next__(self) -> str:
        if not self._remaining:
            return next(self._reserves)
        index = _draw_index(self._remaining, self._domain, self._round_no)
        winner = self._remaining.pop(index)
        self._round_no += 1
        return winner.backend


def _disabled_order(
    model: Mapping[str, object], routing: Mapping[str, object]
) -> Iterator[str]:
    backend = routing.get(
        "disabled_backend", routing.get("legacy_backend", model.get("backend"))
    )
    if backend is None or backend == "":
        return iter(())
    return iter((_contract.required_text(backend),))


def route_order(
    model_id: str,
    model: Mapping[str, object],
    seed: str,
    subagent_id: str | None = None,
    eligible: Iterable[_contract.RouteSpec] | None = None,
) -> Iterator[str]:
    """Возвращает weighted draw, затем резервы, не меняя frozen catalog_hash.

    Schema/hash проверяются при загрузке каталога, eligibility снимок формируется
    до вызова. Здесь нет env, RNG, health I/O или разрешения повторять исполнение.
    """
    routing = model.get("routing")
    if routing is None:
        return _disabled_order(model, {})
    if not isinstance(routing, Mapping):
        raise ValueError("routing_invalid")
    routing = cast(Mapping[str, object], routing)
    if routing.get("enabled") is not True:
        return _disabled_order(model, routing)
    if routing.get("algorithm") != _contract.ROUTING_ALGORITHM:
        raise ValueError("routing_algorithm_invalid")
    domain = _contract.canonical_json(
        [
            _contract.ROUTING_ALGORITHM,
            _contract.required_text(model_id),
            subagent_id or "",
            _contract.required_text(routing.get("catalog_hash")),
            _contract.required_text(seed),
        ]
    )
    routes = _contract.parse_routes(model) if eligible is None else eligible
    return RouteDraw(routes, domain)
