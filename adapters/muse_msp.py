"""Чистая аккумуляция MSP v1: append-only reasoning, snapshots и бюджеты ADR 0012."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterator

import adapters.muse_msp_final as _final
from adapters.muse_msp_hints import extract_tool_name as _extract_tool_name
from adapters.muse_msp_hints import format_tool_completed as _format_tool_completed
from adapters.muse_msp_hints import format_tool_started as _format_tool_started

MAX_TRACKED_ITEMS = 1024
LIVE_DELTA_MAX_BYTES = 8 << 10
REASONING_TRUNCATED = "\n[reasoning truncated: reasoning budget reached]\n"
SNAPSHOT_DIVERGED = "\n[reasoning snapshot diverged; live prefix preserved]\n"
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


class _MspCore:
    """Один ход MSP. Возвращаемая из feed строка — только новый хвост reasoning.

    Порядок — порядок поступления событий, ключ сверки snapshot — (itemId, summary.N).
    Уже опубликованные символы никогда не перезаписываются; повторный completed
    идемпотентен. Аргументы toolCall не сохраняются; в маркер идёт только подсказка
    из allowlist полей args.
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
            item = _Item(kind=kind, tool_name=_extract_tool_name(raw))
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
                return self._append(_format_tool_started(item.tool_name))
            return ""
        item.completed = True
        if item.kind == "toolCall":
            item.tool_name = item.tool_name or _extract_tool_name(raw)
            return self._append(_format_tool_completed(item.tool_name))
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


class MspEvents(_MspCore):
    """MspEvents с маршрутизацией фаз agentMessage по главному ходу.

    Логика фаз — чистые функции adapters.muse_msp_final над PhaseState;
    здесь только тонкие делегаты к базовым _summary/_append.
    """

    def __init__(self, *, reasoning_cap: int, answer_cap: int) -> None:
        super().__init__(reasoning_cap=reasoning_cap, answer_cap=answer_cap)
        self._phase = _final.PhaseState(limit=MAX_TRACKED_ITEMS)
        self._mirror_items: dict[str, _Item] = {}

    @property
    def text(self) -> str:
        return _final.choose_text(self._answers, self._phase.phases)

    @property
    def tracked_count(self) -> int:
        phase = self._phase
        return max(
            super().tracked_count,
            len(phase.routes),
            len(phase.phases),
            len(phase.mirror_indices),
            len(phase.sub_texts),
            len(phase.flushed),
            len(self._mirror_items),
        )

    def feed(self, method: str, params: dict[str, Any]) -> str:
        """Принять уведомление MSP: чужие agentMessage отрезать, остальные — в базу."""
        raw = params.get("item", params)
        iid, route = (
            _final.route_for(self._phase, raw) if isinstance(raw, dict) else ("", "")
        )
        if route == "ignore":
            return ""
        if route == "sub_final":
            return self._sub_event(method, raw, iid)
        tool_item = self._items.get(iid)
        was_completed = tool_item.completed if tool_item else False
        if tool_item:
            if isinstance(raw, dict):
                tool_item.tool_name = _final.merge_tool_display(
                    _extract_tool_name(raw), tool_item.tool_name
                )
        out = super().feed(method, params)
        if isinstance(raw, dict):
            out += self._mirror(method, raw, iid, route)
            done_item = self._items.get(iid)
            display = done_item.tool_name if done_item else ""
            display = "" if was_completed else display
            out += self._append(_final.tool_failure_line(method, raw, display))
        if method == "turn/completed":
            out += "".join(self._flush(i) for i in list(self._phase.sub_texts))
        return out

    def _mirror(self, method: str, raw: dict[str, Any], iid: str, route: str) -> str:
        payload = _final.mirror_payload(method, raw, route)
        if payload is None:
            return ""
        text, snapshot = payload
        mirrored = ""
        if _final.trackable(self._mirror_items, iid, MAX_TRACKED_ITEMS):
            item = self._mirror_items.setdefault(iid, _Item(kind="reasoning"))
            mirrored = self._summary(
                item, _final.mirror_index_for(self._phase, iid), text, snapshot
            )
        return mirrored

    def _sub_event(self, method: str, raw: dict[str, Any], iid: str) -> str:
        text, snapshot = _final.sub_payload(method, raw)
        if text is not None:
            _final.store_sub(self._phase, iid, text, snapshot)
        return self._flush(iid) if snapshot else ""

    def _flush(self, iid: str) -> str:
        return self._append(_final.flush_chunk(self._phase, iid, self.reasoning))
