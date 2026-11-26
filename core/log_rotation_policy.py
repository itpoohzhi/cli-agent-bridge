"""Zero-I/O policy, strict flag precedence, and 40-cell FSM for P1.3 log rotation.

100% Python 3.9.6+ compatible (stdlib Zero-I/O imports only; no os/pathlib/time/logging).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Mapping, Optional, Tuple

DEFAULT_MAX_BYTES = 20 * 1024 * 1024  # 20 MiB per file (model_georouter baseline)
DEFAULT_BACKUP_COUNT = 5  # 120 MiB nominal per service / 480 MiB aggregate
DEFAULT_DIR_MODE = 0o700
DEFAULT_FILE_MODE = 0o600

_TRUE_ENV = frozenset({"1", "true", "yes", "on"})
_FALSE_ENV = frozenset({"0", "false", "no", "off"})


@dataclass(frozen=True)
class ServiceSpec:
    """Declarative per-service log rotation metadata (single point of extension)."""

    service_id: str
    prefix: str
    flag_name: str
    config_env_var: Optional[str]
    default_rel_config: str
    default_rel_log: str = "logs/bridge.log"
    is_home_config: bool = False


SERVICE_SPECS: Dict[str, ServiceSpec] = {
    "hub": ServiceSpec(
        service_id="hub",
        prefix="BRIDGE",
        flag_name="BRIDGE_LOG_ROTATION_ENABLED",
        config_env_var="BRIDGE_DYNAMIC_CONFIG_PATH",
        default_rel_config=".config/cli-agent-bridge/dynamic_config.json",
        is_home_config=True,
    ),
    "agy": ServiceSpec(
        service_id="agy",
        prefix="AGY_BRIDGE",
        flag_name="AGY_BRIDGE_LOG_ROTATION_ENABLED",
        config_env_var=None,
        default_rel_config="dynamic_config.json",
    ),
    "claude_p": ServiceSpec(
        service_id="claude_p",
        prefix="CLAUDE_P_BRIDGE",
        flag_name="CLAUDE_P_BRIDGE_LOG_ROTATION_ENABLED",
        config_env_var="CLAUDE_P_BRIDGE_DYNAMIC_CONFIG_PATH",
        default_rel_config="dynamic_config.json",
    ),
    "zen": ServiceSpec(
        service_id="zen",
        prefix="OPENCODE_ZEN_BRIDGE",
        flag_name="OPENCODE_ZEN_BRIDGE_LOG_ROTATION_ENABLED",
        config_env_var=None,
        default_rel_config="dynamic_config.json",
    ),
}


@dataclass(frozen=True)
class RotationConfig:
    """Resolved per-emit rotation parameters."""

    enabled: bool
    log_path: str
    max_bytes: int = DEFAULT_MAX_BYTES
    backup_count: int = DEFAULT_BACKUP_COUNT
    dir_mode: int = DEFAULT_DIR_MODE
    file_mode: int = DEFAULT_FILE_MODE


class WriterState(Enum):
    """Finite state machine states for PrivateWatchedRotatingWriter."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    ROTATING = "ROTATING"
    REOPENING = "REOPENING"
    DEGRADED_FAIL_OPEN = "DEGRADED_FAIL_OPEN"


FSM_EVENTS: Tuple[str, ...] = ("W", "C", "G", "F", "P", "X", "OK", "ER")

