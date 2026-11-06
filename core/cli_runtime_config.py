"""CLI/non-stream/watchdog config (ADR-0015 AD-004)."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from functools import partial
from typing import Any, ClassVar

from core.liveness_signals import FLAG_SOFT_LIVENESS, LivenessWindow, WindowSpec
from core.runtime_env import NumSpec, env_first, flag_enabled, parse_number

FLAG_NEUTRAL_NAMES = "BRIDGE_CLI_NEUTRAL_NAMES_ENABLED"
LAUNCHER_NAMES = ("BRIDGE_CLI_LAUNCHER", "DROID_LAUNCHER")
_N, _W, _C = "BRIDGE_NONSTREAM_", "BRIDGE_WATCHDOG_", "BRIDGE_CLI_"
_S = NumSpec
_LABELS = {
    "exec": ("droid exec", "cli-exec"), "binary": ("droid", "cli"),
    "no_event": ("no droid event", "no CLI event"), "no_progress": ("no droid progress", "no CLI progress"),
    "completion_prefix": ("chatcmpl-droid-", "chatcmpl-cli-"), "bridge": ("droid-bridge", "cli-agent-bridge"),
}


class _EnvConfig:
    _SPECS: ClassVar[dict[str, NumSpec]]

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Any:
        env = os.environ if environ is None else environ
        return cls(**{name: parse_number(env, spec) for name, spec in cls._SPECS.items()})


@dataclass(frozen=True)
class WatchdogConfig(_EnvConfig):
    idle_timeout_s: float = 300.0
    safety_cap_s: float = 3600.0
    finish_reserve_s: float = 35.0
    interval_s: float = 5.0
    ps_timeout_s: float = 2.0


@dataclass(frozen=True)
class NonstreamConfig(_EnvConfig):
    first_progress_timeout_s: float = 90.0
    idle_timeout_s: float = 300.0
    soft_budget_s: float = 120.0
    min_cpu_delta_s: float = 0.05
    safety_cap_s: float = 3600.0
    poll_interval_s: float = 0.1

    def window_spec(self, process_progress: bool, **overrides: Any) -> WindowSpec:
        base = WindowSpec(self.first_progress_timeout_s, self.idle_timeout_s, self.safety_cap_s, self.soft_budget_s, self.min_cpu_delta_s, process_progress)
        return replace(base, **overrides)

    def cli_window(self, idle_s: float, cap_s: float, first_s: float | None, clock: Callable[[], float]) -> LivenessWindow:
        soft = partial(flag_enabled, FLAG_SOFT_LIVENESS)
        first = self.first_progress_timeout_s if first_s is None else first_s
        spec = self.window_spec(True, first_timeout_s=first if soft() else idle_s, idle_timeout_s=idle_s, safety_cap_s=cap_s)
        return LivenessWindow(spec, clock=clock, soft_enabled=soft)


@dataclass(frozen=True)
class CliRuntimeConfig(_EnvConfig):
    """CLI runner settings (BRIDGE_CLI_*, DROID_* fallback)."""

    first_token_timeout_s: float = 90.0
    live_write_timeout_s: float = 30.0
    silence_watchdog_s: float = 120.0
    rpc_call_timeout_s: float = 60.0
    idle_seconds: float = 2700.0
    max_rpc_line_bytes: int = 8 << 20
    max_stderr_bytes: int = 64 << 10
    max_inbox_bytes: int = 4 << 20
    max_turn_text_bytes: int = 10 << 20
    run_queue_maxsize: int = 1024
    max_json_struct_tokens: int = 50000
    max_delivery_bytes: int = 256 << 20
    max_chats: int = 4096
    launcher: str = ""

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> CliRuntimeConfig:
        env = os.environ if environ is None else environ
        found = env_first(env, LAUNCHER_NAMES)
        return cls(**{k: parse_number(env, s) for k, s in _SPECS.items()}, launcher=found[1] if found else "")


_RANGES = {
    "first_token_timeout_s": (1, 3600), "live_write_timeout_s": (1, 300), "silence_watchdog_s": (1, 3600),
    "rpc_call_timeout_s": (1, 3600), "idle_seconds": (1, 86400), "max_rpc_line_bytes": (1024, 1 << 28),
    "max_stderr_bytes": (1024, 1 << 24), "max_inbox_bytes": (1024, 1 << 28), "max_turn_text_bytes": (1024, 1 << 30),
    "run_queue_maxsize": (1, 65536), "max_json_struct_tokens": (1, 10**7), "max_delivery_bytes": (1 << 20, 1 << 32),
    "max_chats": (1, 65536),
}
_SPECS = {
    k: _S((_C + k.upper(), "DROID_DSH_BRIDGE_IDLE_SECONDS" if k == "idle_seconds" else "DROID_BRIDGE_" + k.upper()),
          getattr(CliRuntimeConfig, k), *r, integer=isinstance(getattr(CliRuntimeConfig, k), int))
    for k, r in _RANGES.items()
}
_NS_SPECS = {
    "first_progress_timeout_s": _S((_N + "FIRST_PROGRESS_TIMEOUT_S",), 90, 1, 3600),
    "idle_timeout_s": _S((_N + "IDLE_TIMEOUT_S", "BRIDGE_IDLE_TIMEOUT_S"), 300, 1, 3600),
    "soft_budget_s": _S((_N + "SOFT_LIVENESS_BUDGET_S",), 120, 0, 3600),
    "min_cpu_delta_s": _S((_N + "SOFT_LIVENESS_MIN_CPU_DELTA_S",), 0.05, 0, 60, low_open=True),
    "safety_cap_s": _S((_N + "SAFETY_CAP_S",), 3600, 1, 86400),
    "poll_interval_s": _S((_N + "POLL_INTERVAL_S", "BRIDGE_PASSTHROUGH_POLL_INTERVAL_S"), 0.1, 0.01, 10),
}
_WD_SPECS = {
    "idle_timeout_s": _S((_W + "IDLE_TIMEOUT_S",), 300, 1, 3600),
    "safety_cap_s": _S((_W + "SAFETY_CAP_S", "DROID_DSH_BRIDGE_SAFETY_CAP_S"), 3600, 1, 86400),
    "finish_reserve_s": _S((_W + "FINISH_RESERVE_S",), 35, 0, 600),
    "interval_s": _S((_W + "INTERVAL_S",), 5, 0.1, 60),
    "ps_timeout_s": _S((_W + "PS_TIMEOUT_S",), 2, 0.1, 60),
}


WatchdogConfig._SPECS, NonstreamConfig._SPECS, CliRuntimeConfig._SPECS = _WD_SPECS, _NS_SPECS, _SPECS


def cli_number(field: str, default: float) -> float:
    return parse_number(os.environ, replace(_SPECS[field], default=default))


def neutral_names_enabled() -> bool:
    return flag_enabled(FLAG_NEUTRAL_NAMES)


def cli_label(key: str) -> str:
    """User-visible label: neutral under the flag, else legacy string."""
    legacy, neutral = _LABELS[key]
    return neutral if neutral_names_enabled() else legacy
