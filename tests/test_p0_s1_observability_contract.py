"""W0 (P0-S1): контракт loopback-наблюдаемости /v1/observability + policy-юниты W1-A.

Красный репро: на базе 06f28762 безключевой GET /v1/observability получает 401
(do_GET не знает маршрута), целевой контракт — 200, Cache-Control: no-store и
строгий allowlist-JSON. Policy-юниты импортируют core.http_disconnect_policy и
core.observability_policy ТОЛЬКО локально внутри функций: до W1 модулей нет,
top-level импорт уронил бы коллекцию (VER-001: нужен rc==1, а не rc==2).
"""

from __future__ import annotations

import errno
import http.client
import json
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server  # noqa: E402


def _get(port: int, path: str, timeout: float = 5.0):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        return resp.status, dict(resp.getheaders()), resp.read()
    finally:
        conn.close()


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


def _prepare_loopback_env(monkeypatch, tmp_path) -> None:
    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text(
        json.dumps({"BRIDGE_LOOPBACK_OBSERVABILITY_ENABLED": True}), encoding="utf-8"
    )
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(cfg))
    monkeypatch.delenv("BRIDGE_KEY", raising=False)
    monkeypatch.delenv("DROID_DSH_BRIDGE_KEY", raising=False)
    monkeypatch.setattr(
        server, "TOKEN_CACHE", server.TokenCache(path=tmp_path / "absent.env")
    )


def _assert_allowlist_payload(payload: dict) -> None:
    assert set(payload) == {
        "schema_version",
        "service",
        "admission",
        "p12_pgid",
        "p13_rotation",
    }
    assert payload["schema_version"] == "1.0"
    assert payload["service"] == "hub"
    assert set(payload["p12_pgid"]) == {"active", "quarantined", "bound"}
    assert {
        "active",
        "idle",
        "total",
        "limit",
        "max_idle_age_s",
        "overloaded_rejects",
    } <= set(payload["admission"])
    rotation_text = json.dumps(payload["p13_rotation"]).lower()
    assert "detached_pgids" not in rotation_text and "db_path" not in rotation_text
    assert "token" not in rotation_text and str(ROOT) not in rotation_text


