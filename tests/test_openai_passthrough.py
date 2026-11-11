"""Верификация passthrough (VER-001, VER-003..VER-007): реэкспорт кейсов из test_passthrough_adapter
и контракт non-stream через внутренний SSE (ADR-0015 AD-001/AD-002)."""

# pytest-фикстура `ns_env` импортируется и подставляется аргументом тестов (F811 ожидаем).
# ruff: noqa: F811

from __future__ import annotations

import io
import json
import random
import threading
import time

import pytest

from tests.test_passthrough_adapter import *  # noqa: F401, F403
from tests.test_passthrough_adapter import (  # noqa: F401
    DONE,
    SCHEMAS,
    TOOLS,
    CollectSink,
    FakeUpstream,
    SeamCase,
    args_of,
    chunk,
    content,
    finish,
    frame,
    make_adapter,
    ns_env,
    tool_delta,
)
from adapters.passthrough_adapter import PassthroughLimits, iter_sse_events
from core.cli_runtime_config import NonstreamConfig
from core.liveness_signals import classify_sse_data
from core.nonstream_aggregator import (
    NonstreamAggregator,
    NonstreamError,
    aggregate_events,
)

BIG = 1 << 20


# ---- помощники агрегатора ------------------------------------------------------------
def events_of(raw: bytes) -> list:
    return list(iter_sse_events(io.BytesIO(raw).readline, BIG))


def test_late_bridge_liveness_marker_is_stripped_before_yield() -> None:
    payload = json.dumps(
        {
            "bridge_liveness": {
                "v": 1,
                "kind": "progress",
                "seq": 1,
                "source": "reasoning",
            }
        },
        separators=(",", ":"),
    ).encode()
    padded = payload + b" " * (4000 - len(payload))
    raw = b"data: " + padded + b"\nevent: bridge_liveness\n\n"
    assert events_of(raw) == []


def kind_of(data):
    return classify_sse_data(data)[0]


def agg(raw: bytes, max_body: int = BIG) -> dict:
    return json.loads(aggregate_events(events_of(raw), None, max_body))


def agg_error(raw: bytes, max_body: int = BIG) -> NonstreamError:
    with pytest.raises(NonstreamError) as info:
        aggregate_events(events_of(raw), None, max_body)
    return info.value


def delta_frame(delta: dict, index: int = 0, reason=None, **extra) -> bytes:
    return frame(
        chunk([{"index": index, "delta": delta, "finish_reason": reason}], **extra)
    )


def role_frame(index: int = 0, role: str = "assistant", **extra) -> bytes:
    return delta_frame({"role": role}, index, **extra)


def message_of(body: dict, index: int = 0) -> dict:
    return body["choices"][index]["message"]


# ---- 1. агрегатор: юнит-контракт --------------------------------------------------------
def test_aggregate_single_response_fields_and_usage() -> None:
    raw = (
        role_frame()
        + content("Hel")
        + content("lo")
        + delta_frame({"reasoning_content": "think"})
        + finish(0, "stop")
        + frame(
            chunk(
                [],
                usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            )
        )
        + DONE
    )
    assert agg(raw) == {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 1,
        "model": "m",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hello",
                    "reasoning_content": "think",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
    }


def test_aggregate_usage_comes_from_last_chunk_that_has_it() -> None:
    raw = (
        content("a")
        + delta_frame({}, 0, "stop", usage={"total_tokens": 1})
        + frame(chunk([], usage={"total_tokens": 9}))
        + frame(chunk([]))  # без usage: прежнее значение не затирается
        + DONE
    )
    assert agg(raw)["usage"] == {"total_tokens": 9}


def test_aggregate_usage_absent_is_allowed() -> None:
    body = agg(content("a") + finish(0, "stop") + DONE)
    assert "usage" not in body
    assert message_of(body)["content"] == "a"


def test_aggregate_preserves_step_separators_verbatim() -> None:
    raw = (
        content("Шаг 1.")
        + content("\n\n")
        + content("Шаг 2.\n\n")
        + content("Итог")
        + finish(0, "stop")
        + DONE
    )
    assert message_of(agg(raw))["content"] == "Шаг 1.\n\nШаг 2.\n\nИтог"
    plain = content("a") + content("b") + finish(0, "stop") + DONE
    assert message_of(agg(plain))["content"] == "ab"  # ничего не вставляется


