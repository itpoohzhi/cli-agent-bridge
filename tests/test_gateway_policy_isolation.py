"""Регрессия: ошибки одного теста не карантинят модели следующих тестов."""

from __future__ import annotations

import io
import json
import os
import sys
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

import server  # noqa: E402
from tests.bridge_testlib import BridgeCase  # noqa: E402


def _handler(
    method: str, path: str, body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    instance: Any = object.__new__(server.Handler)
    raw = b"" if body is None else json.dumps(body).encode()
    instance.command, instance.path = method, path
    instance.headers = Message()
    for key, value in (headers or {}).items():
        instance.headers[key] = value
    instance.headers["Content-Length"] = str(len(raw))
    instance.rfile, instance.wfile = io.BytesIO(raw), io.BytesIO()
    instance.client_address = ("127.0.0.1", 1)
    instance.statuses = []
    instance.send_response = instance.statuses.append
    instance.send_header = lambda *_args: None
    instance.end_headers = lambda: None
    return instance


def _invoke(instance: Any) -> tuple[int, dict[str, Any]]:
    instance.do_POST() if instance.command == "POST" else instance.do_GET()
    return instance.statuses[-1], json.loads(instance.wfile.getvalue())


def _forbid_dispatch(monkeypatch: pytest.MonkeyPatch) -> Mock:
    forbidden = Mock(side_effect=AssertionError("dispatch side effect"))
    monkeypatch.setattr(server, "_auth_ok", forbidden)
    monkeypatch.setattr(server, "_resolve_model_alias", forbidden)
    monkeypatch.setattr(server.BACKENDS, "get", forbidden)
    monkeypatch.setattr(server.BACKENDS, "adapters", forbidden)
    monkeypatch.setattr(server.RESILIENCE, "acquire", forbidden)
    monkeypatch.setattr(server.RESILIENCE, "snapshot", forbidden)
    monkeypatch.setattr(server, "read_model_notes_file", forbidden)
    return forbidden


@pytest.mark.parametrize("round_id", (0, 1))
def test_penalty_state_is_private_and_fresh(tmp_path: Path, round_id: int) -> None:
    policy_dir = Path(os.environ["BRIDGE_STATE_DIR"]).parent
    assert policy_dir.parent == tmp_path.parent
    tracker = server._PENALTY_TRACKER
    assert tracker.storage_path == policy_dir / "penalties.json"
    assert tracker.get_model_status("claude-sonnet-5-5")["fails"] == 0
    tracker.manually_penalize("claude-sonnet-5-5", duration_s=60)
    assert tracker.is_penalized("claude-sonnet-5-5")[0] is True
    assert tracker.storage_path.is_file()


def test_runtime_policy_paths_do_not_point_to_owner_files(tmp_path: Path) -> None:
    policy_dir = Path(os.environ["BRIDGE_STATE_DIR"]).parent
    assert policy_dir.parent == tmp_path.parent
    notes: Any = server._MODEL_NOTES_FILTER
    assert server._QUOTA_CB_CACHE.path == policy_dir / "quota.json"
    assert notes.path == policy_dir / "notes.md"
    assert notes.is_blocked("claude-sonnet-5-5") is False


def test_subclass_cleanup_cannot_restore_stale_adapter() -> None:
    case = BridgeCase()
    original = server.BACKENDS
    case._save_server()
    case.addCleanup(case._restore_server)
    case.addCleanup(setattr, server, "BACKENDS", object())
    try:
        assert case.doCleanups() is True
        assert server.BACKENDS is original
    finally:
        server.BACKENDS = original


@pytest.mark.parametrize(
    ("body_extra", "headers"),
    [
        ({"is_probe": False}, {}),
        ({}, {"X-Probe": ""}),
        ({}, {"x-bRiDgE-pRoBe": "0"}),
    ],
)
def test_real_do_post_probe_spoof_is_guarded_before_all_side_effects(
    monkeypatch: pytest.MonkeyPatch,
    body_extra: dict[str, Any],
    headers: dict[str, str],
) -> None:
    forbidden = _forbid_dispatch(monkeypatch)
    monkeypatch.setattr(
        server,
        "_MODEL_NOTES_FILTER",
        SimpleNamespace(is_failed_closed=forbidden, is_blocked=forbidden),
    )
    body = {"model": "gpt-6.1-sol", "messages": [], **body_extra}
    status, payload = _invoke(_handler("POST", "/v1/chat/completions", body, headers))
    assert status == 400
    assert payload["error"]["type"] == "invalid_request_error"
    forbidden.assert_not_called()


@pytest.mark.parametrize("path", ["/v1/chat/completions", "/v1/messages"])
def test_real_do_post_failed_closed_precedes_auth_backend_and_lease(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    forbidden = _forbid_dispatch(monkeypatch)
    notes = SimpleNamespace(
        status="FAILED_CLOSED", is_failed_closed=lambda: True, is_blocked=forbidden
    )
    monkeypatch.setattr(server, "_MODEL_NOTES_FILTER", notes)
    headers = {"X-Bypass-Model-Filter": "1"}
    body = {"model": "gpt-6.1-sol", "messages": []}
    status, payload = _invoke(_handler("POST", path, body, headers))
    assert status == 503
    assert payload["error"]["type"] == "notes_unavailable"
    forbidden.assert_not_called()


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/health"),
        ("GET", "/v1/models"),
        ("POST", "/v1/chat/completions"),
        ("POST", "/v1/messages"),
    ],
)
def test_failed_closed_handler_matrix_is_503(
    monkeypatch: pytest.MonkeyPatch, method: str, path: str
) -> None:
    forbidden = Mock(side_effect=AssertionError("notes or backend I/O"))
    notes = SimpleNamespace(
        status="FAILED_CLOSED", is_failed_closed=lambda: True, is_blocked=forbidden
    )
    monkeypatch.setattr(server, "_MODEL_NOTES_FILTER", notes)
    monkeypatch.setattr(server.BACKENDS, "get", forbidden)
    monkeypatch.setattr(server.BACKENDS, "adapters", forbidden)
    monkeypatch.setattr(server.RESILIENCE, "acquire", forbidden)
    monkeypatch.setattr(server.RESILIENCE, "snapshot", forbidden)
    monkeypatch.setattr(server, "_resolve_model_alias", forbidden)
    monkeypatch.setattr(server, "read_model_notes_file", forbidden)
    monkeypatch.setattr(server, "_auth_ok", lambda _handler: True)
    body = {"model": "gpt-6.1-sol", "messages": []} if method == "POST" else None
    instance = _handler(method, path, body, {"X-Bypass-Model-Filter": "1"})
    status, payload = _invoke(instance)
    assert status == 503, payload
    forbidden.assert_not_called()
