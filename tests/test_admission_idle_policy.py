"""Чистые L1-оракулы политики phase-idle admission и TTL-пула (0 sockets/subprocess/sleep)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

pytestmark = pytest.mark.strict_leak_check

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters.passthrough_pool import PassthroughConnectionPool  # noqa: E402
from core import admission_idle_policy as P  # noqa: E402
from core import bridge_io_config, drain_response, http_accept  # noqa: E402

# fmt: off
# Плотные тест-таблицы: форматтер не должен раздувать файл сверх лимита M-MOD-I1.


def test_config_defaults_fail_closed() -> None:
    cfg = P.AdmissionIdleConfig()
    assert not cfg.phase_idle_timeout_enabled and not cfg.active_ttl_sweep_enabled
    assert not cfg.admission_telemetry_enabled and not cfg.claude_stderr_log_enabled
    assert (cfg.phase_idle_timeout_s, cfg.active_socket_timeout_s, cfg.claude_stderr_max_chars) == (30.0, 3600.0, 240)


def test_admission_budget_limit_and_config_properties() -> None:
    budget = bridge_io_config.AdmissionBudget()
    assert (budget.limit, budget.config.admission_limit) == (128, 128)
    assert (budget.config.ui_reserve, budget.config.header_headroom) == (2, 2)


@pytest.mark.parametrize("phase", ["idle", "active"])
def test_resolve_timeout_disabled_preserves_legacy(phase: str) -> None:
    cfg = P.AdmissionIdleConfig()
    assert P.resolve_socket_timeout_for_phase(phase, cfg) == 3600.0
    assert P.resolve_socket_timeout_for_phase(phase, cfg, 4.5) == 4.5


def test_resolve_timeout_enabled_idle_and_active() -> None:
    cfg = P.AdmissionIdleConfig(phase_idle_timeout_enabled=True, phase_idle_timeout_s=0.05)
    assert P.resolve_socket_timeout_for_phase("idle", cfg) == 0.05
    assert P.resolve_socket_timeout_for_phase("idle", cfg, 0.01) == 0.01
    assert P.resolve_socket_timeout_for_phase("idle", cfg, 9.0) == 0.05
    assert P.resolve_socket_timeout_for_phase("active", cfg) == 3600.0
    assert P.resolve_socket_timeout_for_phase("active", cfg, 7.0) == 7.0


def test_resolve_timeout_unknown_phase_raises() -> None:
    with pytest.raises(ValueError):
        P.resolve_socket_timeout_for_phase("bogus", P.AdmissionIdleConfig())


@pytest.mark.parametrize("raw", ["0", "-1", "nan", "inf", "abc", "99999"])
def test_phase_idle_timeout_invalid_falls_back(raw: str, tmp_path: Path) -> None:
    env = {"BRIDGE_HTTP_PHASE_IDLE_TIMEOUT_S": raw}
    cfg = http_accept.load_admission_idle_config(env=env, config_path=tmp_path / "a.json")
    assert cfg.phase_idle_timeout_s == 30.0


def test_kill_switch_veto_and_broken_config(tmp_path: Path) -> None:
    flag = "BRIDGE_HTTP_IDLE_ADMISSION_TIMEOUT_ENABLED"
    good = tmp_path / "c.json"
    good.write_text('{"%s": false}' % flag, encoding="utf-8")
    assert not http_accept.load_admission_idle_config({flag: "1"}, good).phase_idle_timeout_enabled
    broken = tmp_path / "b.json"
    broken.write_text("{not json", encoding="utf-8")
    assert not http_accept.load_admission_idle_config({flag: "1"}, broken).phase_idle_timeout_enabled
    assert not http_accept.load_admission_idle_config({}, tmp_path / "n.json").phase_idle_timeout_enabled


def test_legacy_knob_warning_matrix() -> None:
    for raw, none in [("", True), ("128", True), ("1024", False), ("garbage", False)]:
        env = {"BRIDGE_MAX_HTTP_CONNECTIONS": raw} if raw else {}
        assert (P.check_legacy_max_http_connections_warning(env, 128) is None) is none
    env = {"BRIDGE_MAX_HTTP_CONNECTIONS": "Bearer sk-secret123\r\nforged=1"}
    line = P.check_legacy_max_http_connections_warning(env, 128)
    assert line is not None and "\n" not in line and "\r" not in line
    assert "sk-secret123" not in line and "[REDACTED]" in line and "effective_limit=128" in line


def test_sanitize_stderr_tail_matrix() -> None:
    assert P.sanitize_stderr_tail("") == "" and P.sanitize_stderr_tail("line1\nline2") == "line1 line2" and P.sanitize_stderr_tail("monkey=banana") == "monkey=banana" and P.sanitize_stderr_tail("disk-1234") == "disk-1234" and P.sanitize_stderr_tail("api_key=abc") == P.sanitize_stderr_tail("ghp_abcdef123456") == "[REDACTED]" and P.sanitize_stderr_tail("x" * 500, 40) == "..." + "x" * 40


@pytest.mark.parametrize("raw,bad", [
    ("Authorization: Bearer sk-abc12345", "sk-abc12345"), ("Bearer tok123456", "tok123456"), ("x sk-abc12345 y", "sk-abc12345"), ("OPENAI_API_KEY=xyz", "xyz"), ("BRIDGE_KEY=supersecret OPENAI_API_KEY=xyz", "supersecret"), ("AWS_SECRET_ACCESS_KEY=foo", "foo"), ("\x1b[31merr sk-abc12345\x1b[0m", "\x1b"), ("a\r\nb\x00c sk-abc12345", "\x00"), ("\x1b]0;title\x07ok sk-abc12345", "title"),
    ("sk-\x1b[31mABCDEF", "ABCDEF"), ("sk-\x00ABCDEF", "ABCDEF"), ("\x1b(BAuthorization: Bearer tok123456", "tok123456"), ("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.SigPartSecret999", "SigPartSecret999"), ('{"api_key": "jsonsecret999"}', "jsonsecret999"), ("Cookie: sid=cookiesecret999", "cookiesecret999"), ("Authorization: Bearer sk-abc12345\r\nBRIDGE_KEY=topsecret \x1b[31mERR\x1b[0m\x00", "topsecret"), ("err\x1b[31msk-abc12345\x1b[0m", "sk-abc12345"), ("err\x1b[31mBearer tok123456\x1b[0m", "tok123456"),
    ("err\x00sk-abc12345", "sk-abc12345"), ("err\x1b[31msk-\x1b[0mABCDEF", "ABCDEF"), ("sk-\tabc123456", "abc123456"), ("sk-abc\n1234567890abcdef", "1234567890abcdef"), ("eyJhbGciOiJIUzI1NiJ9.\nSigPartSecret999", "SigPartSecret999"), ("sk-\x1b[38:2:255:0:0mABCDEF", "ABCDEF"), ("Cookie: a=1; sid=cookiesecret999", "cookiesecret999"), ('{"authorization": "rawsecret999"}', "rawsecret999"),
    ("Cookie: a=1;\x1b[31msid=cookiesecret999", "cookiesecret999"), ("Authorization: Bearer tok\x1b[31m123456", "123456"), ("Authorization: Bearer sk-\x1b[31mABCDEF123456", "ABCDEF123456"), ("Authorization: Bearer sk-\tabc123456", "abc123456"), ("Bearer\ntok123456", "tok123456"), ("api_key=\nrawsecret999", "rawsecret999"), ("api_key=abc\x1b[31mDEF", "DEF"),
    ("SECRETKEY=rawsecret999", "rawsecret999"), ("sk-abc12345\r\nBRIDGE_KEY=topsecret", "topsecret"), ("sk-abc12345\nCookie: sid=cookiesecret999", "cookiesecret999"), ("\x1b[31msk-abc12345\x1b[0mOPENAI_API_KEY=supersecret", "supersecret"), ('{"api_key": "\x1b[33mjsonsecret999\x1b[0m"}', "jsonsecret999"), ('OPENAI_API_KEY="\x1b[31msupersecret\x1b[0m"', "supersecret"), ("err\x1b[31mBearer tok\x1b[0m123456", "123456")])
def test_sanitize_stderr_tail_negative(raw: str, bad: str) -> None:
    out = P.sanitize_stderr_tail(raw)
    assert bad not in out and "[REDACTED]" in out and "sk-abc12345" not in out and not any(c in out for c in "\r\n\x1b\x00")


def test_summarize_snapshot_empty_clamp_mixed() -> None:
    snap = P.summarize_admission_snapshot({}, 10.0, 128, 3)
    assert (snap["active"], snap["idle"], snap["total"], snap["limit"]) == (0, 0, 0, 128)
    assert snap["max_idle_age_s"] == 0.0 and snap["overloaded_rejects"] == 3
    clamped = P.summarize_admission_snapshot({object(): (False, 20.0)}, 10.0, 128, 0)
    assert clamped["max_idle_age_s"] == 0.0
    conns = {object(): (True, 5.0), object(): (False, 2.0), object(): (False, 8.0)}
    mixed = P.summarize_admission_snapshot(conns, 10.0, 128, 1)
    assert (mixed["active"], mixed["idle"], mixed["total"]) == (1, 2, 3)
    assert mixed["max_active_age_s"] == 5.0 and mixed["max_idle_age_s"] == 8.0


def test_resolve_drain_actor_default_and_sanitized() -> None:
    base = P.resolve_drain_actor({}, 11, 22, 33)
    assert base["actor"] == "signal" and (base["pid"], base["ppid"], base["pgid"]) == (11, 22, 33)
    secret = P.resolve_drain_actor({"BRIDGE_RESTART_ACTOR": "Bearer sk-secret123\n"}, 1, 2, 3)
    assert secret["actor"] == "[REDACTED]" and "sk-secret123" not in str(secret)


def test_drain_response_allows_actor_ppid() -> None:
    assert "actor" in drain_response.ALLOWED_EVENT_FIELDS
    assert "ppid" in drain_response.ALLOWED_EVENT_FIELDS
    fields = {"actor": "signal", "pid": 1, "ppid": 2, "pgid": 3}
    line = drain_response.format_drain_event("drain_started", fields)
    assert "actor=signal" in line and "ppid=2" in line


_DONE_OUT = {"rc": 0, "state": "ok", "tool_calls": [1, 2], "text": "hi"}
_DONE_LEGACY = ("done model=m effort=high rc=0 state=ok tools=2 out_bytes=2 "
                "wall_s=2.0 client=1.2.3.4:5 ua=x")


def test_format_claude_done_legacy_exact() -> None:
    line = P.format_claude_done_fields(("m", "high", "client=1.2.3.4:5 ua=x"), _DONE_OUT, 2.0)
    assert line == _DONE_LEGACY


def test_format_claude_done_no_stderr_when_not_applicable() -> None:
    for out in ({"rc": 0, "state": "ok", "err": "boom"}, {"rc": 1, "state": "e", "err": ""}):
        line = P.format_claude_done_fields(("m", "high", "tag"), out, 1.0, P.AdmissionIdleConfig(claude_stderr_log_enabled=True))
        assert "stderr_tail" not in line


def test_format_claude_done_redacted_stderr_on_fail() -> None:
    out = {"rc": 1, "state": "e", "err": "Bearer sk-secret123\napi_key=abc"}
    line = P.format_claude_done_fields(("m", "high", "tag"), out, 1.0, P.AdmissionIdleConfig(claude_stderr_log_enabled=True))
    assert "stderr_tail=[REDACTED] [REDACTED]" in line
    assert "sk-secret123" not in line and "\n" not in line and "\r" not in line


class _FakeServer:
    def admission_snapshot(self) -> dict:
        return {"active": 1, "idle": 0, "total": 1, "limit": 128}


def test_attach_admission_telemetry_flag_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"x": 1}
    assert http_accept.attach_admission_telemetry(payload, _FakeServer()) is payload
    monkeypatch.setenv("BRIDGE_ADMISSION_TELEMETRY_ENABLED", "1")
    out = http_accept.attach_admission_telemetry(payload, _FakeServer())
    assert out["admission"]["total"] == 1 and out["x"] == 1 and "admission" not in payload
    assert http_accept.attach_admission_telemetry(payload, object()) is payload


class _FakeClock:
    def __init__(self) -> None: self.t = 0.0
    def __call__(self) -> float: return self.t
    def advance(self, dt: float) -> None: self.t += dt


class _FakeConn:
    def __init__(self) -> None:
        self.sock, self.closed, self.timeout = SimpleNamespace(settimeout=lambda t: None), 0, None
    def connect(self) -> None: pass
    def close(self) -> None: self.closed += 1


def _pool(clock: _FakeClock, **kw) -> PassthroughConnectionPool:
    pool = PassthroughConnectionPool(
        max_keepalive=kw.pop("max_keepalive", 4), keepalive_expiry_s=kw.pop("keepalive_expiry_s", 1.0),
        select_fn=lambda r, w, x, timeout=0: ([], [], []),
        monotonic_fn=clock, connection_fn=lambda h, p, t: _FakeConn())
    pool.set_active_ttl_sweep(kw.pop("active_ttl_sweep", None))
    return pool


@pytest.fixture
def sweep_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_PASSTHROUGH_ACTIVE_TTL_SWEEP_ENABLED", "1")


def test_passthrough_pool_sweep_empty_alive_and_after_close_all(sweep_env) -> None:
    pool = _pool(_FakeClock(), active_ttl_sweep=True)
    assert pool.sweep_expired() == 0
    pool.release_connection("a", 1, _FakeConn())
    assert pool.sweep_expired() == 0 and pool.idle_count == 1
    pool.close_all()
    assert pool.sweep_expired() == 0 and pool.idle_count == 0


def test_passthrough_pool_sweep_expired_other_host() -> None:
    clock = _FakeClock()
    pool = _pool(clock, active_ttl_sweep=False)
    a, b = _FakeConn(), _FakeConn()
    pool.release_connection("a", 1, a)
    clock.advance(2.0)
    pool.release_connection("b", 2, b)
    assert pool.sweep_expired() == 1 and a.closed == 1 and b.closed == 0
    assert pool.idle_count == 1 and pool.stats()["evicted_expired"] == 1


def test_passthrough_pool_sweep_closes_outside_lock() -> None:
    clock = _FakeClock()
    pool = _pool(clock, active_ttl_sweep=False)
    conn = _FakeConn()
    pool.release_connection("a", 1, conn)
    clock.advance(2.0)
    seen: list[bool] = []
    orig = conn.close
    conn.close = Mock(side_effect=lambda: (seen.append(pool._lock.locked()), orig()))
    assert pool.sweep_expired() == 1 and seen == [False]


def test_passthrough_pool_release_and_get_trigger_sweep(sweep_env) -> None:
    clock = _FakeClock()
    pool = _pool(clock, active_ttl_sweep=True)
    old = _FakeConn()
    pool.release_connection("a", 1, old)
    clock.advance(2.0)
    pool.release_connection("b", 2, _FakeConn())
    assert old.closed == 1 and pool.idle_count == 1
    clock.advance(2.0)
    conn, _ = pool.get_connection("c", 3, 5.0, fresh=True)
    assert getattr(conn, "closed") == 0 and pool.idle_count == 0


@pytest.mark.parametrize("active", [False, True])
def test_pool_disabled_and_env_off_overrides_active_true(active: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    clock = _FakeClock()
    pool = _pool(clock, active_ttl_sweep=active)
    monkeypatch.setenv("BRIDGE_PASSTHROUGH_ACTIVE_TTL_SWEEP_ENABLED", "0")
    old = _FakeConn()
    pool.release_connection("a", 1, old)
    clock.advance(2.0)
    pool.release_connection("b", 2, _FakeConn())
    _ = pool.get_connection("c", 3, 5.0, fresh=True)
    assert pool._sweep_enabled() is False and old.closed == 0 and pool.idle_count == 2


def test_pool_fifo_head_batch_and_oserror() -> None:
    clock = _FakeClock()
    pool = _pool(clock, max_keepalive=200, active_ttl_sweep=False)
    olds = [_FakeConn() for _ in range(5)]
    _ = [pool.release_connection(f"o{i}", 1, c) for i, c in enumerate(olds)]
    clock.advance(2.0)
    _ = [pool.release_connection(f"l{i}", 1, _FakeConn()) for i in range(120)]
    olds[0].close = Mock(side_effect=OSError("close"))
    assert (pool.sweep_expired(max_items=32), pool.sweep_expired(32)) == (5, 0)
    assert [c.closed for c in olds[1:]] == [1] * 4
    assert (len(pool._fifo), pool.idle_count, pool.stats()["evicted_expired"]) == (120, 120, 5)
    _ = pool.get_connection("l0", 1, 5.0)
    clock.advance(2.0)
    assert (pool.sweep_expired(max_items=3), pool.idle_count, len(pool._fifo)) == (3, 116, 116)


def test_pool_fifo_compaction() -> None:
    clock = _FakeClock()
    c_pool = _pool(clock, max_keepalive=1, active_ttl_sweep=False)
    for _ in range(34):
        c_pool.release_connection("h", 1, _FakeConn())
        _ = c_pool.get_connection("h", 1, 5.0)
    last = _FakeConn()
    assert len(c_pool._fifo) == 34
    c_pool.release_connection("h", 1, last)
    clock.advance(2.0)
    assert (len(c_pool._fifo), c_pool.sweep_expired(), last.closed) == (1, 1, 1)


def test_passthrough_pool_none_reads_fresh_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = _FakeClock()
    pool = _pool(clock)
    old = _FakeConn()
    pool.release_connection("a", 1, old)
    clock.advance(2.0)
    monkeypatch.setenv("BRIDGE_PASSTHROUGH_ACTIVE_TTL_SWEEP_ENABLED", "1")
    pool.release_connection("b", 2, _FakeConn())
    assert old.closed == 1 and pool.idle_count == 1


def test_passthrough_pool_lifo_reuse_preserved() -> None:
    clock = _FakeClock()
    pool = _pool(clock, active_ttl_sweep=False)
    a, b = _FakeConn(), _FakeConn()
    pool.release_connection("h", 1, a)
    pool.release_connection("h", 1, b)
    assert pool.get_connection("h", 1, 5.0) == (b, True)
    assert pool.get_connection("h", 1, 5.0) == (a, True)
