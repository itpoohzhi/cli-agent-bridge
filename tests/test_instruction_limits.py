"""Лимит блока agent-instructions 500 000 Б и мягкое усечение проектных правил вместо 503.

Тесты работают на чистых функциях b_guard/server и на `Handler._prompt_guard` с заглушками
(HTTP-сервер и реальные профили/канон владельца не используются).
"""

import hashlib
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import b_guard  # noqa: E402
import server  # noqa: E402

LIMIT = 500000
MARGIN = 2048
CANON_BODY = "Канон: правила владельца.\n" * 200
CANON_HEAD = "Instructions from: /Users/test/.dsh/AGENTS.md\n"
PROJECT_HEAD = "Instructions from: /work/project/AGENTS.md\n"
INTRO = "<system-reminder>\nThe following workspace instructions may be relevant.\n\n"


def canon_digest() -> str:
    return hashlib.sha256(CANON_BODY.strip().encode("utf-8")).hexdigest()


def build_block(project_bytes: int, filler: str = "p") -> str:
    """Блок: канон (защищённая секция) и проектная секция примерно `project_bytes` байт."""
    unit = len(filler.encode("utf-8"))
    project = filler * (project_bytes // unit)
    return (
        INTRO
        + CANON_HEAD
        + CANON_BODY
        + "\n"
        + PROJECT_HEAD
        + project
        + "\n</system-reminder>"
    )


def nbytes(text: str) -> int:
    return len(text.encode("utf-8"))


class FakeHandler:
    """Минимальный носитель `_prompt_guard`: отказ фиксируется, а не отправляется по сети."""

    _prompt_guard = server.Handler._prompt_guard

    def __init__(self):
        self.rejected = []
        self._instr_truncated = False

    def _reject(self, status, error_type, message, model_id, model_len):
        self.rejected.append((status, error_type, message))

    def _chat_known_stub(self, *_args):
        return True


class InstructionLimitsBase(unittest.TestCase):
    def setUp(self):
        patches = [
            mock.patch.object(server, "INSTR_BLOCK_LIMIT", LIMIT),
            mock.patch.object(server, "INSTR_NONKB_MARGIN", MARGIN),
            mock.patch.object(server, "_canon_digest", lambda: canon_digest()),
            mock.patch.dict(server._canon_seen, {}, clear=True),
            # Профиль DSH со старым maxBytes 118 784: предел моста от него зависеть не должен.
            mock.patch.object(
                server.GUARD, "snapshot", return_value=("ok", [], 118784)
            ),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def guard(self, messages, cwd=""):
        handler = FakeHandler()
        instr = handler._prompt_guard(messages, "nokey", None, cwd, "m", 1, object())
        return handler, instr


class TestLimitResolution(unittest.TestCase):
    def test_default_block_limit_500k(self):
        self.assertEqual(b_guard.BLOCK_LIMIT, LIMIT)
        self.assertEqual(b_guard.DEFAULT_MAXBYTES, LIMIT)
        self.assertEqual(b_guard.resolve_block_limit({}), LIMIT)
        # Потолок диапазона выше умолчания: 500k не упирается в границу.
        self.assertGreater(b_guard.INSTR_LIMIT_MAX, LIMIT)

    def test_env_override_block_limit(self):
        self.assertEqual(
            b_guard.resolve_block_limit({"BRIDGE_INSTR_LIMIT": "300000"}), 300000
        )
        self.assertEqual(
            b_guard.resolve_block_limit({"DROID_DSH_BRIDGE_INSTR_LIMIT": "250000"}),
            250000,
        )
        both = {
            "BRIDGE_INSTR_LIMIT": "300000",
            "DROID_DSH_BRIDGE_INSTR_LIMIT": "250000",
        }
        self.assertEqual(b_guard.resolve_block_limit(both), 300000)
        self.assertEqual(
            b_guard.resolve_block_limit({"BRIDGE_INSTR_LIMIT": "750000"}), 750000
        )


class TestNonKbBudget(InstructionLimitsBase):
    def test_nonkb_margin_budget(self):
        expected = LIMIT - MARGIN
        self.assertEqual(expected, 497952)
        non_kb = {"canon_only": False}
        # Устаревший профиль cordis.patch.yml (118k) и отсутствие maxBytes предел не занижают.
        self.assertEqual(server._instr_limit(non_kb, 118784), expected)
        self.assertEqual(server._instr_limit(non_kb, None), expected)
        # Больший maxBytes клиента допустим.
        self.assertEqual(server._instr_limit(non_kb, 600000), 600000 - MARGIN)
        # Канон-форма — без запаса.
        self.assertEqual(server._instr_limit({"canon_only": True}, 118784), LIMIT)

    def test_nonkb_block_within_budget_is_not_touched(self):
        text = build_block(497952 - nbytes(build_block(0)))
        self.assertEqual(nbytes(text), 497952)
        messages = [{"role": "user", "content": text}]
        handler, instr = self.guard(messages)
        self.assertEqual(handler.rejected, [])
        self.assertFalse(handler._instr_truncated)
        self.assertEqual(messages[0]["content"], text)
        self.assertEqual(instr[2], 497952)


class TestSoftTruncation(InstructionLimitsBase):
    def test_soft_truncation_preserves_canon(self):
        text = build_block(LIMIT + 100000)
        self.assertGreater(nbytes(text), LIMIT)
        messages = [{"role": "user", "content": text}]
        handler, instr = self.guard(messages)
        limit = LIMIT - MARGIN
        out = messages[0]["content"]
        self.assertEqual(handler.rejected, [], "503 при усечении недопустим")
        self.assertTrue(handler._instr_truncated)
        self.assertLessEqual(nbytes(out), limit)
        self.assertEqual(instr[2], nbytes(out))
        # Канон цел, проектная секция усечена, маркер с динамическим пределом на месте.
        self.assertIn(CANON_HEAD + CANON_BODY, out)
        self.assertIn(PROJECT_HEAD, out)
        self.assertLess(out.count("p"), text.count("p"))
        self.assertIn(
            f"[... agent-instructions truncated by bridge to limit {limit} bytes ...]",
            out,
        )
        self.assertTrue(out.endswith("</system-reminder>"))
        self.assertLess(out.index(CANON_HEAD), out.index(PROJECT_HEAD))

    def test_lifo_drops_whole_trailing_sections_first(self):
        first = "Instructions from: /a/AGENTS.md\n" + "a" * 1000 + "\n"
        second = "Instructions from: /b/AGENTS.md\n" + "b" * 1000 + "\n"
        text = INTRO + first + second + "</system-reminder>"
        # Остаётся место лишь под первую секцию и маркер: заголовок второй уже не помещается.
        limit = nbytes(INTRO + first) + nbytes(server._truncation_marker(0)) + nbytes("</system-reminder>") + 5 + len(str(nbytes(text)))
        out = server._truncate_instr_text(text, limit)
        self.assertLessEqual(nbytes(out), limit)
        self.assertIn("a" * 1000, out)  # ранняя секция цела
        self.assertNotIn("/b/AGENTS.md", out)  # хвостовая удалена целиком
        self.assertIn("truncated by bridge", out)

    def test_irreducible_canon_block_is_still_refused(self):
        body = CANON_BODY * 4000  # канон сам больше предела: усекать нечего
        canon_text = CANON_HEAD + body
        digest = hashlib.sha256(body.strip().encode("utf-8")).hexdigest()
        self.assertGreater(nbytes(canon_text), LIMIT)
        messages = [{"role": "user", "content": canon_text}]
        with mock.patch.object(server, "_canon_digest", lambda: digest):
            handler, instr = self.guard(messages)
        self.assertIsNone(instr)
        self.assertEqual([r[:2] for r in handler.rejected], [(503, "launcher_unavailable")])
        self.assertEqual(messages[0]["content"], canon_text)

    def test_list_content_keeps_non_text_parts(self):
        text = build_block(LIMIT + 1000)
        image = {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA"}}
        messages = [{"role": "user", "content": [{"type": "text", "text": text}, image]}]
        handler, _instr = self.guard(messages)
        self.assertEqual(handler.rejected, [])
        content = messages[0]["content"]
        self.assertIn(image, content)
        joined = server._flatten_content(content)
        self.assertLessEqual(nbytes(joined), LIMIT - MARGIN)
        self.assertIn(CANON_BODY, joined)


class TestUtf8Safety(InstructionLimitsBase):
    def test_utf8_truncation_safety(self):
        # 2-, 3- и 4-байтовые символы: срез в любой точке не рвёт символ.
        for filler in ("я", "€", "😀", "я€😀"):
            text = build_block(6000, filler)
            for shift in range(0, 9):
                limit = nbytes(text) - 1000 - shift
                with self.subTest(filler=filler, shift=shift):
                    out = server._truncate_instr_text(text, limit)
                    raw = out.encode("utf-8")
                    self.assertLessEqual(len(raw), limit)
                    self.assertEqual(raw.decode("utf-8"), out)  # строгая декодировка
                    self.assertNotIn("�", out)
                    self.assertIn(CANON_BODY, out)

    def test_utf8_through_guard(self):
        text = build_block(LIMIT, "я€😀")
        messages = [{"role": "user", "content": text}]
        handler, _instr = self.guard(messages)
        out = messages[0]["content"]
        self.assertEqual(handler.rejected, [])
        self.assertLessEqual(nbytes(out), LIMIT - MARGIN)
        self.assertNotIn("�", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
