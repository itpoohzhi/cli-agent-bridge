"""Изолированный Zero-Canon рантайм и GigaRC kill-switch для muse-bridge."""

from __future__ import annotations

import contextvars
import json
import os
import sys
import tempfile
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.subbridge_zero_canon import (  # noqa: E402
    MUSE_ZERO_CANON_FLAG,
    filter_muse_settings,
    is_zero_canon_profile,
    review_profile_from_headers,
)
from core.zero_canon_fs import (  # noqa: E402
    cleanup_ephemeral_zc_cwd,
    ensure_private_dir,
    make_ephemeral_zc_cwd,
    read_gigarc_bool,
    remove_entry,
    sanitize_zero_canon_env,
    write_atomic_0600,
)

DEFAULT_CONFIG_PATH: Final[Path] = Path(__file__).resolve().parent.parent / "dynamic_config.json"
DEFAULT_PATH: Final[str] = f"{Path.home()}/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
_FORBIDDEN_NAMES: Final[tuple[str, ...]] = ("AGENTS.md", "CLAUDE.md", "hooks", "hooks.json", "plugins", "skills")
_PREP_LOCK = threading.Lock()


@dataclass(frozen=True, slots=True)
class MuseZeroCanonContext:
    """Контекст активного Zero-Canon хода для muse-bridge."""

    enabled: bool
    zc_home: Path
    zc_cwd: Path


_ACTIVE_ZC: contextvars.ContextVar[MuseZeroCanonContext | None] = contextvars.ContextVar(
    "muse_zero_canon_ctx", default=None
)


def is_muse_zero_canon_enabled(
    config_path: Path | None = None, *, environ: Mapping[str, str] | None = None
) -> bool:
    """GigaRC kill-switch `MUSE_ZERO_CANON_ENABLED` (дефолт False, fail-closed)."""
    return read_gigarc_bool(
        MUSE_ZERO_CANON_FLAG,
        DEFAULT_CONFIG_PATH if config_path is None else Path(config_path),
        environ=environ,
        default=False,
    )


