"""Конфигурация квалификации Droid из fleet, без импорта шлюза."""

from __future__ import annotations

import json
import os
from pathlib import Path

from core.backend_adapter import EFFORT_LEVELS


class ProbeError(Exception):
    """Квалификация не пройдена: receipt не пишется."""


def _extend(models: dict[str, str], configured: dict[str, dict]) -> None:
    """Дополнить обязательные модели и проверить явные переопределения effort."""
    extra = os.environ.get("DROID_EXTRA_PROBE_MODELS", "")
    for item in filter(None, map(str.strip, extra.split(","))):
        mid, _, effort = item.partition(":")
        mid, effort = mid.strip(), effort.strip()
        if not mid or (effort and effort not in EFFORT_LEVELS):
            raise ProbeError("недопустимый effort или пустой id модели")
        models[mid] = effort or models.get(mid, "high")
        if mid in configured and models[mid] not in configured[mid]["efforts"]:
            raise ProbeError("недопустимый effort модели fleet")


def probe_models() -> dict[str, str]:
    """Все модели fleet плюс `model[:effort]`, без исключения обязательных."""
    path = Path(
        os.environ.get("DROID_DSH_BRIDGE_FLEET")
        or Path(__file__).resolve().parents[1] / "fleet.json"
    )
    try:
        configured = {
            m["id"]: m
            for m in json.loads(path.read_text(encoding="utf-8"))["models"]
            if m.get("backend") == "droid" and m.get("enabled", True)
        }
        models = {mid: m["default_effort"] for mid, m in configured.items()}
        _extend(models, configured)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ProbeError(
            f"некорректная конфигурация проб: {type(exc).__name__}"
        ) from exc
    if not models:
        raise ProbeError("в fleet отсутствуют модели droid")
    return models
