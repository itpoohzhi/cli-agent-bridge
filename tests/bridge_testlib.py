"""Общая библиотека тестов моста droid-bridge (не собирается как тесты).

Фейковый droid (настоящий subprocess со stream-jsonrpc, tests/fake_droid.py) и
его хаб, базовый HTTP-класс на свободном порту и сборщики запросов к image-пути.
Сеть — только петлевой сокет тестового сервера; реальный droid не вызывается.
"""

import base64
import copy
import http.client
import json
import os
import socket
import sys
import tempfile
import threading
import time
import unittest

from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402

TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get current weather",
        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}},
    },
}]

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff\xe0"
GIF_MAGIC = b"GIF89a"
WEBP_MAGIC = b"RIFF\x00\x00\x00\x00WEBPVP8 "


def make_png(size=64):
    """PNG-подобные байты (сигнатура + нули) заданного размера."""
    return PNG_MAGIC + b"\x00" * max(0, size - len(PNG_MAGIC))


def make_sig(magic, size=64):
    return magic + b"\x00" * max(0, size - len(magic))


def data_url(raw, mime="image/png"):
    return "data:%s;base64,%s" % (mime, base64.b64encode(raw).decode())


def text_part(text):
    return {"type": "text", "text": text}


def image_part(raw, mime="image/png"):
    return {"type": "image_url", "image_url": {"url": data_url(raw, mime)}}


def image_url_part(url):
    return {"type": "image_url", "image_url": {"url": url}}


def chat_body(model=None, effort=None, content=None, messages=None, **extra):
    body = {"messages": messages if messages is not None else [
        {"role": "user", "content": content if content is not None else "hi"}]}
    if model is not None:
        body["model"] = model
    if effort is not None:
        body["reasoning_effort"] = effort
    body.update(extra)
    return body


def load_raw_fleet():
    """Сырой JSON каталога (без нормализации) для сборки стендовых каталогов."""
    return json.loads(Path(server.FLEET_PATH).read_text(encoding="utf-8"))


def find_model(data, model_id):
    for item in data["models"]:
        if item["id"] == model_id:
            return item
    raise KeyError(model_id)


def make_proof(binary_path, efforts_proven, impl_version=1, method="workspace-read",
               formats=("image/png",), droid_version="0.0.0-test"):
    import hashlib
    digest = hashlib.sha256(Path(binary_path).read_bytes()).hexdigest()
    return {
        "droid_version": droid_version,
        "droid_binary_sha256": digest,
        "method": method,
        "impl_version": impl_version,
        "formats": list(formats),
        "efforts_proven": list(efforts_proven),
        "verified_at": "test",
        "census_sha256": "0" * 64,
        "census_ref": "test",
    }


FAKE_DROID = Path(__file__).resolve().parent / "fake_droid.py"
TEST_FACTORY_KEY = "bridge-test-factory-key-not-real"  # то же значение, что ждёт fake_droid
_MISSING = object()


def legacy_scenario(events):
    """Старый сценарий FakeRun (text/reasoning/result/stderr/done) -> сценарий fake_droid."""
    steps = []
    usage = {}
    silent = not events
    for ev in events:
        kind = ev[0]
        if kind == "text":
            steps.append({"op": "text", "text": ev[1]})
        elif kind == "reasoning":
            steps.append({"op": "thinking", "text": ev[1]})
        elif kind == "result":
            raw = (ev[1] or {}).get("usage") or {}
            usage = {"inputTokens": raw.get("input_tokens", 0), "outputTokens": raw.get("output_tokens", 0)}
        elif kind == "stderr":
            steps.append({"op": "exit", "rc": 1, "stderr": ev[1]})
        elif kind == "done" and ev[1][0] != 0 and not any(s["op"] == "exit" for s in steps):
            steps.append({"op": "exit", "rc": ev[1][0]})
    if silent:
        steps.append({"op": "hang"})
    return {"steps": steps, "usage": usage}


