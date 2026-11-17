"""Провенанс процесса: git-ревизия кода в памяти и момент старта (фиксируются при старте).

Недоступное значение — `unknown`. Env: `BRIDGE_BUILD_INFO_GIT_TIMEOUT_S` (дефолт 2.0).
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
DEFAULT_GIT_TIMEOUT_S: Final[float] = 2.0


def _env_float(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, "").strip())
    except ValueError:
        return default
    return value if 0 < value < float("inf") else default


def resolve_git_head_sha(repo_root: Path | str) -> str:
    """`git rev-parse HEAD` каталога `repo_root`; любой сбой — `unknown`."""
    try:
        done = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=False,
            timeout=_env_float(GIT_TIMEOUT_ENV, DEFAULT_GIT_TIMEOUT_S),
        )  # fmt: skip
    except (OSError, subprocess.SubprocessError):
        return UNKNOWN
    sha = done.stdout.strip()
    ok = done.returncode == 0 and len(sha) in (40, 64) and set(sha) <= set("0123456789abcdef")
    return sha if ok else UNKNOWN


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
