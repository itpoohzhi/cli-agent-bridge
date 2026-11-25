"""Изолированная fail-closed фильтрация маршрутов по scope провайдера."""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, Sequence
from typing import Protocol, TypeVar, cast

T = TypeVar("T")
_BodyT = TypeVar("_BodyT")
_WireT = TypeVar("_WireT")
_RouteT = TypeVar("_RouteT", bound="_RouteLike")
_UNSET = object()


class BackendLookup(Protocol):
    """Минимальный контракт реестра бэкендов (AdapterRegistry или Mapping)."""

    def get(self, key: str, /) -> object | None: ...


class _ModelMap(Protocol):
    def get(self, key: str, /) -> object | None: ...

    def __setitem__(self, key: str, value: object, /) -> None: ...


class _RouteLike(Protocol):
    model: _ModelMap

    @property
    def ingress(self) -> object: ...

    @property
    def host(self) -> object: ...

    def reject(self, status: int, kind: str, message: str) -> object: ...


def _adapter_matches(adapter: object, allowed: Collection[str]) -> bool:
    owned_by: object = getattr(adapter, "owned_by", None)
    if isinstance(owned_by, str) and owned_by in allowed:
        return True
    cfg: object = getattr(adapter, "config", None)
    if not isinstance(cfg, Mapping):
        return False
    cfg_map = cast(Mapping[str, object], cfg)
    provider = cfg_map.get("provider")
    owner = cfg_map.get("owned_by")
    return (isinstance(provider, str) and provider in allowed) or (
        isinstance(owner, str) and owner in allowed
    )


def _normalize_allowed(raw: object) -> frozenset[str]:
    if isinstance(raw, str):
        return frozenset((raw,)) if raw else frozenset()
    if isinstance(raw, Collection) and not isinstance(raw, (bytes, bytearray, Mapping)):
        return frozenset(x for x in raw if isinstance(x, str) and x)
    return frozenset()


def backend_matches_provider(
    backend_id: str,
    provider_id: str | None,
    provider_scopes: Mapping[str, Collection[str]],
    backends: BackendLookup | None = None,
) -> bool:
    """Fail-closed проверка принадлежности бэкенда разрешённой области провайдера."""
    if provider_id is None:
        return True
    if not backend_id or provider_id not in provider_scopes:
        return False
    allowed = _normalize_allowed(provider_scopes[provider_id])
    if not allowed:
        return False
    if backend_id in allowed:
        return True
    adapter = backends.get(backend_id) if backends is not None else None
    if adapter is not None:
        return _adapter_matches(adapter, allowed)
    return False


def scope_routes(
    routes: Sequence[T],
    provider_id: str | None,
    provider_scopes: Mapping[str, Collection[str]],
    backends: BackendLookup | None = None,
) -> tuple[T, ...]:
    """Фильтрует маршруты по scope провайдера; неизвестный provider_id -> ()."""
    if provider_id is None:
        return tuple(routes)
    if provider_id not in provider_scopes:
        return ()
    return tuple(
        spec
        for spec in routes
        if backend_matches_provider(
            b if isinstance(b := getattr(spec, "backend", None), str) else "",
            provider_id,
            provider_scopes,
            backends,
        )
    )


def _route_scope_context(
    route: _RouteLike,
) -> tuple[str | None, Mapping[str, Collection[str]], BackendLookup | None]:
    ingress: object = getattr(route, "ingress", None)
    raw_provider: object = getattr(ingress, "provider_id", None)
    provider_id = (
        None
        if raw_provider is None
        else (raw_provider if isinstance(raw_provider, str) else str(raw_provider))
    )
    raw_scopes: object = getattr(route.host, "PROVIDER_SCOPES", None)
    empty_scopes: Mapping[str, Collection[str]] = {}
    scopes: Mapping[str, Collection[str]] = (
        cast(Mapping[str, Collection[str]], raw_scopes)
        if isinstance(raw_scopes, Mapping)
        else empty_scopes
    )
    raw_backends: object = getattr(route.host, "BACKENDS", None)
    backends = (
        cast(BackendLookup, raw_backends)
        if callable(getattr(raw_backends, "get", None))
        else None
    )
    return provider_id, scopes, backends


def _reject_provider_scope(route: _RouteLike, provider_id: str) -> None:
    _ = route.reject(
        503,
        "provider_route_unavailable",
        f"no eligible transport for provider '{provider_id}'",
    )


def single_route_provider_allowed(route: _RouteLike, backend: object = _UNSET) -> bool:
    """Проверяет допустимость одиночного маршрута для provider_id; при отказе 503."""
    target = route.model.get("backend") if backend is _UNSET else backend
    provider_id, scopes, backends = _route_scope_context(route)
    if provider_id is None:
        return True
    if not backend_matches_provider(str(target or ""), provider_id, scopes, backends):
        _reject_provider_scope(route, provider_id)
        return False
    return True


def dispatch_scoped_single(
    route: _RouteT,
    routing: Mapping[str, object],
    apply_effort_fn: Callable[[_RouteT, object | None, _BodyT], tuple[_RouteT, _WireT]],
    prepare_body_fn: Callable[[_RouteT], _BodyT],
    dispatch_fn: Callable[[_RouteT, _WireT], object],
) -> None:
    """Диспетчеризует одиночный маршрут с fail-closed проверкой provider_id."""
    backend = (
        routing.get("zero_canon_backend")
        or routing.get("disabled_backend")
        or route.model.get("backend")
    )
    provider_id, scopes, backends = _route_scope_context(route)
    if provider_id is not None and not backend_matches_provider(
        str(backend or ""), provider_id, scopes, backends
    ):
        _reject_provider_scope(route, provider_id)
        return
    route.model["backend"] = backend
    adapter = backends.get(str(backend or "")) if backends is not None else None
    scoped_route, wire = apply_effort_fn(route, adapter, prepare_body_fn(route))
    _ = dispatch_fn(scoped_route, wire)


def filter_dispatch_routes(
    route: _RouteLike, routes: Sequence[T]
) -> tuple[T, ...] | None:
    """Фильтрует eligible-маршруты по provider_id или отклоняет запрос с 503."""
    provider_id, scopes, backends = _route_scope_context(route)
    if provider_id is None:
        if not routes:
            _ = route.reject(
                503, "route_unavailable", "no eligible transport is available"
            )
            return None
        return tuple(routes)
    scoped = scope_routes(routes, provider_id, scopes, backends)
    if not scoped:
        _reject_provider_scope(route, provider_id)
        return None
    return scoped
