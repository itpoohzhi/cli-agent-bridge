"""Общее ядро эмуляции OpenAI function calling (чистые функции, без I/O).

Единый источник для всех бэкендов хаба: рендер истории и протокола инструментов в
текстовый промпт, разбор блоков `<tool_call>…</tool_call>` из потока текстовых дельт.
Модуль не импортирует `server` и адаптеры; `server.py` реэкспортирует имена для
существующих тестов и совместимости.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
import uuid
from dataclasses import replace
from typing import Any
from core.backend_adapter import ToolCall, ToolFunction, TurnEvent, TurnResult

TOOL_CALL_OPEN = "<tool_call>"
TOOL_CALL_CLOSE = "</tool_call>"

# ADR-0020 (BND-001): ядро окружение не читает — здесь только умолчания
# RepetitionGuard; эффективные значения передаёт владелец маршрута аргументами.
DEFAULT_MAX_REPETITION_REPEATS = 20
DEFAULT_MAX_REPETITION_TOKEN_LEN = 64
REPETITION_MIN_REPEATS = 3
REPETITION_MAX_REPEATS_CAP = 1000


def _flatten_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
        return "\n".join(p for p in parts if p)
    return str(content)


def _render_content(content: Any, counter: list) -> str:
    """Содержимое сообщения -> текст; на месте изображений маркер `[image N]`.

    Нумерация сквозная по порядку появления во всей истории. Неизвестные
    НЕ-image части (например input_audio) молча пропускаются, как раньше.
    """
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
                if item.get("type") == "image_url":
                    counter[0] += 1
                    parts.append(f"[image {counter[0]}]")
                elif "text" in item and item.get("text") is not None:
                    parts.append(str(item["text"]))
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


def _tools_section(tools: list, tool_choice: Any, has_attachments: bool = False) -> str:
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
    ]
    if has_attachments:
        lines[-1] += ", except Read on the attachment files listed under [attachments]."
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


def _render_message(msg: Any, counter: list) -> str:
    """Одно сообщение истории -> текстовый блок (с рендером tool-вызовов/результатов)."""
    if not isinstance(msg, dict):
        return ""
    role = str(msg.get("role") or "user")
    if role == "tool":
        call_id = str(msg.get("tool_call_id") or msg.get("id") or "")
        name = str(msg.get("name") or "")
        text = _render_content(msg.get("content"), counter)
        header = f"[tool result {call_id}]"
        if name:
            header += f" ({name})"
        return f"{header}\n{text}" if text.strip() else header
    text = _render_content(msg.get("content"), counter)
    if role == "assistant":
        parts = []
        if text.strip():
            parts.append(text)
        calls = msg.get("tool_calls")
        if isinstance(calls, list):
            parts.extend(_render_tool_call(tc) for tc in calls)
        body = "\n".join(p for p in parts if p)
        return f"[assistant]\n{body}" if body.strip() else ""
    if text.strip():
        return f"[{role}]\n{text}"
    return ""


def _attachments_section(images: list) -> str:
    """Хвост промпта метода workspace-read (эталон — kit/mkprompt.py)."""
    lines = [
        "[attachments]",
        "This request includes %d image(s) as local files in the working directory. "
        "The markers [image N] in the conversation refer to them in order."
        % len(images),
    ]
    for index, image in enumerate(images, 1):
        lines.append(
            "- [image %d] ./%s (%s, %d bytes)"
            % (index, image["name"], image["mime"], len(image["data"]))
        )
    lines.append(
        "Open each image with the Read tool on exactly these paths before answering about it "
        "(Read is the only built-in tool you may use, and only on these files). Do not claim to "
        "see an image you have not opened. If an image cannot be opened, say so explicitly "
        "instead of guessing."
    )
    return "\n".join(lines)


def _messages_to_prompt(
    messages: list,
    tools: list | None = None,
    tool_choice: Any = None,
    images: list | None = None,
) -> str:
    """Собрать единый текстовый промпт; при наличии tools — с секцией протокола.

    При наличии изображений в конец добавляется секция [attachments], а строка
    протокола инструментов получает исключение для Read (C-09).
    """
    tools = tools or []
    counter = [0]
    blocks = []
    for msg in messages:
        rendered = _render_message(msg, counter)
        if rendered:
            blocks.append(rendered)
    head = []
    if tools and not _tool_choice_none(tool_choice):
        head.append(_tools_section(tools, tool_choice, bool(images)))
    text = "\n\n".join(head + blocks).strip() or "Reply with exactly: PONG"
    if images:
        text = text + "\n\n" + _attachments_section(images)
    return text


def _strip_code_fence(text: str) -> str:
    """Снять обёртку ```…``` или ~~~…~~~ (в т.ч. ```json) вокруг JSON внутри блока."""
    body = text.strip()
    if body.startswith(("```", "~~~")):
        newline = body.find("\n")
        body = body[newline + 1 :] if newline != -1 else body[3:]
    if body.rstrip().endswith(("```", "~~~")):
        body = body.rstrip()[:-3]
    return body.strip()


_MAX_EXTRA_BRACES = 16  # предел лишних `}` после полного объекта вызова


def _recover_trailing_braces(text: str) -> dict | None:
    """Первый JSON-объект, за которым идут только пробелы и 1..16 лишних `}`; иначе None (холодный путь)."""
    body = text.lstrip()
    try:
        obj, end = json.JSONDecoder().raw_decode(body)
    except (ValueError, RecursionError):
        return None
    tail = body[end:]
    if (
        isinstance(obj, dict)
        and 1 <= tail.count("}") <= _MAX_EXTRA_BRACES
        and not tail.strip(" \t\r\n}")
    ):
        return obj
    return None


def _loads_tolerant(text: str) -> Any:
    """json.loads, допускающий лишние `}` после полного объекта (модель закрыла скобок больше нужного).

    Слишком глубокая вложенность (RecursionError) — невалидный JSON (ValueError).
    """
    try:
        return json.loads(text)
    except (ValueError, RecursionError) as exc:
        recovered = _recover_trailing_braces(text)
        if recovered is None:
            if isinstance(exc, RecursionError):
                raise ValueError("JSON is nested too deeply") from exc
            raise
        return recovered


def _parse_tool_call_block(inner: str) -> dict | None:
    """Содержимое блока -> {"name","arguments"}; None, если блок невалиден.

    Отсутствие ключа arguments — допустимый вызов с {}; присутствующее, но
    не-объектное значение (строка-не-JSON, список, число, null) — вызов
    отклоняем, чтобы не запускать инструмент с пустыми аргументами.
    """
    try:
        obj = _loads_tolerant(_strip_code_fence(inner))
    except ValueError:
        return None
    if not isinstance(obj, dict):
        return None
    if "name" not in obj and isinstance(obj.get("function"), dict):
        # OpenAI tool_calls: {"id", "type", "function": {"name", "arguments"}}
        obj = obj["function"]
    name = obj.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    if "arguments" not in obj:
        arguments: dict = {}
    else:
        normalized = _normalize_arguments(obj.get("arguments"))
        if normalized is None:
            return None
        arguments = normalized
    return {"name": name.strip(), "arguments": arguments}


class LiveParserError(Exception):
    """Strict-live (AD-002): recognized `<tool_call>` блок невалиден либо не закрыт.

    Поднимается только при `strict_live=True`; legacy-режим (stream=false либо
    без sink) этот блок, как раньше, молча отдаёт текстом — исключение означает
    fail-close всего live-хода (сырой XML клиенту не уходит).
    """


def _is_quoted_open(text: str, start: int) -> bool:
    """`<tool_call>` в inline-коде markdown (`` `<tool_call>` ``) — не тег."""
    if start > 0 and text[start - 1] == "`":
        return True
    tail = text[start + len(TOOL_CALL_OPEN) : start + len(TOOL_CALL_OPEN) + 3]
    return bool(tail) and tail[0] == "`" and tail != "```"


def _split_tool_call_inner(inner: str) -> list[str]:
    """Разбить содержимое блока по вложенным `<tool_call>` вне строковых литералов JSON.

    Модель иногда пропускает `</tool_call>` между соседними вызовами пачки и ставит
    один общий закрывающий тег в конце. Литерал `<tool_call>` внутри JSON-строки
    границей не считается (та же логика, что в `_find_close_outside_string`).
    Пустые сегменты сохраняются: пустой элемент делает всю пачку невалидной.
    """
    segments: list[str] = []
    seg_start = 0
    index = 0
    length = len(inner)
    in_string = False
    escaped = False
    while index < length:
        char = inner[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif inner.startswith(TOOL_CALL_OPEN, index) and not _is_quoted_open(
            inner, index
        ):
            segments.append(inner[seg_start:index])
            index += len(TOOL_CALL_OPEN)
            seg_start = index
            continue
        index += 1
    segments.append(inner[seg_start:])
    return segments


def _parse_tool_call_blocks(inner: str) -> list[dict] | None:
    """Содержимое блока -> список вызовов; None, если блок (или любой его член) невалиден.

    Обычный блок даёт один вызов. Если он не разбирается, но внутри есть
    несколько `<tool_call>` без промежуточных закрывающих тегов, блок делится на
    сегменты; пачка принимается только целиком (все сегменты валидны).
    """
    single = _parse_tool_call_block(inner)
    if single is not None:
        return [single]
    if TOOL_CALL_OPEN not in inner:
        return None
    segments = _split_tool_call_inner(inner)
    if len(segments) < 2:
        return None
    calls: list[dict] = []
    for segment in segments:
        call = _parse_tool_call_block(segment)
        if call is None:
            return None
        calls.append(call)
    return calls


_OPAQUE_BLOCK = "￼"  # в `_history` на месте разобранного блока вызова


def _fence_run(line: str) -> tuple[str, int, str]:
    """Строка -> (символ, длина серии, остаток), если это строка-забор fenced-блока.

    Забор — серия от 3 одинаковых бэктиков или тильд после отступа до 3 пробелов;
    ("", 0, "") — не забор.
    """
    stripped = line.lstrip(" ")
    if len(line) - len(stripped) > 3 or stripped[:1] not in ("`", "~"):
        return "", 0, ""
    char = stripped[0]
    rest = stripped.lstrip(char)
    run = len(stripped) - len(rest)
    return (char, run, rest) if run >= 3 else ("", 0, "")


def _is_fence_open(char: str, run: int, rest: str) -> bool:
    """Строка-забор открывает блок: в info-строке бэктик-забора нет бэктиков."""
    return bool(run) and (char == "~" or "`" not in rest)


def _find_closing_run(doc: str, start: int, end: int, ticks: int) -> int:
    """Конец первой серии ровно из `ticks` бэктиков в `doc[start:end]`, или -1."""
    index = start
    while index < end:
        if doc[index] != "`":
            index += 1
            continue
        run_start = index
        while index < end and doc[index] == "`":
            index += 1
        if index - run_start == ticks:
            return index
    return -1


def _is_atx_heading(line: str) -> bool:
    """Строка — ATX-заголовок: отступ до 3 пробелов, 1-6 `#`, затем пробел/таб/конец."""
    stripped = line.lstrip(" ")
    if len(line) - len(stripped) > 3:
        return False
    rest = stripped.lstrip("#")
    return 1 <= len(stripped) - len(rest) <= 6 and (
        not rest.rstrip("\r") or rest[0] in " \t"
    )


def _code_context(doc: str, pos: int, final: bool) -> str:
    """Положение `pos` в `doc` относительно markdown-кода: "code" | "text" | "wait".

    "code" — внутри fenced-блока (CommonMark: забор с отступом до 3 пробелов, закрывает
    серия того же символа (``` или ~~~) не короче открывающей, без текста после неё) или парного inline-кода (серия из
    k бэктиков и ближайшая серия ровно из k в том же абзаце; абзац обрывают пустая
    строка, забор и ATX-заголовок — он сам отдельный блок). Непарная серия — обычный
    текст. "wait" — ответ зависит от ещё не пришедшего текста (только при `final=False`).
    Результат определяется одним `doc`, поэтому не зависит от нарезки потока на чанки.
    """
    line_start = doc.rfind("\n", 0, pos) + 1
    fence_char, fence_len, para, index = "", 0, 0, 0
    while index < line_start:
        eol = doc.index("\n", index)
        line = doc[index:eol]
        char, run, rest = _fence_run(line)
        if fence_len:
            if char == fence_char and run >= fence_len and not rest.strip(" \t\r"):
                fence_len, para = 0, eol + 1
        elif _is_fence_open(char, run, rest):
            fence_char, fence_len = char, run
        elif not line.strip() or _is_atx_heading(line):
            para = eol + 1
        index = eol + 1
    if fence_len:
        return "code"
    eol = doc.find("\n", pos)
    char, run, rest = _fence_run(doc[line_start : len(doc) if eol == -1 else eol])
    if _is_fence_open(char, run, rest):  # тег в info-строке забора
        return "code" if eol != -1 or final else "wait"
    para_end, decided = len(doc), final
    index = len(doc) if eol == -1 else eol + 1
    if _is_atx_heading(doc[line_start : len(doc) if eol == -1 else eol]):
        para = line_start  # заголовок — отдельный однострочный блок
        if eol != -1:
            para_end, decided, index = eol, True, len(doc)
    while index < len(doc):  # абзац кончается пустой строкой, забором или заголовком
        nxt = doc.find("\n", index)
        line = doc[index : len(doc) if nxt == -1 else nxt]
        # заголовок с текстом после `#` решён по префиксу, не дожидаясь конца строки
        if (
            nxt == -1
            and not final
            and not (_is_atx_heading(line) and line.lstrip(" ").lstrip("#"))
        ):
            break
        char, run, rest = _fence_run(line)
        if not line.strip() or _is_fence_open(char, run, rest) or _is_atx_heading(line):
            para_end, decided = index, True
            break
        if nxt == -1:
            break
        index = nxt + 1
    index = para
    while index < pos:
        char = doc[index]
        if char == "\\":
            index += 2
        elif char != "`":
            index += 1
        else:
            open_start = index
            while index < para_end and doc[index] == "`":
                index += 1
            close_end = _find_closing_run(doc, index, para_end, index - open_start)
            if close_end == -1:
                if not decided:  # пара может прийти позже
                    return "wait"
            elif close_end > pos:
                return "wait" if close_end == len(doc) and not final else "code"
            else:
                index = close_end
    return "text"


class RepetitionLoopDetected(LiveParserError):
    """RepetitionGuard обнаружил авторегрессионный цикл повторений (ADR-0020)."""

    code = "upstream_repetition_loop"


_SEPARATOR_LINE_RE = re.compile(r"^[-=*_]{3,}$")


def _unpack_guard_state(
    state: tuple[Any, ...] | None,
) -> tuple[str, int, int]:
    if not state:
        return "", 0, 0
    if len(state) == 2:
        return str(state[0] or ""), int(state[1] or 0), 0
    return str(state[0] or ""), int(state[1] or 0), int(state[2] or 0)


def _pack_guard_state(
    fence_char: str, fence_len: int, inline_ticks: int
) -> tuple[str, int, int] | None:
    if fence_len or inline_ticks:
        return (fence_char, fence_len, inline_ticks)
    return None


def _strip_inline_code_line(raw_line: str, inline_ticks: int) -> tuple[str, int]:
    """Вырезать inline-код из строки с переносом незакрытого состояния `inline_ticks`."""
    out: list[str] = []
    idx = 0
    length = len(raw_line)
    while idx < length:
        ch = raw_line[idx]
        if ch == "`":
            end = idx
            while end < length and raw_line[end] == "`":
                end += 1
            run = end - idx
            if inline_ticks == 0:
                inline_ticks = run
                out.append(" ")
            elif run == inline_ticks:
                inline_ticks = 0
                out.append(" ")
            idx = end
            continue
        if inline_ticks == 0 or ch in ("\n", "\r"):
            out.append(ch)
        idx += 1
    return "".join(out), inline_ticks


def _fence_state_after(
    text: str, state: tuple[Any, ...] | None
) -> tuple[str, int, int] | None:
    """Состояние fenced/inline-кода после `text` при входном состоянии `state`."""
    return _strip_code_for_guard(text, state)[1]


def _strip_code_for_guard(
    text: str, state: tuple[Any, ...] | None = None
) -> tuple[str, tuple[str, int, int] | None]:
    """Текст без fenced/inline-кода и строк-разделителей Markdown (защита от FP)."""
    out: list[str] = []
    fence_char, fence_len, inline_ticks = _unpack_guard_state(state)
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        char, run, rest = _fence_run(line)
        if fence_len:
            if char == fence_char and run >= fence_len and not rest.strip(" \t\r"):
                fence_char, fence_len = "", 0
            continue
        if _is_fence_open(char, run, rest):
            fence_char, fence_len = char, run
            inline_ticks = 0
            continue
        if not inline_ticks and _SEPARATOR_LINE_RE.match(line.strip()):
            continue
        stripped_line, inline_ticks = _strip_inline_code_line(raw_line, inline_ticks)
        out.append(stripped_line)
    return "".join(out), _pack_guard_state(fence_char, fence_len, inline_ticks)


def _is_separator_token(token: str) -> bool:
    """Токен только из символов Markdown-разделителей (`---`, `===`, `***`)."""
    return bool(token) and all(char in "-=*_" for char in token)


class RepetitionGuard:
    """Детектор циклов повторений в потоке текста (ADR-0020 AD-001).

    `feed(chunk)` накапливает текст и возвращает `(chunk, detected)`: `detected`
    взводится, когда один непробельный токен длиной до `max_token_len` или
    периодический паттерн такой длины (например `\\n\\n_placeholder`)
    повторяется подряд не менее `max_repeats` раз. Fenced/inline-код, чистый
    whitespace и строки-разделители Markdown из детекции исключены.
    """

    _MAX_BUFFER = 32768
    _KEEP_BUFFER = 16384

    def __init__(
        self,
        max_repeats: int = DEFAULT_MAX_REPETITION_REPEATS,
        max_token_len: int = DEFAULT_MAX_REPETITION_TOKEN_LEN,
        enabled: bool = True,
    ) -> None:
        self.max_repeats = (
            min(int(max_repeats), REPETITION_MAX_REPEATS_CAP)
            if int(max_repeats) >= 1
            else DEFAULT_MAX_REPETITION_REPEATS
        )
        self.max_token_len = (
            int(max_token_len)
            if int(max_token_len) >= 1
            else DEFAULT_MAX_REPETITION_TOKEN_LEN
        )
        self.enabled = bool(enabled)
        self._max_buffer = max(
            self._MAX_BUFFER, (self.max_repeats + 10) * (self.max_token_len + 4)
        )
        self._keep_buffer = self._max_buffer // 2
        self._buffer = ""
        self._buffer_fence: tuple[Any, ...] | None = None
        self._detected = False

    @property
    def detected(self) -> bool:
        return self._detected

    @property
    def loop_detected(self) -> bool:
        return self._detected

    @property
    def triggered(self) -> bool:
        return self._detected

    def reset(self) -> None:
        self._buffer = ""
        self._buffer_fence = None
        self._detected = False

    def feed(self, chunk: str) -> tuple[str, bool]:
        """Принять очередной кусок текста; `(chunk, loop_detected)`."""
        if not self.enabled or not chunk:
            return chunk, False
        self._buffer += chunk
        if len(self._buffer) > self._max_buffer:
            cut = len(self._buffer) - self._keep_buffer
            newline = self._buffer.find("\n", cut)
            if newline != -1 and newline + 1 < len(self._buffer):
                cut = newline + 1
            self._buffer_fence = _fence_state_after(
                self._buffer[:cut], self._buffer_fence
            )
            self._buffer = self._buffer[cut:]
        if not self._detected:
            cleaned, _ = _strip_code_for_guard(self._buffer, self._buffer_fence)
            self._detected = self._scan_cleaned(cleaned)
        return chunk, self._detected

    def check(self, chunk: str | None = None) -> bool:
        """Скормить `chunk` (если дан) и вернуть флаг детекции."""
        if chunk:
            return self.feed(chunk)[1]
        return self._detected

    def detect(self, text: str) -> bool:
        """Разовая проверка целого текста без изменения состояния guard."""
        if not self.enabled or not text:
            return False
        cleaned, _ = _strip_code_for_guard(text, None)
        return self._scan_cleaned(cleaned)

    def _scan_cleaned(self, cleaned: str) -> bool:
        if not cleaned.strip():
            return False
        prev: str | None = None
        run = 0
        for token in cleaned.split():
            if len(token) > self.max_token_len or _is_separator_token(token):
                prev, run = None, 0
                continue
            if token == prev:
                run += 1
            else:
                prev, run = token, 1
            if run >= self.max_repeats:
                return True
        tail = cleaned[-(self.max_token_len * self.max_repeats + self.max_token_len) :]
        max_pat = min(self.max_token_len, len(tail) // self.max_repeats)
        for pat_len in range(1, max_pat + 1):
            pattern = tail[-pat_len:]
            core = pattern.strip()
            if not core or set(core) <= set("-=*_"):
                continue
            if len(set(core)) == 1 and not core.isalnum():
                continue
            count = 0
            index = len(tail)
            while index - pat_len >= 0 and tail[index - pat_len : index] == pattern:
                count += 1
                index -= pat_len
                if count >= self.max_repeats:
                    return True
        return False


_INVOKE_CANDIDATE_RE = re.compile(
    r"</invoke(?=[\s>:/])|</parameter(?=[\s>])"
    r"|<invoke(?=[\s>:/])|<parameter(?=[\s>:/])"
)
_INVOKE_CLOSE_RE = re.compile(r"</invoke(?::[A-Za-z0-9_.\-]+)?\s*>")
_PARAMETER_CLOSE_RE = re.compile(r"</parameter\s*>")
_PARAMETER_RE = re.compile(
    r"<parameter\s+name\s*=\s*(?:\"([^\"]+)\"|'([^']+)')\s*>(.*?)</parameter\s*>",
    re.DOTALL,
)
_PARAMETER_SELF_RE = re.compile(
    r"<parameter\s+name\s*=\s*(?:\"([^\"]+)\"|'([^']+)')\s*/>"
)
_ATTR_NAME_RE = re.compile(r"\bname\s*=\s*(?:\"([^\"]+)\"|'([^']+)')")
_INVOKE_PREFIX_RE = re.compile(r"^<invoke:([A-Za-z0-9_.\-]+)")
_INVOKE_OPEN_INNER_RE = re.compile(r"<invoke(?::([A-Za-z0-9_.\-]+)|\s[^>]*)>")


def _coerce_parameter_value(raw: str) -> Any:
    """Значение `<parameter>`: строка; JSON — только если начинается с `{` или `[`."""
    value = raw.strip()
    if value[:1] in ("{", "["):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def _invoke_tag_name(tag: str) -> str:
    """Имя инструмента из открывающего тега `<invoke name=...>` / `<invoke:NAME>`."""
    prefix = _INVOKE_PREFIX_RE.match(tag)
    if prefix:
        return prefix.group(1).strip()
    attr = _ATTR_NAME_RE.search(tag)
    if attr:
        return (attr.group(1) or attr.group(2) or "").strip()
    return ""


def _nested_invoke_name(inner: str) -> str:
    """Имя из вложенного `<invoke ...>` (инцидент `<invoke:bash><invoke name=...>`)."""
    match = _INVOKE_OPEN_INNER_RE.search(inner)
    if not match:
        return ""
    if match.group(1):
        return match.group(1).strip()
    return _invoke_tag_name(match.group(0))


def _parse_invoke_arguments(inner: str) -> dict:
    """Содержимое блока `<invoke>` -> словарь аргументов из тегов `<parameter>`."""
    arguments: dict[str, Any] = {}
    for match in _PARAMETER_RE.finditer(inner):
        name = (match.group(1) or match.group(2) or "").strip()
        if name:
            arguments[name] = _coerce_parameter_value(match.group(3))
    for match in _PARAMETER_SELF_RE.finditer(inner):
        name = (match.group(1) or match.group(2) or "").strip()
        if name and name not in arguments:
            arguments[name] = ""
    if not arguments:
        body = inner.strip()
        if body[:1] == "{":
            try:
                parsed = json.loads(body)
            except ValueError:
                parsed = None
            if isinstance(parsed, dict):
                return parsed
    return arguments


def _find_tool_close_outside_string(text: str, start: int) -> int:
    """Позиция `</tool_call>` вне строковых литералов JSON в `text[start:]`, или -1.

    Закрывающий тег внутри JSON-строки (например значение аргумента содержит
    `</tool_call>`) границей блока не является. Экранированные кавычки `\\"`
    строку не закрывают.
    """
    index = start
    length = len(text)
    in_string = False
    escaped = False
    while index < length:
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif text.startswith(TOOL_CALL_CLOSE, index):
            return index
        index += 1
    return -1


class ToolCallParser:
    """Поток текстовых дельт -> content и завершённые вызовы инструментов.

    Тег <tool_call> может прийти разорванным между дельтами: хвост, который может
    оказаться началом тега, удерживается и не уходит в content до разрешения.

    `strict_live=True` (AD-002, только Droid stream=true с живым sink) запрещает
    malformed/unclosed recognized-блокам уйти в content как текст: вместо
    `_flush_all()`/raw-passthrough поднимается `LiveParserError`. `strict_live=False`
    (умолчание, legacy nonstream/без sink) ведёт себя абсолютно без изменений.
    """

    def __init__(
        self,
        on_content,
        on_tool_call,
        strict_live: bool = False,
        *,
        allowed_tools=None,
        tool_schemas=None,
        invoke_normalization_enabled: bool = True,
        repetition_guard_enabled: bool = True,
        max_repetition_repeats: int = DEFAULT_MAX_REPETITION_REPEATS,
        max_repetition_token_len: int = DEFAULT_MAX_REPETITION_TOKEN_LEN,
    ):
        self._buf = ""
        self._on_content = on_content
        self._on_tool_call = on_tool_call
        self.strict_live = strict_live
        self._history = ""  # весь текст, ушедший в content
        self._allowed_tools = (
            {str(name) for name in allowed_tools} if allowed_tools is not None else None
        )
        self._tool_schemas = tool_schemas
        self._invoke_enabled = bool(invoke_normalization_enabled)
        self._guard = (
            RepetitionGuard(
                max_repeats=max_repetition_repeats,
                max_token_len=max_repetition_token_len,
                enabled=True,
            )
            if repetition_guard_enabled
            else None
        )

    @property
    def repetition_detected(self) -> bool:
        """Guard зафиксировал цикл повторений в уже отданном content."""
        return bool(self._guard is not None and self._guard.detected)

    def _check_allowed(self, name: str) -> bool:
        """Whitelist `allowed_tools`: strict — ошибка, иначе вызов отбрасывается."""
        if self._allowed_tools is None or name in self._allowed_tools:
            return True
        if self.strict_live:
            raise LiveParserError(f"unauthorized tool: {name}")
        return False

    def _emit_invoke_call(self, name: str, arguments: dict) -> None:
        """Invoke-вызов -> плоский `{"id", "name", "arguments"}` в `on_tool_call`."""
        calls: list[dict] = [
            {"id": _new_call_id(), "name": name, "arguments": arguments}
        ]
        if self._tool_schemas is not None:
            calls = []
            for item in sanitize_tool_call(
                {"id": _new_call_id(), "name": name, "arguments": arguments},
                self._tool_schemas,
            ):
                item_name, item_args = _call_name_and_args(item)
                normalized = _normalize_arguments(item_args)
                calls.append(
                    {
                        "id": str(item.get("id") or _new_call_id())
                        if isinstance(item, dict)
                        else _new_call_id(),
                        "name": item_name,
                        "arguments": normalized if normalized is not None else {},
                    }
                )
        for call in calls:
            if call["name"] and self._check_allowed(call["name"]):
                self._history += _OPAQUE_BLOCK
                self._on_tool_call(call)

    def feed(self, text: str) -> None:
        self._buf += text
        self._drain(final=False)

    def finish(self) -> None:
        self._drain(final=True)

    def _classify_open(self, after: int, final: bool) -> str:
        """`<tool_call>` в буфере: "real" | "quoted" (inline-код markdown) | "wait" (нужен следующий символ)."""
        context = _code_context(self._history + self._buf, len(self._history), final)
        if context != "text":
            return "quoted" if context == "code" else "wait"
        tail = self._buf[after : after + 3]
        if not tail:
            return "real" if final else "wait"
        # ```json-обёртка внутри блока — настоящий вызов
        if tail[0] != "`" or tail == "```":
            return "real"
        if not final and tail == "`" * len(tail) and len(tail) < 3:
            return "wait"
        return "quoted"

    def _drain_invoke(self, final: bool, start: int) -> bool:
        """Разобрать invoke-тег в начале буфера; True — продолжить `_drain`."""
        if start > 0:
            self._emit(self._buf[:start])
            self._buf = self._buf[start:]
        context = _code_context(self._history + self._buf, len(self._history), final)
        if context == "code":
            self._emit(self._buf[:1])
            self._buf = self._buf[1:]
            return True
        if context == "wait":
            return False
        gt = self._buf.find(">")
        if gt == -1:
            if not final:
                return False
            if self.strict_live:
                raise LiveParserError("unclosed invoke tag")
            self._buf = ""
            return False
        tag = self._buf[: gt + 1]
        if tag.startswith("</"):
            self._buf = self._buf[gt + 1 :]
            self._history += _OPAQUE_BLOCK
            return True
        if tag.startswith("<parameter"):
            if self.strict_live:
                raise LiveParserError("parameter outside invoke")
            if tag[:-1].rstrip().endswith("/"):
                self._buf = self._buf[gt + 1 :]
                return True
            close = _PARAMETER_CLOSE_RE.search(self._buf, gt + 1)
            if close is None:
                if not final:
                    return False
                self._buf = ""
                return False
            self._buf = self._buf[close.end() :]
            return True
        name = _invoke_tag_name(tag)
        if tag[:-1].rstrip().endswith("/"):
            self._buf = self._buf[gt + 1 :]
            if not name:
                if self.strict_live:
                    raise LiveParserError("invoke without tool name")
                return True
            self._emit_invoke_call(name, {})
            return True
        close = _INVOKE_CLOSE_RE.search(self._buf, gt + 1)
        if close is None:
            if not final:
                return False
            if self.strict_live:
                raise LiveParserError("unclosed invoke block")
            self._buf = ""
            return False
        inner = self._buf[gt + 1 : close.start()]
        self._buf = self._buf[close.end() :]
        if not name:
            name = _nested_invoke_name(inner)
        if not name:
            if self.strict_live:
                raise LiveParserError("invoke without tool name")
            return True
        self._emit_invoke_call(name, _parse_invoke_arguments(inner))
        return True

    def _drain(self, final: bool) -> None:
        while True:
            invoke = (
                _INVOKE_CANDIDATE_RE.search(self._buf) if self._invoke_enabled else None
            )
            tc_start = self._buf.find(TOOL_CALL_OPEN)
            if invoke is not None and (tc_start == -1 or invoke.start() < tc_start):
                if self._drain_invoke(final, invoke.start()):
                    continue
                return
            start = tc_start
            if start == -1:
                if final:
                    if (
                        self.strict_live
                        and self._pending_prefix()
                        and not self._tail_in_code()
                    ):
                        raise LiveParserError("unresolved tool_call prefix at finish")
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
                # всё до тега завершено: текст уходит в content и в `_history`
                self._emit(self._buf[:start])
                self._buf = self._buf[start:]
            after = len(TOOL_CALL_OPEN)
            verdict = self._classify_open(after, final)
            if verdict == "quoted":
                self._emit(self._buf[:after])
                self._buf = self._buf[after:]
                continue
            if verdict == "wait":
                return
            end = self._find_close_outside_string(len(TOOL_CALL_OPEN))
            if end == -1:
                if final:
                    if self.strict_live:
                        raise LiveParserError("unclosed tool_call block")
                    self._flush_all()  # незакрытый/невалидный блок отдаём текстом
                return
            inner = self._buf[len(TOOL_CALL_OPEN) : end]
            self._buf = self._buf[end + len(TOOL_CALL_CLOSE) :]
            calls = _parse_tool_call_blocks(inner)
            if calls is None:
                if self.strict_live:
                    raise LiveParserError("malformed tool_call block")
                self._emit(TOOL_CALL_OPEN + inner + TOOL_CALL_CLOSE)
            else:
                if self._allowed_tools is not None and self.strict_live:
                    for call in calls:
                        self._check_allowed(str(call.get("name") or ""))
                self._history += _OPAQUE_BLOCK
                for call in calls:
                    if self._allowed_tools is not None and not self._check_allowed(
                        str(call.get("name") or "")
                    ):
                        continue
                    self._on_tool_call(call)

    def _find_close_outside_string(self, start: int) -> int:
        """Позиция `</tool_call>` вне строковых литералов JSON, или -1."""
        return _find_tool_close_outside_string(self._buf, start)

    def _pending_prefix(self) -> int:
        """Длина хвоста — префикса открывающего тега (его нельзя отдать в content)."""
        tags = [TOOL_CALL_OPEN]
        if self._invoke_enabled:
            tags += ["<invoke", "</invoke", "<parameter", "</parameter>"]
        best = 0
        for tag in tags:
            if self._buf.endswith(tag):
                best = max(best, len(tag))
                continue
            limit = min(len(tag) - 1, len(self._buf))
            for length in range(limit, 0, -1):
                if self._buf[-length:] == tag[:length]:
                    best = max(best, length)
                    break
        return best

    def _tail_in_code(self) -> bool:
        """Хвост-префикс тега в буфере лежит внутри markdown-кода."""
        doc = self._history + self._buf
        return _code_context(doc, len(doc) - self._pending_prefix(), True) == "code"

    def _emit(self, text: str) -> None:
        if text:
            self._history += text
            if self._guard is not None:
                _, detected = self._guard.feed(text)
                if detected and self.strict_live:
                    raise RepetitionLoopDetected(
                        "upstream_repetition_loop: excessive token repetitions"
                    )
            self._on_content(text)

    def _flush_all(self) -> None:
        if self._buf:
            text, self._buf = self._buf, ""
            self._emit(text)


# --- Универсальный live reasoning и вложения (ADR 0014 AD-003/AD-005) -----------
# Ядро окружение не читает: эффективные лимиты (env/конфиг) передаёт владелец
# маршрута параметрами; здесь только безопасные значения по умолчанию.
REASONING_TAGS = ("think", "thought", "thinking", "analysis")
DEFAULT_MAX_REASONING_DEPTH = 8
DEFAULT_MAX_IMAGES = 10
DEFAULT_MAX_IMAGE_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_TOTAL_IMAGE_BYTES = 20 * 1024 * 1024
# Служебные теги протокола <tool_call>, не имеющие смысла вне настоящего блока.
_ORPHAN_SERVICE_TAGS = (
    TOOL_CALL_CLOSE,
    "<arg_key>",
    "</arg_key>",
    "<arg_value>",
    "</arg_value>",
)
# (MIME, магические байты, расширение файла) — принимаемые форматы вложений.
_IMAGE_FORMATS = (
    ("image/png", b"\x89PNG\r\n\x1a\n", "png"),
    ("image/jpeg", b"\xff\xd8\xff", "jpg"),
)


class ImageInputError(ValueError):
    """Отказ валидации изображения запроса; `code` — машинный код причины."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _sniff_image_mime(data: bytes) -> str:
    """MIME по магическим байтам ('' — сигнатура неизвестна)."""
    for mime, magic, _ext in _IMAGE_FORMATS:
        if data.startswith(magic):
            return mime
    return ""


def extract_data_url_images(
    messages: Any,
    *,
    max_images: int = DEFAULT_MAX_IMAGES,
    max_image_bytes: int = DEFAULT_MAX_IMAGE_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_IMAGE_BYTES,
) -> list[dict]:
    """Все `image_url`-части истории -> [{"name", "mime", "data"}] в порядке появления.

    Принимаются только data URI с base64 PNG/JPEG: строгая проверка кодировки и
    соответствия MIME сигнатуре; URL не скачиваются, `file://` не читается,
    пользовательские пути не используются (имена генерируются: `image_N.<ext>`).
    Любое нарушение — `ImageInputError` до запуска CLI (fail-closed).
    """
    images: list[dict] = []
    total = 0
    if not isinstance(messages, list):
        return images
    for msg in messages:
        if not isinstance(msg, dict) or not isinstance(msg.get("content"), list):
            continue
        for item in msg["content"]:
            if not isinstance(item, dict) or item.get("type") != "image_url":
                continue
            image_url = item.get("image_url")
            url = image_url.get("url") if isinstance(image_url, dict) else None
            if not isinstance(url, str):
                raise ImageInputError("invalid_image_content")
            if not url.startswith("data:"):
                raise ImageInputError("image_url_not_allowed")
            comma = url.find(",")
            if comma == -1:
                raise ImageInputError("invalid_image_content")
            fields = [f.strip().lower() for f in url[5:comma].split(";")]
            mime = fields[0] if fields else ""
            if not mime or "base64" not in fields[1:]:
                raise ImageInputError("invalid_image_content")
            ext = next((e for m, _magic, e in _IMAGE_FORMATS if m == mime), "")
            if not ext:
                raise ImageInputError("unsupported_image_type")
            if len(images) >= max_images:
                raise ImageInputError("too_many_images")
            approx_bytes = (len(url) - comma - 1) * 3 // 4
            if approx_bytes > max_image_bytes:
                raise ImageInputError("image_too_large")
            if total + approx_bytes > max_total_bytes:
                raise ImageInputError("images_too_large")
            payload = url[comma + 1 :]
            if not payload:
                raise ImageInputError("invalid_image_base64")
            try:
                data = base64.b64decode(payload, validate=True)
            except (binascii.Error, ValueError):
                raise ImageInputError("invalid_image_base64") from None
            sniffed = _sniff_image_mime(data)
            if not sniffed:
                raise ImageInputError("unsupported_image_type")
            if sniffed != mime:
                raise ImageInputError("image_type_mismatch")
            if len(data) > max_image_bytes:
                raise ImageInputError("image_too_large")
            total += len(data)
            if total > max_total_bytes:
                raise ImageInputError("images_too_large")
            images.append(
                {"name": f"image_{len(images) + 1}.{ext}", "mime": mime, "data": data}
            )
    return images


def extract_thinking_delta(delta: Any) -> str:
    """Текст нативной дельты размышления (`thinking_delta`) -> строка; иначе ''.

    Транспортные адаптеры переводят свои события в общий словарь дельты; текст
    берётся из `thinking` (форма Claude stream-json) либо `thinking_delta`.
    """
    if not isinstance(delta, dict) or delta.get("type") != "thinking_delta":
        return ""
    value = delta.get("thinking")
    if value is None:
        value = delta.get("thinking_delta")
    return value if isinstance(value, str) else ""


class StreamNormalizer:
    """Единый нормализатор живого потока: content / reasoning / tool_calls (AD-005).

    Один лексический автомат на все выходы транспорта. В обычном тексте первая
    встреченная конструкция определяет контекст до своего закрытия: теги
    размышлений (`REASONING_TAGS`) уводят дельты в reasoning, блок `<tool_call>`
    непрозрачен и целиком уходит в `ToolCallParser` (тег размышления внутри
    JSON-строки аргумента канал не переключает; `<tool_call>` внутри размышления
    вызовом не становится). Теги в Markdown-коде каналом не являются (контекст —
    `_code_context`). Нативное thinking (`feed_thinking`) уже типизировано: в
    парсер не подаётся и не исполняется.

    Каждое событие сначала добавляется в аккумуляторы (`content`,
    `reasoning_content`, `tool_calls`), затем синхронно уведомляется sink:
    SSE-сериализатор публикует `delta.reasoning_content` сразу, до терминального
    события, JSON берёт тот же итог в `message.reasoning_content`; сумма
    SSE-дельт равна JSON-итогу при одинаковом входном потоке.

    При `strict_live=True` повреждённый/незакрытый блок, orphan служебный тег и
    EOF внутри размышления поднимают `LiveParserError` — сырой XML в content не
    попадает (fail-closed). Мысли не генерируются: upstream не дал — пусто.
    """

    def __init__(
        self,
        on_content=None,
        on_reasoning=None,
        on_tool_call=None,
        *,
        strict_live: bool = True,
        reasoning_tags=REASONING_TAGS,
        max_reasoning_depth: int = DEFAULT_MAX_REASONING_DEPTH,
    ):
        self._on_content = on_content or (lambda _text: None)
        self._on_reasoning = on_reasoning or (lambda _text: None)
        self._on_tool_call = on_tool_call or (lambda _call: None)
        self.strict_live = strict_live
        self._tags = tuple(reasoning_tags)
        self._max_depth = max(int(max_reasoning_depth), 1)
        self._parser = ToolCallParser(
            self._emit_content, self._emit_call, strict_live=strict_live
        )
        self._buf = ""
        self._state = "text"  # text | reasoning | tool
        self._tag = ""
        self._depth = 0
        self._doc = ""  # текст, уже ушедший в ToolCallParser (для _code_context)
        self._content_pieces: list[str] = []
        self._reasoning_pieces: list[str] = []
        self._calls: list[dict] = []
        candidates: list[tuple[str, str, str]] = []
        for tag in self._tags:
            candidates.append((f"<{tag}>", "reasoning_open", tag))
            candidates.append((f"</{tag}>", "orphan", tag))
        candidates.append((TOOL_CALL_OPEN, "tool_open", ""))
        candidates.extend((lit, "orphan", "") for lit in _ORPHAN_SERVICE_TAGS)
        self._candidates = candidates

    @property
    def content(self) -> str:
        return "".join(self._content_pieces)

    @property
    def reasoning_content(self) -> str:
        return "".join(self._reasoning_pieces)

    @property
    def tool_calls(self) -> list[dict]:
        return list(self._calls)

    def feed(self, text: str) -> None:
        self.feed_text(text)

    def feed_text(self, text: str) -> None:
        if text:
            self._buf += text
            self._drain(final=False)

    def feed_thinking(self, text: str) -> None:
        """Нативная дельта размышления транспорта (мимо парсера инструментов)."""
        if text:
            self._emit_reasoning(text)

    def feed_event_delta(self, delta: Any) -> None:
        """Словарь дельты транспорта: `thinking_delta` -> reasoning, `text_delta` -> текст."""
        thinking = extract_thinking_delta(delta)
        if thinking:
            self.feed_thinking(thinking)
        elif isinstance(delta, dict) and delta.get("type") == "text_delta":
            text = delta.get("text")
            if isinstance(text, str):
                self.feed_text(text)

    def finish(self) -> None:
        self._drain(final=True)
        self._parser.finish()

    # -- sink-и нормализатора: аккумулятор сначала, уведомление следом ----------
    def _emit_content(self, text: str) -> None:
        if text:
            self._content_pieces.append(text)
            self._on_content(text)

    def _emit_reasoning(self, text: str) -> None:
        if text:
            self._reasoning_pieces.append(text)
            self._on_reasoning(text)

    def _emit_call(self, call: dict) -> None:
        self._calls.append(call)
        self._on_tool_call(call)

    def _feed_parser(self, text: str) -> None:
        if text:
            # JSON вызова не участвует в Markdown-контексте последующего текста.
            self._doc += _OPAQUE_BLOCK if self._state == "tool" else text
            self._parser.feed(text)

    def _partial_prefix_len(self, literals) -> int:
        """Длина хвоста буфера — собственного префикса одного из литералов."""
        best = 0
        for literal in literals:
            limit = min(len(literal) - 1, len(self._buf))
            for length in range(limit, best, -1):
                if self._buf[-length:] == literal[:length]:
                    best = length
                    break
        return best

    def _drain(self, final: bool) -> None:
        while True:
            if self._state == "reasoning":
                if not self._drain_reasoning(final):
                    return
            elif self._state == "tool":
                if not self._drain_tool(final):
                    return
            elif not self._drain_text(final):
                return

    def _drain_text(self, final: bool) -> bool:
        """Шаг в обычном тексте; False — нужно ещё данных (или буфер пуст в финале)."""
        best_idx = -1
        best = None
        for literal, kind, tag in self._candidates:
            idx = self._buf.find(literal)
            if idx != -1 and (best_idx == -1 or idx < best_idx):
                best_idx, best = idx, (literal, kind, tag)
        if best is None:
            if final:
                literals = [
                    lit for lit, kind, _t in self._candidates if kind != "tool_open"
                ]
                if self.strict_live and self._partial_prefix_len(literals):
                    raise LiveParserError("unresolved reasoning tag prefix at finish")
                self._feed_parser(self._buf)
                self._buf = ""
                return False
            keep = self._partial_prefix_len([lit for lit, _k, _t in self._candidates])
            if keep:
                self._feed_parser(self._buf[:-keep])
                self._buf = self._buf[-keep:]
            else:
                self._feed_parser(self._buf)
                self._buf = ""
            return False
        if best_idx > 0:
            self._feed_parser(self._buf[:best_idx])
            self._buf = self._buf[best_idx:]
            return True
        literal, kind, tag = best
        context = _code_context(self._doc + self._buf, len(self._doc), final)
        if context == "wait":
            return False
        if context == "code":
            self._feed_parser(literal)
            self._buf = self._buf[len(literal) :]
            return True
        if kind == "reasoning_open":
            self._state, self._tag, self._depth = "reasoning", tag, 1
            self._buf = self._buf[len(literal) :]
            return True
        if kind == "tool_open":
            self._state = "tool"
            return True
        if self.strict_live:
            raise LiveParserError(f"orphan service tag: {literal.strip('<>/')}")
        self._feed_parser(literal)
        self._buf = self._buf[len(literal) :]
        return True

    def _drain_reasoning(self, final: bool) -> bool:
        """Шаг внутри размышления; тело выпускается инкрементально, держится только префикс тега."""
        open_lit, close_lit = f"<{self._tag}>", f"</{self._tag}>"
        idx_open, idx_close = self._buf.find(open_lit), self._buf.find(close_lit)
        found = [i for i in (idx_open, idx_close) if i != -1]
        if not found:
            if final:
                raise LiveParserError("unclosed reasoning tag")
            keep = self._partial_prefix_len((open_lit, close_lit))
            if keep:
                self._emit_reasoning(self._buf[:-keep])
                self._buf = self._buf[-keep:]
            else:
                self._emit_reasoning(self._buf)
                self._buf = ""
            return False
        idx = min(found)
        if idx > 0:
            self._emit_reasoning(self._buf[:idx])
            self._buf = self._buf[idx:]
            return True
        if self._buf.startswith(close_lit):
            self._depth -= 1
            self._buf = self._buf[len(close_lit) :]
            if self._depth == 0:
                self._state, self._tag = "text", ""
            return True
        self._depth += 1
        if self._depth > self._max_depth:
            raise LiveParserError("reasoning tags nested too deeply")
        self._buf = self._buf[len(open_lit) :]
        return True

    def _drain_tool(self, final: bool) -> bool:
        """Шаг внутри `<tool_call>`: блок непрозрачен, целиком уходит в ToolCallParser."""
        end = _find_tool_close_outside_string(self._buf, len(TOOL_CALL_OPEN))
        if end == -1:
            if final:
                # Финал решает сам парсер: настоящий незакрытый блок — LiveParserError,
                # процитированный в Markdown-коде — обычный текст.
                self._feed_parser(self._buf)
                self._buf = ""
                self._state = "text"
            return False
        self._feed_parser(self._buf[: end + len(TOOL_CALL_CLOSE)])
        self._buf = self._buf[end + len(TOOL_CALL_CLOSE) :]
        self._state = "text"
        return True


_PARALLEL_NAME = "parallel"
_PARALLEL_LIST_KEYS = ("tool_uses", "calls", "tools")
_SUBCALL_NAME_KEYS = ("recipient_name", "name")
_SUBCALL_ARGS_KEYS = ("parameters", "arguments")
# Умолчания лимитов распаковки `parallel`: не потолки, а значения по умолчанию параметров
# `max_parallel_calls`/`max_parallel_depth`. Ядро окружение не читает (BND-001) — эффективные
# значения (env `BRIDGE_MAX_PARALLEL_CALLS`/`BRIDGE_MAX_PARALLEL_DEPTH`) передаёт владелец маршрута.
DEFAULT_MAX_PARALLEL_CALLS = 64
DEFAULT_MAX_PARALLEL_DEPTH = 8
# Семантические payload-поля: пустая строка там может быть осмысленной нагрузкой.
PAYLOAD_FIELDS = frozenset({"prompt", "content", "command"})


def _new_call_id() -> str:
    return "call_" + uuid.uuid4().hex[:24]


def _call_name_and_args(tool_call: Any) -> tuple[str, Any]:
    """(имя, arguments) вызова — ToolCall либо OpenAI-словаря; ("", None) для чужого типа."""
    if isinstance(tool_call, ToolCall):
        return tool_call.function.name, tool_call.function.arguments
    if isinstance(tool_call, dict):
        fn = tool_call.get("function")
        if isinstance(fn, dict):
            return str(fn.get("name") or ""), fn.get("arguments")
        return str(tool_call.get("name") or ""), tool_call.get("arguments")
    return "", None


def _with_arguments(tool_call: Any, arguments: Any) -> Any:
    """Копия вызова с новыми arguments (тип и остальные поля вызова сохраняются)."""
    if isinstance(tool_call, ToolCall):
        return replace(
            tool_call, function=replace(tool_call.function, arguments=arguments)
        )
    if isinstance(tool_call.get("function"), dict):
        return dict(
            tool_call, function=dict(tool_call["function"], arguments=arguments)
        )
    return dict(tool_call, arguments=arguments)


def _make_call(template: Any, index: int, name: str, arguments: str) -> Any:
    """Новый вызов того же типа, что `template`, со свежим id `call_<hex>`."""
    if isinstance(template, ToolCall):
        return ToolCall(index, _new_call_id(), ToolFunction(name, arguments))
    call: dict[str, Any] = {
        "id": _new_call_id(),
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }
    if "index" in template:
        call["index"] = index
    return call


def _with_index(tool_call: Any, index: int) -> Any:
    if isinstance(tool_call, ToolCall):
        return replace(tool_call, index=index)
    return dict(tool_call, index=index) if "index" in tool_call else tool_call


def build_tool_schemas(tools: Any) -> dict[str, Any]:
    """`request.tools` (OpenAI) -> {имя: описание инструмента} для санитизации; чужие формы пропускаются."""
    schemas: dict[str, Any] = {}
    for tool in tools if isinstance(tools, list) else ():
        if not isinstance(tool, dict):
            continue
        fn = tool.get("function") if isinstance(tool.get("function"), dict) else tool
        name = fn.get("name")
        if isinstance(name, str) and name:
            schemas[name] = tool
    return schemas


def _parameters_schema(
    tool_name: str, tool_schemas: dict[str, Any] | None
) -> dict | None:
    """Объект `parameters` схемы инструмента; None — схемы для имени нет."""
    schema = (tool_schemas or {}).get(tool_name)
    if not isinstance(schema, dict):
        return None
    fn = schema.get("function") if isinstance(schema.get("function"), dict) else schema
    params = fn.get("parameters")
    return (
        params
        if isinstance(params, dict)
        and not any(
            key in params
            for key in (
                "$ref",
                "anyOf",
                "oneOf",
                "allOf",
                "if",
                "then",
                "else",
                "dependentRequired",
                "dependentSchemas",
            )
        )
        else None
    )


def _is_blank(value: Any) -> bool:
    return isinstance(value, str) and value.strip() == ""


def _is_string_property(prop: Any) -> bool:
    """Явно строковое свойство: `type == "string"` либо `"string"` в массиве `type`.

    Составные схемы, `$ref` и `enum` без явного строкового `type` — неразрешимы (fail-conservative).
    """
    if not isinstance(prop, dict) or any(
        key in prop for key in ("$ref", "anyOf", "oneOf", "allOf", "if", "then", "else")
    ):
        return False
    declared = prop.get("type")
    if isinstance(declared, list):
        return "string" in declared
    return declared == "string"


def _allows_blank(prop: dict) -> bool:
    """`const`/`enum` явно допускают пустую либо пробельную строку."""
    if "const" in prop and _is_blank(prop["const"]):
        return True
    enum = prop.get("enum")
    return isinstance(enum, list) and any(_is_blank(item) for item in enum)


def _is_protected(key: str, params: dict | None) -> bool:
    """Пустое значение нельзя считать отсутствием ключа (required, enum/const допускают '')."""
    if params is None:
        return False
    required = params.get("required")
    if isinstance(required, list) and key in required:
        return True
    properties = params.get("properties")
    prop = properties.get(key) if isinstance(properties, dict) else None
    return isinstance(prop, dict) and _allows_blank(prop)


def _is_removable_by_schema(key: str, params: dict | None) -> bool:
    """Пустое опциональное строковое поле, объявленное в `properties` схемы."""
    if params is None or key in PAYLOAD_FIELDS or _is_protected(key, params):
        return False
    properties = params.get("properties")
    return isinstance(properties, dict) and _is_string_property(properties.get(key))


def _sanitize_arguments_dict(args: dict, params: dict | None) -> dict:
    """Очистка пустых строк в аргументах; исходный словарь не меняется."""
    cleaned = dict(args)
    for key in list(cleaned):
        value = cleaned[key]
        if not _is_blank(value):
            continue
        if _is_removable_by_schema(key, params):
            del cleaned[key]
    return cleaned


def _sanitize_arguments(name: str, arguments: Any, tool_schemas: dict | None) -> Any:
    """arguments (JSON-строка либо dict) -> то же представление без пустых опциональных строк.

    Невалидные/не-объектные аргументы и аргументы без изменений возвращаются как есть.
    """
    parsed = _normalize_arguments(arguments)
    if parsed is None:
        return arguments
    cleaned = _sanitize_arguments_dict(parsed, _parameters_schema(name, tool_schemas))
    if cleaned == parsed:
        return arguments
    return (
        cleaned
        if isinstance(arguments, dict)
        else json.dumps(cleaned, ensure_ascii=False)
    )


def _unpack_parallel(tool_call: Any, arguments: Any, limit: int) -> list[Any] | None:
    """Вложенные вызовы `parallel` как вызовы верхнего уровня; None — распаковать нечего.

    Не более `limit` детей: превышение прекращает распаковку, накопленное сохраняется.
    """
    parsed = _normalize_arguments(arguments)
    if parsed is None:
        return None
    items = next(
        (
            parsed[key]
            for key in _PARALLEL_LIST_KEYS
            if isinstance(parsed.get(key), list)
        ),
        None,
    )
    calls: list[Any] = []
    for item in items or ():
        if len(calls) >= limit:
            break
        if not isinstance(item, dict):
            continue
        name = next((str(item[k]) for k in _SUBCALL_NAME_KEYS if item.get(k)), "")
        name = name.removeprefix("functions.").strip()
        if not name:
            continue
        sub_args = next((item[k] for k in _SUBCALL_ARGS_KEYS if k in item), None)
        if isinstance(sub_args, str):
            serialized = sub_args
        else:
            serialized = json.dumps(
                sub_args if sub_args is not None else {}, ensure_ascii=False
            )
        calls.append(_make_call(tool_call, len(calls), name, serialized))
    return calls or None


def _sanitize_call(
    tool_call: Any,
    tool_schemas: dict[str, Any] | None,
    depth: int,
    budget: list[int],
    max_depth: int,
) -> list[Any]:
    """`budget[0]` — сколько вызовов ещё можно опубликовать из текущего верхнего вызова."""
    name, arguments = _call_name_and_args(tool_call)
    if not name:
        return [tool_call]
    if name.rsplit(".", 1)[-1] == _PARALLEL_NAME and depth < max_depth:
        unpacked = _unpack_parallel(tool_call, arguments, max(budget[0], 0))
        if unpacked is not None:
            results: list[Any] = []
            for sub in unpacked:
                if budget[0] <= 0:
                    break
                results.extend(
                    _sanitize_call(sub, tool_schemas, depth + 1, budget, max_depth)
                )
            return results
    budget[0] -= 1
    cleaned = _sanitize_arguments(name, arguments, tool_schemas)
    return [tool_call if cleaned is arguments else _with_arguments(tool_call, cleaned)]


def sanitize_tool_call(
    tool_call: ToolCall | dict,
    tool_schemas: dict[str, Any] | None = None,
    *,
    max_parallel_calls: int = DEFAULT_MAX_PARALLEL_CALLS,
    max_parallel_depth: int = DEFAULT_MAX_PARALLEL_DEPTH,
) -> list[Any]:
    """Один вызов -> список вызовов того же типа (ToolCall либо dict) с чистыми аргументами.

    Чистая функция: синтетический `parallel` разворачивается во вложенные вызовы с новыми
    id (не более `max_parallel_calls` опубликованных вызовов и глубины `max_parallel_depth`;
    сверх лимита распаковка прекращается, накопленное возвращается). Пустые строки
    удаляются по схеме инструмента: поле объявлено в `properties` как строковое
    (`type == "string"` или `"string"` в массиве `type`), не входит в `required`, его
    `enum`/`const` не допускают пустую строку, это не payload-поле (`prompt`/`content`/
    `command`). Без схемы или при неразрешимой схеме (`anyOf`/`oneOf`/`$ref`) поля не трогаются
    (fail-conservative). Значения, в том числе justification, никогда не подставляются.
    Невалидные аргументы остаются нетронутыми (fail-safe), повторный вызов идемпотентен.
    """
    return _sanitize_call(
        tool_call,
        tool_schemas,
        0,
        [max(int(max_parallel_calls), 1)],
        max_parallel_depth,
    )


def sanitize_tool_calls_list(
    tool_calls: list[Any],
    tool_schemas: dict[str, Any] | None = None,
    *,
    max_parallel_calls: int = DEFAULT_MAX_PARALLEL_CALLS,
    max_parallel_depth: int = DEFAULT_MAX_PARALLEL_DEPTH,
) -> list[Any]:
    """Санитизация списка вызовов в плоский список; `index` перенумеровывается подряд."""
    flat = [
        result
        for tool_call in tool_calls
        for result in sanitize_tool_call(
            tool_call,
            tool_schemas,
            max_parallel_calls=max_parallel_calls,
            max_parallel_depth=max_parallel_depth,
        )
    ]
    return [_with_index(call, index) for index, call in enumerate(flat)]


def finalize_turn(
    raw: TurnResult,
    emulate_tools: bool,
    sanitize: bool = False,
    *,
    tool_schemas: dict[str, Any] | None = None,
    max_parallel_calls: int = DEFAULT_MAX_PARALLEL_CALLS,
    max_parallel_depth: int = DEFAULT_MAX_PARALLEL_DEPTH,
    allowed_tools=None,
    invoke_normalization_enabled: bool = True,
    repetition_guard_enabled: bool = True,
    max_repetition_repeats: int = DEFAULT_MAX_REPETITION_REPEATS,
    max_repetition_token_len: int = DEFAULT_MAX_REPETITION_TOKEN_LEN,
) -> TurnResult:
    """Сырой итог адаптера -> `out` фасада с буфером `events` (content/reasoning/tool_call).

    Готовый `out` (в нём уже есть `events`, как у droid-пути, где разбор идёт по потоку)
    возвращается без изменений. Для остальных: размышления идут мимо парсера, текст — через
    `ToolCallParser` при `emulate_tools`, вызовы получают `call_<hex>` как в droid-пути.
    При `sanitize` каждый вызов проходит `sanitize_tool_call` (в т.ч. распаковка `parallel`).
    """
    if raw.events is not None:
        return raw
    events: list[TurnEvent] = []
    tool_calls: list[ToolCall] = []
    pieces: list[str] = []
    reasoning = raw.reasoning
    if reasoning:
        events.append(TurnEvent("reasoning", reasoning))

    def add_content(text: str) -> None:
        if text:
            pieces.append(text)
            events.append(TurnEvent("content", text))

    def add_call(call: dict) -> None:
        entry = ToolCall(
            index=len(tool_calls),
            id=_new_call_id(),
            function=ToolFunction(
                call["name"], json.dumps(call["arguments"], ensure_ascii=False)
            ),
        )
        for item in (
            sanitize_tool_call(
                entry,
                tool_schemas,
                max_parallel_calls=max_parallel_calls,
                max_parallel_depth=max_parallel_depth,
            )
            if sanitize
            else [entry]
        ):
            item = replace(item, index=len(tool_calls))
            tool_calls.append(item)
            events.append(TurnEvent("tool_call", item))

    text = raw.text
    if emulate_tools:
        parser = ToolCallParser(
            add_content,
            add_call,
            allowed_tools=allowed_tools,
            tool_schemas=tool_schemas if sanitize else None,
            invoke_normalization_enabled=invoke_normalization_enabled,
            repetition_guard_enabled=repetition_guard_enabled,
            max_repetition_repeats=max_repetition_repeats,
            max_repetition_token_len=max_repetition_token_len,
        )
        parser.feed(text)
        parser.finish()
    else:
        add_content(text)
    return replace(
        raw, text="".join(pieces), tool_calls=tuple(tool_calls), events=tuple(events)
    )
