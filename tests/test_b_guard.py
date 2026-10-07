"""Тесты охранника B (tools/b_guard.py): TM-017 (модель рендера, границы, golden-фикстуры)
и TM-018 (коды выхода, граница 60 000 Б, рост/выход канона из окна, рекомендуемый maxBytes).

Расчётные тесты работают на чистых размерах (снимок zone-F: канон 55 417 Б), без доступа
к боевым файлам. Единственный «живой» тест запускает `main(["--check", ...])` в подпроцессе
на реальных путях и пропускается только если этих путей на машине нет.
"""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import b_guard as bg  # noqa: E402

CANON = 55417  # снимок zone-F (F-704)
CANON_NOW_CEILING = 63600  # потолок «40 000 симв.» ~ 63 600 Б


def project(*items):
    """Проектные файлы одного каталога `.`: (имя, размер, is_canon)."""
    return [bg.FileEntry(n, s, c, ".", None, False) for n, s, c in items]


def snapshot_files(canon=CANON):
    """Проектные файлы четырёх cwd снимка (user-global добавляет evaluate)."""
    return {
        "KB": project(("AGENTS.md", canon, True)),
        "WA": project(("AGENTS.md", 23245, False), ("CLAUDE.md", 478, False)),
        "AB": project(("AGENTS.md", 37520, False), ("CLAUDE.md", 448, False)),
        "DW": [],
    }


def with_ug(files, canon=CANON):
    return [bg.make_user_global(canon)] + list(files)


