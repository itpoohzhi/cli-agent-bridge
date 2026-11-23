from __future__ import annotations

__doc__ = """Тонкий re-export канареечного конфига; реализация перенесена в общий слой."""

from adapters.stdio_drivers.agy_canary import (  # noqa: E402
    LAUNCHD_SERVICE_LABEL,
    AgyResidentCanaryConfig,
    CanaryObservations,
    _check_rss_metric as _check_rss_metric,
    apply_canary_limits,
    canary_stop_reasons,
    load_agy_canary_config,
    rollback_plan,
)

__all__ = [
    "LAUNCHD_SERVICE_LABEL",
    "AgyResidentCanaryConfig",
    "CanaryObservations",
    "apply_canary_limits",
    "canary_stop_reasons",
    "load_agy_canary_config",
    "rollback_plan",
]
