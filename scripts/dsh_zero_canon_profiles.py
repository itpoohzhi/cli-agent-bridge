#!/usr/bin/env python3
"""Неинвазивный CLI подготовки Zero-Canon профилей DSH для Claude и Codex."""

from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import sys
import tomllib
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.claude_zero_canon import (  # noqa: E402
    CLAUDE_PRESERVED_CA_FILES,
    filter_claude_settings,
    filter_claude_state,
    serialize_claude_json,
)
from core.subbridge_zero_canon import dump_toml, filter_codex_config  # noqa: E402

_CLAUDE_AUTH_FILES: Final[tuple[str, ...]] = (".credentials.json", "credentials.json", "auth.json")
_CLAUDE_FORBIDDEN: Final[tuple[str, ...]] = (
    "CLAUDE.md", "AGENTS.md", "agents-global.md", "plugins", "hooks", "hooks.json", "skills", "commands",
)
_CODEX_FORBIDDEN: Final[tuple[str, ...]] = ("AGENTS.md", "CLAUDE.md", "hooks", "hooks.json", "plugins", "skills")
_BACKUP_GLOBS: Final[tuple[str, ...]] = ("*.bak*", "*.backup*")


def _ensure_dir_0700(path: Path) -> None:
    if path.is_symlink():
        raise RuntimeError(f"Refusing symlink target directory: {path}")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path, 0o700)


def _write_atomic_0600(dst: Path, payload: bytes) -> None:
    if dst.is_symlink():
        dst.unlink()
    tmp = dst.parent / f".tmp_{dst.name}_{uuid.uuid4().hex}"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
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


def _read_json_dict(path: Path) -> dict[str, Any] | None:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def prepare_claude_zc_profile(src_dir: Path | str, dst_dir: Path | str, *, dry_run: bool = False) -> dict[str, Any]:
    """Копирует auth/CA (0600) и отфильтрованный settings.json без CLAUDE.md/plugins/hooks."""
    src, dst = Path(src_dir).expanduser(), Path(dst_dir).expanduser()
    copied: list[str] = []
    if not dry_run:
        _ensure_dir_0700(dst)
    for name in (*_CLAUDE_AUTH_FILES, *sorted(CLAUDE_PRESERVED_CA_FILES)):
        src_file = src / name
        if src_file.is_file() and not src_file.is_symlink():
            copied.append(name)
            if not dry_run:
                _write_atomic_0600(dst / name, src_file.read_bytes())
    for state_src in (src / ".claude.json", src.parent / ".claude.json"):
        if state_src.is_file() and not state_src.is_symlink():
            if (raw_state := _read_json_dict(state_src)) is not None:
                copied.append(".claude.json")
                if not dry_run:
                    _write_atomic_0600(dst / ".claude.json", serialize_claude_json(filter_claude_state(raw_state)).encode("utf-8"))
            break
    settings_src = src / "settings.json"
    raw_settings = _read_json_dict(settings_src) if settings_src.is_file() and not settings_src.is_symlink() else {}
    filtered = filter_claude_settings(raw_settings if raw_settings is not None else {})
    copied.append("settings.json")
    if not dry_run:
        _write_atomic_0600(dst / "settings.json", serialize_claude_json(filtered).encode("utf-8"))
        for forbidden in _CLAUDE_FORBIDDEN:
            _remove_entry(dst / forbidden)
    return {"src": str(src), "dst": str(dst), "files": copied, "dry_run": dry_run}


