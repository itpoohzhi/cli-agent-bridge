#!/usr/bin/env python3
"""Regression (порт из droid-bridge, 2026-10-08): блок <tool_call> с СЫРЫМИ переводами
строк/табами внутри JSON-строк. Строгий json.loads падал («Invalid control character»),
блок утекал в content текстом, finish_reason "stop" — DSH заканчивал ход.
"""

from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

import server
from tests._fixtures import install_test_models

install_test_models(server)

O, C = server.TOOL_CALL_OPEN, server.TOOL_CALL_CLOSE
RAW_BLOCK = (O + '{"name": "bash", "arguments": {"command": "python3 -c \\"\nimport os\nprint(1)\n\\"", '
             '"description": "Run multi-line python"}}' + C)


class TestLenientToolCall(unittest.TestCase):
    def test_tests_never_write_to_live_bridge_log(self) -> None:
        live = Path(server.__file__).resolve().parent / "logs" / "bridge.log"
        self.assertNotEqual(Path(server.LOG_PATH).resolve(), live)

    def test_raw_newlines_in_block_parsed_as_call(self) -> None:
        content, calls = server._split_tool_calls(["Запускаю.\n", RAW_BLOCK])
        self.assertEqual(len(calls), 1)
        args = json.loads(calls[0]["function"]["arguments"])
        self.assertEqual(args["command"], 'python3 -c "\nimport os\nprint(1)\n"')
        self.assertNotIn(O, content)

    def test_raw_control_chars_in_string_arguments(self) -> None:
        inner = '{"name": "bash", "arguments": "{\\"command\\": \\"a\nb\\tc\\"}"}'
        self.assertEqual(server._parse_tool_call_block(inner),
                         {"name": "bash", "arguments": {"command": "a\nb\tc"}})

    def test_normalize_arguments_lenient(self) -> None:
        self.assertEqual(server._normalize_arguments('{"c": "a\tb"}'), {"c": "a\tb"})

    def test_negative_control_garbage_still_text_and_logged(self) -> None:
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            content, calls = server._split_tool_calls([O + '{"name": "bash", "arguments": {broken' + C])
        self.assertEqual(calls, [])
        self.assertIn("{broken", content)
        self.assertIn("tool_call_unparsed", err.getvalue())


# Боевой вызов (2026-10-24): лишняя `}` после объекта, bash-heredoc с экранированными/сырыми переводами строк.
_PROD_ESCAPED = ('{"id": "call_1", "name": "bash", "arguments": {"command": "cat > a.py <<\'EOF\'\\nprint({1: 2})'
                 '\\nEOF", "description": "write"}}}')
_PROD_RAW = _PROD_ESCAPED.replace("\\n", "\n")
_PROD_ARGS = {"command": "cat > a.py <<'EOF'\nprint({1: 2})\nEOF", "description": "write"}
_BASE = '{"name": "bash", "arguments": {"command": "ls"}}'
_BASH_LS = {"name": "bash", "arguments": {"command": "ls"}}


class TestTrailingBraceRecovery(unittest.TestCase):
    def test_trailing_braces_recovered(self) -> None:
        for tail in ("}", "}}", "} }\n}", "}}}\n", "}" * 16):
            with self.subTest(tail=tail):
                self.assertEqual(server._parse_tool_call_block(_BASE + tail), _BASH_LS)
                self.assertEqual(server._parse_tool_call_blocks(_BASE + tail), [_BASH_LS])

    def test_production_payload_single_call(self) -> None:
        for label, payload in (("escaped", _PROD_ESCAPED), ("raw_newlines", _PROD_RAW)):
            for open_tag, close_tag in ((O, C), (server.ALT_TOOL_CALL_OPEN, server.ALT_TOOL_CALL_CLOSE)):
                with self.subTest(payload=label, tag=open_tag):
                    content, calls = server._split_tool_calls(["Запускаю.\n", open_tag + payload + close_tag])
                    self.assertEqual(len(calls), 1)
                    self.assertEqual(calls[0]["function"]["name"], "bash")
                    self.assertEqual(json.loads(calls[0]["function"]["arguments"]), _PROD_ARGS)
                    self.assertEqual(content, "Запускаю.\n")

    def test_trailing_garbage_not_recovered(self) -> None:
        bad = (
            '{"name": "bash", "arguments": {}}}, "x": 1}',
            _BASE + '}, "x": 1}',
            _BASE + "}x",
            "[1]}",
            '{"name": "bash", "arguments": {"command": "ls"}',  # недозакрыт
            "{broken",
            _BASE + "}" * 20,  # больше предела лишних скобок
            "[" * 100000,
            '{"a":' * 100000 + "}",  # RecursionError не утекает наружу
        )
        for text in bad:
            with self.subTest(text=text[:40]):
                self.assertIsNone(server._parse_tool_call_block(text))
                self.assertIsNone(server._parse_tool_call_blocks(text))

    def test_recovered_logged_unless_quiet(self) -> None:
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            server._parse_tool_call_blocks(_BASE + "}}")
        self.assertIn("tool_call_recovered extra_braces=2", err.getvalue())
        quiet = io.StringIO()
        with contextlib.redirect_stderr(quiet):
            self.assertEqual(server._parse_tool_call_blocks(_BASE + "}}", quiet=True), [_BASH_LS])
        self.assertNotIn("tool_call_recovered", quiet.getvalue())

    def test_openai_function_wrapper(self) -> None:
        wrapper = json.dumps({"id": "call_1", "type": "function",
                              "function": {"name": "bash", "arguments": json.dumps({"command": "ls"})}})
        self.assertEqual(server._parse_tool_call_block(wrapper), _BASH_LS)
        self.assertEqual(server._parse_tool_call_block(wrapper + "}"), _BASH_LS)
        as_object = json.dumps({"function": {"name": "bash", "arguments": {"command": "ls"}}})
        self.assertEqual(server._parse_tool_call_block(as_object), _BASH_LS)
        # name верхнего уровня всегда побеждает
        both = json.dumps({"name": "bash", "function": {"name": "other", "arguments": {"z": 1}}})
        self.assertEqual(server._parse_tool_call_block(both), {"name": "bash", "arguments": {}})
        # присутствующее, но пустое/не-строковое name — не повод разворачивать обёртку
        for name in ("", "  ", None, 5):
            blank = json.dumps({"name": name, "function": {"name": "other", "arguments": {}}})
            with self.subTest(name=name):
                self.assertIsNone(server._parse_tool_call_block(blank))
        for text in ('{"function": "bash"}', '{"function": ["bash"]}', '{"function": {"arguments": {}}}'):
            with self.subTest(text=text):
                self.assertIsNone(server._parse_tool_call_block(text))

    def test_batch_segment_with_extra_brace(self) -> None:
        second = '{"name": "read", "arguments": {"file_path": "/etc/hosts"}}}'
        content, calls = server._split_tool_calls([O + _BASE + " " + O + second + C])
        self.assertEqual([c["function"]["name"] for c in calls], ["bash", "read"])
        self.assertEqual(content, "")


if __name__ == "__main__":
    unittest.main()
