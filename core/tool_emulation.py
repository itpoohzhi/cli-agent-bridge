"""Общее ядро эмуляции OpenAI function calling (чистые функции, без I/O).

Единый источник для всех бэкендов хаба: рендер истории и протокола инструментов в
текстовый промпт, разбор блоков `<tool_call>…</tool_call>` из потока текстовых дельт.
Модуль не импортирует `server` и адаптеры; `server.py` реэкспортирует имена для
существующих тестов и совместимости.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import replace
from typing import Any
from core.backend_adapter import ToolCall, ToolFunction, TurnEvent, TurnResult

TOOL_CALL_OPEN = "<tool_call>"
TOOL_CALL_CLOSE = "</tool_call>"


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


class ToolCallParser:
    """Поток текстовых дельт -> content и завершённые вызовы инструментов.

    Тег <tool_call> может прийти разорванным между дельтами: хвост, который может
    оказаться началом тега, удерживается и не уходит в content до разрешения.

    `strict_live=True` (AD-002, только Droid stream=true с живым sink) запрещает
    malformed/unclosed recognized-блокам уйти в content как текст: вместо
    `_flush_all()`/raw-passthrough поднимается `LiveParserError`. `strict_live=False`
    (умолчание, legacy nonstream/без sink) ведёт себя абсолютно без изменений.
    """

    def __init__(self, on_content, on_tool_call, strict_live: bool = False):
        self._buf = ""
        self._on_content = on_content
        self._on_tool_call = on_tool_call
        self.strict_live = strict_live
        self._history = ""  # весь текст, ушедший в content

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

    def _drain(self, final: bool) -> None:
        while True:
            start = self._buf.find(TOOL_CALL_OPEN)
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
                self._history += _OPAQUE_BLOCK
                for call in calls:
                    self._on_tool_call(call)

    def _find_close_outside_string(self, start: int) -> int:
        """Позиция `</tool_call>` вне строковых литералов JSON, или -1.

        Закрывающий тег внутри JSON-строки (например значение аргумента содержит
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

    def _tail_in_code(self) -> bool:
        """Хвост-префикс тега в буфере лежит внутри markdown-кода."""
        doc = self._history + self._buf
        return _code_context(doc, len(doc) - self._pending_prefix(), True) == "code"

    def _emit(self, text: str) -> None:
        if text:
            self._history += text
            self._on_content(text)

    def _flush_all(self) -> None:
        if self._buf:
            text, self._buf = self._buf, ""
            self._emit(text)


def finalize_turn(raw: TurnResult, emulate_tools: bool) -> TurnResult:
    """Сырой итог адаптера -> `out` фасада с буфером `events` (content/reasoning/tool_call).

    Готовый `out` (в нём уже есть `events`, как у droid-пути, где разбор идёт по потоку)
    возвращается без изменений. Для остальных: размышления идут мимо парсера, текст — через
    `ToolCallParser` при `emulate_tools`, вызовы получают `call_<hex>` как в droid-пути.
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
            id="call_" + uuid.uuid4().hex[:24],
            function=ToolFunction(
                call["name"], json.dumps(call["arguments"], ensure_ascii=False)
            ),
        )
        tool_calls.append(entry)
        events.append(TurnEvent("tool_call", entry))

    text = raw.text
    if emulate_tools:
        parser = ToolCallParser(add_content, add_call)
        parser.feed(text)
        parser.finish()
    else:
        add_content(text)
    return replace(
        raw, text="".join(pieces), tool_calls=tuple(tool_calls), events=tuple(events)
    )
