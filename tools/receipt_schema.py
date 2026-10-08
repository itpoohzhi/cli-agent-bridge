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


def tools_policy_digest(disabled_ids: list) -> str:
    """Отпечаток политики tools: идентификатор политики + набор отключённых id (читают мост и установщик)."""
    return json_digest(
        {"policy": TOOLS_POLICY, "disabled_tool_ids": sorted(map(str, disabled_ids))}
    )


def settings_profile_digest() -> str:
    """Отпечаток профиля настроек сессии, который мост выставляет и проверяет read-back'ом."""
    return json_digest(SETTINGS_PROFILE)
