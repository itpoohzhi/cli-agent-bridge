"""Тесты переиспользования сессий Claude CLI (AD-004, THREAT-001..006, RW-001..RW-003)."""

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


def test_default_config_is_off_and_env_is_clamped_and_handles_overflow() -> None:
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
    huge = SessionConfig.from_env({"CLAUDE_P_BRIDGE_SESSION_MAX_ENTRIES": "9" * 450, "CLAUDE_P_BRIDGE_SESSION_TTL_S": "nan"})
    assert (huge.max_entries, huge.ttl_s) == (256, 3600.0)
    junk = SessionConfig.from_env({"CLAUDE_P_BRIDGE_SESSION_MAX_ENTRIES": "x", "CLAUDE_P_BRIDGE_SESSION_TTL_S": "0"})
    assert (junk.max_entries, junk.ttl_s) == (256, 3600.0)


@pytest.mark.parametrize("value", ["Zero-Canon", "zero-canon", "ZERO-CANON", " zero-canon ", "bogus", "standard2", "\x00"])
def test_zero_canon_and_unknown_profiles_force_stateless(value: str) -> None:
    store, _ = _store()
    headers = {"X-Review-Profile": value, "X-Session-Id": "chat-1"}
    assert is_session_reuse_allowed_profile(headers) is False
    with plan_session(store, {}, headers) as (plan, lease):
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
    with plan_session(store, {}, headers, append_system_prompt="SYS") as (first, lease1):
        assert lease1 is not None and first.mode == SessionMode.CREATE
        assert build_session_argv(first) == ("--session-id", first.session_id, "--append-system-prompt", "SYS")
        first_digest = lease1.key_digest
    with plan_session(store, {}, headers) as (second, lease2):
        assert lease2 is not None and second.mode == SessionMode.RESUME
        assert first.session_id == second.session_id
        assert build_session_argv(second) == ("--resume", first.session_id)
    assert store.snapshot()[0].key_digest == first_digest != "chat-1"


def test_prompt_cache_key_does_not_open_session_and_disabled_is_stateless() -> None:
    store, _ = _store()
    with plan_session(store, {"prompt_cache_key": "shared"}, {}) as (plan, lease):
        assert lease is None and plan.mode == SessionMode.STATELESS
    off, _ = _store(enabled=False)
    with plan_session(off, {}, {"X-Session-Id": "chat-1"}) as (plan, lease):
        assert lease is None and build_session_argv(plan) == ("--no-session-persistence",)
    assert build_session_argv(None) == ("--no-session-persistence",)


def test_lru_eviction_drops_least_recently_used_and_gc_gate() -> None:
    store, _ = _store(max_entries=2)
    with store.lease("a"):
        pass
    with store.lease("b"):
        pass
    with store.lease("a"):
        pass
    with store.lease("c"):
        pass
    assert [s.key_digest for s in store.snapshot()] == ["a", "c"]
    assert "b" not in store._gates  # noqa: SLF001
    with store.lease("b") as lb:
        assert lb.mode == SessionMode.CREATE


def test_per_key_gate_survives_lru_eviction() -> None:
    """RW-001 (F-001/F-017): активный lock не уничтожается при LRU-эвикции."""
    store, _ = _store(max_entries=2)
    a_entered, a_release, b_done = threading.Event(), threading.Event(), threading.Event()
    events: list[tuple[str, int]] = []

    def worker_a() -> None:
        with store.lease("k") as la:
            events.append(("a_enter", id(la.lock)))
            a_entered.set()
            assert a_release.wait(timeout=5.0)
            events.append(("a_exit", id(la.lock)))

    def worker_b() -> None:
        with store.lease("k") as lb:
            events.append(("b_enter", id(lb.lock)))
        b_done.set()

    t_a = threading.Thread(target=worker_a)
    t_a.start()
    assert a_entered.wait(timeout=5.0)
    with store.lease("x"):
        pass
    with store.lease("y"):
        pass
    t_b = threading.Thread(target=worker_b)
    t_b.start()
    assert not b_done.wait(timeout=0.05)
    a_release.set()
    t_a.join(timeout=5.0)
    t_b.join(timeout=5.0)
    assert [e[0] for e in events] == ["a_enter", "a_exit", "b_enter"]
    assert events[0][1] == events[2][1]


def test_per_key_gate_serializes_create_before_resume() -> None:
    """RW-001 (F-013): поток B ждёт lock до завершения CREATE потока A и получает RESUME."""
    store, _ = _store(max_entries=8)
    entered, release = threading.Event(), threading.Event()
    modes: list[tuple[str, SessionMode, str]] = []

    def wa() -> None:
        with store.lease("same") as la:
            modes.append(("a", la.mode, la.session_id))
            entered.set()
            assert release.wait(timeout=5.0)

    def wb() -> None:
        with store.lease("same") as lb:
            modes.append(("b", lb.mode, lb.session_id))

    ta = threading.Thread(target=wa)
    ta.start()
    assert entered.wait(timeout=5.0)
    tb = threading.Thread(target=wb)
    tb.start()
    release.set()
    ta.join(timeout=5.0)
    tb.join(timeout=5.0)
    assert modes[0][1] == SessionMode.CREATE and modes[1][1] == SessionMode.RESUME
    assert modes[0][2] == modes[1][2]


