"""Поддельный `opencode`: пишет argv и OPENCODE_* окружение в файлы и отвечает событиями JSON."""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path
from unittest.mock import patch

import server


def allow_child_env(*names: str):
    """Патчер: тестовые переменные проходят белый список env (THREAT-003) до дочернего процесса."""
    return patch.object(server, "_STANDALONE_ENV_ALLOWLIST", (*server._STANDALONE_ENV_ALLOWLIST, *names))

_SCRIPT = """#!/bin/sh
printf '%s\\n' "$@" > "$ZEN_FAKE_OUT/argv"
env | grep '^OPENCODE_' | sort > "$ZEN_FAKE_OUT/env"
cat > /dev/null
echo '{"type":"text","part":{"text":"OK"}}'
echo '{"type":"step_finish","part":{"reason":"stop","tokens":{"input":1,"output":1}}}'
"""


class FakeCli:
    """Временный лаунчер; `argv()` и `env()` — то, что получил дочерний процесс."""

    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="zen-fake-cli-")
        self.dir = Path(self._tmp.name)
        self.path = self.dir / "opencode"
        self.path.write_text(_SCRIPT, "utf-8")
        self.path.chmod(self.path.stat().st_mode | stat.S_IXUSR)
        self._old = os.environ.get("ZEN_FAKE_OUT")
        os.environ["ZEN_FAKE_OUT"] = str(self.dir)
        self._allow = allow_child_env("ZEN_FAKE_OUT")
        self._allow.start()

    def close(self) -> None:
        self._allow.stop()
        if self._old is None:
            os.environ.pop("ZEN_FAKE_OUT", None)
        else:
            os.environ["ZEN_FAKE_OUT"] = self._old
        self._tmp.cleanup()

    def argv(self) -> list[str]:
        return (self.dir / "argv").read_text("utf-8").splitlines()

    def env(self) -> dict[str, str]:
        pairs = (line.split("=", 1) for line in (self.dir / "env").read_text("utf-8").splitlines() if "=" in line)
        return {k: v for k, v in pairs}
