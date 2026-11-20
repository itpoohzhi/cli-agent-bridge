#!/usr/bin/env python3
"""CLI управления оперативными весами маршрутизации и безопасной пересборки каталога."""
from __future__ import annotations

import argparse, contextlib, fcntl, json, os, re, stat, subprocess, sys, time, urllib.error, urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, NamedTuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.routing_weights_domain import WeightsOverrideDoc, build_catalog_routing_view  # noqa: E402
from core.routing_weights_runtime import RoutingWeightsStore, WeightsCorruptError, WeightsLockTimeoutError, default_weights_path  # noqa: E402
from core.runtime_env import DynamicFlagSource, NumSpec, parse_number  # noqa: E402

_EXIT_OK, _EXIT_ERR, _EXIT_CORRUPT, _EXIT_BUSY, _MAX_WEIGHT = 0, 1, 2, 3, 10_000
_WEIGHT_RE, _TRUE_VALUES = re.compile(r"^\d+$"), frozenset({"1", "true", "yes", "on"})
_DEFAULT_STATE_DIR, _DEFAULT_HEALTH_URL, _DEFAULT_SERVICE = "~/work/cli-agent-bridge/state", "http://127.0.0.1:9882/health", "com.user.dsh-hub"
_HEALTH_TIMEOUT, _COMPILE_TIMEOUT = NumSpec(("BRIDGE_HEALTH_TIMEOUT_S",), 1.5, 0.2, 15.0), NumSpec(("BRIDGE_COMPILE_TIMEOUT_S",), 60.0, 5.0, 600.0)
_LOCK_WAIT, _LOCK_POLL = NumSpec(("BRIDGE_LIFECYCLE_LOCK_WAIT_S",), 30.0, 0.1, 120.0), NumSpec(("BRIDGE_LIFECYCLE_LOCK_POLL_S",), 0.05, 0.005, 1.0)
_Context = NamedTuple("_Context", [("fleet_path", Path), ("lock_path", Path | None), ("weights_path", Path), ("compiled_enabled", bool), ("weights_enabled", bool), ("transport_routing_enabled", bool), ("updated_by", str)])
class _CliError(Exception):
    """Управляемая ошибка CLI с точным кодом возврата."""
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message
class _ArgParser(argparse.ArgumentParser):
    """Парсер аргументов с кодом возврата 1 вместо стандартного 2."""
    def error(self, message: str) -> None:
        self.exit(_EXIT_ERR, f"{self.prog}: error: {message}\n")
def _env_num(spec: NumSpec) -> float:
    return float(parse_number(os.environ, spec))
def _dynamic_flag(name: str, default: bool, fallback: bool) -> bool:
    """Читает флаг из dynamic_config.json или env (fail-closed при битом JSON)."""
    path = Path(os.path.expanduser(os.environ.get("BRIDGE_DYNAMIC_CONFIG_PATH") or "~/.config/cli-agent-bridge/dynamic_config.json"))
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError):
        return fallback
    raw = data.get(name, os.environ.get(name, default)) if isinstance(data, dict) else None
    return fallback if raw is None else (raw if isinstance(raw, bool) else str(raw).strip().lower() in _TRUE_VALUES)
def _transport_routing_enabled() -> bool:
    """Читает мастер-флаг BRIDGE_TRANSPORT_ROUTING_ENABLED (fail-closed -> False)."""
    try:
        return DynamicFlagSource("BRIDGE_TRANSPORT_ROUTING_ENABLED", default=True).enabled(fallback=False)
    except Exception:
        return False
def _build_context(args: argparse.Namespace) -> _Context:
    """Разрешает активный fleet.json, catalog.lock.json, routing_weights.json и флаги."""
    compiled_en = _dynamic_flag("BRIDGE_COMPILED_FLEET_ENABLED", False, False)
    weights_en = _dynamic_flag("BRIDGE_ROUTING_WEIGHTS_ENABLED", True, False)
    compiled = Path(os.path.expanduser(os.environ.get("BRIDGE_STATE_DIR") or _DEFAULT_STATE_DIR)) / "fleet.compiled.json"
    fleet = Path(os.path.expanduser(args.fleet)) if args.fleet else (compiled if compiled_en and compiled.is_file() else ROOT / "fleet.json")
    lock = Path(os.path.expanduser(args.lock)) if args.lock else (fleet.parent / "catalog.lock.json")
    if args.lock and not lock.is_file():
        raise _CliError(_EXIT_ERR, f"lock_not_found: {lock}")
    return _Context(fleet, lock if lock.is_file() else None, Path(os.path.expanduser(args.weights)) if args.weights else default_weights_path(), compiled_en, weights_en, _transport_routing_enabled(), args.updated_by)
