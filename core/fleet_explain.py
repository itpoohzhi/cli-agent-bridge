from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from core.provider_manifest import ProviderManifest


@dataclass(frozen=True, slots=True)
class FleetExplainEntry:
    """Выбор провайдера для модели: primary, alternates и `(priority, provider_id)`."""

    model_id: str
    primary: str
    alternates: tuple[str, ...]
    candidates: tuple[tuple[int, str], ...]

    def to_document(self) -> dict[str, object]:
        """JSON-документ `--explain`."""
        ranked = [{"provider_id": pid, "priority": prio} for prio, pid in self.candidates]
        return {
            "model_id": self.model_id,
            "primary": self.primary,
            "alternates": list(self.alternates),
            "candidates": ranked,
        }


def explain_model(
    sidecar: Mapping[str, object], manifests: Sequence[ProviderManifest], model_id: str
) -> FleetExplainEntry | None:
    """Выбор провайдера из сайдкара; нет модели — None."""
    models = sidecar.get("models")
    entry = models.get(model_id) if isinstance(models, Mapping) else None
    if not isinstance(entry, Mapping):
        return None
    primary = str(entry["provider"])
    raw = entry.get("alternates")
    alternates = tuple(
        str(item["provider"])
        for item in (raw if isinstance(raw, Sequence) else ())
        if isinstance(item, Mapping) and item.get("provider")
    )
    priority = {m.provider_id: m.priority for m in manifests}
    ranked = sorted((priority.get(pid, -1), pid) for pid in (primary, *alternates))
    return FleetExplainEntry(model_id, primary, alternates, tuple(ranked))
