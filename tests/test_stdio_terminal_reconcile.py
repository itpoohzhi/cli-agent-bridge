"""W0-B: unit-тесты реконсиляции terminal-текста (AD-004, M-MOD-I1..I5).

Покрывают точный дубль, многофрагментное накопление, суффиксный хвост,
расходящийся terminal, сохранность полей кадра, fail-open при переполнении
бюджета, выключенный режим, allowlist протоколов и AST-чистоту модуля
(M-MOD-I3: ноль запрещённых I/O-импортов).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from core.stdio_resident.protocol_driver import DecodedChunk
from core.stdio_resident.terminal_reconcile import (
    DEFAULT_MAX_ACCUM_BYTES,
    RECONCILE_PROTOCOLS,
    TerminalTextReconciler,
    should_reconcile_protocol,
)
from core.turn_usage import UsageUpdate

_MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "stdio_resident"
    / "terminal_reconcile.py"
)

# Канонические 24 запрещённых I/O-модуля (architecture.md §5.1, M-MOD-I3)
# плюс time/logging, явно запрещённые брифом волны W0-B.
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


def _progressive(text: str) -> DecodedChunk:
    """Progressive-кадр с текстовой дельтой."""
    return DecodedChunk(text=text)


def _terminal(text: str) -> DecodedChunk:
    """Terminal-кадр с полным текстом ответа."""
    return DecodedChunk(text=text, is_terminal=True)


def test_exact_duplicate_terminal_text_cleared() -> None:
    """Точный дубль: итог 'PONG', terminal пуст, без 'PONGPONG'."""
    reconciler = TerminalTextReconciler()
    progressive = _progressive("PONG")
    assert reconciler.apply(progressive) is progressive
    terminal = _terminal("PONG")
    result = reconciler.apply(terminal)
    assert result.text == ""
    assert result.is_terminal is True
    assert progressive.text + result.text == "PONG"
    assert "PONGPONG" not in progressive.text + result.text
    # Входной кадр не мутируется: replace возвращает копию.
    assert terminal.text == "PONG"
    assert result is not terminal


def test_multi_chunk_progressive_accumulation() -> None:
    """Накопление 'PO' + 'NG' снимает дубль с terminal 'PONG'."""
    reconciler = TerminalTextReconciler()
    assert reconciler.apply(_progressive("PO")).text == "PO"
    assert reconciler.apply(_progressive("NG")).text == "NG"
    assert reconciler.apply(_terminal("PONG")).text == ""


def test_suffix_tail_keeps_only_remainder() -> None:
    """Terminal 'Hello world' при накопленном 'Hello ' даёт хвост 'world'."""
    reconciler = TerminalTextReconciler()
    reconciler.apply(_progressive("Hello "))
    result = reconciler.apply(_terminal("Hello world"))
    assert result.text == "world"
    assert result.is_terminal is True


def test_divergent_terminal_untouched() -> None:
    """Расходящийся terminal 'xyz' при накопленном 'abc' нетронут."""
    reconciler = TerminalTextReconciler()
    reconciler.apply(_progressive("abc"))
    terminal = _terminal("xyz")
    assert reconciler.apply(terminal) is terminal
    assert terminal.text == "xyz"


def test_shorter_terminal_prefix_of_accum_untouched() -> None:
    """Terminal короче накопленного ('PO' против 'PONG') — без изменений."""
    reconciler = TerminalTextReconciler()
    reconciler.apply(_progressive("PONG"))
    terminal = _terminal("PO")
    assert reconciler.apply(terminal) is terminal


def test_terminal_fields_preserved_on_dedupe() -> None:
    """Дубль снят, но tool_calls/reasoning/usage/error/флаги сохранены."""
    tool_calls = [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "ping", "arguments": "{}"},
        }
    ]
    usage = UsageUpdate(input_tokens=10, output_tokens=4, source="test")
    raw = {"type": "done"}
    terminal = DecodedChunk(
        text="PONG",
        reasoning="мысль",
        tool_calls=tool_calls,
        is_terminal=True,
        is_tool_stop=True,
        raw=raw,
        error="retry_hint",
        usage=usage,
    )
    reconciler = TerminalTextReconciler()
    reconciler.apply(_progressive("PONG"))
    result = reconciler.apply(terminal)
    assert result.text == ""
    assert result.reasoning == "мысль"
    assert result.tool_calls == tool_calls
    assert result.usage is usage
    assert result.error == "retry_hint"
    assert result.is_terminal is True
    assert result.is_tool_stop is True
    assert result.raw is raw
    # Исходный кадр не изменён.
    assert terminal.text == "PONG"


def test_empty_terminal_and_no_accum_passthrough() -> None:
    """Пустой terminal и terminal без накопления проходят без изменений."""
    reconciler = TerminalTextReconciler()
    empty = _terminal("")
    assert reconciler.apply(empty) is empty
    reconciler.apply(_progressive("PONG"))
    assert reconciler.apply(empty) is empty
    fresh = TerminalTextReconciler()
    lone = _terminal("PONG")
    assert fresh.apply(lone) is lone
    assert lone.text == "PONG"


def test_overflow_cap_fail_open() -> None:
    """Бюджет 8 байт: переполнение -> passthrough, terminal не обрезается."""
    reconciler = TerminalTextReconciler(max_accum_bytes=8)
    first = _progressive("12345")  # 5 байт — помещается
    assert reconciler.apply(first) is first
    overflow = _progressive("6789")  # 5 + 4 = 9 > 8 — fail-open
    assert reconciler.apply(overflow) is overflow
    late = _progressive("x")
    assert reconciler.apply(late) is late
    terminal = _terminal("123456789")
    assert reconciler.apply(terminal) is terminal
    assert terminal.text == "123456789"


def test_utf8_bytes_counted_and_exact_cap_fits() -> None:
    """Бюджет считается в байтах UTF-8; точное равенство бюджету допустимо."""
    reconciler = TerminalTextReconciler(max_accum_bytes=8)
    # 'абвг' = 4 символа * 2 байта = 8 байт — ровно бюджет, помещается.
    reconciler.apply(_progressive("абвг"))
    assert reconciler.apply(_terminal("абвг")).text == ""
    tight = TerminalTextReconciler(max_accum_bytes=8)
    tight.apply(_progressive("абвг"))
    tight.apply(_progressive("д"))  # 8 + 2 = 10 > 8 — переполнение
    terminal = _terminal("абвгд")
    assert tight.apply(terminal) is terminal


def test_disabled_reconciler_passthrough() -> None:
    """enabled=False: progressive и terminal проходят нетронутыми."""
    reconciler = TerminalTextReconciler(enabled=False)
    progressive = _progressive("PONG")
    terminal = _terminal("PONG")
    assert reconciler.apply(progressive) is progressive
    assert reconciler.apply(terminal) is terminal
    assert terminal.text == "PONG"


@pytest.mark.parametrize(
    ("protocol", "expected"),
    [
        ("agy-stream-json", True),
        ("codex-jsonl", False),
        ("claude-stream-json", False),
        ("stream-json", False),
        (None, False),
    ],
)
def test_should_reconcile_protocol_allowlist(
    protocol: str | None, expected: bool
) -> None:
    """Allowlist: только 'agy-stream-json', остальные и None — False."""
    assert should_reconcile_protocol(protocol) is expected


def test_constants_contract() -> None:
    """Константы allowlist и бюджета соответствуют брифу W0-B."""
    assert RECONCILE_PROTOCOLS == frozenset({"agy-stream-json"})
    assert DEFAULT_MAX_ACCUM_BYTES == 4 * 1024 * 1024


def test_module_ast_purity_zero_io() -> None:
    """M-MOD-I3: модуль не импортирует запрещённые I/O-модули и не зовёт I/O."""
    tree = ast.parse(_MODULE_PATH.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in FORBIDDEN_CALLS
    assert not imported & FORBIDDEN_IMPORTS


def test_module_line_budget() -> None:
    """Бюджет брифа: оба файла волны <= 300 физических строк."""
    test_path = Path(__file__).resolve()
    assert len(_MODULE_PATH.read_text(encoding="utf-8").splitlines()) <= 300
    assert len(test_path.read_text(encoding="utf-8").splitlines()) <= 300
