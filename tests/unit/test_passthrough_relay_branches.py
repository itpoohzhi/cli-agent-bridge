"""L1: ветви SSE-relay passthrough: служебные кадры, [DONE], ошибки и сбой чтения."""

from __future__ import annotations

import io
import json
import socket
from typing import Any
from unittest.mock import Mock

from adapters.passthrough_adapter import (
    PassthroughAdapter,
    PassthroughLimits,
    StreamOutcome,
    _SseRelay,
    relay_sse,
)
from tests.unit._passthrough_tool_branches import (
    EMULATE_SPEC,
    adapter as adapter,
    delta_chunk,
    isolated_env as isolated_env,
    limits as limits,
    sink as sink,
    sse_events,
)
from tests.unit._passthrough_tool_sink import _CollectSink

DONE = b"data: [DONE]\n\n"


def _frames(body: bytes) -> list[dict[str, Any]]:
    return [
        json.loads(line[5:])
        for line in body.splitlines()
        if line.startswith(b"data:") and line[5:].strip() != b"[DONE]"
    ]


def _run(limits: PassthroughLimits, wire: bytes) -> tuple[StreamOutcome, bytes]:
    written: list[bytes] = []
    outcome = relay_sse(
        io.BytesIO(wire).readline,
        written.append,
        tool_schemas=None,
        limits=limits,
        mode_spec=EMULATE_SPEC,
    )
    return outcome, b"".join(written)


def _relay(limits: PassthroughLimits, written: list[bytes]) -> _SseRelay:
    return _SseRelay(written.append, None, limits, {"mode_spec": EMULATE_SPEC})


def test_other_chunk_without_error_only_records_metadata(
    limits: PassthroughLimits,
) -> None:
    written: list[bytes] = []
    relay = _relay(limits, written)
    relay.seen.add(0)
    assert relay._other_chunk({"id": "i1", "model": "m", "created": 3}) is False
    assert relay.last_chunk == {"id": "i1", "created": 3, "model": "m"}
    assert written == [] and relay.outcome.incomplete is False


def test_other_chunk_error_with_nothing_pending_is_ignored(
    limits: PassthroughLimits,
) -> None:
    written: list[bytes] = []
    relay = _relay(limits, written)
    relay.seen.add(0)
    relay.finished.add(0)
    assert relay._other_chunk({"error": {"code": "rate", "message": "slow"}}) is False
    assert written == [] and relay.outcome.incomplete is False


def test_other_chunk_error_with_pending_choice_emits_terminal_error(
    limits: PassthroughLimits,
) -> None:
    written: list[bytes] = []
    relay = _relay(limits, written)
    relay.seen.add(0)
    chunk = {
        "id": "i1",
        "model": "m",
        "created": 3,
        "error": {"code": "rate", "message": "slow"},
    }
    assert relay._other_chunk(chunk) is True
    assert relay.outcome.incomplete is True
    (frame,) = _frames(b"".join(written))
    assert frame["id"] == "i1" and frame["model"] == "m"
    assert frame["error"]["code"] == "rate" and frame["error"]["message"] == "slow"
    assert b"".join(written).endswith(DONE)


def test_other_chunk_non_dict_error_uses_default_code_and_stringified_message(
    limits: PassthroughLimits,
) -> None:
    written: list[bytes] = []
    relay = _relay(limits, written)
    relay.seen.add(2)
    assert relay._other_chunk({"error": "boom"}) is True
    (frame,) = _frames(b"".join(written))
    assert frame["error"]["code"] == "upstream_stream_error"
    assert frame["error"]["message"] == "boom"


def test_comment_event_has_no_data_and_is_forwarded_verbatim(
    limits: PassthroughLimits,
) -> None:
    stop = delta_chunk(0, {}, "stop")
    outcome, body = _run(limits, b": ping\n\n" + sse_events(stop))
    assert body.startswith(b": ping\n\n")
    assert [item["choices"][0]["finish_reason"] for item in _frames(body)] == ["stop"]
    assert outcome.done is True and body.endswith(DONE)


def test_done_event_ends_stream_and_is_forwarded_once(
    limits: PassthroughLimits,
) -> None:
    wire = sse_events(delta_chunk(0, {"content": "hi"}), delta_chunk(0, {}, "stop"))
    outcome, body = _run(limits, wire + b"data: ignored-after-done\n\n")
    assert outcome.done is True and outcome.incomplete is False
    assert body.count(DONE) == 1 and b"ignored-after-done" not in body
    assert outcome.unfinished_choices == set()


