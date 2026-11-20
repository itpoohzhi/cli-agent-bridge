"""Harness Live-Isolated E2E: реальный процесс `server.py` agy-bridge вместо моков.

Изоляция (Гейт 3 `bridge-e2e-verification`): копия `core/` + `bridges/agy-bridge/` во временном
каталоге, `HOME=<tmp>`, свой `dynamic_config.json`, свободный порт `127.0.0.1`, отдельный PGID
(`start_new_session=True`), стаб `tests/agy_stub_agent.py` вместо `agy.real`. Запрещены порты
9881-9887, 18080, 10809-10840, `~/.dsh`, `~/.config/*`, launchd. Остановка: SIGTERM→SIGKILL по
своему PGID, затем проверка `orphan_pids == 0` и `listeners == 0`.
"""

from __future__ import annotations

import contextlib
import http.client
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FORBIDDEN_PORTS = frozenset({*range(9881, 9888), 18080, *range(10809, 10841)})
API_KEY = "live-isolated-key"
MODEL = "gemini-3.8-flash"
TOOLS = ({"type": "function", "function": {"name": "read", "description": "read a file", "parameters": {
    "type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"]}}},)


def free_port() -> int:
    """Свободный порт, выданный ОС; порты живого контура исключены."""
    for _ in range(50):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = int(sock.getsockname()[1])
        if port not in FORBIDDEN_PORTS:
            return port
    raise RuntimeError("no free port outside the forbidden ranges")


@dataclass
class ChatResult:
    """Итог SSE-запроса: статус, разобранные chunk-и и сырой текст потока."""

    status: int
    raw: str
    chunks: list[dict[str, object]] = field(default_factory=list)

    @property
    def done_count(self) -> int:
        return self.raw.count("data: [DONE]")

    @property
    def errors(self) -> list[object]:
        return [c["error"] for c in self.chunks if "error" in c]

    def delta_values(self, key: str) -> list[object]:
        deltas = (c.get("choices", [{}])[0].get("delta", {}) for c in self.chunks if c.get("choices"))  # type: ignore[union-attr, index]
        return [d[key] for d in deltas if key in d]

    @property
    def finish_reasons(self) -> list[object]:
        return [c["choices"][0].get("finish_reason") for c in self.chunks if c.get("choices")]  # type: ignore[index, union-attr]


