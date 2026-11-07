from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple, Protocol

import droid_receipt_verify as verify
import receipt_schema as schema

REPO_ROOT = Path(__file__).resolve().parent.parent


class ProbeError(Exception):
    """Проба квалификации не пройдена: receipt не пишется."""


class RpcExchange(NamedTuple):
    """Ответ RPC-вызова: result и нотификации сессии."""

    result: Mapping[str, object]
    notifications: Sequence[object]


class DroidRpcSessionProtocol(Protocol):
    """RPC-клиент одного процесса droid (`droid_image._Rpc` и двойники)."""

    def call(self, method: str, params: Mapping[str, object], timeout: float = ...) -> RpcExchange:
        """Вызов метода droid; ошибки протокола — `ProbeError`."""
        ...

    def close(self) -> None:
        """Завершить процесс droid."""
        ...


@dataclass(frozen=True, slots=True)
class ProbeSettings:
    """Рабочий каталог, effort и autonomy проб-сессий."""

    cwd: Path
    effort: str
    autonomy: str


def init_params(settings: ProbeSettings, model: str) -> dict[str, object]:
    """Параметры initialize_session пробы: модель, effort и профиль настроек моста."""
    profile = {k: v for k, v in schema.SETTINGS_PROFILE.items() if k != "interactionMode"}
    return {
        "machineId": "droid-image-probe",
        "cwd": str(settings.cwd),
        "modelId": model,
        "reasoningEffort": settings.effort,
        "autonomyLevel": settings.autonomy,
        "interactionMode": "auto",
        "title": "droid-image-probe",
        **profile,
    }


def qualify_model(
    open_rpc: Callable[[], DroidRpcSessionProtocol], settings: ProbeSettings, model: str
) -> schema.QualifiedModelSpec:
    """Каталог tools модели: новая сессия -> initialize_session -> list_tools."""
    rpc = open_rpc()
    try:
        result, _ = rpc.call("droid.initialize_session", init_params(settings, model))
        reported = result.get("settings")
        shown = reported.get("modelId") if isinstance(reported, dict) else None
        if shown != model:
            raise ProbeError(f"qualify {model}: initialize_session подменил модель")
        tools, _ = rpc.call("droid.list_tools", {})
        ids = schema.catalog_tool_ids(tools.get("tools"))
        if not ids:
            raise ProbeError(f"qualify {model}: list_tools вернул некорректный каталог")
        return schema.QualifiedModelSpec(model, ids)
    finally:
        rpc.close()


def qualify_models(
    open_rpc: Callable[[], DroidRpcSessionProtocol], settings: ProbeSettings, models: Sequence[str]
) -> tuple[schema.QualifiedModelSpec, ...]:
    """Каждая модель — отдельной сессией; первая неудача — `ProbeError`."""
    return tuple(qualify_model(open_rpc, settings, model) for model in models)


def build_parser(description: str) -> argparse.ArgumentParser:
    """CLI `droid_image`: источник, workspace, модели и каталог манифестов."""
    parser = argparse.ArgumentParser(prog="droid_image", description=description)
    add = parser.add_argument
    add("--source", default=None, help="бинарь droid (по умолчанию ~/.local/bin/droid)")
    add("--workspace", default=str(REPO_ROOT / "workspace"), help="workspace моста")
    add("--models", default="", help="модели через запятую (по умолчанию — из droid.yaml)")
    add("--providers-dir", default=str(REPO_ROOT / "providers.d"), help="каталог манифестов")
    return parser


def resolve_models(args: argparse.Namespace) -> Sequence[str]:
    """Модели квалификации: `--models` либо все модели манифеста droid."""
    listed = [m.strip() for m in str(args.models).split(",") if m.strip()]
    return listed or verify.droid_models(Path(str(args.providers_dir)))
