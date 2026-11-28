#!/usr/bin/env python3
"""OpenAI-совместимый мост к CLI `claude -p` (Claude Code).
Один запрос = один stream-json ход; протокол только из core (AD-002).
Reasoning нормализуется всегда; теги инструментов в OFF+TEXT буквальны,
в EMULATE/FORBID/OFF+ERROR — fail-closed без result-fallback (AD-004/005).
Вложения: изоляция 0700/0600, Read через --add-dir, cleanup после reap (AD-003).
"""

from __future__ import annotations

import contextlib
import hmac
import json
import os
import queue
import select
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, NamedTuple, cast

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT, Path(__file__).resolve().parents[1], Path(__file__).resolve().parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from core.admission_idle_policy import format_claude_done_fields  # noqa: E402
from core.bridge_watchdog_settings import BridgeWatchdogFacade  # noqa: E402
from core.chat_key import SOURCES_SESSION_ID, resolve_chat_key  # noqa: E402
from core.claude_bridge_telemetry import format_done_usage_suffix, project_wire_usage  # noqa: E402
from core.claude_prompt import PromptBudgetConfig, prepare_prompt_with_cap, wire_cache_creation_enabled  # noqa: E402
from core.claude_session import (  # noqa: E402
    NO_PERSISTENCE_FLAG, SessionConfig, SessionMode, SessionPlan, SessionStore,
    assert_zero_canon_argv_safe, build_session_argv, is_session_reuse_allowed_profile,
)
from core.http_accept import load_admission_idle_config  # noqa: E402
from core.http_server_error import handle_accept_error  # noqa: E402
from core.log_redaction import redact_log_text  # noqa: E402
from core.log_rotation_adapters import emit_service_log as _emit_rotated_log  # noqa: E402
from core.claude_zero_canon import (  # noqa: E402
    CLAUDE_PRESERVED_CA_FILES, build_claude_zero_canon_env, build_claude_zero_canon_flags,
    filter_claude_settings, filter_claude_state, serialize_claude_json,
)
from core.stdio_resident.claude_standby_adapter import ClaudeRunRequest, acquire_claude_run_proc  # noqa: E402
from core.proc_groups import live_proc_groups, spawn_registered as _spawn_registered  # noqa: E402
from core.recovery_flags import read_diagnostic_redact_margin_chars, read_diagnostic_window_chars, read_post_call_cutoff_enabled  # noqa: E402
from core.subbridge_lifecycle import SubbridgeHooks, SubbridgeLifecycle  # noqa: E402
from core.tool_post_call_policy import PostCallPolicy  # noqa: E402
from core.usage_wire import CACHE_READ_KEYS, build_wire_usage, extract_cache_creation_tokens  # noqa: E402

try:
    from core.watchdog import AdaptiveTimeoutController
except ImportError:
    AdaptiveTimeoutController = None  # type: ignore[assignment,misc]

try:
    from core.runtime_env import resolve_toolless_tag_policy, synthesize_required_bash_desc_enabled
    from core.stream_framing import format_stream_error_sse
    from core.tool_emulation import (  # noqa: E402
        DEFAULT_MAX_IMAGE_BYTES, DEFAULT_MAX_IMAGES, DEFAULT_MAX_TOTAL_IMAGE_BYTES, ImageInputError,
        LiveParserError, StreamNormalizer, _messages_to_prompt, build_tool_schemas,
        extract_data_url_images, extract_thinking_delta, sanitize_tool_call,
    )
    from core.tool_mode import (
        TOOLLESS_PURE_TEXT_HINT, NormalizerModeSpec, NormalizerSinks, ToolMode,
        build_mode_spec, format_tool_mode_log, resolve_tool_mode,
    )
except ImportError as exc:
    # Fail-closed (AD-002): без согласованного core мост не запускается;
    # встроенной запасной копии парсера не существует.
    sys.stderr.write(
        "claude-p-bridge: core.tool_emulation is required "
        f"(repo root {_REPO_ROOT}): {exc}\n"
    )
    raise SystemExit(1) from exc


def _raw_cache_read(usage: dict) -> object:
    """Первое заданное (не `None`) сырое значение cache-read без фильтрации."""
    for key in CACHE_READ_KEYS:
        if usage.get(key) is not None:
            return usage[key]
    return None


def _wire_usage(usage: dict) -> dict:
    """Кэш исключён из Claude input_tokens (fixtures/claude_result_usage.json).

    core.usage_wire единолично фильтрует и прибавляет сырой cache-read/creation;
    top-level `cache_creation_input_tokens` — только по opt-in флагу (AD-002).
    """
    wire, inconsistent = build_wire_usage(
        usage.get("input_tokens", 0),
        usage.get("output_tokens", 0),
        _raw_cache_read(usage),
        extract_cache_creation_tokens(usage),
        input_includes_cache=False,
    )
    if inconsistent:
        _log("usage_cache_inconsistent in claude result usage")
    return project_wire_usage(wire, usage, include_cache_creation=wire_cache_creation_enabled())


