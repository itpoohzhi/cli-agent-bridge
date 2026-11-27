"""W0 (P0-S4): красный репро — разрыв клиента не должен печатать traceback в stderr.

Целевой контракт: при включённом BRIDGE_SUPPRESS_CLIENT_DISCONNECT_TRACEBACK_ENABLED
хаб гасит traceback штатного socketserver.handle_error и пишет ровно одну строку
журнала с client_disconnected и BrokenPipeError. На базе 06f28762 Handler._send
пробрасывает BrokenPipeError (server.py:5454-5457), traceback уходит в stderr.
"""

from __future__ import annotations

import errno
import http.client
import io
import json
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server  # noqa: E402


class _BrokenClientPipe(io.BufferedIOBase):
    """wfile клиента, который ушёл: первая же запись ответа даёт BrokenPipeError."""

    def writable(self) -> bool:
        return True

    def write(self, data) -> int:
        raise BrokenPipeError(errno.EPIPE, "Broken pipe (red repro: client gone)")

    def flush(self) -> None:
        return None


def _wait_disconnect_outcome(
    logs: list[str], stderr: io.StringIO, timeout_s: float = 5.0
) -> None:
    """Ждём любой исход обработчика: legacy 'http accept error', целевой
    'client_disconnected' (после фикса W2-A) или traceback в stderr."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if (
            any(
                "http accept error" in line or "client_disconnected" in line
                for line in logs
            )
            or "Traceback (most recent call last):" in stderr.getvalue()
        ):
            return
        time.sleep(0.02)
    raise AssertionError(
        f"disconnect outcome not seen; logs={logs!r} stderr={stderr.getvalue()!r}"
    )


def _isolate_dynamic_config(monkeypatch, tmp_path, flags: dict) -> None:
    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text(json.dumps(flags), encoding="utf-8")
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(cfg))


def _run_gone_hub_get() -> None:
    class _GoneClientHandler(server.Handler):
        def setup(self) -> None:
            super().setup()
            self.wfile = _BrokenClientPipe()

    httpd = server.Server(("127.0.0.1", 0), _GoneClientHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        conn = http.client.HTTPConnection(
            "127.0.0.1", httpd.server_address[1], timeout=5.0
        )
        try:
            conn.connect()
            conn.sock.setsockopt(
                socket.SOL_SOCKET, socket.SO_LINGER, b"\x01\x00\x00\x00\x00\x00\x00\x00"
            )
            conn.request("GET", "/health")
        finally:
            conn.close()
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


@pytest.mark.red_repro
def test_red_repro_hub_server_disconnect_writes_single_line_not_stderr(
    monkeypatch, tmp_path
):
    _isolate_dynamic_config(
        monkeypatch,
        tmp_path,
        {
            "BRIDGE_SUPPRESS_CLIENT_DISCONNECT_TRACEBACK_ENABLED": True,
            "BRIDGE_LOG_ROTATION_ENABLED": True,
        },
    )
    logs: list[str] = []
    stderr = io.StringIO()
    monkeypatch.setattr(server, "_log", logs.append)
    monkeypatch.setattr(sys, "stderr", stderr)
    _run_gone_hub_get()
    _wait_disconnect_outcome(logs, stderr)
    captured = stderr.getvalue()
    assert "Traceback (most recent call last):" not in captured, captured
    assert len(captured) == 0, captured
    lines = [line for line in logs if "client_disconnected" in line]
    assert len(lines) == 1, logs
    line = lines[0]
    assert "BrokenPipeError" in line, line
    assert "\n" not in line and "\r" not in line, line
