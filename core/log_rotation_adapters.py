"""Negative-cached JSON reader, writer registry, pre-lock redaction, and facade for P1.3.

100% Python 3.9.6+ compatible (stdlib only). Lock hierarchy: L0 (_REG_LOCK) -> L1 (writer._lock).
Legacy _LOG_LOCK (zen) is acquired ONLY on the flag=False legacy branch, never nested with L0/L1.
"""
from __future__ import annotations

import atexit
import errno
import os
import stat
import sys
import threading
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from core.log_rotation_policy import (
    SERVICE_SPECS,
    ServiceSpec,
    encode_log_line,
    parse_dynamic_json_doc,
    resolve_rotation_config,
    stat_signature,
)
from core.userspace_log_rotation import PrivateWatchedRotatingWriter

_DETERMINISTIC_READ_ERRNOS = frozenset({errno.EACCES, errno.EISDIR, errno.ENOTDIR})


class DynamicJsonBoolCache:
    """Stat-keyed negative cache for dynamic_config.json (json.loads <= 1/1000 when unchanged).

    Caches valid docs, ENOENT, and deterministic format/EACCES/EISDIR errors; NEVER caches
    transient open/read OSErrors (EMFILE/ENFILE/EINTR/EAGAIN/ENOMEM) so rotation self-heals.
    """

    def __init__(self) -> None:
        self._entries: Dict[str, Tuple[Optional[Tuple[int, int, int, int, int]], Tuple[Optional[Dict[str, object]], bool]]] = {}

    def read(self, config_path: str) -> Tuple[Optional[Dict[str, object]], bool]:
        try:
            st = os.stat(config_path)
        except FileNotFoundError:
            self._entries[config_path] = (None, (None, False))
            return None, False
        except OSError:
            return None, True
        sig = stat_signature(st.st_dev, st.st_ino, st.st_mtime_ns, st.st_size, st.st_ctime_ns)
        cached = self._entries.get(config_path)
        if cached is not None and cached[0] == sig:
            return cached[1]
        if stat.S_ISDIR(st.st_mode):
            res: Tuple[Optional[Dict[str, object]], bool] = (None, True)
            self._entries[config_path] = (sig, res)
            return res
        return self._load_and_cache(config_path, sig)

    def _load_and_cache(
        self, config_path: str, sig: Tuple[int, int, int, int, int]
    ) -> Tuple[Optional[Dict[str, object]], bool]:
        try:
            with open(config_path, "r", encoding="utf-8") as fh:
                raw = fh.read()
        except UnicodeDecodeError:
            res: Tuple[Optional[Dict[str, object]], bool] = (None, True)
            self._entries[config_path] = (sig, res)
            return res
        except OSError as exc:
            if exc.errno in _DETERMINISTIC_READ_ERRNOS:
                self._entries[config_path] = (sig, (None, True))
            return None, True
        parsed = parse_dynamic_json_doc(raw)
        self._entries[config_path] = (sig, parsed)
        return parsed

    def clear(self) -> None:
        self._entries.clear()


_REG_LOCK = threading.Lock()
_WRITERS: Dict[str, PrivateWatchedRotatingWriter] = {}
_FLAG_CACHE = DynamicJsonBoolCache()
_TLS = threading.local()
_SHUTDOWN = False
_HOOKS_INSTALLED = False
_REENTRANT_DROPS = 0


def resolve_service_config_path(
    spec: ServiceSpec,
    root_dir: str,
    env_map: Optional[Mapping[str, str]] = None,
) -> str:
    """Declarative stdlib resolver for per-service dynamic_config.json path."""
    env = os.environ if env_map is None else env_map
    if spec.config_env_var:
        override = (env.get(spec.config_env_var) or "").strip()
        if override:
            return os.path.expanduser(override)
    base = os.path.expanduser("~") if spec.is_home_config else root_dir
    return os.path.join(base, spec.default_rel_config)


def _install_lifecycle_hooks_locked() -> None:
    global _HOOKS_INSTALLED
    if _HOOKS_INSTALLED:
        return
    atexit.register(close_all_writers)
    if hasattr(os, "register_at_fork"):
        os.register_at_fork(after_in_child=_reset_after_fork)
    _HOOKS_INSTALLED = True