# Total 40-cell FSM transition table (5 states x 8 events); dict lookup keeps CC == 1.
_S = WriterState
_FSM_TRANSITIONS: Dict[Tuple[WriterState, str], Tuple[WriterState, str]] = {
    (_S.CLOSED, "W"): (_S.REOPENING, "OPEN_FD"),
    (_S.CLOSED, "C"): (_S.CLOSED, "NOOP"),
    (_S.CLOSED, "G"): (_S.CLOSED, "NOOP"),
    (_S.CLOSED, "F"): (_S.CLOSED, "NOOP"),
    (_S.CLOSED, "P"): (_S.CLOSED, "SET_PATH"),
    (_S.CLOSED, "X"): (_S.CLOSED, "NOOP"),
    (_S.CLOSED, "OK"): (_S.CLOSED, "NOOP"),
    (_S.CLOSED, "ER"): (_S.DEGRADED_FAIL_OPEN, "DROP_AND_WARN"),
    (_S.OPEN, "W"): (_S.OPEN, "CHECK"),
    (_S.OPEN, "C"): (_S.OPEN, "WRITE"),
    (_S.OPEN, "G"): (_S.REOPENING, "CLOSE_AND_OPEN"),
    (_S.OPEN, "F"): (_S.ROTATING, "ROLLOVER"),
    (_S.OPEN, "P"): (_S.REOPENING, "REBIND_PATH"),
    (_S.OPEN, "X"): (_S.CLOSED, "CLOSE_FD"),
    (_S.OPEN, "OK"): (_S.OPEN, "DONE"),
    (_S.OPEN, "ER"): (_S.DEGRADED_FAIL_OPEN, "CLOSE_DROP_WARN"),
    (_S.ROTATING, "W"): (_S.ROTATING, "NOOP"),
    (_S.ROTATING, "C"): (_S.ROTATING, "NOOP"),
    (_S.ROTATING, "G"): (_S.ROTATING, "NOOP"),
    (_S.ROTATING, "F"): (_S.ROTATING, "NOOP"),
    (_S.ROTATING, "P"): (_S.ROTATING, "NOOP"),
    (_S.ROTATING, "X"): (_S.CLOSED, "CLOSE_FD"),
    (_S.ROTATING, "OK"): (_S.OPEN, "WRITE"),
    (_S.ROTATING, "ER"): (_S.DEGRADED_FAIL_OPEN, "CLOSE_DROP_WARN"),
    (_S.REOPENING, "W"): (_S.REOPENING, "NOOP"),
    (_S.REOPENING, "C"): (_S.REOPENING, "NOOP"),
    (_S.REOPENING, "G"): (_S.REOPENING, "NOOP"),
    (_S.REOPENING, "F"): (_S.ROTATING, "ROLLOVER"),
    (_S.REOPENING, "P"): (_S.REOPENING, "REBIND_PATH"),
    (_S.REOPENING, "X"): (_S.CLOSED, "CLOSE_FD"),
    (_S.REOPENING, "OK"): (_S.OPEN, "WRITE"),
    (_S.REOPENING, "ER"): (_S.DEGRADED_FAIL_OPEN, "CLOSE_DROP_WARN"),
    (_S.DEGRADED_FAIL_OPEN, "W"): (_S.DEGRADED_FAIL_OPEN, "PROBE_COMMIT"),
    (_S.DEGRADED_FAIL_OPEN, "C"): (_S.DEGRADED_FAIL_OPEN, "NOOP"),
    (_S.DEGRADED_FAIL_OPEN, "G"): (_S.DEGRADED_FAIL_OPEN, "NOOP"),
    (_S.DEGRADED_FAIL_OPEN, "F"): (_S.DEGRADED_FAIL_OPEN, "NOOP"),
    (_S.DEGRADED_FAIL_OPEN, "P"): (_S.DEGRADED_FAIL_OPEN, "SET_PATH"),
    (_S.DEGRADED_FAIL_OPEN, "X"): (_S.CLOSED, "RESET"),
    (_S.DEGRADED_FAIL_OPEN, "OK"): (_S.OPEN, "NOTE_REC"),
    (_S.DEGRADED_FAIL_OPEN, "ER"): (_S.DEGRADED_FAIL_OPEN, "DROP_SILENT"),
}


def step_fsm(state: WriterState, event: str) -> Tuple[WriterState, str]:
    """Total pure transition function over 5 states x 8 events."""
    return _FSM_TRANSITIONS.get((state, event), (state, "NOOP"))


def parse_env_bool(raw: Optional[str]) -> bool:
    """Parse env boolean string; unknown or empty values fail closed to False."""
    if raw is None:
        return False
    norm = str(raw).strip().lower()
    if norm in _TRUE_ENV:
        return True
    if norm in _FALSE_ENV:
        return False
    return False


def parse_dynamic_json_doc(raw_text: Optional[str]) -> Tuple[Optional[Dict[str, object]], bool]:
    """Parse dynamic JSON text -> (doc, is_corrupt). None means file absent (not corrupt)."""
    if raw_text is None:
        return None, False
    try:
        parsed = json.loads(raw_text)
    except (TypeError, ValueError):
        return None, True
    if not isinstance(parsed, dict):
        return None, True
    return parsed, False


def resolve_flag(
    doc: Optional[Mapping[str, object]],
    is_corrupt: bool,
    env_map: Mapping[str, str],
    flag_name: str,
) -> bool:
    """Strict dynamic JSON (bool only, fail-closed without env fallback) > env > False."""
    if is_corrupt:
        return False
    if doc is not None and flag_name in doc:
        val = doc[flag_name]
        return val if type(val) is bool else False
    return parse_env_bool(env_map.get(flag_name))