def _env_positive_int(name: str, default: int) -> int:
    """Положительное целое из env; пустое/нечисловое/неположительное -> default."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


# Несекретный фасад watchdog-настроек (AD-002): os.environ > ~/.dsh/.env > fallback > default.
_WATCHDOG_SETTINGS = BridgeWatchdogFacade.for_prefix("CLAUDE_P_BRIDGE_", first_progress_keys=("BRIDGE_NONSTREAM_FIRST_PROGRESS_TIMEOUT_S",))
_get_positive_float = _WATCHDOG_SETTINGS.get_positive_float
_is_watchdog_enabled = _WATCHDOG_SETTINGS.is_watchdog_enabled
CLAUDE_P_BRIDGE_FIRST_TOKEN_TIMEOUT_S = _WATCHDOG_SETTINGS.first_token_timeout_s

CLAUDE_P_BRIDGE_IDLE_TIMEOUT_S = _get_positive_float("CLAUDE_P_BRIDGE_IDLE_TIMEOUT_S", "BRIDGE_IDLE_TIMEOUT_S", 600.0)
CLAUDE_P_BRIDGE_IO_WAIT_CAP_S = _get_positive_float("CLAUDE_P_BRIDGE_IO_WAIT_CAP_S", "BRIDGE_IO_WAIT_CAP_S", 900.0)
CLAUDE_P_BRIDGE_SAFETY_CAP_S = _get_positive_float("CLAUDE_P_BRIDGE_SAFETY_CAP_S", "BRIDGE_SAFETY_CAP_S", 3600.0)
CLAUDE_P_BRIDGE_WATCHDOG_INTERVAL_S = _get_positive_float("CLAUDE_P_BRIDGE_WATCHDOG_INTERVAL_S", "BRIDGE_WATCHDOG_INTERVAL_S", 5.0)

ROOT = Path(__file__).resolve().parent
HOST = os.environ.get("CLAUDE_P_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("CLAUDE_P_BRIDGE_PORT", "9881"))
AUTH_KEY = os.environ.get("CLAUDE_P_BRIDGE_KEY", "").strip()
MODEL_ID = os.environ.get("CLAUDE_P_BRIDGE_MODEL", "claude-sonnet-5-5")
# Поддерживаемые модели -> уровень effort по умолчанию (если reasoning_effort не задан).
SUPPORTED_MODELS = {"claude-opus-5-5": "high", "claude-sonnet-5-5": "high", "claude-haiku-5-5": "high"}
CLAUDE_BIN = os.environ.get(
    "CLAUDE_P_BRIDGE_BIN",
    shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")
)
MCP_CONFIG = ROOT / "empty-mcp.json"
WORKSPACE = ROOT / "workspace"

_CLAUDE_HOME_LOCK = threading.Lock()
_CLAUDE_HOME_INITIALIZED = False
_CLAUDE_CA_FILES = tuple(sorted(CLAUDE_PRESERVED_CA_FILES))

def _write_atomic(dest: Path, body: bytes) -> None:
    if not dest.is_symlink() and dest.is_file() and (dest.stat().st_mode & 0o777) == 0o600 and dest.read_bytes() == body:
        return
    fd, tmp = tempfile.mkstemp(dir=str(dest.parent), prefix=".tmp_")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(body)
        os.replace(tmp, dest)
    finally:
        Path(tmp).unlink(missing_ok=True)

def _read_json_dict(path: Path) -> dict | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None
    except (OSError, ValueError):
        return None

def _sync_ca_files(real_claude: Path, claude_dir: Path) -> None:
    claude_dir.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        os.chmod(claude_dir, 0o700)
    for name in _CLAUDE_CA_FILES:
        with contextlib.suppress(OSError):
            src = real_claude / name
            if src.is_file():
                _write_atomic(claude_dir / name, src.read_bytes())
    for src in (real_claude / ".claude.json", real_claude.parent / ".claude.json"):
        if src.is_file():
            st = _read_json_dict(src)
            if st is not None:
                _write_atomic(claude_dir / ".claude.json", serialize_claude_json(filter_claude_state(st)).encode("utf-8"))
            break

def spawn_registered(cmd: list, **kwargs: Any) -> subprocess.Popen:
    raw = kwargs.get("env")
    env, iso = (os.environ if raw is None else raw), str(WORKSPACE / "runtime" / "claude-home")
    h = env.get("HOME", "") if raw is not None else ""
    kwargs["env"] = build_claude_zero_canon_env(env, h if h and Path(h).resolve() != Path.home().resolve() else iso)
    return _spawn_registered(cmd, **kwargs)
for _a in ("unregister", "set_blocked"):
    setattr(spawn_registered, _a, getattr(_spawn_registered, _a))

def _prepare_claude_home(claude_home: Path | None = None, real_home: Path | None = None) -> Path:
    global _CLAUDE_HOME_INITIALIZED
    use_cache = (claude_home, real_home) == (None, None)
    real_claude = (real_home or Path.home()) / ".claude"
    home = claude_home or WORKSPACE / "runtime" / "claude-home"
    claude_dir = home / ".claude"
    with _CLAUDE_HOME_LOCK:
        if use_cache and _CLAUDE_HOME_INITIALIZED and claude_dir.is_dir():
            return home
        _sync_ca_files(real_claude, claude_dir)
        src = real_claude / "settings.json"
        raw = _read_json_dict(src) if src.is_file() else {}
        if raw is not None:
            _write_atomic(claude_dir / "settings.json", serialize_claude_json(filter_claude_settings(raw)).encode("utf-8"))
            if use_cache:
                _CLAUDE_HOME_INITIALIZED = True
        return home
MAX_CONCURRENT = int(os.environ.get("CLAUDE_P_BRIDGE_MAX_CONCURRENT", "32"))
QUEUE_TIMEOUT_S = int(os.environ.get("CLAUDE_P_BRIDGE_QUEUE_TIMEOUT", "900"))
KEEPALIVE_S = float(os.environ.get("CLAUDE_P_BRIDGE_KEEPALIVE", "15"))
MAX_REQUEST_BYTES = _env_positive_int("CLAUDE_P_BRIDGE_MAX_BODY_BYTES", 100 * 1024 * 1024)
QUEUE_MAXSIZE = _env_positive_int("CLAUDE_P_BRIDGE_QUEUE_MAXSIZE", 1000)
MAX_STDERR_BYTES = _env_positive_int("CLAUDE_P_BRIDGE_MAX_STDERR_BYTES", 10 * 1024 * 1024)
IO_CHUNK_BYTES = _env_positive_int("CLAUDE_P_BRIDGE_IO_CHUNK_BYTES", 64 * 1024)
PROCESS_WAIT_S = float(os.environ.get("CLAUDE_P_BRIDGE_PROCESS_WAIT_S", "5"))
POLL_INTERVAL_S = float(os.environ.get("CLAUDE_P_BRIDGE_POLL_INTERVAL_S", "1"))
STDERR_DRAIN_S = float(os.environ.get("CLAUDE_P_BRIDGE_STDERR_DRAIN_S", "0.05"))
HTTP_TIMEOUT_S = float(os.environ.get("CLAUDE_P_BRIDGE_HTTP_TIMEOUT_S", "1800"))
HTTP_BACKLOG = _env_positive_int("CLAUDE_P_BRIDGE_HTTP_BACKLOG", 64)
# Лимиты изображений — env с безопасными значениями по умолчанию из core.
MAX_IMAGES = _env_positive_int("CLAUDE_P_BRIDGE_MAX_IMAGES", DEFAULT_MAX_IMAGES)
MAX_IMAGE_BYTES = _env_positive_int("CLAUDE_P_BRIDGE_MAX_IMAGE_BYTES", DEFAULT_MAX_IMAGE_BYTES)
MAX_TOTAL_IMAGE_BYTES = _env_positive_int("CLAUDE_P_BRIDGE_MAX_TOTAL_IMAGE_BYTES", DEFAULT_MAX_TOTAL_IMAGE_BYTES)
IMAGE_TMP_ROOT = Path(os.environ.get("CLAUDE_P_BRIDGE_TMPDIR", "/tmp"))
MODEL_CONTEXT = {"claude-sonnet-5-5": 1_000_000, "claude-opus-5-5": 1_000_000, "claude-haiku-5-5": 200_000}
CONTEXT_LENGTH = 1_000_000  # fallback для неизвестных моделей
TOOL_CALL_OPEN = "<tool_call>"
TOOL_CALL_CLOSE = "</tool_call>"

_slots = threading.BoundedSemaphore(MAX_CONCURRENT)
_active = {}
_active_img_dirs: set = set()
_active_lock = threading.Lock()
_started = time.time()

def _log(msg: str) -> None:
    _emit_rotated_log("claude_p", f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}", ROOT, redact_fn=redact_log_text)


def _auth_ok(handler: BaseHTTPRequestHandler) -> bool:
    hdr = handler.headers.get("Authorization", "")
    expected = AUTH_KEY.encode("utf-8")
    if hdr.startswith("Bearer "):
        return hmac.compare_digest(hdr[7:].strip().encode("utf-8"), expected)
    return hmac.compare_digest(
        handler.headers.get("x-api-key", "").encode("utf-8"), expected
    ) or hmac.compare_digest(hdr.strip().encode("utf-8"), expected)


def _extract_request_images(req: dict) -> list:
    """Изображения всей истории `messages` -> [{"name", "mime", "data"}] (core, AD-003)."""
    messages = req.get("messages") if isinstance(req.get("messages"), list) else []
    return extract_data_url_images(
        messages,
        max_images=MAX_IMAGES,
        max_image_bytes=MAX_IMAGE_BYTES,
        max_total_bytes=MAX_TOTAL_IMAGE_BYTES,
    )


def _stage_images(images: list) -> Path | None:
    """Каталог 0700 без umask; файлы 0600 exclusive/no-follow; cleanup при ошибке."""
    if not images:
        return None
    img_dir = IMAGE_TMP_ROOT / f"claude-img-{uuid.uuid4().hex}"
    os.mkdir(img_dir, 0o700)
    os.chmod(img_dir, 0o700)
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        for image in images:
            target = img_dir / image["name"]
            fd = os.open(target, flags, 0o600)
            try:
                view = memoryview(image["data"])
                while view:
                    view = view[os.write(fd, view) :]
            finally:
                os.close(fd)
            os.chmod(target, 0o600)
    except BaseException:
        shutil.rmtree(img_dir, ignore_errors=True)
        raise
    with _active_lock:
        _active_img_dirs.add(img_dir)
    return img_dir


def _cleanup_img_dir(img_dir: Path | None) -> None:
    """Гарантированное удаление сессионного каталога картинок своего хода."""
    if img_dir is None:
        return
    with _active_lock:
        _active_img_dirs.discard(Path(img_dir))
    shutil.rmtree(img_dir, ignore_errors=True)


def _build_claude_cmd(model: str, effort: str, img_dir: Path | None = None,
                      session_plan: SessionPlan | None = None) -> list:
    """argv `claude -p`; Zero-Canon флаги из core, с картинками — Read по `--add-dir` (AD-003).

    Флаги сессии — `build_session_argv`; без плана -> `--no-session-persistence` (AD-004).
    """
    flags = filter(NO_PERSISTENCE_FLAG.__ne__, build_claude_zero_canon_flags(bool(img_dir)))
    cmd = [CLAUDE_BIN, "-p", "--model", model, "--effort", effort,
           "--output-format", "stream-json", "--verbose", "--include-partial-messages",
           "--mcp-config", str(MCP_CONFIG), *flags, *build_session_argv(session_plan)]
    assert_zero_canon_argv_safe(cmd, zero_canon=not session_plan)  # fail-closed до spawn_registered
    if img_dir is None:  # встроенные инструменты отключены: действия только через DSH
        return cmd + ["--permission-mode", "bypassPermissions"]
    return cmd + ["--permission-mode", "dontAsk", "--allowedTools", f"Read({img_dir}/**)",
                  "--add-dir", str(img_dir)]


def _effort(value: Any, model: str = MODEL_ID) -> str:
    """Модельный reasoning_effort; неизвестное значение -> SUPPORTED_MODELS."""
    eff = str(value or "").strip().lower()
    default = SUPPORTED_MODELS.get(model, "high")
    if model == "claude-haiku-5-5":
        return eff if eff in ("low", "medium", "high", "xhigh", "max") else default
    if model == "claude-sonnet-5-5":
        if eff == "max":
            return "xhigh"
        return eff if eff in ("low", "medium", "high", "xhigh") else default
    if eff in ("xhigh", "max"):
        return "high"
    return eff if eff in ("low", "medium", "high") else default


def _resolve_model(req: dict) -> tuple[str, dict | None]:
    """Модель запроса (fallback MODEL_ID) и тело ошибки 400, если модель не поддержана."""
    raw = req.get("model")
    model = str(raw).strip() if raw else MODEL_ID
    if model not in SUPPORTED_MODELS:
        return model, {"message": f"model not allowed: {model}",
                       "type": "invalid_request_error", "code": 400}
    return model, None


def _kill_group(proc: subprocess.Popen) -> None:
    """SIGTERM процессной группе, затем SIGKILL, если не завершилась."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            return
        try:
            proc.wait(timeout=PROCESS_WAIT_S)
            return
        except subprocess.TimeoutExpired:
            continue


