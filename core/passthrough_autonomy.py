"""Очистка локальных полей и подготовка passthrough-запросов."""

from __future__ import annotations

import json
from typing import Any

from core.effort_policy import ModelEffortSpec, resolve_passthrough_effort
from core.runtime_env import DynamicFlagSource

FLAG_STRIP_PASSTHROUGH_AUTONOMY = "BRIDGE_STRIP_PASSTHROUGH_AUTONOMY_ENABLED"
_STRIP_PASSTHROUGH_AUTONOMY = DynamicFlagSource(
    FLAG_STRIP_PASSTHROUGH_AUTONOMY, default=False
)


def strip_passthrough_autonomy_enabled(reader=None, fallback: bool = False) -> bool:
    """Вернуть состояние rollout-флага, сохраняя fail-safe fallback."""
    try:
        if reader is None:
            return _STRIP_PASSTHROUGH_AUTONOMY.enabled(fallback)
        return bool(reader(FLAG_STRIP_PASSTHROUGH_AUTONOMY))
    except Exception:  # noqa: BLE001 - источник флага не должен ломать запрос
        return fallback


def passthrough_autonomy_validation_enabled(is_passthrough: bool) -> bool:
    """Ограничить валидацию autonomy только passthrough-маршрутом под флагом."""
    return is_passthrough and strip_passthrough_autonomy_enabled()


def resolve_target_model(model_entry: dict, requested_model_id: str) -> str:
    """Вернуть каноническую upstream-модель, если она задана в каталоге."""
    if not isinstance(model_entry, dict):
        return requested_model_id
    upstream = model_entry.get("upstream_model")
    if isinstance(upstream, str) and upstream.strip():
        return upstream.strip()
    return requested_model_id


def prepare_passthrough_request(
    req: dict, model: dict, model_id: str, *positional: object, **options: object
) -> tuple[dict, Any]:
    """Подготовить модель и effort без зависимости ядра от HTTP-фасада."""
    if len(positional) > 3:
        raise TypeError("prepare_passthrough_request accepts at most six arguments")
    alias = positional[0] if positional else options.get("alias")
    alias_effort = positional[1] if len(positional) > 1 else options.get("alias_effort")
    effort_on = bool(positional[2] if len(positional) > 2 else options.get("effort_on", False))
    has_upstream = bool(resolve_target_model(model, ""))
    pt_effort = resolve_passthrough_effort(
        req.get("reasoning_effort"),
        alias_effort if isinstance(alias_effort, str) else None,
        ModelEffortSpec.from_catalog_entry(model) if effort_on else ModelEffortSpec(),
        enabled=effort_on,
    )
    if has_upstream or alias or pt_effort.apply:
        req = {**req, "model": resolve_target_model(model, model_id)}
        if pt_effort.apply:
            req["reasoning_effort"] = pt_effort.value
    return req, pt_effort


def strip_passthrough_request(raw: bytes, req: dict) -> tuple[bytes, dict]:
    """Удалить локальные поля, сохранив исходные bytes при отсутствии изменений."""
    extra = req.get("extra_body")
    strip_autonomy = strip_passthrough_autonomy_enabled()
    extra_values = extra if isinstance(extra, dict) else {}
    strip_env = "env" in extra_values
    strip_nested = strip_autonomy and "autonomy" in extra_values
    strip_top = strip_autonomy and "autonomy" in req
    if not any((strip_env, strip_nested, strip_top)):
        return raw, req
    clean_req = dict(req)
    if strip_autonomy:
        clean_req.pop("autonomy", None)
    if strip_env or strip_nested:
        removed = {"env", "autonomy"} if strip_autonomy else {"env"}
        clean_req["extra_body"] = {
            key: value for key, value in extra_values.items() if key not in removed
        }
    return json.dumps(clean_req, ensure_ascii=False).encode("utf-8"), clean_req
