"""Общий HTTP-стенд тестов: настоящий Server на свободном порту и вызов эндпоинтов."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from typing import Any
from unittest.mock import patch

import server

KEY = "test-key"


class LiveServer:
    """Поднимает `server.Server` на 127.0.0.1:0 с подменой ключа; `stop()` обязателен."""

    def __init__(self) -> None:
        self._key_patch = patch.object(server, "AUTH_KEY", KEY)
        self._key_patch.start()
        self.httpd = server.Server(("127.0.0.1", 0), server.Handler)
        self.port = int(self.httpd.server_address[1])
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=10)
        self._key_patch.stop()

    def call(self, method: str, path: str, body: dict[str, Any] | None = None,
             key: str | None = KEY) -> tuple[int, dict[str, Any]]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"}
        if key is not None:
            headers["Authorization"] = f"Bearer {key}"
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            with exc:
                return exc.code, json.loads(exc.read())
