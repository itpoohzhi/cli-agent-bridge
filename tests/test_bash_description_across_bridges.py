"""Сквозные тесты сохранения и синтеза `description` у `bash`/`pwsh` во всех 6 путях."""

from __future__ import annotations

import importlib.util
import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from core.backend_adapter import TurnResult
from core.tool_emulation import (
    ToolCallParser,
    _parse_execute_block,
    build_tool_schemas,
)
from core.tool_mode import DEFAULT_EMULATE_SPEC

ROOT = Path(__file__).resolve().parents[1]

DSH_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "command": {"type": "string"},
                },
                "required": ["description", "command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pwsh",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "command": {"type": "string"},
                },
                "required": ["description", "command"],
            },
        },
    },
]

STRICT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    }
]


def _load_module(name: str, rel_path: str, env: dict[str, str] | None = None) -> Any:
    if name in sys.modules:
        return sys.modules[name]
    import os

    for k, v in (env or {}).items():
        os.environ.setdefault(k, v)
    path = ROOT / rel_path
    parent = str(path.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _tc_block(name: str, args: dict[str, Any]) -> str:
    return f"<tool_call>{json.dumps({'name': name, 'arguments': args})}</tool_call>"


def test_agy_bridge_tool_turn_preserves_and_synthesizes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRIDGE_SYNTHESIZE_REQUIRED_BASH_DESC_ENABLED", raising=False)
    agy = _load_module(
        "agy_bridge_bash_desc_test",
        "bridges/agy-bridge/server.py",
        {"AGY_BRIDGE_KEY": "test-key"},
    )
    emitted: list[dict[str, Any]] = []
    turn = agy._ToolTurn(DSH_TOOLS, lambda _c: True, lambda _r: True, lambda b: emitted.extend(b) or True)
    payload = _tc_block("bash", {"command": "ls", "description": "List files"}) + _tc_block(
        "bash", {"command": "pwd"}
    )
    for idx in range(0, len(payload), 7):
        turn.feed(payload[idx : idx + 7])
    turn.finish()
    assert len(emitted) == 2
    assert json.loads(emitted[0]["function"]["arguments"]) == {
        "command": "ls",
        "description": "List files",
    }
    args1 = json.loads(emitted[1]["function"]["arguments"])
    assert args1["command"] == "pwd"
    assert args1["description"].startswith("Run: pwd")


def test_claude_p_bridge_execution_preserves_description(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRIDGE_SYNTHESIZE_REQUIRED_BASH_DESC_ENABLED", raising=False)
    claude = _load_module(
        "claude_p_bridge_bash_desc_test",
        "bridges/claude-p-bridge/server.py",
        {"CLAUDE_BRIDGE_KEY": "test-key"},
    )
    calls: list[dict[str, Any]] = []
    callbacks = SimpleNamespace(
        on_text=lambda _t: True,
        on_reasoning=lambda _r: True,
        on_tool_call=lambda c: calls.append(c) or True,
        keepalive=None,
    )
    ex = claude._Execution(SimpleNamespace(), callbacks, DEFAULT_EMULATE_SPEC, DSH_TOOLS)
    ex.normalizer.feed_text(_tc_block("bash", {"command": "whoami", "description": "Show user"}))
    ex.normalizer.feed_text(_tc_block("bash", {"command": "date"}))
    ex.normalizer.finish()
    assert len(calls) == 2
    assert json.loads(calls[0]["function"]["arguments"]) == {
        "command": "whoami",
        "description": "Show user",
    }
    assert json.loads(calls[1]["function"]["arguments"])["description"].startswith("Run: date")


def test_muse_tool_parser_preserves_and_strips_per_schema() -> None:
    from core.tool_emulation import sanitize_tool_calls_list

    muse_tp = _load_module(
        "muse_runtime_tool_parser_test",
        "bridges/muse-bridge/muse_runtime/tool_parser.py",
    )
    dsh_schemas = build_tool_schemas(DSH_TOOLS)
    strict_schemas = build_tool_schemas(STRICT_TOOLS)
    block = _tc_block("bash", {"command": "ls", "description": "List", "toolSummary": "L"})
    _, calls_dsh = muse_tp._split_tool_calls([block], dsh_schemas, sanitize_tool_calls_list)
    assert json.loads(calls_dsh[0]["function"]["arguments"]) == {
        "command": "ls",
        "description": "List",
    }
    _, calls_strict = muse_tp._split_tool_calls([block], strict_schemas, sanitize_tool_calls_list)
    assert json.loads(calls_strict[0]["function"]["arguments"]) == {"command": "ls"}


def test_opencode_zen_bridge_preserves_description_and_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRIDGE_SYNTHESIZE_REQUIRED_BASH_DESC_ENABLED", raising=False)
    zen = _load_module(
        "opencode_zen_bash_desc_test",
        "bridges/opencode-zen-bridge/server.py",
        {"OPENCODE_ZEN_BRIDGE_KEY": "test-key"},
    )
    from core.turn_dispatch import ToolSchemaScope

    dsh_schemas = build_tool_schemas(DSH_TOOLS)
    strict_schemas = build_tool_schemas(STRICT_TOOLS)
    with ToolSchemaScope.bind(dsh_schemas):
        _, calls = zen._split_tool_calls(
            [_tc_block("bash", {"command": "ls", "description": "List", "summary": "S"})]
        )
        assert json.loads(calls[0]["function"]["arguments"]) == {
            "command": "ls",
            "description": "List",
        }
        _, synth_calls = zen._split_tool_calls([_tc_block("bash", {"command": "uname"})])
        assert json.loads(synth_calls[0]["function"]["arguments"])["description"].startswith(
            "Run: uname"
        )
    with ToolSchemaScope.bind(strict_schemas):
        _, strict_calls = zen._split_tool_calls(
            [_tc_block("bash", {"command": "ls", "description": "List"})]
        )
        assert json.loads(strict_calls[0]["function"]["arguments"]) == {"command": "ls"}


def test_server_dispatch_turn_and_tool_schema_scope_isolation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BRIDGE_SYNTHESIZE_REQUIRED_BASH_DESC_ENABLED", raising=False)
    import server
    from core.turn_dispatch import ToolSchemaScope

    dsh_schemas = build_tool_schemas(DSH_TOOLS)
    strict_schemas = build_tool_schemas(STRICT_TOOLS)
    raw = TurnResult(
        state="ok",
        rc=0,
        text=_tc_block("bash", {"command": "ls", "description": "List", "toolSummary": "T"})
        + _tc_block("pwsh", {"command": "Get-Date", "summary": "Current date"}),
    )

    class _DummyAdapter:
        id = "dummy"
        kind = "muse"

        def execute_turn(self, _turn: Any, _sse: Any = None) -> TurnResult:
            assert ToolSchemaScope.get_current() == dsh_schemas
            return raw

    monkeypatch.setattr(server, "BACKENDS", {"dummy_bash_desc": _DummyAdapter()})
    ctx = {
        "backend": "dummy_bash_desc",
        "model": "m",
        "effort": "high",
        "prompt": "p",
        "emulate_tools": True,
        "tool_schemas": dsh_schemas,
        "rpc": {"system": "", "runnable": True, "items": []},
        "images": [],
        "tag": "t",
    }
    handler = server.Handler.__new__(server.Handler)
    handler.connection = None
    out = handler._dispatch(ctx, lambda: True)
    assert ToolSchemaScope.get_current() is None
    assert json.loads(out["tool_calls"][0]["function"]["arguments"]) == {
        "command": "ls",
        "description": "List",
    }
    assert json.loads(out["tool_calls"][1]["function"]["arguments"]) == {
        "command": "Get-Date",
        "description": "Current date",
    }

    errors: list[BaseException] = []

    def worker(schemas: dict[str, Any]) -> None:
        try:
            with ToolSchemaScope.bind(schemas):
                assert ToolSchemaScope.get_current() == schemas
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    t1 = threading.Thread(target=worker, args=(dsh_schemas,))
    t2 = threading.Thread(target=worker, args=(strict_schemas,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert not errors
    assert ToolSchemaScope.get_current() is None


def test_xml_execute_and_invoke_preserve_summary_and_respect_schemas() -> None:
    dsh_schemas = build_tool_schemas(DSH_TOOLS)
    strict_schemas = build_tool_schemas(STRICT_TOOLS)

    parsed = _parse_execute_block(
        "<execute><command>ls -la</command><summary>List files</summary></execute>",
        tool_schemas=dsh_schemas,
    )
    assert parsed is not None
    assert parsed[0] == {
        "name": "bash",
        "arguments": {"command": "ls -la", "description": "List files"},
    }

    calls_dsh: list[dict[str, Any]] = []
    p_dsh = ToolCallParser(lambda _t: None, calls_dsh.append, tool_schemas=dsh_schemas)
    xml = '<invoke name="bash"><parameter name="command">pwd</parameter><summary>Show cwd</summary></invoke>'
    for idx in range(0, len(xml), 5):
        p_dsh.feed(xml[idx : idx + 5])
    p_dsh.finish()
    assert calls_dsh[0]["arguments"] == {"command": "pwd", "description": "Show cwd"}

    calls_strict: list[dict[str, Any]] = []
    p_strict = ToolCallParser(lambda _t: None, calls_strict.append, tool_schemas=strict_schemas)
    p_strict.feed(xml)
    p_strict.finish()
    assert calls_strict[0]["arguments"] == {"command": "pwd"}
