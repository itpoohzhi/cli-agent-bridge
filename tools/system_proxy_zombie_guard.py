#!/usr/bin/env python3
"""Conservative macOS proxy/orphan auditor; cleanup requires explicit enforce."""

import argparse
import errno
import fcntl
import json
import logging
import math
import os
import re
import shlex
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field, fields
from typing import Any, Callable, Mapping, Optional

# Legacy path hint only. FileLock resolves and validates its directory at runtime.
LOCK_PATH = os.path.join(
    tempfile.gettempdir(), f"system-proxy-zombie-guard-{os.getuid()}.lock",
)
PROXY_NAMES = (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
    "http_proxy", "https_proxy", "all_proxy",
)
OWNED_PORTS = frozenset((44445, 10816, 10817, 10818, 10819, 10820))
ALLOWED_COMMANDS = frozenset(("proxyrack-forward.py", "droid"))
ALLOWED_ENV_FIELDS = frozenset((
    "mode", "run_timeout_s", "command_timeout_s", "connect_timeout_s",
    "orphan_min_age_s", "retry_backoff_s", "notify",
))
LAUNCHCTL = "/bin/launchctl"
PS = "/bin/ps"
LSOF = "/usr/sbin/lsof"
OSASCRIPT = "/usr/bin/osascript"
PROCESS_FORMAT = "pid=,ppid=,tty=,lstart=,comm="
LOG = logging.getLogger(__name__)


class GuardError(Exception):
    pass


class BudgetExpired(GuardError):
    pass


@dataclass(frozen=True)
class Config:
    mode: str = "report"
    run_timeout_s: float = 24.0
    command_timeout_s: float = 1.0
    connect_timeout_s: float = 0.2
    orphan_min_age_s: float = 300.0
    retry_backoff_s: tuple[float, ...] = (0.1, 0.2, 0.4)
    notify: bool = True
    run_timeout_limit_s: float = 24.0
    orphan_age_floor_s: float = 300.0
    proxy_names: tuple[str, ...] = PROXY_NAMES
    owned_ports: frozenset[int] = OWNED_PORTS
    allowed_commands: frozenset[str] = ALLOWED_COMMANDS
    python_pattern: str = r"(?:python(?:3(?:\.[0-9]+)?)?|Python)"
    script_name: str = "proxyrack-forward.py"
    launchctl: str = LAUNCHCTL
    ps: str = PS
    lsof: str = LSOF
    osascript: str = OSASCRIPT
    notification_title: str = "System Proxy Zombie Guard"

    def __post_init__(self) -> None:
        if self.mode not in ("report", "enforce"):
            raise ValueError("invalid mode")
        positive = (
            self.run_timeout_s, self.command_timeout_s,
            self.connect_timeout_s, self.run_timeout_limit_s,
        )
        if any(not math.isfinite(v) or v <= 0 for v in positive):
            raise ValueError("timeouts must be finite and positive")
        if (
            self.run_timeout_s > 24.0
            or self.run_timeout_s > self.run_timeout_limit_s
        ):
            raise ValueError("execution budget exceeds safety limit")
        if (
            not math.isfinite(self.orphan_age_floor_s)
            or not math.isfinite(self.orphan_min_age_s)
            or self.orphan_min_age_s < 300.0
            or not 0 <= self.orphan_age_floor_s <= self.orphan_min_age_s
        ):
            raise ValueError("invalid orphan age threshold")
        for name, executable in (
            ("launchctl", LAUNCHCTL), ("ps", PS),
            ("lsof", LSOF), ("osascript", OSASCRIPT),
        ):
            if getattr(self, name) != executable:
                raise ValueError("system executable path is fixed")
        delays = self.retry_backoff_s
        if (
            not delays
            or any(not math.isfinite(v) or v < 0 for v in delays)
            or tuple(sorted(delays)) != tuple(delays)
        ):
            raise ValueError("finite nondecreasing backoff delays required")
        if not isinstance(self.notify, bool):
            raise ValueError("notify must be boolean")
        if not self.proxy_names or any(
            re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", n) is None
            for n in self.proxy_names
        ):
            raise ValueError("invalid proxy names")
        if not self.owned_ports or any(
            not 0 < p <= 65535 for p in self.owned_ports
        ):
            raise ValueError("invalid owned ports")
        if not self.allowed_commands or any(
            not n or "/" in n for n in (*self.allowed_commands, self.script_name)
        ):
            raise ValueError("invalid command allowlist")
        re.compile(self.python_pattern)

    @classmethod
    def from_environment(
        cls, environ: Mapping[str, str], mode: Optional[str] = None,
        notify: Optional[bool] = None,
    ) -> "Config":
        settings: dict[str, Any] = {}
        for item in fields(cls):
            if item.name not in ALLOWED_ENV_FIELDS:
                continue
            raw = environ.get("SYSTEM_GUARD_" + item.name.upper())
            if raw is None and item.name == "run_timeout_s":
                # Retain the original operational timeout variable as an alias.
                raw = environ.get("SYSTEM_GUARD_TIMEOUT_S")
            if raw is None:
                continue
            default = item.default
            if isinstance(default, bool):
                raw = raw.strip().lower()
                if raw not in ("1", "true", "yes", "on", "0", "false", "no", "off"):
                    raise ValueError("invalid notification setting")
                value: Any = raw in ("1", "true", "yes", "on")
            elif isinstance(default, float):
                value = float(raw)
            elif isinstance(default, (tuple, frozenset)):
                convert = type(next(iter(default)))
                value = type(default)(convert(v.strip()) for v in raw.split(","))
            else:
                value = raw
            settings[item.name] = value
        if mode is not None:
            settings["mode"] = mode
        if notify is not None:
            settings["notify"] = notify
        return cls(**settings)


