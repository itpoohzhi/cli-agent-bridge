"""3-ярусная карта потока запросов (клиенты -> L7-мосты -> L4/L7 egress-прокси) с живыми счётчиками."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from typing import Any

from core import defaults as D


def _env_json(name: str, fallback: Any) -> Any:
    try:
        return json.loads(os.environ[name])
    except (KeyError, ValueError):
        return fallback


def _caller_node(nodes: Sequence[Mapping[str, Any]], row: Mapping[str, Any]) -> str:
    ua = str(row.get("user_agent") or "").lower()
    for n in nodes:
        by_kind = n.get("subagent") and row.get("client_kind") == "subagent"
        if by_kind or row.get("subagent_role") in n.get("roles", ()) or any(m in ua for m in n.get("ua", ())):
            return str(n["id"])
    return "other"


def build_architecture_flow(
    by_backend: Sequence[Mapping[str, Any]],
    callers: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
    topology: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """3 яруса: входящие клиенты -> L7-мосты протоколов -> L4/L7 egress-прокси, с живыми счётчиками."""
    topo = topology or _env_json("BRIDGE_TELEMETRY_TOPOLOGY_JSON", D.BRIDGE_TELEMETRY_TOPOLOGY)
    t1, t2, t3 = (dict(topo[k]) for k in ("tier1_entry_callers", "tier2_l7_bridges", "tier3_l4_egress_proxies"))
    counts: dict[str, int] = {}
    for row in callers:
        node_id = _caller_node(t1["nodes"], row)
        counts[node_id] = counts.get(node_id, 0) + int(row.get("requests") or 0)
    t1["nodes"] = [{**n, "requests": counts.get(n["id"], 0)} for n in t1["nodes"]]
    t1["nodes"].append({"id": "other", "name": "Other", "requests": counts.get("other", 0)})
    nodes2 = []
    for n in t2["nodes"]:
        rows = list(by_backend) if n.get("all") else [r for r in by_backend if r.get("backend_id") in n.get("backends", ())]
        reqs = sum(int(r.get("requests") or 0) for r in rows)
        weighted = sum((r.get("avg_total_ms") or 0.0) * int(r.get("requests") or 0) for r in rows)
        nodes2.append({**n, "requests": reqs, "total_tokens": sum(int(r.get("total_tokens") or 0) for r in rows),
                       "avg_total_ms": round(weighted / reqs, 2) if reqs else None})
    t2["nodes"] = nodes2
    egress = [(str(r.get("egress_proxy") or "direct"), int(r.get("requests") or 0)) for r in by_backend]
    t3["nodes"] = [{**n, "requests": sum(c for e, c in egress if any(m in e for m in n.get("match", ())))} for n in t3["nodes"]]
    t3["direct_requests"] = sum(c for e, c in egress if e == "direct")
    return {"total_requests": int(summary.get("total_requests") or 0), "tier1_entry_callers": t1,
            "tier2_l7_bridges": t2, "tier3_l4_egress_proxies": t3}
