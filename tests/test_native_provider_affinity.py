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


@pytest.mark.parametrize("expected_alias,expected_backend,expected_effort", [
    ("gemini-3.8-flash-droid-low", "droid", "low"),
    ("gemini-3.8-flash-droid-medium", "droid", "medium"),
    ("gemini-3.8-flash-droid-high", "droid", "high"),
    ("gpt-6.1-sol-droid-low", "droid", "low"),
    ("gpt-6.1-sol-droid-medium", "droid", "medium"),
    ("gpt-6.1-sol-droid-high", "droid", "high"),
    ("claude-sonnet-5-5-droid-low", "droid", "low"),
    ("claude-sonnet-5-5-droid-medium", "droid", "medium"),
    ("claude-sonnet-5-5-droid-high", "droid", "high"),
    ("claude-sonnet-5-5-droid-max", "droid", "max"),
    ("gpt-6.1-sol-low", "codex", "low"),
    ("gpt-6.1-sol-medium", "codex", "medium"),
    ("gpt-6.1-sol-high", "codex", "high"),
    ("gemini-3.8-flash-low", "agy", "low"),
    ("gemini-3.8-flash-medium", "agy", "medium"),
    ("gemini-3.8-flash-high", "agy", "high"),
    ("claude-sonnet-5-5-low", "claude-p", "low"),
    ("claude-sonnet-5-5-medium", "claude-p", "medium"),
    ("claude-sonnet-5-5-high", "claude-p", "high"),
])
def test_explicit_effort_alias_contract(expected_alias, expected_backend, expected_effort):
    """Каждый обязательный алиас строго проверяется на backend и effort."""
    fleet = _load_fleet()
    aliases = fleet.get("aliases", {})
    assert expected_alias in aliases, f"Missing required alias: {expected_alias}"
    spec = aliases[expected_alias]
    assert isinstance(spec, dict), f"{expected_alias} must be a dict spec"
    assert spec["backend"] == expected_backend
    assert spec["effort"] == expected_effort


@pytest.mark.parametrize("droid_model,expected_upstream", [
    ("gemini-3.8-flash-droid", "gemini-3.8-flash"),
    ("gpt-6.1-sol-droid", "gpt-6.1-sol"),
    ("claude-sonnet-5-5-droid", "claude-sonnet-5-5"),
])
def test_make_plan_droid_uses_upstream_model(droid_model, expected_upstream):
    """Проверяет, что runtime _make_plan прокидывает канонический upstream_model в Droid RPC settings."""
    from server import _make_plan, resolve_target_model
    fleet = _load_fleet()
    entry = next((m for m in fleet.get("models", []) if m.get("id") == droid_model), None)
    assert entry is not None
    target = resolve_target_model(entry, droid_model)
    assert target == expected_upstream
    ctx = {
        "rpc": {"items": [], "system": ""},
        "model": droid_model,
        "target_model": target,
        "effort": "low",
        "autonomy": "off",
        "route": "nokey",
    }
    plan = _make_plan(ctx, None, "", "/tmp", [])
    assert plan["settings"][0] == expected_upstream


def test_compiled_catalog_matches_manifests():
    """Проверяет, что fleet.json и catalog.lock.json строго соответствуют компиляции манифестов providers.d."""
    from core.fleet_compiler import compile_from_disk, default_kinds
    res = compile_from_disk(
        providers_path=ROOT / "providers.d",
        fleet_meta_path=ROOT / "providers.d" / "_fleet.yaml",
        kinds=default_kinds(),
    )
    fleet = _load_fleet()
    catalog = _load_catalog()
    assert {m["id"] for m in res.fleet["models"]} == {m["id"] for m in fleet["models"]}
    assert res.fleet["aliases"] == fleet["aliases"]
    for mid, info in res.sidecar.get("models", {}).items():
        assert mid in catalog["models"]
        assert info["provider"] == catalog["models"][mid]["provider"]
