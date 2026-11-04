"""Защитный прунинг истории диалога (ADR-001.2)."""
from __future__ import annotations
import logging
from typing import Any, NamedTuple
from .prompt_builder import (
    COMPACTION_MARKER,
    _COMPACTION_MARKER_ROLE,
    _assemble_prompt,
    _normalize_tool_call,
    _render_turn,
)
from .token_budget import (
    _estimate_tokens,
    _overhead_tokens_estimate,
)
logger = logging.getLogger("muse_bridge")
class PruneResult(NamedTuple):
    status: str  # "pass_through" | "pruned" | "refused"
    messages: list[dict[str, Any]]
    prompt: str
    est_before: int
    est_after: int
    msgs_total: int
    msgs_kept: int
    msgs_dropped: int
    mandatory_est: int
    overhead_est: int
def _partition_units(
    valid_msgs: list[dict[str, Any]], roles: list[str]
) -> tuple[list[list[dict[str, Any]]], set[int]]:
    """Разбить валидные сообщения на атомарные единицы и выделить обязательные индексы M."""
    units: list[list[dict[str, Any]]] = []
    consumed_tools: set[int] = set()
    for idx, msg in enumerate(valid_msgs):
        role = roles[idx]
        if role == "tool":
            continue
        if (
            role == "assistant"
            and isinstance(msg.get("tool_calls"), list)
            and msg.get("tool_calls")
        ):
            call_ids = [
                _normalize_tool_call(tc)["id"]
                for tc in msg["tool_calls"]
                if _normalize_tool_call(tc)["id"]
            ]
            if call_ids:
                expected = set(call_ids)
                matched_indices: list[int] = []
                matched_ids: set[str] = set()
                for j in range(idx + 1, len(valid_msgs)):
                    if roles[j] != "tool":
                        break
                    if j in consumed_tools:
                        continue
                    tc_id = str(
                        valid_msgs[j].get("tool_call_id")
                        or valid_msgs[j].get("id")
                        or ""
                    )
                    if tc_id in expected and tc_id not in matched_ids:
                        matched_indices.append(j)
                        matched_ids.add(tc_id)
                if matched_ids == expected:
                    consumed_tools.update(matched_indices)
                    units.append([msg] + [valid_msgs[j] for j in matched_indices])
                continue
        units.append([msg])
    mandatory_indices: set[int] = set()
    user_unit_indices: list[int] = []
    last_non_sys_idx: int | None = None
    for u_idx, unit in enumerate(units):
        u_role = _render_turn(unit[0])[0]
        if u_role in ("system", "developer"):
            mandatory_indices.add(u_idx)
        elif u_role != _COMPACTION_MARKER_ROLE:
            last_non_sys_idx = u_idx
            if u_role not in ("assistant", "tool"):
                user_unit_indices.append(u_idx)
    if user_unit_indices:
        mandatory_indices.add(user_unit_indices[0])
        mandatory_indices.add(user_unit_indices[-1])
        if (
            last_non_sys_idx is not None
            and last_non_sys_idx > user_unit_indices[-1]
            and len(units[last_non_sys_idx]) > 1
        ):
            mandatory_indices.add(last_non_sys_idx)
    return units, mandatory_indices
def _compute_mandatory_est_only(
    valid_msgs: list[dict[str, Any]],
    roles: list[str],
    tools: list[dict[str, Any]] | None,
    tool_choice: Any,
    raw_tools: Any,
) -> int:
    units, mandatory_indices = _partition_units(valid_msgs, roles)
    mandatory_msgs = [
        m
        for u_idx, unit in enumerate(units)
        if u_idx in mandatory_indices
        for m in unit
    ]
    _, _, mandatory_prompt = _assemble_prompt(
        mandatory_msgs, tools=tools, tool_choice=tool_choice, raw_tools=raw_tools
    )
    return _estimate_tokens(mandatory_prompt)
