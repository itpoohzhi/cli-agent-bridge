"""Чистый доменный разбор XML-блоков ``<invoke>`` и ``<execute>``."""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

from core.tool_call_schema_policy import JsonMap, canonicalize_tool_invocation

INVOKE_CANDIDATE_RE = re.compile(
    r"</invoke(?=[\s>:/])|</parameter(?=[\s>])|<invoke(?=[\s>:/])|<parameter(?=[\s>:/])"
    r"|</execute(?=[\s>])|<execute(?=[\s>:/])|</command(?=[\s>])|<command(?=[\s>])"
    r"|</summary(?=[\s>])|<summary(?=[\s>])",
    re.IGNORECASE,
)
INVOKE_CLOSE_RE = re.compile(r"</invoke(?::[A-Za-z0-9_.\-]+)?\s*>")
PARAMETER_CLOSE_RE = re.compile(r"</parameter\s*>")
PARAMETER_RE = re.compile(r"<parameter\s+name\s*=\s*(?:\"([^\"]+)\"|'([^']+)')\s*>(.*?)</parameter\s*>", re.DOTALL)
PARAMETER_SELF_RE = re.compile(r"<parameter\s+name\s*=\s*(?:\"([^\"]+)\"|'([^']+)')\s*/>")
ATTR_NAME_RE = re.compile(r"\bname\s*=\s*(?:\"([^\"]+)\"|'([^']+)')")
INVOKE_PREFIX_RE = re.compile(r"^<invoke:([A-Za-z0-9_.\-]+)")
INVOKE_OPEN_INNER_RE = re.compile(r"<invoke(?::([A-Za-z0-9_.\-]+)|\s[^>]*)>")
COMMAND_TAG_RE = re.compile(r"<\s*command(?:\s+[^>]*)?\s*>(.*?)</\s*command\s*>", re.DOTALL | re.IGNORECASE)
COMMAND_CLOSE_RE = re.compile(r"</\s*command\s*>", re.IGNORECASE)
SUMMARY_TAG_RE = re.compile(r"<\s*summary(?:\s+[^>]*)?\s*>(.*?)</\s*summary\s*>", re.DOTALL | re.IGNORECASE)
SUMMARY_CLOSE_RE = re.compile(r"</summary\s*>", re.IGNORECASE)
EXECUTE_OPEN_RE = re.compile(r"<execute(?::([A-Za-z0-9_.\-]+)|(\s[^>]*))?>", re.IGNORECASE)
EXECUTE_CLOSE_RE = re.compile(r"</execute\s*>", re.IGNORECASE)
SUMMARY_TAG_BOUNDARY_RE = re.compile(r"<\s*(/)?\s*summary(?:\s+[^>]*)?\s*>", re.IGNORECASE)
_INJECTED_XML_IN_SUMMARY_RE = re.compile(r"<\s*/?\s*(?:summary|command|parameter|invoke|execute)\b", re.IGNORECASE)
_OPAQUE_BLOCK = "￼"


class InvokeDrainParser(Protocol):
    """Контракт состояния потокового парсера для ``drain_invoke``."""

    _buf: str
    strict_live: bool
    _tool_schemas: JsonMap | None

    def _emit(self, text: str) -> None: ...
    def _classify_open(self, after: int, final: bool) -> str: ...
    def _remember(self, text: str) -> None: ...
    def _emit_invoke_call(self, name: str, arguments: dict[str, Any]) -> None: ...
    def _parse_error(self, message: str) -> Exception: ...


def coerce_parameter_value(raw: str) -> Any:
    """Значение ``<parameter>``: строка; JSON — только если начинается с ``{`` или ``[``."""
    value = raw.strip()
    if value[:1] in ("{", "["):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def invoke_tag_name(tag: str) -> str:
    """Имя инструмента из открывающего тега ``<invoke name=...>`` / ``<invoke:NAME>``."""
    if prefix := INVOKE_PREFIX_RE.match(tag):
        return prefix.group(1).strip()
    attr = ATTR_NAME_RE.search(tag)
    return (attr.group(1) or attr.group(2) or "").strip() if attr else ""


def nested_invoke_name(inner: str) -> str:
    """Имя из вложенного ``<invoke ...>``."""
    match = INVOKE_OPEN_INNER_RE.search(inner)
    return (match.group(1).strip() if match.group(1) else invoke_tag_name(match.group(0))) if match else ""


def strip_summary_blocks(text: str) -> str:
    """Полностью удаляет все блоки ``<summary>...</summary>``, включая вложенные и незакрытые."""
    res: list[str] = []
    depth = pos = 0
    for match in SUMMARY_TAG_BOUNDARY_RE.finditer(text):
        if depth == 0:
            res.append(text[pos : match.start()])
        depth = depth - 1 if match.group(1) and depth > 0 else (depth + 1 if not match.group(1) else 0)
        pos = match.end()
    if depth == 0:
        res.append(text[pos:])
    return "".join(res)


def _extract_plain_summary(inner: str) -> str:
    match = SUMMARY_TAG_RE.search(inner)
    if match is None:
        return ""
    text = match.group(1).strip()
    return "" if (not text or _INJECTED_XML_IN_SUMMARY_RE.search(text)) else text


def _parse_json_fallback(cleaned: str, summary_text: str) -> dict[str, Any] | None:
    body = cleaned.strip()
    if body[:1] != "{":
        return None
    try:
        parsed = json.loads(body)
    except ValueError:
        return None
    if not isinstance(parsed, dict):
        return None
    if summary_text and "summary" not in parsed:
        parsed["summary"] = summary_text
    return parsed


