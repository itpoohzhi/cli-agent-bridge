"""Deterministic contract for the reserved bridge-liveness SSE event."""

from __future__ import annotations

import io
import json

import pytest

from adapters.passthrough_adapter import (
    PassthroughLimits,
    UpstreamBodyTooLarge,
    iter_sse_events,
)
from core.liveness_signals import (
    REASON_CAP,
    REASON_FIRST,
    SIGNAL_S,
    LivenessWindow,
    WindowSpec,
    passthrough_window,
)
from core.nonstream_aggregator import (
    NonstreamAggregator,
    NonstreamError,
    aggregate_events,
)
from core.upstream_progress_policy import (
    DEFAULT_LIVENESS_MAX_FRAME_BYTES,
    ERROR,
    ORDINARY,
    PROGRESS,
    STRIP,
    classify_complete_sse_event,
)
from tests import test_openai_passthrough as openai


def _payload(seq: object = 1, **changes: object) -> bytes:
    evidence: dict[str, object] = {
        "v": 1,
        "kind": "progress",
        "seq": seq,
        "source": "reasoning",
    }
    evidence.update(changes)
    return json.dumps(
        {"bridge_liveness": evidence},
        separators=(",", ":"),
    ).encode()


def _frame(
    payload: bytes | None = None,
    *,
    marker_last: bool = False,
    size: int | None = None,
) -> bytes:
    data = b"data: " + (payload if payload is not None else _payload())
    fields = (
        [data, b"event: bridge_liveness"]
        if marker_last
        else [b"event: bridge_liveness", data]
    )
    base = b"\n".join(fields)
    if size is not None:
        padding = size - len(base) - 2
        assert padding >= 0
        base += b" " * padding
    return base + b"\n\n"


@pytest.mark.parametrize("marker_last", [False, True])
def test_valid_reserved_event_is_recognized_in_any_field_order(
    marker_last: bool,
) -> None:
    decision = classify_complete_sse_event(
        _frame(marker_last=marker_last),
        0,
        DEFAULT_LIVENESS_MAX_FRAME_BYTES,
    )
    assert (decision.disposition, decision.highest_seq) == (PROGRESS, 1)


def test_multiline_data_is_joined_before_strict_json_validation() -> None:
    raw = (
        b'data: {"bridge_liveness":\n'
        b'data: {"v":1,"kind":"progress","seq":7,"source":"transcript"}}\n'
        b"event: bridge_liveness\n\n"
    )
    decision = classify_complete_sse_event(raw, 3, DEFAULT_LIVENESS_MAX_FRAME_BYTES)
    assert (decision.disposition, decision.highest_seq) == (PROGRESS, 7)


@pytest.mark.parametrize(
    "raw",
    [
        b"event: bridge_liveness\nevent: bridge_liveness\ndata: "
        + _payload()
        + b"\n\n",
        b"event: noop\nevent: bridge_liveness\ndata: " + _payload() + b"\n\n",
        b"event: bridge_liveness\nevent: noop\ndata: " + _payload() + b"\n\n",
    ],
)
def test_duplicate_or_mixed_event_fields_are_malformed(raw: bytes) -> None:
    decision = classify_complete_sse_event(raw, 0, DEFAULT_LIVENESS_MAX_FRAME_BYTES)
    assert (decision.disposition, decision.highest_seq) == (ERROR, 0)


@pytest.mark.parametrize(
    "raw",
    [
        _frame(
            b'{"bridge_liveness":{"v":1,"v":1,"kind":"progress","seq":1,"source":"process"}}'
        ),
        _frame(
            b'{"bridge_liveness":{"v":1,"kind":"progress","seq":1,"source":"process","extra":0}}'
        ),
        _frame(
            b'{"bridge_liveness":{"v":1,"kind":"progress","seq":1,"source":"process"},"extra":0}'
        ),
        _frame(_payload(v=2)),
        _frame(_payload(v=True)),
        _frame(_payload(kind="status")),
        _frame(_payload(source="cpu")),
        _frame(_payload(seq=True)),
        _frame(_payload(seq=0)),
        _frame(_payload(seq=1 << 63)),
        _frame(b"not-json"),
        b"event: bridge_liveness\ndata: \xff\n\n",
        b"event: bridge_liveness\n: comment\ndata: " + _payload() + b"\n\n",
        b"event: bridge_liveness\nid: 1\ndata: " + _payload() + b"\n\n",
    ],
)
def test_strict_reserved_schema_rejects_malformed_events(raw: bytes) -> None:
    assert (
        classify_complete_sse_event(
            raw, 0, DEFAULT_LIVENESS_MAX_FRAME_BYTES
        ).disposition
        == ERROR
    )


