"""Согласованность лимита Muse между манифестом провайдера и fleet-каталогом."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapters import ADAPTER_KINDS
from core.provider_manifest import load_manifests, providers_dir, validate_manifest


ROOT = Path(__file__).resolve().parents[1]


def test_shipped_muse_concurrency_matches_fleet_catalog() -> None:
    loaded = load_manifests(providers_dir(), ADAPTER_KINDS)
    muse = next(item for item in loaded.manifests if item.provider_id == "muse")
    fleet = json.loads((ROOT / "fleet.json").read_text(encoding="utf-8"))
    assert muse.limits.max_concurrent == 8
    assert fleet["backends"]["muse"]["max_concurrent"] == 8


@pytest.mark.parametrize("max_concurrent", (2, 8, 32))
def test_muse_max_concurrent_has_no_kind_ceiling(max_concurrent: int) -> None:
    doc = {
        "manifest_version": 1,
        "provider_id": "mus",
        "kind": "muse",
        "owned_by": "m",
        "limits": {"max_concurrent": max_concurrent},
        "fingerprint": {"binary_path": "~/.local/bin/muse"},
    }
    result = validate_manifest(doc, ADAPTER_KINDS, filename="mus.yaml")
    assert result.errors == ()
