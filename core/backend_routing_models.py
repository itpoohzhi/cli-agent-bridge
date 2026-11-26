"""Чистые делегаты проверки и принадлежности моделей транспортам."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import NotRequired, Protocol, TypedDict, TypeVar, cast

from core.fleet_model_validation import FLEET_MODEL_KEYS as FLEET_MODEL_KEYS
from core.fleet_model_validation import normalize_model as normalize_model
from core.fleet_model_validation import validate_proof as validate_proof
from core.routing_schema import RoutingDocument

_Model = TypeVar("_Model")


class CatalogModel(TypedDict):
    """Минимальная проверенная запись для проекции каталога адаптера."""

    id: str
    backend: str
    context_window: NotRequired[int]
    routing: NotRequired[RoutingDocument]


class ModelCatalog(TypedDict):
    """Текущий каталог без копирования состояния в адаптер."""

    models: Mapping[str, CatalogModel]
    order: NotRequired[Sequence[str]]


class _ModelWithId(Protocol):
    @property
    def id(self) -> str: ...


class _CatalogAdapter(Protocol):
    def get_models(self) -> Sequence[_ModelWithId]: ...


_Adapter = TypeVar("_Adapter", bound=_CatalogAdapter)


def safe_path_segments(raw_path: str, decoded_path: str) -> bool:
    """Отсекает обход пути до применения провайдерских разрешений."""
    return all(
        segment not in {".", ".."}
        and not any(token in segment.lower() for token in ("%2e", "%2f", "\\"))
        for path in (raw_path, decoded_path)
        for segment in path.split("/")
    )


def matches_url_policy(base_url: str, policy: str) -> bool:
    """Ошибочная дополнительная политика закрывает допуск, а не расширяет его."""
    try:
        return re.fullmatch(policy, base_url) is not None
    except re.error:
        return False


def catalog_owner(catalog: ModelCatalog, model_id: str) -> str | None:
    """Возвращает канонического владельца, а не первый alternate transport."""
    model = (catalog.get("models") or {}).get(model_id)
    return model["backend"] if model is not None else None


def registry_adapter(
    adapters: Mapping[str, _Adapter],
    catalog_source: Callable[[], Mapping[str, object]] | None,
    model_id: str,
) -> _Adapter | None:
    """Ищет владельца в живом каталоге, сохраняя ручную регистрацию адаптеров."""
    if catalog_source is not None:
        owner = catalog_owner(cast(ModelCatalog, catalog_source()), model_id)
        if owner is not None and owner in adapters:
            return adapters[owner]
    for adapter in adapters.values():
        if any(model.id == model_id for model in adapter.get_models()):
            return adapter
    return None


def _belongs_to_backend(model: CatalogModel, backend_id: str) -> bool:
    routing = model.get("routing")
    if routing is None:
        return model["backend"] == backend_id
    return any(route["backend"] == backend_id for route in routing["routes"])


def catalog_models(
    catalog: ModelCatalog,
    backend_id: str,
    model_factory: Callable[[str, str, int], _Model],
) -> list[_Model]:
    """Проецирует owner и alternate membership, сохраняя порядок и тип DTO."""
    models = catalog.get("models") or {}
    order = catalog.get("order") or list(models)
    return [
        model_factory(
            str(models[mid]["id"]),
            backend_id,
            int(models[mid].get("context_window") or 0),
        )
        for mid in order
        if mid in models and _belongs_to_backend(models[mid], backend_id)
    ]


@dataclass(frozen=True)
class TranscriptItem:
    """Один вход истории для неизменённого Droid-пути."""

    role: str
    text: str
    digest: str
    origin_role: str = ""


@dataclass(frozen=True)
class Transcript:
    """Нормализованная история хода."""

    system: str | None = None
    runnable: bool = True
    items: tuple[TranscriptItem, ...] = ()


@dataclass(frozen=True)
class ImageAttachment:
    """Проверенное вложение хода."""

    name: str
    mime: str
    data: bytes


@dataclass(frozen=True)
class Usage:
    """Токены готового ответа."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int | None = None
    cache_creation_tokens: int | None = None


@dataclass(frozen=True)
class ToolFunction:
    """Сериализованные аргументы вызова OpenAI function."""

    name: str
    arguments: str


@dataclass(frozen=True)
class ToolCall:
    """Вызов инструмента в готовом ответе."""

    index: int
    id: str
    function: ToolFunction
    type: str = "function"


@dataclass(frozen=True)
class TurnEvent:
    """Событие доставки: текст или типизированный вызов."""

    kind: str
    value: str | ToolCall


@dataclass(frozen=True)
class TurnResult:
    """Итог адаптера; None events означает необходимость фасадного разбора текста."""

    state: str = "done"
    rc: int = 0
    text: str = ""
    reasoning: str = ""
    usage: Usage = field(default_factory=Usage)
    err: str = ""
    events: tuple[TurnEvent, ...] | None = None
    tool_calls: tuple[ToolCall, ...] = ()