@pytest.mark.parametrize("source", [[], {}, None, 0, 1.5, True, ["process"]])
def test_reserved_source_with_unexpected_type_is_controlled_error(
    source: object,
) -> None:
    decision = classify_complete_sse_event(
        _frame(_payload(source=source)),
        0,
        DEFAULT_LIVENESS_MAX_FRAME_BYTES,
    )
    assert (decision.disposition, decision.highest_seq) == (ERROR, 0)


@pytest.mark.parametrize(
    "raw",
    [
        b"event:bridge_liveness\ndata: anything\n\n",
        b"event: bridge_liveness \ndata: anything\n\n",
        b"event: Bridge_Liveness\ndata: anything\n\n",
        b"event: bridge_liveness-extra\ndata: anything\n\n",
    ],
)
def test_near_marker_names_remain_ordinary_byte_stream_events(raw: bytes) -> None:
    decision = classify_complete_sse_event(raw, 9, 1)
    assert (decision.disposition, decision.highest_seq) == (ORDINARY, 9)


def test_reserved_frame_bound_is_inclusive_and_reserved_only() -> None:
    exact = _frame(size=DEFAULT_LIVENESS_MAX_FRAME_BYTES)
    oversized = _frame(size=DEFAULT_LIVENESS_MAX_FRAME_BYTES + 1)
    assert len(exact) == DEFAULT_LIVENESS_MAX_FRAME_BYTES
    assert len(oversized) == DEFAULT_LIVENESS_MAX_FRAME_BYTES + 1
    assert classify_complete_sse_event(exact, 0, len(exact)).disposition == PROGRESS
    assert classify_complete_sse_event(oversized, 0, len(exact)).disposition == ERROR

    ordinary = b"event: ordinary\ndata: " + b"x" * 5000 + b"\n\n"
    assert classify_complete_sse_event(ordinary, 0, 1).disposition == ORDINARY


def test_sequence_cursor_is_strictly_monotonic_and_consumed_once() -> None:
    first = classify_complete_sse_event(_frame(_payload(seq=5)), 0, 4096)
    duplicate = classify_complete_sse_event(
        _frame(_payload(seq=5)), first.highest_seq, 4096
    )
    regressed = classify_complete_sse_event(
        _frame(_payload(seq=4)), duplicate.highest_seq, 4096
    )
    gap = classify_complete_sse_event(
        _frame(_payload(seq=9)), regressed.highest_seq, 4096
    )

    assert (first.disposition, first.highest_seq) == (PROGRESS, 5)
    assert (duplicate.disposition, duplicate.highest_seq) == (STRIP, 5)
    assert (regressed.disposition, regressed.highest_seq) == (STRIP, 5)
    assert (gap.disposition, gap.highest_seq) == (PROGRESS, 9)


@pytest.mark.parametrize(
    "event_lines",
    [
        [b"event: bridge_liveness", b"event: bridge_liveness"],
        [b"event: ordinary", b"event: bridge_liveness"],
        [b"event: bridge_liveness", b"event: ordinary"],
    ],
)
def test_assembler_rejects_duplicate_event_fields_before_any_yield(
    event_lines: list[bytes],
) -> None:
    raw = b"\n".join([*event_lines, b"data: " + _payload(), b"", b""])
    yielded: list[tuple[bytes, str | None]] = []
    with pytest.raises(NonstreamError) as info:
        yielded.extend(iter_sse_events(io.BytesIO(raw).readline, 1 << 20))
    assert yielded == []
    assert (info.value.status, info.value.code) == (502, "upstream_protocol_error")


