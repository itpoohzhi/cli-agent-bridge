"""W3-A: adversarial F-FSM / T-ISO матрица жизненного цикла беседы agy (VER-024).

F-FSM-I1: таблица state x event тотальна. F-FSM-I2: нет мёртвых состояний.
F-FSM-I3: любое событие, выводящее беседу из ACTIVE, даёт ROTATE/полный prompt.
T-ISO-I1..I4: tmp HOME, 0 живых портов, нет утечки глобального состояния,
детерминированные часы (время передаётся явно, wall clock запрещён).
"""

from __future__ import annotations

import ast
import itertools
import os
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Final, NoReturn

import pytest

ROOT: Final = Path(__file__).resolve().parents[1]
RUNTIME: Final = ROOT / "bridges" / "agy-bridge" / "agy_runtime"
AGY_BRIDGE: Final = ROOT / "bridges" / "agy-bridge"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(AGY_BRIDGE) not in sys.path:
    sys.path.append(str(AGY_BRIDGE))

from agy_runtime import loss_contract_config as lcc  # noqa: E402
from agy_runtime.conversation_lifecycle import (  # noqa: E402
    ConversationLifecycle,
    LifecycleEvent,
    LifecyclePolicy,
    LifecycleState,
    is_conversation_expired,
)
from agy_runtime.persistent_worker_config import PersistentWorkerSettings  # noqa: E402
from agy_runtime.worker_rotation_policy import (  # noqa: E402
    ReuseProbe,
    SlotBinding,
    SlotReuseVerdict,
    decide_slot_reuse,
)
from core.hot_session_policy import PolicyConfig  # noqa: E402

_E: Final = LifecycleEvent
_S: Final = LifecycleState
_POLICY: Final = LifecyclePolicy(max_turns=3, idle_ttl_s=10.0, max_ttl_s=100.0)
_COLD_ENTERING: Final = (
    (_E.MAX_TURNS, _S.EXPIRED),
    (_E.IDLE_TTL, _S.EXPIRED),
    (_E.MAX_TTL, _S.EXPIRED),
    (_E.TOMBSTONE, _S.TOMBSTONED),
    (_E.CONTINUITY_MISS, _S.EXPIRED),
    (_E.RESTART, _S.NONE),
    (_E.TEXT_ONLY_FALLBACK, _S.NONE),
)
_FORBIDDEN_IMPORTS: Final = {"os", "time", "threading", "socket", "subprocess"}
_MUTABLE_CALLS: Final = {"dict", "list", "set", "defaultdict", "deque"}


def _forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("forbidden side effect in isolated lifecycle test")


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """T-ISO-I1/I2: tmp HOME, чистый env, любые bind/connect запрещены."""
    for key in tuple(os.environ):
        if key.startswith(("AGY_BRIDGE_", "BRIDGE_HOT_")):
            monkeypatch.delenv(key)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    for name in ("bind", "connect", "connect_ex", "listen"):
        monkeypatch.setattr(socket.socket, name, _forbidden)
    return home


def _probe_for(state: LifecycleState) -> tuple[ReuseProbe, SlotBinding]:
    """Факты запроса для живого слота: только ACTIVE несёт доказанный cid+якорь."""
    if state is _S.ACTIVE:
        return ReuseProbe(reused=True, run_cid="cid-a", resume_base_idx=7), SlotBinding(5, "cid-a")
    return ReuseProbe(reused=True, run_cid="", resume_base_idx=0), SlotBinding(5, "cid-a")


def test_fsm_table_is_total_and_closed() -> None:
    """F-FSM-I1: все 4x9 пар определены и замкнуты на LifecycleState."""
    pairs = list(itertools.product(_S, _E))
    assert len(pairs) == len(_S) * len(_E) == 36
    for state, event in pairs:
        assert isinstance(ConversationLifecycle.transition(state, event), _S)


def test_fsm_has_no_dead_states() -> None:
    """F-FSM-I2: каждое состояние достижимо из NONE и ведёт обратно в ACTIVE."""
    reachable, frontier = {_S.NONE}, [_S.NONE]
    while frontier:
        current = frontier.pop()
        for event in _E:
            nxt = ConversationLifecycle.transition(current, event)
            if nxt not in reachable:
                reachable.add(nxt)
                frontier.append(nxt)
    assert reachable == set(_S)
    for state in _S:
        assert ConversationLifecycle.transition(state, _E.COLD_REQUEST) is _S.ACTIVE


def test_fsm_non_active_states_are_not_resurrected_by_commit_or_expiry() -> None:
    """Адверсариально: delta/expiry/miss не оживляют EXPIRED/TOMBSTONED/NONE."""
    inert = (_E.DELTA_COMMITTED, _E.MAX_TURNS, _E.IDLE_TTL, _E.MAX_TTL, _E.CONTINUITY_MISS)
    for state in (_S.NONE, _S.EXPIRED, _S.TOMBSTONED):
        for event in inert:
            assert ConversationLifecycle.transition(state, event) is state
    assert ConversationLifecycle.transition(_S.ACTIVE, _E.DELTA_COMMITTED) is _S.ACTIVE


