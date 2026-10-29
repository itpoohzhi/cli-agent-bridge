#!/usr/bin/env python3
"""Реалтайм-размышление serve-транспорта и watchdog legacy-пути (REQ-001..REQ-020)."""

from __future__ import annotations

import ast
import gc
import hashlib
import http.client
import io
import json
import os
import queue
import signal
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TypeVar, cast
from unittest import mock

import server
from tests._fixtures import install_test_models

if TYPE_CHECKING:
    from typing import override
else:
    _OverrideT = TypeVar("_OverrideT")

    def override(method: _OverrideT) -> _OverrideT:
        """Сохранить декорируемый метод на Python без typing.override."""
        return method


_ = install_test_models(server)
MODEL = "muse-spark-1.3-contributor-free"


class _Patcher(Protocol):
    """Минимальный протокол patch-объекта unittest.mock для тестов."""

    def start(self) -> object:
        """Запустить patch."""
        ...

    def stop(self) -> object:
        """Остановить patch."""
        ...


LEGACY_FAKE = r"""#!/usr/bin/env python3
import json, os, sys, time
def ev(o): print(json.dumps(o), flush=True)
mode = os.environ.get("FAKE_RT_MODE", "fast")
prompt = sys.stdin.read()
if mode == "slow":
    time.sleep(1.6)
    ev({"type": "reasoning", "part": {"text": "Думаю медленно"}})
    ev({"type": "text", "part": {"text": "Готово"}})
    ev({"type": "step_finish", "part": {"tokens": {"input": 3, "output": 2}}})
elif mode == "silent":
    time.sleep(8)
elif mode == "stall":
    ev({"type": "reasoning", "part": {"text": "Первая мысль"}})
    time.sleep(8)
else:
    ev({"type": "reasoning", "part": {"text": "Simple greeting."}})
    ev({"type": "text", "part": {"text": "Привет!"}})
    ev({"type": "step_finish", "part": {"tokens": {"input": 3, "output": 2}}})
"""

FAKE_SERVE = r"""#!/usr/bin/env python3
import base64, json, os, re, socket, struct, sys, threading, time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.stderr.write("x" * 70000 + "\n"); sys.stderr.flush()
if len(sys.argv) > 1 and sys.argv[1] == "run":
    time.sleep(1.2)
    print(json.dumps({"type": "reasoning", "part": {"text": "Поздняя мысль"}}), flush=True)
    print(json.dumps({"type": "text", "part": {"text": "Поздний ответ"}}), flush=True)
    print(json.dumps({"type": "step_finish", "part": {"tokens": {"input": 1, "output": 1}}}), flush=True)
    raise SystemExit(0)
port = int(sys.argv[sys.argv.index("--port") + 1])
password = os.environ.get("OPENCODE_SERVER_PASSWORD", "")
state = {"prompt": "", "cancelled": False, "rejected": False, "interrupted": False, "record": ""}
lock = threading.Lock()
def expected_auth():
    return "Basic " + base64.b64encode(("opencode:" + password).encode()).decode()
class H(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def check(self):
        if self.headers.get("Authorization") != expected_auth():
            self.send_response(401); self.end_headers(); return False
        return True
    def send_json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path == "/api/info":
            self.send_json(200, {"version": "2.1.2", "pid": os.getpid()}); return
        if not self.check(): return
        if self.path == "/api/session/active":
            self.send_json(200, {"data": {}}); return
        if self.path == "/api/event":
            self.send_response(200); self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache"); self.end_headers()
            def emit(obj):
                self.wfile.write(("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n").encode()); self.wfile.flush()
            emit({"id": "e0", "type": "server.connected", "data": {}})
            deadline = time.time() + 30
            while time.time() < deadline and not state["prompt"]:
                time.sleep(0.02)
            prompt = state["prompt"]
            if "__record:" in prompt:
                rec = prompt.split("__record:", 1)[1].split("__", 1)[0]
                state["record"] = rec
                Path_write = rec
                with open(Path_write, "w") as fh:
                    json.dump({"argv": sys.argv, "pid": os.getpid(), "pgid": os.getpgid(0),
                               "has_opencode_bin_env": "OPENCODE_BIN" in os.environ,
                               "db": os.environ.get("OPENCODE_DB", "")}, fh)
            sid = "ses_test1"
            if "__native_pause__" in prompt:
                time.sleep(0.4)
                emit({"id": "nt1", "type": "session.tool.input.started", "data": {"sessionID": sid, "id": "nc1", "name": "bash"}})
                emit({"id": "nt2", "type": "session.tool.called", "data": {"sessionID": sid, "id": "nc1", "name": "bash", "input": {"command": "pwd"}}})
                time.sleep(0.4)
                emit({"id": "nt3", "type": "session.execution.succeeded", "data": {"sessionID": sid}}); return
            if "__never_event__" in prompt:
                time.sleep(10); return
            emit({"id": "e1", "type": "session.execution.started", "data": {"sessionID": sid}})
            if "__silent__" in prompt:
                time.sleep(10); return
            if "__stall__" in prompt:
                emit({"id": "es", "type": "session.reasoning.delta", "data": {"sessionID": sid, "assistantMessageID": "m1", "delta": "Первая мысль"}})
                time.sleep(10); return
            if "__slow__" in prompt:
                time.sleep(1.4)
            if "__form_missing_title__" in prompt or "__form_ok__" in prompt:
                form = {"id": "form1", "sessionID": sid}
                if "__form_ok__" in prompt: form.update({"title": "Вопрос", "fields": []})
                emit({"id": "ef", "type": "form.created", "data": {"form": form}})
                time.sleep(0.6)
                if not state["cancelled"]:
                    emit({"id": "e2", "type": "session.text.delta", "data": {"sessionID": sid, "assistantMessageID": "m1", "delta": "STEP2"}})
                emit({"id": "e3", "type": "session.step.ended", "data": {"sessionID": sid, "assistantMessageID": "m1", "tokens": {"input": 1, "output": 1, "reasoning": 0, "cache": {"read": 0, "write": 0}}}})
                emit({"id": "e4", "type": "session.execution.succeeded", "data": {"sessionID": sid}}); return
            if "__permission__" in prompt or "__native_tool__" in prompt:
                emit({"id": "ep", "type": "permission.asked", "data": {"id": "per1", "sessionID": sid, "action": "bash", "resources": ["*"], "source": {"type": "tool", "messageID": "m1", "id": "call1"}}})
                emit({"id": "et1", "type": "session.tool.input.started", "data": {"sessionID": sid, "assistantMessageID": "m1", "id": "call1", "name": "bash"}})
                emit({"id": "et2", "type": "session.tool.input.delta", "data": {"sessionID": sid, "assistantMessageID": "m1", "id": "call1", "delta": "{\"command\": \"printf probe\"}"}})
                emit({"id": "et3", "type": "session.tool.input.ended", "data": {"sessionID": sid, "assistantMessageID": "m1", "id": "call1", "text": "{\"command\": \"printf probe\"}"}})
                emit({"id": "et4", "type": "session.tool.failed", "data": {"sessionID": sid, "assistantMessageID": "m1", "id": "call1", "error": {"type": "permission.rejected", "message": "Rejected"}, "executed": False}})
                emit({"id": "e5", "type": "session.step.ended", "data": {"sessionID": sid, "assistantMessageID": "m1", "tokens": {"input": 5, "output": 3, "reasoning": 1, "cache": {"read": 2, "write": 9}}}})
                emit({"id": "e6", "type": "session.execution.succeeded", "data": {"sessionID": sid}}); return
            if "__tool_text__" in prompt:
                for part in ["<tool_in", "voke>{\"name\": \"bash\", \"arguments\": ", "{\"command\": \"echo hi\", \"description\": \"x\"}}</tool_invoke>"]:
                    emit({"id": "etx", "type": "session.text.delta", "data": {"sessionID": sid, "assistantMessageID": "m1", "delta": part}}); time.sleep(0.05)
                emit({"id": "e7", "type": "session.step.ended", "data": {"sessionID": sid, "assistantMessageID": "m1", "tokens": {"input": 5, "output": 3, "reasoning": 1, "cache": {"read": 2, "write": 9}}}})
                emit({"id": "e8", "type": "session.execution.succeeded", "data": {"sessionID": sid}}); return
            sent_times = []
            for i in range(5):
                sent_times.append(time.monotonic())
                emit({"id": f"er{i}", "type": "session.reasoning.delta", "data": {"sessionID": sid, "assistantMessageID": "m1", "delta": f"Мысль{i} "}}); time.sleep(0.12)
            emit({"id": "et", "type": "session.text.delta", "data": {"sessionID": sid, "assistantMessageID": "m1", "delta": "Ответ\n"}})
            emit({"id": "e9", "type": "session.step.ended", "data": {"sessionID": sid, "assistantMessageID": "m1", "tokens": {"input": 17, "output": 9, "reasoning": 4, "cache": {"read": 3, "write": 2}}}})
            if "__end_record:" in prompt:
                end_record = prompt.split("__end_record:", 1)[1].split("__", 1)[0]
                with open(end_record, "w") as fh: fh.write(str(time.monotonic()))
                with open(end_record + ".sent", "w") as fh: json.dump(sent_times, fh)
            emit({"id": "e10", "type": "session.execution.succeeded", "data": {"sessionID": sid}})
            return
        self.send_json(404, {"data": {}})
    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        if self.path == "/api/session":
            if os.environ.get("FAKE_SERVE_SESSION_STATUS") == "503":
                self.send_json(503, {"error": "unavailable"}); return
            if os.environ.get("FAKE_SERVE_SESSION_STATUS") == "400":
                self.send_json(400, {"error": "bad request"}); return
            if not self.check(): return
            self.send_json(200, {"data": {"id": "ses_test1"}}); return
        if self.path == "/api/session/ses_test1/prompt":
            if not self.check(): return
            try: body = json.loads(raw)
            except Exception: body = {}
            prompt_text = str(body.get("text") or "")
            if "__prompt_reset__" in prompt_text or "__prompt_hang401__" in prompt_text:
                self.send_response(401 if "hang401" in prompt_text else 200)
                self.send_header("Content-Length", "100"); self.end_headers(); self.wfile.flush()
                if "hang401" in prompt_text:
                    time.sleep(5); return
                time.sleep(0.1)
                self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
                self.connection.close(); return
            forced = re.search(r"__prompt_status_(\d+)__", prompt_text)
            if forced:
                self.send_json(int(forced.group(1)), {"error": "forced"}); return
            state["prompt"] = prompt_text
            self.send_json(200, {"data": {"id": "msg1"}}); return
        if self.path == "/api/session/ses_test1/permission/per1/reply":
            if not self.check(): return
            state["rejected"] = True; self.send_response(204); self.end_headers(); return
        if self.path == "/api/session/ses_test1/form/form1/cancel":
            if not self.check(): return
            state["cancelled"] = True
            if state["record"]:
                with open(state["record"] + ".control", "w") as fh: fh.write("cancelled")
            self.send_response(204); self.end_headers(); return
        if self.path == "/api/session/ses_test1/interrupt":
            if not self.check(): return
            state["interrupted"] = True
            if state["record"]:
                with open(state["record"] + ".control", "a") as fh: fh.write("+interrupt")
            self.send_response(204); self.end_headers(); return
        self.send_json(404, {"data": {}})
    def do_DELETE(self):
        if not self.check(): return
        self.send_response(204); self.end_headers()
ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
"""


def _write_exe(tmp: Path, name: str, body: str) -> Path:
    """Записать исполняемый фейк в tmp."""
    path = tmp / name
    path.write_text(body, "utf-8")  # pyright: ignore[reportUnusedCallResult] — причина: результат вызова в тесте не используется
    _ = path.chmod(0o755)
    return path


class _Bridge:
    """Живой мост на эфемерном порту с сохранением глобалок."""

    def __init__(self) -> None:
        self.tmp: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.saved_bin: str = server.OPENCODE_BIN
        self.saved_key: str = server.AUTH_KEY
        self.stream_started: float = 0.0
        self.saved_log: Path = server.LOG_PATH
        server.AUTH_KEY = "test-key"
        server.LOG_PATH = Path(self.tmp.name) / "bridge.log"
        self.httpd: server.Server = server.Server(("127.0.0.1", 0), server.Handler)
        self.port: int = int(self.httpd.server_address[1])
        self.thread: threading.Thread = threading.Thread(
            target=self.httpd.serve_forever, daemon=True
        )
        self.thread.start()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        server.OPENCODE_BIN = self.saved_bin
        server.AUTH_KEY = self.saved_key
        server.LOG_PATH = self.saved_log
        self.tmp.cleanup()

    def post_json(
        self,
        prompt: str,
        timeout: float = 20.0,
        with_tools: bool = True,
        tool_choice: object = None,
    ) -> tuple[int, dict[str, object]]:
        """POST без stream: код и тело ответа (RemoteDisconnected — если мост ничего не отправил)."""
        payload: dict[str, object] = {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
        }
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if with_tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": "bash",
                        "description": "x",
                        "parameters": {
                            "type": "object",
                            "properties": {"command": {"type": "string"}},
                            "required": ["command"],
                        },
                    },
                }
            ]
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            conn.request(
                "POST",
                "/v1/chat/completions",
                json.dumps(payload).encode(),
                {
                    "Authorization": f"Bearer {server.AUTH_KEY}",
                    "Content-Type": "application/json",
                },
            )
            resp = conn.getresponse()
            parsed: object = json.loads(resp.read())  # pyright: ignore[reportAny] — причина: тело ответа моста — динамический JSON
            return resp.status, _as_obj_dict(parsed)
        finally:
            conn.close()

    def post_stream_timed(
        self,
        prompt: str,
        timeout: float = 20.0,
        tool_choice: object = None,
        effort: str | None = None,
    ) -> tuple[list[tuple[float, dict[str, object]]], float]:
        """POST stream с метками времени каждого SSE-чанка."""
        payload: dict[str, object] = {
            "model": MODEL,
            "stream": True,
            "messages": [{"role": "user", "content": prompt}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "bash",
                        "description": "x",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "command": {"type": "string"},
                                "description": {"type": "string"},
                            },
                            "required": ["command"],
                        },
                    },
                }
            ],
        }
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if effort is not None:
            payload["reasoning_effort"] = effort
        body = json.dumps(payload).encode()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        started = time.monotonic()
        self.stream_started = started
        conn.request(
            "POST",
            "/v1/chat/completions",
            body,
            {
                "Authorization": f"Bearer {server.AUTH_KEY}",
                "Content-Type": "application/json",
            },
        )
        resp = conn.getresponse()
        chunks: list[tuple[float, dict[str, object]]] = []
        buf = b""
        end = started
        while True:
            raw_data: object = (
                resp.read1() if hasattr(resp, "read1") else resp.read(4096)
            )
            data: bytes = raw_data if isinstance(raw_data, bytes) else b""  # pyright: ignore[reportUnnecessaryIsInstance] — причина: typeshed уже выводит bytes для read1/read; проверка сохраняет защиту адаптера
            if not data:
                end = time.monotonic()
                break
            buf += data  # pyright: ignore[reportUnknownVariableType] — причина: буфер SSE пополняется байтами динамического read1/read после проверки bytes
            while b"\n\n" in buf:
                raw, buf = buf.split(b"\n\n", 1)  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType] — причина: split делит накопленные байты SSE на кадр и хвост, тип буфера потерян в typeshed
                for line in raw.decode("utf-8", "replace").splitlines():  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType] — причина: байтовый кадр SSE декодируется в строки, тип raw наследуется от динамического буфера
                    if line.startswith("data: {"):  # pyright: ignore[reportUnknownMemberType] — причина: line — строка из decode/splitlines динамического SSE-буфера
                        parsed_obj: object = json.loads(line[6:])  # pyright: ignore[reportAny,reportUnknownArgumentType] — причина: json.loads возвращает динамический объект, далее он проверяется как dict
                        parsed_chunk: dict[str, object] = (  # pyright: ignore[reportUnknownVariableType] — причина: ответ моста — динамический JSON, тип сужается проверкой isinstance
                            parsed_obj if isinstance(parsed_obj, dict) else {}
                        )
                        chunks.append((time.monotonic() - started, parsed_chunk))
        conn.close()
        return chunks, end - started


def _as_obj_dict(value: object) -> dict[str, object]:
    """Объект как словарь с строковыми ключами, иначе пустой."""
    if isinstance(value, dict):
        return {str(k): v for k, v in value.items()}  # pyright: ignore[reportUnknownArgumentType,reportUnknownVariableType] — причина: ответ моста — динамический JSON, тип сужается проверкой isinstance
    return {}


def _deltas(
    chunks: list[tuple[float, dict[str, object]]], key: str
) -> list[tuple[float, str]]:
    """Дельты одного поля с метками."""
    out: list[tuple[float, str]] = []
    for at, chunk in chunks:
        choices_obj: object = chunk.get("choices")
        if not isinstance(choices_obj, list) or not choices_obj:
            continue
        first: dict[str, object] = _as_obj_dict(cast("list[object]", choices_obj)[0])
        delta: dict[str, object] = _as_obj_dict(first.get("delta"))
        value_obj: object = delta.get(key)
        if isinstance(value_obj, str):
            out.append((at, value_obj))
    return out


def _tool_names(chunks: list[tuple[float, dict[str, object]]]) -> list[str]:
    """Имена tool_calls из SSE-чанков."""
    names: list[str] = []
    for _at, chunk in chunks:
        choices_obj: object = chunk.get("choices")
        if not isinstance(choices_obj, list) or not choices_obj:
            continue
        first: dict[str, object] = _as_obj_dict(cast("list[object]", choices_obj)[0])
        delta: dict[str, object] = _as_obj_dict(first.get("delta"))
        calls_obj: object = delta.get("tool_calls")
        if not isinstance(calls_obj, list):
            continue
        for tc_obj in cast("list[object]", calls_obj):
            fn: dict[str, object] = _as_obj_dict(_as_obj_dict(tc_obj).get("function"))
            name_obj: object = fn.get("name")
            if isinstance(name_obj, str):
                names.append(name_obj)
    return names


