"""Общие сборщики для тестов core/context_resilience (не собирается как тесты).

Содержит фабрики бюджетов/каталога/сообщений и НЕЗАВИСИМЫЙ структурный оракул:
он пересчитывает байты конечного тела отдельной простой функцией и не использует
весовую арифметику планировщика.
"""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import context_resilience as ctx  # noqa: E402


def passport(**kw: Any) -> ctx.Passport:
    return ctx.Passport(**kw)


def target(c: int = 100_000, r: int = 10_000, **pkw: Any) -> ctx.TargetBudget:
    return ctx.TargetBudget(c, r, ctx.Passport(**pkw))


def entry(
    c: int = 100_000,
    r: int = 10_000,
    *,
    protocol: str = "openai",
    enrolled: bool = True,
    model: str = "m",
    reasoning_policy: str = "preserve",
    **pkw: Any,
) -> ctx.RouteEntry:
    return ctx.RouteEntry(
        backend="b",
        ingress="i",
        route="/r",
        model=model,
        target=target(c, r, **pkw),
        protocol=protocol,
        enrolled=enrolled,
        reasoning_policy=reasoning_policy,
    )


def flags(pruner: bool = True, shadow: bool = False, revision: int = 1) -> ctx.Flags:
    return ctx.Flags(pruner, shadow, revision, "test")


def big(n: int, ch: str = "x") -> str:
    return ch * n


# ---- OpenAI ---------------------------------------------------------------


def oa(role: str, content: Any, **extra: Any) -> dict[str, Any]:
    return dict({"role": role, "content": content}, **extra)


def oa_tool_exchange(i: int, size: int, calls: int = 1) -> list[dict[str, Any]]:
    """assistant с `calls` параллельными вызовами + по результату на каждый."""
    ids = [f"call_{i}_{k}" for k in range(calls)]
    out: list[dict[str, Any]] = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": cid,
                    "type": "function",
                    "function": {"name": "f", "arguments": "{}"},
                }
                for cid in ids
            ],
        }
    ]
    for cid in ids:
        out.append({"role": "tool", "tool_call_id": cid, "content": big(size, "r")})
    return out


def oa_history(turns: int, size: int, *, tools: bool = True) -> list[dict[str, Any]]:
    """system + стартовый user + `turns` ходов (user/assistant[+tool]) + последний user."""
    msgs = [oa("system", "SYS-ANCHOR"), oa("user", "TASK-ANCHOR")]
    for i in range(turns):
        msgs.append(oa("assistant", f"a{i}-" + big(size, "a")))
        if tools:
            msgs.extend(oa_tool_exchange(i, size))
        msgs.append(oa("user", f"u{i}-" + big(size, "u")))
    msgs.append(oa("user", "LAST-USER"))
    return msgs


# ---- независимый оракул ----------------------------------------------------------


def raw_bytes(obj: Any) -> int:
    """Байты всех строк и ключей + len(str) примитивов; не зависит от ядра."""
    if isinstance(obj, str):
        return len(obj.encode("utf-8"))
    if isinstance(obj, dict):
        return sum(raw_bytes(k) + raw_bytes(v) for k, v in obj.items())
    if isinstance(obj, (list, tuple)):
        return sum(raw_bytes(v) for v in obj)
    return len(str(obj).lower()) if obj is not None else 4


def oracle_total(body: dict[str, Any], key: str = "messages", f_msg: int = 8) -> int:
    """Независимая верхняя оценка конечного тела: байты + F_msg на сообщение."""
    msgs = body[key]
    rest = {k: v for k, v in body.items() if k != key}
    return raw_bytes(rest) + sum(raw_bytes(m) + f_msg for m in msgs)


def tool_ids(msgs: list[dict[str, Any]]) -> tuple[set[str], set[str]]:
    provided: set[str] = set()
    needed: set[str] = set()
    for m in msgs:
        for c in m.get("tool_calls") or []:
            provided.add(c["id"])
        if m.get("role") == "tool":
            needed.add(m["tool_call_id"])
    return provided, needed


def count_marker(msgs: list[dict[str, Any]]) -> int:
    return sum(1 for m in msgs if m.get("content") == ctx.MARKER_TEXT)
