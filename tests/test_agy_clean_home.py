"""Тесты изоляции <clean-home> agy-bridge (Zero-Canon, ADR-0023).

Покрыто: структура каталогов и права (0700/0600), симлинк Library -> ~/Library,
симлинки bin/builtin, отсутствие AGENTS.md/GEMINI.md/hooks.json, окружение
`_launch_env()`, согласованность BRAIN_DIR/CONV_DIR с CLEAN_HOME_DIR и
потокобезопасность `_prepare_agy_home()`.

Мост лежит в каталоге с дефисом, поэтому грузится через `importlib`. Реальный HOME
не трогается: `HOME` и `CLEAN_HOME_DIR` подменяются на временные каталоги.
"""

from __future__ import annotations

import importlib.util
import os
import stat
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

_BRIDGE_PY = (
    Path(__file__).resolve().parents[1] / "bridges" / "agy-bridge" / "server.py"
)

_SECRET_FILES = {
    ".gemini/jetski-standalone-oauth-token": "oauth-secret",
    ".gemini/projects.json": '{"projects": {}}',
    ".gemini/antigravity-cli/installation_id": "install-id",
    ".gemini/antigravity-cli/jetski_state.pbtxt": "state: 1",
    ".gemini/antigravity-cli/settings.json": "{}",
}
_CANON_NAMES = ("AGENTS.md", "GEMINI.md", "hooks.json")