class TestLegacyWatchdogAndKillpg(unittest.TestCase):
    """Группа A: legacy watchdog, статусы, O-EXIT без FakeServe."""

    bridge: _Bridge = cast(_Bridge, None)  # pyright: ignore[reportInvalidCast] — причина: атрибут класса задаётся в setUp до первого обращения
    tmp: Path = Path()
    fake: Path = Path()
    env: object = None
    allow: object = None

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-legacy", LEGACY_FAKE)
        server.OPENCODE_BIN = str(self.fake)
        self.env = mock.patch.dict(os.environ, {"FAKE_RT_MODE": "fast"}, clear=False)
        _ = cast(_Patcher, self.env).start()
        # Белый список standalone пропускает FAKE_RT_MODE дочернему процессу.
        self.allow = mock.patch.object(
            server,
            "_STANDALONE_ENV_ALLOWLIST",
            (*server._STANDALONE_ENV_ALLOWLIST, "FAKE_RT_MODE"),  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        )
        _ = cast(_Patcher, self.allow).start()

    @override
    def tearDown(self) -> None:
        _ = cast(_Patcher, self.allow).stop()
        _ = cast(_Patcher, self.env).stop()
        self.bridge.close()

    def test_python39_runtime_cast_and_sse_compatibility(self) -> None:
        """Сложные cast не вычисляются; системный Python обслуживает реальный SSE."""
        bridge_dir = Path(server.__file__).resolve().parent
        for source_path in (bridge_dir / "server.py", Path(__file__).resolve()):
            tree = ast.parse(source_path.read_text("utf-8"))
            invalid = [
                node.lineno
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "cast"
                and node.args
                and any(
                    isinstance(arg, ast.Subscript)
                    or (isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.BitOr))
                    for arg in ast.walk(node.args[0])
                )
            ]
            self.assertEqual(invalid, [], str(source_path))

        python39 = Path("/usr/bin/python3")
        if not python39.is_file():
            self.skipTest("Системный /usr/bin/python3 отсутствует")
        smoke = r"""
import http.client, json, sys, threading
from pathlib import Path
import server
from tests._fixtures import install_test_models
install_test_models(server)
server.OPENCODE_BIN = sys.argv[1]
server.AUTH_KEY = "test-key"
server.LOG_PATH = Path(sys.argv[2])
httpd = server.Server(("127.0.0.1", 0), server.Handler)
thread = threading.Thread(target=httpd.serve_forever, daemon=True)
thread.start()
conn = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=10)
try:
    payload = {"model": sys.argv[3], "stream": True,
               "messages": [{"role": "user", "content": "hello"}]}
    conn.request("POST", "/v1/chat/completions", json.dumps(payload),
                 {"Authorization": "Bearer test-key", "Content-Type": "application/json"})
    response = conn.getresponse()
    body = response.read().decode("utf-8")
    assert response.status == 200, (response.status, body)
    assert response.getheader("Content-Type").startswith("text/event-stream"), body
    assert "data: [DONE]" in body, body
    chunks = [json.loads(line[6:]) for line in body.splitlines()
              if line.startswith("data: {")]
    assert not any("error" in chunk for chunk in chunks), body
    content = "".join(choice.get("delta", {}).get("content", "")
                      for chunk in chunks for choice in chunk.get("choices", []))
    assert content == "Привет!", body
    print("SSE_RUNTIME_OK", sys.version.split()[0], len(chunks))
finally:
    conn.close()
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)
"""
        result = subprocess.run(
            [
                str(python39),
                "-B",
                "-c",
                smoke,
                str(self.fake),
                str(self.tmp / "python39-smoke.log"),
                MODEL,
            ],
            cwd=bridge_dir,
            env={**os.environ, "OPENCODE_ZEN_BRIDGE_TRANSPORT": "run"},
            capture_output=True,
            text=True,
            timeout=25,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SSE_RUNTIME_OK", result.stdout)
        self.assertNotIn("TypeError", result.stderr)

    def test_sse_reader_tolerates_concurrent_response_close(self) -> None:
        """Закрытие HTTPResponse завершает читателя и передаёт терминальный маркер."""
        read_events = server._read_serve_events  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет закрытие приватного читателя
        for error in (OSError, ValueError, AttributeError, http.client.HTTPException):
            with self.subTest(error=error.__name__):
                events: queue.Queue[dict[str, object] | None] = queue.Queue()
                response = mock.Mock(
                    spec=http.client.HTTPResponse,
                    readline=mock.Mock(side_effect=error("response closed")),
                )
                read_events(
                    response,
                    events,
                    threading.Event(),
                    [0],
                    threading.Lock(),
                    lambda _event: None,
                )
                self.assertIsNone(events.get_nowait())
                self.assertTrue(events.empty())

    def test_fast_greeting_has_no_synthetic_status(self) -> None:
        """Быстрый ответ: ровно модельные байты, без [мост]."""
        chunks, _elapsed = self.bridge.post_stream_timed("привет")
        reasoning = "".join(text for _at, text in _deltas(chunks, "reasoning_content"))
        content = "".join(text for _at, text in _deltas(chunks, "content"))
        self.assertEqual(reasoning, "Simple greeting.")
        self.assertEqual(content, "Привет!")

    def test_slow_upstream_gets_initial_status_before_1s(self) -> None:
        """Медленный апстрим: первый [мост] не позже 1.0 с (REQ-004)."""
        os.environ["FAKE_RT_MODE"] = "slow"
        chunks, _elapsed = self.bridge.post_stream_timed("медленно")
        statuses = [
            (at, t)
            for at, t in _deltas(chunks, "reasoning_content")
            if t.startswith("[мост]") or "[мост]" in t
        ]
        self.assertTrue(statuses, "нет синтетического статуса")
        self.assertLessEqual(statuses[0][0], 1.0)
        self.assertTrue(statuses[0][1].endswith("\n"))

    def test_initial_status_before_1s_under_startup_gate_contention(self) -> None:
        """RW-017: TRANSPORT=run и занятый StartupGate — первый статус не позднее 1.0 с."""
        saved_wait = server.STARTUP_WAIT_S
        server.STARTUP_WAIT_S = 2.5
        self.assertTrue(server._STARTUP_LOCK.acquire(timeout=1.0))  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
        try:
            chunks, _elapsed = self.bridge.post_stream_timed("привет")
        finally:
            server._STARTUP_LOCK.release()  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
            server.STARTUP_WAIT_S = saved_wait
        reasoning = _deltas(chunks, "reasoning_content")
        statuses = [at for at, t in reasoning if "[мост]" in t]
        self.assertTrue(statuses, chunks)
        self.assertLessEqual(statuses[0], 1.0)
        model = [at for at, t in reasoning if "[мост]" not in t]
        self.assertTrue(model and statuses[0] < model[0], chunks)
        self.assertEqual(
            len([t for _at, t in reasoning if server.STATUS_INITIAL.strip() in t]), 1
        )

    def test_rw002_initial_status_while_waiting_spawn_limiter(self) -> None:
        """RW-002: свободный StartupGate и задержанный лимитер не гасят начальный статус."""

        def delayed_acquire(*_args: object, **_kw: object) -> bool:
            time.sleep(1.2)
            return True

        with mock.patch.object(
            self.bridge.httpd.resilience.spawn_limiter,
            "acquire",
            side_effect=delayed_acquire,
        ):
            chunks, _ = self.bridge.post_stream_timed("привет")
        statuses = [
            (at, t)
            for at, t in _deltas(chunks, "reasoning_content")
            if server.STATUS_INITIAL.strip() in t
        ]
        self.assertEqual(len(statuses), 1, chunks)
        self.assertLessEqual(statuses[0][0], 1.0)

    def test_c5_rw002_limiter_delay_half_second_still_emits_first_status_under_1s(
        self,
    ) -> None:
        """Cycle 5 RW-002: задержка слота 0.5 с сохраняет абсолютный срок статуса."""
        os.environ["FAKE_RT_MODE"] = "slow"

        def delayed(*_args: object, **_kw: object) -> bool:
            time.sleep(0.5)
            return True

        with mock.patch.object(
            self.bridge.httpd.resilience.spawn_limiter, "acquire", side_effect=delayed
        ):
            chunks, _ = self.bridge.post_stream_timed("жди")
        initial = [
            (at, text)
            for at, text in _deltas(chunks, "reasoning_content")
            if server.STATUS_INITIAL.strip() in text
        ]
        self.assertEqual(len(initial), 1, chunks)
        self.assertLessEqual(initial[0][0], 1.0)

    def test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate(
        self,
    ) -> None:
        """Cycle 5 RW-003: один разделитель трёх recovery-веток только при thinking."""
        for branch in ("watchdog", "unmapped", "incomplete"):
            for effort in ("high", "off"):
                with self.subTest(branch=branch, effort=effort):
                    counter = self.tmp / (branch + effort)
                    body = """#!/usr/bin/env python3
import json, sys, time
from pathlib import Path
p = Path(COUNTER)
n = int(p.read_text()) if p.exists() else 0
p.write_text(str(n + 1))
prompt = sys.stdin.read()
def ev(o): print(json.dumps(o), flush=True)
if n == 0:
    ev({"type": "reasoning", "part": {"text": "Первая мысль"}})
    if BRANCH == "watchdog": time.sleep(3)
    elif BRANCH == "unmapped":
        ev({"type": "tool_use", "part": {"tool": "todoread", "state": {"status": "error", "input": {}}}})
    else: ev({"type": "text", "part": {"text": "Проверяю файлы.<tool_call>{"}})
else:
    ev({"type": "text", "part": {"text": "Ответ"}})
ev({"type": "step_finish", "part": {"tokens": {"input": 1, "output": 1}}})
""".replace("COUNTER", repr(str(counter))).replace("BRANCH", repr(branch))
                    server.OPENCODE_BIN = str(
                        _write_exe(self.tmp, "retry-legacy", body)
                    )
                    with (
                        mock.patch.object(server, "STALL_TIMEOUT_S", 0.3),
                        mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
                    ):
                        chunks, _ = self.bridge.post_stream_timed(
                            "проверь файлы", effort=effort
                        )
                    output = "".join(
                        text for _, text in _deltas(chunks, "reasoning_content")
                    )
                    self.assertEqual(counter.read_text(), "2", chunks)
                    self.assertEqual(
                        output.count("[мост] Повтор попытки"),
                        1 if effort == "high" else 0,
                        chunks,
                    )

    def test_reasoning_content_excluded_from_prompt(self) -> None:
        """AC-007: reasoning истории не попадает в промпт."""
        fn = server._messages_to_prompt  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        _system, prompt = fn(
            [
                {
                    "role": "assistant",
                    "content": "Ответ",
                    "reasoning_content": "[мост] секретный статус",
                },
                {"role": "user", "content": "дальше"},
            ]
        )
        self.assertNotIn("секретный статус", prompt)
        self.assertNotIn("reasoning_content", prompt)

    def test_frozen_slices_hashes(self) -> None:
        """Замороженные функции побайтово неизменны."""
        import ast as _ast

        raw = Path(server.__file__).read_bytes()
        lines = raw.splitlines(keepends=True)
        nodes = {
            n.name: n
            for n in _ast.walk(_ast.parse(raw))
            if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef))
        }
        expected = {
            "_run_env": "1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31",
            "_stream_google_sse": "5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3",
            "_execute_google_once": "88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6",
        }
        for name, digest in expected.items():
            node = nodes[name]
            blob = b"".join(lines[node.lineno - 1 : node.end_lineno])
            self.assertEqual(hashlib.sha256(blob).hexdigest(), digest, name)

    def test_oexit_fields_present(self) -> None:
        """O-EXIT/v1 содержит transport/first_event_ms/ttft_ms."""
        _ = self.bridge.post_stream_timed("привет")
        log = Path(self.bridge.tmp.name, "bridge.log")
        text = log.read_text("utf-8") if log.exists() else ""
        if not text:
            text = Path(server.LOG_PATH).read_text("utf-8")
        oexit = [line for line in text.splitlines() if "O-EXIT/v1" in line]
        self.assertTrue(oexit)
        self.assertIn("transport=", oexit[-1])
        self.assertIn("first_event_ms=", oexit[-1])
        self.assertIn("ttft_ms=", oexit[-1])

    def test_watchdog_first_event_timeout(self) -> None:
        """Тишина апстрима: watchdog срабатывает, а не TIMEOUT_S=1800."""
        os.environ["FAKE_RT_MODE"] = "silent"
        old: float = server.FIRST_EVENT_TIMEOUT_S
        old_tok: float = server.FIRST_TOKEN_TIMEOUT_S
        try:
            server.FIRST_EVENT_TIMEOUT_S = 1.0
            server.FIRST_TOKEN_TIMEOUT_S = 2.0
            started = time.monotonic()
            chunks, _elapsed = self.bridge.post_stream_timed("тишина", timeout=30.0)
            elapsed = time.monotonic() - started
        finally:
            server.FIRST_EVENT_TIMEOUT_S = old
            server.FIRST_TOKEN_TIMEOUT_S = old_tok
        self.assertLess(elapsed, 25.0)
        has_error = any("error" in chunk for _at, chunk in chunks)
        self.assertTrue(has_error, chunks)

    def test_c6_rw002_legacy_first_token_timeout_respects_configured_value_under_120s(
        self,
    ) -> None:
        """RW-002: служебное событие не продлевает порог первого токена до 120 секунд."""
        body = LEGACY_FAKE.replace(
            'if mode == "slow":',
            'if mode == "service":\n    ev({"type": "step_start"})\n    time.sleep(8)\nelif mode == "slow":',
        )
        _ = self.fake.write_text(body)
        with (
            mock.patch.dict(os.environ, {"FAKE_RT_MODE": "service"}),
            mock.patch.object(server, "FIRST_EVENT_TIMEOUT_S", 20.0),
            mock.patch.object(server, "FIRST_TOKEN_TIMEOUT_S", 0.35),
            mock.patch.object(server, "MAX_TOTAL_SPAWNS", 1),
            mock.patch.object(server, "TIMEOUT_S", 2.0),
        ):
            chunks, elapsed = self.bridge.post_stream_timed("x")
        self.assertLess(elapsed, 1.5)
        self.assertIn("first_token_timeout", server.LOG_PATH.read_text())
        self.assertIn("error", json.dumps(chunks))

    def test_c6_rw003_nonstream_json_run_execute_enforces_phase_watchdogs(self) -> None:
        """RW-003: все три фазы убивают CLI и повторяются в общем бюджете."""
        for phase in ("first_event_timeout", "first_token_timeout", "stall_timeout"):
            with self.subTest(phase=phase):
                counter = self.tmp / (phase + ".count")
                event = (
                    ""
                    if phase == "first_event_timeout"
                    else 'print(json.dumps({"type": "step_start"}), flush=True)'
                )
                if phase == "stall_timeout":
                    event = 'print(json.dumps({"type": "reasoning", "part": {"text": "мысль"}}), flush=True)'
                body = """#!/usr/bin/env python3
import json,sys,time
from pathlib import Path
p=Path(COUNTER)
n=int(p.read_text()) if p.exists() else 0
p.write_text(str(n+1))
sys.stdin.read()
if n==0:
    EVENT
    time.sleep(8)
else:
    print(json.dumps({"type":"text","part":{"text":"Ответ"}}),flush=True)
    print(json.dumps({"type":"step_finish","part":{"tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0,"write":0}}}}),flush=True)
""".replace("COUNTER", repr(str(counter))).replace(
                    "    EVENT", "    " + event if event else "    pass"
                )
                server.OPENCODE_BIN = str(_write_exe(self.tmp, "watchdog-cli", body))
                with (
                    mock.patch.dict(
                        os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": "run"}
                    ),
                    mock.patch.object(
                        server,
                        "FIRST_EVENT_TIMEOUT_S",
                        0.35 if phase == "first_event_timeout" else 20.0,
                    ),
                    mock.patch.object(server, "FIRST_TOKEN_TIMEOUT_S", 0.5),
                    mock.patch.object(server, "STALL_TIMEOUT_S", 0.2),
                    mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
                    mock.patch.object(server, "TIMEOUT_S", 3.0),
                    mock.patch.object(server, "MAX_TOTAL_SPAWNS", 2),
                    mock.patch.object(
                        server,
                        "_stop_proc",
                        wraps=server._stop_proc,  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватный API
                    ) as stopped,
                ):
                    started = time.monotonic()
                    status, result = self.bridge.post_json("x", with_tools=False)
                self.assertLess(time.monotonic() - started, 2.5)
                self.assertEqual(status, 200, result)
                self.assertEqual(counter.read_text(), "2")
                self.assertTrue(stopped.called)
                self.assertIn(phase, server.LOG_PATH.read_text())
                _ = counter.write_text("0")
                self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: независимый бюджет для исчерпания попыток
                with (
                    mock.patch.dict(
                        os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": "run"}
                    ),
                    mock.patch.object(
                        server,
                        "FIRST_EVENT_TIMEOUT_S",
                        0.35 if phase == "first_event_timeout" else 20.0,
                    ),
                    mock.patch.object(server, "FIRST_TOKEN_TIMEOUT_S", 0.5),
                    mock.patch.object(server, "STALL_TIMEOUT_S", 0.2),
                    mock.patch.object(server, "MAX_TOTAL_SPAWNS", 1),
                    mock.patch.object(server, "TIMEOUT_S", 2.0),
                ):
                    status, result = self.bridge.post_json("x", with_tools=False)
                self.assertEqual(status, 502, result)
                self.assertEqual(counter.read_text(), "1")
                self.assertIn("opencode " + phase, json.dumps(result))
                self.assertNotIn(
                    "provider error after partial output", json.dumps(result)
                )

    def test_c7_rw001_json_run_watchdog_oexit_reason_and_phase_timings(self) -> None:
        """RW-001: исчерпание watchdog сохраняет фазу и наступившие времена O-EXIT."""
        for phase in ("first_event_timeout", "first_token_timeout", "stall_timeout"):
            with self.subTest(phase=phase):
                event = ""
                if phase == "first_token_timeout":
                    event = 'print(json.dumps({"type":"step_start"}),flush=True)'
                elif phase == "stall_timeout":
                    event = 'print(json.dumps({"type":"reasoning","part":{"text":"мысль"}}),flush=True)'
                body = (
                    "#!/usr/bin/env python3\nimport json,sys,time\nsys.stdin.read()\n"
                    + event
                    + "\ntime.sleep(8)\n"
                )
                server.OPENCODE_BIN = str(_write_exe(self.tmp, "c7-watchdog", body))
                logged = threading.Event()
                log_original = cast("Callable[[str], None]", getattr(server, "_log"))

                def log(message: str) -> None:
                    log_original(message)
                    if "O-EXIT/v1" in message:
                        logged.set()

                with (
                    mock.patch.object(server, "_log", side_effect=log),
                    mock.patch.dict(
                        os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": "run"}
                    ),
                    mock.patch.object(server, "FIRST_EVENT_TIMEOUT_S", 0.35),
                    mock.patch.object(server, "FIRST_TOKEN_TIMEOUT_S", 0.45),
                    mock.patch.object(server, "STALL_TIMEOUT_S", 0.25),
                    mock.patch.object(server, "MAX_TOTAL_SPAWNS", 1),
                    mock.patch.object(server, "TIMEOUT_S", 3.0),
                ):
                    status, result = self.bridge.post_json("x", with_tools=False)
                    self.assertTrue(logged.wait(1.0))
                self.assertEqual(status, 502, result)
                lines = [
                    line
                    for line in server.LOG_PATH.read_text().splitlines()
                    if "O-EXIT/v1" in line
                ]
                self.assertTrue(lines)
                self.assertIn("exit_reason=" + phase, lines[-1])
                self.assertIn("opencode " + phase, json.dumps(result))
                self.assertNotIn(
                    "provider error after partial output", json.dumps(result)
                )
                self.assertRegex(
                    lines[-1],
                    r"first_event_ms="
                    + ("None" if phase == "first_event_timeout" else r"\d+"),
                )
                self.assertRegex(
                    lines[-1],
                    r"ttft_ms=" + (r"\d+" if phase == "stall_timeout" else "None"),
                )

    def test_c7_rw003_legacy_sse_watchdog_records_breaker_failure_with_and_without_output(
        self,
    ) -> None:
        """RW-003: каждая убитая watchdog попытка учитывается как отказ до OPEN."""
        breaker = self.bridge.httpd.resilience.breaker
        for phase in ("first_event_timeout", "first_token_timeout", "stall_timeout"):
            with self.subTest(phase=phase):
                event = ""
                if phase == "first_token_timeout":
                    event = 'print(json.dumps({"type":"step_start"}),flush=True)'
                elif phase == "stall_timeout":
                    event = 'print(json.dumps({"type":"reasoning","part":{"text":"мысль"}}),flush=True)'
                server.OPENCODE_BIN = str(
                    _write_exe(
                        self.tmp,
                        "c7-breaker",
                        "#!/usr/bin/env python3\nimport json,sys,time\nsys.stdin.read()\n"
                        + event
                        + "\ntime.sleep(8)\n",
                    )
                )
                breaker.record_success()
                counts: list[int] = []
                failed = threading.Event()
                original = breaker.record_failure

                def failure() -> None:
                    original()
                    counts.append(cast(int, getattr(breaker, "_failures")))
                    failed.set()

                with (
                    mock.patch.dict(
                        os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": "run"}
                    ),
                    mock.patch.object(breaker, "_threshold", 2),
                    mock.patch.object(breaker, "record_failure", side_effect=failure),
                    mock.patch.object(
                        breaker, "record_success", wraps=breaker.record_success
                    ) as success,
                    mock.patch.object(server, "FIRST_EVENT_TIMEOUT_S", 0.35),
                    mock.patch.object(server, "FIRST_TOKEN_TIMEOUT_S", 0.45),
                    mock.patch.object(server, "STALL_TIMEOUT_S", 0.25),
                    mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
                    mock.patch.object(server, "MAX_TOTAL_SPAWNS", 1),
                    mock.patch.object(server, "TIMEOUT_S", 3.0),
                ):
                    for expected_count in (1, 2):
                        failed.clear()
                        chunks, _ = self.bridge.post_stream_timed("x")
                        self.assertTrue(failed.wait(1.0))
                        self.assertIn("error", json.dumps(chunks))
                        self.assertEqual(counts[-1], expected_count)
                self.assertEqual(counts, [1, 2])
                success.assert_not_called()
                self.assertEqual(breaker.state, "OPEN")

    def test_c6_rw003_active_subagent_does_not_trigger_token_stall(self) -> None:
        """RW-003: ожидание действующего task не считается тишиной модели."""
        body = r"""#!/usr/bin/env python3
import json,sys,time
sys.stdin.read()
def ev(o): print(json.dumps(o),flush=True)
ev({"type":"tool_use","part":{"id":"t1","tool":"task","state":{"status":"running","input":{}}}})
time.sleep(0.6)
ev({"type":"tool_use","part":{"id":"t1","tool":"task","state":{"status":"completed","input":{}}}})
ev({"type":"text","part":{"text":"Ответ"}})
ev({"type":"step_finish","part":{"tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0,"write":0}}}})
"""
        _ = self.fake.write_text(body)
        with (
            mock.patch.dict(os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": "run"}),
            mock.patch.object(server, "FIRST_EVENT_TIMEOUT_S", 2.0),
            mock.patch.object(server, "FIRST_TOKEN_TIMEOUT_S", 2.0),
            mock.patch.object(server, "STALL_TIMEOUT_S", 0.2),
            mock.patch.object(server, "MAX_TOTAL_SPAWNS", 1),
        ):
            status, result = self.bridge.post_json("x", with_tools=False)
        self.assertEqual(status, 200, result)
        self.assertNotIn("stall_timeout", server.LOG_PATH.read_text())


class TestServeTransportAndFakeServe(unittest.TestCase):
    """Группа B: serve-транспорт на FakeServe."""

    def _c13_security_protocol_matrix(self, drain: bool) -> None:
        """Сбой любого security control завершает одну попытку без run/fallback."""
        self._auto_mode()
        if drain:
            prefix = '            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"first","name":"bash","input":{"command":"pwd"}}})\n'
            _ = self.fake.write_text(
                FAKE_SERVE.replace(
                    '            if "__native_pause__" in prompt:',
                    prefix + '            if "__native_pause__" in prompt:',
                )
            )
        http_call = cast(
            "Callable[..., tuple[int, dict[str, object]]]",
            getattr(server, "_serve_http"),
        )
        attempt = cast("Callable[..., object]", getattr(server, "_serve_one_attempt"))
        attempts_type = cast("type[object]", getattr(server, "_RequestAttempts"))
        original_note = cast(
            "Callable[..., None]", getattr(attempts_type, "note_spawn")
        )
        for stream in (False, True):
            for control in ("form", "permission"):
                for failed in ("first", "interrupt"):
                    for error_type in (server.ServeProtocolError,):
                        with self.subTest(
                            stream=stream,
                            control=control,
                            failed=failed,
                            error=error_type,
                        ):
                            paths: list[str] = []
                            raised: list[str] = []
                            spawns: list[int] = []
                            self.bridge.httpd.resilience = type(
                                self.bridge.httpd.resilience
                            )()

                            def note_spawn(owner: object) -> None:
                                original_note(owner)
                                spawns.append(cast(int, getattr(owner, "total_spawns")))

                            def control_http(
                                *args: object, **kwargs: object
                            ) -> tuple[int, dict[str, object]]:
                                path = str(args[3])
                                if path.endswith(
                                    ("/reply", "/cancel", "/interrupt")
                                ) and not kwargs.get("skip_body"):
                                    paths.append(path)
                                    if (
                                        drain
                                        and control == "permission"
                                        and failed == "interrupt"
                                        and path.endswith("/reply")
                                    ):
                                        return 503, {}
                                    if (failed == "interrupt") == path.endswith(
                                        "/interrupt"
                                    ):
                                        raise error_type("control rejected")
                                return http_call(*args, **kwargs)

                            def one_attempt(*args: object, **kwargs: object) -> object:
                                try:
                                    return attempt(*args, **kwargs)
                                except server.ServeSecurityError:
                                    raised.append("security_rejected")
                                    raise

                            with (
                                mock.patch.object(
                                    server, "_serve_http", side_effect=control_http
                                ),
                                mock.patch.object(
                                    server,
                                    "_serve_one_attempt",
                                    side_effect=one_attempt,
                                ),
                                mock.patch.object(
                                    attempts_type, "note_spawn", note_spawn
                                ),
                                mock.patch.object(server.Run, "execute") as legacy,
                                mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
                            ):
                                marker = (
                                    "__form_ok__"
                                    if control == "form"
                                    else "__permission__"
                                )
                                if stream:
                                    chunks, _ = self.bridge.post_stream_timed(marker)
                                    encoded = json.dumps(chunks)
                                else:
                                    status, body = self.bridge.post_json(marker)
                                    self.assertEqual(status, 502, body)
                                    encoded = json.dumps(body)
                                self.assertIn("serve security failure", encoded)
                                legacy.assert_not_called()
                            self.assertEqual(raised, ["security_rejected"])
                            self.assertEqual(spawns, [1])
                            self.assertTrue(
                                any(p.endswith("/interrupt") for p in paths), paths
                            )

    def test_c13_rw003_disconnect_during_active_drain_sse_json(self) -> None:
        """Отключение при потоке tool delta быстро останавливает drain и cleanup."""
        fragment = """
            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"first","name":"bash","input":{"command":"pwd"}}})
            for i in range(40):
                time.sleep(0.05)
                emit({"type":"session.tool.input.delta","data":{"sessionID":sid,"assistantMessageID":"m1","id":"next","delta":" "}})
            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{}}})
            return
"""
        _ = self.fake.write_text(
            FAKE_SERVE.replace(
                '            if "__native_pause__" in prompt:',
                fragment + '            if "__native_pause__" in prompt:',
            )
        )
        finish = cast("Callable[..., bool]", getattr(server, "_finish_serve_tool_step"))
        attempt = cast(
            "Callable[..., Mapping[str, object]]", getattr(server, "_serve_one_attempt")
        )
        lease = cast("type[object]", getattr(server, "_ServeLease"))
        cleanup = cast("Callable[..., None]", getattr(lease, "cleanup"))
        for stream in (False, True):
            with self.subTest(stream=stream):
                entered: list[float] = []
                published: list[dict[str, object]] = []
                disconnected: list[float] = []
                results: list[Mapping[str, object]] = []
                finished_at: list[float] = []
                finished = threading.Event()

                def draining(*args: object, **kwargs: object) -> bool:
                    entered.append(time.monotonic())
                    return finish(*args, **kwargs)

                def gone() -> bool:
                    value = bool(entered and time.monotonic() - entered[0] >= 0.10)
                    if value and not disconnected:
                        disconnected.append(time.monotonic())
                    return value

                def one_attempt(
                    *args: object, **kwargs: object
                ) -> Mapping[str, object]:
                    kwargs["is_client_gone"] = gone
                    argv = list(args)
                    argv[6] = published.append
                    result = attempt(*argv, **kwargs)
                    results.append(result)
                    finished_at.append(time.monotonic())
                    finished.set()
                    return result

                self.bridge.httpd.resilience = type(self.bridge.httpd.resilience)()
                self._auto_mode()
                with (
                    mock.patch.object(
                        server, "_finish_serve_tool_step", side_effect=draining
                    ),
                    mock.patch.object(
                        server, "_serve_one_attempt", side_effect=one_attempt
                    ),
                    mock.patch.object(
                        lease, "cleanup", autospec=True, side_effect=cleanup
                    ) as cleaned,
                    mock.patch.object(server.Run, "execute") as legacy,
                    mock.patch.object(server, "_STEP_DRAIN_WINDOW_S", 1.0),
                ):
                    if stream:
                        _ = self.bridge.post_stream_timed("x")
                    else:
                        with self.assertRaises(
                            (
                                http.client.RemoteDisconnected,
                                ConnectionError,
                                TimeoutError,
                            )
                        ):
                            _ = self.bridge.post_json("x", timeout=2.0)
                    self.assertTrue(finished.wait(1.0))
                    legacy.assert_not_called()
                self.assertEqual(len(results), 1)
                result = results[0]
                self.assertTrue(entered)
                self.assertEqual(result["exit_reason"], "client_gone", result)
                self.assertLess(finished_at[0] - entered[0], 1.0)
                self.assertFalse(published)
                self.assertFalse(result["native_calls"])
                cleaned.assert_called_once()
                self.assertFalse(list(server.LEASE_DIR.glob("lease-*.json")))

    def test_c13_rw001_protocol_errors_main_sse_json(self) -> None:
        """Протокольные ошибки control терминальны в основном цикле SSE/JSON."""
        self._c13_security_protocol_matrix(False)

    def test_c13_rw001_protocol_errors_drain_sse_json(self) -> None:
        """Cancel/reply и interrupt в дренаже не теряют security-классификацию."""
        self._c13_security_protocol_matrix(True)

    def test_c12_rw001_control_errors_are_terminal_main_sse_json(self) -> None:
        """Сбой любого security control завершает одну попытку без run/fallback."""
        self._auto_mode()
        http_call = cast(
            "Callable[..., tuple[int, dict[str, object]]]",
            getattr(server, "_serve_http"),
        )
        attempt = cast("Callable[..., object]", getattr(server, "_serve_one_attempt"))
        attempts_type = cast("type[object]", getattr(server, "_RequestAttempts"))
        original_note = cast(
            "Callable[..., None]", getattr(attempts_type, "note_spawn")
        )
        for stream in (False, True):
            for control in ("form", "permission"):
                for failed in ("first", "interrupt"):
                    for error_type in (
                        socket.timeout,
                        ConnectionResetError,
                        http.client.HTTPException,
                        server.ServeUnavailable,
                        None,
                    ):
                        with self.subTest(
                            stream=stream,
                            control=control,
                            failed=failed,
                            error=error_type,
                        ):
                            paths: list[str] = []
                            raised: list[str] = []
                            spawns: list[int] = []
                            self.bridge.httpd.resilience = type(
                                self.bridge.httpd.resilience
                            )()

                            def note_spawn(owner: object) -> None:
                                original_note(owner)
                                spawns.append(cast(int, getattr(owner, "total_spawns")))

                            def control_http(
                                *args: object, **kwargs: object
                            ) -> tuple[int, dict[str, object]]:
                                path = str(args[3])
                                if path.endswith(
                                    ("/reply", "/cancel", "/interrupt")
                                ) and not kwargs.get("skip_body"):
                                    paths.append(path)
                                    if (failed == "interrupt") == path.endswith(
                                        "/interrupt"
                                    ):
                                        if error_type is None:
                                            return 503, {}
                                        raise error_type("control rejected")
                                return http_call(*args, **kwargs)

                            def one_attempt(*args: object, **kwargs: object) -> object:
                                try:
                                    return attempt(*args, **kwargs)
                                except server.ServeSecurityError:
                                    raised.append("security_rejected")
                                    raise

                            with (
                                mock.patch.object(
                                    server, "_serve_http", side_effect=control_http
                                ),
                                mock.patch.object(
                                    server,
                                    "_serve_one_attempt",
                                    side_effect=one_attempt,
                                ),
                                mock.patch.object(
                                    attempts_type, "note_spawn", note_spawn
                                ),
                                mock.patch.object(server.Run, "execute") as legacy,
                                mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
                            ):
                                marker = (
                                    "__form_ok__"
                                    if control == "form"
                                    else "__permission__"
                                )
                                if stream:
                                    chunks, _ = self.bridge.post_stream_timed(marker)
                                    encoded = json.dumps(chunks)
                                else:
                                    status, body = self.bridge.post_json(marker)
                                    self.assertEqual(status, 502, body)
                                    encoded = json.dumps(body)
                                self.assertIn("serve security failure", encoded)
                                legacy.assert_not_called()
                            self.assertEqual(raised, ["security_rejected"])
                            self.assertEqual(spawns, [1])
                            self.assertTrue(
                                any(p.endswith("/interrupt") for p in paths), paths
                            )

    def _c13_run_retry_http(self, *, timings: bool) -> None:
        """Пройти Run.execute и HTTP JSON с двумя внутренними попытками."""
        captured: list[dict[str, object]] = []
        logs: list[str] = []
        done = threading.Event()
        counter = [0]
        t0 = 1000.0
        new_exit = cast(
            "Callable[[], dict[str, object]]", getattr(server, "_new_exit_state")
        )
        execute = server.Run.execute

        def exit_state() -> dict[str, object]:
            xs = new_exit()
            xs["t0"] = t0
            return xs

        def once(_runner: server.Run) -> dict[str, object]:
            index = counter[0]
            counter[0] += 1
            return {
                "state": "stall_timeout" if index == 0 else "ok",
                "rc": 0,
                "err": "",
                "text": "" if index == 0 else "ответ",
                "chunks": [] if index == 0 else ["ответ"],
                "reasoning": "мысль-run-1" if index == 0 else "мысль-run-2",
                "first_event_at": t0 + (0.12 if index == 0 else 1.50),
                "first_token_at": t0 + (0.25 if index == 0 else 1.80),
                "usage": {},
                "native_calls": [],
            }

        def run(runner: server.Run) -> object:
            out = cast("dict[str, object]", execute(runner))
            captured.append(out)
            return out

        def log(message: str) -> None:
            if "O-EXIT/v1" in message:
                logs.append(message)
                done.set()

        with (
            mock.patch.dict(os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": "run"}),
            mock.patch.object(server, "_new_exit_state", side_effect=exit_state),
            mock.patch.object(server.Run, "_execute_once", once),
            mock.patch.object(server.Run, "execute", run),
            mock.patch.object(server, "_log", side_effect=log),
        ):
            status, body = self.bridge.post_json("x", with_tools=False)
            self.assertTrue(done.wait(1.0))
        self.assertEqual(status, 200, body)
        self.assertEqual(counter, [2])
        self.assertEqual(len(captured), 1)
        if timings:
            self.assertEqual(captured[0]["first_event_at"], t0 + 0.12)
            self.assertEqual(captured[0]["first_token_at"], t0 + 0.25)
            self.assertIn("first_event_ms=120 ", logs[-1])
            self.assertIn("ttft_ms=250 ", logs[-1])
        else:
            expected = "мысль-run-1мысль-run-2"
            self.assertEqual(captured[0]["reasoning"], expected)
            choices = cast("list[dict[str, object]]", body["choices"])
            message = cast("dict[str, object]", choices[0]["message"])
            self.assertEqual(message["reasoning_content"], expected)
            self.assertNotIn("\n\n", str(message["reasoning_content"]))

    def test_c13_rw002_run_retry_reasoning_concat_no_synthetic_newlines(self) -> None:
        """Внутренний retry сохраняет точные байты reasoning до HTTP-ответа."""
        self._c13_run_retry_http(timings=False)

    def test_c13_rw004_run_retry_retains_first_timings_in_http_oexit(self) -> None:
        """Run и O-EXIT отражают первые 120/250 мс, а не второй retry."""
        self._c13_run_retry_http(timings=True)

    def test_c12_rw002_json_retry_preserves_partial_output_and_usage(self) -> None:
        """Все внутренние JSON retry сохраняют нормализованный вывод и токены."""
        for reason, marker in (
            (r, m)
            for r in ("stall_timeout", "prompt_status", "transient_error")
            for m in (
                "I was interrupted right before making tool calls.",
                "[opencode-zen-bridge: шаг модели оборвался]",
            )
        ):
            with self.subTest(reason=reason):
                self.bridge.httpd.resilience = type(self.bridge.httpd.resilience)()

                def first(args: tuple[object, ...]) -> dict[str, object]:
                    text = "начало " + marker + '<tool_call>{"name":"bash","arguments":'
                    _callback(args, 4)("мысль-1")
                    _callback(args, 5)(text)
                    return _fake_result(
                        reasonings=["мысль-1"],
                        texts=[text],
                        delivered=True,
                        usage={"input": 10, "output": 5, "cached": 0, "reasoning": 3},
                        exit_reason="stall_timeout"
                        if reason == "stall_timeout"
                        else "",
                        prompt_status=503 if reason == "prompt_status" else None,
                        error={"message": "interrupted", "status": 503}
                        if reason == "transient_error"
                        else None,
                        transient_error=reason == "transient_error",
                    )

                def second(args: tuple[object, ...]) -> dict[str, object]:
                    _callback(args, 4)("мысль-2")
                    _callback(args, 5)("начало продолжение")
                    return _fake_result(
                        reasonings=["мысль-2"],
                        texts=["начало продолжение"],
                        terminal="succeeded",
                        usage={"input": 12, "output": 8, "cached": 0, "reasoning": 4},
                    )

                calls, patcher = self._patched_attempts([first, second])
                with patcher, mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0):
                    status, body = self.bridge.post_json("x")
                self.assertEqual(status, 200, body)
                self.assertEqual(len(calls), 2)
                choices = cast("list[dict[str, object]]", body["choices"])
                message = _as_obj_dict(choices[0]["message"])
                self.assertEqual(message["reasoning_content"], "мысль-1мысль-2")
                self.assertEqual(message["content"], "начало продолжение")
                self.assertNotIn("tool_calls", message)
                usage = _as_obj_dict(body["usage"])
                self.assertEqual(
                    (usage["prompt_tokens"], usage["completion_tokens"]), (22, 13)
                )
                self.assertEqual(
                    _as_obj_dict(usage["completion_tokens_details"])[
                        "reasoning_tokens"
                    ],
                    7,
                )

    def test_c12_rw004_unmapped_exhaustion_returns_diagnostic_json(self) -> None:
        """JSON serve совпадает с legacy при исчерпании unmapped без текста."""

        def unmapped(args: tuple[object, ...]) -> dict[str, object]:
            native: dict[str, object] = {
                "type": "tool_use",
                "part": {"id": "c1", "tool": "missing", "input": {}},
            }
            cast("Callable[[dict[str, object]], None]", args[6])(native)
            return _fake_result(
                native_calls=[native], terminal="tool_calls", delivered=True
            )

        calls, patcher = self._patched_attempts([unmapped] * 5)
        with (
            patcher,
            mock.patch.object(server, "NATIVE_RETRY_LIMIT", 1),
            mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
        ):
            status, body = self.bridge.post_json("x")
        self.assertEqual(status, 200, body)
        self.assertEqual(len(calls), 2)
        choices = cast("list[dict[str, object]]", body["choices"])
        self.assertEqual(choices[0]["finish_reason"], "stop")
        self.assertEqual(
            _as_obj_dict(choices[0]["message"])["content"],
            "[opencode-zen-bridge: модель вызывала недоступный встроенный инструмент (missing); повторы исчерпаны]",
        )

    def test_c12_rw004_unmapped_exhaustion_transport_matrix(self) -> None:
        """Локальный лимит, общий spawn cap и Retry Budget одинаковы в четырёх путях."""
        fragment = """
            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"c1","name":"missing","input":{}}})
            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0,"write":0}}}})
            return
"""
        legacy = """#!/usr/bin/env python3
import json,sys
sys.stdin.read()
print(json.dumps({"type":"tool_use","part":{"tool":"missing","state":{"status":"completed","input":{}}}}),flush=True)
print(json.dumps({"type":"step_finish","part":{"tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0,"write":0}}}}),flush=True)
"""
        expected = (
            "[opencode-zen-bridge: модель вызывала недоступный встроенный инструмент (missing); повторы исчерпаны]",
            "stop",
        )
        for budget in ("local", "spawn", "retry"):
            for transport in ("serve", "run"):
                for stream in (False, True):
                    with self.subTest(
                        budget=budget, transport=transport, stream=stream
                    ):
                        self.bridge.httpd.resilience = type(
                            self.bridge.httpd.resilience
                        )()
                        source = (
                            legacy
                            if transport == "run"
                            else FAKE_SERVE.replace(
                                '            if "__native_pause__" in prompt:',
                                fragment
                                + '            if "__native_pause__" in prompt:',
                            )
                        )
                        _ = self.fake.write_text(source)
                        attempts_type = cast(
                            "type[object]", getattr(server, "_RequestAttempts")
                        )
                        allow_retry = cast(
                            "Callable[..., bool]", getattr(attempts_type, "allow_retry")
                        )

                        def retry(
                            owner: object, *args: object, **kwargs: object
                        ) -> bool:
                            return (
                                False
                                if budget == "retry"
                                else allow_retry(owner, *args, **kwargs)
                            )

                        with (
                            mock.patch.dict(
                                os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": transport}
                            ),
                            mock.patch.object(
                                server,
                                "NATIVE_RETRY_LIMIT",
                                0 if budget == "local" else 2,
                            ),
                            mock.patch.object(
                                server,
                                "MAX_TOTAL_SPAWNS",
                                1 if budget == "spawn" else 3,
                            ),
                            mock.patch.object(attempts_type, "allow_retry", retry),
                            mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
                        ):
                            content, finish = self._c6_response(stream)
                            self.assertEqual((content.strip(), finish), expected)

    bridge: _Bridge = cast(_Bridge, None)  # pyright: ignore[reportInvalidCast] — причина: атрибут класса задаётся в setUp до первого обращения
    tmp: Path = Path()
    fake: Path = Path()
    cfg: Path = Path()
    saved_cfg: Path = Path()
    saved_lease: Path = Path()
    _had_dyn_cfg: bool = False
    _had_lease: bool = False
    env: object = None

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
        self._had_dyn_cfg = hasattr(server, "DYNAMIC_CONFIG_PATH")
        self.saved_cfg = getattr(
            server, "DYNAMIC_CONFIG_PATH", self.tmp / "missing_dyn.json"
        )
        server.DYNAMIC_CONFIG_PATH = self.cfg
        self._had_lease = hasattr(server, "LEASE_DIR")
        self.saved_lease = getattr(server, "LEASE_DIR", self.tmp / "missing_leases")
        server.LEASE_DIR = self.tmp / "leases"
        self.env = mock.patch.dict(
            os.environ,
            {
                "OPENCODE_ZEN_BRIDGE_TRANSPORT": "serve",
                "HOME": str(self.tmp / "empty-home"),
            },
            clear=False,
        )
        _ = cast(_Patcher, self.env).start()
        (self.tmp / "empty-home").mkdir(exist_ok=True)

    @override
    def tearDown(self) -> None:
        _ = cast(_Patcher, self.env).stop()
        if self._had_dyn_cfg:
            server.DYNAMIC_CONFIG_PATH = self.saved_cfg
        else:
            delattr(server, "DYNAMIC_CONFIG_PATH")
        if self._had_lease:
            server.LEASE_DIR = self.saved_lease
        else:
            delattr(server, "LEASE_DIR")
        self.bridge.close()

    def test_c8_rw001_early_transient_error_after_execution_started_retries_serve_without_run_fallback(
        self,
    ) -> None:
        """Начало execution запрещает run, но допускает повтор serve без токенов."""
        self._auto_mode()
        counter = self.tmp / "attempt-count"
        fragment = """
            counter = Path(COUNTER)
            n = int(counter.read_text()) if counter.exists() else 0
            counter.write_text(str(n + 1))
            if n == 0:
                emit({"type":"session.execution.started","data":{"sessionID":sid}})
                emit({"type":"session.execution.failed","data":{"sessionID":sid,"error":{"message":"overloaded","status":STATUS}}})
                return
""".replace("COUNTER", repr(str(counter)))
        for stream in (True, False):
            for code in (429, 503):
                with self.subTest(stream=stream, code=code):
                    counter.unlink(missing_ok=True)
                    _ = self.fake.write_text(
                        FAKE_SERVE.replace(
                            '            if "__native_pause__" in prompt:',
                            fragment.replace("STATUS", str(code))
                            + '            if "__native_pause__" in prompt:',
                        )
                    )
                    with (
                        mock.patch.object(server.Run, "execute") as legacy,
                        mock.patch.object(server, "_spawn_with_stdin") as spawn,
                        mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
                    ):
                        if stream:
                            chunks, _ = self.bridge.post_stream_timed("обычный запрос")
                            self.assertFalse(
                                any("error" in chunk for _, chunk in chunks), chunks
                            )
                            self.assertEqual(
                                "".join(t for _, t in _deltas(chunks, "content")),
                                "Ответ\n",
                            )
                        else:
                            status, body = self.bridge.post_json(
                                "обычный запрос", with_tools=False
                            )
                            self.assertEqual(status, 200, body)
                            self.assertIn("Ответ", json.dumps(body, ensure_ascii=False))
                        legacy.assert_not_called()
                        spawn.assert_not_called()
                    self.assertEqual(counter.read_text(), "2")

    def test_c8_rw002_unpaired_surrogate_raises_serve_protocol_error_in_sse_and_json(
        self,
    ) -> None:
        """Непарные суррогаты дают управляемый отказ; пара остаётся символом."""
        mapper = server._map_serve_event  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватная граница serve и управление запуском
        protocol_error = server.ServeProtocolError
        original_log = cast("Callable[[str], None]", getattr(server, "_log"))
        self._auto_mode()
        for surrogate in ("\ud800", "\udc00"):
            for field in ("reasoning", "text"):
                event: dict[str, object] = {
                    "type": f"session.{field}.delta",
                    "data": {"sessionID": "s", "delta": surrogate},
                }
                with self.assertRaises(protocol_error):
                    _ = mapper(event)
                for stream in (True, False):
                    with self.subTest(
                        surrogate=repr(surrogate), field=field, stream=stream
                    ):
                        _ = server.LOG_PATH.write_text("")
                        logged_exit = threading.Event()

                        def record_log(message: str) -> None:
                            """Сигнализировать после записи финализатором O-EXIT в файл."""
                            original_log(message)
                            if message.startswith("O-EXIT/v1 "):
                                logged_exit.set()

                        self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: независимые защиты сценария
                        os.environ["OPENCODE_ZEN_BRIDGE_TRANSPORT"] = (
                            "serve" if field == "reasoning" else "auto"
                        )
                        fragment = """
            if not state["prompt_replied"].wait(5): return
            time.sleep(0.05)
            emit({"type":"session.execution.started","data":{"sessionID":sid}})
            emit({"type":"session.FIELD.delta","data":{"sessionID":sid,"delta":SURROGATE}})
            time.sleep(0.2)
            return
""".replace("FIELD", field).replace("SURROGATE", repr(surrogate))
                        body = (
                            FAKE_SERVE.replace(
                                '            if "__native_pause__" in prompt:',
                                fragment
                                + '            if "__native_pause__" in prompt:',
                            )
                            .replace(
                                "json.dumps(obj, ensure_ascii=False)",
                                "json.dumps(obj, ensure_ascii=True)",
                            )
                            .replace(
                                "lock = threading.Lock()",
                                'lock = threading.Lock()\nstate["prompt_replied"] = threading.Event()',
                            )
                            .replace(
                                '            self.send_json(200, {"data": {"id": "msg1"}}); return',
                                '            self.send_json(200, {"data": {"id": "msg1"}}); state["prompt_replied"].set(); return',
                            )
                        )
                        _ = self.fake.write_text(body)
                        lease_cls = server._ServeLease  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватная граница serve и управление запуском
                        cleanup = lease_cls.cleanup
                        response_debug = ""
                        with (
                            mock.patch.object(server, "_log", side_effect=record_log),
                            mock.patch.object(server, "MAX_TOTAL_SPAWNS", 1),
                            mock.patch.object(
                                lease_cls, "cleanup", autospec=True, side_effect=cleanup
                            ) as cleaned,
                            mock.patch.object(server.Run, "execute") as legacy,
                            mock.patch.object(server, "_spawn_with_stdin") as spawn,
                        ):
                            if stream:
                                chunks, _ = self.bridge.post_stream_timed("x")
                                response_debug = repr(chunks)
                                self.assertTrue(
                                    any("error" in chunk for _, chunk in chunks), chunks
                                )
                            else:
                                status, reply = self.bridge.post_json(
                                    "x", with_tools=False
                                )
                                response_debug = repr(reply)
                                self.assertEqual(status, 502, reply)
                            self.assertTrue(logged_exit.wait(5), "Нет O-EXIT/v1")
                            cleaned.assert_called_once()
                            legacy.assert_not_called()
                            spawn.assert_not_called()
                        self.assertIn(
                            "exit_reason=invalid_serve_event",
                            server.LOG_PATH.read_text(),
                            response_debug,
                        )
        mapped: object = mapper(
            {
                "type": "session.text.delta",
                "data": {"sessionID": "s", "delta": "\ud83d\ude00"},
            }
        )
        self.assertEqual(mapped, ("text", {"sessionID": "s", "content": "😀"}))
        for field in ("name", "input", "text"):
            tool_data: dict[str, object] = {
                "sessionID": "s",
                "id": "c",
                field: "\ud800",
            }
            with self.assertRaises(protocol_error):
                _ = mapper({"type": "session.tool.called", "data": tool_data})
        fragment = """
            time.sleep(0.05)
            emit({"type":"session.reasoning.delta","data":{"sessionID":sid,"delta":"\\ud83d\\ude00"}})
            emit({"type":"session.text.delta","data":{"sessionID":sid,"delta":"\\ud83d\\ude00"}})
            emit({"type":"session.step.ended","data":{"sessionID":sid,"tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0}}}})
            emit({"type":"session.execution.succeeded","data":{"sessionID":sid}})
            time.sleep(0.2)
            return
"""
        _ = self.fake.write_text(
            FAKE_SERVE.replace(
                '            if "__native_pause__" in prompt:',
                fragment + '            if "__native_pause__" in prompt:',
            ).replace(
                "json.dumps(obj, ensure_ascii=False)",
                "json.dumps(obj, ensure_ascii=True)",
            )
        )
        for stream in (True, False):
            if stream:
                chunks, _ = self.bridge.post_stream_timed("x")
                self.assertEqual(
                    "".join(t for _, t in _deltas(chunks, "content")), "😀"
                )
                self.assertIn(
                    "😀", "".join(t for _, t in _deltas(chunks, "reasoning_content"))
                )
            else:
                status, reply = self.bridge.post_json("x", with_tools=False)
                self.assertEqual(status, 200, reply)
                self.assertIn("😀", json.dumps(reply, ensure_ascii=False))
        for stream in (True, False):
            self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватная граница serve и управление запуском
            calls, patcher = self._patched_attempts(
                [
                    lambda _args: _fake_result(
                        exit_reason="invalid_serve_event", delivered=False
                    )
                ]
            )
            _ = self.fake.write_text(FAKE_SERVE)
            with (
                patcher,
                mock.patch.object(
                    server.Run,
                    "execute",
                    return_value={
                        "text": "резерв",
                        "reasoning": "",
                        "usage": {},
                        "state": "ok",
                        "rc": 0,
                    },
                ) as legacy,
                mock.patch.object(server, "MAX_TOTAL_SPAWNS", 2),
            ):
                if stream:
                    chunks, _ = self.bridge.post_stream_timed("x")
                    self.assertIn(
                        "Поздний ответ", json.dumps(chunks, ensure_ascii=False)
                    )
                else:
                    status, _ = self.bridge.post_json("x", with_tools=False)
                    self.assertEqual(status, 200)
                    legacy.assert_called_once()
            self.assertEqual(len(calls), 1)

    def test_c8_rw002_pre_delivery_surrogate_falls_back_to_run(self) -> None:
        """Битое событие до execution и заголовков prompt допускает резервный run."""
        self._auto_mode()
        for stream, field, surrogate in (
            (True, "reasoning", "\ud800"),
            (False, "text", "\udc00"),
        ):
            self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: независимые защиты сценария
            fragment = """
            emit({"type":"session.FIELD.delta","data":{"sessionID":sid,"delta":SURROGATE}})
            return
""".replace("FIELD", field).replace("SURROGATE", repr(surrogate))
            fake = (
                FAKE_SERVE.replace(
                    '            if "__native_pause__" in prompt:',
                    fragment + '            if "__native_pause__" in prompt:',
                )
                .replace(
                    "json.dumps(obj, ensure_ascii=False)",
                    "json.dumps(obj, ensure_ascii=True)",
                )
                .replace(
                    '            state["prompt"] = prompt_text\n',
                    '            state["prompt"] = prompt_text\n            time.sleep(5)\n',
                )
            )
            _ = self.fake.write_text(fake)
            with (
                mock.patch.object(server, "MAX_TOTAL_SPAWNS", 2),
                mock.patch.object(
                    server,
                    "_serve_one_attempt",
                    wraps=server._serve_one_attempt,  # pyright: ignore[reportPrivateUsage] — причина: проверяется реальная попытка serve до барьера
                ) as attempt,
            ):
                if stream:
                    chunks, _ = self.bridge.post_stream_timed("x")
                    output = json.dumps(chunks, ensure_ascii=False)
                else:
                    status, reply = self.bridge.post_json("x", with_tools=False)
                    self.assertEqual(status, 200, reply)
                    output = json.dumps(reply, ensure_ascii=False)
                self.assertIn("Поздний ответ", output)
                attempt.assert_called_once()
            self.assertIn("transport=run", server.LOG_PATH.read_text())

    def test_c8_rw003_request_deadline_timeout_is_neutral_for_circuit_breaker(
        self,
    ) -> None:
        """Локальный дедлайн нейтрален, фазовые watchdog учитываются breaker."""
        self._auto_mode()
        for stream in (True, False):
            for reason in (
                "startup",
                "timeout",
                "first_token_timeout",
                "stall_timeout",
            ):
                self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватная граница serve и управление запуском
                breaker = self.bridge.httpd.resilience.breaker
                for _ in range(2):
                    calls, patcher = self._patched_attempts(
                        [lambda _args: _fake_result(exit_reason=reason, delivered=True)]
                    )
                    if reason == "startup":
                        patcher = mock.patch.object(
                            server,
                            "_spawn_serve",
                            side_effect=server.ServeStartupDeadlineExceeded("deadline"),
                        )
                    with (
                        patcher,
                        mock.patch.object(server, "MAX_TOTAL_SPAWNS", 1),
                        mock.patch.object(server.Run, "execute") as legacy,
                        mock.patch.object(server, "_spawn_with_stdin") as spawn,
                    ):
                        if stream:
                            chunks, _ = self.bridge.post_stream_timed("x")
                            self.assertTrue(
                                any("error" in chunk for _, chunk in chunks), chunks
                            )
                        else:
                            status, reply = self.bridge.post_json("x", with_tools=False)
                            self.assertIn(status, (502, 504), reply)
                        legacy.assert_not_called()
                        spawn.assert_not_called()
                    if reason != "startup":
                        self.assertEqual(len(calls), 1)
                self.assertEqual(
                    breaker._failures,  # pyright: ignore[reportPrivateUsage] — причина: проверяется точное число отказов breaker
                    0 if reason in ("startup", "timeout") else 2,
                )
                self.assertEqual(breaker.state, "CLOSED")

    def test_c8_fu001_multiple_native_tool_calls_same_step_preserved_next_step_excluded(
        self,
    ) -> None:
        """Все вызовы закрываемого шага сохранены один раз, следующий шаг исключён."""
        fragment = """
            emit({"type":"session.execution.started","data":{"sessionID":sid}})
            for cid, mid, command in [("c1","m1","pwd"),("c2","m1","ls"),("c2","m1","ls"),("foreign","m2","wrong")]:
                if cid == "c2": time.sleep(0.22)
                emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":mid,"id":cid,"name":"bash","input":{"command":command}}})
            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":123,"output":45,"reasoning":6,"cache":{"read":10}}}})
            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m2","id":"c3","name":"bash","input":{"command":"wrong"}}})
            return
"""
        _ = self.fake.write_text(
            FAKE_SERVE.replace(
                '            if "__native_pause__" in prompt:',
                fragment + '            if "__native_pause__" in prompt:',
            )
        )
        for stream in (True, False):
            with self.subTest(stream=stream):
                if stream:
                    chunks, _ = self.bridge.post_stream_timed("x")
                    self.assertEqual(_tool_names(chunks), ["bash", "bash"])
                    output = json.dumps(chunks, ensure_ascii=False)
                    usages = [
                        _as_obj_dict(c["usage"]) for _, c in chunks if "usage" in c
                    ]
                    usage = usages[-1]
                else:
                    status, reply = self.bridge.post_json("x")
                    self.assertEqual(status, 200, reply)
                    output = json.dumps(reply, ensure_ascii=False)
                    choices = cast("list[object]", reply["choices"])
                    message = _as_obj_dict(_as_obj_dict(choices[0])["message"])
                    self.assertEqual(
                        len(cast("list[object]", message["tool_calls"])), 2
                    )
                    usage = _as_obj_dict(reply["usage"])
                self.assertIn("pwd", output)
                self.assertIn("ls", output)
                self.assertNotIn("wrong", output)
                self.assertEqual(usage["prompt_tokens"], 123)
                self.assertEqual(usage["completion_tokens"], 45)
                self.assertEqual(
                    _as_obj_dict(usage["prompt_tokens_details"])["cached_tokens"], 10
                )
                self.assertEqual(
                    _as_obj_dict(usage["completion_tokens_details"])[
                        "reasoning_tokens"
                    ],
                    6,
                )

    def test_c9_rw001_idless_and_unconfirmed_native_step(self) -> None:
        """Без ID сохраняются оба вызова; EOF и окно без step.ended дают ошибку."""
        for scenario in ("idless", "inherited", "eof", "window"):
            fragment = """
            emit({"type":"session.reasoning.delta","data":{"sessionID":sid,"assistantMessageID":"m1","delta":"Думаю"}})
            emit({"type":"session.tool.called","data":{"sessionID":sid,"id":"c1","name":"bash","input":{"command":"pwd"}}})
            time.sleep(0.22)
            if SCENARIO in ("idless", "inherited"):
                emit({"type":"session.tool.input.started","data":{"sessionID":sid,"id":"c2","name":"bash"}})
                emit({"type":"session.tool.input.ended","data":{"sessionID":sid,"id":"c2","text":'{"command":"ls"}'}})
                if SCENARIO == "idless":
                    emit({"type":"session.tool.called","data":{"sessionID":sid,"id":"c2","name":"bash","input":{"command":"ls"}}})
                emit({"type":"session.step.ended","data":{"sessionID":sid,"tokens":{"input":123,"output":45,"reasoning":6,"cache":{"read":10}}}})
                emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m2","id":"c3","name":"bash","input":{"command":"wrong"}}})
            if SCENARIO == "window": time.sleep(2)
            return
""".replace("SCENARIO", repr(scenario))
            if scenario == "idless":
                fragment = fragment.replace(',"assistantMessageID":"m1"', "")
            _ = self.fake.write_text(
                FAKE_SERVE.replace(
                    '            if "__native_pause__" in prompt:',
                    fragment + '            if "__native_pause__" in prompt:',
                )
            )
            for stream in (True, False):
                with self.subTest(scenario=scenario, stream=stream):
                    self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: независимый breaker для каждого сценария
                    with mock.patch.object(server, "MAX_TOTAL_SPAWNS", 1):
                        if stream:
                            chunks, _ = self.bridge.post_stream_timed("x")
                            output = json.dumps(chunks, ensure_ascii=False)
                            if scenario in ("eof", "window"):
                                self.assertTrue(
                                    any("error" in c for _, c in chunks), chunks
                                )
                                self.assertNotIn(
                                    '"finish_reason": "tool_calls"', output
                                )
                                self.assertIn(
                                    "exit_reason=invalid_serve_event",
                                    server.LOG_PATH.read_text(),
                                )
                                continue
                            self.assertEqual(_tool_names(chunks), ["bash", "bash"])
                            usage = [
                                _as_obj_dict(c["usage"])
                                for _, c in chunks
                                if "usage" in c
                            ][-1]
                        else:
                            status, reply = self.bridge.post_json("x")
                            if scenario in ("eof", "window"):
                                self.assertEqual(status, 502, reply)
                                self.assertIn(
                                    "exit_reason=invalid_serve_event",
                                    server.LOG_PATH.read_text(),
                                )
                                continue
                            self.assertEqual(status, 200, reply)
                            output = json.dumps(reply, ensure_ascii=False)
                            choices = cast("list[object]", reply["choices"])
                            message = _as_obj_dict(_as_obj_dict(choices[0])["message"])
                            self.assertEqual(
                                len(cast("list[object]", message["tool_calls"])), 2
                            )
                            usage = _as_obj_dict(reply["usage"])
                        self.assertIn("pwd", output)
                        self.assertIn("ls", output)
                        self.assertNotIn("wrong", output)
                        self.assertEqual(usage["prompt_tokens"], 123)
                        self.assertEqual(usage["completion_tokens"], 45)
                        self.assertEqual(
                            _as_obj_dict(usage["prompt_tokens_details"])[
                                "cached_tokens"
                            ],
                            10,
                        )
                        self.assertEqual(
                            _as_obj_dict(usage["completion_tokens_details"])[
                                "reasoning_tokens"
                            ],
                            6,
                        )

    def test_c11_rw003_initial_writes_fail_closed(self) -> None:
        """RW-003: заголовки, role и таймер ограничены одной обёрткой записи."""
        locked_cls = server._LockedWfile  # pyright: ignore[reportPrivateUsage] — причина: инъекции на реальной границе downstream
        write = locked_cls.write
        mark = locked_cls._mark_client_gone  # pyright: ignore[reportPrivateUsage] — причина: проверяется сигнал ухода клиента
        for stage in (b"HTTP/", b'"role"', b'"reasoning_content"'):
            with self.subTest(stage=stage):
                self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: изолированный bulkhead
                gone: list[bool] = []

                def mark_gone(locked: server._LockedWfile) -> None:  # pyright: ignore[reportPrivateUsage] — причина: spy ограниченной записи
                    mark(locked)
                    sock = locked._sock  # pyright: ignore[reportPrivateUsage] — причина: проверяется закрытие клиентского сокета
                    gone.append(
                        locked.client_gone
                        and (
                            sock is None
                            or bool(cast(object, getattr(sock, "_closed", False)))
                        )
                    )

                def write_failed(locked: server._LockedWfile, data: bytes) -> int:  # pyright: ignore[reportPrivateUsage] — причина: инъекция в ограниченную запись
                    if stage in data:
                        with mock.patch.object(
                            locked._inner,  # pyright: ignore[reportPrivateUsage] — причина: оракул проверяет приватную границу моста
                            "write",
                            side_effect=TimeoutError("blocked initial write"),
                        ):
                            return write(locked, data)
                    return write(locked, data)

                with (
                    mock.patch.object(
                        locked_cls, "write", autospec=True, side_effect=write_failed
                    ),
                    mock.patch.object(
                        locked_cls,
                        "_mark_client_gone",
                        autospec=True,
                        side_effect=mark_gone,
                    ),
                    mock.patch.object(server, "FIRST_TOKEN_TIMEOUT_S", 1.0),
                    mock.patch.object(server, "MAX_TOTAL_SPAWNS", 1),
                    mock.patch.object(
                        server,
                        "_spawn_serve",
                        wraps=server._spawn_serve,  # pyright: ignore[reportPrivateUsage] — причина: оракул проверяет приватную границу моста
                    ) as spawned,
                ):
                    try:
                        _ = self.bridge.post_stream_timed("__silent__", timeout=5.0)
                    except (OSError, http.client.HTTPException):
                        pass
                    cleanup_deadline = time.monotonic() + 6.0
                    while (
                        self.bridge.httpd.resilience.slots.in_use
                        and time.monotonic() < cleanup_deadline
                    ):
                        time.sleep(0.02)
                self.assertTrue(gone, stage)
                self.assertTrue(all(gone))
                self.assertEqual(self.bridge.httpd.resilience.slots.in_use, 0)
                if stage != b'"reasoning_content"':
                    spawned.assert_not_called()
                self.assertFalse(list(server.LEASE_DIR.glob("lease-*.json")))

    def test_c11_rw003_status_socket_timeout_before_model_token(self) -> None:
        """RW-003: полное окно клиента ограничивает status ещё до первого токена."""
        groups: list[int] = []
        lease_cls = server._ServeLease  # pyright: ignore[reportPrivateUsage] — причина: наблюдается реальная группа serve
        cleanup = lease_cls.cleanup

        def cleanup_group(lease: server._ServeLease) -> None:  # pyright: ignore[reportPrivateUsage] — причина: фиксируется PGID убираемой группы
            groups.append(lease.pgid)
            cleanup(lease)

        body = json.dumps(
            {
                "model": MODEL,
                "stream": True,
                "messages": [{"role": "user", "content": "__silent__"}],
            }
        ).encode()
        request = (
            b"POST /v1/chat/completions HTTP/1.1\r\nHost: localhost\r\n"
            + f"Authorization: Bearer {server.AUTH_KEY}\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
            + body
        )
        client = socket.socket()
        try:
            client.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
            client.settimeout(3.0)
            client.connect(("127.0.0.1", self.bridge.port))
            with (
                mock.patch.object(
                    server, "STATUS_INITIAL", "[мост] " + "x" * (8 * 1024 * 1024)
                ),
                mock.patch.object(
                    lease_cls, "cleanup", autospec=True, side_effect=cleanup_group
                ),
            ):
                started = time.monotonic()
                client.sendall(request)
                received = b""
                while not received.endswith(b"\r\n\r\n"):
                    received += client.recv(1)
                slots = self.bridge.httpd.resilience.slots
                while time.monotonic() - started < 6.5:
                    if groups and slots.in_use == 0:
                        break
                    time.sleep(0.02)
                self.assertTrue(groups)
                self.assertEqual(slots.in_use, 0)
                for pgid in groups:
                    self.assertFalse(server._pid_alive(-pgid))  # pyright: ignore[reportPrivateUsage] — причина: реальный оракул остановки группы
                self.assertGreaterEqual(time.monotonic() - started, 5.0)
                self.assertLess(time.monotonic() - started, 7.0)
        finally:
            client.close()

    def test_c11_rw001_drain_text_delivered_once_with_native_tool(self) -> None:
        """RW-001: хвост в дренаже доставляется один раз вместе с native tool."""
        fragment = """
            emit({"type":"session.execution.started","data":{"sessionID":sid}})
            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"c1","name":"bash","input":{"command":"pwd"}}})
            emit({"type":"session.text.delta","data":{"sessionID":sid,"assistantMessageID":"m1","delta":"хвост"}})
            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0,"write":0}}}})
            return
"""
        _ = self.fake.write_text(
            FAKE_SERVE.replace(
                '            if "__native_pause__" in prompt:',
                fragment + '            if "__native_pause__" in prompt:',
            )
        )
        for stream in (True, False):
            with self.subTest(stream=stream):
                if stream:
                    chunks, _ = self.bridge.post_stream_timed("x")
                    content = "".join(t for _, t in _deltas(chunks, "content"))
                    self.assertEqual(_tool_names(chunks), ["bash"])
                    finishes = [
                        _as_obj_dict(cast("list[object]", c["choices"])[0]).get(
                            "finish_reason"
                        )
                        for _, c in chunks
                        if c.get("choices")
                    ]
                    self.assertIn("tool_calls", finishes)
                else:
                    status, reply = self.bridge.post_json("x")
                    self.assertEqual(status, 200, reply)
                    choice = _as_obj_dict(cast("list[object]", reply["choices"])[0])
                    message = _as_obj_dict(choice["message"])
                    content = str(message.get("content") or "")
                    self.assertEqual(
                        len(cast("list[object]", message["tool_calls"])), 1
                    )
                    self.assertEqual(choice["finish_reason"], "tool_calls")
                self.assertEqual(content, "хвост")

    def test_c11_rw005_completed_text_preserves_reasoning_without_retry(self) -> None:
        """RW-005: serve/run SSE/JSON сохраняют reasoning и завершают за одну попытку."""
        marker = "I was interrupted right before making tool calls."
        thought = "Начало " + marker + " Конец\n"
        serve_body = (
            FAKE_SERVE.replace('f"Мысль{i} "', repr(thought))
            .replace("range(5)", "range(1)")
            .replace('"Ответ\\n"', '"Привет!"')
        )
        legacy_body = LEGACY_FAKE.replace('"Simple greeting."', repr(thought))
        for transport in ("serve", "run"):
            _ = self.fake.write_text(
                serve_body if transport == "serve" else legacy_body
            )
            for stream in (True, False):
                with (
                    self.subTest(transport=transport, stream=stream),
                    mock.patch.dict(
                        os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": transport}
                    ),
                    mock.patch.object(server, "STEP_RECOVERY_ENABLED", True),
                    mock.patch.object(
                        server,
                        "_serve_one_attempt",
                        wraps=server._serve_one_attempt,  # pyright: ignore[reportPrivateUsage] — причина: оракул проверяет приватную границу моста
                    ) as attempt,
                    mock.patch.object(
                        subprocess,
                        "Popen",
                        wraps=subprocess.Popen,
                    ) as spawned,
                ):
                    if stream:
                        chunks, _ = self.bridge.post_stream_timed(
                            "x", tool_choice="auto"
                        )
                        reasoning = "".join(
                            t
                            for _, t in _deltas(chunks, "reasoning_content")
                            if not t.lstrip("\n").startswith("[мост]")
                        )
                        content = "".join(t for _, t in _deltas(chunks, "content"))
                    else:
                        status, reply = self.bridge.post_json("x", tool_choice="auto")
                        self.assertEqual(status, 200, reply)
                        message = _as_obj_dict(
                            _as_obj_dict(cast("list[object]", reply["choices"])[0])[
                                "message"
                            ]
                        )
                        reasoning = str(message.get("reasoning_content") or "")
                        content = str(message.get("content") or "")
                    self.assertIn("Привет!", content)
                    self.assertEqual(reasoning.encode(), thought.encode())
                    if transport == "serve":
                        self.assertEqual(attempt.call_count, 1)
                    else:
                        runs = [c for c in spawned.call_args_list if "run" in c.args[0]]
                        self.assertEqual(len(runs), 1)

    def test_c10_rw001_drain_permission_reject_continues_and_reasoning_delivered(
        self,
    ) -> None:
        """RW-001 цикл 10: permission в дренаже — reject без interrupt, reasoning доставлен."""
        fragment = """
            emit({"type":"session.execution.started","data":{"sessionID":sid}})
            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"c1","name":"bash","input":{"command":"pwd"}}})
            emit({"type":"session.reasoning.delta","data":{"sessionID":sid,"assistantMessageID":"m1","delta":"Думаю в дренаже"}})
            emit({"type":"permission.asked","data":{"id":"per1","sessionID":sid,"action":"bash","resources":["*"]}})
            time.sleep(0.5)
            emit({"type":"session.reasoning.delta","data":{"sessionID":sid,"assistantMessageID":"m1","delta":" perm=" + ("rejected" if state["rejected"] else "pending") + " interrupted=" + ("yes" if state["interrupted"] else "no")}})
            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":11,"output":7,"reasoning":2,"cache":{"read":3}}}})
            emit({"type":"session.execution.succeeded","data":{"sessionID":sid}})
            return
"""
        _ = self.fake.write_text(
            FAKE_SERVE.replace(
                '            if "__native_pause__" in prompt:',
                fragment + '            if "__native_pause__" in prompt:',
            )
        )
        for stream in (True, False):
            with self.subTest(stream=stream):
                self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: независимые защиты сценария
                if stream:
                    chunks, _ = self.bridge.post_stream_timed("x")
                    self.assertFalse(any("error" in c for _, c in chunks), chunks)
                    self.assertEqual(_tool_names(chunks), ["bash"])
                    reasoning = "".join(
                        t for _, t in _deltas(chunks, "reasoning_content")
                    )
                    usages = [
                        _as_obj_dict(c["usage"]) for _, c in chunks if "usage" in c
                    ]
                    usage = usages[-1]
                else:
                    status, reply = self.bridge.post_json("x")
                    self.assertEqual(status, 200, reply)
                    choices = cast("list[object]", reply["choices"])
                    message = _as_obj_dict(_as_obj_dict(choices[0])["message"])
                    self.assertEqual(
                        len(cast("list[object]", message["tool_calls"])), 1
                    )
                    reasoning_obj: object = message.get("reasoning_content")
                    reasoning = reasoning_obj if isinstance(reasoning_obj, str) else ""
                    usage = _as_obj_dict(reply["usage"])
                self.assertIn("Думаю в дренаже", reasoning)
                self.assertIn("perm=rejected", reasoning)
                self.assertIn("interrupted=no", reasoning)
                self.assertEqual(usage["prompt_tokens"], 11)
                self.assertEqual(usage["completion_tokens"], 7)

    def test_c10_rw001_drain_form_created_fails_closed_without_tool(self) -> None:
        """RW-001 цикл 10: form.created своей сессии в дренаже — cancel+interrupt, без tool."""
        record = self.tmp / "rec-c10-form.json"
        fragment = """
            emit({"type":"session.execution.started","data":{"sessionID":sid}})
            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"c1","name":"bash","input":{"command":"pwd"}}})
            emit({"type":"form.created","data":{"form":{"id":"form1","sessionID":sid}}})
            time.sleep(0.5)
            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":11,"output":7,"reasoning":2,"cache":{"read":3}}}})
            emit({"type":"session.execution.succeeded","data":{"sessionID":sid}})
            return
"""
        _ = self.fake.write_text(
            FAKE_SERVE.replace(
                '            if "__native_pause__" in prompt:',
                fragment + '            if "__native_pause__" in prompt:',
            )
        )
        for stream in (True, False):
            with self.subTest(stream=stream):
                self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: независимые защиты сценария
                control = Path(str(record) + ".control")
                control.unlink(missing_ok=True)
                record.unlink(missing_ok=True)
                prompt = f"__record:{record}__ заполни"
                if stream:
                    chunks, _ = self.bridge.post_stream_timed(prompt)
                    self.assertTrue(any("error" in c for _, c in chunks), chunks)
                    self.assertEqual(_tool_names(chunks), [])
                    self.assertNotIn(
                        '"finish_reason": "tool_calls"',
                        json.dumps(chunks, ensure_ascii=False),
                    )
                else:
                    status, reply = self.bridge.post_json(prompt)
                    self.assertEqual(status, 502, reply)
                    self.assertNotIn("tool_calls", json.dumps(reply))
                self.assertTrue(control.exists(), "FakeServe не получил cancel")
                control_text = control.read_text("utf-8")
                self.assertIn("cancelled", control_text)
                self.assertIn("interrupt", control_text)

    def test_c10_rw001_drain_error_classification_preserved(self) -> None:
        """RW-001 цикл 10: ошибка в дренаже — 401 без повтора, 429 с повтором serve."""
        counter = self.tmp / "c10-drain-error-count"
        for code, with_step_ended in ((401, True), (429, False)):
            fragment = (
                (
                    """
            counter = Path(COUNTER)
            n = int(counter.read_text()) if counter.exists() else 0
            counter.write_text(str(n + 1))
            if n == 0:
                emit({"type":"session.execution.started","data":{"sessionID":sid}})
                emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"c1","name":"bash","input":{"command":"AAA"}}})
                emit({"type":"session.execution.failed","data":{"sessionID":sid,"error":{"message":"boom","status":STATUS}}})
"""
                    + (
                        '                emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0}}}})\n'
                        if with_step_ended
                        else ""
                    )
                    + """                return
"""
                )
                .replace("COUNTER", repr(str(counter)))
                .replace("STATUS", str(code))
            )
            _ = self.fake.write_text(
                FAKE_SERVE.replace(
                    '            if "__native_pause__" in prompt:',
                    fragment + '            if "__native_pause__" in prompt:',
                )
            )
            for stream in (True, False):
                with self.subTest(code=code, stream=stream):
                    self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: независимые защиты сценария
                    counter.unlink(missing_ok=True)
                    with (
                        mock.patch.object(server, "MAX_TOTAL_SPAWNS", 2),
                        mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
                    ):
                        if stream:
                            chunks, _ = self.bridge.post_stream_timed("x")
                            output = json.dumps(chunks, ensure_ascii=False)
                            if code == 401:
                                self.assertTrue(
                                    any("error" in c for _, c in chunks), chunks
                                )
                            else:
                                self.assertIn("Ответ", output)
                            self.assertNotIn("AAA", output)
                        else:
                            status, reply = self.bridge.post_json("x")
                            output = json.dumps(reply, ensure_ascii=False)
                            if code == 401:
                                self.assertEqual(status, 502, reply)
                            else:
                                self.assertEqual(status, 200, reply)
                                self.assertIn("Ответ", output)
                            self.assertNotIn("AAA", output)
                    self.assertEqual(counter.read_text(), "1" if code == 401 else "2")

    def test_c10_rw002_unconfirmed_tool_not_published_retry_b_only(self) -> None:
        """RW-002 цикл 10: EOF без step.ended не публикует A; повтор публикует только B."""
        counter = self.tmp / "c10-rw002-count"
        fragment = """
            counter = Path(COUNTER)
            n = int(counter.read_text()) if counter.exists() else 0
            counter.write_text(str(n + 1))
            emit({"type":"session.execution.started","data":{"sessionID":sid}})
            if n == 0:
                emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"cA","name":"bash","input":{"command":"AAA"}}})
                return
            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"cB","name":"bash","input":{"command":"BBB"}}})
            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":5,"output":3,"reasoning":1,"cache":{"read":0}}}})
            emit({"type":"session.execution.succeeded","data":{"sessionID":sid}})
            return
""".replace("COUNTER", repr(str(counter)))
        _ = self.fake.write_text(
            FAKE_SERVE.replace(
                '            if "__native_pause__" in prompt:',
                fragment + '            if "__native_pause__" in prompt:',
            )
        )
        for stream in (True, False):
            with self.subTest(stream=stream):
                self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: независимые защиты сценария
                counter.unlink(missing_ok=True)
                with (
                    mock.patch.object(server, "MAX_TOTAL_SPAWNS", 2),
                    mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
                ):
                    if stream:
                        chunks, _ = self.bridge.post_stream_timed("x")
                        output = json.dumps(chunks, ensure_ascii=False)
                        self.assertEqual(_tool_names(chunks), ["bash"])
                    else:
                        status, reply = self.bridge.post_json("x")
                        self.assertEqual(status, 200, reply)
                        output = json.dumps(reply, ensure_ascii=False)
                        choices = cast("list[object]", reply["choices"])
                        message = _as_obj_dict(_as_obj_dict(choices[0])["message"])
                        self.assertEqual(
                            len(cast("list[object]", message["tool_calls"])), 1
                        )
                self.assertIn("BBB", output)
                self.assertNotIn("AAA", output)
                self.assertEqual(counter.read_text(), "2")

    def test_c10_rw003_reasoning_markers_preserved_text_clean(self) -> None:
        """RW-003 цикл 10: оба маркера в reasoning побайтово (целые и split), content чист."""
        marker1 = "I was interrupted right before making tool calls."
        marker2 = (
            "The previous response was interrupted. Continue from where you left off "
            "without repeating completed content."
        )
        cut = 40
        fragment = (
            """
            emit({"type":"session.execution.started","data":{"sessionID":sid}})
            emit({"type":"session.reasoning.delta","data":{"sessionID":sid,"assistantMessageID":"m1","delta":M1}})
            emit({"type":"session.reasoning.delta","data":{"sessionID":sid,"assistantMessageID":"m1","delta":M2A}})
            emit({"type":"session.reasoning.delta","data":{"sessionID":sid,"assistantMessageID":"m1","delta":M2B}})
            emit({"type":"session.text.delta","data":{"sessionID":sid,"assistantMessageID":"m1","delta":TA}})
            emit({"type":"session.text.delta","data":{"sessionID":sid,"assistantMessageID":"m1","delta":TB}})
            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":5,"output":3,"reasoning":1,"cache":{"read":0}}}})
            emit({"type":"session.execution.succeeded","data":{"sessionID":sid}})
            return
""".replace("M1", repr(marker1))
            .replace("M2A", repr(marker2[:cut]))
            .replace("M2B", repr(marker2[cut:]))
            .replace("TA", repr("Ответ " + marker1[:20]))
            .replace("TB", repr(marker1[20:] + " хвост"))
        )
        _ = self.fake.write_text(
            FAKE_SERVE.replace(
                '            if "__native_pause__" in prompt:',
                fragment + '            if "__native_pause__" in prompt:',
            )
        )
        for stream in (True, False):
            with self.subTest(stream=stream):
                self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: независимые защиты сценария
                with mock.patch.object(server, "STEP_RECOVERY_ENABLED", False):
                    if stream:
                        chunks, _ = self.bridge.post_stream_timed("x")
                        reasoning = "".join(
                            t
                            for _, t in _deltas(chunks, "reasoning_content")
                            if not t.lstrip("\n").startswith("[мост]")
                        )
                        content = "".join(t for _, t in _deltas(chunks, "content"))
                    else:
                        status, reply = self.bridge.post_json("x", with_tools=True)
                        self.assertEqual(status, 200, reply)
                        choices = cast("list[object]", reply["choices"])
                        message = _as_obj_dict(_as_obj_dict(choices[0])["message"])
                        reasoning_obj: object = message.get("reasoning_content")
                        reasoning = (
                            reasoning_obj if isinstance(reasoning_obj, str) else ""
                        )
                        content_obj: object = message.get("content")
                        content = content_obj if isinstance(content_obj, str) else ""
                self.assertEqual(reasoning, marker1 + marker2)
                self.assertNotIn("interrupted", content)
                self.assertIn("Ответ", content)
                self.assertIn("хвост", content)

    def test_c10_rw005_slow_client_bounded_cleanup_and_slot_released(self) -> None:
        """RW-005 цикл 10: клиент не читает после заголовков — ограниченный финиш и cleanup."""
        record = self.tmp / "c10-slow-record.json"
        fragment = """
            emit({"type":"session.execution.started","data":{"sessionID":sid}})
            for _i in range(160):
                emit({"type":"session.reasoning.delta","data":{"sessionID":sid,"assistantMessageID":"m1","delta":"x" * 65536}})
            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":5,"output":3,"reasoning":1,"cache":{"read":0}}}})
            emit({"type":"session.execution.succeeded","data":{"sessionID":sid}})
            return
"""
        _ = self.fake.write_text(
            FAKE_SERVE.replace(
                '            if "__native_pause__" in prompt:',
                fragment + '            if "__native_pause__" in prompt:',
            )
        )
        payload: dict[str, object] = {
            "model": MODEL,
            "stream": True,
            "messages": [
                {"role": "user", "content": f"__record:{record}__ большой вывод"}
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "bash",
                        "description": "x",
                        "parameters": {
                            "type": "object",
                            "properties": {"command": {"type": "string"}},
                            "required": ["command"],
                        },
                    },
                }
            ],
        }
        body = json.dumps(payload).encode()
        request = (
            b"POST /v1/chat/completions HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            + f"Authorization: Bearer {server.AUTH_KEY}\r\n".encode()
            + b"Content-Type: application/json\r\n"
            + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
            + body
        )
        client = socket.socket()
        try:
            client.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
            client.settimeout(10)
            client.connect(("127.0.0.1", self.bridge.port))
            with mock.patch.object(
                server, "_DOWNSTREAM_WRITE_TIMEOUT_S", 0.5, create=True
            ):
                client.sendall(request)
                received = b""
                while b"\r\n\r\n" not in received:
                    chunk = client.recv(4096)
                    self.assertTrue(chunk, "сервер не прислал заголовки")
                    received += chunk
                self.assertIn(b"200", received.split(b"\r\n", 1)[0])
                started = time.monotonic()
                slots = self.bridge.httpd.resilience.slots
                while time.monotonic() - started < 20.0:
                    if slots.in_use == 0 and record.exists():
                        break
                    time.sleep(0.05)
                elapsed = time.monotonic() - started
                self.assertEqual(slots.in_use, 0, "bulkhead-слот не возвращён")
                self.assertLess(elapsed, 20.0)
                self.assertTrue(record.exists(), "FakeServe не записал record")
                record_obj: object = json.loads(record.read_text())  # pyright: ignore[reportAny] — причина: record FakeServe — динамический JSON
                pgid_obj: object = _as_obj_dict(record_obj).get("pgid")
                self.assertIsInstance(pgid_obj, int)
                pgid = cast(int, pgid_obj)
                deadline = time.monotonic() + 5.0
                while time.monotonic() < deadline:
                    try:
                        os.killpg(pgid, 0)
                    except ProcessLookupError:
                        break
                    time.sleep(0.05)
                else:
                    self.fail("группа процессов serve пережила downstream-таймаут")
                self.assertFalse(list(server.LEASE_DIR.glob("lease-*.json")))
        finally:
            client.close()

    def test_c8_fu002_legacy_spawn_rechecks_cancel_and_deadline_after_reservation(
        self,
    ) -> None:
        """После резерва токена отмена и дедлайн запрещают legacy spawn и возвращают резерв."""
        for stream in (True, False):
            for cancel in (True, False):
                log_before = (
                    server.LOG_PATH.read_text() if server.LOG_PATH.exists() else ""
                )
                exit_logged = threading.Event()
                original_log = server._log  # pyright: ignore[reportPrivateUsage] — причина: синхронизация с реальной записью O-EXIT

                def observe_log(message: str) -> None:
                    original_log(message)
                    if "O-EXIT/v1" in message:
                        exit_logged.set()

                gone = [False]
                limiter = self.bridge.httpd.resilience.spawn_limiter

                def reserve(*_args: object, **_kw: object) -> bool:
                    if cancel:
                        gone[0] = True
                    else:
                        time.sleep(0.08)
                    return True

                with (
                    mock.patch.object(server, "_log", side_effect=observe_log),
                    mock.patch.dict(
                        os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": "run"}
                    ),
                    mock.patch.object(server, "TIMEOUT_S", 0.05),
                    mock.patch.object(
                        server.Handler,
                        "_client_gone_check",
                        side_effect=lambda: gone[0],
                    ),
                    mock.patch.object(limiter, "acquire", side_effect=reserve),
                    mock.patch.object(
                        limiter, "refund", wraps=limiter.refund
                    ) as refund,
                    mock.patch.object(server, "_spawn_with_stdin") as spawn,
                ):
                    if stream:
                        _ = self.bridge.post_stream_timed("x")
                    else:
                        status, _ = self.bridge.post_json("x", with_tools=False)
                        self.assertIn(status, (502, 504))
                    self.assertTrue(exit_logged.wait(3.0), "O-EXIT не записан")
                    spawn.assert_not_called()
                    refund.assert_called_once()
                new_lines = server.LOG_PATH.read_text()[len(log_before) :].splitlines()
                exits = [line for line in new_lines if "O-EXIT/v1" in line]
                self.assertEqual(len(exits), 1, exits)
                self.assertIn(
                    "exit_reason=" + ("client_gone" if cancel else "timeout"), exits[0]
                )
                self.assertIn("total_spawns=0", exits[0])
                self.assertEqual(self.bridge.httpd.resilience.breaker._failures, 0)  # pyright: ignore[reportPrivateUsage] — причина: проверяется нейтральный timeout
                self.assertEqual(self.bridge.httpd.resilience.slots.in_use, 0)
                self.assertFalse(server._STARTUP_LOCK.locked())  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватная граница serve и управление запуском

    def test_ac026_realtime_chunks_before_upstream_end(self) -> None:
        """AC-026: reasoning-чанки приходят, пока апстрим ещё идёт."""
        end_record = self.tmp / "upstream-ended"
        chunks, _elapsed = self.bridge.post_stream_timed(
            f"обычный запрос __end_record:{end_record}__"
        )
        reasoning = _deltas(chunks, "reasoning_content")
        model_reasoning = [
            (at, t) for at, t in reasoning if not t.lstrip("\n").startswith("[мост]")
        ]
        self.assertGreaterEqual(len(model_reasoning), 5, chunks)
        sent_raw = cast(object, json.loads(Path(str(end_record) + ".sent").read_text()))
        sent_times = [float(t) for t in cast("list[float]", sent_raw)]
        recv_times = [self.bridge.stream_started + at for at, _t in model_reasoning]
        self.assertEqual(len(sent_times), len(recv_times))
        for sent_t, recv_t in zip(sent_times, recv_times):
            self.assertGreaterEqual(recv_t - sent_t, 0.0)
            self.assertLess(recv_t - sent_t, 0.25)
        r_times = [at for at, _t in model_reasoning]
        c_times = [at for at, t in _deltas(chunks, "content") if t]
        self.assertTrue(c_times, chunks)
        self.assertLess(r_times[0], c_times[0])
        self.assertGreaterEqual(r_times[-1] - r_times[0], 0.15)
        self.assertLess(max(b - a for a, b in zip(r_times, r_times[1:])), 0.5)
        first_reasoning_t = model_reasoning[0][0]
        upstream_end_t = float(end_record.read_text()) - self.bridge.stream_started
        self.assertLess(first_reasoning_t, upstream_end_t)
        self.assertLess(model_reasoning[-1][0] - model_reasoning[0][0], 2.0)
        joined = "".join(t for _at, t in model_reasoning)
        self.assertEqual(joined, "Мысль0 Мысль1 Мысль2 Мысль3 Мысль4 ")

    def test_dynamic_config_switch_same_server(self) -> None:
        """Тот же Server: false -> run, true -> serve, битый JSON -> false."""
        reader = server._read_dynamic_config_enabled  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        self.assertTrue(reader())
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": False}), "utf-8")
        self.assertFalse(reader())
        _ = self.cfg.write_text("{broken", "utf-8")
        self.assertFalse(reader())
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": "yes"}), "utf-8")
        self.assertFalse(reader())
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
        self.assertTrue(reader())

    def test_serve_env_sanitized_all_branches(self) -> None:
        """_serve_env: :memory:, allowlist, без OPENCODE_BIN и секретов."""
        with mock.patch.dict(
            os.environ, {"SECRET_SENTINEL": "x", "MY_API_KEY": "y"}, clear=False
        ):
            env: dict[str, str] = server._serve_env(MODEL)  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        try:
            self.assertEqual(env.get("OPENCODE_DB"), ":memory:")
            self.assertNotIn("OPENCODE_BIN", env)
            self.assertNotIn("SECRET_SENTINEL", env)
            self.assertNotIn("MY_API_KEY", env)
            self.assertTrue(env.get("OPENCODE_SERVER_PASSWORD"))
            self.assertTrue(env.get("XDG_STATE_HOME"))
            self.assertNotEqual(env.get("XDG_DATA_HOME"), env.get("XDG_STATE_HOME"))
        finally:
            shutil.rmtree(env["XDG_STATE_HOME"], ignore_errors=True)

    def test_canonical_frozen_fixtures(self) -> None:
        """Каноническое отображение замороженных wire-фикстур v2.1.2."""
        mapper = server._map_serve_event  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        wire: dict[str, object] = {
            "id": "evt1",
            "type": "session.reasoning.delta",
            "data": {
                "sessionID": "ses_fixture_1",
                "assistantMessageID": "msg1",
                "delta": "Мысль без LF",
            },
        }
        result = mapper(wire)
        self.assertIsNotNone(result)
        assert result is not None
        etype, payload = result[0], result[1]
        self.assertEqual(etype, "reasoning")
        self.assertEqual(
            payload, {"reasoning_content": "Мысль без LF", "sessionID": "ses_fixture_1"}
        )
        wire2: dict[str, object] = {
            "id": "evt3",
            "type": "session.step.ended",
            "data": {
                "sessionID": "ses_fixture_1",
                "assistantMessageID": "msg1",
                "tokens": {
                    "input": 17,
                    "output": 9,
                    "reasoning": 4,
                    "cache": {"read": 3, "write": 2},
                },
            },
        }
        result2 = mapper(wire2)
        self.assertIsNotNone(result2)
        assert result2 is not None
        etype2, payload2 = result2[0], result2[1]
        self.assertEqual(etype2, "step_finish")
        self.assertEqual(
            payload2,
            {
                "input": 17,
                "output": 9,
                "cached": 3,
                "reasoning": 4,
                "sessionID": "ses_fixture_1",
            },
        )

    def test_tool_text_split_across_deltas(self) -> None:
        """ToolCallParser на разрезанных дельтах serve."""
        chunks, _elapsed = self.bridge.post_stream_timed("__tool_text__ вызов")
        self.assertEqual(_tool_names(chunks), ["bash"])

    def test_native_tool_and_permission_reject(self) -> None:
        """permission.asked -> reject, native tool -> DSH tool_call."""
        chunks, _elapsed = self.bridge.post_stream_timed("__native_tool__ сделай")
        self.assertIn("bash", _tool_names(chunks))

    def test_form_missing_title_cancels_without_step2(self) -> None:
        """form.created без title: cancel+interrupt до проверки схемы, без Step2."""
        record = self.tmp / "rec.json"
        chunks, _elapsed = self.bridge.post_stream_timed(
            f"__form_missing_title__ __record:{record}__ заполни"
        )
        content = "".join(t for _at, t in _deltas(chunks, "content"))
        self.assertNotIn("STEP2", content)
        control = Path(str(record) + ".control")
        self.assertTrue(control.exists(), "FakeServe не получил cancel")
        self.assertIn("cancelled", control.read_text("utf-8"))

    def test_slow_serve_gets_status_and_no_status_on_fast(self) -> None:
        """Медленный serve: статус <1с; быстрый serve: без лишнего статуса в reasoning модели."""
        chunks, _elapsed = self.bridge.post_stream_timed("__slow__ жди")
        statuses = [
            (at, t) for at, t in _deltas(chunks, "reasoning_content") if "[мост]" in t
        ]
        self.assertTrue(statuses)
        self.assertLessEqual(statuses[0][0], 1.0)

    def test_helper_argv_validation_and_lease_dir(self) -> None:
        """--serve-helper: 6 аргументов, lease только в переданном каталоге."""
        fn = server._run_serve_helper_cli  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        self.assertNotEqual(fn([]), 0)
        self.assertNotEqual(fn(["a", "notaport", "bin", "lease", "1", "x"]), 0)
        lease_dir = self.tmp / "leases-custom"
        script = Path(server.__file__).resolve()
        proc = subprocess.run(
            [
                sys.executable,
                "-I",
                str(script),
                "--serve-helper",
                "attemptX",
                "9",
                "bin",
                str(lease_dir),
                "1",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertNotEqual(proc.returncode, 0)

    def test_serve_health_and_fallback_table(self) -> None:
        """_ServeHealth sticky и таблица fallback_decision_table."""
        health = server._ServeHealth()  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        for _i in range(3):
            health.record_failure()
        self.assertTrue(health.is_degraded())
        health.record_success()
        self.assertFalse(health.is_degraded())
        rows: list[dict[str, object]] = list(server.FALLBACK_DECISION_TABLE)
        self.assertGreaterEqual(len(rows), 10)
        by_event: dict[str, dict[str, object]] = {
            str(r.get("event", "")): r for r in rows
        }
        silence_rows = [
            r
            for ev, r in by_event.items()
            if "first_token_timeout" in ev and "silence" in ev
        ]
        self.assertEqual(len(silence_rows), 1)
        self.assertEqual(silence_rows[0].get("action"), "serve_retry")
        self.assertEqual(silence_rows[0].get("UpstreamBreaker_failure_increment"), 1)
        auth_rows = [r for ev, r in by_event.items() if "HTTP401/403" in ev]
        self.assertEqual(len(auth_rows), 1)
        self.assertEqual(auth_rows[0].get("action"), "fail_closed")

    def test_helper_drains_large_stderr(self) -> None:
        """FakeServe пишет >64КиБ в stderr до SSE и не блокируется."""
        chunks, elapsed = self.bridge.post_stream_timed("обычный запрос")
        self.assertLess(elapsed, 15.0)
        self.assertTrue(_deltas(chunks, "reasoning_content"))

    def test_clean_room_fake_serve_via_monkeypatched_bin(self) -> None:
        """RW-002: OPENCODE_BIN подменён при пустом HOME, serve работает."""
        chunks, _elapsed = self.bridge.post_stream_timed("чистая комната")
        self.assertTrue(_deltas(chunks, "content"))

    def test_auto_fallback_to_run_and_sticky_degradation(self) -> None:
        """auto: 503 на создании сессии -> fallback на run; после 3 запросов serve деградирован."""
        saved_eligible = server.SERVE_TEST_ELIGIBLE
        server.SERVE_TEST_ELIGIBLE = True
        try:
            with (
                mock.patch.dict(
                    os.environ,
                    {
                        "OPENCODE_ZEN_BRIDGE_TRANSPORT": "auto",
                        "FAKE_SERVE_SESSION_STATUS": "503",
                    },
                    clear=False,
                ),
                mock.patch.object(
                    server,
                    "_SERVE_ALLOWLIST",
                    (*server._SERVE_ALLOWLIST, "FAKE_SERVE_SESSION_STATUS"),  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
                ),
                mock.patch.object(
                    server,
                    "_STANDALONE_ENV_ALLOWLIST",
                    (
                        *server._STANDALONE_ENV_ALLOWLIST,  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
                        "FAKE_SERVE_SESSION_STATUS",
                    ),
                ),
            ):
                for _i in range(3):
                    chunks, _elapsed = self.bridge.post_stream_timed("обычный запрос")
                    content = "".join(t for _at, t in _deltas(chunks, "content"))
                    self.assertIn("Поздний ответ", content)
                self.assertTrue(self.bridge.httpd.resilience.serve_health.is_degraded())
        finally:
            server.SERVE_TEST_ELIGIBLE = saved_eligible

    def test_foreign_listener_rejected_and_startup_reaper(self) -> None:
        """Чужой слушатель порта -> ServeUnavailable; reaper удаляет lease мёртвого родителя."""
        with mock.patch.object(server, "_lsof_listener_pid", return_value=999998):
            with self.assertRaises(server.ServeUnavailable) as ctx:
                _ = server._spawn_serve("att_foreign", server._serve_env(MODEL))  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        self.assertIn("foreign listener", str(ctx.exception))
        lease_dir = self.tmp / "reaper-leases"
        lease_dir.mkdir()
        dead = lease_dir / "lease-dead.json"
        alive = lease_dir / "lease-alive.json"
        _ = dead.write_text(
            json.dumps(
                {
                    "parent_pid": 999999,
                    "helper_pid": 0,
                    "pgid": 0,
                    "owner_uid": os.getuid(),
                }
            ),
            "utf-8",
        )
        _ = alive.write_text(
            json.dumps(
                {
                    "parent_pid": os.getpid(),
                    "helper_pid": 0,
                    "pgid": 0,
                    "owner_uid": os.getuid(),
                }
            ),
            "utf-8",
        )
        _ = server._startup_reaper(lease_dir)  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        self.assertFalse(dead.exists())
        self.assertTrue(alive.exists())

    def test_serve_400_fails_closed_without_health_increment(self) -> None:
        """400 на создании сессии: SSE error fail-closed без инкремента serve_health."""
        health = self.bridge.httpd.resilience.serve_health
        failures_before = health.failures
        with (
            mock.patch.dict(
                os.environ, {"FAKE_SERVE_SESSION_STATUS": "400"}, clear=False
            ),
            mock.patch.object(
                server,
                "_SERVE_ALLOWLIST",
                (*server._SERVE_ALLOWLIST, "FAKE_SERVE_SESSION_STATUS"),  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
            ),
            mock.patch.object(
                server,
                "_STANDALONE_ENV_ALLOWLIST",
                (*server._STANDALONE_ENV_ALLOWLIST, "FAKE_SERVE_SESSION_STATUS"),  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
            ),
        ):
            chunks, _elapsed = self.bridge.post_stream_timed("обычный запрос")
        joined = json.dumps(chunks, ensure_ascii=False)
        self.assertIn("serve security failure", joined)
        self.assertEqual(health.failures, failures_before)
        self.assertFalse(health.is_degraded())

    def _auto_mode(self) -> None:
        """auto + eligible: serve выбирается для скриптового FakeServe."""
        saved = server.SERVE_TEST_ELIGIBLE
        server.SERVE_TEST_ELIGIBLE = True
        self.addCleanup(setattr, server, "SERVE_TEST_ELIGIBLE", saved)
        # Окружение восстановит patch.dict из setUp: отдельный patch в cleanup вернул бы его устаревший снимок.
        os.environ["OPENCODE_ZEN_BRIDGE_TRANSPORT"] = "auto"

    def _patched_attempts(
        self, plan: list[Callable[[tuple[object, ...]], dict[str, object]]]
    ) -> tuple[list[tuple[object, ...]], mock._patch[mock.MagicMock]]:  # pyright: ignore[reportPrivateUsage] — причина: тип patch-объекта mock приватен в typeshed
        """Подмена `_serve_one_attempt` сценарием по очереди; возвращает журнал аргументов."""
        calls: list[tuple[object, ...]] = []
        queue_plan = list(plan)

        def fake(*args: object, **_kw: object) -> dict[str, object]:
            calls.append(args)
            return queue_plan.pop(0)(args)

        return calls, mock.patch.object(server, "_serve_one_attempt", side_effect=fake)

    def test_c7_rw002_execution_started_before_prompt_headers_sets_delivered_and_blocks_run_fallback(
        self,
    ) -> None:
        """RW-002: начало execution закрывает fallback даже без заголовков prompt."""
        self._auto_mode()
        for stream in (True, False):
            for ending in ("eof", "error"):
                with self.subTest(stream=stream, ending=ending):
                    fragment = """
            emit({"type":"session.execution.started","data":{"sessionID":sid}})
            if ENDING=="error":
                emit({"type":"session.execution.failed","data":{"sessionID":sid,"error":{"message":"overloaded","status":503}}})
            return
""".replace("ENDING", repr(ending))
                    body = FAKE_SERVE.replace(
                        '            if "__native_pause__" in prompt:',
                        fragment + '            if "__native_pause__" in prompt:',
                    )
                    body = body.replace(
                        '            state["prompt"] = prompt_text\n',
                        '            state["prompt"] = prompt_text\n            time.sleep(5)\n',
                    )
                    _ = self.fake.write_text(body)
                    results: list[Mapping[str, object]] = []
                    original = cast(
                        "Callable[..., Mapping[str, object]]",
                        getattr(server, "_serve_one_attempt"),
                    )

                    def attempt(
                        *args: object, **kwargs: object
                    ) -> Mapping[str, object]:
                        result = original(*args, **kwargs)
                        results.append(result)
                        return result

                    health = self.bridge.httpd.resilience.serve_health
                    health.record_success()
                    with (
                        mock.patch.object(
                            server, "_serve_one_attempt", side_effect=attempt
                        ),
                        mock.patch.object(
                            server,
                            "_spawn_with_stdin",
                            wraps=getattr(server, "_spawn_with_stdin"),
                        ) as spawn,
                        mock.patch.object(
                            server.Run,
                            "execute",
                            side_effect=AssertionError("unexpected run fallback"),
                        ) as run,
                        mock.patch.object(
                            health, "record_success", wraps=health.record_success
                        ) as success,
                        mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
                        mock.patch.object(server, "MAX_TOTAL_SPAWNS", 2),
                    ):
                        if stream:
                            chunks, _ = self.bridge.post_stream_timed("x")
                            self.assertIn("error", json.dumps(chunks))
                        else:
                            status, response = self.bridge.post_json("x")
                            self.assertEqual(status, 502, response)
                    self.assertGreaterEqual(len(results), 1)
                    self.assertLessEqual(len(results), 2)
                    self.assertTrue(
                        all(r["first_event_at"] is not None for r in results)
                    )
                    self.assertTrue(
                        all(r["delivered"] is True for r in results), results
                    )
                    spawn.assert_not_called()
                    run.assert_not_called()
                    success.assert_not_called()
                    self.bridge.httpd.resilience.breaker.record_success()

    def test_c7_fu001_native_tool_call_captures_step_ended_usage(self) -> None:
        """FU-001: usage закрытого native-шага попадает в финальный чанк вместе с tool_calls."""
        fragment = """
            emit({"type":"session.execution.started","data":{"sessionID":sid}})
            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"nc1","name":"bash","input":{"command":"pwd"}}})
            emit({"type":"session.text.delta","data":{"sessionID":sid,"assistantMessageID":"m2","delta":"ЛИШНИЙ ШАГ"}})
            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m2","id":"nc2","name":"bash","input":{"command":"wrong"}}})
            emit({"type":"session.step.ended","data":{"sessionID":"foreign","assistantMessageID":"m1","tokens":{"input":999}}})
            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":123,"output":45,"reasoning":67,"cache":{"read":10,"write":0}}}})
            return
"""
        _ = self.fake.write_text(
            FAKE_SERVE.replace(
                '            if "__native_pause__" in prompt:',
                fragment + '            if "__native_pause__" in prompt:',
            )
        )
        chunks, _ = self.bridge.post_stream_timed("x")
        self.assertEqual(_tool_names(chunks), ["bash"])
        self.assertNotIn(
            "ЛИШНИЙ ШАГ", "".join(t for _, t in _deltas(chunks, "content"))
        )
        usages = [_as_obj_dict(c["usage"]) for _, c in chunks if "usage" in c]
        self.assertTrue(usages, chunks)
        self.assertEqual(usages[-1]["prompt_tokens"], 123)
        self.assertEqual(usages[-1]["completion_tokens"], 45)
        self.assertEqual(
            _as_obj_dict(usages[-1]["prompt_tokens_details"])["cached_tokens"], 10
        )
        self.assertEqual(
            _as_obj_dict(usages[-1]["completion_tokens_details"])["reasoning_tokens"],
            67,
        )

    def test_slow_pause_streams_all_deltas_and_single_initial_status(self) -> None:
        """RW-008/RW-016: пауза SSE 1.4 с не рвёт поток; STATUS_INITIAL ровно один, чанки целы."""
        chunks, _elapsed = self.bridge.post_stream_timed("__slow__ жди")
        self.assertFalse(any("error" in chunk for _at, chunk in chunks), chunks)
        content = "".join(t for _at, t in _deltas(chunks, "content"))
        self.assertEqual(content, "Ответ\n")
        initial = [
            at
            for at, t in _deltas(chunks, "reasoning_content")
            if server.STATUS_INITIAL.strip() in t
        ]
        self.assertEqual(len(initial), 1, chunks)
        self.assertLessEqual(initial[0], 1.0)

    def test_prompt_http_4xx_fail_closed_without_run_fallback(self) -> None:
        """RW-003: 400/404/422 prompt в auto — fail_closed: без run и без инкремента serve_health."""
        self._auto_mode()
        health = self.bridge.httpd.resilience.serve_health
        for code in (400, 404, 422):
            with self.subTest(code=code):
                before = health.failures
                chunks, _elapsed = self.bridge.post_stream_timed(
                    f"__prompt_status_{code}__ запрос"
                )
                joined = json.dumps(chunks, ensure_ascii=False)
                self.assertIn("serve security failure", joined)
                self.assertNotIn("Поздний ответ", joined)
                self.assertEqual(health.failures, before)

    def test_timeout_and_client_gone_never_count_as_success(self) -> None:
        """RW-002: exit_reason timeout/client_gone — не успех ни в SSE, ни в JSON."""
        health = self.bridge.httpd.resilience.serve_health
        for reason in ("timeout", "client_gone"):
            for streaming in (True, False):
                with (
                    self.subTest(reason=reason, stream=streaming),
                    mock.patch.object(health, "record_success") as ok,
                    mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
                    mock.patch.object(
                        server,
                        "_serve_one_attempt",
                        side_effect=lambda *_a, **_k: _fake_result(  # pyright: ignore[reportUnknownLambdaType] — причина: подмена попытки возвращает заготовленный результат
                            exit_reason=reason, delivered=True
                        ),
                    ),
                ):
                    if streaming:
                        chunks, _elapsed = self.bridge.post_stream_timed("x")
                        finishes = [
                            _as_obj_dict(
                                cast("list[object]", c.get("choices") or [{}])[0]
                            ).get("finish_reason")
                            for _at, c in chunks
                            if c.get("choices")
                        ]
                        self.assertFalse(any(finishes), chunks)
                        self.assertEqual(
                            any("error" in c for _at, c in chunks), reason == "timeout"
                        )
                    elif reason == "timeout":
                        status, _body = self.bridge.post_json("x")
                        self.assertEqual(status, 502)
                    else:
                        with self.assertRaises(
                            (
                                TimeoutError,
                                http.client.RemoteDisconnected,
                                ConnectionError,
                            )
                        ):
                            _ = self.bridge.post_json("x", timeout=2.5)
                    ok.assert_not_called()

    def test_retry_separator_once_and_delivery_barrier_is_monotonic(self) -> None:
        """RW-009/RW-012: один разделитель на повтор; после reasoning нет тихого fallback на run."""
        self._auto_mode()

        def first(args: tuple[object, ...]) -> dict[str, object]:
            _callback(args, 4)("мысль\n")
            return _fake_result(
                exit_reason="stall_timeout", delivered=True, reasonings=["мысль\n"]
            )

        def second(_args: tuple[object, ...]) -> dict[str, object]:
            return _fake_result(exit_reason="first_event_timeout", delivered=False)

        def third(args: tuple[object, ...]) -> dict[str, object]:
            _callback(args, 5)("Готово")
            return _fake_result(texts=["Готово"], terminal="succeeded")

        calls, patcher = self._patched_attempts([first, second, third])
        with patcher, mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0):
            chunks, _elapsed = self.bridge.post_stream_timed("x")
        self.assertEqual(len(calls), 3)
        joined = "".join(t for _at, t in _deltas(chunks, "content"))
        self.assertEqual(joined, "Готово")
        separators = [
            t
            for _at, t in _deltas(chunks, "reasoning_content")
            if "Повтор попытки" in t
        ]
        self.assertEqual(len(separators), 2, chunks)

    def test_json_tool_calls_are_deduplicated(self) -> None:
        """RW-013: одинаковый (name, arguments) из native и из текста даёт один tool_call."""
        call_text = '<tool_invoke>{"name": "bash", "arguments": {"command": "echo hi"}}</tool_invoke>'
        native: dict[str, object] = {
            "part": {
                "tool": "bash",
                "state": {"input": {"command": "echo hi"}, "status": "completed"},
            }
        }

        def attempt(args: tuple[object, ...]) -> dict[str, object]:
            _callback(args, 5)(call_text)
            on_tool = cast("Callable[[dict[str, object]], None]", args[6])
            on_tool(native)
            on_tool(native)
            return _fake_result(terminal="succeeded")

        _calls, patcher = self._patched_attempts([attempt])
        with patcher:
            status, body = self.bridge.post_json("x")
        self.assertEqual(status, 200)
        message = _as_obj_dict(
            _as_obj_dict(cast("list[object]", body["choices"])[0]).get("message")
        )
        self.assertEqual(len(cast("list[object]", message["tool_calls"])), 1)

    def test_json_run_fallback_respects_total_spawn_cap(self) -> None:
        """RW-010: исчерпанный потолок спавнов serve не даёт четвёртый спавн run в JSON."""

        def fake_serve(*args: object) -> bool:
            attempts = cast("server._RequestAttempts", args[9])  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
            for _i in range(server.MAX_TOTAL_SPAWNS):
                attempts.note_spawn()
            return False

        with (
            mock.patch.object(
                server.Handler,
                "_serve_json_serve",
                autospec=True,
                side_effect=fake_serve,
            ),
            mock.patch.object(server, "Run") as run_cls,
        ):
            status, _body = self.bridge.post_json("x")
        self.assertEqual(status, 502)
        run_cls.assert_not_called()

    def test_proxy_pool_advances_once_per_serve_attempt(self) -> None:
        """RW-019: запрос с одной попыткой serve сдвигает пул прокси один раз."""
        with (
            mock.patch.object(
                server, "_next_standalone_proxy", return_value=None
            ) as rotate,
            mock.patch.object(
                server, "_spawn_serve", side_effect=server.ServeUnavailable("stop")
            ),
        ):
            _chunks, _elapsed = self.bridge.post_stream_timed("x")
        self.assertEqual(rotate.call_count, 1)

    def test_tool_choice_preserved_in_step_recovery_prompt(self) -> None:
        """RW-007: tool_choice попадает в промпт step-interruption recovery serve."""
        for choice, phrase in (
            ("required", "MUST call at least one tool"),
            (
                {"type": "function", "function": {"name": "bash"}},
                'MUST call the tool "bash"',
            ),
        ):
            with self.subTest(choice=choice):

                def preamble(args: tuple[object, ...]) -> dict[str, object]:
                    _callback(args, 5)("Сейчас проверю.")
                    return _fake_result(texts=["Сейчас проверю."], terminal="succeeded")

                def done(args: tuple[object, ...]) -> dict[str, object]:
                    call = '<tool_invoke>{"name": "bash", "arguments": {"command": "ls"}}</tool_invoke>'
                    _callback(args, 5)(call)
                    return _fake_result(texts=[call], terminal="succeeded")

                calls, patcher = self._patched_attempts([preamble, done])
                with patcher, mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0):
                    _chunks, _elapsed = self.bridge.post_stream_timed(
                        "x", tool_choice=choice
                    )
                self.assertEqual(len(calls), 2)
                self.assertIn(phrase, str(calls[1][1]))

    def test_fu003_usage_once_across_distinct_retry_branches(self) -> None:
        """FU-003: timeout, prompt-status и успешная попытка учитываются по одному разу."""

        def first(args: tuple[object, ...]) -> dict[str, object]:
            _callback(args, 4)("мысль\n")
            return _fake_result(
                delivered=True,
                reasonings=["мысль\n"],
                exit_reason="stall_timeout",
                usage={"output": 3},
            )

        def second(_args: tuple[object, ...]) -> dict[str, object]:
            return _fake_result(delivered=True, prompt_status=429, usage={"output": 5})

        def third(args: tuple[object, ...]) -> dict[str, object]:
            _callback(args, 5)("Ответ.")
            return _fake_result(
                texts=["Ответ."], terminal="succeeded", usage={"output": 7}
            )

        calls, patcher = self._patched_attempts([first, second, third])
        with (
            patcher,
            mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
            mock.patch.object(server, "STEP_RECOVERY_ENABLED", False),
        ):
            chunks, _ = self.bridge.post_stream_timed("x")
        self.assertEqual(len(calls), 3)
        usages = [
            _as_obj_dict(chunk["usage"]) for _, chunk in chunks if "usage" in chunk
        ]
        self.assertTrue(usages, chunks)
        self.assertEqual(usages[-1].get("completion_tokens"), 15)

    def test_fu010_thinking_off_omits_retry_separator(self) -> None:
        """FU-010: синтетический разделитель отключён вместе с thinking."""

        def first(args: tuple[object, ...]) -> dict[str, object]:
            _callback(args, 5)("начало ")
            return _fake_result(
                delivered=True, texts=["начало "], exit_reason="stall_timeout"
            )

        def second(args: tuple[object, ...]) -> dict[str, object]:
            _callback(args, 5)("конец")
            return _fake_result(texts=["конец"], terminal="succeeded")

        _calls, patcher = self._patched_attempts([first, second])
        with (
            patcher,
            mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
            mock.patch.object(server, "STEP_RECOVERY_ENABLED", False),
        ):
            chunks, _ = self.bridge.post_stream_timed("x", effort="off")
        self.assertNotIn("Повтор попытки", json.dumps(chunks, ensure_ascii=False))

    def test_rw001_delivery_survives_unavailable_or_limiter(self) -> None:
        """RW-001: частичный ответ запрещает run при следующем отказе serve или лимитера."""
        self._auto_mode()
        unavailable = server.ServeUnavailable
        for stream in (True, False):
            for limited in (False, True):
                with self.subTest(stream=stream, limited=limited):

                    def first(args: tuple[object, ...]) -> dict[str, object]:
                        _callback(args, 4)("частичная мысль\n")
                        return _fake_result(
                            exit_reason="stall_timeout",
                            delivered=True,
                            reasonings=["частичная мысль\n"],
                        )

                    def second(_args: tuple[object, ...]) -> dict[str, object]:
                        raise unavailable("нет serve")

                    calls, patcher = self._patched_attempts([first, second])
                    health = self.bridge.httpd.resilience.serve_health
                    limiter = self.bridge.httpd.resilience.spawn_limiter
                    with (
                        patcher,
                        mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
                        mock.patch.object(health, "record_success") as success,
                        mock.patch.object(server.Run, "execute") as legacy,
                        mock.patch.object(server, "_spawn_with_stdin") as spawn,
                        mock.patch.object(
                            limiter,
                            "acquire",
                            side_effect=[True, False] if limited else [True, True],
                        ),
                    ):
                        if stream:
                            chunks, _ = self.bridge.post_stream_timed("x")
                            output = json.dumps(chunks, ensure_ascii=False)
                            self.assertLessEqual(output.count("Повтор попытки"), 1)
                            self.assertIn("error", output)
                        else:
                            status, body = self.bridge.post_json("x", with_tools=False)
                            self.assertEqual(status, 502, body)
                        legacy.assert_not_called()
                        spawn.assert_not_called()
                        success.assert_not_called()
                    self.assertEqual(len(calls), 1 if limited else 2)

    def test_c5_rw001_prompt_headers_then_body_error_or_429_blocks_run_fallback(
        self,
    ) -> None:
        """Cycle 5 RW-001: заголовки prompt запрещают run и успешный учёт."""
        self._auto_mode()
        for marker in (
            "__prompt_reset__",
            "__prompt_status_429__",
            "__prompt_status_503__",
        ):
            for stream in (True, False):
                with self.subTest(marker=marker, stream=stream):
                    self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: каждый сценарий получает независимые бюджеты
                    with (
                        mock.patch.object(server.Run, "execute") as legacy,
                        mock.patch.object(server, "_spawn_with_stdin") as spawn,
                        mock.patch.object(
                            self.bridge.httpd.resilience.serve_health, "record_success"
                        ) as success,
                        mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
                        mock.patch.object(server, "MAX_TOTAL_SPAWNS", 2),
                        mock.patch.object(
                            self.bridge.httpd.resilience.retry_budget,
                            "try_acquire_retry",
                            wraps=self.bridge.httpd.resilience.retry_budget.try_acquire_retry,
                        ) as retry_budget,
                    ):
                        if stream:
                            chunks, _ = self.bridge.post_stream_timed(marker)
                            self.assertIn("error", json.dumps(chunks))
                        else:
                            status, body = self.bridge.post_json(
                                marker, with_tools=False
                            )
                            self.assertEqual(status, 502, body)
                        legacy.assert_not_called()
                        spawn.assert_not_called()
                        success.assert_not_called()
                        self.assertEqual(retry_budget.call_count, 1)

    def test_c5_fu003_json_transient_recovery_normalizes_and_deduplicates(self) -> None:
        """Cycle 5 FU-003: частичный tool-блок не попадает в content и не дублирует преамбулу."""
        preamble = "Проверяю файлы."

        def first(args: tuple[object, ...]) -> dict[str, object]:
            text = preamble + '<tool_call>{"name":"bash","arguments":'
            _callback(args, 5)(text)
            return _fake_result(
                texts=[text],
                delivered=True,
                error={"message": "overloaded"},
                transient_error=True,
                terminal="failed",
            )

        def second(args: tuple[object, ...]) -> dict[str, object]:
            text = preamble + " Ответ"
            _callback(args, 5)(text)
            return _fake_result(texts=[text], terminal="succeeded")

        _calls, patcher = self._patched_attempts([first, second])
        with patcher, mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0):
            status, body = self.bridge.post_json("проверь файлы")
        self.assertEqual(status, 200, body)
        output = json.dumps(body, ensure_ascii=False)
        self.assertEqual(output.count(preamble), 1, body)
        self.assertNotIn("<tool_call>", output)

    def test_rw007_split_interrupted_marker_at_every_boundary(self) -> None:
        """RW-007: маркер удаляется при любом разрезе, включая прежнюю границу буфера."""
        marker = "I was interrupted right before making tool calls."
        for split in (1, 19, len(marker) - 1):
            with self.subTest(split=split):

                def first(args: tuple[object, ...]) -> dict[str, object]:
                    chunks = [
                        "начало " + marker[:split],
                        marker[split:] + " конец" + "x" * 100,
                    ]
                    for chunk in chunks:
                        _callback(args, 5)(chunk)
                    return _fake_result(texts=chunks, terminal="succeeded")

                _calls, patcher = self._patched_attempts([first])
                with patcher, mock.patch.object(server, "STEP_RECOVERY_ENABLED", False):
                    chunks, _ = self.bridge.post_stream_timed("x")
                text = "".join(t for _, t in _deltas(chunks, "content"))
                self.assertEqual(text, "начало  конец" + "x" * 100)

    def test_rw008_provider_secrets_hidden_in_sse_json_and_log(self) -> None:
        """RW-008: ошибка провайдера не выдаёт секреты через SSE, JSON и лог."""
        secret = "sk-" + "a" * 32
        message = (
            secret
            + " Bearer hidden-token OPENCODE_SERVER_PASSWORD=hidden-pass http://u:proxy-pass@localhost:1080"
        )
        for stream in (True, False):

            def failure(_args: tuple[object, ...]) -> dict[str, object]:
                return _fake_result(error={"message": message}, terminal="failed")

            _calls, patcher = self._patched_attempts([failure])
            with patcher:
                if stream:
                    chunks, _ = self.bridge.post_stream_timed("x")
                    output = json.dumps(chunks)
                else:
                    _status, body = self.bridge.post_json("x", with_tools=False)
                    output = json.dumps(body)
            output += server.LOG_PATH.read_text()
            for sentinel in (secret, "hidden-token", "hidden-pass", "proxy-pass"):
                self.assertNotIn(sentinel, output)

    def test_rw006_invalid_utf8_falls_back_and_recovers(self) -> None:
        """RW-006: повреждённый UTF-8 безопасен, восстановление JSON включает serve."""
        self._auto_mode()
        _ = self.cfg.write_bytes(b"\xff\xfe")
        self.assertEqual(server._select_transport(), "run")  # pyright: ignore[reportPrivateUsage] — причина: проверяется выбор транспорта после повреждения файла
        _ = self.cfg.write_text('{"REALTIME_SERVE_ENABLED": true}', encoding="utf-8")
        self.assertEqual(server._select_transport(), "serve")  # pyright: ignore[reportPrivateUsage] — причина: проверяется восстановление транспорта без рестарта

    def test_rw003_mkdtemp_failure_is_serve_unavailable(self) -> None:
        """RW-003: ENOSPC при выделении каталога не оставляет портов и не уходит как client_gone."""
        ports = server._ACTIVE_SERVE_PORTS.copy()  # pyright: ignore[reportPrivateUsage] — причина: сверяются ресурсы после отказа до запуска
        attempt = server._serve_one_attempt  # pyright: ignore[reportPrivateUsage] — причина: оракул инъецирует отказ до запуска попытки
        with mock.patch.object(
            tempfile, "mkdtemp", side_effect=OSError(28, "нет места")
        ):
            with self.assertRaises(server.ServeUnavailable):
                _ = attempt(
                    MODEL,
                    "x",
                    "high",
                    self.tmp,
                    lambda _: None,
                    lambda _: None,
                    lambda _: None,
                    time.monotonic(),
                )
        self.assertEqual(server._ACTIVE_SERVE_PORTS, ports)  # pyright: ignore[reportPrivateUsage] — причина: инвариант отсутствия занятых портов после отказа

    def test_fu011_cancelled_never_counts_as_success(self) -> None:
        """FU-011: отменённая form.created не считается успехом в обоих протоколах."""
        for stream in (True, False):

            def cancelled(_args: tuple[object, ...]) -> dict[str, object]:
                return _fake_result(terminal="cancelled")

            _calls, patcher = self._patched_attempts([cancelled])
            with (
                patcher,
                mock.patch.object(
                    self.bridge.httpd.resilience.serve_health, "record_success"
                ) as success,
            ):
                if stream:
                    chunks, _ = self.bridge.post_stream_timed("x")
                    self.assertIn("cancelled", json.dumps(chunks))
                else:
                    status, body = self.bridge.post_json("x", with_tools=False)
                    self.assertEqual(status, 502, body)
                success.assert_not_called()

    def test_c6_rw001_headers_at_blocks_run_fallback_on_sse_error_and_timeout(
        self,
    ) -> None:
        """RW-001: заголовки prompt удерживают обе формы ответа на serve до ошибки."""
        self._auto_mode()
        fake = FAKE_SERVE.replace(
            'if "__native_pause__" in prompt:',
            'if "__c6_fail__" in prompt:\n                time.sleep(0.08)\n                emit({"type":"session.execution.failed","data":{"sessionID":sid,"error":{"status":429,"message":"rate limit"}}}); return\n            if "__native_pause__" in prompt:',
        )
        _ = self.fake.write_text(fake)
        original = server._serve_one_attempt  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта
        for marker in ("__c6_fail__", "__never_event__"):
            for stream in (True, False):
                with self.subTest(marker=marker, stream=stream):
                    self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта
                    results: list[dict[str, object]] = []

                    def capture(*args: object, **kwargs: object) -> object:
                        result = cast(
                            "dict[str, object]",
                            cast("Callable[..., object]", original)(*args, **kwargs),
                        )
                        results.append(result)
                        return result

                    with (
                        mock.patch.object(
                            server, "_serve_one_attempt", side_effect=capture
                        ),
                        mock.patch.object(server.Run, "execute") as run,
                        mock.patch.object(server, "_spawn_with_stdin") as spawn,
                        mock.patch.object(
                            self.bridge.httpd.resilience.serve_health, "record_success"
                        ) as success,
                        mock.patch.object(server, "MAX_TOTAL_SPAWNS", 1),
                        mock.patch.object(server, "TIMEOUT_S", 0.9),
                        mock.patch.object(server, "FIRST_EVENT_TIMEOUT_S", 20.0),
                    ):
                        if stream:
                            chunks, _ = self.bridge.post_stream_timed(marker)
                            self.assertIn("error", json.dumps(chunks))
                        else:
                            status, body = self.bridge.post_json(
                                marker, with_tools=False
                            )
                            self.assertEqual(status, 502, body)
                        run.assert_not_called()
                        spawn.assert_not_called()
                        success.assert_not_called()
                    self.assertEqual(len(results), 1)
                    self.assertIs(results[0]["delivered"], True)

    def test_c6_rw005_startup_abort_never_falls_back_or_changes_serve_health(
        self,
    ) -> None:
        """RW-005: исключения отмены старта не расходуют здоровье serve и не запускают run."""
        self._auto_mode()
        for error in (
            server.ServeClientDisconnect,
            server.ServeStartupDeadlineExceeded,
        ):
            for stream in (True, False):
                self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: каждый сценарий имеет свой бюджет
                with (
                    self.subTest(error=error.__name__, stream=stream),
                    mock.patch.object(
                        server, "_spawn_serve", side_effect=error("stop")
                    ),
                    mock.patch.object(server, "_spawn_with_stdin") as spawn,
                    mock.patch.object(server.Run, "execute") as run,
                    mock.patch.object(
                        self.bridge.httpd.resilience.serve_health, "record_failure"
                    ) as failure,
                    mock.patch.object(
                        self.bridge.httpd.resilience.serve_health, "record_success"
                    ) as success,
                    mock.patch.object(server, "MAX_TOTAL_SPAWNS", 1),
                ):
                    try:
                        if stream:
                            chunks, _ = self.bridge.post_stream_timed("x", timeout=2.0)
                            if error is server.ServeStartupDeadlineExceeded:
                                self.assertIn("error", json.dumps(chunks))
                        else:
                            status, body = self.bridge.post_json("x", timeout=2.0)
                            self.assertEqual(status, 502, body)
                    except (http.client.RemoteDisconnected, TimeoutError):
                        self.assertIs(error, server.ServeClientDisconnect)
                    run.assert_not_called()
                    spawn.assert_not_called()
                    failure.assert_not_called()
                    success.assert_not_called()

    def _c6_scenario(self, scenario: str, counter: Path) -> None:
        """Один сценарий с общим счётчиком попыток для настоящих serve и run."""
        fragment = r"""
            counter=Path(COUNTER)
            n=int(counter.read_text()) if counter.exists() else 0
            counter.write_text(str(n+1))
            scenario=SCENARIO
            if n==0 or scenario=="budget":
                if scenario=="unmapped":
                    emit({"type":"session.text.delta","data":{"sessionID":sid,"delta":"Проверяю файлы."}})
                if scenario in ("text","broken","budget","transient"):
                    text=("Проверяю файлы..." if scenario=="text" else "Проверяю файлы.") + ('<tool_call>{"name":"bash","arguments":' if scenario in ("broken","budget") else "")
                    emit({"type":"session.text.delta","data":{"sessionID":sid,"delta":text}})
                elif scenario=="reasoning":
                    emit({"type":"session.reasoning.delta","data":{"sessionID":sid,"delta":"I need to call bash next."}})
                elif scenario=="native":
                    emit({"type":"session.tool.called","data":{"sessionID":sid,"id":"nc1","name":"bash","input":{"command":"pwd"}}})
                elif scenario=="unmapped":
                    emit({"type":"session.tool.called","data":{"sessionID":sid,"id":"nc1","name":"todoread","input":{}}})
                if scenario in ("native","unmapped"):
                    emit({"type":"session.step.ended","data":{"sessionID":sid,"tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0}}}})
                if scenario=="native": time.sleep(2); return
                if scenario=="transient":
                    emit({"type":"session.execution.failed","data":{"sessionID":sid,"error":{"message":"overloaded","status":503}}}); return
            else:
                emit({"type":"session.text.delta","data":{"sessionID":sid,"delta":("Проверяю файлы... Ответ" if scenario=="text" else "Проверяю файлы. Ответ")}})
                emit({"type":"session.step.ended","data":{"sessionID":sid,"tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0}}}})
            emit({"type":"session.execution.succeeded","data":{"sessionID":sid}}); return
""".replace("COUNTER", repr(str(counter))).replace("SCENARIO", repr(scenario))
        body = FAKE_SERVE.replace(
            '            if "__native_pause__" in prompt:',
            fragment + '            if "__native_pause__" in prompt:',
        )
        _ = self.fake.write_text(body)

    def test_c6_rw004_ac016_serve_step_interruption_matrix(self) -> None:
        """AC-016: пять ветвей прерывания на настоящем serve для SSE и JSON."""
        for scenario in ("text", "reasoning", "broken", "native", "budget"):
            for stream in (True, False):
                with self.subTest(scenario=scenario, stream=stream):
                    counter = self.tmp / (scenario + str(stream))
                    self._c6_scenario(scenario, counter)
                    self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта
                    with (
                        mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
                        mock.patch.object(server, "MAX_TOTAL_SPAWNS", 2),
                    ):
                        text, finish = self._c6_response(stream)
                    self.assertEqual(
                        counter.read_text(), "1" if scenario == "native" else "2"
                    )
                    self.assertLessEqual(int(counter.read_text()), 2)
                    self.assertNotIn("<tool_call>", text)
                    self.assertLessEqual(text.count("Проверяю файлы."), 1, text)
                    if scenario == "native":
                        self.assertEqual(finish, "tool_calls")
                    elif scenario != "budget":
                        self.assertEqual(finish, "stop")
                        self.assertIn("Ответ", text)

    def _c6_response(self, stream: bool) -> tuple[str, str]:
        """Вернуть собранный текст и finish_reason обеих форм ответа."""
        if stream:
            chunks, _ = self.bridge.post_stream_timed("проверь файлы")
            text = "".join(t for _, t in _deltas(chunks, "content"))
            finish = ""
            for _, chunk in chunks:
                choices = cast("list[object]", chunk.get("choices") or [])
                if choices:
                    value = _as_obj_dict(choices[0]).get("finish_reason")
                    if isinstance(value, str):
                        finish = value
            return text, finish
        status, body = self.bridge.post_json("проверь файлы")
        self.assertEqual(status, 200, body)
        choice = _as_obj_dict(cast("list[object]", body["choices"])[0])
        return str(_as_obj_dict(choice.get("message")).get("content") or ""), str(
            choice.get("finish_reason")
        )

    def test_c6_rw004_ac017_unmapped_recovery_serve_vs_run_equivalence(self) -> None:
        """AC-017: unmapped и transient повтор дают равный итог через serve/run, SSE/JSON."""
        for scenario in ("unmapped", "transient"):
            outputs: list[tuple[str, str]] = []
            for transport in ("serve", "run"):
                for stream in (True, False):
                    with self.subTest(
                        scenario=scenario, transport=transport, stream=stream
                    ):
                        counter = self.tmp / (scenario + transport + str(stream))
                        self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта
                        self._c6_scenario(scenario, counter)
                        if transport == "run":
                            body = r"""#!/usr/bin/env python3
import json,sys
from pathlib import Path
p=Path(COUNTER)
n=int(p.read_text()) if p.exists() else 0
p.write_text(str(n+1)); sys.stdin.read()
def ev(o): print(json.dumps(o),flush=True)
if n==0:
    if SCENARIO=="unmapped":
        ev({"type":"text","part":{"text":"Проверяю файлы."}})
        ev({"type":"tool_use","part":{"tool":"todoread","state":{"status":"completed","input":{}}}})
    else:
        ev({"type":"text","part":{"text":"Проверяю файлы."}})
        ev({"type":"error","error":{"name":"APIError","data":{"statusCode":503,"message":"overloaded"}}})
else: ev({"type":"text","part":{"text":"Проверяю файлы. Ответ"}})
ev({"type":"step_finish","part":{"tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0,"write":0}}}})
""".replace("COUNTER", repr(str(counter))).replace("SCENARIO", repr(scenario))
                            _ = self.fake.write_text(body)
                        with (
                            mock.patch.dict(
                                os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": transport}
                            ),
                            mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
                            mock.patch.object(server, "MAX_TOTAL_SPAWNS", 2),
                        ):
                            output = self._c6_response(stream)
                        outputs.append(output)
                        self.assertEqual(counter.read_text(), "2")
                        self.assertEqual(output, ("Проверяю файлы. Ответ", "stop"))
            self.assertEqual(len(set(outputs)), 1)


