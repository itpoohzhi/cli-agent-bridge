"""Интеграционные тесты мульти-бинарного фасада: Muse через настоящий HTTP-handler (RW-013).

Фейковый Muse — bash-обёртка (пишет argv/env/prompt, по файлу `mode` отдаёт JSONL), фейковый
Droid — tests/fake_droid.py из bridge_testlib. Проверяются сквозные ветки фасада: POST muse-модели
JSON/SSE с разбором `<tool_call>` (общий `finalize_turn`), backend_error -> 502 с detail,
preflight -> 503 до spawn, отказ b_guard для muse под unsafe при живом droid-чате, независимость
ёмкости backend (Droid отвечает, пока muse занят), обрыв SSE-клиента с очисткой, а также
отсутствие пользовательского текста backend'а в журнале (RW-007) и unit-ветки finalize_turn /
_error_body.
"""

import hashlib
import json
import os
import socket
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from adapters import ADAPTER_KINDS  # noqa: E402
from bridge_testlib import BridgeCase, TOOLS, chat_body  # noqa: E402
from core.backend_adapter import AdapterRegistry  # noqa: E402

TOOL_JSON = (
    '{"payload_type":"run.output.delta","payload":{"text":"<tool_call>'
    '{\\"name\\": \\"get_weather\\", \\"arguments\\": {\\"city\\": \\"Paris\\"}}'
    '</tool_call>"}}'
)

WRAPPER = r"""#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
n=$(cat "$DIR/count" 2>/dev/null || echo 0); n=$((n+1)); echo $n > "$DIR/count"
printf '%s\n' "$@" > "$DIR/argv.$$"
env > "$DIR/env.$$"
while [ $# -gt 0 ]; do
  if [ "$1" = "--prompt-file" ]; then cp "$2" "$DIR/prompt.$$"; fi
  shift
done
mode=$(cat "$DIR/mode")
case "$mode" in
  ok)
    echo '{"payload_type":"run.output.delta","payload":{"text":"Hello "}}'
    echo '{"payload_type":"run.output.delta","payload":{"text":"world"}}'
    echo '{"payload_type":"run.terminal.completed","payload":{"terminal":"completed"}}' ;;
  tool)
    cat <<'EOF'
@TOOL@
{"payload_type":"run.terminal.completed","payload":{"terminal":"completed"}}
EOF
    ;;
  noterminal)
    echo '{"payload_type":"run.output.delta","payload":{"text":"partial"}}' ;;
  failed)
    echo '{"payload_type":"run.terminal.failed","payload":{"terminal":"failed","reason":"boom"}}' ;;
  sentinel)
    echo "invalid prompt: patient John has HIV" >&2
    echo '{"payload_type":"run.terminal.failed","payload":{"terminal":"failed","reason":"invalid prompt: patient John has HIV"}}' ;;
  sleep)
    echo $$ > "$DIR/pid"
    sleep 30 ;;
esac
"""


class FakeMuse:
    """Фейковая обёртка muse-cli.sh со счётчиком запусков и слушающим «прокси»."""

    def __init__(self, base: Path):
        base.mkdir(parents=True, exist_ok=True)
        self.base = base
        self.wrapper = base / "muse-cli.sh"
        self.wrapper.write_text(WRAPPER.replace("@TOOL@", TOOL_JSON), encoding="utf-8")
        self.wrapper.chmod(0o755)
        self.set_mode("ok")
        self._proxy = socket.socket()
        self._proxy.bind(("127.0.0.1", 0))
        self._proxy.listen(8)
        self.proxy_port = self._proxy.getsockname()[1]

    def set_mode(self, mode: str) -> None:
        (self.base / "mode").write_text(mode, encoding="utf-8")

    def count(self) -> int:
        try:
            return int((self.base / "count").read_text())
        except (OSError, ValueError):
            return 0

    def pin(self) -> dict:
        digest = hashlib.sha256(self.wrapper.read_bytes()).hexdigest()
        return {"binary_path": str(self.wrapper), "binary_sha256": digest}

    def close(self) -> None:
        self._proxy.close()


def wait_pid_gone(pid: int, timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


class HubCase(BridgeCase):
    """Мост с фейковым Droid (bridge_testlib) и фейковым Muse в BACKENDS."""

    def setUp(self):
        super().setUp()
        self.fake_muse = FakeMuse(Path(self._tmp.name) / "muse-fake")
        self.addCleanup(self.fake_muse.close)

        def mutate(data):
            muse = data["backends"]["muse"]
            muse["wrapper"] = str(self.fake_muse.wrapper)
            muse["proxy_port"] = self.fake_muse.proxy_port
            muse["technical_ref"] = self.fake_muse.pin()

        catalog = self.stand(mutate)
        self._saved_backends = server.BACKENDS
        self.registry = AdapterRegistry.from_fleet(
            catalog, ADAPTER_KINDS, lambda: server.FLEET, server
        )
        server.BACKENDS = self.registry
        self.addCleanup(self._restore_backends)

    def _restore_backends(self):
        self.registry.shutdown()
        server.BACKENDS = self._saved_backends

    @property
    def muse(self):
        return self.registry.get("muse")

    def _sse_socket(self, body: dict):
        raw = json.dumps(body).encode("utf-8")
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=10)
        self.addCleanup(sock.close)
        sock.sendall(
            b"POST /v1/chat/completions HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Authorization: Bearer test-key\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: " + str(len(raw)).encode() + b"\r\n\r\n" + raw
        )
        return sock


