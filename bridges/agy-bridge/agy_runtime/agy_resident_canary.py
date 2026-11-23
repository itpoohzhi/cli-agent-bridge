"""Канареечная конфигурация включения AGY_RESIDENT_ENABLED и чистая проверка стоп-условий.

Параметры модуля — предварительные, некалиброванные, калибруются по базовому тесту
max_slots=2, утверждаются владельцем/Советом перед выкатом.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

__all__ = [
    "AgyResidentCanaryConfig",
    "canary_stop_reasons",
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


def rollback_plan() -> list[str]:
    """Вернуть команды отката канареечного включения AGY_RESIDENT_ENABLED без исполнения."""
    return [
        "AGY_RESIDENT_ENABLED=false",
        "launchctl kickstart -k gui/$(id -u)/com.user.dsh-hub",
    ]


def _read_float(
    observations: Mapping[str, object], keys: tuple[str, ...]
) -> tuple[str, float] | None:
    """Прочитать первое присутствующее числовое наблюдение по набору ключей."""
    for key in keys:
        if key not in observations:
            continue
        raw = observations[key]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            return key, math.nan
        return key, float(raw)
    return None


def canary_stop_reasons(
    observations: Mapping[str, object],
    config: AgyResidentCanaryConfig | None = None,
) -> list[str]:
    """Оценить словарь наблюдений канарейки и вернуть список причин остановки rollout."""
    cfg = config if config is not None else AgyResidentCanaryConfig()
    cfg.validate()
    reasons: list[str] = []

    slot_rss = _read_float(
        observations, ("max_slot_rss_mb", "rss_per_slot_mb", "slot_rss_mb")
    )
    if slot_rss is not None:
        key, val = slot_rss
        if not math.isfinite(val):
            reasons.append(f"invalid_metric:{key}")
        elif val > cfg.rss_ceiling_per_slot_mb:
            reasons.append(
                f"rss_per_slot_exceeded: {val:.1f} MiB > {cfg.rss_ceiling_per_slot_mb} MiB"
            )

    total_rss = _read_float(observations, ("total_rss_mb", "rss_total_mb"))
    if total_rss is not None:
        key, val = total_rss
        if not math.isfinite(val):
            reasons.append(f"invalid_metric:{key}")
        elif val > cfg.rss_ceiling_total_mb:
            reasons.append(
                f"rss_total_exceeded: {val:.1f} MiB > {cfg.rss_ceiling_total_mb} MiB"
            )

    err_rate = _read_float(observations, ("error_rate_pct", "error_rate"))
    if (
        err_rate is None
        and "errors" in observations
        and "total_requests" in observations
    ):
        errs = _read_float(observations, ("errors",))
        reqs = _read_float(observations, ("total_requests",))
        if (
            errs is not None
            and reqs is not None
            and math.isfinite(errs[1])
            and math.isfinite(reqs[1])
            and reqs[1] > 0.0
        ):
            err_rate = ("error_rate_pct", (errs[1] / reqs[1]) * 100.0)
    if err_rate is not None:
        key, val = err_rate
        if not math.isfinite(val):
            reasons.append(f"invalid_metric:{key}")
        elif val > cfg.error_rate_stop_pct:
            reasons.append(
                f"error_rate_exceeded: {val:.2f}% > {cfg.error_rate_stop_pct:.2f}%"
            )

    if cfg.fd_leak_stop:
        if bool(observations.get("fd_leak")) or bool(
            observations.get("fd_leak_detected")
        ):
            reasons.append("fd_leak_detected")
        slot_fds = _read_float(
            observations, ("max_slot_fds", "fd_per_slot", "fds_per_slot")
        )
        if slot_fds is not None:
            key, val = slot_fds
            if not math.isfinite(val):
                reasons.append(f"invalid_metric:{key}")
            elif val > cfg.fd_limit_per_slot:
                reasons.append(
                    f"fd_limit_exceeded: {int(val)} > {cfg.fd_limit_per_slot}"
                )

    return reasons
