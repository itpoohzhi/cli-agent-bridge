"""Fail-closed проба well-known Unix-сокета Muse (VER-007, AD-004).

Недокументированный handshake ``museClientCredential`` не реализуется и
не обходится: при ответе ``rejected`` детерминированно возвращается
``MUSE_SOCKET_HANDSHAKE_UNSUPPORTED`` без ретраев, вызывающий код уходит
в fallback на warm stdio MSP v1. За фичефлагом
``MUSE_UNIX_SOCKET_PROBE_ENABLED`` (по умолчанию ``false``).
"""

from __future__ import annotations

import json
import math
import os
import socket
import stat
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from core.runtime_env import env_bool

PROBE_FLAG = "MUSE_UNIX_SOCKET_PROBE_ENABLED"
ERR_UNSUPPORTED = "MUSE_SOCKET_HANDSHAKE_UNSUPPORTED"
ERR_PATH_REJECTED = "MUSE_SOCKET_PATH_REJECTED"
ERR_PERMISSION_REJECTED = "MUSE_SOCKET_PERMISSION_REJECTED"
ERR_MISSING = "MUSE_SOCKET_MISSING"
ERR_CONNECT_FAILED = "MUSE_SOCKET_CONNECT_FAILED"
ERR_BAD_RESPONSE = "MUSE_SOCKET_BAD_RESPONSE"
ERR_RPC_ERROR = "MUSE_SOCKET_RPC_ERROR"
_TIMEOUT_ENV = "MUSE_SOCKET_PROBE_TIMEOUT_S"
_RECV_ENV = "MUSE_SOCKET_PROBE_RECV_BYTES"
_DEFAULT_TIMEOUT_S = 2.0
_DEFAULT_RECV_BYTES = 65536
_DIR_MODE = 0o700
_FILE_MODE = 0o600

Connector = Callable[[Path, bytes], bytes]


@dataclass(frozen=True, slots=True)
class SocketProbeResult:
    """Итог пробы сокета: успех либо детерминированный fail-closed код."""

    ok: bool
    error_code: str | None
    socket_path: str
    detail: str = ""


def _env(environ: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if environ is None else environ


def probe_enabled(environ: Mapping[str, str] | None = None) -> bool:
    """Включена ли проба сокета (env/GigaRC-флаг, по умолчанию ``false``)."""
    return env_bool(_env(environ), (PROBE_FLAG,), False)


def well_known_socket_path(environ: Mapping[str, str] | None = None) -> Path:
    """Единственный допустимый путь: ``$XDG_DATA_HOME/muse/session-server/…``."""
    env = _env(environ)
    base = env.get("XDG_DATA_HOME", "").strip()
    if base:
        root = Path(base)
    else:
        home = env.get("HOME", "").strip()
        root = Path(home) / ".local" / "share" if home else Path.home() / ".local" / "share"
    return root / "muse" / "session-server" / "session-server.sock"


def validate_socket_path(
    path: str | Path, environ: Mapping[str, str] | None = None
) -> Path:
    """Принимает только well-known путь; любой иной — ``ValueError`` до I/O."""
    candidate = Path(path)
    expected = well_known_socket_path(environ)
    if candidate != expected:
        raise ValueError(f"{ERR_PATH_REJECTED}:{candidate}")
    return candidate


def _positive_float(raw: str, default: float) -> float:
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if math.isfinite(value) and value > 0 else default


def _recv_bytes(environ: Mapping[str, str]) -> int:
    try:
        value = int(environ.get(_RECV_ENV, "").strip())
    except ValueError:
        return _DEFAULT_RECV_BYTES
    return value if 1024 <= value <= 1048576 else _DEFAULT_RECV_BYTES


def _permissions_error(path: Path) -> str | None:
    try:
        dir_mode = stat.S_IMODE(path.parent.stat().st_mode)
        file_mode = stat.S_IMODE(path.stat().st_mode)
    except OSError as exc:
        return str(exc)
    if dir_mode != _DIR_MODE:
        return f"dir mode {dir_mode:04o} != {_DIR_MODE:04o}"
    if file_mode != _FILE_MODE:
        return f"socket mode {file_mode:04o} != {_FILE_MODE:04o}"
    return None


def _initialize_payload() -> bytes:
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"compatibilityEpoch": 0},
    }
    return (json.dumps(body, ensure_ascii=False) + "\n").encode("utf-8")


