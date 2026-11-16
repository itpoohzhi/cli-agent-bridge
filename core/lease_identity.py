"""Аппаратная идентичность и локальное обслуживание lease с долговечным аудитом."""
from __future__ import annotations
import argparse
import errno
import fcntl
import hashlib
import json
import os
import re
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
FIELDS = ("owner_host", "boot_id", "owner_pid", "owner_started_at_utc", "lease_epoch", "lease_token")
def _output(command: list[str]) -> str:
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True, env={**os.environ, "TZ": "UTC", "LC_ALL": "C"},
                              timeout=float(os.environ.get("CAB_IDENTITY_TIMEOUT_S", "5"))).stdout.strip()
    except (OSError, ValueError, subprocess.SubprocessError):
        return ""
class HostIdentityProvider(Protocol):
    def host_id(self) -> str | None: ...
class MacOSHostIdentityProvider:
    def host_id(self) -> str | None:
        values = re.findall(r'"IOPlatformUUID"\s*=\s*"([^"]*)"', _output(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"]))
        value = values[0].strip().upper() if len(values) == 1 else ""
        return hashlib.sha256(value.encode()).hexdigest() if value else None
def host_id(provider: HostIdentityProvider | None = None, *, test_override: bool = False) -> str | None:
    """Override доступен только через явный тестовый opt-in, не через CLI."""
    return (os.environ.get("CAB_HOST_ID_OVERRIDE") or None) if test_override else (provider or MacOSHostIdentityProvider()).host_id()
def boot_id() -> int | None:
    match = re.fullmatch(r"\{\s*sec\s*=\s*(\d+),\s*usec\s*=\s*\d+\s*\}[^\n{}]*", _output(["sysctl", "-n", "kern.boottime"]))
    return int(match[1]) if match else None
def process_birth_utc(pid: int) -> int | None:
    if type(pid) is not int or pid <= 0:
        return None
    try:
        _, month, day, clock, year = _output(["ps", "-p", str(pid), "-o", "lstart="]).split()
        month_number = list[str]("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()).index(month) + 1
        value = datetime.strptime(f"{year}-{month_number}-{day} {clock}", "%Y-%m-%d %H:%M:%S")
        return int(value.replace(tzinfo=timezone.utc).timestamp())
    except (ValueError, OverflowError):
        return None
process_started_at_utc = process_birth_utc
def _complete(owner: dict[str, Any]) -> bool:
    return type(owner.get("owner_host")) is str and bool(owner["owner_host"].strip()) and all(type(owner.get(k)) is int for k in FIELDS[1:4]) and owner["owner_pid"] > 0
def is_alive_or_unknown(owner: dict[str, Any], current_host: str | None, current_boot: int | None) -> bool:
    """Только подтверждённая смерть разрешает reclaim."""
    if not _complete(owner):
        return True
    if not current_host or owner["owner_host"] != current_host or type(current_boot) is not int:
        return True
    if owner["boot_id"] != current_boot:
        return False
    try:
        os.kill(owner["owner_pid"], 0)
    except OSError as error:
        if error.errno == errno.ESRCH:
            return False
        if error.errno != errno.EPERM:
            return True
    birth = process_started_at_utc(owner["owner_pid"])
    return birth is None or birth == owner["owner_started_at_utc"]
@dataclass(frozen=True)
class ClearForeignLeaseRequest:
    edge_key: str
    operator_id: str
    confirm_exclusive_storage: bool
    expected_owner_host: str
    expected_boot_id: int
    expected_owner_pid: int
    expected_owner_started_at_utc: int
    expected_lease_epoch: int
    expected_lease_token: str
@dataclass
class LeaseMaintenanceContext:
    lease_path: Path
    audit_path: Path
    host_id: str | None = field(default_factory=host_id)
    lock_path: Path | None = None
    unreconciled_intent: str | None = field(default=None, init=False)
    def __post_init__(self) -> None:
        self.lock_path = self.lock_path or self.lease_path.with_suffix(".json.lock")
def _valid(request: ClearForeignLeaseRequest) -> bool:
    values = (request.edge_key, request.operator_id, request.expected_owner_host, request.expected_lease_token)
    return (all(type(v) is str and bool(v.strip()) for v in values)
            and request.confirm_exclusive_storage is True
            and all(type(getattr(request, "expected_" + k)) is int for k in FIELDS[1:5]) and request.expected_owner_pid > 0)
def _sync_directory(path: Path) -> None:
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
def _append(path: Path, row: dict[str, Any]) -> None:
    payload = (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")
    with path.open("ab", buffering=0) as stream:
        if stream.write(payload) != len(payload):
            raise OSError("short audit write")
        os.fsync(stream.fileno())
    _sync_directory(path)
def _audit_phase(row: Any) -> tuple[str, bool]:
    if type(row) is not dict or row.get("phase") not in ("intent", "committed", "failed") or type(row.get("audit_id")) is not str or not row["audit_id"]:
        raise ValueError("invalid audit")
    return row["audit_id"], row["phase"] != "committed"
def _recover(context: LeaseMaintenanceContext) -> None:
    context.unreconciled_intent = None
    if not context.audit_path.exists():
        return
    with context.audit_path.open("r+b", buffering=0) as stream:
        data = stream.read()
        end = data.rfind(b"\n") + 1
        if end != len(data):
            stream.truncate(end)
            os.fsync(stream.fileno())
    rows = [json.loads(line.decode("utf-8")) for line in data[:end].split(b"\n")[:-1]]
    pending = dict(map(_audit_phase, rows))
    context.unreconciled_intent = next((key for key in pending if pending[key]), None)
    if context.unreconciled_intent is not None:
        raise ValueError("unreconciled_intent")
def _remove(context: LeaseMaintenanceContext, store: dict[str, Any], edge: str) -> None:
    if "edge_key" in store:
        os.unlink(context.lease_path)
    else:
        del store[edge]
        with tempfile.NamedTemporaryFile(dir=context.lease_path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            try:
                stream.write(json.dumps(store, ensure_ascii=False).encode("utf-8"))
                stream.flush()
                os.fsync(stream.fileno())
                os.replace(temporary, context.lease_path)
            finally:
                if temporary.exists():
                    os.unlink(temporary)
    _sync_directory(context.lease_path)
def _clear(request: ClearForeignLeaseRequest, context: LeaseMaintenanceContext) -> int:
    _recover(context)
    store = json.loads(context.lease_path.read_text(encoding="utf-8"))
    lease = store if "edge_key" in store else store.get(request.edge_key, {})
    fingerprint = {key: getattr(request, "expected_" + key) for key in FIELDS}
    if not context.host_id or context.host_id == request.expected_owner_host or lease.get("edge_key", request.edge_key) != request.edge_key:
        return 1
    if any(type(lease.get(k)) is not type(v) or lease.get(k) != v for k, v in fingerprint.items()):
        return 1
    row = dict(fingerprint, audit_id=uuid.uuid4().hex, ts_utc=int(datetime.now(timezone.utc).timestamp()), operator_id=request.operator_id, edge_key=request.edge_key, lease_fingerprint=fingerprint)
    _append(context.audit_path, dict(row, phase="intent"))
    try:
        _remove(context, store, request.edge_key)
    except (OSError, ValueError, MemoryError) as error:
        _append(context.audit_path, dict(row, phase="failed", error=type(error).__name__))
        return 1
    _append(context.audit_path, dict(row, phase="committed"))
    return 0
def operator_clear_foreign_lease(request: ClearForeignLeaseRequest, context: LeaseMaintenanceContext) -> int:
    """Проверка, восстановление аудита и CAS выполняются под стабильным flock."""
    try:
        if context.lock_path is None or not _valid(request) or len({p.resolve() for p in (context.lease_path, context.audit_path, context.lock_path)}) != 3:
            return 1
        with open(context.lock_path, "a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            return _clear(request, context)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, MemoryError):
        return 1
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["clear-foreign-lease"], help=argparse.SUPPRESS)
    for name in ("lease-path", "audit-path", "lock-path"):
        parser.add_argument("--" + name, type=Path, required=name != "lock-path")
    for name in ("edge_key", "operator_id", *("expected_" + k for k in FIELDS)):
        parser.add_argument("--" + name.replace("_", "-"), required=True, type=int if name[9:] in FIELDS[1:5] else str)
    parser.add_argument("--confirm-exclusive-storage", action="store_true", required=True)
    values = {k: v for k, v in vars(parser.parse_args()).items() if k != "command"}
    context = LeaseMaintenanceContext(**{k: values.pop(k) for k in ("lease_path", "audit_path", "lock_path")})
    return operator_clear_foreign_lease(ClearForeignLeaseRequest(**values), context)
if __name__ == "__main__":
    raise SystemExit(main())