class TestMuseFacade(HubCase):
    def test_json_tool_calls_200(self):
        """POST muse-модели JSON: 200 + tool_calls из общего finalize_turn."""
        self.fake_muse.set_mode("tool")
        status, body = self._post_json(chat_body(model="muse-spark-1.3", tools=TOOLS))
        self.assertEqual(status, 200)
        choice = body["choices"][0]
        self.assertEqual(choice["finish_reason"], "tool_calls")
        call = choice["message"]["tool_calls"][0]
        self.assertEqual(call["type"], "function")
        self.assertEqual(call["function"]["name"], "get_weather")
        self.assertEqual(json.loads(call["function"]["arguments"]), {"city": "Paris"})
        self.assertNotIn(server.TOOL_CALL_OPEN, choice["message"]["content"] or "")
        self.assertEqual(body["model"], "muse-spark-1.3")

    def test_json_plain_text_200(self):
        status, body = self._post_json(chat_body(model="muse-spark-1.3"))
        self.assertEqual(status, 200)
        self.assertEqual(body["choices"][0]["message"]["content"], "Hello world")
        self.assertEqual(body["choices"][0]["finish_reason"], "stop")
        self.assertGreater(body["usage"]["total_tokens"], 0)

    def test_sse_tool_calls_200(self):
        """POST muse-модели SSE: кадры вызова и finish_reason tool_calls, затем [DONE]."""
        self.fake_muse.set_mode("tool")
        status, stream = self._post(
            chat_body(model="muse-spark-1.3", stream=True, tools=TOOLS)
        )
        self.assertEqual(status, 200)
        self.assertIn('"tool_calls"', stream)
        self.assertIn('"finish_reason": "tool_calls"', stream)
        self.assertTrue(stream.rstrip().endswith("data: [DONE]"))

    def test_sse_plain_text_200(self):
        status, stream = self._post(chat_body(model="muse-spark-1.3", stream=True))
        self.assertEqual(status, 200)
        self.assertIn("Hello ", stream)
        self.assertIn('"finish_reason": "stop"', stream)
        self.assertTrue(stream.rstrip().endswith("data: [DONE]"))

    def test_missing_terminal_is_502_with_detail(self):
        """RW-004: delta + EOF без terminal.completed -> 502 backend_error с detail."""
        self.fake_muse.set_mode("noterminal")
        status, body = self._post_json(chat_body(model="muse-spark-1.3"))
        self.assertEqual(status, 502)
        self.assertEqual(body["error"]["type"], "proxy_error")
        self.assertEqual(body["error"]["code"], 502)
        self.assertIn("muse", body["error"]["message"])
        self.assertIn("terminal_missing", body["error"]["detail"])

    def test_failed_terminal_is_502(self):
        self.fake_muse.set_mode("failed")
        status, body = self._post_json(chat_body(model="muse-spark-1.3"))
        self.assertEqual(status, 502)
        self.assertIn("terminal_failed", body["error"]["detail"])
        self.assertIn("boom", body["error"]["detail"])

    def test_preflight_failure_is_503_before_spawn(self):
        self.fake_muse.wrapper.chmod(0o644)
        status, body = self._post_json(chat_body(model="muse-spark-1.3"))
        self.assertEqual(status, 503)
        self.assertEqual(body["error"]["type"], "launcher_unavailable")
        self.assertEqual(self.fake_muse.count(), 0)

    def test_proxy_down_is_503_before_spawn(self):
        self.fake_muse._proxy.close()
        status, body = self._post_json(chat_body(model="muse-spark-1.3"))
        self.assertEqual(status, 503)
        self.assertEqual(body["error"]["type"], "launcher_unavailable")
        self.assertIn("proxy_down", body["error"]["message"])
        self.assertEqual(self.fake_muse.count(), 0)

    def test_stderr_sentinel_stays_out_of_journal(self):
        """RW-007: сырой stderr/reason — только в ответ клиенту, не в постоянный журнал."""
        self.fake_muse.set_mode("sentinel")
        with self.capture_logs() as lines:
            status, body = self._post_json(chat_body(model="muse-spark-1.3"))
        self.assertEqual(status, 502)
        self.assertIn("John", body["error"]["detail"])
        journal = "\n".join(lines)
        self.assertNotIn("John", journal)
        self.assertNotIn("HIV", journal)

    def test_unsafe_guard_refuses_new_muse_chat_but_keeps_droid_continuation(self):
        """RW-008: ключ существующего droid-чата не делает muse-запрос продолжением."""
        key = "guard-key-1"
        block = {
            "role": "user",
            "content": "Instructions from: AGENTS.md\npayload",
        }
        scenario = [
            ("text", "droid ok"),
            ("result", {"finalText": "", "usage": {}}),
            ("done", (0, "")),
        ]
        self.hub.legacy([scenario, scenario])
        # 1) резидентный droid-чат создаётся до перехода guard в unsafe.
        status, _ = self._post_json(
            chat_body(
                model="claude-sonnet-5-5",
                prompt_cache_key=key,
                messages=[block],
            )
        )
        self.assertEqual(status, 200)
        saved = server.GUARD.snapshot
        server.GUARD.snapshot = lambda: ("unsafe", ["TEST"], 60000)
        self.addCleanup(lambda: setattr(server.GUARD, "snapshot", saved))
        # 2) продолжение droid-чата проходит как раньше.
        status, _ = self._post_json(
            chat_body(
                model="claude-sonnet-5-5",
                prompt_cache_key=key,
                messages=[block],
            )
        )
        self.assertEqual(status, 200)
        # 3) muse с тем же ключом — новый чат (sessions=none): 503 до spawn.
        status, body = self._post_json(
            chat_body(
                model="muse-spark-1.3",
                prompt_cache_key=key,
                messages=[block],
            )
        )
        self.assertEqual(status, 503)
        self.assertEqual(body["error"]["type"], "launcher_unavailable")
        self.assertIn("instruction guard is unsafe", body["error"]["message"])
        self.assertEqual(self.fake_muse.count(), 0)

    def test_droid_stays_available_while_muse_is_busy(self):
        """RW-013: насыщение muse (max_concurrent=1) не отбирает ёмкость droid."""
        self.fake_muse.set_mode("sleep")
        self.hub.legacy(
            [
                [
                    ("text", "droid ok"),
                    ("result", {"finalText": "", "usage": {}}),
                    ("done", (0, "")),
                ]
            ]
        )
        sock = self._sse_socket(chat_body(model="muse-spark-1.3", stream=True))
        deadline = time.monotonic() + 10
        while self.muse.active_count() == 0 and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertEqual(self.muse.active_count(), 1)
        status, body = self._post_json(chat_body(model="claude-sonnet-5-5"))
        self.assertEqual(status, 200)
        self.assertEqual(body["choices"][0]["message"]["content"], "droid ok")
        sock.close()
        deadline = time.monotonic() + 15
        while self.muse.active_count() != 0 and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertEqual(self.muse.active_count(), 0)

    def test_stream_abort_kills_muse_child(self):
        """Обрыв SSE-клиента: ход muse прекращается, процесс группы не остаётся."""
        self.fake_muse.set_mode("sleep")
        sock = self._sse_socket(chat_body(model="muse-spark-1.3", stream=True))
        pid_file = self.fake_muse.base / "pid"
        deadline = time.monotonic() + 10
        while not pid_file.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(pid_file.exists(), "muse child never started")
        pid = int(pid_file.read_text())
        sock.close()
        self.assertTrue(wait_pid_gone(pid), "muse child survived stream abort")
        deadline = time.monotonic() + 10
        while self.muse.active_count() != 0 and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertEqual(self.muse.active_count(), 0)