class TestTm017Model(unittest.TestCase):
    """TM-017: границы окна, классы рендера и golden-фикстуры размеров."""

    def test_tm017_kb_boundary_111177_111176(self):
        """TM-017: KB - при 111 177 обе копии канона (ALL), при 111 176 одна (UG_OMITTED, 55 790 Б)."""
        entries = with_ug(snapshot_files()["KB"])
        full = bg.render_plan(entries, 111177)
        self.assertEqual((full.cls, full.block_bytes, full.canon_copies), (bg.CLASS_ALL, 111177, 2))
        cut = bg.render_plan(entries, 111176)
        self.assertEqual((cut.cls, cut.block_bytes, cut.canon_copies), (bg.CLASS_UG_OMITTED, 55790, 1))
        self.assertEqual(cut.omitted, [bg.UG_DISPLAY])

    def test_tm017_ab_boundary_93760_93759(self):
        """TM-017: AB - при 93 760 всё влезает, при 93 759 user-global отбрасывается (38 372 Б, канон потерян)."""
        entries = with_ug(snapshot_files()["AB"])
        full = bg.render_plan(entries, 93760)
        self.assertEqual((full.cls, full.block_bytes, full.canon_copies), (bg.CLASS_ALL, 93760, 1))
        cut = bg.render_plan(entries, 93759)
        self.assertEqual((cut.cls, cut.block_bytes, cut.canon_copies), (bg.CLASS_UG_OMITTED, 38372, 0))

    def test_tm017_wa_boundary_79515_79514(self):
        """TM-017: WA - при 79 515 всё влезает, при 79 514 user-global отбрасывается (24 127 Б)."""
        entries = with_ug(snapshot_files()["WA"])
        full = bg.render_plan(entries, 79515)
        self.assertEqual((full.cls, full.block_bytes), (bg.CLASS_ALL, 79515))
        cut = bg.render_plan(entries, 79514)
        self.assertEqual((cut.cls, cut.block_bytes, cut.canon_copies), (bg.CLASS_UG_OMITTED, 24127, 0))

    def test_tm017_truncated_and_project_omitted_classes(self):
        """TM-017: классы TRUNCATED (DW 55 500: Y=55 093, блок = бюджет) и PROJECT_OMITTED (AB 30 000: 831 Б, остался CLAUDE.md)."""
        dw = bg.render_plan(with_ug([]), 55500)
        self.assertEqual(dw.cls, bg.CLASS_TRUNCATED)
        self.assertEqual(dw.truncated, (bg.UG_DISPLAY, CANON, 55093))
        self.assertEqual(dw.block_bytes, 55500)
        self.assertEqual(dw.canon_copies, 0)  # усечённый канон - не канон
        ab = bg.render_plan(with_ug(snapshot_files()["AB"]), 30000)
        self.assertEqual((ab.cls, ab.block_bytes, ab.kept), (bg.CLASS_PROJECT_OMITTED, 831, ["CLAUDE.md"]))

    def test_tm017_journal_line_bytes_est_golden(self):
        """TM-017: два набора одной длины (100 симв.) с разным экранированием дают разные journal_line_bytes_est, равные json.dumps."""
        plain = "a" * 100
        quotes = '"' * 100
        newlines = "\n" * 100
        cyr = "я" * 100
        self.assertEqual({len(t) for t in (plain, quotes, newlines, cyr)}, {100})
        golden = {plain: 102, quotes: 202, newlines: 202, cyr: 202}
        for text, expected in golden.items():
            self.assertEqual(bg.journal_line_bytes_est(text), expected)
            self.assertEqual(bg.journal_line_bytes_est(text),
                             len(json.dumps(text, ensure_ascii=False).encode("utf-8")))
        self.assertNotEqual(bg.journal_line_bytes_est(plain), bg.journal_line_bytes_est(quotes))
        # ensure_ascii=False: кириллица считается как UTF-8, а не как \uXXXX (6 Б).
        self.assertLess(bg.journal_line_bytes_est(cyr), len(json.dumps(cyr)))

    def test_tm017_same_directory_duplicates_collapse(self):
        """TM-017: одинаковые файлы в ОДНОМ каталоге схлопываются по содержимому, в разных каталогах - нет (F-314)."""
        a = bg.FileEntry("AGENTS.md", 1000, False, "/p", "same", False)
        b = bg.FileEntry("CLAUDE.md", 1000, False, "/p", "same", False)
        c = bg.FileEntry("sub/AGENTS.md", 1000, False, "/p/sub", "same", False)
        self.assertEqual([e.display for e in bg.dedupe_entries([a, b])], ["AGENTS.md"])
        self.assertEqual([e.display for e in bg.dedupe_entries([a, c])], ["AGENTS.md", "sub/AGENTS.md"])
        # user-global и проектная копия канона - разные каталоги: обе секции остаются.
        kb = bg.render_plan(with_ug(project(("AGENTS.md", CANON, True))), 262144)
        self.assertEqual(kb.canon_copies, 2)
        # Ключ None (содержимое неизвестно) никогда не считается совпадением.
        n1 = bg.FileEntry("AGENTS.md", 5, False, "/p", None, False)
        n2 = bg.FileEntry("CLAUDE.md", 5, False, "/p", None, False)
        self.assertEqual(len(bg.dedupe_entries([n1, n2])), 2)

    def test_tm017_display_paths_change_block_size(self):
        """TM-017: разные display paths дают разный размер блока на байт длины пути; для типичных имён совпадает с 279+32·N+Σ."""
        short = [bg.FileEntry("A.md", 100, False, ".", None, False)]
        long_ = [bg.FileEntry("A" * 14 + ".md", 100, False, ".", None, False)]  # на 13 Б длиннее
        self.assertEqual(bg.render_plan(short, 10**6).block_bytes + 13,
                         bg.render_plan(long_, 10**6).block_bytes)
        for files in snapshot_files().values():
            entries = with_ug(files)
            self.assertEqual(bg.render_plan(entries, 10**6).block_bytes,
                             bg.estimate_block_bytes(len(entries), sum(e.size for e in entries)))

    def test_tm017_collect_chain_symlink_canon_stat_only(self):
        """TM-017: сбор по stat - симлинк на канон помечается is_canon с размером цели; цепочка идёт до .git; отсутствующий cwd не падает."""
        with tempfile.TemporaryDirectory() as tmp:
            canon = Path(tmp) / "canon.md"
            canon.write_bytes(b"x" * 1234)
            repo = Path(tmp) / "repo"
            sub = repo / "sub"
            sub.mkdir(parents=True)
            (repo / ".git").mkdir()
            (repo / "AGENTS.md").write_bytes(b"y" * 10)
            (sub / "AGENTS.md").symlink_to(canon)
            (sub / "CLAUDE.md").write_bytes(b"z" * 7)
            entries, exists = bg.collect_cwd_entries(str(sub), os.path.realpath(str(canon)))
            self.assertTrue(exists)
            self.assertEqual([(e.display, e.size, e.is_canon) for e in entries],
                             [("../AGENTS.md", 10, False), ("AGENTS.md", 1234, True), ("CLAUDE.md", 7, False)])
            self.assertEqual(bg.collect_cwd_entries(str(Path(tmp) / "nope"), "/x"), ([], False))

    def test_tm017_self_test_passes(self):
        """TM-017: встроенный --self-test воспроизводит границы zone-F без расхождений."""
        self.assertEqual(bg.self_test(), [])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(bg.main(["--self-test"]), 0)


