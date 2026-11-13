"""L1/L2: agy-bridge — fast-fail capacity-503, hot-reload auth, TTL каталогов img-*, бюджет промпта,
протокол с вложениями, провенанс в /health, `~` в путях профиля."""

from __future__ import annotations

import os
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from core.runtime_build_info import UNKNOWN, RuntimeBuildInfo
from tests.test_agy_clean_home import CleanHomeFixture, _load_bridge

_REPO = Path(__file__).resolve().parents[1]
_CAPACITY = "503 UNAVAILABLE: No capacity available for model gemini-3.8-flash-medium on the server"


def _bump(path: Path, text: str, delta_ns: int = 5_000_000_000) -> None:
    now = time.time_ns() + delta_ns
    path.write_text(text, encoding="utf-8")
    os.utime(path, ns=(now, now))


class AuthHotReloadTests(CleanHomeFixture):
    def test_rotated_token_is_recopied_without_restart(self) -> None:
        _ = self.srv._prepare_agy_home()
        token = self.gemini / "jetski-standalone-oauth-token"
        src = self.real_home / ".gemini" / "jetski-standalone-oauth-token"
        self.assertEqual(token.read_text(encoding="utf-8"), "oauth-secret")
        _bump(src, "rotated-oauth-secret-longer")
        _ = self.srv._prepare_agy_home()
        self.assertEqual(token.read_text(encoding="utf-8"), "rotated-oauth-secret-longer")
        self.assertEqual(stat.S_IMODE(os.lstat(token).st_mode), 0o600)
        self.assertEqual([p.name for p in self.clean_home.rglob(".tmp_*")], [])

    def test_unchanged_source_is_not_recopied(self) -> None:
        _ = self.srv._prepare_agy_home()
        token = self.gemini / "jetski-standalone-oauth-token"
        token.write_text("agy-refreshed-inside-clean-home", encoding="utf-8")
        _ = self.srv._prepare_agy_home()
        self.assertEqual(token.read_text(encoding="utf-8"), "agy-refreshed-inside-clean-home")

    def test_fresher_clean_home_copy_survives_source_change(self) -> None:
        _ = self.srv._prepare_agy_home()
        token = self.gemini / "jetski-standalone-oauth-token"
        src = self.real_home / ".gemini" / "jetski-standalone-oauth-token"
        _bump(src, "older-source-change", delta_ns=-3_000_000_000)
        far = time.time() + 1000
        token.write_text("fresh-in-clean-home", encoding="utf-8")
        os.utime(token, (far, far))
        _ = self.srv._prepare_agy_home()
        self.assertEqual(token.read_text(encoding="utf-8"), "fresh-in-clean-home")

    def test_kill_switch_disables_refresh(self) -> None:
        _ = self.srv._prepare_agy_home()
        src = self.real_home / ".gemini" / "jetski-standalone-oauth-token"
        _bump(src, "rotated-but-disabled")
        with mock.patch.dict(os.environ, {"AGY_AUTH_HOT_RELOAD_ENABLED": "0"}):
            _ = self.srv._prepare_agy_home()
        self.assertEqual((self.gemini / "jetski-standalone-oauth-token").read_text(encoding="utf-8"), "oauth-secret")


