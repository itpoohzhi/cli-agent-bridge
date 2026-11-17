"""Сборка записей компилятора без обратной зависимости от его фасада."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, TypeAlias, TypedDict

from core.model_lifecycle import STATUS_CONFIRMED, STATUS_QUARANTINE, STATUS_STALE
from core.model_lifecycle import LifecycleRegistry, ModelRecord

# Входные DTO принадлежат HOST: здесь нет зависимости от загрузчика манифестов.
ManifestLike: TypeAlias = Any


class CompileError(Exception):
    """Фатальная ошибка шапки или итоговой проверки каталога."""

    def __init__(self, slug: str, model: str = "-") -> None:
        super().__init__(slug)
        self.slug = slug
        self.model = model


@dataclass(frozen=True)
class CompileResult:
    """Совместимый результат schema 3 и catalog-lock/1."""

    fleet: dict[str, Any]
    sidecar: dict[str, Any]
    rejected: Mapping[str, str] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    rejected_providers: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


class CompileOptions(TypedDict, total=False):
    """Именованные параметры совместимого публичного API."""

    discovery: Mapping[str, Any] | None
    registry: LifecycleRegistry | None
    receipts: Mapping[str, Mapping[str, Any]] | None
    rejected_providers: Mapping[str, tuple[str, ...]] | None
    manifest_digests: Mapping[str, str] | None
    now: str
    env: Mapping[str, str] | None
    error_factory: Callable[..., Exception]
    result_factory: Callable[..., CompileResult]


@dataclass(frozen=True)
class ModelProof:
    """Receipt принадлежит только своему provider/model/fingerprint."""

    status: str
    record: ModelRecord | None
    receipt: Mapping[str, Any] | None


def _confirmed_receipt(
    record: ModelRecord | None,
    receipts: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    if record is None or record.status not in (STATUS_CONFIRMED, STATUS_STALE):
        return None
    candidate = receipts.get(record.receipt_sha256) if record.receipt_sha256 else None
    if isinstance(candidate, Mapping) and candidate.get("verdict") == "confirmed":
        return candidate
    return None


def model_proof(
    provider: ManifestLike,
    model_id: str,
    fingerprint: str,
    options: CompileOptions,
) -> ModelProof:
    """Не переносит подтверждение между маршрутами одной модели."""
    registry = options.get("registry")
    key = (provider.provider_id, model_id, fingerprint)
    record = registry.get(key) if registry else None
    status = record.status if record else STATUS_QUARANTINE
    receipt = _confirmed_receipt(record, options.get("receipts") or {})
    if status == STATUS_CONFIRMED and receipt is None:
        status = STATUS_QUARANTINE
    return ModelProof(status, record, receipt)


def receipt_efforts(
    receipt: Mapping[str, Any],
    pin: Sequence[str] | None,
) -> tuple[list[str], str]:
    """Оставляет только доказанные усилия, разрешённые pin."""
    proven = receipt.get("efforts_proven")
    if not isinstance(proven, list):
        return [], ""
    efforts = [str(e) for e in proven if pin is None or str(e) in pin]
    default = str(receipt.get("default_effort") or "")
    if efforts and default not in efforts:
        default = efforts[-1]
    return efforts, default


def _model_efforts(
    manifest: ManifestLike,
    rule: Any,
    receipt: Mapping[str, Any] | None,
) -> tuple[list[str], str]:
    override = rule.fields if rule else {}
    defaults = manifest.models_defaults
    efforts = list(override.get("efforts") or defaults.efforts)
    default = str(override.get("default_effort") or defaults.default_effort)
    if receipt is not None:
        pin = rule.efforts_pin if rule else None
        proven, proven_default = receipt_efforts(receipt, pin)
        if proven:
            efforts, default = proven, proven_default
    return efforts, default


def _model_images(override: Mapping[str, Any]) -> dict[str, Any]:
    """Удаляет только значения, восстанавливаемые absent-only загрузчиком."""
    images = dict(override.get("images") or {"status": "unverified"})
    for key in ("method", "proof"):
        if images.get(key) is None:
            images.pop(key, None)
    if images.get("cli_registry") in ("", "implicit_supported"):
        images.pop("cli_registry")
    return images


def model_record(
    manifest: ManifestLike,
    model_id: str,
    meta: Mapping[str, Any],
    receipt: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Сохраняет приоритет overrides, discovery.meta и models_defaults."""
    rule = manifest.rule_for(model_id)
    override = rule.fields if rule else {}
    defaults = manifest.models_defaults
    efforts, default = _model_efforts(manifest, rule, receipt)
    record: dict[str, Any] = {
        "id": model_id,
        "backend": manifest.provider_id,
        "name": str(override.get("name") or model_id),
        "efforts": efforts,
        "default_effort": default,
    }
    for key in ("context_window", "max_tokens"):
        record[key] = override.get(key, meta.get(key, getattr(defaults, key)))
    inputs = list(override.get("input") or ["text"])
    if inputs != ["text"]:
        record["input"] = inputs
    record["images"] = _model_images(override)
    if override.get("policy_lines"):
        record["policy_lines"] = list(override["policy_lines"])
    for key in ("upstream_model", "resident", "pool_size", "alias_of"):
        if override.get(key) is not None:
            record[key] = override[key]
    return record


