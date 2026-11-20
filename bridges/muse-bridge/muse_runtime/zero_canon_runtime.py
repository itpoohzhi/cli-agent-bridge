"""Изолированный Zero-Canon рантайм и GigaRC kill-switch для muse-bridge."""

from __future__ import annotations

import contextvars
import json
import os
import shutil
import sys
import tempfile
import threading
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.subbridge_zero_canon import (  # noqa: E402
    MUSE_ZERO_CANON_FLAG, filter_muse_settings, is_zero_canon_profile, review_profile_from_headers,
)

DEFAULT_CONFIG_PATH: Final[Path] = Path(__file__).resolve().parent.parent / "dynamic_config.json"
DEFAULT_PATH: Final[str] = "/Users/aazhiry1/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
_ENV_TRUE: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})
_ENV_FALSE: Final[frozenset[str]] = frozenset({"0", "false", "no", "off"})
_FORBIDDEN_NAMES: Final[tuple[str, ...]] = ("AGENTS.md", "CLAUDE.md", "hooks", "hooks.json", "plugins", "skills")
_CFG_LOCK, _PREP_LOCK = threading.Lock(), threading.Lock()
_CFG_CACHE: dict[str, tuple[tuple[int, int, int], bool]] = {}


@dataclass(frozen=True, slots=True)
class MuseZeroCanonContext:
    """Контекст активного Zero-Canon хода для muse-bridge."""

    enabled: bool
    zc_home: Path
    zc_cwd: Path


_ACTIVE_ZC: contextvars.ContextVar[MuseZeroCanonContext | None] = contextvars.ContextVar("muse_zero_canon_ctx", default=None)


def is_muse_zero_canon_enabled(config_path: Path | None = None, *, environ: Mapping[str, str] | None = None) -> bool:
    """GigaRC kill-switch `MUSE_ZERO_CANON_ENABLED` (дефолт False, fail-closed)."""
    env_val = str((os.environ if environ is None else environ).get(MUSE_ZERO_CANON_FLAG, "")).strip().lower()
    if env_val in _ENV_TRUE:
        return True
    if env_val in _ENV_FALSE:
        return False
    path = DEFAULT_CONFIG_PATH if config_path is None else Path(config_path)
    try:
        st = path.stat()
    except OSError:
        return False
    sig, key = (st.st_mtime_ns, st.st_size, st.st_ino), str(path)
    with _CFG_LOCK:
        if (hit := _CFG_CACHE.get(key)) is not None and hit[0] == sig:
            return hit[1]
    enabled = _read_dict(path).get(MUSE_ZERO_CANON_FLAG) is True
    with _CFG_LOCK:
        _CFG_CACHE[key] = (sig, enabled)
    return enabled


def _write_atomic_0600(dst: Path, data: bytes) -> None:
    if dst.is_symlink():
        dst.unlink()
    tmp = dst.parent / f".tmp_{dst.name}_{uuid.uuid4().hex}"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.chmod(tmp, 0o600)
        os.replace(tmp, dst)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _remove_entry(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path, ignore_errors=True)


def _ensure_private_dir(path: Path) -> None:
    if path.is_symlink():
        raise RuntimeError(f"Refusing symlink directory: {path}")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path, 0o700)


