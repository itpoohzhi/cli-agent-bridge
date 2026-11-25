"""Тесты матрицы классификации доставки канона (AD-002, systemPrompt-only).

Канон доставляется симлинком-якорем ~/.dsh/canon/AGENTS.md, а user-global
~/.dsh/AGENTS.md после миграции должен отсутствовать. Классификация
проверяется через фасад tools/b_guard.check_installed (frozen interfaces);
живой ~/.dsh не затрагивается.
"""

import os
import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

try:
    from tests.test_b_guard import PROFILE_YML, build_snapshot_fs, write_profile  # noqa: F401
except ImportError:  # pytest запускается из корня репо без пакета tests
    from test_b_guard import PROFILE_YML, build_snapshot_fs, write_profile  # noqa: F401

from tools import b_guard

OK_MAXBYTES = 106496
DUP_MAXBYTES = 262144


def _exit_code(result):
    """Код возврата Result; None (нечитаемый канон) трактуется как 2."""
    if result is None:
        return 2
    if isinstance(result, int):
        return result
    return getattr(result, "exit_code", result[0])


def _reasons(result):
    """Список reason-строк Result (для None — пустой список)."""
    if result is None:
        return []
    return getattr(result, "reasons", result[1])


class CanonDeliveryTest(unittest.TestCase):
    """Здоровый снапшот, валидный якорь, отсутствующий user-global."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="canon-delivery-")
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.fs = build_snapshot_fs(pathlib.Path(self.tmpdir))
        self.cwds = tuple(
            (str(name), str(path)) for name, path in self.fs["cwds"].items()
        )
        self.canon = str(self.fs["canon"])
        self.ug_path = os.path.join(self.tmpdir, "dsh-home", "AGENTS.md")
        os.makedirs(os.path.dirname(self.ug_path), exist_ok=True)
        self.anchor_path = self._make_anchor()
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

    def _make_anchor(self, target=None):
        """Якорь ~/.dsh/canon/AGENTS.md: симлинк на канон (или иной target)."""
        anchor = os.path.join(self.tmpdir, "canon-home", "AGENTS.md")
        os.makedirs(os.path.dirname(anchor), exist_ok=True)
        if os.path.lexists(anchor):
            os.unlink(anchor)
        real = os.path.realpath(self.canon) if target is None else target
        os.symlink(real, anchor)
        return anchor

    def _remove_anchor(self):
        if os.path.lexists(self.anchor_path):
            os.unlink(self.anchor_path)

    def _write_bytes(self, path, data):
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def _canon_bytes(self):
        with open(self.canon, "rb") as fh:
            return fh.read()

    def _check(self, maxbytes=OK_MAXBYTES):
        return b_guard.check_installed(maxbytes, self.cwds, self.canon)

    def _assert_rejected(self, result, prefix):
        self.assertEqual(_exit_code(result), 2)
        self.assertEqual(getattr(result, "lower_margin", result[2]), 0)
        reasons = _reasons(result)
        self.assertTrue(any(r.startswith(prefix) for r in reasons), reasons)

    # --- норма: валидный якорь + отсутствующий user-global ---

    def test_valid_anchor_without_user_global_is_ok(self):
        self.assertEqual(_exit_code(self._check()), 0)

    def test_evaluate_duplicate_verdict_passes_through(self):
        # разросшийся артефакт: тот же снапшот, но лимит профиля больше канона
        result = self._check(DUP_MAXBYTES)
        self.assertEqual(_exit_code(result), 2)
        self.assertTrue(any("DUPLICATE_RETURNED" in r for r in _reasons(result)))

    # --- проблемы якоря ~/.dsh/canon/AGENTS.md (fail-closed) ---

    def _anchor_prefix(self):
        return "CANON_LOST anchor %s" % getattr(b_guard, "CANON_ANCHOR_DISPLAY", "~/.dsh/canon/AGENTS.md")

    def test_anchor_missing_is_canon_lost(self):
        self._remove_anchor()
        self._assert_rejected(self._check(), self._anchor_prefix())

    def test_anchor_regular_file_is_canon_lost(self):
        self._remove_anchor()
        self._write_bytes(self.anchor_path, b"plain copy, not a symlink")
        self._assert_rejected(self._check(), self._anchor_prefix())

    def test_anchor_directory_is_canon_lost(self):
        self._remove_anchor()
        os.makedirs(self.anchor_path)
        self._assert_rejected(self._check(), self._anchor_prefix())

    def test_anchor_dangling_symlink_is_canon_lost(self):
        self._make_anchor(target=os.path.join(self.tmpdir, "no-such-target.md"))
        self._assert_rejected(self._check(), self._anchor_prefix())

    def test_anchor_retargeted_symlink_is_canon_lost(self):
        other = os.path.join(self.tmpdir, "other-target.md")
        self._write_bytes(other, b"not the canon")
        self._make_anchor(target=other)
        self._assert_rejected(self._check(), self._anchor_prefix())

    def test_anchor_problem_wins_over_user_global_duplicate(self):
        # сломанный якорь даёт CANON_LOST anchor, даже если дубль вернулся
        self._remove_anchor()
        os.symlink(os.path.realpath(self.canon), self.ug_path)
        self._assert_rejected(self._check(), self._anchor_prefix())

    # --- user-global ~/.dsh/AGENTS.md: дубль вернулся ---

    def test_user_global_symlink_to_canon_is_duplicate(self):
        os.symlink(os.path.realpath(self.canon), self.ug_path)
        self._assert_rejected(self._check(), "DUPLICATE_RETURNED user-global %s" % b_guard.UG_DISPLAY)

    def test_user_global_equal_bytes_is_duplicate(self):
        self._write_bytes(self.ug_path, self._canon_bytes())
        self._assert_rejected(self._check(), "DUPLICATE_RETURNED user-global %s" % b_guard.UG_DISPLAY)

    # --- user-global ~/.dsh/AGENTS.md: сломанное состояние ---

    def test_user_global_changed_bytes_is_canon_lost(self):
        self._write_bytes(self.ug_path, self._canon_bytes() + b"\n# drift\n")
        self._assert_rejected(self._check(), "CANON_LOST user-global %s" % b_guard.UG_DISPLAY)

    def test_user_global_dangling_symlink_is_canon_lost(self):
        os.symlink(os.path.join(self.tmpdir, "no-such-ug.md"), self.ug_path)
        self._assert_rejected(self._check(), "CANON_LOST user-global %s" % b_guard.UG_DISPLAY)

    def test_user_global_retargeted_symlink_is_canon_lost(self):
        other = os.path.join(self.tmpdir, "ug-other.md")
        self._write_bytes(other, b"elsewhere")
        os.symlink(other, self.ug_path)
        self._assert_rejected(self._check(), "CANON_LOST user-global %s" % b_guard.UG_DISPLAY)

    def test_user_global_directory_is_canon_lost(self):
        os.makedirs(self.ug_path)
        res = self._check()
        self._assert_rejected(res, "CANON_LOST user-global %s" % b_guard.UG_DISPLAY)
        self.assertTrue(any("нечитаем" in r for r in _reasons(res)), _reasons(res))

    # --- нечитаемый канон ---

    def test_unreadable_canon_returns_none(self):
        missing = os.path.join(self.tmpdir, "missing-canon.md")
        self.assertIsNone(b_guard.check_installed(OK_MAXBYTES, self.cwds, missing))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
