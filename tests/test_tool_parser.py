"""Unit-тесты ToolCallParser и _tools_section моста droid-bridge (импорт из server.py)."""

import importlib.util
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server import (  # noqa: E402
    TOOL_CALL_CLOSE,
    TOOL_CALL_OPEN,
    LiveParserError,
    ToolCallParser,
    _messages_to_prompt,
    _parse_tool_call_block,
    _tools_section,
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
            },
        },
    }
]


class Collector:
    def __init__(self):
        self.content = []
        self.calls = []

    def on_content(self, text):
        self.content.append(text)

    def on_call(self, call):
        self.calls.append(call)


class TestToolCallParser(unittest.TestCase):
    def test_plain_text_passthrough(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        p.feed("Hello, ")
        p.feed("world")
        p.finish()
        self.assertEqual("".join(c.content), "Hello, world")
        self.assertEqual(c.calls, [])

    def test_single_call_split_across_deltas(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        p.feed("Pre text ")
        p.feed(TOOL_CALL_OPEN[:5])  # разрыв прямо внутри тега
        p.feed(TOOL_CALL_OPEN[5:])
        p.feed('{"name": "get_we')
        p.feed('ather", "arguments": {"city": "Berlin"}}')
        p.feed(TOOL_CALL_CLOSE)
        p.finish()
        self.assertEqual("".join(c.content), "Pre text ")
        self.assertEqual(
            c.calls, [{"name": "get_weather", "arguments": {"city": "Berlin"}}]
        )

    def test_multiple_calls_in_row(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        p.feed(
            TOOL_CALL_OPEN
            + '{"name": "a", "arguments": {}}'
            + TOOL_CALL_CLOSE
            + TOOL_CALL_OPEN
            + '{"name": "b"}'
            + TOOL_CALL_CLOSE
        )
        p.finish()
        self.assertEqual(
            c.calls, [{"name": "a", "arguments": {}}, {"name": "b", "arguments": {}}]
        )
        self.assertEqual("".join(c.content), "")

    def test_close_tag_inside_string_is_not_boundary(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        payload = json.dumps(
            {"name": "t", "arguments": {"text": "x " + TOOL_CALL_CLOSE + " y"}}
        )
        p.feed(TOOL_CALL_OPEN + payload + TOOL_CALL_CLOSE)
        p.finish()
        self.assertEqual(
            c.calls,
            [{"name": "t", "arguments": {"text": "x " + TOOL_CALL_CLOSE + " y"}}],
        )

    def test_escaped_quote_does_not_end_string(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        p.feed(
            TOOL_CALL_OPEN
            + '{"name": "t", "arguments": {"q": "a\\"b"}}'
            + TOOL_CALL_CLOSE
        )
        p.finish()
        self.assertEqual(c.calls, [{"name": "t", "arguments": {"q": 'a"b'}}])

    def test_invalid_block_falls_back_to_text(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        p.feed(TOOL_CALL_OPEN + "not json" + TOOL_CALL_CLOSE)
        p.finish()
        self.assertEqual(c.calls, [])
        self.assertIn("not json", "".join(c.content))

    def test_unclosed_block_flushed_as_text_on_finish(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        p.feed("tail " + TOOL_CALL_OPEN + '{"name": "t"')
        p.finish()
        self.assertEqual(c.calls, [])
        self.assertIn('{"name": "t"', "".join(c.content))

    def test_pending_prefix_not_emitted_early(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        p.feed("abc<tool_")
        self.assertEqual("".join(c.content), "abc")  # хвост удержан
        p.feed("call>" + '{"name": "t"}' + TOOL_CALL_CLOSE)
        p.finish()
        self.assertEqual(c.calls, [{"name": "t", "arguments": {}}])
        self.assertEqual("".join(c.content), "abc")

    def test_non_object_arguments_rejected(self):
        self.assertIsNone(_parse_tool_call_block('{"name": "t", "arguments": "[1,2]"}'))
        self.assertEqual(
            _parse_tool_call_block('{"name": "t"}'), {"name": "t", "arguments": {}}
        )

    def test_code_fence_stripped(self):
        inner = "```json\n" + '{"name": "t", "arguments": {"a": 1}}' + "\n```"
        self.assertEqual(
            _parse_tool_call_block(inner), {"name": "t", "arguments": {"a": 1}}
        )

    # -- AD-002: strict_live vs legacy, парные регрессии -----------------------------
    # Legacy (strict_live=False, умолчание) не меняется ни байтом: malformed/unclosed
    # блок, как и раньше, молча уходит в content как текст (test_invalid_block_falls_back_to_text/
    # test_unclosed_block_flushed_as_text_on_finish выше). strict_live=True (живой SSE-ход
    # droid) вместо этого поднимает LiveParserError — сырой `<tool_call>` клиенту не утекает.

    def test_nonstream_malformed_xml_fallback_unchanged(self):
        """Legacy (strict_live=False): невалидный блок — текстом, без исключения."""
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call, strict_live=False)
        p.feed(TOOL_CALL_OPEN + "not json" + TOOL_CALL_CLOSE)
        p.finish()
        self.assertEqual(c.calls, [])
        self.assertIn(TOOL_CALL_OPEN + "not json" + TOOL_CALL_CLOSE, "".join(c.content))

    def test_nonstream_unclosed_xml_finish_fallback_unchanged(self):
        """Legacy (strict_live=False): незакрытый блок на finish() — текстом, без исключения."""
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call, strict_live=False)
        p.feed("tail " + TOOL_CALL_OPEN + '{"name": "t"')
        p.finish()
        self.assertEqual(c.calls, [])
        self.assertIn('{"name": "t"', "".join(c.content))

    def test_strict_live_malformed_xml_error_no_leak(self):
        """strict_live=True: невалидный блок — LiveParserError, сырой XML не уходит в content."""
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call, strict_live=True)
        with self.assertRaises(LiveParserError):
            p.feed("Pre text " + TOOL_CALL_OPEN + "not json" + TOOL_CALL_CLOSE)
        self.assertEqual(c.calls, [])
        # Текст ДО блока — легитимный контент, его отдать можно (это не часть <tool_call>).
        self.assertEqual("".join(c.content), "Pre text ")
        self.assertNotIn("not json", "".join(c.content))
        self.assertNotIn(TOOL_CALL_OPEN, "".join(c.content))

    def test_strict_live_unclosed_xml_error_no_leak(self):
        """strict_live=True: незакрытый блок на finish() — LiveParserError, не текст."""
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call, strict_live=True)
        p.feed("tail " + TOOL_CALL_OPEN + '{"name": "t"')
        with self.assertRaises(LiveParserError):
            p.finish()
        self.assertEqual(c.calls, [])
        # "tail " до открывающего тега — легитимный текст, его отдать можно;
        # а вот незакрытое содержимое самого блока наружу не ушло — вместо него исключение.
        self.assertEqual("".join(c.content), "tail ")
        self.assertNotIn('{"name": "t"', "".join(c.content))

    def test_strict_live_unresolved_prefix_error_no_leak(self):
        """strict_live=True: оборванный префикс открывающего тега на finish() — тоже ошибка."""
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call, strict_live=True)
        p.feed("abc" + TOOL_CALL_OPEN[:5])  # разрыв прямо внутри тега, конца хода нет
        with self.assertRaises(LiveParserError):
            p.finish()
        self.assertEqual(c.calls, [])
        self.assertEqual("".join(c.content), "abc")
        self.assertNotIn(TOOL_CALL_OPEN[:5], "".join(c.content)[3:])

    def test_strict_live_well_formed_call_unaffected(self):
        """strict_live=True не меняет поведение для валидного блока (только malformed/unclosed)."""
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call, strict_live=True)
        p.feed(
            "Pre "
            + TOOL_CALL_OPEN
            + '{"name": "get_weather", "arguments": {"city": "Berlin"}}'
            + TOOL_CALL_CLOSE
        )
        p.finish()
        self.assertEqual(
            c.calls, [{"name": "get_weather", "arguments": {"city": "Berlin"}}]
        )
        self.assertEqual("".join(c.content), "Pre ")


CALL_A = '{"name": "read", "arguments": {"file_path": "/a"}}'
CALL_B = '{"name": "read", "arguments": {"file_path": "/b"}}'
CALL_C = '{"name": "bash", "arguments": {"command": "ls"}}'
PARSED_A = {"name": "read", "arguments": {"file_path": "/a"}}
PARSED_B = {"name": "read", "arguments": {"file_path": "/b"}}
PARSED_C = {"name": "bash", "arguments": {"command": "ls"}}

# Пачка с пустым первым/средним/последним элементом отклоняется целиком.
EMPTY_MEMBER_BATCHES = {
    "first": TOOL_CALL_OPEN + TOOL_CALL_OPEN + '{"name":"a"}' + TOOL_CALL_CLOSE,
    "middle": TOOL_CALL_OPEN
    + '{"name":"a"}'
    + TOOL_CALL_OPEN
    + " "
    + TOOL_CALL_OPEN
    + '{"name":"b"}'
    + TOOL_CALL_CLOSE,
    "last": TOOL_CALL_OPEN + '{"name":"a"}' + TOOL_CALL_OPEN + TOOL_CALL_CLOSE,
}


class TestBatchWithoutIntermediateClose(unittest.TestCase):
    """Регрессия: пачка `<tool_call>{..} <tool_call>{..}</tool_call>` уходила в чат сырым текстом."""

    def test_batch_with_single_shared_close_tag(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        p.feed(
            "Читаю. "
            + TOOL_CALL_OPEN
            + CALL_A
            + " "
            + TOOL_CALL_OPEN
            + CALL_B
            + "\n"
            + TOOL_CALL_OPEN
            + CALL_C
            + TOOL_CALL_CLOSE
        )
        p.finish()
        self.assertEqual(c.calls, [PARSED_A, PARSED_B, PARSED_C])
        self.assertEqual("".join(c.content), "Читаю. ")
        self.assertNotIn(TOOL_CALL_OPEN, "".join(c.content))

    def test_batch_fed_in_chunks(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        head = TOOL_CALL_OPEN + CALL_A + " " + TOOL_CALL_OPEN + CALL_B
        for i in range(0, len(head), 7):
            p.feed(head[i : i + 7])
        self.assertEqual(c.calls, [])  # до закрывающего тега пачка не разбирается
        self.assertEqual("".join(c.content), "")
        p.feed(TOOL_CALL_CLOSE)
        p.finish()
        self.assertEqual(c.calls, [PARSED_A, PARSED_B])
        self.assertEqual("".join(c.content), "")

    def test_mixed_closed_and_unclosed_calls(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        p.feed(
            TOOL_CALL_OPEN
            + CALL_A
            + TOOL_CALL_CLOSE
            + TOOL_CALL_OPEN
            + CALL_B
            + TOOL_CALL_OPEN
            + CALL_C
            + TOOL_CALL_CLOSE
        )
        p.finish()
        self.assertEqual(c.calls, [PARSED_A, PARSED_B, PARSED_C])
        self.assertEqual("".join(c.content), "")

    def test_open_tag_inside_string_is_not_separator(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call)
        tricky = json.dumps(
            {"name": "t", "arguments": {"text": "x " + TOOL_CALL_OPEN + " y"}}
        )
        p.feed(
            TOOL_CALL_OPEN + tricky + " " + TOOL_CALL_OPEN + CALL_A + TOOL_CALL_CLOSE
        )
        p.finish()
        self.assertEqual(
            c.calls,
            [
                {"name": "t", "arguments": {"text": "x " + TOOL_CALL_OPEN + " y"}},
                PARSED_A,
            ],
        )
        self.assertEqual("".join(c.content), "")

    def test_malformed_member_rejects_whole_batch_as_text(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call, strict_live=False)
        p.feed(
            TOOL_CALL_OPEN
            + '{"name": "a"} '
            + TOOL_CALL_OPEN
            + "{broken"
            + TOOL_CALL_CLOSE
        )
        p.finish()
        self.assertEqual(c.calls, [])
        self.assertIn("{broken", "".join(c.content))

    def test_strict_live_malformed_member_raises_no_partial_calls(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call, strict_live=True)
        with self.assertRaises(LiveParserError):
            p.feed(
                TOOL_CALL_OPEN
                + '{"name": "a"} '
                + TOOL_CALL_OPEN
                + "{broken"
                + TOOL_CALL_CLOSE
            )
        self.assertEqual(c.calls, [])
        self.assertEqual("".join(c.content), "")

    def test_strict_live_batch_without_intermediate_close(self):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call, strict_live=True)
        p.feed(
            TOOL_CALL_OPEN + CALL_A + " " + TOOL_CALL_OPEN + CALL_B + TOOL_CALL_CLOSE
        )
        p.finish()
        self.assertEqual(c.calls, [PARSED_A, PARSED_B])
        self.assertEqual("".join(c.content), "")

    def test_empty_member_rejects_whole_batch_as_text(self):
        for name, raw in EMPTY_MEMBER_BATCHES.items():
            with self.subTest(position=name):
                c = Collector()
                p = ToolCallParser(c.on_content, c.on_call, strict_live=False)
                p.feed(raw)
                p.finish()
                self.assertEqual(c.calls, [])
                self.assertEqual("".join(c.content), raw)

    def test_strict_live_empty_member_raises_no_calls(self):
        for name, raw in EMPTY_MEMBER_BATCHES.items():
            with self.subTest(position=name):
                c = Collector()
                p = ToolCallParser(c.on_content, c.on_call, strict_live=True)
                with self.assertRaises(LiveParserError):
                    p.feed(raw)
                self.assertEqual(c.calls, [])
                self.assertEqual("".join(c.content), "")

    def test_strict_live_malformed_and_empty_batches_across_chunkings(self):
        """strict_live=True: испорченная пачка атомарно отклоняется при любой нарезке потока."""
        cases = {
            "malformed_member": TOOL_CALL_OPEN
            + '{"name": "a"} '
            + TOOL_CALL_OPEN
            + "{broken"
            + TOOL_CALL_CLOSE,
            "empty_first": EMPTY_MEMBER_BATCHES["first"],
            "empty_middle": EMPTY_MEMBER_BATCHES["middle"],
            "empty_last": EMPTY_MEMBER_BATCHES["last"],
        }
        for name, batch in cases.items():
            raw = "Pre " + batch
            chunkings = [("whole", [raw]), ("char_by_char", list(raw))]
            chunkings += [(f"cut_{k}", [raw[:k], raw[k:]]) for k in range(1, len(raw))]
            for mode, chunks in chunkings:
                with self.subTest(case=name, mode=mode):
                    c = Collector()
                    p = ToolCallParser(c.on_content, c.on_call, strict_live=True)
                    with self.assertRaises(LiveParserError):
                        for chunk in chunks:
                            p.feed(chunk)
                        p.finish()
                    self.assertEqual(c.calls, [])
                    self.assertEqual("".join(c.content), "Pre ")
                    self.assertNotIn(TOOL_CALL_OPEN, "".join(c.content))


class TestInlineCodeBatch(unittest.TestCase):
    """Регрессия: пачка `<tool_call>` в inline-backticks — пример-текст, а не вызовы."""

    def _texts(self):
        o, cl = TOOL_CALL_OPEN, TOOL_CALL_CLOSE
        return {
            "batch": "Пример: `"
            + o
            + '{"name":"a"}'
            + " "
            + o
            + '{"name":"b"}'
            + cl
            + "`",
            "text_before_tag": "Пример: `пример "
            + o
            + '{"name":"a"}'
            + " "
            + o
            + '{"name":"b"}'
            + cl
            + "`",
            "space_before_tag": "Пример: ` "
            + o
            + '{"name":"a"}'
            + " "
            + o
            + '{"name":"b"}'
            + cl
            + "`",
            "single": "Пример: `" + o + '{"name":"a"}' + cl + "`",
            "batch_then_text": "`"
            + o
            + '{"name":"a"}'
            + " "
            + o
            + '{"name":"b"}'
            + cl
            + "` и дальше",
        }

    def _run(self, text, char_by_char, **kwargs):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call, **kwargs)
        if char_by_char:
            for ch in text:
                p.feed(ch)
        else:
            p.feed(text)
        p.finish()
        return c

    def test_inline_code_batch_is_plain_text(self):
        for name, text in self._texts().items():
            for char_by_char in (False, True):
                with self.subTest(case=name, char_by_char=char_by_char):
                    c = self._run(text, char_by_char)
                    self.assertEqual(c.calls, [])
                    self.assertEqual("".join(c.content), text)

    def test_strict_live_inline_code_batch_does_not_raise(self):
        for name, text in self._texts().items():
            for char_by_char in (False, True):
                with self.subTest(case=name, char_by_char=char_by_char):
                    c = self._run(text, char_by_char, strict_live=True)
                    self.assertEqual(c.calls, [])
                    self.assertEqual("".join(c.content), text)

    def test_real_call_after_closed_text_inline_code_parsed(self):
        o, cl = TOOL_CALL_OPEN, TOOL_CALL_CLOSE
        quoted = (
            "Пример: `пример "
            + o
            + '{"name":"a"}'
            + " "
            + o
            + '{"name":"b"}'
            + cl
            + "`"
        )
        text = quoted + " и затем " + o + '{"name":"c"}' + cl
        for strict in (False, True):
            for char_by_char in (False, True):
                with self.subTest(strict=strict, char_by_char=char_by_char):
                    c = self._run(text, char_by_char, strict_live=strict)
                    self.assertEqual(c.calls, [{"name": "c", "arguments": {}}])
                    self.assertEqual("".join(c.content), quoted + " и затем ")

    def test_real_call_after_closed_inline_code_still_parsed(self):
        o, cl = TOOL_CALL_OPEN, TOOL_CALL_CLOSE
        text = "Смотри `код` и " + o + '{"name":"a"}' + cl
        for char_by_char in (False, True):
            with self.subTest(char_by_char=char_by_char):
                c = self._run(text, char_by_char)
                self.assertEqual(c.calls, [{"name": "a", "arguments": {}}])
                self.assertEqual("".join(c.content), "Смотри `код` и ")

    def _run_chunks(self, chunks, **kwargs):
        c = Collector()
        p = ToolCallParser(c.on_content, c.on_call, **kwargs)
        for chunk in chunks:
            p.feed(chunk)
        p.finish()
        return c

    @staticmethod
    def _chunkings(text):
        """Цельная подача, посимвольная и каждое разбиение на два чанка."""
        yield "whole", [text]
        yield "char_by_char", list(text)
        for cut in range(1, len(text)):
            yield f"cut_{cut}", [text[:cut], text[cut:]]

    def _nested_ticks_cases(self):
        o, cl = TOOL_CALL_OPEN, TOOL_CALL_CLOSE
        batch = o + '{"name":"a"}' + " " + o + '{"name":"b"}' + cl
        single = o + '{"name":"a"}' + cl
        quoted_double = "Пример: ``пример ` " + batch + "``"
        quoted_multiline = "Пример: `пример\n" + batch + "`"
        quoted_single = "Пример: `код `` " + batch + "`"
        return {
            # одиночный бэктик внутри двойных не закрывает inline-код
            "single_inside_double": (quoted_double, [], quoted_double),
            # двойная серия внутри одиночных не закрывает inline-код
            "double_inside_single": (quoted_single, [], quoted_single),
            # перенос строки внутри inline-кода не закрывает его
            "multiline_example": (quoted_multiline, [], quoted_multiline),
            # настоящий вызов после закрытого «``код ` текст``»
            "real_after_double_with_single": (
                "``код ` текст`` " + single,
                [{"name": "a", "arguments": {}}],
                "``код ` текст`` ",
            ),
            # настоящий вызов после многострочного inline-кода
            "real_after_multiline": (
                "`пример\nещё` " + single,
                [{"name": "a", "arguments": {}}],
                "`пример\nещё` ",
            ),
        }

    def test_nested_ticks_and_multiline_inline_code(self):
        for name, (text, calls, content) in self._nested_ticks_cases().items():
            for strict in (False, True):
                for mode, chunks in self._chunkings(text):
                    with self.subTest(case=name, strict=strict, mode=mode):
                        c = self._run_chunks(chunks, strict_live=strict)
                        self.assertEqual(c.calls, calls)
                        self.assertEqual("".join(c.content), content)

    def _escape_and_long_ticks_cases(self):
        o, cl = TOOL_CALL_OPEN, TOOL_CALL_CLOSE
        single = o + '{"name":"a"}' + cl
        batch = o + '{"name":"a"}' + " " + o + '{"name":"b"}' + cl
        long_quoted = "Пример: ```пример " + batch + "``` "
        double_quoted = "Двойной слэш \\\\`пример " + single + "` "
        return {
            # экранированный бэктик код не открывает: вызов после него настоящий
            "escaped_tick": (
                "Литерал \\` и затем " + single,
                [{"name": "a", "arguments": {}}],
                "Литерал \\` и затем ",
            ),
            # `\\` — пара слэшей, бэктик после неё открывает inline-код
            "double_backslash_opens_code": (double_quoted, [], double_quoted),
            # разделитель из 3 бэктиков открывает inline-код целиком
            "triple_tick_inline_code": (long_quoted, [], long_quoted),
            # настоящий вызов после закрытия разделителя из 3 бэктиков
            "real_after_triple_tick": (
                long_quoted + "и затем " + single,
                [{"name": "a", "arguments": {}}],
                long_quoted + "и затем ",
            ),
        }

    def test_escaped_tick_and_long_delimiter(self):
        for name, (text, calls, content) in self._escape_and_long_ticks_cases().items():
            for strict in (False, True):
                for mode, chunks in self._chunkings(text):
                    with self.subTest(case=name, strict=strict, mode=mode):
                        c = self._run_chunks(chunks, strict_live=strict)
                        self.assertEqual(c.calls, calls)
                        self.assertEqual("".join(c.content), content)

    def _fence_and_unpaired_cases(self):
        o, cl = TOOL_CALL_OPEN, TOOL_CALL_CLOSE
        single = o + '{"name":"a"}' + cl
        batch = o + '{"name":"a"}' + " " + o + '{"name":"b"}' + cl
        call_a = [{"name": "a", "arguments": {}}]
        # `\n` — реальные переводы строк
        fence_inner = "```text\nпример ``` внутри строки\n" + batch + "\n```"
        fence_four = "```\nкод\n````\n" + single
        return {
            # B1: непарный бэктик — обычный текст, вызов после него настоящий
            "unpaired_tick_real_call": (
                "Литерал ` без пары; затем " + single,
                call_a,
                "Литерал ` без пары; затем ",
            ),
            # непарная серия из двух бэктиков тоже литерал
            "unpaired_double_tick_real_call": (
                "Литерал `` без пары; затем " + single,
                call_a,
                "Литерал `` без пары; затем ",
            ),
            # непарный бэктик в прошлом абзаце не уходит в пару к следующему
            "unpaired_tick_other_paragraph": (
                "Литерал `\n\nкод `x` и " + single,
                call_a,
                "Литерал `\n\nкод `x` и ",
            ),
            # B2: три бэктика посреди строки забор не закрывают
            "triple_tick_mid_line_keeps_fence": (fence_inner, [], fence_inner),
            # B2: закрывающий забор из четырёх бэктиков закрывает открывающий из трёх
            "four_tick_closes_three_fence": (
                fence_four,
                call_a,
                "```\nкод\n````\n",
            ),
            # забор не закрывает серия короче открывающей
            "shorter_run_keeps_fence": (
                "````\nкод\n```\n" + single,
                [],
                "````\nкод\n```\n" + single,
            ),
            # закрывающий забор с текстом после серии забором не считается
            "closing_with_text_keeps_fence": (
                "```\nкод\n``` текст\n" + single,
                [],
                "```\nкод\n``` текст\n" + single,
            ),
            # вызов после закрытого забора настоящий
            "real_after_closed_fence": (
                "```\nкод\n```\n" + single,
                call_a,
                "```\nкод\n```\n",
            ),
        }

    def test_fence_blocks_and_unpaired_ticks(self):
        for name, (text, calls, content) in self._fence_and_unpaired_cases().items():
            for strict in (False, True):
                for mode, chunks in self._chunkings(text):
                    with self.subTest(case=name, strict=strict, mode=mode):
                        c = self._run_chunks(chunks, strict_live=strict)
                        self.assertEqual(c.calls, calls)
                        self.assertEqual("".join(c.content), content)

    def _tilde_fence_cases(self):
        o, cl = TOOL_CALL_OPEN, TOOL_CALL_CLOSE
        single = o + '{"name":"a"}' + cl
        call_c = o + '{"name":"c"}' + cl
        batch = o + '{"name":"a"}' + " " + o + '{"name":"b"}' + cl
        calls_a = [{"name": "a", "arguments": {}}]
        calls_c = [{"name": "c", "arguments": {}}]
        # `\n` — реальные переводы строк
        tilde_example = "~~~text\n" + batch + "\n~~~"
        return {
            # B1: пачка внутри забора из тильд — пример, вызовов нет
            "tilde_fence_batch_example": (tilde_example, [], tilde_example),
            # настоящий вызов после закрывающего `~~~`
            "real_after_closing_tilde": (
                tilde_example + "\n" + call_c,
                calls_c,
                tilde_example + "\n",
            ),
            # `~~~~` закрывает открывающий `~~~`
            "four_tilde_closes_three_fence": (
                "~~~text\n" + batch + "\n~~~~\n" + call_c,
                calls_c,
                "~~~text\n" + batch + "\n~~~~\n",
            ),
            # забор из тильд закрывают только тильды, не бэктики
            "backticks_do_not_close_tilde_fence": (
                "~~~text\n" + single + "\n```\n" + call_c,
                [],
                "~~~text\n" + single + "\n```\n" + call_c,
            ),
            # забор из бэктиков закрывают только бэктики, не тильды
            "tildes_do_not_close_backtick_fence": (
                "```text\n" + single + "\n~~~\n" + call_c,
                [],
                "```text\n" + single + "\n~~~\n" + call_c,
            ),
            # серия тильд короче открывающей забор не закрывает
            "shorter_tilde_run_keeps_fence": (
                "~~~~\n" + single + "\n~~~\n" + call_c,
                [],
                "~~~~\n" + single + "\n~~~\n" + call_c,
            ),
            # закрывающий забор с текстом после серии забором не считается
            "tilde_closing_with_text_keeps_fence": (
                "~~~\n" + single + "\n~~~ текст\n" + call_c,
                [],
                "~~~\n" + single + "\n~~~ текст\n" + call_c,
            ),
            # бэктик в info-строке забора из тильд допустим (CommonMark)
            "tilde_info_with_backtick": (
                "~~~ a`b\n" + batch + "\n~~~\n" + call_c,
                calls_c,
                "~~~ a`b\n" + batch + "\n~~~\n",
            ),
            # отступ до 3 пробелов — всё ещё забор, и открывающий, и закрывающий
            "indented_tilde_fence": (
                "   ~~~\n" + batch + "\n   ~~~\n" + call_c,
                calls_c,
                "   ~~~\n" + batch + "\n   ~~~\n",
            ),
            # тег в info-строке забора из тильд — пример
            "tag_in_tilde_info_line": ("~~~" + single, [], "~~~" + single),
            # две тильды — не забор: вызов настоящий
            "two_tildes_not_fence": (
                "~~\n" + single,
                calls_a,
                "~~\n",
            ),
        }

    def test_tilde_fence_blocks(self):
        for name, (text, calls, content) in self._tilde_fence_cases().items():
            for strict in (False, True):
                for mode, chunks in self._chunkings(text):
                    with self.subTest(case=name, strict=strict, mode=mode):
                        c = self._run_chunks(chunks, strict_live=strict)
                        self.assertEqual(c.calls, calls)
                        self.assertEqual("".join(c.content), content)

    def test_tilde_json_fence_inside_block_is_real_call(self):
        o, cl = TOOL_CALL_OPEN, TOOL_CALL_CLOSE
        text = o + "\n~~~json\n" + '{"name":"a"}' + "\n~~~\n" + cl
        for char_by_char in (False, True):
            with self.subTest(char_by_char=char_by_char):
                c = self._run(text, char_by_char)
                self.assertEqual(c.calls, [{"name": "a", "arguments": {}}])
                self.assertEqual("".join(c.content), "")

    def test_json_fence_inside_block_is_real_call(self):
        o, cl = TOOL_CALL_OPEN, TOOL_CALL_CLOSE
        text = o + "\n```json\n" + '{"name":"a"}' + "\n```\n" + cl
        for char_by_char in (False, True):
            with self.subTest(char_by_char=char_by_char):
                c = self._run(text, char_by_char)
                self.assertEqual(c.calls, [{"name": "a", "arguments": {}}])
                self.assertEqual("".join(c.content), "")

    def _atx_heading_cases(self):
        o, cl = TOOL_CALL_OPEN, TOOL_CALL_CLOSE
        single = o + '{"name":"a"}' + cl
        call_a = [{"name": "a", "arguments": {}}]
        # `\n` — реальные переводы строк
        hash_no_space = "#x `\n" + single + "\nтекст `"
        return {
            # B1: бэктик в ATX-заголовке не парится с бэктиком из следующего блока
            "atx_heading_tick_then_text": (
                "# Литерал `\n" + single + "\nТекст ` здесь",
                call_a,
                "# Литерал `\n\nТекст ` здесь",
            ),
            # бэктик в абзаце не парится с бэктиком из следующего ATX-заголовка
            "tick_before_atx_heading": (
                "Текст `\n" + single + "\n## Заголовок `x",
                call_a,
                "Текст `\n\n## Заголовок `x",
            ),
            # `#` без пробела — не заголовок: inline-код продолжается через строки
            "hash_without_space_is_not_heading": (hash_no_space, [], hash_no_space),
        }

    def test_atx_heading_ends_inline_code_block(self):
        for name, (text, calls, content) in self._atx_heading_cases().items():
            for strict in (False, True):
                for mode, chunks in self._chunkings(text):
                    with self.subTest(case=name, strict=strict, mode=mode):
                        c = self._run_chunks(chunks, strict_live=strict)
                        self.assertEqual(c.calls, calls)
                        self.assertEqual("".join(c.content), content)


def _load_muse_bridge():
    """Загружает bridges/muse-bridge/server.py как модуль, без запуска HTTP-сервера."""
    path = (
        Path(__file__).resolve().parent.parent / "bridges" / "muse-bridge" / "server.py"
    )
    spec = importlib.util.spec_from_file_location("muse_bridge_server_contract", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestCrossBridgeParserContract(unittest.TestCase):
    """Единый контракт: core/tool_emulation.py и muse-bridge дают одинаковые (calls, content)."""

    @classmethod
    def setUpClass(cls):
        cls.muse = _load_muse_bridge()

    def _contract_cases(self):
        o, cl = TOOL_CALL_OPEN, TOOL_CALL_CLOSE
        a, b, c = '{"name":"a"}', '{"name":"b"}', '{"name":"c"}'
        call = lambda n: {"name": n, "arguments": {}}  # noqa: E731
        single = o + a + cl
        batch = o + a + " " + o + b + cl
        tricky = json.dumps({"name": "t", "arguments": {"text": "x " + o + " y"}})
        tricky_parsed = {"name": "t", "arguments": {"text": "x " + o + " y"}}
        fence_example = "```text\n" + batch + "\n```"
        tilde_example = "~~~text\n" + batch + "\n~~~"
        inline_single = "Пример: `" + batch + "`"
        inline_double = "Пример: ``пример ` " + batch + "``"
        atx = "# Литерал `\n" + single + "\nТекст ` здесь"
        return {
            "single": (o + a + cl, [call("a")], ""),
            "batch_shared_close": (
                o + a + " " + o + b + "\n" + o + c + cl,
                [call("a"), call("b"), call("c")],
                "",
            ),
            "mixed_batch": (
                o + a + cl + o + b + o + c + cl,
                [call("a"), call("b"), call("c")],
                "",
            ),
            "open_tag_in_json_string": (
                o + tricky + " " + o + a + cl,
                [tricky_parsed, call("a")],
                "",
            ),
            "malformed_member": (
                o + a + " " + o + "{broken" + cl,
                [],
                o + a + " " + o + "{broken" + cl,
            ),
            "empty_first": (o + o + a + cl, [], o + o + a + cl),
            "empty_middle": (
                o + a + o + " " + o + b + cl,
                [],
                o + a + o + " " + o + b + cl,
            ),
            "empty_last": (o + a + o + cl, [], o + a + o + cl),
            "inline_code_single_tick": (inline_single, [], inline_single),
            "inline_code_double_tick": (inline_double, [], inline_double),
            "escaped_tick_before_real_call": (
                "Литерал \\` и затем " + single,
                [call("a")],
                "Литерал \\` и затем ",
            ),
            "backtick_fence": (fence_example, [], fence_example),
            "real_call_after_backtick_fence": (
                fence_example + "\n" + single,
                [call("a")],
                fence_example + "\n",
            ),
            "tilde_fence": (tilde_example, [], tilde_example),
            "real_call_after_tilde_fence": (
                tilde_example + "\n" + single,
                [call("a")],
                tilde_example + "\n",
            ),
            "atx_heading_unpaired_tick": (
                atx,
                [call("a")],
                "# Литерал `\n\nТекст ` здесь",
            ),
        }

    @staticmethod
    def _run(parser_cls, chunks):
        content, calls = [], []
        p = parser_cls(content.append, calls.append)
        for chunk in chunks:
            p.feed(chunk)
        p.finish()
        return calls, "".join(content)

    def test_core_and_muse_parsers_follow_same_contract(self):
        parsers = {"core": ToolCallParser, "muse": self.muse.ToolCallParser}
        for name, (text, calls, content) in self._contract_cases().items():
            for mode, chunks in TestInlineCodeBatch._chunkings(text):
                for impl, parser_cls in parsers.items():
                    with self.subTest(case=name, mode=mode, impl=impl):
                        got_calls, got_content = self._run(parser_cls, chunks)
                        self.assertEqual(got_calls, calls)
                        self.assertEqual(got_content, content)

    def test_muse_bridge_uses_same_markers(self):
        self.assertEqual(self.muse.TOOL_CALL_OPEN, TOOL_CALL_OPEN)
        self.assertEqual(self.muse.TOOL_CALL_CLOSE, TOOL_CALL_CLOSE)


class TestToolsSection(unittest.TestCase):
    def test_protocol_and_schema_present(self):
        section = _tools_section(TOOLS, None)
        self.assertIn("# Tool calling protocol", section)
        self.assertIn(
            TOOL_CALL_OPEN
            + '{"name": "<tool_name>", "arguments": {<json>}}'
            + TOOL_CALL_CLOSE,
            section,
        )
        self.assertIn("- get_weather: Get current weather", section)
        self.assertIn('"city"', section)
        self.assertNotIn("You MUST", section)

    def test_tool_choice_required(self):
        self.assertIn(
            "You MUST call at least one tool now.", _tools_section(TOOLS, "required")
        )

    def test_forced_function(self):
        self.assertIn(
            'You MUST call the tool "get_weather" now.',
            _tools_section(
                TOOLS, {"type": "function", "function": {"name": "get_weather"}}
            ),
        )


class TestPromptRendering(unittest.TestCase):
    def test_tool_history_roundtrip(self):
        prompt = _messages_to_prompt(
            [
                {"role": "user", "content": "Weather?"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "arguments": '{"city": "Berlin"}',
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": "call_1",
                    "name": "get_weather",
                    "content": "18C, rain",
                },
            ],
            TOOLS,
        )
        self.assertIn("[tool result call_1] (get_weather)", prompt)
        self.assertIn("18C, rain", prompt)
        self.assertIn(TOOL_CALL_OPEN, prompt)
        self.assertIn('"city": "Berlin"', prompt)

    def test_tool_choice_none_omits_section(self):
        prompt = _messages_to_prompt([{"role": "user", "content": "hi"}], TOOLS, "none")
        self.assertNotIn("# Tool calling protocol", prompt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
