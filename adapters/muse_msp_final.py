"""Фазовая обёртка MspEvents: только finalAnswer главного хода попадает в content.

Главный ход — turnId первого userMessage (в реальном MSP-потоке приходит первым).
commentary главного хода зеркалится в reasoning через базовый _summary,
финалы подагентов копятся и уходят одной строкой в reasoning на своём
item/completed либо на turn/completed (реальные финалы подагентов completed
могут не получать). Тела базовых feed/_summary/_append не тронуты.
"""

from __future__ import annotations

from typing import Any, Callable

from adapters.muse_msp import _Item, _MspCore, _extract_tool_name
from adapters.muse_msp_hints import (
    classify_route,
    is_failed_status,
    one_line,
    sep_for,
    subagent_final_limit,
)

_ForeignHandler = Callable[[str, dict[str, Any], str], str]


class MspEvents(_MspCore):
    """MspEvents с маршрутизацией фаз agentMessage по главному ходу."""

    def __init__(self, *, reasoning_cap: int, answer_cap: int) -> None:
        super().__init__(reasoning_cap=reasoning_cap, answer_cap=answer_cap)
        self._main_turn = ""
        self._routes: dict[str, str] = {}
        self._phases: dict[str, str] = {}
        self._mirrors: dict[str, tuple[_Item, int]] = {}
        self._sub_texts: dict[str, list[str]] = {}
        self._flushed: set[str] = set()
        self._foreign: dict[str, _ForeignHandler] = {
            "ignore": self._drop,
            "sub_final": self._sub_event,
        }

    @property
    def text(self) -> str:
        finals: list[str] = []
        fallback: list[str] = []
        for iid, pieces in self._answers.items():
            joined = "".join(pieces)
            if joined:
                fallback.append(joined)
                if self._phases.get(iid) == "finalAnswer":
                    finals.append(joined)
        chosen = finals
        if not chosen:
            chosen = fallback
        return "\n\n".join(chosen)

    def feed(self, method: str, params: dict[str, Any]) -> str:
        """Принять уведомление MSP: чужие agentMessage отрезать, остальные — в базу."""
        raw = params.get("item", params)
        iid, route = self._route_for(raw) if isinstance(raw, dict) else ("", "")
        handler = self._foreign.get(route)
        if handler is not None:
            return handler(method, raw, iid)
        out = super().feed(method, params)
        if isinstance(raw, dict):
            out += self._mirror(method, raw, iid, route)
            out += self._tool_failure(method, raw)
        if method == "turn/completed":
            out += "".join(self._flush(i) for i in list(self._sub_texts))
        return out

    def _route_for(self, raw: dict[str, Any]) -> tuple[str, str]:
        iid = raw.get("itemId")
        iid = iid if isinstance(iid, str) else ""
        turn = raw.get("turnId")
        turn = turn if isinstance(turn, str) else ""
        if not self._main_turn:
            self._main_turn = turn
        route = self._routes.get(iid, "")
        if raw.get("kind") == "agentMessage":
            phase = raw.get("messagePhase")
            phase = phase if isinstance(phase, str) else ""
            scope = "main" if turn in (self._main_turn, "") else "foreign"
            route = classify_route(scope, phase)
            self._routes[iid] = route
            self._phases[iid] = phase
        return iid, route

    def _mirror(self, method: str, raw: dict[str, Any], iid: str, route: str) -> str:
        out = ""
        if route == "commentary":
            text = raw.get("delta")
            if not isinstance(text, str):
                text = raw.get("text")
            if isinstance(text, str):
                item, index = self._mirror_item(iid)
                out = self._summary(item, index, text, method == "item/completed")
        return out

    def _mirror_item(self, iid: str) -> tuple[_Item, int]:
        found = self._mirrors.get(iid)
        if found is None:
            found = (_Item(kind="reasoning"), len(self._mirrors))
            self._mirrors[iid] = found
        return found

    def _drop(self, _method: str, _raw: dict[str, Any], _iid: str) -> str:
        return ""

    def _sub_event(self, method: str, raw: dict[str, Any], iid: str) -> str:
        text = raw.get("delta")
        if not isinstance(text, str):
            text = raw.get("text")
        snapshot = method == "item/completed"
        if isinstance(text, str):
            self._store_sub(iid, text, snapshot)
        return self._flush(iid) if snapshot else ""

    def _store_sub(self, iid: str, text: str, snapshot: bool) -> None:
        pieces = self._sub_texts.setdefault(iid, [])
        if snapshot:
            pieces.clear()
        cap = subagent_final_limit() * 8
        stored = sum(len(piece) for piece in pieces)
        if stored < cap:
            pieces.append(text[: cap - stored])

    def _flush(self, iid: str) -> str:
        line = one_line("".join(self._sub_texts.get(iid, [])))
        out = ""
        if line:
            if iid not in self._flushed:
                self._flushed.add(iid)
                out = self._append(sep_for(self.reasoning) + line + "\n")
        return out

    def _tool_failure(self, method: str, raw: dict[str, Any]) -> str:
        out = ""
        if (method, raw.get("kind")) == ("item/completed", "toolCall"):
            display = _extract_tool_name(raw)
            if " — " in display:
                if is_failed_status(raw.get("status")):
                    out = self._append(f"[Инструмент {display} завершён]\n")
        return out
