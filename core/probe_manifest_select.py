from __future__ import annotations

import fnmatch
from collections.abc import Sequence
from dataclasses import dataclass

from core.provider_manifest import ProviderManifest


@dataclass(frozen=True, slots=True)
class ProbeCandidate:
    """Манифест либо причина отказа."""

    manifest: ProviderManifest | None = None
    problem: str | None = None


def _lists_model(manifest: ProviderManifest, model_id: str) -> bool:
    """Модель в `static` или под `include`."""
    cfg = manifest.discovery
    return model_id in cfg.static or any(fnmatch.fnmatchcase(model_id, g) for g in cfg.include)


def _claims_model(manifest: ProviderManifest, model_id: str) -> bool:
    """Активный манифест заявляет модель."""
    return manifest.enabled and not any(fnmatch.fnmatchcase(model_id, g) for g in manifest.discovery.exclude) and (_lists_model(manifest, model_id) or manifest.rule_for(model_id) is not None)


def select_manifest(
    manifests: Sequence[ProviderManifest],
    model_id: str,
    provider_id: str | None,
    *,
    strict_ambiguous: bool = False,
) -> ProbeCandidate:
    """`--provider` по id, иначе лучший; `strict_ambiguous` — прежний CLI."""
    claims = _lists_model if strict_ambiguous else _claims_model
    pool = [m for m in manifests if (m.provider_id == provider_id if provider_id else claims(m, model_id))]
    if strict_ambiguous:
        return (
            ProbeCandidate(None, "provider_not_found"),
            ProbeCandidate(pool[0] if pool else None, None),
            ProbeCandidate(None, "provider_ambiguous"),
        )[min(len(pool[:1] if provider_id else pool), 2)]
    best = min(pool, key=lambda m: (m.transport.bridge is None, m.priority, m.provider_id), default=None)
    return ProbeCandidate(best, None if best else "provider_not_found")
