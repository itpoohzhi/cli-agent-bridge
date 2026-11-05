"""Тесты восстановления после транзиентного обрыва стрима agy (INV-STREAM-001..005, T-ISO-I1..I4).

Покрывают чистое ядро `core/stream_interruption_recovery.py`, `_TranscriptTail`,
`Handler._serve_sse` (мягкое закрытие частичного ответа) и обратную совместимость
kwargs `AdaptiveTimeoutController`.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import threading
import unittest
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.stream_interruption_recovery import (  # noqa: E402
    DEFAULT_INTERRUPTION_NOTICE,
    evaluate_graceful_interruption,
    evaluate_stream_retry_eligibility,
    is_transient_stream_interruption,
    resolve_done_turn_outcome,
)
from core.watchdog import AdaptiveTimeoutController  # noqa: E402

_BRIDGE_PY = _REPO_ROOT / "bridges" / "agy-bridge" / "server.py"
_INTERRUPTED = (
    "The stream was interrupted. Please continue the task you were working on."
)
_PARTIAL = "Частичный ответ модели"


def _load_bridge() -> Any:
    os.environ.setdefault("AGY_BRIDGE_KEY", "test-key-stream-interrupted")
    spec = importlib.util.spec_from_file_location(
        "agy_bridge_server_stream_interrupted_under_test", _BRIDGE_PY
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


srv = _load_bridge()


def _heal_kwargs(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = dict(
        rc=1,
        result_error=_INTERRUPTED,
        result_status="ERROR",
        final_text="Полный ответ",
        emitted_text="",
        completion_done_without_tools=True,
        last_completion_seq=5,
        last_error_seq=3,
        drain_complete=True,
        had_transient_error=True,
    )
    base.update(over)
    return base


def _make_tail() -> Any:
    plan = srv._TurnPlan()
    plan.mode = "OFF"
    plan.base_idx = 0
    plan.offset = 0
    return srv._TranscriptTail(
        emit=lambda _idx, _text, _cb: True,
        stop_event=threading.Event(),
        done_event=threading.Event(),
        resumed=False,
        plan=plan,
        turn_id="turn-recovery",
        emit_content=lambda _idx, _text: True,
    )


def _feed(tail: Any, **record: Any) -> None:
    tail._emit_record(json.dumps(record, ensure_ascii=False).encode("utf-8"))


def _error_record(step_index: int) -> dict[str, Any]:
    return dict(
        type="ERROR_MESSAGE",
        step_index=step_index,
        content="The stream was interrupted",
    )


def _planner_record(step_index: int) -> dict[str, Any]:
    return dict(
        type="PLANNER_RESPONSE",
        step_index=step_index,
        status="DONE",
        content="Финальный ответ",
        tool_calls=[],
    )


def _serve_partial_interrupted_sse() -> tuple[list[str], dict[str, Any]]:
    """Прогоняет `Handler._serve_sse` с обрывом после частичного ответа; (кадры SSE, итог)."""
    frames: list[str] = []
    outs: list[dict[str, Any]] = []
    handler = srv.Handler.__new__(srv.Handler)
    handler.send_response = lambda *_a, **_k: None
    handler.send_header = lambda *_a, **_k: None
    handler.end_headers = lambda: None
    handler._emit = lambda data: frames.append(data) or True

    def run_once(ctx: dict, on_text: Any, *_rest: Any) -> dict[str, Any]:
        assert on_text(_PARTIAL)
        out = {
            "state": "agy_error",
            "rc": 1,
            "err": _INTERRUPTED,
            "text": _PARTIAL,
            "conversation_id": "cid-12345678",
        }
        ctx["finalize_timeout"](out)
        outs.append(out)
        return out

    handler._run_once = run_once
    handler._serve_sse({"model": "m"})
    return frames, outs[0]


class StreamInterruptedRecoveryTests(unittest.TestCase):
    def test_inv_stream_001_done_turn_self_heals_after_transient_error(self) -> None:
        res = resolve_done_turn_outcome(**_heal_kwargs())
        self.assertEqual(res.state, "done")
        self.assertEqual(res.rc, 0)
        self.assertIs(res.self_healed, True)

        tail = _make_tail()
        _feed(tail, **_error_record(3))
        _feed(tail, **_planner_record(5))
        self.assertIs(tail.had_transient_error, True)
        self.assertIs(tail.final_planner, True)
        self.assertEqual(tail.final_planner_content, "Финальный ответ")
        self.assertEqual(tail.last_planner_step_index, 5)
        self.assertEqual(tail.last_error_step_index, 3)

    def test_inv_stream_002_no_false_heal_on_error_after_planner_or_incomplete_drain(
        self,
    ) -> None:
        cases = {
            "error_after_planner": dict(last_error_seq=7),
            "planner_with_tools": dict(completion_done_without_tools=False),
            "drain_timeout": dict(drain_complete=False),
            "self_heal_disabled": dict(self_heal_enabled=False),
            "non_transient": dict(
                result_error="401 Unauthorized", had_transient_error=False
            ),
        }
        for name, over in cases.items():
            with self.subTest(case=name):
                res = resolve_done_turn_outcome(**_heal_kwargs(**over))
                self.assertEqual(res.state, "agy_error")
                self.assertIs(res.self_healed, False)

        tail = _make_tail()
        _feed(tail, **_planner_record(5))
        self.assertIs(tail.final_planner, True)
        _feed(tail, **_error_record(6))
        self.assertIs(tail.final_planner, False)
        self.assertEqual(tail.last_error_step_index, 6)

    def test_inv_stream_003_retry_eligibility_and_delivered_guard(self) -> None:
        for err in (
            "The stream was interrupted",
            "RST_STREAM",
            "EOF occurred in violation of protocol",
        ):
            with self.subTest(err=err):
                dec = evaluate_stream_retry_eligibility(
                    error_text=err,
                    delivered=False,
                    had_tool_side_effects=False,
                    attempt=1,
                )
                self.assertIs(dec.can_retry, True)
        blocked = {
            "delivered_any": dict(delivered=True),
            "headers_sent": dict(delivered=True),
            "tool_side_effects": dict(delivered=False, had_tool_side_effects=True),
            "second_attempt": dict(delivered=False, attempt=2),
        }
        for name, over in blocked.items():
            with self.subTest(case=name):
                dec = evaluate_stream_retry_eligibility(
                    error_text=_INTERRUPTED, **{"had_tool_side_effects": False, **over}
                )
                self.assertIs(dec.can_retry, False)

        self.assertIs(srv._is_transient_upstream_error(_INTERRUPTED), True)
        self.assertIs(srv._is_transient_upstream_error("503 Service Unavailable"), True)
        self.assertIs(srv._is_transient_upstream_error("Service Unavailable"), False)

    def test_inv_stream_004_graceful_interruption_closes_partial_sse_stream_cleanly(
        self,
    ) -> None:
        dec = evaluate_graceful_interruption(
            error_text=_INTERRUPTED, delivered_content=True
        )
        self.assertIs(dec.should_gracefully_close, True)
        self.assertEqual(dec.finish_reason, "stop")
        self.assertEqual(dec.target_channel, "content")

        frames, out = _serve_partial_interrupted_sse()
        self.assertEqual(out["state"], "done")
        self.assertIs(out["graceful_interruption_closed"], True)
        joined = "".join(frames)
        self.assertIn(_PARTIAL, joined)
        self.assertIn(
            json.dumps(DEFAULT_INTERRUPTION_NOTICE, ensure_ascii=False)[1:-1], joined
        )
        self.assertIn('"finish_reason": "stop"', joined)
        self.assertEqual(frames[-1], "data: [DONE]\n\n")
        self.assertNotIn('"error"', joined)

    def test_inv_stream_005_watchdog_adaptive_timeout_backward_compat_kwargs(
        self,
    ) -> None:
        now = [0.0]
        ctrl = AdaptiveTimeoutController(
            idle_timeout_s=30.0,
            safety_cap_s=120.0,
            io_wait_cap_s=45.0,
            watchdog_interval_s=0.25,
            watchdog_enabled=False,
            clock=lambda: now[0],
        )
        self.assertEqual(ctrl.io_wait_cap_s, 45.0)
        self.assertEqual(ctrl.watchdog_interval_s, 0.25)
        now[0] = 20.0
        ctrl.on_activity("text")
        self.assertEqual(ctrl.last_activity_ts, 20.0)
        now[0] = 40.0  # 40 > 30 от старта, но активность сдвинула дедлайн вперёд
        self.assertEqual(ctrl.check()[:2], (False, ""))
        now[0] = 51.0
        self.assertEqual(ctrl.check()[:2], (True, "idle_timeout"))

    def test_t_iso_i1_to_i4_negative_corpus_isolation(self) -> None:
        # T-ISO-I1: текст модели никогда не классифицируется как обрыв транспорта.
        self.assertIs(
            is_transient_stream_interruption(
                "The stream was interrupted", source="model_content"
            ),
            False,
        )
        # T-ISO-I2: постоянные ошибки не транзиентны.
        for err in (
            "401 Unauthorized",
            "403 Forbidden",
            "Quota exceeded",
            "Invalid API key",
        ):
            with self.subTest(err=err):
                self.assertIs(is_transient_stream_interruption(err), False)
        # T-ISO-I3: нулевая выдача — мягкого закрытия нет.
        zero = evaluate_graceful_interruption(
            error_text=_INTERRUPTED, delivered_content=False, delivered_reasoning=False
        )
        self.assertIs(zero.should_gracefully_close, False)
        # T-ISO-I4: незакрытый/выданный tool_call блокирует закрытие и самоисцеление.
        for over in (
            dict(has_unclosed_tool_call=True),
            dict(delivered_tool_calls=True),
        ):
            with self.subTest(over=over):
                dec = evaluate_graceful_interruption(
                    error_text=_INTERRUPTED, delivered_content=True, **over
                )
                self.assertIs(dec.should_gracefully_close, False)
        res = resolve_done_turn_outcome(**_heal_kwargs(has_unclosed_tool_call=True))
        self.assertIs(res.self_healed, False)
        self.assertEqual(res.state, "agy_error")


if __name__ == "__main__":
    unittest.main()
