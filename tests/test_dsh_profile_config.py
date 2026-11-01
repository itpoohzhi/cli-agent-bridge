from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import pytest

try:
    import yaml
except ModuleNotFoundError:
    homebrew_site_packages = Path("/opt/homebrew/lib/python3.14/site-packages")
    if not homebrew_site_packages.is_dir():
        raise
    sys.path.append(str(homebrew_site_packages))
    import yaml

ROOT = Path(__file__).resolve().parents[1]
AGY_MODELS = ("gemini-4-argon", "gemini-3.8-flash")
REMOVED_MODELS = {
    "agy-bridge": {
        "gemini-4-argon-high",
        "gemini-4-argon-medium",
        "gemini-3.8-flash-high",
        "gemini-3.8-flash-medium",
        "gemini-3.8-flash-low",
    },
    "claude-p-bridge": {"claude-opus-5-5-high", "claude-sonnet-5-5-xhigh"},
}
AGY_EFFORTS = {
    "off": None,
    "low": "low",
    "medium": "medium",
    "high": "high",
    "xhigh": "high",
    "max": "high",
}


class _ProfileSafeLoader(yaml.SafeLoader):
    """Читать выражения DSH !!js как строки без исполнения."""


_ProfileSafeLoader.add_constructor(
    "tag:yaml.org,2002:js", lambda loader, node: loader.construct_scalar(node)
)


def _parse_profile(content: str) -> dict:
    """Разобрать patch-список DSH, сохраняя семантику YAML 1.2 для ключа off."""
    # Штатные !!js проверяем как строки только в памяти, без исполнения выражений.
    entries = {
        entry["id"]: entry.get("config", {})
        for entry in yaml.load(content, Loader=_ProfileSafeLoader)
        if "id" in entry
    }
    # PyYAML использует YAML 1.1 и читает некавыченный ключ off как False.
    for provider in entries["llm-pi-ai"]["providers"].values():
        for model in provider.get("models") or ():
            efforts = model.get("reasoningEfforts", {})
            if False in efforts:
                efforts["off"] = efforts.pop(False)
    return entries


def _assert_deduplicated_profile(entries: dict) -> None:
    providers = entries["llm-pi-ai"]["providers"]
    agy_models = providers["agy-bridge"]["models"]
    assert [model["id"] for model in agy_models] == list(AGY_MODELS)
    assert all(model["reasoningEfforts"] == AGY_EFFORTS for model in agy_models)
    allowed = entries["subagent-model-selection-settings"]["allowedModels"]
    for provider, removed in REMOVED_MODELS.items():
        assert not removed & {model["id"] for model in providers[provider]["models"]}
        assert not removed & {
            model["model"] for model in allowed if model["provider"] == provider
        }
    claude = {model["id"]: model for model in providers["claude-p-bridge"]["models"]}
    assert "claude-haiku-5-5" in claude
    for model in ("claude-opus-5-5", "claude-sonnet-5-5"):
        efforts = claude[model]["reasoningEfforts"]
        assert efforts.get("low") == "low"
        assert efforts.get("medium") == "medium"
        assert efforts.get("high") == "high"
    assert claude["claude-sonnet-5-5"]["reasoningEfforts"].get("xhigh") == "xhigh"


@pytest.mark.parametrize("profile", ["desktop", "web"])
def test_dsh_profile_models_are_deduplicated(profile: str) -> None:
    path = Path.home() / ".dsh" / "profiles" / profile / "cordis.patch.yml"
    if not path.exists():
        pytest.skip(f"{path} отсутствует в чистом CI; парсер проверяется фикстурой")
    _assert_deduplicated_profile(_parse_profile(path.read_text(encoding="utf-8")))


def test_dsh_profile_parser_fixture() -> None:
    content = """
- insert:
    - id: platform-plugin
      disabled: !!js process.platform === 'win32'
- id: parser-fixture
  config:
    literal: 'use !!js here'
    expression: !!js process.platform === 'win32'
- id: llm-pi-ai
  config:
    providers:
      empty-provider: {}
      agy-bridge:
        models:
          - id: gemini-4-argon
            reasoningEfforts: &agy {off: null, low: low, medium: medium, high: high, xhigh: high, max: high}
          - id: gemini-3.8-flash
            reasoningEfforts: *agy
      claude-p-bridge:
        models:
          - id: claude-opus-5-5
            reasoningEfforts: {off: null, low: low, medium: medium, high: high, max: max}
          - id: claude-sonnet-5-5
            reasoningEfforts: {off: null, low: low, medium: medium, high: high, xhigh: xhigh, max: max}
          - id: claude-haiku-5-5
- id: subagent-model-selection-settings
  config:
    allowedModels:
      - {provider: agy-bridge, model: gemini-4-argon}
      - {provider: agy-bridge, model: gemini-3.8-flash}
      - {provider: claude-p-bridge, model: claude-opus-5-5}
      - {provider: claude-p-bridge, model: claude-sonnet-5-5}
      - {provider: claude-p-bridge, model: claude-haiku-5-5}
"""
    entries = _parse_profile(content)
    assert entries["parser-fixture"]["literal"] == "use !!js here"
    assert entries["parser-fixture"]["expression"] == "process.platform === 'win32'"
    _assert_deduplicated_profile(entries)

    entries = _parse_profile(content)
    entries["llm-pi-ai"]["providers"]["agy-bridge"]["models"].append(
        {"id": "gemini-3.8-flash-high", "reasoningEfforts": AGY_EFFORTS.copy()}
    )
    with pytest.raises(AssertionError):
        _assert_deduplicated_profile(entries)

    entries = _parse_profile(content)
    agy_models = entries["llm-pi-ai"]["providers"]["agy-bridge"]["models"]
    flash = next(model for model in agy_models if model["id"] == "gemini-3.8-flash")
    flash["reasoningEfforts"] = {**flash["reasoningEfforts"], "medium": "high"}
    with pytest.raises(AssertionError):
        _assert_deduplicated_profile(entries)


def test_root_fleet_agy_models_efforts() -> None:
    fleet = json.loads((ROOT / "fleet.json").read_text(encoding="utf-8"))
    models = {item["id"]: item for item in fleet["models"]}
    for model in AGY_MODELS:
        assert models[model]["efforts"] == ["low", "medium", "high"]


def test_web_profile_registers_persona_suffix_plugin() -> None:
    path = Path.home() / ".dsh" / "profiles" / "web" / "cordis.patch.yml"
    if not path.exists():
        pytest.skip(f"{path} отсутствует в чистом CI")
    assert "deployment:persona-suffix" in _parse_profile(
        path.read_text(encoding="utf-8")
    )


class DshProfileConfigTests(unittest.TestCase):
    def test_cordis_patch_yml_persona_suffix_does_not_contain_volatile_cwd(
        self,
    ) -> None:
        patch_path = Path.home() / ".dsh" / "profiles" / "web" / "cordis.patch.yml"
        if not patch_path.exists():
            self.skipTest(f"{patch_path} is not present on this machine")

        content = patch_path.read_text(encoding="utf-8")
        self.assertIn("id: deployment:persona-suffix", content)
        self.assertNotIn(
            "{{cwd}}",
            content,
            "cordis.patch.yml must not inject volatile {{cwd}} into persona-suffix",
        )


if __name__ == "__main__":
    unittest.main()
