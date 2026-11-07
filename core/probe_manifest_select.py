from __future__ import annotations

import fnmatch
from collections.abc import Sequence
from dataclasses import dataclass

from core.provider_manifest import ProviderManifest


@dataclass(frozen=True, slots=True)
class ProbeCandidate:
    """Выбранный манифест либо причина отказа `provider_not_found`."""

    manifest: ProviderManifest | None = None
    problem: str | None = None


def _claims_model(manifest: ProviderManifest, model_id: str) -> bool:
    """Модель заявлена активным манифестом: `static`, `include` или overrides вне `exclude`."""
    cfg = manifest.discovery
    excluded = any(fnmatch.fnmatchcase(model_id, g) for g in cfg.exclude)
    named = (model_id in cfg.static, manifest.rule_for(model_id) is not None)
    included = any(fnmatch.fnmatchcase(model_id, g) for g in cfg.include)
    claimed = bool(manifest.enabled) and not excluded and any((*named, included))
    return claimed


def select_manifest(
    manifests: Sequence[ProviderManifest], model_id: str, provider_id: str | None
) -> ProbeCandidate:
    """Манифест по --provider, иначе лучший (bridge, priority, provider_id) среди активных."""
    active = [m for m in manifests if m.enabled]
    by_id = [m for m in active if m.provider_id == provider_id]
    claimed = [m for m in active if _claims_model(m, model_id)]
    matches = by_id if provider_id else claimed
    best = min(
        matches,
        key=lambda m: (m.transport.bridge is None, m.priority, m.provider_id),
        default=None,
    )
    return ProbeCandidate(best, None if best else "provider_not_found")