def test_aggregate_n_greater_than_one_orders_by_choice_index() -> None:
    raw = (
        content("B1", index=1)
        + content("A1", index=0)
        + content("B2", index=1)
        + content("A2", index=0)
        + finish(1, "length")
        + finish(0, "stop")
        + DONE
    )
    body = agg(raw)
    assert [c["index"] for c in body["choices"]] == [0, 1]
    assert [message_of(body, i)["content"] for i in (0, 1)] == ["A1A2", "B1B2"]
    assert [c["finish_reason"] for c in body["choices"]] == ["stop", "length"]


def test_aggregate_tool_calls_by_choice_and_call_index_concatenate_arguments() -> None:
    raw = (
        tool_delta(0, 0, call_id="c0", name="subagent", args='{"prompt":')
        + tool_delta(1, 0, call_id="d0", name="other", args='{"k":')
        + tool_delta(0, 1, call_id="c1", name="second", args="{}")
        + tool_delta(0, 0, args='"p"}')
        + tool_delta(1, 0, args="1}")
        + finish(0)
        + finish(1)
        + DONE
    )
    body = agg(raw)
    first, second = message_of(body, 0), message_of(body, 1)
    assert first["content"] is None
    assert [
        (c["id"], c["type"], c["function"]["name"]) for c in first["tool_calls"]
    ] == [
        ("c0", "function", "subagent"),
        ("c1", "function", "second"),
    ]
    assert json.loads(first["tool_calls"][0]["function"]["arguments"]) == {
        "prompt": "p"
    }
    assert first["tool_calls"][1]["function"]["arguments"] == "{}"
    assert [(c["id"], c["function"]["name"]) for c in second["tool_calls"]] == [
        ("d0", "other")
    ]
    assert json.loads(second["tool_calls"][0]["function"]["arguments"]) == {"k": 1}
    assert body["choices"][0]["finish_reason"] == "tool_calls"


def test_aggregate_tool_call_first_nonempty_id_and_name_win_when_repeated_equal() -> (
    None
):
    raw = (
        tool_delta(0, 0, call_id="c0", name="subagent", args="{")
        + tool_delta(
            0, 0, call_id="c0", name="subagent", args="}"
        )  # повтор того же значения совместим
        + finish(0)
        + DONE
    )
    call = message_of(agg(raw))["tool_calls"][0]
    assert (call["id"], call["function"]["name"], call["function"]["arguments"]) == (
        "c0",
        "subagent",
        "{}",
    )


@pytest.mark.parametrize(
    "second",
    [
        tool_delta(0, 0, call_id="OTHER", args="x"),
        tool_delta(0, 0, name="other_name", args="x"),
    ],
    ids=["tool_call_id", "tool_call_name"],
)
def test_aggregate_tool_call_conflict_is_502(second: bytes) -> None:
    raw = (
        tool_delta(0, 0, call_id="c0", name="subagent", args="{")
        + second
        + finish(0)
        + DONE
    )
    error = agg_error(raw)
    assert error.status == 502
    assert error.code == "upstream_metadata_conflict"


def test_aggregate_role_conflict_is_502() -> None:
    error = agg_error(
        role_frame(role="assistant")
        + role_frame(role="tool")
        + finish(0, "stop")
        + DONE
    )
    assert (error.status, error.code) == (502, "upstream_metadata_conflict")


def test_aggregate_role_is_kept_per_choice_index() -> None:
    raw = (
        role_frame(0, "assistant")
        + role_frame(1, "assistant")
        + content("a", 0)
        + finish(0, "stop")
        + finish(1, "stop")
        + DONE
    )
    assert [message_of(agg(raw), i)["role"] for i in (0, 1)] == [
        "assistant",
        "assistant",
    ]


@pytest.mark.parametrize(
    "field,value", [("id", "chatcmpl-OTHER"), ("model", "other-model")]
)
def test_aggregate_chunk_metadata_conflict_is_502(field: str, value: str) -> None:
    second = frame(
        {
            **chunk([{"index": 0, "delta": {"content": "b"}, "finish_reason": None}]),
            field: value,
        }
    )
    error = agg_error(content("a") + second + finish(0, "stop") + DONE)
    assert (error.status, error.code) == (502, "upstream_metadata_conflict")