class Budget:
    def __init__(self, seconds: float, monotonic: Callable[[], float]) -> None:
        self._clock = monotonic
        self._deadline = monotonic() + seconds

    def remaining(self) -> float:
        remaining = self._deadline - self._clock()
        if remaining <= 0:
            raise BudgetExpired("execution budget exhausted")
        return remaining

    def check(self) -> None:
        self.remaining()

    def timeout(self, requested: float) -> float:
        return min(requested, self.remaining())


@dataclass(frozen=True)
class Endpoint:
    host: str
    port: int


def parse_endpoint(
    value: Optional[str], owned_ports: frozenset[int] = OWNED_PORTS,
) -> Optional[Endpoint]:
    if not value or any(ord(c) <= 32 or ord(c) == 127 for c in value):
        return None
    authority = value
    if "://" in value:
        scheme, authority = value.split("://", 1)
        if scheme.lower() not in ("http", "https", "socks", "socks5", "socks5h"):
            return None
    if authority.endswith("/"):
        authority = authority[:-1]
    if any(c in authority for c in "/?#@\\"):
        return None
    host, separator, port_text = authority.rpartition(":")
    hosts = {"localhost": "127.0.0.1", "127.0.0.1": "127.0.0.1", "[::1]": "::1"}
    if (
        not separator or host.lower() not in hosts
        or not port_text or len(port_text) > 5
        or any(c not in "0123456789" for c in port_text)
    ):
        return None
    port = int(port_text)
    if str(port) != port_text or port not in owned_ports:
        return None
    return Endpoint(hosts[host.lower()], port)


def tcp_probe(host: str, port: int, timeout: float) -> Optional[bool]:
    if host not in ("127.0.0.1", "::1"):
        raise ValueError("only numeric loopback probes are permitted")
    family = socket.AF_INET6 if host == "::1" else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as connection:
            connection.settimeout(timeout)
            connection.connect((host, port))
        return True
    except (ConnectionRefusedError, TimeoutError):
        return False
    except OSError:
        return None