def test_assembler_enforces_reserved_bound_and_preserves_eof_rules() -> None:
    exact = _frame(size=DEFAULT_LIVENESS_MAX_FRAME_BYTES)
    oversized = _frame(size=DEFAULT_LIVENESS_MAX_FRAME_BYTES + 1)
    assert list(iter_sse_events(io.BytesIO(exact).readline, 1 << 20)) == []
    with pytest.raises(NonstreamError) as info:
        list(iter_sse_events(io.BytesIO(oversized).readline, 1 << 20))
    assert info.value.code == "upstream_protocol_error"

    frame = _frame()
    assert list(iter_sse_events(io.BytesIO(frame[:-1]).readline, 1 << 20)) == []
    assert (
        list(iter_sse_events(io.BytesIO(frame.rstrip(b"\n")).readline, 1 << 20)) == []
    )


def test_large_ordinary_event_is_delivered_byte_for_byte() -> None:
    raw = b"event: ordinary\ndata: " + b"x" * 5000 + b"\n\n"
    assert list(iter_sse_events(io.BytesIO(raw).readline, 1 << 20)) == [
        (raw, "x" * 5000)
    ]


def test_physical_sse_line_and_event_bounds_are_unchanged() -> None:
    limit = PassthroughLimits().max_body_bytes
    with pytest.raises(UpstreamBodyTooLarge):
        list(iter_sse_events(io.BytesIO(b"x" * (limit + 1)).readline, limit))
    max_line = b": " + b"x" * (limit - 3) + b"\n"
    assert len(max_line) == limit
    with pytest.raises(UpstreamBodyTooLarge):
        list(iter_sse_events(io.BytesIO(max_line * 3).readline, limit))


def test_sequence_is_consumed_even_when_progress_callback_suppresses_it() -> None:
    calls: list[int] = []

    def suppress() -> bool:
        calls.append(len(calls) + 1)
        return False

    raw = (
        _frame(_payload(seq=5))
        + _frame(_payload(seq=5))
        + _frame(_payload(seq=4))
        + _frame(_payload(seq=9))
    )
    assert list(iter_sse_events(io.BytesIO(raw).readline, 1 << 20, suppress)) == []
    assert calls == [1, 2]


def test_reserved_bytes_never_reach_relay_or_aggregator_inputs() -> None:
    ordinary = openai.content("safe") + openai.finish(0, "stop") + openai.DONE
    offered = list(
        iter_sse_events(
            io.BytesIO(_frame(marker_last=True) + ordinary).readline, 1 << 20
        )
    )
    relay_bytes = b"".join(raw for raw, _data in offered)
    offered_data = "\n".join(data or "" for _raw, data in offered)
    assert b"bridge_liveness" not in relay_bytes
    assert b'"source":"reasoning"' not in relay_bytes
    assert "bridge_liveness" not in offered_data
    body = json.loads(aggregate_events(offered, None, 1 << 20))
    assert openai.message_of(body)["content"] == "safe"


def test_aggregator_defensively_consumes_reserved_events_without_raw_accounting() -> (
    None
):
    progress: list[bool] = []
    aggregator = NonstreamAggregator(1 << 20)
    raw = _frame()
    aggregator.add_event(raw, None, on_upstream_progress=lambda: progress.append(True))
    assert aggregator._raw_bytes == 0  # noqa: SLF001
    assert progress == [True]
    malformed = raw.replace(b'"seq":1', b'"seq":true')
    with pytest.raises(NonstreamError) as info:
        aggregator.add_event(
            malformed, None, on_upstream_progress=lambda: progress.append(True)
        )
    assert info.value.code == "upstream_protocol_error"
    assert aggregator._raw_bytes == 0  # noqa: SLF001
    assert progress == [True]


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0
        self.calls = 0

    def __call__(self) -> float:
        self.calls += 1
        return self.now


def _window(clock: _Clock, **overrides: object) -> LivenessWindow:
    values: dict[str, object] = {
        "first_timeout_s": 10.0,
        "idle_timeout_s": 10.0,
        "safety_cap_s": 5000.0,
        "upstream_progress": True,
        "upstream_progress_max_events": 2,
        "upstream_progress_min_interval_s": 5.0,
        "upstream_progress_cap_s": 3600.0,
    }
    values.update(overrides)
    return LivenessWindow(WindowSpec(**values), clock=clock)