def test_aggregate_unknown_delta_fields_are_dropped() -> None:
    raw = (
        delta_frame({"role": "assistant", "x_vendor_extra": {"a": 1}})
        + delta_frame({"content": "ok", "x_vendor_note": "zzz"})
        + finish(0, "stop")
        + DONE
    )
    body = agg(raw)
    assert message_of(body) == {"role": "assistant", "content": "ok"}
    assert "x_vendor" not in json.dumps(body)


def test_aggregate_requires_done_marker_and_gives_no_partial() -> None:
    error = agg_error(content("partial") + finish(0, "stop"))  # EOF до [DONE]
    assert (error.status, error.code) == (502, "upstream_incomplete_stream")
    assert "partial" not in error.message


def test_aggregate_done_without_useful_chunk_is_502() -> None:
    for raw in (DONE, role_frame() + finish(0, "stop") + DONE, b": ping\n\n" + DONE):
        error = agg_error(raw)
        assert (error.status, error.code) == (502, "upstream_empty_stream")


def test_aggregate_missing_finish_reason_on_any_choice_is_502() -> None:
    raw = content("a", 0) + content("b", 1) + finish(0, "stop") + DONE
    error = agg_error(raw)
    assert (error.status, error.code) == (502, "upstream_incomplete_stream")


def test_aggregate_malformed_json_is_502() -> None:
    error = agg_error(content("a") + b"data: {not json\n\n" + finish(0, "stop") + DONE)
    assert (error.status, error.code) == (502, "upstream_malformed_chunk")
    assert (
        agg_error(
            content("a") + b'data: "string"\n\n' + finish(0, "stop") + DONE
        ).status
        == 502
    )


def test_aggregate_error_chunk_is_502() -> None:
    raw = (
        content("a")
        + frame({"error": {"message": "boom", "type": "server_error"}})
        + DONE
    )
    error = agg_error(raw)
    assert (error.status, error.code) == (502, "upstream_stream_error")
    assert "boom" not in error.message


def test_aggregate_accepts_pings_keepalives_and_sse_comments() -> None:
    raw = (
        b": comment\n\n"
        + b"data: ping\n\n"
        + content("a")
        + b"data: keepalive\n\n"
        + b"event: noop\n\n"
        + b": another\n\n"
        + b"data: \n\n"
        + finish(0, "stop")
        + DONE
    )
    assert message_of(agg(raw))["content"] == "a"


def test_aggregate_done_literal_does_not_leak_into_response() -> None:
    raw = content("a") + finish(0, "stop") + DONE
    assert b"[DONE]" not in aggregate_events(events_of(raw), None, BIG)


def test_aggregate_stops_reading_after_done() -> None:
    consumed: list = []

    def source():
        for event in events_of(content("a") + finish(0, "stop") + DONE):
            consumed.append(event)
            yield event
        raise AssertionError("aggregator must not read past [DONE]")

    aggregate_events(source(), None, BIG)
    assert consumed[-1][1] == "[DONE]"


def test_aggregate_raw_byte_limit_is_independent_of_result_size() -> None:
    raw = content("a") + content("b") + finish(0, "stop") + DONE
    ok_len = len(aggregate_events(events_of(raw), None, BIG))
    assert (
        len(raw) > ok_len
    )  # сырой SSE больше итогового JSON: срабатывает только raw-лимит
    limit = len(raw) - 1
    assert limit >= ok_len
    error = agg_error(raw, max_body=limit)
    assert (error.status, error.code) == (502, "upstream_response_too_large")
    assert agg(raw, max_body=len(raw))["choices"][0]["message"]["content"] == "ab"


def test_aggregate_result_json_limit_is_independent_of_raw_size() -> None:
    raw = (
        b'data: {"choices":[{"delta":{"content":"xxx"},"finish_reason":"stop"}]}\n\n'
        + DONE
    )
    ok_len = len(aggregate_events(events_of(raw), None, BIG))
    assert (
        len(raw) < ok_len
    )  # итоговый JSON больше сырых байт: срабатывает только лимит результата
    error = agg_error(raw, max_body=ok_len - 1)
    assert (error.status, error.code) == (502, "upstream_response_too_large")
    assert len(aggregate_events(events_of(raw), None, ok_len)) == ok_len


def test_aggregate_iterator_timeout_is_504() -> None:
    def source():
        yield from events_of(content("a"))
        raise TimeoutError("deadline")

    with pytest.raises(NonstreamError) as info:
        aggregate_events(source(), None, BIG)
    assert info.value.status == 504
    assert info.value.code == "upstream_timeout"


