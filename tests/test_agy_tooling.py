"""Эмуляция OpenAI function calling в agy-bridge (ядро `core.tool_emulation`).

Сквозные тесты через настоящий HTTP-сервер моста и фейковый agy (NDJSON stream-json):
`<tool_call>` из текста хода -> `delta.tool_calls` (SSE) / `message.tool_calls` (JSON)
с `finish_reason="tool_calls"`; без tools и при `tool_choice="none"` — текстовый ход
с `finish_reason="stop"`. После закрытого `</tool_call>` фейк «висит» (имитация фоновых
задач CLI): ход обязан завершиться сразу, не дожидаясь его.

Мост лежит в каталоге с дефисом, поэтому грузится через `importlib`. Реальный HOME не
трогается: `_prepare_agy_home` и каталоги моста подменяются временными.
"""

from __future__ import annotations

import contextlib
import http.client
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BRIDGE_PY = _REPO_ROOT / "bridges" / "agy-bridge" / "server.py"

# Порог «ход не завис»: фейк после </tool_call> спит _HANG_S, ответ обязан прийти раньше.
_HANG_S = 30.0
_NO_HANG_BUDGET_S = 10.0

_FAKE_AGY = """
import json, os, sys, time, uuid

scen = json.load(open(os.environ["FAKE_TOOLING_SCENARIO"], encoding="utf-8"))
with open(scen["argv_log"], "w", encoding="utf-8") as fh:
    json.dump(sys.argv[1:], fh)
line = sys.stdin.readline()
try:
    text = json.loads(line)["message"]["content"][0]["text"]
except (ValueError, KeyError, IndexError, TypeError):
    text = line
with open(scen["prompt_log"], "w", encoding="utf-8") as fh:
    fh.write(text)

def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\\n")
    sys.stdout.flush()

cid = str(uuid.uuid4())
emit({"event": "init", "conversation_id": cid, "init": {"tools": [], "permission_mode": "x"}})
time.sleep(scen.get("pre_sleep_s", 0))
for delta in scen["deltas"]:
    time.sleep(0.02)
    emit({"event": "step_update", "step_update": {
        "step_type": "agent_response", "step_index": 1, "text_delta": delta}})
time.sleep(scen.get("hang_s", 0))
emit({"event": "result", "result": {
    "response": "".join(scen["deltas"]), "status": "OK", "conversation_id": cid,
    "usage": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5}}})
"""

_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    }
]
_CALL_ARGS = {"path": "a.txt", "content": "x"}
_TOOL_DELTAS = [
    "Создаю файл.",
    '<tool_call>{"name": "write_file", "arguments": ',
    json.dumps(_CALL_ARGS) + "}",
    "</tool_call>",
]


