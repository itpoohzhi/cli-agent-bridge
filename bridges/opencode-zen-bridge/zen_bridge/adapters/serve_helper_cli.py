"""Ранний помощник serve: один лидер группы на попытку, lease и дренаж пайпов."""

from __future__ import annotations

import errno
import json
import os
import select
import signal
import subprocess
import sys
import time
from pathlib import Path


def _lstart_of(pid: int) -> str:
    """lstart процесса из ps; при сбое ps — epoch-секунды."""
    try:
        out = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return out.stdout.strip() or str(int(time.time()))
    except (OSError, subprocess.SubprocessError):
        return str(int(time.time()))


def _write_lease(
    lease_path: Path,
    base_payload: dict[str, object],
    extra: dict[str, object],
) -> None:
    """Атомарно опубликовать lease помощника."""
    payload = dict(base_payload)
    payload.update(extra)
    tmp_path = lease_path.with_suffix(".tmp")
    try:
        _ = tmp_path.write_text(json.dumps(payload), "utf-8")
        os.replace(tmp_path, lease_path)
    except OSError:
        pass


def _fd_ready(fd: int = 0) -> bool:
    """EOF на lifeline fd 0 виден без блокировки."""
    try:
        ready, _w, _x = select.select([fd], [], [], 0)
        return bool(ready)
    except BlockingIOError:
        return False
    except (OSError, ValueError) as _gone_exc:
        if isinstance(_gone_exc, OSError) and _gone_exc.errno in (
            errno.EAGAIN,
            errno.EWOULDBLOCK,
        ):
            return False
        return True


def _drain_and_forward(pipes: list[int]) -> None:
    """Дренировать остаток пайпов, чтобы потомок не остался с полным буфером."""
    for fd in pipes:
        try:
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                _ = sys.stderr.write(chunk.decode("utf-8", "replace"))
        except OSError:
            pass


def _group_members(proc: subprocess.Popen[bytes], pgid: int) -> list[int]:
    """Живые члены группы, кроме самого помощника (ps — в отдельной сессии)."""
    _ = proc.poll()
    try:
        listing = subprocess.run(
            ["ps", "-A", "-o", "pid=,pgid="],
            capture_output=True,
            text=True,
            timeout=2,
            start_new_session=True,
        )
    except (OSError, subprocess.SubprocessError):
        return [proc.pid] if proc.poll() is None else []
    members: list[int] = []
    for row in listing.stdout.splitlines():
        cols = row.split()
        if (
            len(cols) == 2
            and cols[0].isdecimal()
            and cols[1] == str(pgid)
            and int(cols[0]) != os.getpid()
        ):
            pid = int(cols[0])
            if pid == proc.pid and proc.poll() is not None:
                continue
            members.append(pid)
    return members


def _cleanup_process_group(
    proc: subprocess.Popen[bytes],
    pgid: int,
    pipes: list[int],
    lease_path: Path,
) -> None:
    """Гарантированное завершение группы процессов и удаление lease."""
    try:
        os.killpg(pgid, signal.SIGTERM)
    except OSError:
        if proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass
    members = _group_members(proc, pgid)
    deadline = time.monotonic() + 4.0
    while members and time.monotonic() < deadline:
        time.sleep(0.1)
        members = _group_members(proc, pgid)
    if members:
        for pid in members:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        kill_deadline = time.monotonic() + 2.0
        while members and time.monotonic() < kill_deadline:
            time.sleep(0.05)
            members = _group_members(proc, pgid)
    _drain_and_forward(pipes)
    if not members:
        try:
            lease_path.unlink()
        except OSError:
            pass


def _event_pump(
    proc: subprocess.Popen[bytes],
    pipes: list[int],
    stopped: dict[str, bool],
) -> int:
    """Цикл пересылки потоков stderr/stdout до завершения процесса."""
    while True:
        if stopped["flag"] or _fd_ready():
            return 0
        poll = proc.poll()
        if poll is not None:
            return int(poll)
        watch = [0, *pipes]
        try:
            ready, _w, _x = select.select(watch, [], [], 0.05)
        except (OSError, ValueError):
            ready = []
        for item in ready:
            if item == 0:
                stopped["flag"] = True
                continue
            try:
                chunk = os.read(item, 65536)
            except OSError:
                chunk = b""
            if chunk:
                try:
                    _ = sys.stderr.write(chunk.decode("utf-8", "replace"))
                    _ = sys.stderr.flush()
                except OSError:
                    pass
        if stopped["flag"]:
            return 0


