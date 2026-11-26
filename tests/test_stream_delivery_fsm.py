"""W1: детерминированные L1-тесты чистого ядра потоковой доставки agy-bridge.

Zero-I/O FSM (`agy_runtime.stream_delivery_fsm`): переходы фаз, no-replay-after-wire,
chunk-boundary-invariant [B-05] / F-FSM-I2, drop_stale на чужом epoch (F-FSM-I3),
sanitizer-headers fail-closed и redact-safe turn summary.
"""

from __future__ import annotations

import ast
import json
import random
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bridges" / "agy-bridge"))

from agy_runtime.stream_delivery_fsm import (  # noqa: E402
    DeliveryAction,
    DeliveryEvent,
    DeliveryEventKind,
    DeliveryPhase,
    TurnSummaryMetrics,
    can_retry_after_failure,
    canonical_trace_key,
    filter_unemitted_retained,
    format_turn_summary,
    initial_delivery_state,
    mark_sent,
    next_retry_epoch,
    sanitizer_headers,
    step_delivery,
)


def _evt(
    kind: DeliveryEventKind,
    seq: int,
    payload: str,
    channel: str = "text",
    epoch: int = 0,
    deliverable: bool = True,
) -> DeliveryEvent:
    return DeliveryEvent(
        epoch=epoch,
        seq=seq,
        kind=kind,
        channel=channel,
        payload=payload,
        deliverable=deliverable,
    )


class TestPhasesAndTransitions:
    def test_legacy_buffered_stages_and_finishes(self) -> None:
        state = initial_delivery_state(progressive=False)
        staged = step_delivery(state, _evt(DeliveryEventKind.CONTENT, 0, "hello"))
        assert staged[1] == (DeliveryAction("stage", "text", "hello", 0),)
        finished = step_delivery(state, _evt(DeliveryEventKind.DONE, 1, ""))
        assert finished[0].phase is DeliveryPhase.CLOSED
        assert finished[1][0].kind == "finish"
        assert finished[1][0].payload == ""

    def test_precommit_flush_and_emit_then_live_after_mark_sent(self) -> None:
        state = initial_delivery_state(progressive=True)
        first = step_delivery(state, _evt(DeliveryEventKind.CONTENT, 0, "chunk1"))
        assert first[0].phase is DeliveryPhase.PRECOMMIT  # фаза остаётся до mark_sent
        assert first[1] == (DeliveryAction("flush_and_emit", "text", "chunk1", 0),)
        live = mark_sent(first[0], 0)
        assert live.phase is DeliveryPhase.LIVE
        assert live.wire_committed is True
        assert live.last_sent_seq == 0
        assert live.emitted_events == 1
        assert live.pending_bytes == 0
        second = step_delivery(live, _evt(DeliveryEventKind.CONTENT, 1, "chunk2"))
        assert second[1] == (DeliveryAction("emit", "text", "chunk2", 1),)

    def test_precommit_tool_trace_does_not_race_ahead(self) -> None:
        state = initial_delivery_state(progressive=True)
        traced = step_delivery(
            state,
            _evt(DeliveryEventKind.TOOL_TRACE, 0, '{"k": 1}', channel="tool_trace"),
        )
        assert traced[0].phase is DeliveryPhase.PRECOMMIT
        assert traced[1] == (DeliveryAction("stage", "tool_trace", '{"k": 1}', 0),)

    def test_precommit_empty_and_undeliverable_payloads_are_staged(self) -> None:
        state = initial_delivery_state(progressive=True)
        empty = step_delivery(state, _evt(DeliveryEventKind.CONTENT, 0, ""))
        assert empty[1] == (DeliveryAction("stage", "text", "", 0),)
        undeliverable = step_delivery(
            state, _evt(DeliveryEventKind.CONTENT, 1, "x", deliverable=False)
        )
        assert undeliverable[1][0].kind == "stage"

    def test_precommit_and_live_terminal_close(self) -> None:
        for progressive in (True, False):
            state = initial_delivery_state(progressive=progressive)
            if progressive:
                state = mark_sent(state, 0)
            closed = step_delivery(state, _evt(DeliveryEventKind.ERROR, 2, "boom"))
            assert closed[0].phase is DeliveryPhase.CLOSED
            assert closed[1] == (DeliveryAction("finish", "", "boom", 2),)

    def test_closed_state_drops_everything(self) -> None:
        state = initial_delivery_state(progressive=True, epoch=0)
        state = step_delivery(state, _evt(DeliveryEventKind.DONE, 0, ""))[0]
        after = step_delivery(state, _evt(DeliveryEventKind.CONTENT, 1, "late"))
        assert after[0] is state
        assert after[1][0].kind == "drop_stale"


