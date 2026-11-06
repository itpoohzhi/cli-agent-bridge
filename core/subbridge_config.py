"""Параметры graceful-drain саб-мостов: единые дефолты и клампинг под `ExitTimeOut` (launchd).

Значения согласованы с `core/lifecycle.py` (`DEFAULT_DRAIN_SECONDS`, `RETRY_AFTER_S`), чтобы
`BRIDGE_DRAIN_TIMEOUT_S` / `BRIDGE_RETRY_AFTER_S` имели одну семантику для хаба и саб-мостов.
Любой эксплуатационный таймаут настраивается переменной окружения, в коде только дефолты.
"""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, fields, replace

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
SHORT_EXIT_TIMEOUT_ENV = "BRIDGE_SHORT_EXIT_TIMEOUT_S"
SHORT_EXIT_TIMEOUT_S = 15.0


def _env_float(env: Mapping[str, str], name: str, default: float) -> float:
    try:
        value = float(str(env.get(name, "")).strip())
    except ValueError:
        return default
    return value if math.isfinite(value) and value > 0 else default


def short_exit_timeout_s(env: Mapping[str, str] | None = None) -> float:
    """Порог короткого `ExitTimeOut`, ниже которого kill-таймеры сжимаются (настраивается env)."""
    source = os.environ if env is None else env
    return _env_float(source, SHORT_EXIT_TIMEOUT_ENV, SHORT_EXIT_TIMEOUT_S)


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

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> SubbridgeDrainConfig:
        source = os.environ if env is None else env
        base = {f.name: float(getattr(cls, f.name)) for f in fields(cls)}
        values = {
            name: _env_float(source, var, base[name]) for name, var in _ENV_VARS.items()
        }
        retry = int(_env_float(source, "BRIDGE_RETRY_AFTER_S", base["retry_after_s"]))
        # Порядок как у хаба: явный флаг саб-моста, затем переменные `HubLifecycleManager`.
        enabled = env_bool(source, _DRAIN_ENABLED_ENV, True)
        # `exit_timeout_s` не растёт вслед за drain: он отражает реальный `ExitTimeOut` launchd,
        # поэтому `effective_drain_timeout_s` клампит удлинённый drain под него.
        return cls(enabled=enabled, retry_after_s=retry, **values)

    @property
    def tail_s(self) -> float:
        """Бюджет после drain: зачистка групп, дозапись кадров и запас до `SIGKILL` от launchd."""
        kill_s = self.kill_term_grace_s + self.kill_wait_s
        return kill_s + self.flush_grace_s + self.safety_margin_s

    def effective_timers(self) -> SubbridgeDrainConfig:
        """Короткий `ExitTimeOut`: `TERM`+`KILL` пропорционально сжимаются, чтобы успеть до `SIGKILL` launchd."""
        cap = max(0.2, (self.exit_timeout_s - self.safety_margin_s) * 0.5)
        k = min(1.0, cap / (self.kill_term_grace_s + self.kill_wait_s))
        if self.exit_timeout_s > short_exit_timeout_s() or k == 1.0:
            return self
        return replace(
            self,
            kill_term_grace_s=self.kill_term_grace_s * k,
            kill_wait_s=self.kill_wait_s * k,
        )

    @property
    def effective_drain_timeout_s(self) -> float:
        """Drain не длиннее `ExitTimeOut` минус бюджет зачистки: launchd не убьёт процесс посреди drain."""
        return min(
            self.drain_timeout_s,
            max(0.05, self.exit_timeout_s - self.effective_timers().tail_s),
        )