class _FakeSock:
    """Фейковый клиентский сокет для downstream-тестов RW-005."""

    def __init__(self) -> None:
        self.timeouts: list[float | None] = []
        self.shutdown_calls: list[int] = []
        self.closed: bool = False

    def settimeout(self, value: float | None) -> None:
        """Запомнить установленный таймаут."""
        self.timeouts.append(value)

    def shutdown(self, how: int) -> None:
        """Запомнить shutdown."""
        self.shutdown_calls.append(how)

    def close(self) -> None:
        """Запомнить закрытие."""
        self.closed = True


class _FailingWfile:
    """Внутренний wfile, чья запись падает по таймауту сокета."""

    def write(self, _data: bytes) -> int:
        """Симуляция зависшей записи клиенту."""
        raise TimeoutError("timed out")

    def flush(self) -> None:
        """Симуляция зависшего сброса буфера клиенту."""
        raise TimeoutError("timed out")


class TestReworkUnits(unittest.TestCase):
    @staticmethod
    def _c12_ignore(_payload: dict[str, object]) -> None:
        """Типизированный пустой callback для оракулов дренажа."""
        return None

    def test_c13_rw003_empty_queue_and_release_disconnect(self) -> None:
        """Пустая очередь и отключение при release не пропускают быстрый выход."""
        drain = cast("Callable[..., bool]", getattr(server, "_drain_serve_step_usage"))
        make_state = cast("Callable[[], object]", getattr(server, "_ServeToolState"))
        for during_release in (False, True):
            with self.subTest(during_release=during_release):
                events: queue.Queue[dict[str, object] | None] = queue.Queue()
                gone = threading.Event()
                released: list[dict[str, object]] = []
                if during_release:
                    events.put(
                        {"type": "session.step.ended", "data": {"sessionID": "s"}}
                    )
                timer = threading.Timer(0.10, gone.set)

                def release(event: dict[str, object]) -> None:
                    released.append(event)
                    gone.set()

                timer.start()
                started = time.monotonic()
                try:
                    with self.assertRaises(server.ServeClientDisconnect):
                        _ = drain(
                            events,
                            "s",
                            None,
                            started + 2.0,
                            {},
                            make_state(),
                            _fake_result(),
                            self._c12_ignore,
                            release,
                            is_client_gone=gone.is_set,
                        )
                    self.assertLess(time.monotonic() - started, 0.5)
                    self.assertEqual(len(released), int(during_release))
                finally:
                    timer.cancel()
                    timer.join()

    def test_c13_rw003_disconnect_before_pending_publication(self) -> None:
        """Отключение после подтверждения шага запрещает публикацию pending."""
        finish = cast("Callable[..., bool]", getattr(server, "_finish_serve_tool_step"))
        make_state = cast("Callable[[], object]", getattr(server, "_ServeToolState"))
        events: queue.Queue[dict[str, object] | None] = queue.Queue()
        published: list[dict[str, object]] = []
        with mock.patch.object(server, "_drain_serve_step_usage", return_value=True):
            with self.assertRaises(server.ServeClientDisconnect):
                _ = finish(
                    events,
                    "s",
                    None,
                    time.monotonic() + 1.0,
                    make_state(),
                    _fake_result(),
                    published.append,
                    self._c12_ignore,
                    pending_calls=[{"id": "first"}],
                    is_client_gone=lambda: True,
                )
        self.assertFalse(published)

    def test_c12_rw002_run_retry_preserves_partial_output_and_usage(self) -> None:
        """Run.execute сохраняет прошлые попытки и не публикует их tool calls."""
        for state in ("stall_timeout", "provider_error"):
            for tools in (None, [{"type": "function", "function": {"name": "bash"}}]):
                with self.subTest(state=state, tools=bool(tools)):
                    runner = server.Run(MODEL, "x", "high", Path("."), tools=tools)
                    first_text = (
                        "кусок-1 I was interrupted right before making tool calls."
                    )
                    first_text += "[opencode-zen-bridge: шаг модели оборвался]"
                    if tools:
                        first_text += '<tool_call>{"name":"bash","arguments":'
                    first = {
                        "state": state,
                        "rc": 1,
                        "err": "database is locked",
                        "provider_status": None,
                        "had_output": False,
                        "reasoning": "мысль-run-1",
                        "text": first_text,
                        "chunks": [first_text],
                        "usage": {
                            "input": 10,
                            "output": 5,
                            "cached": 2,
                            "reasoning": 3,
                        },
                        "native_calls": [{"bad": True}],
                    }
                    second = {
                        "state": "ok",
                        "rc": 0,
                        "text": "кусок-1 продолжение",
                        "chunks": ["кусок-1 продолжение"],
                        "reasoning": "мысль-run-2",
                        "usage": {
                            "input": 12,
                            "output": 8,
                            "cached": 1,
                            "reasoning": 4,
                        },
                        "native_calls": [],
                    }
                    with (
                        mock.patch.object(
                            runner, "_execute_once", side_effect=[first, second]
                        ),
                        mock.patch.object(runner, "close"),
                        mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
                    ):
                        out = cast("dict[str, object]", runner.execute())
                    self.assertEqual(out["reasoning"], "мысль-run-1мысль-run-2")
                    self.assertEqual(out["text"], "кусок-1 продолжение")
                    self.assertEqual(
                        "".join(cast("list[str]", out["chunks"])), out["text"]
                    )
                    self.assertEqual(
                        out["usage"],
                        {"input": 22, "output": 13, "cached": 3, "reasoning": 7},
                    )
                    self.assertEqual(out["native_calls"], [])

    def test_c12_rw003_drain_activity_extends_window_but_not_hard_deadline(
        self,
    ) -> None:
        """Живые события продлевают окно, тишина и общий дедлайн его ограничивают."""
        finish = cast("Callable[..., bool]", getattr(server, "_finish_serve_tool_step"))
        make_state = cast("Callable[[], object]", getattr(server, "_ServeToolState"))
        for scenario in ("active", "silent", "hard", "foreign"):
            with self.subTest(scenario=scenario):
                events: queue.Queue[dict[str, object] | None] = queue.Queue()
                pending: list[dict[str, object]] = [{"id": "first"}]
                published: list[dict[str, object]] = []
                ended = threading.Event()
                stop = threading.Event()
                result = _fake_result()
                result["usage"] = {}
                started = time.monotonic()

                def feed() -> None:
                    if scenario == "silent":
                        return
                    for i in range(5):
                        if stop.wait(0.08):
                            return
                        event_type = (
                            "session.tool.called" if i == 0 else "session.text.delta"
                        )
                        data: dict[str, object] = {
                            "sessionID": "other" if scenario == "foreign" else "s",
                            "assistantMessageID": "m",
                            "id": "second",
                            "name": "bash",
                            "input": {"command": "pwd"},
                            "delta": "хвост",
                        }
                        events.put({"type": event_type, "data": data})
                    ended.set()
                    events.put(
                        {
                            "type": "session.step.ended",
                            "data": {
                                "sessionID": "s",
                                "assistantMessageID": "m",
                                "tokens": {
                                    "input": 1,
                                    "output": 1,
                                    "reasoning": 0,
                                    "cache": {"read": 0, "write": 0},
                                },
                            },
                        }
                    )

                def publish(call: dict[str, object]) -> None:
                    self.assertTrue(ended.is_set())
                    published.append(call)

                worker = threading.Thread(target=feed)
                worker.start()
                try:
                    with mock.patch.object(server, "_STEP_DRAIN_WINDOW_S", 0.15):
                        kwargs: dict[str, object] = {
                            "pending_calls": pending,
                            "attempt_deadline": started
                            + (0.25 if scenario == "hard" else 2.0),
                        }
                        if scenario == "active":
                            self.assertTrue(
                                finish(
                                    events,
                                    "s",
                                    "m",
                                    started + 0.15,
                                    make_state(),
                                    result,
                                    publish,
                                    self._c12_ignore,
                                    **kwargs,
                                )
                            )
                            self.assertEqual(len(published), 2)
                            self.assertGreater(time.monotonic() - started, 0.3)
                        else:
                            with self.assertRaisesRegex(
                                server.ServeProtocolError,
                                "incomplete tool step without step.ended",
                            ):
                                _ = finish(
                                    events,
                                    "s",
                                    "m",
                                    started + 0.15,
                                    make_state(),
                                    result,
                                    publish,
                                    self._c12_ignore,
                                    **kwargs,
                                )
                            self.assertFalse(published)
                            self.assertLess(time.monotonic() - started, 0.4)
                finally:
                    stop.set()
                    worker.join(timeout=2)

    def test_c12_rw001_drain_reject_preserves_neutral_exceptions(self) -> None:
        """Disconnect/deadline нейтральны; отказ reject прерывает с SecurityError."""
        drain = cast("Callable[..., bool]", getattr(server, "_drain_serve_step_usage"))
        make_state = cast("Callable[[], object]", getattr(server, "_ServeToolState"))
        for error in (
            server.ServeClientDisconnect,
            server.ServeStartupDeadlineExceeded,
            socket.timeout,
            ConnectionResetError,
            http.client.HTTPException,
            server.ServeUnavailable,
            None,
        ):
            with self.subTest(error=error):
                events: queue.Queue[dict[str, object] | None] = queue.Queue()
                events.put(
                    {"type": "permission.asked", "data": {"id": "p", "sessionID": "s"}}
                )
                paths: list[str] = []

                def control(
                    _method: str, path: str, _body: object
                ) -> tuple[int, dict[str, object]]:
                    paths.append(path)
                    if path.endswith("/reply") and error is not None:
                        raise error("reject failed")
                    return 503, {}

                expected = (
                    error
                    if error
                    in (
                        server.ServeClientDisconnect,
                        server.ServeStartupDeadlineExceeded,
                    )
                    else server.ServeSecurityError
                )
                with self.assertRaises(expected):
                    _ = drain(
                        events,
                        "s",
                        None,
                        time.monotonic() + 1,
                        {},
                        make_state(),
                        _fake_result(),
                        self._c12_ignore,
                        self._c12_ignore,
                        ctrl_http=control,
                    )
                self.assertEqual(
                    any(p.endswith("/interrupt") for p in paths),
                    expected is server.ServeSecurityError,
                )

    @staticmethod
    def _permission_event(request_id: str, session_id: str = "s") -> dict[str, object]:
        """Событие `permission.asked` для оракулов каскадного reject."""
        return {
            "type": "permission.asked",
            "data": {"id": request_id, "sessionID": session_id},
        }

    @staticmethod
    def _step_ended_event() -> dict[str, object]:
        """Подтверждение конца шага для дренажа."""
        return {
            "type": "session.step.ended",
            "data": {
                "sessionID": "s",
                "tokens": {
                    "input": 1,
                    "output": 1,
                    "reasoning": 0,
                    "cache": {"read": 0},
                },
            },
        }

    def _drain_permissions(
        self,
        events_in: list[dict[str, object]],
        statuses: Mapping[str, int],
        *,
        replied: set[str] | None = None,
        cascade: dict[str, bool] | None = None,
    ) -> tuple[bool, list[str]]:
        """Прогнать дренаж шага с заданными HTTP-статусами reply; вернуть итог и пути POST."""
        drain = cast("Callable[..., bool]", getattr(server, "_drain_serve_step_usage"))
        make_state = cast("Callable[[], object]", getattr(server, "_ServeToolState"))
        events: queue.Queue[dict[str, object] | None] = queue.Queue()
        for item in events_in:
            events.put(item)
        paths: list[str] = []

        def control(
            _method: str, path: str, _body: object
        ) -> tuple[int, dict[str, object]]:
            paths.append(path)
            return statuses.get(path.rsplit("/", 2)[-2], 204), {}

        extra: dict[str, object] = {}
        if replied is not None:
            extra["replied_permissions"] = replied
        if cascade is not None:
            extra["cascade_reject_state"] = cascade
        confirmed = drain(
            events,
            "s",
            None,
            time.monotonic() + 1,
            {},
            make_state(),
            _fake_result(),
            self._c12_ignore,
            self._c12_ignore,
            ctrl_http=control,
            **extra,
        )
        return confirmed, paths

    def test_serve_cascaded_permission_asked_second_reply_404_succeeds(self) -> None:
        """Каскадный reject: первый reply 200, второй 404 — шаг завершается без SecurityError."""
        confirmed, paths = self._drain_permissions(
            [
                self._permission_event("perm_1"),
                self._permission_event("perm_2"),
                self._step_ended_event(),
            ],
            {"perm_1": 200, "perm_2": 404},
        )
        self.assertTrue(confirmed)
        self.assertEqual(
            paths,
            [
                "/api/session/s/permission/perm_1/reply",
                "/api/session/s/permission/perm_2/reply",
            ],
        )

    def test_serve_permission_replied_event_prevents_cascade_failure(self) -> None:
        """permission.replied(reject) фиксирует requestID, в том числе без sessionID."""
        map_event = cast(
            "Callable[[dict[str, object]], tuple[str, dict[str, object]] | None]",
            getattr(server, "_map_serve_event"),
        )
        for field in ("reply", "decision"):
            mapped = map_event(
                {
                    "type": "permission.replied",
                    "data": {"requestID": " perm_2 ", field: "reject"},
                }
            )
            self.assertIsNotNone(mapped)
            kind, payload = cast("tuple[str, dict[str, object]]", mapped)
            self.assertEqual(kind, "permission_replied")
            self.assertEqual(payload["id"], "perm_2")
        for ignored in (
            {"requestID": "perm_2", "reply": "once"},
            {"requestID": "perm_2", "decision": "always"},
            {"requestID": "  ", "reply": "reject"},
            {"reply": "reject"},
        ):
            self.assertIsNone(
                map_event({"type": "permission.replied", "data": ignored}), ignored
            )
        # replied без sessionID приходит раньше buffered asked: повторный POST не нужен.
        replied: set[str] = set()
        confirmed, paths = self._drain_permissions(
            [
                {
                    "type": "permission.replied",
                    "data": {"requestID": "perm_2", "reply": "reject"},
                },
                self._permission_event("perm_2"),
                self._step_ended_event(),
            ],
            {"perm_2": 404},
            replied=replied,
        )
        self.assertTrue(confirmed)
        self.assertEqual(paths, [])
        self.assertEqual(replied, {"perm_2"})
        # Чужая сессия и не-reject события не создают доказательство каскада.
        replied = set()
        with self.assertRaises(server.ServeSecurityError):
            _ = self._drain_permissions(
                [
                    {
                        "type": "permission.replied",
                        "data": {
                            "requestID": "perm_3",
                            "reply": "reject",
                            "sessionID": "foreign",
                        },
                    },
                    {
                        "type": "permission.replied",
                        "data": {"requestID": "perm_3", "reply": "once"},
                    },
                    self._permission_event("perm_3"),
                    self._step_ended_event(),
                ],
                {"perm_3": 404},
                replied=replied,
            )
        self.assertEqual(replied, set())

    def test_serve_primary_permission_reject_404_fails_closed(self) -> None:
        """Первичный 404 без каскадного доказательства, 5xx и пустой id — fail-closed."""
        cases: list[tuple[str, list[dict[str, object]], dict[str, int]]] = [
            ("primary_404", [self._permission_event("perm_1")], {"perm_1": 404}),
            (
                "second_500",
                [self._permission_event("perm_1"), self._permission_event("perm_2")],
                {"perm_1": 200, "perm_2": 500},
            ),
            (
                "second_401",
                [self._permission_event("perm_1"), self._permission_event("perm_2")],
                {"perm_1": 204, "perm_2": 401},
            ),
            ("primary_500", [self._permission_event("perm_1")], {"perm_1": 500}),
            ("empty_id", [self._permission_event("  ")], {}),
        ]
        for name, events_in, statuses in cases:
            with self.subTest(case=name):
                with self.assertRaisesRegex(
                    server.ServeSecurityError, "permission reject failed"
                ):
                    _ = self._drain_permissions(
                        [*events_in, self._step_ended_event()], statuses
                    )
        # Кроме 404-толерантности: interrupt всегда пробуется при отказе.
        paths: list[str] = []

        def control(
            _method: str, path: str, _body: object
        ) -> tuple[int, dict[str, object]]:
            paths.append(path)
            return 404, {}

        drain = cast("Callable[..., bool]", getattr(server, "_drain_serve_step_usage"))
        make_state = cast("Callable[[], object]", getattr(server, "_ServeToolState"))
        events: queue.Queue[dict[str, object] | None] = queue.Queue()
        events.put(self._permission_event("perm_1"))
        with self.assertRaisesRegex(
            server.ServeSecurityError, "permission reject failed"
        ):
            _ = drain(
                events,
                "s",
                None,
                time.monotonic() + 1,
                {},
                make_state(),
                _fake_result(),
                self._c12_ignore,
                self._c12_ignore,
                ctrl_http=control,
            )
        self.assertEqual(paths[-1], "/api/session/s/interrupt")

    """Группа C: детерминированные оракулы RW-001..RW-032 без живого FakeServe."""

    def test_c11_rw004_callback_error_logged_and_socket_aborted(self) -> None:
        """RW-004: сбой callback маскируется в логе и не отменяет закрытие сокета."""
        sock = _FakeSock()

        def callback() -> None:
            raise RuntimeError("boom secret_token")

        def mask_message(text: str) -> str:
            return text.replace("secret_token", "[MASKED]")

        locked = server._LockedWfile(  # pyright: ignore[reportPrivateUsage] — причина: оракул проверяет приватную границу моста
            io.BytesIO(),
            threading.Lock(),
            sock=cast(socket.socket, cast(object, sock)),
            on_client_gone=callback,
        )
        log = server._log  # pyright: ignore[reportPrivateUsage] — причина: проверяется запись диагностики в bridge.log
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "bridge.log"
            with (
                mock.patch.object(server, "LOG_PATH", log_path),
                mock.patch.object(server, "_log", wraps=log) as logged,
                mock.patch.object(
                    server,
                    "_mask_secrets",
                    side_effect=mask_message,
                ) as masked,
            ):
                locked._mark_client_gone()  # pyright: ignore[reportPrivateUsage] — причина: проверяется сбой callback
            masked.assert_any_call("boom secret_token")
            logged.assert_called_once_with("client_gone callback error: boom [MASKED]")
            self.assertTrue(sock.closed)
            self.assertTrue(locked.client_gone)

            self.assertIn(
                "client_gone callback error: boom [MASKED]", log_path.read_text()
            )
            self.assertNotIn("secret_token", log_path.read_text())

    def test_c10_rw004_tool_count_and_state_bytes_caps(self) -> None:
        """RW-004 цикл 10: 128 уникальных call_id, замена не суммируется повторно."""
        self.assertEqual(
            server._MAX_SERVE_NATIVE_TOOLS,  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватный потолок native-вызовов
            128,
        )
        state = server._ServeToolState()  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватное состояние native-вызовов
        for index in range(128):
            state.feed({"id": f"c{index}", "name": "bash", "text": "{}"})
        state.feed({"id": "c0", "name": "bash", "text": '{"command": "pwd"}'})
        with self.assertRaises(server.ServeProtocolError) as caught:
            state.feed({"id": "c128", "name": "bash", "text": "{}"})
        self.assertEqual(
            str(caught.exception), "serve native tool calls count exceeded cap"
        )
        sized = server._ServeToolState()  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватное состояние native-вызовов
        sized.feed({"id": "one", "name": "bash", "text": "x" * 10})
        measure = server._serve_tool_state_bytes  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватный байтовый учёт состояния
        first = measure(sized)
        sized.feed({"id": "one", "name": "bash", "text": "y" * 10})
        self.assertEqual(measure(sized), first)
        sized.feed({"id": "one", "name": "bash", "input": {"command": "z" * 20}})
        self.assertGreater(measure(sized), first)

    def test_c10_rw005_locked_wfile_timeout_and_abort_without_lock(self) -> None:
        """RW-005 цикл 10: таймаут записи -> BrokenPipe, abort без замка, client gone."""
        self.assertEqual(
            server._DOWNSTREAM_WRITE_TIMEOUT_S,  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватный downstream-таймаут
            5.0,
        )
        gone: list[bool] = []
        sock = _FakeSock()
        lock = threading.Lock()
        with mock.patch.object(server, "_DOWNSTREAM_WRITE_TIMEOUT_S", 0.5, create=True):
            locked = server._LockedWfile(  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватная обёртка wfile
                cast(io.BufferedIOBase, cast(object, _FailingWfile())),
                lock,
                sock=cast(socket.socket, cast(object, sock)),
                deadline=time.monotonic() + 100.0,
                on_client_gone=lambda: gone.append(True),
            )
            with self.assertRaises(BrokenPipeError):
                _ = locked.write(b"data: x\n\n")
        self.assertEqual(gone, [True])
        self.assertEqual(sock.timeouts, [0.5])
        self.assertEqual(sock.shutdown_calls, [socket.SHUT_RDWR])
        self.assertTrue(sock.closed)
        locked.cancel_deadline_timer()
        self.assertTrue(lock.acquire(timeout=1.0))
        try:
            worker = threading.Thread(target=locked.abort_socket, daemon=True)
            worker.start()
            worker.join(1.0)
            self.assertFalse(worker.is_alive(), "abort_socket заблокирован замком")
        finally:
            lock.release()

    def test_c10_fu002_aux_budget_three_subscriptions_deterministic(self) -> None:
        """FU-002 цикл 10: три подписки по 20 с упираются в общий бюджет 54 с."""
        self.assertEqual(
            server._AUX_IO_BUDGET_S,  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватный aux-бюджет
            54.0,
        )
        now = [0.0]
        budget = server._AuxIoBudget(clock_fn=lambda: now[0])  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватный aux-бюджет
        request_deadline = 1000.0

        def subscribe() -> float:
            budget.check()
            phase_deadline = budget.deadline(request_deadline)
            started = now[0]
            try:
                now[0] = min(started + 20.0, phase_deadline)
                return now[0] - started
            finally:
                budget.debit_elapsed(started)

        self.assertEqual([subscribe(), subscribe(), subscribe()], [20.0, 20.0, 14.0])
        self.assertEqual(budget.spent_s(), 54.0)
        self.assertLessEqual(budget.spent_s(), 54.0)
        self.assertEqual(budget.remaining_s(), 0.0)
        before = now[0]
        with self.assertRaises(server.ServeStartupDeadlineExceeded):
            _ = subscribe()
        self.assertEqual(now[0], before, "после исчерпания бюджета I/O не стартует")

    def test_c8_fu002_pre_spawn_gate_and_limiter_respect_deadline_and_client_disconnect(
        self,
    ) -> None:
        """Ожидание gate и лимитера ограничено дедлайном и отменой клиента."""
        lock = server._STARTUP_LOCK  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватная граница serve и управление запуском
        gate_cls = server._StartupGate  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватная граница serve и управление запуском
        limiter_cls = server._SpawnRateLimiter  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватная граница serve и управление запуском
        self.assertTrue(lock.acquire(timeout=0.1))
        try:
            for cancel in (False, True):
                started = time.monotonic()
                gate = gate_cls(wait_s=1.0)
                gate.acquire(deadline=started + 0.06, is_client_gone=lambda: cancel)
                gate.release()
                self.assertLess(time.monotonic() - started, 0.2)
                self.assertTrue(lock.locked())
        finally:
            lock.release()
        for cancel in (False, True):
            now = [0.0]
            sleeps: list[float] = []

            def advance(seconds: float) -> None:
                sleeps.append(seconds)
                now[0] += seconds

            limiter = limiter_cls(
                rate_rps=1.0, burst=1.0, clock_fn=lambda: now[0], sleep_fn=advance
            )
            self.assertTrue(limiter.acquire())
            self.assertFalse(
                limiter.acquire(
                    max_wait_s=2.0,
                    deadline=0.08 if not cancel else 2.0,
                    is_client_gone=lambda: cancel and now[0] >= 0.05,
                )
            )
            self.assertLessEqual(now[0], 0.08)
            self.assertTrue(all(s <= 0.05 for s in sleeps))
            now[0] = 1.1
            self.assertTrue(limiter.acquire(max_wait_s=0.0))

    def test_surrogate_pair_and_broken_json(self) -> None:
        """RW-005: суррогатная пара декодируется, битый JSON serve — ServeProtocolError."""
        parsed = server._loads_object('{"emoji": "\ud83d\ude00"}')  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        self.assertEqual(parsed, {"emoji": "\U0001f600"})
        self.assertEqual(
            json.dumps(parsed, ensure_ascii=False).encode("utf-8").decode("utf-8"),
            '{"emoji": "\U0001f600"}',
        )
        self.assertIsNone(server._loads_object("{broken"))  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        with self.assertRaises(server.ServeProtocolError):
            _ = server._loads_serve_object("{broken")  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста

    def test_service_events_ignored_and_foreign_session(self) -> None:
        """RW-029/RW-031: служебные события — None, sessionID сохраняется в payload."""
        self.assertIsNone(
            server._map_serve_event({"type": "integration.updated", "data": {}})  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        )
        self.assertIsNone(
            server._map_serve_event({"type": "server.heartbeat", "data": {}})  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        )
        mapped = server._map_serve_event(  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
            {"type": "session.text.delta", "data": {"sessionID": "ses_a", "delta": " "}}
        )
        self.assertIsNotNone(mapped)
        assert mapped is not None
        self.assertEqual(mapped[1].get("sessionID"), "ses_a")
        self.assertEqual(mapped[1].get("content"), " ")

    def test_whitespace_delta_preserved_in_map(self) -> None:
        """RW-007: пробельная дельта не отбрасывается маппером."""
        mapped = server._map_serve_event(  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
            {
                "type": "session.reasoning.delta",
                "data": {"sessionID": "s1", "delta": "\n\n"},
            }
        )
        self.assertIsNotNone(mapped)
        assert mapped is not None
        self.assertEqual(mapped[1].get("reasoning_content"), "\n\n")

    def test_half_open_to_closed_via_attempt_done(self) -> None:
        """RW-014: успешный serve через attempt_done переводит breaker в CLOSED."""
        res = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        res.breaker = server._UpstreamBreaker(fail_threshold=1, reset_timeout_s=0.01)  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        res.breaker.record_failure()
        self.assertEqual(res.breaker.state, "OPEN")
        time.sleep(0.03)
        self.assertTrue(res.breaker.allow())
        self.assertEqual(res.breaker.state, "HALF_OPEN")
        attempts = server._RequestAttempts(res, time.monotonic() + 60.0)  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        attempts.attempt_done(False, True)
        self.assertEqual(res.breaker.state, "CLOSED")

    def test_transport_matrix(self) -> None:
        """RW-025: TRANSPORT=run, override 0, disable-файл и опечатка дают run."""
        with mock.patch.dict(
            os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": "run"}, clear=False
        ):
            self.assertEqual(server._select_transport(), "run")  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        with mock.patch.dict(
            os.environ,
            {
                "OPENCODE_ZEN_BRIDGE_TRANSPORT": "serve",
                "OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED": "0",
            },
            clear=False,
        ):
            self.assertEqual(server._select_transport(), "run")  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        with mock.patch.dict(
            os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": "serv"}, clear=False
        ):
            self.assertEqual(server._select_transport(), "run")  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста

    def test_disable_file_overrides_forced_serve(self) -> None:
        """FU-013: файл отключения важнее принудительного выбора serve."""
        with tempfile.TemporaryDirectory() as name:
            disable = Path(name) / "disable-serve"
            _ = disable.write_text("1")
            with mock.patch.dict(
                os.environ,
                {
                    "OPENCODE_ZEN_BRIDGE_TRANSPORT": "serve",
                    "OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE": str(disable),
                    "OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED": "1",
                },
            ):
                self.assertEqual(server._select_transport(), "run")  # pyright: ignore[reportPrivateUsage] — причина: проверяется приоритет аварийного файла отключения

    def test_fake_rt_mode_preset_preserved(self) -> None:
        """RW-027: предустановленный FAKE_RT_MODE сохраняется после patch.dict."""
        patcher = mock.patch.dict(
            os.environ, {"FAKE_RT_MODE": "preset-value"}, clear=False
        )
        _ = patcher.start()  # pyright: ignore[reportAny] — причина: динамический результат запуска patch.dict не используется
        try:
            inner = mock.patch.dict(os.environ, {"FAKE_RT_MODE": "fast"}, clear=False)
            _ = inner.start()  # pyright: ignore[reportAny] — причина: mock.patch.start возвращает динамический объект подмены, результат не используется
            _ = inner.stop()  # pyright: ignore[reportAny] — причина: mock.patch.stop возвращает динамический результат восстановления, он не используется
            self.assertEqual(os.environ.get("FAKE_RT_MODE"), "preset-value")
        finally:
            _ = patcher.stop()  # pyright: ignore[reportAny] — причина: динамический результат восстановления patch.dict не используется

    def test_spawn_cap_and_proxy_rotation_helpers(self) -> None:
        """RW-001/RW-013: can_spawn ограничен MAX_TOTAL_SPAWNS, пул прокси ротируется."""
        res = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        attempts = server._RequestAttempts(res, time.monotonic() + 60.0)  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        for _i in range(server.MAX_TOTAL_SPAWNS):
            self.assertTrue(attempts.can_spawn())
            attempts.note_spawn()
        self.assertFalse(attempts.can_spawn())
        self.assertTrue(callable(server._next_standalone_proxy))  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста

    def test_elf_magic_and_tool_status(self) -> None:
        """FU-001/FU-002: 4 случайных байта не ELF, статус tool из типа события."""
        state = server._ServeToolState()  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        state.feed({"id": "c1", "name": "bash", "text": '{"command": "x"}'})
        done = state.complete("c1", "session.tool.called")
        self.assertIsNotNone(done)
        assert done is not None
        part_obj: object = done[1].get("part")
        self.assertIsInstance(part_obj, dict)
        self.assertEqual(
            _as_obj_dict(_as_obj_dict(part_obj).get("state")).get("status"), "completed"
        )
        with tempfile.TemporaryDirectory() as name:
            binary = Path(name) / "opencode"
            with mock.patch.object(server, "SERVE_TEST_ELIGIBLE", False):
                for magic, expected in (
                    (b"xxxx", False),
                    (b"#!/b", False),
                    (b"\x7fELF", True),
                    (b"\xcf\xfa\xed\xfe", True),
                ):
                    _ = binary.write_bytes(magic)
                    native = server._is_native_opencode_bin  # pyright: ignore[reportPrivateUsage] — причина: проверяется сигнатура отдельно от тестового допуска
                    self.assertEqual(native(str(binary)), expected)

    def test_fu001_http_checks_deadline_and_cancellation_before_connect(self) -> None:
        """FU-001: просроченный бюджет и ушедший клиент запрещают даже соединение HTTP."""
        call = server._serve_http  # pyright: ignore[reportPrivateUsage] — причина: проверяется граница фазы управляющего HTTP-вызова
        with self.assertRaises(TimeoutError):
            _ = call(0, "", "GET", "/", deadline=time.monotonic() - 1)
        with self.assertRaises(BrokenPipeError):
            _ = call(0, "", "GET", "/", is_client_gone=lambda: True)

    def test_rw004_native_calls_share_canonical_mapping(self) -> None:
        """RW-004: bash/read/edit/list/multiedit используют ровно канонический fit_args."""
        tools: list[dict[str, object]] = [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "parameters": {
                        "type": "object",
                        "properties": props,
                        "required": list(props),
                    },
                },
            }
            for name, props in (
                (
                    "bash",
                    {"command": {"type": "string"}, "description": {"type": "string"}},
                ),
                ("read", {"file_path": {"type": "string"}}),
                (
                    "edit",
                    {
                        "file_path": {"type": "string"},
                        "old_string": {"type": "string"},
                        "new_string": {"type": "string"},
                    },
                ),
            )
        ]
        mapper = server._native_to_tool_calls  # pyright: ignore[reportPrivateUsage] — причина: канонический преобразователь run служит оракулом адаптера serve
        canonical = cast(
            "Callable[\n                [object, object, list[dict[str, object]]], list[dict[str, object]]\n            ]",
            mapper,
        )
        for name, args in (
            ("bash", {"command": "pwd"}),
            ("read", {"filePath": "/tmp/a"}),
            ("edit", {"filePath": "/tmp/a", "oldString": "a", "newString": "b"}),
            ("list", {"path": "/tmp"}),
            (
                "multiedit",
                {
                    "filePath": "/tmp/a",
                    "edits": [
                        {"oldString": "a", "newString": "b"},
                        {"oldString": "c", "newString": "d"},
                    ],
                },
            ),
        ):
            with self.subTest(name=name):
                expected = canonical(name, args, tools)
                adapter = server._native_call_as_dsh  # pyright: ignore[reportPrivateUsage] — причина: сверяется адаптер serve с преобразователем run
                actual = adapter(
                    {"part": {"tool": name, "state": {"input": args}}}, tools
                )
                self.assertTrue(expected, name)
                self.assertEqual(
                    json.dumps(actual, sort_keys=True),
                    json.dumps(expected, sort_keys=True),
                )

    def test_rw005_stop_group_after_leader_exit(self) -> None:
        """RW-005: завершившийся лидер не мешает убить живого потомка его группы."""
        with tempfile.TemporaryDirectory() as name:
            pidfile = Path(name) / "child.pid"
            code = (
                "import os,signal,time; from pathlib import Path; "
                "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                f"Path({str(pidfile)!r}).write_text(str(os.getpid())); time.sleep(30)"
            )
            parent = "import subprocess,sys,time; from pathlib import Path; subprocess.Popen([sys.executable,'-c',sys.argv[1]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); p=Path(sys.argv[2]); deadline=time.monotonic()+3; "
            parent += (
                "\nwhile not p.exists() and time.monotonic()<deadline: time.sleep(0.01)"
            )
            proc = subprocess.Popen(
                [sys.executable, "-c", parent, code, str(pidfile)],
                text=True,
                start_new_session=True,
            )
            try:
                _ = proc.wait(timeout=5)
                self.assertTrue(pidfile.exists())
                child = int(pidfile.read_text())
                server._stop_proc(proc)  # pyright: ignore[reportPrivateUsage] — причина: проверяется остановка осиротевшего потомка завершившегося лидера
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    try:
                        os.kill(child, 0)
                    except ProcessLookupError:
                        break
                    time.sleep(0.02)
                else:
                    self.fail("потомок пережил остановку группы")
            finally:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                _ = proc.wait(timeout=5)

    def test_rw008_error_payload_masks_message_and_detail(self) -> None:
        """RW-008: общий конструктор ошибки очищает оба поля до сериализации."""
        secret = "sk-" + "b" * 32
        payload = server._error_payload(secret, "Bearer hidden-detail")  # pyright: ignore[reportPrivateUsage] — причина: проверяется последняя граница очистки клиентской ошибки
        encoded = json.dumps(payload)
        self.assertNotIn(secret, encoded)
        self.assertNotIn("hidden-detail", encoded)


