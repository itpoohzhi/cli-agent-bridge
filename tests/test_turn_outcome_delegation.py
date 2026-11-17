"""C2-5: thin HTTP seam, shared turn classification and notes lifecycle."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server as srv  # noqa: E402
from core import http_post_dispatch_guard as dispatch_guard  # noqa: E402


def test_repo_root_precedes_import_paths() -> None:
    assert str(ROOT) in sys.path and Path(srv.__file__).resolve().parent == ROOT


def test_post_is_thin_and_guarded_before_facade_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[Any, Any]] = []
    monkeypatch.setattr(srv._transport_facade, "handle_post", lambda handler, host: seen.append((handler, host)))
    handler = object.__new__(srv.Handler)
    handler.do_POST()
    assert seen == [(handler, srv)]
    assert srv._transport_facade.begin_post is dispatch_guard.begin_post


@pytest.mark.parametrize(
    ("out", "error", "expected"),
    [
        ({"state": "done", "rc": 0, "text": "ok"}, None, "OK"),
        ({"state": "backend_error", "rc": 1}, {"type": "proxy_error"}, "ERROR_BODY"),
        ({"state": "delivery_budget", "rc": 1}, {"type": "proxy_error"}, "CLIENT_ABORT"),
    ],
)
def test_turn_classification_is_delegated_to_core(out: dict[str, Any], error: Any, expected: str) -> None:
    assert srv._classify_turn_outcome(out, error) == expected


def test_record_turn_outcome_uses_shared_classifier(monkeypatch: pytest.MonkeyPatch) -> None:
    lease, tracker = Mock(), Mock()
    classifier = Mock(return_value="OK")
    monkeypatch.setattr(srv, "_classify_turn_outcome", classifier)
    monkeypatch.setattr(srv, "_PENALTY_TRACKER", tracker)
    srv.Handler._record_turn_outcome(lease, {"state": "done", "rc": 0}, None, "model-a")
    classifier.assert_called_once()
    lease.record_success.assert_called_once_with()
    tracker.record_start_success.assert_called_once_with("model-a")


def test_refresh_publishes_fresh_notes_before_retiring_old(monkeypatch: pytest.MonkeyPatch) -> None:
    old, fresh = Mock(), Mock()
    monkeypatch.setattr(srv, "_MODEL_NOTES_FILTER", old)
    monkeypatch.setattr(srv, "ModelNotesFilter", Mock(return_value=fresh))
    srv._refresh_model_notes_filter()
    assert srv._MODEL_NOTES_FILTER is fresh
    old.close.assert_called_once_with()


def test_server_does_not_replace_or_close_external_notes(monkeypatch: pytest.MonkeyPatch) -> None:
    parent_init, parent_close = Mock(), Mock()
    refresh, notes = Mock(), Mock()
    monkeypatch.setattr(srv.ThreadingHTTPServer, "__init__", parent_init)
    monkeypatch.setattr(srv.ThreadingHTTPServer, "server_close", parent_close)
    monkeypatch.setattr(srv, "_refresh_model_notes_filter", refresh)
    monkeypatch.setattr(srv, "_MODEL_NOTES_FILTER", notes)
    server = srv.Server(("127.0.0.1", 0), srv.Handler)
    refresh.assert_not_called()
    assert srv._MODEL_NOTES_FILTER is notes
    server.server_close()
    parent_close.assert_called_once_with()
    notes.close.assert_not_called()


def test_failed_closed_health_is_l1_only(monkeypatch: pytest.MonkeyPatch) -> None:
    handler = object.__new__(srv.Handler)
    handler._send = Mock()
    notes = SimpleNamespace(is_failed_closed=lambda: True, status="FAILED_CLOSED")
    monkeypatch.setattr(srv, "_MODEL_NOTES_FILTER", notes)
    monkeypatch.setattr(srv.BACKENDS, "adapters", Mock(side_effect=AssertionError("backend probe")))
    assert handler._handle_health_get("/health")
    handler._send.assert_called_once_with(503, {"ok": False, "notes_status": "FAILED_CLOSED"})
