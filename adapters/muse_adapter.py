"""Адаптер Meta Muse Code CLI: exec (ADR 0002) и per-turn MSP serve (ADR 0012).

Один ход = один headless-запуск `~/.config/muse-launch/muse-cli.sh exec … --json`
(обёртка держит прокси-контур :10816, вычищает `META_API_KEY` и возвращает exit 42 при
недоступном прокси). Сессий нет (`sessions="none"`): каждый ход — полный replay истории,
которую фасад уже собрал в `ctx["prompt"]`; блоки `<tool_call>` из текста разбирает фасад.

Решение владельца AD-007 (2026-10-08 12:07 MSK, «ставим --yolo»): флаги `--yolo
--trust-workspace` сохраняются, как в muse-bridge :9886. Риск (нативные shell/write/web
инструменты Muse при отключённых approval и sandbox) компенсируется: ход исполняется в
собственном подкаталоге `workspace/muse/turn-<uuid>/` (0700), оба `cwd` и `--workspace`
указывают только на него, prompt-файл лежит внутри и удаляется вместе с каталогом в
`finally`; параллельные ходы сериализованы (`fleet.json` `max_concurrent: 1`) — при одном
UID процессы нельзя взаимно изолировать правами, поэтому одновременный доступ исключён
планированием (RW-001). Окружение ребёнка — allowlist без `META_API_KEY`, ключа моста и
унаследованного `MUSE_BIN` (обёртка берёт канонический `~/.local/bin/muse`, именно его
сверяет обязательный pin `technical_ref` — RW-002); `MUSE_PROXY_PORT` — нормализованный
`proxy_port` бэкенда, а не ambient-значение (RW-011). Ход успешен только при
`terminal.completed` (RW-004), автоматического replay промпта нет (RW-003), текст и
failure reasons ограничены общим байтовым бюджетом (RW-006), завершение группы процессов
ограничено по времени и потомки гасятся до освобождения слота (RW-009), собственные дети
регистрируются в персистентном реестре хаба для reconcile после SIGKILL (RW-010), сырые
stderr/terminal reason в журнал не пишутся (RW-007). Модуль не импортирует `server`:
настройки берутся у `host` (duck-typing: WORKSPACE, TIMEOUT_S, QUEUE_TIMEOUT_S,
KEEPALIVE_S, `_log`, необязательные `_children_update`/`_proc_start_sig`) либо из
значений по умолчанию.
"""

from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import shutil
import signal
import socket
import select
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, cast

from adapters.muse_msp import LIVE_DELTA_MAX_BYTES, MspEvents, utf8_slices

from core.backend_adapter import (
    SESSIONS_NONE,
    STREAMING_EMULATED,
    STREAMING_NATIVE,
    BackendAdapter,
    BackendNotSupported,
    BackendModel,
    Capabilities,
    Qualification,
    StreamSink,
    TurnContext,
    TurnResult,
    Usage,
)
from core.watchdog import AdaptiveTimeoutController


DEFAULT_WRAPPER = "~/.config/muse-launch/muse-cli.sh"
DEFAULT_PROXY_PORT = 10816
PROXY_DOWN_RC = 42  # обёртка: прокси-контур недоступен, прямой вызов запрещён
# Окружение ребёнка — allowlist, а не наследование (ADR 0002, AD-007 п. 3).
# `MUSE_BIN` в allowlist НЕТ и вычищается явно: обёртка иначе исполнила бы произвольный файл
# в обход qualify (RW-002). `MUSE_PROXY_PORT` всегда перезаписывается нормализованным
# значением бэкенда, а не ambient-окружением (RW-011).
ENV_ALLOWLIST = (
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TMPDIR",
    "TERM",
    "TZ",
    "MUSE_PROXY_PORT",
    "NO_PROXY",
    "no_proxy",
)
_DEFAULT_PATH = "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
MAX_LINE_BYTES = 8 << 20  # одна JSONL-строка stdout
MAX_TURN_TEXT_BYTES = 10 << 20  # суммарный текст хода, включая failure reasons (RW-006)
MAX_ERR_LINES = 6  # строк stderr в err-сводке
MAX_ERR_CHARS = 500  # длина одной строки/причины в err-сводке
MAX_EVENT_ERRORS = 6  # ошибок из потока событий: bounded-буфер до append (RW-006)
STDERR_DRAIN_GRACE_S = 5.0  # грейс добора stderr после EOF stdout (RW-009)
MAX_JSON_STRUCT_TOKENS = 50_000
MAX_JSON_DEPTH = 128
MAX_EVENTS = 50_000
READ_CHUNK_BYTES = 65536
ANSWER_RESERVE_BYTES = 2 << 20
LIVE_QUEUE_CAPACITY = 1000
LIVE_QUEUE_MAX_BYTES = 1 << 20
LIVE_WRITE_TIMEOUT_S = 3.0
SINK_JOIN_TIMEOUT_S = 5.0
STDERR_BUFFER_BYTES = 64 << 10
MSP_SETUP_TIMEOUT_S = 30.0
_MUSE_SLOTS = threading.BoundedSemaphore(1)  # один UID: общий слот всех Muse-адаптеров
# Свидетель группы создаётся ДО exec и подписывается/пишется в реестр ДО открытия gate.
# Он не держит stdout/stderr, но остаётся жив после выхода лидера и аварии хаба.
_GROUP_BOOTSTRAP = """
import os, signal, sys
ready, gate = int(sys.argv[1]), int(sys.argv[2])
member = os.fork()
if member == 0:
    for fd in (0, 1, 2, ready, gate):
        try: os.close(fd)
        except OSError: pass
    while True: signal.pause()
os.write(ready, (str(member) + "\\n").encode("ascii"))
os.close(ready)
if os.read(gate, 1) != b"1":
    os.killpg(0, signal.SIGKILL)
os.close(gate)
os.execv(sys.argv[3], sys.argv[3:])
"""
TURN_DIR_PREFIX = "turn-"
_TOKEN_SPLIT = re.compile(r"\s+")


def estimate_tokens(text: str) -> int:
    """Оценка токенов по словам (×1.3), как в muse-bridge: exec точных токенов не отдаёт."""
    if not text:
        return 0
    return max(1, int(len(_TOKEN_SPLIT.split(text.strip())) * 1.3))


