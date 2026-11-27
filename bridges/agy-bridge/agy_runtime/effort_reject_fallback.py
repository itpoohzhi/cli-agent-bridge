"""Флаг-фолбэк: одноразовый повтор без --effort при отказе модели (default OFF)."""
from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Mapping
from pathlib import Path

from agy_runtime.long_session_config import read_bool_setting

FLAG_EFFORT_REJECT_FALLBACK = "AGY_BRIDGE_EFFORT_REJECT_FALLBACK_ENABLED"
CONFIG_KEY_EFFORT_REJECT_FALLBACK = "effort_reject_fallback_enabled"
_EFFORT_REJECT_MARKER = "--effort is not supported for model"
_REJECTED_PAIRS_MAX = 64
_REJECTED_LOCK = threading.Lock()
_REJECTED_PAIRS: OrderedDict[tuple[str, str], None] = OrderedDict()


def is_effort_reject_fallback_enabled(config_path: Path | None = None) -> bool:
    """OFF по умолчанию."""
    return read_bool_setting(
        CONFIG_KEY_EFFORT_REJECT_FALLBACK, FLAG_EFFORT_REJECT_FALLBACK, False, config_path=config_path
    )


def _norm_pair(model: str, effort: str) -> tuple[str, str]:
    return (str(model or "").strip(), str(effort or "").strip().lower())


def record_effort_rejection(model: str, effort: str) -> None:
    """Запомнить отказавшую пару (model, effort) в bounded thread-safe LRU-кэше."""
    pair = _norm_pair(model, effort)
    with _REJECTED_LOCK:
        _REJECTED_PAIRS[pair] = None
        _REJECTED_PAIRS.move_to_end(pair)
        while len(_REJECTED_PAIRS) > _REJECTED_PAIRS_MAX:
            _REJECTED_PAIRS.popitem(last=False)


def clear_effort_rejections_for_tests() -> None:
    """Сброс кэша отказов (только для тестов)."""
    with _REJECTED_LOCK:
        _REJECTED_PAIRS.clear()


def resolve_effort_with_fallback(
    model: str, effort: str, effort_source: str, *, config_path: Path | None = None
) -> tuple[str, str]:
    """Turn 2+: уже отказавшая пара сразу идёт без --effort, не ломая hot-resume."""
    if is_effort_reject_fallback_enabled(config_path):
        with _REJECTED_LOCK:
            rejected = _norm_pair(model, effort) in _REJECTED_PAIRS
        if rejected:
            return ("off", "effort_reject_fallback")
    return (effort, effort_source)


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
