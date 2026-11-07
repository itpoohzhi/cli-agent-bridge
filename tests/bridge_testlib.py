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

from typing import Any, cast
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from core.model_penalty import ModelPenaltyTracker  # noqa: E402
from droid_test_helpers import apply_stand_efforts, make_receipt  # noqa: E402,F401  # tests/ — корень импорта pytest

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
            },
        },
    }
]

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
    body = {
        "messages": messages
        if messages is not None
        else [{"role": "user", "content": content if content is not None else "hi"}]
    }
    if model is not None:
        body["model"] = model
    if effort is not None:
        body["reasoning_effort"] = effort
    body.update(extra)
    return body


def load_raw_fleet():
    """Сырой JSON каталога (без нормализации) для сборки стендовых каталогов."""
    return json.loads(Path(server.FLEET_PATH).read_text(encoding="utf-8"))


# Модели, которые стенд FakeDroid обслуживает через бэкенд droid (боевой fleet.json
# переведён на единый мост :9882, Droid там выключен).
_DROID_STAND_MODELS = ("claude-sonnet-5-5", "deepseek-v4.1-flash", "gemini-3.8-flash")
_DROID_LEGACY_MODELS = (
    {
        "id": "grok-4.7",
        "backend": "droid",
        "name": "Grok 4.7 (Droid test stand)",
        "efforts": ["high"],
        "default_effort": "high",
        "context_window": 256000,
        "max_tokens": 32768,
        "input": ["text"],
        "images": {
            "cli_registry": "explicit_supported",
            "status": "unverified",
            "method": None,
            "proof": None,
        },
    },
    {
        "id": "glm-5.3",
        "backend": "droid",
        "name": "GLM-5.3 (Droid test stand)",
        "efforts": ["max"],
        "default_effort": "max",
        "context_window": 1000000,
        "max_tokens": 131072,
        "input": ["text"],
        "images": {
            "cli_registry": "explicit_unsupported",
            "status": "unsupported",
            "method": None,
            "proof": None,
        },
    },
)


_ORIG_CONTEXT_MAX_OUTPUT = server._context_max_output


def _stand_context_max_output(model_id: str) -> int:
    """max_tokens стендовых legacy-моделей (в боевом fleet.json их уже нет)."""
    for legacy in _DROID_LEGACY_MODELS:
        if legacy["id"] == model_id:
            return cast(int, legacy["max_tokens"])
    return _ORIG_CONTEXT_MAX_OUTPUT(model_id)


def droidify_raw_fleet(data):
    """Сырой каталог -> стенд FakeDroid: droid включён, тестовые модели на droid."""
    data["backends"]["droid"]["enabled"] = True
    present = {m["id"] for m in data["models"]}
    for m in data["models"]:
        if m["id"] in _DROID_STAND_MODELS:
            m["backend"] = "droid"
        apply_stand_efforts(m)
    for legacy in _DROID_LEGACY_MODELS:
        if legacy["id"] not in present:
            data["models"].append(copy.deepcopy(legacy))
    return data


def install_droid_stand(data=None):
    """Собрать стендовый каталог и пересоздать server.BACKENDS под него."""
    if data is None:
        data = droidify_raw_fleet(load_raw_fleet())
    catalog = server._build_catalog(data)
    for key in ("path", "sha256"):  # метаданные загрузки живого fleet.json
        if key in server.FLEET:
            catalog.setdefault(key, server.FLEET[key])
    server.FLEET = catalog
    server._context_max_output = _stand_context_max_output
    server.BACKENDS = server.AdapterRegistry.from_fleet(
        server.FLEET, server.ADAPTER_KINDS, lambda: server.FLEET, server
    )
    return server.FLEET


def find_model(data, model_id):
    for item in data["models"]:
        if item["id"] == model_id:
            return item
    raise KeyError(model_id)


