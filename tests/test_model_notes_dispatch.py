"""C0-6, VER-009/021: mandatory notes/probe ingress, независимо от P0.

L1 вызывает настоящий Handler без socket; L2 использует только loopback.
Никаких xfail/skip при отсутствующем контракте W1/W2.
"""

from __future__ import annotations

import importlib
import sys
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.test_routing_catalog_p0_owner import (  # noqa: E402
    MODEL,
    VALID_NOTES,
    request_local,
    request_wire,
    compile_local,
    install_catalog,
    local_provider,
    routing_flag as routing_flag,
    stand as stand,
)

PATHS = ("/v1/chat/completions", "/v1/messages")


def replace_notes(stand: Any, content: str | None) -> Any:
    path = stand.root / "selected-notes.md"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    elif path.exists():
        path.unlink()
    stand.patcher.setenv("MODEL_NOTES_PATH", str(path))
    stand.patcher.setenv("BRIDGE_MODEL_NOTES_PATH", str(path))
    notes = stand.srv.ModelNotesFilter(path=path)
    stand.notes.append(notes)
    stand.patcher.setattr(stand.srv, "_MODEL_NOTES_FILTER", notes)
    return notes


def assert_error(response: tuple[int, Any], expected: tuple[int, str]) -> None:
    status, payload = response
    error = payload.get("error", {})
    assert status == expected[0], payload
    assert expected[1] in (error.get("type"), error.get("code")), payload


