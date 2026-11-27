"""W0-A: unit-тесты чистого домена быстрого выхода из дрена (AD-001).

Покрывают fail-closed дефолты ``DrainFacts``, единственный чистый кейс
``fast_clean``, независимость предиката от ``end_marker``, каждый негативный
и граничный флаг по отдельности с точной причиной отказа, иммутабельность
контрактов и AST-чистоту домена (M-MOD-I3: ноль запрещённых I/O-импортов).
"""

from __future__ import annotations

import ast
import dataclasses
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_DIR = _ROOT / "bridges" / "agy-bridge"
if str(BRIDGE_DIR) not in sys.path:
    sys.path.append(str(BRIDGE_DIR))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agy_runtime.drain_fast_path_domain import (  # noqa: E402
    DrainFacts,
    DrainFastExitDecision,
    decide_fast_exit,
)

_DOMAIN_PATH = BRIDGE_DIR / "agy_runtime" / "drain_fast_path_domain.py"

# Канонические 24 запрещённых I/O-модуля (architecture.md §5.1, M-MOD-I3)
# плюс time/logging, явно запрещённые брифом волны W0-A.
FORBIDDEN_IMPORTS = frozenset(
    {
        "os",
        "sys",
        "socket",
        "ssl",
        "subprocess",
        "asyncio",
        "httpx",
        "aiohttp",
        "websockets",
        "requests",
        "urllib",
        "curl_cffi",
        "litestar",
        "sqlalchemy",
        "asyncpg",
        "psycopg",
        "sqlite3",
        "redis",
        "valkey",
        "aioboto3",
        "aiofiles",
        "pathlib",
        "shutil",
        "tempfile",
        "time",
        "logging",
    }
)
FORBIDDEN_CALLS = frozenset({"open", "input", "print", "eval", "exec", "__import__"})

_CLEAN: dict[str, object] = {
    "flag_enabled": True,
    "authoritative_read_done": True,
    "clean_rc": True,
    "pending_steps": 0,
    "buffered_events": 0,
    "has_tool_trace": False,
    "has_progressive_chunks": False,
    "failed": False,
    "interrupted": False,
    "stopped": False,
}


def test_default_facts_fail_closed() -> None:
    """Дефолтный ``DrainFacts()`` запрещает быстрый выход (fail-closed)."""
    facts = DrainFacts()
    assert facts == DrainFacts(
        flag_enabled=False,
        authoritative_read_done=False,
        clean_rc=False,
        pending_steps=1,
        buffered_events=1,
        has_tool_trace=True,
        has_progressive_chunks=True,
        failed=True,
        interrupted=True,
        stopped=False,
    )
    decision = decide_fast_exit(facts)
    assert decision.should_fast_exit is False
    assert decision.reason == "flag_disabled"


def test_clean_case_allows_fast_clean() -> None:
    """Полный набор чистых фактов даёт ``fast_clean`` детерминированно."""
    facts = DrainFacts(**_CLEAN)
    expected = DrainFastExitDecision(should_fast_exit=True, reason="fast_clean")
    assert decide_fast_exit(facts) == expected
    assert decide_fast_exit(facts) == expected


def test_end_marker_independence() -> None:
    """Предикат не зависит от end_marker: clean с ним и без него — fast_clean."""
    field_names = {f.name for f in dataclasses.fields(DrainFacts)}
    assert "end_marker" not in field_names
    with pytest.raises(TypeError):
        DrainFacts(**_CLEAN, end_marker="[END_TURN]")
    for extra in ({"end_marker": "[END_TURN]"}, {}):
        snapshot = {**_CLEAN, **extra}
        facts = DrainFacts(**{k: v for k, v in snapshot.items() if k in field_names})
        assert decide_fast_exit(facts) == DrainFastExitDecision(True, "fast_clean")


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"flag_enabled": False}, "flag_disabled"),
        ({"authoritative_read_done": False}, "no_authoritative_read"),
        ({"stopped": True}, "stopped"),
        ({"clean_rc": False}, "nonzero_rc"),
        ({"pending_steps": 1}, "pending_steps"),
        ({"pending_steps": -1}, "pending_steps"),
        ({"buffered_events": 1}, "buffered_events"),
        ({"buffered_events": -1}, "buffered_events"),
        ({"has_tool_trace": True}, "tool_trace"),
        ({"has_progressive_chunks": True}, "progressive_chunks"),
        ({"failed": True}, "failed"),
        ({"interrupted": True}, "interrupted"),
    ],
)
def test_single_violation_rejects_with_exact_reason(
    override: dict[str, object], reason: str
) -> None:
    """Каждый негативный/граничный флаг по отдельности даёт точную причину."""
    facts = DrainFacts(**{**_CLEAN, **override})
    decision = decide_fast_exit(facts)
    assert decision.should_fast_exit is False
    assert decision.reason == reason


def test_contracts_are_frozen_and_slotted() -> None:
    """Оба контракта — ``@dataclass(frozen=True, slots=True)`` (M-MOD-I4)."""
    for cls in (DrainFacts, DrainFastExitDecision):
        params = cls.__dataclass_params__
        assert params.frozen is True
        assert params.slots is True
    facts = DrainFacts()
    assert not hasattr(facts, "__dict__")
    with pytest.raises(dataclasses.FrozenInstanceError):
        facts.flag_enabled = True  # type: ignore[misc]
    decision = decide_fast_exit(facts)
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.reason = "mutated"  # type: ignore[misc]


def test_domain_ast_zero_io_imports_and_budgets() -> None:
    """AST-оракул: 0 запрещённых I/O-импортов, бюджеты строк и аргументов."""
    src = _DOMAIN_PATH.read_text(encoding="utf-8")
    assert len(src.splitlines()) <= 300
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in FORBIDDEN_IMPORTS
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in FORBIDDEN_IMPORTS
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in FORBIDDEN_CALLS
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert node.end_lineno is not None
            assert node.end_lineno - node.lineno + 1 <= 40, node.name
            args = node.args
            total = len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs)
            assert total <= 5, node.name
