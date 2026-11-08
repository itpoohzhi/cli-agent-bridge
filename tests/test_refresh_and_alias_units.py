from __future__ import annotations

# Узкие проверки `server.py`: отчёт `/v1/models/refresh` о провалившихся upstream.

import http.client
import json
import sys
from pathlib import Path
from typing import Any
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from bridge_testlib import BridgeCase  # noqa: E402  # tests/ — корень импорта pytest


class TestModelsRefresh(BridgeCase):
    def _refresh(self) -> tuple[int, Any]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        auth = {"Authorization": "Bearer test-key"}
        with mock.patch.dict(server._REFRESH_LAST, clear=True), mock.patch.dict(server._MODELS_CACHE, clear=True):
            try:
                conn.request("POST", "/v1/models/refresh", body=b"{}", headers=auth)
                resp = conn.getresponse()
                return resp.status, json.loads(resp.read().decode("utf-8"))
            finally:
                conn.close()

    def test_refresh_reports_upstreams_that_failed_to_refresh(self) -> None:
        with mock.patch.object(server, "_refresh_fleet", lambda: ["up-1"], create=True):
            status, body = self._refresh()
        assert (status, body["status"], body["failed_upstreams"]) == (200, "partial", ["up-1"])

    def test_refresh_without_failures_is_complete(self) -> None:
        for outcome in (None, []):
            with mock.patch.object(server, "_refresh_fleet", lambda: outcome, create=True):
                status, body = self._refresh()
            assert (status, body["status"], body["failed_upstreams"]) == (200, "complete", [])
