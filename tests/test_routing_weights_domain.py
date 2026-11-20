"""Контрактные тесты чистого домена весов маршрутизации (Wave 0: red-repro)."""

from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError, is_dataclass
from typing import Any

import pytest

from core.routing_contract import routes_catalog_hash
from core.routing_weights_domain import (
    SCHEMA_VERSION,
    WeightsOverrideDoc,
    WeightsValidationError,
    apply_weight_overrides,
    build_catalog_routing_view,
    validate_weights_document,
)


def _sample_routing() -> dict[str, Any]:
    """Возвращает эталонную копию routing для модели с несколькими маршрутами."""
    routes = [
        {"route_id": "codex", "backend": "codex", "weight": 20, "priority": 10},
        {"route_id": "openai-key-3", "backend": "openai-key-3", "weight": 80, "priority": 20},
        {"route_id": "droid", "backend": "droid", "weight": 0, "priority": 30},
    ]
    return {
        "algorithm": "weighted-sha256-v1",
        "enabled": True,
        "catalog_hash": routes_catalog_hash(routes),
        "legacy_backend": "openai-key-3",
        "disabled_backend": "codex",
        "routes": routes,
    }


def _sample_fleet() -> dict[str, Any]:
    """Формирует компактный каталог из всех четырёх категорий моделей."""
    return {
        "backends": {
            "opencode-go-claude": {"enabled": True},
            "claude-p": {"enabled": True},
            "agy": {"enabled": True},
            "agy-passthrough": {"enabled": False},
            "droid": {"enabled": False},
        },
        "models": [
            {
                "id": "claude-haiku-5-5",
                "backend": "opencode-go-claude",
                "routing": {
                    "enabled": True,
                    "routes": [
                        {"route_id": "opencode-go-claude", "backend": "opencode-go-claude", "weight": 75, "priority": 10},
                        {"route_id": "claude-p", "backend": "claude-p", "weight": 25, "priority": 20},
                    ],
                },
            },
            {
                "id": "claude-sonnet-5-5",
                "backend": "claude-p",
                "routing": {
                    "enabled": True,
                    "routes": [
                        {"route_id": "claude-p", "backend": "claude-p", "weight": 50, "priority": 10},
                        {"route_id": "droid", "backend": "droid", "weight": 50, "priority": 20},
                    ],
                },
            },
            {"id": "gemini-4-hydrogen", "backend": "agy"},
            {"id": "claude-opus-5-5", "backend": "claude-p"},
            {"id": "claude-sonnet-5-5-droid", "backend": "droid"},
        ],
    }


def _sample_lock() -> dict[str, Any]:
    """Возвращает lock-снимок с disabled-альтернативой для одиночной модели."""
    return {"models": {"gemini-4-hydrogen": {"provider": "agy", "alternates": [{"provider": "agy-passthrough"}]}}}


def test_contract_constants_and_frozen_doc() -> None:
    """Проверяет версию схемы, иерархию исключений и неизменяемость DTO."""
    assert SCHEMA_VERSION == 1
    assert issubclass(WeightsValidationError, ValueError)
    assert is_dataclass(WeightsOverrideDoc)

    doc = validate_weights_document(
        {
            "schema_version": 1,
            "updated_at": None,
            "updated_by": None,
            "providers": {"claude-p": 0},
            "models": {"gpt-6.1-sol": {"codex": 100}},
        }
    )
    with pytest.raises(FrozenInstanceError):
        setattr(doc, "schema_version", 2)


def test_validate_valid_v1_document() -> None:
    """Принимает валидный v1-документ на границах диапазона весов 0..10000."""
    raw = {
        "schema_version": 1,
        "updated_at": "2026-11-20T17:30:00Z",
        "updated_by": "swiftbar",
        "providers": {"claude-p": 0, "codex": 10000},
        "models": {"gpt-6.1-sol": {"openai-key-3": 80, "codex": 20}},
    }
    doc = validate_weights_document(raw)
    assert doc.schema_version == 1
    assert doc.providers == {"claude-p": 0, "codex": 10000}
    assert doc.models["gpt-6.1-sol"] == {"openai-key-3": 80, "codex": 20}
    assert doc.updated_at == "2026-11-20T17:30:00Z"
    assert doc.updated_by == "swiftbar"


