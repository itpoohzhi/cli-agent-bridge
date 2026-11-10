import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent

def _load_catalog():
    with (ROOT / "catalog.lock.json").open(encoding="utf-8") as f:
        return json.load(f)

def _load_fleet():
    with (ROOT / "fleet.json").open(encoding="utf-8") as f:
        return json.load(f)

@pytest.mark.parametrize("model_id,expected_provider", [
    ("gemini-3.8-flash", "agy"),
    ("claude-sonnet-5-5", "claude-p"),
    ("deepseek-v4.1-flash", "opencode-go"),
    ("gpt-6.1-sol", "codex"),
])
def test_native_provider_priority(model_id, expected_provider):
    cat = _load_catalog()
    models = cat.get("models", {})
    assert model_id in models, f"{model_id} not in catalog.lock.json"
    assert models[model_id].get("provider") == expected_provider

@pytest.mark.parametrize("model_id", [
    "gemini-3.8-flash-droid",
    "gpt-6.1-sol-droid",
    "claude-sonnet-5-5-droid",
])
def test_explicit_droid_models(model_id):
    cat = _load_catalog()
    models = cat.get("models", {})
    assert model_id in models, f"{model_id} not in catalog.lock.json"
    assert models[model_id].get("provider") == "droid"

@pytest.mark.parametrize("model_id", [
    "gemini-3.8-flash",
    "claude-sonnet-5-5",
    "gpt-6.1-sol",
])
def test_droid_alternates(model_id):
    cat = _load_catalog()
    models = cat.get("models", {})
    assert model_id in models
    alts = models[model_id].get("alternates", [])
    providers = [a.get("provider") if isinstance(a, dict) else a for a in alts]
    assert "droid" in providers

@pytest.mark.parametrize("droid_model,upstream_model", [
    ("gemini-3.8-flash-droid", "gemini-3.8-flash"),
    ("gpt-6.1-sol-droid", "gpt-6.1-sol"),
    ("claude-sonnet-5-5-droid", "claude-sonnet-5-5"),
])
def test_droid_upstream_model(droid_model, upstream_model):
    fleet = _load_fleet()
    models = fleet.get("models", [])
    entry = next((m for m in models if m.get("id") == droid_model), None)
    assert entry is not None, f"{droid_model} not in fleet.json models"
    assert entry.get("upstream_model") == upstream_model

EXPECTED_FAMILY_PROVIDER = {
    "Google": "agy",
    "Anthropic": "claude-p",
    "OpenAI": "codex",
    "DeepSeek": "opencode-go",
    "Meta": "muse",
}

def test_native_provider_affinity_invariant():
    """Инвариант: родной провайдер всегда побеждает агрегаторы (droid, opencode-zen)."""
    cat = _load_catalog()
    models = cat.get("models", {})
    aggregators = {"droid", "opencode-zen"}

    for model_id, info in models.items():
        provider = info.get("provider")
        family = info.get("family")
        alternates = [a.get("provider") if isinstance(a, dict) else a for a in info.get("alternates", [])]

        if model_id.endswith("-droid"):
            assert provider == "droid", f"{model_id} should be droid, got {provider}"
        elif family in EXPECTED_FAMILY_PROVIDER:
            expected = EXPECTED_FAMILY_PROVIDER[family]
            assert provider == expected, f"{model_id} (family={family}) should be {expected}, got {provider}"
            assert provider not in aggregators, f"Canonical model {model_id} cannot have aggregator as primary, got {provider}"

        if any(alt in aggregators for alt in alternates):
            assert provider not in aggregators, f"{model_id} has aggregator alternate but primary is {provider}"

@pytest.mark.parametrize("droid_model,expected_canonical", [
    ("gemini-3.8-flash-droid", "gemini-3.8-flash"),
    ("gpt-6.1-sol-droid", "gpt-6.1-sol"),
    ("claude-sonnet-5-5-droid", "claude-sonnet-5-5"),
])
def test_runtime_upstream_model_translation(droid_model, expected_canonical):
    """Runtime-трансляция server.py:7248-7258 подставляет upstream_model."""
    fleet = _load_fleet()
    entry = next((m for m in fleet.get("models", []) if m.get("id") == droid_model), None)
    assert entry is not None, f"{droid_model} not in fleet.json models"
    upstream_model = entry.get("upstream_model")
    has_upstream = isinstance(upstream_model, str) and bool(upstream_model.strip())
    target_model = upstream_model.strip() if has_upstream else droid_model
    assert target_model == expected_canonical
