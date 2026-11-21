"""Изоляция dual clean-home `agy-home-zc`, флага GigaRC и ротации рантайм-артефактов."""
from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable, Mapping, Set as AbstractSet
from pathlib import Path
from typing import Final

from agy_runtime.long_session_config import read_float_setting, read_int_setting
from core.agy_zero_canon import (
    AGY_CANON_FILE_NAMES, AGY_ZERO_CANON_FLAG, AgyZeroCanonPlan,
    build_agy_zero_canon_plan, filter_agy_settings, serialize_agy_json,
)
from core.env_hot_reload import file_signature
from core.zero_canon_fs import (
    cleanup_ephemeral_zc_cwd,
    make_ephemeral_zc_cwd,
    read_gigarc_bool,
    remove_entry,
    write_atomic_0600,
    write_atomic_text_0600,
)

_DEFAULT_CFG: Final[Path] = Path(__file__).resolve().parent.parent / "dynamic_config.json"
_ROTATE_SUBDIRS: Final[tuple[str, ...]] = ("log", "presence", "conversations", "brain")
_ROTATE_LOCK = threading.Lock()
_ROTATE_LAST: dict[str, float] = {}
_MGR_LOCK, _MANAGERS = threading.Lock(), {}  # type: ignore[var-annotated]


def is_agy_zero_canon_enabled(config_path: Path | None = None, *, environ: Mapping[str, str] | None = None) -> bool:
    """Читает kill-switch `AGY_ZERO_CANON_ENABLED` с дефолтом False (fail-closed)."""
    return read_gigarc_bool(
        AGY_ZERO_CANON_FLAG,
        _DEFAULT_CFG if config_path is None else Path(config_path),
        environ=environ,
        default=False,
    )


def resolve_turn_plan(headers: object, config_path: Path | None = None, *, environ: Mapping[str, str] | None = None) -> AgyZeroCanonPlan:
    """Построить план изоляции хода по `X-Review-Profile` и GigaRC-флагу."""
    return build_agy_zero_canon_plan(headers, flag_enabled=is_agy_zero_canon_enabled(config_path, environ=environ))


def agy_gemini_files(real_gemini: Path, real_cli: Path, clean_gemini: Path, clean_cli: Path, *, zero_canon_only: bool = False) -> tuple[tuple[Path, Path], ...]:
    """Пары (источник, каталог назначения) для auth/state файлов."""
    pairs = ((real_gemini / "jetski-standalone-oauth-token", clean_gemini), (real_gemini / "projects.json", clean_gemini), (real_cli / "antigravity-oauth-token", clean_cli), (real_cli / "installation_id", clean_cli), (real_cli / "jetski_state.pbtxt", clean_cli))
    return pairs if zero_canon_only else pairs + ((real_cli / "antigravity-account.json", clean_cli), (real_cli / "settings.json", clean_cli))


def sync_agy_gemini_files(pairs: tuple[tuple[Path, Path], ...], signatures: dict[str, tuple[int, int]], copy_fn: Callable[[Path, Path], None], remove_fn: Callable[[Path, str], bool] | None, inside_fn: Callable[[Path], None], log_fn: Callable[[str], None]) -> int:
    """Атомарно синхронизирует auth-файлы в clean-home с сохранением mtime-guard."""
    copied = 0
    for src, dst in pairs:
        key, sig, dst_file = str(src), file_signature(src), dst / src.name
        prev = signatures.get(key)
        if sig is None:
            if prev is not None and (remove_fn(dst_file, src.name) if remove_fn else (inside_fn(dst_file.parent if dst_file.is_symlink() else dst_file), dst_file.unlink(missing_ok=True))[1] is None):
                signatures.pop(key, None)
            continue
        if not dst_file.is_symlink() and dst_file.is_file() and prev == sig:
            continue
        try:
            if dst_file.is_symlink():
                dst_file.unlink()
            if (prev is not None and prev != sig) or not dst_file.exists() or src.stat().st_mtime >= dst_file.stat().st_mtime:
                copy_fn(src, dst_file)
                copied += 1
            else:
                inside_fn(dst_file)
                dst_file.chmod(0o600)
        except OSError as exc:
            log_fn(f"agy-home auth sync skipped file={src.name} err={type(exc).__name__}")
            continue
        signatures[key] = sig
    return copied


def _write_atomic_0600(dst: Path, *, text: str | None = None, src: Path | None = None) -> None:
    if text is not None:
        write_atomic_text_0600(dst, text)
    elif src is not None:
        write_atomic_0600(dst, src.read_bytes())


def _remove_entry(entry: Path) -> None:
    remove_entry(entry)


def maybe_rotate_agy_runtime_artifacts(
    agy_home: Path,
    *,
    min_interval_s: float = 300.0,
    active_cids: AbstractSet[str] = frozenset(),
    config_path: Path | None = None,
) -> int:
    """Периодически запускает `rotate_agy_runtime_artifacts` не чаще `min_interval_s`."""
    key = str(agy_home)
    now_mono = time.monotonic()
    with _ROTATE_LOCK:
        last = _ROTATE_LAST.get(key)
        if last is not None and (now_mono - last) < min_interval_s:
            return 0
        _ROTATE_LAST[key] = now_mono
    try:
        return rotate_agy_runtime_artifacts(agy_home, active_cids=active_cids, config_path=config_path)
    except OSError:
        return 0


