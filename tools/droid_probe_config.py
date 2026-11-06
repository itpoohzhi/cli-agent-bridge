"""Конфигурация квалификации Droid из fleet, без импорта шлюза."""

from __future__ import annotations

import json
import math
import os
import shutil
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import cast

from core.backend_adapter import EFFORT_LEVELS
from core.gateway_execution_policy import require
from tools.receipt_schema import SETTINGS_PROFILE


class ProbeError(Exception):
    """Квалификация не пройдена: receipt не пишется."""


def get_probe_timeout_s() -> float:
    """Прочитать конечный положительный таймаут при каждом RPC-вызове."""
    try:
        raw = os.environ.get("DROID_PROBE_TIMEOUT_S", "").strip()
        if not raw:
            raw = "30.0"
        value = float(raw)
        require(
            all((math.isfinite(value), value > 0.0)),
            ValueError("non-positive or non-finite"),
        )
    except ValueError as exc:
        raise ProbeError(
            "DROID_PROBE_TIMEOUT_S должен быть конечным числом > 0"
        ) from exc
    return value


@contextmanager
def probe_directories(
    home: Path,
    cwd: Path,
    workspace: Path,
    ensure_private: Callable[[Path, Path], None],
) -> Iterator[Path]:
    """Изолировать состояние каждой модели и гарантировать очистку при отказе."""
    try:
        for directory in (home, cwd):
            if directory.exists():
                shutil.rmtree(directory)
            ensure_private(directory, workspace)
        settings_dir = home / ".factory"
        ensure_private(settings_dir, workspace)
        settings_path = settings_dir / "settings.json"
        settings_path.write_text(json.dumps(SETTINGS_PROFILE), encoding="utf-8")
        settings_path.chmod(0o600)
        yield settings_path
    finally:
        for directory in (home, cwd):
            if directory.exists():
                shutil.rmtree(directory)


def verify_disk_profile(
    path: Path, verify: Callable[[str, object, dict, tuple], set]
) -> None:
    """Повторно прочитать обязательные флаги с диска после квалификации."""
    try:
        written = json.loads(path.read_text(encoding="utf-8"))
        verify("settings.json", written, SETTINGS_PROFILE, tuple(SETTINGS_PROFILE))
    except (OSError, ValueError) as exc:
        raise ProbeError("settings.json: профиль на диске не подтверждён") from exc


def initialize_probe(
    call: Callable[[str, dict], tuple],
    cwd: Path,
    expected: dict,
    verify: Callable[[str, object, dict, tuple], set],
) -> tuple[str, set]:
    """Открыть сессию и подтвердить обязательные настройки без импорта RPC-транспорта."""
    result, _ = call(
        "droid.initialize_session",
        {
            **expected,
            "machineId": "droid-image-probe",
            "cwd": str(cwd),
            "title": "droid-image-probe",
        },
    )
    sid, settings = result.get("sessionId"), result.get("settings")
    require(
        all((isinstance(sid, str), bool(sid), isinstance(settings, dict))),
        ProbeError("spawn: initialize_session без sessionId или с подменой модели"),
    )
    confirmed = verify(
        "spawn", settings, expected, ("modelId", "reasoningEffort", "autonomyLevel")
    )
    return cast(str, sid), confirmed


def _extend(models: dict[str, str], configured: dict[str, dict]) -> None:
    """Дополнить обязательные модели и проверить явные переопределения effort."""
    extra = os.environ.get("DROID_EXTRA_PROBE_MODELS", "")
    for item in filter(None, map(str.strip, extra.split(","))):
        mid, _, effort = item.partition(":")
        mid, effort = mid.strip(), effort.strip()
        require(
            all((bool(mid), effort in ("", *EFFORT_LEVELS))),
            ProbeError("недопустимый effort или пустой id модели"),
        )
        models[mid] = effort if effort else models.get(mid, "high")
        catalogue = configured.get(mid, {"efforts": EFFORT_LEVELS})
        require(
            models[mid] in catalogue["efforts"],
            ProbeError("недопустимый effort модели fleet"),
        )


def probe_models() -> dict[str, str]:
    """Все модели fleet плюс `model[:effort]`, без исключения обязательных."""
    configured_path = os.environ.get("DROID_DSH_BRIDGE_FLEET")
    if not configured_path:
        configured_path = str(Path(__file__).resolve().parents[1] / "fleet.json")
    path = Path(configured_path)
    try:
        configured = {
            m["id"]: m
            for m in json.loads(path.read_text(encoding="utf-8"))["models"]
            if all((m.get("backend") == "droid", m.get("enabled", True)))
        }
        models = {mid: m["default_effort"] for mid, m in configured.items()}
        _extend(models, configured)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ProbeError(
            f"некорректная конфигурация проб: {type(exc).__name__}"
        ) from exc
    require(bool(models), ProbeError("в fleet отсутствуют модели droid"))
    return models