def _read_dict(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
        return parsed if isinstance(parsed, dict) else {}
    except (OSError, ValueError):
        return {}


def prepare_muse_zero_canon_home(
    source_home: Path, zc_home: Path, *, source_xdg_config: Path | None = None
) -> Path:
    """Готовит изолированный HOME: только `auth.json` (0600) и отфильтрованный `settings.json`."""
    if zc_home.is_symlink():
        raise RuntimeError(f"Refusing symlink zc_home: {zc_home}")
    src_resolved, zc_resolved = source_home.resolve(), zc_home.resolve()
    if zc_resolved == src_resolved or zc_resolved in src_resolved.parents:
        raise RuntimeError(f"Invalid zc_home overlaps source HOME: {zc_resolved}")
    with _PREP_LOCK:
        zc_cfg = zc_home / ".config" / "muse"
        for directory in (zc_home, zc_home / ".config", zc_cfg):
            ensure_private_dir(directory, 0o700)
        candidates = ([source_xdg_config / "muse"] if source_xdg_config else []) + [
            source_home / ".config" / "muse",
            source_home / ".muse",
        ]
        auth_src = next(
            (c / "auth.json" for c in candidates if (c / "auth.json").is_file() and not (c / "auth.json").is_symlink()),
            None,
        )
        settings_src = next(
            (
                c / "settings.json"
                for c in candidates
                if (c / "settings.json").is_file() and not (c / "settings.json").is_symlink()
            ),
            None,
        )
        filtered = (
            json.dumps(filter_muse_settings(_read_dict(settings_src)), indent=2, sort_keys=True, ensure_ascii=False)
            + "\n"
        ).encode("utf-8")
        targets = [zc_cfg]
        if (source_home / ".muse").is_dir():
            ensure_private_dir(zc_home / ".muse", 0o700)
            targets.append(zc_home / ".muse")
        for target in targets:
            if auth_src is not None:
                write_atomic_0600(target / "auth.json", auth_src.read_bytes())
            write_atomic_0600(target / "settings.json", filtered)
        for base in (zc_home, *targets):
            for name in _FORBIDDEN_NAMES:
                remove_entry(base / name)
        if sys.platform == "darwin":
            kc_src = source_home / "Library" / "Keychains"
            if kc_src.is_dir():
                lib_dir = zc_home / "Library"
                ensure_private_dir(lib_dir, 0o700)
                kc_dst = lib_dir / "Keychains"
                if not kc_dst.exists() and not kc_dst.is_symlink():
                    os.symlink(kc_src, kc_dst)
        return zc_resolved


def ensure_muse_zero_canon_cwd(zc_cwd: Path) -> Path:
    """Создаёт и очищает пустой `cwd` для Zero-Canon хода."""
    with _PREP_LOCK:
        ensure_private_dir(zc_cwd, 0o700)
        for entry in list(zc_cwd.iterdir()):
            remove_entry(entry)
        return zc_cwd.resolve()


@contextmanager
def zero_canon_scope(
    headers: object,
    config_path: Path | None = None,
    *,
    workspace: Path | None = None,
    real_home: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Iterator[MuseZeroCanonContext | None]:
    """Привязывает Zero-Canon контекст с уникальным per-request `zc_cwd`."""
    active = is_zero_canon_profile(review_profile_from_headers(headers)) and is_muse_zero_canon_enabled(
        config_path, environ=environ
    )
    ctx: MuseZeroCanonContext | None = None
    turn_cwd: Path | None = None
    if active:
        env = os.environ if environ is None else environ
        src_home = real_home if real_home is not None else Path(env.get("HOME") or str(Path.home()))
        xdg_raw = env.get("XDG_CONFIG_HOME")
        root = workspace if workspace is not None else Path(tempfile.gettempdir()) / "muse-zero-canon"
        zc_home = prepare_muse_zero_canon_home(
            src_home, root / "muse-home-zc", source_xdg_config=Path(xdg_raw) if xdg_raw else None
        )
        turn_cwd = make_ephemeral_zc_cwd(root / "muse-zc-cwd", prefix="turn-")
        ctx = MuseZeroCanonContext(True, zc_home, turn_cwd)
    token = _ACTIVE_ZC.set(ctx)
    try:
        yield ctx
    finally:
        _ACTIVE_ZC.reset(token)
        cleanup_ephemeral_zc_cwd(turn_cwd)


def apply_muse_preset_empty(cmd: list[str]) -> list[str]:
    """Принудительно выставляет `--preset empty`, заменяя любой предустановленный `--preset`."""
    result: list[str] = []
    idx = 0
    while idx < len(cmd):
        tok = cmd[idx]
        if tok == "--preset":
            idx += 2 if idx + 1 < len(cmd) else 1
            continue
        if tok.startswith("--preset="):
            idx += 1
            continue
        result.append(tok)
        idx += 1
    if "--prompt-file" in result:
        pos = result.index("--prompt-file")
        result[pos:pos] = ["--preset", "empty"]
    else:
        result.extend(("--preset", "empty"))
    return result


def prepare_muse_launch(
    cmd: list[str],
    base_env: Mapping[str, str] | None,
    workdir: Path,
    *,
    ctx: MuseZeroCanonContext | None = None,
) -> tuple[list[str], dict[str, str], Path]:
    """Готовит `(cmd, env, cwd)` для `Run`/`ServeRun` с учётом Zero-Canon."""
    env = dict(os.environ if base_env is None else base_env)
    env.setdefault("PATH", DEFAULT_PATH)
    env.setdefault("MUSE_NO_AUTO_UPDATE", "1")
    env.pop("META_API_KEY", None)
    active = ctx if ctx is not None else _ACTIVE_ZC.get()
    if active is None or not active.enabled:
        return list(cmd), env, workdir
    orig_home = Path(env.get("HOME") or str(Path.home()))
    muse_bin = env.get("MUSE_BIN") or env.get("MUSE_BIN_PATH") or str(orig_home / ".local" / "bin" / "muse")
    zc_cwd = active.zc_cwd
    ensure_private_dir(zc_cwd, 0o700)
    env = sanitize_zero_canon_env(env, active.zc_home)
    env["MUSE_BIN"] = muse_bin
    env["MUSE_BIN_PATH"] = muse_bin
    env["MUSE_NO_AUTO_UPDATE"] = "1"
    env["BRIDGE_ZERO_CANON"] = "1"
    new_cmd = apply_muse_preset_empty(cmd)
    for idx, token in enumerate(new_cmd[:-1]):
        if token == "--workspace":
            new_cmd[idx + 1] = str(zc_cwd)
    return new_cmd, env, zc_cwd
