from __future__ import annotations

"""Канареечная конфигурация включения AGY_RESIDENT_ENABLED и чистая проверка стоп-условий.

Параметры модуля — предварительные, некалиброванные, калибруются по базовому тесту
max_slots=2, утверждаются владельцем/Советом перед выкатом.
"""

import math  # noqa: E402
from collections.abc import Mapping  # noqa: E402
from dataclasses import dataclass, replace  # noqa: E402
from typing import TYPE_CHECKING  # noqa: E402

if TYPE_CHECKING:
    from .agy_config import AgyResidentConfig

LAUNCHD_SERVICE_LABEL = "gui/$(id -u)/com.user.dsh-hub"

__all__ = [
    "LAUNCHD_SERVICE_LABEL",
    "AgyResidentCanaryConfig",
    "CanaryObservations",
    "apply_canary_limits",
    "canary_stop_reasons",
    "load_agy_canary_config",
    "rollback_plan",
]


@dataclass(frozen=True)
class AgyResidentCanaryConfig:
    """Пороги канарейки AGY_RESIDENT_ENABLED.

    Параметры предварительные, некалиброванные, калибруются по базовому тесту
    max_slots=2, утверждаются владельцем/Советом перед выкатом.
    """

    baseline_max_slots: int = 2
    max_slots: int = 10
    rss_ceiling_per_slot_mb: int = 300
    rss_ceiling_total_mb: int = 3000
    fd_limit_per_slot: int = 256
    error_rate_stop_pct: float = 5.0
    fd_leak_stop: bool = True

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Fail-closed проверка инвариантов канареечного конфига."""
        int_fields = (
            ("baseline_max_slots", self.baseline_max_slots),
            ("max_slots", self.max_slots),
            ("rss_ceiling_per_slot_mb", self.rss_ceiling_per_slot_mb),
            ("rss_ceiling_total_mb", self.rss_ceiling_total_mb),
            ("fd_limit_per_slot", self.fd_limit_per_slot),
        )
        for name, value in int_fields:
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive int, got {value!r}")
        if self.baseline_max_slots > self.max_slots:
            raise ValueError(
                f"baseline_max_slots ({self.baseline_max_slots}) must be <= max_slots ({self.max_slots})"
            )
        if self.rss_ceiling_total_mb < self.rss_ceiling_per_slot_mb:
            raise ValueError("rss_ceiling_total_mb must be >= rss_ceiling_per_slot_mb")
        if (
            isinstance(self.error_rate_stop_pct, bool)
            or not isinstance(self.error_rate_stop_pct, (int, float))
            or not math.isfinite(float(self.error_rate_stop_pct))
            or self.error_rate_stop_pct <= 0.0
            or self.error_rate_stop_pct > 100.0
        ):
            raise ValueError(
                f"error_rate_stop_pct must be in (0, 100], got {self.error_rate_stop_pct!r}"
            )
        if not isinstance(self.fd_leak_stop, bool):
            raise ValueError(f"fd_leak_stop must be a bool, got {self.fd_leak_stop!r}")


@dataclass(frozen=True)
class CanaryObservations:
    """Типизированные наблюдения канарейки для fail-closed проверки стоп-условий."""

    max_slot_rss_mb: float | None = None
    total_rss_mb: float | None = None
    fd_open_per_slot: int | None = None
    errors: int | None = None
    total_requests: int | None = None
    fd_leak_detected: bool = False


def rollback_plan() -> list[str]:
    """Вернуть команды отката AGY_RESIDENT_ENABLED без исполнения.

    Выполняет сессионный откат GUI-сессии launchd; authoritative-источник —
    EnvironmentVariables plist (для PlistBuddy Set ключ
    :EnvironmentVariables:AGY_RESIDENT_ENABLED должен существовать в plist).
    """
    return [
        "launchctl setenv AGY_RESIDENT_ENABLED false",
        (
            "/usr/libexec/PlistBuddy -c 'Set :EnvironmentVariables:AGY_RESIDENT_ENABLED false' "
            '"$HOME/Library/LaunchAgents/com.user.dsh-hub.plist"'
        ),
        f"launchctl kickstart -k {LAUNCHD_SERVICE_LABEL}",
        (
            'sh -c \'pids=$(pgrep -f "[b]ridges/agy-bridge/server.py"); '
            'test -n "$pids" || { echo "ROLLBACK_VERIFY_FAILED: no server process"; exit 1; }; '
            'for pid in $pids; do ps eww "$pid" | tr " " "\\n" '
            '| grep -q "^AGY_RESIDENT_ENABLED=false" '
            '|| { echo "ROLLBACK_VERIFY_FAILED pid=$pid"; rc=1; }; '
            "done; exit ${rc:-0}'"
        ),
    ]


def load_agy_canary_config(env: Mapping[str, str]) -> AgyResidentCanaryConfig:
    """Загрузить канареечные пороги `AGY_CANARY_*` из явного окружения без `os.environ`."""
    from .agy_config import _parse_bool, _parse_num

    d, p = AgyResidentCanaryConfig(), _parse_num
    baseline_max_slots = p(
        env, "AGY_CANARY_BASELINE_MAX_SLOTS", int, d.baseline_max_slots
    )
    max_slots = p(env, "AGY_CANARY_MAX_SLOTS", int, d.max_slots)
    rss_per_slot = p(
        env, "AGY_CANARY_RSS_CEILING_PER_SLOT_MB", int, d.rss_ceiling_per_slot_mb
    )
    rss_total = p(env, "AGY_CANARY_RSS_CEILING_TOTAL_MB", int, d.rss_ceiling_total_mb)
    fd_limit = p(env, "AGY_CANARY_FD_LIMIT_PER_SLOT", int, d.fd_limit_per_slot)
    error_rate_stop = p(
        env, "AGY_CANARY_ERROR_RATE_STOP_PCT", float, d.error_rate_stop_pct
    )
    fd_leak_stop = _parse_bool(env, "AGY_CANARY_FD_LEAK_STOP", d.fd_leak_stop)
    is_baseline = _parse_bool(env, "AGY_CANARY_BASELINE", False)
    if is_baseline:
        AgyResidentCanaryConfig(
            baseline_max_slots=baseline_max_slots,
            max_slots=max_slots,
            rss_ceiling_per_slot_mb=rss_per_slot,
            rss_ceiling_total_mb=rss_total,
            fd_limit_per_slot=fd_limit,
            error_rate_stop_pct=error_rate_stop,
            fd_leak_stop=fd_leak_stop,
        )
        max_slots = min(max_slots, baseline_max_slots)
    return AgyResidentCanaryConfig(
        baseline_max_slots=baseline_max_slots,
        max_slots=max_slots,
        rss_ceiling_per_slot_mb=rss_per_slot,
        rss_ceiling_total_mb=rss_total,
        fd_limit_per_slot=fd_limit,
        error_rate_stop_pct=error_rate_stop,
        fd_leak_stop=fd_leak_stop,
    )


def apply_canary_limits(
    cfg: AgyResidentConfig,
    canary: AgyResidentCanaryConfig,
    *,
    baseline: bool = False,
    env: Mapping[str, str] | None = None,
) -> AgyResidentConfig:
    """Клампит лимиты резидентного конфига потолками канарейки и возвращает новый инстанс."""
    cfg.validate()
    canary.validate()
    if env is not None:
        from .agy_config import _parse_bool

        env_baseline = _parse_bool(env, "AGY_CANARY_BASELINE", False)
    else:
        env_baseline = False
    use_baseline = baseline or env_baseline
    slot_cap = canary.baseline_max_slots if use_baseline else canary.max_slots
    return replace(
        cfg,
        max_slots=min(cfg.max_slots, slot_cap),
        max_rss_mb=min(cfg.max_rss_mb, canary.rss_ceiling_per_slot_mb),
    )


def _is_valid_number(value: object) -> bool:
    """Проверить, что значение является конечным числом, а не bool."""
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def _check_rss_metric(
    value: float | None,
    metric_name: str,
    ceiling_mb: int,
    exceeded_label: str,
    reasons: list[str],
) -> None:
    """Fail-closed проверка метрики RSS против заданного потолка в MiB."""
    if value is None:
        reasons.append(f"telemetry_missing:{metric_name}")
        return
    if not _is_valid_number(value) or float(value) < 0.0:
        reasons.append(f"invalid_metric:{metric_name}")
        return
    val = float(value)
    if val > ceiling_mb:
        reasons.append(f"{exceeded_label}: {val:.1f} MiB > {ceiling_mb} MiB")


def canary_stop_reasons(
    obs: CanaryObservations,
    config: AgyResidentCanaryConfig | None = None,
) -> list[str]:
    """Fail-closed оценка типизированных наблюдений канарейки и выдача причин остановки."""
    cfg = config if config is not None else AgyResidentCanaryConfig()
    cfg.validate()
    reasons: list[str] = []

    _check_rss_metric(
        obs.max_slot_rss_mb,
        "max_slot_rss_mb",
        cfg.rss_ceiling_per_slot_mb,
        "rss_per_slot_exceeded",
        reasons,
    )
    _check_rss_metric(
        obs.total_rss_mb,
        "total_rss_mb",
        cfg.rss_ceiling_total_mb,
        "rss_total_exceeded",
        reasons,
    )

    if obs.errors is None or obs.total_requests is None:
        reasons.append("telemetry_missing:error_rate")
    elif (
        not _is_valid_number(obs.errors)
        or not _is_valid_number(obs.total_requests)
        or float(obs.errors) < 0.0
        or float(obs.total_requests) <= 0.0
    ):
        reasons.append("invalid_metric:error_rate")
    else:
        rate_pct = (float(obs.errors) / float(obs.total_requests)) * 100.0
        if rate_pct > cfg.error_rate_stop_pct:
            reasons.append(
                f"error_rate_exceeded: {rate_pct:.2f}% > {cfg.error_rate_stop_pct:.2f}%"
            )

    if obs.fd_open_per_slot is None:
        reasons.append("telemetry_missing:fd_open_per_slot")
    elif not _is_valid_number(obs.fd_open_per_slot) or int(obs.fd_open_per_slot) < 0:
        reasons.append("invalid_metric:fd_open_per_slot")
    elif int(obs.fd_open_per_slot) > cfg.fd_limit_per_slot:
        reasons.append(
            f"fd_limit_exceeded: {int(obs.fd_open_per_slot)} > {cfg.fd_limit_per_slot}"
        )

    if not isinstance(obs.fd_leak_detected, bool):
        reasons.append("invalid_metric:fd_leak_detected")
    elif cfg.fd_leak_stop and obs.fd_leak_detected is True:
        reasons.append("fd_leak_detected")

    return reasons