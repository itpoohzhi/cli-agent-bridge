import json
from pathlib import Path

import yaml


def test_openai_key_2_is_disabled():
    provider = yaml.safe_load(Path("providers.d/openai-key-2.yaml").read_text())
    assert provider["enabled"] is False


def test_sol_and_terra_do_not_use_openai_key_2():
    fleet = json.loads(Path("fleet.json").read_text())
    models = fleet.get("models", fleet) if isinstance(fleet, dict) else fleet
    if isinstance(models, list):
        models = {
            model.get("id", model.get("name", model.get("model"))): model
            for model in models
        }

    for name in ("gpt-6.1-sol", "gpt-6.1-terra"):
        model = models[name]
        assert model.get("backend") != "openai-key-2", name
        assert model.get("routing", {}).get("legacy_backend") != "openai-key-2", name
        routes = model.get("routing", {}).get("routes", [])
        assert not any(
            route.get("backend") == "openai-key-2"
            and route.get("weight", 0) > 0
            for route in routes
        ), f"{name} has a positive-weight route to openai-key-2"
