#!/usr/bin/env python3
"""muse-bridge — локальный OpenAI-совместимый мост поверх Muse Code CLI (Meta).

Один запрос `/v1/chat/completions` = один headless-ход
`~/.config/muse-launch/muse-cli.sh exec --provider meta --model muse-spark-1.3
 --reasoning-effort <TIER> --yolo --trust-workspace --workspace <WS> --json --prompt-file <f>`.

Вызов ТОЛЬКО через обёртку muse-cli.sh (прокси :10816, вычистка META_API_KEY,
exit 42 при DOWN прокси) — канон model-invocation.md §2d. Голый `muse` не используется.

Stdout CLI — JSONL-конверты (schema_version=1). Текст ответа — из
`run.terminal.completed` (payload.text); fallback — конкатенация `run.output.delta`
(payload.text). Ошибки — `run.terminal.*` с terminal != completed либо
`task.lifecycle.failed` (event.reason). Usage CLI в JSONL не отдаёт — оценка по словам.

Транспорт — stdlib. `stream:true`: заголовки 200 и role-delta уходят сразу, пока ход
идёт — комментарии `: keepalive` (MUSE_BRIDGE_KEEPALIVE_S); по готовности — reasoning
summaries как `delta.reasoning_content`, tool_calls, content-чанки (~300 символов), финал
с finish_reason + usage, затем `data: [DONE]`. Ошибка после старта потока — кадр
`{"error": …}` + `[DONE]`. Текст ответа CLI отдаёт в конце хода, поэтому content
по-прежнему приходит в конце. `stream:false` — обычный JSON.

Провал хода (failed terminal, rc != 0, таймаут) не отдаётся как успешный финал: частичный
текст и tool-блоки отбрасываются — SSE-кадр ошибки + `[DONE]` (stream) либо 502 (JSON).

Keepalive: комментарии `: keepalive` держат TCP-соединение от закрытия клиентом/прокси, но
SDK отбрасывает их на уровне декодера и idle-watchdog не сбрасывают. Поэтому после применения
профиля muse (`streamIdleTimeoutMs=1900000`) DSH нужно перезапустить; сброс watchdog кадрами
данных (полный стрим текста muse) в этот мост не входит.

Эмуляция OpenAI function calling (порт из droid-bridge): если запрос содержит
непустой `tools` (и tool_choice != "none"), в системный текст добавляется протокол
`<tool_call>{"name":…,"arguments":{…}}</tool_call>` и схемы инструментов; блоки в
ответе модели разбираются ToolCallParser в `message.tool_calls` +
`finish_reason:"tool_calls"`; история assistant.tool_calls / role:"tool"
рендерится обратно в те же блоки. Без `tools` мост чисто текстовый.
"""

from __future__ import annotations

import json
import os
import random
import re
import select
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HOST = os.environ.get("MUSE_BRIDGE_HOST", "127.0.0.1").strip() or "127.0.0.1"
PORT = int(os.environ.get("MUSE_BRIDGE_PORT", "9886"))
AUTH_KEY = os.environ.get("MUSE_BRIDGE_KEY", "").strip()

TIMEOUT_S = float(os.environ.get("MUSE_BRIDGE_TIMEOUT_S", "1800"))
MAX_CONCURRENT = int(os.environ.get("MUSE_BRIDGE_MAX_CONCURRENT", "2"))

MUSE_WRAPPER = os.environ.get(
    "MUSE_BRIDGE_CLI", str(Path.home() / ".config" / "muse-launch" / "muse-cli.sh")
)
ROOT = Path(__file__).resolve().parent
WORKSPACE = Path(os.environ.get("MUSE_BRIDGE_WORKSPACE", str(ROOT / "workspace")))
LOG_PATH = Path(os.environ.get("MUSE_BRIDGE_LOG", str(ROOT / "logs" / "bridge.log")))

ALLOWED_MODELS: dict[str, dict[str, Any]] = {
    "muse-spark-1.3": {"context_length": 1048576, "max_output": 131072},
    # 2026-10-05: контрибьютор-слот (только пикер, по просьбе владельца).
    # id подтверждён `muse model-profile show` (резолвится); окно/лимит как у spark.
    "muse-spark-1.3-contributor": {"context_length": 1048576, "max_output": 131072},
}
DEFAULT_MODEL = os.environ.get("MUSE_BRIDGE_MODEL", "muse-spark-1.3")

# OpenAI/DSH effort -> `--reasoning-effort` Muse CLI. Нет/неизвестно -> max (канон слота).
EFFORT_MAP: dict[str, str] = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "xhigh": "xhigh",
    "max": "max",
    # 2026-10-08: "none" запрещён meta-провайдером (muse exec RC=2:
    # "--reasoning-effort none is not supported with --provider meta"),
    # мост отдавал 502. "Без рассуждений" -> ближайший живой тир minimal.
    "off": "minimal",
    "none": "minimal",
    "minimal": "minimal",
    "ultra": "xhigh",  # runtime-гейт ultra откатывается в xhigh
}
DEFAULT_EFFORT = "max"

# Однократный ретрай exec — ТОЛЬКО на этот маркер (exec идемпотентен).
# Остальные ошибки (rc=42 прокси DOWN, timeout, terminal_*) не ретраятся.
NETWORK_RETRY_MARKER = "network connection could not be opened"

# Bridge-тир -> MSP ReasoningEffort (closed-вокабуляр SS3.2). _map_effort уже
# нормализовал запрос; ultra откатан в xhigh там же (EFFORT_MAP).
# 2026-10-08: +minimal (низший живой тир meta -> низший известный MSP-тир low);
# "none" оставлен оборонительно (сюда больше не приходит, но MSP-вокабуляр под вопросом).
_MSP_EFFORT = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "xhigh": "xhigh",
    "max": "max",
    "minimal": "low",
    "none": "low",
}

# Грейс выхода CLI после terminal completed: вышел сам -> его rc настоящий; завис -> добивает мост.
# Грейс вне бюджета хода (таймер TIMEOUT_S отменяется по completed), но ограничен.
QUARANTINE_MAX_S = 600.0  # потолок карантина слота: группа не подтверждена мёртвой
_SIGNAL_RCS = (
    -signal.SIGKILL,
    -signal.SIGTERM,
)  # rc процесса, убитого мостом при уборке
TERMINAL_EXIT_GRACE_S = 0.5
SERVE_SPAWN_TIMEOUT_S = 30.0  # handshake+session/start должны уложиться сюда


class ServeUnavailable(Exception):
    """Транспорт serve недоступен -> тихий fallback на exec. Не ошибка запроса."""


def _uuid7() -> str:
    ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF
    rand = random.getrandbits(74)
    value = (ms << 74) | rand
    hx = f"{value:032x}"
    hx = hx[:12] + "7" + hx[13:16] + f"{8 | (int(hx[16], 16) & 3):x}" + hx[17:]
    return f"{hx[:8]}-{hx[8:12]}-{hx[12:16]}-{hx[16:20]}-{hx[20:]}"


TOOL_CALL_OPEN = "<tool_call>"
TOOL_CALL_CLOSE = "</tool_call>"

DEFAULT_SYSTEM_HINT = (
    "Ты отвечаешь в текстовом чате. Не вызывай инструменты и не выполняй команды; "
    "верни только текстовый ответ."
)

_started = time.time()
_active: dict[str, float] = {}
_active_lock = threading.Lock()
_slots = threading.Semaphore(MAX_CONCURRENT)
_LOG_LOCK = threading.Lock()


