"""Выделенная логика выбора Zero-Canon маршрута (compact routing helper)."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

__all__ = ("backend_configs", "select_zero_canon_route", "apply_filtered_routes")


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_drained(item: Mapping[str, Any]) -> bool:
    return "weight" in item and _numeric(item.get("weight")) and item["weight"] <= 0


def backend_configs(host: Any) -> dict[str, dict[str, Any]]:
    """Собирает конфиги адаптеров из host.BACKENDS.adapters (Mapping или callable)."""
    backends = getattr(host, "BACKENDS", None)
    adapters = getattr(backends, "adapters", None)
    items: list[tuple[str, Any]] = []
    if isinstance(adapters, Mapping):
        items = list(adapters.items())
    elif callable(adapters):
        for adapter in adapters():
            key = getattr(adapter, "id", None) or getattr(adapter, "name", None)
            if _nonempty_str(key):
                items.append((key, adapter))
    configs: dict[str, dict[str, Any]] = {}
    for key, adapter in items:
        raw = getattr(adapter, "config", None)
        cfg = dict(raw) if isinstance(raw, Mapping) else {}
        kind = getattr(adapter, "kind", None)
        if _nonempty_str(kind):
            cfg["kind"] = kind
        configs[key] = cfg
    return configs


def select_zero_canon_route(
    kept: list[Any], *, disabled_backend: str | None = None, routing_enabled: bool = True
) -> str | None:
    """Выбирает backend среди недренированных: disabled при выключенном routing, иначе min(priority)."""
    candidates = [i for i in kept if isinstance(i, Mapping) and _nonempty_str(i.get("backend"))]
    eligible = [i for i in candidates if not _is_drained(i)]
    if not eligible:
        return None
    if not routing_enabled and _nonempty_str(disabled_backend):
        for item in eligible:
            if item.get("backend") == disabled_backend:
                return disabled_backend
    best: Mapping[str, Any] | None = None
    best_priority: float = float("inf")
    for item in eligible:
        raw_p = item.get("priority")
        priority = float(raw_p) if _numeric(raw_p) else float("inf")
        if best is None or priority < best_priority:
            best, best_priority = item, priority
    return best.get("backend") if best is not None else None


def apply_filtered_routes(
    route: Any, routing: Mapping[str, Any], kept: list[Any], *, routing_enabled: bool = True
) -> str | None:
    """Мутирует только route.model; переданный routing и host.FLEET не трогаем."""
    new_routing = copy.deepcopy(dict(routing))
    new_routing["routes"] = copy.deepcopy(kept)
    chosen = select_zero_canon_route(
        kept,
        disabled_backend=new_routing.get("disabled_backend"),
        routing_enabled=routing_enabled,
    )
    if chosen:
        route.model["backend"] = chosen
        new_routing["zero_canon_backend"] = chosen
    else:
        route.model["backend"] = ""
        new_routing["routes"] = []
        new_routing.pop("zero_canon_backend", None)
    route.model["routing"] = new_routing
    return chosen
