from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from typing import Protocol


class ToolsGateError(RuntimeError):
    """Отказ допуска модели или набора tools (slug без путей и данных)."""


class QualifiedTools(Protocol):
    """Квалификация tools по моделям из receipt v3."""

    def tools_for(self, model_id: str) -> tuple[str, ...] | None:
        """Каталог tools модели; `None` — модели нет в `qualified_models`."""
        ...


@dataclass(frozen=True, slots=True)
class ToolsDisablePlan:
    """Что отключить в сессии модели: нативные tools за вычетом `keep`."""

    model_id: str
    disabled_ids: tuple[str, ...]


def admit_model(receipt: QualifiedTools | None, model_id: str) -> tuple[str, ...] | None:
    """Каталог tools модели; `None` — gate выключен; неквалифицированная модель — отказ."""
    expected = None if receipt is None else receipt.tools_for(model_id)
    if receipt is not None and expected is None:
        raise ToolsGateError("model not qualified in receipt (qualified_models)")
    return expected


def plan_tools_disable(
    ids: tuple[str, ...], receipt: QualifiedTools | None, model_id: str, keep: Collection[str]
) -> ToolsDisablePlan:
    """План отключения по актуальному `list_tools` (пустой `ids` — каталог некорректен)."""
    if not ids:
        raise ToolsGateError("list_tools: invalid catalogue")
    if admit_model(receipt, model_id) not in (None, tuple(sorted(set(ids)))):
        raise ToolsGateError("native tool catalogue differs from the qualified tools policy")
    return ToolsDisablePlan(model_id, tuple(dict.fromkeys(i for i in ids if i not in keep)))


def verify_tools_disabled(plan: ToolsDisablePlan, updated: object) -> None:
    """Read-back `settings_updated` обязан подтвердить отключение всех tools плана."""
    reported = updated.get("disabledToolIds") if isinstance(updated, dict) else None
    confirmed = set(map(str, reported if isinstance(reported, list) else ()))
    if not set(plan.disabled_ids) <= confirmed:
        raise ToolsGateError("native tools were not disabled (read-back missing or mismatch)")
