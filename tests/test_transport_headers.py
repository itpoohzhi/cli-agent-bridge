"""Граница доверия: клиент, route-owned credential и фактический loopback POST.

Контракт W2-C: outbound_headers(client, configured, credential) -> dict[str, str].
До extraction измеряется настоящий legacy _open, а не отсутствие нового импорта.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
from collections.abc import Mapping
from typing import Any

import pytest

from core.backend_adapter import AllowEntry, _base_url_allowed
from tests.transport_test_support import (
    RecordingSink,
    RecordingUpstream,
    make_adapter,
    semantic_equal,
)

CONTROL_HEADERS = (
    "Authorization", "X-Api-Key", "Cookie", "Proxy-Authorization",
    "X-Transport-Seed", "X-Exclude-Transports", "X-Subagent-Id",
    "X-Internal-Service-Key", "X-Bypass-Model-Filter", "X-Turn-Owner-Token",
    "X-Bridge-Unlisted-Control",
)
DROP_NAMES = frozenset(name.lower() for name in CONTROL_HEADERS)
SSE = b'data: {"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}]}\n\n'


@pytest.fixture(autouse=True)
def transport_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Настройки меняются только через откатываемый monkeypatch."""
    monkeypatch.setenv("BRIDGE_CONNECTION_POOLING_ENABLED", "false")
    monkeypatch.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "false")
    monkeypatch.setenv("BRIDGE_PASSTHROUGH_PRESEND_MAX_RETRIES", "0")
    monkeypatch.setenv("BRIDGE_TRANSPORT_ROUTING_ENABLED", "false")
    monkeypatch.delenv("BRIDGE_DEFAULT_BASE_URL_POLICY", raising=False)


def _attacker_headers(casing: str) -> dict[str, str]:
    transform = getattr(str, casing)
    headers = {transform(name): "untrusted-test-value" for name in CONTROL_HEADERS}
    headers.update({
        transform("Connection"): "X-Connection-Secret",
        transform("X-Connection-Secret"): "must-not-leak",
        transform("X-Request-Id"): "public-request-id",
        transform("Content-Type"): "application/json",
    })
    return headers


def _legacy_headers(
    client: Mapping[str, str], configured: Mapping[str, str], credential: str,
) -> dict[str, str]:
    with RecordingUpstream() as upstream:
        adapter = make_adapter(upstream, {
            "api_key": credential, "per_request_headers": dict(configured),
        })
        try:
            connection = adapter._open("/v1/chat/completions", b"{}", client)
            try:
                response = connection.getresponse()
                assert response.status == 200
                response.read()
            finally:
                connection.close()
            assert upstream.post_count == 1
            return dict(upstream.requests[0].headers)
        finally:
            adapter.shutdown()


def _boundary_headers(
    client: Mapping[str, str], configured: Mapping[str, str], credential: str,
) -> dict[str, str]:
    """Новый чистый шов либо наблюдаемый старый wire, без подавления ImportError."""
    name = "core.passthrough_headers"
    if importlib.util.find_spec(name) is None:
        return _legacy_headers(client, configured, credential)
    module = importlib.import_module(name)
    return module.outbound_headers(client, configured, credential)


def _leaked(headers: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted(
        (name.lower(), value)
        for name, value in headers.items()
        if name.lower() in DROP_NAMES - {"authorization"}
        or name.lower().startswith("x-bridge-")
        or name.lower() == "x-connection-secret"
    ))


@pytest.mark.semantic_red("outbound_control_header_leak")
@pytest.mark.parametrize("casing", ["lower", "upper", "swapcase"])
def test_stage_w2_c_case_insensitive_trust_boundary(casing: str) -> None:
    actual = _boundary_headers(_attacker_headers(casing), {}, "route-test-key")
    authorization = [value for name, value in actual.items() if name.lower() == "authorization"]
    semantic_equal(
        (_leaked(actual), authorization),
        ((), ["Bearer route-test-key"]),
        "outbound_control_header_leak",
    )


@pytest.mark.semantic_red("configured_header_boundary_bypass")
def test_stage_w2_c_final_filter_after_configured_overrides() -> None:
    configured = _attacker_headers("swapcase")
    configured["aUtHoRiZaTiOn"] = "Bearer config-must-not-win"
    configured["X-Public-Route-Metadata"] = "keep-me"
    actual = _boundary_headers({}, configured, "route-test-key")
    auth = [value for name, value in actual.items() if name.lower() == "authorization"]
    public = {name.lower(): value for name, value in actual.items()}
    semantic_equal(
        (_leaked(actual), auth, public.get("x-public-route-metadata")),
        ((), ["Bearer route-test-key"], "keep-me"),
        "configured_header_boundary_bypass",
    )


def _send(
    upstream: RecordingUpstream, request: dict[str, Any],
    headers: Mapping[str, str], config: Mapping[str, Any],
) -> RecordingSink:
    adapter, sink = make_adapter(upstream, config), RecordingSink()
    try:
        adapter.handle(
            path="/v1/chat/completions", raw_body=json.dumps(request).encode(),
            request=request, headers=headers, sink=sink,
        )
        return sink
    finally:
        adapter.shutdown()


