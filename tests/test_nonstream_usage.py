"""Unit tests for core.nonstream_usage helpers (W1)."""

from __future__ import annotations

import copy
import json
import time
from typing import Any

import pytest

from core.nonstream_aggregator import aggregate_events
from core.nonstream_usage import extract_usage, internal_usage_injected
from core.passthrough_adapter_runtime import (
    PassthroughRequest,
    RuntimeOptions,
    _RequestRuntime,
)


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

    def _upstream_headers(
        self, raw_body: bytes, headers: Any, affinity_out: Any = None
    ) -> dict[str, str]:
        return {}

    def _read_presend_body(self, response: Any) -> bytes:
        return response.body

    def _emit_response(
        self, response: Any, sink: Any, pre_read: tuple[bytes, bool]
    ) -> bool:
        self.emit_calls.append((response, sink, pre_read))
        return True

    def _respond(self, response: Any, *args: Any, **kwargs: Any) -> bool:
        self.respond_calls.append(response)
        return True


def _make_internal_runtime(
    adapter: _FakeAdapter, monkeypatch: pytest.MonkeyPatch
) -> _RequestRuntime:
    monkeypatch.setattr(
        "core.passthrough_adapter_runtime.passthrough_window", lambda *_args: None
    )
    raw = json.dumps({"model": "m", "messages": []}).encode()
    request = PassthroughRequest(
        path="/v1/chat/completions",
        raw_body=raw,
        request={"model": "m", "stream": False},
        headers={},
        sink=_FakeSink(),
    )
    return _RequestRuntime(
        adapter,
        request,
        RuntimeOptions(
            sliding_enabled=lambda: False,
            deadlines_fn=lambda _limits, _internal: (
                time.monotonic() + 30,
                time.monotonic() + 10,
            ),
        ),
    )


def _aggregate_chunks(*chunks: dict) -> dict:
    events = []
    for chunk in chunks:
        data = json.dumps(chunk)
        events.append((f"data: {data}\n\n".encode(), data))
    events.append((b"data: [DONE]\n\n", "[DONE]"))
    return json.loads(aggregate_events(events, None, 1 << 20))


class TestExtractUsage:
    def test_kimi_choices_usage_fallback(self) -> None:
        chunk = {
            "usage": None,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "usage": {
                        "prompt_tokens": 91,
                        "completion_tokens": 31,
                        "total_tokens": 122,
                        "prompt_tokens_details": {"cached_tokens": 64},
                    },
                }
            ],
        }
        original = copy.deepcopy(chunk)
        result = extract_usage(chunk)
        assert result == chunk["choices"][0]["usage"]
        assert chunk == original, "extract_usage must not mutate input"

    def test_top_level_usage_priority(self) -> None:
        top = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        chunk = {
            "usage": top,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "usage": {
                        "prompt_tokens": 1,
                        "completion_tokens": 1,
                        "total_tokens": 2,
                    },
                }
            ],
        }
        assert extract_usage(chunk) is top

    def test_fail_open_missing_usage(self) -> None:
        assert extract_usage({}) is None
        assert extract_usage({"usage": None}) is None
        assert extract_usage({"usage": "not-a-dict"}) is None
        assert extract_usage({"choices": [{"index": 0, "delta": {}}]}) is None

    def test_fail_open_non_dict_choices_usage(self) -> None:
        chunk = {"choices": [{"index": 0, "delta": {}, "usage": None}]}
        assert extract_usage(chunk) is None
        chunk2 = {"choices": [{"index": 0, "delta": {}, "usage": 42}]}
        assert extract_usage(chunk2) is None

    def test_multiple_choices_usage_not_in_zero(self) -> None:
        expected = {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70}
        chunk = {
            "choices": [
                {"index": 0, "delta": {}, "usage": None},
                {"index": 1, "delta": {}, "usage": expected},
            ]
        }
        assert extract_usage(chunk) is expected

    def test_invalid_choices_types(self) -> None:
        chunk = {
            "choices": [
                "not-a-dict",
                None,
                42,
                {"index": 0, "delta": {}, "usage": {"prompt_tokens": 1}},
            ]
        }
        assert extract_usage(chunk) == {"prompt_tokens": 1}

    def test_choices_not_a_list(self) -> None:
        chunk = {"choices": "not-a-list", "usage": None}
        assert extract_usage(chunk) is None

    def test_empty_choices_list(self) -> None:
        chunk = {"choices": []}
        assert extract_usage(chunk) is None


