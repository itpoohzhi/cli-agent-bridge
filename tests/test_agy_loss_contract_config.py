"""W2-A: адаптер конфигурации loss-контракта (VER-012, AD-003/AD-013, CD-004/CD-008).

Детерминированно: 0 сокетов, 0 sleep; env только через monkeypatch,
dynamic_config.json — отдельный tmp-файл на каждый сценарий (кэш по пути).
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

from agy_runtime import loss_contract_config as lcc  # noqa: E402
from agy_runtime.conversation_lifecycle import LifecyclePolicy  # noqa: E402
from agy_runtime.input_guard_policy import InputGuardMode  # noqa: E402
from agy_runtime.persistent_worker_config import PersistentWorkerSettings  # noqa: E402
from core.hot_session_policy import PolicyConfig  # noqa: E402
from core.resumed_tools_policy import (  # noqa: E402
    CompactToolsMode,
    CompactToolsQuery,
    compute_tools_fingerprint,
)

_KEYS: Final = (
    "strict_cold_rotation", "unified_lifecycle_enabled", "lifecycle_max_turns",
    "lifecycle_idle_ttl_s", "lifecycle_max_ttl_s", "loss_receipt_enabled",
    "compact_tools_mode", "atomic_active_tools_enabled", "input_guard_mode",
)
_TOOLS: Final = [{"type": "function", "function": {"name": "t"}}]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _KEYS:
        monkeypatch.delenv(f"AGY_BRIDGE_{key.upper()}", raising=False)


def _cfg(tmp_path: Path, name: str, data: dict[str, object]) -> Path:
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_defaults_without_env_or_file(tmp_path: Path) -> None:
    got = lcc.read_loss_contract_settings(config_path=tmp_path / "absent.json")
    assert got == lcc.LossContractSettings()
    assert got.lifecycle == LifecyclePolicy(30, 2700.0, 86400.0)
    assert got.compact_tools_mode is CompactToolsMode.PROVEN
    assert got.input_guard_mode is InputGuardMode.COMPACT_OR_REJECT


def test_dynamic_config_overrides_default_for_all_nine_keys(tmp_path: Path) -> None:
    path = _cfg(tmp_path, "dyn", {
        "strict_cold_rotation": False, "unified_lifecycle_enabled": False,
        "lifecycle_max_turns": 12, "lifecycle_idle_ttl_s": 600,
        "lifecycle_max_ttl_s": 7200, "loss_receipt_enabled": False,
        "compact_tools_mode": "legacy", "atomic_active_tools_enabled": False,
        "input_guard_mode": "legacy",
    })
    got = lcc.read_loss_contract_settings(config_path=path)
    assert (got.strict_cold_rotation, got.unified_lifecycle_enabled) == (False, False)
    assert got.lifecycle == LifecyclePolicy(12, 600.0, 7200.0)
    assert (got.loss_receipt_enabled, got.atomic_active_tools_enabled) == (False, False)
    assert got.compact_tools_mode is CompactToolsMode.LEGACY
    assert got.input_guard_mode is InputGuardMode.LEGACY


def test_env_beats_dynamic_config_for_all_nine_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _cfg(tmp_path, "dyn", {
        "strict_cold_rotation": True, "unified_lifecycle_enabled": True,
        "lifecycle_max_turns": 99, "lifecycle_idle_ttl_s": 99,
        "lifecycle_max_ttl_s": 99999, "loss_receipt_enabled": True,
        "compact_tools_mode": "proven", "atomic_active_tools_enabled": True,
        "input_guard_mode": "compact_or_reject",
    })
    env = {
        "STRICT_COLD_ROTATION": "0", "UNIFIED_LIFECYCLE_ENABLED": "off",
        "LIFECYCLE_MAX_TURNS": "7", "LIFECYCLE_IDLE_TTL_S": "300",
        "LIFECYCLE_MAX_TTL_S": "3600", "LOSS_RECEIPT_ENABLED": "false",
        "COMPACT_TOOLS_MODE": "off", "ATOMIC_ACTIVE_TOOLS_ENABLED": "no",
        "INPUT_GUARD_MODE": "legacy",
    }
    for key, val in env.items():
        monkeypatch.setenv(f"AGY_BRIDGE_{key}", val)
    got = lcc.read_loss_contract_settings(config_path=path)
    assert not any((got.strict_cold_rotation, got.unified_lifecycle_enabled,
                    got.loss_receipt_enabled, got.atomic_active_tools_enabled))
    assert got.lifecycle == LifecyclePolicy(7, 300.0, 3600.0)
    assert got.compact_tools_mode is CompactToolsMode.OFF
    assert got.input_guard_mode is InputGuardMode.LEGACY


@pytest.mark.parametrize("raw", ["garbage", "", "nan", "-5", "0"])
def test_invalid_numeric_values_fall_back_or_clamp(tmp_path: Path, raw: str) -> None:
    path = _cfg(tmp_path, f"bad-{raw or 'empty'}", {
        "lifecycle_max_turns": raw, "lifecycle_idle_ttl_s": raw, "lifecycle_max_ttl_s": raw,
    })
    policy = lcc.resolve_lifecycle_policy(config_path=path)
    assert 1 <= policy.max_turns <= 1000
    assert 1.0 <= policy.idle_ttl_s <= policy.max_ttl_s


def test_unparsable_numeric_uses_defaults(tmp_path: Path) -> None:
    path = _cfg(tmp_path, "junk", {"lifecycle_max_turns": "x", "lifecycle_idle_ttl_s": "y"})
    assert lcc.resolve_lifecycle_policy(config_path=path) == LifecyclePolicy()


def test_numeric_bounds_clamped(tmp_path: Path) -> None:
    path = _cfg(tmp_path, "huge", {
        "lifecycle_max_turns": 10**6, "lifecycle_idle_ttl_s": 10**9,
        "lifecycle_max_ttl_s": 10**12,
    })
    policy = lcc.resolve_lifecycle_policy(config_path=path)
    assert (policy.max_turns, policy.idle_ttl_s, policy.max_ttl_s) == (1000, 604_800.0, 2_592_000.0)


def test_max_ttl_never_below_idle_ttl(tmp_path: Path) -> None:
    path = _cfg(tmp_path, "inv", {"lifecycle_idle_ttl_s": 5000, "lifecycle_max_ttl_s": 100})
    policy = lcc.resolve_lifecycle_policy(config_path=path)
    assert policy.max_ttl_s == policy.idle_ttl_s == 5000.0


@pytest.mark.parametrize("raw", ["bogus", "", "  ", 42, None])
def test_invalid_enum_values_use_safe_defaults(tmp_path: Path, raw: object) -> None:
    path = _cfg(tmp_path, f"enum-{raw!r}".replace(" ", "_").replace("'", ""),
                {"compact_tools_mode": raw, "input_guard_mode": raw})
    got = lcc.read_loss_contract_settings(config_path=path)
    assert got.compact_tools_mode is CompactToolsMode.PROVEN
    assert got.input_guard_mode is InputGuardMode.COMPACT_OR_REJECT


def test_invalid_bool_falls_back_to_default(tmp_path: Path) -> None:
    path = _cfg(tmp_path, "badbool", {"strict_cold_rotation": "maybe", "loss_receipt_enabled": "??"})
    got = lcc.read_loss_contract_settings(config_path=path)
    assert got.strict_cold_rotation is True
    assert got.loss_receipt_enabled is True


def test_enum_values_are_case_and_whitespace_insensitive(tmp_path: Path) -> None:
    path = _cfg(tmp_path, "case", {"compact_tools_mode": " LEGACY ", "input_guard_mode": " Legacy "})
    got = lcc.read_loss_contract_settings(config_path=path)
    assert got.compact_tools_mode is CompactToolsMode.LEGACY
    assert got.input_guard_mode is InputGuardMode.LEGACY


def test_session_max_turns_unified_vs_legacy(tmp_path: Path) -> None:
    unified = _cfg(tmp_path, "u", {"lifecycle_max_turns": 11, "session_max_turns": 77})
    legacy = _cfg(tmp_path, "l", {
        "unified_lifecycle_enabled": False, "lifecycle_max_turns": 11, "session_max_turns": 77,
    })
    assert lcc.session_max_turns(config_path=unified) == 11
    assert lcc.session_max_turns(config_path=legacy) == 77


def test_session_max_turns_legacy_default_and_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _cfg(tmp_path, "off", {"unified_lifecycle_enabled": False})
    assert lcc.session_max_turns(config_path=path) == 30
    monkeypatch.setenv("AGY_BRIDGE_SESSION_MAX_TURNS", "9")
    assert lcc.session_max_turns(config_path=path) == 9


def _entry(created: float, last_used: float, turns: int) -> dict[str, object]:
    return {"created": created, "last_used": last_used, "turns": turns}


def test_session_expired_boundaries_unified(tmp_path: Path) -> None:
    path = _cfg(tmp_path, "exp", {
        "lifecycle_max_turns": 3, "lifecycle_idle_ttl_s": 100, "lifecycle_max_ttl_s": 1000,
    })
    legacy = (1e9, 1e9)
    check = lambda e, now: lcc.session_expired(e, now, legacy, config_path=path)  # noqa: E731
    assert check(_entry(0, 0, 2), 100) is False
    assert check(_entry(0, 0, 2), 100.5) is True
    assert check(_entry(0, 999, 2), 1000) is False
    assert check(_entry(0, 1000, 2), 1001) is True
    assert check(_entry(0, 0, 3), 1) is True


def test_session_expired_kill_switch_uses_legacy_limits(tmp_path: Path) -> None:
    path = _cfg(tmp_path, "expl", {
        "unified_lifecycle_enabled": False, "lifecycle_idle_ttl_s": 1,
        "lifecycle_max_turns": 1, "session_max_turns": 5,
    })
    legacy = (2700.0, 86400.0)
    assert lcc.session_expired(_entry(0, 0, 4), 2700, legacy, config_path=path) is False
    assert lcc.session_expired(_entry(0, 0, 5), 1, legacy, config_path=path) is True
    assert lcc.session_expired(_entry(0, 0, 0), 2701, legacy, config_path=path) is True


def test_hot_overrides_applies_policy_and_keeps_other_fields(tmp_path: Path) -> None:
    path = _cfg(tmp_path, "hot", {
        "lifecycle_max_turns": 8, "lifecycle_idle_ttl_s": 90, "lifecycle_max_ttl_s": 900,
    })
    base = PolicyConfig(enabled=True, guard_max_bytes=4096, max_turns=30)
    got = lcc.hot_overrides(base, config_path=path)
    assert (got.max_turns, got.idle_ttl_s, got.max_ttl_s) == (8, 90.0, 900.0)
    assert (got.enabled, got.guard_max_bytes) == (True, 4096)


def test_hot_overrides_kill_switch_returns_legacy_object(tmp_path: Path) -> None:
    path = _cfg(tmp_path, "hotoff", {"unified_lifecycle_enabled": False, "lifecycle_max_turns": 8})
    base = PolicyConfig(max_turns=30, idle_ttl_s=2700.0)
    assert lcc.hot_overrides(base, config_path=path) is base


def test_worker_bounds_clamp_default_50_to_30(tmp_path: Path) -> None:
    got = lcc.worker_bounds(PersistentWorkerSettings(max_turns=50), config_path=tmp_path / "n.json")
    assert got.max_turns == 30
    assert got.idle_timeout_s == 300.0
    assert got.ttl_s == 1800.0


def test_worker_bounds_clamps_idle_and_ttl_to_conversation(tmp_path: Path) -> None:
    path = _cfg(tmp_path, "wb", {"lifecycle_idle_ttl_s": 120, "lifecycle_max_ttl_s": 600})
    base = PersistentWorkerSettings(idle_timeout_s=300.0, ttl_s=1800.0, max_rss_mb=512, enabled=True)
    got = lcc.worker_bounds(base, config_path=path)
    assert (got.idle_timeout_s, got.ttl_s) == (120.0, 600.0)
    assert (got.max_rss_mb, got.enabled) == (512, True)


def test_worker_bounds_ttl_not_below_idle_and_turns_ceiling(tmp_path: Path) -> None:
    path = _cfg(tmp_path, "wb2", {"lifecycle_max_turns": 900})
    base = PersistentWorkerSettings(idle_timeout_s=60.0, ttl_s=60.0)
    got = lcc.worker_bounds(base, config_path=path)
    assert got.max_turns == 500
    assert got.ttl_s >= got.idle_timeout_s


def test_worker_bounds_kill_switch_returns_legacy_object(tmp_path: Path) -> None:
    path = _cfg(tmp_path, "wboff", {"unified_lifecycle_enabled": False})
    base = PersistentWorkerSettings(max_turns=50)
    assert lcc.worker_bounds(base, config_path=path) is base


def test_continuity_ttl_follows_idle_or_legacy(tmp_path: Path) -> None:
    on = _cfg(tmp_path, "con", {"lifecycle_idle_ttl_s": 321})
    off = _cfg(tmp_path, "coff", {"unified_lifecycle_enabled": False, "lifecycle_idle_ttl_s": 321})
    assert lcc.continuity_ttl_s(1800.0, config_path=on) == 321.0
    assert lcc.continuity_ttl_s(1800.0, config_path=off) == 1800.0


def _query(**kw: object) -> CompactToolsQuery:
    fp = compute_tools_fingerprint(_TOOLS)
    base = CompactToolsQuery(
        is_resumed=True, stored_fp=fp, stored_cid="c1", run_cid="c1", tools=_TOOLS,
    )
    return replace(base, **kw)  # type: ignore[arg-type]


def test_compact_tools_decision_proven_default(tmp_path: Path) -> None:
    path = tmp_path / "none.json"
    assert lcc.compact_tools_decision(_query(), config_path=path) is True
    assert lcc.compact_tools_decision(_query(stored_cid="other"), config_path=path) is False
    assert lcc.compact_tools_decision(_query(explicit_path=True), config_path=path) is False
    assert lcc.compact_tools_decision(_query(is_resumed=False), config_path=path) is False


def test_compact_tools_decision_modes_override_query_mode(tmp_path: Path) -> None:
    legacy = _cfg(tmp_path, "cl", {"compact_tools_mode": "legacy"})
    off = _cfg(tmp_path, "co", {"compact_tools_mode": "off"})
    mismatched = _query(stored_cid="other", mode=CompactToolsMode.OFF)
    assert lcc.compact_tools_decision(mismatched, config_path=legacy) is True
    assert lcc.compact_tools_decision(_query(), config_path=off) is False
    assert lcc.compact_tools_decision(_query(explicit_path=True), config_path=legacy) is True
