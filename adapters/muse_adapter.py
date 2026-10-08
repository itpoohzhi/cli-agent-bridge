"""Адаптер Meta Muse Code CLI (`muse exec`) для мульти-бинарного хаба (ADR 0002).

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
import re
import shutil
import signal
import socket
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping

from core.backend_adapter import (
    SESSIONS_NONE,
    STREAMING_EMULATED,
    BackendAdapter,
    BackendNotSupported,
)

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
TURN_DIR_PREFIX = "turn-"
_TOKEN_SPLIT = re.compile(r"\s+")


def estimate_tokens(text: str) -> int:
    """Оценка токенов по словам (×1.3), как в muse-bridge: exec точных токенов не отдаёт."""
    if not text:
        return 0
    return max(1, int(len(_TOKEN_SPLIT.split(text.strip())) * 1.3))


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

    def _charge(self, text: str) -> None:
        """Текст учитывается в байтовом бюджете хода (включая причины ошибок)."""
        self.text_bytes += len(text.encode("utf-8", "replace"))

    def feed_line(self, raw: str) -> None:
        raw = raw.strip()
        if not raw:
            return
        try:
            event = json.loads(raw)
        except ValueError:
            return
        if not isinstance(event, dict):
            return
        ptype = str(event.get("payload_type") or "")
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if ptype == "run.output.delta":
            text = payload.get("text")
            if isinstance(text, str):
                self._charge(text)
                self.deltas.append(text)
        elif ptype.startswith("run.terminal"):
            self.terminal = str(payload.get("terminal") or ptype.rsplit(".", 1)[-1])
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


class MuseAdapter(BackendAdapter):
    kind = "muse"
    capabilities = {
        "sessions": SESSIONS_NONE,
        "streaming": STREAMING_EMULATED,  # готовый текст режет фасад SSE-срезами
        "autonomy": False,  # поле запроса принимается и игнорируется
        "usage": "estimated",
    }

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
        self._slots = threading.BoundedSemaphore(self.max_concurrent)
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
    def get_models(self) -> list:
        return self._catalog_models()

    def _file_sha256(self, path: str) -> str:
        try:
            st = os.stat(path)
        except OSError:
            return ""
        cached = self._sha_cache.get(path)
        if cached and cached[0] == st.st_mtime_ns and cached[1] == st.st_size:
            return str(cached[2])
        try:
            with open(path, "rb") as handle:
                digest = hashlib.sha256(handle.read()).hexdigest()
        except OSError:
            return ""
        self._sha_cache[path] = (st.st_mtime_ns, st.st_size, digest)
        return digest

    def qualify(self) -> tuple:
        """Допуск: обёртка исполняема; образ Muse совпал с обязательным pin `technical_ref`.

        Без комплектного pin квалифицировать нечего (AD-007), и ход не запускается: иначе
        обёртка исполнила бы произвольный файл (в т.ч. подсунутый через `MUSE_BIN`) без
        проверки. Обёртка при этом сама выбирает канонический `~/.local/bin/muse` — ровно
        тот путь, который сверяет pin (RW-002).
        """
        if not (os.path.isfile(self.wrapper) and os.access(self.wrapper, os.X_OK)):
            return (False, "wrapper_not_executable")
        ref = self.config.get("technical_ref")
        if not isinstance(ref, dict):
            return (False, "pin_missing")
        binary = os.path.expanduser(str(ref.get("binary_path") or ""))
        pinned = str(ref.get("binary_sha256") or "")
        if not binary or not pinned:
            return (False, "pin_missing")
        actual = self._file_sha256(binary)
        if not actual:
            return (False, "binary_missing")
        if actual != pinned:
            return (False, "binary_sha256_mismatch")
        return (True, "ok")

    def _normalize_proxy_port(self) -> int:
        """proxy_port бэкенда (иначе env, иначе default) -> int; мусор -> default."""
        raw = self.config.get("proxy_port") or os.environ.get("MUSE_PROXY_PORT")
        try:
            return int(raw) if raw else DEFAULT_PROXY_PORT
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

    def preflight(self) -> tuple:
        ok, reason = self.qualify()
        if not ok:
            return (False, reason)
        if not self._proxy_up():
            return (False, "proxy_down")
        return (True, "")

    def active_count(self) -> int:
        with self._lock:
            return len(self._active)

    # -- сессии (нет) ---------------------------------------------------------------------
    def spawn_session(self, ctx: dict) -> Any:
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

    def _register_child(self, pid: int) -> None:
        sig_fn = getattr(self.host, "_proc_start_sig", None)
        start = str(sig_fn(pid) or "") if callable(sig_fn) else ""
        self._registry_update(
            add={
                "pid": pid,
                "pgid": pid,
                "start": start,
                "bridge_pid": os.getpid(),
                "kind": self.kind,
            }
        )

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
    ) -> dict:
        usage = {}
        if state == "done":
            usage = {
                "input_tokens": estimate_tokens(prompt),
                "output_tokens": estimate_tokens(text),
            }
        return {
            "state": state,
            "rc": rc,
            "text": text,
            "reasoning": "",
            "usage": usage,
            "result": {},
            "err": err,
        }

    def _acquire_slot(self, ctx: dict) -> str:
        """Ждать ёмкость бэкенда (≤ QUEUE_TIMEOUT_S): '' — взят, иначе причина отказа."""
        queue_s = self._setting("QUEUE_TIMEOUT_S", 900.0)
        keepalive_s = self._setting("KEEPALIVE_S", 15.0)
        gone = ctx.get("client_gone")
        keepalive = ctx.get("keepalive")
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

    def execute_turn(self, ctx: dict, sse_writer: Any) -> dict:
        """Один ход; автоматического replay промпта нет (RW-003): после старта процесса
        нативные shell/write/web-инструменты могли исполниться, повтор небезопасен даже при
        network-marker, поэтому ненулевой exit — сразу backend_error.
        """
        prompt = str(ctx["prompt"])
        ok, reason = self.preflight()
        if not ok:
            return self._result("launcher_unavailable", 1, err=reason)
        waited = self._acquire_slot(ctx)
        if waited:
            return self._result(waited, 1)
        try:
            return self._run_exec(ctx, prompt)
        finally:
            self._slots.release()

    def _run_exec(self, ctx: dict, prompt: str) -> dict:
        model = str(ctx["model"])
        effort = str(ctx["effort"])
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
            f"{ctx.get('tag', '')}".rstrip()
        )
        events = ExecEvents()
        err_lines: list = []
        flags: dict = {}
        done = threading.Event()
        proc = None
        try:
            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(turn_dir),
                    env=self.child_env(),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    start_new_session=True,
                )
            except OSError as exc:
                return self._result(
                    "launcher_unavailable", -1, err=f"spawn failed: {exc}"
                )
            with self._lock:
                self._active[proc.pid] = proc
            self._register_child(proc.pid)
            if self._shutting_down:  # shutdown успел пройти до регистрации ребёнка
                self._kill_group(proc)
            timeout_s = self._setting("TIMEOUT_S", 1800.0)
            keepalive_s = self._setting("KEEPALIVE_S", 15.0)
            gone = ctx.get("client_gone")
            keepalive = ctx.get("keepalive")

            def watch() -> None:
                deadline = time.monotonic() + timeout_s
                last_ka = time.monotonic()
                while not done.wait(0.25):
                    now = time.monotonic()
                    if now > deadline:
                        flags["timeout"] = True
                    elif callable(gone) and gone():
                        flags["client_gone"] = True
                    elif callable(keepalive) and now - last_ka >= keepalive_s:
                        last_ka = now
                        if not keepalive():
                            flags["client_gone"] = True
                    if flags:
                        self._kill_group(proc)
                        return

            def drain_stderr() -> None:
                try:
                    for line in iter(lambda: proc.stderr.readline(8192), ""):
                        line = line.strip()
                        if line:
                            err_lines.append(line[:MAX_ERR_CHARS])
                            del err_lines[:-MAX_ERR_LINES]
                except (OSError, ValueError):
                    pass

            err_thread = threading.Thread(target=drain_stderr, daemon=True)
            watch_thread = threading.Thread(target=watch, daemon=True)
            err_thread.start()
            watch_thread.start()
            state = "done"
            try:
                while True:
                    line = proc.stdout.readline(MAX_LINE_BYTES + 1)
                    if not line:
                        break
                    if len(line) > MAX_LINE_BYTES:
                        state = "pump_error"
                        err_lines.append("jsonl line exceeds the limit")
                        self._kill_group(proc)
                        break
                    events.feed_line(line)
                    if events.text_bytes > MAX_TURN_TEXT_BYTES:
                        state = "pump_error"
                        err_lines.append("turn text exceeds the limit")
                        self._kill_group(proc)
                        break
            except (OSError, ValueError) as exc:
                state = "pump_error"
                err_lines.append(f"stdout read failed: {exc}")
            finally:
                # Ограниченное завершение группы (RW-009): EOF stdout НЕ выключает сторож —
                # `done` взводится только после гашения группы; слот и _active освобождаются
                # после killpg, а не после EOF одного pipe.
                try:
                    proc.wait(timeout=STDERR_DRAIN_GRACE_S)
                except subprocess.TimeoutExpired:
                    if events.terminal != "completed":
                        flags.setdefault("timeout", True)
                    self._kill_group(proc)
                    try:
                        proc.wait(timeout=5.0)
                    except subprocess.TimeoutExpired:
                        pass
                drain_deadline = time.monotonic() + STDERR_DRAIN_GRACE_S
                while err_thread.is_alive() and time.monotonic() < drain_deadline:
                    err_thread.join(timeout=0.1)
                self._kill_group(
                    proc
                )  # потомки лидера (в т.ч. с закрытыми pipe) — до слота
                self._wait_group_exit(proc.pid, 2.0)
                err_thread.join(timeout=1.0)
                done.set()
                if not err_thread.is_alive():
                    # Закрываем трубы только когда добор завершён: close при заблокированном
                    # readline мог бы ждать блокировку потока (RW-009).
                    for stream in (proc.stdout, proc.stderr):
                        try:
                            stream.close()
                        except (OSError, ValueError):
                            pass
                watch_thread.join(timeout=5.0)
        finally:
            if proc is not None:
                self._unregister_child(proc.pid)
                with self._lock:
                    self._active.pop(proc.pid, None)
            if turn_dir is not None:
                shutil.rmtree(str(turn_dir), ignore_errors=True)
        rc = proc.returncode if proc.returncode is not None else -1
        err = "\n".join(events.errors + err_lines)[-1000:]
        if events.reason:
            err = (err + f"\nreason: {events.reason}").strip()
        if flags.get("client_gone"):
            return self._result("client_gone", 1)
        if flags.get("timeout"):
            return self._result(
                "timeout", 124, err=f"proxy timeout after {timeout_s:g}s"
            )
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