def test_upstream_progress_one_clock_cadence_budget_and_deadline_precedence() -> None:
    clock = _Clock()
    window = _window(clock)
    clock.calls, clock.now = 0, 9.0
    assert window.record_upstream_progress() is True
    assert clock.calls == 1
    assert window.remaining_s() == pytest.approx(10.0)
    clock.now = 10.0
    assert window.record_upstream_progress() is False
    clock.now = 14.0
    assert window.record_upstream_progress() is True
    clock.now = 18.0
    assert window.record_upstream_progress() is False

    late_clock = _Clock()
    late = _window(late_clock)
    late_clock.now = 10.0
    assert late.record_upstream_progress() is False
    assert late.expired() == REASON_FIRST


def test_upstream_progress_never_changes_post_first_s_or_absolute_cap() -> None:
    clock = _Clock()
    window = _window(clock)
    window.record_signal(SIGNAL_S, frozenset({"content"}))
    before = window.remaining_s()
    clock.now = 1.0
    assert window.record_upstream_progress() is False
    assert window.remaining_s() == pytest.approx(before - 1.0)

    capped_clock = _Clock()
    capped = _window(capped_clock, first_timeout_s=5000.0)
    capped_clock.now = 3599.0
    assert capped.record_upstream_progress() is True
    assert capped.remaining_s() == pytest.approx(1.0)
    capped_clock.now = 3600.0
    assert capped.expired() == REASON_CAP


def test_upstream_progress_flag_is_default_off_and_request_scoped(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "missing.json"))
    monkeypatch.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
    monkeypatch.delenv("BRIDGE_NONSTREAM_UPSTREAM_PROGRESS_ENABLED", raising=False)
    limits = PassthroughLimits()
    disabled = passthrough_window(limits, "/v1/chat/completions", {"stream": False})
    assert disabled.record_upstream_progress() is False
    monkeypatch.setenv("BRIDGE_NONSTREAM_UPSTREAM_PROGRESS_ENABLED", "true")
    assert disabled.record_upstream_progress() is False
    enabled = passthrough_window(limits, "/v1/chat/completions", {"stream": False})
    assert enabled.record_upstream_progress() is True


def test_env_cannot_weaken_frozen_upstream_progress_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRIDGE_NONSTREAM_PRE_FIRST_S_MAX_PROGRESS_EVENTS", "1024")
    monkeypatch.setenv("BRIDGE_UPSTREAM_PROGRESS_MIN_EMIT_INTERVAL_S", "0.001")
    monkeypatch.setenv("BRIDGE_LIVENESS_MAX_FRAME_BYTES", "999999")

    limits = PassthroughLimits.from_env()

    assert limits.upstream_progress_max_events == 2
    assert limits.upstream_progress_min_interval_s == 5.0
    assert limits.liveness_max_frame_bytes == DEFAULT_LIVENESS_MAX_FRAME_BYTES

    clock = _Clock()
    window = _window(
        clock,
        upstream_progress_max_events=limits.upstream_progress_max_events,
        upstream_progress_min_interval_s=limits.upstream_progress_min_interval_s,
    )
    assert window.record_upstream_progress() is True
    clock.now = 4.999
    assert window.record_upstream_progress() is False
    clock.now = 5.0
    assert window.record_upstream_progress() is True
    clock.now = 10.0
    assert window.record_upstream_progress() is False

    oversized = _frame(size=DEFAULT_LIVENESS_MAX_FRAME_BYTES + 1)
    with pytest.raises(NonstreamError) as info:
        list(
            iter_sse_events(
                io.BytesIO(oversized).readline,
                1 << 20,
                progress_max_frame_bytes=limits.liveness_max_frame_bytes,
            )
        )
    assert info.value.code == "upstream_protocol_error"
    with pytest.raises(NonstreamError) as direct_info:
        list(iter_sse_events(io.BytesIO(oversized).readline, 1 << 20))
    assert direct_info.value.code == "upstream_protocol_error"

    monkeypatch.setenv("BRIDGE_NONSTREAM_PRE_FIRST_S_MAX_PROGRESS_EVENTS", "1")
    monkeypatch.setenv("BRIDGE_UPSTREAM_PROGRESS_MIN_EMIT_INTERVAL_S", "6.25")
    monkeypatch.setenv("BRIDGE_LIVENESS_MAX_FRAME_BYTES", "2048")
    conservative = PassthroughLimits.from_env()
    assert conservative.upstream_progress_max_events == 1
    assert conservative.upstream_progress_min_interval_s == 6.25
    assert conservative.liveness_max_frame_bytes == 2048
