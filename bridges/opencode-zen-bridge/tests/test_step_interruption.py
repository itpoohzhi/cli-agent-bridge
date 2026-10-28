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

import contextlib
import io
import json
import os
import socket
import tempfile
import threading
import unittest
from unittest import mock
import urllib.request
from pathlib import Path
from typing import Any
from typing import Protocol, cast

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
BROKEN_FRAGMENT = "{broken"
BROKEN_INVOKE = "<tool_invoke>" + BROKEN_FRAGMENT + "</tool_invoke>"
# Боевой вызов: bash-heredoc с лишней `}` перед закрывающим тегом.
OVERCLOSED_INVOKE = ('<tool_invoke>{"id": "call_1", "name": "bash", "arguments": {"command": '
                     '"cat > a.py <<\'EOF\'\\nprint({1: 2})\\nEOF", "description": "write"}}}</tool_invoke>')
PLAN = ("One message: job_output(bash-4a99049e1f764309) + bash check state.json. "
        "Let me do: 1. job_output for fetch 2. bash: cat state.json")
CALLS = ('<tool_call>{"name": "job_output", "arguments": {"job_id": "bash-4a99"}}</tool_call>'
         '<tool_call>{"name": "bash", "arguments": {"command": "cat state.json", '
         '"description": "Show state"}}</tool_call>')
INVOKE_CALLS = CALLS.replace("tool_call", "tool_invoke")
# Реальный шаг glm-5.3-flash-free: апстрим вырезал `<tool_call>…` из text, а 97 токенов выставил.
SWALLOWED_TEXT = "2026-10-24 (MSK) — статус: проверяю вывод джобы job_fetch_01 и читаю goal.md."

FAKE_OPENCODE = r"""#!/usr/bin/env python3
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
elif mode == "emit_raw":
    text(os.environ["FAKE_OC_RAW"])
    finish()
elif mode == "raw_then_calls" and n == 0:
    text(os.environ["FAKE_OC_PREAMBLE"] + os.environ["FAKE_OC_RAW"])
    finish()
elif mode == "unmapped_then_promise" and n < 2:
    ev({"type": "tool_use", "part": {"tool": "todoread", "state": {"status": "error", "input": {}}}})
    finish()
elif mode == "unmapped_then_promise" and n == 2:
    reasoning(os.environ["FAKE_OC_PLAN"])
    text(os.environ["FAKE_OC_STATUS"])
    finish()
elif mode == "unmapped_incomplete_calls" and n == 0:
    ev({"type": "tool_use", "part": {"tool": "todoread", "state": {"status": "error", "input": {}}}})
    finish()
elif mode == "unmapped_incomplete_calls" and n == 1:
    reasoning(os.environ["FAKE_OC_PLAN"])
    text(os.environ["FAKE_OC_STATUS"])
    finish()
else:
    text(calls)
    finish()
"""


class _EnvPatcher(Protocol):
    """Протокол patch.dict для изоляции окружения."""

    def start(self) -> object:
        """Запустить patch."""
        ...

    def stop(self) -> object:
        """Остановить patch."""
        ...