@pytest.mark.parametrize(("event", "expected"), _COLD_ENTERING)
def test_every_cold_entering_event_forces_rotate_or_full_prompt(
    event: LifecycleEvent, expected: LifecycleState
) -> None:
    """F-FSM-I3: после события живой слот не переиспользуется, re-entry — COLD_REQUEST."""
    live_probe, live_binding = _probe_for(_S.ACTIVE)
    assert decide_slot_reuse(live_probe, live_binding) is SlotReuseVerdict.REUSE
    state = ConversationLifecycle.transition(_S.ACTIVE, event)
    assert state is expected
    probe, binding = _probe_for(state)
    verdict = decide_slot_reuse(probe, binding)
    assert verdict.evicts_slot and verdict is not SlotReuseVerdict.REUSE
    assert ConversationLifecycle.transition(state, _E.COLD_REQUEST) is _S.ACTIVE


def test_cold_entering_events_cover_every_non_commit_event() -> None:
    covered = {event for event, _ in _COLD_ENTERING} | {_E.COLD_REQUEST, _E.DELTA_COMMITTED}
    assert covered == set(_E)


def test_max_turns_boundary_is_deterministic() -> None:
    assert not is_conversation_expired(0.0, 0.0, _POLICY.max_turns - 1, 1.0, _POLICY)
    assert is_conversation_expired(0.0, 0.0, _POLICY.max_turns, 1.0, _POLICY)


def test_idle_and_max_ttl_use_strict_greater_than_with_explicit_now() -> None:
    assert not is_conversation_expired(0.0, 0.0, 1, _POLICY.idle_ttl_s, _POLICY)
    assert is_conversation_expired(0.0, 0.0, 1, _POLICY.idle_ttl_s + 0.001, _POLICY)
    # last_used свежий: idle не срабатывает, но max TTL от created срабатывает.
    assert not is_conversation_expired(0.0, 95.0, 1, _POLICY.max_ttl_s, _POLICY)
    assert is_conversation_expired(0.0, 95.0, 1, _POLICY.max_ttl_s + 0.001, _POLICY)


def test_tombstone_survives_cold_attempts_until_explicit_cold_request() -> None:
    state = ConversationLifecycle.transition(_S.ACTIVE, _E.TOMBSTONE)
    for _ in range(3):
        state = ConversationLifecycle.transition(state, _E.CONTINUITY_MISS)
        assert state is _S.TOMBSTONED
    assert ConversationLifecycle.transition(state, _E.COLD_REQUEST) is _S.ACTIVE


def test_cid_mismatch_and_unanchored_resume_rotate() -> None:
    binding = SlotBinding(4, "cid-a")
    mismatch = ReuseProbe(reused=True, run_cid="cid-b", resume_base_idx=9)
    assert decide_slot_reuse(mismatch, binding) is SlotReuseVerdict.ROTATE_MISMATCH
    for anchor in (0, -1, -100):
        probe = ReuseProbe(reused=True, run_cid="cid-a", resume_base_idx=anchor)
        assert decide_slot_reuse(probe, binding) is SlotReuseVerdict.ROTATE_UNANCHORED
    assert decide_slot_reuse(mismatch, None) is SlotReuseVerdict.ROTATE_MISMATCH


def test_missing_binding_and_empty_cid_fail_closed() -> None:
    anchored = ReuseProbe(reused=True, run_cid="cid-a", resume_base_idx=3)
    assert decide_slot_reuse(anchored, None) is SlotReuseVerdict.ROTATE_MISMATCH
    cold = ReuseProbe(reused=True, run_cid="", resume_base_idx=3)
    assert decide_slot_reuse(cold, SlotBinding(2, "")) is SlotReuseVerdict.ROTATE_COLD
    assert decide_slot_reuse(ReuseProbe(reused=False), None) is SlotReuseVerdict.FRESH


def test_kill_switch_restores_legacy_reuse_without_cid_check() -> None:
    legacy = ReuseProbe(strict=False, reused=True, run_cid="", resume_base_idx=0)
    assert decide_slot_reuse(legacy, None) is SlotReuseVerdict.REUSE
    assert decide_slot_reuse(ReuseProbe(strict=False), None) is SlotReuseVerdict.FRESH


