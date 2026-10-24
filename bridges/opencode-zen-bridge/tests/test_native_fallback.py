#!/usr/bin/env python3
"""Regression: отклонённый встроенный инструмент opencode без DSH-двойника (2026-10-08).

Баг (живая сессия DSH 18:46:27): Muse вызвал встроенный `todowrite`, мост не нашёл
DSH-инструмент с тем же именем (`mapped=False`), отдал 87 символов преамбулы и
finish_reason "stop" — DSH завершил ход после одного шага.

Ожидается: (1) встроенные инструменты opencode переводятся в DSH-двойники запроса
(todowrite→todo_write, webfetch→web_fetch, list→bash, task→subagent, multiedit→edit…);
(2) встроенный инструмент без двойника не заканчивает ход молча — мост перезапускает
`opencode run` с сообщением о недоступности и списком DSH-инструментов (ограниченно).
"""

from __future__ import annotations

import json
import os
import socket
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from typing import Any

import server
from tests._fake_cli import allow_child_env
from tests._fixtures import install_test_models

install_test_models(server)

# Реальные схемы DSH-инструментов из сессии владельца (request/header, 08.10 18:45).
DSH_TOOLS = json.loads((Path(__file__).resolve().parent / "dsh_tools_fixture.json").read_text("utf-8"))


def _names(calls: list[dict[str, Any]]) -> list[str]:
    return [c["name"] for c in calls]


class TestNativeAliasMapping(unittest.TestCase):
    def test_todowrite_to_todo_write(self) -> None:
        calls = server._native_to_tool_calls("todowrite", {"todos": [
            {"content": "Посчитать строки", "status": "in_progress", "priority": "high", "id": "1"},
            {"content": "Отчёт", "status": "cancelled", "priority": "low", "id": "2"},
        ]}, DSH_TOOLS)
        self.assertEqual(calls, [{"name": "todo_write", "arguments": {"todos": [
            {"content": "Посчитать строки", "status": "in_progress"},
            {"content": "Отчёт", "status": "completed"},
        ]}}])

    def test_todowrite_without_dsh_todo_not_mapped(self) -> None:
        tools = [t for t in DSH_TOOLS if t["function"]["name"] != "todo_write"]
        self.assertEqual(server._native_to_tool_calls("todowrite", {"todos": []}, tools), [])

    def test_webfetch_to_web_fetch(self) -> None:
        calls = server._native_to_tool_calls(
            "webfetch", {"url": "https://example.com", "format": "markdown"}, DSH_TOOLS)
        self.assertEqual(calls, [{"name": "web_fetch", "arguments": {"url": "https://example.com"}}])

    def test_websearch_to_mcp_search(self) -> None:
        calls = server._native_to_tool_calls("websearch", {"query": "opencode zen"}, DSH_TOOLS)
        self.assertEqual(_names(calls), ["mcp__web-search-prime__web_search_prime"])
        self.assertEqual(calls[0]["arguments"], {"search_query": "opencode zen"})

    def test_list_to_bash_ls(self) -> None:
        calls = server._native_to_tool_calls("list", {"path": "/etc"}, DSH_TOOLS)
        self.assertEqual(_names(calls), ["bash"])
        self.assertEqual(calls[0]["arguments"]["command"], "ls -la /etc")
        self.assertTrue(calls[0]["arguments"]["description"])

    def test_task_to_subagent(self) -> None:
        calls = server._native_to_tool_calls("task", {
            "description": "Count lines", "prompt": "wc -l /etc/shells", "subagent_type": "general"}, DSH_TOOLS)
        self.assertEqual(calls, [{"name": "subagent", "arguments": {
            "description": "Count lines", "prompt": "wc -l /etc/shells"}}])

    def test_multiedit_to_several_edits(self) -> None:
        calls = server._native_to_tool_calls("multiedit", {"filePath": "/tmp/a", "edits": [
            {"oldString": "a", "newString": "b"},
            {"oldString": "c", "newString": "d", "replaceAll": True},
        ]}, DSH_TOOLS)
        self.assertEqual(calls, [
            {"name": "edit", "arguments": {"file_path": "/tmp/a", "old_string": "a", "new_string": "b"}},
            {"name": "edit", "arguments": {"file_path": "/tmp/a", "old_string": "c", "new_string": "d",
                                           "replace_all": True}},
        ])

    def test_same_name_still_mapped(self) -> None:
        calls = server._native_to_tool_calls("read", {"filePath": "/etc/shells"}, DSH_TOOLS)
        self.assertEqual(calls, [{"name": "read", "arguments": {"file_path": "/etc/shells"}}])

    def test_no_counterpart(self) -> None:
        self.assertEqual(server._native_to_tool_calls("lsp", {"operation": "hover"}, DSH_TOOLS), [])
        self.assertEqual(server._native_to_tool_calls("todoread", {}, DSH_TOOLS), [])

    def test_retry_prompt_lists_tools(self) -> None:
        text = server._unavailable_tools_prompt("BASE", "Смотрю", ["todoread"], DSH_TOOLS)
        self.assertTrue(text.startswith("BASE"))
        self.assertIn("todoread", text)
        self.assertIn("todo_write", text)
        self.assertIn("<tool_call>", text)