class TestStepInterruptionLive(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        fake = Path(cls.tmp.name) / "opencode"
        fake.write_text(FAKE_OPENCODE, "utf-8")
        fake.chmod(0o755)
        cls.saved = (server.OPENCODE_BIN, server.AUTH_KEY, server.DEFAULTWORKDIR, server.LOG_PATH)
        cls.env_patch = allow_child_env("FAKE_OC_COUNTER", "FAKE_OC_MODE", "FAKE_OC_PLAN",
                                        "FAKE_OC_PREAMBLE", "FAKE_OC_STATUS", "FAKE_OC_CALLS", "FAKE_OC_SWALLOW",
                                        "FAKE_OC_RAW")
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
    _fake_env: object = None

    def setUp(self) -> None:
        # Изоляция REQ-017: свежий бюджет повторов на каждый тест, без сброса в проде.
        self.httpd.resilience = server._Resilience()
        self.counter = Path(self.tmp.name) / f"counter-{self.id()}"
        # RW-032: все FAKE_OC_* изолированы patch.dict — предустановленные значения восстановятся.
        self._fake_env = mock.patch.dict(
            os.environ,
            {
                "FAKE_OC_COUNTER": str(self.counter),
                "FAKE_OC_PLAN": PLAN,
                "FAKE_OC_PREAMBLE": PREAMBLE,
                "FAKE_OC_STATUS": STATUS_ONLY,
                "FAKE_OC_CALLS": CALLS,
                "FAKE_OC_SWALLOW": SWALLOWED_TEXT,
            },
            clear=False,
        )
        _ = cast(_EnvPatcher, self._fake_env).start()

    def tearDown(self) -> None:
        _ = cast(_EnvPatcher, self._fake_env).stop()

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

    # --- RW-003 (цикл 10): reasoning побайтово, маркер вычищается только из content -----

    def test_interrupted_artifact_removed_from_reasoning_stream(self) -> None:
        os.environ["FAKE_OC_MODE"] = "reasoning_interrupted"
        raw = self._post(stream=True).decode()
        chunks = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: {")]
        thoughts = "".join(c["choices"][0]["delta"].get("reasoning_content") or "" for c in chunks)
        content_parts: list[str] = []
        for line in raw.splitlines():
            if not line.startswith("data: {"):
                continue
            parsed = server._loads_object(line[6:]) or {}
            choices = parsed.get("choices")
            if isinstance(choices, list) and choices:
                delta = server._as_dict(server._as_dict(choices[0]).get("delta"))
                value = delta.get("content")
                if isinstance(value, str):
                    content_parts.append(value)
        content = "".join(content_parts)
        marker = (
            "The previous response was interrupted. Continue from where you left off "
            "without repeating completed content."
        )
        self.assertEqual(thoughts, marker + "Simple greeting.")
        self.assertEqual(content, "Привет!")
        self.assertNotIn("interrupted", content)
        self.assertEqual(self._runs(), 1)

    def test_interrupted_artifact_removed_from_reasoning_json(self) -> None:
        os.environ["FAKE_OC_MODE"] = "reasoning_interrupted"
        out = json.loads(self._post(stream=False))
        message = out["choices"][0]["message"]
        marker = (
            "The previous response was interrupted. Continue from where you left off "
            "without repeating completed content."
        )
        self.assertEqual(message["reasoning_content"], marker + "Simple greeting.")
        self.assertEqual(message["content"], "Привет!")
        self.assertEqual(out["choices"][0]["finish_reason"], "stop")
        self.assertEqual(self._runs(), 1)

    # --- Бюджеты повторов раздельные -----------------------------------------------------

    def test_unmapped_retries_do_not_exhaust_incomplete_budget_stream(self) -> None:
        """REQ-017/MAX_TOTAL_SPAWNS=3: unmapped-повторы не исчерпывают бюджет шага (итого 3 запуска)."""
        os.environ["FAKE_OC_MODE"] = "unmapped_then_promise"
        content, finishes, names = self._stream()
        self.assertEqual(self._runs(), 3)
        self.assertEqual(names, [])
        self.assertEqual(finishes, ["stop"])
        self.assertEqual(content.count("Собираю факты"), 1)

    def test_unmapped_retries_do_not_exhaust_incomplete_budget_json(self) -> None:
        """REQ-017/MAX_TOTAL_SPAWNS=3: unmapped-повторы не исчерпывают бюджет шага (итого 3 запуска)."""
        os.environ["FAKE_OC_MODE"] = "unmapped_then_promise"
        raw_post = self._post(stream=False)
        raw_text = raw_post.decode("utf-8") if isinstance(raw_post, bytes) else raw_post
        parsed_obj: object = server._loads_object(raw_text)
        self.assertIsInstance(parsed_obj, dict)
        choices_obj = (
            parsed_obj.get("choices") if isinstance(parsed_obj, dict) else None
        )
        self.assertIsInstance(choices_obj, list)
        choice_obj = (
            choices_obj[0] if isinstance(choices_obj, list) and choices_obj else {}
        )
        self.assertIsInstance(choice_obj, dict)
        message_obj = (
            choice_obj.get("message") if isinstance(choice_obj, dict) else None
        )
        self.assertIsInstance(message_obj, dict)
        self.assertEqual(self._runs(), 3)
        self.assertEqual(
            message_obj.get("tool_calls") or []
            if isinstance(message_obj, dict)
            else [],
            [],
        )
        self.assertEqual(
            choice_obj.get("finish_reason") if isinstance(choice_obj, dict) else None,
            "stop",
        )

    def test_unmapped_then_incomplete_then_calls_within_cap_stream(self) -> None:
        os.environ["FAKE_OC_MODE"] = "unmapped_incomplete_calls"
        _content, finishes, names = self._stream()
        self.assertEqual(self._runs(), 3)
        self.assertEqual(names, ["job_output", "bash"])
        self.assertEqual(finishes, ["tool_calls"])

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


    # --- Битый блок вызова (2026-10-24): не в SSE/JSON content и не в повторный промпт --------------------

    def _assert_reprompt_clean(self) -> None:
        reprompt = self._prompts()[1]
        self.assertIn(PREAMBLE, reprompt)
        self.assertNotIn(BROKEN_FRAGMENT, reprompt)

    def test_stream_broken_block_not_in_sse_nor_reprompt(self) -> None:
        os.environ["FAKE_OC_MODE"] = "raw_then_calls"
        os.environ["FAKE_OC_RAW"] = BROKEN_INVOKE
        os.environ["FAKE_OC_CALLS"] = INVOKE_CALLS
        content, finishes, names = self._stream(model=GLM_MODEL)
        self.assertEqual(self._runs(), 2)
        self.assertNotIn("<tool_invoke>", content)
        self.assertNotIn(BROKEN_FRAGMENT, content)
        self.assertIn("забираю вывод", content)
        self.assertEqual(names, ["job_output", "bash"])
        self.assertEqual(finishes, ["tool_calls"])
        self._assert_reprompt_clean()

    def test_json_broken_block_not_in_content_nor_reprompt(self) -> None:
        os.environ["FAKE_OC_MODE"] = "raw_then_calls"
        os.environ["FAKE_OC_RAW"] = BROKEN_INVOKE
        os.environ["FAKE_OC_CALLS"] = INVOKE_CALLS
        out = json.loads(self._post(stream=False, model=GLM_MODEL))
        message = out["choices"][0]["message"]
        self.assertEqual(self._runs(), 2)
        self.assertNotIn("<tool_invoke>", message["content"])
        self.assertNotIn(BROKEN_FRAGMENT, message["content"])
        self.assertEqual([c["function"]["name"] for c in message["tool_calls"]], ["job_output", "bash"])
        self._assert_reprompt_clean()

    def test_stream_recovered_trailing_braces_single_spawn(self) -> None:
        os.environ["FAKE_OC_CALLS"] = OVERCLOSED_INVOKE
        content, finishes, names = self._stream(model=GLM_MODEL)
        self.assertEqual(self._runs(), 1)
        self.assertEqual(names, ["bash"])
        self.assertEqual(finishes, ["tool_calls"])
        self.assertNotIn("<tool_invoke>", content)

    def test_json_recovered_trailing_braces_single_spawn(self) -> None:
        os.environ["FAKE_OC_CALLS"] = OVERCLOSED_INVOKE
        out = json.loads(self._post(stream=False, model=GLM_MODEL))
        self.assertEqual(self._runs(), 1)
        self.assertEqual([c["function"]["name"] for c in out["choices"][0]["message"]["tool_calls"]], ["bash"])

    def test_stream_notice_when_only_broken_block(self) -> None:
        os.environ["FAKE_OC_MODE"] = "emit_raw"
        os.environ["FAKE_OC_RAW"] = BROKEN_INVOKE
        content, finishes, names = self._stream(model=GLM_MODEL)
        self.assertLessEqual(self._runs(), 3)
        self.assertEqual(names, [])
        self.assertEqual(content, server._BROKEN_BLOCK_NOTICE)
        self.assertEqual(finishes, ["stop"])

    def test_serve_json_broken_block_stripped_and_notice(self) -> None:
        os.environ["FAKE_OC_MODE"] = "emit_raw"
        os.environ["FAKE_OC_RAW"] = BROKEN_INVOKE
        out = json.loads(self._post(stream=False, model=GLM_MODEL))
        choice = out["choices"][0]
        self.assertLessEqual(self._runs(), 3)
        self.assertEqual(choice["message"]["content"], server._BROKEN_BLOCK_NOTICE)
        self.assertNotIn("tool_calls", choice["message"])
        self.assertEqual(choice["finish_reason"], "stop")

    def test_serve_json_mixed_valid_and_broken(self) -> None:
        os.environ["FAKE_OC_MODE"] = "emit_raw"
        os.environ["FAKE_OC_RAW"] = BROKEN_INVOKE + INVOKE_CALLS
        out = json.loads(self._post(stream=False, model=GLM_MODEL))
        message = out["choices"][0]["message"]
        self.assertEqual(self._runs(), 1)
        self.assertEqual([c["function"]["name"] for c in message["tool_calls"]], ["job_output", "bash"])
        self.assertNotIn("<tool_invoke>", message["content"])
        self.assertNotIn(BROKEN_FRAGMENT, message["content"])
        self.assertNotIn(server._BROKEN_BLOCK_NOTICE, message["content"])


class TestStripBrokenBlocks(unittest.TestCase):
    BROKEN = "<tool_invoke>{broken</tool_invoke>"
    VALID = '<tool_invoke>{"name": "a", "arguments": {}}</tool_invoke>'

    def test_strip_broken_blocks_helper(self) -> None:
        strip = server._strip_broken_tool_blocks
        plain = "Просто текст без тегов."
        out, dropped = strip(plain)
        self.assertIs(out, plain)
        self.assertEqual(dropped, 0)
        self.assertEqual(strip(f"до {self.BROKEN} после"), ("до  после", 1))
        self.assertEqual(strip("до <tool_call>{broken</tool_call> после"), ("до  после", 1))
        # незакрытый хвост отбрасывается целиком
        self.assertEqual(strip('Текст <tool_call>{"name": "read", "arguments": {"f'), ("Текст ", 1))
        # валидные блоки (одиночный, пачка без промежуточных закрытий) — те же байты, тот же объект
        batch = ('<tool_call>{"name": "a", "arguments": {}}\n<tool_call>{"name": "b", "arguments": {}}'
                 '</tool_call>')
        for kept in (self.VALID, batch, f"x {self.VALID} y"):
            with self.subTest(kept=kept[:30]):
                out, dropped = strip(kept)
                self.assertIs(out, kept)
                self.assertEqual(dropped, 0)
        # валидный блок с лишней `}` разбирается и сохраняется
        overclosed = '<tool_invoke>{"name": "a", "arguments": {}}}</tool_invoke>'
        self.assertEqual(strip(overclosed), (overclosed, 0))
        # смешанный текст: битый уходит, валидный остаётся
        self.assertEqual(strip(f"{self.BROKEN}{self.VALID}"), (self.VALID, 1))
        # цитаты markdown (inline и fenced) — не вызовы
        quoted = ("Блок `<tool_call>` открывает вызов, а пример `x <tool_call>{broken</tool_call>` - код.\n"
                  "```\n<tool_invoke>{broken</tool_invoke>\n```\n")
        self.assertEqual(strip(quoted), (quoted, 0))
        # слишком глубокая вложенность — «не разбирается», а не исключение
        deep = "<tool_invoke>" + '{"a":' * 100000 + "}</tool_invoke>"
        self.assertEqual(strip(deep), ("", 1))

    def test_strip_cap_is_fail_closed(self) -> None:
        text = "".join("a" + self.BROKEN for _ in range(20))
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            out, dropped = server._strip_broken_tool_blocks(text)
        self.assertIn("tool_strip_cap_hit", err.getvalue())  # метка не должна маскироваться как секрет
        quiet = io.StringIO()
        with contextlib.redirect_stderr(quiet):
            server._strip_broken_tool_blocks(text, quiet=True)
        self.assertNotIn("tool_strip_cap_hit", quiet.getvalue())
        self.assertEqual(out, "a" * (server._STRIP_SCAN_MAX_TAGS + 1))
        self.assertEqual(dropped, server._STRIP_SCAN_MAX_TAGS + 1)
        self.assertNotIn("<tool_invoke>", out)

    def test_sanitize_strips_malformed_closed_tool_invoke(self) -> None:
        text = f"Смотрю.\n{self.BROKEN}\nДальше."
        out = server._sanitize_assistant_text(text)
        self.assertNotIn("<tool_invoke>", out)
        self.assertNotIn("{broken", out)
        self.assertIn("Смотрю.", out)
        self.assertIn("Дальше.", out)
        overclosed = '<tool_invoke>{"name": "a", "arguments": {}}}</tool_invoke>'
        self.assertEqual(server._sanitize_assistant_text(overclosed), overclosed)

    def test_incomplete_prompt_has_no_broken_block(self) -> None:
        prompt = server._incomplete_tool_step_prompt(
            "PROMPT", f"Статус: собираю. {self.BROKEN}", TOOLS, None, GLM_MODEL)
        self.assertIn("Статус: собираю.", prompt)
        self.assertNotIn("{broken", prompt)

    def test_strip_scan_is_bounded_broken_block(self) -> None:
        import time
        cases = {
            "closed_invoke": self.BROKEN * 1000,
            "closed_call": "<tool_call>{broken</tool_call>" * 1000,
            "unclosed": "<tool_invoke>{" * 1000,
            "mixed": ("x" + self.VALID + self.BROKEN) * 500,
        }
        for label, text in cases.items():
            with self.subTest(case=label):
                started = time.perf_counter()
                out, dropped = server._strip_broken_tool_blocks(text)
                elapsed = time.perf_counter() - started
                self.assertLess(elapsed, 0.05)
                self.assertGreater(dropped, 0)
                self.assertNotIn("{broken", out)
                self.assertNotIn("<tool_call>{", out.replace(self.VALID, ""))
                self.assertNotIn("<tool_invoke>{broken", out)


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


if __name__ == "__main__":
    unittest.main()
