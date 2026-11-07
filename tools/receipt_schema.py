"""Общая схема receipt допуска образа droid: константы и отпечатки (RW-009, RW-013).

Модуль самодостаточен: только stdlib, без fleet.json, сокетов и импорта моста. Его читают и
мост (`server.py`), и установщик `tools/droid_image.py`, поэтому отпечатки обязаны совпадать
побайтово: любое изменение значений здесь инвалидирует ранее выданные receipt.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

RPC_API_VERSION = "1.0.0"
RECEIPT_SCHEMA = 3  # v3: qualified_models (tools каждой модели)
TOOLS_POLICY = "disable-all-listed-keep-read-for-images"
SETTINGS_PROFILE = {
    "disableBuiltinSkills": True,
    "autoRejectPermissionRequests": True,
    "interactionMode": "auto",
}
RECEIPT_PROBES = ("spawn", "update", "load")


@dataclass(frozen=True, slots=True)
class QualifiedModelSpec:
    """Модель и отсортированные id нативных tools, которые droid показывает ей."""

    model_id: str
    tool_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReceiptV3:
    """Проверенная часть receipt v3: отключаемые id и квалификация по моделям."""

    disabled_tool_ids: tuple[str, ...]
    qualified: tuple[QualifiedModelSpec, ...]

    def tools_for(self, model_id: str) -> tuple[str, ...] | None:
        """Каталог tools модели; `None` — вне `qualified_models`."""
        return {q.model_id: q.tool_ids for q in self.qualified}.get(model_id)

    @classmethod
    def parse(cls, rec: object) -> ReceiptV3 | str:
        """`ReceiptV3` либо slug причины отказа (fail-closed)."""
        top = rec if isinstance(rec, Mapping) else {}
        raw_policy = top.get("tools_policy")
        policy = raw_policy if isinstance(raw_policy, Mapping) else {}
        disabled = _tool_ids(policy.get("disabled_tool_ids"))
        qualified = parse_qualified(top.get("qualified_models"))
        digest = tools_policy_digest(disabled, {q.model_id: q.tool_ids for q in qualified})
        problems = (
            ("receipt_malformed", not top),
            ("schema_mismatch", top.get("schema") != RECEIPT_SCHEMA),
            ("qualified_models_invalid", not qualified),
            ("tools_policy_invalid", policy.get("policy") != TOOLS_POLICY),
            ("tools_policy_digest_mismatch", policy.get("digest") != digest),
            ("disabled_tool_ids_invalid", not disabled),  # отпечаток пустого списка вычислим
        )
        return next((slug for slug, bad in problems if bad), cls(disabled, qualified))


def _protocol_ok(protocol: object) -> bool:
    """`api_version` совпадает с мостом, `protocol_version` — непустая строка."""
    fields = protocol if isinstance(protocol, Mapping) else {}
    version = fields.get("protocol_version")
    return fields.get("api_version") == RPC_API_VERSION and isinstance(version, str) and bool(version)


def _profile_ok(profile: object) -> bool:
    """Профиль настроек и его отпечаток совпадают с профилем моста."""
    got = {k: profile.get(k) for k in ("profile", "digest")} if isinstance(profile, Mapping) else None
    return got == {"profile": SETTINGS_PROFILE, "digest": settings_profile_digest()}


def _probes_ok(probes: object) -> bool:
    """Все пробы квалификации завершились `ok`."""
    return isinstance(probes, Mapping) and all(probes.get(n) == "ok" for n in RECEIPT_PROBES)


def receipt_gate_problem(rec: object) -> str:
    """Slug первой причины отказа допуска (протокол, tools, профиль, пробы) либо ''."""
    top = rec if isinstance(rec, Mapping) else {}
    parsed = ReceiptV3.parse(rec)
    problems = (
        ("protocol_mismatch", not _protocol_ok(top.get("protocol"))),
        (parsed if isinstance(parsed, str) else "", isinstance(parsed, str)),
        ("settings_profile_mismatch", not _profile_ok(top.get("settings_profile"))),
        ("probes_not_ok", not _probes_ok(top.get("probes"))),
    )
    return next((slug for slug, bad in problems if bad), "")


def json_digest(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()


def canonical_qualified_models(qualified: Mapping[str, Sequence[str]]) -> dict[str, list[str]]:
    """Каноническое `qualified_models`: `model_id -> sorted(tool_id)`."""
    return {str(model): sorted(map(str, ids)) for model, ids in qualified.items()}


def tools_policy_digest(
    disabled_ids: Sequence[str], qualified_models: Mapping[str, Sequence[str]] | None = None
) -> str:
    """Отпечаток политики tools: отключаемые id (+ `qualified_models` в receipt v3)."""
    payload: dict[str, object] = {"policy": TOOLS_POLICY, "disabled_tool_ids": sorted(map(str, disabled_ids))}
    if qualified_models is not None:
        payload["qualified_models"] = canonical_qualified_models(qualified_models)
    return json_digest(payload)


def _tool_ids(ids: object) -> tuple[str, ...]:
    """Непустой список непустых строк -> отсортированный кортеж; иначе `()`."""
    items = ids if isinstance(ids, list) else []
    ok = items and all(isinstance(i, str) and i for i in items)
    return tuple(sorted(map(str, items))) if ok else ()


def catalog_tool_ids(listed: object) -> tuple[str, ...]:
    """id tools из `list_tools` в порядке каталога; битый каталог — `()`."""
    items = listed if isinstance(listed, list) else []
    raw = [t.get("id") if isinstance(t, dict) else None for t in items]
    return tuple(dict.fromkeys(map(str, raw))) if _tool_ids(raw) else ()


def parse_qualified(raw: object) -> tuple[QualifiedModelSpec, ...]:
    """`dict[str, list[str]]` -> DTO по моделям; любое нарушение формы — `()`."""
    pairs = raw.items() if isinstance(raw, dict) else ()
    specs = tuple(QualifiedModelSpec(str(model), _tool_ids(ids)) for model, ids in pairs)
    return specs if specs and all(s.model_id and s.tool_ids for s in specs) else ()


def settings_profile_digest() -> str:
    """Отпечаток профиля настроек сессии, который мост выставляет и проверяет read-back'ом."""
    return json_digest(SETTINGS_PROFILE)