def _fake_result(**over: object) -> dict[str, object]:
    """Результат попытки serve для подмены `_serve_one_attempt`."""
    base: dict[str, object] = {
        "reasonings": [],
        "texts": [],
        "native_calls": [],
        "usage": {},
        "error": None,
        "exit_reason": "",
        "delivered": False,
        "terminal": "",
        "first_event_at": None,
        "first_token_at": None,
        "step_closed": False,
        "first_event_ms": None,
        "ttft_ms": None,
        "prompt_status": None,
        "transient_error": False,
    }
    base.update(over)
    return base


def _callback(args: tuple[object, ...], index: int) -> Callable[[str], None]:
    """Колбэк `_serve_one_attempt` по позиции (4 reasoning, 5 text)."""
    return cast("Callable[[str], None]", args[index])


class _AttemptCase(unittest.TestCase):
    """База: FakeServe в tmp, пустой HOME и изолированный LEASE_DIR для прямых вызовов попытки."""

    tmpdir: tempfile.TemporaryDirectory[str] = cast(
        "tempfile.TemporaryDirectory[str]", None
    )  # pyright: ignore[reportInvalidCast] — причина: значение задаётся в setUp до первого обращения
    tmp: Path = Path()
    saved_bin: str = ""
    saved_lease: Path = Path()
    env: object = None

    @override
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        self.saved_bin = server.OPENCODE_BIN
        self.saved_lease = server.LEASE_DIR
        server.OPENCODE_BIN = str(fake)
        server.LEASE_DIR = self.tmp / "leases"
        (self.tmp / "home").mkdir()
        self.env = mock.patch.dict(
            os.environ, {"HOME": str(self.tmp / "home")}, clear=False
        )
        _ = cast(_Patcher, self.env).start()

    @override
    def tearDown(self) -> None:
        _ = cast(_Patcher, self.env).stop()
        server.OPENCODE_BIN = self.saved_bin
        server.LEASE_DIR = self.saved_lease
        self.tmpdir.cleanup()

    def attempt(
        self,
        prompt: str,
        *,
        reasoning: list[tuple[float, str]] | None = None,
        on_ready: Callable[[], None] | None = None,
        on_token: Callable[[], None] | None = None,
        emulate_tools: bool = False,
        on_tool: Callable[[dict[str, object]], None] | None = None,
    ) -> Mapping[str, object]:
        """Одна реальная попытка serve против FakeServe (метки времени — монотонные)."""
        marks = reasoning if reasoning is not None else []
        t0 = time.monotonic()

        def on_reasoning(text: str) -> None:
            marks.append((time.monotonic(), text))
            if on_token is not None:
                on_token()

        def ignore(_text: str) -> None:
            return None

        def ignore_tool(_payload: dict[str, object]) -> None:
            return None

        return server._serve_one_attempt(  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
            MODEL,
            prompt,
            "high",
            self.tmp,
            on_reasoning,
            ignore,
            ignore_tool if on_tool is None else on_tool,
            t0,
            on_startup_ready=on_ready,
            emulate_tools=emulate_tools,
        )


