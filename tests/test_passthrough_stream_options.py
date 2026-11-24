"""Tests for passthrough stream_options helpers and claude-p usage policy."""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from core.passthrough_adapter_runtime import PassthroughRequest, RuntimeOptions, _RequestRuntime

from core.passthrough_stream_options import (
    BoundedNegativeCache,
    classify_400_for_stream_options,
    model_scope_hash,
    prepare_stream_usage_body,
    should_retry_stream_options,
    strip_stream_options,
    supports_stream_options,
)

_ROOT = Path(__file__).resolve().parents[1]

NEURALWATT_400 = (
    b'{"error":{"message":"1 validation error for Request\\nstream_options\\n'
    b'  Extra inputs are not permitted (type: extra_forbidden)",'
    b'"type":"invalid_request_error"}}'
)
OPENCODE_GO_400 = (
    b"{'error':{'message':'Unknown parameter: stream_options is not supported'}}"
    .replace(b"'", b'"')
)
CONTEXT_LENGTH_400 = (
    b'{"error":{"code":"context_length_exceeded",'
    b'"message":"This model maximum context length is 4096 tokens"}}'
)
TOOLS_400 = b"{'error':{'message':'Invalid value for 'tools': array expected'}}".replace(
    b"'", b'"'
)


def _load_usage_policy() -> ModuleType:
    path = _ROOT / "bridges" / "claude-p-bridge" / "usage_policy.py"
    spec = importlib.util.spec_from_file_location("claude_p_usage_policy", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


usage_policy = _load_usage_policy()


def _body(**payload: Any) -> bytes:
    return json.dumps(payload).encode("utf-8")


def test_supports_stream_options_declarative() -> None:
    assert supports_stream_options("/v1/chat/completions", None) is True
    assert supports_stream_options("/v1/chat/completions", {}) is True
    assert (
        supports_stream_options(
            "/v1/chat/completions", {"supports_stream_options": True}
        )
        is True
    )
    assert (
        supports_stream_options(
            "/v1/chat/completions", {"supports_stream_options": False}
        )
        is False
    )
    assert (
        supports_stream_options(
            "/v1/chat/completions", {"supports_stream_options": None}
        )
        is True
    )
    assert supports_stream_options("/v1/embeddings", {"supports_stream_options": True}) is False


def test_supports_stream_options_no_model_name_hardcode() -> None:
    source = (_ROOT / "core" / "passthrough_stream_options.py").read_text(
        "utf-8"
    ).lower()
    assert "claude" not in source
    assert "anthropic" not in source


def test_model_scope_hash_is_opaque_and_stable() -> None:
    assert model_scope_hash("gpt-x") == model_scope_hash("gpt-x")
    assert len(model_scope_hash("gpt-x")) == 12
    assert model_scope_hash("gpt-x") != model_scope_hash("gpt-y")
    assert model_scope_hash(None) == model_scope_hash("")


def test_prepare_injects_for_stream_without_options() -> None:
    raw = _body(model="m", stream=True, messages=[{"role": "user", "content": "hi"}])
    out, injected = prepare_stream_usage_body(
        "/v1/chat/completions", {"model": "m"}, raw,
        enabled=True, supports=True, negative_hit=False,
    )
    assert injected is True
    data = json.loads(out)
    assert data["stream_options"]["include_usage"] is True
    assert data["messages"] == [{"role": "user", "content": "hi"}]


def test_prepare_never_overwrites_client_include_usage() -> None:
    raw = _body(stream=True, stream_options={"include_usage": False})
    out, injected = prepare_stream_usage_body(
        "/v1/chat/completions", {}, raw,
        enabled=True, supports=True, negative_hit=False,
    )
    assert injected is False
    assert out == raw


def test_prepare_skips_non_stream_and_guards() -> None:
    stream = _body(stream=True)
    non_stream = _body(stream=False)
    assert prepare_stream_usage_body(
        "/v1/chat/completions", {}, non_stream,
        enabled=True, supports=True, negative_hit=False,
    ) == (non_stream, False)
    assert prepare_stream_usage_body(
        "/v1/chat/completions", {}, stream,
        enabled=False, supports=True, negative_hit=False,
    ) == (stream, False)
    assert prepare_stream_usage_body(
        "/v1/chat/completions", {}, stream,
        enabled=True, supports=False, negative_hit=False,
    ) == (stream, False)
    assert prepare_stream_usage_body(
        "/v1/chat/completions", {}, stream,
        enabled=True, supports=True, negative_hit=True,
    ) == (stream, False)
    assert prepare_stream_usage_body(
        "/v1/other", {}, stream,
        enabled=True, supports=True, negative_hit=False,
    ) == (stream, False)


def test_strip_stream_options() -> None:
    raw = _body(stream=True, stream_options={"include_usage": True}, model="m")
    stripped = strip_stream_options(raw)
    assert "stream_options" not in json.loads(stripped)
    assert json.loads(stripped)["model"] == "m"
    assert strip_stream_options(b"not json") == b"not json"


def test_classify_400_fixtures() -> None:
    assert classify_400_for_stream_options(400, NEURALWATT_400) == "stream_options_rejected"
    assert classify_400_for_stream_options(400, OPENCODE_GO_400) == "stream_options_rejected"
    assert classify_400_for_stream_options(400, CONTEXT_LENGTH_400) == "other_400"
    assert classify_400_for_stream_options(400, TOOLS_400) == "other_400"
    assert classify_400_for_stream_options(401, NEURALWATT_400) == "not_400"
    plain = b"{'error':{'message':'stream_options: see docs'}}".replace(b"'", b'"')
    assert classify_400_for_stream_options(400, plain) == "other_400"


def test_negative_cache_ttl_and_bounded_eviction() -> None:
    cache = BoundedNegativeCache(ttl_s=10.0, max_entries=2)
    key_a = ("b1", "e1", model_scope_hash("m1"), "v1")
    cache.mark_rejected(key_a, now=100.0)
    assert cache.is_rejected(key_a, now=105.0) is True
    assert cache.is_rejected(key_a, now=111.0) is False
    cache.clear()
    cache.mark_rejected(key_a, now=200.0)
    cache.mark_rejected(("b1", "e1", model_scope_hash("m2"), "v1"), now=201.0)
    cache.mark_rejected(("b2", "e2", model_scope_hash("m1"), "v2"), now=202.0)
    assert cache.is_rejected(key_a, now=203.0) is False
    assert cache.is_rejected(("b1", "e1", model_scope_hash("m2"), "v1"), now=203.0) is True
    assert cache.is_rejected(("b2", "e2", model_scope_hash("m1"), "v2"), now=203.0) is True


def test_negative_cache_scope_isolation() -> None:
    cache = BoundedNegativeCache(ttl_s=60.0, max_entries=16)
    base = ("b1", "e1", model_scope_hash("m1"), "v1")
    cache.mark_rejected(base, now=1.0)
    assert cache.is_rejected(("b2", "e1", model_scope_hash("m1"), "v1"), now=2.0) is False
    assert cache.is_rejected(("b1", "e2", model_scope_hash("m1"), "v1"), now=2.0) is False
    assert cache.is_rejected(("b1", "e1", model_scope_hash("m2"), "v1"), now=2.0) is False
    assert cache.is_rejected(("b1", "e1", model_scope_hash("m1"), "v2"), now=2.0) is False
    assert cache.is_rejected(base, now=2.0) is True


def test_no_secret_leak_t_iso_i4() -> None:
    secret = "sk-secret-prompt-xyz"
    body = (
        "{'error':{'message':'Unknown parameter stream_options',"
        "'auth':'Bearer " + secret + "'}}"
    ).replace("'", '"').encode("utf-8")
    verdict = classify_400_for_stream_options(400, body)
    assert verdict == "stream_options_rejected"
    assert secret not in verdict
    cache = BoundedNegativeCache()
    key = ("b", "e", model_scope_hash("m"), "v1")
    cache.mark_rejected(key, now=1.0)
    assert secret not in repr(cache)
    assert all(secret not in part for part in key)


def test_should_retry_stream_options() -> None:
    kwargs: dict[str, Any] = {
        "status_code": 400,
        "body": NEURALWATT_400,
        "committed_to_client": False,
        "injected_by_hub": True,
        "attempt_index": 0,
    }
    assert should_retry_stream_options(**kwargs) is True
    assert should_retry_stream_options(**{**kwargs, "attempt_index": 1}) is False
    assert should_retry_stream_options(**{**kwargs, "injected_by_hub": False}) is False
    assert should_retry_stream_options(**{**kwargs, "committed_to_client": True}) is False
    assert should_retry_stream_options(**{**kwargs, "body": TOOLS_400}) is False
    assert should_retry_stream_options(**{**kwargs, "status_code": 500}) is False


def test_usage_policy_include_usage() -> None:
    emit = usage_policy.should_emit_terminal_usage
    assert emit(None) is False
    assert emit({}) is False
    assert emit("anything") is False
    assert emit({"include_usage": True}) is True
    assert emit({"include_usage": False}) is False
    assert emit(None, emit_when_unspecified=True) is True
    assert emit({}, emit_when_unspecified=True) is True


class _FakeLimits:
    poll_interval_s, reader_join_timeout_s, read_timeout_s = 0.05, 0.1, 30.0

    def __getattr__(self, _name: str) -> float:
        return 30.0


class _FakeSink:
    accepts_presend_errors = False

    def client_gone(self) -> bool:
        return False


class _FakeResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status, self.body = status, body


class _FakeAdapter:
    id, _port, config, limits = "b1", 8000, {}, _FakeLimits()

    def __init__(self) -> None:
        self.emit_calls: list[tuple[Any, Any, tuple[bytes, bool]]] = []
        self.respond_calls: list[Any] = []

    def _with_body_defaults(self, raw_body: bytes) -> bytes:
        return raw_body

    def _upstream_headers(self, raw_body: bytes, headers: Any, affinity_out: Any = None) -> dict[str, str]:
        return {}

    def _read_presend_body(self, response: Any) -> bytes:
        return response.body

    def _emit_response(self, response: Any, sink: Any, pre_read: tuple[bytes, bool]) -> bool:
        self.emit_calls.append((response, sink, pre_read))
        return True

    def _respond(self, response: Any, *args: Any, **kwargs: Any) -> bool:
        self.respond_calls.append(response)
        return True


def _make_runtime(adapter: _FakeAdapter, raw_body: bytes, req_map: dict[str, Any]) -> _RequestRuntime:
    opts = RuntimeOptions(
        sliding_enabled=lambda: False,
        deadlines_fn=lambda _limits, _internal: (time.monotonic() + 30.0, time.monotonic() + 10.0),
    )
    req = PassthroughRequest(path="/v1/chat/completions", raw_body=raw_body, request=req_map, headers={}, sink=_FakeSink())
    return _RequestRuntime(adapter, req, opts)


def test_runtime_injects_stream_options_include_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_PASSTHROUGH_STREAM_USAGE_ENABLED", "1")
    adapter = _FakeAdapter()
    rt1 = _make_runtime(
        adapter,
        _body(model="m", stream=True, messages=[{"role": "user", "content": "hi"}]),
        {"model": "m", "stream": True},
    )
    assert rt1._stream_options_injected is True
    assert json.loads(rt1.exchange.raw_body)["stream_options"] == {"include_usage": True}
    rt2 = _make_runtime(
        adapter,
        _body(model="m", stream=True, stream_options={"include_usage": False}),
        {"model": "m", "stream": True, "stream_options": {"include_usage": False}},
    )
    assert rt2._stream_options_injected is False
    assert json.loads(rt2.exchange.raw_body)["stream_options"] == {"include_usage": False}


def test_runtime_retries_once_on_schema_400_and_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_PASSTHROUGH_STREAM_USAGE_ENABLED", "1")
    adapter = _FakeAdapter()
    rt1 = _make_runtime(
        adapter,
        _body(model="m", stream=True, messages=[{"role": "user", "content": "hi"}]),
        {"model": "m", "stream": True},
    )
    rt1.response = _FakeResponse(400, b'{"error": {"message": "Unknown parameter: stream_options"}}')
    reopen_bodies: list[bytes] = []

    def fake_reopen() -> _FakeResponse:
        reopen_bodies.append(rt1.exchange.raw_body)
        ok = _FakeResponse(200, b"data: [DONE]\n\n")
        rt1.response = ok
        return ok

    monkeypatch.setattr(rt1, "_reopen_response", fake_reopen)
    rt1.respond()
    assert len(reopen_bodies) == 1 and "stream_options" not in json.loads(reopen_bodies[0])
    assert len(adapter.respond_calls) == 1 and adapter.respond_calls[0].status == 200
    assert adapter.emit_calls == []
    rt2 = _make_runtime(
        adapter,
        _body(model="m", stream=True, messages=[{"role": "user", "content": "next"}]),
        {"model": "m", "stream": True},
    )
    assert rt2._stream_options_injected is False
    assert "stream_options" not in json.loads(rt2.exchange.raw_body)


def test_runtime_no_retry_on_context_length_400(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_PASSTHROUGH_STREAM_USAGE_ENABLED", "1")
    adapter = _FakeAdapter()
    rt = _make_runtime(
        adapter,
        _body(model="m", stream=True, messages=[{"role": "user", "content": "hi"}]),
        {"model": "m", "stream": True},
    )
    err_400 = b'{"error": {"message": "context_length_exceeded"}}'
    rt.response = _FakeResponse(400, err_400)
    reopen_calls = 0

    def fake_reopen() -> _FakeResponse:
        nonlocal reopen_calls
        reopen_calls += 1
        return _FakeResponse(200, b"")

    monkeypatch.setattr(rt, "_reopen_response", fake_reopen)
    rt.respond()
    assert reopen_calls == 0
    assert rt._stream_opt_cache.is_rejected(rt._stream_opt_key, time.monotonic()) is False
    assert len(adapter.emit_calls) == 1
    assert adapter.emit_calls[0][0].status == 400 and adapter.emit_calls[0][2] == (err_400, False)
    assert adapter.respond_calls == []
