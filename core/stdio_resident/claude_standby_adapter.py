"""Тонкий standby-адаптер Claude Code (`claude --print --input-format stream-json`) для DemandStandbyPool (AD-003, AD-005, BND-003)."""
from __future__ import annotations

import atexit
import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial
from typing import IO, cast, final

from core.claude_zero_canon import build_claude_zero_canon_flags
from core.stdio_resident.claude_driver import ClaudeStreamJsonDriver
from core.stdio_resident.demand_standby_pool import DemandStandbyPool, load_dynamic_config
from core.stdio_resident.process_reaper import get_pgid_rss_bytes, get_process_start_time, terminate_process_group
from core.stdio_resident.standby_pool_fsm import ProfileKey, StandbyAdapter, parse_limits

__all__ = ["BACKEND_ID", "ClaudeRunRequest", "ClaudeStandbyAdapter", "ClaudeWarmHandle",
           "acquire_claude_run_proc", "encode_claude_stdin_prompt"]

_log = logging.getLogger(__name__)
BACKEND_ID = "claude-p-bridge"
_ENV_DIGEST_KEYS = ("ANTHROPIC_BASE_URL", "HTTPS_PROXY", "HTTP_PROXY", "NODE_EXTRA_CA_CERTS", "CLAUDE_CONFIG_DIR", "HOME")
_BYTES_PER_MB = 1024 * 1024


def encode_claude_stdin_prompt(prompt: str, *, stream_json_input: bool) -> bytes:
    """stream-json: одна user-строка NDJSON; иначе сырой UTF-8 промпт."""
    if not stream_json_input:
        return prompt.encode("utf-8")
    frame = {"type": "user", "message": {"role": "user", "content": prompt}}
    return json.dumps(frame, ensure_ascii=False).encode("utf-8") + b"\n"


@dataclass
class ClaudeWarmHandle:
    proc: subprocess.Popen[bytes]
    profile: ProfileKey
    zc_home_root: str = ""
    cwd: str = ""
    pgid: int = 0
    start_time: str = ""
    stream_json_input: bool = True


def _default_argv(claude_bin: str, profile: ProfileKey) -> list[str]:
    argv = [claude_bin, "--print", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
            "--include-partial-messages", "--model", profile.model, "--effort", profile.effort]
    if profile.is_zero_canon:
        argv.extend(build_claude_zero_canon_flags(has_images=False))
    return [*argv, "--permission-mode", "bypassPermissions"]


def _host_env() -> Mapping[str, str]:
    return {k: v for k, v in os.environ.items() if k != "CLAUDE_P_BRIDGE_KEY"}


def _make_private_dirs() -> tuple[str, str]:
    root = tempfile.mkdtemp(prefix="zc-claude-")
    os.chmod(root, 0o700)
    cwd = os.path.join(root, "cwd")
    os.mkdir(cwd, 0o700)
    return root, cwd


