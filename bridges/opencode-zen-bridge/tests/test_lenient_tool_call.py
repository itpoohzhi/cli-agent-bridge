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


if __name__ == "__main__":
    unittest.main()
