"""Эквивалентность --profiles (run_profiles) и check_installed.

Контракт: run_profiles вызывает check_installed для каждого профиля,
пробрасывает exit_code 0/1/2 и печатает каждую reason через _say
в формате "reason: %s" — вердикты CLI и runtime обязаны совпадать.
"""

import os
import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

try:
    from tests.test_b_guard import PROFILE_YML, build_snapshot_fs, write_profile
except ImportError:  # pytest запускается из корня репо без пакета tests
    from test_b_guard import PROFILE_YML, build_snapshot_fs, write_profile

from tools import b_guard

OK_MAXBYTES = 106496
DUP_MAXBYTES = 262144


def _exit_code(result):
    """Код возврата Result/int; None (нечитаемый канон) трактуется как 2."""
    if result is None:
        return 2
    if isinstance(result, int):
        return result
    return getattr(result, "exit_code", result[0])


class ProfilesEquivTest(unittest.TestCase):
    """Один снапшот -> вердикты check_installed и run_profiles совпадают."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="profiles-equiv-")
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.fs = build_snapshot_fs(pathlib.Path(self.tmpdir))
        self.cwds = tuple(
            (str(name), str(path)) for name, path in self.fs["cwds"].items()
        )
        self.canon = str(self.fs["canon"])
        self.ug_path = os.path.join(self.tmpdir, "dsh-home", "AGENTS.md")
        os.makedirs(os.path.dirname(self.ug_path), exist_ok=True)
        self.anchor_path = self._make_anchor()
        self.profiles_dir = os.path.join(self.tmpdir, "profiles")
        os.makedirs(self.profiles_dir, exist_ok=True)
        self._patch_globals()

    def _patch_globals(self):
        """Подменяет патч-константы b_guard на изолированные пути снапшота."""
        cwd_map = dict(self.cwds)
        patches = [
            mock.patch.object(b_guard, "UG_PATH", self.ug_path),
            mock.patch.object(b_guard, "CANON_ANCHOR_PATH", self.anchor_path, create=True),
            mock.patch.object(b_guard, "KB_CWD", str(self.fs["cwds"]["KB"])),
            mock.patch.object(b_guard, "DEFAULT_CWDS", self.cwds),
            mock.patch.dict(os.environ, {}, clear=True),
        ]
        for key, attr in (("WA", "WA_CWD"), ("AB", "AB_CWD"), ("DW", "DW_CWD")):
            if key in cwd_map:
                patches.append(mock.patch.object(b_guard, attr, cwd_map[key]))
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def _make_anchor(self):
        """Якорь ~/.dsh/canon/AGENTS.md: симлинк на канон."""
        anchor = os.path.join(self.tmpdir, "canon-home", "AGENTS.md")
        os.makedirs(os.path.dirname(anchor), exist_ok=True)
        if os.path.lexists(anchor):
            os.unlink(anchor)
        os.symlink(os.path.realpath(self.canon), anchor)
        return anchor

    def _write_profile(self, maxbytes):
        """Записывает профиль preset-standard с заданным maxBytes."""
        try:
            write_profile(self.profiles_dir, "preset-standard", maxbytes)
            return
        except TypeError:
            pass
        try:
            write_profile(self.profiles_dir, maxbytes)
            return
        except TypeError:
            pass
        path = os.path.join(self.profiles_dir, "preset-standard.yml")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(PROFILE_YML % maxbytes)

    def _both(self, maxbytes):
        """Возвращает (код check_installed, код run_profiles, вывод _say)."""
        self._write_profile(maxbytes)
        said = []
        with mock.patch.object(b_guard, "_say", said.append):
            result = b_guard.check_installed(maxbytes, self.cwds, self.canon)
            cli_code = _exit_code(result)
            run = b_guard.run_profiles(self.profiles_dir, self.cwds, self.canon)
            profile_code = _exit_code(run)
        return cli_code, profile_code, said

    @staticmethod
    def _reason_lines(said, needle):
        """Строки вывода run_profiles вида "reason: ...", содержащие needle."""
        return [e for e in said if e.startswith("reason: ") and needle in e]

    def test_ok_verdicts_match(self):
        cli_code, profile_code, _said = self._both(OK_MAXBYTES)
        self.assertEqual((cli_code, profile_code), (0, 0))

    def test_duplicate_verdicts_match(self):
        # дубль вернулся: user-global снова симлинк на канон
        os.symlink(os.path.realpath(self.canon), self.ug_path)
        cli_code, profile_code, said = self._both(OK_MAXBYTES)
        self.assertEqual((cli_code, profile_code), (2, 2))
        self.assertTrue(self._reason_lines(said, "DUPLICATE_RETURNED user-global"), said)

    def test_anchor_lost_verdicts_match(self):
        os.unlink(self.anchor_path)
        cli_code, profile_code, said = self._both(OK_MAXBYTES)
        self.assertEqual((cli_code, profile_code), (2, 2))
        self.assertTrue(self._reason_lines(said, "CANON_LOST anchor"), said)

    def test_grown_artifact_verdicts_match(self):
        # разросшийся артефакт: лимит профиля больше канона -> DUPLICATE_RETURNED
        cli_code, profile_code, said = self._both(DUP_MAXBYTES)
        self.assertEqual((cli_code, profile_code), (2, 2))
        self.assertTrue(self._reason_lines(said, "DUPLICATE_RETURNED"), said)

    def test_unreadable_canon_verdicts_match(self):
        # check_installed -> None, run_profiles обязан вернуть 2 (CANON_LOST)
        self._write_profile(OK_MAXBYTES)
        missing = os.path.join(self.tmpdir, "missing-canon.md")
        self.assertIsNone(b_guard.check_installed(OK_MAXBYTES, self.cwds, missing))
        with mock.patch.object(b_guard, "_say", lambda *args, **kwargs: None):
            code = _exit_code(b_guard.run_profiles(self.profiles_dir, self.cwds, missing))
        self.assertEqual(code, 2)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
