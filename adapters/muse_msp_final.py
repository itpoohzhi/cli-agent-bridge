"""Фазы MSP: только finalAnswer главного хода попадает в content."""

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
    """Состояние фаз; main_turn требует непустых userMessage itemId и turnId."""

    main_turn: str = ""
    anchored: bool = False
    limit: int = 1024
    routes: dict[str, str] = field(default_factory=dict)
    phases: dict[str, str] = field(default_factory=dict)
    sub_routes: dict[str, str] = field(default_factory=dict)
    sub_phases: dict[str, str] = field(default_factory=dict)
    mirror_indices: dict[str, int] = field(default_factory=dict)
    sub_texts: dict[str, list[str]] = field(default_factory=dict)
    flushed: set[str] = field(default_factory=set)
    quarantined: set[str] = field(default_factory=set)


def trackable(container: Any, iid: str, limit: int) -> bool:
    """Проверить, что реестр и длина iid остаются в пределах базы."""
    allowed = True
    try:
        container[iid]
    except (KeyError, TypeError):
        allowed = len(container) < limit
    allowed = allowed and not iid[256:]
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


def _remember_route(
    state: PhaseState, iid: str, scope: str, phase: str, route: str
) -> str:
    routes = {"main": state.routes}.get(scope, state.sub_routes)
    phases = {"main": state.phases}.get(scope, state.sub_phases)
    allowed = trackable(routes, iid, state.limit)
    if allowed:
        allowed = trackable(phases, iid, state.limit)
    remembered = "ignore"
    if allowed:
        routes[iid] = route
        phases[iid] = phase
        remembered = route
    return remembered


def _reject_collision(state: PhaseState, iid: str, scope: str) -> None:
    routes = {"main": state.routes}.get(scope, state.sub_routes)
    routes[iid] = "ignore"
    state.sub_texts.pop(iid, None)
    if trackable(state.quarantined, iid, state.limit):
        state.quarantined.add(iid)
    if trackable(state.flushed, iid, state.limit):
        state.flushed.add(iid)


def _event_scope(
    state: PhaseState, turn: str, cached_scope: str, cached_route: str
) -> str:
    scope = "foreign"
    if state.anchored:
        if {state.main_turn: True}.get(turn, False):
            scope = "main"
    if cached_route:
        if not turn:
            scope = cached_scope
    return scope


def _route_compatible(
    phases: dict[str, str], iid: str, phase: str, cached_scope: str, scope: str
) -> bool:
    compatible = {cached_scope: True}.get(scope, False)
    if compatible:
        stored_phase = phases.get(iid, "")
        if stored_phase:
            if phase:
                compatible = {stored_phase: True}.get(phase, False)
    return compatible


def _agent_route(
    state: PhaseState, method: str, raw: dict[str, Any], iid: str, route: str
) -> str:
    """Классифицировать agentMessage с учётом проверенного кэша itemId."""
    main_route = state.routes.get(iid, "")
    cached_scope = "main" if main_route else "foreign"
    phases = state.phases if main_route else state.sub_phases
    turn = raw.get("turnId")
    turn = turn if isinstance(turn, str) else ""
    phase = raw.get("messagePhase")
    phase = phase if isinstance(phase, str) else ""
    scope = _event_scope(state, turn, cached_scope, route)
    if route:
        if not _route_compatible(phases, iid, phase, cached_scope, scope):
            _reject_collision(state, iid, cached_scope)
            route = "ignore"
        elif phase:
            route = _remember_route(
                state, iid, scope, phase, classify_route(scope, phase)
            )
    else:
        route = classify_route(scope, phase)
        if not phase:
            pending = {"main": "pending"}.get(scope, "ignore")
            route = {"item/completed": route}.get(method, pending)
        route = _remember_route(state, iid, scope, phase, route)
    return route


def _ignore_untyped(state: PhaseState, iid: str, kind: object, turn: object) -> bool:
    if not iid:
        return False
    if kind in ("userMessage", "agentMessage"):
        return False
    if kind is not None:
        return kind not in ("toolCall", "reasoning")
    if isinstance(turn, str) and turn and state.anchored and turn != state.main_turn:
        return True
    return False