def _log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    sys.stderr.write(line + "\n")
    sys.stderr.flush()
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_LOCK, LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def _auth_ok(handler: BaseHTTPRequestHandler) -> bool:
    hdr = handler.headers.get("Authorization", "")
    if hdr.startswith("Bearer "):
        return hdr[7:].strip() == AUTH_KEY
    return handler.headers.get("x-api-key", "") == AUTH_KEY or hdr.strip() == AUTH_KEY


def _flatten_content(content: Any) -> str:
    """OpenAI content (str | list[part]) -> plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if "text" in item:
                    parts.append(str(item["text"]))
                elif item.get("type") == "image_url":
                    parts.append("[image omitted]")
        return "\n".join(p for p in parts if p)
    return str(content)


def _normalize_arguments(value: Any) -> dict | None:
    """arguments -> JSON-объект; None, если значение задано, но объектом не является.

    None отличает невалидные аргументы (строку-не-JSON, список, число, null) от
    отсутствия ключа: вызывающий код не вправе молча подменять их на пустой словарь
    и запускать инструмент с пустыми аргументами.
    """
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text:
            try:
                parsed = json.loads(text)
            except ValueError:
                return None
            if isinstance(parsed, dict):
                return parsed
    return None


def _normalize_tool_call(item: Any) -> dict:
    """Один OpenAI tool_call -> {"id", "name", "arguments"}.

    id сохраняется, чтобы результат [tool result <id>] однозначно сопоставлялся
    с конкретным вызовом при нескольких одинаковых инструментах.
    """
    if not isinstance(item, dict):
        return {"id": "", "name": "", "arguments": {}}
    fn = item.get("function") if isinstance(item.get("function"), dict) else {}
    name = fn.get("name") or item.get("name") or ""
    args = fn.get("arguments")
    if args is None:
        args = item.get("arguments")
    normalized = _normalize_arguments(args)
    return {
        "id": str(item.get("id") or ""),
        "name": str(name),
        "arguments": normalized if normalized is not None else {},
    }


def _render_tool_call(item: Any) -> str:
    """Историю вызова рендерим тем же блоком, что просим от модели."""
    payload = json.dumps(_normalize_tool_call(item), ensure_ascii=False)
    return f"{TOOL_CALL_OPEN}{payload}{TOOL_CALL_CLOSE}"


def _tool_choice_none(tool_choice: Any) -> bool:
    """tool_choice:"none" — инструменты не предлагаем вовсе."""
    return isinstance(tool_choice, str) and tool_choice.strip().lower() == "none"


def _tool_choice_name(tool_choice: Any) -> str:
    """Имя обязательного инструмента из tool_choice ("" — без принуждения)."""
    if not isinstance(tool_choice, dict):
        return ""
    fn = (
        tool_choice.get("function")
        if isinstance(tool_choice.get("function"), dict)
        else {}
    )
    name = fn.get("name") or tool_choice.get("name") or ""
    return str(name) if name else ""


def _tools_section(tools: list, tool_choice: Any) -> str:
    """Английская секция протокола и схем инструментов для промпта."""
    lines = [
        "[system]",
        "# Tool calling protocol",
        "You may call the external tools listed below.",
        "When you need a tool, output ONLY blocks exactly in this form:",
        f'{TOOL_CALL_OPEN}{{"name": "<tool_name>", "arguments": {{<json>}}}}{TOOL_CALL_CLOSE}',
        "You may output several such blocks in a row. Do not narrate around them.",
        "Tool results arrive later as lines like [tool result <id>] with the result text.",
        "If no tool is needed, reply normally in plain text.",
        "Never attempt to use built-in tools; the only tools available are the ones listed here.",
        "Do not run shell commands or edit files yourself: emit a tool_call block instead.",
    ]
    if tool_choice == "required":
        lines.append("You MUST call at least one tool now.")
    else:
        forced = _tool_choice_name(tool_choice)
        if forced:
            lines.append(f'You MUST call the tool "{forced}" now.')
    lines.append("")
    lines.append("Available tools:")
    for item in tools:
        fn = item.get("function") if isinstance(item.get("function"), dict) else item
        if not isinstance(fn, dict):
            continue
        name = str(fn.get("name") or "")
        desc = str(fn.get("description") or "")
        params = fn.get("parameters") if isinstance(fn.get("parameters"), dict) else {}
        lines.append(f"- {name}: {desc}")
        lines.append("  parameters: " + json.dumps(params, ensure_ascii=False))
    return "\n".join(lines)


def _render_turn(msg: dict[str, Any]) -> tuple[str, str]:
    """Одна реплика истории -> (role, текст); пустой текст = пропустить.

    assistant.tool_calls и role:"tool" рендерятся в те же блоки, что протокол.
    """
    role = str(msg.get("role") or "user").strip().lower()
    text = _flatten_content(msg.get("content"))
    if role == "tool":
        call_id = str(msg.get("tool_call_id") or msg.get("id") or "")
        name = str(msg.get("name") or "")
        header = f"[tool result {call_id}]"
        if name:
            header += f" ({name})"
        return role, f"{header}\n{text}" if text.strip() else header
    if role == "assistant":
        parts = [text] if text.strip() else []
        calls = msg.get("tool_calls")
        if isinstance(calls, list):
            parts.extend(_render_tool_call(tc) for tc in calls)
        return role, "\n".join(parts)
    return role, text


def _messages_to_prompt(messages: list[dict[str, Any]]) -> tuple[str, str]:
    """История OpenAI -> (system_text, размеченный текст реплик)."""
    systems: list[str] = []
    turns: list[str] = []
    for msg in messages or []:
        if not isinstance(msg, dict):
            continue
        role, text = _render_turn(msg)
        if not text.strip():
            continue
        if role in ("system", "developer"):
            systems.append(text)
        elif role == "assistant":
            turns.append(f"Assistant: {text}")
        elif role == "tool":
            turns.append(text)
        else:
            turns.append(f"User: {text}")
    return "\n\n".join(systems).strip(), "\n\n".join(turns)


def _strip_code_fence(text: str) -> str:
    """Снять обёртку ```…``` (в т.ч. ```json) вокруг JSON внутри блока."""
    body = text.strip()
    if body.startswith("```"):
        newline = body.find("\n")
        body = body[newline + 1 :] if newline != -1 else body[3:]
    if body.rstrip().endswith("```"):
        body = body.rstrip()[:-3]
    return body.strip()


def _parse_tool_call_block(inner: str) -> dict | None:
    """Содержимое блока -> {"name","arguments"}; None, если блок невалиден.

    Отсутствие ключа arguments — допустимый вызов с {}; присутствующее, но
    не-объектное значение (строка-не-JSON, список, число, null) — вызов
    отклоняем, чтобы не запускать инструмент с пустыми аргументами.
    """
    try:
        obj = json.loads(_strip_code_fence(inner))
    except ValueError:
        return None
    if not isinstance(obj, dict):
        return None
    name = obj.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    if "arguments" not in obj:
        arguments: dict = {}
    else:
        arguments = _normalize_arguments(obj.get("arguments"))
        if arguments is None:
            return None
    return {"name": name.strip(), "arguments": arguments}


class ToolCallParser:
    """Поток текстовых дельт -> content и завершённые вызовы инструментов.

    Тег <tool_call> может прийти разорванным между дельтами: хвост, который может
    оказаться началом тега, удерживается и не уходит в content до разрешения.
    """

    def __init__(self, on_content, on_tool_call):
        self._buf = ""
        self._on_content = on_content
        self._on_tool_call = on_tool_call

    def feed(self, text: str) -> None:
        self._buf += text
        self._drain(final=False)

    def finish(self) -> None:
        self._drain(final=True)

    def _drain(self, final: bool) -> None:
        while True:
            start = self._buf.find(TOOL_CALL_OPEN)
            if start == -1:
                if final:
                    self._flush_all()
                    return
                keep = self._pending_prefix()
                if keep:
                    self._emit(self._buf[:-keep])
                    self._buf = self._buf[-keep:]
                else:
                    self._flush_all()
                return
            if start > 0:
                self._emit(self._buf[:start])
                self._buf = self._buf[start:]
            end = self._find_close_outside_string(len(TOOL_CALL_OPEN))
            if end == -1:
                if final:
                    self._flush_all()  # незакрытый/невалидный блок отдаём текстом
                return
            inner = self._buf[len(TOOL_CALL_OPEN) : end]
            self._buf = self._buf[end + len(TOOL_CALL_CLOSE) :]
            call = _parse_tool_call_block(inner)
            if call is None:
                self._emit(TOOL_CALL_OPEN + inner + TOOL_CALL_CLOSE)
            else:
                self._on_tool_call(call)

    def _find_close_outside_string(self, start: int) -> int:
        """Позиция `</tool_call>` вне строковых литералов JSON, или -1.

        Закрывающий тег внутри JSON-строки (например, значение аргумента содержит
        `</tool_call>`) границей блока не является. Экранированные кавычки `\\"`
        строку не закрывают.
        """
        index = start
        length = len(self._buf)
        in_string = False
        escaped = False
        while index < length:
            char = self._buf[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
            elif char == '"':
                in_string = True
            elif self._buf.startswith(TOOL_CALL_CLOSE, index):
                return index
            index += 1
        return -1

    def _pending_prefix(self) -> int:
        """Длина хвоста — префикса открывающего тега (его нельзя отдать в content)."""
        limit = min(len(TOOL_CALL_OPEN) - 1, len(self._buf))
        for length in range(limit, 0, -1):
            if self._buf[-length:] == TOOL_CALL_OPEN[:length]:
                return length
        return 0

    def _emit(self, text: str) -> None:
        if text:
            self._on_content(text)

    def _flush_all(self) -> None:
        if self._buf:
            text, self._buf = self._buf, ""
            self._on_content(text)


def _split_tool_calls(chunks: list[str]) -> tuple[str, list[dict]]:
    """Дельты текста ответа -> (content, tool_calls в формате OpenAI).

    Тот же ToolCallParser, что у droid-bridge; id вызовов — call_<hex24>.
    """
    pieces: list[str] = []
    calls: list[dict] = []

    def add_call(call: dict) -> None:
        calls.append(
            {
                "index": len(calls),
                "id": "call_" + uuid.uuid4().hex[:24],
                "type": "function",
                "function": {
                    "name": call["name"],
                    "arguments": json.dumps(call["arguments"], ensure_ascii=False),
                },
            }
        )

    parser = ToolCallParser(pieces.append, add_call)
    for chunk in chunks:
        parser.feed(chunk)
    parser.finish()
    return "".join(pieces), calls


def _map_effort(req: dict[str, Any]) -> str:
    """reasoning_effort (chat) | reasoning.effort (responses-стиль) -> тир Muse."""
    raw: Any = req.get("reasoning_effort")
    if raw is None and isinstance(req.get("reasoning"), dict):
        raw = req["reasoning"].get("effort")
    key = str(raw).strip().lower() if raw is not None else ""
    return EFFORT_MAP.get(key, DEFAULT_EFFORT)


_TOKEN_RE = re.compile(r"\s+")


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, int(len(_TOKEN_RE.split(text.strip())) * 1.3))


# Эмуляция SSE (OpenAI chat.completion.chunk): результат генерации уже целиком —
# «стрим» = нарезка готового текста на чанки с минимальной задержкой между ними.
SSE_CHUNK_SIZE = int(os.environ.get("MUSE_BRIDGE_SSE_CHUNK_SIZE", "300"))
SSE_CHUNK_DELAY_S = float(os.environ.get("MUSE_BRIDGE_SSE_CHUNK_DELAY_S", "0.005"))
# stream=true: заголовки и role-кадр уходят сразу, пока ход идёт — комментарии keepalive.
# Без них клиент (OpenAI SDK в DeepSeek Harness) ждал заголовков до своего таймаута
# (~600 с) и рвал долгий ход как "Request timed out".
KEEPALIVE_S = float(os.environ.get("MUSE_BRIDGE_KEEPALIVE_S", "15"))


def _split_sse_chunks(text: str, size: int = 0) -> list[str]:
    """Готовый текст -> куски для SSE-дельт (по символам, юникод-сейф)."""
    size = size or SSE_CHUNK_SIZE
    size = max(1, size)
    return [text[i : i + size] for i in range(0, len(text), size)] if text else []


def _kill_group(proc: subprocess.Popen) -> None:
    """Убить всю группу процессов хода: ребёнок — лидер группы (start_new_session).

    Фолбэк proc.kill() — если killpg недоступен/запрещён (эталон
    adapters/muse_adapter.py, RW-009).
    """
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except OSError:
            pass


def _group_alive(pgid: int) -> bool:
    """Жива ли группа pgid (killpg сигналом 0 ничего не убивает)."""
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def _wait_group_exit(pgid: int, timeout: float, leader_reaped: bool = False) -> bool:
    """Короткое ожидание ухода группы после SIGKILL (обычно мгновенно).

    Пока группа жива, SIGKILL повторяется: потомок, форкнувшийся в момент первого killpg,
    остаётся в группе и иначе держал бы pipe (close() вешался бы на чтении stderr).
    Лидер реапнут (leader_reaped) — его pid свободен для переиспользования, поэтому после
    одного контрольного killpg по ещё живым потомкам сигналы прекращаются, остаётся опрос.
    """
    deadline = time.monotonic() + timeout
    control_sent = False
    while _group_alive(pgid) and time.monotonic() < deadline:
        if not (leader_reaped and control_sent):
            try:
                os.killpg(pgid, signal.SIGKILL)
            except OSError:
                pass
            control_sent = True
        time.sleep(0.05)
    return not _group_alive(pgid)


def _terminate_run(run: Any, streams: tuple) -> None:
    """Убить группу хода и подтвердить её смерть; результат — run.dead_confirmed.

    TimeoutExpired при ожидании после SIGKILL не считается смертью: SIGKILL группы повторяется
    (в _wait_group_exit тоже), смерть группы проверяется по факту. Не подтверждена — трубы не
    закрываются (close() ждал бы читателя), слот хендлера уйдёт в карантин.
    """
    proc = run.proc
    if proc is None or run._closed:
        return
    run._closed = True
    _kill_group(proc)
    try:
        proc.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        _log(f"cleanup: wait after SIGKILL timed out pid={proc.pid}, escalating")
        _kill_group(proc)
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            pass
    run.dead_confirmed = _wait_group_exit(
        proc.pid, 2.0, leader_reaped=proc.poll() is not None
    )
    if not run.dead_confirmed:
        _log(f"cleanup: process group {proc.pid} not confirmed dead after SIGKILL")
        return
    for stream in streams:
        try:
            if stream is not None:
                stream.close()
        except OSError:
            pass


def _quarantine_slot(runs: list) -> None:
    """Слот держится, пока группы ходов не подтверждены мёртвыми (карантин), затем возвращается."""
    pgids = [r.proc.pid for r in runs if r.proc is not None]
    _log(f"quarantine: slot held, groups not confirmed dead pgids={pgids}")

    def work() -> None:
        end = time.monotonic() + QUARANTINE_MAX_S
        escalated = False
        while True:
            alive = [r for r in runs if r.proc is not None and _group_alive(r.proc.pid)]
            if not alive:
                break
            if not escalated and time.monotonic() >= end:
                # Потолок вышел, а группа жива: слот отпускать нельзя (orphan продолжит
                # работу при свободном слоте) — сигнал оператору, ожидание продолжается.
                escalated = True
                _log(
                    "CRITICAL quarantine: process groups still alive after "
                    f"{QUARANTINE_MAX_S:.0f}s pgids={[r.proc.pid for r in alive]}, "
                    "slot stays withdrawn until they die"
                )
            for run in alive:
                _kill_group(run.proc)
            time.sleep(1.0)
        _log("quarantine: slot released")
        _slots.release()

    threading.Thread(target=work, daemon=True).start()


class Run:
    """Один прогон `muse-cli.sh exec` с разбором JSONL-конвертов."""

    def __init__(self, model_id: str, prompt: str, effort: str, workdir: Path) -> None:
        self.model_id = model_id
        self.prompt = prompt
        self.effort = effort
        self.workdir = workdir
        self.proc: subprocess.Popen | None = None
        self._closed = False
        self.dead_confirmed = (
            True  # False — группа не подтверждена мёртвой (карантин слота)
        )

    def close(self) -> None:
        """Убить группу процессов хода и коротко дождаться её ухода.

        Идемпотентно: повторный вызов (таймер, надзор обрыва, finally) — no-op,
        поэтому поздний killpg не может попасть в переиспользованный pid.
        """
        proc = self.proc
        if proc is None:
            return
        _terminate_run(self, (proc.stdout, proc.stderr))

    def execute(self) -> dict[str, Any]:
        if not os.access(MUSE_WRAPPER, os.X_OK):
            return {
                "rc": -1,
                "text": "",
                "err": f"muse wrapper not executable: {MUSE_WRAPPER}",
                "state": "launcher_missing",
            }

        self.workdir.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env.setdefault(
            "PATH",
            "/Users/aazhiry1/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        )
        env.pop(
            "META_API_KEY", None
        )  # обёртка тоже вычищает; двойная страховка (flat-подписка, не PAYG)

        fd, prompt_path = tempfile.mkstemp(
            prefix="muse-prompt-", suffix=".txt", dir=str(self.workdir)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(self.prompt)
        except OSError as exc:
            return {
                "rc": -1,
                "text": "",
                "err": f"prompt file write failed: {exc}",
                "state": "spawn_failed",
            }

        cmd = [
            MUSE_WRAPPER,
            "exec",
            "--provider",
            "meta",
            "--model",
            self.model_id,
            "--reasoning-effort",
            self.effort,
            "--yolo",
            "--trust-workspace",
            "--workspace",
            str(self.workdir),
            "--json",
            "--no-session-log",
            "--prompt-file",
            prompt_path,
        ]
        _log(
            f"exec model={self.model_id} effort={self.effort} prompt_chars={len(self.prompt)} ws={self.workdir}"
        )

        run_id = uuid.uuid4().hex[:8]
        deltas: list[str] = []
        final_text: str | None = None
        terminal: str | None = None
        reason: str | None = None
        err_lines: list[str] = []
        state = "ok"
        try:
            try:
                self.proc = subprocess.Popen(
                    cmd,
                    cwd=str(self.workdir),
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    start_new_session=True,
                )
            except OSError as exc:
                return {
                    "rc": -1,
                    "text": "",
                    "err": f"spawn failed: {exc}",
                    "state": "spawn_failed",
                }

            with _active_lock:
                _active[run_id] = time.time()

            def drain_stderr() -> None:
                try:
                    assert self.proc is not None and self.proc.stderr is not None
                    for line in self.proc.stderr:
                        line = line.strip()
                        if line:
                            err_lines.append(line)
                except (OSError, ValueError):
                    pass

            err_thread = threading.Thread(target=drain_stderr, daemon=True)
            err_thread.start()

            # Жёсткий дедлайн: таймер убивает процесс, даже если stdout молчит.
            timer = threading.Timer(
                TIMEOUT_S, lambda: (err_lines.append("bridge timeout"), self.close())
            )
            timer.daemon = True
            timer.start()
            timed_out = False
            try:
                assert self.proc.stdout is not None
                for raw in self.proc.stdout:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        event = json.loads(raw)
                    except ValueError:
                        continue
                    if not isinstance(event, dict):
                        continue
                    ptype = str(event.get("payload_type") or "")
                    payload = (
                        event.get("payload")
                        if isinstance(event.get("payload"), dict)
                        else {}
                    )
                    if ptype == "run.output.delta":
                        text = payload.get("text")
                        if isinstance(text, str):
                            deltas.append(text)
                    elif ptype.startswith("run.terminal"):
                        terminal = str(
                            payload.get("terminal") or ptype.rsplit(".", 1)[-1]
                        )
                        text = payload.get("text")
                        if isinstance(text, str):
                            final_text = text
                        if payload.get("reason"):
                            reason = str(payload["reason"])
                        if terminal == "completed":
                            # Ход завершён: общий таймер хода отменяется сразу (грейс уборки вне
                            # бюджета хода). Процесс может висеть после terminal — ждать EOF не
                            # нужно, группу добьёт close() ниже.
                            timer.cancel()
                            break
                    elif ptype == "task.lifecycle.failed":
                        ev = (
                            payload.get("event")
                            if isinstance(payload.get("event"), dict)
                            else {}
                        )
                        if ev.get("reason"):
                            err_lines.append(f"task failed: {ev['reason']}")
                if terminal == "completed":
                    # Короткий ограниченный грейс: CLI выходит сам (его rc настоящий) либо висит
                    # после terminal — тогда его добивает мост (rc от сигнала моста — не ошибка).
                    try:
                        self.proc.wait(timeout=TERMINAL_EXIT_GRACE_S)
                    except subprocess.TimeoutExpired:
                        pass
            except (OSError, ValueError) as exc:
                state = "stream_error"
                err_lines.append(f"stdout read failed: {exc}")
            finally:
                timer.cancel()
                # Порядок: kill группы -> wait ребёнка -> снятие с _active
                # (слот отпускается позже, в finally хендлера — после execute).
                self.close()
                try:
                    self.proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    timed_out = True
                err_thread.join(timeout=5)
                with _active_lock:
                    _active.pop(run_id, None)
        finally:
            try:
                os.unlink(prompt_path)
            except OSError:
                pass

        raw_rc = self.proc.returncode if self.proc else None
        rc = raw_rc if raw_rc is not None else -1
        if terminal == "completed" and (
            raw_rc is None or raw_rc == 0 or raw_rc in _SIGNAL_RCS
        ):
            # completed доставлен: rc 0 либо смерть от сигнала моста при уборке (SIGKILL/SIGTERM)
            # не ошибка; самостоятельный rc != 0 CLI (в т.ч. между грейсом и уборкой) — ошибка.
            # Не подтверждённая уборка (raw_rc None) не отменяет доставленный ход: журнал + карантин.
            state, rc = "ok", 0
        elif timed_out or any(line == "bridge timeout" for line in err_lines):
            state = "timeout"
        elif terminal is not None and terminal != "completed":
            state = f"terminal_{terminal}"
        elif rc != 0 and state == "ok":
            state = "nonzero_exit"

        # chunks — то, что кормим ToolCallParser: итоговый текст (приоритет) или дельты.
        chunks = [final_text] if final_text else deltas
        text = "".join(chunks)
        if reason:
            err_lines.append(f"reason: {reason}")
        return {
            "rc": rc,
            "text": text,
            "chunks": chunks,
            "err": "\n".join(err_lines[-6:]),
            "state": state,
        }


class ServeRun:
    """Один запрос через `muse serve` (MSP v1 по stdio, NDJSON JSON-RPC).

    Поток (проверен офлайн на echo-провайдере 05.10.2026): initialize ->
    notify initialized -> session/start (без approvalMode: любое явное
    значение режектится startup ceiling; провайдер meta)
    провайдер meta) -> turn/start (reasoningEffort=тир) -> ждём turn/completed.
    Текст — из agentMessage (item/completed.text, fallback — item/delta);
    reasoning summaries — из reasoning-item (summary[] + item/delta
    field "summary.N"); токены — из session/tokenUsage (reasoningTokens
    включительно). Сырой reasoning-текст в v1 не стримится (только
    summaries) — ограничение протокола, не моста.

    Любая транспортная неполадка (спавн, handshake, таймаут, интерактивный
    запрос approval/userInput, JSON-RPC error) -> ServeUnavailable, и
    вызывающий код тихо идёт на exec. Ошибка самой модели
    (terminal != completed) — НЕ ServeUnavailable: ход реально выполнен,
    fallback лишь удвоил бы вызов.
    """

    def __init__(self, model_id: str, prompt: str, effort: str, workdir: Path) -> None:
        self.model_id = model_id
        self.prompt = prompt
        self.effort = effort
        self.workdir = workdir
        self.proc: subprocess.Popen | None = None
        self._rid = 0
        self._closed = False
        self.dead_confirmed = (
            True  # False — группа не подтверждена мёртвой (карантин слота)
        )
        # Запись в stdin serve ограничена дедлайном (ставится в execute): зависший читатель
        # не держит слот бессрочно, при истечении ход завершается, группа убивается.
        self._write_until = float("inf")

    def close(self) -> None:
        """Убить группу процессов хода и коротко дождаться её ухода (идемпотентно)."""
        proc = self.proc
        if proc is None:
            return
        _terminate_run(self, (proc.stdin, proc.stdout, proc.stderr))

    def _send(
        self, method: str, params: dict | None = None, notify: bool = False
    ) -> int:
        assert self.proc is not None and self.proc.stdin is not None
        self._rid += 1
        msg: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if not notify:
            msg["id"] = self._rid
        if params is not None:
            msg["params"] = params
        data = (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")
        try:
            fd = self.proc.stdin.fileno()
            view = memoryview(data)
            sent = 0
            while sent < len(data):
                remaining = self._write_until - time.time()
                if remaining <= 0:
                    raise ServeUnavailable(
                        "serve stdin write timed out: child does not read"
                    )
                _, writable, _ = select.select([], [fd], [], min(0.5, remaining))
                if not writable:
                    continue
                try:
                    sent += os.write(fd, view[sent:])
                except BlockingIOError:
                    continue
        except (OSError, ValueError) as exc:
            raise ServeUnavailable(f"stdio write failed: {exc}")
        return self._rid

    def execute(self) -> dict[str, Any]:
        if not os.access(MUSE_WRAPPER, os.X_OK):
            raise ServeUnavailable(f"muse wrapper not executable: {MUSE_WRAPPER}")
        self.workdir.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env.setdefault(
            "PATH",
            "/Users/aazhiry1/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        )
        env.pop("META_API_KEY", None)
        cmd = [
            MUSE_WRAPPER,
            "serve",
            "--provider",
            "meta",
            "--model",
            self.model_id,
            "--no-session-log",
            "--trust-workspace",
        ]
        try:
            self.proc = subprocess.Popen(
                cmd,
                cwd=str(self.workdir),
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                start_new_session=True,
            )
        except OSError as exc:
            raise ServeUnavailable(f"serve spawn failed: {exc}")
        assert self.proc.stdout is not None and self.proc.stdin is not None
        # stdin неблокирующий: запись идёт срезами с дедлайном (см. _send).
        os.set_blocking(self.proc.stdin.fileno(), False)

        err_lines: list[str] = []

        def drain_stderr() -> None:
            try:
                assert self.proc is not None and self.proc.stderr is not None
                for line in self.proc.stderr:
                    line = line.strip()
                    if line:
                        err_lines.append(line)
            except (OSError, ValueError):
                pass

        err_thread = threading.Thread(target=drain_stderr, daemon=True)
        err_thread.start()
        deadline = time.time() + TIMEOUT_S
        setup_deadline = time.time() + SERVE_SPAWN_TIMEOUT_S
        self._write_until = setup_deadline

        # Чтение stdout serve — собственным буфером поверх os.read: select по fd не видит строки,
        # уже вычитанные в буфер TextIOWrapper (пачка строк за один write зависала бы).
        rbuf = bytearray()

        def read_msg(timeout_at: float) -> dict[str, Any]:
            while time.time() < min(timeout_at, deadline):
                if self.proc is None or self.proc.stdout is None:
                    raise ServeUnavailable("serve stdout closed")
                newline = rbuf.find(b"\n")
                if newline < 0:
                    ready, _, _ = select.select([self.proc.stdout], [], [], 0.5)
                    if not ready:
                        if self.proc.poll() is not None:
                            raise ServeUnavailable(
                                f"serve exited rc={self.proc.returncode}: "
                                + " ".join(err_lines[-3:])
                            )
                        continue
                    chunk = os.read(self.proc.stdout.fileno(), 65536)
                    if not chunk:
                        raise ServeUnavailable(
                            f"serve stdout EOF rc={self.proc.poll()}: "
                            + " ".join(err_lines[-3:])
                        )
                    rbuf.extend(chunk)
                    continue
                line = bytes(rbuf[:newline]).decode("utf-8", "replace").strip()
                del rbuf[: newline + 1]
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                if isinstance(msg, dict):
                    return msg
            raise ServeUnavailable("serve read timeout")

        def await_result(rid: int, timeout_at: float) -> dict[str, Any]:
            while True:
                msg = read_msg(timeout_at)
                if isinstance(msg, dict) and msg.get("id") == rid:
                    if "error" in msg:
                        raise ServeUnavailable(f"serve RPC error: {msg['error']}")
                    return (
                        msg.get("result") if isinstance(msg.get("result"), dict) else {}
                    )
                self._handle_event(msg, None)

        kinds: dict[str, str] = {}
        deltas: list[str] = []
        summary_parts: dict[int, str] = {}
        summaries: list[str] = []
        final_text: str | None = None
        usage: dict[str, Any] = {}
        turn_id: str | None = None
        session_id: str | None = None

        def _handle_event(msg: dict[str, Any], _unused: Any) -> None:
            nonlocal final_text
            method = msg.get("method")
            params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
            if method in ("approval/request", "userInput/request"):
                raise ServeUnavailable(f"serve needs interaction ({method})")
            if method in ("item/started", "item/completed"):
                item = (
                    params.get("item") if isinstance(params.get("item"), dict) else {}
                )
                iid = str(item.get("itemId") or "")
                kind = str(item.get("kind") or "")
                if iid:
                    kinds[iid] = kind
                if (
                    method == "item/completed"
                    and turn_id is not None
                    and item.get("turnId") == turn_id
                ):
                    if kind == "agentMessage" and isinstance(item.get("text"), str):
                        final_text = item["text"]
                    if kind == "reasoning" and isinstance(item.get("summary"), list):
                        summaries.extend(
                            str(p) for p in item["summary"] if isinstance(p, str)
                        )
            elif method == "item/delta":
                iid = str(params.get("itemId") or "")
                field = str(params.get("field") or "text")
                piece = params.get("delta")
                if not isinstance(piece, str) or not piece:
                    return
                if kinds.get(iid) == "reasoning" and field.startswith("summary"):
                    try:
                        idx = int(field.split(".", 1)[1])
                    except (IndexError, ValueError):
                        idx = len(summary_parts)
                    summary_parts[idx] = summary_parts.get(idx, "") + piece
                elif (
                    kinds.get(iid, "agentMessage") == "agentMessage" and field == "text"
                ):
                    deltas.append(piece)
            elif method == "session/tokenUsage":
                raw = params.get("usage")
                if isinstance(raw, dict):
                    usage.update(raw)

        self._handle_event = _handle_event  # type: ignore[attr-defined]

        try:
            init_rid = self._send(
                "initialize", {"clientInfo": {"name": "muse_bridge", "version": "1"}}
            )
            init = await_result(init_rid, setup_deadline)
            schema = init.get("schema") if isinstance(init.get("schema"), dict) else {}
            _log(
                f"serve init server={init.get('serverInfo', {}).get('version') if isinstance(init.get('serverInfo'), dict) else '?'} "
                f"schema_fp={str(schema.get('fingerprint', ''))[:19]}"
            )
            self._send("initialized", {}, notify=True)
            sess_rid = self._send(
                "session/start",
                {
                    "commandId": _uuid7(),
                    "workspaceRoot": str(self.workdir),
                    "providerId": "meta",
                    "modelId": self.model_id,
                },
            )
            # approvalMode намеренно НЕ передаём: любое явное значение
            # (allowAll, onRequest) отвергается sealed startup ceiling
            # неинтерактивного serve (commandRejected/approval_mode_ceiling),
            # а без ключа сервер назначает свой дефолт (promptUnmatched — так
            # было в офлайн-пробе на echo). Запрос approval/userInput по ходу
            # хода ведёт в ServeUnavailable -> fallback на exec.
            sess = await_result(sess_rid, setup_deadline)
            session = (
                sess.get("session") if isinstance(sess.get("session"), dict) else {}
            )
            session_id = str(session.get("sessionId") or "")
            if not session_id:
                raise ServeUnavailable("session/start gave no sessionId")
            tier = _MSP_EFFORT.get(self.effort, "max")
            turn_rid = self._send(
                "turn/start",
                {
                    "commandId": _uuid7(),
                    "sessionId": session_id,
                    "reasoningEffort": tier,
                    "input": [{"type": "text", "text": self.prompt}],
                },
            )
            turn = await_result(turn_rid, setup_deadline)
            if turn.get("status") != "accepted":
                raise ServeUnavailable(f"turn/start not accepted: {turn}")
            turn_id = str(turn.get("turnId") or "")
            _log(
                f"serve turn session={session_id[:8]} turn={turn_id[:8]} effort={tier}"
            )
            terminal: str | None = None
            while time.time() < deadline:
                # Смерть serve здесь не проверяется: события и completed, уже лежащие в буфере
                # чтения или pipe, разбираются первыми; read_msg сам поднимет ServeUnavailable
                # на EOF/выходе процесса, когда разбирать больше нечего.
                msg = read_msg(deadline)
                if msg.get("method") == "turn/completed" and isinstance(
                    msg.get("params"), dict
                ):
                    p = msg["params"]
                    if turn_id is not None and p.get("turnId") not in (turn_id, None):
                        _handle_event(msg, None)
                        continue
                    terminal = str(p.get("terminal") or "unknown")
                    break
                if "id" in msg and ("result" in msg or "error" in msg):
                    continue  # чужой/дублированный ack — игнор, не разрываем ход
                _handle_event(msg, None)
            else:
                raise ServeUnavailable("serve turn deadline exceeded")
            serve_rc: int | None = None
            if terminal == "completed":
                # D-A3-1: после completed — тот же грейс, что у exec: serve вышел сам с rc != 0 ->
                # ошибка; жив -> мост закрывает группу (сигнал моста rc не определяет).
                try:
                    self.proc.wait(timeout=TERMINAL_EXIT_GRACE_S)
                except subprocess.TimeoutExpired:
                    pass
                self.close()
                serve_rc = self.proc.returncode
            ordered = [
                summary_parts[i] for i in sorted(summary_parts) if summary_parts[i]
            ]
            for part in ordered:
                if part not in summaries:
                    summaries.append(part)
            text = final_text if final_text is not None else "".join(deltas)
            err = "\n".join(err_lines[-6:])
            if terminal == "completed" and serve_rc not in (None, 0, *_SIGNAL_RCS):
                return {
                    "rc": serve_rc,
                    "text": text,
                    "chunks": [text] if text else [],
                    "err": err,
                    "state": "nonzero_exit",
                    "summaries": summaries,
                    "usage": usage,
                    "via": "serve",
                }
            if terminal != "completed":
                return {
                    "rc": 1,
                    "text": text,
                    "chunks": [text] if text else [],
                    "err": err,
                    "state": f"terminal_{terminal}",
                    "summaries": summaries,
                    "usage": usage,
                    "via": "serve",
                }
            return {
                "rc": 0,
                "text": text,
                "chunks": [text] if text else [],
                "err": err,
                "state": "ok",
                "summaries": summaries,
                "usage": usage,
                "via": "serve",
            }
        finally:
            err_thread.join(timeout=5)
            self.close()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = 300

    def log_message(self, fmt: str, *args: Any) -> None:
        _log("http " + (fmt % args))

    def handle_error(self, request: Any, client_address: Any) -> None:
        _log(f"http accept error from {client_address}")

    # Обрыв клиента и текущий ход: значения инициализируются в setup() каждого соединения.
    _client_gone: bool = False
    _current_run: Run | ServeRun | None = None
    # Ранний SSE (stream=true): состояние потока и keepalive текущего соединения.
    _sse_open: bool = False
    _sse_id: str = ""
    _sse_created: int = 0
    _sse_model: str = ""
    _wlock: threading.Lock = threading.Lock()
    _ka_stop: threading.Event | None = None
    _ka_thread: threading.Thread | None = None

    def setup(self) -> None:
        # Состояние обрыва клиента и ссылка на текущий ход — на каждое соединение.
        self._client_gone = False
        self._current_run = None
        self._sse_open = False
        self._sse_id = ""
        self._sse_created = 0
        self._sse_model = ""
        self._wlock = threading.Lock()
        self._ka_stop: threading.Event | None = None
        self._ka_thread: threading.Thread | None = None
        super().setup()

    # ---- ранний SSE: заголовки сразу, keepalive во время хода ---------------------
    def _sse_write(self, text: str) -> bool:
        """Запись кадра SSE под замком (keepalive и выдача из разных потоков)."""
        try:
            with self._wlock:
                self.wfile.write(text.encode("utf-8"))
                self.wfile.flush()
            return True
        except (BrokenPipeError, ConnectionResetError, OSError):
            if not self._client_gone:
                self._client_gone = True
                _log("client gone mid-stream")
                self._kill_current_run()
            return False

    def _sse_chunk(self, delta: dict, finish_reason: Any = None) -> dict:
        return {
            "id": self._sse_id,
            "object": "chat.completion.chunk",
            "created": self._sse_created,
            "model": self._sse_model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }

    def _sse_emit(self, obj: dict) -> bool:
        return self._sse_write("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n")

    def _sse_begin(self, model: str) -> bool:
        """Заголовки 200 + role-кадр до запуска хода и поток keepalive; False — клиент ушёл."""
        self._sse_id = f"chatcmpl-muse-{uuid.uuid4().hex[:12]}"
        self._sse_created = int(time.time())
        self._sse_model = model
        self.close_connection = True
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
        except (BrokenPipeError, ConnectionResetError, OSError):
            self._client_gone = True
            _log("client gone before headers")
            return False
        self._sse_open = True
        if not self._sse_emit(self._sse_chunk({"role": "assistant", "content": ""})):
            return False
        stop = threading.Event()
        self._ka_stop = stop
        self._ka_thread = threading.Thread(
            target=self._keepalive_loop, args=(stop,), daemon=True
        )
        self._ka_thread.start()
        return True

    def _keepalive_loop(self, stop: threading.Event) -> None:
        """Комментарии `: keepalive`: держат TCP, но не сбрасывают idle-watchdog SDK."""
        while not stop.wait(KEEPALIVE_S):
            if not self._sse_write(": keepalive\n\n"):
                return

    def _sse_stop_keepalive(self) -> None:
        if self._ka_stop is not None:
            self._ka_stop.set()
        if self._ka_thread is not None:
            self._ka_thread.join(timeout=2)
        self._ka_stop = None
        self._ka_thread = None

    def _client_gone_probe(self) -> bool:
        """Обрыв клиента: FIN даёт пустой peek; ошибки сокета считаем обрывом.

        Режим сокета (timeout/blocking) не меняется: сокет общий с _sse_write
        в соседних потоках, смена режима из пробы ломала бы их запись. Peek идёт
        флагом MSG_DONTWAIT; select(0) заранее отсекает случай «данных нет».
        """
        conn = self.connection
        if conn is None:
            return False
        try:
            ready, _, _ = select.select([conn], [], [], 0)
        except (OSError, ValueError):
            return True
        if not ready:
            return False
        try:
            data = conn.recv(1, socket.MSG_PEEK | getattr(socket, "MSG_DONTWAIT", 0))
        except (BlockingIOError, InterruptedError):
            return False
        except OSError:
            return True
        return data == b""

    def _kill_current_run(self) -> None:
        """Убить группу текущего хода: призраки не переживают обрыв клиента."""
        run = self._current_run
        if run is not None:
            run.close()

    def _watch_client(self, stop: threading.Event) -> None:
        """Надзор за клиентом во время хода: обрыв -> флаг + killpg группы хода.

        Не выходит после первого убийства: ход может зарегистрироваться (или запустить
        процесс) уже после обрыва — kill идемпотентен и повторяется каждый тик до stop.
        """
        reported = False
        while not stop.wait(0.25):
            if self._client_gone or self._client_gone_probe():
                self._client_gone = True
                if not reported:
                    reported = True
                    _log("client gone during run — killing process group")
                self._kill_current_run()

    def _send(self, code: int, payload: dict) -> None:
        if self._sse_open:
            # Заголовки 200 уже ушли: ошибка — кадром SSE, как у OpenAI-совместимых прокси.
            self._sse_stop_keepalive()
            error = payload.get("error") if isinstance(payload, dict) else None
            if isinstance(error, dict):
                error = dict(error)
                error.setdefault("code", int(code))
            self._sse_emit({"error": error or payload})
            self._sse_write("data: [DONE]\n\n")
            return
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(int(code))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, OSError):
            self._client_gone = True
            _log("client gone before response")
            self._kill_current_run()

    def _send_sse(
        self,
        model: str,
        content: str,
        tool_calls: list[dict],
        prompt_tokens: int,
        completion_tokens: int,
        reasoning_tokens: int,
        summaries: list[str] | None = None,
    ) -> None:
        """Выдача готового хода в поток SSE (см. модуль-docstring).

        Заголовки и role-кадр обычно уже ушли (_sse_begin до запуска хода); здесь —
        reasoning_content (summaries размышлений) -> tool_calls -> content-чанки
        (~SSE_CHUNK_SIZE символов) -> финал с finish_reason + usage -> `data: [DONE]`.
        """
        finish = "tool_calls" if tool_calls else "stop"
        if not self._sse_open and not self._sse_begin(model):
            return
        self._sse_stop_keepalive()
        chunk = self._sse_chunk
        reasoning = "\n\n".join(s for s in (summaries or []) if s)
        if reasoning and not self._sse_emit(chunk({"reasoning_content": reasoning})):
            return
        for tc in tool_calls:
            fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
            delta = {
                "tool_calls": [
                    {
                        "index": tc.get("index", 0),
                        "id": tc.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": fn.get("name", ""),
                            "arguments": fn.get("arguments", ""),
                        },
                    }
                ]
            }
            if not self._sse_emit(chunk(delta)):
                return
        for piece in _split_sse_chunks(content):
            if not self._sse_emit(chunk({"content": piece})):
                return
            if SSE_CHUNK_DELAY_S > 0:
                time.sleep(SSE_CHUNK_DELAY_S)
        final = chunk({}, finish)
        final["usage"] = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "reasoning_tokens": reasoning_tokens,
        }
        if self._sse_emit(final):
            self._sse_write("data: [DONE]\n\n")

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/health", "/v1/health"):
            with _active_lock:
                active = len(_active)
            self._send(
                200,
                {
                    "ok": True,
                    "transport": "muse-cli",
                    "wrapper": MUSE_WRAPPER,
                    "models": sorted(ALLOWED_MODELS),
                    "default_model": DEFAULT_MODEL,
                    "default_effort": DEFAULT_EFFORT,
                    "active": active,
                    "max_concurrent": MAX_CONCURRENT,
                    "stream": True,
                    "tool_emulation": True,
                    "uptime_s": int(time.time() - _started),
                },
            )
            return
        if not _auth_ok(self):
            self._send(
                401, {"error": {"message": "unauthorized", "type": "auth_error"}}
            )
            return
        if path in ("/v1/models", "/models"):
            self._send(
                200,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": mid,
                            "object": "model",
                            "owned_by": "meta-muse",
                            "created": 0,
                            "context_length": meta["context_length"],
                        }
                        for mid, meta in ALLOWED_MODELS.items()
                    ],
                },
            )
            return
        self._send(404, {"error": {"message": f"not found: {path}"}})

    def do_POST(self) -> None:  # noqa: N802
        if not _auth_ok(self):
            self.close_connection = True
            self._send(
                401, {"error": {"message": "unauthorized", "type": "auth_error"}}
            )
            return
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            req = json.loads(raw.decode("utf-8") or "{}")
        except ValueError:
            self._send(400, {"error": {"message": "invalid json"}})
            return
        if path not in ("/v1/chat/completions", "/chat/completions"):
            self._send(404, {"error": {"message": f"not found: {path}"}})
            return
        try:
            self._serve_json(req)
        finally:
            # Любой выход (в т.ч. обрыв в очереди за слотом): поток keepalive не переживает запрос.
            self._sse_stop_keepalive()

    def _serve_json(self, req: dict) -> None:
        model = str(req.get("model") or DEFAULT_MODEL).strip()
        if model not in ALLOWED_MODELS:
            self._send(
                400,
                {
                    "error": {
                        "message": f"unknown model '{model}'; allowed: {sorted(ALLOWED_MODELS)}",
                        "type": "invalid_request_error",
                        "code": "model_not_found",
                    }
                },
            )
            return

        raw_tools = req.get("tools")
        tools = (
            [t for t in raw_tools if isinstance(t, dict)]
            if isinstance(raw_tools, list)
            else []
        )
        tool_choice = req.get("tool_choice")
        emulate_tools = bool(tools) and not _tool_choice_none(tool_choice)

        system_text, prompt = _messages_to_prompt(req.get("messages") or [])
        if not prompt:
            self._send(
                400,
                {
                    "error": {
                        "message": "no user content",
                        "type": "invalid_request_error",
                    }
                },
            )
            return
        head: list[str] = []
        if system_text:
            head.append(f"[system]\n{system_text}")
        if emulate_tools:
            head.append(_tools_section(tools, tool_choice))
        elif raw_tools and not system_text:
            head.append(f"[system]\n{DEFAULT_SYSTEM_HINT}")
        if head:
            prompt = "\n\n".join(head) + f"\n\n{prompt}"

        effort = _map_effort(req)

        if req.get("stream") is True and not self._sse_begin(model):
            return
        waited = time.monotonic()
        while not _slots.acquire(timeout=1.0):
            if self._client_gone or self._client_gone_probe():
                self._client_gone = True
                _log("client gone while waiting for a slot")
                return
            if time.monotonic() - waited > TIMEOUT_S:
                self._send(
                    503, {"error": {"message": "bridge busy", "type": "overloaded"}}
                )
                return
        if self._client_gone or self._client_gone_probe():
            # Клиент ушёл на границе получения слота: ход без надзора не стартует.
            self._client_gone = True
            _log("client gone while waiting for a slot")
            _slots.release()
            return
        watch_stop = threading.Event()
        watcher = threading.Thread(
            target=self._watch_client, args=(watch_stop,), daemon=True
        )
        watcher.start()
        runs: list = []
        try:
            # Serve-first: пробуем MSP serve (там reasoning summaries), при любой
            # транспортной неполадке — тихий fallback на проверенный exec.
            out: dict[str, Any] | None = None
            via = "exec"
            try:
                serve_run = ServeRun(model, prompt, effort, WORKSPACE)
                runs.append(serve_run)
                self._current_run = serve_run
                out = serve_run.execute()
                via = "serve"
            except ServeUnavailable as exc:
                if self._client_gone:
                    # Обрыв клиента уже убил serve-группу: новый exec-ход не запускаем.
                    _log("client gone during serve — exec fallback skipped")
                    out = {
                        "rc": -1,
                        "text": "",
                        "err": "client gone",
                        "state": "client_gone",
                    }
                    via = "aborted"
                else:
                    _log(f"serve unavailable ({exc}), fallback exec model={model}")
                    exec_run = Run(model, prompt, effort, WORKSPACE)
                    runs.append(exec_run)
                    self._current_run = exec_run
                    out = exec_run.execute()
                    via = "exec-after-serve-fallback"
                    if (
                        out.get("rc") != 0
                        and not self._client_gone
                        and NETWORK_RETRY_MARKER in str(out.get("err") or "")
                    ):
                        _log("exec hit network marker, single retry")
                        retry_run = Run(model, prompt, effort, WORKSPACE)
                        runs.append(retry_run)
                        self._current_run = retry_run
                        out = retry_run.execute()
                        via = "exec-retry"
        finally:
            # Слот отпускаем после остановки надзора (kill -> wait уже внутри execute).
            watch_stop.set()
            watcher.join(timeout=2)
            if all(run.dead_confirmed for run in runs):
                _slots.release()
            else:
                # Смерть группы не подтверждена: слот не освобождается, пока она жива (карантин).
                _quarantine_slot([run for run in runs if not run.dead_confirmed])

        if self._client_gone:
            # Клиент ушёл: ответ в закрытый сокет не пишется (ни JSON, ни кадр ошибки).
            _log("client gone — response skipped")
            return
        if out.get("state") in ("launcher_missing", "spawn_failed"):
            self._send(
                502,
                {
                    "error": {
                        "message": out.get("err") or out["state"],
                        "type": "proxy_error",
                        "code": 502,
                    }
                },
            )
            return
        if out.get("state") != "ok" or out.get("rc") != 0:
            # Провал хода (failed terminal, rc != 0, таймаут): частичный текст и tool-блоки
            # не выдаются как успешный финал — SSE error + [DONE] либо 502 (Q-004).
            hint = " (proxy :10816 DOWN?)" if out.get("rc") == 42 else ""
            self._send(
                502,
                {
                    "error": {
                        "message": f"muse turn failed (rc={out.get('rc')}, state={out.get('state')}){hint}",
                        "detail": str(out.get("err"))[:500],
                        "type": "proxy_error",
                        "code": 502,
                    }
                },
            )
            return
        content = out["text"]
        tool_calls: list[dict] = []
        if emulate_tools and content:
            content, tool_calls = _split_tool_calls(out.get("chunks") or [content])
        if not content and not tool_calls:
            hint = " (proxy :10816 DOWN?)" if out.get("rc") == 42 else ""
            self._send(
                502,
                {
                    "error": {
                        "message": f"muse exec produced no text (rc={out.get('rc')}, state={out.get('state')}){hint}",
                        "detail": str(out.get("err"))[:500],
                        "type": "proxy_error",
                        "code": 502,
                    }
                },
            )
            return

        prompt_tokens = _estimate_tokens(prompt)
        completion_tokens = _estimate_tokens(out["text"])
        # Serve даёт настоящие токены (session/tokenUsage); exec — оценку.
        # tokenUsage serve не даёт promptTokens — фолбэк на оценку по каждому
        # полю отдельно (раньше общий if занулял prompt при пустом поле).
        ru = out.get("usage") if isinstance(out.get("usage"), dict) else {}
        ru_prompt = ru.get("promptTokens") or ru.get("prompt_tokens") or 0
        ru_output = ru.get("outputTokens") or ru.get("output_tokens") or 0
        try:
            ru_prompt = int(ru_prompt)
        except (TypeError, ValueError):
            ru_prompt = 0
        try:
            ru_output = int(ru_output)
        except (TypeError, ValueError):
            ru_output = 0
        if ru_prompt > 0:
            prompt_tokens = ru_prompt
        if ru_output > 0:
            completion_tokens = ru_output
        ru_reasoning = ru.get("reasoningTokens") or ru.get("reasoning_tokens") or 0
        try:
            reasoning_tokens = int(ru_reasoning)
        except (TypeError, ValueError):
            reasoning_tokens = 0
        if reasoning_tokens < 0:
            reasoning_tokens = 0
        summaries = (
            out.get("summaries") if isinstance(out.get("summaries"), list) else []
        )
        summaries = [s for s in summaries if isinstance(s, str)]
        sum_chars = sum(len(s) for s in summaries)
        if summaries:
            preview = next((s for s in summaries if s), "")[:300]
            _log(
                f"reasoning summaries={len(summaries)} chars={sum_chars} "
                f"reasoning_tokens={reasoning_tokens} preview={preview!r}"
            )
        message: dict[str, Any] = {"role": "assistant", "content": content}
        finish = "stop"
        if tool_calls:
            message["tool_calls"] = tool_calls
            finish = "tool_calls"
        _log(
            f"done model={model} via={via} rc={out.get('rc')} state={out.get('state')} "
            f"tools={len(tool_calls)} out_chars={len(out['text'])} "
            f"stream={req.get('stream') is True}"
        )
        if req.get("stream") is True:
            self._send_sse(
                model,
                content,
                tool_calls,
                prompt_tokens,
                completion_tokens,
                reasoning_tokens,
                summaries,
            )
            return
        self._send(
            200,
            {
                "id": f"chatcmpl-muse-{uuid.uuid4().hex[:12]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                    "reasoning_tokens": reasoning_tokens,
                },
                "reasoning_summaries": summaries,
            },
        )


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main() -> int:
    if not AUTH_KEY:
        sys.stderr.write("MUSE_BRIDGE_KEY is required; refusing to start\n")
        return 2
    try:
        WORKSPACE.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _log(f"workspace mkdir failed: {exc}")
    _log(
        f"start host={HOST} port={PORT} models={sorted(ALLOWED_MODELS)} wrapper={MUSE_WRAPPER}"
    )
    server = Server((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
