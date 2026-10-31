"""Тесты охранника B (tools/b_guard.py): TM-017 (модель рендера, границы, golden-фикстуры)
и TM-018 (коды выхода, граница предела блока, рост/выход канона из окна, рекомендуемый maxBytes).
Предел блока (ADR 0015) - параметр `limit`/переменная `BRIDGE_INSTR_LIMIT`, умолчание 100 000 Б;
граничные сценарии 60 000 Б (прежний предел) задаются явно.

Расчётные тесты работают на чистых размерах (снимок zone-F: канон 55 417 Б), без доступа
к боевым файлам. CLI-тесты (RW-003/RW-004/RW-002) строят снимок из временных файлов и патчат
пути по умолчанию. Единственный «живой» тест запускает `main(["--check", ...])` в подпроцессе
на реальных путях и пропускается только если этих путей на машине нет.
"""

import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import b_guard as bg  # noqa: E402

CANON = 55417  # снимок zone-F (F-704)
CANON_NOW_CEILING = 63600  # потолок «40 000 симв.» ~ 63 600 Б
LEGACY_LIMIT = 60000  # прежний зашитый предел: граничные сценарии задают его явно
LIMIT_ENV = ("BRIDGE_INSTR_LIMIT", "DROID_DSH_BRIDGE_INSTR_LIMIT")


def clean_env(**extra):
    """Окружение без переменных предела блока плюс `extra` (для mock.patch.dict(..., clear=False))."""
    env = {k: v for k, v in os.environ.items() if k not in LIMIT_ENV}
    env.update(extra)
    return env


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