def _load_bridge() -> Any:
    os.environ.setdefault("AGY_BRIDGE_KEY", "test-key-agy-tooling")
    spec = importlib.util.spec_from_file_location(
        "agy_bridge_server_tooling_under_test", _BRIDGE_PY
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class AgyToolingTests(unittest.TestCase):
    """Сквозная эмуляция tools: HTTP-сервер моста + фейковый agy."""

    srv: Any = None
    server: Any = None
    port: int = 0
    tmp: Path = Path()
    scenario: Path = Path()
    prompt_log: Path = Path()
    argv_log: Path = Path()

    @classmethod
    def setUpClass(cls) -> None:
        cls.srv = _load_bridge()

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="agy-tooling-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        fake = self.tmp / "fake-agy.py"
        _ = fake.write_text("#!" + sys.executable + "\n" + _FAKE_AGY, encoding="utf-8")
        fake.chmod(0o755)
        agy_bin = self.tmp / "agy.real"
        _ = agy_bin.write_text("agy-fixture-binary", encoding="utf-8")
        clean_home = self.tmp / "clean-home"
        clean_home.mkdir()
        for name in ("brain", "conv"):
            (self.tmp / name).mkdir()
        patches = {
            "LAUNCHER": str(fake),
            "AGY_BIN": str(agy_bin),
            "WORKSPACE": self.tmp / "ws",
            "BRAIN_DIR": self.tmp / "brain",
            "CONV_DIR": self.tmp / "conv",
            "DYNAMIC_CONFIG_PATH": self.tmp / "dynamic_config.json",
            "_prepare_agy_home": lambda: clean_home,
        }
        for name, value in patches.items():
            _ = stack.enter_context(mock.patch.object(self.srv, name, value))
        self.scenario = self.tmp / "scenario.json"
        self.prompt_log = self.tmp / "prompt.txt"
        self.argv_log = self.tmp / "argv.json"
        env = {
            "FAKE_TOOLING_SCENARIO": str(self.scenario),
            "AGY_BRIDGE_SESSIONS_FILE": str(self.tmp / "sessions.json"),
            "AGY_SQLITE_REASONING_ENABLED": "0",
        }
        _ = stack.enter_context(mock.patch.dict(os.environ, env))
        for key in (
            "AGY_TOOL_EMULATION_ENABLED",
            "AGY_PLANNER_CONTENT_STREAMING_ENABLED",
        ):
            _ = os.environ.pop(key, None)
        self.srv._session_store.clear()
        self.srv._in_flight_cids.clear()
        self.addCleanup(self.srv._session_store.clear)
        self.server = self.srv.Server(("127.0.0.1", 0), self.srv.Handler)
        self.port = self.server.server_address[1]
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 10)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    # ---- helpers -------------------------------------------------------------------
    def _scenario(
        self, deltas: list[str], hang_s: float = 0.0, pre_sleep_s: float = 0.0
    ) -> None:
        body = {
            "deltas": deltas,
            "hang_s": hang_s,
            "pre_sleep_s": pre_sleep_s,
            "prompt_log": str(self.prompt_log),
            "argv_log": str(self.argv_log),
        }
        _ = self.scenario.write_text(json.dumps(body), encoding="utf-8")

    def _post(self, body: dict[str, Any]) -> tuple[int, bytes, float]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + str(self.srv.AUTH_KEY),
        }
        started = time.monotonic()
        conn.request(
            "POST", "/v1/chat/completions", body=json.dumps(body), headers=headers
        )
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        return response.status, raw, time.monotonic() - started

    @staticmethod
    def _body(stream: bool, **extra: Any) -> dict[str, Any]:
        body: dict[str, Any] = {
            "messages": [{"role": "user", "content": "создай файл a.txt"}],
            "stream": stream,
        }
        body.update(extra)
        return body

    @staticmethod
    def _sse_chunks(raw: bytes) -> tuple[list[dict[str, Any]], list[str]]:
        frames = [
            line[len("data: ") :]
            for line in raw.decode("utf-8").splitlines()
            if line.startswith("data: ")
        ]
        chunks = [json.loads(f) for f in frames if f != "[DONE]"]
        return chunks, frames

    def _argv_mode(self) -> str:
        argv = json.loads(self.argv_log.read_text(encoding="utf-8"))
        return str(argv[argv.index("--mode") + 1])

    # ---- tests ---------------------------------------------------------------------
    def test_streaming_tool_call_emits_delta_tool_calls(self) -> None:
        self._scenario(_TOOL_DELTAS, hang_s=_HANG_S)
        status, raw, elapsed = self._post(self._body(True, tools=_TOOLS))
        self.assertEqual(status, 200)
        self.assertLess(elapsed, _NO_HANG_BUDGET_S, "ход ждал фоновый процесс agy")
        chunks, frames = self._sse_chunks(raw)
        self.assertEqual(frames[-1], "[DONE]")
        deltas = [c["choices"][0]["delta"] for c in chunks]
        calls = [call for d in deltas for call in d.get("tool_calls") or []]
        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertEqual(call["index"], 0)
        self.assertEqual(call["type"], "function")
        self.assertTrue(str(call["id"]).startswith("call_"))
        self.assertEqual(call["function"]["name"], "write_file")
        self.assertEqual(json.loads(call["function"]["arguments"]), _CALL_ARGS)
        content = "".join(str(d.get("content") or "") for d in deltas)
        self.assertNotIn("<tool_call>", content)
        self.assertNotIn("</tool_call>", content)
        self.assertIn("Создаю файл.", content)
        finishes = [c["choices"][0]["finish_reason"] for c in chunks]
        self.assertIn("tool_calls", finishes)
        self.assertNotIn("stop", finishes)
        prompt = self.prompt_log.read_text(encoding="utf-8")
        self.assertIn("# Tool calling protocol", prompt)
        self.assertIn("write_file", prompt)
        self.assertNotEqual(self._argv_mode(), "auto")

    def test_json_tool_call_returns_message_tool_calls(self) -> None:
        self._scenario(_TOOL_DELTAS, hang_s=_HANG_S)
        status, raw, elapsed = self._post(self._body(False, tools=_TOOLS))
        self.assertEqual(status, 200)
        self.assertLess(elapsed, _NO_HANG_BUDGET_S, "ход ждал фоновый процесс agy")
        payload = json.loads(raw.decode("utf-8"))
        choice = payload["choices"][0]
        self.assertEqual(choice["finish_reason"], "tool_calls")
        message = choice["message"]
        calls = message["tool_calls"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["type"], "function")
        self.assertTrue(str(calls[0]["id"]).startswith("call_"))
        self.assertEqual(calls[0]["function"]["name"], "write_file")
        self.assertEqual(json.loads(calls[0]["function"]["arguments"]), _CALL_ARGS)
        self.assertNotIn("<tool_call>", str(message.get("content") or ""))
        self.assertEqual(message["content"], "Создаю файл.")

    def test_text_only_request_returns_stop_finish_reason(self) -> None:
        self._scenario(["Привет", ", мир."])
        status, raw, _elapsed = self._post(self._body(True))
        self.assertEqual(status, 200)
        chunks, frames = self._sse_chunks(raw)
        self.assertEqual(frames[-1], "[DONE]")
        deltas = [c["choices"][0]["delta"] for c in chunks]
        self.assertFalse(any(d.get("tool_calls") for d in deltas))
        self.assertEqual(
            "".join(str(d.get("content") or "") for d in deltas), "Привет, мир."
        )
        finishes = {c["choices"][0]["finish_reason"] for c in chunks} - {None}
        self.assertEqual(finishes, {"stop"})
        self.assertNotIn("# Tool calling protocol", self.prompt_log.read_text("utf-8"))

        self._scenario(["Привет", ", мир."])
        status, raw, _elapsed = self._post(self._body(False))
        self.assertEqual(status, 200)
        choice = json.loads(raw.decode("utf-8"))["choices"][0]
        self.assertEqual(choice["finish_reason"], "stop")
        self.assertEqual(choice["message"]["content"], "Привет, мир.")
        self.assertNotIn("tool_calls", choice["message"])

    def test_quiet_upstream_before_tool_call_keeps_turn_alive(self) -> None:
        """Регресс: проверка watchdog в тихой итерации не ломает хук завершения хода."""
        self._scenario(_TOOL_DELTAS, hang_s=_HANG_S, pre_sleep_s=1.6)
        with mock.patch.object(self.srv, "WATCHDOG_INTERVAL_S", 0.1):
            status, raw, elapsed = self._post(self._body(False, tools=_TOOLS))
        self.assertEqual(status, 200)
        self.assertLess(elapsed, _NO_HANG_BUDGET_S, "ход ждал фоновый процесс agy")
        choice = json.loads(raw.decode("utf-8"))["choices"][0]
        self.assertEqual(choice["finish_reason"], "tool_calls")
        self.assertEqual(
            choice["message"]["tool_calls"][0]["function"]["name"], "write_file"
        )

    def test_tool_choice_none_disables_tool_emulation(self) -> None:
        raw_block = '<tool_call>{"name": "write_file", "arguments": {}}</tool_call>'
        self._scenario(["Текст ", raw_block])
        body = self._body(False, tools=_TOOLS, tool_choice="none")
        status, raw, _elapsed = self._post(body)
        self.assertEqual(status, 200)
        choice = json.loads(raw.decode("utf-8"))["choices"][0]
        self.assertEqual(choice["finish_reason"], "stop")
        self.assertNotIn("tool_calls", choice["message"])
        self.assertEqual(choice["message"]["content"], "Текст " + raw_block)
        self.assertNotIn("# Tool calling protocol", self.prompt_log.read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
