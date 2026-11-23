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
        {"baseline_max_slots": -1},
        {"baseline_max_slots": True},
        {"baseline_max_slots": 1.5},
        {"max_slots": 0},
        {"max_slots": -1},
        {"max_slots": True},
        {"rss_ceiling_per_slot_mb": 0},
        {"rss_ceiling_per_slot_mb": -1},
        {"rss_ceiling_per_slot_mb": True},
        {"rss_ceiling_total_mb": 0},
        {"rss_ceiling_total_mb": -1},
        {"rss_ceiling_total_mb": True},
        {"rss_ceiling_per_slot_mb": 400, "rss_ceiling_total_mb": 300},
        {"fd_limit_per_slot": 0},
        {"fd_limit_per_slot": -1},
        {"fd_limit_per_slot": True},
        {"error_rate_stop_pct": 0.0},
        {"error_rate_stop_pct": -1.0},
        {"error_rate_stop_pct": 100.1},
        {"error_rate_stop_pct": 101.0},
        {"error_rate_stop_pct": math.nan},
        {"error_rate_stop_pct": math.inf},
        {"error_rate_stop_pct": -math.inf},
        {"error_rate_stop_pct": True},
        {"error_rate_stop_pct": "5.0"},
        {"fd_leak_stop": "yes"},
        {"fd_leak_stop": 1},
    ],
)
def test_canary_config_validate_fail_closed(kwargs: dict[str, object]) -> None:
    """Невалидные параметры отклоняются через ValueError."""
    with pytest.raises(ValueError):
        AgyResidentCanaryConfig(**kwargs)  # type: ignore[arg-type]


def test_canary_config_valid_boundaries() -> None:
    """Граничные валидные значения проходят validate() без ошибок."""
    cfg = AgyResidentCanaryConfig(
        rss_ceiling_per_slot_mb=300,
        rss_ceiling_total_mb=300,
        error_rate_stop_pct=100.0,
        fd_leak_stop=False,
    )
    assert cfg.rss_ceiling_total_mb == 300
    assert cfg.error_rate_stop_pct == 100.0
    assert cfg.fd_leak_stop is False


def test_rollback_plan_returns_expected_commands() -> None:
    """rollback_plan возвращает точный список из двух команд отката."""
    cmds = rollback_plan()
    assert len(cmds) == 2
    assert cmds[0] == "AGY_RESIDENT_ENABLED=false"
    assert cmds[1] == "launchctl kickstart -k gui/$(id -u)/com.user.dsh-hub"


def test_canary_stop_reasons_boundaries_and_unknown_keys() -> None:
    """Значения ровно на потолке и неизвестные ключи не дают причин остановки."""
    at_ceiling = {
        "max_slot_rss_mb": 300.0,
        "total_rss_mb": 3000.0,
        "error_rate_pct": 5.0,
        "fd_leak": False,
        "max_slot_fds": 256,
        "unknown_metric": 999999,
    }
    assert canary_stop_reasons(at_ceiling) == []
    assert canary_stop_reasons({"unknown_only": "ignored"}) == []

    over_ceiling = {
        "max_slot_rss_mb": 301.0,
        "total_rss_mb": 3001.0,
        "error_rate_pct": 5.1,
        "fd_leak_detected": True,
        "max_slot_fds": 257,
    }
    reasons = canary_stop_reasons(over_ceiling)
    assert len(reasons) == 5
    assert "rss_per_slot_exceeded: 301.0 MiB > 300 MiB" in reasons
    assert "rss_total_exceeded: 3001.0 MiB > 3000 MiB" in reasons
    assert "error_rate_exceeded: 5.10% > 5.00%" in reasons
    assert "fd_leak_detected" in reasons
    assert "fd_limit_exceeded: 257 > 256" in reasons


@pytest.mark.parametrize(
    ("observations", "expected"),
    [
        ({"max_slot_rss_mb": math.nan}, ["invalid_metric:max_slot_rss_mb"]),
        ({"max_slot_rss_mb": True}, ["invalid_metric:max_slot_rss_mb"]),
        ({"max_slot_rss_mb": "bad"}, ["invalid_metric:max_slot_rss_mb"]),
        ({"total_rss_mb": math.inf}, ["invalid_metric:total_rss_mb"]),
        ({"error_rate_pct": math.nan}, ["invalid_metric:error_rate_pct"]),
        ({"max_slot_fds": math.nan}, ["invalid_metric:max_slot_fds"]),
        ({"errors": 5, "total_requests": 100}, []),
        (
            {"errors": 6, "total_requests": 100},
            ["error_rate_exceeded: 6.00% > 5.00%"],
        ),
        ({"error_rate_pct": 1.0, "errors": 50, "total_requests": 100}, []),
        ({"errors": 10}, []),
        ({"total_requests": 100}, []),
        ({"errors": math.nan, "total_requests": 100}, []),
        ({"errors": 10, "total_requests": math.nan}, []),
        ({"errors": 10, "total_requests": 0}, []),
        ({"errors": 10, "total_requests": -5}, []),
    ],
)
def test_canary_stop_reasons_invalid_metrics_and_error_rate_derived(
    observations: dict[str, object],
    expected: list[str],
) -> None:
    """Невалидные метрики, bool/строки и расчёт error_rate из errors/total_requests."""
    assert canary_stop_reasons(observations) == expected


def test_canary_stop_reasons_respects_fd_leak_stop_disabled() -> None:
    """При fd_leak_stop=False утечка FD не добавляет причину остановки."""
    cfg = AgyResidentCanaryConfig(fd_leak_stop=False)
    reasons = canary_stop_reasons({"fd_leak": True, "max_slot_fds": 999}, config=cfg)
    assert reasons == []
