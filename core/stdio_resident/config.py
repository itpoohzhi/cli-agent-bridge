"""Environment-backed configuration for the resident stdio pool."""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar, cast

from core.runtime_env import NumSpec, env_bool, flag_enabled, parse_number

FLAG_RESIDENT_ENABLED = "BRIDGE_STDIO_RESIDENT_ENABLED"
FLAG_MCP_TOOL_CAPTURE_ENABLED = "BRIDGE_STDIO_MCP_TOOL_CAPTURE_ENABLED"
FLAG_SUPPRESS_BUILTIN_TOOLS_ENABLED = "BRIDGE_STDIO_SUPPRESS_BUILTIN_TOOLS_ENABLED"
FLAG_CLEAN_CLI_HOME_ENABLED = "BRIDGE_STDIO_CLEAN_CLI_HOME_ENABLED"
ENV_CLEAN_CLI_HOME_ROOT = "BRIDGE_STDIO_CLEAN_CLI_HOME_ROOT"

_S = NumSpec


def _read_flag(flag: str, environ: Mapping[str, str] | None = None) -> bool:
    return flag_enabled(flag) if environ is None else env_bool(environ, (flag,), False)


def mcp_tool_capture_enabled(environ: Mapping[str, str] | None = None) -> bool:
    """Return whether resident MCP tool capture is enabled."""
    return _read_flag(FLAG_MCP_TOOL_CAPTURE_ENABLED, environ)


def suppress_builtin_tools_enabled(environ: Mapping[str, str] | None = None) -> bool:
    """Return whether resident built-in tool suppression is enabled."""
    return _read_flag(FLAG_SUPPRESS_BUILTIN_TOOLS_ENABLED, environ)


