"""Общая схема receipt допуска образа droid: константы и отпечатки (RW-009, RW-013).

Модуль не читает fleet.json, не открывает сокеты и не импортирует мост. Его читают и
мост (`server.py`), и установщик `tools/droid_image.py`, поэтому отпечатки обязаны совпадать
побайтово: любое изменение значений здесь инвалидирует ранее выданные receipt.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, cast

from core.gateway_execution_policy import require

RPC_API_VERSION = "1.0.0"
RECEIPT_SCHEMA = 2
TOOLS_POLICY = "disable-all-listed-keep-read-for-images"
SETTINGS_PROFILE = {
    "disableBuiltinSkills": True,
    "autoRejectPermissionRequests": True,
    "interactionMode": "auto",
}
RECEIPT_PROBES = ("spawn", "update", "load")


def json_digest(obj: Any) -> str:
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
    qualified: object, disabled_ids: list
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


def _receipt_section(rec: dict, name: str, message: str) -> dict:
    """Получить обязательную секцию receipt без неявных преобразований."""
    section = rec.get(name)
    require(isinstance(section, dict), ValueError(message))
    return cast(dict, section)


def validate_model_catalog(
    qualified: object, model: str, listed: list, error_type: type[Exception]
) -> None:
    """Сверить фактический каталог модели после уже проверенного receipt."""
    require(
        all((isinstance(qualified, dict), bool(qualified))),
        error_type(
            "receipt missing or invalid qualified_models, re-run droid_image.py"
        ),
    )
    expected = cast(dict, qualified).get(model)
    error = error_type("native tool catalogue differs from the qualified tools policy")
    require(all((bool(listed), isinstance(expected, list))), error)
    require(sorted(listed) == sorted(cast(list, expected)), error)


def validate_receipt_components(rec: dict) -> None:
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


def _validate_receipt_policy(rec: dict) -> None:
    """Сверить строгие каталоги и их канонический отпечаток."""
    message = "droid receipt: tools policy mismatch"
    policy = _receipt_section(rec, "tools_policy", message)
    ids = policy.get("disabled_tool_ids")
    require(all((isinstance(ids, list), bool(ids))), ValueError(message))
    listed = cast(list, ids)
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


def tools_policy_digest(disabled_ids: list, qualified_models: object = None) -> str:
    """Schema-2 расширение: отпечаток включает канонические каталоги моделей.

    Старые receipt без каталогов должны быть перевыпущены, а не приняты молча.
    """
    policy: dict[str, Any] = {
        "policy": TOOLS_POLICY,
        "disabled_tool_ids": sorted(map(str, disabled_ids)),
    }
    if qualified_models is not None:
        qualified = validate_qualified_models(qualified_models, disabled_ids)
        policy["qualified_models"] = {
            mid: sorted(tools) for mid, tools in qualified.items()
        }
    return json_digest(policy)


def settings_profile_digest() -> str:
    """Отпечаток профиля настроек сессии, который мост выставляет и проверяет read-back'ом."""
    return json_digest(SETTINGS_PROFILE)