def _parse_cli_args(args: list[str]) -> tuple[str, int, str, Path, int, str] | None:
    """Валидация аргументов командной строки раннего помощника."""
    if len(args) != 6:
        return None
    attempt_id, port_t, opencode_bin, lease_t, ppid_t, parent_lstart = args
    if not (attempt_id and opencode_bin and lease_t and parent_lstart):
        return None
    if not (port_t.isdecimal() and ppid_t.isdecimal()):
        return None
    port, ppid = int(port_t), int(ppid_t)
    if not (1 <= port <= 65535 and ppid > 0):
        return None
    return attempt_id, port, opencode_bin, Path(lease_t), ppid, parent_lstart


def _init_helper_lease(
    attempt_id: str, port: int, lease_dir: Path, ppid: int, parent_lstart: str
) -> tuple[Path, dict[str, object]] | None:
    """Создаёт каталог lease и записывает начальное состояние попытки."""
    try:
        lease_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(lease_dir, 0o700)
    except OSError:
        return None
    lease_path = lease_dir / f"lease-{attempt_id}.json"
    helper_lstart = _lstart_of(os.getpid())
    base_payload: dict[str, object] = {
        "schema_version": 1,
        "attempt_id": attempt_id,
        "owner_uid": os.getuid(),
        "parent_pid": ppid,
        "parent_start_ts": parent_lstart,
        "helper_pid": os.getpid(),
        "helper_lstart": helper_lstart,
        "pgid": os.getpgrp(),
        "port": port,
        "start_ts": time.time(),
        "phase": "starting",
    }
    _write_lease(lease_path, base_payload, {})
    return lease_path, base_payload


def _spawn_serve_subprocess(
    opencode_bin: str, port: int
) -> subprocess.Popen[bytes] | None:
    """Запускает процесс serve с изолированными пайпами."""
    serve_env = dict(os.environ)
    _ = serve_env.pop("OPENCODE_BIN", None)
    try:
        return subprocess.Popen(
            [opencode_bin, "serve", "--hostname", "127.0.0.1", "--port", str(port)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=False,
            close_fds=True,
            env=serve_env,
        )
    except OSError:
        return None


def _run_serve_helper_cli(args: list[str]) -> int:
    """Ранний помощник serve: один лидер группы на попытку, lease и дренаж пайпов."""
    parsed = _parse_cli_args(args)
    if parsed is None:
        return 2
    attempt_id, port, opencode_bin, lease_dir, ppid, parent_lstart = parsed
    stopped = {"flag": False}

    def _on_term(_signum: int, _frame: object) -> None:
        stopped["flag"] = True

    _ = signal.signal(signal.SIGTERM, _on_term)
    lease_res = _init_helper_lease(attempt_id, port, lease_dir, ppid, parent_lstart)
    if lease_res is None:
        return 2
    lease_path, base_payload = lease_res
    if _fd_ready():
        try:
            lease_path.unlink()
        except OSError:
            pass
        return 0

    proc = _spawn_serve_subprocess(opencode_bin, port)
    if proc is None:
        return 2

    _write_lease(
        lease_path,
        base_payload,
        {"serve_pid": proc.pid, "serve_lstart": _lstart_of(proc.pid), "phase": "ready"},
    )
    try:
        _ = sys.stdout.write(
            json.dumps({"serve_pid": proc.pid, "pgid": os.getpgrp()}) + "\n"
        )
        _ = sys.stdout.flush()
    except OSError:
        pass

    pipes: list[int] = []
    for stream in (proc.stdout, proc.stderr):
        if stream is not None:
            pipes.append(stream.fileno())
            os.set_blocking(stream.fileno(), False)

    try:
        return _event_pump(proc, pipes, stopped)
    finally:
        _cleanup_process_group(proc, os.getpgrp(), pipes, lease_path)