def _check_json_structure(raw: str) -> None:
    """Ограничить вложенность и число структурных токенов до декодирования JSON."""
    depth = tokens = 0
    in_string = escaped = False
    for char in raw:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "{[":
            depth += 1
            tokens += 1
        elif char in "}]":
            depth -= 1
        elif char in ",:":
            tokens += 1
        if depth > MAX_JSON_DEPTH or tokens > MAX_JSON_STRUCT_TOKENS:
            raise ValueError("json structure exceeds the limit")


class ExecEvents:
    """Накопитель JSONL-конвертов `muse exec --json` (payload_type / payload).

    Любой текст (дельта, финальный, failure reason) списывается в общий байтовый бюджет
    хода, а errors/reason хранятся в bounded-виде: итоговый join не выделяет накопленную
    строку целиком до обрезки (RW-006).
    """

    def __init__(self) -> None:
        self.deltas: list = []
        self.final_text: "str | None" = None
        self.terminal: "str | None" = None
        self.reason: "str | None" = None
        self.errors: list = []
        self.text_bytes = 0
        self.event_count = 0

    def _charge(self, text: str) -> None:
        """Текст учитывается в байтовом бюджете хода (включая причины ошибок)."""
        self.text_bytes += len(text.encode("utf-8", "strict"))

    def feed_line(self, raw: str) -> None:
        raw = raw.strip()
        if not raw:
            return
        self.event_count += 1
        if self.event_count > MAX_EVENTS:
            raise ValueError("event count exceeds the limit")
        _check_json_structure(raw)
        try:
            event = json.loads(raw)
        except RecursionError as exc:
            raise ValueError("json depth exceeds the limit") from exc
        except ValueError:
            return
        if not isinstance(event, dict):
            return
        ptype = str(event.get("payload_type") or "")
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if ptype == "run.output.delta":
            text = payload.get("text")
            if isinstance(text, str) and text:
                self._charge(text)
                self.deltas.append(text)
        elif ptype.startswith("run.terminal"):
            expected = {
                "run.terminal.completed": "completed",
                "run.terminal.failed": "failed",
                "run.terminal.cancelled": "cancelled",
            }.get(ptype)
            if (
                expected is None
                or payload.get("terminal") != expected
                or self.terminal is not None
            ):
                raise ValueError("terminal envelope invalid")
            self.terminal = expected
            text = payload.get("text")
            if isinstance(text, str):
                self._charge(text)
                self.final_text = text
            reason = payload.get("reason")
            if isinstance(reason, str) and reason:
                self._charge(reason)
                self.reason = reason[:MAX_ERR_CHARS]
        elif ptype == "task.lifecycle.failed":
            inner = payload.get("event")
            inner = inner if isinstance(inner, dict) else {}
            reason = inner.get("reason")
            if isinstance(reason, str) and reason:
                text = f"task failed: {reason}"
                self._charge(text)
                if len(self.errors) < MAX_EVENT_ERRORS:
                    self.errors.append(text[:MAX_ERR_CHARS])

    @property
    def text(self) -> str:
        """Итоговый текст: финальный из terminal (приоритет) либо склейка дельт."""
        return self.final_text if self.final_text else "".join(self.deltas)


class _LiveSink:
    """Ограниченный, необратимо отключаемый live sink; stdout никогда не ждёт сокет."""

    def __init__(self, writer: StreamSink | None) -> None:
        self.writer = writer
        self.queue: queue.Queue[str | None] = queue.Queue(maxsize=LIVE_QUEUE_CAPACITY)
        self.live_degraded = threading.Event()
        self.client_write_dead = threading.Event()
        self.sink_closed = threading.Event()
        self._lock = threading.Lock()
        self.queued_bytes = 0
        self.inflight_at: float | None = None
        self.consumer: threading.Thread | None = None
        if writer is not None:
            self.consumer = threading.Thread(target=self._consume, daemon=True)
            self.consumer.start()

    def offer(self, text: str) -> None:
        if (
            self.writer is None
            or self.live_degraded.is_set()
            or self.sink_closed.is_set()
        ):
            return
        for piece in utf8_slices(text, LIVE_DELTA_MAX_BYTES):
            size = len(piece.encode())
            with self._lock:
                if self.queued_bytes + size > LIVE_QUEUE_MAX_BYTES:
                    self.live_degraded.set()
                    return
                try:
                    self.queue.put_nowait(piece)
                except queue.Full:
                    self.live_degraded.set()
                    return
                self.queued_bytes += size

    def check_timeout(self) -> None:
        started = self.inflight_at
        if started is not None and time.monotonic() - started >= LIVE_WRITE_TIMEOUT_S:
            self.live_degraded.set()

    def _consume(self) -> None:
        assert self.writer is not None
        while not self.sink_closed.is_set():
            try:
                piece = self.queue.get(timeout=0.05)
            except queue.Empty:
                continue
            if piece is None:
                return
            with self._lock:
                self.queued_bytes -= len(piece.encode())
            if self.live_degraded.is_set() or self.sink_closed.is_set():
                continue
            self.inflight_at = time.monotonic()
            try:
                if not self.writer("reasoning", piece):
                    self.live_degraded.set()
                    self.client_write_dead.set()
            except Exception:  # noqa: BLE001 - отказ произвольного sink не останавливает pipe
                self.live_degraded.set()
                self.client_write_dead.set()
            finally:
                self.check_timeout()
                self.inflight_at = None

    def close(self) -> None:
        self.sink_closed.set()
        try:
            self.queue.put_nowait(None)
        except queue.Full:
            self.live_degraded.set()
        if self.consumer is not None:
            self.consumer.join(timeout=SINK_JOIN_TIMEOUT_S)
            if self.consumer.is_alive():
                self.live_degraded.set()