def test_done_with_surrounding_whitespace_still_ends_stream(
    limits: PassthroughLimits,
) -> None:
    wire = sse_events(delta_chunk(0, {}, "stop"), done=False) + b"data:   [DONE]  \n\n"
    outcome, body = _run(limits, wire)
    assert outcome.done is True and b"[DONE]" in body


def test_dict_events_without_done_end_at_eof_without_done_flag(
    limits: PassthroughLimits,
) -> None:
    outcome, body = _run(limits, sse_events(delta_chunk(0, {}, "stop"), done=False))
    assert outcome.done is False and outcome.incomplete is False
    assert DONE not in body


def test_eof_with_unfinished_choice_emits_incomplete_error(
    limits: PassthroughLimits,
) -> None:
    outcome, body = _run(
        limits, sse_events(delta_chunk(0, {"content": "hi"}), done=False)
    )
    assert outcome.incomplete is True and outcome.done is False
    assert outcome.unfinished_choices == {0}
    assert _frames(body)[-1]["error"]["code"] == "upstream_incomplete_stream"
    assert body.endswith(DONE)


def test_non_json_data_event_is_forwarded_untouched(limits: PassthroughLimits) -> None:
    wire = b"data: not json\n\n" + sse_events(delta_chunk(0, {}, "stop"))
    outcome, body = _run(limits, wire)
    assert body.startswith(b"data: not json\n\n")
    assert outcome.done is True


def test_stream_io_error_with_every_choice_finished_writes_only_done(
    adapter: PassthroughAdapter, sink: _CollectSink
) -> None:
    outcome = StreamOutcome(unfinished_choices=set())
    handled = adapter._stream_io_error(sink, outcome, {"error": OSError("x")})
    assert handled is False
    assert sink.body == b"data: [DONE]\n\n"


def test_stream_io_error_reports_each_unfinished_choice_in_order(
    adapter: PassthroughAdapter, sink: _CollectSink
) -> None:
    last = {"id": "cid", "model": "mm", "created": 5}
    outcome = StreamOutcome(unfinished_choices={3, 1}, last_chunk=last)
    assert adapter._stream_io_error(sink, outcome, {"error": OSError("x")}) is False
    (frame,) = _frames(sink.body)
    assert [choice["index"] for choice in frame["choices"]] == [1, 3]
    assert (frame["id"], frame["model"], frame["created"]) == ("cid", "mm", 5)
    assert frame["error"]["code"] == "upstream_stream_error"
    assert sink.body.endswith(DONE)


def test_stream_io_error_without_choice_tracking_reports_choice_zero(
    adapter: PassthroughAdapter, sink: _CollectSink
) -> None:
    outcome = StreamOutcome(unfinished_choices=None)
    assert adapter._stream_io_error(sink, outcome, {"error": OSError("x")}) is False
    (frame,) = _frames(sink.body)
    assert [choice["index"] for choice in frame["choices"]] == [0]
    assert frame["model"] == "p"
    assert frame["error"]["message"] == "upstream stream failed"


def test_stream_io_error_timeout_invokes_abort_callback_once(
    adapter: PassthroughAdapter, sink: _CollectSink
) -> None:
    abort = Mock()
    options = {"error": socket.timeout("t"), "on_timeout": abort}
    adapter._stream_io_error(sink, StreamOutcome(unfinished_choices=set()), options)
    abort.assert_called_once_with()


def test_stream_io_error_timeout_without_callback_still_writes_done(
    adapter: PassthroughAdapter, sink: _CollectSink
) -> None:
    options = {"error": TimeoutError("t")}
    adapter._stream_io_error(sink, StreamOutcome(unfinished_choices=set()), options)
    assert sink.body == b"data: [DONE]\n\n"


def test_stream_io_error_non_timeout_does_not_abort(
    adapter: PassthroughAdapter, sink: _CollectSink
) -> None:
    abort = Mock()
    adapter._stream_io_error(
        sink,
        StreamOutcome(unfinished_choices=set()),
        {"error": OSError("x"), "on_timeout": abort},
    )
    abort.assert_not_called()
