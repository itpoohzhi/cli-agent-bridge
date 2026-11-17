"""L2: маршрутизация gemini-3.8-flash в droid, явный AGY-слот и согласованность с providers.d."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.passthrough_autonomy import resolve_target_model

ROOT = Path(__file__).resolve().parents[1]
EFFORTS = ("low", "medium", "high")


def _fleet() -> dict:
    return json.loads((ROOT / "fleet.json").read_text(encoding="utf-8"))


def _model(model_id: str) -> dict:
    return next(m for m in _fleet()["models"] if m["id"] == model_id)


def test_base_model_routes_to_droid_with_upstream() -> None:
    model = _model("gemini-3.8-flash")
    assert model["backend"] == "droid"
    assert resolve_target_model(model, "gemini-3.8-flash") == "gemini-3.8-flash"


@pytest.mark.parametrize("effort", ("low", "high"))
def test_effort_aliases_route_to_droid(effort: str) -> None:
    alias = _fleet()["aliases"][f"gemini-3.8-flash-{effort}"]
    assert alias == {"backend_id": "gemini-3.8-flash", "backend": "droid", "effort": effort}


def test_medium_effort_alias_routes_to_agy() -> None:
    alias = _fleet()["aliases"]["gemini-3.8-flash-medium"]
    assert alias == {
        "backend_id": "gemini-3.8-flash-agy",
        "backend": "agy",
        "effort": "medium",
    }


def test_explicit_agy_slot_is_kept_and_rewrites_to_upstream_model() -> None:
    model = _model("gemini-3.8-flash-agy")
    assert model["backend"] == "agy"
    assert model["upstream_model"] == "gemini-3.8-flash"
    assert resolve_target_model(model, "gemini-3.8-flash-agy") == "gemini-3.8-flash"
    for effort in EFFORTS:
        alias = _fleet()["aliases"][f"gemini-3.8-flash-agy-{effort}"]
        assert alias == {"backend_id": "gemini-3.8-flash-agy", "backend": "agy", "effort": effort}


def test_catalog_lock_primary_providers() -> None:
    lock = json.loads((ROOT / "catalog.lock.json").read_text(encoding="utf-8"))["models"]
    assert lock["gemini-3.8-flash"]["provider"] == "droid"
    assert lock["gemini-3.8-flash-agy"]["provider"] == "agy"
