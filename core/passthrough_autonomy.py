"""Очистка локальных полей и подготовка passthrough-запросов."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass

from core.effort_policy import (
    EffortResolution,
    ModelEffortSpec,
    resolve_passthrough_effort,
)
from core.effortless_policy import is_effortless, strip_effortless_effort
from core.runtime_env import DynamicFlagSource

FLAG_STRIP_PASSTHROUGH_AUTONOMY = "BRIDGE_STRIP_PASSTHROUGH_AUTONOMY_ENABLED"
_STRIP_PASSTHROUGH_AUTONOMY = DynamicFlagSource(
    FLAG_STRIP_PASSTHROUGH_AUTONOMY, default=False
)


@dataclass(frozen=True, slots=True)
class PassthroughOptions:
    """Типизированные опции подготовки passthrough-запроса."""

    alias: tuple[str, str] | None = None
    alias_effort: str | None = None
    effort_on: bool = False
    clamp_enabled: bool | None = None


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


def resolve_target_model(
    model_entry: Mapping[str, object] | None, requested_model_id: str
) -> str:
    """Вернуть каноническую upstream-модель, если она задана в каталоге."""
    if not isinstance(model_entry, Mapping):
        return requested_model_id
    upstream = model_entry.get("upstream_model")
    if isinstance(upstream, str) and upstream.strip():
        return upstream.strip()
    return requested_model_id


def _catalog_effort_spec(
    model: Mapping[str, object], effort_on: bool
) -> ModelEffortSpec:
    """Построить спеку effort каталога; при выключенном флаге — только для effortless."""
    declared = model.get("efforts")
    if effort_on or is_effortless(declared):
        return ModelEffortSpec.from_catalog_entry(model)
    return ModelEffortSpec()


def _prepare_effortless_passthrough(
    req: dict[str, object],
    model: Mapping[str, object],
    model_id: str,
    opts: PassthroughOptions,
    catalog_spec: ModelEffortSpec,
    has_upstream: bool,
) -> tuple[dict[str, object], EffortResolution]:
    """Подготовить passthrough-запрос для effortless-модели без лишнего копирования."""
    needs_rewrite = has_upstream or bool(opts.alias)
    target_model = resolve_target_model(model, model_id) if needs_rewrite else model_id
    alias_effort = (
        opts.alias_effort.strip() if isinstance(opts.alias_effort, str) else ""
    )
    if "reasoning_effort" not in req and not alias_effort:
        base = {**req, "model": target_model} if needs_rewrite else req
        return base, EffortResolution()
    candidate_req = (
        req if "reasoning_effort" in req else {**req, "reasoning_effort": alias_effort}
    )
    clean, resolution = strip_effortless_effort(
        candidate_req,
        catalog_spec,
        EffortResolution(),
        clamp_enabled=opts.clamp_enabled,
    )
    if needs_rewrite and clean.get("model") != target_model:
        clean = {**clean, "model": target_model}
    return clean, resolution


def prepare_passthrough_request(
    req: dict[str, object],
    model: Mapping[str, object],
    model_id: str,
    options: PassthroughOptions | None = None,
) -> tuple[dict[str, object], EffortResolution]:
    """Подготовить модель и effort без зависимости ядра от HTTP-фасада."""
    opts = PassthroughOptions() if options is None else options
    has_upstream = bool(resolve_target_model(model, ""))
    catalog_spec = _catalog_effort_spec(model, opts.effort_on)
    if is_effortless(catalog_spec.efforts):
        return _prepare_effortless_passthrough(
            req, model, model_id, opts, catalog_spec, has_upstream
        )
    pt_effort = resolve_passthrough_effort(
        req.get("reasoning_effort"),
        opts.alias_effort if isinstance(opts.alias_effort, str) else None,
        catalog_spec if opts.effort_on else ModelEffortSpec(),
        enabled=opts.effort_on,
    )
    if has_upstream or opts.alias or pt_effort.apply:
        req = {**req, "model": resolve_target_model(model, model_id)}
        if pt_effort.apply:
            req["reasoning_effort"] = pt_effort.value
    return strip_effortless_effort(
        req, catalog_spec, pt_effort, clamp_enabled=opts.clamp_enabled
    )


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