class BridgeUnitTests(unittest.TestCase):
    srv: Any

    @classmethod
    def setUpClass(cls) -> None:
        cls.srv = _load_bridge("agy_bridge_server_wave3_under_test")

    def test_capacity_error_body_is_503(self) -> None:
        body = self.srv.Handler._error_body({"state": "capacity_exhausted", "err": _CAPACITY})
        self.assertEqual((body["code"], body["type"]), (503, "model_capacity_exhausted"))

    def test_tool_turn_drops_unnamed_call_without_empty_delta(self) -> None:
        delivered: list[Any] = []
        turn = self.srv._ToolTurn([], lambda _t: True, lambda _t: True, lambda c: delivered.append(c) or True)
        turn._call({"id": "x", "name": "  ", "arguments": {}})
        self.assertEqual((delivered, turn.calls), ([], []))
        turn._call({"id": "y", "name": "read", "arguments": {"p": 1}})
        self.assertEqual(len(delivered), 1)
        self.assertEqual(delivered[0][0]["function"]["name"], "read")

    def test_protocols_respect_attachments(self) -> None:
        tools = [{"type": "function", "function": {"name": "t", "description": "d", "parameters": {"type": "object"}}}]
        attached = "### 1. user\nhi\n\n[attachments]\n- [image 1] /x/img-1.png\nRead every attached image"
        with_att = self.srv._with_tools_protocol(attached, tools, None)
        plain = self.srv._with_tools_protocol("### 1. user\nhi", tools, None)
        self.assertIn("except view_file on the attachment files", with_att)
        self.assertNotIn("except", plain.split("Available tools:")[0])
        text_att = self.srv._with_pure_text_protocol(attached)
        self.assertIn("DO NOT USE ANY TOOLS", text_att)
        self.assertIn("except view_file", text_att)
        self.assertNotIn("except", self.srv._with_pure_text_protocol("hi"))
        with mock.patch.dict(os.environ, {"AGY_BRIDGE_ATTACHMENT_TOOL": "read_media"}):
            self.assertIn("except read_media", self.srv._with_pure_text_protocol(attached))

    def test_single_pass_pruning_with_protocol_wrapper(self) -> None:
        srv = self.srv
        tools = [
            {"type": "function", "function": {"name": f"tool_{i}", "description": "x" * 300, "parameters": {"type": "object"}}}
            for i in range(40)
        ]
        messages = [{"role": "system", "content": "sys"}] + [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i} " + "y" * 4000} for i in range(60)
        ] + [{"role": "user", "content": "last question"}]
        reserve = srv._protocol_reserve_bytes(True, tools, None)
        self.assertGreater(reserve, 10_000)
        history = srv._messages_to_prompt(messages, reserve_bytes=reserve)
        full = srv._with_tools_protocol(history, tools, None)
        limit = srv.PROMPT_MAX_NDJSON_BYTES
        self.assertLessEqual(srv._ndjson_bytes(full), limit)
        logs: list[str] = []
        with mock.patch.object(srv, "_log", logs.append):
            self.assertEqual(srv._ensure_prompt_fits_ndjson(full), full)
        self.assertFalse([m for m in logs if "middle-pruned" in m])
        self.assertIn("last question", full)
        # без резерва тот же вход после обёртки превышал бы потолок (прежний двойной проход)
        legacy = srv._with_tools_protocol(srv._messages_to_prompt(messages), tools, None)
        self.assertGreater(srv._ndjson_bytes(legacy), limit)

    def test_prompt_budget_floor_and_config(self) -> None:
        srv = self.srv
        self.assertEqual(srv._prompt_budget(0), srv.PROMPT_MAX_NDJSON_BYTES)
        self.assertEqual(srv._prompt_budget(10**9), 4096)
        with mock.patch.dict(os.environ, {"AGY_BRIDGE_PRUNE_MIN_BUDGET_BYTES": "8192"}):
            self.assertEqual(srv._prompt_budget(10**9), 8192)

    def test_runtime_build_fields(self) -> None:
        fields = self.srv._runtime_build_fields()
        for key in ("git_head_sha", "boot_ts", "agy_binary_sha256", "agy_home"):
            self.assertIn(key, fields)
        self.assertIsInstance(fields["boot_ts"], float)

    def test_tilde_paths_are_expanded(self) -> None:
        env = {"AGY_BRIDGE_CLEAN_HOME": "~/agy-wave3-home-probe", "AGY_BRIDGE_AGY_BIN": "~/bin/agy.real"}
        with mock.patch.dict(os.environ, env):
            mod = _load_bridge("agy_bridge_server_wave3_tilde")
        self.assertEqual(mod.CLEAN_HOME_DIR, (Path.home() / "agy-wave3-home-probe").resolve())
        self.assertEqual(mod.AGY_BIN, str(Path.home() / "bin" / "agy.real"))


class ImageDirTtlTests(unittest.TestCase):
    srv: Any

    @classmethod
    def setUpClass(cls) -> None:
        cls.srv = _load_bridge("agy_bridge_server_wave3_img")

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.addCleanup(self.srv._retained_img_dirs.clear)

    def _dir(self) -> Path:
        path = self.root / f"img-{len(list(self.root.iterdir()))}"
        path.mkdir()
        (path / "img-1.png").write_bytes(b"x")
        self.srv._active_img_dirs.add(str(path))
        return path

    def test_dir_survives_until_ttl_then_gc(self) -> None:
        srv = self.srv
        path = self._dir()
        with mock.patch.dict(os.environ, {"AGY_IMG_DIR_TTL_S": "300"}):
            srv._release_img_dir(path, retain=True)
            self.assertTrue(path.is_dir())
            self.assertEqual(srv._gc_retained_img_dirs(), 0)
            future = time.monotonic() + 301
            with mock.patch.object(srv.time, "monotonic", return_value=future):
                self.assertEqual(srv._gc_retained_img_dirs(), 1)
        self.assertFalse(path.exists())
        self.assertNotIn(str(path), srv._active_img_dirs)

    def test_no_retention_without_tool_call_or_with_zero_ttl(self) -> None:
        srv = self.srv
        plain = self._dir()
        with mock.patch.dict(os.environ, {"AGY_IMG_DIR_TTL_S": "300"}):
            srv._release_img_dir(plain, retain=False)
        self.assertFalse(plain.exists())
        zero = self._dir()
        with mock.patch.dict(os.environ, {"AGY_IMG_DIR_TTL_S": "0"}):
            srv._release_img_dir(zero, retain=True)
        self.assertFalse(zero.exists())

    def test_retained_count_is_bounded(self) -> None:
        srv = self.srv
        dirs = [self._dir() for _ in range(4)]
        with mock.patch.dict(os.environ, {"AGY_IMG_DIR_TTL_S": "300", "AGY_IMG_DIR_RETAIN_MAX": "2"}):
            for path in dirs:
                srv._release_img_dir(path, retain=True)
        self.assertEqual(sum(p.exists() for p in dirs), 2)
        self.assertTrue(dirs[-1].exists())


