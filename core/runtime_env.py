"""Config primitives (ADR-0015)."""

from __future__ import annotations

import json
import math
import os
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

_Env = Mapping[str, str]

_TRUE = ("1", "true", "yes", "on")
_FALSE = ("0", "false", "no", "off")


class ConfigError(ValueError):
    """Invalid config parameter."""


@dataclass(frozen=True)
class NumSpec:
    names: tuple[str, ...]
    default: float
    low: float
    high: float
    integer: bool = False
    low_open: bool = False


def env_first(environ: _Env, names: tuple[str, ...]) -> tuple[str, str] | None:
    for name in names:
        value = str(environ.get(name, "")).strip()
        if value:
            return name, value
    return None


def parse_number(environ: _Env, spec: NumSpec) -> Any:
    found = env_first(environ, spec.names)
    if found is None:
        return int(spec.default) if spec.integer else float(spec.default)
    try:
        value = int(found[1]) if spec.integer else float(found[1])
    except (ValueError, OverflowError):
        raise ConfigError(f"invalid config parameter: {spec.names[0]}") from None
    above = value > spec.low if spec.low_open else value >= spec.low
    if not (math.isfinite(value) and above and value <= spec.high):
        raise ConfigError(f"invalid config parameter: {spec.names[0]}")
    return value


def env_bool(environ: _Env, names: tuple[str, ...], default: bool) -> bool:
    raw = (env_first(environ, names) or ("", ""))[1].lower()
    return True if raw in _TRUE else False if raw in _FALSE else default


def bounded_int(environ: _Env, name: str, default: int, low: int, high: float) -> int:
    try:
        value = int(str(environ.get(name, "")).strip())
    except ValueError:
        return default
    return value if low <= value <= high else default


def positive_int(environ: _Env, name: str, default: int) -> int:
    return bounded_int(environ, name, default, 1, math.inf)


class ConfigSnapshotError(Exception):
    """Dynamic config file unreadable (fail-closed)."""


_SNAP_TTL_S = 0.5
_SNAPSHOTS: dict[str, tuple[float, tuple, dict | None]] = {}
_SNAP_LOCK = threading.Lock()


def read_config_snapshot(path: str) -> dict | None:
    now = time.monotonic()
    with _SNAP_LOCK:
        hit = _SNAPSHOTS.get(path)
    if hit is not None and now - hit[0] < _SNAP_TTL_S:
        return hit[2]
    try:
        st = os.stat(path)
        sig: tuple = (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_mode)
    except OSError:
        sig = ()
    data = hit[2] if hit is not None and hit[1] == sig else _load_snapshot(path) if sig else None
    with _SNAP_LOCK:
        _SNAPSHOTS[path] = (now, sig, data)
    return data


def _load_snapshot(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.loads(handle.read(1 << 20))
    except (OSError, ValueError):
        raise ConfigSnapshotError(path) from None
    if not isinstance(data, dict):
        raise ConfigSnapshotError(path)
    return data


class DynamicFlagSource:
    """GigaRC dynamic flag; env fallback, default false."""

    _flag_name = ""
    _default = "false"

    def __init__(self, flag_name: str | None = None, default: bool = False) -> None:
        if flag_name:
            self._flag_name = flag_name
        self._default = "true" if default else "false"

    @staticmethod
    def _truthy(raw: Any) -> bool:
        return raw if isinstance(raw, bool) else str(raw).strip().lower() in _TRUE

    def enabled(self, fallback: bool = False) -> bool:
        path = os.environ.get("BRIDGE_DYNAMIC_CONFIG_PATH") or os.path.expanduser("~/.config/cli-agent-bridge/dynamic_config.json")
        try:
            data = read_config_snapshot(path)
        except ConfigSnapshotError:
            return fallback  # fail-closed: битый снимок GigaRC не обходится env/default; fallback=False по умолчанию
        if data is None or self._flag_name not in data:
            return self._truthy(os.environ.get(self._flag_name, self._default))
        return self._truthy(data[self._flag_name])


_SOURCES: dict[str, DynamicFlagSource] = {}
_SOURCES_LOCK = threading.Lock()


def flag_enabled(name: str) -> bool:
    with _SOURCES_LOCK:
        source = _SOURCES.get(name)
        if source is None:
            source = _SOURCES[name] = DynamicFlagSource(name)
    return source.enabled()
