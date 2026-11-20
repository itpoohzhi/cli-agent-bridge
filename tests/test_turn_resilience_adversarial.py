"""Adversarial / Interleaving / Neighbor-Contract (W3-B, Гейт 2): устойчивость хода под нагрузкой.

Мультичат-интерливинг, ретрай/форк, рестарт, TTL окна сбоев на FakeClock (без sleep),
переключение флагов без рестарта, грязные входы и соседние контракты. Без сети и портов.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from resilience_wiring_support import (
    FLAG_ENVS,
    collect_log,
    enable,
    facade,
    load_server,
    malformed_ctx,
    stub,
    tail_with_steps,
    use_config,
)

from core.failure_window import FailureWindow
from core.recovery_flags import read_recovery_flags
from core.tool_call_completion_tracker import ToolCallCompletionTracker


class FakeClock:
    """Управляемые часы: время двигает только тест."""

    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def _malformed_out() -> dict[str, Any]:
    return {"state": "agy_error", "rc": 1, "err": stub.MALFORMED_TEXT, "text": "", "tool_events": 0}


def test_two_chats_with_identical_start_do_not_cross_recover(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Два чата с одинаковым стартовым сообщением: recovery одного не касается второго."""
    enable(monkeypatch, tmp_path, "recovery")
    fac = facade()
    tail_a, tail_b = tail_with_steps(), tail_with_steps(broken=True)
    fed_a: list[str] = []
    fed_b: list[str] = []
    out_a, out_b = _malformed_out(), _malformed_out()
    fac.recover(malformed_ctx(fed_a), SimpleNamespace(_tail=tail_a), out_a, lambda _l: None)
    fac.recover(malformed_ctx(fed_b), SimpleNamespace(_tail=tail_b), out_b, lambda _l: None)
    assert (out_a["state"], len(fed_a)) == ("done", 1)
    assert (out_b["state"], fed_b) == ("agy_error", [])
    assert tail_a._resilience_step_tracker is not tail_b._resilience_step_tracker  # pyright: ignore[reportAttributeAccessIssue]


def test_interleaved_threads_keep_per_turn_state_isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """16 потоков с общим окном сбоев: у каждого хода свой счётчик попыток, окно ограничено."""
    enable(monkeypatch, tmp_path, "pause")
    fac = facade()
    results: list[tuple[bool, int]] = []
    guard = threading.Lock()

    def worker() -> None:
        ctx: dict[str, Any] = {"t_req_start": 0.0, "resilience_clock": lambda: 10.0}
        first = fac.take(ctx, {"duration_s": 5.0}, lambda: True, lambda _l: None)
        with guard:
            results.append((first, int(ctx["_resilience_attempts"])))

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    assert results == [(True, 1)] * 16
    assert fac._WINDOW.recent_count(10.0) == 16  # pyright: ignore[reportPrivateUsage]


def test_retry_fork_copies_have_independent_attempt_counters(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    enable(monkeypatch, tmp_path, "pause")
    fac = facade()
    ctx: dict[str, Any] = {"t_req_start": 0.0, "resilience_clock": lambda: 1.0}
    assert fac.take(ctx, {}, lambda: True, lambda _l: None) is True
    fork = dict(ctx)
    assert fac.take(fork, {}, lambda: True, lambda _l: None) is False  # attempt 2 > max_retries
    assert ctx["_resilience_attempts"] == 1 and fork["_resilience_attempts"] == 2


def test_failure_window_ttl_eviction_on_fake_clock_without_sleep() -> None:
    clock, window = FakeClock(), FailureWindow(window_s=60.0, maxlen=8)
    for _ in range(5):
        _ = window.record(clock())
    clock.now = 59.9
    assert window.recent_count(clock()) == 5
    clock.now = 60.1
    assert window.recent_count(clock()) == 0
    for _ in range(20):
        _ = window.record(clock())
    assert window.recent_count(clock()) == 8  # O(1)-память: maxlen ограничивает окно


def test_process_restart_resets_failure_memory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    enable(monkeypatch, tmp_path, "pause")
    fac = facade()
    _ = fac._WINDOW.record(1.0)  # pyright: ignore[reportPrivateUsage]
    assert fac._WINDOW.recent_count(1.0) == 1  # pyright: ignore[reportPrivateUsage]
    fac.reset_failure_window()
    assert fac._WINDOW.recent_count(1.0) == 0  # pyright: ignore[reportPrivateUsage]


def test_flags_false_true_false_without_restart_via_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = use_config(monkeypatch, tmp_path)
    seen = []
    for value in (False, True, False):
        cfg.write_text(json.dumps({name: value for name in FLAG_ENVS.values()}), encoding="utf-8")
        seen.append(all(vars(read_recovery_flags()).values()))
    assert seen == [False, True, False]


@pytest.mark.parametrize("text", ["{не json", "[]", "null", '{"BRIDGE_TOOLCALL_ERROR_RECOVERY_ENABLED": "true"}', "\x00\x01"])
def test_dirty_config_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, text: str) -> None:
    _ = use_config(monkeypatch, tmp_path, text)
    monkeypatch.setenv(FLAG_ENVS["recovery"], "true")
    assert read_recovery_flags().toolcall_error_recovery is False