FAKE_OPENCODE = r'''#!/usr/bin/env python3
import json, os, sys
counter = os.environ["FAKE_OC_COUNTER"]
n = int(open(counter).read()) if os.path.exists(counter) else 0
open(counter, "w").write(str(n + 1))
with open(counter + ".prompts", "a") as fh:
    fh.write(json.dumps(sys.stdin.read()) + "\n")
def ev(o): print(json.dumps(o), flush=True)
if os.environ.get("FAKE_OC_MODE") == "dup":
    # Живой замер 18:55: после «отклонения» Muse повторяет тот же вызов следующим шагом.
    todo = {"todos": [{"content": "a", "status": "pending"}]}
    ev({"type": "tool_use", "part": {"tool": "read", "state": {"status": "error", "input": {"filePath": "/etc/shells"}}}})
    ev({"type": "tool_use", "part": {"tool": "todowrite", "state": {"status": "error", "input": todo}}})
    ev({"type": "tool_use", "part": {"tool": "todowrite", "state": {"status": "error", "input": todo}}})
    ev({"type": "step_finish", "part": {"tokens": {"input": 10, "output": 5}}})
    ev({"type": "text", "part": {"text": "Повторяю."}})
    ev({"type": "tool_use", "part": {"tool": "bash", "state": {"status": "error", "input": {"command": "rm -rf x"}}}})
    ev({"type": "step_finish", "part": {"tokens": {"input": 10, "output": 5}}})
elif n == 0:
    ev({"type": "text", "part": {"text": "Составляю план."}})
    ev({"type": "tool_use", "part": {"tool": "todoread", "state": {"status": "error", "input": {}}}})
else:
    ev({"type": "tool_use", "part": {"tool": "bash", "state": {"status": "error",
        "input": {"command": "wc -l /etc/shells"}}}})
ev({"type": "step_finish", "part": {"tokens": {"input": 10, "output": 5}}})
'''


class TestUnmappedToolRetryLive(unittest.TestCase):
    """HTTP-мост с фейковым opencode: первый прогон зовёт todoread (двойника нет)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        fake = Path(cls.tmp.name) / "opencode"
        fake.write_text(FAKE_OPENCODE, "utf-8")
        fake.chmod(0o755)
        cls.saved = (server.OPENCODE_BIN, server.AUTH_KEY, server.DEFAULTWORKDIR, server.LOG_PATH)
        cls.env_patch = allow_child_env("FAKE_OC_COUNTER", "FAKE_OC_MODE")
        cls.env_patch.start()
        server.OPENCODE_BIN = str(fake)
        server.AUTH_KEY = "test-key"
        server.DEFAULTWORKDIR = Path(cls.tmp.name) / "ws"
        server.LOG_PATH = Path(cls.tmp.name) / "bridge.log"
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            cls.port = s.getsockname()[1]
        cls.httpd = server.Server(("127.0.0.1", cls.port), server.Handler)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.env_patch.stop()
        server.OPENCODE_BIN, server.AUTH_KEY, server.DEFAULTWORKDIR, server.LOG_PATH = cls.saved
        cls.tmp.cleanup()

    counter: Path = Path()

    def setUp(self) -> None:
        self.counter = Path(self.tmp.name) / f"counter-{self.id()}"
        os.environ["FAKE_OC_COUNTER"] = str(self.counter)

    def tearDown(self) -> None:
        os.environ.pop("FAKE_OC_COUNTER", None)
        os.environ.pop("FAKE_OC_MODE", None)

    def _stream_calls(self) -> list[str]:
        raw = self._post(stream=True).decode()
        return [tc["function"]["name"] for line in raw.splitlines() if line.startswith("data: {")
                for tc in json.loads(line[6:])["choices"][0]["delta"].get("tool_calls") or []]

    def test_stream_stops_after_step_and_dedupes(self) -> None:
        os.environ["FAKE_OC_MODE"] = "dup"
        self.assertEqual(self._stream_calls(), ["read", "todo_write"])

    def test_json_stops_after_step_and_dedupes(self) -> None:
        os.environ["FAKE_OC_MODE"] = "dup"
        out = json.loads(self._post(stream=False))
        names = [c["function"]["name"] for c in out["choices"][0]["message"]["tool_calls"]]
        self.assertEqual(names, ["read", "todo_write"])
        self.assertNotIn("Повторяю", out["choices"][0]["message"]["content"] or "")

    def _post(self, stream: bool) -> bytes:
        body = json.dumps({"model": "muse-spark-1.3-contributor-free", "stream": stream,
                           "messages": [{"role": "user", "content": "составь план и выполни"}],
                           "tools": DSH_TOOLS}).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/chat/completions", data=body,
                                     headers={"Authorization": "Bearer test-key",
                                              "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()

    def _runs(self) -> int:
        return int(self.counter.read_text())

    def test_stream_retries_and_returns_tool_call(self) -> None:
        raw = self._post(stream=True).decode()
        chunks = [json.loads(line[6:]) for line in raw.splitlines()
                  if line.startswith("data: {")]
        finishes = [c["choices"][0].get("finish_reason") for c in chunks if c["choices"][0].get("finish_reason")]
        calls = [tc for c in chunks for tc in c["choices"][0]["delta"].get("tool_calls") or []]
        self.assertEqual(self._runs(), 2)
        self.assertEqual(finishes, ["tool_calls"])
        self.assertEqual([c["function"]["name"] for c in calls], ["bash"])
        retry_prompt = json.loads((Path(str(self.counter) + ".prompts")).read_text().splitlines()[1])
        self.assertIn("todoread", retry_prompt)

    def test_json_retries_and_returns_tool_call(self) -> None:
        out = json.loads(self._post(stream=False))
        choice = out["choices"][0]
        self.assertEqual(self._runs(), 2)
        self.assertEqual(choice["finish_reason"], "tool_calls")
        self.assertEqual([c["function"]["name"] for c in choice["message"]["tool_calls"]], ["bash"])


if __name__ == "__main__":
    unittest.main()