class TestInternalUsageInjected:
    def test_injected_true(self) -> None:
        request = json.dumps({"model": "kimi-k3.1-pro", "messages": []}).encode()
        internal = json.dumps(
            {
                "model": "kimi-k3.1-pro",
                "messages": [],
                "stream_options": {"include_usage": True},
            }
        ).encode()
        assert internal_usage_injected(request, internal) is True

    def test_not_injected_when_flag_disabled(self) -> None:
        request = json.dumps({"model": "kimi-k3.1-pro", "messages": []}).encode()
        internal = json.dumps({"model": "kimi-k3.1-pro", "messages": []}).encode()
        assert internal_usage_injected(request, internal) is False

    def test_client_already_sent_include_usage(self) -> None:
        request = json.dumps(
            {
                "model": "kimi-k3.1-pro",
                "messages": [],
                "stream_options": {"include_usage": True},
            }
        ).encode()
        internal = json.dumps(
            {
                "model": "kimi-k3.1-pro",
                "messages": [],
                "stream_options": {"include_usage": True},
            }
        ).encode()
        assert internal_usage_injected(request, internal) is False

    def test_internal_body_none(self) -> None:
        request = json.dumps({"model": "kimi-k3.1-pro"}).encode()
        assert internal_usage_injected(request, None) is False

    def test_internal_body_invalid_json(self) -> None:
        request = json.dumps({"model": "kimi-k3.1-pro"}).encode()
        assert internal_usage_injected(request, b"not-json") is False

    def test_request_body_invalid_json(self) -> None:
        assert internal_usage_injected(b"not-json", b"{}") is False

    def test_internal_stream_options_not_dict(self) -> None:
        request = json.dumps({"model": "m"}).encode()
        internal = json.dumps({"stream_options": "invalid"}).encode()
        assert internal_usage_injected(request, internal) is False

    def test_client_stream_options_not_dict(self) -> None:
        request = json.dumps({"stream_options": "invalid"}).encode()
        internal = json.dumps({"stream_options": {"include_usage": True}}).encode()
        assert internal_usage_injected(request, internal) is True

    def test_include_usage_false_in_internal(self) -> None:
        request = json.dumps({"model": "m"}).encode()
        internal = json.dumps({"stream_options": {"include_usage": False}}).encode()
        assert internal_usage_injected(request, internal) is False


class TestAggregatorUsage:
    @staticmethod
    def _chunks(usage: object = None, choice_usage: object = None) -> list[dict]:
        return [
            {
                "id": "chatcmpl-kimi",
                "model": "kimi-k3.1-pro",
                "created": 1,
                "choices": [
                    {"index": 0, "delta": {"content": "ok"}, "finish_reason": None}
                ],
            },
            {
                "usage": usage,
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop",
                        "usage": choice_usage,
                    }
                ],
            },
        ]

    def test_aggregator_kimi_choices_usage_fallback(self) -> None:
        body = _aggregate_chunks(
            *self._chunks(
                choice_usage={
                    "prompt_tokens": 91,
                    "completion_tokens": 31,
                    "total_tokens": 122,
                    "prompt_tokens_details": {"cached_tokens": 64},
                }
            )
        )
        assert body["usage"] == {
            "prompt_tokens": 91,
            "completion_tokens": 31,
            "total_tokens": 122,
            "prompt_tokens_details": {"cached_tokens": 64},
        }

    def test_aggregator_qwen_top_level_usage_priority(self) -> None:
        top = {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}
        body = _aggregate_chunks(
            *self._chunks(
                usage=top,
                choice_usage={
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            )
        )
        assert body["usage"] == top

    def test_aggregator_no_usage_fail_open(self) -> None:
        body = _aggregate_chunks(*self._chunks())
        assert "usage" not in body
        assert body["choices"][0]["message"]["content"] == "ok"


class TestInternalStreamFallback400:
    @staticmethod
    def _enable_internal_stream(monkeypatch: pytest.MonkeyPatch, usage: str) -> None:
        monkeypatch.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
        monkeypatch.setenv("BRIDGE_INTERNAL_STREAM_USAGE_ENABLED", usage)

    def test_internal_stream_fallback_400_strips_and_extracts_usage(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._enable_internal_stream(monkeypatch, "true")
        adapter = _FakeAdapter()
        rt = _make_internal_runtime(adapter, monkeypatch)
        assert rt.internal is True
        assert rt._stream_options_injected is True
        assert (
            json.loads(rt.exchange.raw_body)["stream_options"]["include_usage"] is True
        )
        rt.response = _FakeResponse(
            400, b'{"error": {"message": "Unknown parameter: stream_options"}}'
        )
        reopen_bodies: list[bytes] = []

        def fake_reopen() -> _FakeResponse:
            reopen_bodies.append(rt.exchange.raw_body)
            ok = _FakeResponse(200, b"")
            rt.response = ok
            return ok

        monkeypatch.setattr(rt, "_reopen_response", fake_reopen)
        rt.respond()
        assert len(reopen_bodies) == 1 and "stream_options" not in json.loads(
            reopen_bodies[0]
        )
        assert rt._stream_options_injected is False
        assert (
            rt._stream_opt_cache.is_rejected(rt._stream_opt_key, time.monotonic())
            is True
        )
        assert (
            len(adapter.respond_calls) == 1 and adapter.respond_calls[0].status == 200
        )
        assert adapter.emit_calls == []

        cached_rt = _make_internal_runtime(adapter, monkeypatch)
        assert cached_rt.internal is True
        assert cached_rt._stream_options_injected is False
        assert "stream_options" not in json.loads(cached_rt.exchange.raw_body)

    def test_internal_stream_no_400_retry_when_not_injected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._enable_internal_stream(monkeypatch, "false")
        adapter = _FakeAdapter()
        rt = _make_internal_runtime(adapter, monkeypatch)
        assert rt.internal is True
        assert rt._stream_options_injected is False
        assert "stream_options" not in json.loads(rt.exchange.raw_body)
        err_400 = b'{"error": {"message": "Unknown parameter: stream_options"}}'
        rt.response = _FakeResponse(400, err_400)

        def fake_reopen() -> _FakeResponse:
            raise AssertionError("400 fallback must not reopen without hub injection")

        monkeypatch.setattr(rt, "_reopen_response", fake_reopen)
        rt.respond()
        assert adapter.emit_calls == []
        assert (
            len(adapter.respond_calls) == 1 and adapter.respond_calls[0].status == 400
        )
        assert (
            rt._stream_opt_cache.is_rejected(rt._stream_opt_key, time.monotonic())
            is False
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