def _load_bridge(name: str = "agy_bridge_server_clean_home_under_test") -> Any:
    os.environ.setdefault("AGY_BRIDGE_KEY", "test-key-agy-clean-home")
    spec = importlib.util.spec_from_file_location(name, _BRIDGE_PY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _mode(path: Path) -> int:
    return stat.S_IMODE(os.lstat(path).st_mode)


class CleanHomeFixture(unittest.TestCase):
    """Фиксирует поддельный HOME и временный <clean-home>."""

    srv: Any

    @classmethod
    def setUpClass(cls) -> None:
        cls.srv = _load_bridge()

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.real_home = self.tmp / "home"
        self.clean_home = self.tmp / "ws" / "runtime" / "agy-home"
        (self.real_home / "Library" / "Keychains").mkdir(parents=True)
        for rel, body in _SECRET_FILES.items():
            path = self.real_home / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            _ = path.write_text(body, encoding="utf-8")
        cli = self.real_home / ".gemini" / "antigravity-cli"
        (cli / "bin").mkdir()
        (cli / "builtin").mkdir()
        # Канон пользователя, который не должен попасть в <clean-home>.
        for name in _CANON_NAMES:
            _ = (self.real_home / ".gemini" / name).write_text("x", encoding="utf-8")
            _ = (cli / name).write_text("x", encoding="utf-8")
        for patcher in (
            mock.patch.object(self.srv, "HOME", self.real_home),
            mock.patch.object(self.srv, "CLEAN_HOME_DIR", self.clean_home),
            mock.patch.object(self.srv, "_AGY_HOME_INITIALIZED", False),
        ):
            _ = patcher.start()
            self.addCleanup(patcher.stop)

    @property
    def gemini(self) -> Path:
        return self.clean_home / ".gemini"

    @property
    def cli(self) -> Path:
        return self.gemini / "antigravity-cli"


class PrepareAgyHomeTests(CleanHomeFixture):
    def test_returns_clean_home_and_sets_initialized(self) -> None:
        result = self.srv._prepare_agy_home()
        self.assertEqual(result, self.clean_home)
        self.assertTrue(self.srv._AGY_HOME_INITIALIZED)

    def test_directory_structure_and_modes_0700(self) -> None:
        _ = self.srv._prepare_agy_home()
        for path in (
            self.clean_home,
            self.gemini,
            self.cli,
            self.cli / "conversations",
            self.cli / "brain",
        ):
            self.assertTrue(path.is_dir(), str(path))
            self.assertEqual(_mode(path), 0o700, str(path))

    def test_modes_forced_despite_permissive_umask(self) -> None:
        old = os.umask(0o000)
        try:
            _ = self.srv._prepare_agy_home()
        finally:
            _ = os.umask(old)
        self.assertEqual(_mode(self.clean_home), 0o700)
        self.assertEqual(_mode(self.cli / "brain"), 0o700)
        for rel in _SECRET_FILES:
            self.assertEqual(_mode(self.clean_home / rel), 0o600, rel)

    def test_config_files_copied_with_0600(self) -> None:
        _ = self.srv._prepare_agy_home()
        for rel, body in _SECRET_FILES.items():
            dst = self.clean_home / rel
            self.assertTrue(dst.is_file() and not dst.is_symlink(), rel)
            self.assertEqual(dst.read_text(encoding="utf-8"), body)
            self.assertEqual(_mode(dst), 0o600, rel)

    def test_no_temporary_files_left(self) -> None:
        _ = self.srv._prepare_agy_home()
        leftovers = [p.name for p in self.clean_home.rglob(".tmp_*")]
        self.assertEqual(leftovers, [])

    def test_library_symlink_points_to_real_library(self) -> None:
        _ = self.srv._prepare_agy_home()
        link = self.clean_home / "Library"
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), str(self.real_home / "Library"))
        self.assertTrue((link / "Keychains").is_dir())

    def test_wrong_library_symlink_is_replaced(self) -> None:
        self.clean_home.mkdir(parents=True)
        os.symlink(self.tmp / "elsewhere", self.clean_home / "Library")
        _ = self.srv._prepare_agy_home()
        self.assertEqual(
            os.readlink(self.clean_home / "Library"), str(self.real_home / "Library")
        )

    def test_bin_and_builtin_symlinks(self) -> None:
        _ = self.srv._prepare_agy_home()
        real_cli = self.real_home / ".gemini" / "antigravity-cli"
        for name in ("bin", "builtin"):
            link = self.cli / name
            self.assertTrue(link.is_symlink(), name)
            self.assertEqual(os.readlink(link), str(real_cli / name))

    def test_missing_bin_and_builtin_are_skipped(self) -> None:
        real_cli = self.real_home / ".gemini" / "antigravity-cli"
        (real_cli / "bin").rmdir()
        (real_cli / "builtin").rmdir()
        _ = self.srv._prepare_agy_home()
        self.assertFalse((self.cli / "bin").exists())
        self.assertFalse((self.cli / "builtin").is_symlink())

    def test_missing_source_files_are_skipped(self) -> None:
        (self.real_home / ".gemini" / "projects.json").unlink()
        _ = self.srv._prepare_agy_home()
        self.assertFalse((self.gemini / "projects.json").exists())
        self.assertTrue((self.gemini / "jetski-standalone-oauth-token").is_file())

    def test_zero_canon_no_agents_gemini_hooks(self) -> None:
        _ = self.srv._prepare_agy_home()
        for name in _CANON_NAMES:
            self.assertEqual(
                [p for p in self.clean_home.rglob(name)],
                [],
                f"{name} найден в clean-home",
            )

    def test_zero_canon_removes_preexisting_canon_files(self) -> None:
        self.cli.mkdir(parents=True)
        for base in (self.clean_home, self.gemini, self.cli):
            for name in _CANON_NAMES:
                _ = (base / name).write_text("stale", encoding="utf-8")
        _ = self.srv._prepare_agy_home()
        for base in (self.clean_home, self.gemini, self.cli):
            for name in _CANON_NAMES:
                self.assertFalse((base / name).exists(), f"{base / name}")

    def test_stale_config_is_overwritten_atomically(self) -> None:
        self.gemini.mkdir(parents=True)
        dst = self.gemini / "projects.json"
        _ = dst.write_text("old", encoding="utf-8")
        _ = self.srv._prepare_agy_home()
        self.assertEqual(dst.read_text(encoding="utf-8"), '{"projects": {}}')
        self.assertEqual(_mode(dst), 0o600)

    def test_copy_failure_leaves_no_tmp_file(self) -> None:
        dst_dir = self.tmp / "dst"
        dst_dir.mkdir()
        src = self.real_home / ".gemini" / "projects.json"
        with mock.patch.object(self.srv.os, "replace", side_effect=OSError("boom")):
            with self.assertRaises(OSError):
                self.srv._copy_private_atomic(src, dst_dir / "projects.json")
        self.assertEqual(list(dst_dir.iterdir()), [])

    def test_initialization_runs_only_once(self) -> None:
        _ = self.srv._prepare_agy_home()
        marker = self.gemini / "projects.json"
        marker.unlink()
        _ = self.srv._prepare_agy_home()
        self.assertFalse(
            marker.exists(), "повторный вызов не должен переинициализировать"
        )

    def test_threadsafe_concurrent_calls(self) -> None:
        workers = 16
        barrier = threading.Barrier(workers)
        results: list[Path] = []
        errors: list[BaseException] = []
        sync = threading.Lock()
        copies = 0
        real_copy = self.srv._copy_private_atomic

        def counting_copy(src: Path, dst: Path) -> None:
            nonlocal copies
            with sync:
                copies += 1
            real_copy(src, dst)

        def run() -> None:
            try:
                _ = barrier.wait(timeout=10)
                res = self.srv._prepare_agy_home()
                with sync:
                    results.append(res)
            except BaseException as exc:  # noqa: BLE001 - собираем для assert
                with sync:
                    errors.append(exc)

        with mock.patch.object(self.srv, "_copy_private_atomic", counting_copy):
            threads = [threading.Thread(target=run) for _ in range(workers)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)
        self.assertEqual(errors, [])
        self.assertEqual(results, [self.clean_home] * workers)
        self.assertEqual(copies, len(_SECRET_FILES), "инициализация ровно один раз")
        self.assertEqual(_mode(self.clean_home), 0o700)


