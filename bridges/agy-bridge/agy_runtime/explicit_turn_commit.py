"""Отложенный explicit-коммит/аборт хода ПОСЛЕ tool_turn.finish() (AD-001 / BUG-B1).

Чистые помощники для JSON- и SSE-веток (W1): не знают про HTTP и процесс-раннеры,
работают с любым adapter/state, удовлетворяющим протоколу ExplicitResumeAdapter.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from contextlib import suppress
from typing import Any

__all__ = ["build_explicit_commit_out", "finalize_deferred_explicit_turn", "abort_explicit_turn_safe"]


def build_explicit_commit_out(out: Mapping[str, Any], tool_turn: Any | None = None) -> dict[str, Any]:
    """Копия out с клиент-видимым text/tool_calls из tool_turn (без мутации входа).

    Текст НЕ вызывается .strip(): точные пробелы важны для compute_history_fingerprints.
    Пустой список calls убирает ключ tool_calls (согласованно с canonicalize_tool_calls).
    """
    commit_out = dict(out)
    if tool_turn is None:
        return commit_out
    commit_out["text"] = str(getattr(tool_turn, "content", "") or "")
    calls = list(getattr(tool_turn, "calls", None) or [])
    if calls:
        commit_out["tool_calls"] = calls
    else:
        commit_out.pop("tool_calls", None)
    return commit_out


def finalize_deferred_explicit_turn(
    adapter: Any,
    state: Any,
    out: Mapping[str, Any],
    *,
    tool_turn: Any | None = None,
    err: Any | None = None,
    commit_act: str = "commit",
    cid_re: re.Pattern[str] | None = None,
) -> bool:
    """Финализация explicit-хода после finish(): commit очищенного out либо безопасный abort.

    Никогда не коммитит слот при ошибке парсера (LiveParserError), tool_turn.error,
    ok=False, cid_re is None или commit_act != "commit" — освобождает слот через abort.
    """
    if adapter is None or state is None or not getattr(state, "handled", False) or getattr(state, "finalized", False):
        return False
    if cid_re is None:
        abort_explicit_turn_safe(adapter, state, post_spawn=True)
        return False
    turn_failed = tool_turn is not None and (bool(getattr(tool_turn, "error", None)) or not bool(getattr(tool_turn, "ok", True)))
    if bool(err) or turn_failed or commit_act != "commit":
        _ = adapter.finalize_turn(state, out, "abort", cid_re)
        return False
    commit_out = build_explicit_commit_out(out, tool_turn)
    return bool(adapter.finalize_turn(state, commit_out, "commit", cid_re))


def abort_explicit_turn_safe(adapter: Any, state: Any, *, post_spawn: bool = True) -> None:
    """Лучший-усилие освобождение незафинализированного explicit-хода (без падений).

    Подавляет любые ошибки (в т.ч. отсутствие lease или метода у адаптера).
    """
    if adapter is None or state is None or not getattr(state, "handled", False) or getattr(state, "finalized", False):
        return
    release = getattr(adapter, "release_if_unfinalized", None)
    if not callable(release):
        return
    with suppress(Exception):
        release(state, post_spawn=post_spawn)