def _http_references(http: Mapping[str, Any]) -> dict[str, Any]:
    """Копирует ссылки, не читая файлы с ключами и заголовками."""
    out: dict[str, Any] = {}
    ref = http.get("api_key_ref")
    if isinstance(ref, str) and ref.startswith("file:"):
        out["api_key_ref"] = ref
    elif isinstance(ref, Mapping):
        fallback = ref.get("fallback_file")
        if isinstance(fallback, str) and fallback:
            out["api_key_ref"] = "file:" + fallback
    out.update(_header_reference(http.get("headers_from_json")))
    per_request = http.get("per_request_headers")
    if isinstance(per_request, Mapping) and per_request:
        out["per_request_headers"] = {str(k): str(v) for k, v in per_request.items()}
    return out


def _header_reference(headers: object) -> dict[str, Any]:
    if isinstance(headers, Mapping):
        path, key = headers.get("path"), headers.get("key")
        pick = headers.get("pick") or headers.get("required")
        if isinstance(path, str) and isinstance(key, str) and isinstance(pick, list):
            selected = {
                "file": path,
                "json_path": key.split("."),
                "pick": [str(name) for name in pick],
            }
            return {"headers_from_json": selected}
    return {}


def upstream_params(manifest: ManifestLike) -> dict[str, Any]:
    """Сохраняет raw-HTTP настройки без разрешения секретных ссылок."""
    bridge, direct = manifest.transport.bridge, manifest.transport.direct
    http = direct.http if direct else None
    if bridge is None or bridge.base_url is None or not http:
        return {}
    out = _http_references(http)
    default_off = manifest.params.effort_map.get("off")
    rules = manifest.models_overrides
    # Дефолт одной модели не должен выключать reasoning остальных моделей.
    if isinstance(default_off, Mapping) and default_off and rules:
        if all(rule.fields.get("default_effort") == "off" for rule in rules):
            out["default_body_extra"] = deepcopy(default_off)
    return out


def _backend_fingerprint(manifest: ManifestLike) -> dict[str, Any]:
    """Сохраняет полную техническую ссылку без чтения бинарного файла."""
    fingerprint = manifest.fingerprint
    if not fingerprint.binary_path or not fingerprint.binary_sha256:
        return {}
    ref = {
        key: getattr(fingerprint, key)
        for key in ("version", "binary_sha256", "binary_path")
        if getattr(fingerprint, key) is not None
    }
    return {"technical_ref": ref}


def backend_entry(manifest: ManifestLike) -> dict[str, Any]:
    """Собирает backend, сохраняя отдельный слот учётных данных."""
    bridge = manifest.transport.bridge
    if bridge is None:
        raise CompileError("provider_bridge_missing", manifest.provider_id)
    entry: dict[str, Any] = {
        "kind": manifest.kind,
        "enabled": manifest.enabled,
        "required": manifest.required,
        "owned_by": manifest.owned_by,
        "max_concurrent": manifest.limits.max_concurrent,
    }
    if manifest.required is False:
        entry.pop("required")
    for key in ("base_url", "api_key_env", "wrapper"):
        value = getattr(bridge, key)
        if value is not None:
            entry[key] = value
    entry.update(_backend_fingerprint(manifest))
    for key in ("options", "proxy_port", "idle_timeout_s", "safety_cap_s"):
        value = getattr(bridge, key)
        if value is not None and value != {}:
            entry[key] = deepcopy(value)
    failover = getattr(manifest, "failover", None)
    if failover is not None and failover.statuses:
        entry["failover_statuses"] = list(failover.statuses)
        if failover.error_types:
            entry["failover_error_types"] = list(failover.error_types)
    entry.update(upstream_params(manifest))
    return entry


def _resolve_family(manifest: ManifestLike, model_id: str) -> tuple[str | None, str]:
    """Повторяет чистую семантику HOST без импорта загрузчика."""
    rule = manifest.family_rule
    if rule.type in ("exact_map", "owned_by"):
        family = rule.exact_map.get(model_id) if rule.type == "exact_map" else rule.owned_by
        return (family, rule.type) if family else (None, "unmapped")
    if rule.type == "prefix" and rule.prefix_verified:
        families = {fam for pre, fam in rule.prefix_map.items() if model_id.startswith(pre)}
        if len(families) == 1:
            return next(iter(families)), "prefix"
        return None, "ambiguous" if families else "unmapped"
    return None, "unmapped"


def model_sidecar(
    provider: ManifestLike,
    model_id: str,
    proof: ModelProof,
    alternates: list[dict[str, str]],
    history_max: int,
) -> dict[str, Any]:
    """Фиксирует независимые status, family, quorum и происхождение proof."""
    family, source = _resolve_family(provider, model_id)
    receipt, record = proof.receipt, proof.record
    entry: dict[str, Any] = {
        "provider": provider.provider_id,
        "status": proof.status,
        "family": family,
        "family_source": source,
        "quorum_eligible": bool(
            proof.status == STATUS_CONFIRMED and family
            and source in ("exact_map", "owned_by", "prefix")
        ),
        "quota_group": provider.limits.quota_group,
        "in_fleet": False,
        "efforts_proven": list(receipt.get("efforts_proven") or []) if receipt else [],
        "alternates": alternates,
        "history": [dict(h) for h in (record.history if record else ())][-history_max:],
    }
    if receipt is not None and record is not None:
        entry["probe"] = {
            "receipt_sha256": record.receipt_sha256,
            "fingerprint_sha256": record.fingerprint_sha256,
            "probe_version": receipt.get("probe_version"),
            "at": receipt.get("finished_at"),
        }
    return entry