def test_eight_concurrent_cold_requests_on_one_chat_key_never_reuse() -> None:
    """8 потоков на один chat_key: каждый получает eviction, итог ACTIVE без гонок."""
    lock = threading.Lock()
    barrier = threading.Barrier(8, timeout=10.0)
    shared = {"state": _S.ACTIVE, "binding": SlotBinding(5, "cid-a")}
    verdicts: list[SlotReuseVerdict] = []
    errors: list[BaseException] = []

    def cold_request() -> None:
        try:
            barrier.wait()
            probe = ReuseProbe(reused=True, run_cid="", resume_base_idx=0)
            with lock:
                verdict = decide_slot_reuse(probe, shared["binding"])
                shared["state"] = ConversationLifecycle.transition(shared["state"], _E.COLD_REQUEST)
                shared["binding"] = SlotBinding()
                verdicts.append(verdict)
        except BaseException as exc:  # noqa: BLE001 - проброс в основной поток
            errors.append(exc)

    threads = [threading.Thread(target=cold_request) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10.0)
    assert not errors and not any(t.is_alive() for t in threads)
    assert len(verdicts) == 8 and SlotReuseVerdict.REUSE not in verdicts
    assert verdicts[0] is SlotReuseVerdict.ROTATE_COLD
    assert shared["state"] is _S.ACTIVE


def _write_cfg(home: Path) -> Path:
    path = home.parent / "dynamic_config.json"
    path.write_text(
        '{"lifecycle_max_turns": 3, "lifecycle_idle_ttl_s": 10, "lifecycle_max_ttl_s": 100}',
        encoding="utf-8",
    )
    return path


def test_all_components_share_one_policy_from_tmp_config(_isolated: Path) -> None:
    """T-ISO-I1 + AD-003: store, hot-policy, worker и continuity читают один предел."""
    cfg = _write_cfg(_isolated)
    entry = {"created": 0.0, "last_used": 0.0, "turns": 3}
    assert lcc.session_expired(entry, 1.0, (1e6, 1e6), config_path=cfg)
    assert lcc.session_max_turns(config_path=cfg) == 3
    hot = lcc.hot_overrides(PolicyConfig(), config_path=cfg)
    assert (hot.max_turns, hot.idle_ttl_s, hot.max_ttl_s) == (3, 10.0, 100.0)
    worker = lcc.worker_bounds(PersistentWorkerSettings(), config_path=cfg)
    assert (worker.max_turns, worker.idle_timeout_s, worker.ttl_s) == (3, 10.0, 100.0)
    assert lcc.continuity_ttl_s(1.0, config_path=cfg) == 10.0
    assert list(_isolated.iterdir()) == []


def test_unified_kill_switch_restores_legacy_without_touching_home(
    monkeypatch: pytest.MonkeyPatch, _isolated: Path
) -> None:
    cfg = _write_cfg(_isolated)
    monkeypatch.setenv("AGY_BRIDGE_UNIFIED_LIFECYCLE_ENABLED", "0")
    legacy = PersistentWorkerSettings()
    assert lcc.worker_bounds(legacy, config_path=cfg) == legacy
    assert lcc.continuity_ttl_s(77.0, config_path=cfg) == 77.0
    entry = {"created": 0.0, "last_used": 0.0, "turns": 3}
    assert not lcc.session_expired(entry, 1.0, (1e6, 1e6), config_path=cfg)


def test_no_live_ports_are_reachable() -> None:
    """T-ISO-I2: попытка открыть порт падает до сети."""
    with pytest.raises(AssertionError, match="forbidden side effect"):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).bind(("127.0.0.1", 0))


def test_env_and_module_state_do_not_leak(monkeypatch: pytest.MonkeyPatch) -> None:
    """T-ISO-I3: env восстанавливается, чистые модули без module-level mutable."""
    before = dict(os.environ)
    with monkeypatch.context() as scoped:
        scoped.setenv("AGY_BRIDGE_LIFECYCLE_MAX_TURNS", "7")
        assert lcc.resolve_lifecycle_policy(config_path=None).max_turns == 7
    assert dict(os.environ) == before
    assert lcc.resolve_lifecycle_policy(config_path=None) == LifecyclePolicy()
    for name in ("conversation_lifecycle", "worker_rotation_policy"):
        tree = ast.parse((RUNTIME / f"{name}.py").read_text(encoding="utf-8"))
        _assert_pure_module(tree)


def _assert_pure_module(tree: ast.Module) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not {a.name.split(".")[0] for a in node.names} & _FORBIDDEN_IMPORTS
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in _FORBIDDEN_IMPORTS
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(isinstance(t, ast.Name) and t.id == "__all__" for t in targets):
            continue
        assert not isinstance(node.value, (ast.Dict, ast.List, ast.Set))
        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
            assert node.value.func.id not in _MUTABLE_CALLS


def test_transitions_and_expiry_do_not_read_wall_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-ISO-I4: время только параметром now_s; time.time/monotonic запрещены."""
    monkeypatch.setattr(time, "time", _forbidden)
    monkeypatch.setattr(time, "monotonic", _forbidden)
    for state, event in itertools.product(_S, _E):
        ConversationLifecycle.transition(state, event)
    assert is_conversation_expired(0.0, 0.0, 1, 10.001, _POLICY)
    assert not is_conversation_expired(0.0, 0.0, 1, 10.0, _POLICY)
    probe, binding = _probe_for(_S.ACTIVE)
    assert decide_slot_reuse(probe, binding) is SlotReuseVerdict.REUSE