def _read_dict(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
        return parsed if isinstance(parsed, dict) else {}
    except (OSError, ValueError):
        return {}


def prepare_muse_zero_canon_home(source_home: Path, zc_home: Path, *, source_xdg_config: Path | None = None) -> Path:
    """Готовит изолированный HOME: только `auth.json` (0600) и отфильтрованный `settings.json`."""
    if zc_home.is_symlink():
        raise RuntimeError(f"Refusing symlink zc_home: {zc_home}")
    src_resolved, zc_resolved = source_home.resolve(), zc_home.resolve()
    if zc_resolved == src_resolved or zc_resolved in src_resolved.parents:
        raise RuntimeError(f"Invalid zc_home overlaps source HOME: {zc_resolved}")
    with _PREP_LOCK:
        zc_cfg = zc_home / ".config" / "muse"
        for directory in (zc_home, zc_home / ".config", zc_cfg):
            _ensure_private_dir(directory)
        candidates = ([source_xdg_config / "muse"] if source_xdg_config else []) + [source_home / ".config" / "muse", source_home / ".muse"]
        auth_src = next((c / "auth.json" for c in candidates if (c / "auth.json").is_file() and not (c / "auth.json").is_symlink()), None)
        settings_src = next((c / "settings.json" for c in candidates if (c / "settings.json").is_file() and not (c / "settings.json").is_symlink()), None)
        filtered = (json.dumps(filter_muse_settings(_read_dict(settings_src)), indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
        targets = [zc_cfg]
        if (source_home / ".muse").is_dir():
            _ensure_private_dir(zc_home / ".muse")
            targets.append(zc_home / ".muse")
        for target in targets:
            if auth_src is not None:
                _write_atomic_0600(target / "auth.json", auth_src.read_bytes())
            _write_atomic_0600(target / "settings.json", filtered)
        for base in (zc_home, *targets):
            for name in _FORBIDDEN_NAMES:
                _remove_entry(base / name)
        return zc_resolved


def ensure_muse_zero_canon_cwd(zc_cwd: Path) -> Path:
    """Создаёт и очищает пустой `cwd` для Zero-Canon хода."""
    with _PREP_LOCK:
        _ensure_private_dir(zc_cwd)
        for entry in list(zc_cwd.iterdir()):
            _remove_entry(entry)
        return zc_cwd.resolve()


@contextmanager
def zero_canon_scope(
    headers: object, config_path: Path | None = None, *, workspace: Path | None = None,
    real_home: Path | None = None, environ: Mapping[str, str] | None = None,
) -> Iterator[MuseZeroCanonContext | None]:
    """Привязывает Zero-Canon контекст к текущему HTTP-запросу (или `None`)."""
    active = is_zero_canon_profile(review_profile_from_headers(headers)) and is_muse_zero_canon_enabled(config_path, environ=environ)
    ctx: MuseZeroCanonContext | None = None
    if active:
        env = os.environ if environ is None else environ
        src_home = real_home if real_home is not None else Path(env.get("HOME") or str(Path.home()))
        xdg_raw, root = env.get("XDG_CONFIG_HOME"), (workspace if workspace is not None else Path(tempfile.gettempdir()) / "muse-zero-canon")
        zc_home = prepare_muse_zero_canon_home(src_home, root / "muse-home-zc", source_xdg_config=Path(xdg_raw) if xdg_raw else None)
        ctx = MuseZeroCanonContext(True, zc_home, ensure_muse_zero_canon_cwd(root / "muse-zc-cwd"))
    token = _ACTIVE_ZC.set(ctx)
    try:
        yield ctx
    finally:
        _ACTIVE_ZC.reset(token)


def apply_muse_preset_empty(cmd: list[str]) -> list[str]:
    """Добавляет `--preset empty` в аргументы Muse, если флаг ещё не задан."""
    result = list(cmd)
    if any(arg == "--preset" or arg.startswith("--preset=") for arg in result):
        return result
    if "--prompt-file" in result:
        idx = result.index("--prompt-file")
        result[idx:idx] = ["--preset", "empty"]
    else:
        result.extend(("--preset", "empty"))
    return result


def prepare_muse_launch(
    cmd: list[str], base_env: Mapping[str, str] | None, workdir: Path, *, ctx: MuseZeroCanonContext | None = None
) -> tuple[list[str], dict[str, str], Path]:
    """Готовит `(cmd, env, cwd)` для `Run`/`ServeRun` с учётом Zero-Canon."""
    env = dict(os.environ if base_env is None else base_env)
    env.setdefault("PATH", DEFAULT_PATH)
    env.pop("META_API_KEY", None)
    active = ctx if ctx is not None else _ACTIVE_ZC.get()
    if active is None or not active.enabled:
        return list(cmd), env, workdir
    zc_cwd = ensure_muse_zero_canon_cwd(active.zc_cwd)
    env["HOME"], env["XDG_CONFIG_HOME"], env["BRIDGE_ZERO_CANON"] = str(active.zc_home), str(active.zc_home / ".config"), "1"
    new_cmd = apply_muse_preset_empty(cmd)
    for idx, token in enumerate(new_cmd[:-1]):
        if token == "--workspace":
            new_cmd[idx + 1] = str(zc_cwd)
    return new_cmd, env, zc_cwd
