"""Делегированные хуки жизненного цикла Run для persistent-пула и cold-spawn."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import IO, cast

from core.stdio_resident.process_io import EOF as _STDIO_EOF
from core.stdio_resident.process_io import LINE as _STDIO_LINE
from core.stdio_resident.process_io import TIMEOUT as _STDIO_TIMEOUT

from .persistent_worker_adapter import AgyPersistentWorkerPool, StdioWriteError
from .persistent_worker_config import (
    PersistentAcquireRequest, PersistentLease, PersistentReleaseParams, RunCloseContext,
    RunPumpDrainContext, RunSpawnContext, compute_env_digest, persistent_worker_settings,
)

__all__ = [
    "RunCloseContext", "RunPumpDrainContext", "RunSpawnContext", "cancel_run_persistent",
    "close_run_resources", "drain_run_stderr", "feed_run_stdin", "finish_run_pump_drain",
    "iter_run_stdout_lines", "join_run_source", "release_run_persistent",
    "resolve_run_chat_key", "start_run_process",
]

_LOGGER = logging.getLogger(__name__)


def _lease_of(run: object) -> PersistentLease | None:
    raw = cast(object, getattr(run, "_persistent_lease", None))
    return raw if isinstance(raw, PersistentLease) else None


def _proc_of(run: object) -> subprocess.Popen[bytes]:
    return cast(subprocess.Popen[bytes], getattr(run, "proc"))


def start_run_process(run: object, ctx: RunSpawnContext) -> float:
    """Арендовать persistent-слот или запустить cold-процесс; вернуть monotonic-время старта."""
    run_cid = str(cast(object, getattr(run, "run_cid", "")))
    for k, v in (
        ("_release_lock", threading.Lock()), ("_persistent_lease", None),
        ("_persistent_mode", False), ("_persistent_reused", False),
        ("_persistent_turn_ok", False), ("_persistent_cancelled", False),
        ("_persistent_resolved_cid", run_cid),
    ):
        setattr(run, k, v)
    pw_cfg = persistent_worker_settings(config_path=ctx.config_path)
    pool = cast(AgyPersistentWorkerPool, ctx.pool)
    if not pw_cfg.enabled:
        pool.reconcile_disabled()
    t0 = time.monotonic()
    try:
        lease: PersistentLease | None = None
        if pw_cfg.enabled and ctx.add_dir is None:
            digest = compute_env_digest(
                ctx.cli_mode, ctx.zero_canon, str(ctx.launch_env.get("HOME") or ""), ctx.settings_arg
            )
            req = PersistentAcquireRequest(
                chat_key=ctx.chat_key, cid=run_cid, model=ctx.model, effort=ctx.effort,
                cwd=ctx.work_dir, env_digest=digest,
                review_profile="zero-canon" if ctx.zero_canon else "standard",
                argv_builder=lambda: list(ctx.cmd), env=ctx.launch_env,
            )
            lease = pool.acquire(req, pw_cfg)
        if lease is not None:
            setattr(run, "_persistent_lease", lease)
            setattr(run, "_persistent_mode", True)
            setattr(run, "_persistent_reused", lease.reused)
            setattr(run, "proc", lease.handle.proc)
            return t0
        setattr(run, "proc", ctx.spawn_cold())
    except BaseException:
        ctx.on_cold_fail()
        raise
    return t0


def feed_run_stdin(run: object) -> None:
    """Подать промпт на stdin; для persistent-слота поток остаётся открытым."""
    stdin_line = str(cast(object, getattr(run, "stdin_line", "")))
    lease = _lease_of(run)
    if lease is not None:
        try:
            lease.handle.write(stdin_line.encode("utf-8"))
        except (StdioWriteError, BrokenPipeError, OSError, ValueError):
            rel = cast(Callable[..., None], getattr(run, "_release_persistent"))
            rel(success=False, cancel=True)
        return
    proc = _proc_of(run)
    stdin = proc.stdin
    try:
        if stdin is not None:
            _ = stdin.write(stdin_line.encode("utf-8"))
            stdin.flush()
    except (BrokenPipeError, OSError, ValueError):
        pass
    finally:
        if stdin is not None:
            try:
                stdin.close()
            except (BrokenPipeError, OSError, ValueError):
                pass
        proc.stdin = None


def drain_run_stderr(run: object, noise_re: re.Pattern[str]) -> None:
    """Считать хвост stderr для cold-spawn (не более 40 строк)."""
    head: list[str] = []
    stderr = cast(IO[bytes] | None, _proc_of(run).stderr)
    note_cap = cast(Callable[[str], None], getattr(run, "_note_capacity_line"))
    try:
        if stderr is not None:
            while True:
                raw: bytes = stderr.readline()
                if not raw:
                    break
                line = raw.decode("utf-8", "replace").rstrip()
                if not line:
                    continue
                note_cap(line)
                if noise_re.search(line):
                    continue
                head.append(line)
                if len(head) > 40:
                    del head[0]
    except (OSError, ValueError) as exc:
        _LOGGER.debug("stderr drain stopped: %s", exc)
    err_box = cast(list[str], getattr(run, "err_box"))
    err_box.append("\n".join(head).strip())


def iter_run_stdout_lines(run: object) -> Iterator[str]:
    """Итератор строк stdout: прямой пайп (cold) или generation-очередь (persistent)."""
    lease = _lease_of(run)
    if lease is None:
        stdout = cast(IO[bytes] | None, _proc_of(run).stdout)
        if stdout is not None:
            while True:
                raw: bytes = stdout.readline()
                if not raw:
                    break
                yield raw.decode("utf-8", "replace").strip()
        return
    stop_watch = cast(threading.Event, getattr(run, "_stop_watch"))
    while not (stop_watch.is_set() or bool(getattr(run, "capacity_exhausted", ""))):
        kind, tagged = lease.handle.read_stdout_line_outcome(timeout_s=lease.pump_tick_s)
        if kind == _STDIO_LINE and tagged is not None:
            yield tagged.line.strip()
        elif kind == _STDIO_EOF or (kind == _STDIO_TIMEOUT and not lease.handle.is_alive()):
            return


def finish_run_pump_drain(run: object, ctx: RunPumpDrainContext) -> int:
    """Завершить окно SQLite-drain и вычислить код возврата хода (persistent или cold)."""
    lease = _lease_of(run)
    tail = cast(object, getattr(run, "_tail"))
    proc_done = cast(threading.Event, getattr(run, "_proc_done"))
    join_src = cast(Callable[..., None], getattr(run, "_join_source"))
    if lease is not None:
        t_exit = time.monotonic()
        drain_w = min(lease.drain_window_s, ctx.drain_max_s)
        setattr(run, "_drain_t0", t_exit)
        setattr(tail, "drain_deadline", t_exit + drain_w)
        proc_done.set()
        join_src(t_exit, drain_window_s=drain_w)
        turn_ok = bool(getattr(run, "_persistent_turn_ok", False))
        if not turn_ok:
            tail_err = lease.handle.stderr_tail().strip()
            if tail_err:
                cast(list[str], getattr(run, "err_box")).append(tail_err)
        return 0 if (ctx.result_ev and turn_ok) else 1
    try:
        rc: int | None = _proc_of(run).wait(timeout=ctx.proc_exit_wait_s)
    except subprocess.TimeoutExpired:
        rc = None
    time.sleep(0.05)
    t_exit = time.monotonic()
    drain_w = min(
        persistent_worker_settings(config_path=ctx.config_path).drain_window_s,
        ctx.drain_max_s,
    )
    setattr(run, "_drain_t0", t_exit)
    setattr(tail, "drain_deadline", t_exit + drain_w)
    proc_done.set()
    join_src(t_exit, drain_window_s=drain_w)
    return (0 if ctx.result_ev else 1) if rc is None else rc


def join_run_source(
    run: object, t_exit: float, window: float, join_timeout_s: float, on_timeout: Callable[[str], None]
) -> None:
    """Дождаться потока транскрипта в бюджете окна drain и прервать активный SELECT."""
    tail = cast(object, getattr(run, "_tail"))
    thread = cast(object, getattr(tail, "thread"))
    if isinstance(thread, threading.Thread) and thread.ident is None:
        return
    join_fn = cast(Callable[..., None], getattr(thread, "join"))
    is_alive_fn = cast(Callable[[], bool], getattr(thread, "is_alive"))
    join_fn(timeout=max(0.0, t_exit + window - time.monotonic()))
    if not is_alive_fn():
        return
    cast(Callable[[], None], getattr(tail, "interrupt_active_query"))()
    join_fn(timeout=join_timeout_s)
    if is_alive_fn():
        on_timeout(str(cast(object, getattr(tail, "cid", "")))[:8] or "-")


def release_run_persistent(
    run: object, pool: AgyPersistentWorkerPool, config_path: Path, *, success: bool, cancel: bool
) -> None:
    """Идемпотентно вернуть или уничтожить persistent-слот под `_release_lock`."""
    lock = cast(threading.Lock, getattr(run, "_release_lock"))
    with lock:
        lease = _lease_of(run)
        if lease is None or lease.released:
            return
        if cancel:
            setattr(run, "_persistent_cancelled", True)
        cid = str(
            cast(object, getattr(run, "_persistent_resolved_cid", ""))
            or cast(object, getattr(run, "run_cid", ""))
        )
        cancelled_now = bool(getattr(run, "_persistent_cancelled", False))
    pw_cfg = persistent_worker_settings(config_path=config_path)
    pool.release(
        lease,
        PersistentReleaseParams(
            success=bool(success and not cancel and not cancelled_now),
            cancel=cancel, cid=cid, still_enabled=pw_cfg.enabled, max_slots=pw_cfg.max_slots,
        ),
    )


def cancel_run_persistent(run: object) -> None:
    """Аварийно отменить persistent-ход и вернуть/уничтожить арендованный слот."""
    cast(threading.Event, getattr(run, "_stop_watch")).set()
    cast(threading.Event, getattr(run, "_proc_done")).set()
    cast(Callable[..., None], getattr(run, "_release_persistent"))(success=False, cancel=True)


def close_run_resources(run: object, ctx: RunCloseContext) -> None:
    """Закрыть ресурсы хода: вернуть persistent-слот или убить группу cold-процесса."""
    cast(threading.Event, getattr(run, "_stop_watch")).set()
    cast(threading.Event, getattr(run, "_proc_done")).set()
    tail = cast(object, getattr(run, "_tail"))
    cast(Callable[[], None], getattr(tail, "interrupt_active_query"))()
    cast(Callable[[], None], getattr(cast(object, getattr(run, "controller")), "close"))()
    if _lease_of(run) is not None:
        cancelled = bool(getattr(run, "_persistent_cancelled", False))
        turn_ok = bool(
            getattr(run, "_persistent_turn_ok", False)
            and not cancelled
            and not bool(getattr(run, "capacity_exhausted", ""))
        )
        cast(Callable[..., None], getattr(run, "_release_persistent"))(
            success=turn_ok, cancel=cancelled
        )
    else:
        proc = _proc_of(run)
        ctx.kill_group(proc)
        ctx.unregister_proc(proc)
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass
    thread = cast(object, getattr(tail, "thread"))
    is_alive_fn = cast(Callable[[], bool], getattr(thread, "is_alive"))
    if is_alive_fn() and thread is not threading.current_thread():
        cast(Callable[..., None], getattr(thread, "join"))(timeout=ctx.join_timeout_s)


def resolve_run_chat_key(ctx: Mapping[str, object]) -> str:
    """Извлечь нормализованный ключ сессии хода (sess_key > explicit_state.session_key > chat_id)."""
    sess_key = ctx.get("sess_key")
    if isinstance(sess_key, (tuple, list)):
        parts = [s for p in cast(tuple[object, ...] | list[object], sess_key) if p is not None and (s := str(p).strip())]
        if parts:
            return hashlib.sha256(json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()[:32]
    elif isinstance(sess_key, str):
        if s_key := sess_key.strip():
            return hashlib.sha256(json.dumps(s_key, ensure_ascii=False).encode("utf-8")).hexdigest()[:32]
    elif sess_key:
        return hashlib.sha256(json.dumps(str(sess_key), ensure_ascii=False).encode("utf-8")).hexdigest()[:32]
    exp_st = ctx.get("explicit_state")
    if exp_st is not None and bool(getattr(exp_st, "handled", False)):
        if exp_key := str(cast(object, getattr(exp_st, "session_key", "")) or "").strip():
            return exp_key
    return str(ctx.get("chat_id") or "").strip()
