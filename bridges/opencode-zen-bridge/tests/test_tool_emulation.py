#!/usr/bin/env python3
"""Regression: мост эмулирует OpenAI function calling (2026-10-08).

Баг: DSH через opencode-zen-bridge делал ровно один ход — мост отдавал только текст
и finish_reason "stop", tools в промпт не попадали вовсе.
"""

from __future__ import annotations

import json
import unittest
from typing import Any, ClassVar

import server
from tests._fixtures import install_test_models

PRODUCTION_MODELS = install_test_models(server)

TOOLS = [{"type": "function", "function": {
    "name": "bash", "description": "run",
    "parameters": {"type": "object", "properties": {"command": {"type": "string"}}}}}]


class TestToolEmulation(unittest.TestCase):
    def test_split_tool_calls_across_chunks(self) -> None:
        chunks = ["Проверяю. <tool", '_call>{"name": "bash", "arguments": {"command": "pgrep nginx"}}</tool_call>']
        content, calls = server._split_tool_calls(chunks)
        self.assertEqual(content.strip(), "Проверяю.")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["function"]["name"], "bash")
        self.assertEqual(json.loads(calls[0]["function"]["arguments"]), {"command": "pgrep nginx"})

    def test_plain_text_no_calls(self) -> None:
        content, calls = server._split_tool_calls(["just text"])
        self.assertEqual((content, calls), ("just text", []))

    def test_history_renders_tool_calls_and_results(self) -> None:
        _, prompt = server._messages_to_prompt([
            {"role": "user", "content": "go"},
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "call_1", "type": "function",
                 "function": {"name": "bash", "arguments": "{\"command\": \"ls\"}"}}]},
            {"role": "tool", "tool_call_id": "call_1", "name": "bash", "content": "a.txt"},
        ])
        self.assertIn('<tool_call>{"id": "call_1", "name": "bash"', prompt)
        self.assertIn("[tool result call_1] (bash)\na.txt", prompt)

    def test_tools_section_lists_schema(self) -> None:
        section = server._tools_section(TOOLS, "auto")
        self.assertIn("<tool_call>", section)
        self.assertIn("- bash: run", section)

    def test_tool_choice_none(self) -> None:
        self.assertTrue(server._tool_choice_none("none"))
        self.assertFalse(server._tool_choice_none("auto"))


CALL_A = '{"name": "read", "arguments": {"file_path": "/a"}}'
CALL_B = '{"name": "read", "arguments": {"file_path": "/b"}}'
CALL_C = '{"name": "bash", "arguments": {"command": "ls"}}'
PARSED_A = {"name": "read", "arguments": {"file_path": "/a"}}
PARSED_B = {"name": "read", "arguments": {"file_path": "/b"}}
PARSED_C = {"name": "bash", "arguments": {"command": "ls"}}


class _Collector:
    def __init__(self) -> None:
        self.content: list[str] = []
        self.calls: list[dict[str, Any]] = []

    def parser(self) -> server.ToolCallParser:
        return server.ToolCallParser(self.content.append, self.calls.append)