class TestEpochAndRetry:
    def test_foreign_epoch_dropped_and_counted(self) -> None:
        state = initial_delivery_state(progressive=True)
        dropped = step_delivery(
            state, _evt(DeliveryEventKind.CONTENT, 0, "stale", epoch=state.epoch + 1)
        )
        assert dropped[0].stale_dropped == 1
        assert dropped[1] == (DeliveryAction("drop_stale"),)
        again = step_delivery(
            dropped[0], _evt(DeliveryEventKind.CONTENT, 1, "stale", epoch=99)
        )
        assert again[0].stale_dropped == 2

    def test_no_replay_after_wire(self) -> None:
        state = initial_delivery_state(progressive=True)
        state = mark_sent(state, 3)
        assert can_retry_after_failure(state) is False
        assert (
            can_retry_after_failure(initial_delivery_state(progressive=False)) is True
        )

    def test_next_retry_epoch_injectable_now(self) -> None:
        state = initial_delivery_state(progressive=True)
        state = step_delivery(state, _evt(DeliveryEventKind.CONTENT, 0, "x"))[0]
        retried = next_retry_epoch(state, now_ms=4242.0)
        assert retried.epoch == state.epoch + 1
        assert retried.pending_bytes == 0
        assert retried.precommit_started_ms == 4242.0
        assert retried.phase is DeliveryPhase.PRECOMMIT
        assert retried.wire_committed is False
        # wire_committed → идемпотентный no-op
        committed = mark_sent(state, 1)
        assert next_retry_epoch(committed, now_ms=9.0) is committed
        legacy = next_retry_epoch(initial_delivery_state(progressive=False), now_ms=1.0)
        assert legacy.phase is DeliveryPhase.LEGACY_BUFFERED


class TestChunkBoundaryInvariant:
    def _run(
        self, chunks: list[str], emitted: str
    ) -> tuple[list[tuple[str, Any]], int]:
        retained: list[tuple[str, Any]] = [("text", c) for c in chunks]
        return filter_unemitted_retained(retained, emitted_content=emitted)

    def test_whole_chunking_is_invariant(self) -> None:
        text = "streaming delivery keeps every byte"
        for size in (len(text), 1, 7):
            chunks = [text[i : i + size] for i in range(0, len(text), size)]
            filtered, skipped = self._run(chunks, text)
            assert "".join(c for _, c in filtered) == ""
            assert skipped == len(text)

    def test_partial_midchunk_overlap_cut_exactly(self) -> None:
        chunks = ["abcdef", "ghijkl"]
        filtered, skipped = self._run(chunks, "abcdefghi")
        assert "".join(c for _, c in filtered) == "jkl"
        assert skipped == 9

    def test_zero_prefix_emits_everything(self) -> None:
        filtered, skipped = self._run(["abc", "def"], "")
        assert "".join(c for _, c in filtered) == "abcdef"
        assert skipped == 0

    def test_divergent_fallback_keeps_remaining_text_intact(self) -> None:
        filtered, skipped = self._run(["abcX", "def"], "abcdef")
        assert "".join(c for _, c in filtered) == "abcXdef"
        assert skipped == 0

    def test_seeded_random_chunking_is_invariant(self) -> None:
        rng = random.Random(20241126)
        for _ in range(50):
            text = "".join(rng.choice("abcdefgh ") for _ in range(rng.randint(0, 64)))
            cut = rng.randint(0, len(text))
            emitted, tail = text[:cut], text[cut:]
            size = rng.randint(1, max(1, len(text)))
            chunks = [text[i : i + size] for i in range(0, len(text), size)]
            filtered, skipped = self._run(chunks, emitted)
            assert "".join(c for _, c in filtered) == tail
            assert skipped == cut

    def test_reasoning_channel_uses_own_cursor(self) -> None:
        retained = [("reasoning", "abc"), ("text", "abc"), ("reasoning", "de")]
        filtered, skipped = filter_unemitted_retained(
            retained, emitted_reasoning="abcde"
        )
        assert [c for kind, c in filtered if kind == "reasoning"] == []
        assert [c for kind, c in filtered if kind == "text"] == ["abc"]
        assert skipped == 5

    def test_tool_trace_canonical_key_matching(self) -> None:
        key_a = canonical_trace_key({"b": 2, "a": 1})
        assert key_a == '{"a": 1, "b": 2}'
        assert canonical_trace_key({"a": 1, "b": 2}) == key_a
        retained = [
            ("tool_trace", {"a": 1, "b": 2}),
            ("tool_trace", "non-object"),
            ("tool_trace", {"z": 9}),
        ]
        filtered, skipped = filter_unemitted_retained(
            retained, emitted_tool_traces=(key_a, '{"z": 9}')
        )
        assert [payload for _, payload in filtered] == ["non-object"]
        assert skipped == len(key_a) + len('{"z": 9}')

    def test_unknown_kinds_pass_through(self) -> None:
        retained: list[tuple[str, Any]] = [("other", {"x": 1})]
        filtered, skipped = filter_unemitted_retained(retained)
        assert filtered == retained
        assert skipped == 0