def _cleanup_active_img_dirs() -> None:
    """Зачистка каталогов картинок убитых ходов; вызывается вне обработчика сигнала."""
    if live_proc_groups():  # каталоги живых ходов не трогаем
        return
    with _active_lock:
        img_dirs = list(_active_img_dirs)
    for img_dir in img_dirs:  # только свои сессионные каталоги картинок
        _cleanup_img_dir(img_dir)


_LIFECYCLE = SubbridgeLifecycle(hooks=SubbridgeHooks(
    procs_fn=lambda: list(_active.copy().values()), cleanup_fn=_cleanup_active_img_dirs, log_fn=_log
), workspace=WORKSPACE)


class Run:
    """Один процесс `claude -p`; поток-читатель превращает stdout в события очереди."""

    def __init__(self, prompt: str, model: str, effort: str, tag: str,
                 img_dir: Path | None = None, **opts: Any):
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        # С картинками Claude работает из сессионного каталога вложений: пути
        # в секции [attachments] относительные, Read ограничен этим каталогом.
        cmd = _build_claude_cmd(model, effort, img_dir, opts.get("session_plan"))
        self.cmd = cmd
        self.img_dir = img_dir
        _log(f"exec model={model} effort={effort} prompt_bytes={len(prompt.encode())} {tag}")
        child_env = os.environ.copy()
        child_env["HOME"] = str(_prepare_claude_home())
        child_env["BRIDGE_ZERO_CANON"] = "1"
        child_env.pop("CLAUDE_P_BRIDGE_KEY", None)

        self.proc, _, self._release = acquire_claude_run_proc(ClaudeRunRequest(model, effort, img_dir, opts.get("session_plan")), lambda: spawn_registered(
            cmd, cwd=str(img_dir if img_dir is not None else WORKSPACE), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, start_new_session=True, env=child_env))
        with _active_lock:
            _active[self.proc.pid] = self.proc
        self.q = queue.Queue(maxsize=QUEUE_MAXSIZE)
        self._closed = threading.Event()
        self.err_box = []
        threading.Thread(target=self._feed, args=(prompt,), daemon=True).start()
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        threading.Thread(target=self._pump, daemon=True).start()

    def _feed(self, prompt: str) -> None:
        """Промпт уходит только через stdin."""
        try:
            self.proc.stdin.write(prompt.encode("utf-8"))
            self.proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    def _drain_stderr(self) -> None:
        remaining = MAX_STDERR_BYTES
        retained = bytearray()
        try:
            while chunk := self.proc.stderr.read(IO_CHUNK_BYTES):
                if remaining:
                    retained.extend(chunk[:remaining])
                    remaining = max(0, remaining - len(chunk))
        except Exception:  # noqa: BLE001 - вторичный поток, ошибку терять нельзя молча
            pass
        finally:
            self.err_box.append(retained.decode("utf-8", "replace"))

    def _enqueue(self, event: tuple) -> None:
        """Ограниченная очередь с прерыванием ожидания при закрытии хода."""
        while not self._closed.is_set():
            try:
                self.q.put(event, timeout=POLL_INTERVAL_S)
                return
            except queue.Full:
                continue

    def _pump(self) -> None:
        """Разбор stream-json: content_block_delta -> text/thinking, result -> итог."""
        try:
            for raw in iter(self.proc.stdout.readline, b""):
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("{"):
                    continue
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                etype = ev.get("type")
                if etype == "stream_event":
                    inner = ev.get("event") or {}
                    if inner.get("type") == "content_block_delta":
                        delta = inner.get("delta") or {}
                        dtype = delta.get("type")
                        if dtype == "text_delta" and delta.get("text"):
                            self._enqueue(("text", delta["text"]))
                        elif dtype == "thinking_delta":
                            thinking = extract_thinking_delta(delta)
                            if thinking:
                                self._enqueue(("thinking", thinking))
                elif etype == "result":
                    self._enqueue(("result", ev))
            rc = self.proc.wait()
        except Exception as exc:  # noqa: BLE001 - читатель не должен умирать молча
            self._enqueue(("pump_error", repr(exc)))
            return
        time.sleep(STDERR_DRAIN_S)  # дать стоку stderr дозавершиться
        self._enqueue(("done", rc))

    def close(self) -> None:
        self._closed.set()
        if self.proc.poll() is None:
            _kill_group(self.proc)
        self.proc.wait(timeout=PROCESS_WAIT_S)
        with _active_lock:
            _active.pop(self.proc.pid, None)
        cast(Any, spawn_registered).unregister(self.proc)
        self._release()
        for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            try:
                if stream is not None:
                    stream.close()
            except OSError:
                pass