def _get_or_create_writer(service: str) -> PrivateWatchedRotatingWriter:
    with _REG_LOCK:
        _install_lifecycle_hooks_locked()
        writer = _WRITERS.get(service)
        if writer is None:
            writer = PrivateWatchedRotatingWriter(service)
            _WRITERS[service] = writer
        return writer


def _close_writer_if_present(service: str) -> None:
    with _REG_LOCK:
        writer = _WRITERS.get(service)
    if writer is not None and writer.is_active():
        writer.close()


def _legacy_emit(line: str, legacy_target: Optional[Tuple[Any, Any]]) -> None:
    """Byte-for-byte legacy stderr (+ optional zen LOG_PATH dual-write under _LOG_LOCK)."""
    payload = line + "\n"
    try:
        sys.stderr.write(payload)
        sys.stderr.flush()
    except OSError:
        pass
    if legacy_target is None:
        return
    log_path, legacy_lock = legacy_target
    try:
        parent = os.path.dirname(os.path.abspath(str(log_path)))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with legacy_lock, open(str(log_path), "a", encoding="utf-8") as fh:
            fh.write(payload)
    except OSError:
        pass


def emit_service_log(
    service: str,
    line: str,
    root: Any,
    redact_fn: Optional[Callable[[str], str]] = None,
    legacy_target: Optional[Tuple[Any, Any]] = None,
) -> None:
    """Single seam called by the 4 services: OFF -> legacy; ON -> pre-lock redact -> rotated log."""
    global _REENTRANT_DROPS
    if _SHUTDOWN:
        return
    depth = getattr(_TLS, "depth", 0)
    if depth > 0:
        _REENTRANT_DROPS += 1
        return
    _TLS.depth = depth + 1
    try:
        spec = SERVICE_SPECS[service]
        root_str = str(root)
        cfg_path = resolve_service_config_path(spec, root_str)
        doc_state = _FLAG_CACHE.read(cfg_path)
        runtime_log = str(legacy_target[0]) if legacy_target is not None else None
        cfg = resolve_rotation_config(spec, doc_state, os.environ, root_str, runtime_log)
        if not cfg.enabled:
            _close_writer_if_present(service)
            _legacy_emit(line, legacy_target)
            return
        writer = _get_or_create_writer(service)
        safe_line = line
        if redact_fn is not None:
            try:
                safe_line = redact_fn(line)
            except Exception:
                writer.note_external_degrade("REDACT_UNAVAILABLE")
                return
        writer.write_bytes(cfg, encode_log_line(safe_line))
    finally:
        _TLS.depth = depth


def get_rotation_snapshot(service: str) -> Dict[str, Any]:
    """Read-only diagnostic snapshot of service writer FSM & counters (does not alter /health)."""
    with _REG_LOCK:
        writer = _WRITERS.get(service)
    if writer is None:
        return {"service": service, "state": "CLOSED", "writes": 0, "dropped_lines": 0, "reentrant_drops": _REENTRANT_DROPS}
    snap = writer.snapshot()
    snap["reentrant_drops"] = _REENTRANT_DROPS
    return snap


def close_all_writers(mark_shutdown: bool = True) -> None:
    """Idempotently close all active writers (called on atexit)."""
    global _SHUTDOWN
    if mark_shutdown:
        _SHUTDOWN = True
    with _REG_LOCK:
        writers = list(_WRITERS.values())
    for writer in writers:
        try:
            writer.close()
        except Exception:
            pass


def _reset_after_fork() -> None:
    global _REG_LOCK, _SHUTDOWN
    _REG_LOCK = threading.Lock()
    _SHUTDOWN = False
    for writer in _WRITERS.values():
        writer.reset_after_fork()
    _WRITERS.clear()
    _FLAG_CACHE.clear()


def reset_for_tests() -> None:
    """Close all writers, clear caches, and reset shutdown state for pytest isolation."""
    global _SHUTDOWN, _REENTRANT_DROPS
    close_all_writers(mark_shutdown=False)
    with _REG_LOCK:
        _WRITERS.clear()
    _FLAG_CACHE.clear()
    _SHUTDOWN = False
    _REENTRANT_DROPS = 0