def test_aggregate_socket_error_is_502_not_504() -> None:
    def source():
        yield from events_of(content("a"))
        raise ConnectionResetError("reset")

    with pytest.raises(NonstreamError) as info:
        aggregate_events(source(), None, BIG)
    assert info.value.status == 502


def test_aggregator_class_is_incremental_and_finalize_checks_contract() -> None:
    aggregator = NonstreamAggregator(BIG)
    for raw, data in events_of(content("a") + finish(0, "stop")):
        aggregator.add_event(raw, data)
    assert not aggregator.done
    with pytest.raises(NonstreamError) as info:
        aggregator.finalize()
    assert info.value.status == 502


# ---- 2. инвариантность к границам чанков (QA-006) -------------------------------------------
class ChunkedLineReader:
    """`readline` над потоком, приходящим кусками заданного размера (сеть режет произвольно)."""

    def __init__(self, raw: bytes, sizer) -> None:
        self.raw, self.pos, self.sizer, self.buf = raw, 0, sizer, bytearray()

    def readline(self, limit: int = -1) -> bytes:
        while b"\n" not in self.buf and self.pos < len(self.raw):
            size = max(1, self.sizer())
            self.buf += self.raw[self.pos : self.pos + size]
            self.pos += size
        end = self.buf.find(b"\n") + 1 or len(self.buf)
        line = bytes(self.buf[:end])
        del self.buf[:end]
        return line


def rich_stream() -> bytes:
    return (
        b": open\n\n"
        + role_frame(0)
        + role_frame(1)
        + content("Привет, ", 0)
        + b"data: ping\n\n"
        + content("мир 🌍.", 0)
        + content("\n\n", 0)
        + content("Второй шаг.", 0)
        + delta_frame({"reasoning_content": "размышляю"}, 1)
        + tool_delta(1, 0, call_id="call_1", name="subagent", args='{"prompt":')
        + b"data: keepalive\n\n"
        + tool_delta(1, 0, args='"п"}')
        + b'data: {"choices":[{"index":0,"delta":{"x_vendor":1}}]}\n\n'
        + finish(0, "stop")
        + finish(1, "tool_calls")
        + frame(chunk([], usage={"total_tokens": 7}))
        + DONE
    )


def sizers():
    rnd = random.Random(1234)
    return {
        "whole": lambda: 1 << 20,
        "1-byte": lambda: 1,
        "7-byte": lambda: 7,
        "seeded-random": lambda: rnd.randint(1, 23),
    }


@pytest.mark.parametrize("variant", ["lf", "crlf"])
def test_aggregation_is_byte_identical_for_any_chunk_boundaries(variant: str) -> None:
    raw = rich_stream()
    if variant == "crlf":
        raw = raw.replace(b"\n", b"\r\n")
    baseline_events = events_of(raw)
    baseline_body = aggregate_events(baseline_events, None, BIG)
    baseline_kinds = [classify_sse_data(data) for _, data in baseline_events]
    assert baseline_body.startswith(b"{") and b"x_vendor" not in baseline_body
    for name, sizer in sizers().items():
        reader = ChunkedLineReader(raw, sizer)
        events = list(iter_sse_events(reader.readline, BIG))
        assert events == baseline_events, name
        assert aggregate_events(iter(events), None, BIG) == baseline_body, name
        assert [classify_sse_data(data) for _, data in events] == baseline_kinds, name


def test_crlf_and_lf_streams_aggregate_identically() -> None:
    lf = rich_stream()
    assert aggregate_events(events_of(lf), None, BIG) == aggregate_events(
        events_of(lf.replace(b"\n", b"\r\n")), None, BIG
    )


def test_chunk_boundary_classification_sequence_matches_expected_kinds() -> None:
    kinds = [classify_sse_data(data)[0] for _, data in events_of(rich_stream())]
    assert kinds[0] == "T"  # SSE-комментарий
    assert kinds[-1] == "T"  # [DONE]
    assert "S" in kinds and kinds.count("S") >= 6


