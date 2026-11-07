"""Конфигурация квалификации Droid из fleet, без импорта шлюза."""

from __future__ import annotations

import json
import math
import os
import shutil
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, cast

from core.backend_adapter import EFFORT_LEVELS
from core.gateway_execution_policy import require
from tools.receipt_schema import SETTINGS_PROFILE


FLEET_PATH = Path(__file__).resolve().parents[1] / "fleet.json"


@dataclass(frozen=True)
class ProbeTarget:
    """Одна квалифицируемая пара модели и уровня рассуждения."""

    model: str
    effort: str


class ProbeFacts(TypedDict):
    """JSON-совместимый результат квалификации с типизированными полями."""

    protocol_version: str
    disabled_tool_ids: list[str]
    qualified_models: dict[str, list[str]]
    not_confirmed_readback_by_model: dict[str, list[str]]
    probes: dict[str, str]
    readback: dict[str, list[str]]


class ProbeError(RuntimeError):
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
) -> Generator[Path]:
    """Изолировать состояние каждой модели и гарантировать очистку при отказе."""
    try:
        for directory in (home, cwd):
            if directory.exists():
                shutil.rmtree(directory)
            ensure_private(directory, workspace)
        settings_dir = home / ".factory"
        ensure_private(settings_dir, workspace)
        settings_path = settings_dir / "settings.json"
        _ = settings_path.write_text(json.dumps(SETTINGS_PROFILE), encoding="utf-8")
        settings_path.chmod(0o600)
        yield settings_path
    finally:
        for directory in (home, cwd):
            if directory.exists():
                shutil.rmtree(directory)


def verify_disk_profile(
    path: Path,
    verify: Callable[[str, object, dict[str, object], tuple[str, ...]], set[str]],
) -> None:
    """Повторно прочитать обязательные флаги с диска после квалификации."""
    try:
        written: object = cast(object, json.loads(path.read_text(encoding="utf-8")))
        _ = verify("settings.json", written, SETTINGS_PROFILE, tuple(SETTINGS_PROFILE))
    except (OSError, ValueError) as exc:
        raise ProbeError("settings.json: профиль на диске не подтверждён") from exc


def initialize_probe(
    call: Callable[
        [str, dict[str, object]], tuple[dict[str, object], list[dict[str, object]]]
    ],
    cwd: Path,
    expected: dict[str, object],
    verify: Callable[[str, object, dict[str, object], tuple[str, ...]], set[str]],
) -> tuple[str, set[str]]:
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


def probe_models() -> dict[str, str]:
    """Все модели fleet плюс `model[:effort]`, без исключения обязательных."""
    return load_droid_probe_models(
        Path(os.environ.get("DROID_DSH_BRIDGE_FLEET") or FLEET_PATH)
    )


def load_droid_probe_models(path: Path = FLEET_PATH) -> dict[str, str]:
    """Совместимое представление default_effort без потери явных overrides."""
    configured = _configured_models(path)
    models = {
        mid: cast(str, model["default_effort"]) for mid, model in configured.items()
    }
    models.update((t.model, t.effort) for t in _extra_targets(configured))
    return models


def _configured_models(path: Path) -> dict[str, dict[str, object]]:
    """Прочитать обязательные модели из указанного fleet."""
    try:
        data = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
        models = cast(list[dict[str, object]], data["models"])
        configured = {
            cast(str, model["id"]): model
            for model in models
            if model.get("backend") == "droid" and model.get("enabled", True)
        }
        require(bool(configured), ProbeError("в fleet отсутствуют модели droid"))
        for mid, model in configured.items():
            efforts = model["efforts"]
            require(
                isinstance(model["id"], str)
                and bool(mid)
                and isinstance(efforts, list),
                ProbeError("некорректная модель fleet"),
            )
            require(
                all(isinstance(e, str) for e in cast(list[object], efforts)),
                ProbeError("недопустимый effort модели fleet"),
            )
            require(
                model["default_effort"] in cast(list[str], efforts),
                ProbeError("недопустимый default_effort модели fleet"),
            )
        return configured
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ProbeError(
            f"некорректная конфигурация проб: {type(exc).__name__}"
        ) from exc


def load_droid_probe_targets(path: Path = FLEET_PATH) -> tuple[ProbeTarget, ...]:
    """Квалифицировать все опубликованные efforts и дополнительные пары без перезаписи."""
    configured = _configured_models(path)
    targets = {
        ProbeTarget(mid, effort): None
        for mid, model in configured.items()
        for effort in dict.fromkeys(
            [cast(str, model["default_effort"]), *cast(list[str], model["efforts"])]
        )
    }
    targets.update((target, None) for target in _extra_targets(configured))
    return tuple(targets)


def _extra_targets(configured: dict[str, dict[str, object]]) -> tuple[ProbeTarget, ...]:
    """Сохранить каждую дополнительную пару, включая повторные id."""
    defaults = {
        mid: cast(str, model["default_effort"]) for mid, model in configured.items()
    }
    targets: list[ProbeTarget] = []
    for item in filter(
        None, map(str.strip, os.environ.get("DROID_EXTRA_PROBE_MODELS", "").split(","))
    ):
        mid, _, effort = item.partition(":")
        mid, effort = mid.strip(), effort.strip()
        require(
            bool(mid) and effort in ("", *EFFORT_LEVELS),
            ProbeError("недопустимый effort или пустой id модели"),
        )
        effort = effort or defaults.get(mid, "high")
        require(
            effort
            in cast(
                list[str] | tuple[str, ...],
                configured.get(mid, {"efforts": EFFORT_LEVELS})["efforts"],
            ),
            ProbeError("недопустимый effort модели fleet"),
        )
        defaults[mid] = effort
        targets.append(ProbeTarget(mid, effort))
    return tuple(targets)
