#!/usr/bin/env python3
"""OpenAI-совместимый мост к CLI `claude -p` (Claude Code).

Один запрос /v1/chat/completions = один headless-ход
`claude -p --output-format stream-json --verbose --include-partial-messages`.
Поток stream-json переводится в OpenAI Chat Completions (stream и не-stream).

Мост эмулирует OpenAI function calling: если запрос содержит непустой `tools`,
в промпт добавляется протокол и схемы инструментов, а встроенные инструменты
Claude Code отключаются (`--tools ""`). Модель просят отвечать блоками
`<tool_call>{"name":…,"arguments":{…}}</tool_call>`; потоковые блоки переводятся
в OpenAI-чанки `delta.tool_calls`, история с `tool_calls`/`role:"tool"`
рендерится обратно в те же блоки.

Общая протокольная логика живёт только в универсальном ядре `core/` (ADR 0014,
AD-002: этот файл в репозитории — SSOT, локальных копий парсера нет; без core
мост не стартует). Весь поток Claude всегда проходит через
`core.tool_emulation.StreamNormalizer` поверх
`ToolCallParser(strict_live=True)` (AD-004, ALWAYS-ON): повреждённый XML не
попадает в `content`, fallback на терминальный `result` исключён, ошибка
потока — корректный `502 proxy_error`.

Изображения (`image_url` data URI PNG/JPEG/GIF/WebP) мост материализует в изолированный
сессионный каталог `/tmp/claude-img-<uuid>/` (0700, файлы 0600) и запускает
Claude с `--allowedTools "Read(<каталог>/**)"`, `--restricted` и
`--add-dir <каталог>` (AD-003, workspace-read);
каталог удаляется в `finally` после подтверждённого завершения ребёнка. Без
картинок сохраняется прежний режим `--tools ""`.

Reasoning публикуется в реальном времени (AD-005): нативные `thinking_delta` и
теги размышлений в тексте уходят в SSE как `choices[0].delta.reasoning_content`
до терминального события; в JSON тот же накопленный итог отдаётся как
`message.reasoning_content`.

Секреты с диска не читаются: ключ авторизации берётся только из окружения
CLAUDE_P_BRIDGE_KEY, переменные окружения ребёнка не трогаются.
"""

from __future__ import annotations

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
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT, Path(__file__).resolve().parents[1]):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from core.proc_groups import live_proc_groups, spawn_registered  # noqa: E402
from core.subbridge_lifecycle import SubbridgeHooks, SubbridgeLifecycle  # noqa: E402

try:
    from core.watchdog import AdaptiveTimeoutController
except ImportError:
    AdaptiveTimeoutController = None  # type: ignore[assignment,misc]

try:
    from core.stream_framing import format_stream_error_sse
    from core.tool_emulation import (  # noqa: E402
        DEFAULT_MAX_IMAGE_BYTES,
        DEFAULT_MAX_IMAGES,
        DEFAULT_MAX_TOTAL_IMAGE_BYTES,
        ImageInputError,
        LiveParserError,
        StreamNormalizer,
        _messages_to_prompt,
        _tool_choice_none,
        build_tool_schemas,
        extract_data_url_images,
        extract_thinking_delta,
        sanitize_tool_call,
    )
except ImportError as exc:
    # Fail-closed (AD-002): без согласованного core мост не запускается;
    # встроенной запасной копии парсера не существует.
    sys.stderr.write(
        "claude-p-bridge: core.tool_emulation is required "
        f"(repo root {_REPO_ROOT}): {exc}\n"
    )
    raise SystemExit(1) from exc


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


_ALLOWED_SETTINGS_KEYS = frozenset({
    "CLAUDE_P_BRIDGE_WATCHDOG_ENABLED",
    "CLAUDE_P_BRIDGE_IDLE_TIMEOUT_S",
    "CLAUDE_P_BRIDGE_IO_WAIT_CAP_S",
    "CLAUDE_P_BRIDGE_SAFETY_CAP_S",
    "CLAUDE_P_BRIDGE_WATCHDOG_INTERVAL_S",
    "BRIDGE_IDLE_TIMEOUT_S",
    "BRIDGE_IO_WAIT_CAP_S",
    "BRIDGE_SAFETY_CAP_S",
    "BRIDGE_WATCHDOG_INTERVAL_S",
})


