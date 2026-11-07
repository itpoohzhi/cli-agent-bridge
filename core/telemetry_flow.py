"""3-ярусная карта потока запросов (клиенты -> L7-мосты -> L4/L7 egress-прокси) с живыми счётчиками."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from typing import Any

from core import defaults as D
from core.telemetry_util import as_float, as_int, as_str, first_truthy


def _env_json(name: str, fallback: Any) -> Any:
    try:
        return json.loads(os.environ[name])
    except (KeyError, ValueError):
        return fallback


def _matches(node: Mapping[str, Any], row: Mapping[str, Any], ua: str) -> bool:
    """Узел tier1 совпал: роль сабагента, флаг subagent или подстрока User-Agent."""
    roles: Sequence[Any] = node.get("roles", ())
    markers: Sequence[Any] = node.get("ua", ())
    return any((
        all((bool(node.get("subagent")), row.get("client_kind") == "subagent")),
        row.get("subagent_role") in roles,
        any(marker in ua for marker in markers),
    ))


def _caller_node(nodes: Sequence[Mapping[str, Any]], row: Mapping[str, Any]) -> str:
    ua = as_str(row.get("user_agent")).lower()
    matched = [str(node["id"]) for node in nodes if _matches(node, row, ua)]
    return str(first_truthy(*matched, default="other"))


def _tier_one(nodes: Sequence[Mapping[str, Any]], callers: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """tier1: счётчики по узлам входа плюс агрегат «other» для неопознанных клиентов."""
    counts: dict[str, int] = {}
    for row in callers:
        node_id = _caller_node(nodes, row)
        counts[node_id] = counts.get(node_id, 0) + as_int(row.get("requests"))
    merged = [{**node, "requests": counts.get(node["id"], 0)} for node in nodes]
    return [*merged, {"id": "other", "name": "Other", "requests": counts.get("other", 0)}]


def _tier_two(nodes: Sequence[Mapping[str, Any]], by_backend: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """tier2: счётчики по L7-мостам; узел с all=true агрегирует весь хаб."""
    merged: list[dict[str, Any]] = []
    for node in nodes:
        backends: Sequence[Any] = node.get("backends", ())
        rows = list(by_backend) if node.get("all") else [r for r in by_backend if r.get("backend_id") in backends]
        requests = sum(as_int(r.get("requests")) for r in rows)
        weighted = sum(as_float(r.get("avg_total_ms")) * as_int(r.get("requests")) for r in rows)
        tokens = sum(as_int(r.get("total_tokens")) for r in rows)
        merged.append({**node, "requests": requests, "total_tokens": tokens,
                       "avg_total_ms": round(weighted / requests, 2) if requests else None})
    return merged


def _tier_three(
    nodes: Sequence[Mapping[str, Any]], by_backend: Sequence[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], int]:
    """tier3: счётчики по egress-прокси (совпадение по подстроке) и сумма direct-запросов."""
    egress = [(as_str(first_truthy(r.get("egress_proxy"), "direct")), as_int(r.get("requests"))) for r in by_backend]
    merged = [
        {**node, "requests": sum(count for proxy, count in egress if any(m in proxy for m in node.get("match", ())))}
        for node in nodes
    ]
    return merged, sum(count for proxy, count in egress if proxy == "direct")


def build_architecture_flow(
    by_backend: Sequence[Mapping[str, Any]],
    callers: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
    topology: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """3 яруса: входящие клиенты -> L7-мосты протоколов -> L4/L7 egress-прокси, с живыми счётчиками."""
    topo = dict(first_truthy(topology, _env_json("BRIDGE_TELEMETRY_TOPOLOGY_JSON", D.BRIDGE_TELEMETRY_TOPOLOGY)))
    keys = ("tier1_entry_callers", "tier2_l7_bridges", "tier3_l4_egress_proxies")
    tier1, tier2, tier3 = (dict(topo[key]) for key in keys)
    tier1["nodes"] = _tier_one(tier1["nodes"], callers)
    tier2["nodes"] = _tier_two(tier2["nodes"], by_backend)
    tier3["nodes"], tier3["direct_requests"] = _tier_three(tier3["nodes"], by_backend)
    return {"total_requests": as_int(summary.get("total_requests")), "tier1_entry_callers": tier1,
            "tier2_l7_bridges": tier2, "tier3_l4_egress_proxies": tier3,
            "callers": tier1["nodes"], "bridges": tier2["nodes"], "egress": tier3["nodes"]}  # плоские алиасы для UI
