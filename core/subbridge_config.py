"""Параметры graceful-drain саб-мостов: единые дефолты и клампинг под `ExitTimeOut` (launchd).

Значения согласованы с `core/lifecycle.py` (`DEFAULT_DRAIN_SECONDS`, `RETRY_AFTER_S`), чтобы
`BRIDGE_DRAIN_TIMEOUT_S` / `BRIDGE_RETRY_AFTER_S` имели одну семантику для хаба и саб-мостов.
Любой эксплуатационный таймаут настраивается переменной окружения, в коде только дефолты.
"""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, fields

from core.lifecycle import DEFAULT_DRAIN_SECONDS, RETRY_AFTER_S
from core.runtime_env import env_bool

_ENV_VARS = {
    "drain_timeout_s": "BRIDGE_DRAIN_TIMEOUT_S",
    "exit_timeout_s": "BRIDGE_EXIT_TIMEOUT_S",
    "kill_term_grace_s": "BRIDGE_KILL_TERM_GRACE_S",
    "kill_wait_s": "BRIDGE_KILL_WAIT_S",
    "flush_grace_s": "BRIDGE_DRAIN_FLUSH_GRACE_S",
    "poll_interval_s": "BRIDGE_DRAIN_POLL_INTERVAL_S",
    "safety_margin_s": "BRIDGE_DRAIN_SAFETY_MARGIN_S",
}
_DRAIN_ENABLED_ENV = (
    "BRIDGE_ENABLE_GRACEFUL_DRAIN",
    "BRIDGE_DRAIN_ON_SHUTDOWN",
    "DSH_BRIDGE_DRAIN_ENABLED",
)
SHORT_EXIT_TIMEOUT_S = 15.0
SHORT_EXIT_CAPS_S = (
    0.5,
    0.3,
    0.2,
)  # потолки (TERM, KILL, flush) при коротком `ExitTimeOut`
MIN_DRAIN_S, MIN_TAIL_S = 0.05, 0.3  # пол drain и пол бюджета зачистки


def _env_float(
    env: Mapping[str, str], name: str, default: float, allow_zero: bool = False
) -> float:
    try:
        value = float(str(env.get(name, "")).strip())
    except ValueError:
        return default
    ok = value >= 0 if allow_zero else value > 0
    return value if math.isfinite(value) and ok else default


def short_exit_timeout_s(env: Mapping[str, str] | None = None) -> float:
    """Порог короткого `ExitTimeOut`, ниже которого kill-таймеры сжимаются (настраивается env)."""
    source = os.environ if env is None else env
    return _env_float(source, "BRIDGE_SHORT_EXIT_TIMEOUT_S", SHORT_EXIT_TIMEOUT_S)


@dataclass(frozen=True)
class SubbridgeDrainConfig:
    """Параметры drain; дефолты едины с `HubLifecycleManager` (`core/lifecycle.py`)."""

    enabled: bool = True
    drain_timeout_s: float = DEFAULT_DRAIN_SECONDS
    exit_timeout_s: float = 180.0
    retry_after_s: int = RETRY_AFTER_S
    kill_term_grace_s: float = 2.0
    kill_wait_s: float = 3.0
    flush_grace_s: float = 2.0
    poll_interval_s: float = 0.05
    safety_margin_s: float = 5.0
    short_exit_threshold_s: float = SHORT_EXIT_TIMEOUT_S

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> SubbridgeDrainConfig:
        source = os.environ if env is None else env
        base = {f.name: float(getattr(cls, f.name)) for f in fields(cls)}
        values = {
            name: _env_float(source, var, base[name], name == "drain_timeout_s")
            for name, var in _ENV_VARS.items()
        }
        values["short_exit_threshold_s"] = short_exit_timeout_s(source)
        retry = int(_env_float(source, "BRIDGE_RETRY_AFTER_S", base["retry_after_s"]))
        # Порядок как у хаба: явный флаг саб-моста, затем переменные `HubLifecycleManager`.
        enabled = env_bool(source, _DRAIN_ENABLED_ENV, True)
        # `exit_timeout_s` не растёт вслед за drain: он отражает реальный `ExitTimeOut` launchd,
        # поэтому `effective_drain_timeout_s` клампит удлинённый drain под него.
        return cls(enabled=enabled, retry_after_s=retry, **values)

    @property
    def margin_s(self) -> float:
        """Запас до `SIGKILL` от launchd: `safety_margin_s`, но не больше 10% `ExitTimeOut`."""
        return min(self.safety_margin_s, self.exit_timeout_s * 0.1)

    def effective_timers(self) -> tuple[float, float, float]:
        """`(TERM-grace, KILL-wait, flush)`, вмещающиеся в `ExitTimeOut` при ЛЮБЫХ значениях env.

        Короткий `ExitTimeOut` сначала режет каждый таймер до потолка, затем (для любого
        `ExitTimeOut`) хвост пропорционально сжимается до `ExitTimeOut - margin - MIN_DRAIN_S`.
        """
        timers = (self.kill_term_grace_s, self.kill_wait_s, self.flush_grace_s)
        if self.exit_timeout_s <= self.short_exit_threshold_s:
            timers = tuple(min(v, c) for v, c in zip(timers, SHORT_EXIT_CAPS_S))
        max_tail = max(MIN_TAIL_S, self.exit_timeout_s - self.margin_s - MIN_DRAIN_S)
        total = sum(timers)
        k = max_tail / total if total > max_tail else 1.0
        return (timers[0] * k, timers[1] * k, timers[2] * k)

    @property
    def effective_drain_timeout_s(self) -> float:
        """Drain не длиннее `ExitTimeOut` минус хвост и запас: launchd не убьёт процесс посреди drain."""
        if self.drain_timeout_s <= 0:
            return 0.0
        budget = self.exit_timeout_s - sum(self.effective_timers()) - self.margin_s
        return min(self.drain_timeout_s, max(MIN_DRAIN_S, budget))
