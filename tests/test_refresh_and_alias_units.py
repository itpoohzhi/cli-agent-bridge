from __future__ import annotations

# Узкие проверки `server.py`: каноническое имя модели по effort-алиасу, нейтральные умолчания
# состояния Handler и отчёт `/v1/models/refresh` о провалившихся upstream.

import http.client
import json
import sys
from pathlib import Path
from typing import Any, cast
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from bridge_testlib import BridgeCase  # noqa: E402  # tests/ — корень импорта pytest

CATALOGUE = {"m": {}, "other": {}}


@pytest.mark.parametrize(
    "raw,expected",
    [("m-high", "m"), ("other-low", "other"), ("m", "m"), ("m-bogus", "m-bogus"), ("zzz", "zzz")],
)
def test_canonical_model_id_unwraps_only_known_effort_aliases(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: str
) -> None:
    monkeypatch.setattr(server, "EFFORT_ALIAS_ENABLED", True)
    monkeypatch.setattr(server, "EFFORT_SUFFIXES", ("low", "high"))
    assert server._canonical_model_id(raw, CATALOGUE) == expected


def test_canonical_model_id_is_identity_when_aliases_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(server, "EFFORT_ALIAS_ENABLED", False)
    assert server._canonical_model_id("m-high", CATALOGUE) == "m-high"


def test_handler_request_state_defaults_are_inert() -> None:
    handler = cast(Any, object.__new__(server.Handler))
    flags = (handler._subagent_slot_held, handler._headers_already_sent)
    assert flags + (handler._instr_truncated,) == (False, False, False)
    assert (handler._parsed_req, handler._resilience_lease) == (None, None)


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
