"""Провенанс процесса: git-ревизия кода в памяти и момент старта (фиксируются при старте).

`git_head_sha`: git(repo_root) → git(realpath пакета core) → env `BRIDGE_GIT_HEAD_SHA` → `unknown`.
Env: `BRIDGE_BUILD_INFO_GIT_TIMEOUT_S` (дефолт 2.0). Хардкода ревизий нет.
"""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Final

UNKNOWN: Final[str] = "unknown"
GIT_TIMEOUT_ENV: Final[str] = "BRIDGE_BUILD_INFO_GIT_TIMEOUT_S"
GIT_SHA_ENV: Final[str] = "BRIDGE_GIT_HEAD_SHA"
DEFAULT_GIT_TIMEOUT_S: Final[float] = 2.0
_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")


def _env_float(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, "").strip())
    except ValueError:
        return default
    return value if 0 < value < float("inf") else default


def _valid_sha(sha: str) -> bool:
    return len(sha) in (40, 64) and set(sha) <= _HEX


def _core_package_dir() -> Path:
    """Реальный каталог пакета `core` (разрешает симлинки установки)."""
    return Path(__file__).resolve().parent


def _git_head(repo_root: Path | str) -> str:
    """`git rev-parse HEAD` каталога; любой сбой — `unknown`."""
    try:
        done = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=False,
            timeout=_env_float(GIT_TIMEOUT_ENV, DEFAULT_GIT_TIMEOUT_S),
        )  # fmt: skip
    except (OSError, subprocess.SubprocessError):
        return UNKNOWN
    sha = done.stdout.strip().lower()
    return sha if done.returncode == 0 and _valid_sha(sha) else UNKNOWN


def resolve_git_head_sha(repo_root: Path | str, env: Mapping[str, str] | None = None) -> str:
    """Цепочка: git(repo_root) → git(realpath core) → env `BRIDGE_GIT_HEAD_SHA` → `unknown`."""
    for root in (Path(repo_root), _core_package_dir()):
        sha = _git_head(root)
        if sha != UNKNOWN:
            return sha
    values = os.environ if env is None else env
    declared = values.get(GIT_SHA_ENV, "").strip().lower()
    return declared if _valid_sha(declared) else UNKNOWN


class RuntimeBuildInfo:
    """Снимок провенанса процесса."""

    def __init__(self, repo_root: Path | str, *, git_head_sha: str | None = None) -> None:
        self._repo_root = Path(repo_root)
        self.boot_ts: float = time.time()
        self.git_head_sha: str = resolve_git_head_sha(self._repo_root) if git_head_sha is None else git_head_sha

    def snapshot(self, extra: Mapping[str, object] | None = None) -> dict[str, object]:
        """Поля health: `git_head_sha`, `boot_ts` и `extra`."""
        fields: dict[str, object] = {"git_head_sha": self.git_head_sha, "boot_ts": self.boot_ts}
        if extra:
            fields.update(extra)
        return fields