class TestServeAttemptOracles(_AttemptCase):
    """Поведенческие оракулы `_serve_one_attempt` на FakeServe (RW-003/008/011/014/019)."""

    def test_c12_rw001_main_control_disconnect_and_deadline_are_neutral(self) -> None:
        """Main control не превращает завершение клиента/дедлайна в security error."""
        http_call = cast(
            "Callable[..., tuple[int, dict[str, object]]]",
            getattr(server, "_serve_http"),
        )
        for marker in ("__form_ok__", "__permission__"):
            for interrupt in (False, True):
                for error, reason in (
                    (server.ServeClientDisconnect, "client_gone"),
                    (server.ServeStartupDeadlineExceeded, "timeout"),
                ):
                    with self.subTest(marker=marker, interrupt=interrupt, error=error):

                        def control_http(
                            *args: object, **kwargs: object
                        ) -> tuple[int, dict[str, object]]:
                            path = str(args[3])
                            if (
                                not kwargs.get("skip_body")
                                and path.endswith(("/cancel", "/reply", "/interrupt"))
                                and interrupt == path.endswith("/interrupt")
                            ):
                                raise error("neutral completion")
                            return http_call(*args, **kwargs)

                        with mock.patch.object(
                            server, "_serve_http", side_effect=control_http
                        ):
                            result = self.attempt(marker)
                        self.assertEqual(result["exit_reason"], reason)
                        self.assertFalse(list(server.LEASE_DIR.glob("lease-*.json")))

    def test_c12_rw003_main_passes_attempt_deadline_to_active_drain(self) -> None:
        """Реальная попытка дренирует два tool calls дольше двух исходных окон."""
        fragment = """
            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"first","name":"bash","input":{"command":"pwd"}}})
            for i in range(5):
                time.sleep(0.08)
                if i==0: emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"second","name":"bash","input":{"command":"ls"}}})
                else: emit({"type":"session.text.delta","data":{"sessionID":sid,"assistantMessageID":"m1","delta":"хвост"}})
            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0,"write":0}}}})
            return
"""
        _ = Path(server.OPENCODE_BIN).write_text(
            FAKE_SERVE.replace(
                '            if "__native_pause__" in prompt:',
                fragment + '            if "__native_pause__" in prompt:',
            )
        )
        with mock.patch.object(server, "_STEP_DRAIN_WINDOW_S", 0.15):
            result = self.attempt("x", emulate_tools=True)
        self.assertEqual(result["terminal"], "tool_calls", result)
        self.assertEqual(len(cast("list[object]", result["native_calls"])), 2)
        self.assertEqual(result["texts"], ["хвост"] * 4)

    def _attempt_with_permissions(
        self,
        events_code: str,
        *,
        emulate_tools: bool = False,
        on_tool: Callable[[dict[str, object]], None] | None = None,
    ) -> tuple[list[str], object]:
        """Попытка против FakeServe с заданными permission-событиями; вернуть POST-пути и итог/ошибку."""
        fragment = (
            """
            emit({"type":"session.execution.started","data":{"sessionID":sid}})
"""
            + events_code
            + """
            time.sleep(0.2)
            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0,"write":0}}}})
            emit({"type":"session.execution.succeeded","data":{"sessionID":sid}})
            return
"""
        )
        _ = Path(server.OPENCODE_BIN).write_text(
            FAKE_SERVE.replace(
                '            if "__native_pause__" in prompt:',
                fragment + '            if "__native_pause__" in prompt:',
            )
        )
        http_call = cast(
            "Callable[..., tuple[int, dict[str, object]]]",
            getattr(server, "_serve_http"),
        )
        posts: list[str] = []

        def recording_http(
            *args: object, **kwargs: object
        ) -> tuple[int, dict[str, object]]:
            path = str(args[3])
            if path.endswith(("/reply", "/interrupt")):
                posts.append(path)
            return http_call(*args, **kwargs)

        outcome: object
        with mock.patch.object(server, "_serve_http", side_effect=recording_http):
            try:
                outcome = self.attempt(
                    "x", emulate_tools=emulate_tools, on_tool=on_tool
                )
            except server.ServeSecurityError as exc:
                outcome = exc
        return posts, outcome

    def test_serve_cascaded_permission_asked_second_reply_404_succeeds_main_loop(
        self,
    ) -> None:
        """Основной цикл: reply per1=204, per2=404 (каскад) — без SecurityError, interrupt на каждый permission."""
        posts, outcome = self._attempt_with_permissions(
            """
            emit({"type":"permission.asked","data":{"id":"per1","sessionID":sid,"action":"bash","resources":["*"]}})
            emit({"type":"permission.asked","data":{"id":"per2","sessionID":sid,"action":"bash","resources":["*"]}})
"""
        )
        self.assertNotIsInstance(outcome, BaseException, outcome)
        # Хвостовой interrupt завершения попытки не входит в проверяемый префикс.
        self.assertEqual(
            posts[:4],
            [
                "/api/session/ses_test1/permission/per1/reply",
                "/api/session/ses_test1/interrupt",
                "/api/session/ses_test1/permission/per2/reply",
                "/api/session/ses_test1/interrupt",
            ],
        )

    def test_serve_permission_replied_event_skips_reply_post_main_loop(self) -> None:
        """Основной цикл: permission.replied(reject) без sessionID пропускает POST reply, но не interrupt."""
        posts, outcome = self._attempt_with_permissions(
            """
            emit({"type":"permission.replied","data":{"requestID":"per2","reply":"reject"}})
            emit({"type":"permission.asked","data":{"id":"per2","sessionID":sid,"action":"bash","resources":["*"]}})
"""
        )
        self.assertNotIsInstance(outcome, BaseException, outcome)
        self.assertEqual(posts[:1], ["/api/session/ses_test1/interrupt"])
        self.assertFalse([path for path in posts if path.endswith("/reply")], posts)

    def test_serve_primary_permission_reject_404_fails_closed_main_loop(self) -> None:
        """Основной цикл: первичный 404 без каскадного доказательства — SecurityError, interrupt выполнен."""
        posts, outcome = self._attempt_with_permissions(
            """
            emit({"type":"permission.asked","data":{"id":"per9","sessionID":sid,"action":"bash","resources":["*"]}})
"""
        )
        self.assertIsInstance(outcome, server.ServeSecurityError, outcome)
        self.assertIn("permission reply HTTP 404", str(outcome))
        self.assertEqual(
            posts[:2],
            [
                "/api/session/ses_test1/permission/per9/reply",
                "/api/session/ses_test1/interrupt",
            ],
        )

    def test_serve_main_loop_to_drain_shared_cascade_state_404(self) -> None:
        """Основной цикл -> дренаж шага: per1=204 в основном цикле, per2=404 в дренаже терпится общим состоянием."""
        tool_calls: list[dict[str, object]] = []
        posts, outcome = self._attempt_with_permissions(
            """
            emit({"type":"permission.asked","data":{"id":"per1","sessionID":sid,"action":"bash","resources":["*"]}})
            emit({"type":"session.tool.called","data":{"id":"call_cascade_1","sessionID":sid,"assistantMessageID":"msg_c1","name":"read_file","input":{"path":"README.md"}}})
            emit({"type":"permission.asked","data":{"id":"per2","sessionID":sid,"action":"bash","resources":["*"]}})
            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"msg_c1","tokens":{"input":10,"output":5,"reasoning":0,"cache":{"read":0,"write":0}}}})
""",
            emulate_tools=True,
            on_tool=tool_calls.append,
        )
        self.assertNotIsInstance(outcome, BaseException, outcome)
        self.assertIn("call_cascade_1", repr(tool_calls))
        self.assertIn("read_file", repr(tool_calls))
        for expected in (
            "/api/session/ses_test1/permission/per1/reply",
            "/api/session/ses_test1/interrupt",
            "/api/session/ses_test1/permission/per2/reply",
        ):
            self.assertIn(expected, posts)

    def test_serve_permission_missing_id_fails_closed_main_loop(self) -> None:
        """Основной цикл: permission.asked без id — SecurityError, reply не отправлен, interrupt выполнен."""
        posts, outcome = self._attempt_with_permissions(
            """
            emit({"type":"permission.asked","data":{"id":"","sessionID":sid,"action":"bash","resources":["*"]}})
"""
        )
        self.assertIsInstance(outcome, server.ServeSecurityError, outcome)
        self.assertIn("missing id", str(outcome))
        self.assertFalse([path for path in posts if path.endswith("/reply")], posts)
        self.assertIn("/api/session/ses_test1/interrupt", posts)

    def test_serve_foreign_session_permission_replied_ignored_main_loop(
        self,
    ) -> None:
        """Основной цикл: permission.replied чужой сессии игнорируется — reply и interrupt по своему per1."""
        posts, outcome = self._attempt_with_permissions(
            """
            emit({"type":"permission.replied","data":{"id":"per1","sessionID":"ses_foreign","reply":"reject"}})
            emit({"type":"permission.asked","data":{"id":"per1","sessionID":sid,"action":"bash","resources":["*"]}})
"""
        )
        self.assertNotIsInstance(outcome, BaseException, outcome)
        self.assertEqual(
            posts[:2],
            [
                "/api/session/ses_test1/permission/per1/reply",
                "/api/session/ses_test1/interrupt",
            ],
        )

    def test_c9_fu001_serve_queue_and_accumulated_byte_budget_enforced(self) -> None:
        """Каждый байтовый бюджет останавливает реальную попытку и убирает lease."""
        for budget in ("_MAX_SERVE_QUEUE_BYTES", "_MAX_SERVE_ACCUMULATED_BYTES"):
            with self.subTest(budget=budget):
                lease_cls = server._ServeLease  # pyright: ignore[reportPrivateUsage] — причина: проверяется обязательная уборка попытки
                cleanup = lease_cls.cleanup
                with (
                    mock.patch.object(
                        server,
                        budget,
                        8 if budget == "_MAX_SERVE_QUEUE_BYTES" else 16,
                        create=True,
                    ),
                    mock.patch.object(
                        lease_cls, "cleanup", autospec=True, side_effect=cleanup
                    ) as cleaned,
                ):
                    result = self.attempt("x")
                self.assertEqual(result["exit_reason"], "invalid_serve_event", result)
                self.assertNotEqual(result["terminal"], "succeeded", result)
                cleaned.assert_called_once()
                self.assertFalse(list(server.LEASE_DIR.glob("lease-*.json")))

    def test_c11_rw006_name_and_id_caps_main_and_drain(self) -> None:
        """RW-006: крупные имя/ID до called завершаются protocol error без публикации."""
        for drain in (False, True):
            for field in ("name", "id"):
                with self.subTest(drain=drain, field=field):
                    prefix = (
                        '            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"c1","name":"bash","input":{"command":"pwd"}}})\n'
                        if drain
                        else ""
                    )
                    payload = {"id": "c2", "name": "bash"}
                    payload[field] = "ж" * 200
                    fragment = (
                        prefix
                        + '            emit({"type":"session.tool.input.started","data":dict(sessionID=sid,assistantMessageID="m1",**'
                        + repr(payload)
                        + ')})\n            time.sleep(0.1)\n            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0,"write":0}}}})\n            return\n'
                    )
                    _ = Path(server.OPENCODE_BIN).write_text(
                        FAKE_SERVE.replace(
                            '            if "__native_pause__" in prompt:',
                            fragment + '            if "__native_pause__" in prompt:',
                        )
                    )
                    lease_cls = server._ServeLease  # pyright: ignore[reportPrivateUsage] — причина: проверяется уборка группы
                    cleanup = lease_cls.cleanup
                    with (
                        mock.patch.object(server, "_MAX_SERVE_ACCUMULATED_BYTES", 128),
                        mock.patch.object(
                            lease_cls, "cleanup", autospec=True, side_effect=cleanup
                        ) as cleaned,
                        mock.patch.object(
                            server,
                            "_serve_attempt_error_reason",
                            wraps=server._serve_attempt_error_reason,  # pyright: ignore[reportPrivateUsage] — причина: проверяется доменное исключение байтового потолка
                        ) as classified,
                    ):
                        result = self.attempt("x", emulate_tools=drain)
                    self.assertEqual(
                        result["exit_reason"], "invalid_serve_event", result
                    )
                    self.assertIsInstance(
                        cast(object, classified.call_args.args[0]),
                        server.ServeProtocolError,
                    )
                    self.assertIn(
                        "byte cap", str(cast(object, classified.call_args.args[0]))
                    )
                    self.assertFalse(result["native_calls"], result)
                    cleaned.assert_called_once()
                    self.assertFalse(list(server.LEASE_DIR.glob("lease-*.json")))

    def test_c11_rw002_execution_wait_excluded_from_prompt_budget(self) -> None:
        """RW-002: после execution.started ожидание модели не списывается в aux."""
        fake = Path(server.OPENCODE_BIN)
        _ = fake.write_text(
            FAKE_SERVE.replace(
                '            state["prompt"] = prompt_text',
                '            state["prompt"] = prompt_text\n            time.sleep(10)',
            )
        )
        budget = server._AuxIoBudget()  # pyright: ignore[reportPrivateUsage] — причина: проверяется разделение aux и генерации
        opened = server._open_serve_events  # pyright: ignore[reportPrivateUsage] — причина: реальная подписка с заданным остатком

        def open_events(
            port: int, password: str, deadline: float, gone: Callable[[], bool] | None
        ) -> tuple[http.client.HTTPConnection, http.client.HTTPResponse]:
            response = opened(port, password, deadline, gone)
            budget.debit_seconds(max(0.0, 53.6 - budget.spent_s()))
            return response

        with mock.patch.object(server, "_open_serve_events", side_effect=open_events):
            result = server._serve_one_attempt(  # pyright: ignore[reportPrivateUsage] — причина: оракул реального prompt HTTP
                MODEL,
                "x",
                "high",
                self.tmp,
                lambda _s: None,
                lambda _s: None,
                lambda _t: None,
                time.monotonic(),
                aux_budget=budget,
            )
        self.assertEqual(result["terminal"], "succeeded", result)
        self.assertLess(budget.spent_s(), 54.0)
        self.assertEqual("".join(result["texts"]), "Ответ\n")

    def test_c11_rw002_exhausted_before_prompt_starts_no_http(self) -> None:
        """RW-002: исчерпание после подписки запрещает запуск prompt HTTP."""
        budget = server._AuxIoBudget()  # pyright: ignore[reportPrivateUsage] — причина: проверяется граница запуска prompt
        opened = server._open_serve_events  # pyright: ignore[reportPrivateUsage] — причина: исчерпание в точке после подписки

        def open_events(
            port: int, password: str, deadline: float, gone: Callable[[], bool] | None
        ) -> tuple[http.client.HTTPConnection, http.client.HTTPResponse]:
            response = opened(port, password, deadline, gone)
            budget.debit_seconds(54.0)
            return response

        http_call = server._serve_http  # pyright: ignore[reportPrivateUsage] — причина: spy фактических HTTP-вызовов
        with (
            mock.patch.object(server, "_open_serve_events", side_effect=open_events),
            mock.patch.object(server, "_serve_http", wraps=http_call) as sent,
        ):
            result = server._serve_one_attempt(  # pyright: ignore[reportPrivateUsage] — причина: реальная точка отказа prompt
                MODEL,
                "x",
                "high",
                self.tmp,
                lambda _s: None,
                lambda _s: None,
                lambda _t: None,
                time.monotonic(),
                aux_budget=budget,
            )
        self.assertFalse(
            any(
                str(cast(object, call.args[3])).endswith("/prompt")
                for call in sent.call_args_list
            )
        )
        self.assertEqual(result["exit_reason"], "timeout", result)
        self.assertEqual(budget.spent_s(), 54.0)

    def test_c11_rw002_security_control_time_debited_main_and_drain(self) -> None:
        """RW-002: reject/cancel/interrupt main/drain списывают фактическое время."""
        http_call = server._serve_http  # pyright: ignore[reportPrivateUsage] — причина: измеряется управляющий HTTP
        for drain in (False, True):
            for control in ("permission", "form"):
                with self.subTest(drain=drain, control=control):
                    budget = server._AuxIoBudget()  # pyright: ignore[reportPrivateUsage] — причина: независимый бюджет попытки
                    delays: list[float] = []
                    prefix = (
                        '            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"c1","name":"bash","input":{"command":"pwd"}}})\n'
                        if drain
                        else ""
                    )
                    control_event = (
                        '            emit({"type":"permission.asked","data":{"sessionID":sid,"id":"per1"}})\n'
                        if control == "permission"
                        else '            emit({"type":"form.created","data":{"form":{"sessionID":sid,"id":"form1"}}})\n'
                    )
                    fragment = (
                        prefix
                        + control_event
                        + '            time.sleep(0.3)\n            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0,"write":0}}}})\n            emit({"type":"session.execution.succeeded","data":{"sessionID":sid}})\n            return\n'
                    )
                    _ = Path(server.OPENCODE_BIN).write_text(
                        FAKE_SERVE.replace(
                            '            if "__native_pause__" in prompt:',
                            fragment + '            if "__native_pause__" in prompt:',
                        )
                    )

                    def http_delay(
                        port: int,
                        password: str,
                        method: str,
                        path: str,
                        body: dict[str, object] | None = None,
                        **kwargs: object,
                    ) -> tuple[int, dict[str, object]]:
                        if (
                            "/reply" in path
                            or "/cancel" in path
                            or "/interrupt" in path
                        ) and not kwargs.get("skip_body"):
                            self.assertFalse(budget.exhausted())
                            started = time.monotonic()
                            time.sleep(0.05)
                            delays.append(time.monotonic() - started)
                        return http_call(port, password, method, path, body, **kwargs)  # pyright: ignore[reportArgumentType] — причина: прозрачный HTTP-spy

                    with mock.patch.object(
                        server, "_serve_http", side_effect=http_delay
                    ):
                        try:
                            _ = server._serve_one_attempt(  # pyright: ignore[reportPrivateUsage] — причина: реальные управляющие вызовы main/drain
                                MODEL,
                                "x",
                                "high",
                                self.tmp,
                                lambda _s: None,
                                lambda _s: None,
                                lambda _t: None,
                                time.monotonic(),
                                emulate_tools=drain,
                                aux_budget=budget,
                            )
                        except server.ServeSecurityError:
                            self.assertEqual(control, "form")
                    self.assertTrue(delays)
                    self.assertGreaterEqual(budget.spent_s(), sum(delays))
                    self.assertFalse(list(server.LEASE_DIR.glob("lease-*.json")))

    def test_c11_rw002_first_sse_budget_across_real_attempts(self) -> None:
        """RW-002: реальные точки подписки/prompt делят 54 с между тремя попытками."""
        now = [1000.0]
        budget = server._AuxIoBudget(clock_fn=lambda: now[0])  # pyright: ignore[reportPrivateUsage] — причина: управляемые часы общего бюджета
        prompt_ready = threading.Event()
        io_calls: list[str] = []

        def serve_http_stub(
            _port: int,
            _password: str,
            _method: str,
            path: str,
            _body: object = None,
            **kwargs: object,
        ) -> tuple[int, dict[str, object]]:
            io_calls.append(path)
            self.assertFalse(budget.exhausted(), path)
            if path.endswith("/prompt"):
                callback = kwargs.get("on_headers")
                if callable(callback):
                    _ = callback(200)
                prompt_ready.set()
            return 200, {"data": {"id": "ses_test1"}} if path == "/api/session" else {
                "data": {}
            }

        def read_events(
            _resp: object,
            events: queue.Queue[dict[str, object] | None],
            _stop: threading.Event,
            *_args: object,
        ) -> None:
            if not prompt_ready.wait(1.0):
                events.put(None)
                return
            now[0] += min(20.0, budget.remaining_s())
            events.put(None)

        conn = mock.Mock(spec=http.client.HTTPConnection)
        conn.sock = None
        lease = mock.Mock()
        with (
            mock.patch.object(server.time, "monotonic", side_effect=lambda: now[0]),  # pyright: ignore[reportPrivateLocalImportUsage] — причина: оракул проверяет приватную границу моста
            mock.patch.object(
                server, "_spawn_serve", return_value=(lease, 12345, "pw")
            ) as spawn,
            mock.patch.object(server, "_serve_http", side_effect=serve_http_stub),
            mock.patch.object(
                server,
                "_open_serve_events",
                return_value=(conn, mock.Mock(spec=http.client.HTTPResponse)),
            ) as opened,
            mock.patch.object(server, "_read_serve_events", side_effect=read_events),
            mock.patch.object(server, "_cleanup_serve_attempt") as cleanup,
        ):
            costs: list[float] = []
            for _ in range(3):
                prompt_ready.clear()
                before = budget.spent_s()
                _ = server._serve_one_attempt(  # pyright: ignore[reportPrivateUsage] — причина: оракул проверяет приватную границу моста
                    MODEL,
                    "x",
                    "high",
                    self.tmp,
                    lambda _s: None,
                    lambda _s: None,
                    lambda _t: None,
                    now[0],
                    deadline=2000.0,
                    aux_budget=budget,
                )
                costs.append(budget.spent_s() - before)
            self.assertEqual(costs, [20.0, 20.0, 14.0])
            count = len(io_calls)
            result = server._serve_one_attempt(  # pyright: ignore[reportPrivateUsage] — причина: оракул проверяет приватную границу моста
                MODEL,
                "x",
                "high",
                self.tmp,
                lambda _s: None,
                lambda _s: None,
                lambda _t: None,
                now[0],
                deadline=2000.0,
                aux_budget=budget,
            )
            self.assertEqual(result["exit_reason"], "timeout")
            self.assertEqual(len(io_calls), count)
            self.assertEqual(spawn.call_count, 3)
            self.assertEqual(opened.call_count, 3)
            self.assertEqual(cleanup.call_count, 3)
        self.assertEqual(budget.spent_s(), 54.0)

    def test_c11_rw002_prompt_headers_use_remaining_aux(self) -> None:
        """RW-002: настоящий HTTP prompt без заголовков ограничен остатком одной секунды."""
        fake = Path(server.OPENCODE_BIN)
        _ = fake.write_text(
            FAKE_SERVE.replace(
                '            prompt_text = str(body.get("text") or "")',
                '            time.sleep(10); return\n            prompt_text = str(body.get("text") or "")',
            )
        )
        budget = server._AuxIoBudget()  # pyright: ignore[reportPrivateUsage] — причина: оракул бюджета реальной попытки
        opened = server._open_serve_events  # pyright: ignore[reportPrivateUsage] — причина: фиксируется остаток перед prompt
        prompt_phase_started = [0.0]

        def open_events(
            *args: object, **kwargs: object
        ) -> tuple[http.client.HTTPConnection, http.client.HTTPResponse]:
            response = opened(*args, **kwargs)  # pyright: ignore[reportArgumentType] — причина: прозрачный spy приватной подписки
            budget.debit_seconds(max(0.0, 53.0 - budget.spent_s()))
            prompt_phase_started[0] = time.monotonic()
            return response

        started = time.monotonic()
        with mock.patch.object(server, "_open_serve_events", side_effect=open_events):
            result = server._serve_one_attempt(  # pyright: ignore[reportPrivateUsage] — причина: оракул проверяет приватную границу моста
                MODEL,
                "x",
                "high",
                self.tmp,
                lambda _s: None,
                lambda _s: None,
                lambda _t: None,
                started,
                aux_budget=budget,
            )
        self.assertLess(time.monotonic() - prompt_phase_started[0], 2.0, result)
        self.assertLessEqual(budget.spent_s(), 54.0)
        self.assertEqual(result["exit_reason"], "timeout", result)

    def test_c10_rw004_tool_state_byte_cap_main_and_drain_cleanup(self) -> None:
        """RW-004 цикл 10: байтовый потолок tool_state в main и drain с cleanup."""
        main_fragment = """
            emit({"type":"session.execution.started","data":{"sessionID":sid}})
            emit({"type":"session.tool.input.started","data":{"sessionID":sid,"assistantMessageID":"m1","id":"big1","name":"bash"}})
            emit({"type":"session.tool.input.ended","data":{"sessionID":sid,"assistantMessageID":"m1","id":"big1","text":"x" * 400}})
            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0}}}})
            return
"""
        drain_fragment = """
            emit({"type":"session.execution.started","data":{"sessionID":sid}})
            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"c1","name":"bash","input":{"command":"pwd"}}})
            emit({"type":"session.tool.input.started","data":{"sessionID":sid,"assistantMessageID":"m1","id":"big2","name":"bash"}})
            emit({"type":"session.tool.input.ended","data":{"sessionID":sid,"assistantMessageID":"m1","id":"big2","text":"y" * 400}})
            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0}}}})
            return
"""
        for name, fragment, emulate in (
            ("main", main_fragment, False),
            ("drain", drain_fragment, True),
        ):
            with self.subTest(path=name):
                _ = Path(server.OPENCODE_BIN).write_text(
                    FAKE_SERVE.replace(
                        '            if "__native_pause__" in prompt:',
                        fragment + '            if "__native_pause__" in prompt:',
                    )
                )
                lease_cls = server._ServeLease  # pyright: ignore[reportPrivateUsage] — причина: проверяется обязательная уборка попытки
                cleanup = lease_cls.cleanup
                with (
                    mock.patch.object(server, "_MAX_SERVE_ACCUMULATED_BYTES", 128),
                    mock.patch.object(
                        lease_cls, "cleanup", autospec=True, side_effect=cleanup
                    ) as cleaned,
                ):
                    result = self.attempt("x", emulate_tools=emulate)
                self.assertEqual(result["exit_reason"], "invalid_serve_event", result)
                self.assertNotEqual(result["terminal"], "tool_calls", result)
                self.assertFalse(result["native_calls"], result)
                cleaned.assert_called_once()
                self.assertFalse(list(server.LEASE_DIR.glob("lease-*.json")))

    def test_c10_fu002_exhausted_aux_budget_starts_no_attempt(self) -> None:
        """FU-002 цикл 10: исчерпанный aux-бюджет не стартует spawn и повтор."""
        now = [100.0]
        budget = server._AuxIoBudget(  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватный aux-бюджет
            budget_s=10.0, clock_fn=lambda: now[0]
        )
        now[0] += 10.0
        budget.debit_elapsed(100.0)
        self.assertEqual(budget.remaining_s(), 0.0)

        def ignore(_text: str) -> None:
            return None

        def ignore_tool(_payload: dict[str, object]) -> None:
            return None

        with mock.patch.object(server, "_spawn_serve") as spawn:
            result = server._serve_one_attempt(  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватная попытка serve
                MODEL,
                "x",
                "high",
                self.tmp,
                ignore,
                ignore,
                ignore_tool,
                time.monotonic(),
                aux_budget=budget,
            )
        spawn.assert_not_called()
        self.assertEqual(result["exit_reason"], "timeout")
        res = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватный учёт попыток запроса
        attempts = server._RequestAttempts(res, time.monotonic() + 60.0)  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватный учёт попыток запроса
        attempts.aux_budget = budget
        attempts.note_spawn()
        self.assertFalse(attempts.allow_retry("aux_exhausted"))

    def test_c5_rw004_native_call_updates_last_token_at_no_premature_stall(
        self,
    ) -> None:
        """Cycle 5 RW-004: native-вызов обновляет начало окна stall."""
        with mock.patch.object(server, "STALL_TIMEOUT_S", 0.6):
            result = self.attempt("__native_pause__")
        self.assertTrue(result["native_calls"], result)
        self.assertEqual(result["terminal"], "succeeded", result)
        self.assertEqual(result["exit_reason"], "", result)

    def test_c5_fu002_prompt_401_headers_classified_before_hanging_body(self) -> None:
        """Cycle 5 FU-002: 401 классифицируется до чтения зависшего тела."""
        started = time.monotonic()
        with mock.patch.object(server, "FIRST_EVENT_TIMEOUT_S", 0.8):
            with self.assertRaises(server.ServeSecurityError):
                _ = self.attempt("__prompt_hang401__")
        self.assertLess(time.monotonic() - started, 3.0)

    def test_never_event_gives_first_event_timeout(self) -> None:
        """REQ-006: SSE без событий выполнения -> first_event_timeout."""
        with mock.patch.object(server, "FIRST_EVENT_TIMEOUT_S", 0.8):
            started = time.monotonic()
            result = self.attempt("__never_event__ x")
        self.assertEqual(result["exit_reason"], "first_event_timeout")
        self.assertLess(time.monotonic() - started, 8.0)

    def test_silent_model_gives_first_token_timeout(self) -> None:
        """REQ-007: события есть, токенов нет -> first_token_timeout."""
        with mock.patch.object(server, "FIRST_TOKEN_TIMEOUT_S", 0.8):
            result = self.attempt("__silent__ x")
        self.assertEqual(result["exit_reason"], "first_token_timeout")
        self.assertIs(result["delivered"], True)

    def test_stall_after_first_token(self) -> None:
        """REQ-007: пауза после первого токена -> stall_timeout."""
        reasoning: list[tuple[float, str]] = []
        with mock.patch.object(server, "STALL_TIMEOUT_S", 0.8):
            result = self.attempt("__stall__ x", reasoning=reasoning)
        self.assertEqual(result["exit_reason"], "stall_timeout")
        self.assertEqual([t for _at, t in reasoning], ["Первая мысль"])

    def test_sse_pause_over_half_second_keeps_stream_alive(self) -> None:
        """RW-008: пауза SSE 1.4 с не закрывает читатель и не даёт invalid_serve_event."""
        reasoning: list[tuple[float, str]] = []
        result = self.attempt("__slow__ x", reasoning=reasoning)
        self.assertEqual(result["exit_reason"], "")
        self.assertEqual(result["terminal"], "succeeded")
        self.assertEqual(
            "".join(t for _at, t in reasoning), "Мысль0 Мысль1 Мысль2 Мысль3 Мысль4 "
        )

    def test_startup_gate_released_before_generation_ends(self) -> None:
        """RW-014: замок старта отпускается по готовности serve, а не по концу генерации."""
        gate = server._StartupGate()  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
        gate.acquire()
        self.assertTrue(server._STARTUP_LOCK.locked())  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
        locked_during_tokens: list[bool] = []
        ready_calls: list[float] = []

        def on_ready() -> None:
            ready_calls.append(time.monotonic())
            gate.release()

        def on_token() -> None:
            locked_during_tokens.append(server._STARTUP_LOCK.locked())  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста

        reasoning: list[tuple[float, str]] = []
        try:
            result = self.attempt(
                "__slow__ x", reasoning=reasoning, on_ready=on_ready, on_token=on_token
            )
        finally:
            gate.release()
        self.assertEqual(result["terminal"], "succeeded")
        self.assertEqual(len(ready_calls), 1)
        self.assertLess(ready_calls[0], reasoning[0][0])
        self.assertEqual(len(locked_during_tokens), 5)
        self.assertFalse(any(locked_during_tokens))

    def test_prompt_http_4xx_fails_closed_fast(self) -> None:
        """RW-003: 400/404/422 prompt -> fail_closed быстрее FIRST_EVENT_TIMEOUT при пустом SSE."""
        for code in (400, 404, 422):
            with (
                self.subTest(code=code),
                mock.patch.object(server, "FIRST_EVENT_TIMEOUT_S", 20.0),
            ):
                started = time.monotonic()
                with self.assertRaises(server.ServeSecurityError):
                    _ = self.attempt(f"__prompt_status_{code}__ x")
                self.assertLess(time.monotonic() - started, 6.0)

    def test_text_tool_call_closes_step_on_step_finish(self) -> None:
        """RW-011: текстовый вызов инструмента закрывает шаг tool_calls при эмуляции."""
        emulated = self.attempt("__tool_text__ x", emulate_tools=True)
        self.assertEqual(emulated["terminal"], "tool_calls")
        plain = self.attempt("__tool_text__ x", emulate_tools=False)
        self.assertEqual(plain["terminal"], "succeeded")

    def test_attempt_rotates_proxy_pool_once(self) -> None:
        """RW-019: одна попытка serve сдвигает пул прокси ровно на один шаг."""
        with (
            mock.patch.object(
                server, "_next_standalone_proxy", return_value=None
            ) as rotate,
            mock.patch.object(
                server, "_spawn_serve", side_effect=server.ServeUnavailable("stop")
            ),
            self.assertRaises(server.ServeUnavailable),
        ):
            _ = self.attempt("x")
        self.assertEqual(rotate.call_count, 1)

    def test_c6_fu001_oversized_sse_line_is_terminal_invalid_event(self) -> None:
        """FU-001: читатель ограничивает строку до разбора JSON."""
        with mock.patch.object(server, "_MAX_SSE_LINE_BYTES", 32):
            result = self.attempt("x")
        self.assertEqual(result["exit_reason"], "invalid_serve_event")

    def test_c6_rw005_subscribe_deadline_and_disconnect_cleanup(self) -> None:
        """RW-005: отмена при капающих заголовках подписки возвращает терминальный результат."""
        body = FAKE_SERVE.replace(
            '        if self.path == "/api/event":',
            '        if self.path == "/api/event":\n            for i in range(1000):\n                self.wfile.write(b"x"); self.wfile.flush(); time.sleep(0.03)\n            return\n        if self.path == "/api/event":',
        )
        _ = Path(server.OPENCODE_BIN).write_text(body)
        for gone in (True, False):
            with self.subTest(gone=gone):
                start = time.monotonic()

                def ignore(_text: str) -> None:
                    return None

                def ignore_tool(_tool: dict[str, object]) -> None:
                    return None

                result = server._serve_one_attempt(  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватный API
                    MODEL,
                    "x",
                    "high",
                    self.tmp,
                    ignore,
                    ignore,
                    ignore_tool,
                    start,
                    deadline=start + 0.9,
                    is_client_gone=lambda: gone and time.monotonic() - start > 0.6,
                )
                self.assertEqual(
                    result["exit_reason"], "client_gone" if gone else "timeout"
                )
                self.assertIs(result["delivered"], True)
                self.assertLess(time.monotonic() - start, 2.0)
                self.assertFalse(list(server.LEASE_DIR.glob("lease-*.json")))