def _read_dsh_env_file() -> dict[str, str]:
    """Безопасно читает только несекретные настройки из ~/.dsh/.env.

    НЕ мутирует os.environ, гарантируя полную изоляцию от окружения pytest и подпроцессов.
    """
    env_file = Path.home() / ".dsh" / ".env"
    if not env_file.is_file():
        return {}
    res: dict[str, str] = {}
    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                if line.startswith("export "):
                    line = line[len("export "):].strip()
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k in _ALLOWED_SETTINGS_KEYS:
                    res[k] = v
    except OSError:
        pass
    return res


_DSH_ENV = _read_dsh_env_file()


def _get_setting(name: str, fallback_name: str | None = None, default: str = "") -> str:
    """Двухступенчатый каскад чтения: os.environ -> _DSH_ENV -> fallback -> default."""
    for k in (name, fallback_name) if fallback_name else (name,):
        val = os.environ.get(k)
        if val is not None and val.strip():
            return val.strip()
        val = _DSH_ENV.get(k)
        if val is not None and val.strip():
            return val.strip()
    return default


def _get_positive_float(name: str, fallback_name: str | None = None, default: float = 0.0) -> float:
    raw = _get_setting(name, fallback_name)
    if not raw:
        return default
    try:
        val = float(raw)
        return val if 0 < val < float("inf") else default
    except (ValueError, TypeError):
        return default


def _is_watchdog_enabled() -> bool:
    raw = _get_setting("CLAUDE_P_BRIDGE_WATCHDOG_ENABLED", default="1").lower()
    return raw not in ("0", "false", "no", "off")


CLAUDE_P_BRIDGE_IDLE_TIMEOUT_S = _get_positive_float(
    "CLAUDE_P_BRIDGE_IDLE_TIMEOUT_S", "BRIDGE_IDLE_TIMEOUT_S", 300.0
)
CLAUDE_P_BRIDGE_IO_WAIT_CAP_S = _get_positive_float(
    "CLAUDE_P_BRIDGE_IO_WAIT_CAP_S", "BRIDGE_IO_WAIT_CAP_S", 900.0
)
CLAUDE_P_BRIDGE_SAFETY_CAP_S = _get_positive_float(
    "CLAUDE_P_BRIDGE_SAFETY_CAP_S", "BRIDGE_SAFETY_CAP_S", 3600.0
)
CLAUDE_P_BRIDGE_WATCHDOG_INTERVAL_S = _get_positive_float(
    "CLAUDE_P_BRIDGE_WATCHDOG_INTERVAL_S", "BRIDGE_WATCHDOG_INTERVAL_S", 5.0
)


