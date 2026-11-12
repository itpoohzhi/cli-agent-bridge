"""Чистые функции фаз MSP: только finalAnswer главного хода попадает в content.

Главный ход — turnId первого userMessage (в реальном MSP-потоке приходит первым).
commentary главного хода зеркалится в reasoning вызывающим кодом через базовый
_summary, финалы подагентов копятся в PhaseState и уходят одной строкой в
reasoning на своём item/completed либо на turn/completed (реальные финалы
подагентов completed могут не получать). Модуль не импортирует вызывающий
модуль: все нужные данные принимает аргументами.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from adapters.muse_msp_hints import (
    classify_route,
    extract_tool_name,
    is_failed_status,
    one_line,
    sep_for,
    subagent_final_limit,
)


@dataclass
class PhaseState:
    """Состояние маршрутизации фаз одного хода MSP.

    main_turn якорится только на userMessage с непустым turnId; каждый реестр
    ограничен limit (вызывающий передаёт MAX_TRACKED_ITEMS базы).
    """

    main_turn: str = ""
    anchored: bool = False
    limit: int = 1024
    routes: dict[str, str] = field(default_factory=dict)
    phases: dict[str, str] = field(default_factory=dict)
    mirror_indices: dict[str, int] = field(default_factory=dict)
    sub_texts: dict[str, list[str]] = field(default_factory=dict)
    flushed: set[str] = field(default_factory=set)


def trackable(container: Any, iid: str, limit: int) -> bool:
    """Запись iid заводить можно: уже есть либо реестр и длина iid — в пределах базы.

    Для set подписка даёт TypeError: вызывающий flush_chunk проверяет членство
    сам, здесь для set остаётся только предел длины реестра.
    """
    allowed = True
    try:
        container[iid]
    except (KeyError, TypeError):
        allowed = len(container) < limit
    if iid[256:]:
        allowed = False
    return allowed


def choose_text(answers: dict[str, list[str]], phases: dict[str, str]) -> str:
    """Текст content: непустые finalAnswer главного хода, иначе все ответы."""
    finals: list[str] = []
    fallback: list[str] = []
    for iid, pieces in answers.items():
        joined = "".join(pieces)
        if joined:
            fallback.append(joined)
            if phases.get(iid) == "finalAnswer":
                finals.append(joined)
    return "\n\n".join(finals if finals else fallback)


def route_for(state: PhaseState, raw: dict[str, Any]) -> tuple[str, str]:
    """Маршрут события; главный ход якорится только на userMessage с turnId.

    До якоря agentMessage с фазой считается чужим (fail-closed); безфазовый
    поток без turnId остаётся главным ради fallback choose_text. После якоря
    пустые метаданные безопасны только для уже классифицированного itemId.
    """
    iid = raw.get("itemId")
    iid = iid if isinstance(iid, str) else ""
    turn = raw.get("turnId")
    turn = turn if isinstance(turn, str) else ""
    if raw.get("kind") == "userMessage":
        if turn:
            if not state.anchored:
                state.anchored = True
                state.main_turn = turn
    route = state.routes.get(iid, "")
    if route:
        return iid, route
    if raw.get("kind") == "agentMessage":
        phase = raw.get("messagePhase")
        phase = phase if isinstance(phase, str) else ""
        scope = {
            (True, state.main_turn, phase): "main",
            (False, "", ""): "main",
        }.get((state.anchored, turn, phase), "foreign")
        route = classify_route(scope, phase)
        if trackable(state.routes, iid, state.limit):
            state.routes[iid] = route
            state.phases[iid] = phase
    return iid, route


def mirror_payload(
    method: str, raw: dict[str, Any], route: str
) -> tuple[str, bool] | None:
    """Текст commentary для зеркалирования в reasoning и признак snapshot."""
    if route != "commentary":
        return None
    text = raw.get("delta")
    if not isinstance(text, str):
        text = raw.get("text")
    if not isinstance(text, str):
        return None
    return text, method == "item/completed"


def mirror_index_for(state: PhaseState, iid: str) -> int:
    """Стабильный индекс зеркального reasoning-элемента для agentMessage."""
    index = state.mirror_indices.get(iid)
    if index is None:
        index = len(state.mirror_indices)
        if trackable(state.mirror_indices, iid, state.limit):
            state.mirror_indices[iid] = index
    return index


def sub_payload(method: str, raw: dict[str, Any]) -> tuple[str | None, bool]:
    """Текст финала подагента (delta или snapshot) и признак completed."""
    text = raw.get("delta")
    if not isinstance(text, str):
        text = raw.get("text")
    return (text if isinstance(text, str) else None), method == "item/completed"


def store_sub(state: PhaseState, iid: str, text: str, snapshot: bool) -> None:
    """Накопить текст финала подагента с запасным бюджетом под однострочную обрезку."""
    if trackable(state.sub_texts, iid, state.limit):
        pieces = state.sub_texts.setdefault(iid, [])
        if snapshot:
            pieces.clear()
        cap = subagent_final_limit() * 8
        stored = sum(len(piece) for piece in pieces)
        if stored < cap:
            pieces.append(text[: cap - stored])


def flush_chunk(state: PhaseState, iid: str, reasoning: str) -> str:
    """Однострочный финал подагента для append в reasoning; повторно не выдаётся.

    После выдачи накопленный текст освобождается; реестр flushed ограничен
    тем же пределом, при его исчерпании идемпотентность держит освобождение.
    """
    line = one_line("".join(state.sub_texts.get(iid, [])))
    chunk = ""
    if line:
        if iid not in state.flushed:
            if trackable(state.flushed, iid, state.limit):
                state.flushed.add(iid)
            state.sub_texts.pop(iid, None)
            chunk = sep_for(reasoning) + line + "\n"
    return chunk


def refresh_tool_item(item: Any, raw: Any) -> bool:
    """Слить подсказку инструмента из raw в item до базы; вернуть прежний completed.

    item — _Item вызывающего модуля или None: импорт типа создал бы цикл,
    поэтому поля completed/tool_name доступны утино, как container в trackable.
    """
    was_completed = item.completed if item else False
    if item:
        if isinstance(raw, dict):
            item.tool_name = merge_tool_display(extract_tool_name(raw), item.tool_name)
    return was_completed


def merge_tool_display(fresh: str, stored: str) -> str:
    """Отображение инструмента для базы: вариант с подсказкой выигрывает у голого."""
    merged = stored
    if " — " in fresh:
        merged = fresh
    return merged


def tool_failure_line(method: str, raw: dict[str, Any], display: str) -> str:
    """Строка ошибки для упавшего инструмента с подсказкой; иначе пусто."""
    line = ""
    if (method, raw.get("kind")) == ("item/completed", "toolCall"):
        if " — " in display:
            if is_failed_status(raw.get("status")):
                line = f"[Ошибка инструмента: {display}]\n"
    return line
