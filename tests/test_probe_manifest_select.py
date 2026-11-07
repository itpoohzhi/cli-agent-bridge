from __future__ import annotations

# Прямые детерминированные проверки core/probe_manifest_select.py (`from core import probe_manifest_select`).

import sys
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import probe_manifest_select as pms  # noqa: E402
from core.provider_manifest import (  # noqa: E402
    BridgeTransport,
    DiscoveryConfig,
    ModelRule,
    ProviderManifest,
    TransportConfig,
)


def _manifest(
    pid: str,
    priority: int = 100,
    bridge: bool = True,
    enabled: bool = True,
    **claim: tuple[str, ...],
) -> ProviderManifest:
    """`claim`: `static` / `include` / `exclude` / `overrides` — чем манифест заявляет модель."""
    return ProviderManifest(
        provider_id=pid,
        kind="k",
        owned_by="o",
        enabled=enabled,
        priority=priority,
        transport=TransportConfig(bridge=BridgeTransport() if bridge else None),
        discovery=DiscoveryConfig(
            static=claim.get("static", ()),
            include=claim.get("include", ()),
            exclude=claim.get("exclude", ()),
        ),
        models_overrides=tuple(ModelRule(m) for m in claim.get("overrides", ())),
    )


def _pick(
    manifests: list[ProviderManifest], model: str, provider: str | None = None
) -> str | None:
    picked = pms.select_manifest(manifests, model, provider)
    assert (picked.manifest is None) == (picked.problem is not None)
    return picked.manifest.provider_id if picked.manifest else None


@pytest.mark.parametrize(
    "claim",
    [
        {"static": ("m-1",)},
        {"overrides": ("m-1",)},
        {"include": ("m-*",)},
    ],
)
def test_each_discovery_source_claims_model(claim: dict[str, Any]) -> None:
    manifests = [_manifest("a", **claim), _manifest("b", static=("other",))]
    assert _pick(manifests, "m-1") == "a"
    assert _pick(manifests, "zzz") is None


def test_include_glob_is_case_sensitive_and_unclaimed_model_has_problem() -> None:
    assert _pick([_manifest("a", include=("M-*",))], "m-1") is None
    missing = pms.select_manifest([_manifest("a", static=("m",))], "x", None)
    assert (missing.manifest, missing.problem) == (None, "provider_not_found")
    assert pms.select_manifest([], "x", "a").problem == "provider_not_found"


def test_explicit_provider_wins_over_claims() -> None:
    manifests = [_manifest("a", static=("m",)), _manifest("b", priority=500)]
    assert _pick(manifests, "m", "b") == "b"
    assert _pick(manifests, "m", "missing") is None
    assert _pick(manifests, "m", "") == "a"


def test_bridged_provider_beats_better_priority_direct_only() -> None:
    direct = _manifest("d", priority=1, bridge=False, static=("m",))
    bridged = _manifest("b", priority=50, static=("m",))
    assert _pick([direct, bridged], "m") == "b"
    assert _pick([direct], "m") == "d"


def test_tiebreak_is_priority_then_provider_id() -> None:
    low = _manifest("z", priority=10, static=("m",))
    same_a, same_b = (_manifest(pid, priority=20, static=("m",)) for pid in ("a", "b"))
    assert _pick([same_b, same_a, low], "m") == "z"
    assert _pick([same_b, same_a], "m") == "a"
    direct = [
        _manifest(pid, priority=5, bridge=False, static=("m",)) for pid in ("q", "p")
    ]
    assert _pick(direct, "m") == "p"


def test_probe_candidate_defaults_and_immutability() -> None:
    empty = pms.ProbeCandidate()
    assert (empty.manifest, empty.problem) == (None, None)
    attribute = "problem"
    with pytest.raises(FrozenInstanceError):
        setattr(empty, attribute, "x")
    assert not hasattr(empty, "__dict__")


def test_disabled_manifest_never_claims_or_wins() -> None:
    off = _manifest("off", enabled=False, static=("m-1",))
    on = _manifest("on", static=("m-1",))
    assert _pick([off], "m-1") is None
    assert _pick([off, on], "m-1") == "on"
    assert _pick([on, off], "m-1") == "on"
    assert _pick([off], "m-1", "off") is None


def test_excluded_model_glob_is_not_claimed() -> None:
    excluded = _manifest("a", static=("m-1",), exclude=("m-*",))
    fallback = _manifest("b", priority=200, static=("m-1",))
    assert _pick([excluded], "m-1") is None
    assert _pick([excluded, fallback], "m-1") == "b"
    assert _pick([excluded, fallback], "other") is None