class LiveBridge:
    """Изолированный живой мост: старт, запросы, остановка и проверка утечек."""

    def __init__(self, root: Path, scenario: str, flags: dict[str, object], extra_env: dict[str, str] | None = None) -> None:
        self.root, self.scenario, self.flags = root, scenario, flags
        self.extra_env = extra_env or {}
        self.port = free_port()
        self.proc: subprocess.Popen[bytes] | None = None
        self.repo = root / "repo"
        self.log_path = root / "bridge.log"
        self.leaks: dict[str, int] = {}

    def _prepare(self) -> dict[str, str]:
        skip = shutil.ignore_patterns("__pycache__", "workspace", "*.pyc")
        shutil.copytree(REPO / "core", self.repo / "core", ignore=skip)
        shutil.copytree(REPO / "bridges" / "agy-bridge", self.repo / "bridges" / "agy-bridge", ignore=skip)
        home = self.root / "home"
        home.mkdir()
        (self.root / "dynamic_config.json").write_text(json.dumps(self.flags), encoding="utf-8")
        launcher = self.root / "launcher.sh"
        stub = REPO / "tests" / "agy_stub_agent.py"
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{stub}" "$@"\n', encoding="utf-8")
        launcher.chmod(0o755)
        return self._env(home, launcher)

    def _env(self, home: Path, launcher: Path) -> dict[str, str]:
        env = {k: v for k, v in os.environ.items() if not k.startswith(("BRIDGE_", "AGY_"))}
        env.update(
            HOME=str(home), AGY_BRIDGE_KEY=API_KEY, AGY_BRIDGE_PORT=str(self.port), AGY_LAUNCHER=str(launcher),
            AGY_BRIDGE_CLEAN_HOME=str(self.root / "agy-home"), AGY_STUB_SCENARIO=self.scenario,
            AGY_STUB_STATE_DIR=str(self.root / "stub-state"), BRIDGE_DYNAMIC_CONFIG_PATH=str(self.root / "dynamic_config.json"),
            BRIDGE_TELEMETRY_DB_PATH=str(self.root / "telemetry.duckdb"), BRIDGE_ENV_FILE_PATH=str(self.root / "hot.env"),
            BRIDGE_MODEL_PENALTIES_PATH=str(self.root / "penalties.json"), AGY_BRIDGE_SESSIONS_FILE=str(self.root / "sessions.json"),
            BRIDGE_STREAM_PRECOMMIT_FLUSH_ENABLED="1", BRIDGE_STREAM_PRECOMMIT_FLUSH_S="0.2",
            BRIDGE_STREAM_EARLY_POLL_INTERVAL_S="0.05", BRIDGE_RETRY_PAUSE_MAX_S="0.05",
            AGY_BRIDGE_TRANSCRIPT_GRACE="1.0", PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1",
        )  # fmt: skip
        env.update(self.extra_env)
        return env

    def start(self, timeout_s: float = 40.0) -> None:
        env = self._prepare()
        server = self.repo / "bridges" / "agy-bridge" / "server.py"
        with self.log_path.open("wb") as log:
            self.proc = subprocess.Popen([sys.executable, str(server)], env=env, cwd=self.root, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)  # noqa: S603
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError("bridge exited early:\n" + self.log_text())
            try:
                if self.get("/health")[0] == 200:
                    return
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("bridge did not become healthy:\n" + self.log_text())

    def log_text(self) -> str:
        return self.log_path.read_text(encoding="utf-8", errors="replace") if self.log_path.exists() else ""

    def get(self, path: str) -> tuple[int, dict[str, object]]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request("GET", path)
            resp = conn.getresponse()
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
        finally:
            conn.close()

    def chat(self, tools: bool = True, timeout_s: float = 60.0, chat_id: str = "") -> ChatResult:
        body = {"model": MODEL, "stream": True, "messages": [{"role": "user", "content": "hi"}]}
        if tools:
            body["tools"] = list(TOOLS)
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout_s)
        try:
            headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
            if chat_id:
                headers["X-DSH-Chat-Id"] = chat_id
            conn.request("POST", "/v1/chat/completions", json.dumps(body), headers)
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8", errors="replace")
        finally:
            conn.close()
        chunks = [json.loads(ln[6:]) for ln in raw.splitlines() if ln.startswith("data: {")]
        return ChatResult(resp.status, raw, chunks)

    def spawn_count(self) -> int:
        path = self.root / "stub-state" / f"{self.scenario}.count"
        return int(path.read_text(encoding="utf-8")) if path.exists() else 0

    @property
    def is_clean(self) -> bool:
        """После остановки нет ни осиротевших процессов, ни слушателей."""
        return self.leaks == {"orphan_pids": 0, "listeners": 0}

    def _orphans(self) -> int:
        out = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True, text=True, check=False).stdout  # noqa: S603, S607
        token = str(self.root)
        return sum(1 for ln in out.splitlines() if token in ln and str(os.getpid()) != ln.split()[0])

    def _listeners(self) -> int:
        with socket.socket() as probe:
            probe.settimeout(0.5)
            return 1 if probe.connect_ex(("127.0.0.1", self.port)) == 0 else 0

    def stop(self) -> dict[str, int]:
        """SIGTERM→SIGKILL по своему PGID; вернуть `orphan_pids` и `listeners`."""
        if self.proc is not None:
            pgid = self.proc.pid
            for sig, wait_s in ((signal.SIGTERM, 5.0), (signal.SIGKILL, 5.0)):
                try:
                    os.killpg(pgid, sig)
                except ProcessLookupError:
                    break
                try:
                    _ = self.proc.wait(timeout=wait_s)
                    break
                except subprocess.TimeoutExpired:
                    continue
        time.sleep(0.3)
        return {"orphan_pids": self._orphans(), "listeners": self._listeners()}


FLAG_NAMES = (
    "BRIDGE_TRANSPORT_FAILURE_CLASSIFIER_ENABLED",
    "BRIDGE_KEEPALIVE_ONLY_PRERETRY_ENABLED",
    "BRIDGE_RETRY_WINDOW_PAUSE_ENABLED",
    "BRIDGE_HOT_SESSION_RETAIN_ON_TRANSIENT_ENABLED",
    "BRIDGE_TOOLCALL_ERROR_RECOVERY_ENABLED",
    "BRIDGE_VENDOR_RETRY_PHRASE_MASK_ENABLED",
)
ALL_ON = dict.fromkeys(FLAG_NAMES, True)
ALL_OFF = dict.fromkeys(FLAG_NAMES, False)


@contextlib.contextmanager
def running(root: Path, scenario: str, flags: dict[str, object], extra_env: dict[str, str] | None = None) -> Iterator[LiveBridge]:
    """Поднять изолированный мост; в `finally` — SIGTERM→SIGKILL по PGID и проверка утечек."""
    bridge = LiveBridge(root, scenario, flags, extra_env)
    bridge.leaks = {"orphan_pids": -1, "listeners": -1}
    try:
        bridge.start()
        yield bridge
    finally:
        bridge.leaks = bridge.stop()