class FastFailProcessTests(unittest.TestCase):
    """Реальный дочерний процесс: capacity-строка в stderr прерывает ход без ожидания backoff."""

    def test_capacity_line_kills_child_and_signals_queue(self) -> None:
        srv = _load_bridge("agy_bridge_server_wave3_run")
        with tempfile.TemporaryDirectory() as tmp:
            launcher = Path(tmp) / "launcher.sh"
            args_file = Path(tmp) / "args.txt"
            launcher.write_text(
                f'#!/bin/sh\necho "$@" > "{args_file}"\ncat >/dev/null &\n'
                f'echo "{_CAPACITY}" >&2\nsleep 30\n',
                encoding="utf-8",
            )
            launcher.chmod(0o755)
            env = {"PATH": os.environ["PATH"], "HOME": tmp}
            with (
                mock.patch.object(srv, "LAUNCHER", str(launcher)),
                mock.patch.object(srv, "_launch_env", lambda: env),
                mock.patch.object(srv, "WORKSPACE", Path(tmp) / "ws"),
            ):
                started = time.monotonic()
                run = srv.Run("hi", "gemini-3.8-flash", "high", "default", "", "t", mode="ask")
                try:
                    kind, payload = run.q.get(timeout=10)
                    elapsed = time.monotonic() - started
                    self.assertEqual(kind, "capacity_exhausted")
                    self.assertIn("No capacity available", payload)
                    self.assertLess(elapsed, 10)
                    self.assertEqual(run.proc.wait(timeout=10) is not None, True)
                    self.assertIn("--disable-slash-commands", args_file.read_text(encoding="utf-8"))
                finally:
                    run.close()

    def test_kill_switch_keeps_legacy_behaviour(self) -> None:
        srv = _load_bridge("agy_bridge_server_wave3_run_off")
        with tempfile.TemporaryDirectory() as tmp:
            launcher = Path(tmp) / "launcher.sh"
            launcher.write_text(f'#!/bin/sh\necho "{_CAPACITY}" >&2\nexit 3\n', encoding="utf-8")
            launcher.chmod(0o755)
            env = {"PATH": os.environ["PATH"], "HOME": tmp}
            with (
                mock.patch.object(srv, "LAUNCHER", str(launcher)),
                mock.patch.object(srv, "_launch_env", lambda: env),
                mock.patch.object(srv, "WORKSPACE", Path(tmp) / "ws"),
                mock.patch.dict(os.environ, {"AGY_FAST_FAIL_ON_CAPACITY_503": "0"}),
            ):
                run = srv.Run("hi", "gemini-3.8-flash", "high", "default", "", "t")
                try:
                    kinds = []
                    while True:
                        kind, _payload = run.q.get(timeout=10)
                        kinds.append(kind)
                        if kind in ("done", "pump_error"):
                            break
                    self.assertNotIn("capacity_exhausted", kinds)
                finally:
                    run.close()


class RuntimeBuildInfoTests(unittest.TestCase):
    def test_git_sha_of_repo_and_unknown_outside(self) -> None:
        info = RuntimeBuildInfo(_REPO)
        self.assertRegex(str(info.git_head_sha), r"^[0-9a-f]{40,64}$")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(RuntimeBuildInfo(tmp).git_head_sha, UNKNOWN)
        snap = RuntimeBuildInfo(_REPO, git_head_sha="abc").snapshot({"x": 1})
        self.assertEqual((snap["git_head_sha"], snap["x"]), ("abc", 1))
        self.assertIsInstance(snap["boot_ts"], float)


if __name__ == "__main__":
    sys.exit(unittest.main())