def test_symlink_and_oversize_config_fail_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    real = tmp_path / "real.json"
    real.write_text(json.dumps({FLAG_ENVS["mask"]: True}), encoding="utf-8")
    link = tmp_path / "link.json"
    os.symlink(real, link)
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(link))
    monkeypatch.setenv(FLAG_ENVS["mask"], "true")
    assert read_recovery_flags().vendor_retry_phrase_mask is False  # симлинк отвергнут
    big = tmp_path / "big.json"
    big.write_text(json.dumps({"pad": "x" * 70000, FLAG_ENVS["mask"]: True}), encoding="utf-8")
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(big))
    assert read_recovery_flags().vendor_retry_phrase_mask is False  # oversize отвергнут


def test_env_veto_wins_over_config_opt_in(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _ = use_config(monkeypatch, tmp_path, json.dumps({FLAG_ENVS["retain"]: True}))
    assert read_recovery_flags().hot_session_retain_on_transient is True
    monkeypatch.setenv(FLAG_ENVS["retain"], "false")
    assert read_recovery_flags().hot_session_retain_on_transient is False


@pytest.mark.parametrize("bad", [None, "", 0, [], {}, b"x", float("nan")])
def test_dirty_out_values_never_crash_or_relax(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bad: Any) -> None:
    enable(monkeypatch, tmp_path, "keepalive", "recovery", "retain", "mask", "classifier", "pause")
    fac = facade()
    ctx: dict[str, Any] = {"stream_committed": True, "sess_key": ("m", "/w", "e"), "conversation_id": "c"}
    out = {"err": bad, "state": bad, "num_turns": bad, "tool_events": 0, "duration_s": bad, "conversation_id": bad}
    assert fac.delivered_after_commit(ctx, out, False) is True  # непонятный сбой → база: commit запрещает повтор
    fac.recover(ctx, SimpleNamespace(_tail=None), dict(out), lambda _l: None)
    fac.invalidate(ctx, out, lambda *_a: None, lambda _l: None)
    assert fac.take({}, out, lambda: True, lambda _l: None) in (True, False)
    assert fac.masked_error_body(lambda o, r=None: {"message": bad, "detail": bad})({}, None) is not None


def test_neighbor_json_mode_without_tracker_or_feed_is_noop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """JSON-режим: нет `recovery_feed`/трекера — recovery молчит, ход как в базе."""
    enable(monkeypatch, tmp_path, "recovery")
    out = _malformed_out()
    lines, log = collect_log()
    facade().recover({"tools": []}, SimpleNamespace(_tail=tail_with_steps()), out, log)
    assert out["state"] == "agy_error" and not any("toolcall.recovered" in line for line in lines)
    assert any("toolcall.rejected:delivery.failed" in line for line in lines)


def test_neighbor_explicit_chat_id_key_passed_through_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    enable(monkeypatch, tmp_path, "retain")
    seen: list[Any] = []
    key = ("chat-42", "gemini-3.8-flash", "/w", "high")
    ctx = {"sess_key": key, "conversation_id": "cid-9"}
    out = {"err": stub.MALFORMED_TEXT, "num_turns": 0, "conversation_id": ""}
    facade().invalidate(ctx, out, lambda k, c: seen.append((k, c)), lambda _l: None)
    assert seen == [(key, "cid-9")]


def test_flags_off_is_byte_identical_to_base_for_five_scenarios(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """flags_off: 5 точек фасада возвращают ровно базовые значения."""
    _ = use_config(monkeypatch, tmp_path)
    fac, server = facade(), load_server()
    ctx: dict[str, Any] = {"stream_committed": True}
    assert fac.delivered_after_commit(ctx, {"err": stub.USERINFO_EOF}, False) is True  # 1: commit → delivered
    assert fac.delivered_after_commit({}, {"err": stub.USERINFO_EOF}, False) is False  # 2: нет commit
    assert server._retry_pause_s(2, lambda: 0.25) == pytest.approx(0.5)  # pyright: ignore[reportPrivateUsage]  # 3: пауза U(0, cap=2) · 0.25
    body = server.Handler._error_body({"state": "agy_error", "err": stub.MALFORMED_TEXT})  # pyright: ignore[reportPrivateUsage]
    assert body["message"] == stub.MALFORMED_TEXT[:500]  # 4: тело ошибки без маски
    assert server._is_transient_upstream_error(stub.USERINFO_EOF) is False  # 5: Go-сбой не транзиентен
    assert fac.take({}, {}, lambda: False, lambda _l: None) is False  # токен базы решает
    assert not hasattr(tail_with_steps(), "_resilience_step_tracker")


def test_recover_tracker_survives_out_of_order_and_duplicate_records(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    enable(monkeypatch, tmp_path, "recovery")
    fac = facade()
    tail = SimpleNamespace()
    records = list(stub._transcript_records("malformed_valid"))  # pyright: ignore[reportPrivateUsage]
    for rec in (records[2], records[1], records[0], records[2], records[1]):
        fac.observe_record(tail, rec, int(rec["step_index"]))
    tracker = tail._resilience_step_tracker
    assert isinstance(tracker, ToolCallCompletionTracker)
    assert [(s.index, s.kind) for s in tracker.snapshot().steps] == [(4, "planner"), (5, "error"), (6, "planner")]
