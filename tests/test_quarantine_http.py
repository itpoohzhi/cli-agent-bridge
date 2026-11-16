"""HTTP-контракт карантина на локальном сервере с общим ingress."""

import json

import pytest

from tests.quarantine_api_support import api as api
from tests.test_quarantine_api import clock as clock, tracker as tracker


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_http_requires_authorization(api, tracker, method):
    status, body = api(method, {"action": "ban", "model": "a"}, authorized=False)
    assert status == 401
    assert body == {
        "error": {
            "message": "unauthorized",
            "type": "auth_error",
            "code": 401,
        }
    }
    assert tracker.get_all_penalties() == {}


def test_http_get_catalog(api):
    status, body = api()
    assert status == 200
    assert body["enabled"] is True
    assert body["max_start_fails"] == 3
    assert body["available_models"] == ["model-a", "model-b"]
    assert body["penalized_count"] == 0


def test_http_toggle(api):
    status, body = api("POST", {"action": "set_enabled", "enabled": False})
    assert status == 200
    assert body == {
        "ok": True,
        "action": "set_enabled",
        "enabled": False,
        "max_start_fails": 999999999,
    }
    assert api()[1]["enabled"] is False

    status, body = api("POST", {"action": "set_enabled"})
    assert status == 200
    assert body["enabled"] is True
    assert body["max_start_fails"] == 3


def test_http_ban_and_unban(api):
    status, body = api("POST", {"action": "ban", "model": "MODEL-A", "duration_s": 45})
    assert status == 200
    assert body["action"] == "ban"
    assert body["model"] == "MODEL-A"
    assert body["status"]["model"] == "model-a"
    assert body["status"]["remaining_cooldown"] == 45
    assert api()[1]["penalized_count"] == 1

    status, body = api("POST", {"action": "unban", "model": "model-a"})
    assert status == 200
    assert body == {"ok": True, "action": "unban", "model": "model-a"}
    assert api()[1]["penalized_count"] == 0


def test_http_default_duration(api):
    status, body = api("POST", {"action": "ban", "model": "a"})
    assert status == 200
    assert body["status"]["remaining_cooldown"] == 300


def test_http_clear_all_preserves_disabled_setting(api):
    api("POST", {"action": "ban", "model": "a"})
    api("POST", {"action": "set_enabled", "enabled": False})
    status, body = api("POST", {"action": "clear_all"})
    assert status == 200
    assert body == {"ok": True, "action": "clear_all"}

    payload = api()[1]
    assert payload["enabled"] is False
    assert payload["penalized_count"] == 0


@pytest.mark.parametrize(
    "body",
    [
        [],
        None,
        {"action": "set_enabled", "enabled": "false"},
        {"action": "set_enabled", "enabled": 0},
        {"action": "ban"},
        {"action": "ban", "model": " "},
        {"action": "ban", "model": 123},
        {"action": "ban", "model": "_meta"},
        {"action": "unban", "model": ""},
        {"action": "ban", "model": "a", "duration_s": -1},
        {"action": "ban", "model": "a", "duration_s": "NaN"},
        {"action": "ban", "model": "a", "duration_s": "Infinity"},
        {"action": "ban", "model": "a", "duration_s": None},
        {"action": "ban", "model": "a", "duration_s": True},
    ],
)
def test_http_invalid_requests(api, body):
    status, response = api("POST", raw=json.dumps(body).encode("utf-8"))
    assert status == 400
    assert response["error"]["type"] == "invalid_request"


@pytest.mark.parametrize("raw", [b"", b"{", b"\xff"])
def test_http_invalid_json(api, raw):
    status, body = api("POST", raw=raw)
    assert status == 400
    assert body["error"]["type"] == "invalid_request"


def test_http_unknown_action(api):
    status, body = api("POST", {"action": "unsupported"})
    assert status == 400
    assert body == {
        "error": {
            "message": "unknown action: unsupported",
            "type": "invalid_request",
        }
    }


def test_http_body_size_limit(api):
    status, body = api("POST", raw=b" " * (64 * 1024 + 1))
    assert status == 413
    assert body["error"]["type"] == "invalid_request"
