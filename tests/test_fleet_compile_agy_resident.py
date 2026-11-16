"""Контракт компиляции resident- и alternate-маршрутов AGY."""

from __future__ import annotations

from pathlib import Path

from adapters import ADAPTER_KINDS
from core.fleet_compiler import compile_from_disk


ROOT = Path(__file__).resolve().parents[1]
AGY_MODELS = {
    "gemini-3.8-flash",
    "gemini-4-argon",
    "gemini-4-carbon",
    "gemini-4-hydrogen",
}


def test_agy_manifests_compile_resident_primary_and_disabled_alternate() -> None:
    """W2j-AC3: AGY получает resident primary и выключенный passthrough alternate."""

    compiled = compile_from_disk(
        ROOT / "providers.d",
        ROOT / "providers.d" / "_fleet.yaml",
        kinds=ADAPTER_KINDS,
        now="2026-11-16T00:00:00+03:00",
    ).fleet
    backends = compiled["backends"]
    models = {model["id"]: model for model in compiled["models"]}

    assert backends["agy"]["kind"] == "stdio_resident"
    assert {model_id for model_id in models if models[model_id]["backend"] == "agy"} == (
        AGY_MODELS
    )
    assert backends["agy-passthrough"]["kind"] == "passthrough"
    assert backends["agy-passthrough"]["enabled"] is False