class TestTm018Guard(unittest.TestCase):
    """TM-018: коды выхода 0/1/2, граница 60 000 Б, рост канона, рекомендуемый maxBytes."""

    def run_eval(self, canon=CANON, maxbytes=106496, files=None):
        return bg.evaluate(canon, files or snapshot_files(canon), maxbytes, ("KB",))

    def test_tm018_limit_boundary_59999_60000_60001(self):
        """TM-018: граница 60 000 Б строгая - 59 999 и 60 000 проходят, 60 001 нет."""
        self.assertTrue(bg.block_within_limit(59999))
        self.assertTrue(bg.block_within_limit(60000))
        self.assertFalse(bg.block_within_limit(60001))

    def test_tm018_current_snapshot_exit0_margins(self):
        """TM-018: на снимке zone-F при 106 496 запасы 12 736/4 680 (допуск ±64), exit 0, причин нет."""
        res = self.run_eval()
        self.assertEqual(res.exit_code, 0)
        self.assertEqual(res.reasons, [])
        self.assertLessEqual(abs(res.lower_margin - 12736), 64)
        self.assertLessEqual(abs(res.upper_margin - 4680), 64)
        self.assertEqual((res.window_low, res.window_high), (93760, 111176))

    def test_tm018_exit1_low_margin_with_reasons(self):
        """TM-018: maxBytes у нижней границы - запас снизу < 4096, канон цел, exit 1 с причиной LOW_MARGIN_LOWER."""
        res = self.run_eval(maxbytes=95000)
        self.assertEqual(res.exit_code, 1)
        self.assertTrue(any(r.startswith("LOW_MARGIN_LOWER") for r in res.reasons))
        up = self.run_eval(maxbytes=109000)
        self.assertEqual(up.exit_code, 1)
        self.assertTrue(any(r.startswith("LOW_MARGIN_UPPER") for r in up.reasons))

    def test_tm018_canon_growth_to_ceiling_exit_le1(self):
        """TM-018: рост канона до потолка 40 000 симв. (~63 600 Б) при 106 496 - exit <= 1; блок KB > 60 000 даёт REQ003_SIZE_EXCEEDED."""
        res = self.run_eval(canon=CANON_NOW_CEILING)
        self.assertLessEqual(res.exit_code, 1)
        self.assertTrue(any(r.startswith("REQ003_SIZE_EXCEEDED") for r in res.reasons))
        strict = bg.evaluate(CANON_NOW_CEILING, snapshot_files(CANON_NOW_CEILING), 106496, ("KB",), True)
        self.assertEqual(strict.exit_code, 2)

    def test_tm018_canon_out_of_window_exit2(self):
        """TM-018: канон вне окна - слишком большой (CANON_LOST в AB) и слишком малый (DUPLICATE_RETURNED в KB) дают exit 2."""
        big = self.run_eval(canon=70000)
        self.assertEqual(big.exit_code, 2)
        self.assertTrue(any(r.startswith("CANON_LOST cwd=AB") for r in big.reasons))
        small = self.run_eval(canon=45000)
        self.assertEqual(small.exit_code, 2)
        self.assertTrue(any(r.startswith("DUPLICATE_RETURNED cwd=KB") for r in small.reasons))

    def test_tm018_recommended_maxbytes(self):
        """TM-018: рекомендуемый maxBytes - наибольшее кратное 4 КиБ с запасом >= 4096 с обеих сторон: на снимке 106 496."""
        res = self.run_eval()
        self.assertEqual(res.recommended, 106496)
        self.assertEqual(res.recommended % 4096, 0)
        self.assertGreaterEqual(res.recommended - res.window_low, 4096)
        self.assertGreaterEqual(res.window_high - res.recommended, 4096)
        self.assertIsNone(bg.recommend_maxbytes(100, 50))  # пустое окно
        self.assertEqual(bg.recommend_maxbytes(100, 5000), 2550)  # нет кратного - середина

    def test_tm018_profiles_not_implemented(self):
        """TM-018: --profiles в dev-копии не реализован - понятное сообщение и exit 2, профили не читаются."""
        err = io.StringIO()
        with redirect_stderr(err):
            code = bg.main(["--profiles"])
        self.assertEqual(code, 2)
        self.assertIn("not implemented in dev copy", err.getvalue())

    def test_tm018_check_missing_cwd_does_not_fail(self):
        """TM-018: несуществующий cwd отмечается «cwd отсутствует», проверка не падает (только канон в запросе)."""
        with tempfile.TemporaryDirectory() as tmp:
            canon = Path(tmp) / "AGENTS.md"
            canon.write_bytes(b"c" * 1000)
            out = io.StringIO()
            with redirect_stdout(out):
                code = bg.main(["--check", "--maxbytes", "106496", "--canon", str(canon),
                                "--cwd", str(Path(tmp) / "absent")])
            self.assertIn("cwd отсутствует", out.getvalue())
            self.assertIn("mode=PLANNED", out.getvalue())
            self.assertIn(code, (0, 1))

    def test_tm018_live_check_subprocess(self):
        """TM-018: боевые размеры - `main(["--check","--maxbytes","106496"])` в подпроцессе даёт exit 0 (пропуск только без боевых путей)."""
        needed = [bg.CANON_PATH, bg.KB_CWD, bg.WA_CWD, bg.AB_CWD]
        missing = [p for p in needed if not os.path.exists(p)]
        if missing:
            self.skipTest("нет боевых путей на машине: %s" % missing)
        code = ("import sys; sys.path.insert(0, %r); import b_guard; "
                "sys.exit(b_guard.main(['--check', '--maxbytes', '106496']))" % str(ROOT / "tools"))
        proc = subprocess.run(["/usr/bin/python3", "-c", code], stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        text = proc.stdout.decode("utf-8", "replace")
        self.assertEqual(proc.returncode, 0, text)
        self.assertIn("lower_margin=", text)
        self.assertIn("mode=PLANNED", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
