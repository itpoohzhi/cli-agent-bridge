#!/usr/bin/env python3
"""CLI компилятора каталога: `providers.d/*.yaml` -> `fleet.compiled.json` + `catalog.lock.json`.

Примеры:
    python3 tools/fleet_compile.py --check            # компиляция + self-check + сверка
    python3 tools/fleet_compile.py --write            # запись в <state>/ (атомарно)
    python3 tools/fleet_compile.py --explain gpt-6.1-sol   # primary/alternates

Коды выхода: 0 — успех; 1 — дефект компиляции/расхождение; 3 — ошибка использования.
Каталог состояния — env `BRIDGE_STATE_DIR` (дефолт `~/work/cli-agent-bridge/state`).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.backend_adapter import build_catalog  # noqa: E402
from core.catalog_promote import write_compiled_state  # noqa: E402
from core.fleet_compiler import (  # noqa: E402
    CompileError,
    CompileResult,
    canonical_json,
    compile_from_disk,
    default_kinds,
    load_receipts,
    render_fleet_json,
)
from core.fleet_explain import explain_model  # noqa: E402
from core.model_lifecycle import LifecycleError, LifecycleRegistry  # noqa: E402
from core.param_adapter import resolve_state_dir  # noqa: E402
from core.provider_manifest import load_manifests  # noqa: E402

REGISTRY_FILE = "model-lifecycle.json"
FLEET_FILE = "fleet.compiled.json"
SIDECAR_FILE = "catalog.lock.json"


def _normalized(data: dict) -> dict:
    """Нормализованный каталог без порядка (для сверки эквивалентности)."""
    catalog = build_catalog(data, default_kinds())
    catalog.pop("order", None)
    catalog.pop("backend_order", None)
    catalog.pop("rejected", None)
    return catalog


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="скомпилировать и сверить")
    mode.add_argument("--write", action="store_true", help="записать fleet и сайдкар")
    mode.add_argument("--explain", metavar="MODEL_ID", default=None, help="JSON: primary/alternates модели")
    parser.add_argument("--providers-dir", type=Path, default=None)
    parser.add_argument("--fleet-meta", type=Path, default=None, help="_fleet.yaml")
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=None,
        help="каталог состояния (переопределяет BRIDGE_STATE_DIR)",
    )
    parser.add_argument(
        "--output", type=Path, default=None, help="путь fleet.compiled.json"
    )
    parser.add_argument(
        "--sidecar", type=Path, default=None, help="путь catalog.lock.json"
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=ROOT / "fleet.json",
        help="эталон для --check (дефолт <repo>/fleet.json)",
    )
    parser.add_argument(
        "--now", default=None, help="метка compiled_at (для детерминизма)"
    )
    return parser


def _report_rejections(result: CompileResult) -> None:
    """Отклонённые модели, провайдеры и предупреждения — в stderr."""
    for mid, reason in sorted(result.rejected.items()):
        print(f"fleet_model_rejected model={mid} reason={reason}", file=sys.stderr)
    for pid, reasons in sorted(result.rejected_providers.items()):
        print(
            f"fleet_provider_rejected provider={pid} reason={','.join(reasons)}",
            file=sys.stderr,
        )
    for warning in result.warnings:
        print(f"warning: {warning}", file=sys.stderr)


def _compile_state(args: argparse.Namespace, state: Path) -> CompileResult | int:
    """Реестр + компиляция манифестов; сбой — код 1."""
    registry_path = state / REGISTRY_FILE
    try:
        registry = (
            LifecycleRegistry.load(registry_path) if registry_path.is_file() else None
        )
    except LifecycleError as exc:
        print(f"FAIL: lifecycle_unreadable: {exc}", file=sys.stderr)
        return 1
    now = args.now if args.now is not None else time.strftime("%Y-%m-%dT%H:%M:%S%z")
    try:
        result = compile_from_disk(
            args.providers_dir,
            args.fleet_meta,
            kinds=default_kinds(),
            registry=registry,
            receipts=load_receipts(state / "probes"),
            now=now,
        )
    except CompileError as exc:
        print(
            f"FAIL: compile_error reason={exc.slug} model={exc.model}", file=sys.stderr
        )
        return 1
    _report_rejections(result)
    return result


def _explain(args: argparse.Namespace, result: CompileResult) -> int:
    """`--explain`: JSON выбора провайдера; неизвестная модель — код 1."""
    manifests = load_manifests(args.providers_dir, default_kinds()).manifests
    entry = explain_model(result.sidecar, manifests, args.explain)
    if entry is None:
        print(f"FAIL: model_unknown model={args.explain}", file=sys.stderr)
        return 1
    print(json.dumps(entry.to_document(), sort_keys=True, indent=2, ensure_ascii=False))
    return 0


def _check(args: argparse.Namespace, output: Path, result: CompileResult) -> int:
    """`--check`: сверка с `--output` либо с эталоном `--reference`."""
    fleet_bytes = render_fleet_json(result.fleet)
    if args.output is not None and output.is_file():
        if output.read_bytes() != fleet_bytes:
            print(f"FAIL: fleet_compiled_stale path={output}", file=sys.stderr)
            return 1
        print(f"OK: {output} is up to date")
        return 0
    reference = args.reference
    if reference.is_file():
        try:
            expected = _normalized(json.loads(reference.read_text(encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001 - диагностика эталона
            print(f"FAIL: reference_unreadable: {exc}", file=sys.stderr)
            return 1
        if canonical_json(expected) != canonical_json(_normalized(result.fleet)):
            print(f"FAIL: golden_mismatch reference={reference}", file=sys.stderr)
            return 1
        print(f"OK: compiled catalog is equivalent to {reference.name}")
        return 0
    print("OK: compiled and self-checked (no reference to compare)")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    state = args.state_dir or resolve_state_dir()
    output = args.output or state / FLEET_FILE
    sidecar_path = args.sidecar or state / SIDECAR_FILE
    result = _compile_state(args, state)
    if isinstance(result, int):
        return result
    if args.explain is not None:
        return _explain(args, result)
    if args.write:
        write_compiled_state(result, output, sidecar_path)
        print(f"OK: wrote {output} and {sidecar_path} models={len(result.fleet['models'])}")
        return 0
    return _check(args, output, result)


if __name__ == "__main__":
    sys.exit(main())