ROOT = Path(__file__).resolve().parent
HOST = os.environ.get("CLAUDE_P_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("CLAUDE_P_BRIDGE_PORT", "9881"))
AUTH_KEY = os.environ.get("CLAUDE_P_BRIDGE_KEY", "").strip()
MODEL_ID = os.environ.get("CLAUDE_P_BRIDGE_MODEL", "claude-sonnet-5-5")
# Поддерживаемые модели -> уровень effort по умолчанию (если reasoning_effort не задан).
SUPPORTED_MODELS = {
    "claude-opus-5-5": "high",
    "claude-sonnet-5-5": "high",
    "claude-haiku-5-5": "high",
}
CLAUDE_BIN = os.environ.get(
    "CLAUDE_P_BRIDGE_BIN",
    shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")
)
MCP_CONFIG = ROOT / "empty-mcp.json"
WORKSPACE = ROOT / "workspace"


_CLAUDE_HOME_LOCK = threading.Lock()
_CLAUDE_HOME_INITIALIZED = False


def _prepare_claude_home() -> Path:
    """Подготовить изолированный фиктивный HOME для claude -p (P0/P2 Zero-Canon).

    В ~/.claude/ переносятся только файлы авторизации, настроек и сертификатов,
    без глобальных инструкций (agents-global.md, CLAUDE.md) и пользовательских расширений.
    Защита от race condition (F-001): потокобезопасная однократная инициализация под lock,
    атомарная запись через временный файл (os.replace) и строгие права 0700/0600.
    """
    global _CLAUDE_HOME_INITIALIZED
    real_claude = Path.home() / ".claude"
    home = WORKSPACE / "runtime" / "claude-home"
    claude_dir = home / ".claude"

    if _CLAUDE_HOME_INITIALIZED and claude_dir.is_dir():
        return home

    with _CLAUDE_HOME_LOCK:
        if _CLAUDE_HOME_INITIALIZED and claude_dir.is_dir():
            return home

        home.mkdir(parents=True, exist_ok=True)
        claude_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(claude_dir, 0o700)
        except OSError:
            pass

        allowed_files = (
            "settings.json",
            "aeza-8788-ca.pem",
            "bundle-with-aeza.pem",
            "policy-limits.json",
            "policy-limits.json.signature.json",
            "policy-limits.json.stamp.json",
        )

        for name in allowed_files:
            source = real_claude / name
            if source.is_file():
                dest = claude_dir / name
                tmp_dest = claude_dir / f".tmp_{name}_{uuid.uuid4().hex[:8]}"
                try:
                    shutil.copy2(source, tmp_dest)
                    os.chmod(tmp_dest, 0o600)
                    os.replace(tmp_dest, dest)
                except OSError:
                    if tmp_dest.exists():
                        try:
                            tmp_dest.unlink()
                        except OSError:
                            pass

        _CLAUDE_HOME_INITIALIZED = True
        return home
MAX_CONCURRENT = int(os.environ.get("CLAUDE_P_BRIDGE_MAX_CONCURRENT", "8"))
QUEUE_TIMEOUT_S = int(os.environ.get("CLAUDE_P_BRIDGE_QUEUE_TIMEOUT", "900"))
KEEPALIVE_S = float(os.environ.get("CLAUDE_P_BRIDGE_KEEPALIVE", "15"))
MAX_REQUEST_BYTES = _env_positive_int("CLAUDE_P_BRIDGE_MAX_BODY_BYTES", 100 * 1024 * 1024)
QUEUE_MAXSIZE = _env_positive_int("CLAUDE_P_BRIDGE_QUEUE_MAXSIZE", 1000)
MAX_STDERR_BYTES = _env_positive_int("CLAUDE_P_BRIDGE_MAX_STDERR_BYTES", 10 * 1024 * 1024)
IO_CHUNK_BYTES = _env_positive_int("CLAUDE_P_BRIDGE_IO_CHUNK_BYTES", 64 * 1024)
PROCESS_WAIT_S = float(os.environ.get("CLAUDE_P_BRIDGE_PROCESS_WAIT_S", "5"))
POLL_INTERVAL_S = float(os.environ.get("CLAUDE_P_BRIDGE_POLL_INTERVAL_S", "1"))
STDERR_DRAIN_S = float(os.environ.get("CLAUDE_P_BRIDGE_STDERR_DRAIN_S", "0.05"))
HTTP_TIMEOUT_S = float(os.environ.get("CLAUDE_P_BRIDGE_HTTP_TIMEOUT_S", "300"))
HTTP_BACKLOG = _env_positive_int("CLAUDE_P_BRIDGE_HTTP_BACKLOG", 64)
# Лимиты и корень временных каталогов изображений — только через env с безопасными
# значениями по умолчанию из core (без хардкода эксплуатационных параметров).
MAX_IMAGES = _env_positive_int("CLAUDE_P_BRIDGE_MAX_IMAGES", DEFAULT_MAX_IMAGES)
MAX_IMAGE_BYTES = _env_positive_int(
    "CLAUDE_P_BRIDGE_MAX_IMAGE_BYTES", DEFAULT_MAX_IMAGE_BYTES
)
MAX_TOTAL_IMAGE_BYTES = _env_positive_int(
    "CLAUDE_P_BRIDGE_MAX_TOTAL_IMAGE_BYTES", DEFAULT_MAX_TOTAL_IMAGE_BYTES
)
IMAGE_TMP_ROOT = Path(os.environ.get("CLAUDE_P_BRIDGE_TMPDIR", "/tmp"))
MODEL_CONTEXT = {
    "claude-sonnet-5-5": 1_000_000,
    "claude-opus-5-5": 1_000_000,
    "claude-haiku-5-5": 200_000,
}
CONTEXT_LENGTH = 1_000_000  # fallback для неизвестных моделей
TOOL_CALL_OPEN = "<tool_call>"
TOOL_CALL_CLOSE = "</tool_call>"

_slots = threading.BoundedSemaphore(MAX_CONCURRENT)
_active = {}
_active_img_dirs: set = set()
_active_lock = threading.Lock()
_started = time.time()


def _log(msg: str) -> None:
    """Диагностика в stderr (файлы вне каталога моста не создаём)."""
    try:
        sys.stderr.write(
            f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}\n"
        )
        sys.stderr.flush()
    except OSError:
        pass


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
    """Материализовать изображения в `/tmp/claude-img-<uuid>/` (0700, файлы 0600).

    Каталог создаётся атомарно без изменения глобального umask, файлы —
    exclusive/no-follow созданием. При частичной ошибке каталог удаляется здесь же.
    """
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


