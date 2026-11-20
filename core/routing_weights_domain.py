"""Чистый домен оперативных весов маршрутизации (M-MOD-I3: без I/O и env)."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from core.routing_contract import routes_catalog_hash, validate_weight

SCHEMA_VERSION: int = 1
_MAX_META_LEN: int = 128
_ID_RE: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")
_ROOT_KEYS: frozenset[str] = frozenset({"schema_version", "updated_at", "updated_by", "providers", "models"})
_CATEGORY_ORDER: tuple[str, ...] = ("multi_active", "single_with_disabled", "single_only", "disabled_only")


class WeightsValidationError(ValueError):
    """Ошибка строгой валидации документа оперативных весов v1."""


@dataclass(frozen=True, slots=True)
class WeightsOverrideDoc:
    """Неизменяемый снимок документа оперативных весов маршрутизации v1."""

    schema_version: int = SCHEMA_VERSION
    providers: Mapping[str, int] = field(default_factory=lambda: MappingProxyType({}))
    models: Mapping[str, Mapping[str, int]] = field(default_factory=lambda: MappingProxyType({}))
    updated_at: str | None = None
    updated_by: str | None = None

    def __post_init__(self) -> None:
        frozen_models = {m: MappingProxyType(dict(b)) for m, b in self.models.items()}
        object.__setattr__(self, "providers", MappingProxyType(dict(self.providers)))
        object.__setattr__(self, "models", MappingProxyType(frozen_models))

    @classmethod
    def empty(cls) -> WeightsOverrideDoc:
        """Возвращает пустой документ схемы v1 без переопределений."""
        return cls()

    def to_dict(self) -> dict[str, Any]:
        """Сериализует документ в чистый JSON-совместимый dict схемы v1."""
        return {
            "schema_version": self.schema_version, "updated_at": self.updated_at, "updated_by": self.updated_by,
            "providers": dict(self.providers), "models": {m: dict(b) for m, b in self.models.items()},
        }


def _validate_identifier(value: object, kind: str) -> str:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        raise WeightsValidationError(f"invalid_{kind}_identifier")
    return value


def _validate_meta_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > _MAX_META_LEN:
        raise WeightsValidationError(f"invalid_{field_name}")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise WeightsValidationError(f"control_char_in_{field_name}")
    return value


def _validate_weight_map(raw_map: object, kind: str) -> dict[str, int]:
    if not isinstance(raw_map, Mapping):
        raise WeightsValidationError(f"invalid_{kind}_mapping")
    result: dict[str, int] = {}
    for key, val in raw_map.items():
        ident = _validate_identifier(key, kind)
        try:
            result[ident] = validate_weight(val)
        except ValueError as exc:
            raise WeightsValidationError(f"invalid_weight_{kind}") from exc
    return result


def validate_weights_document(raw: object) -> WeightsOverrideDoc:
    """Строго валидирует JSON-документ весов по контракту CD-001 (v1)."""
    if not isinstance(raw, Mapping):
        raise WeightsValidationError("root_must_be_mapping")
    keys = set(raw.keys())
    if keys - _ROOT_KEYS or not {"schema_version", "providers", "models"}.issubset(keys):
        raise WeightsValidationError("invalid_root_keys")
    version = raw["schema_version"]
    if type(version) is not int or version != SCHEMA_VERSION:
        raise WeightsValidationError("invalid_schema_version")
    updated_at = _validate_meta_text(raw.get("updated_at"), "updated_at")
    updated_by = _validate_meta_text(raw.get("updated_by"), "updated_by")
    providers = _validate_weight_map(raw["providers"], "provider")
    raw_models = raw["models"]
    if not isinstance(raw_models, Mapping):
        raise WeightsValidationError("invalid_models_mapping")
    models = {_validate_identifier(m, "model"): _validate_weight_map(b, "backend") for m, b in raw_models.items()}
    return WeightsOverrideDoc(version, providers, models, updated_at, updated_by)


def resolve_route_weight(model_id: str, backend: str, fleet_weight: int, doc: WeightsOverrideDoc | None) -> tuple[int, str]:
    """Определяет эффективный вес и его источник: model > provider > fleet."""
    if doc is not None:
        model_overrides = doc.models.get(model_id)
        if model_overrides is not None and backend in model_overrides:
            return model_overrides[backend], "model-override"
        if backend in doc.providers:
            return doc.providers[backend], "provider-override"
    return fleet_weight, "fleet"


def apply_weight_overrides(model_id: str, routing: Mapping[str, object], doc: WeightsOverrideDoc | None) -> dict[str, Any]:
    """Возвращает копию routing с эффективными весами, новым hash и legacy_backend."""
    result: dict[str, Any] = dict(routing)
    raw_routes = routing.get("routes")
    if not isinstance(raw_routes, Sequence) or isinstance(raw_routes, (str, bytes, bytearray)):
        return result
    new_routes: list[dict[str, Any]] = []
    for raw_route in raw_routes:
        route_copy = dict(raw_route)
        route_copy["weight"], _ = resolve_route_weight(model_id, str(route_copy["backend"]), int(route_copy["weight"]), doc)
        new_routes.append(route_copy)
    result["routes"] = new_routes
    result["catalog_hash"] = routes_catalog_hash(new_routes)
    if new_routes:
        owner = min(new_routes, key=lambda r: (-int(r["weight"]), int(r["priority"]), str(r["backend"])))
        result["legacy_backend"] = owner["backend"]
    return result


def _is_backend_enabled(backends: Mapping[str, Any], backend: str) -> bool:
    meta = backends.get(backend)
    return meta.get("enabled", True) is True if isinstance(meta, Mapping) else True


def _lock_alternates(lock_data: Mapping[str, Any] | None, model_id: str, known: set[str]) -> list[str]:
    if not isinstance(lock_data, Mapping):
        return []
    lock_models = lock_data.get("models")
    entry = lock_models.get(model_id) if isinstance(lock_models, Mapping) else None
    alternates = entry.get("alternates", ()) if isinstance(entry, Mapping) else ()
    extra: list[str] = []
    for alt in alternates:
        name = alt.get("provider") or alt.get("backend") if isinstance(alt, Mapping) else alt
        if isinstance(name, str) and name and name not in known:
            known.add(name)
            extra.append(name)
    return extra


def _extract_model_routes(model: Mapping[str, Any], backends: Mapping[str, Any]) -> list[dict[str, Any]]:
    routing = model.get("routing")
    if isinstance(routing, Mapping) and routing.get("enabled") is True:
        raw_routes = routing.get("routes")
        if isinstance(raw_routes, Sequence) and not isinstance(raw_routes, (str, bytes, bytearray)):
            return [dict(r) for r in raw_routes if isinstance(r, Mapping)]
    backend = str(model.get("backend", ""))
    if not backend:
        return []
    weight = 100 if _is_backend_enabled(backends, backend) else 0
    return [{"route_id": backend, "backend": backend, "weight": weight, "priority": 0}]


def _classify_model(active_count: int, disabled_count: int) -> str:
    if active_count >= 2:
        return "multi_active"
    if active_count == 1 and disabled_count > 0:
        return "single_with_disabled"
    return "single_only" if active_count == 1 else "disabled_only"


def _evaluate_routes(
    model_id: str, raw_routes: Sequence[Mapping[str, Any]], backends: Mapping[str, Any], doc: WeightsOverrideDoc | None
) -> tuple[list[dict[str, Any]], list[str]]:
    evaluated, disabled = [], []
    for route in raw_routes:
        backend = str(route["backend"])
        enabled = (route.get("enabled", True) is True) and _is_backend_enabled(backends, backend)
        weight, source = resolve_route_weight(model_id, backend, int(route.get("weight", 0)), doc)
        if not enabled:
            disabled.append(backend)
        evaluated.append({
            "route_id": str(route.get("route_id", backend)), "backend": backend, "weight": weight,
            "priority": int(route.get("priority", 0)), "enabled": enabled, "source": source,
        })
    total_active = sum(item["weight"] for item in evaluated if item["enabled"])
    for item in evaluated:
        item["share_pct"] = (item["weight"] / total_active) * 100.0 if item["enabled"] and total_active > 0 else 0.0
    return evaluated, disabled


def _build_model_entry(
    model: Mapping[str, Any], backends: Mapping[str, Any], doc: WeightsOverrideDoc | None, lock_data: Mapping[str, Any] | None
) -> tuple[str, dict[str, Any]]:
    model_id = str(model["id"])
    evaluated, disabled = _evaluate_routes(model_id, _extract_model_routes(model, backends), backends, doc)
    disabled.extend(_lock_alternates(lock_data, model_id, {item["backend"] for item in evaluated}))
    active_count = sum(1 for item in evaluated if item["enabled"])
    return model_id, {
        "id": model_id, "backend": model.get("backend"),
        "category": _classify_model(active_count, len(disabled)), "routes": evaluated,
        "disabled_candidates": disabled, "total_weight": sum(i["weight"] for i in evaluated if i["enabled"]),
    }


def _collect_providers(
    models_view: Mapping[str, Mapping[str, Any]], backends: Mapping[str, Any], doc: WeightsOverrideDoc | None
) -> dict[str, dict[str, Any]]:
    provider_models: dict[str, list[str]] = {str(name): [] for name in backends if isinstance(name, str)}
    for model_id, entry in models_view.items():
        for route in entry["routes"]:
            provider_models.setdefault(route["backend"], []).append(model_id)
    return {
        p: {"enabled": _is_backend_enabled(backends, p), "models": list(dict.fromkeys(ms)), "override_weight": doc.providers.get(p) if doc else None}
        for p, ms in sorted(provider_models.items())
    }


def build_catalog_routing_view(
    fleet: Mapping[str, Any], doc: WeightsOverrideDoc | None = None, lock_data: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Строит динамическую матрицу маршрутизации для всего каталога моделей."""
    backends = fleet.get("backends")
    backends_map: Mapping[str, Any] = backends if isinstance(backends, Mapping) else {}
    models_view: dict[str, dict[str, Any]] = {}
    categories: dict[str, list[str]] = {cat: [] for cat in _CATEGORY_ORDER}
    for model in fleet.get("models", ()):
        if isinstance(model, Mapping) and "id" in model:
            model_id, entry = _build_model_entry(model, backends_map, doc, lock_data)
            models_view[model_id] = entry
            categories[entry["category"]].append(model_id)
    override_count = len(doc.providers) + sum(len(m) for m in doc.models.values()) if doc is not None else 0
    return {"models": models_view, "providers": _collect_providers(models_view, backends_map, doc), "categories": categories, "override_count": override_count}