def make_proof(
    binary_path,
    efforts_proven,
    impl_version=1,
    method="workspace-read",
    formats=("image/png",),
    droid_version="0.0.0-test",
):
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
TEST_FACTORY_KEY = (
    "bridge-test-factory-key-not-real"  # то же значение, что ждёт fake_droid
)
_MISSING = object()
# Сценарии отказа внутри одного теста копят провалы старта: карантин 503 в стенде не включается.
TEST_MAX_START_FAILS = 1_000_000


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
            usage = {
                "inputTokens": raw.get("input_tokens", 0),
                "outputTokens": raw.get("output_tokens", 0),
            }
        elif kind == "stderr":
            steps.append({"op": "exit", "rc": 1, "stderr": ev[1]})
        elif (
            kind == "done"
            and ev[1][0] != 0
            and not any(s["op"] == "exit" for s in steps)
        ):
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
            % (sys.executable, str(FAKE_DROID.parent)),
            encoding="utf-8",
        )
        self.launcher.chmod(0o755)
        self._flush()

    def _flush(self):
        (self.base / "config.json").write_text(
            json.dumps(self.config), encoding="utf-8"
        )

    def configure(self, **cfg):
        self.config.update(cfg)
        self._flush()

    def script(self, scenarios):
        """Добавить сценарии ходов (по одному на запущенный цикл, глобально по очереди)."""
        scripted = self.config.setdefault("scenarios", [])
        counter = self.base / "turn.counter"
        claimed = int(counter.read_text() or 0) if counter.exists() else 0
        while (
            len(scripted) < claimed
        ):  # ходы без сценария уже взяли значение по умолчанию
            scripted.append(None)
        scripted.extend(scenarios)
        self._flush()

    def legacy(self, scripts):
        self.script([legacy_scenario(ev) for ev in scripts])

    def records(self):
        path = self.base / "log.jsonl"
        if not path.exists():
            return []
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def spawns(self):
        return [r for r in self.records() if r["ev"] == "spawn"]

    def rpcs(self, method=None):
        return [
            r
            for r in self.records()
            if r["ev"] == "rpc" and (method is None or r["method"] == method)
        ]

    def admissions(self):
        """Принятые циклы agent loop (add_user_message без skipAgentLoop): аналог Run.instances."""
        return [
            r
            for r in self.rpcs("droid.add_user_message")
            if not r["params"].get("skipAgentLoop")
        ]

    def inits(self):
        return self.rpcs("droid.initialize_session")

    def sent_texts(self):
        return [
            r["params"].get("text", "") for r in self.rpcs("droid.add_user_message")
        ]

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

    _saved: dict[str, Any] = {}
    _env_factory_key: str | None = None
    _env_fake: str | None = None
    _tmp: Any = None
    hub: Any = None
    upstream: Any = None  # стенд fake-upstream подклассов
    httpd: Any = None
    port = 0

    def setUp(self):
        self._saved = {
            name: getattr(server, name, _MISSING)
            for name in (
                "AUTH_KEY", "TOKEN_CACHE", "WORKSPACE", "FLEET", "IMAGE_PROBE", "LAUNCHER",
                "_budget", "MODEL_ID", "_sleep", "INTERRUPT_GRACE_S", "RPC_CALL_TIMEOUT_S",
                "SILENCE_WATCHDOG_S", "FIRST_TOKEN_TIMEOUT_S", "TIMEOUT_S", "_clock",
                "IDLE_SECONDS", "RECEIPT_REQUIRED", "MAX_RPC_LINE_BYTES", "MAX_STDERR_BYTES",
                "MAX_INBOX_BYTES", "MAX_TURN_TEXT_BYTES", "MAX_CHATS", "MAX_CONCURRENT",
                "INSTR_BLOCK_LIMIT", "FINISHED_TURNS_KEEP", "DELIVERY_CHUNK_BYTES",
                "ENTRY_OVERHEAD_BYTES", "GUARD", "GUARD_PROFILES_DIR", "GUARD_CANON",
                "INSTR_NONKB_MARGIN", "MAX_JSON_STRUCT_TOKENS", "BACKENDS",
                "_context_max_output", "_PENALTY_TRACKER", "_MODEL_NOTES_FILTER",
            )
        }
        server._canon_seen.clear()
        # Реальный FACTORY_API_KEY рабочего окружения в тестах не используется: подставляем
        # фиктивный sentinel; восстановление через addCleanup срабатывает и при падении теста.
        self._env_factory_key = os.environ.get("FACTORY_API_KEY")
        self.addCleanup(self._restore_env, "FACTORY_API_KEY", self._env_factory_key)
        os.environ["FACTORY_API_KEY"] = TEST_FACTORY_KEY
        self._env_fake = os.environ.get("FAKE_DROID_DIR")
        self._tmp = tempfile.TemporaryDirectory()
        self.hub = FakeDroidHub(Path(self._tmp.name) / "fake")
        self.addCleanup(self._restore_env, "FAKE_DROID_DIR", self._env_fake)
        os.environ["FAKE_DROID_DIR"] = str(self.hub.base)
        self._isolate_runtime()
        server.LAUNCHER = str(self.hub.launcher)
        server.AUTH_KEY = "test-key"
        server.TOKEN_CACHE = server.TokenCache(
            path=Path(self._tmp.name) / ".env",
            environ={"BRIDGE_KEY": "test-key"},
        )
        server.WORKSPACE = Path(self._tmp.name) / "workspace"
        server.WORKSPACE.mkdir(parents=True, exist_ok=True)
        server._budget = None
        # Охранник B: реальные профили/канон владельца в тестах не читаются (пустые пути под tmp).
        if hasattr(server, "InstructionGuard"):
            server.GUARD = server.InstructionGuard()
            server.GUARD_PROFILES_DIR = str(Path(self._tmp.name) / "profiles-none")
            server.GUARD_CANON = str(Path(self._tmp.name) / "canon-none.md")
            server._canon_cache.update(key=None, digest="")
        # Предел блока KB (ADR 0015: боевое умолчание 100 000 Б): сценарии отказа RW-009/RW-014
        # проверяют границу 60 000 Б, поэтому предел фиксируется явно, а не берётся из окружения.
        server.INSTR_BLOCK_LIMIT = 60000
        server.RECEIPT_REQUIRED = (
            False  # receipt квалификации образа: отдельные тесты RW-007 включают
        )
        server._sleep = lambda _seconds: None  # ретраи 2/4 с — без реального ожидания
        server.INTERRUPT_GRACE_S = 1.0
        server._reset_rpc_state()
        install_droid_stand()
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
        self._tmp.cleanup()

    def _isolate_runtime(self) -> None:
        """Штрафы старта, model-notes и динамический конфиг — только в границах теста.

        Иначе инъекция сбоя старта штрафует модель следующим тестам и пишет боевой
        model_penalties.json, а флаги GigaRC меняют поведение запросов.
        """
        tmp = Path(self._tmp.name)
        self.addCleanup(
            self._restore_env,
            "BRIDGE_DYNAMIC_CONFIG_PATH",
            os.environ.get("BRIDGE_DYNAMIC_CONFIG_PATH"),
        )
        os.environ["BRIDGE_DYNAMIC_CONFIG_PATH"] = str(tmp / "dynamic-config-none.json")
        server._PENALTY_TRACKER = ModelPenaltyTracker(
            storage_path=tmp / "model_penalties.json",
            max_start_fails=TEST_MAX_START_FAILS,
        )
        server._MODEL_NOTES_FILTER = server.ModelNotesFilter(tmp / "notes.md")

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        """Вернуть переменную окружения к значению до setUp (None — удалить)."""
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    # -- helpers ----------------------------------------------------------------
    def _post(self, body: dict, timeout: float = 60.0) -> tuple[int, str]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            conn.request(
                "POST",
                "/v1/chat/completions",
                body=json.dumps(body),
                headers={
                    "Authorization": "Bearer test-key",
                    "Content-Type": "application/json",
                },
            )
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8")
            return resp.status, raw
        finally:
            conn.close()

    def _post_json(self, body: dict, timeout: float = 60.0) -> tuple[int, Any]:
        status, raw = self._post(body, timeout=timeout)
        return status, (json.loads(raw) if raw else None)

    def _get(self, path: str, auth: bool = True) -> tuple[int, Any]:
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
    def _raw_request(
        body: bytes = b"", cl: str | int | None = "auto", extra=(), auth=True, path="/v1/chat/completions"
    ):
        headers = [
            f"POST {path} HTTP/1.1",
            "Host: 127.0.0.1",
            "Content-Type: application/json",
        ]
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
                err = json.loads(body.decode("utf-8", "replace").split("HTTP/1.1")[0])[
                    "error"
                ]
                if (
                    sorted(err) == ["code", "message", "type"]
                    and err.get("code") == code
                ):
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
        droidify_raw_fleet(data)
        mutate(data)
        return install_droid_stand(data)