def _lock_dir() -> str:
    directory = tempfile.gettempdir()
    uid = os.getuid()

    def isolated(path: str) -> bool:
        try:
            info = os.lstat(path)
            return (
                stat.S_ISDIR(info.st_mode)
                and info.st_uid == uid
                and stat.S_IMODE(info.st_mode) == 0o700
            )
        except OSError:
            return False

    if isolated(directory):
        return directory

    # При неизолированном tempdir используем домашний каталог ~/.cache/system-proxy-zombie-guard
    home_cache = os.path.expanduser("~/.cache/system-proxy-zombie-guard")
    try:
        os.makedirs(home_cache, mode=0o700, exist_ok=True)
    except OSError:
        pass
    if not isolated(home_cache):
        raise GuardError("lock directory is not isolated")
    return home_cache


class FileLock:
    def __init__(
        self, opener: Callable = os.open, locker: Callable = fcntl.flock,
        closer: Callable = os.close, statter: Callable = os.fstat,
        owner: Callable = os.getuid,
    ) -> None:
        self._open, self._flock, self._close = opener, locker, closer
        self._stat, self._owner = statter, owner
        self._fd: Optional[int] = None

    def acquire(self) -> bool:
        if self._fd is not None:
            raise GuardError("lock already acquired")
        uid = self._owner()
        flags = os.O_WRONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
        try:
            path = os.path.join(
                _lock_dir(), f"system-proxy-zombie-guard-{uid}.lock",
            )
            try:
                fd = self._open(path, flags | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                # Existing lock files must retain their inode across releases.
                fd = self._open(path, flags, 0o600)
        except OSError as error:
            if error.errno in (
                errno.ELOOP, errno.EACCES, errno.EPERM, errno.EISDIR, errno.ENXIO,
            ):
                return False
            raise
        try:
            info = self._stat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_mode & 0o7777 != 0o600
                or info.st_uid != uid or info.st_nlink != 1
            ):
                return False
            try:
                self._flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (BlockingIOError, PermissionError):
                return False
            self._fd = fd
            return True
        finally:
            if self._fd != fd:
                self._close(fd)

    def release(self) -> None:
        fd, self._fd = self._fd, None
        if fd is not None:
            try:
                self._flock(fd, fcntl.LOCK_UN)
            finally:
                self._close(fd)
        # Unlinking would permit simultaneous locks on different inodes.


@dataclass(frozen=True)
class Process:
    pid: int
    ppid: int
    tty: Optional[str]
    start_time: str
    started_at: float
    command: str

    @property
    def identity(self) -> tuple[int, str]:
        return self.pid, self.start_time


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def _python_command(command: str, config: Optional[Config] = None) -> bool:
    pattern = config.python_pattern if config is not None else Config.python_pattern
    return re.fullmatch(pattern, _basename(command)) is not None


def _text(value: Any) -> str:
    return value.decode("utf-8", "surrogateescape") if isinstance(value, bytes) else value


def _valid_text(text: str) -> bool:
    return not any(
        c in "\0\ufffd" or 0xD800 <= ord(c) <= 0xDFFF for c in text
    )


def _split_arguments(text: str) -> tuple[str, ...]:
    if not _valid_text(text) or "\r" in text or "\n" in text:
        raise GuardError("ambiguous process arguments")
    try:
        return tuple(shlex.split(text))
    except ValueError:
        raise GuardError("ambiguous process arguments") from None


def allowed_command(
    command: str, arguments: tuple[str, ...] = (),
    config: Optional[Config] = None,
) -> bool:
    config = config if config is not None else Config()
    if _basename(command) in config.allowed_commands:
        return True
    return (
        _python_command(command, config) and len(arguments) >= 2
        and _python_command(arguments[0], config)
        and _basename(arguments[1]) == config.script_name
    )


