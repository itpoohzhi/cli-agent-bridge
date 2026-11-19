"""Контрактные red-repro тесты REQ-001, REQ-004, REQ-005 (волна W0-A)."""

from __future__ import annotations

import importlib.util
import inspect
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

from adapters.passthrough_adapter import PassthroughLimits, ToolCallAccumulator
from core.tool_emulation import (
    StreamNormalizer,
    _canonical_tool_invocation,
    build_tool_schemas,
    sanitize_tool_call,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BRIDGE_PY = _REPO_ROOT / "bridges" / "agy-bridge" / "server.py"

_DSH_BASH_TOOLS: list[dict[str, Any]] = [
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
    }
]

_STRICT_BASH_TOOLS: list[dict[str, Any]] = [
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


def _load_bridge() -> Any:
    """Загрузить bridges/agy-bridge/server.py без сокетов и подпроцессов."""
    mod_name = "agy_bridge_server_dsh_contract_test"
    cached = sys.modules.get(mod_name)
    if cached is not None:
        return cached
    os.environ.setdefault("AGY_BRIDGE_KEY", "test-key-dsh-contracts")
    spec = importlib.util.spec_from_file_location(mod_name, _BRIDGE_PY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


def _make_normalizer(schemas: dict[str, Any] | None) -> StreamNormalizer:
    params = inspect.signature(StreamNormalizer.__init__).parameters
    if "tool_schemas" in params:
        kwargs: dict[str, Any] = {"tool_schemas": schemas}
        return StreamNormalizer(strict_live=True, **kwargs)
    return StreamNormalizer(strict_live=True)


def _canonicalize(
    name: str, arguments: dict[str, Any], schemas: dict[str, Any] | None
) -> tuple[str, dict[str, Any]]:
    params = inspect.signature(_canonical_tool_invocation).parameters
    if "tool_schemas" in params:
        fn: Any = _canonical_tool_invocation
        return fn(name, arguments, tool_schemas=schemas)
    return _canonical_tool_invocation(name, arguments)


def _bash_block(command: str, description: str, extra: str = "") -> str:
    payload = {"command": command, "description": description}
    if extra:
        payload["toolSummary"] = extra
    body = json.dumps({"name": "bash", "arguments": payload})
    return f"<tool_call>{body}</tool_call>"


def test_bash_preserves_description_for_dsh_schema() -> None:
    """REQ-001: DSH-схема bash(required=[description, command]) хранит поле."""
    schemas = build_tool_schemas(_DSH_BASH_TOOLS)
    norm = _make_normalizer(schemas)
    norm.feed_text(_bash_block("ls -la", "List directory", extra="Listing"))
    norm.finish()
    assert len(norm.tool_calls) == 1
    raw_call = norm.tool_calls[0]
    openai_call = {
        "id": "call_1",
        "type": "function",
        "function": {
            "name": raw_call["name"],
            "arguments": json.dumps(raw_call["arguments"], ensure_ascii=False),
        },
    }
    sanitized = sanitize_tool_call(openai_call, schemas)
    args = json.loads(sanitized[0]["function"]["arguments"])
    assert args == {"command": "ls -la", "description": "List directory"}


def test_bash_strips_undeclared_description_when_strict_schema_omits_it() -> None:
    """REQ-001: строгая схема без description вырезает description и toolSummary."""
    init_params = inspect.signature(StreamNormalizer.__init__).parameters
    assert "tool_schemas" in init_params
    schemas = build_tool_schemas(_STRICT_BASH_TOOLS)
    norm = _make_normalizer(schemas)
    norm.feed_text(_bash_block("pwd", "Print working dir", extra="Cwd"))
    norm.finish()
    assert len(norm.tool_calls) == 1
    assert norm.tool_calls[0]["arguments"] == {"command": "pwd"}
    name, args = _canonicalize(
        "bash",
        {"command": "pwd", "description": "Print working dir", "summary": "Cwd"},
        schemas,
    )
    assert name == "bash"
    assert args == {"command": "pwd"}


def test_bash_preserves_description_for_unresolvable_schema() -> None:
    """REQ-01: при неразрешимой схеме ($ref) и tool_schemas=None description сохраняется."""
    ref_schemas = build_tool_schemas(
        [{"type": "function", "function": {"name": "bash", "parameters": {"$ref": "#/$defs/Bash"}}}]
    )
    name, args = _canonicalize(
        "bash",
        {
            "command": "echo ok",
            "description": "Echo status",
            "toolSummary": "internal",
            "summary": "internal2",
        },
        ref_schemas,
    )
    assert name == "bash"
    assert args == {"command": "echo ok", "description": "Echo status"}
    _, none_args = _canonicalize(
        "bash",
        {"command": "ls", "description": "y", "toolSummary": "x", "summary": "list"},
        None,
    )
    assert none_args == {"command": "ls", "description": "y"}
    _, promoted = _canonicalize(
        "bash",
        {"command": "ls", "toolSummary": "List dir", "summary": "ignored"},
        None,
    )
    assert promoted == {"command": "ls", "description": "List dir"}


def test_agy_tool_turn_accepts_34_parallel_calls_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """REQ-004 + REQ-01: пачка из 34 вызовов сохраняет description в каждом вызове."""
    monkeypatch.delenv("AGY_MAX_TOOL_CALLS", raising=False)
    bridge = _load_bridge()
    emitted: list[dict[str, Any]] = []
    turn = bridge._ToolTurn(
        _DSH_BASH_TOOLS,
        lambda _c: True,
        lambda _r: True,
        lambda batch: emitted.extend(batch) or True,
    )
    blocks = "\n".join(_bash_block(f"echo {i}", f"step {i}") for i in range(34))
    turn.feed(blocks)
    turn.finish()
    assert turn.error == ""
    assert len(turn.calls) == 34
    assert len(emitted) == 34
    for i, call in enumerate(emitted):
        assert json.loads(call["function"]["arguments"]) == {
            "command": f"echo {i}",
            "description": f"step {i}",
        }


def test_bash_synthesizes_required_description_and_protects_custom_synonym(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """REQ-01: fallback-синтез required description (default True) и защита EXEC_SYNONYMS."""
    from core.tool_call_schema_policy import canonicalize_tool_invocation

    schemas = build_tool_schemas(_DSH_BASH_TOOLS)
    custom = build_tool_schemas(
        [{"type": "function", "function": {"name": "execute", "parameters": {"type": "object"}}}]
    )
    cname, cargs = canonicalize_tool_invocation("execute", {"command": "id"}, custom)
    assert (cname, cargs) == ("execute", {"command": "id"})

    monkeypatch.delenv("BRIDGE_SYNTHESIZE_REQUIRED_BASH_DESC_ENABLED", raising=False)
    bridge = _load_bridge()
    emitted: list[dict[str, Any]] = []
    turn = bridge._ToolTurn(_DSH_BASH_TOOLS, lambda _c: True, lambda _r: True, lambda b: emitted.extend(b) or True)
    turn.feed('<tool_call>{"name": "bash", "arguments": {"command": "git status -s"}}</tool_call>')
    turn.finish()
    args_on = json.loads(emitted[0]["function"]["arguments"])
    assert args_on["command"] == "git status -s" and args_on["description"].startswith("Run: git status -s")

    monkeypatch.setenv("BRIDGE_SYNTHESIZE_REQUIRED_BASH_DESC_ENABLED", "0")
    emitted_off: list[dict[str, Any]] = []
    turn_off = bridge._ToolTurn(_DSH_BASH_TOOLS, lambda _c: True, lambda _r: True, lambda b: emitted_off.extend(b) or True)
    turn_off.feed('<tool_call>{"name": "bash", "arguments": {"command": "git status -s"}}</tool_call>')
    turn_off.finish()
    assert json.loads(emitted_off[0]["function"]["arguments"]) == {"command": "git status -s"}
    _ = schemas


def test_agy_tool_turn_limit_exceeded_returns_distinct_error_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """REQ-004: превышение AGY_MAX_TOOL_CALLS даёт tool_call_limit_exceeded."""
    monkeypatch.setenv("AGY_MAX_TOOL_CALLS", "2")
    bridge = _load_bridge()
    turn = bridge._ToolTurn(
        _DSH_BASH_TOOLS,
        lambda _c: True,
        lambda _r: True,
        lambda _batch: True,
    )
    blocks = "\n".join(_bash_block(f"echo {i}", f"step {i}") for i in range(3))
    turn.feed(blocks)
    turn.finish()
    assert turn.error != ""
    body = turn.error_body()
    assert body["code"] == 502
    assert body["type"] == "tool_call_limit_exceeded"
    assert "malformed" not in str(body["message"]).lower()


def test_passthrough_accumulator_supports_over_64_parallel_calls() -> None:
    """REQ-004: ToolCallAccumulator и PassthroughLimits согласуются выше 64."""
    limits = PassthroughLimits.from_env({"BRIDGE_MAX_PARALLEL_CALLS": "80"})
    assert limits.max_parallel_calls == 80
    assert limits.accumulator_max_keys >= 80
    acc = ToolCallAccumulator(limits)
    deltas = [
        {
            "index": i,
            "id": f"call_{i}",
            "type": "function",
            "function": {"name": "bash", "arguments": '{"command":"pwd"}'},
        }
        for i in range(70)
    ]
    acc.add(0, deltas)
    assert len(acc.pop_choice(0)) == 70
    explicit = PassthroughLimits.from_env(
        {"BRIDGE_MAX_PARALLEL_CALLS": "80", "BRIDGE_ACCUMULATOR_MAX_KEYS": "96"}
    )
    assert explicit.accumulator_max_keys == 96


def test_health_reports_live_tool_emulation_and_max_tool_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """REQ-005: GET /health отдаёт живые tool_emulation=True и max_tool_calls=64."""
    monkeypatch.delenv("AGY_MAX_TOOL_CALLS", raising=False)
    bridge = _load_bridge()
    handler = bridge.Handler.__new__(bridge.Handler)
    handler.path = "/health"
    captured: list[tuple[int, dict[str, Any]]] = []
    monkeypatch.setattr(
        handler,
        "_send",
        lambda code, body, **_kw: captured.append((code, dict(body))),
    )
    handler.do_GET()
    assert len(captured) == 1
    status, payload = captured[0]
    assert status == 200
    assert payload["tool_emulation"] is True
    assert payload["max_tool_calls"] == 64
