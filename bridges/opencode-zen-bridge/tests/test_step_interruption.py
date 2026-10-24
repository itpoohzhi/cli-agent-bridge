#!/usr/bin/env python3
"""Regression: оборванный/незавершённый инструментальный шаг glm-5.3-flash-free (2026-10-24).

Симптом 1 (ECONNRESET посреди ответа): `opencode run` продолжал сам (SYNTHETIC «The previous
response was interrupted…»), модель отвечала «I was interrupted right before making tool calls…»,
текст склеивался с преамбулой, шаг заканчивался `stop` без инструментов.
Симптом 2 (rc=0, tools=0): модель спланировала вызовы в reasoning, выдала статусную преамбулу
и остановилась без `<tool_call>`.

Ожидается: мост останавливает оборванный `opencode run`, не пропускает «I was interrupted…» в
content, распознаёт незавершённый шаг и перезапрашивает модель — клиент получает tool_calls.
"""

from __future__ import annotations

import itertools
import json
import os
import re
import socket
import tempfile
import threading
import time
import types
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from unittest import mock

import server
from tests._fake_cli import allow_child_env
from tests._fixtures import install_test_models

install_test_models(server)
GLM_MODEL = "glm-5.3-flash-free"
server.ALLOWED_MODELS.setdefault(GLM_MODEL, {"context_length": 200000, "max_output": 131072,
                                             "supports_variant": True})

DSH_TOOLS = json.loads((Path(__file__).resolve().parent / "dsh_tools_fixture.json").read_text("utf-8"))
TOOLS = [
    {"type": "function", "function": {
        "name": "job_output", "description": "Read output of a background job",
        "parameters": {"type": "object", "properties": {"job_id": {"type": "string"}},
                       "required": ["job_id"]}}},
    {"type": "function", "function": {
        "name": "bash", "description": "Run a shell command",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"},
                                                        "description": {"type": "string"}},
                       "required": ["command", "description"]}}},
]

PREAMBLE = "**2026-10-24 13:55 MSK — статус.** Фетч был завершён (exit 0) — забираю вывод."
STATUS_ONLY = ("**2026-10-24 13:56 MSK — статус по цели (обновляю туду каждую минуту).** "
               "Собираю факты: вывод fetch-джобы, состояние данных.\n")
PLAN = ("One message: job_output(bash-4a99049e1f764309) + bash check state.json. "
        "Let me do: 1. job_output for fetch 2. bash: cat state.json")
CALLS = ('<tool_call>{"name": "job_output", "arguments": {"job_id": "bash-4a99"}}</tool_call>'
         '<tool_call>{"name": "bash", "arguments": {"command": "cat state.json", '
         '"description": "Show state"}}</tool_call>')
INVOKE_CALLS = CALLS.replace("tool_call", "tool_invoke")
# Реальный шаг glm-5.3-flash-free: апстрим вырезал `<tool_call>…` из text, а 97 токенов выставил.
SWALLOWED_TEXT = "2026-10-24 (MSK) — статус: проверяю вывод джобы job_fetch_01 и читаю goal.md."

FAKE_OPENCODE = r'''#!/usr/bin/env python3
import json, os, sys, time
counter = os.environ["FAKE_OC_COUNTER"]
n = int(open(counter).read()) if os.path.exists(counter) else 0
open(counter, "w").write(str(n + 1))
with open(counter + ".prompts", "a") as fh:
    fh.write(json.dumps(sys.stdin.read()) + "\n")
mode = os.environ.get("FAKE_OC_MODE", "")
def ev(o): print(json.dumps(o), flush=True)
def text(t): ev({"type": "text", "part": {"text": t}})
def reasoning(t): ev({"type": "reasoning", "part": {"text": t}})
def finish(out=5): ev({"type": "step_finish", "part": {"tokens": {"input": 10, "output": out}}})
calls = os.environ["FAKE_OC_CALLS"]
if mode == "econnreset" and n == 0:
    reasoning(os.environ["FAKE_OC_PLAN"])
    text(os.environ["FAKE_OC_PREAMBLE"])
    ev({"type": "error", "error": {"name": "APIError", "data": {
        "message": "provider.transport: Connection lost while reading the response: ECONNRESET"}}})
    time.sleep(2)
    # Сюда opencode попадает сам (SYNTHETIC-продолжение), если мост не остановил процесс.
    open(counter + ".second_step", "w").write("reached")
    reasoning("I was interrupted right before making tool calls. Continue.")
    text("I was interrupted right before making tool calls. Continue: collect output.")
    finish()
elif mode == "promise" and n == 0:
    reasoning(os.environ["FAKE_OC_PLAN"])
    text(os.environ["FAKE_OC_STATUS"])
    finish()
elif mode == "swallowed" and n == 0:
    text(os.environ["FAKE_OC_SWALLOW"])
    finish(97)
elif mode == "plain":
    reasoning("Simple greeting per Rule 0, no tools needed")
    text("Привет!")
    finish()
elif mode == "early_error" and n == 0:
    # Ошибка ДО первого токена: мост не должен убивать proc (opencode вправе восстановиться сам).
    ev({"type": "error", "error": {"name": "APIError", "data": {
        "message": "provider.transport: Connection lost: ECONNRESET"}}})
    time.sleep(1)
    open(counter + ".survived", "w").write("yes")
    text(calls)
    finish()
elif mode == "unmapped_then_error" and n == 0:
    ev({"type": "tool_use", "part": {"tool": "todoread", "state": {"status": "error", "input": {}}}})
    ev({"type": "error", "error": {"name": "APIError", "data": {
        "message": "provider.transport: Connection lost: ECONNRESET"}}})
    time.sleep(2)
    open(counter + ".second_step", "w").write("reached")
    finish()
elif mode == "early_error_plain":
    # Ошибка ДО первого токена, затем opencode сам восстановился и дал короткий текстовый ответ.
    ev({"type": "error", "error": {"name": "APIError", "data": {
        "message": "provider.transport: Connection lost: ECONNRESET"}}})
    time.sleep(1)
    text("Готово, проверил.")
    finish()
elif mode == "reasoning_interrupted":
    reasoning("The previous response was interrupted. Continue from where you left off without repeating completed content.")
    reasoning("Simple greeting.")
    text("Привет!")
    finish()
elif mode == "unmapped_then_promise" and n < 1:
    ev({"type": "tool_use", "part": {"tool": "todoread", "state": {"status": "error", "input": {}}}})
    finish()
elif mode == "unmapped_then_promise" and n == 1:
    reasoning(os.environ["FAKE_OC_PLAN"])
    text(os.environ["FAKE_OC_STATUS"])
    finish()
elif mode == "unmapped_then_promise_forever":
    if n == 0:
        ev({"type": "tool_use", "part": {"tool": "todoread", "state": {"status": "error", "input": {}}}})
        finish()
    else:
        reasoning(os.environ["FAKE_OC_PLAN"])
        text(os.environ["FAKE_OC_STATUS"])
        finish()
elif mode == "unmapped_forever":
    ev({"type": "tool_use", "part": {"tool": "todoread", "state": {"status": "error", "input": {}}}})
    finish()
elif mode == "always_promise":
    reasoning(os.environ["FAKE_OC_PLAN"])
    text(os.environ["FAKE_OC_STATUS"])
    finish()
elif mode == "locked_then_promise":
    if n == 0:
        sys.stderr.write("Error: Unexpected error\n\ndatabase is locked\n")
        sys.exit(1)
    reasoning(os.environ["FAKE_OC_PLAN"])
    text(os.environ["FAKE_OC_STATUS"])
    finish()
elif mode == "slow_promise" and n == 0:
    time.sleep(float(os.environ.get("FAKE_OC_DELAY", "0.4")))
    text("Checking state...")
    finish()
elif mode == "rephrase":
    if n == 0:
        text("Checking state...")
        finish()
    else:
        text("Here is the result" + calls)
        finish()
elif mode == "repeat_prefix":
    if n == 0:
        text("Checking state...")
        finish()
    else:
        text("Checking state..." + calls)
        finish()
elif mode == "error401":
    text(os.environ["FAKE_OC_PREAMBLE"])
    ev({"type": "error", "error": {"name": "APIError", "data": {"statusCode": 401, "message": "api_key_expired"}}})
    time.sleep(2)
    open(counter + ".second_step", "w").write("reached")
    finish()
else:
    text(calls)
    finish()
'''


def fresh_resilience() -> Any:
    """Изолированный набор защит; лимитер запусков ускорен (его темп проверяется отдельно, на FakeClock)."""
    res = server._Resilience()
    res.spawn_limiter = server._SpawnRateLimiter(1000.0, 1000.0)
    return res