class TestSanitizerAndSummary:
    def test_sanitizer_headers_fail_closed(self) -> None:
        assert sanitizer_headers(True) == (("X-Bridge-Tool-Sanitized", "1"),)
        assert sanitizer_headers(False) == ()
        non_boolean: Any = 1
        assert sanitizer_headers(non_boolean) == ()

    def test_format_turn_summary_is_single_line_redact_safe_json(self) -> None:
        state = initial_delivery_state(progressive=True)
        state = mark_sent(state, 7)
        metrics = TurnSummaryMetrics(
            b05_skipped_chars=123,
            b05_flushed_tail_chars=45,
            midstream_replay_blocked=True,
            post_live_replay_attempted=False,
            client_gone=True,
            tool_turn_active=False,
            tool_parse_error=True,
            upstream_rc=42,
            ttft_ms=12.5,
            total_ms=99.5,
        )
        line = format_turn_summary(state, metrics)
        assert "\n" not in line
        parsed: dict[str, Any] = json.loads(line)
        assert parsed["event"] == "agy_turn_delivery_summary"
        assert parsed["mode"] == "progressive"
        assert parsed["phase_end"] == "live"
        assert parsed["emitted_events"] == 1
        assert parsed["b05_skipped_chars"] == 123
        assert parsed["b05_flushed_tail_chars"] == 45
        assert parsed["midstream_replay_blocked"] is True
        assert parsed["post_live_replay_attempted"] is False
        assert parsed["client_gone"] is True
        assert parsed["tool_turn_active"] is False
        assert parsed["tool_parse_error"] is True
        assert parsed["upstream_rc"] == 42
        assert parsed["ttft_ms"] == 12.5
        assert parsed["total_ms"] == 99.5
        leaked_content = "secret prompt and tool arguments"
        leaked_metrics = TurnSummaryMetrics(b05_skipped_chars=len(leaked_content))
        leaked_line = format_turn_summary(state, leaked_metrics)
        assert "secret" not in line
        assert leaked_content not in leaked_line
        assert "prompt" not in leaked_line
        assert "arguments" not in leaked_line

    def test_format_turn_summary_legacy_mode(self) -> None:
        line = format_turn_summary(
            initial_delivery_state(progressive=False), TurnSummaryMetrics()
        )
        parsed: dict[str, Any] = json.loads(line)
        assert parsed["mode"] == "legacy"
        assert parsed["phase_end"] == "legacy_buffered"
        assert parsed["upstream_rc"] is None
        assert parsed["ttft_ms"] is None

    def test_state_defaults_and_frozen(self) -> None:
        state = initial_delivery_state(progressive=False)
        assert state.phase is DeliveryPhase.LEGACY_BUFFERED
        assert state.last_sent_seq == -1
        assert state.emitted_events == 0
        assert state.max_precommit_hold_ms == 15000.0
        assert state.max_precommit_bytes == 262144
        with pytest.raises(Exception):  # noqa: B017 - frozen dataclass contract
            state.epoch = 5  # type: ignore[misc]


class TestZeroIOContract:
    def test_no_io_imports_and_no_positive_sleep(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import agy_runtime.stream_delivery_fsm as fsm

        source = Path(fsm.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        assert imported <= {
            "__future__",
            "collections",
            "dataclasses",
            "enum",
            "json",
            "typing",
        }
        assert not imported & {
            "os",
            "sys",
            "time",
            "threading",
            "socket",
            "subprocess",
            "pathlib",
            "logging",
            "io",
            "http",
        }

        def forbidden_io(*args: Any, **kwargs: Any) -> None:
            raise AssertionError("Zero-I/O module attempted external I/O")

        monkeypatch.setattr("socket.socket", forbidden_io)
        monkeypatch.setattr("subprocess.run", forbidden_io)
        monkeypatch.setattr("time.sleep", forbidden_io)
        state = mark_sent(initial_delivery_state(progressive=True), 0)
        step_delivery(state, _evt(DeliveryEventKind.CONTENT, 1, "safe"))
        canonical_trace_key({"safe": True})
        format_turn_summary(state, TurnSummaryMetrics())
        assert "sleep" not in source
