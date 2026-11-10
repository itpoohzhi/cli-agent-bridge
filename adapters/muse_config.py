"""Configuration for the muse bridge timeouts and proxy routing."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass

DEFAULT_PROXY_PORT = 10820


def _valid_port(value) -> int | None:
    if value is None:
        return None
    try:
        port = int(value)
    except (TypeError, ValueError):
        return None
    if 1 <= port <= 65535:
        return port
    return None


def resolve_proxy_port(config=None) -> int:
    """Resolve proxy port.

    Resolution order (REQ-001 / RW-011):
    1. Explicit backend config (dict key or attribute) has highest priority.
    2. MUSE_PROXY_PORT env var.
    3. DE_NODE_PROXY_PORT env var.
    4. DEFAULT_PROXY_PORT (10820).
    """
    cfg_port = None
    if config is not None:
        if isinstance(config, dict):
            cfg_port = config.get("proxy_port")
        else:
            cfg_port = getattr(config, "proxy_port", None)
    port = _valid_port(cfg_port)
    if port is not None:
        return port

    port = _valid_port(os.environ.get("MUSE_PROXY_PORT"))
    if port is not None:
        return port

    port = _valid_port(os.environ.get("DE_NODE_PROXY_PORT"))
    if port is not None:
        return port

    return DEFAULT_PROXY_PORT


def _to_float(value, default: float) -> float:
    if value is None or str(value).strip() == "":
        return default
    try:
        val = float(value)
        return val if val > 0.0 and math.isfinite(val) else default
    except (TypeError, ValueError):
        return default


def _to_int(value, default: int) -> int:
    if value is None or str(value).strip() == "":
        return default
    try:
        val = int(value)
        return val if val > 0 else default
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class MuseTimeouts:
    stream_write_timeout_s: float = 30.0
    live_write_timeout_s: float = 30.0
    control_write_timeout_s: float = 15.0
    writes_queue_max: int = 128
    writes_queue_put_timeout_s: float = 5.0


def get_muse_timeouts() -> MuseTimeouts:
    return MuseTimeouts(
        stream_write_timeout_s=_to_float(
            os.environ.get("MUSE_STREAM_WRITE_TIMEOUT_S"), 30.0
        ),
        live_write_timeout_s=_to_float(
            os.environ.get("MUSE_LIVE_WRITE_TIMEOUT_S"), 30.0
        ),
        control_write_timeout_s=_to_float(
            os.environ.get("MUSE_CONTROL_WRITE_TIMEOUT_S"), 15.0
        ),
        writes_queue_max=_to_int(os.environ.get("MUSE_WRITES_QUEUE_MAX"), 128),
        writes_queue_put_timeout_s=_to_float(
            os.environ.get("MUSE_WRITES_QUEUE_PUT_TIMEOUT_S"), 5.0
        ),
    )