def rotate_agy_runtime_artifacts(agy_home: Path, *, max_age_s: float | None = None, max_files: int | None = None, active_cids: AbstractSet[str] = frozenset(), now: float | None = None, config_path: Path | None = None) -> int:
    """Безопасная TTL/count-ротация log/presence/conversations/brain и осиротевших .tmp."""
    if agy_home.is_symlink() or not agy_home.is_dir():
        return 0
    ttl = read_float_setting("agy_runtime_artifact_max_age_s", "AGY_RUNTIME_ARTIFACT_MAX_AGE_S", 86400.0, (1.0, 31536000.0), config_path=config_path) if max_age_s is None else max(0.0, float(max_age_s))
    cap = read_int_setting("agy_runtime_artifact_max_files", "AGY_RUNTIME_ARTIFACT_MAX_FILES", 200, (1, 100000), config_path=config_path) if max_files is None else max(0, int(max_files))
    cutoff, gemini_dir, cli_dir, removed = (time.time() if now is None else float(now)) - ttl, agy_home / ".gemini", agy_home / ".gemini" / "antigravity-cli", 0
    for base in (gemini_dir, cli_dir):
        for tmp in (base.glob("jetbox_summaries_proto.pb.*.tmp") if base.is_dir() and not base.is_symlink() else ()):
            if tmp.is_file() and not tmp.is_symlink() and tmp.stat().st_mtime < cutoff:
                tmp.unlink(missing_ok=True)
                removed += 1
    zc_cwd_root = agy_home.parent / "agy-zc-cwd"
    if zc_cwd_root.is_dir() and not zc_cwd_root.is_symlink():
        for turn_dir in zc_cwd_root.glob("turn-*"):
            if not turn_dir.is_symlink() and turn_dir.stat().st_mtime < cutoff:
                _remove_entry(turn_dir)
                removed += 1
    for sub in _ROTATE_SUBDIRS:
        if (target := cli_dir / sub).is_symlink() or not target.is_dir():
            continue
        entries: list[tuple[float, Path]] = []
        for entry in target.iterdir():
            cid_key = entry.name.split(".", 1)[0] if sub == "conversations" else entry.name
            if entry.is_symlink() or (sub in ("conversations", "brain") and cid_key in active_cids):
                continue
            if (mtime := entry.stat().st_mtime) < cutoff:
                _remove_entry(entry)
                removed += 1
            else:
                entries.append((mtime, entry))
        for _mtime, entry in sorted(entries, key=lambda item: item[0], reverse=True)[cap:]:
            _remove_entry(entry)
            removed += 1
    return removed


