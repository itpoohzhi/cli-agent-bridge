from __future__ import annotations

import fnmatch
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from core.provider_manifest import ProviderManifest


@dataclass(frozen=True, slots=True)
class ProbeCandidate:
    """Манифест либо причина отказа: `provider_not_found` / `provider_ambiguous`."""

    manifest: ProviderManifest | None = None
    problem: str | None = None


def _claims_model(manifest: ProviderManifest, model_id: str) -> bool:
    """Активный манифест заявляет модель вне `exclude`."""

    def matches(globs: Iterable[str]) -> bool:
        return any(fnmatch.fnmatchcase(model_id, g) for g in globs)

    cfg = manifest.discovery
    named = model_id in cfg.static or manifest.rule_for(model_id) is not None
    return manifest.enabled and not matches(cfg.exclude) and (named or matches(cfg.include))


def select_manifest(
    manifests: Sequence[ProviderManifest],
    model_id: str,
    provider_id: str | None,
    *,
    strict_ambiguous: bool = False,
) -> ProbeCandidate:
    """`--provider` -> по id; иначе лучший заявивший; `strict_ambiguous` — 2+ -> ambiguous."""
    if provider_id:
        pool = [m for m in manifests if m.provider_id == provider_id]
    else:
        pool = [m for m in manifests if _claims_model(m, model_id)]
    best = min(pool, key=lambda m: (m.transport.bridge is None, m.priority, m.provider_id), default=None)
    problem = None if best else "provider_not_found"
    if strict_ambiguous and not provider_id and len(pool) > 1:
        best, problem = None, "provider_ambiguous"
    return ProbeCandidate(best, problem)