class TestBatchWithoutIntermediateClose(unittest.TestCase):
    """Регрессия: пачка `<tool_call>{..} <tool_call>{..}</tool_call>` уходила в чат сырым текстом."""

    OPEN = server.TOOL_CALL_OPEN
    CLOSE = server.TOOL_CALL_CLOSE

    def test_batch_with_single_shared_close_tag(self) -> None:
        c = _Collector()
        p = c.parser()
        p.feed("Читаю. " + self.OPEN + CALL_A + " " + self.OPEN + CALL_B
               + "\n" + self.OPEN + CALL_C + self.CLOSE)
        p.finish()
        self.assertEqual(c.calls, [PARSED_A, PARSED_B, PARSED_C])
        self.assertEqual("".join(c.content), "Читаю. ")
        self.assertNotIn(self.OPEN, "".join(c.content))
        self.assertEqual(p.tool_calls_count, 3)

    def test_batch_fed_in_chunks(self) -> None:
        c = _Collector()
        p = c.parser()
        head = self.OPEN + CALL_A + " " + self.OPEN + CALL_B
        for i in range(0, len(head), 7):
            p.feed(head[i:i + 7])
        self.assertEqual(c.calls, [])  # до закрывающего тега пачка не разбирается
        self.assertEqual("".join(c.content), "")
        p.feed(self.CLOSE)
        p.finish()
        self.assertEqual(c.calls, [PARSED_A, PARSED_B])
        self.assertEqual("".join(c.content), "")

    def test_mixed_closed_and_unclosed_calls(self) -> None:
        c = _Collector()
        p = c.parser()
        p.feed(self.OPEN + CALL_A + self.CLOSE + self.OPEN + CALL_B
               + self.OPEN + CALL_C + self.CLOSE)
        p.finish()
        self.assertEqual(c.calls, [PARSED_A, PARSED_B, PARSED_C])
        self.assertEqual(p.tool_calls_count, 3)

    def test_open_tag_inside_string_is_not_separator(self) -> None:
        c = _Collector()
        p = c.parser()
        tricky = json.dumps({"name": "t", "arguments": {"text": "x " + self.OPEN + " y"}})
        p.feed(self.OPEN + tricky + " " + self.OPEN + CALL_A + self.CLOSE)
        p.finish()
        self.assertEqual(c.calls, [
            {"name": "t", "arguments": {"text": "x " + self.OPEN + " y"}}, PARSED_A])
        self.assertEqual("".join(c.content), "")

    def test_malformed_member_rejects_whole_batch_as_text(self) -> None:
        c = _Collector()
        p = c.parser()
        p.feed(self.OPEN + '{"name": "a"} ' + self.OPEN + "{broken" + self.CLOSE)
        p.finish()
        self.assertEqual(c.calls, [])
        self.assertIn("{broken", "".join(c.content))
        self.assertEqual(p.tool_calls_count, 0)

    def test_backticked_open_tag_is_not_separator(self) -> None:
        c = _Collector()
        p = c.parser()
        p.feed(self.OPEN + CALL_A + " `" + self.OPEN + "`" + CALL_B + self.CLOSE)
        p.finish()
        self.assertEqual(c.calls, [])
        self.assertIn(CALL_B, "".join(c.content))

    def test_empty_member_rejects_whole_batch_as_text(self) -> None:
        o, cl = self.OPEN, self.CLOSE
        batches = {
            "first": o + o + '{"name":"a"}' + cl,
            "middle": o + '{"name":"a"}' + o + " " + o + '{"name":"b"}' + cl,
            "last": o + '{"name":"a"}' + o + cl,
        }
        for name, raw in batches.items():
            with self.subTest(position=name):
                c = _Collector()
                p = c.parser()
                p.feed(raw)
                p.finish()
                self.assertEqual(c.calls, [])
                self.assertEqual("".join(c.content), raw)
                self.assertEqual(p.tool_calls_count, 0)

    def test_trailing_chars_after_tool_is_chunk_invariant(self) -> None:
        o, cl = self.OPEN, self.CLOSE
        tail = "  a b \n c  "
        expected = len("a b \n c")
        self.assertEqual(expected, 7)
        cases = {
            "single": (o + CALL_A + cl + tail, 1, expected),
            "batch_shared_close": (
                o + CALL_A + " " + o + CALL_B + cl + tail, 2, expected),
            # промежуточный текст до следующего вызова сбрасывается: считается хвост после последнего
            "reset_by_next_call": (
                o + CALL_A + cl + " мусор " + o + CALL_B + cl + tail, 2, expected),
            "reset_without_tail": (
                o + CALL_A + cl + " мусор " + o + CALL_B + cl, 2, 0),
        }
        for name, (text, calls_count, want) in cases.items():
            chunkings: list[tuple[str, list[str]]] = [
                ("whole", [text]), ("char_by_char", list(text))]
            chunkings += [(f"cut_{k}", [text[:k], text[k:]]) for k in range(1, len(text))]
            for mode, chunks in chunkings:
                with self.subTest(case=name, mode=mode):
                    c = _Collector()
                    p = c.parser()
                    for chunk in chunks:
                        p.feed(chunk)
                    p.finish()
                    self.assertEqual(p.tool_calls_count, calls_count)
                    self.assertEqual(p.trailing_chars_after_tool, want)


