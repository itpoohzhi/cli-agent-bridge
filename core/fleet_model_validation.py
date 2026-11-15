"""Чистая нормализация моделей schema 2/3 и закрытых наборов маршрутов."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import NotRequired, TypedDict, TypeGuard, cast

from core.effort_policy import EFFORT_LEVELS as _RANKED_EFFORT_LEVELS
from core.routing_contract import FleetViolation
from core.routing_schema import RoutingDocument

FLEET_MODEL_KEYS = frozenset(
    {
        "id",
        "backend",
        "name",
        "efforts",
        "default_effort",
        "context_window",
        "max_tokens",
        "input",
        "images",
        "policy_lines",
        "upstream_model",
        "resident",
        "pool_size",
        "alias_of",
        "routing",
    }
)
EFFORT_LEVELS = ("off", *_RANKED_EFFORT_LEVELS)
IMAGE_STATUSES = ("unsupported", "unverified", "probe", "confirmed")
IMPLEMENTED_METHODS = MappingProxyType({"workspace-read": 1})
_PROOF_KEYS = frozenset(
    {
        "droid_version",
        "droid_binary_sha256",
        "method",
        "impl_version",
        "formats",
    }
)
_SHA256_HEX = re.compile(r"[0-9a-f]{64}")


class BackendState(TypedDict):
    """Минимальная проекция предварительно проверенной записи backend."""

    enabled: bool


class NormalizedImages(TypedDict):
    """Проверенное состояние поддержки изображений без потери proof."""

    status: str
    cli_registry: str
    method: str | None
    proof: object


class NormalizedModel(TypedDict):
    """Совместимый результат загрузчика с аддитивной routing metadata."""

    id: str
    backend: str
    name: str
    efforts: list[str]
    default_effort: str
    context_window: int
    input: list[str]
    images: NormalizedImages
    upstream_model: NotRequired[str]
    routing: NotRequired[RoutingDocument]


def _str_list(value: object) -> TypeGuard[list[str]]:
    return isinstance(value, list) and all(
        isinstance(item, str) for item in cast(list[object], value)
    )


def _model_backend(
    item: Mapping[str, object],
    mid: str,
    schema: int,
    backends: Mapping[str, BackendState],
) -> str:
    if schema != 3:
        return "droid"
    if set(item) - FLEET_MODEL_KEYS:
        raise FleetViolation("model_key_unknown", mid)
    backend_id = item.get("backend")
    if not isinstance(backend_id, str) or backend_id not in backends:
        raise FleetViolation("model_backend_unknown", mid)
    return backend_id


def _model_efforts(item: Mapping[str, object], mid: str) -> list[str]:
    efforts = item.get("efforts")
    if not _str_list(efforts) or not efforts:
        raise FleetViolation("efforts_invalid", mid)
    if any(effort not in EFFORT_LEVELS for effort in efforts):
        raise FleetViolation("efforts_invalid", mid)
    if item.get("default_effort") not in efforts:
        raise FleetViolation("default_effort_invalid", mid)
    return efforts


def _proof_header(raw: object, mid: str, method: object) -> Mapping[str, object]:
    if not isinstance(raw, dict):
        raise FleetViolation("confirmed_proof_malformed", mid)
    proof = cast(Mapping[str, object], raw)
    if not _PROOF_KEYS.issubset(proof):
        raise FleetViolation("confirmed_proof_malformed", mid)
    if not isinstance(proof.get("droid_version"), str):
        raise FleetViolation("confirmed_proof_malformed", mid)
    digest = proof.get("droid_binary_sha256")
    if not isinstance(digest, str) or not _SHA256_HEX.fullmatch(digest):
        raise FleetViolation("confirmed_proof_malformed", mid)
    if proof.get("method") != method or type(proof.get("impl_version")) is not int:
        raise FleetViolation("confirmed_proof_malformed", mid)
    return proof


def validate_proof(
    model_id: str, images: Mapping[str, object], method: object, efforts: Sequence[str]
) -> None:
    """Сохраняет причины отказа прежнего публичного валидатора proof."""
    raw = images.get("proof")
    if raw is None:
        raise FleetViolation("confirmed_proof_missing", model_id)
    proof = _proof_header(raw, model_id, method)
    if not _str_list(proof.get("formats")):
        raise FleetViolation("confirmed_proof_malformed", model_id)
    proven = proof.get("efforts_proven")
    if not _str_list(proven):
        raise FleetViolation("confirmed_proof_malformed", model_id)
    if (
        not proven
        or len(set(proven)) != len(proven)
        or any(p not in efforts for p in proven)
    ):
        raise FleetViolation("confirmed_efforts_proven_invalid", model_id)


def _image_consistency(
    images: Mapping[str, object], input_types: list[str], mid: str
) -> None:
    status = images["status"]
    if images.get("cli_registry") == "explicit_unsupported" and status != "unsupported":
        raise FleetViolation("status_inconsistent", mid)
    if status in ("unsupported", "unverified") and (
        images.get("method") is not None or input_types != ["text"]
    ):
        raise FleetViolation("status_inconsistent", mid)

__all__ = ('BackendState', 'NormalizedImages', 'NormalizedModel', '_str_list', '_model_backend', '_model_efforts', '_proof_header', 'validate_proof', '_image_consistency')
