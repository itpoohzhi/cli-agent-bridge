"""Deterministic tests for sliding timeout ladder and slot scaling in stdio_resident."""

from __future__ import annotations

import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.stdio_drivers import resolve_pool_and_driver  # noqa: E402
from core.stdio_resident.config import StdioPoolConfig  # noqa: E402
from core.stdio_resident.process_io import LINE, TIMEOUT, TaggedLine  # noqa: E402
from core.stdio_resident.process_pool import ResidentProcessPool, SlotLeaseTimeoutError  # noqa: E402
from core.stdio_resident.protocol_driver import StreamJsonDriver  # noqa: E402
from core.stdio_resident.session_manager import (  # noqa: E402
    DEFAULT_FIRST_PROGRESS_TIMEOUT_S,
    DEFAULT_SAFETY_CAP_S,
    DEFAULT_TURN_IDLE_TIMEOUT_S,
    StdioSessionManager,
    TurnTimeoutError,
    _resolve_deadlines,
)
from core.stdio_resident.sse_error_bridge import _sanitize_log_text  # noqa: E402
from core.stdio_resident.turn_error_sse import ResidentTurnError, build_turn_error  # noqa: E402
from core.stdio_resident.types import SlotAffinityKey  # noqa: E402
from core.stdio_resident.zero_canon_router import _resolve_proxy_timeout_s  # noqa: E402
from core.timeout_ladder import FLAG_TIMEOUT_LADDER, ActivityKind  # noqa: E402

DUMMY_KEY = "sk-dummy-secret-999"


class _FakeClockHandle:
    """Fake handle advancing a deterministic clock per read (0 sleeps, 0 sockets)."""

    def __init__(self, script: list[tuple[float, str, str | None, bool]], clock: list[float]) -> None:
        self._script = list(script)
        self._clock = clock
        self.pid = 8101
        self.generation = 0
        self._pgid_dead = True
        self.seen_timeouts: list[float] = []

    def write(self, data: bytes) -> None:
        _ = data

    def read_line_outcome(self, timeout_s: float | None = None) -> tuple[str, TaggedLine | None]:
        if timeout_s is not None:
            self.seen_timeouts.append(timeout_s)
        dt, kind, line, is_stderr = self._script.pop(0)
        self._clock[0] += dt
        if kind == LINE and line is not None:
            return (LINE, TaggedLine(line=line, generation=0, pid=self.pid, is_stderr=is_stderr))
        return (kind, None)


class _FakeClockPool:
    def __init__(self, handle: _FakeClockHandle) -> None:
        self._handle = handle
        self.releases: list[tuple[bool, bool]] = []

    def acquire(self, key: SlotAffinityKey, *_: Any, **__: Any) -> Any:
        return SimpleNamespace(slot_id="s-ladder", handle=self._handle, affinity_key=key, lease_id="l-ladder")

    def release(self, _slot_id: str, *, success: bool = False, cancel: bool = False, **__: Any) -> None:
        self.releases.append((success, cancel))


def _key(chat: str = "c-ladder") -> SlotAffinityKey:
    return SlotAffinityKey("owner", chat, "codex", "gpt-6.1-terra", "medium", "/tmp", "standard")


def test_flag_off_preserves_legacy_deadlines() -> None:
    dl_pool = _resolve_deadlines(StdioPoolConfig(), {}, now=100.0, environ={})
    assert dl_pool.policy is None
    assert dl_pool.first_progress_deadline == pytest.approx(100.0 + DEFAULT_FIRST_PROGRESS_TIMEOUT_S)
    assert dl_pool.idle_deadline == pytest.approx(100.0 + StdioPoolConfig.idle_timeout_s)
    assert dl_pool.safety_deadline == pytest.approx(100.0 + DEFAULT_SAFETY_CAP_S)

    dl_bare = _resolve_deadlines(object(), {}, now=100.0, environ={})
    assert dl_bare.policy is None
    assert dl_bare.first_progress_deadline == pytest.approx(100.0 + DEFAULT_FIRST_PROGRESS_TIMEOUT_S)
    assert dl_bare.idle_deadline == pytest.approx(100.0 + DEFAULT_TURN_IDLE_TIMEOUT_S)
    assert dl_bare.safety_deadline == pytest.approx(100.0 + DEFAULT_SAFETY_CAP_S)