class FakeClock:
    """Детерминированные часы: sleep двигает время, реального ожидания нет."""

    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class TestStepInterruptionLive(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        fake = Path(cls.tmp.name) / "opencode"
        fake.write_text(FAKE_OPENCODE, "utf-8")
        fake.chmod(0o755)
        cls.saved = (server.OPENCODE_BIN, server.AUTH_KEY, server.DEFAULTWORKDIR, server.LOG_PATH,
                     server.FAIL_RETRY_BACKOFF_S)
        cls.env_patch = allow_child_env("FAKE_OC_COUNTER", "FAKE_OC_MODE", "FAKE_OC_PLAN", "FAKE_OC_DELAY",
                                        "FAKE_OC_PREAMBLE", "FAKE_OC_STATUS", "FAKE_OC_CALLS", "FAKE_OC_SWALLOW")
        cls.env_patch.start()
        server.FAIL_RETRY_BACKOFF_S = 0.0  # без пауз между повторами в живых тестах
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
        (server.OPENCODE_BIN, server.AUTH_KEY, server.DEFAULTWORKDIR, server.LOG_PATH,
         server.FAIL_RETRY_BACKOFF_S) = cls.saved
        cls.tmp.cleanup()

    counter: Path = Path()

    def setUp(self) -> None:
        self.counter = Path(self.tmp.name) / f"counter-{self.id()}"
        os.environ["FAKE_OC_COUNTER"] = str(self.counter)
        # Свежие защиты на каждый тест (Retry Budget и Breaker process-level): изоляция тестов друг от друга.
        self.res = fresh_resilience()
        self.httpd.resilience = self.res
        os.environ["FAKE_OC_PLAN"] = PLAN
        os.environ["FAKE_OC_PREAMBLE"] = PREAMBLE
        os.environ["FAKE_OC_STATUS"] = STATUS_ONLY
        os.environ["FAKE_OC_CALLS"] = CALLS
        os.environ["FAKE_OC_SWALLOW"] = SWALLOWED_TEXT

    def tearDown(self) -> None:
        for name in ("FAKE_OC_COUNTER", "FAKE_OC_MODE", "FAKE_OC_PLAN", "FAKE_OC_PREAMBLE", "FAKE_OC_DELAY",
                     "FAKE_OC_STATUS", "FAKE_OC_CALLS", "FAKE_OC_SWALLOW"):
            os.environ.pop(name, None)

    def _post(self, stream: bool, model: str = "muse-spark-1.3-contributor-free",
              messages: list[dict[str, Any]] | None = None) -> bytes:
        body = json.dumps({"model": model, "stream": stream,
                           "messages": messages or [{"role": "user", "content": "продолжай цель"}],
                           "tools": TOOLS}).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/chat/completions", data=body,
                                     headers={"Authorization": "Bearer test-key",
                                              "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()

    def _runs(self) -> int:
        return int(self.counter.read_text())

    def _prompts(self) -> list[str]:
        return [json.loads(line) for line in Path(str(self.counter) + ".prompts").read_text().splitlines()]

    def _stream(self, model: str = "muse-spark-1.3-contributor-free",
                messages: list[dict[str, Any]] | None = None) -> tuple[str, list[str], list[str]]:
        raw = self._post(stream=True, model=model, messages=messages).decode()
        chunks = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: {")]
        content = "".join(c["choices"][0]["delta"].get("content") or "" for c in chunks)
        finishes = [c["choices"][0]["finish_reason"] for c in chunks if c["choices"][0].get("finish_reason")]
        names = [tc["function"]["name"] for c in chunks
                 for tc in c["choices"][0]["delta"].get("tool_calls") or []]
        return content, finishes, names

    def _assert_reprompt(self) -> None:
        retry_prompt = self._prompts()[1]
        self.assertIn(PREAMBLE if os.environ["FAKE_OC_MODE"] == "econnreset" else STATUS_ONLY.strip(),
                      retry_prompt)
        self.assertIn("<tool_call>", retry_prompt.rsplit("[system]", 1)[1])
        self.assertIn("job_output", retry_prompt.rsplit("[system]", 1)[1])

    # --- Симптом 1: ECONNRESET ---------------------------------------------------------

    def test_econnreset_stream_stops_proc_and_reprompts(self) -> None:
        os.environ["FAKE_OC_MODE"] = "econnreset"
        content, finishes, names = self._stream()
        self.assertEqual(self._runs(), 2)
        self.assertFalse(Path(str(self.counter) + ".second_step").exists(), "proc must be stopped on error")
        self.assertNotIn("interrupted", content)
        self.assertIn("забираю вывод", content)
        self.assertEqual(names, ["job_output", "bash"])
        self.assertEqual(finishes, ["tool_calls"])
        self._assert_reprompt()

    def test_econnreset_json_stops_proc_and_reprompts(self) -> None:
        os.environ["FAKE_OC_MODE"] = "econnreset"
        out = json.loads(self._post(stream=False))
        choice = out["choices"][0]
        self.assertEqual(self._runs(), 2)
        self.assertFalse(Path(str(self.counter) + ".second_step").exists(), "proc must be stopped on error")
        self.assertNotIn("interrupted", choice["message"]["content"])
        self.assertEqual([c["function"]["name"] for c in choice["message"]["tool_calls"]],
                         ["job_output", "bash"])
        self.assertEqual(choice["finish_reason"], "tool_calls")
        self._assert_reprompt()

    # --- Симптом 2: статусная преамбула без <tool_call> --------------------------------

    def test_promise_without_tool_call_stream_reprompts(self) -> None:
        os.environ["FAKE_OC_MODE"] = "promise"
        content, finishes, names = self._stream()
        self.assertEqual(self._runs(), 2)
        self.assertEqual(names, ["job_output", "bash"])
        self.assertEqual(finishes, ["tool_calls"])
        self.assertIn("Собираю факты", content)
        self.assertEqual(content.count("Собираю факты"), 1)
        self._assert_reprompt()

    def test_promise_without_tool_call_json_reprompts(self) -> None:
        os.environ["FAKE_OC_MODE"] = "promise"
        out = json.loads(self._post(stream=False))
        choice = out["choices"][0]
        self.assertEqual(self._runs(), 2)
        self.assertEqual([c["function"]["name"] for c in choice["message"]["tool_calls"]],
                         ["job_output", "bash"])
        self.assertEqual(choice["finish_reason"], "tool_calls")
        self._assert_reprompt()

    # --- GLM: протокол на <tool_invoke>, проглоченный <tool_call> --------------------------

    def _assert_no_tool_call_token(self) -> None:
        for prompt in self._prompts():
            self.assertNotIn("tool_call", prompt)
            self.assertIn("<tool_invoke>", prompt)

    def test_glm_prompt_uses_tool_invoke_only_stream(self) -> None:
        os.environ["FAKE_OC_CALLS"] = INVOKE_CALLS
        _content, finishes, names = self._stream(GLM_MODEL)
        self.assertEqual(self._runs(), 1)
        self.assertEqual(names, ["job_output", "bash"])
        self.assertEqual(finishes, ["tool_calls"])
        self._assert_no_tool_call_token()

    def test_glm_history_tool_calls_rewritten_to_tool_invoke(self) -> None:
        os.environ["FAKE_OC_CALLS"] = INVOKE_CALLS
        messages = [
            {"role": "user", "content": "продолжай цель"},
            {"role": "assistant", "content": "Проверяю.", "tool_calls": [
                {"id": "call_1", "type": "function",
                 "function": {"name": "job_output", "arguments": '{"job_id": "bash-4a99"}'}}]},
            {"role": "tool", "tool_call_id": "call_1", "content": "ok"},
        ]
        _content, _finishes, names = self._stream(GLM_MODEL, messages)
        self.assertEqual(names, ["job_output", "bash"])
        self._assert_no_tool_call_token()
        self.assertIn('<tool_invoke>{"id": "call_1", "name": "job_output"', self._prompts()[0])

    def test_glm_swallowed_tool_call_reprompts_stream(self) -> None:
        os.environ["FAKE_OC_MODE"] = "swallowed"
        os.environ["FAKE_OC_CALLS"] = INVOKE_CALLS
        content, finishes, names = self._stream(GLM_MODEL)
        self.assertEqual(self._runs(), 2)
        self.assertEqual(names, ["job_output", "bash"])
        self.assertEqual(finishes, ["tool_calls"])
        self.assertEqual(content.count("проверяю вывод джобы"), 1)
        self._assert_no_tool_call_token()
        retry_tail = self._prompts()[1].rsplit("[system]", 1)[1]
        self.assertIn('start your reply immediately with <tool_invoke>{"name":', retry_tail)

    def test_glm_swallowed_tool_call_reprompts_json(self) -> None:
        os.environ["FAKE_OC_MODE"] = "swallowed"
        os.environ["FAKE_OC_CALLS"] = INVOKE_CALLS
        out = json.loads(self._post(stream=False, model=GLM_MODEL))
        choice = out["choices"][0]
        self.assertEqual(self._runs(), 2)
        self.assertEqual([c["function"]["name"] for c in choice["message"]["tool_calls"]],
                         ["job_output", "bash"])
        self.assertEqual(choice["finish_reason"], "tool_calls")
        self._assert_no_tool_call_token()

    def test_swallowed_status_not_retried_when_tokens_match_text(self) -> None:
        os.environ["FAKE_OC_MODE"] = "plain"
        _content, finishes, names = self._stream(GLM_MODEL)
        self.assertEqual(self._runs(), 1)
        self.assertEqual(names, [])
        self.assertEqual(finishes, ["stop"])

    # --- Ошибка до первого токена: proc не убиваем ----------------------------------------

    def _assert_early_error_survived(self) -> None:
        self.assertEqual(self._runs(), 1)
        self.assertTrue(Path(str(self.counter) + ".survived").exists(),
                        "proc must not be killed by an error before any output")

    def test_early_error_does_not_kill_proc_stream(self) -> None:
        os.environ["FAKE_OC_MODE"] = "early_error"
        _content, finishes, names = self._stream()
        self._assert_early_error_survived()
        self.assertEqual(names, ["job_output", "bash"])
        self.assertEqual(finishes, ["tool_calls"])

    def test_early_error_does_not_kill_proc_json(self) -> None:
        os.environ["FAKE_OC_MODE"] = "early_error"
        out = json.loads(self._post(stream=False))
        self._assert_early_error_survived()
        self.assertEqual([c["function"]["name"] for c in out["choices"][0]["message"]["tool_calls"]],
                         ["job_output", "bash"])

    def test_unmapped_then_error_stops_proc_json(self) -> None:
        os.environ["FAKE_OC_MODE"] = "unmapped_then_error"
        out = json.loads(self._post(stream=False))
        choice = out["choices"][0]
        self.assertEqual(self._runs(), 2)
        self.assertFalse(Path(str(self.counter) + ".second_step").exists(), "proc must be stopped on error")
        self.assertEqual([c["function"]["name"] for c in choice["message"]["tool_calls"]],
                         ["job_output", "bash"])
        self.assertEqual(choice["finish_reason"], "tool_calls")
        self.assertIn("todoread", self._prompts()[1])

    # --- Ранняя ошибка + восстановление коротким текстом: had_error не липнет --------------

    def test_early_error_then_plain_text_not_retried_json(self) -> None:
        os.environ["FAKE_OC_MODE"] = "early_error_plain"
        out = json.loads(self._post(stream=False))
        choice = out["choices"][0]
        self.assertEqual(self._runs(), 1)
        self.assertEqual(choice["finish_reason"], "stop")
        self.assertEqual(choice["message"]["content"], "Готово, проверил.")

    def test_early_error_then_plain_text_not_retried_stream(self) -> None:
        os.environ["FAKE_OC_MODE"] = "early_error_plain"
        content, finishes, names = self._stream()
        self.assertEqual(self._runs(), 1)
        self.assertEqual((content, finishes, names), ("Готово, проверил.", ["stop"], []))

    # --- «The previous response was interrupted» вычищается и из reasoning -----------------

    def test_interrupted_artifact_removed_from_reasoning_stream(self) -> None:
        os.environ["FAKE_OC_MODE"] = "reasoning_interrupted"
        raw = self._post(stream=True).decode()
        chunks = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: {")]
        thoughts = "".join(c["choices"][0]["delta"].get("reasoning_content") or "" for c in chunks)
        self.assertEqual(thoughts, "Simple greeting.")
        self.assertNotIn("interrupted", raw)
        self.assertEqual(self._runs(), 1)

    def test_interrupted_artifact_removed_from_reasoning_json(self) -> None:
        os.environ["FAKE_OC_MODE"] = "reasoning_interrupted"
        out = json.loads(self._post(stream=False))
        message = out["choices"][0]["message"]
        self.assertEqual(message["reasoning_content"], "Simple greeting.")
        self.assertEqual(message["content"], "Привет!")
        self.assertEqual(out["choices"][0]["finish_reason"], "stop")
        self.assertEqual(self._runs(), 1)

    # --- Бюджеты повторов раздельные -----------------------------------------------------

    def test_unmapped_retries_do_not_exhaust_incomplete_budget_stream(self) -> None:
        os.environ["FAKE_OC_MODE"] = "unmapped_then_promise"
        content, finishes, names = self._stream()
        self.assertEqual(self._runs(), 3)  # 1 unmapped + 1 incomplete: общий потолок MAX_TOTAL_SPAWNS
        self.assertEqual(names, ["job_output", "bash"])
        self.assertEqual(finishes, ["tool_calls"])
        self.assertEqual(content.count("Собираю факты"), 1)

    def test_unmapped_retries_do_not_exhaust_incomplete_budget_json(self) -> None:
        os.environ["FAKE_OC_MODE"] = "unmapped_then_promise"
        out = json.loads(self._post(stream=False))
        self.assertEqual(self._runs(), 3)
        self.assertEqual([c["function"]["name"] for c in out["choices"][0]["message"]["tool_calls"]],
                         ["job_output", "bash"])

    # --- Обычный текстовый ответ не ретраится ------------------------------------------

    def test_plain_answer_not_retried_stream(self) -> None:
        os.environ["FAKE_OC_MODE"] = "plain"
        content, finishes, names = self._stream()
        self.assertEqual(self._runs(), 1)
        self.assertEqual((content, finishes, names), ("Привет!", ["stop"], []))

    def test_plain_answer_not_retried_json(self) -> None:
        os.environ["FAKE_OC_MODE"] = "plain"
        out = json.loads(self._post(stream=False))
        self.assertEqual(self._runs(), 1)
        self.assertEqual(out["choices"][0]["finish_reason"], "stop")
        self.assertEqual(out["choices"][0]["message"]["content"], "Привет!")

    def test_tail_reminder_in_long_prompt(self) -> None:
        os.environ["FAKE_OC_MODE"] = "plain"
        history: list[dict[str, Any]] = []
        for i in range(3):
            history.append({"role": "user", "content": f"шаг {i} " + "x" * 2000})
            history.append({"role": "assistant", "content": f"Смотрю {i}."})
        history.append({"role": "user", "content": "дальше"})
        body = json.dumps({"model": "muse-spark-1.3-contributor-free", "stream": False,
                           "messages": history, "tools": TOOLS}).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/chat/completions", data=body,
                                     headers={"Authorization": "Bearer test-key",
                                              "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60):
            pass
        prompt = self._prompts()[0]
        tail = prompt.rsplit("[system]", 1)[1]
        self.assertIn("Available tools: job_output, bash", tail)
        self.assertIn("<tool_call>", tail)
        self.assertTrue(prompt.rstrip().endswith(tail.rstrip()))

    # --- Помощники для проверок ceiling/O-EXIT ---------------------------------------------

    def _post_raw(self, body: bytes | None = None, stream: bool = False, tool_choice: Any = None,
                  model: str = "muse-spark-1.3-contributor-free") -> tuple[int, bytes]:
        payload: dict[str, Any] = {"model": model, "stream": stream, "tools": TOOLS,
                                   "messages": [{"role": "user", "content": "продолжай цель"}]}
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/chat/completions",
                                     data=body if body is not None else json.dumps(payload).encode(),
                                     headers={"Authorization": "Bearer test-key",
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            with exc:
                return exc.code, exc.read()

    @staticmethod
    def _exit_lines() -> list[dict[str, str]]:
        text = server.LOG_PATH.read_text("utf-8") if server.LOG_PATH.exists() else ""
        return [dict(re.findall(r"(\w+)=(\S+)", line)) for line in text.splitlines() if "O-EXIT/v1" in line]

    def _last_exit(self, before: int) -> dict[str, str]:
        """Последняя строка O-EXIT/v1 после `before` строк (лог пишется уже после ответа клиенту)."""
        for _ in range(100):
            lines = self._exit_lines()
            if len(lines) > before:
                return lines[-1]
            time.sleep(0.05)
        self.fail("O-EXIT/v1 line was not written")

    # --- VER-005: пять целевых тестов ---------------------------------------------------

    def test_serve_json_without_emulate_tools_skips_step_recovery(self) -> None:
        # tool_choice="none" -> emulate_tools=False: детектор не вызывается, ровно один запуск.
        os.environ["FAKE_OC_MODE"] = "promise"
        before = len(self._exit_lines())
        with mock.patch.object(server, "_is_incomplete_tool_step",
                               wraps=server._is_incomplete_tool_step) as detector:
            status, raw = self._post_raw(tool_choice="none")
        self.assertEqual(status, 200)
        detector.assert_not_called()
        self.assertEqual(self._runs(), 1)
        choice = json.loads(raw)["choices"][0]
        self.assertEqual(choice["finish_reason"], "stop")
        self.assertIn("Собираю факты", choice["message"]["content"])
        self.assertEqual(self._last_exit(before)["total_spawns"], "1")

    def test_env_kill_switch_skips_step_recovery_keeps_unmapped_retry(self) -> None:
        # OPENCODE_ZEN_BRIDGE_STEP_RECOVERY=0 выключает дозапрос преамбулы; повтор встроенного инструмента — нет.
        self.assertEqual(server.NATIVE_RETRY_LIMIT, 2)
        with mock.patch.dict(os.environ, {"OPENCODE_ZEN_BRIDGE_STEP_RECOVERY": "0"}):
            os.environ["FAKE_OC_MODE"] = "promise"
            _content, finishes, names = self._stream()
            self.assertEqual((self._runs(), names, finishes), (1, [], ["stop"]))  # преамбула не дозапрошена
            self.counter.unlink()
            Path(str(self.counter) + ".prompts").unlink()
            os.environ["FAKE_OC_MODE"] = "unmapped_then_promise"
            _content, finishes, names = self._stream()
            # повтор встроенного инструмента сработал (2-й запуск), а преамбула 2-го шага — уже без дозапроса
            self.assertEqual(self._runs(), 2)
            self.assertEqual((names, finishes), ([], ["stop"]))
            self.assertIn("todoread", self._prompts()[1])

    def test_stream_dedup_prefix_mismatch_emits_full_text(self) -> None:
        # Попытка 1: «Checking state...»; попытка 2 переформулировала: текст и tool_calls доходят целиком.
        os.environ["FAKE_OC_MODE"] = "rephrase"
        content, finishes, names = self._stream()
        self.assertEqual(self._runs(), 2)
        self.assertIn("Checking state...", content)
        self.assertIn("Here is the result", content)
        self.assertEqual(names, ["job_output", "bash"])
        self.assertEqual(finishes, ["tool_calls"])

    def test_json_dedup_prefix_mismatch_keeps_full_text(self) -> None:
        os.environ["FAKE_OC_MODE"] = "rephrase"
        choice = json.loads(self._post(stream=False))["choices"][0]
        self.assertEqual(self._runs(), 2)
        self.assertIn("Checking state...", choice["message"]["content"])
        self.assertIn("Here is the result", choice["message"]["content"])
        self.assertEqual(choice["finish_reason"], "tool_calls")

    def test_stream_dedup_prefix_match_suppresses_repeated_preamble(self) -> None:
        os.environ["FAKE_OC_MODE"] = "repeat_prefix"
        content, finishes, names = self._stream()
        self.assertEqual(self._runs(), 2)
        self.assertEqual(content.count("Checking state..."), 1)
        self.assertEqual((names, finishes), (["job_output", "bash"], ["tool_calls"]))

    def test_json_dedup_prefix_match_suppresses_repeated_preamble(self) -> None:
        os.environ["FAKE_OC_MODE"] = "repeat_prefix"
        choice = json.loads(self._post(stream=False))["choices"][0]
        self.assertEqual(choice["message"]["content"].count("Checking state..."), 1)
        self.assertEqual(choice["finish_reason"], "tool_calls")

    def test_short_final_answer_with_colon_not_incomplete(self) -> None:
        for text in ("Ответ: 42:", "Итог проверки:", "Результат проверки:", "Вывод:", "Summary:"):
            with self.subTest(text=text):
                self.assertFalse(server._is_incomplete_tool_step(text, "", TOOLS))
                self.assertEqual(server._detect_incomplete_tool_step_signal(text, "", TOOLS), 0)
        self.assertEqual(server._detect_incomplete_tool_step_signal("Читаю файл:", "", TOOLS), 5)

    def test_mid_stream_error_401_not_retried_stream(self) -> None:
        os.environ["FAKE_OC_MODE"] = "error401"
        raw = self._post(stream=True).decode()
        chunks = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: {")]
        errors = [c["error"] for c in chunks if "error" in c]
        self.assertEqual(self._runs(), 1)
        self.assertFalse(Path(str(self.counter) + ".second_step").exists(), "proc must be stopped on error")
        self.assertEqual(len(errors), 1)
        self.assertIn("api_key_expired", errors[0]["message"])
        self.assertFalse([c for c in chunks if c.get("choices") and c["choices"][0].get("finish_reason")])

    def test_mid_stream_error_401_not_retried_json(self) -> None:
        os.environ["FAKE_OC_MODE"] = "error401"
        before = len(self._exit_lines())
        status, raw = self._post_raw()
        self.assertEqual(status, 502)
        self.assertIn("api_key_expired", raw.decode())
        self.assertEqual(self._runs(), 1)
        self.assertEqual(self._last_exit(before)["total_spawns"], "1")
        self.assertFalse(Path(str(self.counter) + ".second_step").exists(), "proc must be stopped on error")

    def test_mid_stream_error_econnreset_retried_stream(self) -> None:
        os.environ["FAKE_OC_MODE"] = "econnreset"
        with mock.patch.object(server, "_stop_proc", wraps=server._stop_proc) as stop:
            content, finishes, names = self._stream()
        self.assertTrue(stop.called)
        self.assertEqual(self._runs(), 2)
        self.assertFalse(Path(str(self.counter) + ".second_step").exists())
        self.assertNotIn("interrupted", content)
        self.assertEqual((names, finishes), (["job_output", "bash"], ["tool_calls"]))

    def test_mid_stream_error_econnreset_retried_json(self) -> None:
        os.environ["FAKE_OC_MODE"] = "econnreset"
        before = len(self._exit_lines())
        choice = json.loads(self._post(stream=False))["choices"][0]
        self.assertEqual(self._runs(), 2)
        self.assertEqual(choice["finish_reason"], "tool_calls")
        info = self._last_exit(before)
        self.assertEqual((info["total_spawns"], info["signal"]), ("2", "1"))

    def test_run_execute_once_stops_proc_on_mid_stream_error(self) -> None:
        os.environ["FAKE_OC_MODE"] = "econnreset"
        run = server.Run("muse-spark-1.3-contributor-free", "prompt", "", Path(self.tmp.name) / "ws",
                         tools=TOOLS, resilience=self.res)
        out = run._execute_once()
        run.close()
        self.assertTrue(out["had_error"])
        self.assertFalse(out["fatal_error"])
        self.assertEqual(out["state"], "provider_error")
        self.assertNotIn("interrupted", out["text"])
        self.assertFalse(Path(str(self.counter) + ".second_step").exists(), "proc must be stopped on error")

    def test_run_execute_once_overflow_stops_proc_and_marks_attempt_failed(self) -> None:
        os.environ["FAKE_OC_MODE"] = "econnreset"
        original = server._StdoutFeed.lines

        def slow_lines(feed: Any, *args: Any, **kwargs: Any) -> Any:
            time.sleep(0.5)  # читатель успевает переполнить очередь maxsize=1
            yield from original(feed, *args, **kwargs)

        with (mock.patch.object(server, "STDOUT_QUEUE_MAX", 1),
              mock.patch.object(server._StdoutFeed, "lines", slow_lines)):
            run = server.Run("muse-spark-1.3-contributor-free", "prompt", "", Path(self.tmp.name) / "ws",
                             tools=TOOLS, resilience=self.res)
            out = run._execute_once()
            run.close()
        self.assertEqual(out["state"], "stdout_overflow")
        self.assertTrue(out["had_error"])
        self.assertFalse(Path(str(self.counter) + ".second_step").exists(), "proc must be stopped on overflow")

    # --- Потолок MAX_TOTAL_SPAWNS = 3 на все комбинации классов повтора ----------------------

    def test_ceiling_always_promise_stops_after_three_spawns(self) -> None:
        # QA-BND-02: 1 + NATIVE_RETRY_LIMIT запусков, дальше накопленный текст с finish stop.
        os.environ["FAKE_OC_MODE"] = "always_promise"
        content, finishes, names = self._stream()
        self.assertEqual(self._runs(), server.MAX_TOTAL_SPAWNS)
        self.assertEqual((names, finishes), ([], ["stop"]))
        self.assertIn("Собираю факты", content)

    def test_ceiling_unmapped_then_promise_forever_json(self) -> None:
        os.environ["FAKE_OC_MODE"] = "unmapped_then_promise_forever"
        before = len(self._exit_lines())
        choice = json.loads(self._post(stream=False))["choices"][0]
        self.assertEqual(self._runs(), 3)  # было бы 1 + 2 + 2 без общего потолка
        self.assertEqual(choice["finish_reason"], "stop")
        self.assertEqual(self._last_exit(before)["total_spawns"], "3")

    def test_ceiling_unmapped_forever_stream(self) -> None:
        os.environ["FAKE_OC_MODE"] = "unmapped_forever"
        content, finishes, _names = self._stream()
        self.assertEqual(self._runs(), 3)
        self.assertIn("повторы исчерпаны", content)
        self.assertEqual(finishes, ["stop"])

    def test_ceiling_locked_then_promise_stream(self) -> None:
        # fail_retries + attempt: 1 (rc=1) + 1 fail-повтор + 1 дозапрос = 3, четвёртого запуска нет.
        os.environ["FAKE_OC_MODE"] = "locked_then_promise"
        _content, finishes, names = self._stream()
        self.assertEqual(self._runs(), 3)
        self.assertEqual((names, finishes), ([], ["stop"]))

    def test_ceiling_locked_then_promise_json(self) -> None:
        os.environ["FAKE_OC_MODE"] = "locked_then_promise"
        out = json.loads(self._post(stream=False))
        self.assertEqual(self._runs(), 3)
        self.assertEqual(out["choices"][0]["finish_reason"], "stop")

    def test_retry_budget_exhausted_returns_last_attempt_without_retry(self) -> None:
        os.environ["FAKE_OC_MODE"] = "promise"
        self.res.retry_budget = server._RetryBudget(capacity=0.0, per_request_refill=0.0, reserve_rps=0.0)
        content, finishes, names = self._stream()
        self.assertEqual(self._runs(), 1)
        self.assertEqual((names, finishes), ([], ["stop"]))
        self.assertIn("Собираю факты", content)

    # --- SSE keepalive во время повтора ------------------------------------------------

    def test_keepalive_chunks_sent_while_waiting_for_step_recovery_retry(self) -> None:
        os.environ["FAKE_OC_MODE"] = "slow_promise"
        os.environ["FAKE_OC_DELAY"] = "0.5"
        with mock.patch.object(server, "KEEPALIVE_INTERVAL_S", 0.05):
            raw = self._post(stream=True).decode()
        chunks = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: {")]
        deltas = [c["choices"][0]["delta"] for c in chunks if c.get("choices")]
        self.assertGreaterEqual(deltas[1:].count({"content": ""}), 1, deltas)
        self.assertEqual(self._runs(), 2)
        self.assertEqual([c["choices"][0].get("finish_reason") for c in chunks if c.get("choices")][-1],
                         "tool_calls")

    # --- O-EXIT/v1: структурная строка на каждом выходе do_POST -------------------------------

    def _assert_exit_fields(self, info: dict[str, str], **expected: str) -> None:
        for key in ("mode", "model", "exit_reason", "total_spawns", "signal", "status"):
            self.assertIn(key, info)
        for key, value in expected.items():
            self.assertEqual(info[key], value, (key, info))

    def test_o_exit_logged_for_json_and_stream_success(self) -> None:
        os.environ["FAKE_OC_MODE"] = "plain"
        before = len(self._exit_lines())
        self._post(stream=False)
        self._assert_exit_fields(self._last_exit(before), mode="json", exit_reason="ok", status="200",
                                 total_spawns="1", signal="0")
        before = len(self._exit_lines())
        self._post(stream=True)
        self._assert_exit_fields(self._last_exit(before), mode="stream", exit_reason="ok", status="200",
                                 total_spawns="1", signal="0",
                                 model="muse-spark-1.3-contributor-free")

    def test_o_exit_logged_for_400_and_401(self) -> None:
        before = len(self._exit_lines())
        status, _ = self._post_raw(body=b"{not json")
        self.assertEqual(status, 400)
        self._assert_exit_fields(self._last_exit(before), exit_reason="bad_request", status="400",
                                 total_spawns="0")
        before = len(self._exit_lines())
        status, _ = self._post_raw(body=json.dumps({"model": "no-such-model", "messages": []}).encode())
        self.assertEqual(status, 400)
        self._assert_exit_fields(self._last_exit(before), exit_reason="bad_request", status="400")
        before = len(self._exit_lines())
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/chat/completions", data=b"{}",
                                     headers={"Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(req, timeout=10)
        caught.exception.close()
        self.assertEqual(caught.exception.code, 401)
        self._assert_exit_fields(self._last_exit(before), exit_reason="unauthorized", status="401")

    def test_o_exit_logged_for_503_circuit_open_without_spawn(self) -> None:
        for _ in range(server.CB_FAIL_THRESHOLD):
            self.res.breaker.record_failure()
        self.assertEqual(self.res.breaker.state, "OPEN")
        for stream in (False, True):
            with self.subTest(stream=stream):
                before = len(self._exit_lines())
                status, raw = self._post_raw(stream=stream)
                self.assertEqual(status, 503)
                error = json.loads(raw)["error"]
                self.assertEqual((error["message"], error["type"]), ("upstream circuit open", "overloaded"))
                self._assert_exit_fields(self._last_exit(before), exit_reason="circuit_open", status="503",
                                         total_spawns="0")
        self.assertFalse(self.counter.exists(), "в OPEN запусков нет")
        self.assertEqual(self.res.slots.in_use, 0)

    def test_o_exit_logged_for_503_slot_timeout_and_overflow(self) -> None:
        self.res.slots = server._SlotBulkhead(max_concurrent=1, max_waiters=1, wait_timeout_s=0.2)
        self.assertEqual(self.res.slots.acquire_ex(), "ok")
        before = len(self._exit_lines())
        started = time.monotonic()
        status, raw = self._post_raw()
        self.assertEqual(status, 503)
        self.assertGreaterEqual(time.monotonic() - started, 0.15)
        self.assertEqual(json.loads(raw)["error"]["type"], "overloaded")
        self._assert_exit_fields(self._last_exit(before), exit_reason="slot_timeout", status="503")
        self.res.slots = server._SlotBulkhead(max_concurrent=1, max_waiters=0, wait_timeout_s=30.0)
        self.assertEqual(self.res.slots.acquire_ex(), "ok")
        before = len(self._exit_lines())
        started = time.monotonic()
        status, _ = self._post_raw(stream=True)
        self.assertEqual(status, 503)
        self.assertLess(time.monotonic() - started, 2.0, "переполнение очереди ждущих — мгновенный отказ")
        self._assert_exit_fields(self._last_exit(before), exit_reason="slot_overflow", status="503")
        self.assertFalse(self.counter.exists())

    def test_breaker_opens_after_repeated_transient_failures_and_blocks_next_request(self) -> None:
        os.environ["FAKE_OC_MODE"] = "locked_then_promise"
        self.res.breaker = server._UpstreamBreaker(fail_threshold=2, reset_timeout_s=60.0)
        with mock.patch.object(server, "FAIL_RETRY_LIMIT", 0):
            for _ in range(2):
                status, _raw = self._post_raw()
                self.assertEqual(status, 502)
                self.counter.unlink()
        self.assertEqual(self.res.breaker.state, "OPEN")
        status, raw = self._post_raw()
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(raw)["error"]["message"], "upstream circuit open")
        self.assertFalse(self.counter.exists())

    def test_retried_then_successful_request_does_not_count_as_breaker_failure(self) -> None:
        self.res.breaker = server._UpstreamBreaker(fail_threshold=1, reset_timeout_s=60.0)
        os.environ["FAKE_OC_MODE"] = "econnreset"  # 1-й запуск оборван ECONNRESET, 2-й — вызовы
        choice = json.loads(self._post(stream=False))["choices"][0]
        self.assertEqual(choice["finish_reason"], "tool_calls")
        self.assertEqual(self.res.breaker.state, "CLOSED")


class TestIsIncompleteToolStep(unittest.TestCase):
    def check(self, text: str = "", reasoning: str = "", **kw: Any) -> bool:
        return server._is_incomplete_tool_step(text, reasoning, kw.pop("tools", TOOLS), **kw)

    def test_no_tools_never_incomplete(self) -> None:
        self.assertFalse(self.check("Собираю факты", "let me batch", tools=[], tool_choice="required"))

    def test_tool_choice_required_or_named(self) -> None:
        self.assertTrue(self.check("Привет", tool_choice="required"))
        self.assertTrue(self.check("Привет", tool_choice={"type": "function", "function": {"name": "bash"}}))

    def test_provider_error_with_partial_output(self) -> None:
        self.assertTrue(self.check("Фетч был завершён", had_error=True))
        self.assertTrue(self.check("", "thinking", had_error=True))
        self.assertFalse(self.check("", "", had_error=True))

    def test_interrupt_markers(self) -> None:
        self.assertTrue(self.check("I was interrupted right before making tool calls."))
        self.assertTrue(self.check("", "The previous response was interrupted. Continue"))

    def test_unparsed_raw_tool_call(self) -> None:
        self.assertTrue(self.check('Смотрю <tool_call>{"name": "bash", "arguments": {"command": "ls"'))
        self.assertFalse(self.check("В протоколе используется `<tool_call>` как тег."))

    def test_russian_promise_preamble_without_reasoning(self) -> None:
        self.assertTrue(self.check("Фетч завершён, забираю вывод:"))
        self.assertTrue(self.check("🕐 [14:11 MSK] Проверяю состояние…"))
        self.assertTrue(self.check("Собираю факты..."))

    def test_english_promise_preamble_without_reasoning(self) -> None:
        self.assertTrue(self.check("Let me check the job output:"))
        self.assertTrue(self.check("Running the tests now..."))

    def test_russian_promise_with_plan_in_reasoning(self) -> None:
        self.assertTrue(self.check(PREAMBLE, PLAN))
        self.assertTrue(self.check(STATUS_ONLY, PLAN))

    def test_plan_in_reasoning_with_short_status(self) -> None:
        self.assertTrue(self.check("**Статус.** Собираю факты.", PLAN))
        self.assertTrue(self.check("", "All in batch: job_output then bash, parallel calls."))

    def test_plan_in_reasoning_requires_promise_in_body(self) -> None:
        self.assertFalse(self.check("**Статус.**", PLAN))
        self.assertFalse(self.check("Суббота", PLAN))
        self.assertFalse(self.check("Проверять ли состояние, или сразу смотрю?", PLAN))

    def test_short_answer_with_promise_words_but_no_plan_is_complete(self) -> None:
        self.assertFalse(self.check("Сейчас проверяю этот пункт — всё в порядке."))
        self.assertFalse(self.check("Обновляю данные раз в час, так задумано."))
        self.assertFalse(self.check("Проверяю: ошибок нет.", "Thinking about the answer."))
        self.assertFalse(self.check("Обновляю.", "Short answer, nothing to run."))
        self.assertFalse(self.check("Let me check: yes, it is Saturday."))

    def test_tool_choice_none_never_incomplete(self) -> None:
        self.assertFalse(self.check(PREAMBLE, PLAN, tool_choice="none"))
        self.assertFalse(self.check("Фетч завершён", had_error=True, tool_choice="none"))
        self.assertFalse(self.check("I was interrupted right before making tool calls.", tool_choice="none"))

    def test_long_final_answer_after_provider_error_is_complete(self) -> None:
        answer = "Итог работы. " * 120 + "Тесты зелёные."
        self.assertGreater(len(answer), server.INCOMPLETE_STEP_MAX_TEXT)
        self.assertFalse(self.check(answer, had_error=True))
        self.assertTrue(self.check(answer[:500], had_error=True))

    def test_interrupted_marker_in_reasoning_or_text(self) -> None:
        self.assertTrue(self.check("", "I was interrupted right before making tool calls."))
        self.assertTrue(self.check("The previous response was interrupted."))

    def test_plain_answers_are_complete(self) -> None:
        self.assertFalse(self.check("Суббота"))
        self.assertFalse(self.check("Привет! Чем помочь?"))
        self.assertFalse(self.check("OK"))
        self.assertFalse(self.check("Привет!", "Simple greeting per Rule 0, no tools needed"))
        self.assertFalse(self.check("Привет!", "Правило 0: не требует инструментов"))
        self.assertFalse(self.check("Готово.", "The answer needs no tools. Let me do: reply with the answer."))

    def test_rule0_quote_in_reasoning_with_tool_plan_and_next_step_promise_triggers_retry(self) -> None:
        # chatcmpl-oczen-07836803fb70: цитата Rule 0 в начале reasoning, дальше — план вызова.
        reasoning = (
            "Per Rule 0 'Status, greeting, a single reference question — one text, without tools' ... "
            "But answering requires reading the file, so tools needed. Per tool protocol, emit blocks ... "
            "Actually keep it minimal: one bash call computing hash")
        text = ("Подтверждаю: общий канон ~/Мой диск/Context/AGENTS.md прочитан целиком "
                "(маркер <!-- КАНОН-КОНЕЦ --> в конце), проектные файлы правил в рабочей папке "
                "проверю следующим шагом.")
        self.assertIn(server._detect_incomplete_tool_step_signal(text, reasoning, TOOLS), (4, 5))
        self.assertTrue(self.check(text, reasoning))
        self.assertFalse(self.check("Привет!", "Simple greeting per Rule 0, no tools needed"))

    def test_long_final_answer_with_plan_words_is_complete(self) -> None:
        answer = "Итог работы. " * 200 + "Тесты зелёные, правки закоммичены."
        self.assertFalse(self.check(answer, "Let me do: summarize; job_output is not needed."))


class TestStripInterrupted(unittest.TestCase):
    def test_i_was_interrupted_with_continue(self) -> None:
        self.assertEqual(server._strip_interrupted(
            "Забираю.I was interrupted right before making tool calls. Continue: collect output."), "Забираю.")

    def test_i_was_interrupted_without_continue(self) -> None:
        self.assertEqual(server._strip_interrupted("Раз. I was interrupted right before making tool calls."),
                         "Раз. ")

    def test_previous_response_interrupted(self) -> None:
        text = ("Раз. The previous response was interrupted. Continue from where you left off without "
                "repeating completed content. Два.")
        self.assertEqual(server._strip_interrupted(text), "Раз.  Два.")

    def test_unrelated_text_untouched(self) -> None:
        text = "Предыдущий ответ был прерван? The previous response was fine. Continue: ok."
        self.assertEqual(server._strip_interrupted(text), text)


class TestTailReminder(unittest.TestCase):
    LONG = "x" * (server.TAIL_REMINDER_MIN_CHARS + 1)

    def test_reminder_for_long_history(self) -> None:
        self.assertIn("Available tools: job_output, bash", server._tools_tail_reminder(self.LONG, TOOLS))

    def test_no_reminder_for_tool_choice_none(self) -> None:
        self.assertEqual(server._tools_tail_reminder(self.LONG, TOOLS, "none"), "")

    def test_no_reminder_without_tools(self) -> None:
        self.assertEqual(server._tools_tail_reminder(self.LONG, []), "")


class TestShellAlias(unittest.TestCase):
    def test_shell_maps_to_bash(self) -> None:
        calls = server._native_to_tool_calls("shell", {"command": "ls -la"}, DSH_TOOLS)
        self.assertEqual([c["name"] for c in calls], ["bash"])
        self.assertEqual(calls[0]["arguments"]["command"], "ls -la")
        self.assertTrue(calls[0]["arguments"]["description"])


class TestSanitizeAssistantHistory(unittest.TestCase):
    def test_interrupted_artifact_removed(self) -> None:
        text = ("Фетч был завершён (exit 0) — забираю вывод."
                "I was interrupted right before making tool calls. Continue: collect output.")
        self.assertEqual(server._sanitize_assistant_text(text),
                         "Фетч был завершён (exit 0) — забираю вывод.")

    def test_interrupted_artifact_own_line(self) -> None:
        text = "Раз.\nI was interrupted right before making tool calls. Continue.\nДва."
        self.assertEqual(server._sanitize_assistant_text(text), "Раз.\n\nДва.")

    def test_unclosed_tool_call_tail_removed(self) -> None:
        text = ('Смотрю.\n<tool_call>{"name": "bash", "arguments": {"command": "ls"}}</tool_call>\n'
                'Потом:\n<tool_call>{"name": "read", "arguments": {"file_path": "/etc/ho')
        out = server._sanitize_assistant_text(text)
        self.assertEqual(out.count("<tool_call>"), 1)
        self.assertTrue(out.rstrip().endswith("Потом:"))

    def test_closed_batch_without_intermediate_close_kept(self) -> None:
        text = ('<tool_call>{"name": "a", "arguments": {}}\n<tool_call>{"name": "b", "arguments": {}}'
                '</tool_call>')
        self.assertEqual(server._sanitize_assistant_text(text), text)

    def test_quoted_tag_in_prose_kept(self) -> None:
        text = "Блок `<tool_call>` открывает вызов."
        self.assertEqual(server._sanitize_assistant_text(text), text)


PLAN_EMIT = ("Let me think... I need to call the tools in the protocol format shown in the [system] block. "
             "I should follow the injected protocol and emit blocks.")


class TestIncompleteStepGlmPatterns(unittest.TestCase):
    """Реальные паттерны glm-5.3-flash-free (2026-10-24), которые раньше пропускались."""

    def check(self, text: str = "", reasoning: str = "", **kw: Any) -> bool:
        return server._is_incomplete_tool_step(text, reasoning, kw.pop("tools", TOOLS), **kw)

    def test_status_ending_with_period_needs_token_evidence(self) -> None:
        self.assertFalse(self.check(SWALLOWED_TEXT))
        self.assertTrue(self.check(SWALLOWED_TEXT, output_tokens=97))

    def test_emit_blocks_plan_with_russian_status(self) -> None:
        text = "Статус: 24.10.2026, время MSK уточню по ходу — забираю вывод job_fetch_01 и читаю goal.md."
        self.assertTrue(self.check(text, PLAN_EMIT))
        self.assertTrue(self.check(text, PLAN_EMIT, output_tokens=144))

    def test_two_independent_calls_plan(self) -> None:
        reasoning = ("Two independent calls — I should make both in one turn. Status line with MSK "
                     "datetime first, then tool blocks... I'll write status and make both calls in parallel.")
        text = "Статус (MSK, 24.10.2026): забираю вывод job_fetch_01 и параллельно проверяю goal.md."
        self.assertTrue(self.check(text, reasoning))

    def test_then_both_tool_calls_plan(self) -> None:
        reasoning = ("Let me start by following the protocol: write a status line with MSK date-time, then "
                     "call job_output for job_fetch_01 and bash... then both tool calls in parallel")
        text = "Статус: 24.10.2026 ~MSK, стартую ход — параллельно забираю вывод job_fetch_01 и читаю goal.md."
        self.assertTrue(self.check(text, reasoning))

    def test_parallel_calls_plan_with_confirmation_text(self) -> None:
        reasoning = ("Parallel calls: job_output and bash... Let me do one bash with date and cat, "
                     "plus job_output in parallel.")
        text = ("Подтверждаю: правила прочитал. Выполняю параллельные вызовы: job_output по фетчу + bash "
                "по goal.md (замер MSK — уже есть: 2026-10-24 13:52 MSK).")
        self.assertTrue(self.check(text, reasoning))

    def test_tool_named_in_reasoning_and_text_without_plan_phrase(self) -> None:
        self.assertTrue(self.check("Продолжаю — job_output по фетчу.", "I should call job_output now."))

    def test_new_promise_verbs(self) -> None:
        for verb in ("Стартую", "Продолжаю", "Начинаю", "Вызываю", "Запрашиваю"):
            self.assertTrue(self.check(f"{verb} проверку:"), verb)

    def test_promise_with_tool_name_short_text_without_reasoning(self) -> None:
        self.assertTrue(self.check("Запускаю bash для проверки."))
        self.assertFalse(self.check("Запускаю проверку."))

    def test_swallowed_tokens_with_reasoning_only(self) -> None:
        self.assertTrue(self.check("", "Some planning.", output_tokens=80))

    def test_swallowed_tokens_need_text_or_reasoning(self) -> None:
        self.assertFalse(self.check("", "", output_tokens=200))

    def test_tokens_matching_visible_text_are_complete(self) -> None:
        text = "Всё в порядке: ошибок нет, тесты зелёные, правки закоммичены."
        self.assertFalse(self.check(text, output_tokens=30))
        self.assertFalse(self.check("Привет!", output_tokens=8))

    def test_question_never_swallowed(self) -> None:
        self.assertFalse(self.check("Какой джобой заняться первой?", output_tokens=200))

    def test_long_final_answer_never_swallowed(self) -> None:
        answer = "Итог работы. " * 200 + "Тесты зелёные."
        self.assertFalse(self.check(answer, output_tokens=5000))

    def test_no_tools_wins_over_swallowed_tokens(self) -> None:
        self.assertFalse(self.check("Привет!", "Simple greeting, no tools needed", output_tokens=100))

    def test_tool_choice_none_ignores_swallowed_tokens(self) -> None:
        self.assertFalse(self.check(SWALLOWED_TEXT, output_tokens=97, tool_choice="none"))

    def test_final_answer_mentioning_tool_is_complete(self) -> None:
        self.assertFalse(self.check("Ответ: в джобе ошибок нет, всё в порядке.",
                                    "The user asks about job_output; I should answer."))

    def test_raw_tool_invoke_is_incomplete(self) -> None:
        self.assertTrue(self.check('Смотрю <tool_invoke>{"name": "bash", "arguments": {"command": "ls"'))
        self.assertFalse(self.check("В протоколе используется `<tool_invoke>` как тег."))

    def test_mentions_request_tool_uses_token_boundaries(self) -> None:
        schemas = server._tool_schemas(TOOLS)
        self.assertTrue(server._mentions_request_tool("Вызываю job_output.", schemas))
        self.assertFalse(server._mentions_request_tool("job_output_2 и bashrc", schemas))


class TestAltToolTagHelpers(unittest.TestCase):
    GLM = "glm-5.3-flash-free"

    def test_uses_alt_tool_tag_only_for_glm(self) -> None:
        self.assertTrue(server._uses_alt_tool_tag(self.GLM))
        self.assertTrue(server._uses_alt_tool_tag("opencode/GLM-5#high"))
        self.assertFalse(server._uses_alt_tool_tag("muse-spark-1.3-contributor-free"))
        self.assertFalse(server._uses_alt_tool_tag(""))
        self.assertFalse(server._uses_alt_tool_tag())

    def test_tool_tags_for_model(self) -> None:
        self.assertEqual(server._tool_tags_for_model(self.GLM), ("<tool_invoke>", "</tool_invoke>"))
        self.assertEqual(server._tool_tags_for_model("muse"), ("<tool_call>", "</tool_call>"))
        self.assertEqual(server._tool_tags_for_model(), ("<tool_call>", "</tool_call>"))
        self.assertEqual(server.TOOL_CALL_OPEN, "<tool_call>")
        self.assertEqual(server.TOOL_CALL_CLOSE, "</tool_call>")

    def test_rewrite_tool_tags_for_model(self) -> None:
        text = '<tool_call>{"name": "a"}</tool_call>'
        self.assertEqual(server._rewrite_tool_tags_for_model(text, self.GLM),
                         '<tool_invoke>{"name": "a"}</tool_invoke>')
        self.assertEqual(server._rewrite_tool_tags_for_model(text, "muse"), text)
        self.assertEqual(server._rewrite_tool_tags_for_model(text), text)

    def test_tools_section_glm_has_no_tool_call_substring(self) -> None:
        section = server._tools_section(TOOLS, None, self.GLM)
        self.assertNotIn("tool_call", section)
        self.assertIn('<tool_invoke>{"name": "<tool_name>"', section)
        self.assertIn("emit a tool_invoke block", section)
        self.assertIn("MUST emit the tool_invoke block", section)

    def test_tools_section_default_keeps_tool_call(self) -> None:
        for section in (server._tools_section(TOOLS, None), server._tools_section(TOOLS, None, "muse")):
            self.assertIn('<tool_call>{"name": "<tool_name>"', section)
            self.assertIn("emit a tool_call block", section)
            self.assertNotIn("tool_invoke", section)

    def test_tail_reminder_glm(self) -> None:
        long_history = "x" * (server.TAIL_REMINDER_MIN_CHARS + 1)
        reminder = server._tools_tail_reminder(long_history, TOOLS, None, self.GLM)
        self.assertIn("<tool_invoke>", reminder)
        self.assertNotIn("tool_call", reminder)
        self.assertIn("<tool_call>", server._tools_tail_reminder(long_history, TOOLS))

    def test_incomplete_step_prompt_glm(self) -> None:
        prompt = server._incomplete_tool_step_prompt("P", "Статус:", TOOLS, None, self.GLM)
        self.assertIn('start your reply immediately with <tool_invoke>{"name":', prompt)
        self.assertIn('<tool_invoke>{"name": "<tool_name>", "arguments": {<json matching its parameters>}}'
                      "</tool_invoke> using ONLY these tools: job_output, bash.", prompt)
        self.assertNotIn("tool_call", prompt)
        default = server._incomplete_tool_step_prompt("P", "Статус:", TOOLS)
        self.assertIn('start your reply immediately with <tool_call>{"name":', default)

    def test_unavailable_tools_prompt_glm(self) -> None:
        prompt = server._unavailable_tools_prompt("P", "", ["todoread"], TOOLS, self.GLM)
        self.assertIn("<tool_invoke>", prompt)
        self.assertNotIn("tool_call", prompt)
        self.assertIn("<tool_call>", server._unavailable_tools_prompt("P", "", ["todoread"], TOOLS))


class TestDualTagParser(unittest.TestCase):
    A = '{"name": "job_output", "arguments": {"job_id": "j1"}}'
    B = '{"name": "bash", "arguments": {"command": "ls"}}'

    def names(self, chunks: list[str]) -> tuple[str, list[str]]:
        content, calls = server._split_tool_calls(chunks)
        return content, [c["function"]["name"] for c in calls]

    def test_tool_invoke_block(self) -> None:
        content, names = self.names([f"Проверяю. <tool_invoke>{self.A}</tool_invoke>"])
        self.assertEqual(names, ["job_output"])
        self.assertEqual(content, "Проверяю. ")

    def test_tool_invoke_split_across_chunks(self) -> None:
        for size in (1, 2, 3, 5, 7):
            doc = f"Статус. <tool_invoke>{self.A}</tool_invoke>"
            chunks = [doc[i:i + size] for i in range(0, len(doc), size)]
            content, names = self.names(chunks)
            self.assertEqual(names, ["job_output"], size)
            self.assertEqual(content, "Статус. ", size)

    def test_tool_invoke_batch_without_intermediate_close(self) -> None:
        content, names = self.names([f"<tool_invoke>{self.A}\n<tool_invoke>{self.B}</tool_invoke>"])
        self.assertEqual(names, ["job_output", "bash"])
        self.assertEqual(content, "")

    def test_tool_invoke_batch_with_all_closes(self) -> None:
        _content, names = self.names([f"<tool_invoke>{self.A}</tool_invoke><tool_invoke>{self.B}</tool_invoke>"])
        self.assertEqual(names, ["job_output", "bash"])

    def test_mixed_tags(self) -> None:
        _content, names = self.names([f"<tool_call>{self.A}</tool_call><tool_invoke>{self.B}</tool_invoke>"])
        self.assertEqual(names, ["job_output", "bash"])

    def test_tool_call_still_parsed(self) -> None:
        _content, names = self.names([f"<tool_call>{self.A}</tool_call>"])
        self.assertEqual(names, ["job_output"])

    def test_quoted_tool_invoke_is_prose(self) -> None:
        text = "Тег `<tool_invoke>` открывает вызов."
        content, names = self.names([text])
        self.assertEqual(names, [])
        self.assertEqual(content, text)

    def test_tool_invoke_in_fenced_code_is_prose(self) -> None:
        text = f"Пример:\n```\n<tool_invoke>{self.A}</tool_invoke>\n```\n"
        content, names = self.names([text])
        self.assertEqual(names, [])
        self.assertEqual(content, text)

    def test_close_tag_inside_json_string_is_not_boundary(self) -> None:
        block = '{"name": "bash", "arguments": {"command": "echo </tool_invoke>"}}'
        _content, calls = server._split_tool_calls([f"<tool_invoke>{block}</tool_invoke>"])
        self.assertEqual([json.loads(c["function"]["arguments"])["command"] for c in calls],
                         ["echo </tool_invoke>"])

    def test_other_tag_close_does_not_end_block(self) -> None:
        content, names = self.names([f"<tool_invoke>{self.A}</tool_call>"])
        self.assertEqual(names, [])
        self.assertIn("<tool_invoke>", content)

    def test_unparsed_block_returned_as_text(self) -> None:
        content, names = self.names(["<tool_invoke>{broken</tool_invoke>"])
        self.assertEqual(names, [])
        self.assertEqual(content, "<tool_invoke>{broken</tool_invoke>")

    def test_has_open_tool_call_for_alt_tag(self) -> None:
        parser = server.ToolCallParser(lambda _t: None, lambda _c: None)
        parser.feed("Текст <tool_inv")
        self.assertTrue(parser.has_open_tool_call())
        parser.feed(f"oke>{self.A}")
        self.assertTrue(parser.has_open_tool_call())
        parser.feed("</tool_invoke>")
        self.assertFalse(parser.has_open_tool_call())

    def test_shared_prefix_not_held_forever(self) -> None:
        content, names = self.names(["Версия <tool_x и <tool_"])
        self.assertEqual(names, [])
        self.assertEqual(content, "Версия <tool_x и <tool_")

    def test_split_inner_on_alt_tag(self) -> None:
        segments = server._split_tool_call_inner(f"{self.A}<tool_invoke>{self.B}")
        self.assertEqual(segments, [self.A, self.B])
        self.assertEqual(len(server._parse_tool_call_blocks(f"{self.A}<tool_invoke>{self.B}") or []), 2)

    def test_quoted_open_alt_tag(self) -> None:
        self.assertTrue(server._is_quoted_open("a `<tool_invoke>` b", 3))
        self.assertTrue(server._is_quoted_open("<tool_invoke>`x`", 0))
        self.assertFalse(server._is_quoted_open(f"<tool_invoke>{self.A}", 0))

    def test_sanitize_unclosed_tool_invoke_tail_removed(self) -> None:
        text = (f"Смотрю.\n<tool_invoke>{self.B}</tool_invoke>\nПотом:\n"
                '<tool_invoke>{"name": "read", "arguments": {"file_path": "/etc/ho')
        out = server._sanitize_assistant_text(text)
        self.assertEqual(out.count("<tool_invoke>"), 1)
        self.assertTrue(out.rstrip().endswith("Потом:"))

    def test_sanitize_unclosed_after_other_tag_close(self) -> None:
        text = f'<tool_call>{self.B}</tool_call>\nПотом:\n<tool_invoke>{{"name": "read", "arguments": {{"f'
        out = server._sanitize_assistant_text(text)
        self.assertNotIn('"read"', out)
        self.assertEqual(out.count("<tool_call>"), 1)

    def test_sanitize_closed_alt_batch_kept(self) -> None:
        text = f"<tool_invoke>{self.A}\n<tool_invoke>{self.B}</tool_invoke>"
        self.assertEqual(server._sanitize_assistant_text(text), text)

    def test_sanitize_quoted_alt_tag_kept(self) -> None:
        text = "Блок `<tool_invoke>` открывает вызов."
        self.assertEqual(server._sanitize_assistant_text(text), text)


class TestDetectorSignals(unittest.TestCase):
    """VER-001: признаки 1..5 `_detect_incomplete_tool_step_signal` и вычитание reasoning_tokens."""

    NAMES = ["job_output", "bash"]

    def signal(self, text: str = "", reasoning: str = "", **kw: Any) -> int:
        return server._detect_incomplete_tool_step_signal(text, reasoning, kw.pop("tools", self.NAMES), **kw)

    def test_signature_accepts_names_and_openai_schemas(self) -> None:
        self.assertEqual(self.signal("Читаю файл:", tools=self.NAMES), 5)
        self.assertEqual(self.signal("Читаю файл:", tools=TOOLS), 5)
        self.assertEqual(self.signal("Читаю файл:", tools=[]), 0)
        self.assertTrue(server._is_incomplete_tool_step("Читаю файл:", "", self.NAMES, False, 0, 0))

    def test_signal_1_mid_stream_error(self) -> None:
        self.assertEqual(self.signal("Фетч завершён", had_mid_stream_error=True), 1)
        self.assertEqual(self.signal("", "thinking", had_mid_stream_error=True), 1)
        self.assertEqual(self.signal("", "", had_mid_stream_error=True), 0)
        self.assertEqual(self.signal("Привет", tool_choice="required"), 1)

    def test_signal_2_interrupted_marker_and_raw_call(self) -> None:
        self.assertEqual(self.signal("I was interrupted right before making tool calls."), 2)
        self.assertEqual(self.signal("", "The previous response was interrupted. Continue from where you left "
                                         "off without repeating completed content."), 2)
        self.assertEqual(self.signal('Смотрю <tool_invoke>{"name": "bash", "arguments": {"command": "ls"'), 2)

    def test_signal_3_swallowed_tokens_and_reasoning_subtraction(self) -> None:
        text = "Готово, все проверки пройдены."
        # output=450, reasoning=430: non_reasoning=20 -> не проглочено; output=500, reasoning=150 -> 350 токенов
        self.assertEqual(self.signal(text, "x", output_tokens=450, reasoning_tokens=430), 0)
        self.assertFalse(server._is_incomplete_tool_step(text, "x", self.NAMES, False, 450, 430))
        self.assertEqual(self.signal(SWALLOWED_TEXT, "x", output_tokens=500, reasoning_tokens=150), 3)
        self.assertTrue(server._is_incomplete_tool_step(SWALLOWED_TEXT, "x", self.NAMES, False, 500, 150))
        # без reasoning_tokens output считается целиком
        self.assertEqual(self.signal(SWALLOWED_TEXT, output_tokens=97), 3)
        # QA-NEG-01: output=400 reasoning=385 -> 15 < 35
        for answer in ("Готово, все проверки пройдены.", "Ответ: 42."):
            self.assertEqual(self.signal(answer, "reasoning", output_tokens=400, reasoning_tokens=385), 0, answer)

    def test_signal_3_boundary_34_false_35_true(self) -> None:
        text = "Статус обновлён и сохранён." * 3
        estimate = server._visible_token_estimate(text.strip())
        tokens = estimate + server.SWALLOWED_TOKENS_MIN
        self.assertEqual(self.signal(text, output_tokens=tokens - 1), 0)
        self.assertEqual(self.signal(text, output_tokens=tokens), 3)
        # граница по длине видимого текста: 600 символов ещё признак 3, 601 — уже нет
        for size, expected in ((600, 3), (601, 0)):
            body = ("слово " * 200)[:size].strip() + "."
            body = body.ljust(size, "я")[:size]
            self.assertEqual(self.signal(body, output_tokens=5000), expected, size)

    def test_signal_4_reasoning_plan_with_tool_name_and_promise(self) -> None:
        self.assertEqual(self.signal(PREAMBLE, PLAN), 4)
        self.assertEqual(self.signal("Продолжаю — job_output по фетчу.", "I should call job_output now."), 4)
        self.assertEqual(self.signal("**Статус.**", PLAN), 0)
        self.assertEqual(self.signal("", "All in batch: job_output then bash, parallel calls."), 4)

    def test_signal_5_narrow_action_preamble(self) -> None:
        for text in ("Читаю…", "Собираю факты...", "Теперь посмотрим:", "Let's check:", "I'll run the tests...",
                     "Фетч завершён, забираю вывод:", "Запускаю bash для проверки."):
            self.assertEqual(self.signal(text), 5, text)

    def test_signal_5_bare_colon_without_action_intent_is_not_incomplete(self) -> None:
        for text in ("Ответ: 42:", "Результат проверки:", "Итог проверки:", "Список файлов:", "Вот что нашёл:"):
            self.assertEqual(self.signal(text), 0, text)
            self.assertFalse(server._is_incomplete_tool_step(text, "", self.NAMES), text)

    def test_signal_5_excludes_long_tables_code_and_conclusions(self) -> None:
        long_text = "Читаю файлы проекта и собираю сводку. " * 20 + "Дальше:"
        self.assertGreater(len(long_text), server.PREAMBLE_MAX_CHARS)
        self.assertEqual(self.signal(long_text), 0)
        table = "Проверяю результаты:\n| a | b |\n|---|---|\n| 1 | 2 |\n"
        self.assertEqual(self.signal(table), 0)
        fenced = "Запускаю:\n```\nls -la\n```\nДальше:"
        self.assertEqual(self.signal(fenced), 0)
        many_lines = "Читаю:\n" + "\n".join(f"- пункт {i}" for i in range(8)) + "\nДальше:"
        self.assertEqual(self.signal(many_lines), 0)
        self.assertEqual(self.signal("Проверяю: ошибок нет, всё в порядке:"), 0)
        self.assertEqual(self.signal("Итог: проверяю результаты..."), 0)
        self.assertEqual(self.signal("Читаю ли я файл?"), 0)

    def test_signal_5_boundary_420_chars(self) -> None:
        base = "Читаю файл "
        at_limit = base + "а" * (server.PREAMBLE_MAX_CHARS - len(base) - 1) + ":"
        self.assertEqual(len(at_limit), server.PREAMBLE_MAX_CHARS)
        self.assertEqual(self.signal(at_limit), 5)
        self.assertEqual(self.signal(at_limit + "я:"), 0)

    def test_signal_5_short_text_without_tool_mention_needs_terminator(self) -> None:
        self.assertEqual(self.signal("Запускаю проверку."), 0)
        self.assertEqual(self.signal("Запускаю job_output."), 5)

    def test_kill_switch_constant_and_env_return_zero_first(self) -> None:
        with mock.patch.object(server, "STEP_RECOVERY_ENABLED", False):
            self.assertEqual(self.signal("Читаю…"), 0)
            self.assertFalse(server._is_incomplete_tool_step("I was interrupted right before making tool calls.",
                                                             "", self.NAMES, had_mid_stream_error=True))
        for value in ("0", "false", "No", "OFF"):
            with mock.patch.dict(os.environ, {"OPENCODE_ZEN_BRIDGE_STEP_RECOVERY": value}):
                self.assertEqual(self.signal("Читаю…"), 0, value)
        with mock.patch.dict(os.environ, {"OPENCODE_ZEN_BRIDGE_STEP_RECOVERY": "1"}):
            self.assertEqual(self.signal("Читаю…"), 5)
        self.assertTrue(server.STEP_RECOVERY_ENABLED)

    def test_incomplete_step_signal_wrapper_follows_is_incomplete_tool_step(self) -> None:
        with mock.patch.object(server, "_is_incomplete_tool_step", return_value=False):
            self.assertEqual(server._incomplete_step_signal("Читаю…", "", self.NAMES), 0)
        self.assertEqual(server._incomplete_step_signal("Читаю…", "", self.NAMES), 5)


class TestTransientStreamError(unittest.TestCase):
    """AD-002: детерминированные ошибки не ретраятся (Fail-Closed), транзиентные — да."""

    @staticmethod
    def event(status: Any = None, message: str = "") -> dict[str, Any]:
        data: dict[str, Any] = {"message": message}
        if status is not None:
            data["statusCode"] = status
        return {"type": "error", "error": {"name": "APIError", "data": data}}

    def test_deterministic_statuses_are_not_transient(self) -> None:
        for status in (400, 401, 403, 404, 422):
            self.assertFalse(server._is_transient_stream_error(self.event(status, "boom ECONNRESET")), status)
            self.assertFalse(server._is_transient_stream_error({"statusCode": status, "message": ""}), status)

    def test_transient_statuses(self) -> None:
        for status in (None, 0, 408, 429, 500, 502, 503, 504):
            self.assertTrue(server._is_transient_stream_error(self.event(status, "whatever")), status)

    def test_transient_message_markers(self) -> None:
        for message in ("read ECONNRESET", "ETIMEDOUT", "request timed out", "socket hang up", "Overloaded",
                        "rate limit exceeded", "temporarily unavailable", "fetch failed", "network error",
                        "connection reset by peer", "broken pipe", "unexpected EOF", "stream interrupted"):
            self.assertTrue(server._is_transient_stream_error(self.event(402, message)), message)
        self.assertFalse(server._is_transient_stream_error(self.event(402, "payment required")))

    def test_event_shapes(self) -> None:
        self.assertTrue(server._is_transient_stream_error({"error": "read ECONNRESET"}))
        self.assertFalse(server._is_transient_stream_error({"part": {"statusCode": 401}}))
        self.assertTrue(server._is_transient_stream_error({"part": {"statusCode": 503}}))
        self.assertTrue(server._is_transient_stream_error({}))
        etype, payload = server.parse_opencode_event(self.event(401, "api_key_expired"))
        self.assertEqual(etype, "error")
        self.assertFalse(server._is_transient_stream_error(payload))
        _etype, payload = server.parse_opencode_event(self.event(None, "Connection lost: ECONNRESET"))
        self.assertTrue(server._is_transient_stream_error(payload))


class TestStdoutFeed(unittest.TestCase):
    """VER-002: ограниченная очередь stdout, переполнение, дедлайн, EOF."""

    @staticmethod
    def spawn(script: str) -> Any:
        import subprocess
        import sys
        return subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, text=True,
                                start_new_session=True)

    def test_default_queue_is_bounded_to_4096(self) -> None:
        self.assertEqual(server.STDOUT_QUEUE_MAX, 4096)
        proc = types.SimpleNamespace(stdout=iter([]), poll=lambda: 0)
        feed = server._StdoutFeed(proc)  # type: ignore[arg-type]
        feed.join(2)
        self.assertEqual(feed._queue.maxsize, 4096)
        self.assertEqual((feed.overflowed, feed.dropped_total), (False, 0))

    def test_overflow_stops_real_proc_and_counts_dropped(self) -> None:
        proc = self.spawn("import time\nfor i in range(200): print(i, flush=True)\ntime.sleep(60)")
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        feed = server._StdoutFeed(proc, maxsize=4)
        feed.join(10)
        self.assertTrue(feed.overflowed)
        self.assertGreaterEqual(feed.dropped_total, 1)
        self.assertIsNotNone(proc.poll(), "_stop_proc обязан остановить процесс на queue.Full")
        self.assertEqual(list(feed.lines(time.monotonic() + 5)), [], "после переполнения попытка неуспешна")

    def test_queue_full_calls_stop_proc_once_per_overflow(self) -> None:
        proc = types.SimpleNamespace(stdout=iter([f"{i}\n" for i in range(10)]))
        with mock.patch.object(server, "_stop_proc") as stop:
            feed = server._StdoutFeed(proc, maxsize=3)  # type: ignore[arg-type]
            feed.join(5)
        stop.assert_called_once_with(proc)
        self.assertEqual((feed.overflowed, feed.dropped_total), (True, 1))

    def test_all_lines_delivered_when_queue_is_big_enough(self) -> None:
        proc = self.spawn("for i in range(50): print(i, flush=True)")
        feed = server._StdoutFeed(proc, maxsize=4096)
        lines = [line.strip() for line in feed.lines(time.monotonic() + 30)]
        proc.wait(5)
        self.assertEqual(lines, [str(i) for i in range(50)])
        self.assertFalse(feed.overflowed)

    def test_deadline_unblocks_silent_proc(self) -> None:
        proc = self.spawn("import time; time.sleep(30)")
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        feed = server._StdoutFeed(proc)
        started = time.monotonic()
        self.assertEqual(list(feed.lines(time.monotonic() + 0.3)), [])
        self.assertLess(time.monotonic() - started, 2.0)
        self.assertTrue(feed.timed_out)

    def test_idle_callback_fires_during_silence(self) -> None:
        proc = self.spawn("import time; time.sleep(0.6); print('x', flush=True)")
        feed = server._StdoutFeed(proc)
        idle: list[int] = []
        lines = list(feed.lines(time.monotonic() + 10, 0.1, lambda: idle.append(1)))
        self.assertEqual([line.strip() for line in lines], ["x"])
        self.assertGreaterEqual(len(idle), 2)

    def test_reader_error_is_raised_to_consumer(self) -> None:
        def boom() -> Any:
            yield "a\n"
            raise ValueError("closed")

        proc = types.SimpleNamespace(stdout=boom())
        feed = server._StdoutFeed(proc)  # type: ignore[arg-type]
        got: list[str] = []
        with self.assertRaises(ValueError):
            for line in feed.lines(time.monotonic() + 5):
                got.append(line)
        self.assertEqual(got, ["a\n"])


class TestParserAndAliasVer001(unittest.TestCase):
    """VER-001 / AD-001: оба тега одинаково, алиас shell."""

    A = '{"name": "job_output", "arguments": {"job_id": "j1"}}'

    def test_tool_invoke_and_tool_call_give_identical_calls(self) -> None:
        for chunks in (["<tool_invoke>" + self.A + "</tool_invoke>"], ["<tool_call>" + self.A + "</tool_call>"]):
            _content, calls = server._split_tool_calls(chunks)
            self.assertEqual([(c["function"]["name"], json.loads(c["function"]["arguments"])) for c in calls],
                             [("job_output", {"job_id": "j1"})])
        for open_tag in ("<tool_invoke>", "<tool_call>"):
            inner = self.A + open_tag + self.A.replace("j1", "j2")
            self.assertEqual([c["arguments"]["job_id"] for c in server._parse_tool_call_blocks(inner) or []],
                             ["j1", "j2"])

    def test_native_aliases_contain_shell_and_bash_maps_to_client_shell(self) -> None:
        self.assertIn("shell", server.NATIVE_TOOL_ALIASES)
        self.assertEqual([c["name"] for c in server._native_to_tool_calls("shell", {"command": "ls"}, DSH_TOOLS)],
                         ["bash"])

    def test_glm_prompts_use_tool_invoke_as_primary_tag(self) -> None:
        self.assertIn("<tool_invoke>", server._tools_section(TOOLS, None, GLM_MODEL))
        self.assertIn("<tool_invoke>", server._incomplete_tool_step_prompt("P", "x", TOOLS, None, GLM_MODEL))


class TestRetryAndDedupHelpers(unittest.TestCase):
    def test_prefix_dedup_match_mismatch_and_partial(self) -> None:
        dedup = server._PrefixDedup("Checking state...")
        self.assertEqual(dedup.push("Check"), "")
        self.assertEqual(dedup.push("ing state... Next"), " Next")
        self.assertEqual(dedup.push(" more"), " more")
        self.assertEqual(dedup.finish(), "")
        dedup = server._PrefixDedup("Checking state...")
        self.assertEqual(dedup.push("Here is the result"), "\n\nHere is the result")
        self.assertEqual(dedup.push("!"), "!")
        dedup = server._PrefixDedup("Checking state...")
        self.assertEqual(dedup.push("Hi"), "\n\nHi")  # разошлось раньше длины префикса
        dedup = server._PrefixDedup("Checking state...")
        self.assertEqual(dedup.push("Check"), "")
        self.assertEqual(dedup.finish(), "", "чистый повтор части префикса не дублируется")
        dedup = server._PrefixDedup("Checking state...")
        self.assertEqual(dedup.finish(), "")

    def test_dedup_retry_text_json_variant(self) -> None:
        self.assertEqual(server._dedup_retry_text("Статус.", "Статус. Дальше"), " Дальше")
        self.assertEqual(server._dedup_retry_text("Статус.", "Другое"), "Другое")
        self.assertEqual(server._dedup_retry_text("", "Текст"), "Текст")
        self.assertEqual(server._dedup_retry_text("Статус.", ""), "")


class HlResilienceOracles(unittest.TestCase):
    """VER-006: детерминированные оракулы (FakeClock / инъекция rng_fn / spy), без wall-clock."""

    # --- S-HERD-I2: Full Jitter ---------------------------------------------------------

    def test_backoff_full_jitter_points(self) -> None:
        def at(u: float) -> Any:
            return lambda lo, hi: lo + u * (hi - lo)

        self.assertEqual([server._retry_backoff_s(1, at(u)) for u in (0.0, 0.5, 1.0)], [0.0, 0.5, 1.0])
        self.assertEqual([server._retry_backoff_s(2, at(u)) for u in (0.0, 0.5, 1.0)], [0.0, 1.0, 2.0])
        seen: list[tuple[float, float]] = []
        server._retry_backoff_s(7, lambda lo, hi: seen.append((lo, hi)) or hi)
        self.assertEqual(seen, [(0.0, server.RETRY_BACKOFF_CAP_S)])
        self.assertEqual((server.RETRY_BACKOFF_BASE_S, server.RETRY_BACKOFF_CAP_S), (0.5, 2.0))

    # --- S-HERD-I1: spawn token bucket --------------------------------------------------

    def test_spawn_token_bucket_at_most_one_per_second(self) -> None:
        clock = FakeClock()
        limiter = server._SpawnRateLimiter(1.0, 1.0, clock_fn=clock, sleep_fn=clock.sleep)
        starts = []
        for _ in range(10):
            self.assertTrue(limiter.acquire())
            starts.append(clock.now)
        self.assertEqual(starts[0], 1000.0)
        for first, second in zip(starts, starts[1:]):
            self.assertGreaterEqual(second - first, 1.0 - 1e-9)
        window = [t for t in starts if 1003.0 <= t < 1004.0]
        self.assertLessEqual(len(window), 1)

    def test_spawn_limiter_ten_concurrent_reservations_are_spread(self) -> None:
        clock = FakeClock()
        waits: list[float] = []
        limiter = server._SpawnRateLimiter(1.0, 1.0, clock_fn=clock, sleep_fn=waits.append)
        for _ in range(10):  # все десять приходят в один и тот же момент времени
            self.assertTrue(limiter.acquire())
        self.assertEqual(waits, [float(i) for i in range(1, 10)])

    def test_spawn_limiter_refuses_without_reserving_when_wait_exceeds_budget(self) -> None:
        clock = FakeClock()
        waits: list[float] = []
        limiter = server._SpawnRateLimiter(1.0, 1.0, clock_fn=clock, sleep_fn=waits.append)
        self.assertTrue(limiter.acquire())
        self.assertFalse(limiter.acquire(max_wait_s=0.5))
        self.assertFalse(limiter.acquire(max_wait_s=0.5))
        self.assertEqual(waits, [])
        clock.sleep(1.0)
        self.assertTrue(limiter.acquire(max_wait_s=0.0), "резерв не списан отказами")

    # --- R-BULK-I2: потолок запусков и Retry Budget ------------------------------------------

    def test_max_total_spawns_ceiling_for_all_retry_class_combinations(self) -> None:
        self.assertEqual(server.MAX_TOTAL_SPAWNS, 3)
        kinds = ("cli_failure", "unmapped", "incomplete_step")
        for sequence in itertools.product(kinds, repeat=5):
            clock = FakeClock()
            res = server._Resilience()
            res.retry_budget = server._RetryBudget(capacity=100.0, clock_fn=clock)
            attempts = server._RequestAttempts(res, clock() + 1e6, sleep_fn=lambda _s: None)
            self.assertTrue(attempts.begin_attempt())
            attempts.note_spawn()
            for kind in sequence:
                if attempts.allow_retry(kind):
                    attempts.note_spawn()
                self.assertLessEqual(attempts.total_spawns, 3, sequence)
            self.assertEqual(attempts.total_spawns, 3, sequence)

    def test_retry_budget_bound_for_100_failing_requests(self) -> None:
        clock = FakeClock()
        budget = server._RetryBudget(6, 0.20, 0.05, clock_fn=clock)
        retries = 0
        for _ in range(100):
            budget.on_request()
            for _retry in range(2):  # каждый запрос падает и хочет оба повтора
                if budget.try_acquire_retry():
                    retries += 1
            clock.sleep(5.0)  # T_w = 500 c
        bound = int(0.20 * 100 + 0.05 * 500) + 6
        self.assertEqual(bound, 51)
        self.assertLessEqual(retries, bound)
        self.assertGreater(retries, 0)
        self.assertLess(retries, 200, "без бюджета было бы 200 повторов")

    def test_retry_budget_starts_full_and_caps(self) -> None:
        clock = FakeClock()
        budget = server._RetryBudget(6, 0.20, 0.05, clock_fn=clock)
        self.assertEqual(sum(budget.try_acquire_retry() for _ in range(10)), 6)
        clock.sleep(20.0)  # +1.0 токен от резерва
        self.assertTrue(budget.try_acquire_retry())
        self.assertFalse(budget.try_acquire_retry())
        clock.sleep(10000.0)
        budget.on_request()
        self.assertEqual(sum(budget.try_acquire_retry() for _ in range(10)), 6, "ёмкость не превышается")

    def test_exhausted_budget_denies_retry_without_sleep_or_spawn(self) -> None:
        clock = FakeClock()
        res = server._Resilience()
        res.retry_budget = server._RetryBudget(0.0, 0.0, 0.0, clock_fn=clock)
        sleeps: list[float] = []
        attempts = server._RequestAttempts(res, clock() + 1e6, sleep_fn=sleeps.append)
        self.assertFalse(attempts.allow_retry("incomplete_step"))
        self.assertEqual((sleeps, attempts.total_spawns, attempts.retries), ([], 0, 0))
        # локальный отказ старта CLI не списывает бюджет: повтор разрешён и при пустом бюджете
        self.assertTrue(attempts.allow_retry("cli_failure", charge_budget=False))
        self.assertEqual(attempts.retries, 1)

    # --- R-BULK-I3: Circuit Breaker -------------------------------------------------------

    def test_breaker_open_after_five_failures_half_open_single_probe(self) -> None:
        clock = FakeClock()
        logs: list[str] = []
        spans: list[tuple[float, float]] = []

        def rng(lo: float, hi: float) -> float:
            spans.append((lo, hi))
            return 1.0

        breaker = server._UpstreamBreaker(5, 10.0, clock_fn=clock, rng_fn=rng, log_fn=logs.append)
        for _ in range(4):
            breaker.record_failure()
        self.assertEqual(breaker.state, "CLOSED")
        self.assertTrue(breaker.allow())
        breaker.record_failure()
        self.assertEqual(breaker.state, "OPEN")
        self.assertEqual(spans, [(0.8, 1.2)])
        self.assertFalse(breaker.allow())
        clock.sleep(9.9)
        self.assertEqual(breaker.state, "OPEN")
        clock.sleep(0.2)
        self.assertEqual(breaker.state, "HALF_OPEN")
        results: list[bool] = []
        barrier = threading.Barrier(10)

        def probe() -> None:
            barrier.wait()
            results.append(breaker.allow())

        threads = [threading.Thread(target=probe) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        self.assertEqual(results.count(True), 1, "в HALF_OPEN ровно одна проба")
        self.assertEqual(breaker.max_half_open_probes, 1)
        breaker.record_failure()  # проба не удалась -> снова OPEN
        self.assertEqual(breaker.state, "OPEN")
        clock.sleep(10.0)
        self.assertTrue(breaker.allow())
        breaker.record_success()
        self.assertEqual(breaker.state, "CLOSED")
        self.assertTrue(any("state=OPEN" in line for line in logs))
        self.assertTrue(any("state=HALF_OPEN" in line for line in logs))
        self.assertTrue(any("state=CLOSED" in line for line in logs))

    def test_breaker_success_resets_failure_streak_and_lost_probe_expires(self) -> None:
        clock = FakeClock()
        breaker = server._UpstreamBreaker(3, 10.0, clock_fn=clock, rng_fn=lambda _lo, hi: hi, log_fn=lambda _m: None)
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_success()
        breaker.record_failure()
        breaker.record_failure()
        self.assertEqual(breaker.state, "CLOSED")
        breaker.record_failure()
        self.assertEqual(breaker.state, "OPEN")
        clock.sleep(12.0)
        self.assertTrue(breaker.allow())      # проба занята
        self.assertFalse(breaker.allow())
        clock.sleep(10.5)                     # результат пробы потерян -> проба истекает
        self.assertTrue(breaker.allow())

    def test_request_attempts_commit_counts_only_final_failure(self) -> None:
        res = server._Resilience()
        res.breaker = server._UpstreamBreaker(1, 60.0, log_fn=lambda _m: None)
        attempts = server._RequestAttempts(res, time.monotonic() + 100)
        attempts.attempt_done(True, False)   # отказ, затем успех повтором
        attempts.attempt_done(False, True)
        attempts.commit()
        self.assertEqual(res.breaker.state, "CLOSED")
        attempts.attempt_done(True, False)   # запрос закончился отказом
        attempts.commit()
        attempts.commit()
        self.assertEqual(res.breaker.state, "OPEN")

    # --- C-MULT-I2 / I4: bulkhead слотов ----------------------------------------------------

    def test_slot_bulkhead_thirteenth_waiter_gets_immediate_overflow(self) -> None:
        bulkhead = server._SlotBulkhead(max_concurrent=6, max_waiters=12, wait_timeout_s=30.0)
        self.assertEqual([bulkhead.acquire_ex() for _ in range(6)], ["ok"] * 6)
        verdicts: list[str] = []

        def waiter() -> None:
            verdict = bulkhead.acquire_ex()
            verdicts.append(verdict)
            if verdict == "ok":
                bulkhead.release()

        threads = [threading.Thread(target=waiter) for _ in range(12)]
        for thread in threads:
            thread.start()
        for _ in range(200):
            if bulkhead.waiters == 12:
                break
            time.sleep(0.01)
        self.assertEqual(bulkhead.waiters, 12)
        started = time.monotonic()
        self.assertEqual(bulkhead.acquire_ex(), "overflow")
        self.assertFalse(bulkhead.acquire())
        self.assertLess(time.monotonic() - started, 0.5, "13-й ждущий получает отказ мгновенно")
        for _ in range(6):
            bulkhead.release()
        for thread in threads:
            thread.join(10)
        self.assertEqual(verdicts, ["ok"] * 12)
        self.assertEqual((bulkhead.in_use, bulkhead.waiters), (0, 0))

    def test_slot_bulkhead_returns_to_zero_after_50_interrupted_requests(self) -> None:
        bulkhead = server._SlotBulkhead(max_concurrent=1, max_waiters=50, wait_timeout_s=0.05)
        self.assertEqual(bulkhead.acquire_ex(), "ok")
        verdicts: list[str] = []
        threads = [threading.Thread(target=lambda: verdicts.append(bulkhead.acquire_ex())) for _ in range(50)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        self.assertEqual(verdicts, ["timeout"] * 50)
        self.assertEqual((bulkhead.in_use, bulkhead.waiters), (1, 0))
        bulkhead.release()
        self.assertEqual(bulkhead.in_use, 0)
        bulkhead.release()  # лишний release не уводит счётчик в минус
        self.assertEqual(bulkhead.in_use, 0)

    def test_slot_bulkhead_cancellation_inside_wait_restores_waiters(self) -> None:
        bulkhead = server._SlotBulkhead(max_concurrent=1, max_waiters=3, wait_timeout_s=30.0)
        self.assertEqual(bulkhead.acquire_ex(), "ok")
        with mock.patch.object(bulkhead._cond, "wait", side_effect=KeyboardInterrupt):
            for _ in range(5):
                with self.assertRaises(KeyboardInterrupt):
                    bulkhead.acquire_ex()
        self.assertEqual((bulkhead.in_use, bulkhead.waiters), (1, 0))

    def test_slot_bulkhead_uses_injected_clock_for_timeout(self) -> None:
        clock = FakeClock()

        class Cond:  # условная переменная без реального ожидания: время двигают часы
            def __init__(self, fake: FakeClock) -> None:
                self._fake = fake

            def __enter__(self) -> "Cond":
                return self

            def __exit__(self, *exc: Any) -> None:
                return None

            def wait(self, timeout: float) -> None:
                self._fake.sleep(timeout)

            def notify(self) -> None:
                return None

        bulkhead = server._SlotBulkhead(max_concurrent=1, max_waiters=1, wait_timeout_s=15.0, clock_fn=clock)
        bulkhead._cond = Cond(clock)  # type: ignore[assignment]
        self.assertEqual(bulkhead.acquire_ex(), "ok")
        self.assertEqual(bulkhead.acquire_ex(), "timeout")
        self.assertEqual(clock.now, 1015.0)

    # --- R-BULK-I1: ожидания и deadline ---------------------------------------------------------

    def test_startup_gate_wait_is_bounded_and_fails_open(self) -> None:
        server._STARTUP_LOCK.acquire()
        try:
            gate = server._StartupGate(wait_s=0.1)
            started = time.monotonic()
            gate.acquire()
            self.assertLess(time.monotonic() - started, 2.0)
            self.assertFalse(gate._held)
            gate.release()  # no-op: замок чужой
            self.assertTrue(server._STARTUP_LOCK.locked())
        finally:
            server._STARTUP_LOCK.release()
        gate = server._StartupGate(wait_s=0.1)
        gate.acquire()
        self.assertTrue(gate._held)
        gate.release()
        self.assertFalse(server._STARTUP_LOCK.locked())
        self.assertEqual((server.STARTUP_WAIT_S, server.STARTUP_GATE_S), (5.0, 12.0))

    def test_deadline_in_the_past_blocks_next_attempt_and_sleep(self) -> None:
        res = server._Resilience()
        sleeps: list[float] = []
        attempts = server._RequestAttempts(res, time.monotonic() - 1.0, sleep_fn=sleeps.append)
        self.assertFalse(attempts.begin_attempt())
        self.assertFalse(attempts.allow_retry("incomplete_step"))
        self.assertEqual((sleeps, attempts.total_spawns), ([], 0))

    def test_retry_sleep_never_exceeds_remaining_deadline(self) -> None:
        res = server._Resilience()
        sleeps: list[float] = []
        attempts = server._RequestAttempts(res, time.monotonic() + 0.3, sleep_fn=sleeps.append,
                                           rng_fn=lambda _lo, hi: hi)
        with mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.8):
            self.assertTrue(attempts.allow_retry("cli_failure"))
        self.assertEqual(len(sleeps), 1)
        self.assertLessEqual(sleeps[0], 0.3)

    # --- H-CPU-I2 / I3: горячий путь ------------------------------------------------------------

    def test_disabled_step_recovery_does_not_touch_regexes(self) -> None:
        spies = {name: mock.Mock() for name in ("_ACTION_INTENT_RE", "_REASONING_TOOL_PLAN_RE",
                                                "_FINAL_CONCLUSION_RE", "_INTERRUPTED_RE", "_RAW_CALL_RE",
                                                "_NO_TOOLS_RE", "_CALL_INTENT_RE")}
        patches = [mock.patch.object(server, name, spy) for name, spy in spies.items()]
        patches.append(mock.patch.object(server, "STEP_RECOVERY_ENABLED", False))
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.assertFalse(server._is_incomplete_tool_step("Читаю…", "plan " * 50, TOOLS, had_mid_stream_error=True,
                                                         output_tokens=900))
        self.assertEqual(sum(spy.search.call_count + spy.match.call_count for spy in spies.values()), 0)

    def test_hot_path_has_no_regex_compile_or_deepcopy(self) -> None:
        import copy
        with (mock.patch.object(re, "_compile", wraps=re._compile) as compiled,
              mock.patch.object(copy, "deepcopy", wraps=copy.deepcopy) as deep):
            for text, reasoning in (("Читаю…", ""), (PREAMBLE, PLAN), ("Привет!", "no tools needed"),
                                    (SWALLOWED_TEXT, "x"), ("Ответ: 42:", "job_output bash")):
                server._is_incomplete_tool_step(text, reasoning, TOOLS, output_tokens=100)
                server._detect_incomplete_tool_step_signal(text, reasoning, TOOLS, True, 300, 150)
            server._is_transient_stream_error({"statusCode": 503, "message": "ECONNRESET"})
            server._retry_backoff_s(2)
        self.assertEqual((compiled.call_count, deep.call_count), (0, 0))

    # --- Расчётные оракулы по константам модуля -------------------------------------------------

    def test_hl_env_01_memory_closure_by_module_constants(self) -> None:
        self.assertEqual(server.STDOUT_QUEUE_MAX, 4096)
        rss_worker, rss_child, mem_limit = 64 * 2**20, 192 * 2**20, 2048 * 2**20
        shared = 6 * rss_child
        self.assertEqual(rss_worker + shared, 1275068416)
        self.assertLessEqual(rss_worker + shared, 0.80 * mem_limit)

    def test_c_mult_i1_i5_by_module_constants(self) -> None:
        concurrent = 6  # MAX_CONCURRENT из plist; дефолт кода (2) укладывается тем более
        self.assertLessEqual(max(server.MAX_CONCURRENT, 1), concurrent)
        self.assertLessEqual(concurrent * 1, 0.60 * 10)
        self.assertEqual(server.MAX_SLOT_WAITERS, 2 * concurrent)
        fds = 1 + (concurrent + server.MAX_SLOT_WAITERS) + concurrent * 3 + 1 + 20
        self.assertLessEqual(fds, 128)
        self.assertLessEqual(128, 0.70 * 4096)
        self.assertLessEqual(0.6 * 1 * 60.0 + 12, 0.50 * (1 * 16383))

    def test_r_bulk_i1_total_auxiliary_wait_by_module_constants(self) -> None:
        cap = server.RETRY_BACKOFF_CAP_S
        base = server.RETRY_BACKOFF_BASE_S
        total = 0.0
        for attempt in range(1, server.MAX_TOTAL_SPAWNS + 1):
            slot_wait = server.SLOT_WAIT_TIMEOUT_S if attempt == 1 else 0.0
            backoff = 0.0 if attempt == 1 else min(cap, base * 2 ** (attempt - 1))
            total += slot_wait + server.STARTUP_WAIT_S + server.SPAWN_WAIT_MAX_S + backoff
        self.assertEqual(total, 48.0)
        self.assertLessEqual(total, 0.30 * 180.0)

    def test_h_cpu_i5_utilisation_by_module_constants(self) -> None:
        t_req = 0.02 + server.MAX_TOTAL_SPAWNS * 0.05
        util = 1.0 * 0.2 * t_req / 1 + 0.02
        self.assertAlmostEqual(util, 0.054, places=6)
        self.assertLessEqual(util, 0.70)
        self.assertLessEqual(util + 0.25, 0.80 * 2.0)

    def test_new_constants_match_architecture_packet(self) -> None:
        self.assertEqual((server.CB_FAIL_THRESHOLD, server.CB_RESET_S), (5, 10.0))
        self.assertEqual((server.RETRY_BUDGET_MAX, server.RETRY_BUDGET_PER_REQUEST,
                          server.RETRY_BUDGET_RESERVE_RPS), (6.0, 0.20, 0.05))
        self.assertEqual((server.SPAWN_RATE_PER_S, server.SPAWN_BURST), (1.0, 1.0))
        self.assertEqual((server.MAX_SLOT_WAITERS, server.SLOT_WAIT_TIMEOUT_S), (12, 15.0))
        self.assertEqual(server.KEEPALIVE_INTERVAL_S, 15.0)
        self.assertLessEqual(server.FAIL_RETRY_LIMIT, server.MAX_TOTAL_SPAWNS - 1)

    def test_server_gets_isolated_resilience_and_main_uses_module_default(self) -> None:
        first = server.Server(("127.0.0.1", 0), server.Handler)
        second = server.Server(("127.0.0.1", 0), server.Handler)
        self.addCleanup(first.server_close)
        self.addCleanup(second.server_close)
        self.assertIsNot(first.resilience, second.resilience)
        self.assertIs(server._slots, server._DEFAULT_RESILIENCE.slots)


if __name__ == "__main__":
    unittest.main()