class MuseAdapter(BackendAdapter):
    kind = "muse"
    capabilities = Capabilities(SESSIONS_NONE, STREAMING_EMULATED, False, "estimated")

    def __init__(
        self,
        backend_id: str,
        config: Mapping[str, Any],
        catalog_source: Callable[[], Mapping[str, Any]],
        host: Any = None,
        *,
        workspace: "Path | None" = None,
    ):
        super().__init__(backend_id, config, catalog_source, host)
        options = self.config.get("options", {})
        if not isinstance(options, dict) or options.get(
            "streaming_mode", "exec"
        ) not in ("exec", "serve"):
            raise ValueError("backend_streaming_mode_invalid")
        self.streaming_mode = options.get("streaming_mode", "exec")
        self.capabilities = Capabilities(
            SESSIONS_NONE,
            STREAMING_NATIVE if self.streaming_mode == "serve" else STREAMING_EMULATED,
            False,
            "estimated",
        )
        self.wrapper = os.path.expanduser(
            str(self.config.get("wrapper") or DEFAULT_WRAPPER)
        )
        if workspace is None:
            base = getattr(host, "WORKSPACE", None)
            workspace = (
                Path(base) / "muse"
                if base
                else Path(os.getcwd()) / "workspace" / "muse"
            )
        self.workspace = Path(workspace)
        # proxy_port нормализуется один раз: preflight и child_env получают одно значение (RW-011).
        self.proxy_port = self._normalize_proxy_port()
        if self.max_concurrent != 1:
            raise ValueError("muse_max_concurrent_must_be_one")
        self._slots = _MUSE_SLOTS
        self._active: dict = {}  # pid -> Popen (под _lock): остановка и /health
        self._lock = threading.Lock()
        self._sha_cache: dict = {}
        self._shutting_down = False

    # -- настройки хоста (читаются на каждом ходе: тесты подменяют значения) -------------
    def _setting(self, name: str, default: float) -> float:
        return float(getattr(self.host, name, default))

    def _log(self, message: str) -> None:
        log = getattr(self.host, "_log", None)
        if callable(log):
            log(message)

    # -- модели / допуск / здоровье ------------------------------------------------------
    def get_models(self) -> list[BackendModel]:
        return self._catalog_models()

    def _file_sha256(self, path: str) -> str:
        try:
            os.stat(path)
        except OSError:
            return ""
        try:
            with open(path, "rb") as handle:
                digest = hashlib.sha256()
                for chunk in iter(lambda: handle.read(READ_CHUNK_BYTES), b""):
                    digest.update(chunk)
        except OSError:
            return ""
        return digest.hexdigest()

    def qualify(self) -> Qualification:
        """Допуск: обёртка исполняема; образ Muse совпал с обязательным pin `technical_ref`.

        Без комплектного pin квалифицировать нечего (AD-007), и ход не запускается: иначе
        обёртка исполнила бы произвольный файл (в т.ч. подсунутый через `MUSE_BIN`) без
        проверки. Обёртка при этом сама выбирает канонический `~/.local/bin/muse` — ровно
        тот путь, который сверяет pin (RW-002).
        """
        if not (os.path.isfile(self.wrapper) and os.access(self.wrapper, os.X_OK)):
            return Qualification(False, "wrapper_not_executable")
        ref = self.config.get("technical_ref")
        if not isinstance(ref, dict):
            return Qualification(False, "pin_missing")
        binary = os.path.expanduser(str(ref.get("binary_path") or ""))
        pinned = str(ref.get("binary_sha256") or "")
        if not binary or not pinned:
            return Qualification(False, "pin_missing")
        canonical = os.path.abspath(os.path.expanduser("~/.local/bin/muse"))
        if os.path.abspath(binary) != canonical:
            return Qualification(False, "binary_path_not_canonical")
        actual = self._file_sha256(binary)
        if not actual:
            return Qualification(False, "binary_missing")
        if actual != pinned:
            return Qualification(False, "binary_sha256_mismatch")
        return Qualification(True, "ok")

    def _normalize_proxy_port(self) -> int:
        """proxy_port бэкенда (иначе env, иначе default) -> int; мусор -> default."""
        raw = self.config.get("proxy_port") or os.environ.get("MUSE_PROXY_PORT")
        try:
            port = int(raw) if raw else DEFAULT_PROXY_PORT
            return port if 1 <= port <= 65535 else DEFAULT_PROXY_PORT
        except (TypeError, ValueError):
            return DEFAULT_PROXY_PORT

    def _proxy_up(self) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", self.proxy_port), timeout=0.3):
                return True
        except OSError:
            return False

    def is_healthy(self) -> bool:
        """Дёшево и без spawn: допуск пройден и прокси-контур слушает."""
        return self.qualify()[0] and self._proxy_up()

    def preflight(self) -> Qualification:
        ok, reason = self.qualify()
        if not ok:
            return Qualification(False, reason)
        if not self._proxy_up():
            return Qualification(False, "proxy_down")
        return Qualification(True, "")

    def active_count(self) -> int:
        with self._lock:
            return len(self._active)

    # -- сессии (нет) ---------------------------------------------------------------------
    def spawn_session(self, ctx: TurnContext) -> object:
        raise BackendNotSupported("sessions_none")

    def close_session(self, sid: str) -> None:
        return None

    # -- запуск --------------------------------------------------------------------------
    def build_argv(self, model: str, effort: str, prompt_path: str) -> list:
        """argv `muse exec` (политика AD-007: `--yolo --trust-workspace`, решение владельца).

        `--workspace` — каталог хода (родитель prompt-файла): общий `workspace/muse` в argv
        не попадает, prompt-файл хода не лежит в каталоге соседнего хода (RW-001).
        """
        return [
            self.wrapper,
            "exec",
            "--provider",
            "meta",
            "--model",
            model,
            "--reasoning-effort",
            effort,
            "--yolo",
            "--trust-workspace",
            "--workspace",
            str(Path(prompt_path).parent),
            "--json",
            "--no-session-log",
            "--prompt-file",
            prompt_path,
        ]

    def child_env(self) -> dict:
        """Окружение ребёнка: только allowlist; секреты моста и Meta вырезаны явно.

        `MUSE_BIN` вычищается всегда (RW-002), `MUSE_PROXY_PORT` перезаписывается
        нормализованным `proxy_port` бэкенда (RW-011).
        """
        env = {k: os.environ[k] for k in ENV_ALLOWLIST if k in os.environ}
        env.setdefault("PATH", _DEFAULT_PATH)
        env.pop("META_API_KEY", None)
        env.pop("DROID_DSH_BRIDGE_KEY", None)
        env.pop("MUSE_BIN", None)
        env["MUSE_PROXY_PORT"] = str(self.proxy_port)
        return env

    # -- реестр собственных детей (RW-010) -----------------------------------------------
    def _registry_update(
        self, add: dict | None = None, remove_pid: int | None = None
    ) -> None:
        """Обновить персистентный реестр детей хаба (server.children.json), если хост умеет.

        Запись жива после SIGKILL процесса: `reconcile_children()` на старте добивает только
        собственные осиротевшие группы по pid + start-signature, чужие процессы не трогает.
        """
        fn = getattr(self.host, "_children_update", None)
        if not callable(fn):
            return
        try:
            fn(add=add, remove_pid=remove_pid)
        except Exception as exc:  # noqa: BLE001 - реестр не должен ронять ход
            self._log(f"muse children_registry_failed err={type(exc).__name__}")

    def _register_child(self, pid: int, member: int) -> None:
        sig_fn = getattr(self.host, "_proc_start_sig", None)

        def signature(target: int) -> str:
            if callable(sig_fn):
                return str(sig_fn(target) or "")
            res = subprocess.run(
                ["ps", "-o", "lstart=", "-p", str(target)],
                capture_output=True,
                text=True,
                timeout=3,
            )
            return res.stdout.strip()

        start = signature(pid)
        member_start = signature(member)
        if not start or not member_start:
            raise OSError("group ownership signature unavailable")
        self._registry_update(
            add={
                "pid": pid,
                "pgid": pid,
                "start": start,
                "bridge_pid": os.getpid(),
                "kind": self.kind,
                "members": [{"pid": member, "start": member_start}],
            }
        )
        read = getattr(self.host, "_read_children", None)
        if callable(read) and not any(
            e.get("pid") == pid
            and e.get("members") == [{"pid": member, "start": member_start}]
            for e in cast(Any, read)()
        ):
            raise OSError("group ownership registration failed")

    def _unregister_child(self, pid: int) -> None:
        self._registry_update(remove_pid=pid)

    # -- процессная группа ----------------------------------------------------------------
    @staticmethod
    def _kill_group(proc: "subprocess.Popen") -> None:
        try:
            os.killpg(
                proc.pid, signal.SIGKILL
            )  # ребёнок — лидер своей группы (start_new_session)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                proc.kill()
            except OSError:
                pass

    @staticmethod
    def _group_alive(pgid: int) -> bool:
        """Жива ли группа процессов pgid (killpg с сигналом 0 ничего не убивает)."""
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return False
        except OSError:
            return True
        return True

    def _wait_group_exit(self, pgid: int, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while self._group_alive(pgid) and time.monotonic() < deadline:
            time.sleep(0.05)
        return not self._group_alive(pgid)

    def _make_turn_dir(self) -> Path:
        """Собственный каталог хода (0700) внутри базового workspace адаптера (RW-001)."""
        self.workspace.mkdir(parents=True, exist_ok=True)
        os.chmod(self.workspace, 0o700)
        turn_dir = self.workspace / (TURN_DIR_PREFIX + uuid.uuid4().hex)
        turn_dir.mkdir(mode=0o700)
        os.chmod(turn_dir, 0o700)
        return turn_dir

    def _result(
        self, state: str, rc: int, text: str = "", err: str = "", prompt: str = ""
    ) -> TurnResult:
        usage = Usage()
        if state == "done":
            usage = Usage(estimate_tokens(prompt), estimate_tokens(text))
        return TurnResult(state=state, rc=rc, text=text, usage=usage, err=err)

    def _acquire_slot(self, ctx: TurnContext) -> str:
        """Ждать ёмкость бэкенда (≤ QUEUE_TIMEOUT_S): '' — взят, иначе причина отказа."""
        queue_s = self._setting("QUEUE_TIMEOUT_S", 900.0)
        keepalive_s = self._setting("KEEPALIVE_S", 15.0)
        gone = ctx.client_gone
        keepalive = ctx.keepalive
        started = time.monotonic()
        last_ka = 0.0
        while not self._slots.acquire(timeout=1.0):
            if callable(gone) and gone():
                return "client_gone"
            now = time.monotonic()
            if now - started > queue_s:
                return "queue_timeout"
            if callable(keepalive) and now - last_ka >= keepalive_s:
                last_ka = now
                if not keepalive():
                    return "client_gone"
        return ""

    def execute_turn(
        self, ctx: TurnContext, sse_writer: Optional[StreamSink]
    ) -> TurnResult:
        """Один ход; автоматического replay промпта нет (RW-003): после старта процесса
        нативные shell/write/web-инструменты могли исполниться, повтор небезопасен даже при
        network-marker, поэтому ненулевой exit — сразу backend_error.
        """
        prompt = ctx.prompt
        ok, reason = self.preflight()
        if not ok:
            return self._result("launcher_unavailable", 1, err=reason)
        waited = self._acquire_slot(ctx)
        if waited:
            return self._result(waited, 1)
        managed_turn = getattr(ctx.handler, "_active_managed_turn", None)
        if managed_turn is not None:
            with managed_turn._lock:
                managed_turn._slot_released = False
                managed_turn._slot_release_fn = self._slots.release
        try:
            if self.streaming_mode == "serve":
                result, fallback = self._run_serve(ctx, sse_writer)
                if not fallback:
                    return result
                self._log(
                    f"muse serve setup failed; group exited; safe exec fallback reason={result.err}"
                )
            return self._run_exec(ctx, prompt)
        finally:
            if managed_turn is not None:
                managed_turn.release_slot_once()
            else:
                self._slots.release()

    def _run_serve(
        self, ctx: TurnContext, writer: StreamSink | None
    ) -> tuple[TurnResult, bool]:
        """Per-turn MSP с независимыми stdio и ограниченным consumer.

        Fallback возможен лишь до первого байта turn/start и после смерти всей группы.
        Это закрывает также потерянное/битое уведомление о начавшемся инструменте.
        """
        if self._shutting_down:
            return self._result(
                "launcher_unavailable", 1, err="adapter_shutting_down"
            ), False
        events = MspEvents(
            reasoning_cap=MAX_TURN_TEXT_BYTES - ANSWER_RESERVE_BYTES,
            answer_cap=ANSWER_RESERVE_BYTES,
        )
        done = threading.Event()
        reader_done = threading.Event()
        writes: queue.Queue[bytes] = queue.Queue(maxsize=32)
        flags: dict[str, bool] = {}
        threads: list[threading.Thread] = []
        pending_rpc: dict[int, str] = {}
        rpc_id = 0
        action_possible = False
        session_id = ""
        turn_id = ""
        stderr_tail = bytearray()
        proc: subprocess.Popen | None = None
        turn_dir: Path | None = None
        sink: _LiveSink | None = None
        pipe_fds: list[int] = []
        error = ""
        group_gone = True
        timeout_s = self._setting("TIMEOUT_S", 1800.0)
        idle_s = float(
            self.config.get("idle_timeout_s")
            or self._setting("IDLE_TIMEOUT_S", min(300.0, timeout_s))
        )
        safety_s = float(
            self.config.get("safety_cap_s") or self._setting("SAFETY_CAP_S", timeout_s)
        )
        controller = AdaptiveTimeoutController(
            idle_timeout_s=min(idle_s, timeout_s),
            safety_cap_s=safety_s,
            finish_reserve_s=0.0 if safety_s <= 60.0 else 35.0,
            watchdog_enabled=os.environ.get(
                "BRIDGE_ADAPTIVE_WATCHDOG_ENABLED", "true"
            ).lower()
            in ("1", "true", "yes", "on"),
            turn_id=ctx.turn_id,
            log_fn=self._log,
        )
        setup_deadline = time.monotonic() + min(MSP_SETUP_TIMEOUT_S, timeout_s)
        self._log(
            f"muse serve model={ctx.model} effort={ctx.effort} prompt_chars={len(ctx.prompt)}"
        )

        def send(method: str, params: dict[str, Any], notify: bool = False) -> None:
            nonlocal rpc_id, action_possible
            if method in ("turn/start", "approval/decide"):
                action_possible = True
            message: dict[str, Any] = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
            }
            if not notify:
                rpc_id += 1
                message["id"] = rpc_id
                pending_rpc[rpc_id] = method
            try:
                writes.put_nowait(
                    json.dumps(message, ensure_ascii=False).encode() + b"\n"
                )
            except queue.Full as exc:
                raise ValueError("MSP stdin queue full") from exc

        def handle(message: Any) -> None:
            nonlocal session_id, turn_id, action_possible
            if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
                raise ValueError("invalid MSP envelope")
            if "id" in message and "method" not in message:
                rid = message["id"]
                if (
                    isinstance(rid, bool)
                    or not isinstance(rid, int)
                    or rid not in pending_rpc
                ):
                    raise ValueError("unexpected MSP response")
                method = pending_rpc.pop(rid)
                result = message.get("result")
                if "error" in message or not isinstance(result, dict):
                    raw_error = message.get("error")
                    code = (
                        raw_error.get("code") if isinstance(raw_error, dict) else None
                    )
                    safe_code = str(code) if type(code) is int else "unknown"
                    raise ValueError(f"MSP {method} rejected code={safe_code}")
                if method == "initialize":
                    schema = result.get("schema")
                    if (
                        not isinstance(schema, dict)
                        or type(schema.get("version")) is not int
                        or schema["version"] != 1
                    ):
                        raise ValueError("unsupported MSP schema version")
                    send("initialized", {}, notify=True)
                    assert turn_dir is not None
                    send(
                        "session/start",
                        {
                            "commandId": str(uuid.uuid4()),
                            "workspaceRoot": str(turn_dir),
                            "providerId": "meta",
                            "modelId": ctx.model,
                            "approvalMode": "allowAll",
                        },
                    )
                elif method == "session/start":
                    session = result.get("session")
                    session_id = (
                        session.get("sessionId", "")
                        if isinstance(session, dict)
                        else ""
                    )
                    if not isinstance(session_id, str) or not session_id:
                        raise ValueError("MSP session id missing")
                    effort = "low" if ctx.effort == "minimal" else ctx.effort
                    send(
                        "turn/start",
                        {
                            "commandId": str(uuid.uuid4()),
                            "sessionId": session_id,
                            "reasoningEffort": effort,
                            "input": [{"type": "text", "text": ctx.prompt}],
                        },
                    )
                elif method == "turn/start":
                    turn_id = result.get("turnId", "")
                    if (
                        result.get("status") != "accepted"
                        or not isinstance(turn_id, str)
                        or not turn_id
                    ):
                        raise ValueError("MSP turn not accepted")
                return
            method = message.get("method")
            params = message.get("params", {})
            if not isinstance(method, str) or not isinstance(params, dict):
                raise ValueError("invalid MSP notification")
            if method.startswith("item/") and not action_possible:
                # Незапрошенная активность — не доказательство безопасного replay.
                action_possible = True
                raise ValueError("MSP activity before turn/start")
            if method in ("approval/request", "approval/requested"):
                choices = params.get("availableChoices", [])
                choice = (
                    next(
                        (
                            c
                            for c in choices
                            if isinstance(c, dict) and c.get("decision") == "approved"
                        ),
                        None,
                    )
                    if isinstance(choices, list)
                    else None
                )
                if choice is None:
                    raise ValueError("MSP approval choice unavailable")
                send(
                    "approval/decide",
                    {
                        "commandId": str(uuid.uuid4()),
                        "sessionId": session_id,
                        "approvalId": params.get("approvalId"),
                        "requirementId": params.get("currentRequirementId"),
                        "choiceId": choice.get("choiceId"),
                    },
                )
                return
            if turn_id and params.get("turnId", turn_id) != turn_id:
                raise ValueError("MSP turn id mismatch")
            piece = events.feed(method, params)
            assert sink is not None
            if events.live_degraded:
                sink.live_degraded.set()
            sink.offer(piece)

        try:
            turn_dir = self._make_turn_dir()
            ok, reason = self.preflight()
            if not ok:
                return self._result("launcher_unavailable", 1, err=reason), False
            ready_r, ready_w = os.pipe()
            gate_r, gate_w = os.pipe()
            pipe_fds = [ready_r, ready_w, gate_r, gate_w]
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    _GROUP_BOOTSTRAP,
                    str(ready_w),
                    str(gate_r),
                    self.wrapper,
                    "serve",
                    "--provider",
                    "meta",
                    "--model",
                    ctx.model,
                    "--no-session-log",
                    "--trust-workspace",
                ],
                cwd=str(turn_dir),
                env=self.child_env(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
                pass_fds=(ready_w, gate_r),
                start_new_session=True,
            )
            with self._lock:
                self._active[proc.pid] = proc
            for fd in (ready_w, gate_r):
                os.close(fd)
                pipe_fds.remove(fd)
            if not select.select([ready_r], [], [], 5.0)[0]:
                raise OSError("group witness handshake timed out")
            member = int(os.read(ready_r, 32).strip())
            self._register_child(proc.pid, member)
            if callable(ctx.register_pgid):
                ctx.register_pgid(proc.pid)
            os.write(gate_w, b"1")
            for fd in (ready_r, gate_w):
                os.close(fd)
                pipe_fds.remove(fd)
            controller.register_pgid(proc.pid)
            assert (
                proc.stdin is not None
                and proc.stdout is not None
                and proc.stderr is not None
            )
            stdin, stdout, stderr = proc.stdin, proc.stdout, proc.stderr
            for stream in (stdin, stdout, stderr):
                os.set_blocking(stream.fileno(), False)
            sink = _LiveSink(writer)

            def write_stdin() -> None:
                try:
                    while not done.is_set():
                        try:
                            raw = writes.get(timeout=0.05)
                        except queue.Empty:
                            continue
                        view = memoryview(raw)
                        deadline = time.monotonic() + min(
                            MSP_SETUP_TIMEOUT_S, timeout_s
                        )
                        while view and not done.is_set():
                            if time.monotonic() >= deadline:
                                raise OSError("MSP stdin write timeout")
                            if not select.select([], [stdin], [], 0.05)[1]:
                                continue
                            try:
                                count = os.write(stdin.fileno(), view)
                            except BlockingIOError:
                                continue
                            view = view[count:]
                except (OSError, ValueError):
                    if not done.is_set():
                        flags["protocol"] = True

            def drain_stderr() -> None:
                try:
                    while not done.is_set():
                        if not select.select([stderr], [], [], 0.05)[0]:
                            continue
                        try:
                            raw = os.read(stderr.fileno(), READ_CHUNK_BYTES)
                        except BlockingIOError:
                            continue
                        if not raw:
                            return
                        stderr_tail.extend(raw)
                        del stderr_tail[:-STDERR_BUFFER_BYTES]
                except (OSError, ValueError):
                    if not done.is_set():
                        flags["protocol"] = True

            def read_stdout() -> None:
                nonlocal error
                pending = bytearray()
                dropping = False
                count = 0
                try:
                    while not done.is_set() and events.terminal is None:
                        if not select.select([stdout], [], [], 0.05)[0]:
                            continue
                        try:
                            raw = os.read(stdout.fileno(), READ_CHUNK_BYTES)
                        except BlockingIOError:
                            continue
                        if not raw:
                            raise ValueError("MSP EOF before terminal")
                        for part in raw.splitlines(keepends=True):
                            pending.extend(part)
                            if len(pending) > MAX_LINE_BYTES:
                                dropping = True
                                pending.clear()
                                events.live_degraded = True
                                sink.live_degraded.set()
                            if not part.endswith(b"\n"):
                                continue
                            if dropping:
                                # Потерянный кадр мог содержать toolCall/terminal: replay запрещён.
                                raise ValueError("MSP line exceeds the limit")
                            count += 1
                            if count > MAX_EVENTS:
                                raise ValueError("MSP event count exceeds the limit")
                            line = pending.decode("utf-8", "strict")
                            _check_json_structure(line)
                            handle(json.loads(line))
                            pending.clear()
                            controller.record_activity("protocol")
                            if callable(ctx.on_activity):
                                ctx.on_activity("protocol")
                            if events.terminal is not None:
                                break
                except (
                    OSError,
                    ValueError,
                    RuntimeError,
                    RecursionError,
                    TypeError,
                    KeyError,
                ) as exc:
                    # Только наши причины/класс парсера, без stderr и RPC error payload.
                    error = f"MSP {type(exc).__name__}: {str(exc)[:160]}"
                    flags["protocol"] = True
                finally:
                    reader_done.set()

            send(
                "initialize",
                {"clientInfo": {"name": "cli_agent_bridge", "version": "1"}},
            )
            for target in (write_stdin, drain_stderr, read_stdout):
                thread = threading.Thread(target=target, daemon=True)
                thread.start()
                threads.append(thread)
            last_keepalive = time.monotonic()
            detached = False
            leader_exited_at: float | None = None
            while not reader_done.wait(0.05):
                now = time.monotonic()
                sink.check_timeout()
                if self._shutting_down:
                    flags["cancelled"] = True
                if ctx.cancel_event is not None and ctx.cancel_event.is_set():
                    flags["cancelled"] = True
                if not turn_id and now >= setup_deadline:
                    flags["protocol"] = True
                if proc.poll() is not None:
                    if leader_exited_at is None:
                        leader_exited_at = now
                    if now - leader_exited_at >= STDERR_DRAIN_GRACE_S:
                        flags["protocol"] = True
                stop, why, _ = controller.check(proc.pid)
                if stop and why in ("idle_timeout", "absolute_cap"):
                    flags["timeout"] = True
                gone = sink.client_write_dead.is_set() or (
                    callable(ctx.client_gone) and ctx.client_gone()
                )
                if (
                    not detached
                    and sink.inflight_at is None
                    and callable(ctx.keepalive)
                    and now - last_keepalive
                    >= min(10.0, self._setting("KEEPALIVE_S", 10.0))
                ):
                    last_keepalive = now
                    gone = not ctx.keepalive() or gone
                if gone:
                    sink.live_degraded.set()
                    if ctx.detach_on_disconnect:
                        if not detached and callable(ctx.on_activity):
                            ctx.on_activity("detached")
                        detached = True
                    else:
                        flags["client_gone"] = True
                if flags:
                    break
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            flags["protocol"] = True
        finally:
            controller.close()
            done.set()
            if sink is not None:
                sink.sink_closed.set()
            if proc is not None:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except OSError:
                    pass  # группа могла уже завершиться
                try:
                    proc.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    self._kill_group(proc)
                    try:
                        proc.wait(timeout=5.0)
                    except subprocess.TimeoutExpired:
                        flags["protocol"] = True
                if not self._wait_group_exit(proc.pid, 0.5):
                    self._kill_group(proc)
                group_gone = self._wait_group_exit(proc.pid, 2.0)
                for thread in threads:
                    thread.join(timeout=1.0)
                for stream in (proc.stdin, proc.stdout, proc.stderr):
                    if stream is not None:
                        stream.close()
                if group_gone:
                    self._unregister_child(proc.pid)
                else:
                    self._shutting_down = True
                    flags["protocol"] = True
                with self._lock:
                    self._active.pop(proc.pid, None)
            for fd in pipe_fds:
                os.close(fd)
            if sink is not None:
                sink.close()
            if turn_dir is not None:
                try:
                    shutil.rmtree(turn_dir)
                except FileNotFoundError:
                    pass  # процесс уже удалил собственный scratch
                except OSError:
                    self._shutting_down = True
                    flags["protocol"] = True
                    error = "MSP workspace cleanup failed"
        # stderr хранится только в bounded оперативном буфере; сырой вывод в лог не попадает.
        stderr_tail.clear()
        if flags.get("cancelled"):
            state, rc, error = "cancelled", 1, "turn cancelled by user"
        elif flags.get("client_gone"):
            state, rc = "client_gone", 1
        elif flags.get("timeout"):
            state, rc, error = "timeout", 124, "MSP turn timeout"
        elif flags.get("protocol") or events.terminal != "completed" or not turn_id:
            state, rc, error = (
                "backend_error",
                1,
                error or "MSP protocol or terminal failure",
            )
        else:
            state, rc = "done", 0
        fallback = bool(
            set(flags) == {"protocol"}
            and not action_possible
            and not events.has_executed_tool
            and group_gone
            and not self._shutting_down
        )
        return TurnResult(
            state=state,
            rc=rc,
            text=events.text,
            reasoning=events.reasoning,
            usage=Usage(estimate_tokens(ctx.prompt), estimate_tokens(events.text))
            if state == "done"
            else Usage(),
            err=error,
        ), fallback

    def _run_exec(self, ctx: TurnContext, prompt: str) -> TurnResult:
        model = ctx.model
        effort = ctx.effort
        if self._shutting_down:
            return self._result("launcher_unavailable", 1, err="adapter_shutting_down")
        turn_dir: "Path | None" = None
        try:
            turn_dir = self._make_turn_dir()
            prompt_path = turn_dir / "prompt.txt"
            fd = os.open(str(prompt_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(prompt)
        except OSError as exc:
            if turn_dir is not None:
                shutil.rmtree(str(turn_dir), ignore_errors=True)
            return self._result(
                "backend_error", -1, err=f"prompt file write failed: {exc}"
            )
        cmd = self.build_argv(model, effort, str(prompt_path))
        self._log(
            f"muse exec model={model} effort={effort} prompt_chars={len(prompt)} "
            f"{ctx.tag}".rstrip()
        )
        events = ExecEvents()
        err_lines: list = []
        flags: dict = {}
        done = threading.Event()
        proc = None
        threads: list[threading.Thread] = []
        state = "done"
        timeout_s = self._setting("TIMEOUT_S", 1800.0)
        cfg_idle = self.config.get("idle_timeout_s")
        cfg_cap = self.config.get("safety_cap_s")
        idle_s = (
            float(cfg_idle)
            if isinstance(cfg_idle, (int, float)) and not isinstance(cfg_idle, bool)
            else self._setting("IDLE_TIMEOUT_S", min(300.0, timeout_s))
        )
        idle_s = min(idle_s, timeout_s)
        safety_s = (
            float(cfg_cap)
            if isinstance(cfg_cap, (int, float)) and not isinstance(cfg_cap, bool)
            else self._setting("SAFETY_CAP_S", timeout_s)
        )
        if (
            timeout_s < 300.0
            and cfg_cap is None
            and not hasattr(self.host, "SAFETY_CAP_S")
        ):
            safety_s = timeout_s
        watchdog_enabled = os.environ.get(
            "BRIDGE_ADAPTIVE_WATCHDOG_ENABLED", "true"
        ).strip().lower() in ("1", "true", "yes", "on")
        timeout_ctrl = AdaptiveTimeoutController(
            idle_timeout_s=idle_s,
            safety_cap_s=safety_s,
            finish_reserve_s=0.0 if safety_s <= 60.0 else 35.0,
            watchdog_enabled=watchdog_enabled,
            turn_id=ctx.turn_id,
            log_fn=self._log,
        )
        pipe_fds: list[int] = []
        try:
            try:
                ready_r, ready_w = os.pipe()
                gate_r, gate_w = os.pipe()
                pipe_fds = [ready_r, ready_w, gate_r, gate_w]
                # Повторный допуск ПОСЛЕ слота, непосредственно перед spawn, без sha-кэша.
                ok, reason = self.preflight()
                if not ok:
                    return self._result("launcher_unavailable", 1, err=reason)
                proc = subprocess.Popen(
                    [sys.executable, "-c", _GROUP_BOOTSTRAP, str(ready_w), str(gate_r)]
                    + cmd,
                    cwd=str(turn_dir),
                    env=self.child_env(),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0,
                    pass_fds=(ready_w, gate_r),
                    start_new_session=True,
                )
            except OSError as exc:
                return self._result(
                    "launcher_unavailable", -1, err=f"spawn failed: {exc}"
                )
            with self._lock:
                self._active[proc.pid] = proc
            for fd in (ready_w, gate_r):
                os.close(fd)
                pipe_fds.remove(fd)
            if not select.select([ready_r], [], [], 5.0)[0]:
                raise OSError("group witness handshake timed out")
            member = int(os.read(ready_r, 32).strip())
            self._register_child(proc.pid, member)
            if callable(ctx.register_pgid):
                ctx.register_pgid(proc.pid)
            os.write(gate_w, b"1")
            for fd in (ready_r, gate_w):
                os.close(fd)
                pipe_fds.remove(fd)
            if self._shutting_down:  # shutdown успел пройти до регистрации ребёнка
                self._kill_group(proc)
            keepalive_s = min(10.0, self._setting("KEEPALIVE_S", 10.0))
            gone = ctx.client_gone
            keepalive = ctx.keepalive
            cancel_ev = ctx.cancel_event
            detach_ok = bool(ctx.detach_on_disconnect)
            stdout, stderr = proc.stdout, proc.stderr
            assert stdout is not None and stderr is not None
            child = proc
            os.set_blocking(stdout.fileno(), False)
            os.set_blocking(stderr.fileno(), False)
            leader_exited: list[float] = []

            def watch() -> None:
                last_ka = time.monotonic()
                seeded = False
                detached = False
                while not done.wait(0.25):
                    now = time.monotonic()
                    if not seeded:
                        seeded = True
                        timeout_ctrl.register_pgid(child.pid)
                    if cancel_ev is not None and cancel_ev.is_set():
                        flags["cancelled"] = True
                        self._kill_group(child)
                        return
                    if child.poll() is not None:
                        if not leader_exited:
                            leader_exited.append(now)
                        if now - leader_exited[0] >= STDERR_DRAIN_GRACE_S:
                            self._kill_group(child)
                            return
                    else:
                        should_stop, wd_reason, _ = timeout_ctrl.check(child.pid)
                        if should_stop and wd_reason in (
                            "idle_timeout",
                            "absolute_cap",
                        ):
                            flags["timeout"] = True
                        elif not detached and callable(gone) and gone():
                            if detach_ok:
                                detached = True
                                if callable(ctx.on_activity):
                                    ctx.on_activity("detached")
                            else:
                                flags["client_gone"] = True
                        elif (
                            not detached
                            and callable(keepalive)
                            and now - last_ka >= keepalive_s
                        ):
                            last_ka = now
                            if not keepalive():
                                if detach_ok:
                                    detached = True
                                    if callable(ctx.on_activity):
                                        ctx.on_activity("detached")
                                else:
                                    flags["client_gone"] = True
                    if flags:
                        self._kill_group(child)
                        return

            def drain_stderr() -> None:
                kept = bytearray()
                try:
                    while not done.is_set():
                        if not select.select([stderr], [], [], 0.1)[0]:
                            continue
                        try:
                            chunk = os.read(stderr.fileno(), 8192)
                        except BlockingIOError:
                            continue
                        if not chunk:
                            break
                        kept.extend(chunk)
                        while b"\n" in kept or len(kept) >= 8192:
                            split = kept.find(b"\n")
                            size = split + 1 if split >= 0 else 8192
                            line = bytes(kept[:size]).decode("utf-8", "strict").strip()
                            del kept[:size]
                            if line:
                                err_lines.append(line[:MAX_ERR_CHARS])
                                del err_lines[:-MAX_ERR_LINES]
                    if kept:
                        err_lines.append(
                            bytes(kept).decode("utf-8", "strict")[:MAX_ERR_CHARS]
                        )
                        del err_lines[:-MAX_ERR_LINES]
                except UnicodeDecodeError:
                    flags["pump_error"] = True
                    self._kill_group(child)
                except (OSError, ValueError):
                    if not done.is_set():
                        flags["pump_error"] = True
                        self._kill_group(child)

            err_thread = threading.Thread(target=drain_stderr, daemon=True)
            watch_thread = threading.Thread(target=watch, daemon=True)
            for thread in (err_thread, watch_thread):
                thread.start()
                threads.append(thread)
            pending = bytearray()
            eof = False
            while not eof:
                if (
                    leader_exited
                    and time.monotonic() - leader_exited[0] > STDERR_DRAIN_GRACE_S + 0.5
                ):
                    break  # сбежавший setsid-потомок не удерживает pipe/потоки/FD
                if not select.select([stdout], [], [], 0.1)[0]:
                    continue
                try:
                    chunk = os.read(
                        stdout.fileno(),
                        min(READ_CHUNK_BYTES, MAX_LINE_BYTES + 1 - len(pending)),
                    )
                except BlockingIOError:
                    continue
                eof = not chunk
                pending.extend(chunk)
                while b"\n" in pending or (eof and pending):
                    split = pending.find(b"\n")
                    size = split + 1 if split >= 0 else len(pending)
                    if size > MAX_LINE_BYTES:
                        raise ValueError("jsonl line exceeds the limit")
                    line = bytes(pending[:size]).decode("utf-8", "strict")
                    del pending[:size]
                    events.feed_line(line)
                    timeout_ctrl.record_activity("protocol")
                    if callable(ctx.on_activity):
                        ctx.on_activity("protocol")
                    if events.text_bytes > MAX_TURN_TEXT_BYTES:
                        raise ValueError("turn text exceeds the limit")
                if len(pending) > MAX_LINE_BYTES:
                    raise ValueError("jsonl line exceeds the limit")
            # EOF одного pipe не даёт бесконечно ждать работающего лидера.
            try:
                child.wait(timeout=STDERR_DRAIN_GRACE_S)
            except subprocess.TimeoutExpired:
                if events.terminal != "completed":
                    flags.setdefault("timeout", True)
            drain_deadline = time.monotonic() + STDERR_DRAIN_GRACE_S
            while err_thread.is_alive() and time.monotonic() < drain_deadline:
                err_thread.join(timeout=0.1)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            state = "pump_error"
            err_lines.append(
                f"muse pump failed: {type(exc).__name__}: {str(exc)[:MAX_ERR_CHARS]}"
            )
        finally:
            timeout_ctrl.close()
            if proc is not None:
                # Владение начинается сразу после Popen: даже отказ первого Thread.start
                # не может обойти kill/wait. Реестр и слот освобождаются ПОСЛЕ группы.
                self._kill_group(proc)
                try:
                    proc.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    state = "pump_error"
                group_gone = self._wait_group_exit(proc.pid, 2.0)
                done.set()
                for thread in threads:
                    thread.join(timeout=1.0)
                for stream in (proc.stdout, proc.stderr):
                    if stream is not None:
                        stream.close()
                if group_gone:
                    self._unregister_child(proc.pid)
                with self._lock:
                    self._active.pop(proc.pid, None)
                if not group_gone:
                    self._shutting_down = (
                        True  # не допустить следующий ход при живом наследии
                    )
                    state = "pump_error"
            for fd in pipe_fds:
                os.close(fd)
            if turn_dir is not None:
                shutil.rmtree(str(turn_dir), ignore_errors=True)
        rc = proc.returncode if proc.returncode is not None else -1
        err = "\n".join(events.errors + err_lines)[-1000:]
        if events.reason:
            err = (err + f"\nreason: {events.reason}").strip()
        if flags.get("cancelled"):
            return self._result("cancelled", 1, err="turn cancelled by user")
        if flags.get("client_gone"):
            return self._result("client_gone", 1)
        if flags.get("timeout"):
            return self._result(
                "timeout", 124, err=f"proxy timeout after {timeout_s:g}s"
            )
        if flags.get("pump_error"):
            state = "pump_error"
        if state != "done":
            return self._result(state, 1, err=err)
        if rc == PROXY_DOWN_RC:
            return self._result("launcher_unavailable", rc, err=err or "proxy_down")
        if events.terminal != "completed":
            # Успех требует подтверждённого terminal.completed (RW-004): delta + EOF + rc=0
            # без terminal — незавершённый протокол, а не готовый ответ.
            terminal = events.terminal or "missing"
            return self._result(
                "backend_error", 1, err=f"terminal_{terminal}: {err}".strip()
            )
        if rc != 0:
            return self._result("backend_error", rc, err=err)
        return self._result("done", 0, text=events.text, err=err, prompt=prompt)

    def shutdown(self) -> None:
        """Убить группы процессов собственных детей (только свои PID из реестра адаптера)."""
        self._shutting_down = True
        with self._lock:
            procs = list(self._active.values())
        for proc in procs:
            self._kill_group(proc)
