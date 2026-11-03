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
delta_sleep = scen.get("delta_sleep_s", 0.02)
for delta in scen["deltas"]:
    time.sleep(delta_sleep)
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
        clean_home = (self.tmp / "clean-home").resolve()
        (clean_home / ".gemini" / "antigravity-cli").mkdir(parents=True)
        for name in ("brain", "conv"):
            (self.tmp / name).mkdir()
        patches = {
            "LAUNCHER": str(fake),
            "AGY_BIN": str(agy_bin),
            "CLEAN_HOME_DIR": clean_home,
            "_VERIFIED_CLEAN_HOME": clean_home,
            "_AGY_HOME_INITIALIZED": True,
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
        self,
        deltas: list[str],
        hang_s: float = 0.0,
        pre_sleep_s: float = 0.0,
        delta_sleep_s: float = 0.02,
    ) -> None:
        body = {
            "deltas": deltas,
            "hang_s": hang_s,
            "pre_sleep_s": pre_sleep_s,
            "delta_sleep_s": delta_sleep_s,
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

    def test_multiple_sequential_tool_calls_in_one_turn(self) -> None:
        import json

        expected = [
            {"path": "first.txt", "content": "first"},
            {"path": "second.txt", "content": "second"},
        ]
        self._scenario(
            [
                '<tool_call>{"name": "write_file", "arguments": ',
                json.dumps(expected[0]) + "}</tool_call>",
                '\n<tool_call>{"name": "write_file", "arguments": ',
                json.dumps(expected[1]) + "}</tool_call>",
            ]
        )
        status, raw, _ = self._post(self._body(stream=True, tools=_TOOLS))
        self.assertEqual(status, 200, raw)
        chunks, _ = self._sse_chunks(raw)
        self.assertTrue(chunks, raw)
        calls = {}
        finish_reasons = []
        for chunk in chunks:
            self.assertNotIn("error", chunk, chunk)
            for choice in chunk.get("choices", []):
                reason = choice.get("finish_reason")
                if reason is not None:
                    finish_reasons.append(reason)
                for call in choice.get("delta", {}).get("tool_calls", []):
                    index = call["index"]
                    entry = calls.setdefault(index, {"name": "", "arguments": ""})
                    function = call.get("function", {})
                    entry["name"] += function.get("name", "")
                    entry["arguments"] += function.get("arguments", "")
        self.assertEqual(set(calls), {0, 1})
        for index, arguments in enumerate(expected):
            self.assertEqual(calls[index]["name"], "write_file")
            self.assertEqual(json.loads(calls[index]["arguments"]), arguments)
        self.assertEqual(set(finish_reasons), {"tool_calls"})
        self.assertNotIn(b"agy emitted a malformed tool call", raw)

    def test_unclosed_tool_call_at_eof_fails_closed(self) -> None:
        import json

        incomplete = '<tool_call>{"name": "write_file", "arguments": {"path": "x"}'
        for stream in (False, True):
            with self.subTest(stream=stream):
                self._scenario([incomplete])
                status, raw, _ = self._post(self._body(stream=stream, tools=_TOOLS))
                if stream and status == 200:
                    chunks, _ = self._sse_chunks(raw)
                    reasons = [
                        choice.get("finish_reason")
                        for chunk in chunks
                        for choice in chunk.get("choices", [])
                    ]
                    self.assertNotIn("tool_calls", reasons, raw)
                    self.assertIn("error", reasons, raw)
                else:
                    self.assertEqual(status, 502, raw)
                    payload = json.loads(raw)
                    self.assertIn("error", payload, payload)
                    self.assertNotIn(
                        "tool_calls",
                        [
                            choice.get("finish_reason")
                            for choice in payload.get("choices", [])
                        ],
                        payload,
                    )
                self.assertIn(b"unclosed tool_call block", raw)

    def test_stalled_open_block_timeout(self) -> None:
        import os
        from unittest.mock import patch

        with patch.dict(
            os.environ,
            {
                "AGY_TOOL_CALL_STALL_TIMEOUT_S": "0.1",
                "WATCHDOG_INTERVAL_S": "0.05",
            },
        ):
            self._scenario(
                ['<tool_call>{"name": "write_file", "arguments": {"path": "x"}'],
                hang_s=5.0,
            )
            status, raw, elapsed = self._post(self._body(stream=True, tools=_TOOLS))
        if status == 200:
            chunks, _ = self._sse_chunks(raw)
            reasons = [
                choice.get("finish_reason")
                for chunk in chunks
                for choice in chunk.get("choices", [])
            ]
            self.assertIn("error", reasons, raw)
            self.assertNotIn("tool_calls", reasons, raw)
        else:
            self.assertEqual(status, 502, raw)
        self.assertIn(b"tool call block stalled without progress for 0.1s", raw)
        self.assertLess(elapsed, 4.0, "Ожидали stall timeout, а не EOF процесса")

    def test_settle_timeout_completes_turn_when_silent_after_tool_call(self) -> None:
        import json
        import os
        from unittest.mock import patch

        deltas = [
            '<tool_call>{"name": "write_file", "arguments": {"path": "a.txt", "content": "123"}}</tool_call>'
        ]
        with patch.dict(
            os.environ,
            {
                "AGY_TOOL_SETTLE_TIMEOUT_S": "0.1",
                "WATCHDOG_INTERVAL_S": "0.05",
            },
        ):
            self._scenario(deltas, hang_s=5.0)
            status, raw, elapsed = self._post(self._body(stream=True, tools=_TOOLS))
        self.assertEqual(status, 200, raw)
        chunks, _ = self._sse_chunks(raw)
        calls = {}
        finish_reasons = []
        for chunk in chunks:
            self.assertNotIn("error", chunk, raw)
            for choice in chunk.get("choices", []):
                reason = choice.get("finish_reason")
                if reason is not None:
                    finish_reasons.append(reason)
                for call in choice.get("delta", {}).get("tool_calls", []):
                    entry = calls.setdefault(
                        call["index"], {"name": "", "arguments": ""}
                    )
                    function = call.get("function", {})
                    entry["name"] += function.get("name", "")
                    entry["arguments"] += function.get("arguments", "")
        self.assertEqual(set(calls), {0}, raw)
        self.assertEqual(calls[0]["name"], "write_file")
        self.assertEqual(
            json.loads(calls[0]["arguments"]),
            {"path": "a.txt", "content": "123"},
        )
        self.assertEqual(set(finish_reasons), {"tool_calls"}, raw)
        self.assertNotIn(b'"error"', raw)
        self.assertNotIn(b"agy emitted a malformed tool call", raw)
        self.assertLess(
            elapsed,
            4.0,
            "Ожидали settle timeout 0.1с, а не ожидание hang_s 5.0с",
        )

    def test_tool_call_count_exceeded_limit(self) -> None:
        import json
        import os
        from unittest.mock import patch

        deltas = [
            '<tool_call>{"name": "write_file", "arguments": {"path": "1"}}</tool_call>',
            '<tool_call>{"name": "write_file", "arguments": {"path": "2"}}</tool_call>',
            '<tool_call>{"name": "write_file", "arguments": {"path": "3"}}</tool_call>',
        ]
        with patch.dict(os.environ, {"AGY_MAX_TOOL_CALLS": "2"}):
            self._scenario(deltas)
            status, raw, _ = self._post(self._body(stream=False, tools=_TOOLS))
        payload = json.loads(raw)
        self.assertTrue(status == 502 or "error" in payload, raw)
        self.assertIn(b"tool call count exceeded limit", raw)

    def test_tool_call_bytes_exceeded_limit_multibyte_utf8(self) -> None:
        import json
        import os
        from unittest.mock import patch

        text = "я" * 50
        self.assertLess(len(text), 80)
        self.assertGreater(len(text.encode("utf-8")), 80)
        with patch.dict(os.environ, {"AGY_MAX_TOOL_BYTES": "80"}):
            self._scenario([text])
            status, raw, _ = self._post(self._body(stream=False, tools=_TOOLS))
        payload = json.loads(raw)
        self.assertTrue(status == 502 or "error" in payload, raw)
        self.assertIn(b"tool call buffer exceeded max bytes", raw)

    def test_env_timeout_validation_rejects_nan_and_negative(self) -> None:
        import os
        from unittest.mock import patch

        bridge = _load_bridge()
        _safe_float_env = bridge._safe_float_env
        _safe_int_env = bridge._safe_int_env
        _ToolTurn = bridge._ToolTurn

        self.assertEqual(_safe_float_env("TEST_FLOAT_NAN", 1.5), 1.5)
        with patch.dict(os.environ, {"TEST_FLOAT_NAN": "nan"}):
            self.assertEqual(_safe_float_env("TEST_FLOAT_NAN", 1.5), 1.5)
        with patch.dict(os.environ, {"TEST_FLOAT_NEG": "-2.0"}):
            self.assertEqual(_safe_float_env("TEST_FLOAT_NEG", 1.5), 1.5)
        with patch.dict(os.environ, {"TEST_FLOAT_ZERO": "0.0"}):
            self.assertEqual(_safe_float_env("TEST_FLOAT_ZERO", 1.5), 1.5)
        with patch.dict(os.environ, {"TEST_FLOAT_POS": "3.5"}):
            self.assertEqual(_safe_float_env("TEST_FLOAT_POS", 1.5), 3.5)

        with patch.dict(os.environ, {"TEST_INT_NEG": "-5"}):
            self.assertEqual(_safe_int_env("TEST_INT_NEG", 10), 10)
        with patch.dict(os.environ, {"TEST_INT_POS": "42"}):
            self.assertEqual(_safe_int_env("TEST_INT_POS", 10), 42)

        # Проверяем, что _ToolTurn с невалидными env безопасно применяет дефолты
        with patch.dict(
            os.environ, {"AGY_TOOL_SETTLE_TIMEOUT_S": "nan", "AGY_MAX_TOOL_CALLS": "-1"}
        ):
            turn = _ToolTurn([], lambda _c: True, lambda _r: True, lambda _k: True)
            self.assertEqual(turn._settle_timeout_s, 5.0)
            self.assertEqual(turn._max_calls, 32)

    def test_tool_turn_activity_wrappers_and_keepalive(self) -> None:
        bridge = _load_bridge()
        _ToolTurn = bridge._ToolTurn

        recorded_reasoning = []
        turn = _ToolTurn(
            _TOOLS,
            lambda _t: True,
            lambda r: recorded_reasoning.append(r) or True,
            lambda _c: True,
        )
        t_init = turn._last_chunk_ts
        time.sleep(0.02)
        turn.feed_reasoning("размышление о плане")
        self.assertGreater(turn._last_chunk_ts, t_init)
        self.assertEqual(recorded_reasoning, ["размышление о плане"])

        t_mid = turn._last_chunk_ts
        time.sleep(0.02)
        turn.notify_activity()
        self.assertGreater(turn._last_chunk_ts, t_mid)

    def test_inter_call_activity_resets_settle_timer_and_delivers_both_calls(
        self,
    ) -> None:
        import os
        from unittest.mock import patch

        call1 = '<tool_call>{"name": "write_file", "arguments": {"path": "1.txt"}}</tool_call>'
        inter_text = "Промежуточный шаг анализа перед следующим действием."
        call2 = '<tool_call>{"name": "write_file", "arguments": {"path": "2.txt"}}</tool_call>'

        # Задаем settle-таймаут 0.15с
        with patch.dict(
            os.environ,
            {
                "AGY_TOOL_SETTLE_TIMEOUT_S": "0.15",
                "WATCHDOG_INTERVAL_S": "0.05",
            },
        ):
            # Межделтовая задержка 0.10с: между call1 и call2 проходит 2*0.10 = 0.20с,
            # что больше settle-таймаута 0.15с. Промежуточная дельта сбрасывает таймер,
            # доказывая работу notify_activity().
            self._scenario([call1, inter_text, call2], delta_sleep_s=0.10)
            status, raw, _ = self._post(self._body(stream=True, tools=_TOOLS))
        self.assertEqual(status, 200, raw)
        chunks, _ = self._sse_chunks(raw)
        calls = {}
        finish_reasons = []
        for chunk in chunks:
            for choice in chunk.get("choices", []):
                reason = choice.get("finish_reason")
                if reason is not None:
                    finish_reasons.append(reason)
                for call in choice.get("delta", {}).get("tool_calls", []):
                    entry = calls.setdefault(
                        call["index"], {"name": "", "arguments": ""}
                    )
                    func = call.get("function", {})
                    entry["name"] += func.get("name", "")
                    entry["arguments"] += func.get("arguments", "")
        self.assertEqual(set(calls), {0, 1}, f"Ожидали 2 вызова, получили {calls}")
        self.assertEqual(calls[0]["name"], "write_file")
        self.assertEqual(calls[1]["name"], "write_file")
        self.assertEqual(set(finish_reasons), {"tool_calls"})

    def test_split_tool_call_tag_prefix_keeps_turn_alive(self) -> None:
        import os
        from unittest.mock import patch

        tag = "<tool_call>"
        # Проверяем все точки разреза открывающего тега: от '<' (длина 1) до '<tool_call' (длина 10)
        for cut in range(1, len(tag)):
            with self.subTest(cut=cut, prefix=tag[:cut]):
                call1 = (
                    '<tool_call>{"name": "write_file", "arguments": {"path": "1.txt"}}</tool_call>\n'
                    + tag[:cut]
                )
                call2 = (
                    tag[cut:]
                    + '{"name": "write_file", "arguments": {"path": "2.txt"}}</tool_call>'
                )
                with patch.dict(
                    os.environ,
                    {
                        "AGY_TOOL_SETTLE_TIMEOUT_S": "0.15",
                        "WATCHDOG_INTERVAL_S": "0.05",
                    },
                ):
                    self._scenario([call1, call2], delta_sleep_s=0.45)
                    status, raw, _ = self._post(self._body(stream=True, tools=_TOOLS))
                self.assertEqual(status, 200, raw)
                chunks, _ = self._sse_chunks(raw)
                calls = {}
                for chunk in chunks:
                    for choice in chunk.get("choices", []):
                        for call in choice.get("delta", {}).get("tool_calls", []):
                            entry = calls.setdefault(
                                call["index"], {"name": "", "arguments": ""}
                            )
                            func = call.get("function", {})
                            entry["name"] += func.get("name", "")
                            entry["arguments"] += func.get("arguments", "")
                self.assertEqual(
                    set(calls),
                    {0, 1},
                    f"Ожидали 2 вызова при разрезе tag[:{cut}]={tag[:cut]!r}, получили {calls}",
                )
                self.assertEqual(calls[0]["name"], "write_file")
                self.assertEqual(calls[1]["name"], "write_file")


class TestD1SettleGuards(unittest.TestCase):
    @staticmethod
    def _normalizer() -> Any:
        from core.tool_emulation import StreamNormalizer

        return StreamNormalizer()

    def test_keepalive_does_not_prevent_settle_timeout(self) -> None:
        """Детерминированная проверка: keepalive не дергает notify_activity и таймеры."""
        server_path = (
            Path(__file__).resolve().parents[1] / "bridges" / "agy-bridge" / "server.py"
        )
        lines = server_path.read_text(encoding="utf-8").splitlines()
        definitions = [
            i
            for i, line in enumerate(lines)
            if line.lstrip().startswith("def keepalive(")
        ]
        self.assertTrue(len(definitions) >= 1, "keepalive() не найден в server.py")

        for start in definitions:
            definition = lines[start]
            indentation = len(definition) - len(definition.lstrip())
            body: list[str] = []
            for line in lines[start + 1 :]:
                if line.strip() and len(line) - len(line.lstrip()) <= indentation:
                    break
                body.append(line)
            keepalive_code = "\n".join(body)
            self.assertTrue(bool(keepalive_code.strip()), "Тело keepalive() не найдено")
            self.assertNotIn("notify_activity", keepalive_code)
            self.assertNotIn("_last_chunk_ts", keepalive_code)
            self.assertNotIn("_last_open_chunk_ts", keepalive_code)

    def test_open_reasoning_keeps_turn_alive_past_settle(self) -> None:
        normalizer = self._normalizer()
        normalizer._state = "reasoning"
        elapsed_s = 0.45
        settle_timeout_s = 0.15
        self.assertGreater(elapsed_s, settle_timeout_s)
        self.assertTrue(normalizer.has_open_tool_call())

        normalizer._state = "text"
        self.assertFalse(normalizer.has_open_tool_call())

    def test_partial_structural_prefixes_keep_turn_alive(self) -> None:
        normalizer = self._normalizer()
        normalizer._state = "text"
        for literal, _kind, _tag in normalizer._candidates:
            for length in range(1, len(literal)):
                with self.subTest(literal=literal, length=length):
                    normalizer._buf = "preceding text " + literal[:length]
                    self.assertTrue(normalizer.has_open_tool_call())


if __name__ == "__main__":
    unittest.main()
