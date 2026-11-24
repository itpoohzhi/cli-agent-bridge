"""AD-002/REQ-002: карта логического effort `"off"` на контракты провайдеров."""
from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import replace
from typing import Any


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


def resolve_provider_off_patch(
    adapter: Any, backend_id: str
) -> tuple[str | None, Mapping[str, Any] | None]:
    """Контракт `"off"`: явные params/effort_map конфига, иначе канон providers.d."""
    config = getattr(adapter, "config", None) if adapter is not None else None
    if isinstance(config, Mapping):
        params = config.get("params")
        if isinstance(params, Mapping):
            field_name, mapping = params.get("effort_field"), params.get("effort_map")
            patch = mapping.get("off") if isinstance(mapping, Mapping) else None
            if isinstance(field_name, str) and field_name and patch is not None:
                return field_name, patch
        mapping = config.get("effort_map")
        patch = mapping.get("off") if isinstance(mapping, Mapping) else None
        if patch is not None:
            return str(config.get("effort_field") or "reasoning_effort"), patch
    backend = str(backend_id or "").strip().lower()
    adapter_id = str(getattr(adapter, "id", "") or "").strip().lower()
    base_url = str(config.get("base_url") or "") if isinstance(config, Mapping) else ""
    if backend.startswith("neuralwatt") or adapter_id.startswith("neuralwatt") or "/neuralwatt/" in base_url:
        return "reasoning_effort", {"reasoning_effort": "none"}
    if backend.startswith("opencode-go") or adapter_id.startswith("opencode-go") or "/go/" in base_url:
        return "none", {"thinking": {"type": "disabled"}}
    return None, None


def _is_logical_off(request: Mapping[str, Any]) -> bool:
    explicit = str(request.get("reasoning_effort", "")).strip().lower()
    return explicit == "off" or is_thinking_disabled(request)


def _wire_body(body: Any, request: Mapping[str, Any], patch: Mapping[str, Any]) -> bytes:
    """Тело запроса с теми же ключами патча; прочие поля исходного body сохраняются."""
    parsed = None
    if isinstance(body, (bytes, bytearray)) and body:
        try:
            parsed = json.loads(body)
        except ValueError:
            parsed = None
    source = dict(parsed) if isinstance(parsed, dict) else dict(request)
    source.pop("reasoning_effort", None)
    source.pop("thinking", None)
    source.update(copy.deepcopy(patch))
    return json.dumps(source, ensure_ascii=False).encode("utf-8")


def apply_attempt_effort_map(
    selected: Any, adapter: Any, body: bytes
) -> tuple[Any, bytes]:
    """Провайдерский контракт логического `"off"`; вход и body не мутируются (failover)."""
    request = getattr(selected, "request", None)
    if not isinstance(request, Mapping) or not _is_logical_off(request):
        return selected, body
    model = getattr(selected, "model", None)
    backend = str(model.get("backend") or "") if isinstance(model, Mapping) else ""
    _effort_field, patch = resolve_provider_off_patch(adapter, backend)
    if not isinstance(patch, Mapping) or not patch:
        return selected, body
    patched = dict(request)
    patched.pop("reasoning_effort", None)
    patched.pop("thinking", None)
    patched.update(copy.deepcopy(patch))
    new_body = _wire_body(body, request, patch)
    try:
        return replace(selected, request=patched), new_body
    except TypeError:
        clone = copy.copy(selected)
        clone.request = patched
        return clone, new_body
