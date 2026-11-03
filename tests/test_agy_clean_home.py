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
import shutil
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
_CLI_REL = Path(".gemini") / "antigravity-cli"


def _load_bridge(name: str = "agy_bridge_server_clean_home_under_test") -> Any:
    spec = importlib.util.spec_from_file_location(name, _BRIDGE_PY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    # Ключ нужен только на время импорта; окружение процесса восстанавливается.
    with mock.patch.dict(os.environ):
        os.environ.setdefault("AGY_BRIDGE_KEY", "test-key-agy-clean-home")
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
        # Пути моста безусловно resolved (macOS: /var -> /private/var).
        self.tmp = Path(tmp.name).resolve()
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
            mock.patch.object(
                self.srv, "BRAIN_DIR", self.clean_home / _CLI_REL / "brain"
            ),
            mock.patch.object(
                self.srv, "CONV_DIR", self.clean_home / _CLI_REL / "conversations"
            ),
            mock.patch.object(self.srv, "_AGY_HOME_INITIALIZED", False),
            mock.patch.object(self.srv, "_VERIFIED_CLEAN_HOME", None),
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
        real_cli = self.real_home / ".gemini" / "antigravity-cli"
        for name in ("bin", "builtin"):
            _ = (real_cli / name / "tool.bin").write_text("x", encoding="utf-8")
            (real_cli / name / "sub").mkdir()
        _ = self.srv._prepare_agy_home()
        for name in ("bin", "builtin"):
            clean_sub = self.cli / name
            self.assertTrue(clean_sub.is_dir() and not clean_sub.is_symlink(), name)
            self.assertEqual(_mode(clean_sub), 0o700, name)
            link = clean_sub / "tool.bin"
            self.assertTrue(link.is_symlink(), f"{name}/tool.bin")
            self.assertEqual(os.readlink(link), str(real_cli / name / "tool.bin"))
            # Подкаталог — приватный каталог 0700, а не симлинк на каталог хоста.
            sub = clean_sub / "sub"
            self.assertTrue(sub.is_dir() and not sub.is_symlink(), f"{name}/sub")
            self.assertEqual(_mode(sub), 0o700, f"{name}/sub")
            # Сквозная запись в реальный каталог невозможна.
            _ = (clean_sub / "new.txt").write_text("y", encoding="utf-8")
            self.assertFalse((real_cli / name / "new.txt").exists(), name)

    def test_legacy_dir_symlink_is_replaced_by_private_dir(self) -> None:
        real_cli = self.real_home / ".gemini" / "antigravity-cli"
        self.cli.mkdir(parents=True)
        os.symlink(real_cli / "bin", self.cli / "bin")
        _ = self.srv._prepare_agy_home()
        self.assertTrue((self.cli / "bin").is_dir())
        self.assertFalse((self.cli / "bin").is_symlink())
        self.assertTrue((real_cli / "bin").is_dir())

    def test_bin_nested_dir_is_not_symlinked_directly(self) -> None:
        real_cli = self.real_home / ".gemini" / "antigravity-cli"
        for name in ("bin", "builtin"):
            nested = real_cli / name / "sub" / "deeper"
            nested.mkdir(parents=True)
            _ = (real_cli / name / "sub" / "inner.bin").write_text("x", "utf-8")
            _ = (nested / "leaf.bin").write_text("x", "utf-8")
        _ = self.srv._prepare_agy_home()
        for name in ("bin", "builtin"):
            sub = self.cli / name / "sub"
            deeper = sub / "deeper"
            for directory in (sub, deeper):
                self.assertTrue(
                    directory.is_dir() and not directory.is_symlink(), str(directory)
                )
                self.assertEqual(_mode(directory), 0o700, str(directory))
            for link, target in (
                (sub / "inner.bin", real_cli / name / "sub" / "inner.bin"),
                (deeper / "leaf.bin", real_cli / name / "sub" / "deeper" / "leaf.bin"),
            ):
                self.assertTrue(link.is_symlink(), str(link))
                self.assertEqual(os.readlink(link), str(target))
            # Сквозная запись через вложенный каталог в реальный профиль невозможна.
            _ = (sub / "new.txt").write_text("y", encoding="utf-8")
            _ = (deeper / "new.txt").write_text("y", encoding="utf-8")
            self.assertFalse((real_cli / name / "sub" / "new.txt").exists())
            self.assertFalse((real_cli / name / "sub" / "deeper" / "new.txt").exists())

    def test_bin_legacy_nested_dir_symlink_is_replaced(self) -> None:
        real_cli = self.real_home / ".gemini" / "antigravity-cli"
        (real_cli / "bin" / "sub").mkdir()
        _ = (real_cli / "bin" / "sub" / "inner.bin").write_text("x", "utf-8")
        (self.cli / "bin").mkdir(parents=True)
        os.symlink(real_cli / "bin" / "sub", self.cli / "bin" / "sub")
        _ = self.srv._prepare_agy_home()
        sub = self.cli / "bin" / "sub"
        self.assertTrue(sub.is_dir() and not sub.is_symlink())
        self.assertTrue((sub / "inner.bin").is_symlink())
        self.assertTrue((real_cli / "bin" / "sub" / "inner.bin").is_file())

    def test_bin_symlink_cycle_is_not_followed_forever(self) -> None:
        real_cli = self.real_home / ".gemini" / "antigravity-cli"
        (real_cli / "bin" / "sub").mkdir()
        os.symlink(real_cli / "bin", real_cli / "bin" / "sub" / "loop")
        _ = self.srv._prepare_agy_home()
        self.assertTrue((self.cli / "bin" / "sub").is_dir())
        self.assertFalse((self.cli / "bin" / "sub" / "loop").exists())

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
        src = self.real_home / ".gemini" / "projects.json"
        src_mtime = src.stat().st_mtime
        os.utime(dst, (src_mtime - 100, src_mtime - 100))
        _ = self.srv._prepare_agy_home()
        self.assertEqual(dst.read_text(encoding="utf-8"), '{"projects": {}}')
        self.assertEqual(_mode(dst), 0o600)

    def test_newer_clean_home_tokens_not_overwritten_by_stale_source(self) -> None:
        self.gemini.mkdir(parents=True)
        token = self.gemini / "jetski-standalone-oauth-token"
        src = self.real_home / ".gemini" / "jetski-standalone-oauth-token"
        _ = token.write_text("fresh-refreshed-token", encoding="utf-8")
        src_mtime = src.stat().st_mtime
        os.utime(token, (src_mtime + 100, src_mtime + 100))
        _ = self.srv._prepare_agy_home()
        self.assertEqual(token.read_text(encoding="utf-8"), "fresh-refreshed-token")
        self.assertEqual(self.srv._AGY_HOME_INITIALIZED, True)
        # Прочие файлы без более свежей копии в <clean-home> по-прежнему копируются.
        self.assertTrue((self.gemini / "projects.json").is_file())

    def test_newer_clean_home_tokens_enforce_0600_and_reject_symlink(self) -> None:
        self.gemini.mkdir(parents=True)
        token = self.gemini / "jetski-standalone-oauth-token"
        src = self.real_home / ".gemini" / "jetski-standalone-oauth-token"
        _ = token.write_text("fresh-refreshed-token", encoding="utf-8")
        token.chmod(0o644)
        src_mtime = src.stat().st_mtime
        os.utime(token, (src_mtime + 100, src_mtime + 100))
        _ = self.srv._prepare_agy_home()
        # Свежий токен сохранён, но права принудительно выровнены до 0600.
        self.assertEqual(token.read_text(encoding="utf-8"), "fresh-refreshed-token")
        self.assertEqual(_mode(token), 0o600)

        # Симлинк на месте токена заменяется регулярным файлом 0600; цель не трогается.
        external = self.tmp / "external-token"
        _ = external.write_text("external", encoding="utf-8")
        external.chmod(0o644)
        token.unlink()
        os.symlink(external, token)
        self.srv._AGY_HOME_INITIALIZED = False
        _ = self.srv._prepare_agy_home()
        self.assertTrue(token.is_file() and not token.is_symlink())
        self.assertEqual(token.read_text(encoding="utf-8"), src.read_text("utf-8"))
        self.assertEqual(_mode(token), 0o600)
        self.assertEqual(external.read_text(encoding="utf-8"), "external")
        self.assertEqual(_mode(external), 0o644)

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

    def test_prepare_agy_home_rejects_home_overlap(self) -> None:
        # clean-home == HOME и clean-home — предок HOME: любые файловые операции
        # над таким каталогом разрушительны, _prepare_agy_home обязан отказать.
        for bad in (self.real_home, self.tmp):
            with self.subTest(clean_home=str(bad)):
                with (
                    mock.patch.object(self.srv, "CLEAN_HOME_DIR", bad),
                    mock.patch.object(self.srv, "_AGY_HOME_INITIALIZED", False),
                ):
                    with self.assertRaises(RuntimeError):
                        _ = self.srv._prepare_agy_home()
                self.assertTrue((self.real_home / "Library" / "Keychains").is_dir())
                self.assertEqual(
                    (self.real_home / ".gemini" / "projects.json").read_text(
                        encoding="utf-8"
                    ),
                    '{"projects": {}}',
                )

    def test_prepare_agy_home_rejects_home_overlap_via_symlink(self) -> None:
        alias = self.tmp / "home-alias"
        os.symlink(self.real_home, alias)
        with (
            mock.patch.object(self.srv, "CLEAN_HOME_DIR", alias),
            mock.patch.object(self.srv, "_AGY_HOME_INITIALIZED", False),
        ):
            with self.assertRaises(RuntimeError):
                _ = self.srv._prepare_agy_home()

    def test_prepare_agy_home_rejects_gemini_overlap(self) -> None:
        # clean-home == ~/.gemini или внутри него: цикл очистки канонов удалил бы
        # AGENTS.md/GEMINI.md/hooks.json реального профиля пользователя.
        real_gemini = self.real_home / ".gemini"
        for bad in (real_gemini, real_gemini / "antigravity-cli"):
            with self.subTest(clean_home=str(bad)):
                with (
                    mock.patch.object(self.srv, "CLEAN_HOME_DIR", bad),
                    mock.patch.object(self.srv, "_AGY_HOME_INITIALIZED", False),
                ):
                    with self.assertRaises(RuntimeError):
                        _ = self.srv._prepare_agy_home()
                for rel, body in _SECRET_FILES.items():
                    self.assertEqual(
                        (self.real_home / rel).read_text(encoding="utf-8"), body, rel
                    )
                for base in (real_gemini, real_gemini / "antigravity-cli"):
                    for name in _CANON_NAMES:
                        self.assertEqual(
                            (base / name).read_text(encoding="utf-8"),
                            "x",
                            str(base / name),
                        )

    def test_prepare_agy_home_allows_clean_home_inside_home(self) -> None:
        # Типовой деплой: <clean-home> под рабочей копией внутри HOME — допустим.
        nested = self.real_home / "work" / "runtime" / "agy-home"
        with (
            mock.patch.object(self.srv, "CLEAN_HOME_DIR", nested),
            mock.patch.object(self.srv, "BRAIN_DIR", nested / _CLI_REL / "brain"),
            mock.patch.object(
                self.srv, "CONV_DIR", nested / _CLI_REL / "conversations"
            ),
            mock.patch.object(self.srv, "_AGY_HOME_INITIALIZED", False),
        ):
            self.assertEqual(self.srv._prepare_agy_home(), nested)

    def test_prepare_agy_home_rejects_external_brain_and_conv(self) -> None:
        # AGY_BRIDGE_BRAIN / AGY_BRIDGE_CONVERSATIONS вне <clean-home>: инвариант
        # изоляции нарушен, отказ до любых файловых операций.
        outside = self.tmp / "outside"
        inside_brain = self.clean_home / "custom_brain"
        inside_conv = self.clean_home / "custom_conv"
        cases = (
            ("BRAIN_DIR", outside / "brain", inside_conv),
            ("CONV_DIR", inside_brain, outside / "conv"),
        )
        for which, brain, conv in cases:
            with self.subTest(external=which):
                with (
                    mock.patch.object(self.srv, "BRAIN_DIR", brain),
                    mock.patch.object(self.srv, "CONV_DIR", conv),
                    mock.patch.object(self.srv, "_AGY_HOME_INITIALIZED", False),
                ):
                    with self.assertRaisesRegex(
                        RuntimeError, "BRAIN_DIR/CONV_DIR resolves outside clean-home"
                    ):
                        _ = self.srv._prepare_agy_home()
                self.assertFalse(self.clean_home.exists())
                self.assertFalse(outside.exists())

    def test_prepare_agy_home_rejects_brain_symlinked_outside(self) -> None:
        # Путь лексически внутри <clean-home>, но через симлинк ведёт наружу.
        external_dir = self.tmp / "external_dir"
        external_dir.mkdir()
        self.clean_home.mkdir(parents=True)
        os.symlink(external_dir, self.clean_home / "escape")
        with mock.patch.object(self.srv, "BRAIN_DIR", self.clean_home / "escape"):
            with self.assertRaises(RuntimeError):
                _ = self.srv._prepare_agy_home()
        self.assertEqual(list(external_dir.iterdir()), [])

    def test_ensure_private_dir_rejects_symlink(self) -> None:
        # .gemini -> внешний каталог: ни chmod, ни создание файлов снаружи.
        external_dir = self.tmp / "external_dir"
        external_dir.mkdir(mode=0o755)
        os.chmod(external_dir, 0o755)
        self.clean_home.mkdir(parents=True)
        os.symlink(external_dir, self.gemini)
        with self.assertRaises(RuntimeError):
            _ = self.srv._prepare_agy_home()
        self.assertEqual(_mode(external_dir), 0o755)
        self.assertEqual(list(external_dir.iterdir()), [])
        with self.assertRaises(RuntimeError):
            self.srv._ensure_private_dir(self.gemini)
        self.assertEqual(_mode(external_dir), 0o755)

    def test_ensure_private_dir_rejects_nested_symlink(self) -> None:
        # Вложенный antigravity-cli -> внешний каталог (выход за границы профиля).
        external_dir = self.tmp / "external_dir"
        external_dir.mkdir(mode=0o755)
        os.chmod(external_dir, 0o755)
        self.gemini.mkdir(parents=True)
        os.symlink(external_dir, self.cli)
        with self.assertRaises(RuntimeError):
            _ = self.srv._prepare_agy_home()
        self.assertEqual(_mode(external_dir), 0o755)
        self.assertEqual(list(external_dir.iterdir()), [])

    def test_ensure_private_dir_rejects_path_outside_clean_home(self) -> None:
        outside = self.tmp / "outside"
        self.clean_home.mkdir(parents=True)
        with self.assertRaises(RuntimeError):
            self.srv._ensure_private_dir(outside)
        self.assertFalse(outside.exists())

    def test_ensure_symlink_rejects_parent_symlinked_outside(self) -> None:
        external_dir = self.tmp / "external_dir"
        external_dir.mkdir()
        self.clean_home.mkdir(parents=True)
        os.symlink(external_dir, self.clean_home / "escape")
        with self.assertRaises(RuntimeError):
            self.srv._ensure_symlink(
                self.clean_home / "escape" / "Library", self.real_home / "Library"
            )
        self.assertEqual(list(external_dir.iterdir()), [])

    def test_prepare_agy_home_cleans_nested_hooks_json(self) -> None:
        config = self.gemini / "config"
        config.mkdir(parents=True)
        _ = (config / "hooks.json").write_text('{"hook": 1}', encoding="utf-8")
        (config / "hooks").mkdir()
        _ = (config / "hooks" / "inject.py").write_text("x", encoding="utf-8")
        _ = self.srv._prepare_agy_home()
        self.assertFalse((config / "hooks.json").exists())
        self.assertFalse((config / "hooks").exists())

    def test_hooks_cleanup_does_not_follow_config_symlink(self) -> None:
        external_dir = self.tmp / "external_dir"
        external_dir.mkdir()
        keep = external_dir / "hooks.json"
        _ = keep.write_text("external", encoding="utf-8")
        self.gemini.mkdir(parents=True)
        os.symlink(external_dir, self.gemini / "config")
        _ = self.srv._prepare_agy_home()
        self.assertEqual(keep.read_text(encoding="utf-8"), "external")
        self.assertFalse((self.gemini / "config").exists())


class EnsureSymlinkTests(CleanHomeFixture):
    def test_ensure_symlink_refuses_to_delete_real_dir(self) -> None:
        self.clean_home.mkdir(parents=True)
        dir_path = self.clean_home / "real-dir"
        dir_path.mkdir()
        keep = dir_path / "keep.txt"
        _ = keep.write_text("important", encoding="utf-8")
        target = self.tmp / "target"
        target.mkdir()
        with self.assertRaises(RuntimeError):
            self.srv._ensure_symlink(dir_path, target)
        self.assertTrue(dir_path.is_dir() and not dir_path.is_symlink())
        self.assertEqual(keep.read_text(encoding="utf-8"), "important")

    def test_ensure_symlink_replaces_file_and_broken_symlink(self) -> None:
        self.clean_home.mkdir(parents=True)
        target = self.tmp / "target"
        target.mkdir()
        as_file = self.clean_home / "as-file"
        _ = as_file.write_text("x", encoding="utf-8")
        broken = self.clean_home / "broken"
        os.symlink(self.tmp / "missing", broken)
        for link in (as_file, broken):
            self.srv._ensure_symlink(link, target)
            self.assertEqual(os.readlink(link), str(target))


class LaunchEnvTests(CleanHomeFixture):
    def test_launch_env_values(self) -> None:
        with mock.patch.dict(os.environ, {"AGY_BRIDGE_KEY": "secret"}):
            env = self.srv._launch_env()
        self.assertEqual(env["HOME"], str(self.clean_home))
        self.assertEqual(env["BRIDGE_ZERO_CANON"], "1")
        self.assertEqual(env["BROWSER"], "/usr/bin/false")
        self.assertNotIn("AGY_BRIDGE_KEY", env)
        self.assertTrue((Path(env["HOME"]) / "Library").is_symlink())

    def test_launch_env_preserves_runtime_paths(self) -> None:
        # agy-cli.sh ищет agy.real и allowed-models.txt относительно $HOME; в
        # <clean-home> их нет, поэтому пути пробрасываются явными переменными.
        allowed = str(self.real_home / ".config" / "agy-launch" / "allowed-models.txt")
        base = {"AGY_BRIDGE_KEY": "secret"}
        with mock.patch.dict(os.environ, base):
            for name in ("AGY_BIN", "AGY_ALLOWED_MODELS_FILE"):
                _ = os.environ.pop(name, None)
            env = self.srv._launch_env()
        self.assertEqual(env["HOME"], str(self.clean_home))
        self.assertEqual(env["AGY_BIN"], str(self.srv.AGY_BIN))
        self.assertEqual(env["AGY_ALLOWED_MODELS_FILE"], allowed)
        self.assertEqual(env["BRIDGE_ZERO_CANON"], "1")
        self.assertEqual(env["BROWSER"], "/usr/bin/false")
        self.assertNotIn("AGY_BRIDGE_KEY", env)

    def test_launch_env_keeps_preset_runtime_paths(self) -> None:
        preset = {
            "AGY_BIN": "/opt/custom/agy.real",
            "AGY_ALLOWED_MODELS_FILE": "/opt/custom/allowed-models.txt",
        }
        with mock.patch.dict(os.environ, preset):
            env = self.srv._launch_env()
        self.assertEqual(env["AGY_BIN"], "/opt/custom/agy.real")
        self.assertEqual(
            env["AGY_ALLOWED_MODELS_FILE"], "/opt/custom/allowed-models.txt"
        )

    def test_launch_env_enforces_per_launch_zero_canon(self) -> None:
        _ = self.srv._launch_env()
        for base in (self.clean_home, self.gemini, self.cli):
            for name in _CANON_NAMES:
                _ = (base / name).write_text("late", encoding="utf-8")
        (self.gemini / "config").mkdir()
        _ = (self.gemini / "config" / "hooks.json").write_text("{}", encoding="utf-8")
        _ = self.srv._launch_env()
        for base in (self.clean_home, self.gemini, self.cli):
            for name in _CANON_NAMES:
                self.assertFalse((base / name).exists(), f"{base / name}")
        self.assertFalse((self.gemini / "config" / "hooks.json").exists())

    def test_launch_env_does_not_mutate_os_environ(self) -> None:
        before = os.environ.get("HOME")
        _ = self.srv._launch_env()
        self.assertEqual(os.environ.get("HOME"), before)
        self.assertNotIn("BRIDGE_ZERO_CANON", os.environ)

    def test_launch_env_keeps_other_variables(self) -> None:
        with mock.patch.dict(os.environ, {"HTTPS_PROXY": "http://p:1"}):
            env = self.srv._launch_env()
        self.assertEqual(env["HTTPS_PROXY"], "http://p:1")


class CleanCanonSafetyTests(CleanHomeFixture):
    def _external_canon(self, name: str) -> tuple[Path, list[Path]]:
        external = self.tmp / name
        (external / "antigravity-cli").mkdir(parents=True)
        victims = [external / n for n in _CANON_NAMES]
        victims += [external / "antigravity-cli" / n for n in _CANON_NAMES]
        for victim in victims:
            _ = victim.write_text("real-user-canon", encoding="utf-8")
        return external, victims

    def _assert_untouched(self, victims: list[Path]) -> None:
        for victim in victims:
            self.assertEqual(
                victim.read_text(encoding="utf-8"), "real-user-canon", str(victim)
            )

    def test_symlinked_antigravity_cli_fails_loud(self) -> None:
        _ = self.srv._prepare_agy_home()
        external, victims = self._external_canon("external_dir")
        shutil.rmtree(self.cli)
        self.cli.symlink_to(external / "antigravity-cli")
        with self.assertRaisesRegex(RuntimeError, "cannot be a symlink"):
            self.srv._clean_canon_files(self.clean_home)
        with self.assertRaisesRegex(
            RuntimeError, "antigravity-cli cannot be a symlink"
        ):
            _ = self.srv._launch_env()
        self.assertTrue(self.cli.is_symlink())
        self._assert_untouched(victims)

    def test_symlinked_gemini_fails_loud_without_degraded_launch(self) -> None:
        _ = self.srv._launch_env()
        external, victims = self._external_canon("external_gemini")
        shutil.rmtree(self.gemini)
        self.gemini.symlink_to(external)
        with self.assertRaisesRegex(RuntimeError, "cannot be a symlink"):
            self.srv._clean_canon_files(self.clean_home)
        with self.assertRaisesRegex(RuntimeError, ".gemini cannot be a symlink"):
            _ = self.srv._launch_env()
        with self.assertRaisesRegex(RuntimeError, ".gemini cannot be a symlink"):
            _ = self.srv._prepare_agy_home()
        self.assertTrue(self.gemini.is_symlink())
        self._assert_untouched(victims)

    def test_missing_gemini_after_init_fails_loud(self) -> None:
        _ = self.srv._launch_env()
        shutil.rmtree(self.gemini)
        with self.assertRaisesRegex(RuntimeError, "missing or damaged"):
            _ = self.srv._launch_env()
        self.assertFalse(self.gemini.exists())

    def test_clean_canon_files_config_symlink_is_removed_not_followed(self) -> None:
        _ = self.srv._prepare_agy_home()
        external, victims = self._external_canon("external_cfg")
        config = self.gemini / "config"
        if config.is_symlink() or config.is_file():
            config.unlink()
        elif config.is_dir():
            shutil.rmtree(config)
        config.symlink_to(external)
        self.srv._clean_canon_files(self.clean_home)
        self.assertFalse(config.is_symlink())
        self._assert_untouched(victims)

    def test_clean_canon_files_removes_symlinked_canon_file_only(self) -> None:
        _ = self.srv._prepare_agy_home()
        outside = self.tmp / "outside_AGENTS.md"
        _ = outside.write_text("real", encoding="utf-8")
        (self.cli / "AGENTS.md").symlink_to(outside)
        self.srv._clean_canon_files(self.clean_home)
        self.assertFalse((self.cli / "AGENTS.md").is_symlink())
        self.assertTrue(outside.exists())

    def test_clean_canon_files_concurrent_launch_env_no_filenotfound(self) -> None:
        _ = self.srv._launch_env()
        errors: list[BaseException] = []
        stop = threading.Event()

        def injector() -> None:
            while not stop.is_set():
                for base in (self.clean_home, self.gemini, self.cli):
                    for name in _CANON_NAMES:
                        try:
                            _ = (base / name).write_text("late", encoding="utf-8")
                        except OSError:
                            pass

        def worker() -> None:
            try:
                for _ in range(30):
                    _ = self.srv._launch_env()
            except RuntimeError as exc:
                # Инжектор пишет канон вплотную к пост-проверке: fail-loud
                # Zero-Canon допустим, FileNotFoundError и прочее — нет.
                if "Zero-Canon invariant violated" not in str(exc):
                    errors.append(exc)
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        inj = threading.Thread(target=injector)
        inj.start()
        workers = [threading.Thread(target=worker) for _ in range(10)]
        for th in workers:
            th.start()
        for th in workers:
            th.join()
        stop.set()
        inj.join()
        self.assertEqual(errors, [])

    def test_clean_home_root_symlink_after_init_is_rejected(self) -> None:
        _ = self.srv._launch_env()
        external = self.tmp / "external_home"
        (external / ".gemini" / "antigravity-cli").mkdir(parents=True)
        victims = [external / n for n in _CANON_NAMES]
        victims += [external / ".gemini" / n for n in _CANON_NAMES]
        victims += [external / ".gemini" / "antigravity-cli" / n for n in _CANON_NAMES]
        for victim in victims:
            _ = victim.write_text("real-user-canon", encoding="utf-8")
        # Подмена корня после первой инициализации: clean-home -> внешний каталог.
        shutil.move(str(self.clean_home), str(self.tmp / "moved-away"))
        self.clean_home.symlink_to(external)
        with self.assertRaisesRegex(RuntimeError, "cannot be a symlink"):
            _ = self.srv._launch_env()
        with self.assertRaisesRegex(RuntimeError, "cannot be a symlink"):
            _ = self.srv._prepare_agy_home()
        self.assertTrue(self.clean_home.is_symlink())
        for victim in victims:
            self.assertEqual(
                victim.read_text(encoding="utf-8"), "real-user-canon", str(victim)
            )

    def test_clean_home_path_mutation_after_init_is_rejected(self) -> None:
        _ = self.srv._launch_env()
        other = self.tmp / "ws" / "runtime" / "other-home"
        other.mkdir(parents=True)
        victim = other / "AGENTS.md"
        _ = victim.write_text("keep", encoding="utf-8")
        with mock.patch.object(self.srv, "CLEAN_HOME_DIR", other):
            with self.assertRaisesRegex(RuntimeError, "mutated after initialization"):
                _ = self.srv._launch_env()
        self.assertTrue(victim.exists())

    def test_clean_canon_files_permission_error_fails_loud(self) -> None:
        _ = self.srv._launch_env()
        canon = self.cli / "AGENTS.md"
        _ = canon.write_text("late", encoding="utf-8")
        real_unlink = Path.unlink

        def deny(path: Path, *args: Any, **kwargs: Any) -> None:
            if path.name == "AGENTS.md":
                raise PermissionError(13, "denied", str(path))
            real_unlink(path, *args, **kwargs)

        with mock.patch.object(Path, "unlink", deny):
            with self.assertRaises(PermissionError):
                _ = self.srv._launch_env()
        self.assertTrue(canon.exists())

    def test_remove_canon_hooks_permission_error_fails_loud(self) -> None:
        _ = self.srv._launch_env()
        hooks_dir = self.gemini / "config" / "hooks"
        hooks_dir.mkdir(parents=True)
        _ = (hooks_dir / "inject.py").write_text("x", encoding="utf-8")
        with mock.patch.object(
            self.srv.shutil, "rmtree", side_effect=PermissionError(13, "denied")
        ):
            with self.assertRaises(PermissionError):
                _ = self.srv._launch_env()
        self.assertTrue((hooks_dir / "inject.py").exists())

    def test_unlink_quiet_suppresses_only_enoent(self) -> None:
        self.srv._unlink_quiet(self.tmp / "missing-file")
        with mock.patch.object(Path, "unlink", side_effect=PermissionError(1, "x")):
            with self.assertRaises(PermissionError):
                self.srv._unlink_quiet(self.tmp / "any")

    def test_zero_canon_post_check_detects_surviving_canon(self) -> None:
        _ = self.srv._launch_env()
        _ = (self.cli / "GEMINI.md").write_text("late", encoding="utf-8")
        with mock.patch.object(self.srv, "_unlink_quiet", lambda path: None):
            with self.assertRaisesRegex(RuntimeError, "Zero-Canon invariant violated"):
                self.srv._clean_canon_files(self.clean_home)

    def test_zero_canon_post_check_detects_surviving_hooks(self) -> None:
        _ = self.srv._launch_env()
        config = self.gemini / "config"
        config.mkdir()
        _ = (config / "hooks.json").write_text("{}", encoding="utf-8")
        with mock.patch.object(self.srv, "_unlink_quiet", lambda path: None):
            with self.assertRaisesRegex(RuntimeError, "Zero-Canon invariant violated"):
                self.srv._clean_canon_files(self.clean_home)


class PathsAlignmentTests(unittest.TestCase):
    def _load_with_env(self, **overrides: str) -> Any:
        keys = ("AGY_BRIDGE_CLEAN_HOME", "AGY_BRIDGE_BRAIN", "AGY_BRIDGE_CONVERSATIONS")
        env = {k: "" for k in keys} | overrides
        with mock.patch.dict(os.environ, env):
            return _load_bridge("agy_bridge_server_paths_under_test")

    def test_default_clean_home_under_workspace_runtime(self) -> None:
        mod = self._load_with_env()
        self.assertEqual(
            mod.CLEAN_HOME_DIR, (mod.WORKSPACE / "runtime" / "agy-home").resolve()
        )
        self.assertTrue(mod.CLEAN_HOME_DIR.is_absolute())
        self.assertTrue(mod.BRAIN_DIR.is_absolute())
        self.assertTrue(mod.CONV_DIR.is_absolute())

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
            expected = Path(td).resolve()
            self.assertEqual(mod.CLEAN_HOME_DIR, expected)
            self.assertEqual(
                mod.BRAIN_DIR, expected / ".gemini" / "antigravity-cli" / "brain"
            )
            self.assertEqual(
                mod.CONV_DIR, expected / ".gemini" / "antigravity-cli" / "conversations"
            )

    def test_explicit_brain_and_conv_overrides_win(self) -> None:
        # Оверрайды допустимы только внутри <clean-home> (инвариант изоляции).
        with tempfile.TemporaryDirectory() as td:
            clean_home = Path(td).resolve()
            mod = self._load_with_env(
                AGY_BRIDGE_CLEAN_HOME=td,
                AGY_BRIDGE_BRAIN=str(clean_home / "custom_brain"),
                AGY_BRIDGE_CONVERSATIONS=str(clean_home / "custom_conv"),
            )
            self.assertEqual(mod.BRAIN_DIR, clean_home / "custom_brain")
            self.assertEqual(mod.CONV_DIR, clean_home / "custom_conv")


if __name__ == "__main__":
    _ = unittest.main()
