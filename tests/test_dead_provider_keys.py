"""Независимые ожидания credential-слотов без чтения значений секретов."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest

from core.provider_manifest import manifest_files, read_yaml_file
from tests.transport_test_support import semantic_equal

ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = ROOT / "providers.d"
POLICY_SHA = "6fc23e304e870f0d91678a401e784692099e7414e73c904d3e3f769722d3354c"
DEAD_UPSTREAM_NAMES = frozenset({
    "OPENAI_API_KEY", "OPENAI_API_KEY_1", "DEEPSEEK_API_KEY_2", "ANTHROPIC_API_KEY",
})


def _provider(provider_id: str) -> dict[str, Any]:
    """Отсутствующий новый слот — семантическое отсутствие, не ошибка collection."""
    documents = {path.stem: read_yaml_file(path) for path in manifest_files(PROVIDERS)}
    return documents.get(provider_id, {})


def _slot(doc: dict[str, Any]) -> tuple:
    bridge = doc.get("transport", {}).get("bridge", {})
    return (
        doc.get("provider_id"), doc.get("kind"), doc.get("enabled", True),
        doc.get("routing", {}).get("weight"), bridge.get("api_key_env"),
        bridge.get("base_url"), doc.get("limits", {}).get("quota_group"),
        tuple(sorted(doc.get("models_overrides", {}))),
    )


def _credential_names(value: Any) -> set[str]:
    """Ищет только источники credential, не произвольные упоминания в README."""
    if isinstance(value, list):
        return set().union(*(_credential_names(item) for item in value))
    if not isinstance(value, dict):
        return set()
    names: set[str] = set()
    for key, item in value.items():
        if key == "api_key_env" and isinstance(item, str):
            names.add(item)
        elif key == "api_key_ref" and isinstance(item, str) and item.startswith("env:"):
            names.add(item.removeprefix("env:"))
        else:
            names.update(_credential_names(item))
    return names


@pytest.mark.semantic_red("openai_distinct_credential_slots")
@pytest.mark.parametrize("slot", [2, 3])
def test_stage_w2_n_both_models_use_their_own_env_and_quota_slot(slot: int) -> None:
    provider_id = f"openai-key-{slot}"
    doc = _provider(provider_id)
    expected = (
        provider_id, "passthrough", slot != 2, 50, f"OPENAI_API_KEY_{slot}",
        "http://127.0.0.1:10830/sg-openai", provider_id,
        ("gpt-6.1-sol", "gpt-6.1-terra"),
    )
    semantic_equal(_slot(doc), expected, "openai_distinct_credential_slots")
    assert _credential_names(doc) == {f"OPENAI_API_KEY_{slot}"}
    assert doc["allow_base_url"] == [
        {"scheme": "http", "host": "127.0.0.1", "port": 10830, "path_prefix": "/sg-openai"},
    ]
    assert doc["limits"]["max_concurrent"] > 0
    assert doc.get("required", False) is False


@pytest.mark.semantic_red("deepseek_single_live_credential_slot")
def test_stage_w2_o_deepseek_uses_only_its_requested_env_slot() -> None:
    doc = _provider("deepseek-direct")
    expected = (
        "deepseek-direct", "passthrough", False, 0, "DEEPSEEK_API_KEY",
        "http://127.0.0.1:10830/sg-deepseek", "deepseek-direct", ("deepseek-v4.1-flash",),
    )
    semantic_equal(_slot(doc), expected, "deepseek_single_live_credential_slot")
    assert _credential_names(doc) == {"DEEPSEEK_API_KEY"}
    assert doc["allow_base_url"] == [
        {"scheme": "http", "host": "127.0.0.1", "port": 10830, "path_prefix": "/sg-deepseek"},
    ]
    assert doc["limits"]["max_concurrent"] > 0
    assert doc.get("required", False) is False


@pytest.mark.semantic_red("current_models_policy_fingerprint")
def test_stage_w2_o_fleet_header_pins_reviewed_models_policy() -> None:
    header = read_yaml_file(PROVIDERS / "_fleet.yaml")
    policy = header.get("policy_ref", {})
    semantic_equal(policy.get("sha256"), POLICY_SHA, "current_models_policy_fingerprint")
    assert policy["path"] == "~/Мой диск/Context/models.md"


def test_dead_upstream_key_names_are_not_provider_credential_sources() -> None:
    names: set[str] = set()
    for path in manifest_files(PROVIDERS):
        names.update(_credential_names(read_yaml_file(path)))
    assert not names & DEAD_UPSTREAM_NAMES


def test_anthropic_client_placeholder_is_preserved_not_mistaken_for_upstream_auth() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    example = re.search(
        r'export ANTHROPIC_BASE_URL="http://127\.0\.0\.1:9882/v1"\s+'
        r'export ANTHROPIC_API_KEY="your-bridge-key"\s+claude\b',
        text,
    )
    assert example is not None
    assert _credential_names({"client_example": example.group()}) == set()
    assert _credential_names({"transport": {"bridge": {"api_key_env": "ANTHROPIC_API_KEY"}}}) == {
        "ANTHROPIC_API_KEY",
    }


@pytest.mark.parametrize("provider_id,path_prefix", [
    ("openai-key-3", "/sg-openai"),
    ("deepseek-direct", "/sg-deepseek"),
])
@pytest.mark.semantic_red("requested_loopback_provider_boundary")
def test_direct_slot_never_grants_itself_remote_egress(
    provider_id: str, path_prefix: str,
) -> None:
    doc = _provider(provider_id)
    bridge = doc.get("transport", {}).get("bridge", {})
    url = urlsplit(bridge.get("base_url", ""))
    actual = (url.scheme, url.hostname, url.port, url.path, url.username, url.password,
              url.query, url.fragment, doc.get("allow_remote_https", False))
    semantic_equal(
        actual, ("http", "127.0.0.1", 10830, path_prefix, None, None, "", "", False),
        "requested_loopback_provider_boundary",
    )
    assert not doc.get("transport", {}).get("direct")