# ---- 3. сквозные тесты PassthroughAdapter.handle ------------------------------------------
def ns_limits(
    first: float = 5.0,
    idle: float = 5.0,
    cap: float = 30.0,
    heartbeat: float = 30.0,
    **kw,
) -> PassthroughLimits:
    return PassthroughLimits(
        nonstream=NonstreamConfig(
            first_progress_timeout_s=first,
            idle_timeout_s=idle,
            safety_cap_s=cap,
            poll_interval_s=0.01,
        ),
        poll_interval_s=0.01,
        heartbeat_interval_s=heartbeat,
        reader_join_timeout_s=0.05,
        **kw,
    )


@pytest.fixture
def upstream():
    server_ = FakeUpstream()
    yield server_
    server_.close()


def invoke(
    upstream,
    request: dict,
    *,
    limits=None,
    raw=None,
    path="/v1/chat/completions",
    **adapter_kw,
):
    adapter = make_adapter(
        upstream.port, limits or ns_limits(), **{"sanitize": True, **adapter_kw}
    )
    body = raw if raw is not None else json.dumps(request).encode("utf-8")
    sink = CollectSink()
    started = time.monotonic()
    try:
        adapter.handle(
            path=path,
            raw_body=body,
            request=request,
            headers={"Authorization": "Bearer upstream-key"},
            sink=sink,
        )
    finally:
        adapter.shutdown()
    return sink, time.monotonic() - started


def error_code(sink: CollectSink) -> str:
    return json.loads(sink.body)["error"]["type"]


def sse_script(upstream, events: bytes):
    upstream.respond = lambda handler, body: FakeUpstream.sse(handler, events)


def timed_sse(upstream, schedule, stop: threading.Event):
    """Заголовки SSE сразу, затем кадры по расписанию [(пауза_c, байты)]; безопасно при обрыве клиента."""

    def respond(handler, body):
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.end_headers()
        handler.wfile.flush()
        try:
            for delay, data in schedule():
                if stop.wait(delay):
                    return
                handler.wfile.write(data)
                handler.wfile.flush()
        except OSError:
            return

    upstream.respond = respond


REQUEST = {
    "model": "m",
    "stream": False,
    "messages": [{"role": "user", "content": "hi"}],
}


@pytest.mark.parametrize("stream_field", [False, None])
def test_via_stream_rewrites_only_stream_flag_and_returns_single_json(
    ns_env, upstream, stream_field
) -> None:
    ns_env.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
    request = {
        "model": "m",
        "temperature": 0.2,
        "stream_options": {"include_usage": True},
        "messages": [{"role": "user", "content": "привет"}],
    }
    if stream_field is not None:
        request["stream"] = stream_field
    sse_script(
        upstream,
        role_frame()
        + content("Hello")
        + content("\n\n")
        + content("world")
        + finish(0, "stop")
        + frame(chunk([], usage={"total_tokens": 5}))
        + DONE,
    )
    sink, _ = invoke(
        upstream, request, raw=json.dumps(request, indent=2).encode("utf-8")
    )
    sent = json.loads(upstream.requests[0]["body"])
    assert sent["stream"] is True
    assert {k: v for k, v in sent.items() if k != "stream"} == {
        k: v for k, v in request.items() if k != "stream"
    }
    assert sent["stream_options"] == {
        "include_usage": True
    }  # include_usage не добавляется и не убирается
    assert sink.status == 200
    assert sink.header("Content-Type").lower().startswith("application/json")
    assert sink.header("Content-Length") == str(len(sink.body))
    assert len(sink.chunks) == 1
    body = json.loads(sink.body)
    assert body["object"] == "chat.completion"
    assert message_of(body)["content"] == "Hello\n\nworld"
    assert body["usage"] == {"total_tokens": 5}
    assert b"[DONE]" not in sink.body and b"data:" not in sink.body


def test_via_stream_does_not_add_stream_options_or_usage(ns_env, upstream) -> None:
    ns_env.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
    sse_script(upstream, content("x") + finish(0, "stop") + DONE)
    sink, _ = invoke(upstream, dict(REQUEST))
    assert "stream_options" not in json.loads(upstream.requests[0]["body"])
    assert sink.status == 200 and "usage" not in json.loads(sink.body)


