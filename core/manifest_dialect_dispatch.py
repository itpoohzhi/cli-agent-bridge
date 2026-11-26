"""Декларативный диспетчер параметров passthrough по `backends.<id>.params` (REQ-004).

Диалект бэкенда (`effort_field`, `effort_map`, `strip_always`) читается из `adapter.config["params"]`;
захардкоженные карты провайдеров остаются только в legacy-ветке. Флаг
`BRIDGE_MANIFEST_PARAMS_NORMALIZE_ENABLED` (дефолт `true`): `false`/`0` — мгновенный откат на
`_apply_legacy_passthrough_transforms`, побайтно совпадающую с прежним поведением.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any, Final

from core import passthrough_effort_map as _pem
from core import param_adapter
from core.backend_params import validate_backend_params
from core.logical_effort import EFFORT_KEYS, LOGICAL_OFF, canonicalize_logical_effort, is_thinking_disabled
from core.runtime_env import DynamicFlagSource

FLAG_MANIFEST_PARAMS_NORMALIZE: Final[str] = "BRIDGE_MANIFEST_PARAMS_NORMALIZE_ENABLED"
_FLAG: Final[DynamicFlagSource] = DynamicFlagSource(FLAG_MANIFEST_PARAMS_NORMALIZE, default=True)


class ParamDegradedError(Exception):
    """Кворумный вызов потерял бы «думающий» параметр: ответ 422 `param_degraded`."""

    def __init__(self, param: str, model_id: str) -> None:
        super().__init__(f"param_degraded param={param} model={model_id}")
        self.param = param
        self.model_id = model_id


def manifest_params_enabled() -> bool:
    """Состояние флага отката (дефолт `true`)."""
    return _FLAG.enabled(fallback=True)


def _apply_legacy_passthrough_transforms(
    prepared: dict[str, Any], route: Any, body: Any, adapter: Any
) -> dict[str, Any]:
    backend_id = str(route.model.get("backend") or "")
    out = _pem.apply_prepared_off_patch(prepared, body.request, route.request, adapter, backend_id)
    if _pem.drops_thinking_route(adapter, backend_id):
        out = _pem.drop_thinking_keep_effort(out)
    return param_adapter.clamp_thinking_budget(out)


def _backend_params(adapter: Any) -> Mapping[str, Any] | None:
    """Валидный непустой `params` бэкенда либо `None` (тогда — legacy)."""
    config = getattr(adapter, "config", None)
    params = config.get("params") if isinstance(config, Mapping) else None
    if not isinstance(params, Mapping) or not params or validate_backend_params(params):
        return None
    return params


def _is_quorum(route: Any) -> bool:
    headers = getattr(getattr(route, "handler", None), "headers", None)
    if headers is None:
        return False
    return param_adapter.is_quorum_call(headers.get("X-Subagent-Id"), headers.get("X-Review-Profile"))


def _translate_off(out: dict[str, Any], effort_map: Mapping[str, Any]) -> bool:
    """Логический `off` -> эффорт `off` для `effort_map`; True — `thinking` поглощён переводом."""
    consumed = is_thinking_disabled(out)
    for key in (*EFFORT_KEYS, *(("thinking",) if consumed else ())):
        out.pop(key, None)
    out["reasoning_effort"] = LOGICAL_OFF
    return consumed


def _check_degrade(explicit: Mapping[str, Any], strip: tuple[str, ...], consumed: set[str], route: Any) -> None:
    """Кворум: явный «думающий» параметр, снимаемый `strip_always` без перевода, — деградация."""
    lost = [k for k in strip if k in param_adapter.DEGRADE_PARAMS and k in explicit and k not in consumed]
    if lost and _is_quorum(route):
        raise ParamDegradedError(lost[0], route.model_id)


def _normalize(out: dict[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
    """`normalize_params` без потери effort при `effort_field == "none"` и отсутствии записи в `effort_map`."""
    field = params.get("effort_field", "reasoning_effort")
    effort_map = params.get("effort_map") or {}
    kept = {k: out[k] for k in EFFORT_KEYS if k in out}
    value = next((v for v in kept.values() if v is not None), None)
    result = param_adapter.normalize_params(out, effort_field=field, effort_map=effort_map)
    if field == "none" and value is not None and not (isinstance(value, str) and isinstance(effort_map.get(value), Mapping)):
        result.update(copy.deepcopy(kept))
    return param_adapter.strip_always(result, params.get("strip_always") or ())


def _apply_manifest_dialect(
    prepared: dict[str, Any], route: Any, body: Any, adapter: Any, params: Mapping[str, Any]
) -> dict[str, Any]:
    out = copy.deepcopy(dict(prepared))
    effort_map = params.get("effort_map") or {}
    explicit = {**(body.request or {}), **(route.request or {})}
    logical = canonicalize_logical_effort(out, route.request, body.request, alias_effort=route.alias_effort)
    consumed: set[str] = set()
    if logical == LOGICAL_OFF and LOGICAL_OFF in effort_map and _translate_off(out, effort_map):
        consumed.add("thinking")
    _check_degrade(explicit, tuple(params.get("strip_always") or ()), consumed, route)
    out = _normalize(out, params)
    backend_id = str(route.model.get("backend") or "")
    if _pem.drops_thinking_route(adapter, backend_id):
        out = _pem.drop_thinking_keep_effort(out)
    thinking = out.get("thinking")
    if isinstance(thinking, dict) and thinking.get("type") == "enabled":
        out = param_adapter.clamp_thinking_budget(out)
    return out


def apply_passthrough_transforms(prepared: dict[str, Any], route: Any, body: Any, adapter: Any) -> dict[str, Any]:
    """Точка входа `http_post_dispatch`: диалект манифеста либо legacy (флаг/нет `params`)."""
    params = _backend_params(adapter) if manifest_params_enabled() else None
    if params is None:
        return _apply_legacy_passthrough_transforms(prepared, route, body, adapter)
    return _apply_manifest_dialect(prepared, route, body, adapter, params)


def handle_param_degraded(route: Any, exc: ParamDegradedError) -> None:
    """HTTP 422 `param_degraded` + заголовок `X-Bridge-Degraded`."""
    status, payload, headers = param_adapter.degraded_response(exc.param, route.model_id)
    route.handler._send(status, payload, extra_headers=headers)