def _client_gone(sock: socket.socket) -> bool:
    try:
        ready, _, _ = select.select([sock], [], [], 0)
        return bool(ready) and sock.recv(1, socket.MSG_PEEK) == b""
    except (OSError, ValueError):
        return True


class _Callbacks(NamedTuple):
    on_text: Callable[[str], bool]
    on_reasoning: Callable[[str], bool]
    on_tool_call: Callable[[dict], bool]
    keepalive: Callable[[], bool] | None = None


class _Turn(NamedTuple):
    prompt: str
    model: str
    effort: str
    tag: str
    images: list
    tools: list
    mode_spec: NormalizerModeSpec
    chat_digest: str | None = None
    session_plan: SessionPlan | None = None


def _failed(state: str, err: str = "") -> dict:
    return {"state": state, "rc": 1, "text": "", "reasoning": "", "usage": {},
            "result": {}, "err": err, "tool_calls": []}


def _prompt_for(req: dict, tools: list, images: list, mode_spec: NormalizerModeSpec) -> str:
    raw = req.get("messages")
    messages = raw if isinstance(raw, list) else []
    prompt = _messages_to_prompt(messages, tools, req.get("tool_choice"), images or None)
    return prompt + ("\n\n" + TOOLLESS_PURE_TEXT_HINT if mode_spec.mode is ToolMode.OFF else "")


