"""W3 (P0-S1): adversarial-безопасность GET /v1/observability против живого хаба.

Интеграция с server.Server(("127.0.0.1", 0), server.Handler) при изолированном
BRIDGE_DYNAMIC_CONFIG_PATH и TokenCache: loopback IPv4/IPv6 allowlist (200,
Cache-Control: no-store, ровно 5 ключей), non-loopback/Origin/Sec-Fetch-Site -> 403,
burst 20 -> 429 (Retry-After: 1), kill-switch/отсутствие флага -> 401; инвариант
GET /health — ровно 7 ключей. IPv6/non-loopback проверяются и на policy-boundary
serve_observability_get (handler.client_address).
"""

from __future__ import annotations

import http.client
import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server  # noqa: E402
from core.observability_endpoint import (  # noqa: E402
    ObservabilityRateLimiter,
    serve_observability_get,
)
from core.observability_policy import is_loopback_ip  # noqa: E402

_HEALTH_KEYS = frozenset(
    {
        "ok",
        "transport",
        "model",
        "active",
        "max_concurrent",
        "tool_emulation",
        "uptime_s",
    }
)
_OBS_KEYS = frozenset(
    {"schema_version", "service", "admission", "p12_pgid", "p13_rotation"}
)
_ADMISSION_KEYS = frozenset(
    {"active", "idle", "total", "limit", "max_idle_age_s", "overloaded_rejects"}
)
_CANARIES = ("sk-", "Bearer ", "detached_pgids", "db_path", str(ROOT), "/Users/")


def _prepare_env(monkeypatch, tmp_path, enabled) -> None:
    doc = {} if enabled is None else {"BRIDGE_LOOPBACK_OBSERVABILITY_ENABLED": enabled}
    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(cfg))
    monkeypatch.delenv("BRIDGE_KEY", raising=False)
    monkeypatch.delenv("DROID_DSH_BRIDGE_KEY", raising=False)
    monkeypatch.delenv("BRIDGE_LOOPBACK_OBSERVABILITY_ENABLED", raising=False)
    monkeypatch.setattr(
        server, "TOKEN_CACHE", server.TokenCache(path=tmp_path / "absent.env")
    )


def _get(port: int, headers: dict | None = None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5.0)
    try:
        conn.request("GET", "/v1/observability", headers=headers or {})
        resp = conn.getresponse()
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, resp.read()
    finally:
        conn.close()


def _serve_live(monkeypatch, tmp_path, probe, enabled=True):
    """Поднимает живой хаб, выполняет probe(port) и гарантированно гасит сервер."""
    _prepare_env(monkeypatch, tmp_path, enabled)
    httpd = server.Server(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        return probe(httpd.server_address[1])
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _assert_allowlist_payload(payload: dict) -> None:
    assert set(payload) == _OBS_KEYS, payload
    assert payload["schema_version"] == "1.0", payload
    assert payload["service"] == "hub", payload
    assert set(payload["p12_pgid"]) == {"active", "quarantined", "bound"}, payload
    assert _ADMISSION_KEYS <= set(payload["admission"]), payload
    text = json.dumps(payload)
    assert not any(canary in text for canary in _CANARIES), text


def _boundary_call(peer: str):
    """serve_observability_get на handler/policy boundary с произвольным peer."""
    sent: list[tuple] = []
    handler = SimpleNamespace(
        client_address=(peer, 5555),
        headers={},
        server=SimpleNamespace(admission_snapshot=lambda: {}),
        _send=lambda code, payload, extra_headers=None: sent.append(
            (code, payload, extra_headers or {})
        ),
    )
    seam = SimpleNamespace(
        snapshot_counts=lambda: {"active": [], "quarantined": [], "bound": []}
    )
    serve_observability_get(handler, seam, limiter=ObservabilityRateLimiter())
    assert len(sent) == 1, sent
    return sent[0]


def _health(port: int):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5.0)
    try:
        conn.request("GET", "/health")
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


def test_loopback_ipv4_live_allowlist_no_store(monkeypatch, tmp_path):
    def probe(port):
        return _get(port)

    status, headers, body = _serve_live(monkeypatch, tmp_path, probe)
    assert status == 200, (status, body[:400])
    assert headers.get("cache-control") == "no-store", headers
    _assert_allowlist_payload(json.loads(body))


def test_loopback_ipv6_boundary_returns_allowlist(monkeypatch, tmp_path):
    _prepare_env(monkeypatch, tmp_path, True)
    assert is_loopback_ip("::1")
    code, payload, extra = _boundary_call("::1")
    assert code == 200, payload
    assert extra.get("Cache-Control") == "no-store", extra
    _assert_allowlist_payload(payload)


def test_non_loopback_peer_denied_at_boundary(monkeypatch, tmp_path):
    _prepare_env(monkeypatch, tmp_path, True)
    assert is_loopback_ip("10.0.0.5") is False
    code, payload, extra = _boundary_call("10.0.0.5")
    assert code == 403, payload
    assert payload["error"]["code"] == 403, payload
    assert extra.get("Cache-Control") == "no-store", extra


def test_non_loopback_forwarded_headers_denied_live(monkeypatch, tmp_path):
    def probe(port):
        return _get(port, {"X-Forwarded-For": "10.0.0.5"})

    status, headers, body = _serve_live(monkeypatch, tmp_path, probe)
    assert status == 403, (status, body[:400])
    assert headers.get("cache-control") == "no-store", headers


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({"Origin": "https://evil.example"}, 403),
        ({"Sec-Fetch-Site": "cross-site"}, 403),
        ({"Sec-Fetch-Site": "same-origin"}, 200),
    ],
)
def test_origin_and_fetch_site_gates_live(monkeypatch, tmp_path, headers, expected):
    def probe(port):
        return _get(port, headers)

    status, resp_headers, body = _serve_live(monkeypatch, tmp_path, probe)
    assert status == expected, (status, body[:400])
    if expected == 200:
        _assert_allowlist_payload(json.loads(body))
    assert resp_headers.get("cache-control") == "no-store", resp_headers


def test_rate_limit_burst_20_then_429_retry_after(monkeypatch, tmp_path):
    def probe(port):
        return [_get(port) for _ in range(21)]

    results = _serve_live(monkeypatch, tmp_path, probe)
    assert [status for status, _h, _b in results[:20]] == [200] * 20, results
    status, headers, body = results[20]
    assert status == 429, (status, body[:400])
    assert headers.get("retry-after") == "1", headers
    assert headers.get("cache-control") == "no-store", headers
    assert json.loads(body)["error"]["code"] == 429, body


@pytest.mark.parametrize("enabled", [False, None])
def test_kill_switch_disabled_or_absent_returns_401(monkeypatch, tmp_path, enabled):
    def probe(port):
        return _get(port)

    status, _headers, body = _serve_live(monkeypatch, tmp_path, probe, enabled=enabled)
    assert status == 401, (status, body[:400])
    assert json.loads(body)["error"]["type"] == "auth_error", body


@pytest.mark.parametrize("enabled", [True, False])
def test_health_invariant_seven_keys(monkeypatch, tmp_path, enabled):
    status, body = _serve_live(monkeypatch, tmp_path, _health, enabled=enabled)
    assert status == 200
    assert set(json.loads(body)) == _HEALTH_KEYS, body
