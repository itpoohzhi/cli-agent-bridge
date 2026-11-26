"""Тесты переиспользования сессий Claude CLI (AD-004, THREAT-001..006)."""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest

_REPO_ROOT = str(Path(__file__).resolve().parents[1])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from core.claude_session import (  # noqa: E402
    SESSION_FORBIDDEN_IN_ZERO_CANON,
    SessionConfig,
    SessionMode,
    SessionPlan,
    SessionStore,
    assert_zero_canon_argv_safe,
    build_session_argv,
    is_session_reuse_allowed_profile,
    plan_session,
)


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _store(max_entries: int = 256, ttl_s: float = 3600.0, enabled: bool = True) -> tuple[SessionStore, _Clock]:
    clock = _Clock()
    return SessionStore(SessionConfig(enabled, max_entries, ttl_s), clock=clock), clock


def test_default_config_is_off_and_env_is_clamped() -> None:
    cfg = SessionConfig.from_env({})
    assert (cfg.enabled, cfg.max_entries, cfg.ttl_s) == (False, 256, 3600.0)
    env = {
        "CLAUDE_P_BRIDGE_SESSION_REUSE": "1",
        "CLAUDE_P_BRIDGE_SESSION_MAX_ENTRIES": "0",
        "CLAUDE_P_BRIDGE_SESSION_TTL_S": "-5",
    }
    cfg = SessionConfig.from_env(env)
    assert (cfg.enabled, cfg.max_entries, cfg.ttl_s) == (True, 1, 3600.0)
    ok = SessionConfig.from_env({**env, "CLAUDE_P_BRIDGE_SESSION_MAX_ENTRIES": "3", "CLAUDE_P_BRIDGE_SESSION_TTL_S": "7.5"})
    assert (ok.max_entries, ok.ttl_s) == (3, 7.5)
    junk = SessionConfig.from_env({"CLAUDE_P_BRIDGE_SESSION_MAX_ENTRIES": "x", "CLAUDE_P_BRIDGE_SESSION_TTL_S": "nan"})
    assert (junk.max_entries, junk.ttl_s) == (256, 3600.0)


@pytest.mark.parametrize("value", ["Zero-Canon", "zero-canon", "ZERO-CANON", " zero-canon ", "bogus", "standard2", "\x00"])
def test_zero_canon_and_unknown_profiles_force_stateless(value: str) -> None:
    store, _ = _store()
    headers = {"X-Review-Profile": value, "X-Session-Id": "chat-1"}
    assert is_session_reuse_allowed_profile(headers) is False
    plan, lease = plan_session(store, {}, headers)
    assert lease is None and plan.mode == SessionMode.STATELESS
    assert build_session_argv(plan) == ("--no-session-persistence",)
    assert store.snapshot() == ()


@pytest.mark.parametrize("headers", [None, {}, {"x-review-profile": ""}, {"X-REVIEW-PROFILE": " Standard "}])
def test_absent_or_standard_profile_is_allowed(headers: dict[str, str] | None) -> None:
    assert is_session_reuse_allowed_profile(headers) is True


def test_non_string_or_duplicate_profile_header_fails_closed() -> None:
    assert is_session_reuse_allowed_profile({"X-Review-Profile": 1}) is False  # type: ignore[dict-item]
    assert is_session_reuse_allowed_profile({"X-Review-Profile": "standard", "x-review-profile": "zero-canon"}) is False


def test_create_then_resume_with_session_id_key() -> None:
    store, _ = _store()
    headers = {"X-Session-Id": "chat-1", "X-Review-Profile": "standard"}
    first, lease1 = plan_session(store, {}, headers, append_system_prompt="SYS")
    second, lease2 = plan_session(store, {}, headers)
    assert lease1 is not None and lease2 is not None
    assert first.mode == SessionMode.CREATE and second.mode == SessionMode.RESUME
    assert first.session_id == second.session_id
    assert build_session_argv(first) == ("--session-id", first.session_id, "--append-system-prompt", "SYS")
    assert build_session_argv(second) == ("--resume", first.session_id)
    assert store.snapshot()[0].key_digest == lease1.key_digest != "chat-1"


def test_prompt_cache_key_does_not_open_session_and_disabled_is_stateless() -> None:
    store, _ = _store()
    plan, lease = plan_session(store, {"prompt_cache_key": "shared"}, {})
    assert lease is None and plan.mode == SessionMode.STATELESS
    off, _ = _store(enabled=False)
    plan, lease = plan_session(off, {}, {"X-Session-Id": "chat-1"})
    assert lease is None and build_session_argv(plan) == ("--no-session-persistence",)
    assert build_session_argv(None) == ("--no-session-persistence",)


def test_lru_eviction_drops_least_recently_used_with_lock() -> None:
    store, _ = _store(max_entries=2)
    store.begin("a")
    store.begin("b")
    store.begin("a")
    store.begin("c")
    assert [s.key_digest for s in store.snapshot()] == ["a", "c"]
    assert store.begin("b").mode == SessionMode.CREATE


def test_monotonic_ttl_expiry_with_fake_clock() -> None:
    store, clock = _store(ttl_s=10.0)
    sid = store.begin("a").session_id
    clock.now += 10.0
    assert store.begin("a").session_id == sid
    clock.now += 10.5
    assert store.evict_expired() == 1 and store.snapshot() == ()
    clock.now += 1
    assert store.begin("a").mode == SessionMode.CREATE


def test_invalidate_respects_session_id() -> None:
    store, _ = _store()
    sid = store.begin("a").session_id
    store.invalidate("a", "other")
    assert len(store.snapshot()) == 1
    store.invalidate("a", sid)
    assert store.snapshot() == ()
    store.begin("b")
    store.invalidate("b")
    store.invalidate("missing")
    assert store.snapshot() == ()


def test_snapshot_is_immutable_and_per_key_locks_are_isolated() -> None:
    store, clock = _store()
    la, lb, la2 = store.begin("a"), store.begin("b"), store.begin("a")
    snap = store.snapshot()
    store.invalidate("a")
    assert isinstance(snap, tuple) and len(snap) == 2
    with pytest.raises(AttributeError):
        snap[0].session_id = "x"  # type: ignore[misc]
    assert la.lock is la2.lock and la.lock is not lb.lock
    assert la.lock.acquire(blocking=False)
    try:
        assert lb.lock.acquire(blocking=False)
        lb.lock.release()
        assert not la2.lock.acquire(blocking=False)
    finally:
        la.lock.release()
    assert isinstance(la.lock, type(threading.Lock())) and clock.now == 1000.0


@pytest.mark.parametrize("flag", sorted(SESSION_FORBIDDEN_IN_ZERO_CANON))
def test_zero_canon_guard_rejects_each_forbidden_flag(flag: str) -> None:
    argv = ["claude", "-p", "--no-session-persistence", flag]
    with pytest.raises(ValueError, match="zero_canon_session_flag_forbidden"):
        assert_zero_canon_argv_safe(argv, zero_canon=True)
    assert_zero_canon_argv_safe(argv, zero_canon=False)


def test_zero_canon_guard_requires_no_persistence_and_passes_safe_argv() -> None:
    with pytest.raises(ValueError, match="zero_canon_session_flag_forbidden"):
        assert_zero_canon_argv_safe(["claude", "-p"], zero_canon=True)
    assert_zero_canon_argv_safe(["claude", *build_session_argv(SessionPlan())], zero_canon=True)
