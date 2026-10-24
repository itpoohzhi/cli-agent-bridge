#!/usr/bin/env python3
"""Regression: `opencode run` завершился rc=1 без вывода (2026-10-10 16:27, живой сбой DSH).

Баг: два параллельных `opencode run` стартовали в одну секунду, один упал за ~1 с
(`Error: Unexpected error … database is locked`, sqlite opencode), мост отдал в SSE
обычный пустой `finish_reason:"stop"` -> DSH: `EMPTY_RESPONSE: model returned a
completed response with no content`.

Ожидается: (1) rc != 0 без вывода никогда не даёт пустого успешного ответа: SSE —
OpenAI-style error-чанк с хвостом stderr, non-stream — 502; (2) транзиторный отказ
(`database is locked`) повторяется, а детерминированный отказ провайдера (HTTP 403) — нет;
(3) хвост stderr пишется в bridge.log.
"""

from __future__ import annotations

import json
import os
import socket
import tempfile
import threading
import time
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

FAKE_OPENCODE = r'''#!/usr/bin/env python3
import json, os, sys
counter = os.environ["FAKE_OC_COUNTER"]
n = int(open(counter).read()) if os.path.exists(counter) else 0
open(counter, "w").write(str(n + 1))
sys.stdin.read()
mode = os.environ.get("FAKE_OC_MODE", "fail")
def ev(o): print(json.dumps(o), flush=True)
if mode in ("slow_ok", "silent"):
    import time
    open(os.environ["FAKE_OC_PID"], "w").write(str(os.getpid()))
    time.sleep(float(os.environ.get("FAKE_OC_DELAY", "30")))
if mode == "fail":
    sys.stderr.write("\x1b[91m\x1b[1mError: \x1b[0mfatal boom xyz\n")
    sys.exit(1)
if mode == "locked_once" and n == 0:
    sys.stderr.write("\x1b[91m\x1b[1mError: \x1b[0mUnexpected error\n\ndatabase is locked\n")
    sys.exit(1)
if mode == "locked":
    sys.stderr.write("Error: Unexpected error\n\ndatabase is locked\n")
    sys.exit(1)
if mode == "provider429":
    ev({"type": "error", "error": {"name": "APIError", "data": {"statusCode": 429, "message": "FreeUsageLimitError"}}})
    sys.exit(1)
if mode == "provider403":
    ev({"type": "error", "error": {"name": "APIError", "data": {"statusCode": 403, "message": "free tier denied"}}})
    sys.exit(1)
ev({"type": "text", "part": {"text": "Суббота"}})
ev({"type": "step_finish", "part": {"tokens": {"input": 10, "output": 5}}})
'''