@pytest.mark.parametrize("flag", [None, "false", "0", "off", ""])
def test_flag_off_keeps_request_bytes_and_static_nonstream_path(
    ns_env, upstream, flag
) -> None:
    if flag is not None:
        ns_env.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", flag)
    completion = {
        "id": "x",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "plain"},
            }
        ],
    }
    upstream.respond = lambda handler, body: FakeUpstream.json(handler, completion)
    raw = json.dumps(REQUEST, indent=3).encode("utf-8")
    sink, _ = invoke(upstream, dict(REQUEST), raw=raw)
    assert upstream.requests[0]["body"] == raw
    assert json.loads(raw)["stream"] is False
    assert sink.status == 200
    assert json.loads(sink.body) == completion
    assert sink.header("Content-Type") == "application/json"


def test_external_stream_true_is_not_rewritten_and_relayed_as_sse(
    ns_env, upstream
) -> None:
    ns_env.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
    events = content("a") + finish(0, "stop") + DONE
    sse_script(upstream, events)
    request = {**REQUEST, "stream": True}
    raw = json.dumps(request, indent=2).encode("utf-8")
    sink, _ = invoke(upstream, request, raw=raw)
    assert upstream.requests[0]["body"] == raw
    assert sink.status == 200
    assert sink.header("Content-Type") == "text/event-stream"
    assert sink.body == events


@pytest.mark.parametrize(
    "path",
    [
        "/v1/completions",
        "/v1/embeddings",
        "/v1/responses",
        "/v1/chat/completions/extra",
    ],
)
def test_via_stream_applies_only_to_chat_completions_route(
    ns_env, upstream, path
) -> None:
    ns_env.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
    upstream.respond = lambda handler, body: FakeUpstream.json(handler, {"ok": True})
    raw = json.dumps(REQUEST, indent=2).encode("utf-8")
    sink, _ = invoke(upstream, dict(REQUEST), raw=raw, path=path)
    assert upstream.requests[0]["body"] == raw
    assert (sink.status, json.loads(sink.body)) == (200, {"ok": True})


def test_via_stream_applies_to_chat_completions_with_query_string(
    ns_env, upstream
) -> None:
    ns_env.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
    sse_script(upstream, content("q") + finish(0, "stop") + DONE)
    sink, _ = invoke(upstream, dict(REQUEST), path="/v1/chat/completions?api-version=1")
    assert json.loads(upstream.requests[0]["body"])["stream"] is True
    assert message_of(json.loads(sink.body))["content"] == "q"


@pytest.mark.parametrize("status", [429, 500])
def test_via_stream_upstream_json_errors_are_forwarded_as_before(
    ns_env, upstream, status
) -> None:
    ns_env.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
    payload = {
        "error": {"message": "limit", "type": "rate_limit_error", "code": "rate"}
    }
    upstream.respond = lambda handler, body: FakeUpstream.json(
        handler, payload, status=status
    )
    sink, _ = invoke(upstream, dict(REQUEST))
    assert sink.status == status
    assert json.loads(sink.body) == payload


def test_via_stream_eof_before_done_is_502_without_partial(ns_env, upstream) -> None:
    ns_env.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
    sse_script(upstream, content("secret-partial") + finish(0, "stop"))
    sink, _ = invoke(upstream, dict(REQUEST))
    assert sink.status == 502
    assert error_code(sink) == "upstream_incomplete_stream"
    assert b"secret-partial" not in sink.body and b"choices" not in sink.body


def test_via_stream_stream_error_chunk_is_502(ns_env, upstream) -> None:
    ns_env.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
    sse_script(upstream, content("a") + frame({"error": {"message": "boom"}}) + DONE)
    sink, _ = invoke(upstream, dict(REQUEST))
    assert sink.status == 502 and error_code(sink) == "upstream_stream_error"


def test_via_stream_raw_size_limit_is_502(ns_env, upstream) -> None:
    ns_env.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
    sse_script(
        upstream,
        b"".join(content("x" * 40) for _ in range(20)) + finish(0, "stop") + DONE,
    )
    sink, _ = invoke(upstream, dict(REQUEST), limits=ns_limits(max_body_bytes=2048))
    assert sink.status == 502 and error_code(sink) == "upstream_response_too_large"


def test_via_stream_heartbeat_only_hits_first_progress_timeout_504(
    ns_env, upstream
) -> None:
    ns_env.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
    stop = threading.Event()
    pulses = [
        b": keepalive\n\n",
        b"data: keepalive\n\n",
        b"data: ping\n\n",
        role_frame(),
    ]
    timed_sse(upstream, lambda: ((0.05, pulses[i % 4]) for i in range(80)), stop)
    try:
        sink, elapsed = invoke(
            upstream, dict(REQUEST), limits=ns_limits(first=0.3, idle=5.0, cap=30.0)
        )
    finally:
        stop.set()
    assert sink.status == 504 and error_code(sink) == "upstream_timeout"
    assert (
        elapsed < 2.5
    )  # T не сдвигает first-progress дедлайн (иначе ждали бы 4 c потока)


