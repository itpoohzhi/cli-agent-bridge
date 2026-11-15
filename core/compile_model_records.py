"""Сборка записей компилятора без обратной зависимости от его фасада."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
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

__all__ = ('CompileError', 'CompileResult', 'CompileOptions', 'ModelProof', '_confirmed_receipt', 'model_proof', 'receipt_efforts', '_model_efforts', '_model_images', 'model_record')