class TestCliFailure(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        fake = Path(cls.tmp.name) / "opencode"
        fake.write_text(FAKE_OPENCODE, "utf-8")
        fake.chmod(0o755)
        cls.saved = (server.OPENCODE_BIN, server.AUTH_KEY, server.DEFAULTWORKDIR, server.LOG_PATH,
                     server.FAIL_RETRY_BACKOFF_S)
        cls.env_patch = allow_child_env("FAKE_OC_COUNTER", "FAKE_OC_MODE", "FAKE_OC_DELAY", "FAKE_OC_PID")
        cls.env_patch.start()
        server.OPENCODE_BIN = str(fake)
        server.AUTH_KEY = "test-key"
        server.DEFAULTWORKDIR = Path(cls.tmp.name) / "ws"
        server.LOG_PATH = Path(cls.tmp.name) / "bridge.log"
        server.FAIL_RETRY_BACKOFF_S = 0.0
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

    def tearDown(self) -> None:
        os.environ.pop("FAKE_OC_COUNTER", None)
        os.environ.pop("FAKE_OC_MODE", None)
        os.environ.pop("FAKE_OC_DELAY", None)
        os.environ.pop("FAKE_OC_PID", None)

    def _post(self, stream: bool) -> tuple[int, bytes]:
        body = json.dumps({"model": "muse-spark-1.3-contributor-free", "stream": stream,
                           "messages": [{"role": "user", "content": "Какой сегодня день недели?"}],
                           "tools": []}).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/chat/completions", data=body,
                                     headers={"Authorization": "Bearer test-key",
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            with exc:
                return exc.code, exc.read()

    def _sse(self) -> tuple[list[dict[str, Any]], str]:
        status, raw = self._post(stream=True)
        self.assertEqual(status, 200)
        text = raw.decode()
        chunks = [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: {")]
        return chunks, text

    def _runs(self) -> int:
        return int(self.counter.read_text())

    def test_stream_rc1_no_output_is_error_not_empty_stop(self) -> None:
        os.environ["FAKE_OC_MODE"] = "fail"
        chunks, _ = self._sse()
        errors = [c["error"] for c in chunks if "error" in c]
        self.assertEqual(len(errors), 1, chunks)
        self.assertIn("fatal boom xyz", errors[0]["message"])
        self.assertNotIn("\x1b", errors[0]["message"])
        finishes = [c["choices"][0].get("finish_reason") for c in chunks
                    if c.get("choices") and c["choices"][0].get("finish_reason")]
        self.assertEqual(finishes, [])

    def test_stream_failure_stderr_tail_in_log(self) -> None:
        os.environ["FAKE_OC_MODE"] = "fail"
        self._sse()
        self.assertIn("fatal boom xyz", server.LOG_PATH.read_text("utf-8"))

    def test_json_rc1_no_output_is_502_with_stderr(self) -> None:
        os.environ["FAKE_OC_MODE"] = "fail"
        status, raw = self._post(stream=False)
        self.assertEqual(status, 502)
        self.assertIn("fatal boom xyz", raw.decode())

    def test_stream_database_locked_is_retried(self) -> None:
        os.environ["FAKE_OC_MODE"] = "locked_once"
        chunks, _ = self._sse()
        self.assertEqual(self._runs(), 2)
        self.assertFalse([c for c in chunks if "error" in c])
        content = "".join(c["choices"][0]["delta"].get("content") or ""
                          for c in chunks if c.get("choices"))
        self.assertEqual(content, "Суббота")

    def test_json_database_locked_is_retried(self) -> None:
        os.environ["FAKE_OC_MODE"] = "locked_once"
        status, raw = self._post(stream=False)
        self.assertEqual(status, 200)
        self.assertEqual(self._runs(), 2)
        self.assertEqual(json.loads(raw)["choices"][0]["message"]["content"], "Суббота")

    def test_stream_persistent_lock_gives_error_after_limit(self) -> None:
        os.environ["FAKE_OC_MODE"] = "locked"
        chunks, _ = self._sse()
        self.assertEqual(self._runs(), server.FAIL_RETRY_LIMIT + 1)
        errors = [c["error"] for c in chunks if "error" in c]
        self.assertEqual(len(errors), 1)
        self.assertIn("database is locked", errors[0]["message"])

    def test_provider_403_not_retried_and_reported(self) -> None:
        os.environ["FAKE_OC_MODE"] = "provider403"
        chunks, _ = self._sse()
        self.assertEqual(self._runs(), 1)
        errors = [c["error"] for c in chunks if "error" in c]
        self.assertEqual(len(errors), 1)
        self.assertIn("free tier denied", errors[0]["message"])

    def test_stream_provider_429_is_retried_then_reported(self) -> None:
        # 429 FreeUsageLimitError транзиторен (лимит по IP): каждый повтор — новый процесс и новое соединение.
        os.environ["FAKE_OC_MODE"] = "provider429"
        chunks, _ = self._sse()
        self.assertEqual(self._runs(), server.FAIL_RETRY_LIMIT + 1)
        errors = [c["error"] for c in chunks if "error" in c]
        self.assertEqual(len(errors), 1)
        self.assertIn("FreeUsageLimitError", errors[0]["message"])

    def test_json_provider_429_is_retried_then_502(self) -> None:
        os.environ["FAKE_OC_MODE"] = "provider429"
        status, raw = self._post(stream=False)
        self.assertEqual(status, 502)
        self.assertEqual(self._runs(), server.FAIL_RETRY_LIMIT + 1)
        self.assertIn("FreeUsageLimitError", raw.decode())

    def test_retryable_failure_classification(self) -> None:
        self.assertTrue(server._is_retryable_failure(1, "limit", 429, False))
        self.assertTrue(server._is_retryable_failure(1, "locked", None, False))
        self.assertFalse(server._is_retryable_failure(1, "denied", 403, False))
        self.assertFalse(server._is_retryable_failure(1, "limit", 429, True))
        self.assertFalse(server._is_retryable_failure(-15, "killed", None, False))

    def test_healthy_run_unchanged(self) -> None:
        os.environ["FAKE_OC_MODE"] = "ok"
        chunks, text = self._sse()
        self.assertEqual(self._runs(), 1)
        self.assertFalse([c for c in chunks if "error" in c])
        self.assertTrue(text.rstrip().endswith("data: [DONE]"))

    # --- тишина stdout `opencode run`: keepalive и дедлайн (клиент рвёт молчащий SSE-стрим) ---

    def _silent_cli(self, mode: str, delay: float, timeout_s: float, keepalive_s: float) -> Path:
        os.environ["FAKE_OC_MODE"] = mode
        os.environ["FAKE_OC_DELAY"] = str(delay)
        pid_file = Path(self.tmp.name) / f"pid-{self.id()}"
        os.environ["FAKE_OC_PID"] = str(pid_file)
        for name, value in (("TIMEOUT_S", timeout_s), ("KEEPALIVE_INTERVAL_S", keepalive_s)):
            patcher = mock.patch.object(server, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        return pid_file

    def _assert_process_killed(self, pid_file: Path) -> None:
        pid = int(pid_file.read_text())
        for _ in range(40):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.05)
        self.fail(f"opencode pid {pid} пережил дедлайн")

    def test_stream_sse_emits_keepalive_during_stdout_silence(self) -> None:
        self._silent_cli("slow_ok", delay=0.4, timeout_s=30.0, keepalive_s=0.05)
        chunks, text = self._sse()
        deltas = [c["choices"][0]["delta"] for c in chunks if c.get("choices")]
        self.assertEqual(deltas[0], {"role": "assistant", "content": ""})
        pong = deltas.index({"content": "Суббота"})
        self.assertGreaterEqual(deltas[1:pong].count({"content": ""}), 1, deltas)
        self.assertEqual(chunks[-1]["choices"][0].get("finish_reason"), "stop")
        self.assertTrue(text.rstrip().endswith("data: [DONE]"))

    def test_stream_sse_enforces_deadline_during_stdout_silence(self) -> None:
        pid_file = self._silent_cli("silent", delay=8.0, timeout_s=1.0, keepalive_s=10.0)
        started = time.monotonic()
        chunks, text = self._sse()
        self.assertLess(time.monotonic() - started, 4.0)
        errors = [c["error"] for c in chunks if "error" in c]
        self.assertEqual(len(errors), 1, chunks)
        self.assertIn("opencode timed out after", errors[0]["message"])
        self.assertTrue(text.rstrip().endswith("data: [DONE]"))
        self.assertEqual(self._runs(), 1)  # таймаут не ретраится
        self._assert_process_killed(pid_file)

    def test_run_execute_once_enforces_deadline_during_stdout_silence(self) -> None:
        pid_file = self._silent_cli("silent", delay=8.0, timeout_s=1.0, keepalive_s=10.0)
        started = time.monotonic()
        out = server.Run("muse-spark-1.3-contributor-free", "Проверка", "", Path(self.tmp.name) / "ws")._execute_once()
        self.assertLess(time.monotonic() - started, 4.0)
        self.assertEqual(out["state"], "timeout")
        self.assertEqual(out["finish"], "error")
        self._assert_process_killed(pid_file)


if __name__ == "__main__":
    unittest.main()