class TestInlineCodeBatch(unittest.TestCase):
    """Регрессия: пачка `<tool_call>` в inline-backticks — пример-текст, а не вызовы."""

    def _texts(self):
        o, cl = server.TOOL_CALL_OPEN, server.TOOL_CALL_CLOSE
        return {
            "batch": "Пример: `" + o + '{"name":"a"}' + " " + o + '{"name":"b"}' + cl + "`",
            "text_before_tag": "Пример: `пример " + o + '{"name":"a"}' + " " + o + '{"name":"b"}' + cl + "`",
            "space_before_tag": "Пример: ` " + o + '{"name":"a"}' + " " + o + '{"name":"b"}' + cl + "`",
            "single": "Пример: `" + o + '{"name":"a"}' + cl + "`",
            "batch_then_text": "`" + o + '{"name":"a"}' + " " + o + '{"name":"b"}' + cl + "` и дальше",
        }

    def _run(self, text, char_by_char):
        c = _Collector()
        p = c.parser()
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

    def test_real_call_after_closed_text_inline_code_parsed(self):
        o, cl = server.TOOL_CALL_OPEN, server.TOOL_CALL_CLOSE
        quoted = "Пример: `пример " + o + '{"name":"a"}' + " " + o + '{"name":"b"}' + cl + "`"
        text = quoted + " и затем " + o + '{"name":"c"}' + cl
        for char_by_char in (False, True):
            with self.subTest(char_by_char=char_by_char):
                c = self._run(text, char_by_char)
                self.assertEqual(c.calls, [{"name": "c", "arguments": {}}])
                self.assertEqual("".join(c.content), quoted + " и затем ")

    def test_real_call_after_closed_inline_code_still_parsed(self):
        o, cl = server.TOOL_CALL_OPEN, server.TOOL_CALL_CLOSE
        text = "Смотри `код` и " + o + '{"name":"a"}' + cl
        for char_by_char in (False, True):
            with self.subTest(char_by_char=char_by_char):
                c = self._run(text, char_by_char)
                self.assertEqual(c.calls, [{"name": "a", "arguments": {}}])
                self.assertEqual("".join(c.content), "Смотри `код` и ")

    def _run_chunks(self, chunks):
        c = _Collector()
        p = c.parser()
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
        o, cl = server.TOOL_CALL_OPEN, server.TOOL_CALL_CLOSE
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
            for mode, chunks in self._chunkings(text):
                with self.subTest(case=name, mode=mode):
                    c = self._run_chunks(chunks)
                    self.assertEqual(c.calls, calls)
                    self.assertEqual("".join(c.content), content)

    def _escape_and_long_ticks_cases(self):
        o, cl = server.TOOL_CALL_OPEN, server.TOOL_CALL_CLOSE
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
            for mode, chunks in self._chunkings(text):
                with self.subTest(case=name, mode=mode):
                    c = self._run_chunks(chunks)
                    self.assertEqual(c.calls, calls)
                    self.assertEqual("".join(c.content), content)

    def _fence_and_unpaired_cases(self):
        o, cl = server.TOOL_CALL_OPEN, server.TOOL_CALL_CLOSE
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
            for mode, chunks in self._chunkings(text):
                with self.subTest(case=name, mode=mode):
                    c = self._run_chunks(chunks)
                    self.assertEqual(c.calls, calls)
                    self.assertEqual("".join(c.content), content)

    def _tilde_fence_cases(self):
        o, cl = server.TOOL_CALL_OPEN, server.TOOL_CALL_CLOSE
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
            for mode, chunks in self._chunkings(text):
                with self.subTest(case=name, mode=mode):
                    c = self._run_chunks(chunks)
                    self.assertEqual(c.calls, calls)
                    self.assertEqual("".join(c.content), content)

    def test_tilde_json_fence_inside_block_is_real_call(self):
        o, cl = server.TOOL_CALL_OPEN, server.TOOL_CALL_CLOSE
        text = o + "\n~~~json\n" + '{"name":"a"}' + "\n~~~\n" + cl
        for char_by_char in (False, True):
            with self.subTest(char_by_char=char_by_char):
                c = self._run(text, char_by_char)
                self.assertEqual(c.calls, [{"name": "a", "arguments": {}}])
                self.assertEqual("".join(c.content), "")

    def test_json_fence_inside_block_is_real_call(self):
        o, cl = server.TOOL_CALL_OPEN, server.TOOL_CALL_CLOSE
        text = o + "\n```json\n" + '{"name":"a"}' + "\n```\n" + cl
        for char_by_char in (False, True):
            with self.subTest(char_by_char=char_by_char):
                c = self._run(text, char_by_char)
                self.assertEqual(c.calls, [{"name": "a", "arguments": {}}])
                self.assertEqual("".join(c.content), "")

    def _atx_heading_cases(self):
        o, cl = server.TOOL_CALL_OPEN, server.TOOL_CALL_CLOSE
        single = o + '{"name":"a"}' + cl
        call_a = [{"name": "a", "arguments": {}}]
        # `\n` — реальные переводы строк
        hash_no_space = "#x `\n" + single + "\nтекст `"
        return {
            # B1: бэктик в ATX-заголовке не парится с бэктиком из следующего блока
            "atx_heading_tick_then_text": (
                "# Литерал `\n" + single + "\nТекст ` здесь",
                call_a,
                # хвост после вызова парсер этого моста по протоколу не отдаёт
                "# Литерал `\n",
            ),
            # бэктик в абзаце не парится с бэктиком из следующего ATX-заголовка
            "tick_before_atx_heading": (
                "Текст `\n" + single + "\n## Заголовок `x",
                call_a,
                "Текст `\n",
            ),
            # `#` без пробела — не заголовок: inline-код продолжается через строки
            "hash_without_space_is_not_heading": (hash_no_space, [], hash_no_space),
        }

    def test_atx_heading_ends_inline_code_block(self):
        for name, (text, calls, content) in self._atx_heading_cases().items():
            for mode, chunks in self._chunkings(text):
                with self.subTest(case=name, mode=mode):
                    c = self._run_chunks(chunks)
                    self.assertEqual(c.calls, calls)
                    self.assertEqual("".join(c.content), content)

