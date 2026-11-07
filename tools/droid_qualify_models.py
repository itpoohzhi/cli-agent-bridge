from __future__ import annotations

import argparse
import sys
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


def qualify_with_probe(
    open_rpc: Callable[[], DroidRpcSessionProtocol],
    settings: ProbeSettings,
    probed: tuple[str, Sequence[str]],
    models: Sequence[str],
) -> dict[str, tuple[str, ...]]:
    """`qualified_models`: проб-модель `(id, tools)` и `models` отдельными сессиями."""
    first = schema.QualifiedModelSpec(probed[0], tuple(sorted(probed[1])))
    specs = (first, *qualify_models(open_rpc, settings, models))
    return {q.model_id: q.tool_ids for q in specs}


def build_parser(description: str) -> argparse.ArgumentParser:
    """CLI `droid_image`: источник, workspace, модели, каталог манифестов, проверка receipt."""
    parser = argparse.ArgumentParser(prog="droid_image", description=description)
    add = parser.add_argument
    add("--source", default=None, help="бинарь droid (по умолчанию ~/.local/bin/droid)")
    add("--workspace", default=str(REPO_ROOT / "workspace"), help="workspace моста")
    add("--models", default="", help="модели через запятую (по умолчанию — из droid.yaml)")
    add("--providers-dir", default=str(REPO_ROOT / "providers.d"), help="каталог манифестов")
    add("--verify-receipt", default=None, metavar="PATH", help="проверить receipt без запуска: 0 — годен, 4 — нет")
    return parser


def verify_receipt_cli(args: argparse.Namespace) -> int:
    """`--verify-receipt`: проверка без запуска образа; 0 — годен, иначе `EXIT_VERIFY_FAILED`."""
    source = Path(str(args.source)) if args.source else None
    verdict = verify.verify_receipt(Path(str(args.verify_receipt)), Path(str(args.providers_dir)), source)
    stream = sys.stdout if verdict.ok else sys.stderr
    stream.write(f"droid_image: receipt v3 {'годен' if verdict.ok else verdict.reason}\n")
    return 0 if verdict.ok else verify.EXIT_VERIFY_FAILED


def resolve_models(args: argparse.Namespace) -> Sequence[str]:
    """Модели квалификации: `--models` либо все модели манифеста droid."""
    listed = [m.strip() for m in str(args.models).split(",") if m.strip()]
    return listed or verify.droid_models(Path(str(args.providers_dir)))