@pytest.mark.parametrize(
    "raw",
    [
        [],
        "invalid",
        {"schema_version": 1, "updated_at": None, "updated_by": None, "providers": {}, "models": {}, "extra": 1},
    ],
)
def test_validate_rejects_non_dict_and_extra_keys(raw: object) -> None:
    """Отвергает некорректный корень и лишние ключи (additionalProperties=false)."""
    with pytest.raises(WeightsValidationError):
        validate_weights_document(raw)


@pytest.mark.parametrize("version", [0, 2, "1", None, True, False])
def test_validate_rejects_invalid_schema_version(version: object) -> None:
    """Отвергает любую версию схемы кроме строгого int == 1 (включая bool)."""
    with pytest.raises(WeightsValidationError):
        validate_weights_document({"schema_version": version, "providers": {}, "models": {}})


@pytest.mark.parametrize("bad_weight", [-1, 10001, True, False, 1.5, "50", None])
def test_validate_rejects_invalid_weights(bad_weight: object) -> None:
    """Отвергает веса вне 0..10000 и нечисловые типы, включая bool."""
    with pytest.raises(WeightsValidationError):
        validate_weights_document({"schema_version": 1, "providers": {"codex": bad_weight}, "models": {}})
    with pytest.raises(WeightsValidationError):
        validate_weights_document({"schema_version": 1, "providers": {}, "models": {"gpt-6.1-sol": {"codex": bad_weight}}})


@pytest.mark.parametrize("bad_id", ["", "../x", ";rm", "bad id", "a" * 65])
def test_validate_rejects_invalid_identifiers(bad_id: str) -> None:
    """Отвергает пустые, небезопасные и слишком длинные идентификаторы."""
    with pytest.raises(WeightsValidationError):
        validate_weights_document({"schema_version": 1, "providers": {bad_id: 50}, "models": {}})
    with pytest.raises(WeightsValidationError):
        validate_weights_document({"schema_version": 1, "providers": {}, "models": {bad_id: {"codex": 50}}})
    with pytest.raises(WeightsValidationError):
        validate_weights_document({"schema_version": 1, "providers": {}, "models": {"gpt-6.1-sol": {bad_id: 50}}})


@pytest.mark.parametrize("bad_meta", ["line1\nline2", "null\x00byte", "del\x7fchar", "x" * 129])
def test_validate_rejects_control_chars_in_metadata(bad_meta: str) -> None:
    """Отвергает управляющие символы и превышение длины в updated_at/updated_by."""
    with pytest.raises(WeightsValidationError):
        validate_weights_document({"schema_version": 1, "updated_at": bad_meta, "providers": {}, "models": {}})
    with pytest.raises(WeightsValidationError):
        validate_weights_document({"schema_version": 1, "updated_by": bad_meta, "providers": {}, "models": {}})


def test_apply_overrides_precedence_hash_and_purity() -> None:
    """Проверяет приоритет model > provider > fleet, пересчёт хеша и чистоту входа."""
    routing = _sample_routing()
    snapshot = copy.deepcopy(routing)
    doc = WeightsOverrideDoc(
        schema_version=1,
        providers={"codex": 90, "openai-key-3": 10},
        models={"gpt-6.1-sol": {"codex": 150}},
        updated_at=None,
        updated_by=None,
    )
    updated = apply_weight_overrides("gpt-6.1-sol", routing, doc)

    assert routing == snapshot
    assert updated is not routing
    weights = {route["backend"]: route["weight"] for route in updated["routes"]}
    # codex взят из models (150), openai-key-3 из providers (10), droid из fleet (0)
    assert weights == {"codex": 150, "openai-key-3": 10, "droid": 0}
    assert updated["catalog_hash"] == routes_catalog_hash(updated["routes"])
    assert updated["legacy_backend"] == "codex"
    assert updated["disabled_backend"] == "codex"