def _parse_processes(
    text: str, config: Optional[Config] = None, candidates_only: bool = False,
) -> list[Process]:
    config = config if config is not None else Config()
    processes: list[Process] = []
    seen: set[int] = set()
    skipped = 0
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    for line in _text(text).splitlines():
        if not line.strip():
            continue
        try:
            parts = line.split(None, 8)
            if len(parts) != 9 or not _valid_text(line):
                raise ValueError
            pid, ppid = int(parts[0]), int(parts[1])
            if pid <= 0 or ppid < 0 or pid in seen:
                raise ValueError
            if candidates_only and (
                ppid != 1 or parts[2] != "??"
                or not (
                    _basename(parts[8]) in config.allowed_commands
                    or _python_command(parts[8], config)
                )
            ):
                skipped += 1
                continue
            if parts[3] not in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"):
                raise ValueError
            clock = tuple(int(v) for v in parts[6].split(":"))
            if len(clock) != 3:
                raise ValueError
            calendar = (
                int(parts[7]), months.index(parts[4]) + 1, int(parts[5]), *clock,
            )
            started_at = time.mktime(calendar + (0, 0, -1))
            if tuple(time.localtime(started_at)[:6]) != calendar:
                raise ValueError
        except (ValueError, OverflowError, OSError):
            skipped += 1
            continue
        seen.add(pid)
        processes.append(Process(
            pid, ppid, parts[2], " ".join(parts[3:8]), started_at, parts[8],
        ))
    LOG.debug("ps skipped_rows=%d", skipped)
    return processes


def _escape_applescript(s: str) -> str:
    return (
        s.replace("\\", "\\\\").replace('"', '\\"')
        .replace("\r", " ").replace("\n", " ")
    )


