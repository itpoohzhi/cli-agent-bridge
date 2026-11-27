"""Флаг-фолбэк: одноразовый повтор без --effort при отказе модели (default OFF)."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from agy_runtime.long_session_config import read_bool_setting

FLAG_EFFORT_REJECT_FALLBACK = "AGY_BRIDGE_EFFORT_REJECT_FALLBACK_ENABLED"
CONFIG_KEY_EFFORT_REJECT_FALLBACK = "effort_reject_fallback_enabled"
_EFFORT_REJECT_MARKER = "--effort is not supported for model"


def is_effort_reject_fallback_enabled(config_path: Path | None = None) -> bool:
    """OFF по умолчанию."""
    return read_bool_setting(
        CONFIG_KEY_EFFORT_REJECT_FALLBACK, FLAG_EFFORT_REJECT_FALLBACK, False, config_path=config_path
    )


def should_fallback_effortless(
    out: Mapping[str, object],
    effort: str,
    *,
    already_retried: bool,
    config_path: Path | None = None,
) -> bool:
    """True только для одноразового повтора без --effort при явном отказе модели."""
    if already_retried or str(effort or "").strip().lower() == "off":
        return False
    if out.get("state") != "agy_error":
        return False
    if _EFFORT_REJECT_MARKER not in str(out.get("err") or "").lower():
        return False
    return is_effort_reject_fallback_enabled(config_path)
