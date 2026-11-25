"""Чистый Zero-I/O ремонт JSON-escape, неэкранированных `"` и EOF-поиск нечётных `"`."""

# fmt: off
from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Final, cast

from core.tool_trailing_semicolon_repair import has_single_trailing_quote_suffix, has_single_trailing_suffix, strip_single_trailing_suffix
DEFAULT_MAX_QUOTE_CANDIDATES: Final[int] = 128
DEFAULT_MAX_VERIFY_CHARS: Final[int] = 65536
DEFAULT_MAX_NESTING_DEPTH: Final[int] = 32
DEFAULT_MAX_ODD_CLOSE_CANDIDATES: Final[int] = 16
_MAX_EXTRA_BRACES: Final[int] = 16
_JSON_MARKERS: Final[re.Pattern[str]] = re.compile(r'["\\<]')
_ESC_QUOTE_RE: Final[re.Pattern[str]] = re.compile(r'\\.|"')
_STR_LIT_RE: Final[re.Pattern[str]] = re.compile(r'"(?:[^"\\]|\\.)*"?')
_IN_STR_ESC_RE: Final[re.Pattern[str]] = re.compile(r'\\(?:u[0-9a-fA-F]{4}|["\\/bfnrt]|.)')
_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r'[\{\[\}\]:,]|"(?:[^"\\]|\\.)*"?')
_NON_WS_RE: Final[re.Pattern[str]] = re.compile(r"[^ \t\r\n]")
_KEY_COLON_RE: Final[re.Pattern[str]] = re.compile(r'"(?:[^"\\\n]|\\.)*"\s*:')


def _fix_one_escape(match: re.Match[str]) -> str:
    seq = match.group(0)
    return "'" if seq == "\\'" else (seq if (len(seq) == 6 or seq[1] in '"\\/bfnrt') else "\\" + seq)


def repair_invalid_json_escapes(text: str) -> str:
    """String-aware O(N) ремонт невалидных JSON-escape: `\\'` -> `'`, прочие `\\<c>` -> `\\\\<c>`."""
    if "\\" not in text:
        return text
    return _STR_LIT_RE.sub(lambda m: _IN_STR_ESC_RE.sub(_fix_one_escape, m.group(0)), text)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    obj: dict[str, object] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate key: {key}")
        obj[key] = value
    return obj


def _loads_no_dup(text: str) -> tuple[bool, object]:
    try:
        return True, cast("object", json.loads(text, strict=False, object_pairs_hook=_reject_duplicate_keys))
    except (ValueError, RecursionError):
        body = text.lstrip()
        try:
            obj, end = cast("tuple[object, int]", json.JSONDecoder(strict=False, object_pairs_hook=_reject_duplicate_keys).raw_decode(body))
        except (ValueError, RecursionError):
            return False, None
        tail = body[end:]
        ok = isinstance(obj, dict) and 1 <= tail.count("}") <= _MAX_EXTRA_BRACES and not tail.strip(" \t\r\n}")
        return (True, obj) if ok else (False, None)


def _step_quote_in_frame(raw: str, pos: int, frames: list[list[object]]) -> tuple[tuple[int, tuple[str, ...], frozenset[str]] | None, bool]:
    top = frames[-1]
    keys = cast("set[str]", top[2])
    if top[0] == "{" and top[1] is True:
        if len(raw) >= 2 and raw[-1] == '"':
            try:
                key = cast("object", json.loads(raw, strict=False))
            except ValueError:
                key = None
            if isinstance(key, str):
                if key in keys:
                    return None, False
                keys.add(key)
        return None, True
    return (pos, tuple(cast("str", f[0]) for f in frames), frozenset(keys)), True


def _step_structural(tok: str, frames: list[list[object]]) -> bool:
    if tok in "{[":
        if len(frames) >= DEFAULT_MAX_NESTING_DEPTH:
            return False
        frames.append([tok, tok == "{", set()])
        return True
    if tok in "}]":
        if not frames:
            return False
        _ = frames.pop()
        return True
    if frames and frames[-1][0] == "{":
        frames[-1][1] = tok == ","
    return True