def _build_claude_cmd(model: str, effort: str, img_dir: Path | None = None) -> list:
    """argv `claude -p`; с картинками — только встроенный Read по `--add-dir` (AD-003)."""
    cmd = [
        CLAUDE_BIN, "-p",
        "--model", model,
        "--effort", effort,
        "--output-format", "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--strict-mcp-config",
        "--mcp-config", str(MCP_CONFIG),
    ]
    if img_dir is not None:
        cmd += ["--permission-mode", "dontAsk",
                "--tools", "Read", "--allowedTools", f"Read({img_dir}/**)",
                "--add-dir", str(img_dir)]
    else:
        # Встроенные инструменты отключены: действия идут только через DSH.
        cmd += ["--permission-mode", "bypassPermissions", "--tools", ""]
    return cmd


def _effort(value: Any, model: str = MODEL_ID) -> str:
    """reasoning_effort -> уровень claude для модели (замеры KB 13.10/19.10.2026).

    Opus 5.5: low/medium/high; xhigh и max -> high. Sonnet 5.5: low/medium/high/xhigh;
    max -> xhigh. Haiku 5.5: low/medium/high/xhigh/max (max не по умолчанию: 300 с+
    против 25-40 с на high). Всё остальное (none/пусто/мусор) -> дефолт модели `high`.
    """
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
                 img_dir: Path | None = None):
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        # С картинками Claude работает из сессионного каталога вложений: пути
        # в секции [attachments] относительные, Read ограничен этим каталогом.
        cmd = _build_claude_cmd(model, effort, img_dir)
        self.cmd = cmd
        self.img_dir = img_dir
        _log(f"exec model={model} effort={effort} prompt_bytes={len(prompt.encode())} {tag}")
        child_env = os.environ.copy()
        child_env["HOME"] = str(_prepare_claude_home())
        child_env["BRIDGE_ZERO_CANON"] = "1"
        child_env.pop("CLAUDE_P_BRIDGE_KEY", None)

        self.proc = spawn_registered(
            cmd, cwd=str(img_dir if img_dir is not None else WORKSPACE),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True, env=child_env,
        )
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
        spawn_registered.unregister(self.proc)
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


