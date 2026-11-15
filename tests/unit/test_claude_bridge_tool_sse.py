"""W3: literal SSE выдаётся до завершения upstream, а не буферизуется до EOF."""

from __future__ import annotations

import pytest

from tests.unit._claude_bridge_tool_fakes import done_script
from tests.unit._claude_bridge_tool_http import (
    DummyConnection,
    Harness,
    bridge as bridge,  # noqa: F401
    harness as harness,  # noqa: F401
    set_toolless_policy,
    split_raw,
    sse_payloads,
)

EXPECTED = 'P1<tool_call>{"name":"x"}</tool_call> <invoke> P2'


def _assert_live_prefix(snapshot: bytes) -> None:
    status_line, body = split_raw(snapshot)
    frames = sse_payloads(body)
    parts = [
        choice["delta"].get("content", "")
        for frame in frames
        for choice in frame["choices"]
    ]
    assert status_line == "HTTP/1.1 200 OK"
    assert "".join(parts) == EXPECTED
    assert len([part for part in parts if part]) > 2
    assert not any("error" in frame for frame in frames)
    assert [c["finish_reason"] for f in frames for c in f["choices"]] == [None] * len(
        frames
    )
    assert "[DONE]" not in body


def test_off_text_sse_emits_literal_before_upstream_done(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_toolless_policy(monkeypatch, None)
    payload = {"stream": True, "messages": []}
    conn = DummyConnection.for_post(payload)
    snapshots: list[tuple[bytes, int]] = []
    runs = harness.play([])

    def snapshot() -> None:
        snapshots.append((conn.written(), runs.runs[0].q.pending))

    runs.script = (
        *(("text", ch) for ch in EXPECTED),
        snapshot,
        *done_script(),
    )
    reply = harness.post(payload, conn)
    assert len(snapshots) == 1
    early_bytes, pending_upstream = snapshots[0]
    assert pending_upstream == len(done_script())
    _assert_live_prefix(early_bytes)
    assert reply.status == 200
    assert reply.body.endswith("data: [DONE]\n\n")
    assert sse_payloads(reply.body)[-1]["choices"][0]["finish_reason"] == "stop"
