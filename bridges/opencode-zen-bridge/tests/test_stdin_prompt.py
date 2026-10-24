"""Промпт идёт в `opencode run` через stdin, а не argv.

Регрессия: история чата ~1,2 млн символов в argv пробивала macOS ARG_MAX
(~1 МБ) — Popen падал `OSError: Argument list too long` (spawn_failed).
Тесты без модели: лаунчер `/bin/cat` (эхо stdin) и python-лаунчер,
считающий суммарную длину argv.

Важно: stdout читаем вручную до EOF (как делает мост), а НЕ через
communicate() — communicate() делает flush+close stdin в начале и
взаимно блокируется с потоком-писателем (штатный deadlock CPython).
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import server
from tests._fixtures import install_test_models

install_test_models(server)


def _read_all(proc: subprocess.Popen[str]) -> str:
    assert proc.stdout is not None
    chunks: list[str] = []
    try:
        while True:
            data = proc.stdout.read(65536)
            if not data:
                break
            chunks.append(data)
    finally:
        proc.stdout.close()
    return "".join(chunks)


def _reap(proc: subprocess.Popen[str]) -> None:
    """Добить процесс и закрыть все pipe (без ResourceWarning/BrokenPipeError)."""
    if proc.poll() is None:
        proc.kill()
    proc.wait(timeout=60)
    for stream in (proc.stdin, proc.stderr, proc.stdout):
        if stream is not None and not stream.closed:
            try:
                stream.close()
            except (OSError, ValueError):
                pass


class StdinPromptTest(unittest.TestCase):
    def test_big_prompt_roundtrip_via_stdin(self) -> None:
        """Промпт 2 МБ (> ARG_MAX) доходит целиком через stdin."""
        prompt = "привет-мир-идёт-через-stdin\n" * 70000  # ~2 МБ
        self.assertGreater(len(prompt.encode("utf-8")), 1_000_000)
        with tempfile.TemporaryDirectory() as tmp:
            proc = server._spawn_with_stdin(
                ["/bin/cat"], prompt, Path(tmp), dict(os.environ))
            try:
                out = _read_all(proc)
                rc = proc.wait(timeout=60)
            finally:
                _reap(proc)
        self.assertEqual(rc, 0)
        self.assertEqual(out, prompt)

    def test_prompt_not_in_argv(self) -> None:
        """В argv промпта нет: суммарная длина argv остаётся байтами."""
        prompt = "x" * 2_000_000
        launcher = [
            sys.executable, "-c",
            "import sys; print(sum(len(a) for a in sys.argv))",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            proc = server._spawn_with_stdin(
                launcher, prompt, Path(tmp), dict(os.environ))
            try:
                out = _read_all(proc)
                rc = proc.wait(timeout=60)
            finally:
                _reap(proc)
        self.assertEqual(rc, 0)
        self.assertLess(int(out.strip()), 10_000)


if __name__ == "__main__":
    unittest.main()