def _locate_broken_value_string(text: str, err_pos: int) -> tuple[int, tuple[str, ...], frozenset[str]] | None:
    frames: list[list[object]] = []
    last_val: tuple[int, tuple[str, ...], frozenset[str]] | None = None
    for m in _TOKEN_RE.finditer(text, 0, min(err_pos, len(text))):
        tok = m.group(0)
        if tok in "{[]}:,":
            if not _step_structural(tok, frames):
                return None
            last_val = last_val if tok == "," else None
        elif frames:
            val, ok = _step_quote_in_frame(tok, m.start(), frames)
            if not ok:
                return None
            last_val = val or last_val
    return last_val


def _is_close_boundary(text: str, pos: int, container: str) -> bool:
    m = _NON_WS_RE.search(text, pos + 1)
    if m is None:
        return False
    ch = text[m.start()]
    if container != "{":
        return ch in "],"
    if ch == "}":
        return True
    m2 = _NON_WS_RE.search(text, m.start() + 1) if ch == "," else None
    return m2 is not None and (text[m2.start()] == "}" or _KEY_COLON_RE.match(text, m2.start()) is not None)


def _collect_close_candidates(text: str, val_start: int, container: str, max_candidates: int) -> list[int] | None:
    candidates: list[int] = []
    for m in _ESC_QUOTE_RE.finditer(text, val_start + 1):
        if m.group(0) == '"' and _is_close_boundary(text, m.start(), container):
            candidates.append(m.start())
            if len(candidates) > max_candidates:
                return None
    return candidates


def _descend_sibling(cur: object, idx: int, ch: str) -> tuple[bool, object]:
    if ch == "{" and isinstance(cur, dict):
        return True, cast("dict[str, object]", cur).get(f"__k{idx}__")
    if ch == "[" and isinstance(cur, list) and cur:
        return True, cast("list[object]", cur)[0]
    return False, None


def _extract_sibling_keys(parsed: object, stack: tuple[str, ...]) -> frozenset[str]:
    cur: object = parsed
    for idx, ch in enumerate(stack[:-1]):
        ok, cur = _descend_sibling(cur, idx, ch)
        if not ok:
            return frozenset()
    if stack[-1] != "{" or not isinstance(cur, dict):
        return frozenset()
    return frozenset(cast("dict[str, object]", cur).keys() - {"__v__"})


def _verify_candidates(text: str, stack: tuple[str, ...], candidates: list[int]) -> list[tuple[int, frozenset[str]]] | None:
    last = len(stack) - 1
    prefix = "".join(('{"__v__":"' if i == last else f'{{"__k{i}__":') if c == "{" else ('["' if i == last else "[") for i, c in enumerate(stack))
    budget, spent, valid = max(len(text) * 4, DEFAULT_MAX_VERIFY_CHARS), 0, []
    for q in candidates:
        suffix = text[q:]
        spent += len(prefix) + len(suffix)
        if spent > budget:
            return None
        ok, parsed = _loads_no_dup(prefix + suffix)
        if ok:
            valid.append((q, _extract_sibling_keys(parsed, stack)))
    return valid


def _matches_schema(
    cand: tuple[int, frozenset[str]], valid: list[tuple[int, frozenset[str]]],
    prior: frozenset[str], allowed: frozenset[str], req: frozenset[str],
) -> bool:
    q, sib = cand
    return bool(sib) and sib <= allowed and req <= (prior | sib) and all((s & allowed) < sib for q_o, s in valid if q_o != q)


def _select_candidate(
    valid: list[tuple[int, frozenset[str]]], prior_keys: frozenset[str],
    allowed: frozenset[str] | None, required: frozenset[str] | None,
) -> int | None:
    if not valid or any(sib & prior_keys for _q, sib in valid):
        return None
    if len(valid) == 1:
        return valid[0][0]
    if allowed is None:
        return None
    req = required or frozenset()
    winners = [q for q, s in valid if _matches_schema((q, s), valid, prior_keys, allowed, req)]
    return winners[0] if len(winners) == 1 else None


