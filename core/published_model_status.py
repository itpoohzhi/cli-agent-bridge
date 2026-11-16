"""Read-only HTTP-представление доменной доступности, не POST-dispatch guard."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from core import route_eligibility
from core.route_eligibility import EdgeSnapshot, ModelAvailability
from core.route_penalty_state import Phase

_HTTP_OK = 200
_HTTP_UNAVAILABLE = 503


@dataclass(frozen=True, slots=True)
class AvailabilityStatus:
    """Доменный вердикт и его HTTP-код без полномочий на healing."""

    available: bool
    phase: Phase
    reason: str
    http_status: int


@dataclass(frozen=True, slots=True)
class PublishedEdgeStatus:
    """Видимость штрафа конкретного actual edge без lease-токенов."""

    model_id: str
    backend: str
    status: AvailabilityStatus


@dataclass(frozen=True, slots=True)
class PublishedModelStatus:
    """Статус модели с раздельными wire owner и канонической принадлежностью."""

    id: str
    owned_by: str
    canonical_owner: str
    status: AvailabilityStatus
    edges: tuple[PublishedEdgeStatus, ...]


def _http_status(result: ModelAvailability) -> AvailabilityStatus:
    code = _HTTP_OK if result.available else _HTTP_UNAVAILABLE
    return AvailabilityStatus(result.available, result.phase, result.reason, code)


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def project_edge_status(edge: EdgeSnapshot) -> PublishedEdgeStatus:
    """Проецирует готовый snapshot; OPEN/HALF_OPEN не истекают от чтения."""
    result = route_eligibility.evaluate_edge_eligibility(edge)
    return PublishedEdgeStatus(edge.model_id, edge.backend, _http_status(result))


def project_model_status(
    model: Mapping[str, object],
    edges: Iterable[EdgeSnapshot],
    primary_provider_id: str,
) -> PublishedModelStatus:
    """Делегирует домену owner-check и агрегат по одним и тем же actual edges.

    Только статусное представление для GET /v1/models и статусных ручек.
    Не читает tracker/storage/часы, не выбирает маршрут и не управляет lease.
    """
    snapshots = tuple(edges)
    result = route_eligibility.aggregate_model_availability(
        model,
        snapshots,
        primary_provider_id,
    )
    visible = tuple(
        project_edge_status(edge)
        for edge in snapshots
        if edge.model_id == model.get("id")
    )
    return PublishedModelStatus(
        _text(model.get("id")),
        _text(model.get("owned_by")),
        _text(model.get("canonical_owner", model.get("backend"))),
        _http_status(result),
        visible,
    )