def test_flag_on_uses_timeout_ladder_defaults_not_truncated_by_pool_defaults() -> None:
    dl = _resolve_deadlines(StdioPoolConfig(), {}, now=100.0, environ={FLAG_TIMEOUT_LADDER: "true"})
    assert dl.policy is not None
    assert dl.first_progress_deadline == pytest.approx(700.0)
    assert dl.idle_deadline == pytest.approx(700.0)
    assert dl.safety_deadline == pytest.approx(3700.0)
    assert dl.next_timeout(100.0) == pytest.approx(600.0)


def test_flag_on_survives_long_hidden_reasoning_and_slides_past_600s(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(FLAG_TIMEOUT_LADDER, "true")
    clock = [0.0]
    ev_text = json.dumps({"type": "text", "text": "chunk"})
    ev_reason = json.dumps({"type": "reasoning", "reasoning": "thinking"})
    ev_done = json.dumps({"type": "done", "text": "final"})
    # First chunk arrives after 120s (would have failed 60s legacy first_progress_timeout),
    # then useful chunks arrive every 400s pushing total duration to 1320s (>600s, <3600s).
    handle = _FakeClockHandle(
        [
            (120.0, LINE, ev_reason, False),
            (400.0, LINE, ev_text, False),
            (400.0, LINE, ev_text, False),
            (400.0, LINE, ev_done, False),
        ],
        clock,
    )
    mgr = StdioSessionManager(_FakeClockPool(handle), StreamJsonDriver(), StdioPoolConfig(), clock=lambda: clock[0])  # type: ignore[arg-type]
    res = mgr.execute_turn(_key(), "prompt", lambda: ["fake"], "/tmp")
    assert len(res.chunks) == 4
    assert clock[0] == pytest.approx(1320.0)
    assert handle.seen_timeouts[0] == pytest.approx(600.0)
    assert handle.seen_timeouts[1] == pytest.approx(600.0)


def test_flag_on_stderr_and_empty_frames_do_not_extend_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(FLAG_TIMEOUT_LADDER, "true")
    clock = [0.0]
    # stderr and non-useful JSON lines must NOT shift first_progress_deadline (600s)
    handle = _FakeClockHandle(
        [
            (250.0, LINE, "stderr noise", True),
            (250.0, LINE, json.dumps({"type": "keepalive"}), False),
            (101.0, TIMEOUT, None, False),
        ],
        clock,
    )
    mgr = StdioSessionManager(_FakeClockPool(handle), StreamJsonDriver(), StdioPoolConfig(), clock=lambda: clock[0])  # type: ignore[arg-type]
    with pytest.raises(TurnTimeoutError, match="first_progress_timeout") as exc_info:
        _ = mgr.execute_turn(_key("no-progress"), "prompt", lambda: ["fake"], "/tmp")
    assert exc_info.value.timeout_kind == "first_progress"
    assert handle.seen_timeouts == [pytest.approx(600.0), pytest.approx(350.0), pytest.approx(100.0)]


def test_flag_on_safety_cap_stops_infinite_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(FLAG_TIMEOUT_LADDER, "true")
    clock = [0.0]
    ev = json.dumps({"type": "text", "text": "tick"})
    script: list[tuple[float, str, str | None, bool]] = [(500.0, LINE, ev, False) for _ in range(7)]
    script.append((101.0, TIMEOUT, None, False))
    handle = _FakeClockHandle(script, clock)
    mgr = StdioSessionManager(_FakeClockPool(handle), StreamJsonDriver(), StdioPoolConfig(), clock=lambda: clock[0])  # type: ignore[arg-type]
    with pytest.raises(TurnTimeoutError, match="safety_cap_timeout") as exc_info:
        _ = mgr.execute_turn(_key("cap"), "prompt", lambda: ["fake"], "/tmp")
    assert exc_info.value.timeout_kind == "safety_cap"


def test_flag_on_precedence_ctx_over_env_over_custom_cfg_over_ladder() -> None:
    env_base = {FLAG_TIMEOUT_LADDER: "true"}
    # Custom cfg overrides ladder default when different from class defaults
    custom_cfg = StdioPoolConfig(turn_idle_timeout_s=240.0, turn_total_timeout_s=1200.0)
    dl_cfg = _resolve_deadlines(custom_cfg, {}, now=0.0, environ=env_base)
    assert dl_cfg.idle_s == pytest.approx(240.0)
    assert dl_cfg.safety_deadline == pytest.approx(1200.0)
    assert dl_cfg.first_progress_deadline == pytest.approx(600.0)

    # Explicit env overrides custom cfg
    env_ov = {
        FLAG_TIMEOUT_LADDER: "true",
        "BRIDGE_STDIO_FIRST_PROGRESS_TIMEOUT_S": "420",
        "BRIDGE_STDIO_TURN_IDLE_TIMEOUT_S": "480",
        "BRIDGE_STDIO_SAFETY_CAP_S": "1800",
    }
    dl_env = _resolve_deadlines(custom_cfg, {}, now=0.0, environ=env_ov)
    assert dl_env.first_progress_deadline == pytest.approx(420.0)
    assert dl_env.idle_s == pytest.approx(480.0)
    assert dl_env.safety_deadline == pytest.approx(1800.0)

    # Per-turn ctx overrides env
    dl_ctx = _resolve_deadlines(
        custom_cfg,
        {"first_progress_timeout_s": 90.0, "idle_timeout_s": 120.0, "safety_cap_s": 300.0},
        now=0.0,
        environ=env_ov,
    )
    assert dl_ctx.first_progress_deadline == pytest.approx(90.0)
    assert dl_ctx.idle_s == pytest.approx(120.0)
    assert dl_ctx.safety_deadline == pytest.approx(300.0)


def test_flag_on_invalid_ladder_env_fails_closed() -> None:
    with pytest.raises(ValueError):
        _ = _resolve_deadlines(
            StdioPoolConfig(),
            {},
            now=0.0,
            environ={FLAG_TIMEOUT_LADDER: "true", "BRIDGE_TIMEOUT_FIRST_EVENT_S": "not-a-number"},
        )
    # With flag OFF, invalid ladder env falls back safely to legacy
    dl = _resolve_deadlines(
        StdioPoolConfig(),
        {},
        now=0.0,
        environ={FLAG_TIMEOUT_LADDER: "false", "BRIDGE_TIMEOUT_FIRST_EVENT_S": "not-a-number"},
    )
    assert dl.policy is None
    assert dl.first_progress_deadline == pytest.approx(DEFAULT_FIRST_PROGRESS_TIMEOUT_S)


def test_slot_lease_timeout_classified_503_and_safe_code_redacted() -> None:
    exc = SlotLeaseTimeoutError(f"timed out waiting for a resident process slot Bearer {DUMMY_KEY}")
    resp = build_turn_error(exc, live_sent=0)
    assert (resp.status, resp.error_type, resp.code) == (503, "service_unavailable", "slot_lease_timeout")
    assert DUMMY_KEY not in resp.message
    log_txt = _sanitize_log_text(f"slot_lease_timeout Bearer {DUMMY_KEY}", extra_code="slot_lease_timeout")
    assert "slot_lease_timeout" in log_txt and DUMMY_KEY not in log_txt


def test_codex_v2_resolve_pool_aligns_ephemeral_slots_with_max_concurrent() -> None:
    driver_cfg = {"limits": {"max_concurrent": 10}}
    pool_cfg, _ = resolve_pool_and_driver("codex-app-server-v2", environ={}, driver_config=driver_cfg)
    assert pool_cfg.max_ephemeral_slots == 10
    assert pool_cfg.max_slots == 10

    # Explicit env wins over driver_config
    pool_env, _ = resolve_pool_and_driver(
        "codex-app-server-v2",
        environ={"BRIDGE_STDIO_MAX_EPHEMERAL_SLOTS": "6", "BRIDGE_STDIO_MAX_SLOTS": "8"},
        driver_config=driver_cfg,
    )
    assert pool_env.max_ephemeral_slots == 6
    assert pool_env.max_slots == 8

    # Legacy defaults remain unchanged for StdioPoolConfig.from_env and non-codex protocols
    plain_cfg = StdioPoolConfig.from_env({})
    assert plain_cfg.max_ephemeral_slots == 2
    assert plain_cfg.lease_wait_s == 30.0
    extended_wait = StdioPoolConfig.from_env({"BRIDGE_STDIO_LEASE_WAIT_S": "600"})
    assert extended_wait.lease_wait_s == 600.0


def test_zero_canon_proxy_timeout_follows_ladder_flag() -> None:
    assert _resolve_proxy_timeout_s(None, {}) == pytest.approx(180.0)
    assert _resolve_proxy_timeout_s(None, {FLAG_TIMEOUT_LADDER: "true"}) == pytest.approx(600.0)
    assert _resolve_proxy_timeout_s(
        None, {FLAG_TIMEOUT_LADDER: "true", "HUB_ZERO_CANON_PROXY_TIMEOUT_S": "240"}
    ) == pytest.approx(240.0)
    assert _resolve_proxy_timeout_s(45.0, {FLAG_TIMEOUT_LADDER: "true"}) == pytest.approx(45.0)


def test_serve_json_body_logs_redacted_resident_turn_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import server

    logs: list[str] = []
    sent: list[tuple[int, Any]] = []
    monkeypatch.setattr(server, "_log", logs.append)

    err_resp = build_turn_error(
        SlotLeaseTimeoutError(f"timed out waiting for a resident process slot Bearer {DUMMY_KEY}"),
        live_sent=0,
    )
    resident_err = ResidentTurnError(err_resp)
    lease = SimpleNamespace(failures=[], record_failure=lambda e: lease.failures.append(e))

    handler: Any = object.__new__(server.Handler)
    handler._current_lease = lambda: lease
    handler._send = lambda status, body: sent.append((status, body))

    def _boom(*_args: Any, **_kwargs: Any) -> Any:
        raise resident_err

    handler._dispatch = _boom
    handler._serve_json_body({"model": "gpt-6.1-terra"})

    assert sent and sent[0][0] == 503
    assert lease.failures == [resident_err]
    assert any("json_resident_error status=503 code=slot_lease_timeout" in line for line in logs)
    assert all(DUMMY_KEY not in line for line in logs)


def test_parallel_4_ephemeral_turns_succeed_without_lease_timeout() -> None:
    """L2 integration: 4 concurrent ephemeral turns run concurrently with aligned slots."""
    fake_agent = ROOT / "tests" / "stdio_fake_agent.py"
    pool_cfg, _ = resolve_pool_and_driver(
        "codex-app-server-v2",
        environ={"BRIDGE_STDIO_RESIDENT_ENABLED": "true", "BRIDGE_STDIO_LEASE_WAIT_S": "2.0"},
        driver_config={"limits": {"max_concurrent": 10}},
    )
    pool = ResidentProcessPool(pool_cfg)
    mgr = StdioSessionManager(pool, StreamJsonDriver(), pool_cfg)

    def _argv() -> list[str]:
        return [sys.executable, str(fake_agent), "--protocol", "stream-json", "--delay", "0.02"]

    barrier = threading.Barrier(4)

    def _run_one(idx: int) -> str:
        barrier.wait(timeout=5.0)
        chunks = list(
            mgr.execute_turn_stream(
                _key(f"eph-{idx}"),
                f"msg-{idx}",
                _argv,
                str(ROOT),
                is_ephemeral=True,
            )
        )
        return "".join(c.text for c in chunks)

    try:
        with ThreadPoolExecutor(max_workers=4) as ex:
            results = list(ex.map(_run_one, range(4)))
        assert results == [f"echo: msg-{i}" for i in range(4)]
    finally:
        pool.shutdown(timeout_s=2.0)


def test_record_useful_activity_kind_mapping() -> None:
    dl = _resolve_deadlines(StdioPoolConfig(), {}, now=0.0, environ={FLAG_TIMEOUT_LADDER: "true"})
    dl.record_useful(100.0, ActivityKind.KEEPALIVE)
    assert dl.has_progress is False
    assert dl.next_timeout(100.0) == pytest.approx(500.0)
    dl.record_useful(100.0, ActivityKind.REASONING)
    assert dl.has_progress is True
    assert dl.next_timeout(100.0) == pytest.approx(600.0)
    dl.record_useful(200.0, ActivityKind.TOOL_CALLS)
    assert dl.next_timeout(200.0) == pytest.approx(600.0)


def test_turn_total_300_clamps_first_progress_and_invalid_raises_config_error() -> None:
    from core.runtime_env import ConfigError

    cfg_300 = StdioPoolConfig(turn_total_timeout_s=300.0)
    dl_off = _resolve_deadlines(cfg_300, {}, now=0.0, environ={})
    assert dl_off.safety_deadline == pytest.approx(300.0)
    assert dl_off.first_progress_deadline == pytest.approx(300.0)
    assert dl_off.idle_deadline == pytest.approx(300.0)

    dl_on = _resolve_deadlines(cfg_300, {}, now=0.0, environ={FLAG_TIMEOUT_LADDER: "true"})
    assert dl_on.safety_deadline == pytest.approx(300.0)
    assert dl_on.first_progress_deadline == pytest.approx(300.0)
    assert dl_on.idle_deadline == pytest.approx(300.0)

    for bad_val in (0.0, -5.0, float("nan"), "invalid"):
        with pytest.raises(ConfigError):
            _resolve_deadlines(StdioPoolConfig(), {"turn_total_timeout_s": bad_val}, now=0.0, environ={})


def test_first_progress_601_720_721_boundaries_without_pool_idle_clamp() -> None:
    dl = _resolve_deadlines(StdioPoolConfig(), {}, now=0.0, environ={})
    assert dl.first_progress_deadline == pytest.approx(720.0)
    assert dl.next_timeout(601.0) == pytest.approx(119.0)
    with pytest.raises(TurnTimeoutError) as exc_720:
        dl.next_timeout(720.0)
    assert exc_720.value.code == "first_progress_timeout"
    with pytest.raises(TurnTimeoutError) as exc_721:
        dl.next_timeout(721.0)
    assert exc_721.value.code == "first_progress_timeout"


def test_turn_idle_timeout_priority_over_pool_idle_timeout() -> None:
    cfg = StdioPoolConfig(turn_idle_timeout_s=450.0)
    dl = _resolve_deadlines(cfg, {}, now=0.0, environ={})
    assert dl.idle_s == pytest.approx(450.0)
    assert dl.idle_deadline == pytest.approx(450.0)


def test_explicit_ctx_total_equal_to_pool_default_caps_idle_and_cap_raw_not_truncated() -> None:
    d = StdioPoolConfig.turn_total_timeout_s
    dl = _resolve_deadlines(
        StdioPoolConfig(),
        {"turn_total_timeout_s": d, "turn_idle_timeout_s": 2.0 * d},
        now=0.0,
        environ={},
    )
    assert dl.safety_deadline == pytest.approx(d)
    assert dl.idle_s == pytest.approx(d)

    dl_cap = _resolve_deadlines(StdioPoolConfig(), {"safety_cap_s": 2.0 * d}, now=0.0, environ={})
    assert dl_cap.safety_deadline == pytest.approx(2.0 * d)

    dl_env_idle = _resolve_deadlines(StdioPoolConfig(), {}, now=0.0, environ={"BRIDGE_STDIO_TURN_IDLE_TIMEOUT_S": "515"})
    assert dl_env_idle.idle_s == pytest.approx(515.0)

    dl_ladder_cap = _resolve_deadlines(
        StdioPoolConfig(),
        {"turn_total_timeout_s": 30.0, "safety_cap_s": 300.0},
        now=0.0,
        environ={FLAG_TIMEOUT_LADDER: "true"},
    )
    assert dl_ladder_cap.safety_deadline == pytest.approx(30.0)
