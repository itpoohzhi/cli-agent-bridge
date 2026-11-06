"""Регрессии smoke_models: путь fleet.json, отсутствие эвристик семейства/эффорта по имени модели."""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "smoke_models.py"
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _load():
    spec = importlib.util.spec_from_file_location("smoke_models_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["smoke_models_under_test"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def sm(monkeypatch):
    monkeypatch.delenv("BRIDGE_FLEET_PATH", raising=False)
    monkeypatch.delenv("DROID_DSH_BRIDGE_FLEET", raising=False)
    module = _load()
    module._load_fleet_config.cache_clear()
    yield module
    module._load_fleet_config.cache_clear()


def test_load_fleet_config_reads_repo_fleet_json(sm):
    models, aliases = sm._load_fleet_config()
    expected = {
        m["id"] for m in json.loads((REPO / "fleet.json").read_text())["models"]
    }
    assert models and set(models) == expected
    assert isinstance(aliases, dict)


def test_load_fleet_config_env_precedence(sm, tmp_path, monkeypatch):
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    first.write_text(
        json.dumps({"models": [{"id": "only-a"}], "aliases": {"x": "only-a"}})
    )
    second.write_text(json.dumps({"models": [{"id": "only-b"}]}))
    monkeypatch.setenv("DROID_DSH_BRIDGE_FLEET", str(second))
    monkeypatch.setenv("BRIDGE_FLEET_PATH", str(first))
    sm._load_fleet_config.cache_clear()
    models, aliases = sm._load_fleet_config()
    assert models == frozenset({"only-a"}) and aliases == {"x": "only-a"}
    monkeypatch.delenv("BRIDGE_FLEET_PATH")
    sm._load_fleet_config.cache_clear()
    assert sm._load_fleet_config()[0] == frozenset({"only-b"})


def test_build_payload_uses_fleet_alias(sm, tmp_path, monkeypatch):
    fleet = tmp_path / "fleet.json"
    fleet.write_text(
        json.dumps(
            {"models": [{"id": "real-1"}], "aliases": {"short": {"model": "real-1"}}}
        )
    )
    monkeypatch.setenv("BRIDGE_FLEET_PATH", str(fleet))
    sm._load_fleet_config.cache_clear()
    assert sm.build_bridge_payload("short")["model"] == "real-1"
    assert sm.build_bridge_payload("real-1")["model"] == "real-1"


def test_no_vendor_prefix_heuristics_in_source():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    banned = ("claude-", "gpt-", "gemini-", "muse-", "deepseek")
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if any(
                node.value.lower().startswith(b) or node.value.lower() == b
                for b in banned
            ):
                hits.append(node.value)
    assert not hits, hits
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "_family_for_model" not in names


MODELS_MD = """\
### Роль — тест

| Модель | Family | Effort |
|---|---|---|
| `deepseek-v4.1-flash` | DeepSeek | `high` / `off` |
| `gemini-3.8-flash` | Google | `high` |
| `custom-x` | Acme | `low` |
"""


def test_models_md_family_from_cell_and_no_effort_name_overrides(
    sm, tmp_path, monkeypatch
):
    path = tmp_path / "models.md"
    path.write_text(MODELS_MD, encoding="utf-8")
    monkeypatch.delenv("BRIDGE_SMOKE_EFFORT_OVERRIDES", raising=False)
    monkeypatch.setenv("BRIDGE_STATE_DIR", str(tmp_path / "state"))
    entries = {e.model_id: e for e in sm.parse_models_md(path)}
    assert entries["deepseek-v4.1-flash"].family == "DeepSeek"
    assert (
        entries["deepseek-v4.1-flash"].effort == "high"
    )  # без хардкод-override -> off
    assert entries["gemini-3.8-flash"].effort == "high"
    assert entries["custom-x"].family == "Acme"


def test_effort_overrides_are_data_driven(sm, tmp_path, monkeypatch):
    path = tmp_path / "models.md"
    path.write_text(MODELS_MD, encoding="utf-8")
    monkeypatch.setenv(
        "BRIDGE_SMOKE_EFFORT_OVERRIDES", json.dumps({"gemini-3.8-flash": "medium"})
    )
    entries = {e.model_id: e for e in sm.parse_models_md(path)}
    assert entries["gemini-3.8-flash"].effort == "medium"
    assert entries["custom-x"].effort == "low"


def test_family_from_catalog_sidecar_wins(sm, tmp_path, monkeypatch):
    path = tmp_path / "models.md"
    path.write_text(MODELS_MD, encoding="utf-8")
    lock = tmp_path / "catalog.lock.json"
    lock.write_text(json.dumps({"models": {"custom-x": {"family": "FromCatalog"}}}))
    monkeypatch.setenv("BRIDGE_CATALOG_LOCK", str(lock))
    entries = {e.model_id: e for e in sm.parse_models_md(path)}
    assert entries["custom-x"].family == "FromCatalog"
    assert entries["gemini-3.8-flash"].family == "Google"
