"""AD-002/REQ-002: карта логического effort `"off"` на контракты провайдеров."""
from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import replace
from typing import Any
from urllib.parse import urlparse

_LOCAL_GEOROUTER_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_LOCAL_GEOROUTER_PORT = 10830
_NEURALWATT_IDS = frozenset({"neuralwatt", "neuralwatt-flex"})
_OPENCODE_GO_IDS = frozenset({"opencode-go"})


def is_thinking_disabled(request: Mapping[str, Any] | None) -> bool:
    """`thinking.type == "disabled"` — логический `"off"` без reasoning_effort."""
    if isinstance(request, Mapping):
        thinking = request.get("thinking")
        if isinstance(thinking, Mapping):
            return str(thinking.get("type", "")).strip().lower() == "disabled"
    return False


def logical_effort(
    request: Mapping[str, Any] | None,
    alias_effort: str | None,
    model: Mapping[str, Any] | None,
) -> str:
    """Явный effort > thinking:disabled ("off") > alias_effort > default_effort."""
    if isinstance(request, Mapping):
        explicit = request.get("reasoning_effort")
        if isinstance(explicit, str) and explicit.strip():
            return explicit
        if is_thinking_disabled(request):
            return "off"
    if isinstance(alias_effort, str) and alias_effort.strip():
        return alias_effort
    if isinstance(model, Mapping):
        default = model.get("default_effort")
        if isinstance(default, str) and default:
            return default
    return ""


def _normalize_off_patch(raw_off: Any, effort_field: Any) -> dict[str, Any] | None:
    if isinstance(raw_off, Mapping):
        return copy.deepcopy(dict(raw_off))
    if isinstance(raw_off, str) and raw_off.strip():
        field = effort_field.strip() if isinstance(effort_field, str) else ""
        if field and field.lower() != "none":
            return {field: raw_off}
    return None


def _local_georouter_patch(base_url: str) -> dict[str, Any] | None:
    if not base_url:
        return None
    parsed = urlparse(base_url.strip())
    try:
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme != "http" or parsed.hostname not in _LOCAL_GEOROUTER_HOSTS or port != _LOCAL_GEOROUTER_PORT:
        return None
    segments = [seg for seg in parsed.path.split("/") if seg]
    first_seg = segments[0].lower() if segments else ""
    if first_seg == "neuralwatt":
        return {"reasoning_effort": "none"}
    if first_seg == "go":
        return {"thinking": {"type": "disabled"}}
    return None


def resolve_provider_off_patch(adapter: Any, backend_id: str) -> dict[str, Any] | None:
    """Контракт `"off"`: явный effort_map конфига, иначе точный provider id / локальный georouter."""
    config = getattr(adapter, "config", None) if adapter is not None else None
    if isinstance(config, Mapping):
        params = config.get("params")
        if isinstance(params, Mapping):
            p_map = params.get("effort_map")
            if isinstance(p_map, Mapping) and "off" in p_map:
                p_field = params.get("effort_field") if "effort_field" in params else config.get("effort_field", "reasoning_effort")
                return _normalize_off_patch(p_map["off"], p_field)
        c_map = config.get("effort_map")
        if isinstance(c_map, Mapping) and "off" in c_map:
            c_field = config.get("effort_field") if "effort_field" in config else "reasoning_effort"
            return _normalize_off_patch(c_map["off"], c_field)
    backend = str(backend_id or "").strip().lower()
    adapter_id = str(getattr(adapter, "id", "") or "").strip().lower()
    for ident in (adapter_id, backend):
        if ident in _NEURALWATT_IDS:
            return {"reasoning_effort": "none"}
        if ident in _OPENCODE_GO_IDS:
            return {"thinking": {"type": "disabled"}}
    base_url = str(config.get("base_url") or "") if isinstance(config, Mapping) else ""
    return _local_georouter_patch(base_url)