def _anchor_user_turn(state: PhaseState, iid: str, kind: object, turn: object) -> None:
    if {"userMessage": True}.get(kind, False):
        if isinstance(turn, str) and turn and iid:
            if not state.anchored:
                state.anchored = True
                state.main_turn = turn


def _handle_agent_route(
    state: PhaseState, method: str, raw: dict[str, Any], iid: str, route: str
) -> str:
    if iid and state.anchored:
        return _agent_route(state, method, raw, iid, route)
    if iid and trackable(state.quarantined, iid, state.limit):
        state.quarantined.add(iid)
    return "ignore"


def route_for(state: PhaseState, method: str, raw: dict[str, Any]) -> tuple[str, str]:
    iid_value = raw.get("itemId")
    iid = iid_value if isinstance(iid_value, str) else ""
    if iid and state.quarantined.__contains__(iid):
        return iid, "ignore"
    route = state.routes.get(iid, state.sub_routes.get(iid, ""))
    kind = raw.get("kind")
    turn = raw.get("turnId")
    if _ignore_untyped(state, iid, kind, turn):
        return iid, "ignore"
    _anchor_user_turn(state, iid, kind, turn)
    if {"agentMessage": True}.get(kind, False):
        route = _handle_agent_route(state, method, raw, iid, route)
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


def sub_payload(method: str, raw: dict[str, Any]) -> tuple[str | None, bool, bool]:
    """Текст финала подагента, признаки snapshot и completed."""
    text = raw.get("delta")
    snapshot = not isinstance(text, str)
    if snapshot:
        text = raw.get("text")
    completed = {"item/completed": True}.get(method, False)
    return (text if isinstance(text, str) else None, snapshot, completed)


def store_sub(state: PhaseState, iid: str, text: str, snapshot: bool) -> None:
    """Накопить текст финала подагента с запасным бюджетом под однострочную обрезку."""
    if state.flushed.__contains__(iid):
        state.sub_texts.pop(iid, None)
    else:
        if trackable(state.sub_texts, iid, state.limit):
            pieces = state.sub_texts.setdefault(iid, [])
            if snapshot:
                if text:
                    pieces.clear()
            cap = subagent_final_limit() * 8
            stored = sum(len(piece) for piece in pieces)
            if text:
                remaining = cap - stored
                if remaining:
                    pieces.append(text[:remaining])


def flush_chunk(state: PhaseState, iid: str, reasoning: str) -> str:
    """Выдать однострочный финал подагента в reasoning не более одного раза."""
    line = one_line("".join(state.sub_texts.pop(iid, [])))
    chunk = ""
    if line:
        if not state.flushed.__contains__(iid):
            if trackable(state.flushed, iid, state.limit):
                state.flushed.add(iid)
                chunk = sep_for(reasoning) + line + "\n"
    return chunk


def normalize_tool_event(
    method: str, params: dict[str, Any], raw: dict[str, Any], item: Any
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Восстановить kind завершения из стабильного состояния toolCall."""
    normalized_params = params
    normalized_raw = raw
    if {"item/completed": True}.get(method, False):
        if item:
            if {"toolCall": True}.get(item.kind, False):
                if not raw.get("kind"):
                    normalized_raw = dict(raw)
                    normalized_raw["kind"] = "toolCall"
                    normalized_params = dict(params)
                    if normalized_params.get("item"):
                        normalized_params["item"] = normalized_raw
                    else:
                        normalized_params = normalized_raw
    return normalized_params, normalized_raw


def refresh_tool_item(item: Any, raw: Any) -> bool:
    was_completed = item.completed if item else False
    if item:
        if isinstance(raw, dict):
            fresh = extract_tool_name(raw)
            should_merge = is_failed_status(raw.get("status"))
            if not should_merge:
                _, separator, _ = fresh.partition(" — ")
                if not separator:
                    should_merge = True
            if should_merge:
                item.tool_name = merge_tool_display(fresh, item.tool_name)
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