def _is_credential_rejected(response: bytes) -> bool:
    try:
        parsed = json.loads(response.decode("utf-8", errors="strict").strip())
    except (UnicodeDecodeError, ValueError):
        parsed = None
    if isinstance(parsed, dict) and parsed.get("museClientCredential") == "rejected":
        return True
    return b"museClientCredential" in response and b"rejected" in response


def _default_connector(path: Path, payload: bytes, timeout_s: float, recv_bytes: int) -> bytes:
    deadline = time.monotonic() + timeout_s
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout_s)
        sock.connect(str(path))
        sock.sendall(payload)
        chunks = bytearray()
        while len(chunks) < recv_bytes:
            rem = deadline - time.monotonic()
            if rem <= 0:
                raise TimeoutError("socket probe recv deadline exceeded")
            sock.settimeout(rem)
            part = sock.recv(min(4096, recv_bytes - len(chunks)))
            if not part:
                break
            chunks.extend(part)
            if b"\n" in part:
                break
        return bytes(chunks)


def _is_valid_rpc_envelope(parsed: object) -> bool:
    if not isinstance(parsed, dict):
        return False
    req_id = parsed.get("id")
    return parsed.get("jsonrpc") == "2.0" and type(req_id) is int and req_id == 1


def _validate_initialize_response(response: bytes, path: Path) -> SocketProbeResult:
    if _is_credential_rejected(response):
        return SocketProbeResult(False, ERR_UNSUPPORTED, str(path), "credential rejected")
    if not response.strip():
        return SocketProbeResult(False, ERR_BAD_RESPONSE, str(path), "empty response")
    try:
        parsed = json.loads(response.splitlines()[0].decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, ValueError):
        return SocketProbeResult(False, ERR_BAD_RESPONSE, str(path), "malformed json response")
    if not _is_valid_rpc_envelope(parsed):
        return SocketProbeResult(False, ERR_BAD_RESPONSE, str(path), "invalid jsonrpc envelope")
    if "error" in parsed:
        return SocketProbeResult(False, ERR_RPC_ERROR, str(path), "jsonrpc error response")
    if not isinstance(parsed.get("result"), dict):
        return SocketProbeResult(False, ERR_BAD_RESPONSE, str(path), "missing initialize result")
    return SocketProbeResult(True, None, str(path), "initialize accepted")


def probe_well_known_socket(
    socket_path: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
    *,
    connector: Connector | None = None,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
) -> SocketProbeResult:
    """Один ``initialize`` в well-known сокет; без ретраев и обхода auth."""
    env = _env(environ)
    try:
        path = (
            well_known_socket_path(env)
            if socket_path is None
            else validate_socket_path(socket_path, env)
        )
    except ValueError as exc:
        return SocketProbeResult(False, ERR_PATH_REJECTED, str(socket_path), str(exc))
    if not path.exists():
        return SocketProbeResult(False, ERR_MISSING, str(path), "socket not found")
    perm_error = _permissions_error(path)
    if perm_error is not None:
        return SocketProbeResult(False, ERR_PERMISSION_REJECTED, str(path), perm_error)
    effective_timeout = _positive_float(env.get(_TIMEOUT_ENV, ""), float(timeout_s))
    send = connector or (
        lambda p, data: _default_connector(p, data, effective_timeout, _recv_bytes(env))
    )
    try:
        response = send(path, _initialize_payload())
    except (OSError, TimeoutError) as exc:
        return SocketProbeResult(False, ERR_CONNECT_FAILED, str(path), str(exc))
    return _validate_initialize_response(response, path)
