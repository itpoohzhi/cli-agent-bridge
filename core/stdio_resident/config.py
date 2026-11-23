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
    max_slots_per_principal: int | None = None
    max_ephemeral_slots: int = 2
    handshake_timeout_s: float = 30.0
    turn_idle_timeout_s: float = 180.0
    turn_total_timeout_s: float = 600.0
    max_turn_output_bytes: int = 4194304
    rss_check_interval_s: float = 10.0
    leave_timeout_s: float = 2.0
    reap_interval_s: float = 5.0

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
        "lease_wait_s": _S(("BRIDGE_STDIO_LEASE_WAIT_S",), 30.0, 0.1, 600.0),
        "cancel_grace_s": _S(("BRIDGE_STDIO_CANCEL_GRACE_S",), 5.0, 0.1, 60.0),
        "shutdown_timeout_s": _S(
            ("BRIDGE_STDIO_SHUTDOWN_TIMEOUT_S",), 10.0, 0.5, 120.0
        ),
        "max_slots_per_principal": _S(
            ("BRIDGE_STDIO_MAX_SLOTS_PER_PRINCIPAL",), 0, 0, 64, integer=True
        ),
        "max_ephemeral_slots": _S(
            ("BRIDGE_STDIO_MAX_EPHEMERAL_SLOTS",), 2, 1, 64, integer=True
        ),
        "handshake_timeout_s": _S(
            ("BRIDGE_STDIO_HANDSHAKE_TIMEOUT_S",), 30.0, 0.01, 3600.0
        ),
        "turn_idle_timeout_s": _S(
            ("BRIDGE_STDIO_TURN_IDLE_TIMEOUT_S",), 180.0, 0.01, 86400.0
        ),
        "turn_total_timeout_s": _S(
            ("BRIDGE_STDIO_TURN_TOTAL_TIMEOUT_S",), 600.0, 0.01, 86400.0
        ),
        "max_turn_output_bytes": _S(
            ("BRIDGE_STDIO_MAX_TURN_OUTPUT_BYTES",),
            4194304,
            1024,
            math.inf,
            integer=True,
        ),
        "rss_check_interval_s": _S(
            ("BRIDGE_STDIO_RSS_CHECK_INTERVAL_S",), 10.0, 0.01, 3600.0
        ),
        "leave_timeout_s": _S(
            ("BRIDGE_MUSE_LEAVE_TIMEOUT_S", "BRIDGE_STDIO_LEAVE_TIMEOUT_S"),
            2.0,
            0.01,
            300.0,
        ),
        "reap_interval_s": _S(
            ("BRIDGE_STDIO_REAP_INTERVAL_S",), 5.0, 0.01, 3600.0
        ),
    }

    def __post_init__(self) -> None:
        """Normalize max_slots_per_principal to [1, min(max_slots, 64)]."""
        raw = self.max_slots_per_principal
        upper = max(1, min(self.max_slots, 64))
        if raw is None or raw <= 0:
            normalized = upper
        else:
            normalized = max(1, min(raw, upper))
        object.__setattr__(self, "max_slots_per_principal", normalized)

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> StdioPoolConfig:
        """Build a validated snapshot from an environment mapping."""

        env = os.environ if environ is None else environ
        enabled = (
            flag_enabled(FLAG_RESIDENT_ENABLED)
            if environ is None
            else env_bool(env, (FLAG_RESIDENT_ENABLED,), False)
        )
        max_slots = cast(int, parse_number(env, cls._SPECS["max_slots"]))
        raw_per_principal = cast(
            int, parse_number(env, cls._SPECS["max_slots_per_principal"])
        )
        max_slots_per_principal = (
            max_slots if raw_per_principal <= 0 else min(raw_per_principal, max_slots)
        )
        return cls(
            max_slots=max_slots,
            idle_timeout_s=cast(float, parse_number(env, cls._SPECS["idle_timeout_s"])),
            ttl_s=cast(float, parse_number(env, cls._SPECS["ttl_s"])),
            max_rss_bytes=cast(int, parse_number(env, cls._SPECS["max_rss_bytes"])),
            lease_wait_s=cast(float, parse_number(env, cls._SPECS["lease_wait_s"])),
            cancel_grace_s=cast(float, parse_number(env, cls._SPECS["cancel_grace_s"])),
            shutdown_timeout_s=cast(
                float, parse_number(env, cls._SPECS["shutdown_timeout_s"])
            ),
            enabled=enabled,
            max_slots_per_principal=max_slots_per_principal,
            max_ephemeral_slots=cast(
                int, parse_number(env, cls._SPECS["max_ephemeral_slots"])
            ),
            handshake_timeout_s=cast(
                float, parse_number(env, cls._SPECS["handshake_timeout_s"])
            ),
            turn_idle_timeout_s=cast(
                float, parse_number(env, cls._SPECS["turn_idle_timeout_s"])
            ),
            turn_total_timeout_s=cast(
                float, parse_number(env, cls._SPECS["turn_total_timeout_s"])
            ),
            max_turn_output_bytes=cast(
                int, parse_number(env, cls._SPECS["max_turn_output_bytes"])
            ),
            rss_check_interval_s=cast(
                float, parse_number(env, cls._SPECS["rss_check_interval_s"])
            ),
            leave_timeout_s=cast(
                float, parse_number(env, cls._SPECS["leave_timeout_s"])
            ),
            reap_interval_s=cast(
                float, parse_number(env, cls._SPECS["reap_interval_s"])
            ),
        )