@pytest.fixture(params=[False, True], ids=["penalty-off", "penalty-on"])
def penalty_flag(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_ROUTE_PENALTY_ENABLED", str(request.param).lower())


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("content", [None, "\xff broken source", ""])
def test_failed_closed_all_dispatch_zero_sends(
    stand: Any, path: str, content: str | None, routing_flag: bool, penalty_flag: None
) -> None:
    replace_notes(stand, content)
    response = request_local(stand, path, {"model": MODEL, "messages": []}, {"X-Bypass-Model-Filter": "1"})
    assert stand.sends == []
    assert_error(response, (503, "notes_unavailable"))


def test_failed_closed_health_has_safe_diagnostic(stand: Any, routing_flag: bool) -> None:
    replace_notes(stand, "invalid token=must-not-leak")
    status, payload = request_local(stand, "/health")
    assert status == 503
    assert payload["notes_status"] == "FAILED_CLOSED"
    assert "must-not-leak" not in str(payload)
    assert stand.sends == []


def test_failed_closed_models_excluded_or_service_unavailable(stand: Any, routing_flag: bool) -> None:
    replace_notes(stand, None)
    status, payload = request_local(stand, "/v1/models")
    assert status in (200, 503)
    assert MODEL not in {card["id"] for card in payload.get("data", [])}
    assert stand.sends == []


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("authorized", [False, True])
@pytest.mark.parametrize(
    "spoof",
    [
        ({"is_probe": True}, {}),
        ({"is_probe": False}, {}),
        ({"is_probe": None}, {}),
        ({}, {"X-Probe": "1"}),
        ({}, {"X-Probe": ""}),
        ({}, {"X-Bridge-Probe": "0"}),
        ({}, {"x-bRiDgE-pRoBe": ""}),
    ],
)
def test_client_probe_presence_rejected_before_dispatch(
    stand: Any, path: str, spoof: tuple[Any, Any], routing_flag: bool, authorized: bool
) -> None:
    stand.patcher.setattr(stand.srv, "_auth_ok", lambda handler: authorized)
    fields, headers = spoof
    body = {"model": MODEL, "messages": [], **fields}
    response = request_local(stand, path, body, headers)
    assert stand.sends == []
    assert_error(response, (400, "invalid_request_error"))


@pytest.mark.parametrize("path", PATHS)
def test_bypass_cannot_override_valid_block_rule(stand: Any, path: str, routing_flag: bool) -> None:
    text = f"| Модель | Статус |\n|---|---|\n| `{MODEL}` | BANNED |\n"
    notes = replace_notes(stand, text)
    assert notes.is_blocked(MODEL), "fixture must be a valid blocking rule"
    response = request_local(stand, path, {"model": MODEL, "messages": []}, {"X-Bypass-Model-Filter": "1"})
    assert response[0] == 503
    assert stand.sends == []


def test_l1_failed_closed_has_no_socket_or_process_effect(
    stand: Any, monkeypatch: pytest.MonkeyPatch, routing_flag: bool
) -> None:
    replace_notes(stand, None)
    forbidden = Mock(side_effect=AssertionError("L1 forbidden side effect"))
    for module, name in (
        ("socket", "socket"),
        ("socket", "create_connection"),
        ("subprocess", "Popen"),
        ("time", "sleep"),
    ):
        monkeypatch.setattr(importlib.import_module(module), name, forbidden)
    response = request_local(stand, PATHS[0], {"model": MODEL, "messages": []})
    assert stand.sends == []
    assert_error(response, (503, "notes_unavailable"))
    forbidden.assert_not_called()


@pytest.mark.parametrize("path", PATHS)
def test_l2_failed_closed_and_probe_spoof_on_real_http(stand: Any, path: str, routing_flag: bool) -> None:
    replace_notes(stand, None)
    support = importlib.import_module("tests.transport_wire_support")
    with support.RecordingUpstream() as upstream:
        provider = local_provider("codex", 7, 1, upstream.port)
        install_catalog(stand, compile_local((provider,)).fleet)
        stand.patcher.setattr(stand.handler, "_serve_passthrough", stand.srv.Handler._serve_passthrough)
        with support.RunningHTTPServer(stand.handler) as server:
            response = request_wire(server, path, {"model": MODEL, "messages": []}, {"X-Bypass-Model-Filter": "1"})
            spoof = request_wire(server, path, {"model": MODEL, "is_probe": False})
        assert upstream.post_count == upstream.body_bytes == 0
    assert stand.sends == []
    assert_error(response, (503, "notes_unavailable"))
    assert_error(spoof, (400, "invalid_request_error"))


def test_background_recovery_without_replacing_filter_or_server(
    stand: Any, monkeypatch: pytest.MonkeyPatch, routing_flag: bool
) -> None:
    monkeypatch.setenv("MODEL_NOTES_REFRESH_INTERVAL_S", "5")
    notes = replace_notes(stand, None)
    running = importlib.import_module("tests.transport_wire_support").RunningHTTPServer
    with running(stand.handler) as server:
        assert_error(request_wire(server, PATHS[0], {"model": MODEL}), (503, "notes_unavailable"))
        refreshed = threading.Event()
        selected = stand.root / "selected-notes.md"
        original = stand.srv.read_model_notes_file

        def read(path: Any, *args: Any, **kwargs: Any) -> Any:
            if Path(path) == selected:
                refreshed.set()
            return original(path, *args, **kwargs)

        monkeypatch.setattr(stand.srv, "read_model_notes_file", read)
        selected.write_text(VALID_NOTES, encoding="utf-8")
        assert refreshed.wait(8), "timer never retried source without HTTP requests"
        response = _await_ok(server)
        assert response[0] == 200
        assert stand.srv._MODEL_NOTES_FILTER is notes
        assert request_wire(server, PATHS[0], {"model": MODEL})[0] == 200
    assert len(stand.sends) == 1
    assert stand.sends[0][0] == MODEL
    assert stand.sends[0][1] in {"codex", "droid"}


def test_disk_last_good_cannot_authorize_after_source_failure(stand: Any, routing_flag: bool) -> None:
    notes = replace_notes(stand, VALID_NOTES)
    assert not notes.is_blocked(MODEL)
    assert (stand.root / "state/model-notes.snapshot.json").is_file()
    replace_notes(stand, None)
    response = request_local(stand, PATHS[0], {"model": MODEL}, {"X-Bypass-Model-Filter": "1"})
    assert stand.sends == []
    assert_error(response, (503, "notes_unavailable"))


def _await_ok(server: Any) -> tuple[int, Any]:
    deadline = time.monotonic() + 3
    pause = threading.Event()
    response = request_wire(server, "/health")
    while response[0] != 200 and time.monotonic() < deadline:
        pause.wait(0.01)
        response = request_wire(server, "/health")
    return response
