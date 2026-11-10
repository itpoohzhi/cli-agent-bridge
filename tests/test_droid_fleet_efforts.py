"""Регрессии подписочного каталога Factory и маршрутизации удалённых моделей.

Эталон: https://docs.factory.com/models.md (проверено 2026-11-07),
подтверждённый read-back установленного Droid при initialize_session.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TypedDict, cast

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.droid_probe_config import load_droid_probe_targets  # noqa: E402


class _EffortConfig(TypedDict):
    """Проверяемая часть конфигурации уровней модели."""

    efforts: list[str]
    default_effort: str


class _FleetModel(_EffortConfig):
    """Запись каталога с идентификатором модели."""

    id: str


class _FleetConfig(TypedDict):
    """Секция моделей в fleet.json."""

    models: list[_FleetModel]


class _DroidManifest(TypedDict):
    """Переопределения моделей провайдера Droid."""

    models_overrides: dict[str, _EffortConfig]


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("claude-sonnet-5-5", ["low", "medium", "high", "max"]),
        ("gemini-3.8-flash", ["low", "medium", "high"]),
        ("gpt-6.1-sol", ["low", "medium", "high"]),
    ],
)
def test_published_efforts_match_factory_capabilities(
    model: str, expected: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Оба каталога публикуют только реальные уровни, и все они квалифицируются."""
    monkeypatch.delenv("DROID_EXTRA_PROBE_MODELS", raising=False)
    fleet = cast(
        _FleetConfig,
        json.loads((ROOT / "fleet.json").read_text(encoding="utf-8")),
    )
    manifest = cast(
        _DroidManifest,
        yaml.safe_load(
            (ROOT / "providers.d" / "droid.yaml").read_text(encoding="utf-8")
        ),
    )
    configured = next(item for item in fleet["models"] if item["id"] == model)
    override = manifest["models_overrides"][model]
    assert configured["efforts"] == expected
    assert override["efforts"] == expected
    assert configured["default_effort"] == override["default_effort"]
    assert configured["default_effort"] in expected
    targets = load_droid_probe_targets(ROOT / "fleet.json")
    assert {target.effort for target in targets if target.model == model} == set(
        expected
    )


def test_removed_droid_models_absent_or_routed_via_opencode_go() -> None:
    """Удалённые модели не возвращаются в Droid, а DeepSeek остаётся в Go."""
    fleet = cast(
        _FleetConfig,
        json.loads((ROOT / "fleet.json").read_text(encoding="utf-8")),
    )
    droid_manifest = cast(
        _DroidManifest,
        yaml.safe_load(
            (ROOT / "providers.d" / "droid.yaml").read_text(encoding="utf-8")
        ),
    )
    go_manifest = cast(
        _DroidManifest,
        yaml.safe_load(
            (ROOT / "providers.d" / "opencode-go.yaml").read_text(encoding="utf-8")
        ),
    )
    model_ids = {model["id"] for model in fleet["models"]}
    assert "kimi-k3.1-pro" not in model_ids
    assert "kimi-k3.1-pro" not in droid_manifest["models_overrides"]
    assert "deepseek-v4.1-flash" in model_ids
    assert any(m["id"] == "deepseek-v4.1-flash" and m.get("backend") == "opencode-go" for m in fleet["models"])
    assert "deepseek-v4.1-flash" not in droid_manifest["models_overrides"]
    deepseek = go_manifest["models_overrides"]["deepseek-v4.1-flash"]
    assert deepseek["efforts"] == ["off", "low", "high", "max"]
    assert deepseek["default_effort"] == "off"
