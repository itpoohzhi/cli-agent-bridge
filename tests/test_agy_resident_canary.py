"""Тесты канареечного конфига AGY_RESIDENT_ENABLED, отката и стоп-причин."""

from __future__ import annotations

import math
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

_BRIDGE_DIR = Path(__file__).resolve().parents[1] / "bridges" / "agy-bridge"
if str(_BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(_BRIDGE_DIR))

from agy_runtime.agy_resident_canary import (  # noqa: E402
    AgyResidentCanaryConfig,
    canary_stop_reasons,
    rollback_plan,
)


def test_canary_config_defaults_and_docstring() -> None:
    """Проверка значений по умолчанию, неизменяемости и пометки о некалиброванности."""
    cfg = AgyResidentCanaryConfig()
    assert cfg.baseline_max_slots == 2
    assert cfg.max_slots == 10
    assert cfg.rss_ceiling_per_slot_mb == 300
    assert cfg.rss_ceiling_total_mb == 3000
    assert cfg.fd_limit_per_slot > 0
    assert cfg.error_rate_stop_pct == 5.0
    assert cfg.fd_leak_stop is True
    assert "предварительные, некалиброванные" in (AgyResidentCanaryConfig.__doc__ or "")
    with pytest.raises(FrozenInstanceError):
        cfg.max_slots = 4  # type: ignore[misc]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"baseline_max_slots": 0},
        {"max_slots": 0},
        {"rss_ceiling_per_slot_mb": 0},
        {"rss_ceiling_per_slot_mb": 400, "rss_ceiling_total_mb": 300},
        {"fd_limit_per_slot": 0},
        {"error_rate_stop_pct": 0.0},
        {"error_rate_stop_pct": 101.0},
        {"error_rate_stop_pct": math.nan},
        {"error_rate_stop_pct": math.inf},
        {"baseline_max_slots": True},
    ],
)
def test_canary_config_validate_fail_closed(kwargs: dict[str, object]) -> None:
    """Невалидные параметры отклоняются через ValueError."""
    with pytest.raises(ValueError):
        AgyResidentCanaryConfig(**kwargs)  # type: ignore[arg-type]


def test_rollback_plan_returns_expected_commands() -> None:
    """rollback_plan возвращает команды отката как строки без побочных эффектов."""
    cmds = rollback_plan()
    assert cmds == [
        "AGY_RESIDENT_ENABLED=false",
        "launchctl kickstart -k gui/$(id -u)/com.user.dsh-hub",
    ]


def test_canary_stop_reasons_clean_vs_violations() -> None:
    """canary_stop_reasons возвращает пустой список в норме и причины при нарушениях."""
    healthy = {
        "max_slot_rss_mb": 250.0,
        "total_rss_mb": 2400.0,
        "error_rate_pct": 5.0,
        "fd_leak": False,
        "max_slot_fds": 128,
    }
    assert canary_stop_reasons(healthy) == []

    violated = {
        "max_slot_rss_mb": 350.0,
        "total_rss_mb": 3200.0,
        "error_rate_pct": 5.5,
        "fd_leak": True,
        "max_slot_fds": 300,
    }
    reasons = canary_stop_reasons(violated)
    assert len(reasons) == 5
    assert any("rss_per_slot_exceeded" in r for r in reasons)
    assert any("rss_total_exceeded" in r for r in reasons)
    assert any("error_rate_exceeded" in r for r in reasons)
    assert "fd_leak_detected" in reasons
    assert any("fd_limit_exceeded" in r for r in reasons)


def test_canary_stop_reasons_respects_fd_leak_stop_disabled() -> None:
    """При fd_leak_stop=False утечка FD не добавляет причину остановки."""
    cfg = AgyResidentCanaryConfig(fd_leak_stop=False)
    reasons = canary_stop_reasons({"fd_leak": True, "max_slot_fds": 999}, config=cfg)
    assert reasons == []
