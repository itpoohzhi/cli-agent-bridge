"""Общая схема receipt допуска образа droid: константы и отпечатки (RW-009, RW-013).

Модуль самодостаточен: только stdlib, без fleet.json, сокетов и импорта моста. Его читают и
мост (`server.py`), и установщик `tools/droid_image.py`, поэтому отпечатки обязаны совпадать
побайтово: любое изменение значений здесь инвалидирует ранее выданные receipt.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

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


def validate_qualified_models(
    qualified: object, disabled_ids: list
) -> dict[str, list[str]]:
    """Строгая проверка каталогов моделей, без приведения неверных типов."""
    if not isinstance(qualified, dict) or not qualified:
        raise ValueError(
            "receipt missing or invalid qualified_models, re-run droid_image.py"
        )
    allowed = set(disabled_ids)
    for model, tools in qualified.items():
        if (
            not isinstance(model, str)
            or not model
            or not isinstance(tools, list)
            or not tools
            or any(not isinstance(tool, str) or tool not in allowed for tool in tools)
        ):
            raise ValueError(
                "receipt missing or invalid qualified_models, re-run droid_image.py"
            )
    return qualified


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
