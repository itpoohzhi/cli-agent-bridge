"""W2-D: unified lifecycle в read_runtime_flags (VER-014, AD-003, CD-004/CD-008).

При AGY_BRIDGE_UNIFIED_LIFECYCLE_ENABLED=true (default) hot-политика берёт
max_turns/idle_ttl_s/max_ttl_s из единой LifecyclePolicy; kill-switch false
мгновенно возвращает legacy-ключи BRIDGE_HOT_*. Детерминированно: 0 сокетов,
0 sleep; env только через monkeypatch, dynamic_config.json — отдельный
tmp-файл на сценарий (кэш long_session_config привязан к пути).
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Final

import pytest

ROOT: Final = Path(__file__).resolve().parents[1]
AGY_BRIDGE: Final = ROOT / "bridges" / "agy-bridge"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(AGY_BRIDGE) not in sys.path:
    sys.path.append(str(AGY_BRIDGE))

from agy_runtime.session_resume_adapter import (  # noqa: E402
    ExplicitResumeAdapter,
    RuntimeFlags,
    read_runtime_flags,
)
from core.hot_session_policy import (  # noqa: E402
    PolicyConfig,
    SlotSnapshot,
    SlotState,
    is_slot_expired,
)

_HOT_KEYS: Final = (
    "max_turns", "idle_ttl_s", "max_ttl_s", "guard_max_bytes", "guard_max_messages",
    "in_flight_max_s", "supersede_max_per_min", "explicit_plain_enabled",
    "zc_plain_enabled", "zc_agentic_enabled", "canonical_tools_enabled", "epoch",
)
_UNIFIED_KEYS: Final = (
    "unified_lifecycle_enabled", "lifecycle_max_turns",
    "lifecycle_idle_ttl_s", "lifecycle_max_ttl_s",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _HOT_KEYS:
        monkeypatch.delenv(f"BRIDGE_HOT_{key.upper()}", raising=False)
    for key in _UNIFIED_KEYS:
        monkeypatch.delenv(f"AGY_BRIDGE_{key.upper()}", raising=False)


def _cfg(tmp_path: Path, name: str, data: dict[str, object]) -> Path:
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _limits(turns: int, idle: float, max_ttl: float) -> tuple[int, float, float]:
    return turns, idle, max_ttl


def _policy_limits(cfg: PolicyConfig) -> tuple[int, float, float]:
    return cfg.max_turns, cfg.idle_ttl_s, cfg.max_ttl_s


def test_defaults_without_env_or_file(tmp_path: Path) -> None:
    flags = read_runtime_flags(config_path=tmp_path / "absent.json")
    assert flags == RuntimeFlags()
    assert _policy_limits(flags.policy) == (30, 2700.0, 86400.0)


def test_unified_lifecycle_beats_bridge_hot_in_dynamic_config(tmp_path: Path) -> None:
    path = _cfg(tmp_path, "on", {
        "lifecycle_max_turns": 8, "lifecycle_idle_ttl_s": 90, "lifecycle_max_ttl_s": 900,
        "bridge_hot_max_turns": 77, "bridge_hot_idle_ttl_s": 111, "bridge_hot_max_ttl_s": 2222,
    })
    flags = read_runtime_flags(config_path=path)
    assert _policy_limits(flags.policy) == (8, 90.0, 900.0)


def test_kill_switch_in_config_restores_bridge_hot_values(tmp_path: Path) -> None:
    path = _cfg(tmp_path, "off", {
        "unified_lifecycle_enabled": False,
        "lifecycle_max_turns": 8, "lifecycle_idle_ttl_s": 90, "lifecycle_max_ttl_s": 900,
        "bridge_hot_max_turns": 77, "bridge_hot_idle_ttl_s": 111, "bridge_hot_max_ttl_s": 2222,
    })
    flags = read_runtime_flags(config_path=path)
    assert _policy_limits(flags.policy) == (77, 111.0, 2222.0)


def test_env_lifecycle_beats_dynamic_config_and_hot_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _cfg(tmp_path, "envwin", {
        "lifecycle_max_turns": 99, "lifecycle_idle_ttl_s": 99, "lifecycle_max_ttl_s": 99999,
        "bridge_hot_max_turns": 88, "bridge_hot_idle_ttl_s": 88, "bridge_hot_max_ttl_s": 8888,
    })
    monkeypatch.setenv("AGY_BRIDGE_LIFECYCLE_MAX_TURNS", "7")
    monkeypatch.setenv("AGY_BRIDGE_LIFECYCLE_IDLE_TTL_S", "300")
    monkeypatch.setenv("AGY_BRIDGE_LIFECYCLE_MAX_TTL_S", "3600")
    monkeypatch.setenv("BRIDGE_HOT_MAX_TURNS", "77")
    monkeypatch.setenv("BRIDGE_HOT_IDLE_TTL_S", "111")
    monkeypatch.setenv("BRIDGE_HOT_MAX_TTL_S", "2222")
    flags = read_runtime_flags(config_path=path)
    assert _policy_limits(flags.policy) == (7, 300.0, 3600.0)


def test_kill_switch_env_false_uses_bridge_hot_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _cfg(tmp_path, "envoff", {"lifecycle_max_turns": 99, "lifecycle_idle_ttl_s": 99})
    monkeypatch.setenv("AGY_BRIDGE_UNIFIED_LIFECYCLE_ENABLED", "0")
    monkeypatch.setenv("AGY_BRIDGE_LIFECYCLE_MAX_TURNS", "7")
    monkeypatch.setenv("BRIDGE_HOT_MAX_TURNS", "77")
    monkeypatch.setenv("BRIDGE_HOT_IDLE_TTL_S", "111")
    monkeypatch.setenv("BRIDGE_HOT_MAX_TTL_S", "2222")
    flags = read_runtime_flags(config_path=path)
    assert _policy_limits(flags.policy) == (77, 111.0, 2222.0)


def test_override_keeps_other_policy_fields_and_route_flags(tmp_path: Path) -> None:
    path = _cfg(tmp_path, "fields", {
        "bridge_hot_explicit_plain_enabled": True, "bridge_hot_epoch": 7,
        "bridge_hot_guard_max_bytes": 4096, "bridge_hot_guard_max_messages": 64,
        "bridge_hot_in_flight_max_s": 120, "bridge_hot_supersede_max_per_min": 9,
        "lifecycle_max_turns": 8, "lifecycle_idle_ttl_s": 90, "lifecycle_max_ttl_s": 900,
    })
    flags = read_runtime_flags(config_path=path)
    assert flags.policy == PolicyConfig(
        enabled=True, guard_max_bytes=4096, guard_max_messages=64,
        idle_ttl_s=90.0, max_ttl_s=900.0, max_turns=8,
        in_flight_max_s=120.0, supersede_max_per_min=9,
    )
    assert (flags.explicit_plain_enabled, flags.epoch) == (True, 7)
    assert not any((flags.zc_plain_enabled, flags.zc_agentic_enabled, flags.canonical_tools_enabled))


def test_max_ttl_never_below_idle_ttl_in_hot_policy(tmp_path: Path) -> None:
    path = _cfg(tmp_path, "inv", {"lifecycle_idle_ttl_s": 5000, "lifecycle_max_ttl_s": 100})
    policy = read_runtime_flags(config_path=path).policy
    assert policy.idle_ttl_s == policy.max_ttl_s == 5000.0


def test_lifecycle_bounds_clamped_in_hot_policy(tmp_path: Path) -> None:
    path = _cfg(tmp_path, "huge", {
        "lifecycle_max_turns": 10**6, "lifecycle_idle_ttl_s": 10**9, "lifecycle_max_ttl_s": 10**12,
    })
    policy = read_runtime_flags(config_path=path).policy
    assert _policy_limits(policy) == (1000, 604_800.0, 2_592_000.0)


def test_invalid_lifecycle_values_use_unified_defaults_not_hot(tmp_path: Path) -> None:
    path = _cfg(tmp_path, "junk", {
        "lifecycle_max_turns": "x", "lifecycle_idle_ttl_s": "y", "lifecycle_max_ttl_s": "z",
        "bridge_hot_max_turns": 77, "bridge_hot_idle_ttl_s": 111, "bridge_hot_max_ttl_s": 2222,
    })
    policy = read_runtime_flags(config_path=path).policy
    assert _policy_limits(policy) == (30, 2700.0, 86400.0)


def _slot(turns: int, created: float, last_used: float) -> SlotSnapshot:
    return SlotSnapshot(SlotState.READY, "cid-1", "digest", 1, 0, 0, 0, created, last_used, turns)


def test_slot_expiry_follows_unified_limits_and_kill_switch(tmp_path: Path) -> None:
    data: dict[str, object] = {
        "lifecycle_max_turns": 5, "lifecycle_idle_ttl_s": 100, "lifecycle_max_ttl_s": 1000,
        "bridge_hot_max_turns": 50, "bridge_hot_idle_ttl_s": 10000, "bridge_hot_max_ttl_s": 100000,
    }
    on = read_runtime_flags(config_path=_cfg(tmp_path, "exp-on", data)).policy
    off = read_runtime_flags(
        config_path=_cfg(tmp_path, "exp-off", {**data, "unified_lifecycle_enabled": False})
    ).policy
    turns_slot = _slot(5, 0.0, 99.0)
    assert is_slot_expired(turns_slot, 100.0, on) is True
    assert is_slot_expired(turns_slot, 100.0, off) is False
    idle_slot = _slot(1, 0.0, 0.0)
    assert is_slot_expired(idle_slot, 100.5, on) is True
    assert is_slot_expired(idle_slot, 100.5, off) is False
    ttl_slot = _slot(1, 0.0, 1000.0)
    assert is_slot_expired(ttl_slot, 1001.0, on) is True
    assert is_slot_expired(ttl_slot, 1001.0, off) is False
    assert is_slot_expired(_slot(4, 0.0, 100.0), 100.0, on) is False


def test_decide_state_enabled_projection_keeps_overrides(tmp_path: Path) -> None:
    path = _cfg(tmp_path, "proj", {"lifecycle_max_turns": 6, "bridge_hot_max_turns": 40})
    policy = read_runtime_flags(config_path=path).policy
    projected = replace(policy, enabled=True)
    assert (projected.max_turns, projected.enabled) == (6, True)
    assert _limits(6, 2700.0, 86400.0) == _policy_limits(projected)


def test_adapter_init_reads_unified_policy(tmp_path: Path) -> None:
    path = _cfg(tmp_path, "adapter", {"lifecycle_max_turns": 6, "bridge_hot_max_turns": 40})
    adapter = ExplicitResumeAdapter(tmp_path / "state", config_path=path)
    try:
        assert adapter._last_flags.policy.max_turns == 6
    finally:
        adapter.close()


def test_hot_toggle_between_config_paths(tmp_path: Path) -> None:
    data: dict[str, object] = {
        "lifecycle_max_turns": 8, "bridge_hot_max_turns": 77,
        "lifecycle_idle_ttl_s": 90, "bridge_hot_idle_ttl_s": 111,
    }
    on = _cfg(tmp_path, "toggle-on", data)
    off = _cfg(tmp_path, "toggle-off", {**data, "unified_lifecycle_enabled": False})
    assert _policy_limits(read_runtime_flags(config_path=on).policy) == (8, 90.0, 86400.0)
    assert _policy_limits(read_runtime_flags(config_path=off).policy) == (77, 111.0, 86400.0)
    assert _policy_limits(read_runtime_flags(config_path=on).policy) == (8, 90.0, 86400.0)