def body_text(size, ch="a", line=120):
    """ASCII-текст ровно `size` Б со строками по `line` символов (переводы строк экранируются в JSON)."""
    if not line:
        return ch * size
    chunk = ch * (line - 1) + "\n"
    return (chunk * (size // line + 1))[:size]


def build_snapshot_fs(root, canon=CANON, canon_line=120):
    """Снимок zone-F на временных файлах: канон, KB (симлинк на канон), WA, AB, DW; возвращает пути."""
    ctx = root / "ctx"
    ctx.mkdir()
    canon_path = ctx / "AGENTS.md"
    canon_path.write_text(body_text(canon, "c", canon_line), encoding="utf-8")
    cwds = {}
    for label in ("KB", "WA", "AB", "DW"):
        d = root / label.lower()
        d.mkdir()
        (d / ".git").mkdir()
        cwds[label] = d
    (cwds["KB"] / "AGENTS.md").symlink_to(canon_path)
    (cwds["WA"] / "AGENTS.md").write_text(body_text(23245, "w"), encoding="utf-8")
    (cwds["WA"] / "CLAUDE.md").write_text(body_text(478, "v"), encoding="utf-8")
    (cwds["AB"] / "AGENTS.md").write_text(body_text(37520, "a"), encoding="utf-8")
    (cwds["AB"] / "CLAUDE.md").write_text(body_text(448, "b"), encoding="utf-8")
    return {"canon": canon_path, "cwds": cwds}


def run_cli_snapshot(fs, argv, env=None):
    """`bg.main` на снимке: пути по умолчанию и KB-метка REQ-003 патчатся на временные каталоги."""
    cwds = fs["cwds"]
    default = tuple((label, str(cwds[label])) for label in ("KB", "WA", "AB", "DW"))
    out = io.StringIO()
    with (
        mock.patch.dict(os.environ, clean_env(**(env or {})), clear=True),
        mock.patch.object(bg, "KB_CWD", str(cwds["KB"])),
        mock.patch.object(bg, "DEFAULT_CWDS", default),
    ):
        with redirect_stdout(out), redirect_stderr(out):
            code = bg.main(list(argv) + ["--canon", str(fs["canon"])])
    return code, out.getvalue()


# Эталонная сериализация строки журнала: написана вручную, независимо от b_guard (golden).
GOLDEN_HEAD = (
    "<system-reminder>\nThe following workspace instructions may be relevant to your work. "
    "Use them as guidance when applicable. More specific instructions take precedence over "
    "broader ones. They do not override system, developer, or direct user instructions.\n\n"
)


def golden_journal_line(sections, maxbytes, marker=""):
    """Эталон: block = head + [marker\\n\\n] + секции + \\n + </system-reminder>; событие - JSON без пробелов + \\n."""
    parts = ["Instructions from: %s\n\n%s" % (d, t) for d, t in sections]
    block = (
        GOLDEN_HEAD
        + (marker + "\n\n" if marker else "")
        + "\n\n".join(parts)
        + "\n</system-reminder>"
    )
    identity = (
        '{"projectRoot":"","projectRootMarkers":[".git"],"maxBytes":%d,"maxSourceBytes":1048576,'
        '"instructionFileCandidates":["AGENTS.md","CLAUDE.md"],'
        '"localInstructionFileCandidates":["AGENTS.local.md","CLAUDE.local.md"]}'
        % maxbytes
    )
    changes = []
    for d, t in sections:
        scope_dir, _, name = d.rpartition("/")
        if d == "~/.dsh/AGENTS.md":
            scope_dir = "user-global"
        changes.append(
            {
                "action": "set",
                "scope": (scope_dir or ".") + "\u0000" + name,
                "path": d,
                "digest": hashlib.sha1(t.encode("utf-8")).hexdigest(),
            }
        )
    event = {
        "type": "user/message",
        "seq": 10,
        "time": 1791393991696,
        "data": {
            "content": [{"type": "text", "text": block}],
            "source": {
                "kind": "agent-instructions",
                "form": "instructions",
                "baseline": True,
                "baselineIdentity": identity,
                "changes": changes,
            },
            "role": "user",
            "id": "c3321a3c-6a0a-4d8e-8137-1dfd672f33fe",
        },
        "surfaceOp": "append",
    }
    return block, json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"


class TestTm017Model(unittest.TestCase):
    """TM-017: границы окна, классы рендера и golden-фикстуры размеров."""

    def test_tm017_kb_boundary_111177_111176(self):
        """TM-017: KB - при 111 177 обе копии канона (ALL), при 111 176 одна (UG_OMITTED, 55 790 Б)."""
        entries = with_ug(snapshot_files()["KB"])
        full = bg.render_plan(entries, 111177)
        self.assertEqual(
            (full.cls, full.block_bytes, full.canon_copies), (bg.CLASS_ALL, 111177, 2)
        )
        cut = bg.render_plan(entries, 111176)
        self.assertEqual(
            (cut.cls, cut.block_bytes, cut.canon_copies),
            (bg.CLASS_UG_OMITTED, 55790, 1),
        )
        self.assertEqual(cut.omitted, [bg.UG_DISPLAY])

    def test_tm017_ab_boundary_93760_93759(self):
        """TM-017: AB - при 93 760 всё влезает, при 93 759 user-global отбрасывается (38 372 Б, канон потерян)."""
        entries = with_ug(snapshot_files()["AB"])
        full = bg.render_plan(entries, 93760)
        self.assertEqual(
            (full.cls, full.block_bytes, full.canon_copies), (bg.CLASS_ALL, 93760, 1)
        )
        cut = bg.render_plan(entries, 93759)
        self.assertEqual(
            (cut.cls, cut.block_bytes, cut.canon_copies),
            (bg.CLASS_UG_OMITTED, 38372, 0),
        )

    def test_tm017_wa_boundary_79515_79514(self):
        """TM-017: WA - при 79 515 всё влезает, при 79 514 user-global отбрасывается (24 127 Б)."""
        entries = with_ug(snapshot_files()["WA"])
        full = bg.render_plan(entries, 79515)
        self.assertEqual((full.cls, full.block_bytes), (bg.CLASS_ALL, 79515))
        cut = bg.render_plan(entries, 79514)
        self.assertEqual(
            (cut.cls, cut.block_bytes, cut.canon_copies),
            (bg.CLASS_UG_OMITTED, 24127, 0),
        )

    def test_tm017_truncated_and_project_omitted_classes(self):
        """TM-017: классы TRUNCATED (DW 55 500: Y=55 093, блок = бюджет) и PROJECT_OMITTED (AB 30 000: 831 Б, остался CLAUDE.md)."""
        dw = bg.render_plan(with_ug([]), 55500)
        self.assertEqual(dw.cls, bg.CLASS_TRUNCATED)
        self.assertEqual(dw.truncated, (bg.UG_DISPLAY, CANON, 55093))
        self.assertEqual(dw.block_bytes, 55500)
        self.assertEqual(dw.canon_copies, 0)  # усечённый канон - не канон
        ab = bg.render_plan(with_ug(snapshot_files()["AB"]), 30000)
        self.assertEqual(
            (ab.cls, ab.block_bytes, ab.kept),
            (bg.CLASS_PROJECT_OMITTED, 831, ["CLAUDE.md"]),
        )

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
            self.assertEqual(
                bg.journal_line_bytes_est(text),
                len(json.dumps(text, ensure_ascii=False).encode("utf-8")),
            )
        self.assertNotEqual(
            bg.journal_line_bytes_est(plain), bg.journal_line_bytes_est(quotes)
        )
        # ensure_ascii=False: кириллица считается как UTF-8, а не как \uXXXX (6 Б).
        self.assertLess(bg.journal_line_bytes_est(cyr), len(json.dumps(cyr)))

    def test_tm017_same_directory_duplicates_collapse(self):
        """TM-017: одинаковые файлы в ОДНОМ каталоге схлопываются по содержимому, в разных каталогах - нет (F-314)."""
        a = bg.FileEntry("AGENTS.md", 1000, False, "/p", "same", False)
        b = bg.FileEntry("CLAUDE.md", 1000, False, "/p", "same", False)
        c = bg.FileEntry("sub/AGENTS.md", 1000, False, "/p/sub", "same", False)
        self.assertEqual([e.display for e in bg.dedupe_entries([a, b])], ["AGENTS.md"])
        self.assertEqual(
            [e.display for e in bg.dedupe_entries([a, c])],
            ["AGENTS.md", "sub/AGENTS.md"],
        )
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
        long_ = [
            bg.FileEntry("A" * 14 + ".md", 100, False, ".", None, False)
        ]  # на 13 Б длиннее
        self.assertEqual(
            bg.render_plan(short, 10**6).block_bytes + 13,
            bg.render_plan(long_, 10**6).block_bytes,
        )
        for files in snapshot_files().values():
            entries = with_ug(files)
            self.assertEqual(
                bg.render_plan(entries, 10**6).block_bytes,
                bg.estimate_block_bytes(len(entries), sum(e.size for e in entries)),
            )

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
            entries, exists = bg.collect_cwd_entries(
                str(sub), os.path.realpath(str(canon))
            )
            self.assertTrue(exists)
            self.assertEqual(
                [(e.display, e.size, e.is_canon) for e in entries],
                [
                    ("../AGENTS.md", 10, False),
                    ("AGENTS.md", 1234, True),
                    ("CLAUDE.md", 7, False),
                ],
            )
            self.assertEqual(
                bg.collect_cwd_entries(str(Path(tmp) / "nope"), "/x"), ([], False)
            )

    def test_tm017_self_test_passes(self):
        """TM-017: встроенный --self-test воспроизводит границы zone-F без расхождений."""
        self.assertEqual(bg.self_test(), [])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(bg.main(["--self-test"]), 0)


class TestRw003ContentKeyAndExactLine(unittest.TestCase):
    """RW-003: ключ содержимого вместо realpath и точный расчёт строки журнала."""

    def test_rw003_identical_content_two_files_collapse(self):
        """RW-003: два РАЗНЫХ файла с одинаковым содержимым в одном каталоге схлопываются в одну секцию; ключ - sha256."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            (repo / ".git").mkdir()
            data = ("одинаковое содержимое\n" * 40).encode("utf-8")
            (repo / "AGENTS.md").write_bytes(data)
            (repo / "CLAUDE.md").write_bytes(data)
            entries, ok = bg.collect_cwd_entries(str(repo), "/nonexistent-canon")
            self.assertTrue(ok)
            self.assertEqual(len(entries), 2)
            self.assertEqual(
                {e.content_key for e in entries}, {hashlib.sha256(data).hexdigest()}
            )
            kept = bg.dedupe_entries(entries)
            self.assertEqual([e.display for e in kept], ["AGENTS.md"])
            one = bg.render_plan(kept, 10**6)
            self.assertEqual(one.kept, ["AGENTS.md"])
            self.assertEqual(
                one.block_bytes,
                bg.FRAME_BASE + bg.section_bytes("AGENTS.md", len(data)),
            )

    def test_rw003_same_file_two_names_and_different_content(self):
        """RW-003: один файл под двумя именами схлопывается; файлы с разным содержимым - нет."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            (repo / ".git").mkdir()
            (repo / "AGENTS.md").write_bytes(b"x" * 50)
            (repo / "CLAUDE.md").symlink_to(repo / "AGENTS.md")
            entries, _ = bg.collect_cwd_entries(str(repo), "/nonexistent-canon")
            self.assertEqual(len(bg.dedupe_entries(entries)), 1)
            (repo / "CLAUDE.md").unlink()
            (repo / "CLAUDE.md").write_bytes(
                b"y" * 50
            )  # тот же размер, другое содержимое
            entries, _ = bg.collect_cwd_entries(str(repo), "/nonexistent-canon")
            self.assertEqual(len(bg.dedupe_entries(entries)), 2)

    def test_rw003_exact_line_golden_quotes_newlines_long_path(self):
        """RW-003: содержимое с кавычками, переводами строк, обратным слешем, кириллицей и длинный display path -
        прогноз строки журнала равен длине эталонной сериализации, а не константной надбавке."""
        long_dir = "/".join(["очень-длинный-каталог-%02d" % i for i in range(6)])
        displays = ["../" + long_dir + "/AGENTS.md", "sub/CLAUDE.md"]
        texts = [
            'Строка "в кавычках"\nвторая\tстрока с \\ слешем\n' * 30,
            'b"b\n' * 200,
        ]
        sections = list(zip(displays, texts))
        block, line = golden_journal_line(sections, 106496)
        got = bg.exact_journal_line_bytes(sections, 106496)
        self.assertEqual(got, len(line.encode("utf-8")))
        self.assertEqual(bg.render_block_text(sections), block)
        # Модель размера блока совпадает с реальным рендером.
        entries = [
            bg.FileEntry(d, len(t.encode("utf-8")), False, ".", None, False)
            for d, t in sections
        ]
        self.assertEqual(len(block.encode("utf-8")), bg._block(entries, ""))
        # Это не «блок + константа»: экранирование и пути дают другое число.
        self.assertNotEqual(got, len(block.encode("utf-8")) + 1225)
        # Тот же набор с коротким путём дешевле ровно на прирост путей в заголовке/path/scope.
        short = bg.exact_journal_line_bytes(
            [("a/AGENTS.md", texts[0]), sections[1]], 106496
        )
        self.assertLess(short, got)

    def test_rw003_exact_line_with_marker(self):
        """RW-003: метка бюджета входит в блок и строку (UG_OMITTED)."""
        marker = bg.marker_text(106496, [bg.UG_DISPLAY], None)
        sections = [("AGENTS.md", 'тело\n"q"\n' * 10)]
        block, line = golden_journal_line(sections, 106496, marker)
        self.assertEqual(
            bg.exact_journal_line_bytes(sections, 106496, marker),
            len(line.encode("utf-8")),
        )
        self.assertEqual(
            len(block.encode("utf-8")),
            bg._block(
                [bg.FileEntry("AGENTS.md", len(sections[0][1].encode("utf-8")))], marker
            ),
        )

    def test_rw003_evaluate_uses_exact_line_when_texts_known(self):
        """RW-003: evaluate при известных текстах считает строку журнала точно (exact), иначе - оценкой по размерам."""
        canon_text = body_text(55000, "c")
        canon_size = len(canon_text.encode("utf-8"))
        files = {"KB": [bg.FileEntry("AGENTS.md", canon_size, True, "/k", "h", False)]}
        texts = {"KB": {"AGENTS.md": canon_text}}
        res = bg.evaluate(
            canon_size, files, 106496, ("KB",), texts=texts, canon_text=canon_text
        )
        marker = bg.marker_text(106496, [bg.UG_DISPLAY], None)
        want = bg.exact_journal_line_bytes([("AGENTS.md", canon_text)], 106496, marker)
        self.assertEqual(res.line_estimates["KB"], (want, True))
        est = bg.evaluate(canon_size, files, 106496, ("KB",))
        self.assertFalse(est.line_estimates["KB"][1])
        # Оценка по размерам - тот же порядок величины, что и точный расчёт (запасной вариант).
        self.assertLess(abs(est.line_estimates["KB"][0] - want), 0.05 * want)


class TestRw004StrictCli(unittest.TestCase):
    """RW-004: strict_req003 включён в рабочем CLI, граница предела блока строгая."""

    def test_rw004_block_boundary_reason_basis_block(self):
        """RW-004: причина basis=block - при блоке KB предел + 1 (strict: exit 2), но не при ровно пределе
        (строка журнала при этом всё равно длиннее блока на обёртку - её граница проверяется в CLI-тесте ниже).
        Проверяется и умолчание 100 000, и явный прежний предел 60 000."""
        marker = bg.marker_text(106496, [bg.UG_DISPLAY], None)
        fixed = (
            bg.FRAME_BASE
            + bg.section_bytes("AGENTS.md", 0)
            + len(marker.encode("utf-8"))
            + bg.MARKER_TAIL_BYTES
        )

        def run(block, limit=None):
            size = block - fixed
            files = {"KB": [bg.FileEntry("AGENTS.md", size, True, "/k", "h", False)]}
            res = bg.evaluate(
                size, files, 106496, ("KB",), strict_req003=True, limit=limit
            )
            self.assertEqual(res.renders["KB"].block_bytes, block)
            return res

        for limit, bound in ((None, bg.BLOCK_LIMIT), (LEGACY_LIMIT, LEGACY_LIMIT)):
            self.assertEqual(
                [r for r in run(bound, limit).reasons if "basis=block" in r], []
            )
            over = run(bound + 1, limit)
            self.assertTrue(
                [r for r in over.reasons if "basis=block" in r], over.reasons
            )
            self.assertIn("limit=%d" % bound, " ".join(over.reasons))
            self.assertEqual(over.exit_code, 2)

    def _line_boundary(self, limit, env, maxbytes=106496):
        """CLI на временных файлах: строка журнала ровно `limit` Б не даёт REQ003_SIZE_EXCEEDED
        (exit 1: запас строки 0 < 2048), `limit` + 1 - REQ003_SIZE_EXCEEDED и exit 2."""
        marker = bg.marker_text(maxbytes, [bg.UG_DISPLAY], None)
        base = bg.exact_journal_line_bytes([("AGENTS.md", "")], maxbytes, marker)
        with tempfile.TemporaryDirectory() as tmp:
            fs = build_snapshot_fs(Path(tmp), canon=limit - base, canon_line=0)
            code, text = run_cli_snapshot(
                fs, ["--check", "--maxbytes", str(maxbytes)], env
            )
            self.assertIn("line_est=%d" % limit, text)
            self.assertIn("block_limit=%d" % limit, text)
            self.assertNotIn("REQ003_SIZE_EXCEEDED", text)
            self.assertEqual(code, 1, text)
        with tempfile.TemporaryDirectory() as tmp:
            fs = build_snapshot_fs(Path(tmp), canon=limit + 1 - base, canon_line=0)
            code, text = run_cli_snapshot(
                fs, ["--check", "--maxbytes", str(maxbytes)], env
            )
            self.assertIn("line_est=%d" % (limit + 1), text)
            self.assertIn("REQ003_SIZE_EXCEEDED cwd=KB", text)
            self.assertEqual(code, 2, text)

    def test_rw004_cli_line_boundary_default_100000(self):
        """RW-004/ADR 0015: без переменных окружения граница строки журнала - 100 000 / 100 001."""
        self._line_boundary(bg.BLOCK_LIMIT, None, 170000)  # канон ~99 КБ: окно [137 316..198 288]

    def test_rw004_cli_line_boundary_legacy_60000_via_env(self):
        """RW-004: BRIDGE_INSTR_LIMIT=60000 возвращает прежнюю границу 60 000 / 60 001 (предел не зашит)."""
        self._line_boundary(LEGACY_LIMIT, {"BRIDGE_INSTR_LIMIT": "60000"})

    def test_rw004_snapshot_cli_exit0(self):
        """RW-004: снимок zone-F на временных файлах при 106 496 - exit 0 (одна копия канона, REQ-003 в норме)."""
        with tempfile.TemporaryDirectory() as tmp:
            fs = build_snapshot_fs(Path(tmp))
            code, text = run_cli_snapshot(fs, ["--check", "--maxbytes", "106496"])
            self.assertEqual(code, 0, text)
            self.assertIn("line_mode=exact", text)


PROFILE_YML = """# Your patch layer
# (в) agent-instructions.maxBytes: 65536 -> 999 (комментарий, не значение)
- id: preset-minimal
  config:
    plugins:
      - id: agent-instructions
        config:
          maxBytes: 1
- id: preset-standard
  name: '@deepseek-ai/dsh-agent-preset'
  config:
    id: standard
    plugins:
      - id: persona
        config:
          prefix: x
      - id: agent-instructions
        name: '@deepseek-ai/dsh-agent-instructions'
        config:
          maxBytes: %d
      - id: tool-bash
- id: other
  config:
    maxBytes: 7
"""


def write_profile(root, name, maxbytes, text=None):
    d = Path(root) / name
    d.mkdir(parents=True)
    (d / "cordis.patch.yml").write_text(
        text if text is not None else PROFILE_YML % maxbytes, encoding="utf-8"
    )


class TestRw002Profiles(unittest.TestCase):
    """RW-002 (b_guard): режим --profiles читает установленные профили (read-only) и проверяет их maxBytes."""

    def test_rw002_parse_maxbytes_preset_standard_only(self):
        """RW-002: maxBytes берётся из agent-instructions внутри preset-standard, комментарии и другие пресеты игнорируются."""
        self.assertEqual(bg.parse_profile_maxbytes(PROFILE_YML % 106496), 106496)
        self.assertIsNone(bg.parse_profile_maxbytes("[]\n"))

    def test_rw002_profile_106496_exit0(self):
        """RW-002: профиль с maxBytes=106496 на снимке - exit 0."""
        with tempfile.TemporaryDirectory() as tmp:
            fs = build_snapshot_fs(Path(tmp))
            write_profile(Path(tmp) / "profiles", "web", 106496)
            code, text = run_cli_snapshot(
                fs, ["--profiles", "--profiles-dir", str(Path(tmp) / "profiles")]
            )
            self.assertEqual(code, 0, text)
            self.assertIn("profile=web", text)
            self.assertIn("maxBytes=106496", text)

    def test_rw002_profile_262144_duplicate_exit2(self):
        """RW-002: профиль с maxBytes=262144 - канон возвращается дважды, DUPLICATE_RETURNED и exit 2."""
        with tempfile.TemporaryDirectory() as tmp:
            fs = build_snapshot_fs(Path(tmp))
            write_profile(Path(tmp) / "profiles", "web", 262144)
            code, text = run_cli_snapshot(
                fs, ["--profiles", "--profiles-dir", str(Path(tmp) / "profiles")]
            )
            self.assertEqual(code, 2, text)
            self.assertIn("DUPLICATE_RETURNED cwd=KB", text)

    def test_rw002_worst_profile_wins_and_bak_skipped(self):
        """RW-002: несколько профилей - итог по худшему; каталоги резервных копий (.bak) пропускаются."""
        with tempfile.TemporaryDirectory() as tmp:
            fs = build_snapshot_fs(Path(tmp))
            prof = Path(tmp) / "profiles"
            write_profile(prof, "desktop", 106496)
            write_profile(prof, "web", 262144)
            write_profile(prof, "web.bak-1", 106496)
            code, text = run_cli_snapshot(
                fs, ["--profiles", "--profiles-dir", str(prof)]
            )
            self.assertEqual(code, 2, text)
            self.assertIn("profile=desktop", text)
            self.assertNotIn("web.bak", text)

    def test_rw002_missing_dir_or_maxbytes_exit2(self):
        """RW-002: нет каталога профилей / нет maxBytes - понятное сообщение и exit 2."""
        with tempfile.TemporaryDirectory() as tmp:
            fs = build_snapshot_fs(Path(tmp))
            code, text = run_cli_snapshot(
                fs, ["--profiles", "--profiles-dir", str(Path(tmp) / "absent")]
            )
            self.assertEqual(code, 2)
            self.assertIn("профили не найдены", text)
            write_profile(Path(tmp) / "empty", "headless", 0, text="[]\n")
            code, text = run_cli_snapshot(
                fs, ["--profiles", "--profiles-dir", str(Path(tmp) / "empty")]
            )
            self.assertEqual(code, 2)
            self.assertIn("maxBytes не найден", text)

    def test_rw002_default_profiles_dir_is_home_dsh(self):
        """RW-002: каталог профилей по умолчанию - ~/.dsh/profiles (через expanduser); FU-008: боевые пути тоже от ~."""
        self.assertEqual(bg.PROFILES_DIR, os.path.expanduser("~/.dsh/profiles"))
        self.assertEqual(
            bg.CANON_PATH, os.path.expanduser("~/Мой диск/Context/AGENTS.md")
        )
        self.assertEqual(
            bg.KB_CWD, os.path.expanduser("~/Мой диск/Работа/Sber/knowledge-base")
        )
        self.assertEqual(
            bg.AB_CWD, os.path.expanduser("~/Мой диск/Workshop/aibunker-workshop")
        )
        self.assertEqual(
            bg.WA_CWD,
            os.path.expanduser("~/src/saluteeye/gigabus/gigawebaccess/webaccess"),
        )
        self.assertEqual(
            bg.DW_CWD,
            os.path.expanduser("~/Documents/deepseek-harness/default-workspace"),
        )


class TestTm018Guard(unittest.TestCase):
    """TM-018: коды выхода 0/1/2, граница предела блока, рост канона, рекомендуемый maxBytes."""

    def run_eval(self, canon=CANON, maxbytes=106496, files=None):
        return bg.evaluate(canon, files or snapshot_files(canon), maxbytes, ("KB",))

    def test_tm018_limit_boundary_default_100000(self):
        """TM-018/ADR 0015: умолчание 100 000 Б строгое - 99 999 и 100 000 проходят, 100 001 нет."""
        self.assertEqual(bg.BLOCK_LIMIT, 100000)
        self.assertTrue(bg.block_within_limit(99999))
        self.assertTrue(bg.block_within_limit(100000))
        self.assertFalse(bg.block_within_limit(100001))

    def test_tm018_limit_boundary_explicit_limit(self):
        """TM-018: явный предел перекрывает умолчание: 60 000 проходит, 60 001 нет."""
        self.assertTrue(bg.block_within_limit(60000, 60000))
        self.assertFalse(bg.block_within_limit(60001, 60000))
        self.assertTrue(bg.block_within_limit(63262, 100000))  # прежний 503: блок 63 262 Б

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

    def test_tm018_canon_growth_to_ceiling_exit2_at_cli(self):
        """TM-018/RW-004: рост канона до потолка (~63 600 Б) при пределе 60 000 - чистый evaluate без strict даёт 1,
        а рабочий CLI (run_check/main на временных файлах в KB-cwd) - ровно exit 2 с REQ003_SIZE_EXCEEDED."""
        res = bg.evaluate(
            CANON_NOW_CEILING,
            snapshot_files(CANON_NOW_CEILING),
            106496,
            ("KB",),
            limit=LEGACY_LIMIT,
        )
        self.assertEqual(
            res.exit_code, 1
        )  # чистая функция: strict_req003 по умолчанию выключен
        self.assertTrue(any(r.startswith("REQ003_SIZE_EXCEEDED") for r in res.reasons))
        strict = bg.evaluate(
            CANON_NOW_CEILING,
            snapshot_files(CANON_NOW_CEILING),
            106496,
            ("KB",),
            True,
            limit=LEGACY_LIMIT,
        )
        self.assertEqual(strict.exit_code, 2)
        with tempfile.TemporaryDirectory() as tmp:
            fs = build_snapshot_fs(Path(tmp), canon=CANON_NOW_CEILING)
            code, text = run_cli_snapshot(
                fs,
                ["--check", "--maxbytes", "106496"],
                {"BRIDGE_INSTR_LIMIT": "60000"},
            )
            self.assertEqual(code, 2, text)
            self.assertIn("REQ003_SIZE_EXCEEDED cwd=KB", text)

    def test_tm018_canon_ceiling_passes_under_default_limit(self):
        """ADR 0015: тот же потолок канона (~63 600 Б, блок 63 262) при умолчании 100 000 - REQ-003 не нарушен."""
        res = self.run_eval(canon=CANON_NOW_CEILING)
        self.assertFalse(any("REQ003_SIZE_EXCEEDED" in r for r in res.reasons))
        with tempfile.TemporaryDirectory() as tmp:
            fs = build_snapshot_fs(Path(tmp), canon=CANON_NOW_CEILING)
            code, text = run_cli_snapshot(fs, ["--check", "--maxbytes", "106496"])
            self.assertNotIn("REQ003_SIZE_EXCEEDED", text)
            self.assertIn("block_limit=100000", text)

    def test_tm018_canon_out_of_window_exit2(self):
        """TM-018: канон вне окна - слишком большой (CANON_LOST в AB) и слишком малый (DUPLICATE_RETURNED в KB) дают exit 2."""
        big = self.run_eval(canon=70000)
        self.assertEqual(big.exit_code, 2)
        self.assertTrue(any(r.startswith("CANON_LOST cwd=AB") for r in big.reasons))
        small = self.run_eval(canon=45000)
        self.assertEqual(small.exit_code, 2)
        self.assertTrue(
            any(r.startswith("DUPLICATE_RETURNED cwd=KB") for r in small.reasons)
        )

    def test_tm018_recommended_maxbytes(self):
        """TM-018: рекомендуемый maxBytes - наибольшее кратное 4 КиБ с запасом >= 4096 с обеих сторон: на снимке 106 496."""
        res = self.run_eval()
        self.assertEqual(res.recommended, 106496)
        self.assertEqual(res.recommended % 4096, 0)
        self.assertGreaterEqual(res.recommended - res.window_low, 4096)
        self.assertGreaterEqual(res.window_high - res.recommended, 4096)
        self.assertIsNone(bg.recommend_maxbytes(100, 50))  # пустое окно
        self.assertEqual(
            bg.recommend_maxbytes(100, 5000), 2550
        )  # нет кратного - середина

    def test_tm018_check_missing_cwd_does_not_fail(self):
        """TM-018: несуществующий cwd отмечается «cwd отсутствует», проверка не падает (только канон в запросе)."""
        with tempfile.TemporaryDirectory() as tmp:
            canon = Path(tmp) / "AGENTS.md"
            canon.write_bytes(b"c" * 1000)
            out = io.StringIO()
            with redirect_stdout(out):
                code = bg.main(
                    [
                        "--check",
                        "--maxbytes",
                        "106496",
                        "--canon",
                        str(canon),
                        "--cwd",
                        str(Path(tmp) / "absent"),
                    ]
                )
            self.assertIn("cwd отсутствует", out.getvalue())
            self.assertIn("mode=PLANNED", out.getvalue())
            self.assertIn(code, (0, 1))

    def test_tm018_live_check_subprocess(self):
        """TM-018: боевые размеры - `main(["--check"])` (maxBytes по умолчанию, предел блока по умолчанию) в подпроцессе
        даёт exit <= 1 (пропуск только без боевых путей)."""
        needed = [bg.CANON_PATH, bg.KB_CWD, bg.WA_CWD, bg.AB_CWD]
        missing = [p for p in needed if not os.path.exists(p)]
        if missing:
            self.skipTest("нет боевых путей на машине: %s" % missing)
        code = (
            "import sys; sys.path.insert(0, %r); import b_guard; "
            "sys.exit(b_guard.main(['--check']))"
            % str(ROOT / "tools")
        )
        proc = subprocess.run(
            ["/usr/bin/python3", "-c", code],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=dict(clean_env(), PYTHONDONTWRITEBYTECODE="1"),
        )
        text = proc.stdout.decode("utf-8", "replace")
        self.assertLessEqual(proc.returncode, 1, text)
        self.assertIn("lower_margin=", text)
        self.assertIn("mode=PLANNED", text)


class TestBlockLimitConfig(unittest.TestCase):
    """ADR 0015: предел блока не зашит - BRIDGE_INSTR_LIMIT -> DROID_DSH_BRIDGE_INSTR_LIMIT -> 100 000, валидация."""

    def test_default_without_env(self):
        self.assertEqual(bg.resolve_block_limit({}), 100000)

    def test_new_name_has_priority_over_legacy(self):
        env = {"BRIDGE_INSTR_LIMIT": "120000", "DROID_DSH_BRIDGE_INSTR_LIMIT": "70000"}
        self.assertEqual(bg.resolve_block_limit(env), 120000)
        self.assertEqual(
            bg.resolve_block_limit({"DROID_DSH_BRIDGE_INSTR_LIMIT": "70000"}), 70000
        )

    def test_malformed_values_fall_back_to_default(self):
        for bad in ("", "   ", "abc", "12.5", "1e5", "-1", "-100000", "0", "+", "٣٠٠٠٠"):
            with self.subTest(value=bad):
                self.assertEqual(
                    bg.resolve_block_limit({"BRIDGE_INSTR_LIMIT": bad}), 100000
                )

    def test_malformed_new_name_falls_through_to_legacy_then_default(self):
        env = {"BRIDGE_INSTR_LIMIT": "oops", "DROID_DSH_BRIDGE_INSTR_LIMIT": "80000"}
        self.assertEqual(bg.resolve_block_limit(env), 80000)
        env["DROID_DSH_BRIDGE_INSTR_LIMIT"] = "-3"
        self.assertEqual(bg.resolve_block_limit(env), 100000)

    def test_range_bounds_inclusive_and_out_of_range_clamped(self):
        for raw, want in (
            ("10000", 10000),
            ("500000", 500000),
            ("9999", 10000),
            ("1", 10000),
            ("500001", 500000),
            ("99999999999", 500000),
            (" 65000 ", 65000),
        ):
            with self.subTest(value=raw):
                self.assertEqual(
                    bg.resolve_block_limit({"BRIDGE_INSTR_LIMIT": raw}), want
                )

    def test_resolve_reads_process_env_by_default(self):
        with mock.patch.dict(os.environ, clean_env(BRIDGE_INSTR_LIMIT="90000"), clear=True):
            self.assertEqual(bg.resolve_block_limit(), 90000)
        with mock.patch.dict(os.environ, clean_env(), clear=True):
            self.assertEqual(bg.resolve_block_limit(), 100000)

    def test_check_installed_limit_param_and_env(self):
        """`check_installed(..., limit=None)`: None - из окружения; явный `limit` перекрывает его.

        Блок KB ~63 262 Б: при 60 000 - unsafe (exit 2), при 100 000 - REQ-003 цел.
        """
        with tempfile.TemporaryDirectory() as tmp:
            fs = build_snapshot_fs(Path(tmp), canon=CANON_NOW_CEILING)
            cwds = tuple((label, str(fs["cwds"][label])) for label in ("KB", "WA", "AB", "DW"))
            ug = Path(tmp) / "ug.md"
            ug.symlink_to(fs["canon"])
            with (
                mock.patch.object(bg, "KB_CWD", str(fs["cwds"]["KB"])),
                mock.patch.object(bg, "UG_PATH", str(ug)),
                mock.patch.dict(os.environ, clean_env(), clear=True),
            ):
                def run(**kw):
                    return bg.check_installed(106496, cwds, str(fs["canon"]), **kw)

                default = run()
                self.assertFalse(
                    any("REQ003_SIZE_EXCEEDED" in r for r in default.reasons),
                    default.reasons,
                )
                legacy = run(limit=LEGACY_LIMIT)
                self.assertEqual(legacy.exit_code, 2)
                self.assertTrue(
                    any("REQ003_SIZE_EXCEEDED cwd=KB" in r for r in legacy.reasons)
                )
                with mock.patch.dict(os.environ, {"BRIDGE_INSTR_LIMIT": "60000"}):
                    self.assertEqual(run().exit_code, 2)
                    self.assertFalse(
                        any(
                            "REQ003_SIZE_EXCEEDED" in r
                            for r in run(limit=100000).reasons
                        )
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
