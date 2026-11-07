"""Регрессия каталога Factory: DeepSeek и Kimi не принимают medium.

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
        ("deepseek-v4.1-flash", ["off", "low", "high", "max"]),
        ("kimi-k3.1-pro", ["low", "high", "max"]),
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