@pytest.mark.red_repro
def test_red_repro_hub_loopback_observability_returns_allowlist_json(
    monkeypatch, tmp_path
):
    _prepare_loopback_env(monkeypatch, tmp_path)
    httpd = server.Server(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        port = httpd.server_address[1]
        status, headers, body = _get(port, "/v1/observability")
        h_status, _h_headers, h_body = _get(port, "/health")
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
    assert status == 200, (status, body[:400])
    lowered = {k.lower(): v for k, v in headers.items()}
    assert lowered.get("cache-control") == "no-store", headers
    _assert_allowlist_payload(json.loads(body))
    assert h_status == 200
    assert set(json.loads(h_body)) == _HEALTH_KEYS


def test_disconnect_policy_classification():
    from core.http_disconnect_policy import (
        classify_client_disconnect,
        format_client_disconnect_log,
    )

    class ClientGone(Exception):
        pass

    def is_disconnect(exc: BaseException) -> bool:
        return classify_client_disconnect(exc, client_gone_cls=ClientGone)

    assert is_disconnect(BrokenPipeError(errno.EPIPE, "Broken pipe"))
    assert is_disconnect(ConnectionResetError(errno.ECONNRESET, "reset by peer"))
    assert is_disconnect(ConnectionAbortedError(errno.ECONNABORTED, "aborted"))
    assert is_disconnect(OSError(errno.EPIPE, "plain oserror EPIPE"))
    chained = OSError(errno.EPIPE, "flush failed")
    wrapper = RuntimeError("delivery failed")
    wrapper.__cause__ = chained
    assert is_disconnect(wrapper)
    assert is_disconnect(ClientGone("user cancel"))
    assert not is_disconnect(RuntimeError("backend exploded"))
    assert not is_disconnect(OSError(errno.ENOSPC, "no space left on device"))
    line = format_client_disconnect_log(
        "127.0.0.1:54321", BrokenPipeError(errno.EPIPE, "Broken pipe")
    )
    assert "\n" not in line and "\r" not in line
    assert len(line.encode("utf-8")) <= 78, line


def test_disconnect_policy_context_group_and_byte_cap():
    from core.http_disconnect_policy import (
        classify_client_disconnect,
        format_client_disconnect_log,
    )

    ctx_bug = RuntimeError("cleanup bug after disconnect")
    ctx_bug.__context__ = BrokenPipeError(errno.EPIPE, "prior disconnect")
    assert not classify_client_disconnect(ctx_bug)
    assert not classify_client_disconnect(
        ExceptionGroup("mixed", [BrokenPipeError(), RuntimeError("boom")])
    )
    assert classify_client_disconnect(
        ExceptionGroup("pure", [BrokenPipeError(), ConnectionResetError()])
    )
    non_ascii = format_client_disconnect_log(
        "юникод-" * 10, ConnectionAbortedError("x")
    )
    assert len(non_ascii.encode("utf-8")) <= 78, non_ascii
    assert "exc=ConnectionAbortedError" in non_ascii, non_ascii


def test_observability_policy_loopback_origin_ratelimit_and_allowlist():
    from core import observability_policy as op

    assert op.is_loopback_ip("127.0.0.1")
    assert op.is_loopback_ip("::1")
    assert not op.is_loopback_ip("10.0.0.5")
    assert op.is_observability_request_allowed("127.0.0.1", {})
    assert not op.is_observability_request_allowed("10.0.0.5", {})
    assert not op.is_observability_request_allowed(
        "127.0.0.1", {"Origin": "https://evil.example"}
    )
    assert not op.is_observability_request_allowed(
        "127.0.0.1", {"Sec-Fetch-Site": "cross-site"}
    )
    assert op.is_observability_request_allowed(
        "127.0.0.1", {"Sec-Fetch-Site": "same-origin"}
    )
    state = {}
    verdicts = [
        op.step_token_bucket(state, 1000.0, rate_per_s=10.0, burst=20.0)
        for _ in range(20)
    ]
    assert all(verdicts)
    assert op.step_token_bucket(state, 1000.0, rate_per_s=10.0, burst=20.0) is False
    assert op.step_token_bucket(state, 1000.2, rate_per_s=10.0, burst=20.0) is True
    _assert_projection_allowlist(op)


def _assert_projection_allowlist(op) -> None:
    admission = {
        "active": 1,
        "idle": 2,
        "total": 3,
        "limit": 128,
        "max_idle_age_s": 60.0,
        "overloaded_rejects": 0,
    }
    pgid = {"active": [11], "quarantined": [], "bound": [11], "detached_pgids": [99]}
    rotation = {
        "enabled": True,
        "rotations": 2,
        "db_path": "/Users/x/.dsh/db",
        "token": "sk-secret",
    }
    projected = op.project_observability_payload(admission, pgid, rotation)
    assert set(projected) == {
        "schema_version",
        "service",
        "admission",
        "p12_pgid",
        "p13_rotation",
    }
    assert projected["schema_version"] == "1.0" and projected["service"] == "hub"
    assert set(projected["p12_pgid"]) == {"active", "quarantined", "bound"}
    assert set(projected["admission"]) == set(admission)
    text = json.dumps(projected)
    assert (
        "detached_pgids" not in text
        and "db_path" not in text
        and "sk-secret" not in text
    )


def test_p12_seam_snapshot_counts_defaults():
    from core.p12_hub_cancel_seam import HubP12CancelSeam

    assert HubP12CancelSeam().snapshot_counts() == {
        "active": 0,
        "quarantined": 0,
        "bound": 128,
    }