def test_apply_overrides_legacy_backend_tiebreak() -> None:
    """Выбирает legacy_backend строго по ключу (-weight, priority, backend)."""
    routing = _sample_routing()
    doc = WeightsOverrideDoc(1, {}, {"gpt-6.1-sol": {"codex": 50, "openai-key-3": 50, "droid": 50}}, None, None)
    updated = apply_weight_overrides("gpt-6.1-sol", routing, doc)
    # При равных весах (50) побеждает наименьший priority=10 (codex)
    assert updated["legacy_backend"] == "codex"

    routing_same_prio = _sample_routing()
    for route in routing_same_prio["routes"]:
        route["priority"] = 10
    updated_tie = apply_weight_overrides("gpt-6.1-sol", routing_same_prio, doc)
    # При равных весах и priority побеждает лексикографически минимальный backend
    assert updated_tie["legacy_backend"] == "codex"


def test_apply_overrides_all_zero_reserve() -> None:
    """Корректно обрабатывает перевод всех маршрутов модели в резерв (weight == 0)."""
    routing = _sample_routing()
    doc = WeightsOverrideDoc(1, {"codex": 0, "openai-key-3": 0}, {}, None, None)
    updated = apply_weight_overrides("gpt-6.1-sol", routing, doc)

    assert all(route["weight"] == 0 for route in updated["routes"])
    assert updated["catalog_hash"] == routes_catalog_hash(updated["routes"])
    assert updated["legacy_backend"] == "codex"
    assert updated["disabled_backend"] == "codex"


def test_catalog_view_classifies_all_four_categories() -> None:
    """Классифицирует все модели каталога на четыре ожидаемые категории."""
    view = build_catalog_routing_view(_sample_fleet(), doc=None, lock_data=_sample_lock())
    models = view["models"]

    assert models["claude-haiku-5-5"]["category"] == "multi_active"
    assert models["claude-sonnet-5-5"]["category"] == "single_with_disabled"
    assert models["gemini-4-hydrogen"]["category"] == "single_with_disabled"
    assert models["claude-opus-5-5"]["category"] == "single_only"
    assert models["claude-sonnet-5-5-droid"]["category"] == "disabled_only"


def test_catalog_view_shares_sources_and_coupling() -> None:
    """Вычисляет доли %, источники весов и список затронутых моделей провайдера."""
    doc = WeightsOverrideDoc(1, {"claude-p": 20}, {"claude-haiku-5-5": {"opencode-go-claude": 80}}, "2026-11-20T18:00:00Z", "test")
    view = build_catalog_routing_view(_sample_fleet(), doc=doc, lock_data=_sample_lock())
    haiku = {r["backend"]: r for r in view["models"]["claude-haiku-5-5"]["routes"]}

    assert (haiku["opencode-go-claude"]["weight"], haiku["opencode-go-claude"]["source"]) == (80, "model-override")
    assert haiku["opencode-go-claude"]["share_pct"] == pytest.approx(80.0)
    assert (haiku["claude-p"]["weight"], haiku["claude-p"]["source"]) == (20, "provider-override")
    assert haiku["claude-p"]["share_pct"] == pytest.approx(20.0)

    gemini = {r["backend"]: r for r in view["models"]["gemini-4-hydrogen"]["routes"]}
    assert gemini["agy"]["source"] == "fleet"
    assert gemini["agy"]["share_pct"] == pytest.approx(100.0)
    assert set(view["providers"]["claude-p"]["models"]) >= {"claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"}


def test_catalog_view_zero_weights_yield_zero_shares() -> None:
    """При всех нулевых весах доли равны 0.0 без деления на ноль."""
    doc = WeightsOverrideDoc(1, {"claude-p": 0}, {"claude-haiku-5-5": {"opencode-go-claude": 0}}, None, None)
    view = build_catalog_routing_view(_sample_fleet(), doc=doc, lock_data=_sample_lock())
    haiku = {r["backend"]: r for r in view["models"]["claude-haiku-5-5"]["routes"]}

    assert haiku["opencode-go-claude"]["share_pct"] == pytest.approx(0.0)
    assert haiku["claude-p"]["share_pct"] == pytest.approx(0.0)