def parse_bounded_int(raw: object, default: int, minimum: int) -> int:
    """Parse integer parameter >= minimum; rejects booleans and garbage."""
    if raw is None or type(raw) is bool:
        return default
    try:
        val = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    return val if val >= minimum else default


def _pick_param(
    doc: Optional[Mapping[str, object]],
    env_map: Mapping[str, str],
    key: str,
) -> object:
    if doc is not None and key in doc:
        return doc[key]
    return env_map.get(key)


def _join_rel(base_dir: str, rel_path: str) -> str:
    return base_dir.rstrip("/") + "/" + rel_path.lstrip("/")


def resolve_rotation_config(
    spec: ServiceSpec,
    doc_state: Tuple[Optional[Mapping[str, object]], bool],
    env_map: Mapping[str, str],
    root_dir: str,
    runtime_log_path: Optional[str] = None,
) -> RotationConfig:
    """Resolve full RotationConfig from (doc, is_corrupt) + env + root + runtime path."""
    doc, is_corrupt = doc_state
    enabled = resolve_flag(doc, is_corrupt, env_map, spec.flag_name)
    src_doc = None if is_corrupt else doc
    pfx = spec.prefix + "_LOG_ROTATION_"
    max_bytes = parse_bounded_int(_pick_param(src_doc, env_map, pfx + "MAX_BYTES"), DEFAULT_MAX_BYTES, 1)
    backup_count = parse_bounded_int(_pick_param(src_doc, env_map, pfx + "BACKUP_COUNT"), DEFAULT_BACKUP_COUNT, 0)
    raw_path = _pick_param(src_doc, env_map, pfx + "PATH")
    if isinstance(raw_path, str) and raw_path.strip():
        log_path = raw_path.strip()
    elif runtime_log_path and str(runtime_log_path).strip():
        log_path = str(runtime_log_path).strip()
    else:
        log_path = _join_rel(root_dir, spec.default_rel_log)
    return RotationConfig(
        enabled=enabled,
        log_path=log_path,
        max_bytes=max_bytes,
        backup_count=backup_count,
    )


def stat_signature(dev: int, ino: int, mtime_ns: int, size: int, ctime_ns: int) -> Tuple[int, int, int, int, int]:
    """5-tuple stat signature including ctime_ns to catch same-tick in-place edits."""
    return (dev, ino, mtime_ns, size, ctime_ns)


def validate_stat(is_reg: bool, uid: int, nlink: int, euid: int) -> Optional[str]:
    """Validate file stat invariants; returns rejection reason or None when safe."""
    if not is_reg:
        return "not_regular_file"
    if uid != euid:
        return "foreign_uid"
    if nlink > 1:
        return "hardlink_detected"
    return None


def should_reopen(
    open_id: Optional[Tuple[int, int]],
    path_id: Optional[Tuple[int, int]],
    path_is_reg: bool,
) -> bool:
    """Return True when active handle must be closed and reopened (unlink/rename/swap)."""
    if open_id is None or path_id is None or not path_is_reg:
        return True
    return open_id != path_id


def should_rollover(current_size: int, incoming_bytes_len: int, max_bytes: int) -> bool:
    """Nominal per-service budget with single-oversized-line allowance on empty active file."""
    return current_size > 0 and (current_size + incoming_bytes_len) > max_bytes


def plan_rollover_ops(base_name: str, backup_count: int) -> Tuple[Tuple[str, str], ...]:
    """Ordered (src, dst) rename pairs from oldest archive down to active -> .1."""
    if backup_count <= 0:
        return ()
    ops = [(f"{base_name}.{idx}", f"{base_name}.{idx + 1}") for idx in range(backup_count - 1, 0, -1)]
    ops.append((base_name, f"{base_name}.1"))
    return tuple(ops)


def encode_log_line(text: str) -> bytes:
    """Encode single log line strictly as UTF-8 bytes with single trailing newline."""
    return (text.rstrip("\r\n") + "\n").encode("utf-8", errors="replace")


def format_transition_notice(
    prev_state: WriterState,
    next_state: WriterState,
    service_id: str,
    reason: str,
) -> Optional[str]:
    """Return <=200 B one-shot notice ONLY on entering/leaving DEGRADED_FAIL_OPEN."""
    if prev_state != WriterState.DEGRADED_FAIL_OPEN and next_state == WriterState.DEGRADED_FAIL_OPEN:
        return f"[log-rotation][{service_id}] degraded fail-open: {reason}\n"[:200]
    if prev_state == WriterState.DEGRADED_FAIL_OPEN and next_state == WriterState.OPEN:
        return f"[log-rotation][{service_id}] recovered: {reason}\n"[:200]
    return None
