"""Контрактные тесты каталога и модальностей Google Gemini 4 Neon (REQ-02)."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from core.model_modalities import MULTIMODAL_MODELS, model_modalities, supports_images

ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(rel: str) -> dict:
    return yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))


def _load_json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def test_model_modalities_include_neon_and_orchestrator() -> None:
    assert "gemini-4-neon" in MULTIMODAL_MODELS
    assert "gemini-pro-orchestrator" in MULTIMODAL_MODELS
    for mid in (
        "gemini-4-neon",
        "gemini-4-neon-xhigh",
        "gemini-pro-orchestrator",
        "gemini-pro-orchestrator-argon",
        "gemini-pro-orchestrator-neon",
    ):
        assert supports_images(model_id=mid) is True
        assert model_modalities(model_id=mid) == ["text", "image"]


def test_provider_manifests_include_gemini_4_neon_and_orchestrators() -> None:
    for rel in ("providers.d/agy.yaml", "providers.d/agy-passthrough.yaml"):
        doc = _load_yaml(rel)
        static = doc["discovery"]["static"]
        overrides = doc["models_overrides"]
        for mid in (
            "gemini-4-neon",
            "gemini-pro-orchestrator",
            "gemini-pro-orchestrator-argon",
            "gemini-pro-orchestrator-neon",
        ):
            assert mid in static, f"{mid} missing in {rel} discovery.static"
            assert mid in overrides, f"{mid} missing in {rel} models_overrides"
        neon = overrides["gemini-4-neon"]
        assert neon["efforts"] == ["low", "medium", "high", "xhigh"]
        assert neon["default_effort"] == "high"
        assert neon["context_window"] == 1048576
        assert neon["max_tokens"] == 65536
        assert "text" in neon["input"]


def test_fleet_yaml_aliases_and_compiled_catalog() -> None:
    fleet_yaml = _load_yaml("providers.d/_fleet.yaml")
    aliases_yaml = fleet_yaml["aliases"]
    for effort in ("low", "medium", "high", "xhigh"):
        assert aliases_yaml[f"gemini-4-neon-{effort}"] == {
            "backend_id": "gemini-4-neon",
            "backend": "agy",
            "effort": effort,
        }
    for effort in ("low", "medium", "high"):
        assert aliases_yaml[f"gemini-4-carbon-{effort}"] == {
            "backend_id": "gemini-4-carbon",
            "backend": "agy",
            "effort": effort,
        }
        assert aliases_yaml[f"gemini-3.8-flash-{effort}"]["backend"] == "agy"

    compiled = _load_json("fleet.json")
    models = {m["id"]: m for m in compiled["models"]}
    assert "gemini-4-neon" in models
    neon = models["gemini-4-neon"]
    assert neon["backend"] == "agy"
    assert neon["efforts"] == ["low", "medium", "high", "xhigh"]
    assert neon["default_effort"] == "high"
    assert neon["context_window"] == 1048576
    assert neon["max_tokens"] == 65536
    assert compiled["aliases"]["gemini-4-neon-xhigh"] == {
        "backend_id": "gemini-4-neon",
        "backend": "agy",
        "effort": "xhigh",
    }

    lock = _load_json("catalog.lock.json")["models"]
    assert lock["gemini-4-neon"]["provider"] == "agy"
    assert lock["gemini-pro-orchestrator-neon"]["provider"] == "agy"


def test_agy_bridge_fleet_has_neon_and_keeps_hydrogen_first() -> None:
    agy_fleet = _load_json("bridges/agy-bridge/fleet.json")
    models_list = agy_fleet["models"]
    assert models_list[0]["id"] == "gemini-4-hydrogen"
    by_id = {m["id"]: m for m in models_list}
    assert "gemini-4-neon" in by_id
    assert by_id["gemini-4-neon"]["efforts"] == ["low", "medium", "high", "xhigh"]
    assert by_id["gemini-4-neon"]["default_effort"] == "high"
    assert "gemini-pro-orchestrator" in by_id
    assert "gemini-pro-orchestrator-argon" in by_id
    assert "gemini-pro-orchestrator-neon" in by_id
    carbon = by_id["gemini-4-carbon"]
    assert set(carbon["images"]["proof"]["efforts_proven"]) == {
        "low",
        "medium",
        "high",
        "off",
    }