class LaunchEnvTests(CleanHomeFixture):
    def test_launch_env_values(self) -> None:
        with mock.patch.dict(os.environ, {"AGY_BRIDGE_KEY": "secret"}):
            env = self.srv._launch_env()
        self.assertEqual(env["HOME"], str(self.clean_home))
        self.assertEqual(env["BRIDGE_ZERO_CANON"], "1")
        self.assertEqual(env["BROWSER"], "/usr/bin/false")
        self.assertNotIn("AGY_BRIDGE_KEY", env)
        self.assertTrue((Path(env["HOME"]) / "Library").is_symlink())

    def test_launch_env_does_not_mutate_os_environ(self) -> None:
        before = os.environ.get("HOME")
        _ = self.srv._launch_env()
        self.assertEqual(os.environ.get("HOME"), before)
        self.assertNotIn("BRIDGE_ZERO_CANON", os.environ)

    def test_launch_env_keeps_other_variables(self) -> None:
        with mock.patch.dict(os.environ, {"HTTPS_PROXY": "http://p:1"}):
            env = self.srv._launch_env()
        self.assertEqual(env["HTTPS_PROXY"], "http://p:1")


class PathsAlignmentTests(unittest.TestCase):
    def _load_with_env(self, **overrides: str) -> Any:
        keys = ("AGY_BRIDGE_CLEAN_HOME", "AGY_BRIDGE_BRAIN", "AGY_BRIDGE_CONVERSATIONS")
        env = {k: "" for k in keys} | overrides
        with mock.patch.dict(os.environ, env):
            return _load_bridge("agy_bridge_server_paths_under_test")

    def test_default_clean_home_under_workspace_runtime(self) -> None:
        mod = self._load_with_env()
        self.assertEqual(mod.CLEAN_HOME_DIR, mod.WORKSPACE / "runtime" / "agy-home")

    def test_brain_and_conv_follow_clean_home(self) -> None:
        mod = self._load_with_env()
        base = mod.CLEAN_HOME_DIR / ".gemini" / "antigravity-cli"
        self.assertEqual(mod.BRAIN_DIR, base / "brain")
        self.assertEqual(mod.CONV_DIR, base / "conversations")
        self.assertEqual(
            mod.BRAIN_DIR.parts[-3:], (".gemini", "antigravity-cli", "brain")
        )
        self.assertEqual(
            mod.CONV_DIR.parts[-3:], (".gemini", "antigravity-cli", "conversations")
        )

    def test_clean_home_env_override_propagates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mod = self._load_with_env(AGY_BRIDGE_CLEAN_HOME=td)
            self.assertEqual(mod.CLEAN_HOME_DIR, Path(td))
            self.assertEqual(
                mod.BRAIN_DIR, Path(td) / ".gemini" / "antigravity-cli" / "brain"
            )
            self.assertEqual(
                mod.CONV_DIR, Path(td) / ".gemini" / "antigravity-cli" / "conversations"
            )

    def test_explicit_brain_and_conv_overrides_win(self) -> None:
        mod = self._load_with_env(
            AGY_BRIDGE_BRAIN="/tmp/custom-brain",
            AGY_BRIDGE_CONVERSATIONS="/tmp/custom-conv",
        )
        self.assertEqual(mod.BRAIN_DIR, Path("/tmp/custom-brain"))
        self.assertEqual(mod.CONV_DIR, Path("/tmp/custom-conv"))


if __name__ == "__main__":
    _ = unittest.main()
