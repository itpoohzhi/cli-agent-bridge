import http.client
import json
import math
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

import server

KEY = "test-bridge-key"
INTERNAL_KEY = "internal-test-key"
AUTH = {"Authorization": f"Bearer {KEY}"}


def _model(mid, owner, context_window=200000):
    return SimpleNamespace(
        id=mid, context_window=context_window, adapter=SimpleNamespace(owned_by=owner)
    )


FLEET_MODELS = [
    _model("claude-opus-5-5", "claude-p-bridge"),
    _model("claude-sonnet-5-5", "claude-p-bridge"),
    _model("gpt-6.1-sol", "openai-codex", 400000),
    _model("gemini-4-argon", "agy-bridge", 1000000),
    _model("deepseek-v4.1-flash", "opencode-zen-bridge", 128000),
    _model("deepseek-v4.1-flash-free", "opencode-zen-bridge", 128000),
]


@pytest.fixture
def port(monkeypatch):
    monkeypatch.setattr(server, "BACKENDS", SimpleNamespace(models=lambda: FLEET_MODELS, adapters=lambda: []))
    monkeypatch.setattr(server, "BRIDGE_KEY", KEY)
    monkeypatch.setattr(server, "_INTERNAL_SERVICE_KEY", INTERNAL_KEY)
    monkeypatch.setattr(server, "ADVERTISED_EFFORT_ALIASES", {
        "claude-sonnet-5-5-high": "claude-sonnet-5-5",
    })
    server._REFRESH_LAST.clear()
    server._MODELS_CACHE.clear()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.BridgeHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)