def parse_invoke_arguments(inner: str) -> dict[str, Any]:
    """Содержимое ``<invoke>``/``<execute>`` -> аргументы; ``<summary>`` читается до вырезания."""
    summary_text = _extract_plain_summary(inner)
    cleaned = strip_summary_blocks(inner)
    arguments: dict[str, Any] = {}
    for match in PARAMETER_RE.finditer(cleaned):
        if name := (match.group(1) or match.group(2) or "").strip():
            arguments[name] = coerce_parameter_value(match.group(3))
    for match in PARAMETER_SELF_RE.finditer(cleaned):
        if (name := (match.group(1) or match.group(2) or "").strip()) and name not in arguments:
            arguments[name] = ""
    if (cmd := COMMAND_TAG_RE.search(cleaned)) is not None and "command" not in arguments:
        arguments["command"] = cmd.group(1).strip()
    if not arguments and (parsed := _parse_json_fallback(cleaned, summary_text)) is not None:
        return parsed
    if summary_text and "summary" not in arguments:
        arguments["summary"] = summary_text
    return arguments


def parse_execute_block(buf: str, start: int = 0, tool_schemas: JsonMap | None = None) -> tuple[dict[str, Any] | None, int] | None:
    """Разбирает ``<execute ...>...</execute>`` с канонизацией по ``tool_schemas``."""
    open_match = EXECUTE_OPEN_RE.match(buf, start)
    close_match = EXECUTE_CLOSE_RE.search(buf, open_match.end()) if open_match is not None else None
    if open_match is None or close_match is None:
        return None
    name = open_match.group(1)
    if not name and open_match.group(2):
        attr = ATTR_NAME_RE.search(open_match.group(2))
        name = (attr.group(1) or attr.group(2) or "").strip() if attr is not None else ""
    raw_args = parse_invoke_arguments(buf[open_match.end() : close_match.start()])
    canon_name, canon_args = canonicalize_tool_invocation(name or "bash", raw_args, tool_schemas)
    if canon_name == "bash" and "command" not in canon_args:
        return None, close_match.end()
    return {"name": canon_name, "arguments": canon_args}, close_match.end()


def _drain_unclosed(parser: InvokeDrainParser, final: bool, error_msg: str) -> bool:
    if final and parser.strict_live:
        raise parser._parse_error(error_msg)
    if final:
        parser._buf = ""
    return False


def _drain_execute_tag(parser: InvokeDrainParser, final: bool) -> bool:
    res = parse_execute_block(parser._buf, 0, tool_schemas=parser._tool_schemas)
    if res is None:
        return _drain_unclosed(parser, final, "unclosed execute block")
    call, next_idx = res
    parser._buf = parser._buf[next_idx:]
    if call is not None:
        parser._emit_invoke_call(call["name"], call["arguments"])
    return True


def _drain_orphan_xml_tag(parser: InvokeDrainParser, tag: str, gt: int, final: bool) -> bool:
    if parser.strict_live:
        raise parser._parse_error("parameter outside invoke")
    if tag[:-1].rstrip().endswith("/"):
        parser._buf = parser._buf[gt + 1 :]
        return True
    low = tag.lower()
    close_re = COMMAND_CLOSE_RE if low.startswith("<command") else (SUMMARY_CLOSE_RE if low.startswith("<summary") else PARAMETER_CLOSE_RE)
    close = close_re.search(parser._buf, gt + 1)
    if close is None:
        return _drain_unclosed(parser, final, "")
    parser._buf = parser._buf[close.end() :]
    return True


def _drain_invoke_tag(parser: InvokeDrainParser, tag: str, gt: int, final: bool) -> bool:
    name = invoke_tag_name(tag)
    if tag[:-1].rstrip().endswith("/"):
        parser._buf = parser._buf[gt + 1 :]
        if not name and parser.strict_live:
            raise parser._parse_error("invoke without tool name")
        if name:
            canon_name, canon_args = canonicalize_tool_invocation(name, {}, parser._tool_schemas)
            parser._emit_invoke_call(canon_name, canon_args)
        return True
    close = INVOKE_CLOSE_RE.search(parser._buf, gt + 1)
    if close is None:
        return _drain_unclosed(parser, final, "unclosed invoke block")
    inner = parser._buf[gt + 1 : close.start()]
    parser._buf = parser._buf[close.end() :]
    name = name or nested_invoke_name(inner)
    if not name and parser.strict_live:
        raise parser._parse_error("invoke without tool name")
    if name:
        canon_name, canon_args = canonicalize_tool_invocation(name, parse_invoke_arguments(inner), parser._tool_schemas)
        parser._emit_invoke_call(canon_name, canon_args)
    return True


def drain_invoke(parser: InvokeDrainParser, final: bool, start: int) -> bool:
    """Разобрать XML-тег в начале буфера парсера; ``True`` — продолжить ``_drain``."""
    if start > 0:
        parser._emit(parser._buf[:start])
        parser._buf = parser._buf[start:]
    verdict = parser._classify_open(0, final)
    if verdict != "real":
        if verdict == "quoted":
            parser._emit(parser._buf[:1])
            parser._buf = parser._buf[1:]
        return verdict == "quoted"
    gt = parser._buf.find(">")
    if gt == -1:
        return _drain_unclosed(parser, final, "unclosed invoke tag")
    tag = parser._buf[: gt + 1]
    if tag.startswith("</"):
        parser._buf = parser._buf[gt + 1 :]
        parser._remember(_OPAQUE_BLOCK)
        return True
    low = tag.lower()
    if low.startswith("<execute"):
        return _drain_execute_tag(parser, final)
    if low.startswith(("<parameter", "<command", "<summary")):
        return _drain_orphan_xml_tag(parser, tag, gt, final)
    return _drain_invoke_tag(parser, tag, gt, final)
