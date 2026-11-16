"""Environment-backed configuration for the resident stdio pool."""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar, cast

from core.runtime_env import NumSpec, env_bool, flag_enabled, parse_number

FLAG_RESIDENT_ENABLED = "BRIDGE_STDIO_RESIDENT_ENABLED"

_S = NumSpec


@dataclass(frozen=True)
class StdioPoolConfig:
    """Validated runtime limits for resident stdio process slots."""

    max_slots: int = 4
    idle_timeout_s: float = 300.0
    ttl_s: float = 3600.0
    max_rss_bytes: int = 1024 * 1024 * 1024
    lease_wait_s: float = 30.0
    cancel_grace_s: float = 5.0
    shutdown_timeout_s: float = 10.0
    enabled: bool = False

    _SPECS: ClassVar[dict[str, NumSpec]] = {
        "max_slots": _S(("BRIDGE_STDIO_MAX_SLOTS",), 4, 1, 64, integer=True),
        "idle_timeout_s": _S(("BRIDGE_STDIO_IDLE_TIMEOUT_S",), 300.0, 1.0, 86400.0),
        "ttl_s": _S(("BRIDGE_STDIO_TTL_S",), 3600.0, 10.0, 86400.0),
        "max_rss_bytes": _S(
            ("BRIDGE_STDIO_MAX_RSS_BYTES",),
            1024 * 1024 * 1024,
            50 * 1024 * 1024,
            math.inf,
            integer=True,
        ),
        "lease_wait_s": _S(("BRIDGE_STDIO_LEASE_WAIT_S",), 30.0, 0.1, 300.0),
        "cancel_grace_s": _S(("BRIDGE_STDIO_CANCEL_GRACE_S",), 5.0, 0.1, 60.0),
        "shutdown_timeout_s": _S(
            ("BRIDGE_STDIO_SHUTDOWN_TIMEOUT_S",), 10.0, 0.5, 120.0
        ),
    }

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> StdioPoolConfig:
        """Build a validated snapshot from an environment mapping."""

        env = os.environ if environ is None else environ
        enabled = (
            flag_enabled(FLAG_RESIDENT_ENABLED)
            if environ is None
            else env_bool(env, (FLAG_RESIDENT_ENABLED,), False)
        )
        return cls(
            max_slots=cast(int, parse_number(env, cls._SPECS["max_slots"])),
            idle_timeout_s=cast(float, parse_number(env, cls._SPECS["idle_timeout_s"])),
            ttl_s=cast(float, parse_number(env, cls._SPECS["ttl_s"])),
            max_rss_bytes=cast(int, parse_number(env, cls._SPECS["max_rss_bytes"])),
            lease_wait_s=cast(float, parse_number(env, cls._SPECS["lease_wait_s"])),
            cancel_grace_s=cast(float, parse_number(env, cls._SPECS["cancel_grace_s"])),
            shutdown_timeout_s=cast(
                float, parse_number(env, cls._SPECS["shutdown_timeout_s"])
            ),
            enabled=enabled,
        )