def test_via_stream_slides_idle_window_over_total_longer_than_idle(
    ns_env, upstream
) -> None:
    ns_env.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
    stop = threading.Event()

    def schedule():
        yield 0.0, content("a")
        for _ in range(4):
            yield 0.2, content("b")
        yield 0.0, finish(0, "stop")
        yield 0.0, DONE

    timed_sse(upstream, schedule, stop)
    try:
        sink, elapsed = invoke(
            upstream, dict(REQUEST), limits=ns_limits(first=2.0, idle=0.5, cap=30.0)
        )
    finally:
        stop.set()
    assert elapsed > 0.5  # суммарная длительность больше idle
    assert sink.status == 200
    assert message_of(json.loads(sink.body))["content"] == "abbbb"


def test_via_stream_heartbeat_pauses_between_progress_do_not_extend_idle(
    ns_env, upstream
) -> None:
    ns_env.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
    stop = threading.Event()

    def schedule():
        yield 0.0, content("a")
        for i in range(60):
            yield 0.05, b": keepalive\n\n" if i % 2 else b"data: ping\n\n"

    timed_sse(upstream, schedule, stop)
    try:
        sink, elapsed = invoke(
            upstream, dict(REQUEST), limits=ns_limits(first=2.0, idle=0.4, cap=30.0)
        )
    finally:
        stop.set()
    assert sink.status == 504 and error_code(sink) == "upstream_timeout"
    assert elapsed < 2.0


def test_via_stream_pause_longer_than_idle_is_504_without_partial(
    ns_env, upstream
) -> None:
    ns_env.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
    stop = threading.Event()

    def schedule():
        yield 0.0, content("partial-text")
        yield 1.5, finish(0, "stop")
        yield 0.0, DONE

    timed_sse(upstream, schedule, stop)
    try:
        sink, elapsed = invoke(
            upstream, dict(REQUEST), limits=ns_limits(first=2.0, idle=0.3, cap=30.0)
        )
    finally:
        stop.set()
    assert sink.status == 504 and error_code(sink) == "upstream_timeout"
    assert b"partial-text" not in sink.body
    assert elapsed < 1.4


def run_safety_cap(ns_env, upstream, cap: float = 0.6):
    ns_env.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
    stop = threading.Event()
    timed_sse(upstream, lambda: ((0.05, content("x")) for _ in range(80)), stop)
    try:
        return invoke(
            upstream, dict(REQUEST), limits=ns_limits(first=5.0, idle=5.0, cap=cap)
        )
    finally:
        stop.set()


def test_via_stream_safety_cap_is_absolute_even_with_continuous_progress(
    ns_env, upstream
) -> None:
    sink, elapsed = run_safety_cap(ns_env, upstream)
    # Потолок абсолютен: поток с непрерывным S не даёт 200 и не отдаёт частичный ответ.
    assert sink.status in (502, 504)
    assert b'"choices"' not in sink.body
    assert 0.5 < elapsed < 3.0


def test_via_stream_safety_cap_is_504(ns_env, upstream) -> None:
    sink, _ = run_safety_cap(ns_env, upstream)
    assert sink.status == 504 and error_code(sink) == "upstream_timeout"


def test_via_stream_sanitizes_tool_calls_in_aggregated_body(ns_env, upstream) -> None:
    ns_env.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
    events = (
        tool_delta(0, 0, call_id="call_a", name="subagent", args='{"prompt":"p",')
        + tool_delta(0, 0, args='"provider":"","note":" "}')
        + finish(0)
        + DONE
    )
    sse_script(upstream, events)
    request = {**REQUEST, "tools": TOOLS}
    sink, _ = invoke(upstream, request)
    message = message_of(json.loads(sink.body))
    assert sink.status == 200
    assert args_of(message["tool_calls"][0]) == {"prompt": "p"}
    assert json.loads(sink.body)["choices"][0]["finish_reason"] == "tool_calls"
    # Контроль: без санитайзера пустые необязательные поля остаются.
    sse_script(upstream, events)
    raw_sink, _ = invoke(upstream, request, sanitize=False)
    raw_args = args_of(message_of(json.loads(raw_sink.body))["tool_calls"][0])
    assert raw_args == {"prompt": "p", "provider": "", "note": " "}