class TestNativeToolMapping(unittest.TestCase):
    """Встроенный инструмент opencode (отклонён permission "ask") -> tool_call DSH."""

    DSH_TOOLS: ClassVar[list[dict[str, Any]]] = [
        {"type": "function", "function": {"name": "bash", "parameters": {
            "type": "object", "required": ["command", "description"],
            "properties": {"command": {"type": "string"}, "description": {"type": "string"},
                           "timeoutMs": {"type": "number"}}}}},
        {"type": "function", "function": {"name": "read", "parameters": {
            "type": "object", "required": ["file_path"],
            "properties": {"file_path": {"type": "string"}, "offset": {"type": "number"}}}}},
    ]

    def test_bash_fills_description(self) -> None:
        call = server._native_to_tool_call("bash", {"command": "pgrep nginx"}, self.DSH_TOOLS)
        self.assertEqual(call, {"name": "bash", "arguments": {
            "command": "pgrep nginx", "description": "bash: pgrep nginx"}})

    def test_read_renames_filepath(self) -> None:
        call = server._native_to_tool_call("read", {"filePath": "/tmp/a", "junk": 1}, self.DSH_TOOLS)
        self.assertEqual(call, {"name": "read", "arguments": {"file_path": "/tmp/a"}})

    def test_unknown_tool_not_mapped(self) -> None:
        self.assertIsNone(server._native_to_tool_call("webfetch", {"url": "x"}, self.DSH_TOOLS))

    def test_missing_required_not_mapped(self) -> None:
        self.assertIsNone(server._native_to_tool_call("read", {"offset": 1}, self.DSH_TOOLS))

    def test_default_config_is_ask_not_deny(self) -> None:
        cfg = json.loads(server.OPENCODE_CONFIG_CONTENT)
        self.assertEqual(cfg["permission"], {"*": "ask"})
        self.assertEqual(
            cfg["provider"]["opencode"]["options"]["baseURL"], "http://127.0.0.1:10830/v1"
        )
        # Статических `models` в конфиге нет: каталог берётся из OPENCODE_MODELS_PATH (свежий api.json).
        self.assertNotIn("models", cfg["provider"]["opencode"])


if __name__ == "__main__":
    unittest.main()
