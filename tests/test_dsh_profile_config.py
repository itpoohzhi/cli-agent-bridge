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
if str(ROOT) not in sys.path:  # изолированный прогон файла: conftest импортирует `core`
    sys.path.insert(0, str(ROOT))
GOOGLE_MODELS = (
    "gemini-4-hydrogen",
    "gemini-4-carbon",
    "gemini-4-argon",
    "gemini-3.8-flash",
)
AGY_MODELS = ("gemini-4-argon", "gemini-3.8-flash")
GOOGLE_BRIDGES = {
    "cli-agent-bridge": ("http://127.0.0.1:9882/v1", "BRIDGE_KEY"),
    "agy-bridge": ("http://127.0.0.1:9887/v1", "AGY_BRIDGE_KEY"),
}
GOOGLE_CONTEXT_WINDOW = 1048576
GOOGLE_MAX_TOKENS = 65536
SUFFIX_ALIASES = {
    f"{model}-{effort}"
    for model in GOOGLE_MODELS
    for effort in ("low", "medium", "high", "xhigh")
}
REMOVED_MODELS = {
    "agy-bridge": SUFFIX_ALIASES,
    "cli-agent-bridge": SUFFIX_ALIASES,
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
HYDROGEN_EFFORTS = {**AGY_EFFORTS, "xhigh": "xhigh", "max": "xhigh"}


def _expected_efforts(model_id: str) -> dict:
    return HYDROGEN_EFFORTS if model_id == "gemini-4-hydrogen" else AGY_EFFORTS


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


def _assert_google_models(entries: dict, *, check_allowed: bool) -> None:
    """Проверить оба способа подключения всех 4 моделей Google Gemini."""
    providers = entries["llm-pi-ai"]["providers"]
    for name, (base_url, api_key_env) in GOOGLE_BRIDGES.items():
        provider = providers[name]
        assert provider["baseURL"] == base_url, name
        assert provider["apiKeyEnv"] == api_key_env, name
        ids = [model["id"] for model in provider["models"]]
        assert len(ids) == len(set(ids)), f"дубли id в {name}"
        assert not SUFFIX_ALIASES & set(ids), f"суффиксные алиасы в {name}"
        models = {model["id"]: model for model in provider["models"]}
        for model_id in GOOGLE_MODELS:
            model = models[model_id]
            assert model["contextWindow"] == GOOGLE_CONTEXT_WINDOW, (name, model_id)
            assert model["maxTokens"] == GOOGLE_MAX_TOKENS, (name, model_id)
            assert "image" in model["input"], (name, model_id)
            assert model["reasoningEfforts"] == _expected_efforts(model_id), (
                name,
                model_id,
            )
    assert [
        model["id"] for model in providers["agy-bridge"]["models"]
    ].count("gemini-4-hydrogen") == 1
    if not check_allowed:
        return
    allowed = entries["subagent-model-selection-settings"]["allowedModels"]
    pairs = [(item["provider"], item["model"]) for item in allowed]
    assert len(pairs) == len(set(pairs)), "дубли (provider, model) в allowedModels"
    for name in GOOGLE_BRIDGES:
        for model_id in GOOGLE_MODELS:
            assert (name, model_id) in pairs, (name, model_id)
        assert not SUFFIX_ALIASES & {m for p, m in pairs if p == name}


def _assert_deduplicated_profile(entries: dict, *, check_allowed: bool = True) -> None:
    providers = entries["llm-pi-ai"]["providers"]
    _assert_google_models(entries, check_allowed=check_allowed)
    if not check_allowed:
        return
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


def test_dsh_headless_profile_google_models() -> None:
    path = Path.home() / ".dsh" / "profiles" / "headless" / "cordis.patch.yml"
    if not path.exists():
        pytest.skip(f"{path} отсутствует в чистом CI")
    entries = _parse_profile(path.read_text(encoding="utf-8"))
    # В headless нет subagent-model-selection-settings: проверяем только провайдеры.
    _assert_google_models(entries, check_allowed=False)


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
      cli-agent-bridge:
        baseURL: http://127.0.0.1:9882/v1
        apiKeyEnv: BRIDGE_KEY
        models:
          - id: gemini-4-hydrogen
            contextWindow: 1048576
            maxTokens: 65536
            input: [text, image]
            reasoningEfforts: {off: null, low: low, medium: medium, high: high, xhigh: xhigh, max: xhigh}
          - id: gemini-4-carbon
            contextWindow: 1048576
            maxTokens: 65536
            input: [text, image]
            reasoningEfforts: {off: null, low: low, medium: medium, high: high, xhigh: high, max: high}
          - id: gemini-4-argon
            contextWindow: 1048576
            maxTokens: 65536
            input: [text, image]
            reasoningEfforts: {off: null, low: low, medium: medium, high: high, xhigh: high, max: high}
          - id: gemini-3.8-flash
            contextWindow: 1048576
            maxTokens: 65536
            input: [text, image]
            reasoningEfforts: {off: null, low: low, medium: medium, high: high, xhigh: high, max: high}
      agy-bridge:
        baseURL: http://127.0.0.1:9887/v1
        apiKeyEnv: AGY_BRIDGE_KEY
        models:
          - id: gemini-4-hydrogen
            contextWindow: 1048576
            maxTokens: 65536
            input: [text, image]
            reasoningEfforts: {off: null, low: low, medium: medium, high: high, xhigh: xhigh, max: xhigh}
          - id: gemini-4-carbon
            contextWindow: 1048576
            maxTokens: 65536
            input: [text, image]
            reasoningEfforts: {off: null, low: low, medium: medium, high: high, xhigh: high, max: high}
          - id: gemini-4-argon
            contextWindow: 1048576
            maxTokens: 65536
            input: [text, image]
            reasoningEfforts: {off: null, low: low, medium: medium, high: high, xhigh: high, max: high}
          - id: gemini-3.8-flash
            contextWindow: 1048576
            maxTokens: 65536
            input: [text, image]
            reasoningEfforts: {off: null, low: low, medium: medium, high: high, xhigh: high, max: high}
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
      - {provider: cli-agent-bridge, model: gemini-4-hydrogen}
      - {provider: cli-agent-bridge, model: gemini-4-carbon}
      - {provider: cli-agent-bridge, model: gemini-4-argon}
      - {provider: cli-agent-bridge, model: gemini-3.8-flash}
      - {provider: agy-bridge, model: gemini-4-hydrogen}
      - {provider: agy-bridge, model: gemini-4-carbon}
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

    for bridge in GOOGLE_BRIDGES:
        entries = _parse_profile(content)
        entries["llm-pi-ai"]["providers"][bridge]["models"].append(
            {"id": "gemini-4-hydrogen-high", "reasoningEfforts": AGY_EFFORTS.copy()}
        )
        with pytest.raises(AssertionError):
            _assert_deduplicated_profile(entries)

        entries = _parse_profile(content)
        models = entries["llm-pi-ai"]["providers"][bridge]["models"]
        flash = next(model for model in models if model["id"] == "gemini-3.8-flash")
        flash["reasoningEfforts"] = {**flash["reasoningEfforts"], "medium": "high"}
        with pytest.raises(AssertionError):
            _assert_deduplicated_profile(entries)

        entries = _parse_profile(content)
        models = entries["llm-pi-ai"]["providers"][bridge]["models"]
        hydrogen = next(m for m in models if m["id"] == "gemini-4-hydrogen")
        hydrogen["reasoningEfforts"] = {**hydrogen["reasoningEfforts"], "xhigh": "high"}
        with pytest.raises(AssertionError):
            _assert_deduplicated_profile(entries)

        entries = _parse_profile(content)
        entries["llm-pi-ai"]["providers"][bridge]["baseURL"] = "http://127.0.0.1:1/v1"
        with pytest.raises(AssertionError):
            _assert_deduplicated_profile(entries)

        entries = _parse_profile(content)
        allowed = entries["subagent-model-selection-settings"]["allowedModels"]
        allowed[:] = [
            item
            for item in allowed
            if (item["provider"], item["model"]) != (bridge, "gemini-4-hydrogen")
        ]
        with pytest.raises(AssertionError):
            _assert_deduplicated_profile(entries)

    entries = _parse_profile(content)
    allowed = entries["subagent-model-selection-settings"]["allowedModels"]
    allowed.append(dict(allowed[0]))
    with pytest.raises(AssertionError):
        _assert_deduplicated_profile(entries)


def _contract_profile_entries() -> dict:
    """Профиль провайдеров, выведенный из контракта репозитория (без чтения `~/.dsh`)."""
    bridge_fleet = json.loads(
        (ROOT / "bridges" / "agy-bridge" / "fleet.json").read_text(encoding="utf-8")
    )
    catalog = {item["id"]: item for item in bridge_fleet["models"]}
    models = []
    for model_id in GOOGLE_MODELS:
        item = catalog[model_id]
        top = item["efforts"][-1]
        ladder = {"off": None, **{e: e for e in item["efforts"]}}
        ladder.update({e: top for e in ("xhigh", "max") if e not in ladder})
        models.append(
            {
                "id": model_id,
                "contextWindow": item["context_window"],
                "maxTokens": item["max_tokens"],
                "input": list(item["input"]),
                "reasoningEfforts": ladder,
            }
        )
    providers = {
        name: {
            "baseURL": base_url,
            "apiKeyEnv": api_key_env,
            "models": [dict(m, reasoningEfforts=dict(m["reasoningEfforts"])) for m in models],
        }
        for name, (base_url, api_key_env) in GOOGLE_BRIDGES.items()
    }
    allowed = [
        {"provider": name, "model": model_id}
        for name in GOOGLE_BRIDGES
        for model_id in GOOGLE_MODELS
    ]
    return {
        "llm-pi-ai": {"providers": providers},
        "subagent-model-selection-settings": {"allowedModels": allowed},
    }


def test_dsh_provider_contract_is_host_independent() -> None:
    """Структура провайдеров cli-agent-bridge/agy-bridge выводится из fleet.json репозитория."""
    entries = _contract_profile_entries()
    _assert_google_models(entries, check_allowed=True)
    providers = entries["llm-pi-ai"]["providers"]
    assert set(providers) == set(GOOGLE_BRIDGES)
    for provider in providers.values():
        by_id = {m["id"]: m for m in provider["models"]}
        assert by_id["gemini-4-hydrogen"]["reasoningEfforts"]["xhigh"] == "xhigh"
        assert by_id["gemini-4-hydrogen"]["reasoningEfforts"]["max"] == "xhigh"
        for sibling in ("gemini-4-carbon", "gemini-4-argon", "gemini-3.8-flash"):
            assert by_id[sibling]["reasoningEfforts"]["xhigh"] == "high", sibling
            assert by_id[sibling]["reasoningEfforts"]["max"] == "high", sibling


def test_dsh_provider_contract_detects_drift() -> None:
    for bridge in GOOGLE_BRIDGES:
        entries = _contract_profile_entries()
        entries["llm-pi-ai"]["providers"][bridge]["models"][0]["input"] = ["text"]
        with pytest.raises(AssertionError):
            _assert_google_models(entries, check_allowed=True)

        entries = _contract_profile_entries()
        allowed = entries["subagent-model-selection-settings"]["allowedModels"]
        allowed[:] = [a for a in allowed if (a["provider"], a["model"]) != (bridge, "gemini-4-carbon")]
        with pytest.raises(AssertionError):
            _assert_google_models(entries, check_allowed=True)


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