def _request(port, method, path, headers=None, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        send_headers = dict(headers or {})
        payload = None
        if body is not None:
            payload = json.dumps(body)
            send_headers.setdefault("Content-Type", "application/json")
        conn.request(method, path, body=payload, headers=send_headers)
        resp = conn.getresponse()
        raw = resp.read()
        data = json.loads(raw) if raw else None
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, data
    finally:
        conn.close()


# ---- Листинги и метаданные ----
@pytest.mark.parametrize(
    "path", ["/v1/providers/nope/v1/models", "/v1/models?provider=nope"]
)
def test_unknown_provider_returns_404(port, path):
    status, _, data = _request(port, "GET", path, AUTH)
    assert status == 404
    assert data["error"]["type"] == "invalid_request_error"


def test_auth_first_before_unknown_provider(port):
    # Без токена неизвестный провайдер отдаёт 401, а не 404
    status, _, _ = _request(port, "GET", "/v1/providers/nope/v1/models")
    assert status == 401
    status, _, _ = _request(port, "POST", "/v1/providers/nope/v1/chat/completions",
                            body={"model": "claude-opus-5-5", "messages": []})
    assert status == 401


def test_unknown_provider_chat_returns_404(port):
    status, _, _ = _request(
        port, "POST", "/v1/providers/nope/v1/chat/completions", AUTH,
        {"model": "claude-opus-5-5", "messages": []},
    )
    assert status == 404


def test_internal_models_hidden_from_listings(port):
    for path in ("/v1/models", "/v1/providers/opencode/v1/models"):
        _, _, data = _request(port, "GET", path, AUTH)
        ids = [m["id"] for m in data["data"]]
        assert "deepseek-v4.1-flash" not in ids
        assert "deepseek-v4.1-flash-free" not in ids


def test_provider_listing_returns_only_own_models(port):
    status, _, data = _request(port, "GET", "/v1/providers/claude-code/v1/models", AUTH)
    assert status == 200
    ids = [m["id"] for m in data["data"]]
    assert "claude-opus-5-5" in ids
    assert "claude-sonnet-5-5" in ids
    assert all(m["owned_by"] == "claude-p-bridge" for m in data["data"])

    _, _, via_query = _request(port, "GET", "/v1/models?provider=codex", AUTH)
    assert [m["id"] for m in via_query["data"]] == ["gpt-6.1-sol"]
    assert via_query["data"][0]["modalities"] == ["text", "image"]


def test_full_fleet_and_metadata_without_scope(port):
    _, _, data = _request(port, "GET", "/v1/models", AUTH)
    ids = [m["id"] for m in data["data"]]
    assert "claude-opus-5-5" in ids
    assert "claude-sonnet-5-5" in ids
    assert "gpt-6.1-sol" in ids
    assert "gemini-4-argon" in ids
    opus = next(m for m in data["data"] if m["id"] == "claude-opus-5-5")
    assert opus["context_window"] == opus["context_length"] == 200000
    assert opus["max_output_tokens"] == 64000
    assert opus["modalities"] == ["text"]
    assert opus["supports_thinking"] is True
    assert opus["supported_reasoning_efforts"] == ["low", "medium", "high"]
    assert opus["default_reasoning_effort"] == "high"
    assert opus["available"] is True


def test_if_none_match_returns_304(port):
    path = "/v1/providers/claude-code/v1/models"
    status, headers, _ = _request(port, "GET", path, AUTH)
    assert status == 200
    etag = headers["etag"]

    status, headers, data = _request(port, "GET", path, {**AUTH, "If-None-Match": etag})
    assert status == 304
    assert data is None
    assert headers["etag"] == etag

    status, _, _ = _request(port, "GET", path, {**AUTH, "If-None-Match": '"stale"'})
    assert status == 200


# ---- Чат и изоляция ----
@pytest.mark.parametrize("model", ["deepseek-v4.1-flash", "deepseek-v4.1-flash-free"])
def test_internal_model_forbidden_without_service_key(port, model):
    path = "/v1/providers/opencode/v1/chat/completions"
    body = {"model": model, "messages": []}

    status, _, _ = _request(port, "POST", path, AUTH, body)
    assert status == 403

    wrong = {**AUTH, "X-Internal-Service-Key": "wrong"}
    status, _, _ = _request(port, "POST", path, wrong, body)
    assert status == 403


def test_chat_model_outside_scope_returns_400(port):
    status, _, data = _request(
        port, "POST", "/v1/providers/codex/v1/chat/completions", AUTH,
        {"model": "claude-opus-5-5", "messages": []},
    )
    assert status == 400
    assert data["error"]["code"] == "model_not_in_provider_scope"


# ---- Refresh, rate-limit и stale-while-revalidate ----
def test_refresh_without_auth_returns_401(port):
    status, _, _ = _request(port, "POST", "/v1/models/refresh")
    assert status == 401


def test_refresh_schema_and_rate_limit(port):
    first, headers, data = _request(port, "POST", "/v1/models/refresh", AUTH)
    assert first == 200
    assert "etag" in headers
    assert data["status"] == "complete"
    assert data["failed_upstreams"] == []
    assert all(m["available"] is True for m in data["data"])

    second, headers, _ = _request(port, "POST", "/v1/models/refresh", AUTH)
    assert second == 429
    retry = int(headers["retry-after"])
    assert 1 <= retry <= 10


def test_refresh_key_normalization_and_bounding():
    def fake(auth, ip="127.0.0.1"):
        return SimpleNamespace(headers={"Authorization": auth}, client_address=(ip, 1234))

    assert server._refresh_client_key(fake("Bearer  tok ")) == server._refresh_client_key(fake("bearer tok"))
    assert server._refresh_client_key(fake("Bearer tok")) != server._refresh_client_key(fake("Bearer other"))
    assert server._refresh_client_key(fake("", "10.0.0.1")) == "ip:10.0.0.1"

    server._REFRESH_LAST.clear()
    for i in range(server._REFRESH_MAX_ENTRIES + 50):
        assert server._refresh_acquire(f"k{i}", now=100.0) is None
    assert len(server._REFRESH_LAST) <= server._REFRESH_MAX_ENTRIES
