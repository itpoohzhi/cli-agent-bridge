from __future__ import annotations  # noqa: E402

"""Тесты канареечного конфига AGY_RESIDENT_ENABLED, отката и стоп-причин."""

import math  # noqa: E402
import sys  # noqa: E402
from dataclasses import FrozenInstanceError  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BRIDGE_DIR = _REPO_ROOT / "bridges" / "agy-bridge"
for _path in (_REPO_ROOT, _BRIDGE_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import adapters.stdio_drivers.agy_config as agy_config_mod  # noqa: E402
import agy_runtime.agy_resident_canary as canary_mod  # noqa: E402
from adapters.stdio_drivers.agy_config import (  # noqa: E402
    AgyResidentConfig,
    apply_canary_limits,
    load_agy_canary_config,
)
from agy_runtime.agy_resident_canary import (  # noqa: E402
    LAUNCHD_SERVICE_LABEL,
    AgyResidentCanaryConfig,
    CanaryObservations,
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
        {"baseline_max_slots": 5, "max_slots": 4},
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
    """rollback_plan возвращает персистентный launchctl-откат, рестарт и верификацию."""
    cmds = rollback_plan()
    assert LAUNCHD_SERVICE_LABEL == "gui/$(id -u)/com.user.dsh-hub"
    assert len(cmds) == 3
    assert cmds[0] == "launchctl setenv AGY_RESIDENT_ENABLED false"
    assert cmds[1] == f"launchctl kickstart -k {LAUNCHD_SERVICE_LABEL}"
    assert "ps eww" in cmds[2]
    assert "AGY_RESIDENT_ENABLED=false" in cmds[2]
    assert "ROLLBACK_VERIFY_FAILED" in cmds[2]


def test_canary_stop_reasons_boundaries_and_fail_closed_defaults() -> None:
    """Значения на потолке не останавливают rollout, а пустой DTO даёт fail-closed причины."""
    at_ceiling = CanaryObservations(
        max_slot_rss_mb=300.0,
        total_rss_mb=3000.0,
        fd_open_per_slot=256,
        errors=5,
        total_requests=100,
        fd_leak_detected=False,
    )
    assert canary_stop_reasons(at_ceiling) == []
    assert canary_stop_reasons(CanaryObservations()) == [
        "telemetry_missing:max_slot_rss_mb",
        "telemetry_missing:total_rss_mb",
        "telemetry_missing:error_rate",
        "telemetry_missing:fd_open_per_slot",
    ]

    over_ceiling = CanaryObservations(
        max_slot_rss_mb=301.0,
        total_rss_mb=3001.0,
        fd_open_per_slot=257,
        errors=6,
        total_requests=100,
        fd_leak_detected=True,
    )
    reasons = canary_stop_reasons(over_ceiling)
    assert len(reasons) == 5
    assert "rss_per_slot_exceeded: 301.0 MiB > 300 MiB" in reasons
    assert "rss_total_exceeded: 3001.0 MiB > 3000 MiB" in reasons
    assert "error_rate_exceeded: 6.00% > 5.00%" in reasons
    assert "fd_open_per_slot" not in reasons
    assert "fd_limit_exceeded: 257 > 256" in reasons
    assert "fd_leak_detected" in reasons


@pytest.mark.parametrize(
    ("obs", "expected_reason"),
    [
        (
            CanaryObservations(
                max_slot_rss_mb=None,
                total_rss_mb=100.0,
                fd_open_per_slot=10,
                errors=0,
                total_requests=10,
            ),
            "telemetry_missing:max_slot_rss_mb",
        ),
        (
            CanaryObservations(
                max_slot_rss_mb=math.nan,
                total_rss_mb=100.0,
                fd_open_per_slot=10,
                errors=0,
                total_requests=10,
            ),
            "invalid_metric:max_slot_rss_mb",
        ),
        (
            CanaryObservations(
                max_slot_rss_mb=100.0,
                total_rss_mb=None,
                fd_open_per_slot=10,
                errors=0,
                total_requests=10,
            ),
            "telemetry_missing:total_rss_mb",
        ),
        (
            CanaryObservations(
                max_slot_rss_mb=100.0,
                total_rss_mb=math.inf,
                fd_open_per_slot=10,
                errors=0,
                total_requests=10,
            ),
            "invalid_metric:total_rss_mb",
        ),
        (
            CanaryObservations(
                max_slot_rss_mb=100.0,
                total_rss_mb=200.0,
                fd_open_per_slot=None,
                errors=0,
                total_requests=10,
            ),
            "telemetry_missing:fd_open_per_slot",
        ),
        (
            CanaryObservations(
                max_slot_rss_mb=100.0,
                total_rss_mb=200.0,
                fd_open_per_slot=-1,
                errors=0,
                total_requests=10,
            ),
            "invalid_metric:fd_open_per_slot",
        ),
        (
            CanaryObservations(
                max_slot_rss_mb=100.0,
                total_rss_mb=200.0,
                fd_open_per_slot=10,
                errors=None,
                total_requests=10,
            ),
            "telemetry_missing:error_rate",
        ),
        (
            CanaryObservations(
                max_slot_rss_mb=100.0,
                total_rss_mb=200.0,
                fd_open_per_slot=10,
                errors=1,
                total_requests=None,
            ),
            "telemetry_missing:error_rate",
        ),
        (
            CanaryObservations(
                max_slot_rss_mb=100.0,
                total_rss_mb=200.0,
                fd_open_per_slot=10,
                errors=1,
                total_requests=0,
            ),
            "invalid_metric:error_rate",
        ),
        (
            CanaryObservations(
                max_slot_rss_mb=100.0,
                total_rss_mb=200.0,
                fd_open_per_slot=10,
                errors=1,
                total_requests=-5,
            ),
            "invalid_metric:error_rate",
        ),
        (
            CanaryObservations(
                max_slot_rss_mb=100.0,
                total_rss_mb=200.0,
                fd_open_per_slot=10,
                errors=0,
                total_requests=10,
                fd_leak_detected="false",  # type: ignore[arg-type]
            ),
            "invalid_metric:fd_leak_detected",
        ),
    ],
)
def test_canary_stop_reasons_fail_closed_and_invalid_metrics(
    obs: CanaryObservations,
    expected_reason: str,
) -> None:
    """Отсутствующие/неконечные метрики и не-bool fd_leak_detected дают fail-closed отказ."""
    assert canary_stop_reasons(obs) == [expected_reason]


def test_canary_stop_reasons_respects_fd_leak_stop_disabled() -> None:
    """При fd_leak_stop=False утечка FD не добавляет причину остановки."""
    cfg = AgyResidentCanaryConfig(fd_leak_stop=False)
    obs = CanaryObservations(
        max_slot_rss_mb=100.0,
        total_rss_mb=200.0,
        fd_open_per_slot=10,
        errors=0,
        total_requests=10,
        fd_leak_detected=True,
    )
    assert canary_stop_reasons(obs, config=cfg) == []


def test_load_agy_canary_config_and_apply_limits() -> None:
    """load_agy_canary_config парсит AGY_CANARY_*, а apply_canary_limits клампит без мутации."""
    default_canary = load_agy_canary_config({})
    assert default_canary == AgyResidentCanaryConfig()

    baseline_canary = load_agy_canary_config({"AGY_CANARY_BASELINE": "1"})
    assert baseline_canary.max_slots == baseline_canary.baseline_max_slots == 2

    custom_canary = load_agy_canary_config(
        {
            "AGY_CANARY_BASELINE_MAX_SLOTS": "3",
            "AGY_CANARY_MAX_SLOTS": "6",
            "AGY_CANARY_RSS_CEILING_PER_SLOT_MB": "256",
            "AGY_CANARY_RSS_CEILING_TOTAL_MB": "1536",
            "AGY_CANARY_FD_LIMIT_PER_SLOT": "128",
            "AGY_CANARY_ERROR_RATE_STOP_PCT": "2.5",
            "AGY_CANARY_FD_LEAK_STOP": "false",
        }
    )
    assert custom_canary.max_slots == 6
    assert custom_canary.rss_ceiling_per_slot_mb == 256
    assert custom_canary.fd_leak_stop is False

    base_cfg = AgyResidentConfig(enabled=True, max_slots=8, max_rss_mb=1024)
    clamped = apply_canary_limits(base_cfg, custom_canary)
    assert clamped is not base_cfg
    assert clamped.max_slots == 6
    assert clamped.max_rss_mb == 256
    assert base_cfg.max_slots == 8
    assert base_cfg.max_rss_mb == 1024

    clamped_baseline = apply_canary_limits(
        base_cfg, custom_canary, env={"AGY_CANARY_BASELINE": "1"}
    )
    assert clamped_baseline.max_slots == 3


def test_check_rss_metric_returns_none_and_checks_bounds() -> None:
    """Прямой вызов _check_rss_metric всегда возвращает None и фиксирует невалидные входы."""
    reasons_missing: list[str] = []
    assert (
        canary_mod._check_rss_metric(
            None, "max_slot_rss_mb", 300, "rss_per_slot_exceeded", reasons_missing
        )
        is None
    )
    assert reasons_missing == ["telemetry_missing:max_slot_rss_mb"]

    reasons_invalid: list[str] = []
    assert (
        canary_mod._check_rss_metric(
            math.inf,
            "max_slot_rss_mb",
            300,
            "rss_per_slot_exceeded",
            reasons_invalid,
        )
        is None
    )
    assert reasons_invalid == ["invalid_metric:max_slot_rss_mb"]

    reasons_negative: list[str] = []
    assert (
        canary_mod._check_rss_metric(
            -1.0,
            "max_slot_rss_mb",
            300,
            "rss_per_slot_exceeded",
            reasons_negative,
        )
        is None
    )
    assert reasons_negative == ["invalid_metric:max_slot_rss_mb"]

    reasons_ok: list[str] = []
    assert (
        canary_mod._check_rss_metric(
            100.0, "max_slot_rss_mb", 300, "rss_per_slot_exceeded", reasons_ok
        )
        is None
    )
    assert reasons_ok == []


def test_agy_config_fallback_import_adds_bridge_dir_to_sys_path() -> None:
    """Fallback-импорт agy_config добавляет _BRIDGE_DIR в sys.path и импортирует конфиг.

    Исполняет исходник модуля в изолированном namespace (без importlib.reload),
    чтобы не подменять объект модуля в sys.modules и не ломать identity классов
    для других тестов.
    """
    orig_sys_path = list(sys.path)
    saved_agy_modules = {
        name: mod
        for name, mod in sys.modules.items()
        if name == "agy_runtime" or name.startswith("agy_runtime.")
    }
    source = Path(agy_config_mod.__file__).read_text(encoding="utf-8")
    try:
        for name in saved_agy_modules:
            sys.modules.pop(name, None)
        sys.path[:] = [p for p in orig_sys_path if "bridges/agy-bridge" not in p]
        namespace: dict[str, object] = {
            "__name__": "adapters.stdio_drivers.agy_config",
            "__file__": str(agy_config_mod.__file__),
        }
        exec(compile(source, str(agy_config_mod.__file__), "exec"), namespace)
        assert namespace.get("AgyResidentCanaryConfig") is not None
        assert any("bridges/agy-bridge" in p for p in sys.path)
    finally:
        sys.path[:] = orig_sys_path
        for name in list(sys.modules):
            if name == "agy_runtime" or name.startswith("agy_runtime."):
                sys.modules.pop(name, None)
        sys.modules.update(saved_agy_modules)
