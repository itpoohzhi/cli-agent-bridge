from __future__ import annotations

# `fleet_compile --explain`: разбор сайдкара как внешнего JSON (fail-closed, без падений).

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters import ADAPTER_KINDS  # noqa: E402
from core.fleet_explain import FleetExplainEntry, explain_model  # noqa: E402
from core.provider_manifest import load_manifests  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = load_manifests(ROOT / "providers.d", ADAPTER_KINDS).manifests


def test_explain_tolerates_malformed_sidecar() -> None:
    """Сайдкар - внешний JSON: `models` может быть null/списком, а alternates - мусором."""
    for sidecar in ({}, {"models": None}, {"models": ["gpt-6.1-sol"]}):
        assert explain_model(sidecar, MANIFESTS, "gpt-6.1-sol") is None


def test_explain_skips_malformed_alternates() -> None:
    """Не-mapping элементы `alternates` не должны ронять разбор выбора провайдера."""
    broken = {
        "models": {
            "gpt-6.1-sol": {
                "provider": "droid",
                "alternates": ["codex", {"priority": 30}],
            }
        }
    }
    entry = explain_model(broken, MANIFESTS, "gpt-6.1-sol")
    assert isinstance(entry, FleetExplainEntry)
    assert (entry.primary, entry.alternates) == ("droid", ())


def test_explain_orders_candidates_by_priority_then_provider() -> None:
    """Кандидаты - `(priority, provider_id)`; неизвестный манифестам провайдер получает -1."""
    sidecar = {
        "models": {
            "m": {"provider": "b", "alternates": [{"provider": "a"}, {"provider": "z"}]}
        }
    }
    entry = explain_model(sidecar, [], "m")
    assert entry is not None
    assert entry.candidates == ((-1, "a"), (-1, "b"), (-1, "z"))
    assert entry.to_document() == {
        "model_id": "m",
        "primary": "b",
        "alternates": ["a", "z"],
        "candidates": [
            {"provider_id": "a", "priority": -1},
            {"provider_id": "b", "priority": -1},
            {"provider_id": "z", "priority": -1},
        ],
    }