class SystemInterface:
    def __init__(
        self, config: Config, runner: Callable = subprocess.run,
        connector: Callable = tcp_probe, killer: Callable = os.kill,
        sleeper: Callable = time.sleep, monotonic: Callable = time.monotonic,
        wall_time: Callable = time.time, lock: Optional[FileLock] = None,
        spawner: Optional[Callable] = None,
    ) -> None:
        self.config = config
        self._run, self._connect, self._kill = runner, connector, killer
        self._sleep, self.monotonic, self.wall_time = sleeper, monotonic, wall_time
        self._spawn = subprocess.Popen if spawner is None else spawner
        self._spawned_children: list = []
        self.lock = FileLock() if lock is None else lock

    def run_command(
        self, arguments: list[str], budget: Budget,
    ) -> subprocess.CompletedProcess:
        try:
            result = self._run(
                arguments, stdin=subprocess.DEVNULL, capture_output=True,
                text=True, encoding="utf-8", errors="surrogateescape", check=False,
                timeout=budget.timeout(self.config.command_timeout_s),
                env={**os.environ, "LC_ALL": "C", "LANG": "C"},
            )
        except subprocess.TimeoutExpired:
            budget.check()
            raise GuardError("command timed out") from None
        except OSError:
            raise GuardError("command unavailable") from None
        budget.check()
        return result

    def _command(
        self, arguments: list[str], budget: Budget,
    ) -> subprocess.CompletedProcess:
        return self.run_command(arguments, budget)

    def getenv(self, name: str, budget: Budget) -> Optional[str]:
        if name not in self.config.proxy_names:
            raise GuardError("environment variable outside scope")
        result = self._command([self.config.launchctl, "getenv", name], budget)
        if (
            result.stderr or result.returncode not in (0, 1)
            or result.returncode == 1 and result.stdout
        ):
            raise GuardError("environment query failed")
        return result.stdout.rstrip("\r\n") or None

    def unsetenv(self, name: str, budget: Budget) -> None:
        if name not in self.config.proxy_names:
            raise GuardError("environment variable outside scope")
        result = self._command([self.config.launchctl, "unsetenv", name], budget)
        if result.returncode or result.stderr:
            raise GuardError("environment update failed")

    def _listeners(self, selectors: list[str], budget: Budget) -> Optional[int]:
        result = self._command(
            [self.config.lsof, "-nP", "-a", *selectors,
             "-sTCP:LISTEN", "-F", "p"], budget,
        )
        if result.stderr:
            return None
        if result.returncode == 1 and not result.stdout.strip():
            return 0
        if result.returncode:
            return None
        pids: set[int] = set()
        for line in result.stdout.splitlines():
            if line.startswith("p") and line[1:].isdigit() and int(line[1:]) > 0:
                pids.add(int(line[1:]))
            elif not (line.startswith("f") and line[1:].isdigit()):
                return None
        return len(pids) if pids else None

    def listener_count(self, port: int, budget: Budget) -> Optional[int]:
        if port not in self.config.owned_ports:
            raise GuardError("port outside scope")
        return self._listeners([f"-iTCP:{port}"], budget)

    def process_listening(self, pid: int, budget: Budget) -> Optional[bool]:
        try:
            count = self._listeners(["-p", str(pid), "-iTCP"], budget)
        except BudgetExpired:
            raise
        except (GuardError, OSError, ValueError):
            return None
        return None if count is None else count > 0

    def probe(
        self, port: int, budget: Budget, host: str = "127.0.0.1",
    ) -> Optional[bool]:
        if port not in self.config.owned_ports:
            raise GuardError("port outside scope")
        connected = self._connect(
            host, port, budget.timeout(self.config.connect_timeout_s),
        )
        budget.check()
        return connected

    def pause(self, delay: float, budget: Budget) -> None:
        if delay >= budget.remaining():
            raise BudgetExpired("insufficient retry budget")
        self._sleep(delay)
        budget.check()

    def launch_pids(self, budget: Budget) -> set[int]:
        result = self._command([self.config.launchctl, "list"], budget)
        lines = result.stdout.splitlines()
        if (
            result.returncode or result.stderr or not lines
            or lines[0].split() != ["PID", "Status", "Label"]
        ):
            raise GuardError("invalid launchctl listing")
        pids: set[int] = set()
        try:
            for line in lines[1:]:
                parts = line.split(None, 2)
                if len(parts) != 3:
                    raise ValueError
                int(parts[1])
                if parts[0] != "-":
                    pid = int(parts[0])
                    if pid <= 0:
                        raise ValueError
                    pids.add(pid)
        except ValueError:
            raise GuardError("invalid launchctl listing") from None
        return pids

    def processes(self, budget: Budget) -> list[Process]:
        result = self._command([self.config.ps, "-axo", PROCESS_FORMAT], budget)
        if result.returncode:
            raise GuardError("process snapshot failed")
        return _parse_processes(result.stdout, self.config, candidates_only=True)

    def process(self, pid: int, budget: Budget) -> Optional[Process]:
        result = self._command(
            [self.config.ps, "-p", str(pid), "-o", PROCESS_FORMAT], budget,
        )
        if result.returncode == 1 and not result.stdout.strip():
            return None
        if result.returncode:
            raise GuardError("process lookup failed")
        rows = _parse_processes(result.stdout, self.config)
        return rows[0] if len(rows) == 1 and rows[0].pid == pid else None

    def arguments(self, pid: int, budget: Budget) -> tuple[str, ...]:
        result = self._command(
            [self.config.ps, "-p", str(pid), "-o", "args="], budget,
        )
        if result.returncode:
            raise GuardError("process argument lookup failed")
        try:
            return _split_arguments(_text(result.stdout).rstrip("\r\n"))
        except GuardError:
            return ()

    def terminate(self, pid: int, budget: Budget) -> None:
        budget.check()
        self._kill(pid, signal.SIGTERM)

    def _reap_children(self) -> None:
        alive = []
        for child in self._spawned_children:
            try:
                if child.poll() is None:
                    alive.append(child)
            except (OSError, AttributeError):
                pass
        self._spawned_children = alive

    def notify(self, message: str) -> None:
        self._reap_children()
        try:
            safe_message = _escape_applescript(message)
            safe_title = _escape_applescript(self.config.notification_title)
            script = (
                f'display notification "{safe_message}" '
                f'with title "{safe_title}"'
            )
            child = self._spawn(
                [self.config.osascript, "-e", script],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True,
            )
            if child is not None:
                self._spawned_children.append(child)
        except Exception:
            pass


