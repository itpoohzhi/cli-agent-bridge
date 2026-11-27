from __future__ import annotations

# Thin kill-switch adapter: ThreadingHTTPServer.handle_error -> pure disconnect policy (P0-S4).
# Flag precedence: dynamic JSON > env > False (fail-closed on JSON/I/O errors).

import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Final

from core.http_disconnect_policy import (
    format_client_disconnect_log,
    should_suppress_disconnect_traceback,
)
from core.log_rotation_adapters import DynamicJsonBoolCache
from core.p12_flag_and_params import resolve_flag

FLAG_SUPPRESS_DISCONNECT_TRACEBACK: Final[str] = (
    "BRIDGE_SUPPRESS_CLIENT_DISCONNECT_TRACEBACK_ENABLED"
)
_CONFIG_PATH_ENV: Final[str] = "BRIDGE_DYNAMIC_CONFIG_PATH"
_DEFAULT_CONFIG_PATH: Final[str] = "~/.config/cli-agent-bridge/dynamic_config.json"

ClientGoneCls = type[BaseException] | tuple[type[BaseException], ...] | None

# Sole mutable module state lives inside this cache instance (no dict/list/set literals here).
_FLAG_CACHE = DynamicJsonBoolCache()


def resolved_config_path(config_path: Path | None) -> str:
    """env BRIDGE_DYNAMIC_CONFIG_PATH wins over config_path; hub default otherwise."""
    raw = (os.environ.get(_CONFIG_PATH_ENV) or "").strip() or (
        _DEFAULT_CONFIG_PATH if config_path is None else str(config_path)
    )
    return os.path.expanduser(raw)


def is_disconnect_suppression_enabled(config_path: Path | None = None) -> bool:
    """Read the kill-switch fail-closed: any JSON/I/O failure resolves to False."""
    doc, invalid = _FLAG_CACHE.read(resolved_config_path(config_path))
    return resolve_flag(
        FLAG_SUPPRESS_DISCONNECT_TRACEBACK, doc, os.environ, json_invalid=invalid
    ).enabled


def handle_accept_error(
    client_address: object,
    log_fn: Callable[[str], None],
    stderr_fallback: Callable[[], None],
    config_path: Path | None = None,
    client_gone_cls: ClientGoneCls = None,
) -> None:
    """Suppress client-disconnect tracebacks when enabled; otherwise legacy stderr."""
    exc = sys.exc_info()[1]
    if exc is not None and should_suppress_disconnect_traceback(
        exc,
        flag_enabled=is_disconnect_suppression_enabled(config_path),
        client_gone_cls=client_gone_cls,
    ):
        log_fn(format_client_disconnect_log(client_address, exc))
    else:
        stderr_fallback()