def test_monotonic_ttl_head_eviction_and_active_renewal() -> None:
    """RW-002 (F-014/F-019): O(k) уборка с головы OrderedDict и продление touched активной записи."""
    store, clock = _store(ttl_s=10.0)
    with store.lease("old") as l1:
        sid = l1.session_id
    clock.now += 5.0
    with store.lease("fresh"):
        pass
    clock.now += 6.0  # old age=11 > 10, fresh age=6 <= 10
    assert store.evict_expired() == 1
    assert [s.key_digest for s in store.snapshot()] == ["fresh"]
    # Активная запись переживает evict_expired, даже если её ход длится дольше TTL
    with store.lease("long"):
        clock.now += 25.0
        assert store.evict_expired() == 1  # вычищен только fresh, не активный long
        assert [s.key_digest for s in store.snapshot()] == ["long"]
    with store.lease("old") as l2:
        assert l2.mode == SessionMode.CREATE and l2.session_id != sid


def test_lease_after_ttl_expiry_creates_fresh_session_for_same_key() -> None:
    """RW-001 (C2 F-001): повторный lease по тому же ключу после TTL открывает CREATE без явного evict_expired."""
    store, clock = _store(ttl_s=10.0)
    with store.lease("solo") as first:
        sid1 = first.session_id
        assert first.mode == SessionMode.CREATE
    clock.now += 10.0  # ровно граница TTL -> ещё валидна
    with store.lease("solo") as second:
        assert second.mode == SessionMode.RESUME and second.session_id == sid1
    clock.now += 10.5  # просрочена, других ключей и evict_expired() не было!
    with store.lease("solo") as third:
        assert third.mode == SessionMode.CREATE and third.session_id != sid1


def test_invalidate_respects_session_id_and_preserves_active_gate() -> None:
    store, _ = _store()
    with store.lease("a") as la:
        sid = la.session_id
        store.invalidate("a", "other")
        assert len(store.snapshot()) == 1
        store.invalidate("a", sid)
        assert store.snapshot() == ()
        assert "a" in store._gates  # noqa: SLF001 — активный gate не удалён!
    assert "a" not in store._gates  # noqa: SLF001 — после выхода gate очищен
    with store.lease("b"):
        pass
    store.invalidate("b")
    store.invalidate("missing")
    assert store.snapshot() == () and "b" not in store._gates  # noqa: SLF001


def test_snapshot_is_immutable_and_per_key_locks_are_isolated() -> None:
    store, clock = _store()
    with store.lease("a") as la:
        with store.lease("b") as lb:
            assert la.lock is not lb.lock
            snap = store.snapshot()
            assert isinstance(snap, tuple) and len(snap) == 2
            with pytest.raises(AttributeError):
                snap[0].session_id = "x"  # type: ignore[misc]
            assert isinstance(la.lock, type(threading.Lock())) and clock.now == 1000.0


@pytest.mark.parametrize(
    "bad_token",
    [
        *sorted(SESSION_FORBIDDEN_IN_ZERO_CANON),
        "--resume=abc-123",
        "--session-id=abc-123",
        "--append-system-prompt=injected",
        "--continue=true",
        "--fork-session",
        "--fork-session=1",
        "--res",
        "--sess=123",
        "--cont",
        "--app=x",
        "--fork",
        "-r123",
        "-r=123",
        "-c1",
        "-c=1",
        "-pr",
        "-pc",
    ],
)
def test_zero_canon_guard_rejects_exact_equals_prefix_and_short_forms(bad_token: str) -> None:
    """RW-003 (F-018): нормализация --flag=value, префиксов и слитных коротких флагов."""
    argv = ["claude", "-p", "--no-session-persistence", bad_token]
    with pytest.raises(ValueError, match="zero_canon_session_flag_forbidden"):
        assert_zero_canon_argv_safe(argv, zero_canon=True)
    assert_zero_canon_argv_safe(argv, zero_canon=False)


def test_zero_canon_guard_requires_exact_no_persistence_and_allows_setting_sources() -> None:
    with pytest.raises(ValueError, match="zero_canon_session_flag_forbidden"):
        assert_zero_canon_argv_safe(["claude", "-p"], zero_canon=True)
    with pytest.raises(ValueError, match="zero_canon_session_flag_forbidden"):
        assert_zero_canon_argv_safe(["claude", "-p", "--no-session-persistence=false"], zero_canon=True)
    safe = ["claude", "-p", "--setting-sources", "user", *build_session_argv(SessionPlan())]
    assert_zero_canon_argv_safe(safe, zero_canon=True)