def _watchdog_for(run: Run) -> Any:
    proc = getattr(run, "proc", None)
    pid = getattr(proc, "pid", None)
    if not (_is_watchdog_enabled() and AdaptiveTimeoutController is not None and pid):
        return None
    controller = AdaptiveTimeoutController(
        idle_timeout_s=CLAUDE_P_BRIDGE_IDLE_TIMEOUT_S,
        safety_cap_s=CLAUDE_P_BRIDGE_SAFETY_CAP_S,
        io_wait_cap_s=CLAUDE_P_BRIDGE_IO_WAIT_CAP_S,
        watchdog_interval_s=CLAUDE_P_BRIDGE_WATCHDOG_INTERVAL_S,
        first_token_timeout_s=CLAUDE_P_BRIDGE_FIRST_TOKEN_TIMEOUT_S,
    )
    controller.register_pgid(pid)
    return controller


class _Execution:
    """Состояние одного транспорта; протокольный разбор остаётся в core."""

    def __init__(self, run: Run, callbacks: _Callbacks,
                 mode_spec: NormalizerModeSpec, tools: list | None) -> None:
        self.run, self.callbacks, self.mode_spec = run, callbacks, mode_spec
        self.schemas = build_tool_schemas(tools or [])
        self.tool_calls: list = []
        self.usage: dict = {}
        self.result: dict = {}
        self.gone = False
        self.last_ka = self.last_check = time.monotonic()
        self.normalizer = StreamNormalizer.for_mode(
            mode_spec, NormalizerSinks(self.add_content, self.add_reasoning, self.add_call),
            strict_live=True, tool_schemas=self.schemas,
        )
        self.normalizer.configure_post_call_policy(PostCallPolicy(
            cutoff_enabled=read_post_call_cutoff_enabled(),
            diagnostic_window_chars=read_diagnostic_window_chars(),
            diagnostic_redact_margin_chars=read_diagnostic_redact_margin_chars(),
        ))

    def state(self, name: str, rc: int, err: str = "") -> dict:
        return {"rc": rc, "text": self.normalizer.content, "usage": self.usage,
                "reasoning": self.normalizer.reasoning_content,
                "result": self.result, "state": name, "err": err,
                "tool_calls": self.tool_calls}

    def add_content(self, text: str) -> None:
        if not self.gone and text and not self.callbacks.on_text(text):
            self.gone = True

    def add_reasoning(self, text: str) -> None:
        if not self.gone and text and not self.callbacks.on_reasoning(text):
            self.gone = True

    def add_call(self, call: dict) -> None:
        if self.mode_spec.mode is not ToolMode.EMULATE:
            raise LiveParserError("tool_call published without tool emulation")
        if self.gone:
            return
        entry = {"index": len(self.tool_calls), "id": "call_" + uuid.uuid4().hex[:24], "type": "function",
                 "function": {"name": call["name"], "arguments": json.dumps(call["arguments"], ensure_ascii=False)}}
        synth = synthesize_required_bash_desc_enabled()
        for item in sanitize_tool_call(entry, self.schemas, synthesize_required_description=synth):
            item = dict(item, index=len(self.tool_calls))
            self.tool_calls.append(item)
            if not self.callbacks.on_tool_call(item):
                self.gone = True
                return

    def next_event(self) -> tuple[str, Any]:
        try:
            return self.run.q.get(timeout=POLL_INTERVAL_S)
        except queue.Empty:
            keepalive = self.callbacks.keepalive
            if keepalive is not None and time.monotonic() - self.last_ka >= KEEPALIVE_S:
                self.last_ka = time.monotonic()
                self.gone = not keepalive()
            return "idle", None

    def check_watchdog(self, controller: Any) -> str:
        now = time.monotonic()
        if controller is None or now - self.last_check < controller.watchdog_interval_s:
            return ""
        self.last_check = now
        stop, reason, _ = controller.check(self.run.proc.pid)
        if stop and reason in ("idle_timeout", "absolute_cap"):
            _kill_group(self.run.proc)
            return f"claude-p watchdog: {reason}"
        return ""  # child_exited: ждём done из очереди, не убиваем.

    def dispatch(self, kind: str, payload: Any) -> dict | None:
        if kind == "text":
            self.normalizer.feed_text(str(payload))
        elif kind == "thinking":
            self.normalizer.feed_thinking(str(payload))
        elif kind == "result":
            self.result = payload
            self.usage = payload.get("usage") or {}
        elif kind == "pump_error":
            return self.state("pump_error", 1, str(payload))
        elif kind == "done":
            self.normalizer.finish()  # Битый хвост — ошибка, result-fallback нет.
            if self.gone:
                return self.state("client_gone", 1)
            time.sleep(STDERR_DRAIN_S)
            return self.state("done", payload, "".join(self.run.err_box))
        if self.gone:
            return self.state("client_gone", 1)
        return None

    def execute(self, connection: socket.socket) -> dict:
        controller = _watchdog_for(self.run)
        try:
            while True:
                if _client_gone(connection):
                    return self.state("client_gone", 1)
                reason = self.check_watchdog(controller)
                if reason:
                    return self.state("timeout", 1, reason)
                kind, payload = self.next_event()
                if controller is not None and kind in ("text", "thinking", "result"):
                    controller.record_activity(kind)
                out = self.dispatch(kind, payload)
                if out is not None:
                    return out
        finally:
            if controller is not None:
                controller.close()