class FakeDroidHub:
    """Каталог управления fake_droid: конфиг, очередь сценариев, журнал процессов."""

    def __init__(self, base):
        self.base = Path(base)
        self.base.mkdir(parents=True, exist_ok=True)
        self.config = {}
        self.launcher = self.base / "fake-launcher"
        self.launcher.write_text(
            "#!%s\nimport sys\nsys.path.insert(0, %r)\nimport fake_droid\nfake_droid.main(sys.argv[1:])\n"
            % (sys.executable, str(FAKE_DROID.parent)), encoding="utf-8")
        self.launcher.chmod(0o755)
        self._flush()

    def _flush(self):
        (self.base / "config.json").write_text(json.dumps(self.config), encoding="utf-8")

    def configure(self, **cfg):
        self.config.update(cfg)
        self._flush()

    def script(self, scenarios):
        """Добавить сценарии ходов (по одному на запущенный цикл, глобально по очереди)."""
        scripted = self.config.setdefault("scenarios", [])
        counter = self.base / "turn.counter"
        claimed = int(counter.read_text() or 0) if counter.exists() else 0
        while len(scripted) < claimed:  # ходы без сценария уже взяли значение по умолчанию
            scripted.append(None)
        scripted.extend(scenarios)
        self._flush()

    def legacy(self, scripts):
        self.script([legacy_scenario(ev) for ev in scripts])

    def records(self):
        path = self.base / "log.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def spawns(self):
        return [r for r in self.records() if r["ev"] == "spawn"]

    def rpcs(self, method=None):
        return [r for r in self.records() if r["ev"] == "rpc" and (method is None or r["method"] == method)]

    def admissions(self):
        """Принятые циклы agent loop (add_user_message без skipAgentLoop): аналог Run.instances."""
        return [r for r in self.rpcs("droid.add_user_message") if not r["params"].get("skipAgentLoop")]

    def inits(self):
        return self.rpcs("droid.initialize_session")

    def sent_texts(self):
        return [r["params"].get("text", "") for r in self.rpcs("droid.add_user_message")]

    def exits(self):
        return [r for r in self.records() if r["ev"] == "exit"]


def wait_until(predicate, timeout=10.0, step=0.05):
    """Ждать условие (закрытие процессов асинхронно)."""
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return True
        time.sleep(step)
    return predicate()


def pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class BridgeCase(unittest.TestCase):
    """Сервер на свободном порту с подменённым Run и временным workspace."""

    def setUp(self):
        self._saved = {name: getattr(server, name, _MISSING) for name in (
            "AUTH_KEY", "WORKSPACE", "FLEET", "IMAGE_PROBE", "LAUNCHER", "_budget", "MODEL_ID",
            "_sleep", "INTERRUPT_GRACE_S", "RPC_CALL_TIMEOUT_S", "SILENCE_WATCHDOG_S",
            "FIRST_TOKEN_TIMEOUT_S", "TIMEOUT_S", "_clock", "IDLE_SECONDS", "RECEIPT_REQUIRED",
            "MAX_RPC_LINE_BYTES", "MAX_STDERR_BYTES", "MAX_INBOX_BYTES", "MAX_TURN_TEXT_BYTES",
            "MAX_CHATS", "MAX_CONCURRENT", "INSTR_BLOCK_LIMIT")}
        # Реальный FACTORY_API_KEY рабочего окружения в тестах не используется: подставляем
        # фиктивный sentinel; восстановление через addCleanup срабатывает и при падении теста.
        self._env_factory_key = os.environ.get("FACTORY_API_KEY")
        self.addCleanup(self._restore_factory_key)
        os.environ["FACTORY_API_KEY"] = TEST_FACTORY_KEY
        self._env_fake = os.environ.get("FAKE_DROID_DIR")
        self._tmp = tempfile.TemporaryDirectory()
        self.hub = FakeDroidHub(Path(self._tmp.name) / "fake")
        os.environ["FAKE_DROID_DIR"] = str(self.hub.base)
        server.LAUNCHER = str(self.hub.launcher)
        server.AUTH_KEY = "test-key"
        server.WORKSPACE = Path(self._tmp.name) / "workspace"
        server.WORKSPACE.mkdir(parents=True, exist_ok=True)
        server._budget = None
        server.RECEIPT_REQUIRED = False  # receipt квалификации образа: отдельные тесты RW-007 включают
        server._sleep = lambda _seconds: None  # ретраи 2/4 с — без реального ожидания
        server.INTERRUPT_GRACE_S = 1.0
        server._reset_rpc_state()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        server._reset_rpc_state()
        for name, value in self._saved.items():
            if value is _MISSING:
                if hasattr(server, name):
                    delattr(server, name)
            else:
                setattr(server, name, value)
        if self._env_fake is None:
            os.environ.pop("FAKE_DROID_DIR", None)
        else:
            os.environ["FAKE_DROID_DIR"] = self._env_fake
        self._tmp.cleanup()

    def _restore_factory_key(self):
        if self._env_factory_key is None:
            os.environ.pop("FACTORY_API_KEY", None)
        else:
            os.environ["FACTORY_API_KEY"] = self._env_factory_key

    # -- helpers ----------------------------------------------------------------
    def _post(self, body: dict, timeout: float = 60.0):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            conn.request("POST", "/v1/chat/completions",
                         body=json.dumps(body),
                         headers={"Authorization": "Bearer test-key",
                                  "Content-Type": "application/json"})
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8")
            return resp.status, raw
        finally:
            conn.close()

    def _post_json(self, body: dict, timeout: float = 60.0):
        status, raw = self._post(body, timeout=timeout)
        return status, (json.loads(raw) if raw else None)

    def _get(self, path: str, auth: bool = True):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            headers = {"Authorization": "Bearer test-key"} if auth else {}
            conn.request("GET", path, headers=headers)
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw else None)
        finally:
            conn.close()

    def _raw_exchange(self, raw: bytes, half_close: bool = False, limit: float = 5.0):
        """Сырой обмен: (буфер ответа, закрыто ли соединение сервером)."""
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=limit)
        try:
            sock.sendall(raw)
            if half_close:
                try:
                    sock.shutdown(socket.SHUT_WR)
                except OSError:
                    pass
            buf, closed, started = b"", False, time.time()
            while time.time() - started < limit:
                try:
                    chunk = sock.recv(65536)
                except socket.timeout:
                    break
                except OSError:
                    closed = True
                    break
                if not chunk:
                    closed = True
                    break
                buf += chunk
            return buf, closed
        finally:
            sock.close()

    @staticmethod
    def _raw_request(body: bytes = b"", cl="auto", extra=(), auth=True, path="/v1/chat/completions"):
        headers = [f"POST {path} HTTP/1.1", "Host: 127.0.0.1",
                   "Content-Type: application/json"]
        if auth:
            headers.append("Authorization: Bearer test-key")
        if cl == "auto":
            headers.append("Content-Length: %d" % len(body))
        elif cl is not None:
            headers.append("Content-Length: " + str(cl))
        headers.extend(extra)
        return ("\r\n".join(headers) + "\r\n\r\n").encode() + body

    @staticmethod
    def _raw_parse(buf: bytes):
        """(код, тип ошибки, число ответов) из буфера сырого обмена."""
        count = buf.count(b"HTTP/1.1 ")
        code = int(buf[9:12]) if buf.startswith(b"HTTP/1.1 ") else 0
        typ = "-"
        if b"\r\n\r\n" in buf:
            body = buf.split(b"\r\n\r\n", 1)[1]
            try:
                err = json.loads(body.decode("utf-8", "replace").split("HTTP/1.1")[0])["error"]
                if sorted(err) == ["code", "message", "type"] and err.get("code") == code:
                    typ = err.get("type", "-")
                else:
                    typ = "BADFORM"
            except Exception:  # noqa: BLE001 - диагностический разбор теста
                typ = "BADBODY"
        return code, typ, count

    @contextmanager
    def capture_logs(self):
        lines = []
        real_log = server._log
        server._log = lambda message: lines.append(str(message))
        try:
            yield lines
        finally:
            server._log = real_log

    def stand(self, mutate, probe: bool = False):
        """Стендовый каталог из живого fleet.json (копия + мутация)."""
        data = copy.deepcopy(load_raw_fleet())
        if probe:
            server.IMAGE_PROBE = True
        mutate(data)
        catalog = server._build_catalog(data)
        server.FLEET = catalog
        return catalog
