"""Контракт компиляции маршрутов AGY и resident-бэкендов владельца."""

from __future__ import annotations

from pathlib import Path

from adapters import ADAPTER_KINDS
from core.fleet_compiler import compile_from_disk


ROOT = Path(__file__).resolve().parents[1]
AGY_MODELS = {
    "gemini-3.8-flash-agy",
    "gemini-4-argon",
    "gemini-4-carbon",
    "gemini-4-hydrogen",
}


def test_agy_manifests_compile_passthrough_primary_and_disabled_alternate() -> None:
    """AGY остаётся passthrough primary; `agy-passthrough` выключен, codex/droid — по политике."""

    compiled = compile_from_disk(
        ROOT / "providers.d",
        ROOT / "providers.d" / "_fleet.yaml",
        kinds=ADAPTER_KINDS,
        now="2026-11-16T00:00:00+03:00",
    ).fleet
    backends = compiled["backends"]
    models = {model["id"]: model for model in compiled["models"]}

    assert backends["agy"]["kind"] == "passthrough"
    assert backends["agy"]["enabled"] is True
    assert {model_id for model_id in models if models[model_id]["backend"] == "agy"} == (
        AGY_MODELS
    )
    assert backends["agy-passthrough"]["kind"] == "passthrough"
    assert backends["agy-passthrough"]["enabled"] is False
    # Политика владельца: resident только codex/claude-p, droid и платные ключи выключены.
    assert backends["codex"]["kind"] == "stdio_resident"
    assert backends["codex"]["enabled"] is True
    assert models["gpt-6.1-sol"]["backend"] == "codex"
    assert backends["droid"]["enabled"] is False
    assert backends["openai-key-2"]["enabled"] is False
    assert backends["openai-key-3"]["enabled"] is False