@_LIFECYCLE.install
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = HTTP_TIMEOUT_S

    def log_message(self, format: str, *args: Any) -> None:
        _log("http " + (format % args))
    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(int(code))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _emit(self, data: str) -> bool:
        try:
            self.wfile.write(data.encode("utf-8"))
            self.wfile.flush()
            return True
        except (BrokenPipeError, ConnectionResetError, OSError):
            return False

    def _acquire_slot(self, keepalive):
        """Ждём слот семафора до QUEUE_TIMEOUT_S, попутно keepalive и проверка клиента."""
        waited = time.monotonic()
        last_ka = 0.0
        while not _slots.acquire(timeout=POLL_INTERVAL_S):
            if _client_gone(self.connection):
                return "client_gone"
            if time.monotonic() - waited > QUEUE_TIMEOUT_S:
                return "queue_timeout"
            if keepalive is not None and time.monotonic() - last_ka >= KEEPALIVE_S:
                last_ka = time.monotonic()
                if not keepalive():
                    return "client_gone"
        return ""

    def _execute(self, run: Run, callbacks: _Callbacks,
                 mode_spec: NormalizerModeSpec, tools: list | None = None) -> dict:
        """AD-002/004: reasoning всегда включён; теги инструментов fail-closed (OFF+TEXT — байт-в-байт)."""
        return _Execution(run, callbacks, mode_spec, tools).execute(self.connection)

    def _prepare(self, req: dict, images: list) -> tuple[str, list, NormalizerModeSpec]:
        """Prompt, tools и режим одним проходом (do_POST проверяет лимит до SSE/spawn)."""
        raw_tools = req.get("tools")
        tools = [t for t in raw_tools if isinstance(t, dict)] if isinstance(raw_tools, list) else []
        spec = build_mode_spec(resolve_tool_mode(tools, req.get("tool_choice")), resolve_toolless_tag_policy(os.environ))
        return _prompt_for(req, tools, images, spec), tools, spec

    def _session_key(self, req: dict) -> str | None:
        """Opt-in reuse (AD-004): только явный session-id и профиль standard/без профиля."""
        extra = req.get("extra_body")
        chat = resolve_chat_key(req, self.headers, extra if isinstance(extra, dict) else None, sources=SOURCES_SESSION_ID)
        return chat.digest if (SessionConfig.from_env().enabled and is_session_reuse_allowed_profile(self.headers) and chat.keyed) else None

    def _run_once(self, req: dict, callbacks: _Callbacks, chat: Any = None) -> dict:
        model, model_err = _resolve_model(req)
        if model_err is not None:
            return _failed("bad_model", model_err["message"])
        try:
            images = _extract_request_images(req)
        except ImageInputError as exc:
            return _failed("bad_image", exc.code)
        prompt, tools, mode_spec = self.__dict__.pop("_prep", None) or self._prepare(req, images)
        effort = _effort(req.get("reasoning_effort"), model)
        tag = (f"client={self.client_address[0]}:{self.client_address[1]} "
               f"ua={(self.headers.get('User-Agent') or '-')[:60]}")
        _log(f"request model={model} effort={effort} {format_tool_mode_log(tools, req.get('tool_choice'), mode_spec)} {tag}")
        turn = _Turn(prompt, model, effort, tag, images, tools, mode_spec, getattr(chat, "digest", None))
        over = prepare_prompt_with_cap(prompt, PromptBudgetConfig.from_env()).exceeded  # страховка: 413 уже в do_POST
        reason = "prompt_too_large" if over else self._acquire_slot(callbacks.keepalive)
        if reason:
            _log(f"no slot ({reason}) model={model} effort={effort} {tag}")
            return _failed(reason)
        t0 = time.monotonic()
        try:
            out = self._run_session(turn, callbacks, self._session_key(req))
        finally:
            _slots.release()
        self._log_turn_done(turn, out, t0)
        return out

    def _run_session(self, turn: _Turn, callbacks: _Callbacks, key_digest: str | None) -> dict:
        """Сериализованный per-key lock до CREATE/RESUME; RESUME-сбой до вывода -> stateless-повтор."""
        if not key_digest:
            return self._run_staged(turn, callbacks)
        store = cast("Server", self.server).session_store
        with store.lease(key_digest) as lease:
            out = self._run_staged(turn._replace(session_plan=SessionPlan(lease.mode, lease.session_id)), callbacks)
            if self._error_body(out):
                store.invalidate(lease.key_digest, lease.session_id)
                if lease.mode is SessionMode.RESUME and out["state"] == "done" and not any(map(out.get, ("text", "reasoning", "tool_calls"))):
                    out = self._run_staged(turn, callbacks)
        return out

    def _run_staged(self, turn: _Turn, callbacks: _Callbacks) -> dict:
        img_dir = None
        can_cleanup = True
        try:
            try:
                img_dir = _stage_images(turn.images)
                kw = {"session_plan": turn.session_plan} if turn.session_plan else {}
                run = Run(turn.prompt, turn.model, turn.effort, turn.tag, img_dir=img_dir, **kw)
                can_cleanup = False
            except OSError as exc:
                _log(f"image stage/spawn failed model={turn.model} err={exc!r:.200} {turn.tag}")
                return _failed("image_error", str(exc)[:200])
            try:
                return self._execute(run, callbacks, turn.mode_spec, turn.tools)
            except LiveParserError as exc:
                _log(f"parser_error model={turn.model} err={exc} {turn.tag}")
                return _failed("parser_error", str(exc))
            finally:
                run.close()  # сначала завершить и reap своего ребёнка
                can_cleanup = True
        finally:
            if can_cleanup:
                _cleanup_img_dir(img_dir)

    @staticmethod
    def _log_turn_done(turn: _Turn, out: dict, t0: float) -> None:
        tag = f"{format_done_usage_suffix(out.get('usage'), getattr(turn, 'chat_digest', ''))} {turn.tag}"
        _log(format_claude_done_fields((turn.model, turn.effort, tag), out, time.monotonic() - t0, load_admission_idle_config()))  # fmt: skip

    @staticmethod
    def _error_body(out: dict) -> Any:
        st = str(out.get("state") or "")
        if st == "timeout":
            return {
                "message": str(out.get("err") or "upstream timeout"),
                "type": "upstream_timeout",
                "code": 504,
            }
        if st == "bad_model":
            return {"message": str(out.get("err")), "type": "invalid_request_error", "code": 400}
        if st == "bad_image":
            return {"message": f"invalid image input: {out.get('err')}",
                    "type": "invalid_request_error", "code": 400}
        if st == "parser_error":
            return {"message": "malformed tool_call stream",
                    "type": "proxy_error", "code": 502}
        if st == "image_error":
            return {"message": "image staging or spawn failed",
                    "type": "proxy_error", "code": 502}
        if st == "queue_timeout":
            return {"message": f"bridge busy: queue full over {QUEUE_TIMEOUT_S}s",
                    "type": "overloaded", "code": 503}
        if st == "client_gone":
            return {"message": "client gone", "type": "client_gone", "code": 499}
        if st == "pump_error":
            return {"message": "bridge reader failed", "detail": str(out.get("err"))[:500],
                    "type": "proxy_error", "code": 502}
        if (out.get("result") or {}).get("is_error"):
            detail = str((out["result"].get("result")) or out.get("err") or "claude reported an error")
            if "<tool_call" in detail:  # сырой XML не публикуется даже в тексте ошибки
                detail = "claude reported an error"
            return {"message": detail[:500], "type": "claude_error", "code": 502}
        if out.get("rc") != 0 or not (out.get("text") or out.get("tool_calls")):
            return {"message": f"claude exited rc={out.get('rc')}",
                    "detail": str(out.get("err"))[:500], "type": "proxy_error", "code": 502}
        return None

    # ---- HTTP --------------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/health", "/v1/health"):
            with _active_lock:
                active = len(_active)
            self._send(200, {
                "ok": True, "transport": "claude-p", "model": MODEL_ID, "models": list(SUPPORTED_MODELS),
                "active": active, "max_concurrent": MAX_CONCURRENT, "tool_emulation": True, "images": True,
                "live_reasoning": True, "uptime_s": int(time.time() - _started),
            })
            return
        if not _auth_ok(self):
            self._send(401, {"error": {"message": "unauthorized", "type": "auth_error"}})
            return
        if path in ("/v1/models", "/models"):
            self._send(200, {"object": "list", "data": [{
                "id": model_id, "object": "model", "owned_by": "anthropic", "created": 0,
                "context_length": MODEL_CONTEXT.get(model_id, CONTEXT_LENGTH),
            } for model_id in SUPPORTED_MODELS]})
            return
        self._send(404, {"error": {"message": f"not found: {path}"}})

    def do_POST(self) -> None:  # noqa: N802
        if not _auth_ok(self):
            # Непрочитанное тело иначе будет разобрано как следующий запрос keep-alive.
            self.close_connection = True
            self._send(401, {"error": {"message": "unauthorized", "type": "auth_error"}})
            return
        path = self.path.split("?", 1)[0]
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            length = -1
        if length < 0 or length > MAX_REQUEST_BYTES:
            self.close_connection = True
            self._send(413 if length > MAX_REQUEST_BYTES else 400,
                       {"error": {"message": "invalid request body length"}})
            return
        raw = self.rfile.read(length) if length else b"{}"
        try:
            req = json.loads(raw.decode("utf-8"))
        except ValueError:
            self._send(400, {"error": {"message": "invalid json"}})
            return
        if path not in ("/v1/chat/completions", "/chat/completions"):
            self._send(404, {"error": {"message": f"not found: {path}"}})
            return
        self._dispatch(req)

    def _dispatch(self, req: dict) -> None:
        """Валидация до SSE-заголовков и spawn (модель, картинки, лимит prompt), затем ответ."""
        # Идентичность чата — для лога/корреляции; невалидный ключ — как без ключа (без 400).
        extra_body = req.get("extra_body")
        chat = resolve_chat_key(req, self.headers, extra_body if isinstance(extra_body, dict) else None)
        if chat.keyed:
            _log(f"chat key={chat.digest[:16]} source={chat.source}")
        model_err = _resolve_model(req)[1]
        if model_err:
            self._send(400, {"error": {"message": model_err["message"], "type": model_err["type"]}})
            return
        try:
            images = _extract_request_images(req)
        except ImageInputError as exc:
            self._send(400, {"error": {"message": f"invalid image input: {exc.code}",
                                       "type": "invalid_request_error"}})
            return
        prep = self._prepare(req, images)  # AD-006: лимит prompt -> 413 до SSE и spawn, без усечения
        cap_err = prepare_prompt_with_cap(prep[0], PromptBudgetConfig.from_env()).error_body
        self._prep = None if cap_err else prep
        if cap_err:
            self._send(413, cap_err)
        elif req.get("stream"):
            self._serve_sse(req, chat)
        else:
            self._serve_json(req, chat)

    def _serve_json(self, req: dict, chat: Any = None) -> None:
        out = self._run_once(req, _Callbacks(lambda _v: True, lambda _v: True, lambda _e: True), chat)
        if out.get("state") == "client_gone":
            return
        err = self._error_body(out)
        if err is not None:
            self._send(err["code"], {"error": err})
            return
        usage = out.get("usage") or {}
        wire_usage = _wire_usage(usage)
        message = {"role": "assistant", "content": out["text"]}
        if out.get("reasoning"):
            message["reasoning_content"] = out["reasoning"]
        finish = "stop"
        if out.get("tool_calls"):
            message["tool_calls"] = out["tool_calls"]
            finish = "tool_calls"
        self._send(200, {
            "id": f"chatcmpl-claudep-{uuid.uuid4().hex[:12]}", "object": "chat.completion",
            "created": int(time.time()), "model": req.get("model") or MODEL_ID,
            "choices": [{"index": 0, "message": message, "finish_reason": finish}],
            "usage": wire_usage,
        })

    def _serve_sse(self, req: dict, chat: Any = None) -> None:
        completion_id = f"chatcmpl-claudep-{uuid.uuid4().hex[:12]}"
        created = int(time.time())
        shown_model = str(req.get("model") or MODEL_ID)
        if not self._start_sse():
            return

        def chunk(delta: dict, finish=None, usage: dict | None = None) -> str:
            payload = {
                "id": completion_id, "object": "chat.completion.chunk", "created": created,
                "model": shown_model,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }
            if usage is not None:
                payload["usage"] = usage
            return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"

        callbacks = _Callbacks(
            lambda value: self._emit(chunk({"content": value})),
            lambda value: self._emit(chunk({"reasoning_content": value})),
            lambda entry: self._emit(chunk({"tool_calls": [entry]})),
            lambda: self._emit(": keepalive\n\n"),
        )
        if not self._emit(chunk({"role": "assistant", "content": ""})):
            return
        self._finish_sse(req, self._run_once(req, callbacks, chat), chunk)

    def _start_sse(self) -> bool:
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            self.close_connection = True
            return True
        except (BrokenPipeError, ConnectionResetError, OSError):
            _log("client gone before headers")
            return False

    def _finish_sse(self, req: dict, out: dict, chunk: Callable) -> None:
        if out.get("state") == "client_gone":
            _log("client gone mid-stream, child killed")
            return
        err = self._error_body(out)
        if err is None:
            finish = "tool_calls" if out.get("tool_calls") else "stop"
            from usage_policy import should_emit_terminal_usage  # F-004: локальный импорт чистой политики
            wants_usage = should_emit_terminal_usage(req.get("stream_options"))
            final_usage = _wire_usage(out.get("usage") or {}) if wants_usage else None
            self._emit(chunk({}, finish, final_usage))
        else:
            error_msg = str(err.get("message") or "") if isinstance(err, dict) else str(err)
            error_chunk = format_stream_error_sse(str(error_msg), finish_reason="stop")
            self._emit(error_chunk)
            return
        self._emit("data: [DONE]\n\n")


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = HTTP_BACKLOG
    allow_reuse_address = True
    def handle_error(self, request: Any, client_address: Any) -> None:
        handle_accept_error(client_address, _log, lambda: ThreadingHTTPServer.handle_error(self, request, client_address), ROOT / "dynamic_config.json")
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.session_store = SessionStore(SessionConfig.from_env())  # владелец состояния reuse (AD-004)


def main() -> None:
    if not AUTH_KEY:
        sys.stderr.write("CLAUDE_P_BRIDGE_KEY is required; refusing to start\n")
        raise SystemExit(1)
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    server = Server((HOST, PORT), Handler)
    _log(f"listen {HOST}:{PORT} model={MODEL_ID} max_concurrent={MAX_CONCURRENT} "
         f"queue_timeout={QUEUE_TIMEOUT_S}s keepalive={KEEPALIVE_S}s")
    print(f"[claude-p-bridge] listening on http://{HOST}:{PORT}/v1", flush=True)
    raise SystemExit(_LIFECYCLE.serve_forever(server))


if __name__ == "__main__":
    main()