def prepare_codex_zc_profile(src_dir: Path | str, dst_dir: Path | str, *, dry_run: bool = False) -> dict[str, Any]:
    """Копирует auth.json (0600) и отфильтрованный config.toml без mcp_servers/plugins/notify/AGENTS.md."""
    src, dst = Path(src_dir).expanduser(), Path(dst_dir).expanduser()
    copied: list[str] = []
    if not dry_run:
        _ensure_dir_0700(dst)
    auth_src = src / "auth.json"
    if auth_src.is_file() and not auth_src.is_symlink():
        copied.append("auth.json")
        if not dry_run:
            _write_atomic_0600(dst / "auth.json", auth_src.read_bytes())
    raw_cfg: dict[str, Any] = {}
    cfg_src = src / "config.toml"
    if cfg_src.is_file() and not cfg_src.is_symlink():
        try:
            parsed = tomllib.loads(cfg_src.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                raw_cfg = parsed
        except (OSError, ValueError):
            raw_cfg = {}
    filtered_toml = dump_toml(filter_codex_config(raw_cfg)).encode("utf-8")
    copied.append("config.toml")
    if not dry_run:
        _write_atomic_0600(dst / "config.toml", filtered_toml)
        for forbidden in _CODEX_FORBIDDEN:
            _remove_entry(dst / forbidden)
    return {"src": str(src), "dst": str(dst), "files": copied, "dry_run": dry_run}


def render_optin_cordis_snippet(claude_zc_dir: Path | str, codex_zc_dir: Path | str) -> str:
    """Генерирует YAML-блок opt-in Zero-Canon инстансов для `cordis.patch.yml`."""
    claude_path = json.dumps(str(Path(claude_zc_dir).expanduser()), ensure_ascii=False)
    codex_path = json.dumps(str(Path(codex_zc_dir).expanduser()), ensure_ascii=False)
    return "\n".join((
        "# Opt-in Zero-Canon subagent instances for cordis.patch.yml",
        "# Interactive chats and dsh-canon-section remain untouched.",
        "- id: tool-subagent-claude-code-zc",
        "  name: '@deepseek-ai/dsh-tool-subagent'",
        "  disabled: true",
        "  config:",
        "    provider: claude-code",
        "    toolName: subagent_claude_code_zc",
        "    backgroundMode: one-shot",
        "    maxDepth: provider-managed",
        "    env:",
        f"      CLAUDE_CONFIG_DIR: {claude_path}",
        '      BRIDGE_ZERO_CANON: "1"',
        "- id: tool-subagent-codex-zc",
        "  name: '@deepseek-ai/dsh-tool-subagent'",
        "  disabled: true",
        "  config:",
        "    provider: codex",
        "    toolName: subagent_codex_zc",
        "    backgroundMode: one-shot",
        "    maxDepth: provider-managed",
        "    env:",
        f"      CODEX_HOME: {codex_path}",
        '      BRIDGE_ZERO_CANON: "1"',
        "",
    ))


def collect_stale_backups(
    dsh_dir: Path | str, backup_dir: Path | str | None = None, *, dry_run: bool = False
) -> list[Path]:
    """Динамически находит `*.bak*`/`*.backup*` и при не-`dry_run` переносит в `backup_dir`."""
    root = Path(dsh_dir).expanduser()
    if not root.exists():
        return []
    dst_root = Path(backup_dir).expanduser().resolve() if backup_dir is not None else None
    found: set[Path] = set()
    for pattern in _BACKUP_GLOBS:
        for candidate in root.rglob(pattern):
            if candidate.is_symlink():
                continue
            if dst_root is not None:
                try:
                    resolved = candidate.resolve()
                except OSError:
                    continue
                if resolved == dst_root or dst_root in resolved.parents:
                    continue
            found.add(candidate)
    ordered = sorted(found, key=lambda item: (len(item.parts), str(item)))
    top_level: list[Path] = [item for item in ordered if not any(parent in found for parent in item.parents)]
    if backup_dir is None or dry_run:
        return top_level
    assert dst_root is not None
    _ensure_dir_0700(dst_root)
    moved: list[Path] = []
    for item in top_level:
        target = dst_root / item.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(item), str(target))
        moved.append(target)
    return moved


def build_parser() -> argparse.ArgumentParser:
    """Парсер CLI-аргументов для подготовки Zero-Canon профилей DSH."""
    today = datetime.date.today().isoformat()
    parser = argparse.ArgumentParser(description="Prepare non-invasive DSH Zero-Canon profiles.")
    parser.add_argument("--dry-run", action="store_true", help="Report planned actions without writing.")
    parser.add_argument("--dsh-dir", default="~/.dsh", help="DSH directory (default: ~/.dsh).")
    parser.add_argument("--claude-src", default="~/.claude", help="Source Claude config dir.")
    parser.add_argument("--codex-src", default="~/.codex", help="Source Codex config dir.")
    parser.add_argument("--backup-dir", default=f"~/work/backups/{today}-dsh-zero-canon", help="Backup destination dir.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Точка входа CLI."""
    args = build_parser().parse_args(argv)
    dsh_dir = Path(args.dsh_dir).expanduser()
    claude_dst, codex_dst = dsh_dir / "zero-canon" / "claude", dsh_dir / "zero-canon" / "codex"
    summary = {
        "dry_run": args.dry_run,
        "claude": prepare_claude_zc_profile(args.claude_src, claude_dst, dry_run=args.dry_run),
        "codex": prepare_codex_zc_profile(args.codex_src, codex_dst, dry_run=args.dry_run),
        "stale_backups": [str(p) for p in collect_stale_backups(dsh_dir, args.backup_dir, dry_run=args.dry_run)],
    }
    sys.stdout.write(json.dumps(summary, indent=2, ensure_ascii=False) + "\n\n")
    sys.stdout.write(render_optin_cordis_snippet(claude_dst, codex_dst))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
