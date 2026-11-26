"""W3: progressive commit, no-replay-after-wire и per-turn dynamic latch."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS
from typing import Any
from unittest.mock import Mock

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_AGY_DIR = str(_ROOT / "bridges" / "agy-bridge")
if _AGY_DIR not in sys.path:
    sys.path.append(_AGY_DIR)

import core.runtime_env as runtime_env  # noqa: E402
from agy_runtime import sse_body_runner as runner  # noqa: E402
from agy_runtime.stream_delivery_fsm import (  # noqa: E402
    DeliveryPhase,
    can_retry_after_failure,
    initial_delivery_state,
)
from core.stream_resilience_policy import UncommittedTurnBuffer  # noqa: E402

_FLAG = "BRIDGE_AGY_PROGRESSIVE_COMMIT_ENABLED"
_REQUIRED_SUMMARY_FIELDS = {
    "mode",
    "phase_end",
    "emitted_events",
    "b05_skipped_chars",
    "b05_flushed_tail_chars",
    "midstream_replay_blocked",
    "post_live_replay_attempted",
    "client_gone",
    "tool_turn_active",
    "tool_parse_error",
    "upstream_rc",
    "ttft_ms",
    "total_ms",
}


def _config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, progressive: bool | None
) -> Path:
    path = tmp_path / "dynamic_config.json"
    data: dict[str, Any] = {
        "midstream_retry_enabled": True,
        "tool_rollback_enabled": True,
        "BRIDGE_STREAM_MIDSTREAM_RETRY_ENABLED": True,
        "BRIDGE_STREAM_TOOL_ROLLBACK_ENABLED": True,
        "first_event_timeout_s": 300,
        "backoff_base_s": 0,
        "backoff_jitter_ratio": 0,
    }
    if progressive is not None:
        data[_FLAG] = progressive
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(path))
    monkeypatch.setenv("BRIDGE_STREAM_MIDSTREAM_RETRY_ENABLED", "true")
    monkeypatch.setenv("BRIDGE_STREAM_TOOL_ROLLBACK_ENABLED", "true")
    monkeypatch.delenv(_FLAG, raising=False)
    runtime_env._SNAPSHOTS.clear()
    return path


def _handler(wire: list[str], once: Any) -> Any:
    return NS(
        wfile=Mock(),
        send_response=Mock(),
        send_header=Mock(),
        end_headers=Mock(),
        _arm_flush_window=Mock(),
        _graceful_notice=lambda reason, _limit: f"\n[graceful:{reason}]",
        _usage_payload=lambda *_: {},
        _send=Mock(),
        close_connection=False,
        _emit=lambda data: wire.append(data) or True,
        _error_body=lambda out, _enabled: out.get("error"),
        _run_once=once,
    )


def _serve(once: Any) -> tuple[list[str], list[str], dict[str, Any]]:
    wire: list[str] = []
    logs: list[str] = []
    ctx: dict[str, Any] = {"model": "m", "conversation_id": "bbdb91e5"}
    hooks = (
        lambda key, default=False: (
            key in ("emit_tool_trace", "graceful_timeout_on_partial") or default
        ),
        logs.append,
        lambda: "stop",
        Mock(),
    )
    runner.serve_sse_body(_handler(wire, once), ctx, hooks)
    return wire, logs, ctx


def _summaries(logs: list[str]) -> list[dict[str, Any]]:
    result = []
    for line in logs:
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if item.get("event") == "agy_turn_delivery_summary":
            result.append(item)
    return result


def _504(ctx: dict[str, Any]) -> dict[str, Any]:
    ctx["step_ledger"].pin_active_step(0)
    return {
        "state": "agy_error",
        "rc": 1,
        "status_code": 504,
        "err": "HTTP 504",
        "trace_snapshot": ctx["step_ledger"].snapshot(),
        "conversation_id": "bbdb91e5",
    }


def test_progressive_commit_streams_first_delta_before_done_with_global_flags_on(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _config(monkeypatch, tmp_path, True)
    attempts = 0
    before_done = 0

    def once(
        _ctx: dict[str, Any], text: Any, trace: Any, *_callbacks: Any
    ) -> dict[str, Any]:
        nonlocal attempts, before_done
        attempts += 1
        assert trace({"step_index": 1, "tool_name": "read_file"})
        for index in range(12):
            assert text(f"payload-{index:02d} ")
        before_done = "".join(wire).count("payload-")
        return {
            **_504(_ctx),
            "state": "client_gone",
            "retained_events": [("text", "payload-00 ")],
        }

    wire: list[str] = []
    logs: list[str] = []
    ctx: dict[str, Any] = {"model": "m", "conversation_id": "bbdb91e5"}
    hooks = (
        lambda key, default=False: (
            key in ("emit_tool_trace", "graceful_timeout_on_partial") or default
        ),
        logs.append,
        lambda: "stop",
        Mock(),
    )
    original_rollback = UncommittedTurnBuffer.rollback_uncommitted
    rollbacks = 0

    def watched_rollback(buffer: UncommittedTurnBuffer) -> None:
        nonlocal rollbacks
        rollbacks += 1
        original_rollback(buffer)

    monkeypatch.setattr(UncommittedTurnBuffer, "rollback_uncommitted", watched_rollback)
    runner.serve_sse_body(_handler(wire, once), ctx, hooks)
    joined = "".join(wire)
    assert before_done >= 12
    assert attempts == 1, "no_replay_after_wire / INV-STREAM-003"
    assert rollbacks == 0, "отправленный LIVE текст нельзя откатывать"
    assert joined.count("payload-00 ") == 1
    first_text = joined.index("payload-00 ")
    assert "tool — done" not in joined[:first_text], "tool_trace не обгоняет текст"
    assert "tool — done" in joined[first_text:]
    summary = _summaries(logs)[0]
    assert summary["midstream_replay_blocked"] is False
    assert summary["post_live_replay_attempted"] is False


def test_progressive_commit_keepalive_in_precommit_does_not_trigger_live_and_preserves_504_retry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _config(monkeypatch, tmp_path, True)
    attempts = 0
    retry_phases: list[DeliveryPhase] = []
    original_next_epoch = runner.next_retry_epoch

    def watched_next_epoch(state: Any, now_ms: float = 0.0) -> Any:
        retry_phases.append(state.phase)
        return original_next_epoch(state, now_ms)

    monkeypatch.setattr(runner, "next_retry_epoch", watched_next_epoch)

    def once(
        _ctx: dict[str, Any], text: Any, _trace: Any, _reason: Any, keepalive: Any
    ) -> dict[str, Any]:
        nonlocal attempts
        attempts += 1
        _ctx["step_job_id"] = "job-precommit"
        assert keepalive()
        if attempts == 1:
            return _504(_ctx)
        assert text("second-attempt-response")
        return {"state": "done", "rc": 0}

    wire, logs, _ctx = _serve(once)
    joined = "".join(wire)
    assert attempts == 2
    assert retry_phases == [DeliveryPhase.PRECOMMIT]
    assert ": keepalive\n\n" in joined
    assert joined.count("second-attempt-response") == 1
    assert _summaries(logs)[0]["phase_end"] == "closed"


def test_progressive_commit_per_turn_latch_ignores_mid_turn_flag_flip_and_hot_reloads_between_turns(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _config(monkeypatch, tmp_path, True)
    observations: list[bool] = []

    def flipped(_ctx: dict[str, Any], text: Any, *_callbacks: Any) -> dict[str, Any]:
        assert text("before-flip")
        data = json.loads(path.read_text(encoding="utf-8"))
        data[_FLAG] = False
        path.write_text(json.dumps(data), encoding="utf-8")
        runtime_env._SNAPSHOTS.clear()
        assert text("after-flip")
        observations.append(
            all(x in "".join(wire) for x in ("before-flip", "after-flip"))
        )
        return {"state": "done", "rc": 0}

    wire: list[str] = []
    runner.serve_sse_body(
        _handler(wire, flipped),
        {"model": "m"},
        (lambda _key, default=False: default, Mock(), lambda: "stop", Mock()),
    )
    assert observations == [True], "latch не меняется посреди хода"

    def legacy(_ctx: dict[str, Any], text: Any, *_callbacks: Any) -> dict[str, Any]:
        assert text("hot-reloaded-legacy")
        observations.append("hot-reloaded-legacy" in "".join(wire))
        return {"state": "done", "rc": 0}

    wire = []
    runner.serve_sse_body(
        _handler(wire, legacy),
        {"model": "m"},
        (lambda _key, default=False: default, Mock(), lambda: "stop", Mock()),
    )
    assert observations == [True, False]
    assert "hot-reloaded-legacy" in "".join(wire)

    path.write_text("{broken", encoding="utf-8")
    runtime_env._SNAPSHOTS.clear()
    monkeypatch.setenv(_FLAG, "true")  # broken dynamic config обязан fail-closed
    wire = []
    logs: list[str] = []
    runner.serve_sse_body(
        _handler(wire, legacy),
        {"model": "m"},
        (lambda _key, default=False: default, logs.append, lambda: "stop", Mock()),
    )
    assert observations[-1] is True
    assert _summaries(logs)[-1]["mode"] == "legacy"


def test_progressive_commit_default_false_preserves_legacy_whole_turn_buffering(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _config(monkeypatch, tmp_path, None)
    attempts = 0
    visible_before_return: list[bool] = []

    def once(_ctx: dict[str, Any], text: Any, *_callbacks: Any) -> dict[str, Any]:
        nonlocal attempts
        attempts += 1
        value = "discarded-first" if attempts == 1 else "kept-second"
        assert text(value)
        visible_before_return.append(value in "".join(wire))
        return _504(_ctx) if attempts == 1 else {"state": "done", "rc": 0}

    wire: list[str] = []
    runner.serve_sse_body(
        _handler(wire, once),
        {"model": "m"},
        (lambda _key, default=False: default, Mock(), lambda: "stop", Mock()),
    )
    joined = "".join(wire)
    assert attempts == 2
    assert visible_before_return == [False, False]
    assert "discarded-first" not in joined
    assert joined.count("kept-second") == 1


def test_progressive_commit_emits_redact_safe_turn_summary_with_all_t1_t2_t3_fields(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _config(monkeypatch, tmp_path, True)
    secret = "user-secret-prompt-and-tool-arguments"

    def once(_ctx: dict[str, Any], text: Any, *_callbacks: Any) -> dict[str, Any]:
        assert text(secret)
        return {"state": "done", "rc": 0}

    _wire, logs, _ctx = _serve(once)
    summaries = _summaries(logs)
    assert len(summaries) == 1
    summary = summaries[0]
    assert _REQUIRED_SUMMARY_FIELDS <= summary.keys()
    assert summary["mode"] == "progressive"
    assert summary["phase_end"] == "closed"
    assert summary["emitted_events"] == 1
    assert summary["upstream_rc"] == 0
    assert summary["total_ms"] >= 0
    assert secret not in logs[0] and secret not in json.dumps(summary)


def test_progressive_commit_no_duplicate_on_idle_timeout_with_graceful_partial(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _config(monkeypatch, tmp_path, True)
    chunks = ("idle-partial-", "response")

    def once(_ctx: dict[str, Any], text: Any, *_callbacks: Any) -> dict[str, Any]:
        for chunk in chunks:
            assert text(chunk)
        return {
            "state": "idle_timeout",
            "rc": 124,
            "timeout_limit_s": 30,
            "retained_events": [("text", chunk) for chunk in chunks],
        }

    wire, logs, _ctx = _serve(once)
    joined = "".join(wire)
    for chunk in chunks:
        assert joined.count(chunk) == 1
    assert joined.count("idle-partial-response") == 0  # разные SSE delta, не слеплены
    assert joined.count("[graceful:idle_timeout]") == 1
    assert joined.endswith("data: [DONE]\n\n")
    summary = _summaries(logs)[0]
    assert summary["b05_skipped_chars"] == sum(map(len, chunks))
    assert summary["b05_flushed_tail_chars"] == 0


def _direct_runner() -> runner._SseBodyRunner:
    wire: list[str] = []
    logs: list[str] = []
    ctx: dict[str, Any] = {"model": "m", "conversation_id": "bbdb91e5"}
    hooks = (
        lambda key, default=False: key == "emit_tool_trace" or default,
        logs.append,
        lambda: "stop",
        Mock(),
    )
    session = runner.SseStreamSession(_handler(wire, Mock()), ctx, hooks)
    return runner._SseBodyRunner(session)


def test_rw002_partial_precommit_flush_commits_wire_and_blocks_retry() -> None:
    body = _direct_runner()
    body.progressive = True
    body.delivery_fsm = initial_delivery_state(True)
    body.s.buffer.stage_fragment("мысль", "reasoning_content")
    body.s.buffer.stage_fragment("ответ")
    delivered: list[str] = []

    def deliver(value: str, _channel: str) -> bool:
        delivered.append(value)
        return len(delivered) == 1

    body._deliver_direct = deliver
    assert body._flush_precommit() is False
    assert delivered == ["мысль", "ответ"]
    assert body.delivery_fsm.wire_committed is True
    assert can_retry_after_failure(body.delivery_fsm) is False


def test_rw003_progressive_precommit_retry_rolls_back_staged_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = _direct_runner()
    body.progressive = body.buffering = True
    body.delivery_fsm = initial_delivery_state(True)
    body.s.buffer.stage_fragment(" ")
    body.s.buffer.stage_fragment("\n")
    body._invoke = lambda: {"state": "done", "rc": 0}
    monkeypatch.setattr(body.s, "config", NS(flag_enabled=lambda _name: False))

    body.attempt(1, 10.0)

    assert body.s.buffer.commit_fragments() == ()
    assert body.delivery_fsm.epoch == 1
    assert body.s.emitted_stream_text == ""


def test_rw004_live_whitespace_is_direct_and_disconnect_gates_stage() -> None:
    body = _direct_runner()
    body.progressive = True
    body.delivery_fsm = initial_delivery_state(True)
    direct: list[str] = []
    body._deliver_direct = lambda value, _channel: direct.append(value) or True

    assert body.stage("first") is True
    assert body.delivery_fsm.wire_committed is True
    assert body.stage(" ") is True
    assert body.stage("\n") is True
    assert direct == ["first", " ", "\n"]
    assert body.s.buffer.commit_fragments() == ()

    body.s.disconnected = True
    assert body.stage("not-delivered") is False
    assert direct == ["first", " ", "\n"]


def test_rw005_progressive_trace_respects_ledger_forwarding() -> None:
    body = _direct_runner()
    body.progressive = True
    body.delivery_fsm = initial_delivery_state(True)
    event = {"step_index": 4, "tool_name": "read"}
    monkey_forward = Mock(return_value=False)
    body.s.ledger.should_forward_step = monkey_forward
    traces = Mock(return_value=True)
    body.s.on_tool_trace = traces

    assert body.trace(event) is True
    assert traces.call_count == 0
    assert body._pending_traces == []
    monkey_forward.assert_called_once_with(4)


def test_rw007_normal_progressive_summary_is_closed_without_replay_block(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _config(monkeypatch, tmp_path, True)

    def once(_ctx: dict[str, Any], text: Any, *_callbacks: Any) -> dict[str, Any]:
        assert text("normal-response")
        return {"state": "done", "rc": 0}

    _wire, logs, _ctx = _serve(once)
    summary = _summaries(logs)[0]
    assert summary["phase_end"] == "closed"
    assert summary["midstream_replay_blocked"] is False
    assert summary["post_live_replay_attempted"] is False


def test_f011_post_live_attempt_blocks_replay_without_reinvoking_upstream() -> None:
    """F-011: attempt(index>0) после wire_committed=True сразу возвращает ошибку без _invoke/prepare_buffer."""
    body = _direct_runner()
    body.progressive = body.buffering = True
    body.delivery_fsm = initial_delivery_state(True)
    assert body.stage("Доставленный чанк") is True
    assert body.delivery_fsm.wire_committed is True
    body._last_out = {"state": "pump_error", "rc": 1, "err": "upstream_broken"}

    invoke_mock = Mock(return_value={"state": "done", "rc": 0})
    prep_mock = Mock()
    body._invoke = invoke_mock
    body.prepare_buffer = prep_mock

    out1 = body.attempt(1, 10.0)
    assert invoke_mock.call_count == 0
    assert prep_mock.call_count == 0
    assert body._post_live_replay_attempted is True
    assert out1 == {"state": "pump_error", "rc": 1, "err": "upstream_broken"}

    logs: list[str] = []
    body.s.hooks = (body.s.hooks[0], logs.append, body.s.hooks[2], body.s.hooks[3])
    body._log_turn_summary(out1)
    summary = json.loads(logs[-1])
    assert summary["phase_end"] == "closed"
    assert summary["post_live_replay_attempted"] is True
    assert summary["midstream_replay_blocked"] is True


def test_f012_progressive_trace_records_to_collector() -> None:
    """F-012: progressive trace() также передаёт forwarded-трейсы в collector.on_record."""
    body = _direct_runner()
    body.progressive = body.buffering = True
    body.delivery_fsm = initial_delivery_state(True)
    rec = Mock()
    body.collector.on_record = rec
    event = {"step_index": 2, "tool_name": "read_file"}

    assert body.trace(event) is True
    assert rec.call_count == 1
    assert rec.call_args[0][0]["tool_name"] == "read_file"


def test_f014_drain_traces_propagates_backpressure_and_stops_on_failure() -> None:
    """F-014: _drain_traces() останавливается на первом False от on_tool_trace и возвращает False из stage()."""
    body = _direct_runner()
    body.progressive = body.buffering = True
    body.delivery_fsm = initial_delivery_state(True)
    assert body.trace({"step_index": 1, "tool_name": "read_file"}) is True
    assert body.trace({"step_index": 2, "tool_name": "grep"}) is True
    trace_mock = Mock(side_effect=[False, True])
    body.s.on_tool_trace = trace_mock

    assert body.stage("Первый чанк") is False
    assert trace_mock.call_count == 1
    assert body.delivery_fsm.wire_committed is True