class System(SystemInterface):
    pass


@dataclass
class Result:
    mode: str
    status: str
    events: list[dict[str, object]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        return 0 if self.status in ("REPORT", "ENFORCED", "SKIPPED_LOCKED") else 1

    def to_dict(self) -> dict[str, object]:
        return dict(mode=self.mode, status=self.status,
                    events=self.events, errors=self.errors)


class Guard:
    def __init__(
        self, config: Config, system: Optional[SystemInterface] = None,
    ) -> None:
        self.config = config
        self.system = System(config) if system is None else system

    def _notify(self, result: Result) -> None:
        actions = [
            str(event["action"]) for event in result.events
            if event["action"] in ("UNSET", "TERMINATED", "WOULD_UNSET",
                                   "WOULD_TERMINATE")
        ]
        if self.config.notify and actions:
            try:
                self.system.notify("; ".join(
                    f"{action}: {actions.count(action)}"
                    for action in sorted(set(actions))
                ))
            except Exception:
                pass

    def _dead(self, endpoint: Endpoint, budget: Budget) -> bool:
        listeners = self.system.listener_count(endpoint.port, budget)
        if listeners is None:
            raise GuardError("listener observation unavailable")
        if listeners:
            return False
        if endpoint.host == "127.0.0.1":
            connected = self.system.probe(endpoint.port, budget)
        else:
            connected = self.system.probe(endpoint.port, budget, host=endpoint.host)
        if connected is None:
            raise GuardError("TCP observation unavailable")
        return connected is False

    def _environment(self, budget: Budget, result: Result) -> None:
        for name in self.config.proxy_names:
            budget.check()
            try:
                value = self.system.getenv(name, budget)
                endpoint = parse_endpoint(value, self.config.owned_ports)
                if endpoint is None:
                    continue
                dead = self._dead(endpoint, budget)
                for delay in self.config.retry_backoff_s:
                    if not dead:
                        break
                    self.system.pause(delay, budget)
                    dead = self._dead(endpoint, budget)
                event: dict[str, object] = {
                    "kind": "environment", "name": name, "port": endpoint.port,
                }
                if not dead:
                    event.update(action="KEPT", reason="endpoint_not_dead")
                elif self.config.mode == "report":
                    event.update(action="WOULD_UNSET")
                elif self.system.getenv(name, budget) != value:
                    event.update(action="KEPT", reason="value_changed")
                elif not self._dead(endpoint, budget):
                    event.update(action="KEPT", reason="endpoint_recovered")
                else:
                    current_val = self.system.getenv(name, budget)
                    if current_val != value:
                        event.update(action="KEPT", reason="value_changed")
                        result.events.append(event)
                        continue
                    self.system.unsetenv(name, budget)
                    event.update(action="UNSET")
                result.events.append(event)
            except BudgetExpired:
                raise
            except (GuardError, OSError, ValueError):
                result.errors.append("ENV_AUDIT_FAILED:" + name)

    def _candidate(
        self, process: Process, managed: set[int], budget: Budget,
    ) -> bool:
        budget.check()
        if (
            process.pid <= 1 or process.ppid != 1
            or process.tty not in (None, "??") or process.pid in managed
            or not process.start_time
            or self.system.wall_time() - process.started_at
            <= self.config.orphan_min_age_s
        ):
            return False
        if allowed_command(process.command, config=self.config):
            return True
        return _python_command(process.command, self.config) and allowed_command(
            process.command, self.system.arguments(process.pid, budget),
            self.config,
        )

    def _processes(self, budget: Budget, result: Result) -> None:
        managed = self.system.launch_pids(budget)
        for process in self.system.processes(budget):
            budget.check()
            try:
                if not self._candidate(process, managed, budget):
                    continue
                event: dict[str, object] = {"kind": "process", "pid": process.pid}
                fresh = process
                if self.config.mode == "enforce":
                    managed_now = self.system.launch_pids(budget)
                    fresh = self.system.process(process.pid, budget)
                    if (
                        fresh is None or fresh.identity != process.identity
                        or not self._candidate(fresh, managed_now, budget)
                    ):
                        event.update(action="KEPT", reason="process_changed")
                        result.events.append(event)
                        continue
                listening = self.system.process_listening(process.pid, budget)
                if listening is not False:
                    reason = "listening" if listening else "listener_unknown"
                    event.update(action="KEPT", reason=reason)
                    LOG.debug("process pid=%d skipped: %s", process.pid, reason)
                elif self.config.mode == "report":
                    event.update(action="WOULD_TERMINATE")
                elif self.system.process(process.pid, budget) != fresh:
                    event.update(action="KEPT", reason="process_changed")
                else:
                    listening_now = self.system.process_listening(
                        process.pid, budget,
                    )
                    if listening_now is not False:
                        reason = (
                            "listening_at_termination"
                            if listening_now else "listener_unknown"
                        )
                        event.update(action="KEPT", reason=reason)
                        LOG.debug(
                            "process pid=%d skipped: %s", process.pid, reason,
                        )
                        result.events.append(event)
                        continue
                    final = self.system.process(process.pid, budget)
                    if final is None or final.identity != fresh.identity:
                        event.update(action="KEPT", reason="process_changed")
                        result.events.append(event)
                        continue
                    self.system.terminate(process.pid, budget)
                    event.update(action="TERMINATED")
                result.events.append(event)
            except BudgetExpired:
                raise
            except (GuardError, OSError, ValueError):
                result.errors.append(f"PROCESS_AUDIT_FAILED:{process.pid}")

    def run(self) -> Result:
        result = Result(
            self.config.mode,
            "REPORT" if self.config.mode == "report" else "ENFORCED",
        )
        budget = Budget(self.config.run_timeout_s, self.system.monotonic)
        try:
            acquired = self.system.lock.acquire()
        except (GuardError, OSError):
            result.status = "ERROR"
            result.errors.append("LOCK_FAILED")
            return result
        if not acquired:
            result.status = "SKIPPED_LOCKED"
            return result
        try:
            self._environment(budget, result)
            try:
                self._processes(budget, result)
            except BudgetExpired:
                raise
            except (GuardError, OSError, ValueError):
                result.errors.append("PROCESS_DISCOVERY_FAILED")
        except BudgetExpired:
            result.status = "TIMEOUT"
            result.errors.append("EXECUTION_BUDGET_EXHAUSTED")
        finally:
            try:
                self.system.lock.release()
            except (GuardError, OSError):
                result.errors.append("LOCK_RELEASE_FAILED")
        if result.errors and result.status != "TIMEOUT":
            result.status = "ERROR"
        self._notify(result)
        return result


def parse_config(
    argv: Optional[list[str]] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> Config:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("report", "enforce"), default=None)
    parser.add_argument("--no-notify", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        return Config.from_environment(
            os.environ if environ is None else environ, arguments.mode,
            notify=False if arguments.no_notify else None,
        )
    except (ValueError, TypeError, re.error):
        parser.error("invalid SYSTEM_GUARD configuration")
        raise AssertionError("unreachable")


def main(
    argv: Optional[list[str]] = None, *,
    system: Optional[SystemInterface] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> int:
    config = parse_config(argv, environ)
    result = Guard(config, system).run()
    print(json.dumps(result.to_dict(), sort_keys=True))
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
