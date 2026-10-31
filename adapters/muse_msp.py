"""Чистая аккумуляция MSP v1: append-only reasoning, snapshots и бюджеты ADR 0012."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterator

MAX_TRACKED_ITEMS = 1024
LIVE_DELTA_MAX_BYTES = 8 << 10
REASONING_TRUNCATED = "\n[reasoning truncated: reasoning budget reached]\n"
SNAPSHOT_DIVERGED = "\n[reasoning snapshot diverged; live prefix preserved]\n"
_TOOL_NAME = re.compile(r"[A-Za-z0-9_.:-]{1,64}")
_SUMMARY_FIELD = re.compile(r"summary\.([0-9]{1,4})")


def utf8_slices(text: str, max_bytes: int = LIVE_DELTA_MAX_BYTES) -> Iterator[str]:
    """Разрезать текст по кодовым точкам, ограничив каждый UTF-8 кусок в байтах."""
    if max_bytes < 4:
        raise ValueError("UTF-8 chunk budget must be at least four bytes")
    # Окно символов ограничено max_bytes: полный многомегабайтный encode не нужен.
    offset = 0
    while offset < len(text):
        window = text[offset : offset + max_bytes]
        piece = window.encode("utf-8")[:max_bytes].decode("utf-8", "ignore")
        yield piece
        offset += len(piece)


@dataclass
class _Item:
    kind: str
    tool_name: str = "unknown_tool"
    started: bool = False
    completed: bool = False
    parts: dict[int, list[str]] = field(default_factory=dict)


class MspEvents:
    """Один ход MSP. Возвращаемая из feed строка — только новый хвост reasoning.

    Порядок — порядок поступления событий, ключ сверки snapshot — (itemId, summary.N).
    Уже опубликованные символы никогда не перезаписываются; повторный completed
    идемпотентен. Аргументы toolCall не сохраняются и не форматируются.
    """

    def __init__(self, *, reasoning_cap: int, answer_cap: int) -> None:
        self.reasoning_cap = reasoning_cap
        self.answer_cap = answer_cap
        self.live_degraded = False
        self.has_executed_tool = False
        self.terminal: str | None = None
        self._items: dict[str, _Item] = {}
        self._keys = 0
        self._reasoning: list[str] = []
        self._reasoning_bytes = 0
        self._truncated = False
        self._answers: dict[str, list[str]] = {}
        self._answer_sizes: dict[str, int] = {}
        self._answer_bytes = 0

    @property
    def reasoning(self) -> str:
        return "".join(self._reasoning)

    @property
    def text(self) -> str:
        return "".join(piece for pieces in self._answers.values() for piece in pieces)

    @property
    def tracked_count(self) -> int:
        return max(len(self._items), self._keys)

    def _append(self, text: str) -> str:
        if self._truncated or not text:
            return ""
        marker_bytes = len(REASONING_TRUNCATED.encode())
        available = max(0, self.reasoning_cap - marker_bytes - self._reasoning_bytes)
        raw = text.encode("utf-8")
        if len(raw) > available:
            text = raw[:available].decode("utf-8", "ignore")
            marker = REASONING_TRUNCATED.encode()[
                : max(
                    0, self.reasoning_cap - self._reasoning_bytes - len(text.encode())
                )
            ].decode("utf-8", "ignore")
            text += marker
            self._truncated = True
        if text:
            self._reasoning.append(text)
            self._reasoning_bytes += len(text.encode())
        return text

    def _summary(self, item: _Item, index: int, text: str, snapshot: bool) -> str:
        if self._truncated:
            return ""
        separator = ""
        if index not in item.parts:
            if self._keys >= MAX_TRACKED_ITEMS:
                self.live_degraded = True
                return ""
            self._keys += 1
            item.parts[index] = []
        parts = item.parts[index]
        if text and not parts and self._reasoning:
            tail = "".join(piece[-2:] for piece in self._reasoning[-2:])
            if not tail.endswith("\n\n"):
                separator = self._append("\n" if tail.endswith("\n") else "\n\n")
        if snapshot:
            previous = "".join(parts)
            if not text.startswith(previous):
                self.live_degraded = True
                return self._append(SNAPSHOT_DIVERGED)
            text = text[len(previous) :]
        added = self._append(text)
        # Храним только принятый бюджетом префикс; после truncation сверки прекращены.
        if added:
            parts.append(added)
        return separator + added

    def _answer(self, iid: str, text: str, snapshot: bool) -> None:
        previous_bytes = self._answer_sizes.get(iid, 0)
        new_bytes = len(text.encode()) + (0 if snapshot else previous_bytes)
        total = self._answer_bytes - previous_bytes + new_bytes
        if total > self.answer_cap:
            raise ValueError("answer text exceeds the limit")
        if snapshot:
            self._answers[iid] = [text]
        else:
            self._answers.setdefault(iid, []).append(text)
        self._answer_sizes[iid] = new_bytes
        self._answer_bytes = total

    def feed(self, method: str, params: dict[str, Any]) -> str:
        """Принять одно уведомление MSP и вернуть добавленный хвост reasoning."""
        if method == "turn/completed":
            terminal = params.get("terminal")
            if self.terminal is not None or terminal not in (
                "completed",
                "failed",
                "cancelled",
            ):
                raise ValueError("invalid MSP terminal")
            self.terminal = terminal
            return ""
        if method not in ("item/started", "item/completed", "item/delta"):
            return ""
        raw = params.get("item") if method != "item/delta" else params
        if not isinstance(raw, dict):
            raise ValueError("invalid MSP item")
        kind = raw.get("kind")
        # Барьер инструмента выставляется даже при исчерпании реестра itemId.
        if kind == "toolCall":
            self.has_executed_tool = True
        iid = raw.get("itemId")
        if not isinstance(iid, str) or not iid or len(iid) > 256:
            raise ValueError("invalid MSP item id")
        item = self._items.get(iid)
        if item is None:
            if len(self._items) >= MAX_TRACKED_ITEMS:
                self.live_degraded = True
                return ""
            if method == "item/delta":
                raise ValueError("MSP delta for unknown item")
            # ItemKind — открытый enum MSP: новые служебные виды можно игнорировать.
            if not isinstance(kind, str) or not kind or len(kind) > 64:
                raise ValueError("invalid MSP item kind")
            name = raw.get("toolName")
            safe_name = (
                name
                if isinstance(name, str) and _TOOL_NAME.fullmatch(name)
                else "unknown_tool"
            )
            item = _Item(kind=kind, tool_name=safe_name)
            self._items[iid] = item
        elif method != "item/delta" and kind != item.kind:
            raise ValueError("MSP item kind changed")
        if item.completed:
            return ""
        if method == "item/delta":
            text = raw.get("delta")
            if not isinstance(text, str):
                raise ValueError("invalid MSP delta")
            field_name = raw.get("field", "text")
            match = (
                _SUMMARY_FIELD.fullmatch(field_name)
                if isinstance(field_name, str)
                else None
            )
            if item.kind == "reasoning" and match:
                return self._summary(item, int(match[1]), text, False)
            if item.kind == "agentMessage" and field_name == "text":
                self._answer(iid, text, False)
            return ""
        if method == "item/started":
            if item.started:
                return ""
            item.started = True
            if item.kind == "toolCall":
                return self._append(f"[Вызов инструмента: {item.tool_name}]\n")
            return ""
        item.completed = True
        if item.kind == "toolCall":
            return self._append(f"[Инструмент {item.tool_name} завершён]\n")
        if item.kind == "agentMessage" and isinstance(raw.get("text"), str):
            self._answer(iid, raw["text"], True)
        if item.kind == "reasoning":
            summary = raw.get("summary", [])
            if not isinstance(summary, list) or any(
                not isinstance(p, str) for p in summary
            ):
                raise ValueError("invalid MSP summary")
            return "".join(
                self._summary(item, idx, text, True) for idx, text in enumerate(summary)
            )
        return ""