def clean_cli_home_enabled(environ: Mapping[str, str] | None = None) -> bool:
    """Return whether clean CLI home isolation is enabled."""
    return _read_flag(FLAG_CLEAN_CLI_HOME_ENABLED, environ)


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
    turn_idle_timeout_s: float = 600.0
    turn_total_timeout_s: float = 1800.0
    max_turn_output_bytes: int = 4194304
    rss_check_interval_s: float = 10.0
    leave_timeout_s: float = 2.0
    reap_interval_s: float = 5.0
    mcp_tool_capture_enabled: bool = False
    suppress_builtin_tools_enabled: bool = False
    clean_cli_home_enabled: bool = False
    clean_cli_home_root: str = ""
    mcp_cancel_wait_s: float = 2.0
    mcp_coalesce_ms: int = 25
    mcp_max_request_bytes: int = 1048576

    _SPECS: ClassVar[dict[str, NumSpec]] = {
        "max_slots": _S(("BRIDGE_STDIO_MAX_SLOTS",), 4, 1, 64, integer=True),
        "idle_timeout_s": _S(("BRIDGE_STDIO_IDLE_TIMEOUT_S",), 300.0, 1.0, 86400.0),
        "ttl_s": _S(("BRIDGE_STDIO_TTL_S",), 3600.0, 10.0, 86400.0),
        "max_rss_bytes": _S(
            ("BRIDGE_STDIO_MAX_RSS_BYTES",), 1024 * 1024 * 1024, 50 * 1024 * 1024, math.inf, integer=True
        ),
        "lease_wait_s": _S(("BRIDGE_STDIO_LEASE_WAIT_S",), 30.0, 0.1, 600.0),
        "cancel_grace_s": _S(("BRIDGE_STDIO_CANCEL_GRACE_S",), 5.0, 0.1, 60.0),
        "shutdown_timeout_s": _S(("BRIDGE_STDIO_SHUTDOWN_TIMEOUT_S",), 10.0, 0.5, 120.0),
        "max_slots_per_principal": _S(
            ("BRIDGE_STDIO_MAX_SLOTS_PER_PRINCIPAL",), 0, 0, 64, integer=True
        ),
        "max_ephemeral_slots": _S(("BRIDGE_STDIO_MAX_EPHEMERAL_SLOTS",), 2, 1, 64, integer=True),
        "handshake_timeout_s": _S(("BRIDGE_STDIO_HANDSHAKE_TIMEOUT_S",), 30.0, 0.01, 3600.0),
        "turn_idle_timeout_s": _S(("BRIDGE_STDIO_TURN_IDLE_TIMEOUT_S",), 600.0, 0.01, 86400.0),
        "turn_total_timeout_s": _S(("BRIDGE_STDIO_TURN_TOTAL_TIMEOUT_S",), 1800.0, 0.01, 86400.0),
        "max_turn_output_bytes": _S(
            ("BRIDGE_STDIO_MAX_TURN_OUTPUT_BYTES",), 4194304, 1024, math.inf, integer=True
        ),
        "rss_check_interval_s": _S(("BRIDGE_STDIO_RSS_CHECK_INTERVAL_S",), 10.0, 0.01, 3600.0),
        "leave_timeout_s": _S(
            ("BRIDGE_MUSE_LEAVE_TIMEOUT_S", "BRIDGE_STDIO_LEAVE_TIMEOUT_S"), 2.0, 0.01, 300.0
        ),
        "reap_interval_s": _S(("BRIDGE_STDIO_REAP_INTERVAL_S",), 5.0, 0.01, 3600.0),
        "mcp_cancel_wait_s": _S(("BRIDGE_STDIO_MCP_CANCEL_WAIT_S",), 2.0, 0.05, 60.0),
        "mcp_coalesce_ms": _S(("BRIDGE_STDIO_MCP_COALESCE_MS",), 25, 0, 5000, integer=True),
        "mcp_max_request_bytes": _S(
            ("BRIDGE_STDIO_MCP_MAX_REQUEST_BYTES",), 1048576, 4096, 16777216, integer=True
        ),
    }

    def __post_init__(self) -> None:
        """Normalize max_slots_per_principal to [1, min(max_slots, 64)]."""
        raw = self.max_slots_per_principal
        upper = max(1, min(self.max_slots, 64))
        normalized = upper if raw is None or raw <= 0 else max(1, min(raw, upper))
        object.__setattr__(self, "max_slots_per_principal", normalized)

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> StdioPoolConfig:
        """Build a validated snapshot from an environment mapping."""
        env = os.environ if environ is None else environ

        def _i(key: str) -> int:
            return cast(int, parse_number(env, cls._SPECS[key]))

        def _f(key: str) -> float:
            return cast(float, parse_number(env, cls._SPECS[key]))

        max_slots = _i("max_slots")
        raw_per_principal = _i("max_slots_per_principal")
        return cls(
            max_slots=max_slots,
            idle_timeout_s=_f("idle_timeout_s"),
            ttl_s=_f("ttl_s"),
            max_rss_bytes=_i("max_rss_bytes"),
            lease_wait_s=_f("lease_wait_s"),
            cancel_grace_s=_f("cancel_grace_s"),
            shutdown_timeout_s=_f("shutdown_timeout_s"),
            enabled=_read_flag(FLAG_RESIDENT_ENABLED, environ),
            max_slots_per_principal=(
                max_slots if raw_per_principal <= 0 else min(raw_per_principal, max_slots)
            ),
            max_ephemeral_slots=_i("max_ephemeral_slots"),
            handshake_timeout_s=_f("handshake_timeout_s"),
            turn_idle_timeout_s=_f("turn_idle_timeout_s"),
            turn_total_timeout_s=_f("turn_total_timeout_s"),
            max_turn_output_bytes=_i("max_turn_output_bytes"),
            rss_check_interval_s=_f("rss_check_interval_s"),
            leave_timeout_s=_f("leave_timeout_s"),
            reap_interval_s=_f("reap_interval_s"),
            mcp_tool_capture_enabled=_read_flag(FLAG_MCP_TOOL_CAPTURE_ENABLED, environ),
            suppress_builtin_tools_enabled=_read_flag(FLAG_SUPPRESS_BUILTIN_TOOLS_ENABLED, environ),
            clean_cli_home_enabled=_read_flag(FLAG_CLEAN_CLI_HOME_ENABLED, environ),
            clean_cli_home_root=str(env.get(ENV_CLEAN_CLI_HOME_ROOT) or "").strip(),
            mcp_cancel_wait_s=_f("mcp_cancel_wait_s"),
            mcp_coalesce_ms=_i("mcp_coalesce_ms"),
            mcp_max_request_bytes=_i("mcp_max_request_bytes"),
        )
