"""Validation helpers for model catalogs and backend registries."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


class ValidationResult(dict):
    """Dictionary report with attribute access retained for older callers."""

    def __init__(
        self,
        errors: Iterable[str] | None = None,
        warnings: Iterable[str] | None = None,
    ) -> None:
        error_list = list(errors or [])
        warning_list = list(warnings or [])
        super().__init__(
            valid=not error_list,
            errors=error_list,
            warnings=warning_list,
        )

    @property
    def valid(self) -> bool:
        return bool(self["valid"])

    @property
    def errors(self) -> list[str]:
        return self["errors"]

    @property
    def warnings(self) -> list[str]:
        return self["warnings"]

    def __bool__(self) -> bool:
        return self.valid


def _field(value: Any, *names: str, default: Any = None) -> Any:
    if value is None:
        return default
    for name in names:
        if isinstance(value, Mapping):
            candidate = value.get(name)
        else:
            candidate = getattr(value, name, None)
        if candidate is not None and not callable(candidate):
            return candidate
    return default


def _models(catalog: Any) -> list[tuple[str, Any]]:
    if catalog is None:
        return []
    source = _field(catalog, "models", default=catalog)
    if isinstance(source, Mapping):
        return [(str(name), spec) for name, spec in source.items()]
    if isinstance(source, Iterable) and not isinstance(source, (str, bytes)):
        result: list[tuple[str, Any]] = []
        for index, spec in enumerate(source):
            name = _field(spec, "model_id", "name", "id", "model")
            result.append((str(name if name is not None else index), spec))
        return result
    return []


def _backend_names(backends: Any) -> set[str]:
    if backends is None:
        return set()
    source = _field(backends, "backends", default=backends)
    if isinstance(source, Mapping):
        return {str(name) for name in source}
    if isinstance(source, Iterable) and not isinstance(source, (str, bytes)):
        names: set[str] = set()
        for backend in source:
            name = _field(backend, "name", "backend_id", "id", "backend")
            if name is not None:
                names.add(str(name))
        return names
    return set()


def _model_backend(model: Any) -> Any:
    backend = _field(model, "backend", "backend_id")
    if backend is not None:
        return backend
    route = _field(model, "route", "routing")
    if route is None:
        return None
    if isinstance(route, str):
        return route
    return _field(route, "backend", "backend_id", "name", "id")


def validate_catalog(catalog: Any, backends: Any = None) -> ValidationResult:
    """Validate that every catalog model has a route to a registered backend."""

    if backends is None:
        backends = _field(catalog, "backends", "backend_registry")

    errors: list[str] = []
    warnings: list[str] = []
    known_backends = _backend_names(backends)

    for model_name, model in _models(catalog):
        backend = _model_backend(model)
        if backend is None or str(backend) not in known_backends:
            errors.append(f"model {model_name} missing backend or route")

    return ValidationResult(errors, warnings)


def validate_registry(
    registry: Any,
    backends: Any = None,
    catalog: Any = None,
) -> ValidationResult:
    """Validate a combined registry or an explicitly supplied catalog/backend pair."""

    selected_catalog = catalog
    if selected_catalog is None:
        selected_catalog = _field(registry, "catalog", "models", default=registry)
        if selected_catalog is not registry and not _field(selected_catalog, "models"):
            selected_catalog = {"models": selected_catalog}

    selected_backends = backends
    if selected_backends is None:
        selected_backends = _field(registry, "backends", "backend_registry")

    return validate_catalog(selected_catalog, selected_backends)


__all__ = ["ValidationResult", "validate_catalog", "validate_registry"]