def _is_logical_off(request: Mapping[str, Any] | None) -> bool:
    if not isinstance(request, Mapping):
        return False
    explicit = request.get("reasoning_effort")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip().lower() in ("off", "none")
    return is_thinking_disabled(request)


def _patch_dict(source: Mapping[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(source)
    out.pop("reasoning_effort", None)
    out.pop("thinking", None)
    out.update(copy.deepcopy(dict(patch)))
    return out


def _wire_body(body: Any, patch: Mapping[str, Any]) -> Any:
    """Тело bytes с ключами патча; PreparedPostBody патчится после prepare_route_request."""
    if not isinstance(body, (bytes, bytearray)) or not body:
        return body
    try:
        parsed = json.loads(body)
    except (ValueError, TypeError):
        return body
    if not isinstance(parsed, dict):
        return body
    return json.dumps(_patch_dict(parsed, patch), ensure_ascii=False).encode("utf-8")


def apply_prepared_off_patch(
    prepared: Mapping[str, Any],
    raw_request: Mapping[str, Any] | None,
    route_request: Mapping[str, Any] | None,
    adapter: Any,
    backend: str,
) -> dict[str, Any]:
    """Применяет провайдерский wire-патч `off` поверх `prepared` (после `prepare_route_request`, без clamp)."""
    out = copy.deepcopy(dict(prepared))
    if not (_is_logical_off(raw_request) or _is_logical_off(route_request)):
        return out
    patch = resolve_provider_off_patch(adapter, backend)
    if not isinstance(patch, Mapping) or not patch:
        return out
    return _patch_dict(out, patch)


def apply_attempt_effort_map(
    selected: Any, adapter: Any, body: bytes
) -> tuple[Any, bytes]:
    """Провайдерский контракт логического `"off"`; вход и body не мутируются (failover)."""
    request = getattr(selected, "request", None)
    if not isinstance(request, Mapping) or not _is_logical_off(request):
        return selected, body
    model = getattr(selected, "model", None)
    backend = str(model.get("backend") or "") if isinstance(model, Mapping) else ""
    patch = resolve_provider_off_patch(adapter, backend)
    if not isinstance(patch, Mapping) or not patch:
        return selected, body
    patched = copy.deepcopy(dict(request))
    patched.pop("reasoning_effort", None)
    patched.pop("thinking", None)
    patched.update(copy.deepcopy(dict(patch)))
    new_body = _wire_body(body, patch)
    try:
        return replace(selected, request=patched), new_body
    except (TypeError, ValueError):
        clone = copy.copy(selected)
        clone.request = patched
        return clone, new_body


def _norm_ident(value: Any) -> str:
    return str(value).strip().lower() if value else ""


def _is_georouter_effort_route(adapter: Any) -> bool:
    config = getattr(adapter, "config", None)
    if not isinstance(config, Mapping):
        return False
    base_url = config.get("base_url")
    patch = _local_georouter_patch(str(base_url) if base_url else "")
    return isinstance(patch, Mapping) and "reasoning_effort" in patch


def drops_thinking_route(adapter: Any, backend: str) -> bool:
    """OpenAI/NeuralWatt маршруты не принимают ``thinking`` — остаётся effort."""
    for ident in (_norm_ident(getattr(adapter, "id", "")), _norm_ident(backend)):
        if ident in _NEURALWATT_IDS or ident.startswith("openai"):
            return True
    return _is_georouter_effort_route(adapter)


def drop_thinking_keep_effort(body: Mapping[str, Any]) -> dict[str, Any]:
    """Снять ``thinking`` (OpenAI/NeuralWatt), сохранив reasoning_effort.

    Явный ``reasoning_effort`` не трогается — в том числе уровень, смапленный
    из ``thinking``: снимается только ключ ``thinking``. Вход не мутируется
    (pristine-копия для каждого хопа/ретрая).
    """
    out = copy.deepcopy(dict(body))
    out.pop("thinking", None)
    return out
