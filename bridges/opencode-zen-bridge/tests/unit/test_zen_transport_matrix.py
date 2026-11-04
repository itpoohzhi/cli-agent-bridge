"""Unit test module test_zen_transport_matrix.py."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import server
from tests.serve_test_base import (
    BaseServeTest,
    MODEL,
    _deltas,
)


class TestZenTransportMatrix(BaseServeTest):


    def test_slow_serve_gets_status_and_no_status_on_fast(self) -> None:
        """Медленный serve: статус <1с; быстрый serve: без лишнего статуса в reasoning модели."""
        chunks, _elapsed = self.bridge.post_stream_timed("__slow__ жди")
        statuses = [
            (at, t) for at, t in _deltas(chunks, "reasoning_content") if "[мост]" in t
        ]
        self.assertTrue(statuses)
        self.assertLessEqual(statuses[0][0], 1.0)
    def test_helper_argv_validation_and_lease_dir(self) -> None:
        """--serve-helper: 6 аргументов, lease только в переданном каталоге."""
        fn = server._run_serve_helper_cli  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        self.assertNotEqual(fn([]), 0)
        self.assertNotEqual(fn(["a", "notaport", "bin", "lease", "1", "x"]), 0)
        lease_dir = self.tmp / "leases-custom"
        script = Path(server.__file__).resolve()
        proc = subprocess.run(
            [
                sys.executable,
                "-I",
                str(script),
                "--serve-helper",
                "attemptX",
                "9",
                "bin",
                str(lease_dir),
                "1",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertNotEqual(proc.returncode, 0)
    def test_helper_drains_large_stderr(self) -> None:
        """FakeServe пишет >64КиБ в stderr до SSE и не блокируется."""
        chunks, elapsed = self.bridge.post_stream_timed("обычный запрос")
        self.assertLess(elapsed, 15.0)
        self.assertTrue(_deltas(chunks, "reasoning_content"))
    def test_clean_room_fake_serve_via_monkeypatched_bin(self) -> None:
        """RW-002: OPENCODE_BIN подменён при пустом HOME, serve работает."""
        chunks, _elapsed = self.bridge.post_stream_timed("чистая комната")
        self.assertTrue(_deltas(chunks, "content"))
    def test_foreign_listener_rejected_and_startup_reaper(self) -> None:
        """Чужой слушатель порта -> ServeUnavailable; reaper удаляет lease мёртвого родителя."""
        with mock.patch.object(server, "_lsof_listener_pid", return_value=999998):
            with self.assertRaises(server.ServeUnavailable) as ctx:
                _ = server._spawn_serve("att_foreign", server._serve_env(MODEL))  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        self.assertIn("foreign listener", str(ctx.exception))
        lease_dir = self.tmp / "reaper-leases"
        lease_dir.mkdir()
        dead = lease_dir / "lease-dead.json"
        alive = lease_dir / "lease-alive.json"
        _ = dead.write_text(
            json.dumps(
                {
                    "parent_pid": 999999,
                    "helper_pid": 0,
                    "pgid": 0,
                    "owner_uid": os.getuid(),
                }
            ),
            "utf-8",
        )
        _ = alive.write_text(
            json.dumps(
                {
                    "parent_pid": os.getpid(),
                    "helper_pid": 0,
                    "pgid": 0,
                    "owner_uid": os.getuid(),
                }
            ),
            "utf-8",
        )
        _ = server._startup_reaper(lease_dir)  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        self.assertFalse(dead.exists())
        self.assertTrue(alive.exists())
