"""Effort нативного CLI-маршрута: строгий тип и downward clamp без повышения вверх."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.effort_errors import EffortBelowFloorError

if TYPE_CHECKING:
    from core.http_post_routing import PostRoute


def native_effort(route: PostRoute) -> tuple[str, str] | None:
    """Сохраняет строгий тип effort и прежний downward clamp CLI.

    Каталог не обязан объявлять `default_effort`/`efforts` для каждого слота:
    отсутствующие поля дают fail-safe "high" вместо падения маршрута.
    Уровень ниже минимума модели не повышается: HTTP 400 `unsupported_reasoning_effort`.
    """
    value = route.request.get("reasoning_effort")
    source = "alias" if value is None and route.alias_effort is not None else "request"
    value = route.alias_effort if source == "alias" else value
    declared = route.model.get("efforts")
    efforts = declared if isinstance(declared, (list, tuple)) and declared else ["high"]
    default_effort = route.model.get("default_effort") or efforts[0]
    if value is None or isinstance(value, str) and not value.strip():
        return default_effort, "default"
    if not isinstance(value, str):
        route.reject(400, "unsupported_reasoning_effort", "reasoning_effort must be a string")
        return None
    try:
        effort, clamped = route.host.clamp_effort_downward(value.strip(), efforts, default_effort)
    except EffortBelowFloorError as exc:
        route.reject(400, "unsupported_reasoning_effort", str(exc))
        return None
    if clamped:
        route.host._log(route.host.describe_clamp("reasoning_effort", value.strip(), effort, route.model_id, route.host._LOG_EFFORT_MAX))
    return effort, source