@pytest.mark.semantic_red("external_wire_controls_and_body_seed")
@pytest.mark.parametrize("stream", [False, True])
def test_external_origin_receives_no_controls_or_body_seed(stream: bool) -> None:
    request = {"model": "m", "messages": [], "stream": stream, "transport_seed": "body-seed"}
    with RecordingUpstream() as upstream:
        if stream:
            upstream.respond = lambda handler, body: upstream.sse(handler, SSE + b"data: [DONE]\n\n")
        sink = _send(upstream, request, _attacker_headers("swapcase"), {"api_key": "route-test-key"})
        assert sink.status == 200
        assert upstream.post_count == 1
        record = upstream.requests[0]
        sent = json.loads(record.body)
        semantic_equal(
            (_leaked(dict(record.headers)), "transport_seed" in sent),
            ((), False), "external_wire_controls_and_body_seed",
        )


@pytest.mark.semantic_red("configured_env_missing_must_not_send")
@pytest.mark.parametrize("name,value", [
    ("W0_TRANSPORT_TEST_ROUTE_CREDENTIAL", None),
    ("W0_TRANSPORT_TEST_ROUTE_CREDENTIAL", ""),
    ("W0_TRANSPORT_TEST_ROUTE_CREDENTIAL", " \t"),
    ("invalid env reference", None),
])
def test_missing_configured_env_is_not_client_or_static_fallback(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str | None,
) -> None:
    if value is None:
        monkeypatch.delenv(name, raising=False)
    else:
        monkeypatch.setenv(name, value)
    with RecordingUpstream() as upstream:
        _send(upstream, {"model": "m"}, {"Authorization": "Bearer client-test-key"}, {
            "api_key_env": name, "api_key": "static-fallback-must-not-win",
        })
        semantic_equal(upstream.post_count, 0, "configured_env_missing_must_not_send")


@pytest.mark.semantic_red("credential_change_must_be_observed_before_send")
@pytest.mark.parametrize("replacement", [None, "rotated-test-key"])
def test_configured_env_revocation_and_rotation_are_live(
    monkeypatch: pytest.MonkeyPatch, replacement: str | None,
) -> None:
    name = "W0_TRANSPORT_TEST_ROUTE_CREDENTIAL"
    monkeypatch.setenv(name, "initial-test-key")
    with RecordingUpstream() as upstream:
        adapter = make_adapter(upstream, {"api_key_env": name})
        try:
            if replacement is None:
                monkeypatch.delenv(name)
            else:
                monkeypatch.setenv(name, replacement)
            adapter.handle(
                path="/v1/chat/completions", raw_body=b'{"model":"m"}',
                request={"model": "m"}, headers={}, sink=RecordingSink(),
            )
            auth = [
                value for record in upstream.requests
                for key, value in record.headers if key.lower() == "authorization"
            ]
            expected = [] if replacement is None else ["Bearer rotated-test-key"]
            semantic_equal(auth, expected, "credential_change_must_be_observed_before_send")
        finally:
            adapter.shutdown()


@pytest.mark.parametrize("source", ["client", "configured"])
def test_header_values_cannot_inject_crlf(source: str) -> None:
    malicious = {"X-Public-Metadata": "safe\r\nAuthorization: Bearer injected"}
    client, configured = (malicious, {}) if source == "client" else ({}, malicious)
    with pytest.raises(ValueError):
        _boundary_headers(client, configured, "route-test-key")


@pytest.mark.semantic_red("provider_allowlist_self_grants_remote_egress")
def test_provider_allowlist_only_narrows_central_egress() -> None:
    url = "https://untrusted.invalid:443/v1"
    grant = AllowEntry(scheme="https", host="untrusted.invalid", port=443, path_prefix="/v1")
    actual = _base_url_allowed("self-grant", url, {"self-grant": [grant]})
    semantic_equal(actual, False, "provider_allowlist_self_grants_remote_egress")


@pytest.mark.parametrize("url", [
    "http://127.0.0.1.evil.invalid:10830/v1",
    "http://user:pass@127.0.0.1:10830/v1",
    "http://127.0.0.1:10830/v1?token=synthetic",
    "http://127.0.0.1:10830/v1#fragment",
])
def test_egress_rejects_remote_suffix_userinfo_and_url_controls(url: str) -> None:
    assert not _base_url_allowed("external", url, None)


@pytest.mark.semantic_red("encoded_or_dot_path_egress_bypass")
@pytest.mark.parametrize("path", ["/../v1", "/%2e%2e/v1", "/sg-openai/../v1"])
def test_egress_rejects_traversal_even_with_provider_grant(path: str) -> None:
    url = "http://127.0.0.1:10830" + path
    grant = AllowEntry(port=10830, path_prefix=path)
    actual = _base_url_allowed("external", url, {"external": [grant]})
    semantic_equal(actual, False, "encoded_or_dot_path_egress_bypass")
