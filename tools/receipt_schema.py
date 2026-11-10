"""Общая схема receipt допуска образа droid: константы и отпечатки (RW-009, RW-013).

Модуль не читает fleet.json, не открывает сокеты и не импортирует мост. Его читают и
мост (`server.py`), и установщик `tools/droid_image.py`, поэтому отпечатки обязаны совпадать
побайтово: любое изменение значений здесь инвалидирует ранее выданные receipt.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TypedDict, cast

from core.gateway_execution_policy import require

RPC_API_VERSION = "1.0.0"
RECEIPT_SCHEMA = 3  # v3: qualified_models (tools каждой модели) + qualified_targets (пары model/effort)
TOOLS_POLICY = "disable-all-listed-keep-read-for-images"
SETTINGS_PROFILE: dict[str, object] = {
    "disableBuiltinSkills": True,
    "autoRejectPermissionRequests": True,
    "interactionMode": "auto",
}
RECEIPT_PROBES = ("spawn", "update", "load")


class ReceiptToolsPolicy(TypedDict):
    """JSON-конверт проверенной политики инструментов."""

    policy: str
    disabled_tool_ids: list[str]
    digest: str


class ReceiptSettings(TypedDict):
    """Профиль и фактически подтверждённый read-back."""

    profile: dict[str, object]
    digest: str
    readback: dict[str, list[str]]


class QualifiedTarget(TypedDict):
    """Квалифицированная пара модели и уровня рассуждения (внутренняя деталь receipt)."""

    model: str
    effort: str


class DroidReceipt(TypedDict):
    """Типизированный JSON receipt, совместимый с прежними словарными читателями."""

    schema: int
    image_path: str
    image_sha256: str
    protocol: dict[str, str]
    tools_policy: ReceiptToolsPolicy
    settings_profile: ReceiptSettings
    probes: dict[str, str]
    qualified_models: dict[str, list[str]]
    # Поуровневое доказательство всех пройденных пар (model, effort); в HTTP-ответы не
    # сериализуется и остаётся внутренней частью receipt.
    qualified_targets: list[QualifiedTarget]
    not_confirmed_readback_by_model: dict[str, list[str]]
    source: dict[str, str | int]
    created_at: int


def json_digest(obj: object) -> str:
    return hashlib.sha256(
        json.dumps(
            obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()


def _validate_model_tools(tools: object, allowed: set[str]) -> None:
    """Проверить непустой список строковых идентификаторов инструментов."""
    error = ValueError(
        "receipt missing or invalid qualified_models, re-run droid_image.py"
    )
    require(isinstance(tools, list), error)
    listed = cast(list[object], tools)
    require(bool(listed), error)
    require(all(isinstance(tool, str) for tool in listed), error)
    require(allowed.issuperset(cast(list[str], listed)), error)


def validate_qualified_models(
    qualified: object, disabled_ids: list[str]
) -> dict[str, list[str]]:
    """Строгая проверка каталогов моделей, без приведения неверных типов."""
    error = ValueError(
        "receipt missing or invalid qualified_models, re-run droid_image.py"
    )
    require(isinstance(qualified, dict), error)
    catalog = cast(dict[object, object], qualified)
    require(bool(catalog), error)
    allowed = set(disabled_ids)
    for model, tools in catalog.items():
        require(all((isinstance(model, str), bool(model))), error)
        _validate_model_tools(tools, allowed)
    return cast(dict[str, list[str]], catalog)


def _receipt_section(
    rec: Mapping[str, object], name: str, message: str
) -> dict[str, object]:
    """Получить обязательную секцию receipt без неявных преобразований."""
    section = rec.get(name)
    require(isinstance(section, dict), ValueError(message))
    return cast(dict[str, object], section)


def validate_model_catalog(
    qualified: object, model: str, listed: list[str], error_type: type[Exception]
) -> None:
    """Сверить фактический каталог модели после уже проверенного receipt."""
    require(
        all((isinstance(qualified, dict), bool(qualified))),
        error_type(
            "receipt missing or invalid qualified_models, re-run droid_image.py"
        ),
    )
    expected = cast(dict[str, object], qualified).get(model)
    error = error_type("native tool catalogue differs from the qualified tools policy")
    require(all((bool(listed), isinstance(expected, list))), error)
    require(sorted(listed) == sorted(cast(list[str], expected)), error)


def validate_qualified_targets(
    targets: object, qualified_models: object
) -> list[QualifiedTarget]:
    """Проверить поуровневую квалификацию: непустые пары (модель, effort) без дублей.

    Каждая модель обязана присутствовать в строгом каталоге `qualified_models`, иначе
    поуровневое доказательство не относится к квалификации этого receipt.
    """
    error = ValueError(
        "receipt missing or invalid qualified_targets, re-run droid_image.py"
    )
    require(isinstance(targets, list), error)
    listed = cast(list[object], targets)
    require(bool(listed), error)
    catalog = (
        cast(dict[object, object], qualified_models)
        if isinstance(qualified_models, dict)
        else {}
    )
    pairs: set[tuple[str, str]] = set()
    for entry in listed:
        require(isinstance(entry, dict), error)
        item = cast(dict[str, object], entry)
        model, effort = item.get("model"), item.get("effort")
        require(
            all(
                (
                    isinstance(model, str),
                    bool(model),
                    isinstance(effort, str),
                    bool(effort),
                )
            ),
            error,
        )
        require(cast(str, model) in catalog, error)
        pairs.add((cast(str, model), cast(str, effort)))
    require(len(pairs) == len(listed), error)
    return cast(list[QualifiedTarget], listed)


def validate_receipt_components(rec: Mapping[str, object]) -> None:
    """Проверить протокол, квалификацию и профиль общей схемы receipt."""
    message = "droid receipt: stream-jsonrpc protocol version mismatch"
    protocol = _receipt_section(rec, "protocol", message)
    require(
        all(
            (
                protocol.get("api_version") == RPC_API_VERSION,
                isinstance(protocol.get("protocol_version"), str),
                bool(protocol.get("protocol_version")),
            )
        ),
        ValueError(message),
    )
    _validate_receipt_policy(rec)
    message = "droid receipt: settings profile mismatch"
    profile = _receipt_section(rec, "settings_profile", message)
    require(
        all(
            (
                profile.get("profile") == SETTINGS_PROFILE,
                profile.get("digest") == settings_profile_digest(),
            )
        ),
        ValueError(message),
    )
    message = "droid receipt: qualification probes are not all ok"
    probes = _receipt_section(rec, "probes", message)
    require(
        all(probes.get(name) == "ok" for name in RECEIPT_PROBES), ValueError(message)
    )


def _validate_receipt_policy(rec: Mapping[str, object]) -> None:
    """Сверить строгие каталоги и их канонический отпечаток."""
    message = "droid receipt: tools policy mismatch"
    policy = _receipt_section(rec, "tools_policy", message)
    ids = policy.get("disabled_tool_ids")
    require(all((isinstance(ids, list), bool(ids))), ValueError(message))
    listed = cast(list[str], ids)
    qualified = validate_qualified_models(rec.get("qualified_models"), listed)
    require(
        all(
            (
                policy.get("policy") == TOOLS_POLICY,
                policy.get("digest") == tools_policy_digest(listed, qualified),
            )
        ),
        ValueError(message),
    )
    targets = validate_qualified_targets(rec.get("qualified_targets"), qualified)
    covered = {entry["model"] for entry in targets}
    require(
        covered == set(qualified),
        ValueError(
            "receipt missing or invalid qualified_targets, re-run droid_image.py"
        ),
    )


def tools_policy_digest(
    disabled_ids: Sequence[str], qualified_models: object = None
) -> str:
    """Schema-2 расширение: отпечаток включает канонические каталоги моделей.

    Старые receipt без каталогов должны быть перевыпущены, а не приняты молча.
    """
    policy: dict[str, object] = {
        "policy": TOOLS_POLICY,
        "disabled_tool_ids": sorted(map(str, disabled_ids)),
    }
    if qualified_models is not None:
        qualified = validate_qualified_models(qualified_models, disabled_ids)
        policy["qualified_models"] = {
            mid: sorted(tools) for mid, tools in qualified.items()
        }
    return json_digest(policy)


@dataclass(frozen=True, slots=True)
class QualifiedModelSpec:
    """Модель и отсортированные id нативных tools, которые droid показывает ей."""

    model_id: str
    tool_ids: tuple[str, ...]


def _qualified_digest(
    disabled: tuple[str, ...], qualified: tuple[QualifiedModelSpec, ...]
) -> str:
    """Отпечаток политики без валидации формы: совпадает с `tools_policy_digest` на корректных данных."""
    payload = {
        "policy": TOOLS_POLICY,
        "disabled_tool_ids": sorted(disabled),
        "qualified_models": {q.model_id: sorted(q.tool_ids) for q in qualified},
    }
    return json_digest(payload)


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
        digest = _qualified_digest(disabled, qualified)
        problems = (
            ("receipt_malformed", not top),
            ("schema_mismatch", top.get("schema") != RECEIPT_SCHEMA),
            ("qualified_models_invalid", not qualified),
            ("tools_policy_invalid", policy.get("policy") != TOOLS_POLICY),
            ("tools_policy_digest_mismatch", policy.get("digest") != digest),
            (
                "disabled_tool_ids_invalid",
                not disabled,
            ),  # отпечаток пустого списка вычислим
        )
        return next((slug for slug, bad in problems if bad), cls(disabled, qualified))


def _protocol_ok(protocol: object) -> bool:
    """`api_version` совпадает с мостом, `protocol_version` — непустая строка."""
    fields = protocol if isinstance(protocol, Mapping) else {}
    version = fields.get("protocol_version")
    return (
        fields.get("api_version") == RPC_API_VERSION
        and isinstance(version, str)
        and bool(version)
    )


def _profile_ok(profile: object) -> bool:
    """Профиль настроек и его отпечаток совпадают с профилем моста."""
    got = (
        {k: profile.get(k) for k in ("profile", "digest")}
        if isinstance(profile, Mapping)
        else None
    )
    return got == {"profile": SETTINGS_PROFILE, "digest": settings_profile_digest()}


def _probes_ok(probes: object) -> bool:
    """Все пробы квалификации завершились `ok`."""
    return isinstance(probes, Mapping) and all(
        probes.get(n) == "ok" for n in RECEIPT_PROBES
    )


def _targets_ok(top: Mapping[str, object]) -> bool:
    """Пары (model, effort) корректны и покрывают ровно квалифицированные модели."""
    qualified = top.get("qualified_models")
    try:
        targets = validate_qualified_targets(top.get("qualified_targets"), qualified)
    except ValueError:
        return False
    return {entry["model"] for entry in targets} == set(
        cast(dict[str, object], qualified)
    )


def receipt_gate_problem(rec: object) -> str:
    """Slug первой причины отказа допуска (протокол, tools, профиль, пробы) либо ''."""
    top = rec if isinstance(rec, Mapping) else {}
    parsed = ReceiptV3.parse(rec)
    problems = (
        ("protocol_mismatch", not _protocol_ok(top.get("protocol"))),
        (parsed if isinstance(parsed, str) else "", isinstance(parsed, str)),
        (
            "qualified_targets_invalid",
            not isinstance(parsed, str) and not _targets_ok(top),
        ),
        ("settings_profile_mismatch", not _profile_ok(top.get("settings_profile"))),
        ("probes_not_ok", not _probes_ok(top.get("probes"))),
    )
    return next((slug for slug, bad in problems if bad), "")


def canonical_qualified_models(
    qualified: Mapping[str, Sequence[str]],
) -> dict[str, list[str]]:
    """Каноническое `qualified_models`: `model_id -> sorted(tool_id)`."""
    return {str(model): sorted(map(str, ids)) for model, ids in qualified.items()}


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
    specs = tuple(
        QualifiedModelSpec(str(model), _tool_ids(ids)) for model, ids in pairs
    )
    return specs if specs and all(s.model_id and s.tool_ids for s in specs) else ()


def settings_profile_digest() -> str:
    """Отпечаток профиля настроек сессии, который мост выставляет и проверяет read-back'ом."""
    return json_digest(SETTINGS_PROFILE)