@final
class ClaudeStandbyAdapter:
    """Жизненный цикл прогретого `claude`-процесса: spawn без stdin-записи, claim, dispose."""

    def __init__(self, *, claude_bin: str = "claude", argv_factory: Callable[[ProfileKey], list[str]] | None = None,
                 base_env_provider: Callable[[], Mapping[str, str]] | None = None,
                 driver: ClaudeStreamJsonDriver | None = None, settle_s: float = 0.2) -> None:
        self._argv = argv_factory or partial(_default_argv, claude_bin)
        self._base_env = base_env_provider or _host_env
        self._driver = driver or ClaudeStreamJsonDriver()
        self._settle_s = settle_s

    def spawn_warm(self, profile: ProfileKey, *, timeout_s: float = 30.0) -> ClaudeWarmHandle:
        env, root, cwd = dict(self._base_env()), "", ""
        try:
            if profile.is_zero_canon:
                root, cwd = _make_private_dirs()
                env = self._driver.build_zero_canon_env(env, root)
            proc = subprocess.Popen(self._argv(profile), cwd=cwd or None, env=env, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        except (OSError, ValueError) as exc:
            shutil.rmtree(root, ignore_errors=True)
            raise RuntimeError("claude_standby_spawn_failed") from exc
        handle = ClaudeWarmHandle(proc, profile, root, cwd, _pgid_of(proc), get_process_start_time(proc.pid))
        try:  # процесс ждёт 1-е user-сообщение на stdin; мгновенное завершение = провал спавна
            _ = proc.wait(timeout=max(0.0, min(self._settle_s, timeout_s)))
        except subprocess.TimeoutExpired:
            return handle
        self.dispose(handle)
        raise RuntimeError("claude_standby_spawn_failed")

    def is_alive(self, handle: ClaudeWarmHandle) -> bool:
        return handle.proc.poll() is None

    def claim(self, handle: ClaudeWarmHandle) -> ClaudeWarmHandle:
        if not self.is_alive(handle):
            raise RuntimeError("claude_standby_dead")
        return handle

    def dispose(self, handle: ClaudeWarmHandle) -> None:
        _ = terminate_process_group(handle.proc, handle.pgid, handle.start_time, cancel_grace_s=2.0)
        for stream in (handle.proc.stdin, handle.proc.stdout, handle.proc.stderr):
            try:
                if stream is not None:
                    stream.close()
            except OSError:
                pass
        if handle.zc_home_root:
            shutil.rmtree(handle.zc_home_root, ignore_errors=True)

    def rss_mb(self, handle: ClaudeWarmHandle) -> float:
        rss = get_pgid_rss_bytes(handle.pgid)
        return rss / _BYTES_PER_MB if rss else 0.0


def _pgid_of(proc: subprocess.Popen[bytes]) -> int:
    try:
        return os.getpgid(proc.pid)
    except OSError:
        return proc.pid


@final
class _StreamJsonStdin:
    """stdin-обёртка: сырой промпт хода Run -> stream-json user-кадр (Run не знает о warm-режиме)."""

    def __init__(self, raw: IO[bytes]) -> None:
        self._raw = raw

    def write(self, data: bytes) -> int:
        _ = self._raw.write(encode_claude_stdin_prompt(data.decode("utf-8"), stream_json_input=True))
        self._raw.flush()
        return len(data)

    def close(self) -> None:
        self._raw.close()


@dataclass(frozen=True)
class ClaudeRunRequest:
    model: str
    effort: str
    img_dir: object | None = None
    session_plan: object | None = None
    env_digest: str = ""
    cwd_class: str = "workspace"


_pool: DemandStandbyPool | None = None
_pool_lock = threading.Lock()


def _limits_enabled() -> bool:
    return parse_limits(os.environ, load_dynamic_config()).enabled


def _get_pool() -> DemandStandbyPool:
    global _pool
    with _pool_lock:
        if _pool is None:
            pool = DemandStandbyPool({BACKEND_ID: cast("StandbyAdapter", cast("object", ClaudeStandbyAdapter()))},
                                     config_provider=lambda: (os.environ, load_dynamic_config()))
            _ = atexit.register(pool.drain_and_shutdown)
            _pool = pool
        return _pool


def _env_digest() -> str:
    raw = "\0".join(os.environ.get(k, "") for k in _ENV_DIGEST_KEYS)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _noop() -> None:
    return None


def acquire_claude_run_proc(req: ClaudeRunRequest,
                            spawn_cold_fn: Callable[[], subprocess.Popen[bytes]],
                            ) -> tuple[subprocess.Popen[bytes], bool, Callable[[], None]]:
    """(proc, warm, release): warm-claim при включённом пуле, иначе холодный spawn без инициализации пула."""
    if req.img_dir is not None or req.session_plan is not None or not _limits_enabled():
        return spawn_cold_fn(), False, _noop
    profile = ProfileKey(BACKEND_ID, req.model, req.effort, "zero-canon", req.env_digest or _env_digest(), req.cwd_class)
    try:
        pool = _get_pool()
        claimed = pool.claim(profile)  # miss -> pool сам ставит submit_demand
    except Exception as exc:  # noqa: BLE001 - пул не должен ронять ход: fallback на холодный старт
        _log.warning("claude standby claim failed err=%s", type(exc).__name__)
        return spawn_cold_fn(), False, _noop
    if claimed is None or not isinstance(claimed.payload, ClaudeWarmHandle):
        return spawn_cold_fn(), False, _noop
    handle = claimed.payload
    if handle.stream_json_input and handle.proc.stdin is not None:
        handle.proc.stdin = cast("IO[bytes]", cast("object", _StreamJsonStdin(handle.proc.stdin)))
    return handle.proc, True, partial(pool.release_claimed, claimed.slot_id, success=True)