def _load_view(ctx: _Context, doc: WeightsOverrideDoc | None) -> dict[str, Any]:
    """Строит матрицу маршрутизации активного каталога."""
    def _rd(path: Path, kind: str) -> dict[str, Any]:
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise _CliError(_EXIT_ERR, f"{kind}_unreadable: {exc}") from None
        if not isinstance(obj, dict):
            raise _CliError(_EXIT_ERR, f"{kind}_must_be_object")
        return obj
    return build_catalog_routing_view(_rd(ctx.fleet_path, "fleet"), doc, _rd(ctx.lock_path, "lock") if ctx.lock_path else None)
def _parse_weight(raw: str) -> int:
    """Строго парсит целый вес маршрута 0..10000."""
    if _WEIGHT_RE.fullmatch(raw) is None or (value := int(raw)) > _MAX_WEIGHT:
        raise _CliError(_EXIT_ERR, f"invalid_weight: {raw}")
    return value
def _mutate_doc(ctx: _Context, updater: Callable[[dict[str, Any]], None]) -> WeightsOverrideDoc:
    """Атомарно обновляет файл весов под flock."""
    def _apply(doc: WeightsOverrideDoc) -> dict[str, Any]:
        payload = doc.to_dict()
        updater(payload)
        payload["updated_at"], payload["updated_by"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), ctx.updated_by
        return payload
    try:
        return RoutingWeightsStore(ctx.weights_path).mutate(ctx.weights_path, _apply)
    except WeightsCorruptError as exc:
        raise _CliError(_EXIT_CORRUPT, f"weights_corrupt: {exc}") from None
    except WeightsLockTimeoutError as exc:
        raise _CliError(_EXIT_BUSY, str(exc)) from None
    except ValueError as exc:
        raise _CliError(_EXIT_ERR, str(exc)) from None
def _cmd_status(ctx: _Context) -> tuple[int, dict[str, Any]]:
    """Возвращает матрицу маршрутизации, флаги и статус целостности весов."""
    doc, corrupt, error = None, False, None
    try:
        doc = RoutingWeightsStore(ctx.weights_path).load_strict()
    except WeightsCorruptError as exc:
        corrupt, error = True, str(exc)
    view = _load_view(ctx, doc)
    return _EXIT_OK, {**view, "ok": not corrupt, "weights_enabled": ctx.weights_enabled, "compiled_fleet_enabled": ctx.compiled_enabled, "transport_routing_enabled": ctx.transport_routing_enabled, "active_fleet_path": str(ctx.fleet_path), "weights_path": str(ctx.weights_path), "overrides_count": view["override_count"], "corrupt": corrupt, "error": error, "updated_at": doc.updated_at if doc else None, "updated_by": doc.updated_by if doc else None}
