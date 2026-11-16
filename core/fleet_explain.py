from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from core.catalog_routes import RouteProvider, provider_routing


@dataclass(frozen=True, slots=True)
class FleetExplainEntry:
    """Выбор провайдера: совместимые пары priority/id и явные веса маршрутов."""

    model_id: str
    primary: str
    alternates: tuple[str, ...]
    candidates: tuple[tuple[int, str], ...]
    weights: tuple[tuple[str, int], ...] = ()

    def to_document(self) -> dict[str, object]:
        """JSON-документ `--explain`."""
        ranked: list[dict[str, object]] = []
        weights = dict(self.weights)
        for prio, pid in self.candidates:
            candidate: dict[str, object] = {"provider_id": pid, "priority": prio}
            if pid in weights:
                candidate["weight"] = weights[pid]
            ranked.append(candidate)
        return {
            "model_id": self.model_id,
            "primary": self.primary,
            "alternates": list(self.alternates),
            "candidates": ranked,
        }


def _alternates(raw: object, primary: str) -> tuple[str, ...]:
    """Пропускает повреждённые элементы, дубликаты и повтор primary."""
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        return ()
    providers = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        pid = item.get("provider")
        if isinstance(pid, str) and pid and pid != primary:
            providers.append(pid)
    return tuple(dict.fromkeys(providers))


def _rank_candidates(
    providers: tuple[str, ...],
    manifests: Sequence[RouteProvider],
) -> tuple[tuple[tuple[int, str], ...], tuple[tuple[str, int], ...]]:
    """Повторяет порядок owner только для исполнимых взвешенных маршрутов."""
    known = {m.provider_id: m for m in manifests if m.provider_id in providers}
    ranked = [(known[pid].priority if pid in known else -1, pid) for pid in providers]
    weights = _routing_weights(known)
    if weights:
        ranked.sort(
            key=lambda item: (
                item[1] not in weights,
                -weights.get(item[1], 0),
                item[0],
                item[1],
            )
        )
    else:
        ranked.sort()
    return tuple(ranked), tuple(sorted(weights.items()))


def _routing_weights(known: Mapping[str, RouteProvider]) -> dict[str, int]:
    """Disabled и direct-only не участвуют в выборе owner, включая нулевой резерв."""
    eligible = {
        pid: m
        for pid, m in known.items()
        if m.enabled and m.transport.bridge is not None
    }
    if not any(provider_routing(m).weight is not None for m in eligible.values()):
        return {}
    return {pid: provider_routing(m).effective_weight for pid, m in eligible.items()}


def explain_model(
    sidecar: Mapping[str, object], manifests: Sequence[RouteProvider], model_id: str
) -> FleetExplainEntry | None:
    """Выбор провайдера из сайдкара; нет модели — None."""
    models = sidecar.get("models")
    entry = models.get(model_id) if isinstance(models, Mapping) else None
    if not isinstance(entry, Mapping):
        return None
    primary = entry.get("provider")
    if not isinstance(primary, str) or not primary:
        return None
    alternates = _alternates(entry.get("alternates"), primary)
    ranked, weights = _rank_candidates((primary, *alternates), manifests)
    return FleetExplainEntry(model_id, primary, alternates, ranked, weights)