class TestFinalizeTurn(unittest.TestCase):
    def test_emulate_true_parses_tool_calls(self):
        raw = {
            "text": 'pre <tool_call>{"name": "t", "arguments": {"a": 1}}</tool_call> post',
            "reasoning": "think",
        }
        out = server.finalize_turn(dict(raw), True)
        self.assertEqual(out["text"], "pre  post")
        self.assertEqual(len(out["tool_calls"]), 1)
        self.assertEqual(out["tool_calls"][0]["function"]["name"], "t")
        self.assertEqual(
            json.loads(out["tool_calls"][0]["function"]["arguments"]), {"a": 1}
        )
        self.assertEqual(
            [kind for kind, _ in out["events"]],
            ["reasoning", "content", "tool_call", "content"],
        )
        self.assertEqual(out["usage"], {})
        self.assertEqual(out["result"], {})

    def test_emulate_false_keeps_raw_text(self):
        raw = {"text": '<tool_call>{"name": "t"}</tool_call>'}
        out = server.finalize_turn(dict(raw), False)
        self.assertEqual(out["tool_calls"], [])
        self.assertEqual(out["text"], raw["text"])
        self.assertEqual([kind for kind, _ in out["events"]], ["content"])

    def test_existing_events_are_returned_untouched(self):
        raw = {"events": [("content", "x")], "text": "x"}
        self.assertIs(server.finalize_turn(raw, True), raw)


class TestErrorBody(unittest.TestCase):
    def test_backend_error_is_502_with_detail(self):
        err = server.Handler._error_body(
            {
                "state": "backend_error",
                "rc": 1,
                "err": "terminal_missing: boom",
                "backend_kind": "muse",
            }
        )
        self.assertEqual((err["code"], err["type"]), (502, "proxy_error"))
        self.assertIn("muse", err["message"])
        self.assertIn("terminal_missing", err["detail"])

    def test_launcher_unavailable_is_503(self):
        err = server.Handler._error_body(
            {"state": "launcher_unavailable", "rc": 1, "err": "pin_missing"}
        )
        self.assertEqual((err["code"], err["type"]), (503, "launcher_unavailable"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