def _build_candidate(
    units: list[list[dict[str, Any]]],
    u_roles: list[str],
    kept_flags: list[bool],
) -> list[dict[str, Any]]:
    pruned: list[dict[str, Any]] = []
    seen_kept_turn = False
    in_dropped_gap = False
    for u_idx, unit in enumerate(units):
        u_role = u_roles[u_idx]
        if u_role in ("system", "developer"):
            pruned.extend(unit)
            continue
        if u_role == _COMPACTION_MARKER_ROLE:
            if seen_kept_turn:
                in_dropped_gap = True
            continue
        if kept_flags[u_idx]:
            if in_dropped_gap:
                pruned.append(
                    {"role": _COMPACTION_MARKER_ROLE, "content": COMPACTION_MARKER}
                )
                in_dropped_gap = False
            pruned.extend(unit)
            seen_kept_turn = True
        elif seen_kept_turn:
            in_dropped_gap = True
    return pruned
def _prune_messages(
    messages: list[dict[str, Any]],
    limit: int,
    target: int,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: Any = None,
    raw_tools: Any = None,
) -> PruneResult:
    """Чистая функция защитного прунинга истории диалога (ADR-001.2)."""
    _, _, full_prompt = _assemble_prompt(
        messages, tools=tools, tool_choice=tool_choice, raw_tools=raw_tools
    )
    est_before = _estimate_tokens(full_prompt)
    valid_msgs: list[dict[str, Any]] = []
    roles: list[str] = []
    real_msgs_total = 0
    for msg in messages or []:
        if not isinstance(msg, dict):
            continue
        role, text = _render_turn(msg)
        if not text.strip():
            continue
        valid_msgs.append(msg)
        roles.append(role)
        if role != _COMPACTION_MARKER_ROLE:
            real_msgs_total += 1
    has_system = any(r in ("system", "developer") for r in roles)
    overhead_est = _overhead_tokens_estimate(has_system, tools, tool_choice, raw_tools)
    if est_before <= limit:
        mandatory_est = _compute_mandatory_est_only(
            valid_msgs, roles, tools, tool_choice, raw_tools
        )
        return PruneResult(
            status="pass_through",
            messages=messages,
            prompt=full_prompt,
            est_before=est_before,
            est_after=est_before,
            msgs_total=real_msgs_total,
            msgs_kept=real_msgs_total,
            msgs_dropped=0,
            mandatory_est=mandatory_est,
            overhead_est=overhead_est,
        )
    units, mandatory_indices = _partition_units(valid_msgs, roles)
    u_roles = [_render_turn(u[0])[0] for u in units]
    u_chars, u_bytes = [], []
    for unit, u_role in zip(units, u_roles):
        if u_role in ("system", "developer", _COMPACTION_MARKER_ROLE):
            u_chars.append(0)
            u_bytes.append(0)
            continue
        rendered = []
        for m in unit:
            mr, mt = _render_turn(m)
            prefix = "Assistant: " if mr == "assistant" else ("" if mr == "tool" else "User: ")
            rendered.append(f"{prefix}{mt}")
        s = "\n\n".join(rendered)
        u_chars.append(len(s))
        u_bytes.append(len(s.encode("utf-8")))
    kept = [i in mandatory_indices for i in range(len(units))]
    mandatory_msgs = _build_candidate(units, u_roles, kept)
    _, mand_turns, mand_prompt = _assemble_prompt(
        mandatory_msgs, tools=tools, tool_choice=tool_choice, raw_tools=raw_tools
    )
    mandatory_est = _estimate_tokens(mand_prompt)
    cap = max(limit, target)
    if mandatory_est > cap:
        kc = sum(len(units[i]) for i in range(len(units)) if kept[i] and u_roles[i] != _COMPACTION_MARKER_ROLE)
        return PruneResult("refused", mandatory_msgs, mand_prompt, est_before, mandatory_est, real_msgs_total, kc, max(0, real_msgs_total - kc), mandatory_est, overhead_est)
    head_pfx_c = len(mand_prompt) - len(mand_turns)
    head_pfx_b = len(mand_prompt.encode("utf-8")) - len(mand_turns.encode("utf-8"))
    mc, mb = len(COMPACTION_MARKER), len(COMPACTION_MARKER.encode("utf-8"))
    non_sys = [i for i in range(len(units)) if u_roles[i] not in ("system", "developer")]
    pos_map = {u: p for p, u in enumerate(non_sys)}
    is_kept = [kept[u] and u_roles[u] != _COMPACTION_MARKER_ROLE for u in non_sys]
    m_ns = len(non_sys)
    first_k = next((p for p, f in enumerate(is_kept) if f), m_ns)
    ft_trans = sum(1 for p in range(1, m_ns) if not is_kept[p - 1] and is_kept[p])
    t_cnt = sum(1 for f in is_kept if f)
    t_c = sum(u_chars[non_sys[p]] for p in range(m_ns) if is_kept[p])
    t_b = sum(u_bytes[non_sys[p]] for p in range(m_ns) if is_kept[p])
    for u_idx in range(len(units) - 1, -1, -1):
        if u_idx in mandatory_indices or u_roles[u_idx] in ("system", "developer", _COMPACTION_MARKER_ROLE):
            continue
        p = pos_map[u_idx]
        b_ft = (1 if p > 0 and not is_kept[p - 1] and is_kept[p] else 0) + (1 if p + 1 < m_ns and not is_kept[p] and is_kept[p + 1] else 0)
        a_ft = 1 if p > 0 and not is_kept[p - 1] else 0
        n_ft = ft_trans - b_ft + a_ft
        n_first = min(first_k, p)
        n_mk = max(0, n_ft - (1 if n_first > 0 else 0)) if n_first < m_ns else 0
        n_cnt, n_c, n_b = t_cnt + 1, t_c + u_chars[u_idx], t_b + u_bytes[u_idx]
        sep = 2 * max(0, n_cnt + n_mk - 1)
        if max((head_pfx_c + n_c + n_mk * mc + sep) // 3, (head_pfx_b + n_b + n_mk * mb + sep) // 3) <= target:
            kept[u_idx] = is_kept[p] = True
            ft_trans, first_k, t_cnt, t_c, t_b = n_ft, n_first, n_cnt, n_c, n_b
            continue
        break
    pruned_msgs = _build_candidate(units, u_roles, kept)
    _, _, pruned_prompt = _assemble_prompt(pruned_msgs, tools=tools, tool_choice=tool_choice, raw_tools=raw_tools)
    est_after = _estimate_tokens(pruned_prompt)
    while est_after > target:
        opts = [i for i in range(len(units)) if kept[i] and i not in mandatory_indices and u_roles[i] != _COMPACTION_MARKER_ROLE]
        if not opts:
            break
        kept[opts[0]] = False
        pruned_msgs = _build_candidate(units, u_roles, kept)
        _, _, pruned_prompt = _assemble_prompt(pruned_msgs, tools=tools, tool_choice=tool_choice, raw_tools=raw_tools)
        est_after = _estimate_tokens(pruned_prompt)
    kc = sum(len(units[i]) for i in range(len(units)) if kept[i] and u_roles[i] != _COMPACTION_MARKER_ROLE)
    dc = max(0, real_msgs_total - kc)
    st = "refused" if est_after > cap else "pruned"
    return PruneResult(st, pruned_msgs, pruned_prompt, est_before, est_after, real_msgs_total, kc, dc, mandatory_est, overhead_est)


def _log_context_prune(
    rid: str,
    model: str,
    reason: str,
    attempt: int,
    limit: int,
    target: int,
    res: PruneResult,
    log_fn: Any = None,
) -> None:
    """Структурная запись прунинга без тел сообщений и секретов."""
    logger.info(
        "muse_context_pruned: model=%s initial=%d target=%d dropped=%d is_retry=%s",
        model,
        res.est_before,
        target,
        res.msgs_dropped,
        attempt > 1,
    )
    if log_fn is not None:
        log_fn(
            f"context_prune rid={rid} model={model} reason={reason} attempt={attempt} "
            f"limit={limit} target={target} est_before={res.est_before} est_after={res.est_after} "
            f"msgs_total={res.msgs_total} msgs_kept={res.msgs_kept} msgs_dropped={res.msgs_dropped} "
            f"mandatory_est={res.mandatory_est} overhead_est={res.overhead_est} method=bytes_div_3"
        )