def repair_unescaped_json_quotes(
    text: str, *, allowed_arg_keys: frozenset[str] | None = None,
    required_arg_keys: frozenset[str] | None = None, max_candidates: int = DEFAULT_MAX_QUOTE_CANDIDATES,
) -> str | None:
    """Fail-closed O(N) ремонт неэкранированных `"` в одном строковом значении JSON."""
    try:
        _ = json.loads(text, strict=False)
        return None
    except json.JSONDecodeError as exc:
        located = _locate_broken_value_string(text, exc.pos)
    except (ValueError, RecursionError):
        return None
    if located is None:
        return None
    val_start, stack, prior_keys = located
    candidates = _collect_close_candidates(text, val_start, stack[-1], max_candidates)
    valid = _verify_candidates(text, stack, candidates) if candidates else None
    q_win = _select_candidate(valid, prior_keys, allowed_arg_keys, required_arg_keys) if valid else None
    if q_win is None:
        return None
    body = _ESC_QUOTE_RE.sub(lambda m: m.group(0) if m.group(0)[0] == "\\" else '\\"', text[val_start + 1 : q_win])
    repaired = repair_invalid_json_escapes(text[: val_start + 1] + body + text[q_win:])
    return repaired if _loads_no_dup(repaired)[0] else None


def repair_json_quotes_strict(
    raw_text: str, escaped_text: str, *,
    allowed_arg_keys: frozenset[str] | None = None,
    required_arg_keys: frozenset[str] | None = None,
) -> str | None:
    if has_single_trailing_suffix(raw_text):
        return strip_single_trailing_suffix(raw_text)
    return repair_unescaped_json_quotes(
        escaped_text, allowed_arg_keys=allowed_arg_keys, required_arg_keys=required_arg_keys
    )


def resolve_odd_quote_tool_close(
    buf: str, start: int, close_tag: str, parse_fn: Callable[[str], object | None]
) -> int:
    """На EOF ищет строго единственное валидное закрытие `close_tag` после `}`."""
    if not close_tag:
        return -1
    candidates: list[int] = []
    pos = buf.find(close_tag, start)
    while pos != -1:
        raw_prefix = buf[start:pos].rstrip(" \t\r\n")
        prefix = raw_prefix[:-3].rstrip(" \t\r\n") if raw_prefix.endswith(("```", "~~~")) else raw_prefix
        if prefix.endswith("}") or has_single_trailing_quote_suffix(raw_prefix):
            candidates.append(pos)
            if len(candidates) > DEFAULT_MAX_ODD_CLOSE_CANDIDATES:
                return -1
        pos = buf.find(close_tag, pos + 1)
    valid = [end for end in candidates if parse_fn(buf[start:end]) is not None]
    return valid[0] if len(valid) == 1 else -1


class ActiveBlockScanner:
    """Инкрементальный O(N) сканер активного `<tool_call>` для ToolCallParser."""

    __slots__ = ("_close_tail", "close_tag", "escaped", "in_string", "open_tag", "parts")

    def __init__(self, open_tag: str = "<tool_call>", close_tag: str = "</tool_call>") -> None:
        self.parts: list[str] = []
        self.reset(open_tag, close_tag)

    def reset(self, open_tag: str, close_tag: str) -> None:
        self.open_tag, self.close_tag, self.in_string, self.escaped, self._close_tail = open_tag, close_tag, False, False, ""
        self.parts.clear()

    def unclosed_text(self) -> str:
        return "".join(self.parts) + self._close_tail

    def _step_char(self, text: str, index: int) -> tuple[int, tuple[str | None, str] | None]:
        char = text[index]
        if char == "\\" and self.in_string:
            self.escaped = index + 2 > len(text)
            return index + 2, None
        if char == '"':
            self.in_string = not self.in_string
            return index + 1, None
        if char == "<" and not self.in_string:
            tail = text[index:]
            if len(tail) < len(self.close_tag) and self.close_tag.startswith(tail):
                self.parts.append(text[:index])
                self._close_tail = tail
                return index, (None, "")
            if tail.startswith(self.close_tag):
                self.parts.append(text[:index])
                inner = "".join(self.parts)
                self.parts.clear()
                return index, (inner, text[index + len(self.close_tag) :])
        return index + 1, None

    def feed(self, text: str) -> tuple[str | None, str]:
        text, self._close_tail = (self._close_tail + text, "") if self._close_tail else (text, "")
        index = 1 if (self.escaped and text) else 0
        self.escaped = False if index else self.escaped
        while (match := _JSON_MARKERS.search(text, index)) is not None:
            index, result = self._step_char(text, match.start())
            if result is not None:
                return result
        self.parts.append(text)
        return None, ""

    def recover_odd_close(self, parse_fn: Callable[[str], object | None]) -> tuple[str, str] | None:
        raw = self.unclosed_text()
        end = resolve_odd_quote_tool_close(raw, 0, self.close_tag, parse_fn)
        return None if end == -1 else (raw[:end], raw[end + len(self.close_tag) :])
