import json
from pathlib import Path
import pytest
from server import resolve_target_model

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
    """Runtime-трансляция server.py resolve_target_model подставляет upstream_model."""
    fleet = _load_fleet()
    entry = next((m for m in fleet.get("models", []) if m.get("id") == droid_model), None)
    assert entry is not None, f"{droid_model} not in fleet.json models"
    target_model = resolve_target_model(entry, droid_model)
    assert target_model == expected_canonical
    assert resolve_target_model({"id": expected_canonical}, expected_canonical) == expected_canonical


def test_canonical_and_droid_effort_aliases():
    """Проверяет, что canonical effort-алиасы ведут на native backend, а droid-алиасы фиксируют effort."""
    fleet = _load_fleet()
    aliases = fleet.get("aliases", {})
    # Canonical aliases must route to native backends
    assert aliases["gpt-6.1-sol-low"]["backend"] == "codex"
    assert aliases["gpt-6.1-sol-medium"]["backend"] == "codex"
    assert aliases["gpt-6.1-sol-high"]["backend"] == "codex"
    assert aliases["gemini-3.8-flash-low"]["backend"] == "agy"
    assert aliases["gemini-3.8-flash-medium"]["backend"] == "agy"
    assert aliases["gemini-3.8-flash-high"]["backend"] == "agy"
    assert aliases["claude-sonnet-5-5-medium"]["backend"] == "claude-p"
    assert aliases["claude-sonnet-5-5-high"]["backend"] == "claude-p"

    # Droid aliases must have backend=droid and matching effort
    for alias_name, spec in aliases.items():
        if alias_name.startswith("gemini-3.8-flash-droid-") or alias_name.startswith("gpt-6.1-sol-droid-") or alias_name.startswith("claude-sonnet-5-5-droid-"):
            suffix = alias_name.rsplit("-", 1)[1]
            assert isinstance(spec, dict), f"{alias_name} must be a dictionary spec"
            assert spec["backend"] == "droid"
            assert spec["effort"] == suffix