@_LIFECYCLE.install
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = HTTP_TIMEOUT_S

    def log_message(self, format: str, *args: Any) -> None:
        _log("http " + (format % args))

    def handle_error(self, request: Any, client_address: Any) -> None:
        _log(f"http accept error from {client_address}")

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

    def _execute(self, run: Run, on_text, on_reasoning, on_tool_call,
                 keepalive, emulate_tools: bool, tools: list | None = None) -> dict:
        """Гнать ход до конца.

        on_text/on_reasoning/on_tool_call/keepalive возвращают False, если клиент ушёл.
        Весь текстовый поток ВСЕГДА проходит через `StreamNormalizer` поверх
        `ToolCallParser(strict_live=True)` (AD-004, ALWAYS-ON — в том числе без
        tools и при tool_choice=none): повреждённый `<tool_call>` поднимает
        `LiveParserError`, сырой XML в content не уходит; распознанный вызов без
        эмуляции — ошибка протокола, а не опубликованный инструмент. Reasoning
        (нативный thinking и теги в тексте) публикуется до терминального события.
        """
        pieces = []
        reasoning_pieces: list = []
        tool_calls: list = []
        usage = {}
        result_ev = {}
        tool_schemas = build_tool_schemas(tools or [])
        last_ka = time.monotonic()
        gone = [False]

        def state(name: str, rc: int, err: str = "") -> dict:
            return {"rc": rc, "text": "".join(pieces), "usage": usage,
                    "reasoning": "".join(reasoning_pieces),
                    "result": result_ev, "state": name, "err": err,
                    "tool_calls": tool_calls}

        def add_content(text: str) -> None:
            if gone[0] or not text:
                return
            pieces.append(text)
            if not on_text(text):
                gone[0] = True

        def add_reasoning(text: str) -> None:
            if gone[0] or not text:
                return
            reasoning_pieces.append(text)
            if not on_reasoning(text):
                gone[0] = True

        def add_call(call: dict) -> None:
            if gone[0]:
                return
            if not emulate_tools:
                raise LiveParserError("tool_call published without tool emulation")
            entry = {
                "index": len(tool_calls),
                "id": "call_" + uuid.uuid4().hex[:24],
                "type": "function",
                "function": {
                    "name": call["name"],
                    "arguments": json.dumps(call["arguments"], ensure_ascii=False),
                },
            }
            # Схемная санитизация — ровно один раз на владельце маршрута (AD-004).
            for item in sanitize_tool_call(entry, tool_schemas):
                item = dict(item, index=len(tool_calls))
                tool_calls.append(item)
                if not on_tool_call(item):
                    gone[0] = True
                    return

        normalizer = StreamNormalizer(
            add_content, add_reasoning, add_call, strict_live=True
        )

        controller = None
        last_check_ts = time.monotonic()
        proc = getattr(run, "proc", None)
        proc_pid = getattr(proc, "pid", None) if proc is not None else None

        if _is_watchdog_enabled() and AdaptiveTimeoutController is not None and proc_pid:
            controller = AdaptiveTimeoutController(
                idle_timeout_s=CLAUDE_P_BRIDGE_IDLE_TIMEOUT_S,
                safety_cap_s=CLAUDE_P_BRIDGE_SAFETY_CAP_S,
                io_wait_cap_s=CLAUDE_P_BRIDGE_IO_WAIT_CAP_S,
                watchdog_interval_s=CLAUDE_P_BRIDGE_WATCHDOG_INTERVAL_S,
            )
            controller.register_pgid(proc_pid)

        try:
            while True:
                if _client_gone(self.connection):
                    return state("client_gone", 1)

                now = time.monotonic()
                if controller is not None and proc is not None and proc_pid and (
                    now - last_check_ts >= controller.watchdog_interval_s
                ):
                    last_check_ts = now
                    should_stop, reason, _ = controller.check(proc_pid)
                    if should_stop and reason in ("idle_timeout", "absolute_cap"):
                        _kill_group(proc)
                        return state("timeout", 1, f"claude-p watchdog: {reason}")
                    # Если reason == "child_exited" — нормальный выход потомка,
                    # не убиваем, ждём done из очереди.

                try:
                    kind, payload = run.q.get(timeout=POLL_INTERVAL_S)
                except queue.Empty:
                    if keepalive is not None and time.monotonic() - last_ka >= KEEPALIVE_S:
                        last_ka = time.monotonic()
                        if not keepalive():
                            return state("client_gone", 1)
                    continue

                if controller is not None and kind in ("text", "thinking", "result"):
                    controller.record_activity(kind)

                if kind == "text":
                    normalizer.feed_text(str(payload))
                    if gone[0]:
                        return state("client_gone", 1)
                elif kind == "thinking":
                    normalizer.feed_thinking(str(payload))
                    if gone[0]:
                        return state("client_gone", 1)
                elif kind == "result":
                    result_ev = payload
                    usage = payload.get("usage") or {}
                elif kind == "pump_error":
                    return state("pump_error", 1, str(payload))
                elif kind == "done":
                    # Fail-closed финал: незакрытый/битый хвост — LiveParserError наверх,
                    # сырой XML текстом не досбрасываем. Fallback на терминальный
                    # `result` исключён (AD-004): пустой ход — ошибка 502 в _error_body.
                    normalizer.finish()
                    if gone[0]:
                        return state("client_gone", 1)
                    time.sleep(STDERR_DRAIN_S)
                    return state("done", payload, "".join(run.err_box))
        finally:
            if controller is not None:
                controller.close()

    def _run_once(self, req: dict, on_text, on_reasoning, on_tool_call, keepalive) -> dict:
        raw_messages = req.get("messages")
        messages: list = raw_messages if isinstance(raw_messages, list) else []
        raw_tools = req.get("tools")
        tools = [t for t in raw_tools if isinstance(t, dict)] if isinstance(raw_tools, list) else []
        tool_choice = req.get("tool_choice")
        emulate_tools = bool(tools) and not _tool_choice_none(tool_choice)
        model, model_err = _resolve_model(req)
        if model_err is not None:
            return {"state": "bad_model", "rc": 1, "text": "", "usage": {}, "result": {},
                    "err": model_err["message"], "tool_calls": []}
        try:
            images = _extract_request_images(req)
        except ImageInputError as exc:
            return {"state": "bad_image", "rc": 1, "text": "", "usage": {}, "result": {},
                    "err": exc.code, "tool_calls": []}
        prompt = _messages_to_prompt(messages, tools, tool_choice, images or None)
        effort = _effort(req.get("reasoning_effort"), model)
        tag = (f"client={self.client_address[0]}:{self.client_address[1]} "
               f"ua={(self.headers.get('User-Agent') or '-')[:60]}")
        reason = self._acquire_slot(keepalive)
        if reason:
            _log(f"no slot ({reason}) model={model} effort={effort} {tag}")
            return {"state": reason, "rc": 1, "text": "", "usage": {}, "result": {},
                    "err": "", "tool_calls": []}
        t0 = time.monotonic()
        img_dir = None
        can_cleanup = True
        try:
            try:
                img_dir = _stage_images(images)
                run = Run(prompt, model, effort, tag, img_dir=img_dir)
                can_cleanup = False
            except OSError as exc:
                _log(f"image stage/spawn failed model={model} err={exc!r:.200} {tag}")
                return {"state": "image_error", "rc": 1, "text": "", "usage": {},
                        "result": {}, "err": str(exc)[:200], "tool_calls": []}
            try:
                out = self._execute(run, on_text, on_reasoning, on_tool_call,
                                    keepalive, emulate_tools, tools)
            except LiveParserError as exc:
                # AD-004: битый поток — 502 proxy_error; сырой XML клиенту не уходит.
                _log(f"parser_error model={model} err={exc} {tag}")
                out = {"state": "parser_error", "rc": 1, "text": "", "reasoning": "",
                       "usage": {}, "result": {}, "err": str(exc), "tool_calls": []}
            finally:
                run.close()  # сначала завершить и reap своего ребёнка
                can_cleanup = True
        finally:
            if can_cleanup:
                _cleanup_img_dir(img_dir)
            _slots.release()
        out_calls = out.get("tool_calls")
        out_text = out.get("text")
        _log(f"done model={model} effort={effort} rc={out['rc']} state={out['state']} "
             f"tools={len(out_calls) if isinstance(out_calls, list) else 0} "
             f"out_bytes={len(out_text.encode()) if isinstance(out_text, str) else 0} "
             f"wall_s={time.monotonic() - t0:.1f} {tag}")
        return out

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
                "ok": True, "transport": "claude-p", "model": MODEL_ID,
                "models": list(SUPPORTED_MODELS),
                "active": active, "max_concurrent": MAX_CONCURRENT,
                "tool_emulation": True, "images": True, "live_reasoning": True,
                "uptime_s": int(time.time() - _started),
            })
            return
        if not _auth_ok(self):
            self._send(401, {"error": {"message": "unauthorized", "type": "auth_error"}})
            return
        if path in ("/v1/models", "/models"):
            self._send(200, {"object": "list", "data": [{
                "id": model_id, "object": "model", "owned_by": "anthropic",
                "created": 0, "context_length": MODEL_CONTEXT.get(model_id, CONTEXT_LENGTH),
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
            req = json.loads(raw.decode("utf-8") or "{}")
        except ValueError:
            self._send(400, {"error": {"message": "invalid json"}})
            return
        if path not in ("/v1/chat/completions", "/chat/completions"):
            self._send(404, {"error": {"message": f"not found: {path}"}})
            return
        # Невалидную модель отсекаем до SSE-заголовков, иначе 400 уже не отправить.
        _model, model_err = _resolve_model(req)
        if model_err is not None:
            self._send(400, {"error": {"message": model_err["message"],
                                       "type": model_err["type"]}})
            return
        # Невалидные изображения отсекаем там же, до спавна и SSE-заголовков.
        try:
            _extract_request_images(req)
        except ImageInputError as exc:
            self._send(400, {"error": {"message": f"invalid image input: {exc.code}",
                                       "type": "invalid_request_error"}})
            return
        if req.get("stream"):
            self._serve_sse(req)
        else:
            self._serve_json(req)

    def _serve_json(self, req: dict) -> None:
        out = self._run_once(req, lambda _v: True, lambda _v: True, lambda _e: True, None)
        if out.get("state") == "client_gone":
            return
        err = self._error_body(out)
        if err is not None:
            self._send(err["code"], {"error": err})
            return
        usage = out.get("usage") or {}
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
            "usage": {
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            },
        })

    def _serve_sse(self, req: dict) -> None:
        completion_id = f"chatcmpl-claudep-{uuid.uuid4().hex[:12]}"
        created = int(time.time())
        shown_model = str(req.get("model") or MODEL_ID)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            self.close_connection = True
        except (BrokenPipeError, ConnectionResetError, OSError):
            _log("client gone before headers")
            return

        def chunk(delta: dict, finish=None) -> str:
            return "data: " + json.dumps({
                "id": completion_id, "object": "chat.completion.chunk", "created": created,
                "model": shown_model,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }, ensure_ascii=False) + "\n\n"

        def on_text(value: str) -> bool:
            return self._emit(chunk({"content": value}))

        def on_reasoning(value: str) -> bool:
            return self._emit(chunk({"reasoning_content": value}))

        def on_tool_call(entry: dict) -> bool:
            return self._emit(chunk({"tool_calls": [entry]}))

        def keepalive() -> bool:
            return self._emit(": keepalive\n\n")

        if not self._emit(chunk({"role": "assistant", "content": ""})):
            return
        out = self._run_once(req, on_text, on_reasoning, on_tool_call, keepalive)
        if out.get("state") == "client_gone":
            _log("client gone mid-stream, child killed")
            return
        err = self._error_body(out)
        if err is None:
            finish = "tool_calls" if out.get("tool_calls") else "stop"
            self._emit(chunk({}, finish))
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