class AgyZeroCanonProfileManager:
    """Управляет dual clean-home `agy-home-zc` и пустым `cwd` для Zero-Canon."""

    def __init__(self, real_home: Path, clean_home: Path, *, zc_home: Path | None = None, zc_cwd: Path | None = None, config_path: Path | None = None) -> None:
        self.real_home, self.clean_home, self.config_path = real_home, clean_home, config_path
        self.zc_home = clean_home.with_name(f"{clean_home.name}-zc") if zc_home is None else zc_home
        self.zc_cwd = clean_home.parent / "agy-zc-cwd" if zc_cwd is None else zc_cwd
        self._lock, self._signatures = threading.Lock(), {}

    def _assert_inside(self, root: Path, path: Path) -> None:
        if (resolved := path.resolve()) != (base := root.resolve()) and base not in resolved.parents:
            raise RuntimeError(f"Path {path} resolves outside {base}: {resolved}")

    def _reject_overlap(self, path: Path, label: str) -> Path:
        if path.is_symlink():
            raise RuntimeError(f"Invalid {label}: cannot be a symlink")
        res, real_r, gem_r = path.resolve(), self.real_home.resolve(), (self.real_home / ".gemini").resolve()
        if res in (real_r, gem_r) or res in real_r.parents or res in gem_r.parents or gem_r in res.parents:
            raise RuntimeError(f"Invalid {label}: overlaps with HOME or .gemini ({res})")
        return res

    def _ensure_dir(self, root: Path, path: Path, mode: int = 0o700) -> None:
        if path.is_symlink():
            raise RuntimeError(f"Refusing symlink directory: {path}")
        self._assert_inside(root, path)
        path.mkdir(mode=mode, parents=True, exist_ok=True)
        os.chmod(path, mode)

    def _ensure_symlink(self, root: Path, link: Path, target: Path) -> None:
        self._assert_inside(root, link.parent)
        if link.is_symlink() and os.readlink(link) == str(target):
            return
        if link.is_dir() and not link.is_symlink():
            raise RuntimeError(f"Refusing to replace dir {link} with symlink")
        link.unlink(missing_ok=True)
        link.symlink_to(target)

    def _mirror_bin(self, src_dir: Path, dst_dir: Path, ancestors: frozenset[Path]) -> None:
        self._ensure_dir(self.zc_home, dst_dir)
        ancestors = ancestors | {src_dir.resolve()}
        for entry in src_dir.iterdir():
            dst = dst_dir / entry.name
            if not entry.is_dir():
                self._ensure_symlink(self.zc_home, dst, entry)
            elif entry.resolve() not in ancestors:
                if dst.is_symlink() or (dst.exists() and not dst.is_dir()):
                    dst.unlink()
                self._mirror_bin(entry, dst, ancestors)

    def _sync_settings_and_builtin(self, real_cli: Path, zc_cli: Path) -> None:
        src_cfg, raw = real_cli / "settings.json", {}
        if src_cfg.is_file() and not src_cfg.is_symlink():
            try:
                raw = p if isinstance((p := json.loads(src_cfg.read_text(encoding="utf-8"))), dict) else {}
            except (OSError, ValueError):
                raw = {}
        _write_atomic_0600(zc_cli / "settings.json", text=serialize_agy_json(filter_agy_settings(raw)))
        for sub_name in ("skills", "plugins"):
            sub = zc_cli / "builtin" / sub_name
            if sub.is_dir() and not sub.is_symlink():
                if (sub.stat().st_mode & 0o777) == 0o500 and not any(sub.iterdir()):
                    continue
                os.chmod(sub, 0o700)
                [_remove_entry(child) for child in list(sub.iterdir())]
            elif sub.is_symlink() or sub.exists():
                sub.unlink()
            self._ensure_dir(self.zc_home, sub, 0o500)

    def prepare_zc_home(self) -> Path:
        """Потокобезопасно готовит изолированный `agy-home-zc` и возвращает resolved путь."""
        with self._lock:
            resolved = self._reject_overlap(self.zc_home, "agy-home-zc")
            zc_gemini, zc_cli = self.zc_home / ".gemini", self.zc_home / ".gemini" / "antigravity-cli"
            if zc_gemini.is_symlink() or zc_cli.is_symlink():
                raise RuntimeError("Invalid agy-home-zc: .gemini/antigravity-cli cannot be a symlink")
            for d in (self.zc_home, zc_gemini, zc_cli, zc_cli / "conversations", zc_cli / "brain", zc_cli / "builtin"):
                self._ensure_dir(self.zc_home, d)
            self._ensure_symlink(self.zc_home, self.zc_home / "Library", self.real_home / "Library")
            real_gemini, real_cli = self.real_home / ".gemini", self.real_home / ".gemini" / "antigravity-cli"
            if (real_cli / "bin").is_dir():
                if (zc_cli / "bin").is_symlink():
                    (zc_cli / "bin").unlink()
                self._mirror_bin(real_cli / "bin", zc_cli / "bin", frozenset())
            sync_agy_gemini_files(agy_gemini_files(real_gemini, real_cli, zc_gemini, zc_cli, zero_canon_only=True), self._signatures, lambda s, d: _write_atomic_0600(d, src=s), None, lambda p: self._assert_inside(self.zc_home, p), lambda _m: None)
            self._sync_settings_and_builtin(real_cli, zc_cli)
            cfg_dir = zc_gemini / "config"
            _remove_entry(cfg_dir) if cfg_dir.is_symlink() else (_remove_entry(cfg_dir / "hooks.json"), _remove_entry(cfg_dir / "hooks"))
            [c.unlink(missing_ok=True) for base in (self.zc_home, zc_gemini, zc_cli) for name in AGY_CANON_FILE_NAMES if (c := base / name).is_symlink() or c.is_file()]
            return resolved

    def ensure_zc_cwd(self) -> Path:
        """Создаёт и полностью очищает пустой изолированный `cwd` для Zero-Canon."""
        with self._lock:
            resolved = self._reject_overlap(self.zc_cwd, "agy-zc-cwd")
            self._ensure_dir(self.zc_cwd, self.zc_cwd)
            for entry in list(self.zc_cwd.iterdir()):
                _remove_entry(entry)
            return resolved

    def create_turn_zc_cwd(self) -> Path:
        """Создаёт уникальный пустой `cwd` (`0o700`) для одного Zero-Canon хода."""
        with self._lock:
            self._reject_overlap(self.zc_cwd, "agy-zc-cwd")
            self._ensure_dir(self.zc_cwd, self.zc_cwd)
            return make_ephemeral_zc_cwd(self.zc_cwd, prefix="turn-")

    @staticmethod
    def cleanup_turn_zc_cwd(path: Path | None) -> None:
        """Удаляет одноразовый `cwd` Zero-Canon хода."""
        cleanup_ephemeral_zc_cwd(path)


def get_manager(real_home: Path, clean_home: Path, *, config_path: Path | None = None) -> AgyZeroCanonProfileManager:
    """Возвращает кешированный потокобезопасный менеджер для пары (HOME, CLEAN_HOME_DIR)."""
    with _MGR_LOCK:
        return _MANAGERS.setdefault((real_home, clean_home, config_path), AgyZeroCanonProfileManager(real_home, clean_home, config_path=config_path))
