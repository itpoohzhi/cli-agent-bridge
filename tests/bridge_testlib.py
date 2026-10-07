"""Общая библиотека тестов моста droid-bridge (не собирается как тесты).

Фейковый Run, базовый HTTP-класс на свободном порту и сборщики запросов к
image-пути. Сеть — только петлевой сокет тестового сервера; droid и лончер
не вызываются (кроме отдельного теста с локальной заглушкой лончера в tmp).
"""

import base64
import copy
import http.client
import json
import socket
import sys
import tempfile
import threading
import time
import types
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


class FakeRun:
    """Заглушка Run: сценарии событий раздаются по одному на попытку."""

    scripts = []
    instances = []

    def __init__(self, prompt, model, effort, effort_source,
                 autonomy, autonomy_source, cwd, tag,
                 img_dir=None, img_stats=None, sess_sid=""):
        self.sess_sid = sess_sid
        self.prompt = prompt
        self.model = model
        self.effort = effort
        self.effort_source = effort_source
        self.autonomy = autonomy
        self.autonomy_source = autonomy_source
        self.cwd = cwd
        self.tag = tag
        self.img_dir = img_dir
        self.img_stats = img_stats
        self.img_snapshot = self._snapshot(img_dir)
        self.events = list(type(self).scripts.pop(0)) if type(self).scripts else [
            ("text", "PONG"), ("result", {"finalText": "", "usage": {}}), ("done", (0, ""))]
        self.q = server.queue.Queue()
        self.err_box = [""]
        self.proc = types.SimpleNamespace(pid=-1, poll=lambda: 0,
                                          stdout=None, stderr=None)
        self.got_event = False
        self.started = time.monotonic()
        self.closed = False
        for ev in self.events:
            if ev[0] == "stderr":  # ("stderr", text) -> err_box, как дренаж stderr
                self.err_box.append(ev[1])
            else:
                self.q.put(ev)
        type(self).instances.append(self)

    @staticmethod
    def _snapshot(img_dir):
        if img_dir is None:
            return None
        path = Path(img_dir)
        snapshot = {"dir": str(path), "dir_mode": "", "files": {}}
        if path.exists():
            snapshot["dir_mode"] = oct(path.stat().st_mode & 0o777)
            for item in sorted(path.iterdir()):
                snapshot["files"][item.name] = oct(item.stat().st_mode & 0o777)
        return snapshot

    def close(self):
        self.closed = True


class BoomRun(FakeRun):
    """Run, падающий на старте (исключение при создании процесса)."""

    def __init__(self, *args, **kwargs):
        raise OSError("boom")


class BridgeCase(unittest.TestCase):
    """Сервер на свободном порту с подменённым Run и временным workspace."""

    def setUp(self):
        FakeRun.scripts = []
        FakeRun.instances = []
        self._real_run = server.Run
        self._real_key = server.AUTH_KEY
        self._real_workspace = server.WORKSPACE
        self._real_fleet = server.FLEET
        self._real_probe = server.IMAGE_PROBE
        self._real_launcher = server.LAUNCHER
        self._real_budget = server._budget
        self._real_model_id = server.MODEL_ID
        server.Run = FakeRun
        server.AUTH_KEY = "test-key"
        self._tmp = tempfile.TemporaryDirectory()
        server.WORKSPACE = Path(self._tmp.name) / "workspace"
        server.WORKSPACE.mkdir(parents=True, exist_ok=True)
        server._budget = None
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        server.Run = self._real_run
        server.AUTH_KEY = self._real_key
        server.WORKSPACE = self._real_workspace
        server.FLEET = self._real_fleet
        server.IMAGE_PROBE = self._real_probe
        server.LAUNCHER = self._real_launcher
        server._budget = self._real_budget
        server.MODEL_ID = self._real_model_id
        self._tmp.cleanup()

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