class TestSpawnAndLeaseOracles(_AttemptCase):
    """RW-004/RW-006/RW-015: атомарность старта, client_gone и бюджеты cleanup."""

    def _fd_count(self) -> int:
        return len(os.listdir("/dev/fd"))

    def test_spawn_failures_leave_no_leftovers(self) -> None:
        """RW-004: сбой Popen/pipe не оставляет FD, порт и каталог состояния."""
        for name, target in (("popen", "Popen"), ("pipe", "pipe")):
            with self.subTest(failure=name):
                env = server._serve_env(MODEL)  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
                state_dir = Path(env["XDG_STATE_HOME"])
                self.assertTrue(state_dir.is_dir())
                ports_before = set(server._ACTIVE_SERVE_PORTS)  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
                _ = gc.collect()
                fds_before = self._fd_count()
                owner = subprocess if name == "popen" else os
                with (
                    mock.patch.object(owner, target, side_effect=OSError(24, "boom")),
                    self.assertRaises(server.ServeUnavailable),
                ):
                    _ = server._spawn_serve("att_fail_" + name, env)  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
                self.assertFalse(state_dir.exists())
                self.assertEqual(set(server._ACTIVE_SERVE_PORTS), ports_before)  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
                self.assertLessEqual(self._fd_count(), fds_before)

    def test_lease_cleanup_confirms_sigkill_in_separate_window(self) -> None:
        """RW-015: группа, игнорирующая SIGTERM, добивается SIGKILL; lease удаляется после смерти."""
        script = (
            "import signal,time;signal.signal(signal.SIGTERM, signal.SIG_IGN);"
            "print('ready', flush=True);time.sleep(60)"
        )
        child: subprocess.Popen[str] = subprocess.Popen(
            [sys.executable, "-I", "-c", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            text=True,
        )
        assert child.stdout is not None
        ready_line = cast(str, child.stdout.readline())
        self.assertEqual(ready_line.strip(), "ready")
        lease_dir = self.tmp / "lease-cleanup"
        lease_dir.mkdir()
        lease_file = lease_dir / "lease-attC.json"
        _ = lease_file.write_text("{}", "utf-8")
        _read_fd, write_fd = os.pipe()
        os.close(_read_fd)
        lease = server._ServeLease(  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
            child, child.pid, child.pid, write_fd, lease_dir, "attC", ""
        )
        started = time.monotonic()
        lease.cleanup()
        elapsed = time.monotonic() - started
        with self.assertRaises(ProcessLookupError):
            os.killpg(child.pid, 0)
        self.assertFalse(lease_file.exists())
        self.assertGreaterEqual(elapsed, 3.9)
        # SIGKILL уходит ровно после 4.0 с окна SIGTERM, смерть группы подтверждается во втором окне.
        self.assertLessEqual(elapsed, 4.9)

    def test_client_gone_check_detects_reset_and_close(self) -> None:
        """RW-006: ECONNRESET, FIN и закрытый rfile — клиент ушёл; живой сокет — нет."""
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(2)
        addr = cast("tuple[str, int]", listener.getsockname())
        try:
            for mode in ("alive", "reset", "fin", "closed"):
                with self.subTest(mode=mode):
                    client = socket.create_connection(addr)
                    conn = listener.accept()[0]
                    handler = server.Handler.__new__(server.Handler)
                    handler.rfile = conn.makefile("rb")
                    try:
                        if mode == "reset":
                            client.setsockopt(
                                socket.SOL_SOCKET,
                                socket.SO_LINGER,
                                struct.pack("ii", 1, 0),
                            )
                            client.close()
                            time.sleep(0.1)
                        elif mode == "fin":
                            client.close()
                            time.sleep(0.1)
                        elif mode == "closed":
                            handler.rfile.close()
                        self.assertEqual(
                            handler._client_gone_check(),  # pyright: ignore[reportPrivateUsage] — причина: оракул проверяет приватный детектор ухода клиента
                            mode != "alive",
                        )
                    finally:
                        client.close()
                        conn.close()
        finally:
            listener.close()

    def test_c6_rw005_spawn_serve_respects_deadline_and_client_disconnect_without_run_fallback(
        self,
    ) -> None:
        """RW-005: отмена до Popen и во время handshake не становится ServeUnavailable."""
        for gone in (True, False):
            env = server._serve_env(MODEL)  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта
            with mock.patch.object(subprocess, "Popen") as popen:
                error = (
                    server.ServeClientDisconnect
                    if gone
                    else server.ServeStartupDeadlineExceeded
                )
                with self.assertRaises(error):
                    _ = server._spawn_serve(  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватный API
                        "cancel",
                        env,
                        deadline=time.monotonic() - 1,
                        is_client_gone=lambda: gone,
                    )
                popen.assert_not_called()
            self.assertFalse(Path(env["XDG_STATE_HOME"]).exists())
        _ = Path(server.OPENCODE_BIN).write_text(
            "#!/usr/bin/env python3\nimport time\ntime.sleep(30)\n"
        )
        for gone in (True, False):
            start = time.monotonic()
            env = server._serve_env(MODEL)  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта
            with self.assertRaises(
                server.ServeClientDisconnect
                if gone
                else server.ServeStartupDeadlineExceeded
            ):
                _ = server._spawn_serve(  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватный API
                    "handshake",
                    env,
                    deadline=start + 0.4,
                    is_client_gone=lambda: gone and time.monotonic() - start > 0.15,
                )
            self.assertLess(time.monotonic() - start, 2.0)
            self.assertFalse(Path(env["XDG_STATE_HOME"]).exists())
            self.assertFalse(list(server.LEASE_DIR.glob("lease-*.json")))

    def test_c6_rw006_spawn_serve_drains_multi_mib_stderr_before_bind_without_deadlock(
        self,
    ) -> None:
        """RW-006: два МиБ stderr без перевода строки до bind не блокируют helper."""
        body = FAKE_SERVE.replace('"x" * 70000 + "\\n"', '"x" * (2 * 1024 * 1024)')
        _ = Path(server.OPENCODE_BIN).write_text(body)
        env = server._serve_env(MODEL)  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта
        lease, _, _ = server._spawn_serve("large-stderr", env)  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта
        try:
            self.assertIsNone(lease.helper.poll())
            self.assertTrue(lease.stderr_tail)
            self.assertLessEqual(len(lease.stderr_tail), server._MAX_STDERR_TAIL_BYTES)  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта
        finally:
            lease.cleanup()
        self.assertFalse(server._pid_alive(-lease.pgid))  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта

    def test_c7_rw004_startup_http_phases_enforce_own_budget_under_long_request_deadline(
        self,
    ) -> None:
        """RW-004: капающие заголовки ограничены фазовым окном с обязательной уборкой группы."""
        for method, path, budget in (
            ("GET", "/api/session/active", 3.0),
            ("POST", "/api/session", 3.0),
            ("GET", "/api/event", 0.3),
        ):
            with self.subTest(path=path):
                drip = """
        if self.command==METHOD and self.path==TARGET:
            for _ in range(2000):
                self.wfile.write(b"x"); self.wfile.flush(); time.sleep(0.02)
            return
""".replace("METHOD", repr(method)).replace("TARGET", repr(path))
                body = FAKE_SERVE.replace(
                    "    def do_GET(self):", "    def do_GET(self):" + drip
                ).replace("    def do_POST(self):", "    def do_POST(self):" + drip)
                _ = Path(server.OPENCODE_BIN).write_text(body)
                leases: list[object] = []
                marks: list[float] = []
                spawn_original = cast(
                    "Callable[..., tuple[object, int, str]]",
                    getattr(server, "_spawn_serve"),
                )
                watch_original = cast(
                    "Callable[..., threading.Event]",
                    getattr(server, "_watch_serve_connection"),
                )

                def spawn(*args: object, **kwargs: object) -> tuple[object, int, str]:
                    result = spawn_original(*args, **kwargs)
                    leases.append(result[0])
                    return result

                def watch(
                    conn: http.client.HTTPConnection,
                    deadline: float | None,
                    gone: Callable[[], bool] | None,
                    socks: list[socket.socket | None],
                ) -> threading.Event:
                    if (path != "/api/event" and len(marks) < 2) or (
                        path == "/api/event" and len(marks) == 2
                    ):
                        self.assertIsNotNone(deadline)
                        self.assertLessEqual(
                            cast(float, deadline) - time.monotonic(), budget + 0.05
                        )
                    marks.append(time.monotonic())
                    return watch_original(conn, deadline, gone, socks)

                with (
                    mock.patch.object(server, "TIMEOUT_S", 30.0),
                    mock.patch.object(server, "FIRST_EVENT_TIMEOUT_S", 0.3),
                    mock.patch.object(server, "_spawn_serve", side_effect=spawn),
                    mock.patch.object(
                        server, "_watch_serve_connection", side_effect=watch
                    ),
                ):
                    started = time.monotonic()
                    with self.assertRaises(server.ServeUnavailable):
                        _ = self.attempt("x")
                self.assertLess(time.monotonic() - started, budget + 4.0)
                self.assertTrue(leases)
                self.assertTrue(cast(bool, getattr(leases[0], "_closed")))
                alive = cast("Callable[[int], bool]", getattr(server, "_pid_alive"))
                self.assertFalse(alive(-cast(int, getattr(leases[0], "pgid"))))

    def test_c6_rw007_fu003_dripping_interrupt_delete_still_cleans_up_under_7s(
        self,
    ) -> None:
        """AC-011: капающие заголовки и тела cleanup не задерживают смерть группы."""
        for phase in ("headers", "body"):
            with self.subTest(phase=phase):
                drip = """
        if self.path.endswith("/interrupt") or self.command=="DELETE":
            if PHASE=="body":
                self.send_response(200); self.send_header("Content-Length","1000"); self.end_headers(); self.wfile.flush()
            for i in range(1000):
                self.wfile.write(b"x"); self.wfile.flush(); time.sleep(0.03)
            return
""".replace("PHASE", repr(phase))
                body = FAKE_SERVE.replace(
                    '        if self.path == "/api/session/ses_test1/interrupt":',
                    drip
                    + '        if self.path == "/api/session/ses_test1/interrupt":',
                ).replace("    def do_DELETE(self):", "    def do_DELETE(self):" + drip)
                _ = Path(server.OPENCODE_BIN).write_text(body)
                cancelled = threading.Event()
                cancelled_at: list[float] = []

                def token(_text: str) -> None:
                    if not cancelled_at:
                        cancelled_at.append(time.monotonic())
                    cancelled.set()

                def ignore_tool(_tool: dict[str, object]) -> None:
                    return None

                leases: list[object] = []
                original = server._spawn_serve  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта

                def spawn(*args: object, **kwargs: object) -> object:
                    result = cast(
                        "tuple[object, int, str]",
                        cast("Callable[..., object]", original)(*args, **kwargs),
                    )
                    leases.append(result[0])
                    return result

                with mock.patch.object(server, "_spawn_serve", side_effect=spawn):
                    result = server._serve_one_attempt(  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватный API
                        MODEL,
                        "x",
                        "high",
                        self.tmp,
                        token,
                        token,
                        ignore_tool,
                        time.monotonic(),
                        is_client_gone=cancelled.is_set,
                    )
                self.assertTrue(cancelled_at)
                self.assertLess(time.monotonic() - cancelled_at[0], 7.0)
                self.assertEqual(result["exit_reason"], "client_gone")
                self.assertFalse(
                    server._pid_alive(-cast(int, getattr(leases[0], "pgid")))  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватный API
                )


FAKE_HELPER_SERVE = """#!/bin/sh
trap '' TERM
sleep 120 &
echo $! > "$GRANDCHILD_FILE"
exit 0
"""


class TestCycle6HttpBounds(unittest.TestCase):
    """Локальный TCP-апстрим для абсолютного HTTP-дедлайна и байтовых пределов."""

    def _peer(
        self, payload: bytes, drip: bool = False, hold_body: bool = False
    ) -> tuple[socket.socket, threading.Thread, threading.Event, int]:
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(2)
        port = cast("tuple[str, int]", listener.getsockname())[1]
        stop = threading.Event()

        def send() -> None:
            try:
                conn = listener.accept()[0]
                with conn:
                    _ = conn.recv(65536)
                    if hold_body:
                        conn.sendall(payload)
                        _ = stop.wait(2.0)
                    elif drip:
                        headers, separator, body = payload.partition(b"\r\n\r\n")
                        stream = payload
                        if separator:
                            conn.sendall(headers + separator)
                            stream = body
                        for byte in stream:
                            if stop.wait(0.02):
                                break
                            conn.sendall(bytes([byte]))
                    else:
                        conn.sendall(payload)
            except OSError:
                return

        thread = threading.Thread(target=send, daemon=True)
        thread.start()
        return listener, thread, stop, port

    def test_c6_rw007_absolute_deadline_interrupts_dripping_headers_and_body(
        self,
    ) -> None:
        """RW-007: каждый байт приходит до socket timeout, но абсолютный deadline обязателен."""
        for payload in (
            b"HTTP/1.1 200 OK\r\nX-Slow: " + b"x" * 200,
            b"HTTP/1.1 200 OK\r\nContent-Length: 1000\r\n\r\n" + b"x" * 1000,
        ):
            listener, thread, stop, port = self._peer(payload, True)
            try:
                start = time.monotonic()
                with self.assertRaises((OSError, http.client.HTTPException)):
                    _ = server._serve_http(  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватный API
                        port, "", "GET", "/", timeout=0.1, deadline=start + 0.25
                    )
                self.assertLess(time.monotonic() - start, 0.7)
            finally:
                stop.set()
                listener.close()
                thread.join(1)

    def test_c6_rw007_skip_body_returns_immediately_after_headers(self) -> None:
        """RW-007: cleanup не вычитывает даже отсутствующее тело с Content-Length."""
        call = server._serve_http  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватный cleanup-контракт
        for method in ("POST", "DELETE"):
            listener, thread, stop, port = self._peer(
                b"HTTP/1.1 200 OK\r\nContent-Length: 1000\r\n\r\n", hold_body=True
            )
            try:
                started = time.monotonic()
                status, body = call(
                    port,
                    "",
                    method,
                    "/",
                    timeout=0.4,
                    deadline=started + 0.8,
                    skip_body=True,
                )
                self.assertEqual((status, body), (200, {}))
                self.assertLess(time.monotonic() - started, 0.3)
            finally:
                stop.set()
                listener.close()
                thread.join(1)

    def test_c6_fu001_fu002_sse_line_body_byte_caps_and_strict_usage_ints(self) -> None:
        """FU-001/002: точные байтовые пределы и запрет bool/отрицательных токенов."""
        self.assertEqual(server._MAX_SSE_LINE_BYTES, 1024 * 1024)  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта
        self.assertEqual(server._MAX_SERVE_HTTP_BODY_BYTES, 8 * 1024 * 1024)  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта
        for key in ("input", "output", "reasoning", "read"):
            for value in (True, -1):
                tokens: dict[str, object] = {
                    "input": 1,
                    "output": 1,
                    "reasoning": 0,
                    "cache": {"read": 0},
                }
                if key == "read":
                    tokens["cache"] = {"read": value}
                else:
                    tokens[key] = value
                with (
                    self.subTest(key=key, value=value),
                    self.assertRaises(server.ServeProtocolError),
                ):
                    _ = server._map_serve_event(  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватный API
                        {
                            "type": "session.step.ended",
                            "data": {"sessionID": "s", "tokens": tokens},
                        }
                    )
        listener, thread, stop, port = self._peer(
            b"HTTP/1.1 200 OK\r\nContent-Length: 1024\r\n\r\n" + b"x" * 1024
        )
        try:
            with (
                mock.patch.object(server, "_MAX_SERVE_HTTP_BODY_BYTES", 32),
                self.assertRaises(server.ServeProtocolError),
            ):
                _ = server._serve_http(port, "", "GET", "/")  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта
        finally:
            stop.set()
            listener.close()
            thread.join(1)


class TestHelperProcess(unittest.TestCase):
    """RW-001/RW-005: процесс --serve-helper (errno до ветки helper, добивание группы)."""

    def _helper_cmd(self, tmp: Path, bin_path: str) -> list[str]:
        return [
            sys.executable,
            "-I",
            str(Path(server.__file__).resolve()),
            "--serve-helper",
            "attemptH",
            "43211",
            bin_path,
            str(tmp / "leases"),
            str(os.getpid()),
            "Mon Jan  1 00:00:00 2024",
        ]

    def test_errno_imported_before_helper_branch(self) -> None:
        """RW-001: errno связан до ветки --serve-helper."""
        tree = ast.parse(Path(server.__file__).read_text("utf-8"))
        branch = next(
            n
            for n in tree.body
            if isinstance(n, ast.If)
            and ast.unparse(n.test).endswith("['--serve-helper']")
        )
        early = {
            a.name
            for n in tree.body[: tree.body.index(branch)]
            if isinstance(n, ast.Import)
            for a in n.names
        }
        self.assertIn("errno", early)

    def test_helper_survives_bad_stdin_without_name_error(self) -> None:
        """RW-001: EBADF на select lifeline обрабатывается без NameError, lease снимается."""
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            argv = " ".join(f"'{a}'" for a in self._helper_cmd(tmp, "/bin/true"))
            proc = subprocess.run(
                ["/bin/sh", "-c", f"exec {argv} <&-"],
                capture_output=True,
                text=True,
                timeout=20,
                start_new_session=True,
            )
            self.assertNotIn("NameError", proc.stderr)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(list((tmp / "leases").glob("lease-*.json")), [])

    def test_helper_kills_surviving_group_and_removes_lease_last(self) -> None:
        """RW-005: serve вышел, внук игнорирует SIGTERM -> SIGKILL группе, lease удалён после смерти."""
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            fake = _write_exe(tmp, "opencode-fake", FAKE_HELPER_SERVE)
            gc_file = tmp / "grandchild.pid"
            env = dict(os.environ)
            env["GRANDCHILD_FILE"] = str(gc_file)
            proc = subprocess.Popen(
                self._helper_cmd(tmp, str(fake)),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                start_new_session=True,
            )
            try:
                # lifeline (stdin) остаётся открытым: helper завершается сам, когда serve вышел.
                _ = proc.wait(timeout=30)
            finally:
                if proc.poll() is None:
                    proc.kill()
                if proc.stdin is not None:
                    proc.stdin.close()
                for stream in (proc.stdout, proc.stderr):
                    if stream is not None:
                        stream.close()
            self.assertEqual(proc.returncode, 0)
            grandchild = int(gc_file.read_text("utf-8").strip())
            deadline = time.monotonic() + 3.0
            alive = True
            while alive and time.monotonic() < deadline:
                try:
                    os.kill(grandchild, 0)
                    time.sleep(0.05)
                except ProcessLookupError:
                    alive = False
            if alive:
                os.kill(grandchild, signal.SIGKILL)
            self.assertFalse(alive, "внук группы пережил helper")
            self.assertEqual(list((tmp / "leases").glob("lease-*.json")), [])


if __name__ == "__main__":
    unittest.main()  # pyright: ignore[reportUnusedCallResult] — причина: результат вызова в тесте не используется