def _cmd_set_model(ctx: _Context, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    """Обновляет per-model веса маршрутов с валидацией по активному fleet.json."""
    updates: dict[str, int] = {}
    for item in args.assignments:
        backend, sep, raw_w = item.partition("=")
        if not sep or not backend:
            raise _CliError(_EXIT_ERR, f"invalid_assignment: {item}")
        updates[backend] = _parse_weight(raw_w)
    if (model := _load_view(ctx, None)["models"].get(args.model_id)) is None:
        raise _CliError(_EXIT_ERR, f"unknown_model: {args.model_id}")
    if unknown := sorted(set(updates) - {r["backend"] for r in model["routes"]}):
        raise _CliError(_EXIT_ERR, f"unknown_backends_for_model: {','.join(unknown)}")
    next_doc = _mutate_doc(ctx, lambda p: p["models"].__setitem__(args.model_id, {**p["models"].get(args.model_id, {}), **updates}))
    all_zero = bool(_load_view(ctx, next_doc)["models"][args.model_id]["all_zero_reserve"])
    return _EXIT_OK, {"ok": True, "model_id": args.model_id, "weights": dict(next_doc.models[args.model_id]), "all_zero_reserve": all_zero}
def _cmd_set_provider(ctx: _Context, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    """Задаёт provider-override и возвращает список всех затронутых моделей."""
    weight = _parse_weight(args.weight)
    if (provider := _load_view(ctx, None)["providers"].get(args.provider_id)) is None:
        raise _CliError(_EXIT_ERR, f"unknown_provider: {args.provider_id}")
    next_doc = _mutate_doc(ctx, lambda p: p["providers"].__setitem__(args.provider_id, weight))
    after_view = _load_view(ctx, next_doc)
    affected = list(provider["models"])
    all_zero = any(after_view["models"][m]["all_zero_reserve"] for m in affected)
    return _EXIT_OK, {"ok": True, "provider_id": args.provider_id, "weight": weight, "affected_models": affected, "routed_models": list(provider["routed_models"]), "single_transport_models": list(provider["single_transport_models"]), "all_zero_reserve": all_zero}
def _cmd_reset(ctx: _Context, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    """Снимает overrides модели, провайдера или всего документа."""
    removed = [0]
    def _update(p: dict[str, Any]) -> None:
        if args.command == "reset-all":
            removed[0], p["providers"], p["models"] = len(p["providers"]) + len(p["models"]), {}, {}
        else:
            bucket, key = ("models", args.model_id) if args.command == "reset-model" else ("providers", args.provider_id)
            removed[0] = int(p[bucket].pop(key, None) is not None)
    _mutate_doc(ctx, _update)
    return _EXIT_OK, {"ok": True, "command": args.command, "removed": removed[0]}
def _cmd_repair(ctx: _Context) -> tuple[int, dict[str, Any]]:
    """Архивирует битый файл/симлинк в .corrupt и создаёт чистый v1 JSON."""
    try:
        return _EXIT_OK, {"ok": True, "weights_path": str(ctx.weights_path), "backup_path": str(RoutingWeightsStore(ctx.weights_path).repair())}
    except WeightsLockTimeoutError as exc:
        raise _CliError(_EXIT_BUSY, str(exc)) from None
def _probe_health() -> dict[str, Any]:
    """Опрашивает BRIDGE_HEALTH_URL и извлекает число активных ходов."""
    url = os.environ.get("BRIDGE_HEALTH_URL", "").strip() or _DEFAULT_HEALTH_URL
    try:
        with urllib.request.urlopen(url, timeout=_env_num(_HEALTH_TIMEOUT)) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        active = data.get("active") if isinstance(data, dict) else None
        return {"url": url, "reachable": True, "ok": bool(data.get("ok")) if isinstance(data, dict) else False, "active": active if type(active) is int else None, "error": None}
    except (OSError, ValueError, urllib.error.URLError) as exc:
        return {"url": url, "reachable": False, "ok": False, "active": None, "error": str(exc)}
def _find_compile_python() -> str | None:
    """Подбирает Python >=3.12 с PyYAML для tools/fleet_compile.py."""
    probe = "import sys, yaml; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"
    for cand in (os.environ.get("BRIDGE_COMPILE_PYTHON", "").strip(), "/opt/homebrew/bin/python3", os.path.expanduser("~/work/agents/.venv/bin/python3")):
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            if cand and subprocess.run([cand, "-c", probe], capture_output=True, text=True, timeout=_env_num(_HEALTH_TIMEOUT)).returncode == 0:
                return cand
    return None
def _inspect_weights(path: Path) -> tuple[dict[str, Any], WeightsOverrideDoc | None]:
    """Проверяет права 0600, отсутствие симлинка и валидность JSON v1."""
    info: dict[str, Any] = {"exists": os.path.lexists(path), "is_symlink": False, "mode": None, "mode_ok": True, "valid_json": True, "error": None}
    if not info["exists"]:
        return info, WeightsOverrideDoc.empty()
    st = os.lstat(path)
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        return {**info, "is_symlink": True, "mode_ok": False, "valid_json": False, "error": "symlink_or_non_regular"}, None
    mode = stat.S_IMODE(st.st_mode)
    info.update({"mode": f"{mode:04o}", "mode_ok": mode == 0o600})
    try:
        return info, RoutingWeightsStore(path).load_strict()
    except WeightsCorruptError as exc:
        return {**info, "valid_json": False, "error": str(exc)}, None
def _find_stale(ctx: _Context, doc: WeightsOverrideDoc | None) -> tuple[list[str], list[dict[str, str]], str | None]:
    """Выявляет устаревшие model_id и backend_id относительно активного fleet.json."""
    if doc is None:
        return [], [], None
    try:
        view = _load_view(ctx, None)
    except _CliError as exc:
        return [], [], exc.message
    stale_m = sorted(mid for mid in doc.models if mid not in view["models"])
    stale_b = [{"scope": "provider", "id": pid} for pid in sorted(doc.providers) if pid not in view["providers"]]
    stale_b.extend({"scope": "model", "model_id": m, "backend_id": b} for m, bm in sorted(doc.models.items()) if m in view["models"] for b in sorted(bm) if b not in {r["backend"] for r in view["models"][m]["routes"]})
    return stale_m, stale_b, None
def _cmd_doctor(ctx: _Context) -> tuple[int, dict[str, Any]]:
    """Запускает диагностику файла весов, stale ID, Python для rebuild и /health."""
    info, doc = _inspect_weights(ctx.weights_path)
    stale_m, stale_b, fleet_err = _find_stale(ctx, doc)
    compile_py, health = _find_compile_python(), _probe_health()
    ok = all((not info["is_symlink"], info["mode_ok"], info["valid_json"], not stale_m, not stale_b, fleet_err is None, compile_py is not None, health["reachable"]))
    return _EXIT_OK, {"ok": ok, "weights_path": str(ctx.weights_path), "active_fleet_path": str(ctx.fleet_path), "weights_enabled": ctx.weights_enabled, "compiled_fleet_enabled": ctx.compiled_enabled, "transport_routing_enabled": ctx.transport_routing_enabled, **info, "stale_models": stale_m, "stale_backends": stale_b, "fleet_error": fleet_err, "compile_python": compile_py, "health": health}
@contextlib.contextmanager
def _lifecycle_lock(state_dir: Path) -> Iterator[None]:
    """Берёт эксклюзивный flock на <state>/.lifecycle.lock."""
    state_dir.mkdir(parents=True, exist_ok=True)
    fd = os.open(state_dir / ".lifecycle.lock", os.O_RDWR | os.O_CREAT, 0o644)
    deadline, poll_s = time.monotonic() + _env_num(_LOCK_WAIT), _env_num(_LOCK_POLL)
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if (rem := deadline - time.monotonic()) <= 0:
                    raise _CliError(_EXIT_BUSY, "lifecycle_lock_busy") from None
                time.sleep(min(poll_s, rem))
        yield
    finally:
        with contextlib.suppress(OSError):
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
def _run_compile(python_bin: str, state_dir: Path, apply: bool, sync_repo: bool) -> list[str]:
    """Запускает fleet_compile.py; stderr-предупреждения при rc==0 не считаются ошибкой."""
    cmd = [python_bin, str(ROOT / "tools" / "fleet_compile.py"), "--write" if apply else "--check", "--state-dir", str(state_dir)]
    if apply and sync_repo:
        cmd.extend(["--output", str(ROOT / "fleet.json"), "--sidecar", str(ROOT / "catalog.lock.json")])
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=_env_num(_COMPILE_TIMEOUT))
    warnings = [line for line in proc.stderr.splitlines() if line.strip()]
    if proc.returncode != 0:
        raise _CliError(_EXIT_ERR, f"fleet_compile_failed: {'; '.join(warnings) or proc.stdout.strip() or proc.returncode}")
    return warnings
def _restart_hub(force_restart: bool) -> tuple[bool, int | None]:
    """Проверяет active == 0 и вызывает launchctl kickstart -k при безопасном рестарте."""
    active = (health := _probe_health())["active"]
    if not force_restart and (not health["reachable"] or active is None or active > 0):
        return False, active
    service = os.environ.get("BRIDGE_LAUNCHD_LABEL", "").strip() or _DEFAULT_SERVICE
    proc = subprocess.run(["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{service}"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise _CliError(_EXIT_ERR, f"launchctl_failed: {proc.stderr.strip() or proc.returncode}")
    return True, active
def _apply_rebuild(ctx: _Context, args: argparse.Namespace, py: str, state: Path) -> tuple[int, dict[str, Any]]:
    """Применяет пересборку под .lifecycle.lock с учётом RISK-007 и активных ходов."""
    with _lifecycle_lock(state):
        warnings = _run_compile(py, state, True, args.sync_repo_fleet)
    if not ctx.compiled_enabled and not args.sync_repo_fleet:
        msg = "BRIDGE_COMPILED_FLEET_ENABLED=false: :9882 читает fleet.json, а не state/fleet.compiled.json — рестарт пропущен"
        return _EXIT_OK, {"ok": True, "applied": True, "python": py, "warnings": warnings, "compiled_shadowed": True, "restarted": False, "restart_deferred": False, "message": msg}
    restarted, active = _restart_hub(args.force_restart)
    return (_EXIT_OK if restarted else _EXIT_BUSY), {"ok": restarted, "applied": True, "python": py, "warnings": warnings, "compiled_shadowed": False, "synced_repo_fleet": args.sync_repo_fleet, "restarted": restarted, "restart_deferred": not restarted, "active": active}
def _cmd_rebuild(ctx: _Context, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    """Проверяет или безопасно пересобирает каталог с защитой RISK-007 и активных ходов."""
    if not args.apply and (args.sync_repo_fleet or args.force_restart):
        raise _CliError(_EXIT_ERR, "sync_or_force_requires_apply")
    if (py := _find_compile_python()) is None:
        raise _CliError(_EXIT_ERR, "no_compatible_compile_python")
    state = Path(os.path.expanduser(os.environ.get("BRIDGE_STATE_DIR") or _DEFAULT_STATE_DIR))
    if args.apply:
        return _apply_rebuild(ctx, args, py, state)
    return _EXIT_OK, {"ok": True, "applied": False, "python": py, "warnings": _run_compile(py, state, False, False)}
def _build_parser() -> _ArgParser:
    """Создаёт CLI-парсер с глобальными флагами и подкомандами."""
    shared, parser = _ArgParser(add_help=False, argument_default=argparse.SUPPRESS), _ArgParser(description="Оперативные веса маршрутизации")
    for p, defs in ((shared, {}), (parser, {"--updated-by": "cli"})):
        for flag in ("--fleet", "--weights", "--lock", "--updated-by"):
            p.add_argument(flag, **({"default": defs.get(flag)} if p is parser else {}))
        p.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "reset-all", "repair", "doctor"):
        sub.add_parser(name, parents=[shared])
    for name, a1, a2 in (("set-model", "model_id", "assignments"), ("set-provider", "provider_id", "weight")):
        sp = sub.add_parser(name, parents=[shared])
        sp.add_argument(a1), sp.add_argument(a2, nargs="+" if a2 == "assignments" else None)
    for name, arg in (("reset-model", "model_id"), ("reset-provider", "provider_id")):
        sub.add_parser(name, parents=[shared]).add_argument(arg)
    p_rb = sub.add_parser("rebuild", parents=[shared])
    [p_rb.add_argument(opt, action="store_true") for opt in ("--apply", "--sync-repo-fleet", "--force-restart")]
    return parser
def main(argv: list[str] | None = None) -> int:
    """Точка входа CLI оперативных весов маршрутизации."""
    args = _build_parser().parse_args(argv)
    try:
        ctx = _build_context(args)
        handlers: dict[str, Callable[[], tuple[int, dict[str, Any]]]] = {"status": lambda: _cmd_status(ctx), "set-model": lambda: _cmd_set_model(ctx, args), "set-provider": lambda: _cmd_set_provider(ctx, args), "reset-model": lambda: _cmd_reset(ctx, args), "reset-provider": lambda: _cmd_reset(ctx, args), "reset-all": lambda: _cmd_reset(ctx, args), "repair": lambda: _cmd_repair(ctx), "doctor": lambda: _cmd_doctor(ctx), "rebuild": lambda: _cmd_rebuild(ctx, args)}
        code, payload = handlers[args.command]()
    except _CliError as exc:
        print(json.dumps({"ok": False, "error": exc.message, "code": exc.code}, ensure_ascii=False) if args.json else f"ERROR: {exc.message}", file=sys.stdout if args.json else sys.stderr)
        return exc.code
    print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else (f"fleet={payload['active_fleet_path']} overrides={payload['overrides_count']} corrupt={payload['corrupt']}" if "models" in payload and "categories" in payload else json.dumps(payload, ensure_ascii=False)))
    return code
if __name__ == "__main__":
    raise SystemExit(main())