def test_via_stream_dynamic_flag_is_read_per_request(ns_env, upstream) -> None:
    sse_script(upstream, content("s") + finish(0, "stop") + DONE)
    upstream_json = {
        "id": "x",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "static"},
            }
        ],
    }
    adapter = make_adapter(upstream.port, ns_limits(), sanitize=True)
    try:
        ns_env.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
        first = CollectSink()
        adapter.handle(
            path="/v1/chat/completions",
            raw_body=json.dumps(REQUEST).encode(),
            request=dict(REQUEST),
            headers={},
            sink=first,
        )
        ns_env.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "false")
        upstream.respond = lambda handler, body: FakeUpstream.json(
            handler, upstream_json
        )
        second = CollectSink()
        adapter.handle(
            path="/v1/chat/completions",
            raw_body=json.dumps(REQUEST).encode(),
            request=dict(REQUEST),
            headers={},
            sink=second,
        )
    finally:
        adapter.shutdown()
    assert [json.loads(r["body"])["stream"] for r in upstream.requests] == [True, False]
    assert message_of(json.loads(first.body))["content"] == "s"
    assert json.loads(second.body) == upstream_json


def test_via_stream_leaves_no_active_requests_after_failures(ns_env, upstream) -> None:
    ns_env.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
    sse_script(upstream, content("a"))  # EOF до [DONE]
    adapter = make_adapter(upstream.port, ns_limits(), sanitize=True)
    try:
        sink = CollectSink()
        adapter.handle(
            path="/v1/chat/completions",
            raw_body=json.dumps(REQUEST).encode(),
            request=dict(REQUEST),
            headers={},
            sink=sink,
        )
        assert sink.status == 502
        assert adapter.active_count() == 0
    finally:
        adapter.shutdown()


# ---- F-017/F-023: function_call/refusal не теряются, JSON разбирается один раз -----------------
def _delta_frame(delta: dict, reason=None, index: int = 0) -> bytes:
    return frame(chunk([{"index": index, "delta": delta, "finish_reason": reason}]))


def test_aggregator_keeps_legacy_function_call_and_refusal() -> None:
    raw = (
        _delta_frame(
            {"role": "assistant", "function_call": {"name": "get", "arguments": '{"a"'}}
        )
        + _delta_frame({"function_call": {"arguments": ":1}"}})
        + _delta_frame({"refusal": "no "}, index=1)
        + _delta_frame({"refusal": "way"}, index=1)
        + finish(0, "function_call")
        + finish(1, "stop")
        + DONE
    )
    choices = {c["index"]: c["message"] for c in agg(raw)["choices"]}
    assert choices[0]["function_call"] == {"name": "get", "arguments": '{"a":1}'}
    assert choices[0]["content"] is None
    assert choices[1]["refusal"] == "no way"


def test_semantic_keys_are_single_source_of_truth() -> None:
    from core import liveness_signals as ls, nonstream_aggregator as na

    assert na.SEMANTIC_TEXT_KEYS is ls.SEMANTIC_TEXT_KEYS
    assert {"content", "reasoning_content", "reasoning", "refusal"} <= set(
        ls.SEMANTIC_TEXT_KEYS
    )
    assert ls.SEMANTIC_CALL_KEYS == ("tool_calls", "function_call")
    for key in (
        ls.SEMANTIC_TEXT_KEYS
    ):  # всё, что классификатор считает S, агрегатор обязан сохранить
        raw = _delta_frame({key: "x"}) + finish(0, "stop") + DONE
        assert agg(raw)["choices"][0]["message"].get(key) == "x"


def test_aggregator_parses_json_once_per_event(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    real = json.loads
    monkeypatch.setattr(
        json, "loads", lambda text, *a, **k: calls.append(text) or real(text, *a, **k)
    )
    signals = []
    aggregate_events(
        events_of(content("a") + finish(0, "stop") + DONE),
        lambda kind, keys: signals.append(kind),
        BIG,
    )
    assert len(calls) == 2 and signals == [
        "S",
        "T",
        "T",
    ]  # два JSON-кадра, [DONE] не разбирается
