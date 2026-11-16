from __future__ import annotations

import fnmatch
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar


class _SelectableDiscovery(Protocol):
    """Списки моделей, необходимые для выбора."""

    @property
    def static(self) -> Sequence[str]: ...

    @property
    def include(self) -> Sequence[str]: ...

    @property
    def exclude(self) -> Sequence[str]: ...


class _SelectableTransport(Protocol):
    """Признак наличия мостового транспорта."""

    @property
    def bridge(self) -> object | None: ...


class _SelectableRouting(Protocol):
    """Явный и эффективный вес владельца модели."""

    @property
    def weight(self) -> int | None: ...

    @property
    def effective_weight(self) -> int: ...


class _SelectableManifest(Protocol):
    """Структурный контракт выбора без зависимости от загрузчика."""

    @property
    def provider_id(self) -> str: ...

    @property
    def enabled(self) -> bool: ...

    @property
    def priority(self) -> int: ...

    @property
    def discovery(self) -> _SelectableDiscovery: ...

    @property
    def transport(self) -> _SelectableTransport: ...

    @property
    def routing(self) -> _SelectableRouting: ...

    def rule_for(self, model_id: str) -> object | None: ...


M = TypeVar("M", bound=_SelectableManifest)


@dataclass(frozen=True, slots=True)
class ProbeCandidate(Generic[M]):
    """Манифест либо причина отказа."""

    manifest: M | None = None
    problem: str | None = None


def _lists_model(manifest: _SelectableManifest, model_id: str) -> bool:
    """Модель в `static` или под `include`."""
    cfg = manifest.discovery
    return model_id in cfg.static or any(
        fnmatch.fnmatchcase(model_id, g) for g in cfg.include
    )


def _claims_model(manifest: _SelectableManifest, model_id: str) -> bool:
    """Активный манифест заявляет модель."""
    return (
        manifest.enabled
        and not any(
            fnmatch.fnmatchcase(model_id, g) for g in manifest.discovery.exclude
        )
        and (
            _lists_model(manifest, model_id) or manifest.rule_for(model_id) is not None
        )
    )


def _best_manifest(pool: Sequence[M]) -> M | None:
    """Явный вес bridge включает тот же порядок владельцев, что у компилятора."""
    if any(
        m.transport.bridge is not None and m.routing.weight is not None for m in pool
    ):
        return min(
            pool,
            key=lambda m: (
                m.transport.bridge is None,
                -m.routing.effective_weight,
                m.priority,
                m.provider_id,
            ),
            default=None,
        )
    return min(
        pool,
        key=lambda m: (m.transport.bridge is None, m.priority, m.provider_id),
        default=None,
    )


def select_manifest(
    manifests: Sequence[M],
    model_id: str,
    provider_id: str | None,
    *,
    strict_ambiguous: bool = False,
) -> ProbeCandidate[M]:
    """`--provider` по id, иначе лучший; `strict_ambiguous` — прежний CLI."""
    claims = _lists_model if strict_ambiguous else _claims_model
    pool = [
        m
        for m in manifests
        if (m.provider_id == provider_id if provider_id else claims(m, model_id))
    ]
    if strict_ambiguous:
        return (
            ProbeCandidate[M](None, "provider_not_found"),
            ProbeCandidate[M](pool[0] if pool else None, None),
            ProbeCandidate[M](None, "provider_ambiguous"),
        )[min(len(pool[:1] if provider_id else pool), 2)]
    best = _best_manifest(pool)
    return ProbeCandidate(best, None if best else "provider_not_found")
